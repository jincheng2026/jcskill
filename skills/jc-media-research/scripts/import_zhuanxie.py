#!/usr/bin/env python3
"""把 jc-zhuanxie 验收通过的逐字稿接进研究任务的 transcript 目录。

转文字统一用同仓库的 jc-zhuanxie（火山引擎豆包语音，失败时改用本机 Qwen3-ASR），本 Skill 不自带转写模型。
本脚本只做格式衔接：读 jc-zhuanxie 输出目录里的 validation.json、校正版逐字稿和原始识别的小句时间，
写成 validate_transcript_ready.py 认得的样子：

  TASK/transcript/manifest.json
  TASK/transcript/corrected/transcript_corrected.md
  TASK/transcript/raw/segments.jsonl

用法：
  python3 import_zhuanxie.py --source <jc-zhuanxie 输出目录> --output TASK/transcript [--item 001-视频] [--media MEDIA]

只有 jc-zhuanxie 的 validation.json 为 ok、校正版非空时才写成 corrected_validated。已有输出不覆盖。
manifest 里不写本机绝对路径。只用 Python 自带模块。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


class TranscriptImportError(RuntimeError):
    pass


def _pick_item(source: Path, item: str | None) -> str:
    corrected = sorted(p.stem for p in (source / "校正版逐字稿").glob("*.md"))
    if item:
        if item not in corrected:
            raise TranscriptImportError(f"校正版逐字稿里没有 {item}；现有：{'、'.join(corrected) or '无'}")
        return item
    if len(corrected) != 1:
        raise TranscriptImportError(f"校正版逐字稿有 {len(corrected)} 份，用 --item 指定是哪一份：{'、'.join(corrected) or '无'}")
    return corrected[0]


def _segments(source: Path, item: str) -> list[dict]:
    path = source / "原始识别" / f"{item}.json"
    if not path.is_file():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise TranscriptImportError(f"原始识别 {path.name} 不是有效 JSON") from exc
    out, previous_end = [], 0.0
    for row in rows if isinstance(rows, list) else []:
        text = str(row.get("text") or "").strip()
        try:
            start, end = float(row["start"]), float(row["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not text or end <= start:
            continue
        if start < previous_end:  # 识别结果偶有几十毫秒重叠，按前段结尾截齐
            start = previous_end
        if end <= start:
            continue
        out.append({"segment": len(out) + 1, "start_seconds": round(start, 3), "end_seconds": round(end, 3), "text": text})
        previous_end = end
    return out


def _probe(media: Path) -> tuple[float, str]:
    duration = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(media)],
        text=True, timeout=30).strip())
    digest = hashlib.sha256()
    with media.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return duration, digest.hexdigest()


def import_transcript(source: Path, output: Path, item: str | None = None, media: Path | None = None) -> dict:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    try:
        validation = json.loads((source / "validation.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TranscriptImportError("jc-zhuanxie 输出目录里没有可读的 validation.json，先跑完它的验收（validate_delivery.py）") from exc
    if validation.get("ok") is not True:
        raise TranscriptImportError("jc-zhuanxie 的验收没通过，先按它的报错处理再接进来")
    item = _pick_item(source, item)
    text = (source / "校正版逐字稿" / f"{item}.md").read_text(encoding="utf-8").strip()
    if not text:
        raise TranscriptImportError("校正版逐字稿是空的")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"{output.name} 已经有内容，不覆盖")
    segments = _segments(source, item)
    engine = None
    try:
        for entry in json.loads((source / "manifest.json").read_text(encoding="utf-8")).get("items", []):
            if entry.get("id") == item:
                engine = entry.get("engine")
    except (OSError, ValueError):
        pass
    manifest = {
        "schema_version": 2,
        "status": "corrected_validated",
        "source": "jc-zhuanxie",
        "item": item,
        "engine": engine,
        "evidence_kind": "transcribed_media" if segments else "reviewed_text",
        "time_precision": "sentence" if segments else "unknown",
        "alignment_reviewed": False,
        "segment_count": len(segments),
        "duration_seconds": None,
    }
    if media:
        manifest["duration_seconds"], manifest["source_sha256"] = _probe(media.expanduser().resolve())
    (output / "corrected").mkdir(parents=True, exist_ok=True)
    (output / "corrected" / "transcript_corrected.md").write_text(text + "\n", encoding="utf-8")
    if segments:
        (output / "raw").mkdir(parents=True, exist_ok=True)
        (output / "raw" / "segments.jsonl").write_text(
            "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in segments), encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="把 jc-zhuanxie 验收通过的逐字稿接进研究任务")
    parser.add_argument("--source", required=True, type=Path, help="jc-zhuanxie 的输出目录")
    parser.add_argument("--output", required=True, type=Path, help="研究任务的 transcript 目录")
    parser.add_argument("--item", help="输出目录里有几份逐字稿时，指定用哪一份（文件名不带 .md）")
    parser.add_argument("--media", type=Path, help="原媒体，用来记录时长和 SHA-256")
    args = parser.parse_args(argv)
    try:
        manifest = import_transcript(args.source, args.output, args.item, args.media)
    except (TranscriptImportError, FileExistsError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "imported", "segment_count": manifest["segment_count"],
                      "time_precision": manifest["time_precision"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
