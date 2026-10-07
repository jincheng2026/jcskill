#!/usr/bin/env python3
"""Run local SenseVoice Small in serial time slices and preserve review layers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


DEFAULT_SEGMENT_SECONDS = 28

NODE_RUNNER = r"""
const { createRequire } = require('node:module');
const path = require('node:path');
const packageJson = process.argv[1];
const wavPath = process.argv[2];
const modelDir = process.argv[3];
const chunkSeconds = Number(process.argv[4]);
const localRequire = createRequire(packageJson);
const { OfflineRecognizer, readWave } = localRequire('sherpa-onnx-node');

function clean(value) {
  return String(value ?? '')
    .replace(/<\|[^|>]+\|>/g, '')
    .replace(/\s+/g, '')
    .trim();
}

const wave = readWave(wavPath, false);
if (!wave?.samples || !wave?.sampleRate) throw new Error('无法读取 16kHz WAV');
const recognizer = new OfflineRecognizer({
  modelConfig: {
    senseVoice: {
      model: path.join(modelDir, 'model.int8.onnx'),
      language: 'auto'
    },
    tokens: path.join(modelDir, 'tokens.txt')
  }
});
const chunkSamples = Math.max(1, Math.floor(chunkSeconds * wave.sampleRate));
const total = Math.ceil(wave.samples.length / chunkSamples);
const records = [];
for (let offset = 0, segment = 1; offset < wave.samples.length; offset += chunkSamples, segment += 1) {
  const end = Math.min(offset + chunkSamples, wave.samples.length);
  const stream = recognizer.createStream();
  stream.acceptWaveform({ samples: wave.samples.slice(offset, end), sampleRate: wave.sampleRate });
  recognizer.decode(stream);
  records.push({
    segment,
    start_seconds: offset / wave.sampleRate,
    end_seconds: end / wave.sampleRate,
    text: clean(recognizer.getResult(stream)?.text)
  });
  if (segment % 10 === 0 || segment === total) {
    process.stderr.write(`${segment}/${total} 段完成\n`);
  }
}
process.stdout.write(JSON.stringify({ sample_rate: wave.sampleRate, records }));
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用本地 SenseVoice Small 按时间片串行转写媒体。"
    )
    parser.add_argument("--input", type=Path, help="本地音频或视频文件。")
    parser.add_argument("--output-dir", type=Path, help="独立转写输出目录。")
    parser.add_argument("--model-dir", type=Path, help="SenseVoice Small 模型目录。")
    parser.add_argument("--segment-seconds", type=int, default=DEFAULT_SEGMENT_SECONDS)
    parser.add_argument("--ffmpeg", help="ffmpeg 可执行文件。")
    parser.add_argument("--ffprobe", help="ffprobe 可执行文件。")
    parser.add_argument("--node", help="node 可执行文件。")
    parser.add_argument(
        "--node-package",
        type=Path,
        help="能够解析 sherpa-onnx-node 的 package.json。",
    )
    parser.add_argument("--check", action="store_true", help="只检查依赖，不读取媒体。")
    return parser.parse_args()


def expand(path: Path | None) -> Path | None:
    return path.expanduser().resolve() if path else None


def first_existing(candidates: list[Path | None], marker: str | None = None) -> Path | None:
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = expand(candidate)
        if resolved is None:
            continue
        target = resolved / marker if marker else resolved
        if target.exists():
            return resolved
    return None


def resolve_executable(explicit: str | None, env_name: str, command: str) -> str | None:
    value = explicit or os.environ.get(env_name)
    if value:
        resolved = shutil.which(value) or str(expand(Path(value)))
        if Path(resolved).is_file():
            return resolved
    return shutil.which(command)


def resolve_model(explicit: Path | None) -> Path | None:
    home = Path.home()
    env_model = os.environ.get("SENSEVOICE_MODEL_DIR")
    candidates = [
        explicit,
        Path(env_model) if env_model else None,
        home / ".newmax" / "models" / "sensevoice-small",
        home / "Library" / "Application Support" / "Shandianshuo" / "models" / "sensevoice-small",
    ]
    model_dir = first_existing(candidates, "model.int8.onnx")
    if model_dir and (model_dir / "tokens.txt").is_file():
        return model_dir
    return None


def resolve_node_package(explicit: Path | None) -> Path | None:
    home = Path.home()
    env_package = os.environ.get("SENSEVOICE_NODE_PACKAGE")
    candidates = [
        explicit,
        Path(env_package) if env_package else None,
        home / ".agents" / "skills" / "wechat-channel-transcript" / "package.json",
        home / ".claude" / "skills" / "wechat-channel-transcript" / "package.json",
        home / ".newmax" / "skills" / "wechat-channel-transcript" / "package.json",
    ]
    return first_existing(candidates)


def dependency_state(args: argparse.Namespace) -> dict[str, Any]:
    ffmpeg = resolve_executable(args.ffmpeg, "FFMPEG_BIN", "ffmpeg")
    ffprobe = resolve_executable(args.ffprobe, "FFPROBE_BIN", "ffprobe")
    node = resolve_executable(args.node, "NODE_BIN", "node")
    model_dir = resolve_model(args.model_dir)
    node_package = resolve_node_package(args.node_package)
    return {
        "ok": all((ffmpeg, ffprobe, node, model_dir, node_package)),
        "ffmpeg_available": bool(ffmpeg),
        "ffprobe_available": bool(ffprobe),
        "node_available": bool(node),
        "model_available": bool(model_dir),
        "sherpa_package_available": bool(node_package),
        "_ffmpeg": ffmpeg,
        "_ffprobe": ffprobe,
        "_node": node,
        "_model_dir": model_dir,
        "_node_package": node_package,
    }


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if not key.startswith("_")}


def probe_media(ffprobe: str, media: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(media),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    payload = json.loads(result.stdout)
    duration = float(payload.get("format", {}).get("duration", 0))
    if duration <= 0:
        raise RuntimeError("媒体时长不可用。")
    return {"duration_seconds": duration}


def media_sha256(media: Path) -> str:
    digest = hashlib.sha256()
    with media.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_recognizer(
    *, node: str, node_package: Path, wav_path: Path, model_dir: Path, segment_seconds: int
) -> list[dict[str, Any]]:
    result = subprocess.run(
        [
            node,
            "-e",
            NODE_RUNNER,
            str(node_package),
            str(wav_path),
            str(model_dir),
            str(segment_seconds),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=12 * 60 * 60,
    )
    if result.stderr:
        sys.stderr.write(result.stderr)
    payload = json.loads(result.stdout)
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise RuntimeError("SenseVoice 没有返回有效分段。")
    return records


def stamp(seconds: float) -> str:
    whole = max(0, int(seconds))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def write_new(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(f"拒绝覆盖已有文件：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def write_outputs(
    *, output_dir: Path, media: Path, records: list[dict[str, Any]], duration: float,
    segment_seconds: int,
) -> dict[str, Any]:
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"输出目录已有 manifest，拒绝覆盖：{manifest_path}")

    raw_lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    raw_text = "\n".join(str(record.get("text") or "") for record in records if record.get("text"))
    review_blocks = [
        f"[{stamp(float(record['start_seconds']))}–{stamp(float(record['end_seconds']))}] "
        f"{record.get('text') or '【空段】'}"
        for record in records
    ]
    corrected_placeholder = (
        "# 校正版逐字稿\n\n"
        "状态：待人工复核。\n\n"
        "请根据 `../review/transcript_review.md` 只纠正确定错误，保留口语表达；"
        "不确定处使用「【待确认】」。完成后再把 manifest 的状态改为 `corrected_validated`。\n"
    )

    relative_files = {
        "segments_jsonl": "raw/segments.jsonl",
        "raw_transcript": "raw/transcript_raw.txt",
        "review_transcript": "review/transcript_review.md",
        "corrected_transcript": "corrected/transcript_corrected.md",
    }
    write_new(output_dir / relative_files["segments_jsonl"], "\n".join(raw_lines) + "\n")
    write_new(output_dir / relative_files["raw_transcript"], raw_text + "\n")
    write_new(
        output_dir / relative_files["review_transcript"],
        "# 分段复核稿\n\n" + "\n\n".join(review_blocks) + "\n",
    )
    write_new(output_dir / relative_files["corrected_transcript"], corrected_placeholder)

    manifest = {
        "schema_version": 1,
        "status": "transcribed_pending_review",
        "source_name": media.name,
        "source_bytes": media.stat().st_size,
        "source_sha256": media_sha256(media),
        "duration_seconds": round(duration, 3),
        "segment_seconds": segment_seconds,
        "segment_count": len(records),
        "empty_segments": sum(1 for record in records if not record.get("text")),
        "files": relative_files,
    }
    write_new(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> int:
    args = parse_args()
    if args.segment_seconds < 5 or args.segment_seconds > 120:
        raise SystemExit("--segment-seconds 必须在 5–120 之间。")

    state = dependency_state(args)
    if args.check:
        print(json.dumps(public_state(state), ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if state["ok"] else 2
    if not state["ok"]:
        print(json.dumps(public_state(state), ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit("本地 SenseVoice 依赖不完整；不会自动改用云端转写。")
    if not args.input or not args.output_dir:
        raise SystemExit("转写时必须同时提供 --input 和 --output-dir。")

    media = expand(args.input)
    output_dir = expand(args.output_dir)
    if media is None or not media.is_file():
        raise SystemExit("输入媒体不存在或不是文件。")
    if output_dir is None:
        raise SystemExit("输出目录无效。")

    probe = probe_media(str(state["_ffprobe"]), media)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jc-media-research-") as temp_dir:
        wav_path = Path(temp_dir) / "audio.wav"
        subprocess.run(
            [
                str(state["_ffmpeg"]),
                "-v",
                "error",
                "-y",
                "-i",
                str(media),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(wav_path),
            ],
            check=True,
            timeout=45 * 60,
        )
        records = run_recognizer(
            node=str(state["_node"]),
            node_package=Path(state["_node_package"]),
            wav_path=wav_path,
            model_dir=Path(state["_model_dir"]),
            segment_seconds=args.segment_seconds,
        )

    manifest = write_outputs(
        output_dir=output_dir,
        media=media,
        records=records,
        duration=probe["duration_seconds"],
        segment_seconds=args.segment_seconds,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"转写失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
