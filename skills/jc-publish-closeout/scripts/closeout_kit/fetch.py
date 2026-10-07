"""用 TikHub 抓自己作品的数据：一条作品的点赞收藏评论转发（播放拿得到才有）、公开评论原话、自己账号最近的作品。

每一步先算计划（最多调几次、最多花多少），过了上限就停下来问用户；跑的时候不超过计划的次数。
抖音走 App V3 的接口（每次约 0.001 美元）；小红书走 App V2 的接口（每次 0.01 美元，不能用试用额度，每次都先问）。
视频号 TikHub 拉不到，只能请用户从视频号助手截图或报数。
接口和翻页写法照 jincheng-workbench 仓库 research_kit/collect.py（同一作者，MIT 许可），只留了这里要用的部分。
"""
import math
import os

from . import UserError
from . import platforms as P
from . import tikhub as T
from .text import money

DY = {
    "sec": "/api/v1/douyin/web/get_sec_user_id",
    "posts": "/api/v1/douyin/app/v3/fetch_user_post_videos",
    "detail": "/api/v1/douyin/app/v3/fetch_one_video",
    "detail_share": "/api/v1/douyin/app/v3/fetch_one_video_by_share_url",
    "comments": "/api/v1/douyin/app/v3/fetch_video_comments",
}
XH = {
    "notes": "/api/v1/xiaohongshu/app_v2/get_user_posted_notes",
    "detail": "/api/v1/xiaohongshu/app_v2/get_image_note_detail",
    "comments": "/api/v1/xiaohongshu/app_v2/get_note_comments",
}
DY_PAGE = 20
XHS_NOTES_PAGE = 6
XHS_COMMENTS_PAGE = 10
SUPPORTED = (P.DOUYIN, P.XHS)
WECHAT = "视频号"


def unsupported(platform):
    if platform == WECHAT:
        return UserError("视频号的数据 TikHub 拉不到。请用户打开视频号助手（channels.weixin.qq.com）的作品数据截图发来，"
                         "或者直接报点赞、收藏、评论、转发、播放几个数；用 record 手动记，来源写「视频号助手截图」或「用户报数」。")
    return UserError("这一版用 TikHub 只能抓抖音和小红书。%s的数据请用户从平台后台截图或报数，用 record 手动记，写明来源。"
                     % (platform or "这个链接"))


def platform_or_fail(target):
    platform = target.get("platform")
    if platform not in SUPPORTED:
        raise unsupported(platform)
    return platform


class Session(object):
    """一次抓取用到的东西：客户端、单价、用量记录、存原始返回的地方。"""

    def __init__(self, hidden=None, env=None, opener=None, sleep=None, run=None):
        env = os.environ if env is None else env
        key, _where = T.read_key(env, run)
        if not key:
            raise UserError(T.no_key_message())
        self.prices = T.prices_for(env, opener)
        self.ledger = T.Ledger(os.path.join(hidden, "用量.jsonl") if hidden else None)
        kwargs = {"base": T.base_url(env), "ledger": self.ledger, "prices": self.prices, "opener": opener}
        if sleep:
            kwargs["sleep"] = sleep
        self.client = T.Client(key, **kwargs)  # 不用缓存：抓的是某个时间点的数，必须现抓
        self.client.raw_dir = os.path.join(hidden, "原始返回") if hidden else None

    def start(self, plan, agreed=None):
        cost, head = T.check_plan(plan, self.prices, self.ledger, agreed)
        T.check_balance(self.client, plan, self.prices, cost)
        self.client.limit_calls = (self.client.calls or 0) + plan.requests
        return cost, head

    def call(self, endpoint, params, parse, *extra):
        body = self.client.get(endpoint, params)
        try:
            return parse(body, *extra), body
        except P.ShapeError as e:
            path = self.client.save_raw(endpoint, body)
            raise UserError("TikHub 返回了数据，但样子和预期的不一样，没解析出来（%s）。这次请求已经按 %s 计费。原始返回存在 %s（只有 TikHub 的返回，不含密钥）。"
                            % (e, money(self.prices.get(endpoint)[0]), path or "（没存）"))
        except LookupError as e:
            raise UserError("%s（这次请求照样按 %s 计费）" % (e, money(self.prices.get(endpoint)[0])))

    def can_call(self):
        return self.client.limit_calls is None or self.client.calls < self.client.limit_calls

    def spent(self):
        return self.client.spent


# ---------- 一条作品的数据 ----------

def work_plan(target):
    platform = platform_or_fail(target)
    plan = T.Plan(platform, "抓这条%s作品的点赞、收藏、评论、转发" % platform)
    if platform == P.DOUYIN:
        plan.add(DY["detail"] if target.get("id") else DY["detail_share"], 1, "作品详情")
    else:
        plan.add(XH["detail"], 1, "笔记详情")
    return plan


def _plays(platform, body):
    """播放数：抖音公开接口里的 play_count 一般是 0（只有作者后台看得到），0 当成拿不到，不写成 0 播放。"""
    data = (body or {}).get("data") or {}
    if platform == P.DOUYIN:
        value = P.parse_count(P.pick(data, "aweme_detail.statistics.play_count", "aweme_details.0.statistics.play_count"))
    else:
        value = P.parse_count(P.pick(data, "data.0.note_list.0.view_count", "data.note_list.0.view_count",
                                     "data.0.note_list.0.interact_info.view_count", "data.view_count"))
    return value or None


def fetch_work(session, target):
    """返回统一格式的作品信息，多一个 plays（拿不到是 None）。"""
    platform = platform_or_fail(target)
    if platform == P.DOUYIN:
        if target.get("id"):
            work, body = session.call(DY["detail"], {"aweme_id": target["id"]}, P.douyin_detail)
        else:
            work, body = session.call(DY["detail_share"], {"share_url": target["url"]}, P.douyin_detail)
    else:
        params = {"note_id": target["id"]} if target.get("id") else {"share_text": target["url"]}
        work, body = session.call(XH["detail"], params, P.xhs_note_detail)
    work["platform"] = platform
    work["plays"] = _plays(platform, body)
    return work


# ---------- 自己账号最近的作品（认作品用） ----------

def own_works_plan(platform, user_id, max_works):
    if platform not in SUPPORTED:
        raise unsupported(platform)
    plan = T.Plan(platform, "拉你%s账号最近 %d 条作品，找刚发的这条" % (platform, max_works))
    if platform == P.DOUYIN:
        if not user_id:
            plan.add(DY["sec"], 1, "从主页链接认出账号")
        plan.add(DY["posts"], int(math.ceil(max_works / float(DY_PAGE))), "作品列表")
    else:
        plan.add(XH["notes"], int(math.ceil(max_works / float(XHS_NOTES_PAGE))), "笔记列表")
        plan.notes.append("小红书笔记列表每页几条官方没写，按每页至少 6 条估的上限，实际多半用不完。")
    return plan


def fetch_own_works(session, platform, home_url, user_id, max_works):
    works = []
    if platform == P.DOUYIN:
        sec = user_id
        if not sec:
            sec, _ = session.call(DY["sec"], {"url": home_url}, lambda b: P.douyin_string(b))
        cursor, more = 0, True
        while more and len(works) < max_works and session.can_call():
            (page, cursor, more), _ = session.call(DY["posts"], {"sec_user_id": sec, "max_cursor": cursor or 0, "count": DY_PAGE}, P.douyin_works)
            works.extend(page)
            if not page:
                break
    else:
        if not user_id:
            raise UserError("从这个小红书主页链接里认不出账号编号：%s。请用户在浏览器里打开自己的主页，复制地址栏里 xiaohongshu.com/user/profile/ 开头的完整链接。" % home_url)
        cursor, more = "", True
        while more and len(works) < max_works and session.can_call():
            (page, cursor, more), _ = session.call(XH["notes"], {"user_id": user_id, "cursor": cursor or ""}, P.xhs_notes)
            works.extend(page)
            if not page or not cursor:
                break
    seen, unique = set(), []
    for w in works:
        if w["id"] and w["id"] not in seen:
            seen.add(w["id"])
            unique.append(w)
    return unique[:max_works]


# ---------- 公开评论原话（复盘用） ----------

def comments_plan(target, max_comments):
    platform = platform_or_fail(target)
    plan = T.Plan(platform, "抓%s这条作品的公开评论原话，最多 %d 条一级评论" % (platform, max_comments))
    plan.comments_over_default = max_comments > T.COMMENTS_DEFAULT_MAX
    if platform == P.DOUYIN:
        plan.add(DY["detail"] if target.get("id") else DY["detail_share"], 1, "作品详情")
        plan.add(DY["comments"], int(math.ceil(max_comments / float(DY_PAGE))), "一级评论")
    else:
        plan.add(XH["comments"], int(math.ceil(max_comments / float(XHS_COMMENTS_PAGE))), "一级评论")
        plan.notes.append("小红书评论每页几条官方没写，按每页 10 条估。")
    return plan


def fetch_comments(session, target, max_comments):
    """返回 (评论行, 作品信息, 说明)。只数一级评论，平台附带在一级评论下的回复（常是作者的回答）一起留下、不占名额。"""
    platform = platform_or_fail(target)
    rows, info, notes, more = [], {}, [], False
    if platform == P.DOUYIN:
        if target.get("id"):
            work, _ = session.call(DY["detail"], {"aweme_id": target["id"]}, P.douyin_detail)
        else:
            work, _ = session.call(DY["detail_share"], {"share_url": target["url"]}, P.douyin_detail)
        vid = work["id"]
        info = {"id": vid, "url": work["url"], "title": work["title"], "comment_count": work["comments"]}
        cursor, more = 0, True
        while more and _top(rows) < max_comments and session.can_call():
            (page, cursor, more, _total), _ = session.call(DY["comments"], {"aweme_id": vid, "cursor": cursor or 0, "count": DY_PAGE}, P.douyin_comments, vid)
            rows.extend(page)
            if not page:
                break
    else:
        nid = target.get("id")
        params = {"note_id": nid} if nid else {"share_text": target["url"]}
        info = {"id": nid, "url": P.work_link(P.XHS, nid) if nid else target.get("url"), "title": None, "comment_count": None}
        nxt, more = {"cursor": "", "index": 0, "pageArea": "UNFOLDED"}, True
        while more and _top(rows) < max_comments and session.can_call():
            q = dict(params, cursor=nxt.get("cursor") or "", index=nxt.get("index") or 0, pageArea=nxt.get("pageArea") or "UNFOLDED", sort_strategy="like_count")
            (page, nxt, more, total), _ = session.call(XH["comments"], q, P.xhs_comments, nid)
            rows.extend(page)
            if total and not info.get("comment_count"):
                info["comment_count"] = total
            if not page:
                break
    out, seen, n = [], set(), 0
    for r in rows:
        key = r["cid"] or (r["text"], r["time"])
        if key in seen:
            continue
        if r["level"] == "一级":
            if n >= max_comments:
                break
            n += 1
        seen.add(key)
        out.append(r)
    if more:
        notes.append("评论还没取完：到了这次的条数上限就停了。")
    return out, info, notes


def _top(rows):
    return len(set(r["cid"] or r["text"] for r in rows if r["level"] == "一级"))
