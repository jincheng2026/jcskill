#!/usr/bin/env python3
"""给校正版逐字稿配上时间码字幕（.srt），并检查字幕是否可用。

字幕的文字取校正版逐字稿正文，时间取转写时的识别时间：把校正版正文逐字对齐到
jc-zhuanxie 写出的原始识别（`原始识别/<id>.json`，小句＋字级起点），校正时改过、
补过的字按前后字的时间插值。原始识别只在暂存区和回收站里，正式目录只留校正版
逐字稿和这份同名字幕。

用法：
  python3 transcript_srt.py build --timing 原始识别/001-视频.json \
      --transcript 校正版逐字稿/001-视频.md [--video 视频.mp4] [--output 校正版逐字稿/001-视频.srt] [--force]
  python3 transcript_srt.py check --transcript 校正版逐字稿/001-视频.md [--srt ...] [--video 视频.mp4]

时间来源可以是 `<id>.json`（首选，有字级时间）、`<id>.volc.json` 或任何 `.srt`
（例如逐字稿改过之后，用现有字幕重建：`--timing 校正版逐字稿/001-视频.srt --force`）。
不调用任何转写接口，不花钱。
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path


PUNCT_CLAUSE = set("，。！？；：,?!;")  # 与 jc-zhuanxie 的小句断法一致（不含 . 和 :，避免拆开 3.5、10:30）
OPENERS = set("「『“‘（(《〈[")
MARKER_OPEN, MARKER_CLOSE = "【", "】"
MIN_MATCH_RATIO = 0.8        # 校正版里至少八成的字要能在原始识别里原样找到，否则判定配错了文件
MIN_CUE_MS = 200             # 过短的字幕播放器会跳过，与 jc-zhuanxie 一致
DURATION_TOLERANCE = 1.0     # 末条字幕允许超出视频时长的秒数
CUES_PER_MIN_RANGE = (6.0, 120.0)
MAX_CUE_SECONDS = 60.0
SRT_TIME = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})")
TIME_LINE = re.compile(rf"^\s*{SRT_TIME.pattern}\s*-->\s*{SRT_TIME.pattern}\s*$")
LEADING_TIMESTAMP = re.compile(
    r"^\[\d{1,2}:\d{2}(?::\d{2})?(?:\s*[–—\-~至到]\s*\d{1,2}:\d{2}(?::\d{2})?)?\]\s*"
)
TIMESTAMP_ONLY = re.compile(r"^[\[（(]?[\d:：.,，\s–—\-~至到]+[\]）)]?$")
HEADER_NOTE = re.compile(r"^(?:说明|注|备注)[：:]")


# ---------- 文字 ----------

def norm_char(ch: str) -> str:
    """口播里读出来的字：中文单字、英文字母、数字；其余（标点、空格、符号）返回空串。"""
    value = unicodedata.normalize("NFKC", ch).lower()
    if len(value) == 1 and ("\u4e00" <= value <= "\u9fff" or value.isascii() and value.isalnum()):
        return value
    return ""


def transcript_body(text: str) -> list[str]:
    """校正版逐字稿里真正属于口播的段落：去掉 YAML 头、标题、元信息列表、引用、表格、
    开头的说明行和纯时间段行；行首的 [00:01:05] 时间戳也去掉。"""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() == "---":
                lines = lines[end + 1:]
                break
    body: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(("#", ">", "|", "<!--")) or re.match(r"^[-*+]\s", line):
            continue
        if TIMESTAMP_ONLY.match(line) and re.search(r"\d:\d", line):
            continue
        if not body and HEADER_NOTE.match(line):
            continue
        line = LEADING_TIMESTAMP.sub("", line).strip()
        if line:
            body.append(line)
    return body


def spoken_positions(text: str) -> list[tuple[int, str]]:
    """文本里每个读出来的字的位置和规范写法；【疑似：…】这类标注不算读出来的字。"""
    out: list[tuple[int, str]] = []
    depth = 0
    for index, ch in enumerate(text):
        if ch == MARKER_OPEN:
            depth += 1
            continue
        if ch == MARKER_CLOSE and depth:
            depth -= 1
            continue
        if depth:
            continue
        value = norm_char(ch)
        if value:
            out.append((index, value))
    return out


def spoken_text(text: str) -> str:
    return "".join(value for _, value in spoken_positions(text))


def split_cues(paragraphs: list[str]) -> list[str]:
    """按小句标点把正文切成字幕条；【…】标注里不切，句末的引号、括号跟着前一条走。"""
    cues: list[str] = []
    for paragraph in paragraphs:
        buf, depth, pending = "", 0, False
        for ch in paragraph:
            # 小句标点之后，遇到下一个读出来的字或开引号才另起一条；标注整段跟着前一条
            if depth == 0 and pending and ch != MARKER_OPEN and (norm_char(ch) or ch in OPENERS):
                cues.append(buf.strip())
                buf, pending = "", False
            buf += ch
            if ch == MARKER_OPEN:
                depth += 1
            elif ch == MARKER_CLOSE and depth:
                depth -= 1
            elif depth == 0 and ch in PUNCT_CLAUSE:
                pending = True
        if buf.strip():
            cues.append(buf.strip())
    # 没有读出来的字的条（只有标点或标注）并进前一条
    merged: list[str] = []
    for cue in cues:
        if merged and not spoken_text(cue):
            merged[-1] += cue
        else:
            merged.append(cue)
    if len(merged) > 1 and not spoken_text(merged[0]):
        merged[1] = merged[0] + merged[1]
        merged.pop(0)
    return merged


# ---------- 时间 ----------

def parse_srt(text: str) -> list[dict]:
    """解析 .srt，返回 [{"i", "start", "end", "text"}]（毫秒）；格式不对抛 ValueError。"""
    cues: list[dict] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\ufeff", "").strip())
    for number, block in enumerate(blocks, 1):
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise ValueError(f"第 {number} 条格式不对：{block[:60]!r}")
        match = TIME_LINE.match(lines[1])
        if not match:
            raise ValueError(f"第 {number} 条时间行不对：{lines[1]!r}")
        g = [int(x) for x in match.groups()]
        start = ((g[0] * 60 + g[1]) * 60 + g[2]) * 1000 + g[3]
        end = ((g[4] * 60 + g[5]) * 60 + g[6]) * 1000 + g[7]
        cues.append({"i": int(lines[0]), "start": start, "end": end, "text": "\n".join(lines[2:]).strip()})
    return cues


def _explode(token: str, start: int, end: int) -> list[tuple[str, int, int]]:
    chars = [value for value in (norm_char(ch) for ch in token) if value]
    if not chars:
        return []
    end = max(end, start)
    step = (end - start) / len(chars)
    return [(ch, round(start + k * step), round(start + (k + 1) * step)) for k, ch in enumerate(chars)]


def load_timing(path: Path) -> list[tuple[str, int, int]]:
    """读时间来源，返回按时间排好的 [(字, 起点毫秒, 终点毫秒)]。"""
    if path.suffix.lower() == ".srt":
        out: list[tuple[str, int, int]] = []
        for cue in parse_srt(path.read_text(encoding="utf-8")):
            out.extend(_explode(spoken_text(cue["text"]), cue["start"], cue["end"]))
        return out
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("clauses") or data.get("sentences") or []
    out = []
    for clause in data:
        c_start = round(float(clause["start"]) * 1000)
        c_end = round(float(clause["end"]) * 1000)
        tokens = clause.get("chars") or []
        if not tokens:
            out.extend(_explode(spoken_text(str(clause.get("text", ""))), c_start, c_end))
            continue
        for k, (token, t_start) in enumerate(tokens):
            start = round(float(t_start) * 1000)
            end = round(float(tokens[k + 1][1]) * 1000) if k + 1 < len(tokens) else max(c_end, start)
            out.extend(_explode(str(token), start, end))
    return out


def align(corrected: list[str], raw: list[tuple[str, int, int]]) -> tuple[list[tuple[int, int]], float]:
    """把校正版的每个字对到原始识别的时间；返回每个字的 (起, 止) 和原样对上的比例。"""
    if not corrected or not raw:
        raise ValueError("校正版正文或时间来源为空")
    raw_chars = [ch for ch, _, _ in raw]
    times: list[tuple[int, int] | None] = [None] * len(corrected)
    matched = 0
    matcher = difflib.SequenceMatcher(None, corrected, raw_chars, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            matched += i2 - i1
            for k in range(i2 - i1):
                times[i1 + k] = (raw[j1 + k][1], raw[j1 + k][2])
        elif tag == "replace":
            span_start, span_end = raw[j1][1], max(raw[j2 - 1][2], raw[j1][1])
            step = (span_end - span_start) / (i2 - i1)
            for k in range(i2 - i1):
                times[i1 + k] = (round(span_start + k * step), round(span_start + (k + 1) * step))
    # 原始识别里没有的字（校正时补的）：夹在前后两个已知字之间均分
    index = 0
    while index < len(times):
        if times[index] is not None:
            index += 1
            continue
        stop = index
        while stop < len(times) and times[stop] is None:
            stop += 1
        left = times[index - 1][1] if index > 0 else raw[0][1]
        right = times[stop][0] if stop < len(times) else raw[-1][2]
        right = max(right, left)
        step = (right - left) / (stop - index)
        for k in range(stop - index):
            times[index + k] = (round(left + k * step), round(left + (k + 1) * step))
        index = stop
    return [t for t in times if t is not None], matched / len(corrected)


def srt_time(ms: int) -> str:
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def probe_duration(video: Path) -> float | None:
    ffprobe = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
    if not Path(ffprobe).is_file():
        return None
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(video)],
        capture_output=True, text=True, timeout=60, check=False,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def build_cues(transcript_text: str, raw: list[tuple[str, int, int]], duration: float | None = None) -> tuple[list[dict], dict]:
    cue_texts = split_cues(transcript_body(transcript_text))
    per_cue = [spoken_text(text) for text in cue_texts]
    corrected = [ch for cue in per_cue for ch in cue]
    times, ratio = align(corrected, raw)
    if ratio < MIN_MATCH_RATIO:
        raise ValueError(
            f"校正版只有 {ratio:.0%} 的字能在时间来源里原样找到（低于 {MIN_MATCH_RATIO:.0%}），"
            "多半是逐字稿和时间来源不是同一条视频，已停止"
        )
    cues: list[dict] = []
    offset = 0
    for text, spoken in zip(cue_texts, per_cue):
        first, last = times[offset], times[offset + len(spoken) - 1]
        offset += len(spoken)
        cues.append({"text": text, "start": first[0], "end": max(last[1], first[0])})
    limit = round(duration * 1000) if duration else None
    changed = True
    while changed:
        changed = False
        for k, cue in enumerate(cues):
            nxt = cues[k + 1]["start"] if k + 1 < len(cues) else None
            if limit is not None:
                cue["end"] = min(cue["end"], limit)
            if nxt is not None and cue["end"] > nxt:
                cue["end"] = nxt
            if cue["end"] - cue["start"] < MIN_CUE_MS:
                ceiling = nxt if nxt is not None else (limit if limit is not None else cue["start"] + MIN_CUE_MS)
                cue["end"] = max(cue["end"], min(cue["start"] + MIN_CUE_MS, ceiling))
            if cue["end"] <= cue["start"]:
                # 挤不出时长的条（通常是校正时补的整句）并进相邻一条
                if k > 0:
                    cues[k - 1]["text"] += cue["text"]
                    cues[k - 1]["end"] = max(cues[k - 1]["end"], cue["end"])
                elif k + 1 < len(cues):
                    cues[k + 1]["text"] = cue["text"] + cues[k + 1]["text"]
                    cues[k + 1]["start"] = cue["start"]
                else:
                    cue["end"] = cue["start"] + 1
                    continue
                cues.pop(k)
                changed = True
                break
    stats = {
        "cues": len(cues),
        "spoken_chars": len(corrected),
        "timing_chars": len(raw),
        "match_ratio": round(ratio, 4),
        "first_start": cues[0]["start"] / 1000 if cues else None,
        "last_end": cues[-1]["end"] / 1000 if cues else None,
    }
    return cues, stats


def render_srt(cues: list[dict]) -> str:
    return "\n".join(
        f"{k}\n{srt_time(cue['start'])} --> {srt_time(cue['end'])}\n{cue['text']}\n" for k, cue in enumerate(cues, 1)
    )


def build_srt(timing: Path, transcript: Path, output: Path | None = None, video: Path | None = None, force: bool = False) -> dict:
    output = output or transcript.with_suffix(".srt")
    if output.exists() and not force:
        raise FileExistsError(f"字幕已存在，不覆盖：{output}（逐字稿改过要重建时加 --force）")
    duration = probe_duration(video) if video else None
    cues, stats = build_cues(transcript.read_text(encoding="utf-8"), load_timing(timing), duration)
    temporary = output.with_name(output.name + ".part")
    temporary.write_text(render_srt(cues), encoding="utf-8")
    temporary.replace(output)
    problems = check_srt(output, transcript, duration)
    return {"ok": not problems, "srt": str(output), "timing": str(timing), "duration_seconds": duration, **stats,
            "problems": problems}


# ---------- 检查 ----------

def check_srt(srt: Path, transcript: Path, duration: float | None = None) -> list[dict[str, str]]:
    """字幕在、能解析、时间码递增不重叠、条数合理、不超出视频、文字和校正版正文一致。
    返回问题列表 [{"code", "detail"}]，空列表表示通过。"""
    def problem(code: str, detail: str) -> dict[str, str]:
        return {"code": code, "detail": detail}

    if not srt.is_file() or srt.stat().st_size == 0:
        return [problem("srt_missing", f"缺少与逐字稿同名的时间码字幕：{srt.name}")]
    try:
        cues = parse_srt(srt.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return [problem("srt_unreadable", f"字幕解析失败：{exc}")]
    if not cues:
        return [problem("srt_empty", "字幕没有任何一条")]
    problems: list[dict[str, str]] = []
    previous_end = 0
    for position, cue in enumerate(cues, 1):
        if cue["end"] <= cue["start"]:
            problems.append(problem("srt_not_increasing", f"第 {position} 条结束不晚于开始：{srt_time(cue['start'])}"))
            break
        if cue["start"] < previous_end:
            problems.append(problem("srt_not_increasing", f"第 {position} 条开始早于上一条结束：{srt_time(cue['start'])}"))
            break
        if (cue["end"] - cue["start"]) / 1000 > MAX_CUE_SECONDS:
            problems.append(problem("srt_cue_count_unreasonable", f"第 {position} 条长达 {(cue['end'] - cue['start']) / 1000:.0f} 秒"))
            break
        previous_end = cue["end"]
    span = (cues[-1]["end"] - cues[0]["start"]) / 1000
    if span >= 60:
        per_minute = len(cues) / span * 60
        low, high = CUES_PER_MIN_RANGE
        if not low <= per_minute <= high:
            problems.append(problem(
                "srt_cue_count_unreasonable",
                f"{len(cues)} 条覆盖 {span:.0f} 秒，每分钟 {per_minute:.1f} 条，不在 {low:.0f} 到 {high:.0f} 条之间",
            ))
    if duration and cues[-1]["end"] / 1000 > duration + DURATION_TOLERANCE:
        problems.append(problem("srt_exceeds_video", f"末条结束 {cues[-1]['end'] / 1000:.1f} 秒，视频只有 {duration:.1f} 秒"))
    if transcript.is_file():
        expected = "".join(spoken_text(line) for line in transcript_body(transcript.read_text(encoding="utf-8")))
        actual = "".join(spoken_text(cue["text"]) for cue in cues)
        if expected != actual:
            at = next((k for k, (a, b) in enumerate(zip(expected, actual)) if a != b), min(len(expected), len(actual)))
            problems.append(problem(
                "srt_text_mismatch",
                f"字幕文字和校正版逐字稿对不上（第 {at + 1} 个字起：逐字稿「{expected[at:at + 12]}」，字幕「{actual[at:at + 12]}」）；"
                "逐字稿改过后用 transcript_srt.py build --timing 现有字幕 --force 重建",
            ))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="给校正版逐字稿生成或检查时间码字幕（不调用转写接口）。")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="用原始识别时间生成校正版字幕")
    build.add_argument("--timing", type=Path, required=True, help="原始识别 <id>.json / <id>.volc.json / 任意 .srt")
    build.add_argument("--transcript", type=Path, required=True, help="校正版逐字稿 .md")
    build.add_argument("--output", type=Path, help="默认与逐字稿同目录同名 .srt")
    build.add_argument("--video", type=Path, help="对应视频，用来把末条限制在视频时长内")
    build.add_argument("--force", action="store_true", help="覆盖已有字幕（逐字稿改过后重建时用）")
    check = sub.add_parser("check", help="检查字幕")
    check.add_argument("--transcript", type=Path, required=True)
    check.add_argument("--srt", type=Path)
    check.add_argument("--video", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_srt(args.timing.expanduser().resolve(), args.transcript.expanduser().resolve(),
                               args.output.expanduser().resolve() if args.output else None,
                               args.video.expanduser().resolve() if args.video else None, args.force)
        else:
            transcript = args.transcript.expanduser().resolve()
            srt = args.srt.expanduser().resolve() if args.srt else transcript.with_suffix(".srt")
            duration = probe_duration(args.video.expanduser().resolve()) if args.video else None
            problems = check_srt(srt, transcript, duration)
            result = {"ok": not problems, "srt": str(srt), "problems": problems}
    except (ValueError, FileExistsError, FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
