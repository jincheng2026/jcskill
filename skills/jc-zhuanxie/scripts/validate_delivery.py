#!/usr/bin/env python3
"""只读检查 jc-zhuanxie 的交付目录，写出 validation.json，不改动其他文件。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


TIMESTAMP_PATTERN = re.compile(r"(?:\d{1,2}:)?\d{2}:\d{2}")


def nonempty(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate raw, review and corrected transcript delivery.")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        parser.error(f"manifest 不存在：{manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []
    items = manifest.get("items", [])
    successful = [item for item in items if item.get("status") in {"transcribed", "transcribed_existing"}]
    failed = [item for item in items if item.get("status") == "failed"]

    if not items:
        errors.append("manifest 中没有输入媒体")
    for item in failed:
        errors.append(f"{item.get('id', '<unknown>')}: 转写失败：{item.get('error', '未记录原因')}")

    seen_ids: set[str] = set()
    for item in items:
        item_id = str(item.get("id", ""))
        if not item_id or item_id in seen_ids:
            errors.append(f"无效或重复 id：{item_id or '<empty>'}")
            continue
        seen_ids.add(item_id)
        if int(item.get("source_bytes") or 0) <= 0:
            errors.append(f"{item_id}: 源媒体为零字节")

    for item in successful:
        item_id = str(item["id"])
        raw_txt = Path(str(item["raw_txt"]))
        raw_md = Path(str(item["raw_md"]))
        review_md = Path(str(item["review_md"]))
        corrected_md = Path(str(item["corrected_md"]))
        if not nonempty(raw_txt):
            errors.append(f"{item_id}: 原始 TXT 缺失或为空")
        if not nonempty(raw_md):
            errors.append(f"{item_id}: 原始 MD 缺失或为空")
        if not nonempty(corrected_md):
            errors.append(f"{item_id}: 校正版缺失或为空")
        duration = item.get("duration_seconds")
        if isinstance(duration, (int, float)) and duration > 60:
            if not nonempty(review_md):
                errors.append(f"{item_id}: 长音视频缺少分段复核稿")
            elif not TIMESTAMP_PATTERN.search(review_md.read_text(encoding="utf-8", errors="replace")):
                warnings.append(f"{item_id}: 分段复核稿未发现时间戳")

    residue = [str(path) for path in output_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".part", ".tmp"}]
    if residue:
        errors.extend(f"临时残留：{path}" for path in residue)

    report = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_items": len(items),
        "successful_items": len(successful),
        "failed_items": len(failed),
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }
    validation_path = output_dir / "validation.json"
    validation_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "validation": str(validation_path)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
