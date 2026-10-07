"""一条视频一个档案：已发布/YYYY-MM-DD-标题/ 里的 内容.md、数据.jsonl、封面；还有 已发布/00_已发布总览.md。

内容.md 是给人看的，各节用「## 」分开：发布事实、平台链接、数据、完整逐字稿（校正版）、复盘。
- 「数据」一节由脚本按 数据.jsonl 重新生成（两行标记中间），别手改；别的节可以直接改，脚本只改它负责的那一行或那张表。
- 「平台链接」表是各平台发布时间的唯一出处：12 小时、7 天两个观察点的到点时间都从这里算。
- 数据.jsonl 一次抓数一行，只追加，不改旧行。
"""
import json
import os
import re
import shutil
from datetime import datetime, timedelta

from . import UserError
from . import places as PL
from .text import safe_name, write_text

CONTENT = "内容.md"
DATA = "数据.jsonl"
HISTORY = ".history"
PLATFORMS = ("抖音", "小红书", "视频号")
POINTS = {"12h": ("12 小时", timedelta(hours=12)), "7d": ("7 天", timedelta(days=7))}
LATE = {"12h": timedelta(hours=2), "7d": timedelta(hours=12)}  # 晚过这么久，在表里标「偏晚」
FACT_KEYS = ("T 编号", "标题", "简介", "封面文字", "发布时间", "时长", "封面", "成片")
LINK_HEAD = ("平台", "状态", "链接", "发布时间", "时长", "怎么认的")
STATUS_FOUND, STATUS_EXPECTED, STATUS_NOT_FOUND, STATUS_SKIP = "已找到", "预计发布", "没找到", "不发"
DATA_START = "<!-- 数据表开始：由 stats.py 按 数据.jsonl 生成，手改会被下次覆盖 -->"
DATA_END = "<!-- 数据表结束 -->"
NO_TRANSCRIPT = "（还没有：用 jc-zhuanxie 对成片转写、校正后放这里）"
NO_REVIEW = "（还没复盘）"
SECTIONS = ("发布事实", "平台链接", "数据", "完整逐字稿（校正版）", "复盘")
TIME_FMT = "%Y-%m-%d %H:%M"


# ---------- 时间 ----------

def parse_when(text):
    """「2026-10-07 20:00」「2026-10-07T20:00:00+08:00」「2026/10/7 20:00」→ 不带时区的本地时间；读不出返回 None。"""
    text = str(text or "").strip()
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if value.tzinfo is not None:
            value = value.astimezone().replace(tzinfo=None)
        return value.replace(second=0, microsecond=0)
    except ValueError:
        pass
    m = re.match(r"^(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?(?:[ T]+(\d{1,2})[:：时](\d{1,2}))?", text)
    if m:
        y, mo, d, h, mi = m.groups()
        try:
            return datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0))
        except ValueError:
            return None
    return None


def fmt(value):
    return value.strftime(TIME_FMT) if value else ""


def span(delta):
    """一段时间说成人话：1 天 2 小时、3 小时 5 分钟、12 分钟。"""
    minutes = int(abs(delta.total_seconds()) // 60)
    days, rest = divmod(minutes, 24 * 60)
    hours, mins = divmod(rest, 60)
    if days:
        return "%d 天 %d 小时" % (days, hours) if hours else "%d 天" % days
    if hours:
        return "%d 小时 %d 分钟" % (hours, mins) if mins else "%d 小时" % hours
    return "%d 分钟" % mins


def delay_text(point, target, collected):
    delta = collected - target
    if delta.total_seconds() < 0:
        return "早 %s" % span(delta)
    text = "晚 %s" % span(delta)
    if delta > LATE[point]:
        text += "，偏晚"
    return text


# ---------- 读写 内容.md ----------

def split_sections(text):
    """→ [(标题或 None, 这一节的行)]。第一个「## 」之前的部分标题是 None。"""
    parts, title, lines = [], None, []
    for line in text.split("\n"):
        if line.startswith("## "):
            parts.append((title, lines))
            title, lines = line[3:].strip(), []
        else:
            lines.append(line)
    parts.append((title, lines))
    return parts


def join_sections(parts):
    out = []
    for title, lines in parts:
        if title is not None:
            out.append("## " + title)
        out.extend(lines)
    return "\n".join(out)


def section(parts, name):
    for title, lines in parts:
        if title is not None and title.startswith(name):
            return lines
    return None


def set_section(parts, name, lines):
    for i, (title, _old) in enumerate(parts):
        if title is not None and title.startswith(name):
            parts[i] = (title, lines)
            return parts
    parts.append((name, lines))
    return parts


_FACT = re.compile(r"^-\s*\*\*(.+?)\*\*[:：]\s*(.*)$")


def read_facts(parts):
    facts = {}
    for line in section(parts, "发布事实") or []:
        m = _FACT.match(line.strip())
        if m:
            facts[m.group(1).strip()] = m.group(2).strip()
    return facts


def set_fact(parts, key, value, overwrite=False):
    """改一行事实：原来空着才填（overwrite 时照改）。返回 (改了没有, 原来的值)。"""
    lines = section(parts, "发布事实")
    if lines is None:
        lines = [""]
        set_section(parts, "发布事实", lines)
    for i, line in enumerate(lines):
        m = _FACT.match(line.strip())
        if m and m.group(1).strip() == key:
            old = m.group(2).strip()
            if old and not overwrite:
                return False, old
            lines[i] = "- **%s**：%s" % (key, value)
            return old != value, old
    fact_lines = [i for i, l in enumerate(lines) if _FACT.match(l.strip())]
    lines.insert(fact_lines[-1] + 1 if fact_lines else len(lines), "- **%s**：%s" % (key, value))
    return True, ""


def _cells(line):
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def _is_rule(cells):
    return cells and all(re.fullmatch(r":?-+:?", c or "-") for c in cells)


def read_table(lines):
    """一节里的第一张表 → (表头, [行 dict], 表在第几行开始, 第几行结束)。没有表返回 (None, [], None, None)。"""
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|"):
            start = i
            break
    if start is None:
        return None, [], None, None
    end = start
    while end < len(lines) and lines[end].strip().startswith("|"):
        end += 1
    head = _cells(lines[start])
    rows = []
    for line in lines[start + 1:end]:
        cells = _cells(line)
        if _is_rule(cells):
            continue
        rows.append({h: (cells[i] if i < len(cells) else "") for i, h in enumerate(head)})
    return head, rows, start, end


def table_lines(head, rows):
    out = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    for row in rows:
        out.append("| " + " | ".join(_cell(row.get(h, "")) for h in head) + " |")
    return out


def _cell(value):
    return str(value if value is not None else "").replace("|", "／").replace("\n", " ").strip()


class Archive(object):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.content_path = os.path.join(self.path, CONTENT)
        self.data_path = os.path.join(self.path, DATA)
        with open(self.content_path, encoding="utf-8-sig") as f:
            self.text = f.read()
        self.parts = split_sections(self.text)

    @property
    def name(self):
        return os.path.basename(self.path)

    def facts(self):
        return read_facts(self.parts)

    def links(self):
        head, rows, _s, _e = read_table(section(self.parts, "平台链接") or [])
        return [r for r in rows if r.get("平台")] if head else []

    def link(self, platform):
        for row in self.links():
            if row.get("平台") == platform:
                return row
        return None

    def set_link(self, platform, **values):
        lines = section(self.parts, "平台链接")
        if lines is None:
            lines = [""]
            set_section(self.parts, "平台链接", lines)
        head, rows, start, end = read_table(lines)
        if head is None:
            head, rows, start, end = list(LINK_HEAD), [], len(lines), len(lines)
            lines.extend(["", ""])
        for h in LINK_HEAD:
            if h not in head:
                head.append(h)
        row = next((r for r in rows if r.get("平台") == platform), None)
        if row is None:
            row = {h: "" for h in head}
            row["平台"] = platform
            rows.append(row)
        for key, value in values.items():
            if value is not None:
                row[key] = str(value)
        lines[start:end] = table_lines(head, rows)

    def records(self):
        out = []
        if not os.path.isfile(self.data_path):
            return out
        with open(self.data_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict):
                    out.append(item)
        return out

    def latest(self, platform, point):
        """这个平台这个观察点最后记的那一行（采到的或者记了没采到的）。"""
        found = None
        for item in self.records():
            if item.get("platform") == platform and item.get("point") == point:
                found = item
        return found

    def append_record(self, record):
        with open(self.data_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def published_at(self, platform):
        row = self.link(platform)
        return parse_when(row.get("发布时间")) if row else None

    def target(self, platform, point):
        when = self.published_at(platform)
        return when + POINTS[point][1] if when else None

    def found_platforms(self):
        return [r["平台"] for r in self.links() if r.get("状态") == STATUS_FOUND]

    def waiting_platforms(self):
        return [r["平台"] for r in self.links() if r.get("状态") in (STATUS_EXPECTED, "")]

    def review_state(self):
        lines = section(self.parts, "复盘") or []
        body = "\n".join(lines).strip()
        if not body or body.startswith(NO_REVIEW):
            return None
        m = re.search(r"复盘于\s*(\d{4}-\d{2}-\d{2})", body)
        return m.group(1) if m else "有"

    def refresh_data(self, now):
        lines = data_section_lines(self, now)
        set_section(self.parts, "数据", lines)

    def save(self):
        text = join_sections(self.parts)
        if not text.endswith("\n"):
            text += "\n"
        write_text(self.content_path, text)
        self.text = text

    def backup(self, now):
        folder = os.path.join(self.path, HISTORY)
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, "内容_%s.md" % now.strftime("%Y%m%d-%H%M%S"))
        n = 2
        while os.path.exists(target):
            target = os.path.join(folder, "内容_%s-%d.md" % (now.strftime("%Y%m%d-%H%M%S"), n))
            n += 1
        shutil.copy2(self.content_path, target)
        return target


def number(value):
    return "—" if value is None else str(value)


def data_section_lines(archive, now):
    rows = []
    head = ("平台", "观察点", "目标时间", "实际采集时间", "晚了多久", "播放", "点赞", "收藏", "评论", "转发", "来源")
    for platform in archive.found_platforms():
        for point, (label, _delta) in POINTS.items():
            target = archive.target(platform, point)
            row = {"平台": platform, "观察点": label, "目标时间": fmt(target) or "（发布时间没填）"}
            item = archive.latest(platform, point)
            if item and item.get("status") == "ok":
                row.update({"实际采集时间": item.get("collected_at", ""), "晚了多久": item.get("delay", ""),
                            "播放": number(item.get("plays")), "点赞": number(item.get("likes")), "收藏": number(item.get("collects")),
                            "评论": number(item.get("comments")), "转发": number(item.get("shares")), "来源": item.get("source", "")})
            elif item and item.get("status") == "missed":
                row.update({"实际采集时间": "没采到：%s" % (item.get("note") or "原因没写"), "来源": item.get("source", "")})
            elif target and now < target:
                row["实际采集时间"] = "还没到"
            elif target:
                row["实际采集时间"] = "到点了，还没抓"
            rows.append(row)
    out = ["", DATA_START]
    if rows:
        out.extend(table_lines(head, rows))
        out.append("")
        out.append("「晚了多久」是实际采集时间比目标时间晚多少；标了「偏晚」的数不能当准点的数去比。拿不到的数写「—」，不当成 0。")
    else:
        out.append("还没有认出任何平台的作品，认出以后这里会列出 12 小时、7 天两个观察点的到点时间。")
    waiting = archive.waiting_platforms()
    if waiting:
        out.append("")
        out.append("还没认出作品的平台：%s（认出以后才有到点时间；预计发布不等于已经发布）。" % "、".join(waiting))
    out.append(DATA_END)
    out.append("")
    return out


# ---------- 建档 ----------

def folder_name(date, title):
    return "%s-%s" % (date, safe_name(title, limit=30))


def new_content(facts, platforms):
    lines = ["# %s" % facts.get("标题", "未命名"), "",
             "> 这份档案由 jc-publish-closeout 建立。「数据」一节由脚本按 数据.jsonl 重新生成，别手改；其他各节可以直接改。", "",
             "## 发布事实", ""]
    for key in FACT_KEYS:
        lines.append("- **%s**：%s" % (key, facts.get(key, "")))
    lines += ["", "## 平台链接", ""]
    rows = [{"平台": p, "状态": STATUS_EXPECTED} for p in platforms]
    lines += table_lines(LINK_HEAD, rows)
    lines += ["", "「状态」写：预计发布 / 已找到 / 没找到 / 不发。只有真的找到作品才写「已找到」。", "",
              "## 数据", "", DATA_START, DATA_END, "",
              "## 完整逐字稿（校正版）", "", NO_TRANSCRIPT, "",
              "## 复盘", "", NO_REVIEW, ""]
    return "\n".join(lines)


def find_existing(workfolder, content_id=None, title=None, date=None):
    for path in PL.list_archives(workfolder):
        try:
            facts = Archive(path).facts()
        except OSError:
            continue
        if content_id and facts.get("T 编号", "").strip() == content_id:
            return path
        if title and date and _norm(facts.get("标题")) == _norm(title) and str(facts.get("发布时间", ""))[:10] == date:
            return path
    return None


def _norm(text):
    return re.sub(r"\s+", "", str(text or ""))


def copy_cover(archive_path, source):
    """复制封面进档案（不移动原件）。档案里已经有不一样的封面时不覆盖，返回 (档案里的文件名, 说明)。"""
    if not os.path.isfile(source):
        raise UserError("找不到封面文件：%s" % source)
    ext = os.path.splitext(source)[1].lower() or ".png"
    target = os.path.join(archive_path, "封面" + ext)
    if os.path.exists(target):
        with open(target, "rb") as a, open(source, "rb") as b:
            if a.read() == b.read():
                return os.path.basename(target), "封面已经在档案里了"
        return os.path.basename(target), "档案里已经有一张不一样的封面，没覆盖；要换，先把旧的挪进回收站再来"
    shutil.copy2(source, target)
    return os.path.basename(target), "封面复制进档案了（原件没动）"


# ---------- 已发布总览 ----------

def overview_path(workfolder):
    return os.path.join(PL.published_dir(workfolder), PL.OVERVIEW_NAME)


def _seven_day_cell(archive, platform, now):
    row = archive.link(platform)
    if not row:
        return "—"
    status = row.get("状态", "")
    if status == STATUS_SKIP:
        return "不发"
    if status != STATUS_FOUND:
        return "没认出" if status == STATUS_NOT_FOUND else "还没认出"
    item = archive.latest(platform, "7d")
    if item and item.get("status") == "ok":
        return "%s／%s" % (number(item.get("likes")), number(item.get("collects")))
    if item and item.get("status") == "missed":
        return "没采到"
    target = archive.target(platform, "7d")
    if target and now < target:
        return "未满 7 天"
    return "到点没抓"


def _link_path(name):
    return name.replace("%", "%25").replace(" ", "%20") + "/" + CONTENT


def render_overview(workfolder, now):
    items = []
    for path in PL.list_archives(workfolder):
        try:
            archive = Archive(path)
        except OSError:
            continue
        facts = archive.facts()
        date = str(facts.get("发布时间", ""))[:10] or archive.name[:10]
        review = archive.review_state()
        items.append((date, archive.name, [
            date, facts.get("标题", "") or archive.name, facts.get("T 编号", "") or "—",
            _seven_day_cell(archive, "抖音", now), _seven_day_cell(archive, "小红书", now), _seven_day_cell(archive, "视频号", now),
            ("已复盘 %s" % review if review and review != "有" else "已复盘") if review else "还没复盘",
            "[内容.md](%s)" % _link_path(archive.name)]))
    items.sort(key=lambda x: (x[0], x[1]), reverse=True)
    head = ("发布日期", "标题", "T 编号", "抖音 7 天 点赞／收藏", "小红书 7 天 点赞／收藏", "视频号 7 天 点赞／收藏", "复盘", "档案")
    lines = ["# 已发布总览", "",
             "> 一条视频一行，按发布日期从新到旧排，最上面是最近发的。这张表由 jc-publish-closeout 的 stats.py 按各档案重新生成，别手改；要改就去改对应档案的 内容.md。",
             "> 点赞／收藏取 7 天观察点的数；没满 7 天写「未满 7 天」，没采到写「没采到」，拿不到的数写「—」。", ""]
    rows = [dict(zip(head, cells)) for _d, _n, cells in items]
    lines += table_lines(head, rows)
    lines.append("")
    path = overview_path(workfolder)
    write_text(path, "\n".join(lines))
    return path, len(rows)


# ---------- 到点没抓的 ----------

def due_items(workfolder, now):
    due, waiting, review, upcoming = [], [], [], []
    for path in PL.list_archives(workfolder):
        try:
            archive = Archive(path)
        except OSError:
            continue
        facts = archive.facts()
        label = archive.name + ("（%s）" % facts["T 编号"] if facts.get("T 编号") else "")
        complete = bool(archive.found_platforms())
        for platform in archive.found_platforms():
            for point, (point_label, _d) in POINTS.items():
                target = archive.target(platform, point)
                item = archive.latest(platform, point)
                if item and item.get("status") in ("ok", "missed"):
                    continue
                complete = False
                if not target:
                    continue
                entry = {"archive": path, "name": archive.name, "label": label, "platform": platform, "point": point,
                         "point_label": point_label, "target_at": fmt(target)}
                if now >= target:
                    entry["late"] = span(now - target)
                    due.append(entry)
                else:
                    upcoming.append(entry)
        published = parse_when(facts.get("发布时间"))
        missing = archive.waiting_platforms()
        if missing and (published is None or now - published <= timedelta(days=3)):
            waiting.append({"archive": path, "label": label, "platforms": missing})
        if complete and not archive.review_state():
            review.append({"archive": path, "label": label})
    due.sort(key=lambda e: e["target_at"])
    upcoming.sort(key=lambda e: e["target_at"])
    return {"due": due, "waiting": waiting, "review": review, "next": upcoming[0] if upcoming else None}
