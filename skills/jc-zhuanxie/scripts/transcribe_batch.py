#!/usr/bin/env python3
"""盘点本地媒体目录并批量转文字（引擎见同目录 volc_asr.py：火山优先，本地 Qwen3-ASR 备用）。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


MEDIA_EXTENSIONS = {
    ".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".ts",
    ".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus",
}
sys.path.insert(0, str(Path(__file__).resolve().parent))
import volc_asr  # noqa: E402


def safe_stem(value: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "-", value, flags=re.UNICODE).strip("-_")
    return cleaned or "media"


def media_inventory(input_dir: Path, output_dir: Path) -> list[Path]:
    files = []
    for path in input_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in MEDIA_EXTENSIONS:
            continue
        try:
            path.resolve().relative_to(output_dir.resolve())
            continue
        except ValueError:
            files.append(path.resolve())
    return sorted(files, key=lambda item: str(item.relative_to(input_dir.resolve())).casefold())


def ffprobe_media(path: Path, ffprobe: str) -> dict[str, object]:
    command = [
        ffprobe, "-v", "error", "-show_format", "-show_streams",
        "-of", "json", str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=True)
    data = json.loads(completed.stdout)
    streams = data.get("streams", [])
    duration_raw = data.get("format", {}).get("duration")
    duration = float(duration_raw) if duration_raw not in (None, "N/A") else None
    if not streams:
        raise RuntimeError("ffprobe 未发现音视频流")
    return {
        "duration_seconds": duration,
        "stream_types": [stream.get("codec_type") for stream in streams if stream.get("codec_type")],
    }


def write_manifest(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_transcription(media: Path, raw_dir: Path, item_id: str) -> None:
    """调用转写引擎，写出 <id>.txt / .md / .srt / .json / .volc.json。"""
    data = volc_asr.transcribe(media)
    if not data["sentences"]:
        raise RuntimeError(f"转写没有返回任何句子（引擎：{data['engine']}）")
    volc_asr.write_outputs(data, raw_dir / item_id, review_md=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch transcription for local media via Volcengine Doubao ASR.")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not input_dir.is_dir():
        parser.error(f"输入目录不存在：{input_dir}")
    if not args.dry_run:
        volc_asr.ensure_ready()
    ffprobe = volc_asr.find_tool("ffprobe")
    if not ffprobe:
        parser.error(volc_asr.INSTALL_HINT["ffprobe"])

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "原始识别"
    review_dir = output_dir / "分段复核"
    corrected_dir = output_dir / "校正版逐字稿"
    for directory in (raw_dir, review_dir, corrected_dir):
        directory.mkdir(exist_ok=True)

    sources = media_inventory(input_dir, output_dir)
    manifest_path = output_dir / "manifest.json"
    manifest: dict[str, object] = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "engine": f"volcengine {volc_asr.RESOURCE_ID}",
        "dry_run": args.dry_run,
        "items": [],
    }

    for index, media in enumerate(sources, 1):
        relative = media.relative_to(input_dir)
        item_id = f"{index:03d}-{safe_stem(relative.stem)}"
        raw_txt = raw_dir / f"{item_id}.txt"
        raw_md = raw_dir / f"{item_id}.md"
        item: dict[str, object] = {
            "id": item_id,
            "source_path": str(media),
            "source_relative": str(relative),
            "source_bytes": media.stat().st_size,
            "raw_txt": str(raw_txt),
            "raw_md": str(raw_md),
            "raw_srt": str(raw_dir / f"{item_id}.srt"),
            "raw_chars_json": str(raw_dir / f"{item_id}.json"),
            "raw_volc_json": str(raw_dir / f"{item_id}.volc.json"),
            "review_md": str(review_dir / f"{item_id}.md"),
            "corrected_md": str(corrected_dir / f"{item_id}.md"),
            "status": "pending",
        }
        manifest["items"].append(item)
        try:
            item.update(ffprobe_media(media, ffprobe))
            if args.dry_run:
                item["status"] = "media_valid"
            elif raw_txt.is_file() and raw_txt.stat().st_size > 0 and raw_md.is_file() and raw_md.stat().st_size > 0:
                item["status"] = "transcribed_existing"
            else:
                run_transcription(media, raw_dir, item_id)
                item["status"] = "transcribed"
        except Exception as exc:  # one failed item must remain visible in the manifest
            item["status"] = "failed"
            item["error"] = str(exc)
            write_manifest(manifest_path, manifest)
            if args.fail_fast:
                break
        write_manifest(manifest_path, manifest)

    completed = sum(item.get("status") in {"transcribed", "transcribed_existing", "media_valid"} for item in manifest["items"])
    failed = sum(item.get("status") == "failed" for item in manifest["items"])
    print(json.dumps({"sources": len(sources), "completed": completed, "failed": failed, "manifest": str(manifest_path)}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
