#!/usr/bin/env python3
"""发布后建档、认平台作品、抓 12 小时和 7 天的数据、抓评论原话、写复盘、列出到点没抓的。

  python3 stats.py check                                   # TikHub 密钥读没读到、余额多少（免费接口，不扣钱）
  python3 stats.py fetch <作品链接>                        # 抓一条抖音、小红书作品现在的点赞收藏评论转发（播放拿得到才有）
  python3 stats.py comments <作品链接> --max 50            # 抓公开评论原话（复盘用）
  python3 stats.py account --platform 抖音 --url <主页链接>   # 记下你自己的主页链接（认作品用，只要记一次）
  python3 stats.py create --title 标题 --published "2026-10-07 20:00" --id T001 ...   # 建档（重复调用不重复建）
  python3 stats.py link --archive <档案> --url <作品链接>   # 记下一个平台的作品（用户贴的链接）
  python3 stats.py find --archive <档案> --platform 抖音    # 到你主页最近的作品里认出这条
  python3 stats.py record --archive <档案> --point 12h      # 到点抓数，写进 数据.jsonl、内容.md 和已发布总览
  python3 stats.py due                                      # 列出到点还没抓的观察点
  python3 stats.py overview                                 # 重新生成 已发布/00_已发布总览.md
  python3 stats.py review --archive <档案> --file 复盘.md   # 用户说行了以后，把复盘写进 内容.md
  python3 stats.py mark-published --id T001 --date 2026-10-07   # 选题总览改「已发布」、选题卡挪到「已做」

每个命令加 -h 看参数。--workfolder 不写时按 Skill 里「先找到工作文件夹」的顺序找。
退出码：0 成功；2 有问题（原因已经说了）；3 要先问用户、用户同意后才能继续。
只用 Python 自带的模块。TikHub 的密钥只在这个程序里用，不打印、不写进任何文件。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from closeout_kit import NeedsAgreement, UserError  # noqa: E402
from closeout_kit import archive as A  # noqa: E402
from closeout_kit import fetch as F  # noqa: E402
from closeout_kit import match as M  # noqa: E402
from closeout_kit import places as PL  # noqa: E402
from closeout_kit import platforms as P  # noqa: E402
from closeout_kit import tikhub as T  # noqa: E402
from closeout_kit import topics as TP  # noqa: E402
from closeout_kit.text import money, now_iso, write_text  # noqa: E402

ENV = os.environ
NUMBERS = (("plays", "播放"), ("likes", "点赞"), ("collects", "收藏"), ("comments", "评论"), ("shares", "转发"))


def say(text=""):
    print(text)


def now_of(args):
    if getattr(args, "now", None):
        value = A.parse_when(args.now)
        if not value:
            raise UserError("--now 的时间读不出来：%s（写成 2026-10-08 09:30）。" % args.now)
        return value
    return datetime.now().replace(second=0, microsecond=0)


def session_for(workfolder):
    hidden = PL.hidden_dir(workfolder) if workfolder else None
    return F.Session(hidden=hidden, env=ENV)


def rel(workfolder, path):
    try:
        inner = os.path.relpath(path, workfolder)
        if workfolder and not inner.startswith(".."):
            return inner
    except ValueError:
        pass
    return path


def target_of(link):
    t = P.parse_target(link)
    if not t.get("url") and not t.get("id"):
        raise UserError("认不出这个链接：%s。把作品的完整链接（或者 App 里「复制链接」得到的那段文字）发我。" % link)
    return t


# ---------- check / fetch / comments ----------

def cmd_check(args):
    key, where = T.read_key(ENV)
    if not key:
        say(T.no_key_message())
        return 2
    workfolder = PL.find_workfolder(ENV)
    ledger = T.Ledger(os.path.join(PL.hidden_dir(workfolder), "用量.jsonl") if workfolder else None)
    client = T.Client(key, base=T.base_url(ENV), ledger=ledger, prices=T.prices_for(ENV))
    info = client.account()
    say("已读到 TikHub 密钥（%s），能用。" % where)
    if info["balance"] is not None or info["free_credit"] is not None:
        say("账户余额：%s；试用额度：%s。抖音接口每次约 0.001 美元；小红书接口每次 0.01 美元，而且只能用充值的余额。"
            % (money(info["balance"] or 0), money(info["free_credit"] or 0)))
    if info.get("email_verified") is False:
        say("TikHub 账号的邮箱还没验证，有些接口会被拒，去 TikHub 网站验证一下。")
    if not info.get("key_active", True):
        say("这个密钥在 TikHub 上是停用状态，去 TikHub 网站的密钥页面看一下。")
    say("今天已经花了约 %s（单次自动上限 %s，当天自动上限 %s；超过、或者用小红书接口，都先问用户）。"
        % (money(ledger.spent_today()), money(T.AUTO_LIMIT), money(T.DAILY_LIMIT)))
    return 0


def _numbers_line(work):
    parts = []
    for key, label in NUMBERS:
        parts.append("%s %s" % (label, A.number(work.get(key))))
    return "  ".join(parts)


def cmd_fetch(args):
    target = target_of(args.link)
    workfolder = PL.find_workfolder(ENV)
    session = session_for(workfolder)
    session.start(F.work_plan(target), args.agreed_budget)
    work = F.fetch_work(session, target)
    if args.json:
        say(json.dumps(work, ensure_ascii=False, indent=2))
        return 0
    say("%s｜%s" % (work["platform"], work.get("title") or "（没有标题）"))
    say("链接：%s" % work.get("url"))
    say("发布时间：%s；时长：%s；作者：%s" % (work.get("published_at") or "没读到",
                                     "%s 秒" % work["duration_seconds"] if work.get("duration_seconds") else "没读到", work.get("author") or "没读到"))
    say(_numbers_line(work))
    if work.get("plays") is None:
        say("播放数拿不到（平台公开接口不给，只有作者后台看得到），写「—」，不当成 0。")
    say("这次花了约 %s。" % money(session.spent()))
    return 0


def cmd_comments(args):
    target = target_of(args.link)
    if args.max < 1:
        raise UserError("--max 至少是 1。")
    workfolder = PL.find_workfolder(ENV)
    session = session_for(workfolder)
    session.start(F.comments_plan(target, args.max), args.agreed_budget)
    rows, info, notes = F.fetch_comments(session, target, args.max)
    collected = now_iso()
    result = {"collected_at": collected, "work": info, "comments": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows],
              "note": "".join(notes) or None, "cost_usd": str(session.spent())}
    if args.save:
        write_text(os.path.abspath(args.save), json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if args.json:
        say(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    say("%s 抓的公开评论（%s），一共 %d 条（含平台附带的回复）；平台显示评论数：%s。"
        % (collected[:16].replace("T", " "), info.get("url") or "", len(rows), A.number(info.get("comment_count"))))
    if not rows:
        say("暂无评论（评论区可能关了，或者还没人评论）。")
    for r in rows:
        tags = ["点赞 %s" % A.number(r.get("likes"))]
        if r.get("ip"):
            tags.append(r["ip"])
        if r.get("time"):
            tags.append(r["time"])
        if r.get("by_author"):
            tags.append("作者本人")
        prefix = "  - 回复：" if r.get("level") == "回复" else "- "
        say("%s「%s」（%s）" % (prefix, r.get("text") or "", "，".join(tags)))
    for note in notes:
        say(note)
    if args.save:
        say("原话存在：%s" % os.path.abspath(args.save))
    say("这次花了约 %s。" % money(session.spent()))
    return 0


# ---------- 我的账号 ----------

def accounts_path(workfolder):
    return os.path.join(PL.published_dir(workfolder), PL.ACCOUNTS_NAME)


def read_accounts(workfolder):
    path = accounts_path(workfolder)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().split("\n")
    _head, rows, _s, _e = A.read_table(lines)
    out = {}
    for row in rows:
        url = P.extract_url(row.get("主页链接", ""))
        if row.get("平台") and url:
            out[row["平台"]] = url
    return out


def cmd_account(args):
    workfolder = PL.workfolder_or_die(args.workfolder, ENV)
    accounts = read_accounts(workfolder)
    if args.url:
        url = P.extract_url(args.url)
        platform = args.platform or P.detect_platform(args.url)
        if not url or platform not in A.PLATFORMS:
            raise UserError("认不出这是哪个平台的主页链接：%s。抖音是 douyin.com/user/…，小红书是 xiaohongshu.com/user/profile/…；视频号 TikHub 拉不到，不用记。" % args.url)
        accounts[platform] = url
        lines = ["# 我的账号", "",
                 "> 发布后认作品用：jc-publish-closeout 会到这些主页的最近作品里找刚发的那条。主页链接变了直接改这张表。", ""]
        lines += A.table_lines(("平台", "主页链接"), [{"平台": k, "主页链接": v} for k, v in sorted(accounts.items())])
        write_text(accounts_path(workfolder), "\n".join(lines) + "\n")
        say("记下了你的%s主页：%s（存在 %s）。" % (platform, url, rel(workfolder, accounts_path(workfolder))))
        return 0
    if not accounts:
        say("还没记你的主页链接。请用户贴一次各平台主页链接（浏览器地址栏里的那个），用 account --platform 抖音 --url <链接> 存下。")
        return 0
    for platform, url in sorted(accounts.items()):
        say("%s：%s" % (platform, url))
    return 0


# ---------- 建档 ----------

def _demote(text):
    """复盘、逐字稿里的一级、二级标题降成三级，免得把 内容.md 的节拆乱。"""
    return re.sub(r"^#{1,2} ", "### ", text, flags=re.M)


def _read_file(path, what):
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read().strip()
    except OSError as e:
        raise UserError("读不了%s文件 %s：%s" % (what, path, e))
    if not text:
        raise UserError("%s文件是空的：%s" % (what, path))
    return text


def cmd_create(args):
    workfolder = PL.workfolder_or_die(args.workfolder, ENV)
    now = now_of(args)
    published = A.parse_when(args.published)
    if not published:
        raise UserError("发布时间读不出来：%s。写成「2026-10-07 20:00」；不确定几点就问用户一句。" % args.published)
    title = re.sub(r"\s+", " ", args.title or "").strip()
    if not title:
        raise UserError("要有标题（--title）。")
    content_id = (args.id or "").strip().upper() or None
    if content_id and not re.fullmatch(r"T\d{3,4}", content_id):
        raise UserError("T 编号要写成 T001 这样：%s" % args.id)
    date = published.strftime("%Y-%m-%d")
    platforms = [p.strip() for p in re.split(r"[,，、\s]+", args.platforms or "") if p.strip()] or list(A.PLATFORMS)
    for p in platforms:
        if p not in A.PLATFORMS:
            raise UserError("平台只认：%s。「%s」不认识。" % ("、".join(A.PLATFORMS), p))
    facts = {"T 编号": content_id or "", "标题": title, "简介": args.intro or "", "封面文字": args.cover_text or "",
             "发布时间": A.fmt(published), "时长": "%s 秒" % _plain(args.duration) if args.duration else ""}
    existing = A.find_existing(workfolder, content_id, title, date)
    notes = []
    if existing:
        path = existing
        archive = A.Archive(path)
        notes.append("这条已经建过档了，没重复建：%s" % rel(workfolder, path))
        for key, value in facts.items():
            if not value:
                continue
            changed, old = A.set_fact(archive.parts, key, value)
            if not changed and old and A._norm(old) != A._norm(value):
                notes.append("「%s」档案里已经是「%s」，和这次给的「%s」不一样，没改；要改就直接改 内容.md。" % (key, old, value))
        known = [r["平台"] for r in archive.links()]
        for p in platforms:
            if p not in known:
                archive.set_link(p, 状态=A.STATUS_EXPECTED)
    else:
        os.makedirs(PL.published_dir(workfolder), exist_ok=True)
        path = os.path.join(PL.published_dir(workfolder), A.folder_name(date, title))
        if os.path.exists(path):
            raise UserError("「已发布」里已经有同名文件夹但不是这条的档案：%s。先看一眼是怎么回事。" % path)
        os.makedirs(path)
        write_text(os.path.join(path, A.CONTENT), A.new_content(facts, platforms))
        open(os.path.join(path, A.DATA), "a").close()
        archive = A.Archive(path)
        notes.append("建好了档案：%s" % rel(workfolder, path))
    if args.cover:
        name, note = A.copy_cover(path, os.path.abspath(os.path.expanduser(args.cover)))
        A.set_fact(archive.parts, "封面", "[%s](%s)" % (name, name))
        notes.append(note)
    if args.video:
        video = os.path.abspath(os.path.expanduser(args.video))
        if not os.path.isfile(video):
            notes.append("成片路径不存在：%s，没记。" % video)
        else:
            A.set_fact(archive.parts, "成片", "%s（没复制进档案）" % video)
    if args.transcript:
        text = _demote(_read_file(args.transcript, "逐字稿"))
        old = "\n".join(A.section(archive.parts, "完整逐字稿") or []).strip()
        if not old or old.startswith(A.NO_TRANSCRIPT):
            A.set_section(archive.parts, "完整逐字稿（校正版）", ["", text, ""])
            notes.append("逐字稿写进去了。")
        elif A._norm(old) == A._norm(text):
            notes.append("逐字稿和档案里的一样，没改。")
        elif args.replace_transcript:
            backup = archive.backup(now)
            A.set_section(archive.parts, "完整逐字稿（校正版）", ["", text, ""])
            notes.append("逐字稿换成了新的，旧的 内容.md 备份在 %s。" % rel(workfolder, backup))
        else:
            notes.append("档案里已经有逐字稿，和这次给的不一样，没覆盖；确定要换就加 --replace-transcript。")
    archive.refresh_data(now)
    archive.save()
    overview, _n = A.render_overview(workfolder, now)
    notes.append("已发布总览更新了：%s" % rel(workfolder, overview))
    if content_id:
        notes.extend(TP.mark_published(workfolder, content_id, date, args.topics_overview))
    for note in notes:
        say(note)
    say("下一步：认出各平台的作品（用户贴的链接用 link，没贴就用 find 到主页里找）。认出以后，12 小时、7 天两个到点时间会写在 内容.md 的「数据」一节。")
    say("档案：%s" % path)
    return 0


def _plain(value):
    return ("%.1f" % float(value)).rstrip("0").rstrip(".")


def cmd_mark_published(args):
    workfolder = PL.workfolder_or_die(args.workfolder, ENV)
    content_id = args.id.strip().upper()
    for note in TP.mark_published(workfolder, content_id, args.date, args.topics_overview):
        say(note)
    return 0


# ---------- 认作品 ----------

def _duration_of(text):
    m = re.search(r"\d+(?:\.\d+)?", str(text or ""))
    return float(m.group(0)) if m else None


def _archive(args):
    workfolder = PL.find_workfolder(ENV) if not getattr(args, "workfolder", None) else PL.workfolder_or_die(args.workfolder, ENV)
    path = PL.archive_dir(args.archive, workfolder)
    return A.Archive(path), PL.workfolder_of_archive(path) or workfolder


def _save(archive, workfolder, now):
    archive.refresh_data(now)
    archive.save()
    if workfolder:
        A.render_overview(workfolder, now)


def cmd_link(args):
    archive, workfolder = _archive(args)
    now = now_of(args)
    url = P.extract_url(args.url) if args.url else None
    platform = args.platform or (P.detect_platform(args.url) if args.url else None)
    if platform not in A.PLATFORMS:
        raise UserError("要说清是哪个平台（--platform 抖音 / 小红书 / 视频号），或者给一个认得出的作品链接。")
    if args.status in (A.STATUS_SKIP, A.STATUS_NOT_FOUND, A.STATUS_EXPECTED):
        archive.set_link(platform, 状态=args.status, 怎么认的=args.how or "")
        _save(archive, workfolder, now)
        say("%s 记成「%s」。" % (platform, args.status))
        return 0
    if not url and platform != F.WECHAT:
        raise UserError("要有作品链接（--url）。用户还没贴的话，用 find 到他主页最近的作品里找。")
    published, duration, title = A.parse_when(args.published), args.duration, None
    if url and platform in F.SUPPORTED and not args.no_fetch and (not published or not duration):
        session = session_for(workfolder)
        target = target_of(url)
        session.start(F.work_plan(target), args.agreed_budget)
        work = F.fetch_work(session, target)
        published = published or A.parse_when(work.get("published_at"))
        duration = duration or work.get("duration_seconds")
        title = work.get("title")
        url = work.get("url") or url
        say("从平台读到：%s｜发布时间 %s｜时长 %s（花了约 %s）。" % (title or "（没有标题）", work.get("published_at") or "没读到",
                                                     "%s 秒" % _plain(duration) if duration else "没读到", money(session.spent())))
    how = args.how or ("用户贴的链接" if url else "用户说已发")
    if not published:
        fallback = A.parse_when(archive.facts().get("发布时间"))
        if not fallback:
            raise UserError("不知道%s是什么时候发的：加 --published「2026-10-07 20:00」，或者先在 内容.md 的「发布时间」写上。" % platform)
        published = fallback
        how += "；发布时间按档案里写的"
    old = archive.link(platform)
    if old and old.get("状态") == A.STATUS_FOUND and old.get("链接") and url and P.canonical_link(old["链接"]) != P.canonical_link(url):
        say("注意：%s 原来记的是 %s，这次改成 %s。" % (platform, old["链接"], url))
    archive.set_link(platform, 状态=A.STATUS_FOUND, 链接=P.canonical_link(url) if url and platform in F.SUPPORTED else (url or "（用户说已发，没有链接）"),
                     发布时间=A.fmt(published), 时长="%s 秒" % _plain(duration) if duration else "", 怎么认的=how)
    _save(archive, workfolder, now)
    say("%s 记下了：发布时间 %s。12 小时观察点 %s，7 天观察点 %s。" % (platform, A.fmt(published), A.fmt(archive.target(platform, "12h")),
                                                       A.fmt(archive.target(platform, "7d"))))
    return 0


def cmd_find(args):
    archive, workfolder = _archive(args)
    now = now_of(args)
    platform = args.platform
    if platform == F.WECHAT:
        raise UserError("视频号 TikHub 拉不到作品列表。请用户确认视频号发了没有、几点发的，用 link --platform 视频号 --published … 记下；有链接就一起给。")
    if platform not in F.SUPPORTED:
        raise UserError("find 只能找抖音和小红书。")
    if not workfolder:
        raise UserError("这个档案不在工作文件夹的「已发布」里，找不到「我的账号」。")
    home = read_accounts(workfolder).get(platform)
    if not home:
        raise UserError("还没记你的%s主页链接。请用户贴一次自己的%s主页链接（浏览器地址栏里的那个），用 account --platform %s --url <链接> 存下，以后就不用再贴了。"
                        "或者这次直接贴作品链接，用 link 记。" % (platform, platform, platform))
    facts = archive.facts()
    title, published, duration = facts.get("标题"), A.parse_when(facts.get("发布时间")), _duration_of(facts.get("时长"))
    target = P.parse_target(home)
    session = session_for(workfolder)
    session.start(F.own_works_plan(platform, target.get("user_id"), args.max), args.agreed_budget)
    works = F.fetch_own_works(session, platform, home, target.get("user_id"), args.max)
    result = M.judge(works, title, published, duration)
    say("在你%s主页最近 %d 条作品里找「%s」（花了约 %s）：" % (platform, len(works), title, money(session.spent())))
    for i, (total, parts, work) in enumerate(result["candidates"], 1):
        say("%d. %s｜%s｜时长 %s｜像不像 %.2f（%s）｜%s" % (i, work.get("title") or "（没有标题）", work.get("published_at") or "时间没读到",
                                                 "%s 秒" % _plain(work["duration_seconds"]) if work.get("duration_seconds") else "没读到",
                                                 total, M.describe(parts), work.get("url")))
    if result["verdict"] == "认定":
        work = result["best"]
        say("认定是第 1 条。")
        if args.apply:
            archive.set_link(platform, 状态=A.STATUS_FOUND, 链接=work["url"], 发布时间=work.get("published_at") or A.fmt(published),
                             时长="%s 秒" % _plain(work["duration_seconds"]) if work.get("duration_seconds") else "",
                             怎么认的="从主页最近作品里按标题、发布时间、时长认出（%s）" % M.describe(result["candidates"][0][1]))
            _save(archive, workfolder, now)
            say("记进档案了。12 小时观察点 %s，7 天观察点 %s。" % (A.fmt(archive.target(platform, "12h")), A.fmt(archive.target(platform, "7d"))))
        return 0
    if result["verdict"] == "拿不准":
        say("拿不准是哪一条。把上面几条给用户看，问一次是哪条（都不是也可以）；用户挑好用 link --url <那条的链接> 记下，都不是就先不记。")
        return 0
    say("没找到像的作品：可能还在审核、刚发还没出现在列表里，或者标题改得很多。过几个小时再找一次，或者请用户直接贴作品链接。")
    return 0


# ---------- 抓数 ----------

def _manual_numbers(args):
    values = {}
    for key, _label in NUMBERS:
        value = getattr(args, key)
        if value is not None:
            if value < 0:
                raise UserError("数不能是负的：%s" % key)
            values[key] = value
    return values


def cmd_record(args):
    archive, workfolder = _archive(args)
    now = now_of(args)
    point = args.point
    label = A.POINTS[point][0]
    manual = _manual_numbers(args)
    if (manual or args.missed) and not args.platform:
        raise UserError("手动记数或者记「没采到」时，要用 --platform 说清是哪个平台。")
    found = archive.found_platforms()
    if args.platform:
        if args.platform not in found:
            raise UserError("档案里%s还没认出作品（「平台链接」表里不是「已找到」），先用 link 或 find 记下作品，再记数。" % args.platform)
        platforms = [args.platform]
    else:
        platforms = found
        if not platforms:
            raise UserError("档案里还没有认出任何平台的作品，先用 link 或 find 记下作品。")
    collected = A.parse_when(args.collected_at) if args.collected_at else now
    if args.collected_at and not collected:
        raise UserError("--collected-at 读不出来：%s" % args.collected_at)
    written, asked, failed, waiting, skipped = [], [], [], [], []
    session = None
    for platform in platforms:
        target = archive.target(platform, point)
        if not target:
            failed.append("%s：「平台链接」表里没有发布时间，算不出到点时间。" % platform)
            continue
        prev = archive.latest(platform, point)
        if prev and prev.get("status") in ("ok", "missed") and not args.again:
            skipped.append("%s %s已经记过了（%s），不重复记。" % (platform, label, prev.get("collected_at") or prev.get("note") or ""))
            continue
        if collected < target and not args.missed:
            waiting.append("%s %s还没到（到点 %s），现在抓的数不能算%s的数。" % (platform, label, A.fmt(target), label))
            continue
        base = {"platform": platform, "point": point, "target_at": A.fmt(target), "recorded_at": now_iso(),
                "link": (archive.link(platform) or {}).get("链接", "")}
        if args.missed:
            archive.append_record(dict(base, status="missed", note=args.missed, source=args.source or ""))
            written.append("%s %s记成没采到：%s。" % (platform, label, args.missed))
            continue
        if manual:
            record = dict(base, status="ok", collected_at=A.fmt(collected), delay=A.delay_text(point, target, collected),
                          delay_minutes=int((collected - target).total_seconds() // 60), source=args.source or "用户报数")
            for key, _l in NUMBERS:
                record[key] = manual.get(key)
            archive.append_record(record)
            written.append("%s %s：%s（%s，来源：%s）。" % (platform, label, _numbers_line(record), record["delay"], record["source"]))
            continue
        link = base["link"]
        if platform not in F.SUPPORTED:
            failed.append("%s %s：%s到点 %s。" % (platform, label, str(F.unsupported(platform)), A.fmt(target)))
            continue
        try:
            if session is None:
                session = session_for(workfolder)
            spec = target_of(link)
            session.start(F.work_plan(spec), args.agreed_budget)
            work = F.fetch_work(session, spec)
        except NeedsAgreement as e:
            asked.append("%s %s：%s" % (platform, label, e))
            continue
        except UserError as e:
            if session is None:
                raise
            failed.append("%s %s没抓到：%s" % (platform, label, e))
            continue
        at = now
        record = dict(base, status="ok", collected_at=A.fmt(at), delay=A.delay_text(point, target, at),
                      delay_minutes=int((at - target).total_seconds() // 60), source="TikHub",
                      work_id=work.get("id"), title=work.get("title"))
        for key, _l in NUMBERS:
            record[key] = work.get(key)
        archive.append_record(record)
        written.append("%s %s：%s（%s，来源：TikHub）。" % (platform, label, _numbers_line(record), record["delay"]))
    if written:
        _save(archive, workfolder, now)
    for group in (written, skipped, waiting, failed, asked):
        for line in group:
            say(line)
    if session is not None and session.spent():
        say("这次花了约 %s。" % money(session.spent()))
    if written:
        say("写进了 %s 和 内容.md 的「数据」一节，已发布总览也更新了。" % A.DATA)
    if asked:
        return 3
    if failed and not written:
        return 2
    return 0


# ---------- 到点没抓的 / 总览 / 复盘 ----------

def cmd_due(args):
    workfolder = PL.workfolder_or_die(args.workfolder, ENV)
    now = now_of(args)
    if not PL.list_archives(workfolder):
        say("还没有已发布的档案。")
        return 0
    result = A.due_items(workfolder, now)
    if args.json:
        say(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if result["due"]:
        say("到点还没抓的数据（%d 项）：" % len(result["due"]))
        for e in result["due"]:
            say("- %s %s %s：%s 到点，已经过了 %s" % (e["label"], e["platform"], e["point_label"], e["target_at"], e["late"]))
    else:
        say("没有到点要抓的数据。")
    if result["waiting"]:
        say("还没认出作品的平台（发布 3 天内）：")
        for w in result["waiting"]:
            say("- %s：%s" % (w["label"], "、".join(w["platforms"])))
    if result["review"]:
        say("7 天数据齐了、还没复盘：%s" % "；".join(r["label"] for r in result["review"]))
    if result["next"]:
        n = result["next"]
        say("下一个到点：%s %s %s %s" % (n["target_at"], n["label"], n["platform"], n["point_label"]))
    return 0


def cmd_overview(args):
    workfolder = PL.workfolder_or_die(args.workfolder, ENV)
    path, count = A.render_overview(workfolder, now_of(args))
    say("已发布总览更新了（%d 条）：%s" % (count, path))
    return 0


def cmd_review(args):
    archive, workfolder = _archive(args)
    now = now_of(args)
    text = _demote(_read_file(args.file, "复盘"))
    text = re.sub(r"^###\s*复盘\s*\n", "", text).strip()
    backup = archive.backup(now)
    A.set_section(archive.parts, "复盘", ["", "> 复盘于 %s，用户看过、同意后写入。" % now.strftime("%Y-%m-%d"), "", text, ""])
    _save(archive, workfolder, now)
    say("复盘写进了 %s 的「复盘」一节；旧的 内容.md 备份在 %s。已发布总览这一行标了「已复盘」。"
        % (rel(workfolder, archive.content_path) if workfolder else archive.content_path, rel(workfolder, backup) if workfolder else backup))
    return 0


# ---------- 命令行 ----------

def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--now", help=argparse.SUPPRESS)  # 测试用：把「现在」固定成某个时间
    money_opt = argparse.ArgumentParser(add_help=False)
    money_opt.add_argument("--agreed-budget", type=float, help="用户在对话里明确同意的花费上限（美元）。超过默认上限、或者用小红书接口时要带")

    ap = argparse.ArgumentParser(description="发布后建档、抓 12 小时和 7 天的数据、写复盘。")
    sub = ap.add_subparsers(dest="command")

    sub.add_parser("check", parents=[common], help="TikHub 密钥读没读到、余额多少（免费）").set_defaults(func=cmd_check)

    f = sub.add_parser("fetch", parents=[common, money_opt], help="抓一条作品现在的数据")
    f.add_argument("link")
    f.add_argument("--json", action="store_true")
    f.set_defaults(func=cmd_fetch)

    c = sub.add_parser("comments", parents=[common, money_opt], help="抓公开评论原话")
    c.add_argument("link")
    c.add_argument("--max", type=int, default=50, help="最多几条一级评论，默认 50；超过 200 要先问用户")
    c.add_argument("--json", action="store_true")
    c.add_argument("--save", help="把评论原话存成 JSON 文件")
    c.set_defaults(func=cmd_comments)

    a = sub.add_parser("account", parents=[common], help="记下或查看你自己的各平台主页链接")
    a.add_argument("--workfolder")
    a.add_argument("--platform", choices=A.PLATFORMS)
    a.add_argument("--url")
    a.set_defaults(func=cmd_account)

    cr = sub.add_parser("create", parents=[common], help="建档（重复调用不重复建）")
    cr.add_argument("--workfolder")
    cr.add_argument("--title", required=True, help="发出去的真实标题")
    cr.add_argument("--published", required=True, help="发布时间，比如 2026-10-07 20:00")
    cr.add_argument("--id", help="T 编号，比如 T001；有就顺手把选题总览改成「已发布」")
    cr.add_argument("--intro", help="简介（发布时的配文）")
    cr.add_argument("--cover-text", help="封面上的文字")
    cr.add_argument("--cover", help="封面图路径（复制进档案，不动原件）")
    cr.add_argument("--video", help="成片路径（只记路径，不复制）")
    cr.add_argument("--duration", type=float, help="成片时长（秒），认作品时用")
    cr.add_argument("--transcript", help="校正版逐字稿文件")
    cr.add_argument("--replace-transcript", action="store_true", help="档案里已有逐字稿时也换成新的（旧的先备份）")
    cr.add_argument("--platforms", default="抖音,小红书,视频号", help="打算发哪些平台，默认 抖音,小红书,视频号")
    cr.add_argument("--topics-overview", help="选题总览的位置，默认 <工作文件夹>/选题库/00_选题总览.md")
    cr.set_defaults(func=cmd_create)

    mp = sub.add_parser("mark-published", parents=[common], help="选题总览改「已发布」、选题卡挪到「已做」")
    mp.add_argument("--workfolder")
    mp.add_argument("--id", required=True)
    mp.add_argument("--date", help="发布日期 YYYY-MM-DD（选题总览「发布日期」空着才填）")
    mp.add_argument("--topics-overview")
    mp.set_defaults(func=cmd_mark_published)

    li = sub.add_parser("link", parents=[common, money_opt], help="记下一个平台的作品")
    li.add_argument("--archive", required=True, help="档案文件夹（「已发布」里的文件夹名或完整路径）")
    li.add_argument("--workfolder")
    li.add_argument("--url", help="作品链接（用户贴的，或者 find 找到的）")
    li.add_argument("--platform", choices=A.PLATFORMS)
    li.add_argument("--published", help="这个平台的发布时间；不写就从平台读")
    li.add_argument("--duration", type=float)
    li.add_argument("--how", help="怎么认出来的，比如「用户贴的链接」「用户挑的第 2 条」")
    li.add_argument("--status", choices=(A.STATUS_SKIP, A.STATUS_NOT_FOUND, A.STATUS_EXPECTED), help="不是记作品，而是把这个平台记成不发、没找到或预计发布")
    li.add_argument("--no-fetch", action="store_true", help="不去平台读发布时间和时长")
    li.set_defaults(func=cmd_link)

    fi = sub.add_parser("find", parents=[common, money_opt], help="到你主页最近的作品里认出这条")
    fi.add_argument("--archive", required=True)
    fi.add_argument("--workfolder")
    fi.add_argument("--platform", required=True, choices=A.PLATFORMS)
    fi.add_argument("--max", type=int, default=20, help="看最近几条，默认 20")
    fi.add_argument("--apply", action="store_true", help="认定了就直接记进档案")
    fi.set_defaults(func=cmd_find)

    r = sub.add_parser("record", parents=[common, money_opt], help="到点抓数，写进档案")
    r.add_argument("--archive", required=True)
    r.add_argument("--workfolder")
    r.add_argument("--point", required=True, choices=tuple(A.POINTS))
    r.add_argument("--platform", choices=A.PLATFORMS, help="只记这个平台；不写就把认出了作品的平台都抓一遍")
    for key, label in NUMBERS:
        r.add_argument("--" + key, type=int, help="手动记的%s数" % label)
    r.add_argument("--source", help="手动记数的来源，比如「视频号助手截图」「用户报数」")
    r.add_argument("--collected-at", help="手动记数时，截图或看数的时间（默认现在）")
    r.add_argument("--missed", help="这个观察点没采到，写原因；以后 due 不再提醒")
    r.add_argument("--again", action="store_true", help="已经记过也再记一行（总表取最后一行）")
    r.set_defaults(func=cmd_record)

    d = sub.add_parser("due", parents=[common], help="列出到点还没抓的观察点")
    d.add_argument("--workfolder")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=cmd_due)

    o = sub.add_parser("overview", parents=[common], help="重新生成已发布总览")
    o.add_argument("--workfolder")
    o.set_defaults(func=cmd_overview)

    rv = sub.add_parser("review", parents=[common], help="把用户看过的复盘写进 内容.md")
    rv.add_argument("--archive", required=True)
    rv.add_argument("--workfolder")
    rv.add_argument("--file", required=True, help="复盘全文（Markdown）")
    rv.set_defaults(func=cmd_review)
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 2
    try:
        return args.func(args) or 0
    except NeedsAgreement as e:
        print(str(e))
        return e.exit_code
    except UserError as e:
        print(str(e))
        return e.exit_code
    except KeyboardInterrupt:
        print("停下了。")
        return 130
    except Exception:  # 程序自己的问题：给 AI 看完整的出错位置（里面没有密钥）
        import traceback
        print("脚本出错了，这是程序的问题，不是操作的问题。出错位置：")
        traceback.print_exc(file=sys.stdout)
        return 1


if __name__ == "__main__":
    sys.exit(main())
