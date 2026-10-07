#!/usr/bin/env python3
"""检查一条对标素材的入库目录，或检查工作文件夹里的整个对标素材库。

对标素材放在工作文件夹的 市场调研/对标素材/ 下（未参考/<平台>/、已参考/<平台>/、.staging/）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transcript_srt  # noqa: E402


# 对标素材在工作文件夹里的位置；改位置只改这一处。
CONTENT_DIR = Path("市场调研") / "对标素材"

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
TRANSCRIPT_MARKERS = ("## 校正版逐字稿", "校正版逐字稿/")
STALE_TRANSCRIPT_LINK_PATTERN = re.compile(
    r"转写/(?:validation\.json|manifest\.json|原始识别/|分段复核/|分段源/)"
)


def canonical_url(value: str) -> str:
    try:
        parts = urlsplit(value.strip().rstrip("|)>，。"))
    except ValueError:
        return ""
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def extract_ids(text: str) -> set[str]:
    patterns = (
        r"(?:作品|笔记|视频)\s*ID\s*[|：:]\s*([A-Za-z0-9_-]{6,})",
        r"/(?:video|note)/([A-Za-z0-9_-]{6,})",
    )
    values: set[str] = set()
    for pattern in patterns:
        values.update(re.findall(pattern, text, flags=re.IGNORECASE))
    return values


def extract_urls(text: str) -> set[str]:
    values: set[str] = set()
    for line in text.splitlines():
        # 达人主页用于记录作者身份，不是作品的稳定来源链接；同一达人
        # 有多条作品时，不能因此把新作品误判为重复。
        if re.search(r"(?:达人|作者)链接\s*(?:\||[：:])", line):
            continue
        values.update(
            url
            for raw in re.findall(r"https?://[^\s<>\]]+", line)
            if (url := canonical_url(raw))
        )
    return values


def extract_hashes(text: str) -> set[str]:
    return {value.lower() for value in re.findall(r"\b[a-fA-F0-9]{64}\b", text)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def issue(level: str, code: str, detail: str, path: Path) -> dict[str, str]:
    return {"level": level, "code": code, "detail": detail, "path": str(path)}


def find_transcript_files(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*.md")
        if "校正版逐字稿" in path.parts and path.is_file() and path.stat().st_size > 0
    )


def find_transcript_intermediates(folder: Path) -> list[Path]:
    transcript_dir = folder / "转写"
    if not transcript_dir.is_dir():
        return []
    return sorted(
        path
        for path in transcript_dir.rglob("*")
        if path.is_file() and "校正版逐字稿" not in path.parts
    )


def validate_video(path: Path) -> tuple[bool, str]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return False, "ffprobe unavailable"
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or "ffprobe failed"
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return False, "duration unreadable"
    return duration > 0, f"duration={duration:.3f}s"


def duration_from_detail(detail: str) -> float | None:
    match = re.search(r"duration=([\d.]+)s", detail)
    return float(match.group(1)) if match else None


def load_records(content_root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for note in sorted(content_root.rglob("笔记信息.md")):
        if ".staging" in note.parts or any(part.startswith("_") for part in note.relative_to(content_root).parts):
            continue
        text = note.read_text(encoding="utf-8", errors="replace")
        records.append(
            {
                "folder": note.parent,
                "ids": extract_ids(text),
                "urls": extract_urls(text),
                "hashes": extract_hashes(text),
            }
        )
    return records


def validate_folder(
    folder: Path,
    content_root: Path,
    strict: bool,
    records: list[dict[str, object]],
    require_srt: bool = False,
) -> dict[str, object]:
    issues: list[dict[str, str]] = []
    note = folder / "笔记信息.md"
    if not note.is_file() or note.stat().st_size == 0:
        issues.append(issue("error", "missing_note", "笔记信息.md 不存在或为空", folder))
        return {"folder": str(folder), "ok": False, "issues": issues}

    text = note.read_text(encoding="utf-8", errors="replace")
    title_match = re.search(r"^#\s+\S.+$", text, flags=re.MULTILINE)
    if not title_match:
        issues.append(issue("error", "missing_title", "缺少一级标题", note))
    if not re.search(r"(?:^>\s*平台[：:]|\|\s*平台\s*\|)", text, flags=re.MULTILINE):
        issues.append(issue("error", "missing_platform", "缺少平台字段", note))

    ids = extract_ids(text)
    urls = extract_urls(text)
    hashes = extract_hashes(text)
    if not ids and not urls:
        issues.append(issue("error", "missing_identity", "作品 ID 与稳定来源链接至少需要一个", note))
    has_body = len(text) >= 200 and any(
        marker in text for marker in ("## 原始复制内容", "作品描述", "视频描述", "笔记内容", "## 校正版逐字稿")
    )
    if not has_body:
        issues.append(issue("error", "missing_body", "没有可读正文、描述、原始复制内容或逐字稿", note))

    media = sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES | IMAGE_SUFFIXES)
    for path in media:
        if path.stat().st_size == 0:
            issues.append(issue("error", "empty_media", "媒体文件为零字节", path))

    videos = [path for path in media if path.suffix.lower() in VIDEO_SUFFIXES]
    images = [path for path in media if path.suffix.lower() in IMAGE_SUFFIXES]
    durations: list[float] = []
    for path in videos:
        ok, detail = validate_video(path)
        if not ok:
            issues.append(issue("error", "invalid_video", detail, path))
        elif (seconds := duration_from_detail(detail)) is not None:
            durations.append(seconds)
        actual_hash = sha256_file(path)
        if actual_hash not in hashes:
            issues.append(issue("error" if strict else "warning", "video_hash_unrecorded", actual_hash, path))

    embedded = set(re.findall(r"!\[\[([^\]]+)\]\]", text))
    for path in images:
        if path.name not in embedded:
            issues.append(issue("error" if strict else "warning", "image_not_embedded", "图片未嵌入笔记", path))

    transcript_files = find_transcript_files(folder)
    transcript_intermediates = find_transcript_intermediates(folder)
    transcript_in_note = any(marker in text for marker in TRANSCRIPT_MARKERS)
    if videos and (not transcript_files or not transcript_in_note):
        issues.append(
            issue(
                "error" if strict else "warning",
                "video_transcript_incomplete",
                "有视频但缺少校正版逐字稿文件或笔记中的逐字稿部分",
                folder,
            )
        )
    is_staging = ".staging" in folder.parts
    # 时间码字幕：与校正版逐字稿同目录同名的 .srt。新入库（暂存区严格检查，或正式目录带
    # --require-srt）必须有；旧素材没有时不报，有就检查。
    srt_files = 0
    if videos:
        srt_required = strict and (is_staging or require_srt)
        for transcript in transcript_files:
            srt = transcript.with_suffix(".srt")
            if not srt.is_file():
                if srt_required:
                    issues.append(issue("error", "srt_missing", f"缺少与逐字稿同名的时间码字幕 {srt.name}", srt))
                continue
            srt_files += 1
            for problem in transcript_srt.check_srt(srt, transcript, max(durations) if durations else None):
                issues.append(issue("error" if strict else "warning", problem["code"], problem["detail"], srt))
    if videos and is_staging:
        validation = folder / "转写" / "validation.json"
        if not validation.is_file():
            issues.append(issue("error" if strict else "warning", "missing_transcript_validation", "缺少转写验收结果", folder))
    if videos and not is_staging:
        if transcript_intermediates:
            issues.append(
                issue(
                    "error" if strict else "warning",
                    "transcript_intermediates_retained",
                    f"正式目录仍有 {len(transcript_intermediates)} 个非校正版转写文件",
                    folder / "转写",
                )
            )
        if STALE_TRANSCRIPT_LINK_PATTERN.search(text):
            issues.append(
                issue(
                    "error" if strict else "warning",
                    "stale_transcript_link",
                    "笔记信息.md 仍链接已清理的转写中间版本",
                    note,
                )
            )

    for record in records:
        other = Path(str(record["folder"]))
        if other.resolve() == folder.resolve():
            continue
        if ids and ids.intersection(record["ids"]):
            issues.append(issue("error", "duplicate_id", f"与 {other} 作品 ID 重复", folder))
        if urls and urls.intersection(record["urls"]):
            issues.append(issue("error", "duplicate_url", f"与 {other} 稳定链接重复", folder))
        if hashes and hashes.intersection(record["hashes"]):
            issues.append(issue("error", "duplicate_media_hash", f"与 {other} 媒体 SHA-256 重复", folder))

    errors = [item for item in issues if item["level"] == "error"]
    return {
        "folder": str(folder),
        "ok": not errors,
        "counts": {
            "images": len(images),
            "videos": len(videos),
            "transcript_files": len(transcript_files),
            "srt_files": srt_files,
            "transcript_intermediates": len(transcript_intermediates),
        },
        "issues": issues,
    }


def resolve_target(work_folder: Path, content_root: Path, target: str | None) -> list[Path]:
    if not target:
        return sorted(
            note.parent
            for note in content_root.rglob("笔记信息.md")
            if ".staging" not in note.parts
            and not any(part.startswith("_") for part in note.relative_to(content_root).parts)
        )
    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = work_folder / candidate
    candidate = candidate.resolve()
    if content_root.resolve() not in candidate.parents and candidate != content_root.resolve():
        raise ValueError(f"target 必须位于工作文件夹的 {CONTENT_DIR.as_posix()}/ 内")
    return [candidate]


def build_report(work_folder: Path, target: str | None, strict: bool, require_srt: bool = False) -> dict[str, object]:
    content_root = work_folder / CONTENT_DIR
    if not content_root.is_dir():
        return {"ok": False, "error": f"missing content root: {content_root}", "results": []}
    try:
        folders = resolve_target(work_folder, content_root, target)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "results": []}
    records = load_records(content_root)
    results = [validate_folder(folder, content_root, strict, records, require_srt) for folder in folders]
    return {
        "ok": all(bool(result["ok"]) for result in results),
        "work_folder": str(work_folder),
        "strict": strict,
        "require_srt": require_srt,
        "checked": len(results),
        "results": results,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"检查工作文件夹里 {CONTENT_DIR.as_posix()}/ 下的对标素材入库目录。")
    parser.add_argument("work_folder", nargs="?", default=".", help="工作文件夹（里面有 市场调研/对标素材/），默认当前目录")
    parser.add_argument("--target", help=f"只检查 {CONTENT_DIR.as_posix()}/ 内的指定目录（相对工作文件夹或绝对路径）")
    parser.add_argument("--strict", action="store_true", help="逐字稿、图片嵌入和哈希缺失按错误处理")
    parser.add_argument(
        "--require-srt",
        action="store_true",
        help="正式目录也要求有视频的条目带时间码字幕（暂存区在 --strict 下本来就要求）",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(Path(args.work_folder).expanduser().resolve(), args.target, args.strict, args.require_srt)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"ok={report.get('ok')} checked={report.get('checked', 0)}")
        for result in report.get("results", []):
            print(f"- {result['folder']}: ok={result['ok']}")
            for item in result.get("issues", []):
                print(f"  {item['level']}: {item['code']} - {item['detail']}")
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
