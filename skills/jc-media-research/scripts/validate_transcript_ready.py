#!/usr/bin/env python3
"""Validate reviewed text; block timing is not precise sentence alignment."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

class TranscriptNotReady(RuntimeError):
    pass

def _number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)

def validate_transcript(transcript_dir: Path, require: str = "text", media: Path | None = None) -> dict:
    root = transcript_dir.expanduser().resolve()
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TranscriptNotReady("缺少或无法解析 manifest.json。") from exc
    if not isinstance(manifest, dict) or manifest.get("status") != "corrected_validated":
        raise TranscriptNotReady("逐字稿尚未完成校正复核。")
    try:
        text = (root / "corrected/transcript_corrected.md").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise TranscriptNotReady("缺少校正版逐字稿。") from exc
    body = "\n".join(line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")).strip()
    if not body or re.fullmatch(r"[\s\[\]【】]*待(?:人工)?(?:校正|复核|确认)[。\s\[\]【】]*", body):
        raise TranscriptNotReady("校正版为空或仍是占位内容。")
    uncertainty = [{"start": m.start(), "end": m.end(), "text": m.group()}
                   for m in re.finditer(r"【[^】]*(?:待确认|疑似|听不清|待复核)[^】]*】|\[待确认[^\]]*\]", text)]
    segments = []
    raw = root / "raw/segments.jsonl"
    if raw.exists():
        try:
            segments = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, ValueError) as exc:
            raise TranscriptNotReady("分段文件包含无效 JSON。") from exc
        if not segments:
            raise TranscriptNotReady("原始分段为空。")
        if manifest.get("segment_count") is not None and manifest["segment_count"] != len(segments):
            raise TranscriptNotReady("分段数量与 manifest 不一致。")
    elif manifest.get("evidence_kind") != "reviewed_text":
        raise TranscriptNotReady("缺少分段；只有明确的 reviewed_text 材料可仅按文字分析。")
    duration = manifest.get("duration_seconds")
    if duration is not None and (not _number(duration) or duration <= 0):
        raise TranscriptNotReady("媒体时长无效。")
    if media:
        try:
            probed = float(subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(media)],
                text=True, timeout=30).strip())
            digest = hashlib.sha256()
            with media.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise TranscriptNotReady("无法读取媒体或取得时长。") from exc
        expected = manifest.get("source_sha256") or manifest.get("sha256")
        if expected and digest.hexdigest() != expected:
            raise TranscriptNotReady("媒体 SHA-256 与 manifest 不一致。")
        if duration is not None and abs(probed - duration) > 0.5:
            raise TranscriptNotReady("媒体实际时长与 manifest 不一致。")
        duration = probed
    gaps, previous_end = [], 0.0
    for i, segment in enumerate(segments):
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            raise TranscriptNotReady(f"第 {i + 1} 段缺少文字。")
        start, end = segment.get("start_seconds"), segment.get("end_seconds")
        if not _number(start) or not _number(end) or start < 0 or end <= start:
            raise TranscriptNotReady(f"第 {i + 1} 段时间范围无效。")
        if start < previous_end - 0.05:
            raise TranscriptNotReady(f"第 {i + 1} 段与前段重叠或乱序。")
        if duration is not None and end > duration + 0.5:
            raise TranscriptNotReady(f"第 {i + 1} 段超过媒体时长。")
        if start > previous_end + 0.5:
            gaps.append([previous_end, start])
        previous_end = end
    if duration is not None and previous_end < duration - 0.5:
        gaps.append([previous_end, duration])
    coverage = bool(segments) and duration is not None and not gaps
    precision = manifest.get("time_precision", "block" if segments else "unknown")
    precise = coverage and precision in {"sentence", "word"} and manifest.get("alignment_reviewed") is True
    issues = []
    if not segments: issues.append("仅有已复核文字，缺少时间轴")
    if duration is None: issues.append("媒体时长未知，覆盖率未验证")
    if gaps: issues.append("时间轴存在缺口")
    if not precise: issues.append("没有已复核的句子或词级对齐，不能作精确时间结论")
    if uncertainty: issues.append("局部疑问需按范围限制对应判断")
    if require == "timing" and not precise:
        raise TranscriptNotReady("；".join(issues))
    return {"status": "ready", "schema_version": 2, "manifest_status": manifest["status"],
            "capabilities": {"text_structure": True, "block_timing": coverage, "precise_timing": precise},
            "time_precision": precision, "duration_seconds": duration, "segment_count": len(segments),
            "coverage_gaps": gaps, "corrected_characters": len(text), "uncertainties": uncertainty,
            "limitations": issues, "media_verified": media is not None}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript-dir", required=True, type=Path)
    parser.add_argument("--require", choices=("text", "timing"), default="text")
    parser.add_argument("--media", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate_transcript(args.transcript_dir, args.require, args.media)
    except TranscriptNotReady as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
