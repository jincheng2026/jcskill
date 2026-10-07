"""在自己账号最近的作品里认出刚发的这条：看标题、发布时间、时长三样。

拿得准才认（一条明显比别的像），拿不准列出候选让用户挑一次，一条都不像就说没找到。宁可不认，不认错。
"""
import re
from difflib import SequenceMatcher

from .archive import parse_when

TIME_WINDOW_HOURS = 36.0


def _norm(text):
    text = re.sub(r"#[^#\s]+", "", str(text or ""))  # 去掉话题
    return re.sub(r"[\s\W_]+", "", text).lower()


def title_score(a, b, desc=""):
    a_n, b_n = _norm(a), _norm(b)
    if not a_n or not (b_n or desc):
        return 0.0
    best = SequenceMatcher(None, a_n, b_n).ratio() if b_n else 0.0
    for other in (b_n, _norm(desc)):
        if other and len(a_n) >= 6 and (a_n in other or (len(other) >= 6 and other in a_n)):
            best = max(best, 0.95)
    return round(best, 2)


def time_score(expected, actual):
    if not expected or not actual:
        return None
    hours = abs((actual - expected).total_seconds()) / 3600.0
    return round(max(0.0, 1 - hours / TIME_WINDOW_HOURS), 2)


def duration_score(expected, actual):
    if not expected or not actual:
        return None
    diff = abs(float(expected) - float(actual))
    if diff <= 1.5:
        return 1.0
    if diff <= 5:
        return 0.5
    return 0.0


def score(work, title, published, duration):
    parts = {"标题": title_score(title, work.get("title"), work.get("desc")),
             "发布时间": time_score(published, parse_when(work.get("published_at"))),
             "时长": duration_score(duration, work.get("duration_seconds"))}
    weights = {"标题": 0.5, "发布时间": 0.25, "时长": 0.25}
    used = {k: v for k, v in parts.items() if v is not None}
    total = sum(weights[k] * v for k, v in used.items()) / sum(weights[k] for k in used)
    return round(total, 2), parts


def judge(works, title, published, duration):
    """→ {"verdict": "认定"|"拿不准"|"没找到", "best": 作品, "candidates": [(分, 明细, 作品)]}。"""
    scored = []
    for work in works:
        if work.get("type") == "图文":
            continue
        total, parts = score(work, title, published, duration)
        scored.append((total, parts, work))
    scored.sort(key=lambda x: -x[0])
    if not scored or scored[0][0] < 0.4:
        return {"verdict": "没找到", "best": None, "candidates": scored[:3]}
    best, parts, work = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    time_ok = parts["发布时间"] is None or parts["发布时间"] > 0
    if best >= 0.75 and best - second >= 0.2 and parts["标题"] >= 0.5 and time_ok:
        return {"verdict": "认定", "best": work, "candidates": scored[:3]}
    return {"verdict": "拿不准", "best": None, "candidates": scored[:3]}


def describe(parts):
    out = []
    for key in ("标题", "发布时间", "时长"):
        value = parts.get(key)
        out.append("%s %s" % (key, "没法比" if value is None else "%.2f" % value))
    return "，".join(out)
