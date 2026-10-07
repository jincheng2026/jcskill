#!/usr/bin/env python3
"""Normalize research data without carrying raw API fields into deliverables.

The script has two explicit paths:

* ``content``: whitelist content fields, deduplicate by ``content_id``, apply the
  confirmed Douyin AI-tutorial gate, and record every exclusion reason.
* ``comments``: whitelist one row per comment and calculate category statistics
  from the exclusive ``primary_category`` field. ``is_noise`` remains an
  independent flag and never becomes a category.

Input may be JSON, JSONL, CSV, or ``-`` for JSON on stdin. Output is JSON. A
filesystem output is opened in exclusive-create mode; existing files are never
overwritten.
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import quote, urlsplit, urlunsplit


SCHEMA_VERSION = 2
DOUYIN_MIN_FOLLOWERS = 100
DOUYIN_MAX_FOLLOWERS = 20_000
DOUYIN_MIN_LIKES = 1_000
PREFERRED_AGE_DAYS = 90


class PreparationError(ValueError):
    """Raised for invalid input or a result that cannot be written safely."""


def _nested_get(row: Mapping[str, Any], path: str) -> Any:
    current: Any = row
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _first(row: Mapping[str, Any], *paths: str) -> Any:
    for path in paths:
        value = _nested_get(row, path)
        if value is not None and value != "":
            return value
    return None


def _text(value: Any, *, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple, set)):
        return None
    result = re.sub(r"\s+", " ", str(value)).strip()
    if not result:
        return None
    if max_length is not None:
        result = result[:max_length]
    return result


def _identifier(value: Any) -> str | None:
    text = _text(value, max_length=256)
    if text is None:
        return None
    # IDs are data, not paths or URLs. Reject control characters defensively.
    return "".join(char for char in text if char.isprintable()).strip() or None


def parse_count(value: Any) -> int | None:
    """Parse common API/count representations such as 1234, 1.2万, or 3k."""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value >= 0 else None

    raw = str(value).strip().lower().replace(",", "").replace("，", "")
    if not raw or raw in {"none", "null", "nan", "-", "--"}:
        return None
    multiplier = Decimal(1)
    for suffix, factor in (("万", 10_000), ("w", 10_000), ("k", 1_000)):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].strip()
            multiplier = Decimal(factor)
            break
    try:
        number = Decimal(raw) * multiplier
    except InvalidOperation:
        return None
    if not number.is_finite() or number < 0:
        return None
    return int(number)


def _parse_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "是",
            "噪声",
            "noise",
        }
    return default


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1_000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    raw = str(value).strip()
    if not raw:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return _parse_datetime(float(raw))
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any) -> str | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _basename(value: Any) -> str | None:
    text = _text(value, max_length=1_024)
    if text is None:
        return None
    # Never publish a local directory. This works for POSIX and Windows paths.
    return text.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or None


def _public_hostname(hostname: str | None) -> bool:
    if not hostname:
        return False
    lowered = hostname.rstrip(".").lower()
    if lowered == "localhost" or lowered.endswith((".localhost", ".local")):
        return False
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    )


def canonical_source_url(
    platform: str | None, content_id: str | None, source_url: Any
) -> str | None:
    """Return a stable public URL without signatures, tracking, or fragments."""

    normalized_platform = (platform or "").strip().lower()
    safe_id = quote(content_id, safe="-_.~") if content_id else None
    if normalized_platform in {"douyin", "抖音"} and safe_id:
        return f"https://www.douyin.com/video/{safe_id}"
    if normalized_platform in {"xiaohongshu", "xhs", "小红书"} and safe_id:
        return f"https://www.xiaohongshu.com/explore/{safe_id}"
    if normalized_platform in {"bilibili", "b站", "哔哩哔哩"} and safe_id:
        return f"https://www.bilibili.com/video/{safe_id}"

    raw = _text(source_url, max_length=4_096)
    if raw is None:
        return None
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not _public_hostname(
        parsed.hostname
    ):
        return None
    hostname = parsed.hostname.lower().rstrip(".")
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    path = quote(parsed.path or "/", safe="/%:@-._~!$&'()*+,;=")
    # Deliberately omit query, fragment, user info, and port. Signed and device
    # parameters belong only in the local raw layer.
    return urlunsplit(("https", hostname, path, "", ""))


def _extract_record_list(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, Mapping):
        raise PreparationError("JSON 顶层必须是对象或对象数组")

    direct_keys = (
        "records",
        "items",
        "videos",
        "comments",
        "aweme_list",
        "comment_list",
        "list",
    )
    for key in direct_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    business_data = payload.get("business_data")
    if isinstance(business_data, list):
        records: list[Mapping[str, Any]] = []
        for card in business_data:
            if not isinstance(card, Mapping):
                continue
            card_data = card.get("data")
            if not isinstance(card_data, Mapping):
                continue
            aweme_info = card_data.get("aweme_info")
            if isinstance(aweme_info, Mapping):
                records.append(aweme_info)
            aweme_list = card_data.get("aweme_list")
            if isinstance(aweme_list, list):
                records.extend(
                    item for item in aweme_list if isinstance(item, Mapping)
                )
        if records:
            return records
    data = payload.get("data")
    if isinstance(data, (list, Mapping)):
        return _extract_record_list(data)
    raise PreparationError("JSON 中没有找到 records/items/videos/comments 等记录数组")


def _annotate_source(
    records: Sequence[Mapping[str, Any]], payload: Any, source_file: Path
) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        collected_at = payload.get("time_stamp") or payload.get("time")
        params = payload.get("params")
        search_query = params.get("keyword") if isinstance(params, Mapping) else None
    else:
        collected_at = None
        search_query = None
    annotated: list[Mapping[str, Any]] = []
    for record in records:
        clone = dict(record)
        clone.setdefault("source_file", source_file.name)
        if collected_at is not None:
            clone.setdefault("collected_at", collected_at)
        if search_query is not None:
            clone.setdefault("search_query", search_query)
        annotated.append(clone)
    return annotated


def _load_json_file(path: Path) -> list[Mapping[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return _annotate_source(_extract_record_list(payload), payload, path)
    except (OSError, json.JSONDecodeError) as exc:
        raise PreparationError(f"读取输入失败：{exc}") from exc


def load_records(path_text: str) -> list[Mapping[str, Any]]:
    if path_text == "-":
        try:
            return _extract_record_list(json.load(sys.stdin))
        except json.JSONDecodeError as exc:
            raise PreparationError(f"stdin 不是有效 JSON：{exc}") from exc

    path = Path(path_text)
    if path.is_dir():
        json_files = sorted(item for item in path.glob("*.json") if item.is_file())
        if not json_files:
            raise PreparationError("输入目录没有 JSON 文件")
        combined: list[Mapping[str, Any]] = []
        for json_file in json_files:
            combined.extend(_load_json_file(json_file))
        return combined
    if not path.is_file():
        raise PreparationError(f"输入文件不存在：{path}")
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return list(csv.DictReader(handle))
        if suffix in {".jsonl", ".ndjson"}:
            records: list[Mapping[str, Any]] = []
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if not isinstance(value, Mapping):
                        raise PreparationError(
                            f"第 {line_number} 行不是 JSON 对象"
                        )
                    records.append(value)
            return records
        return _load_json_file(path)
    except (OSError, csv.Error, json.JSONDecodeError) as exc:
        raise PreparationError(f"读取输入失败：{exc}") from exc


def _direct_relevance(row: Mapping[str, Any]) -> tuple[bool | None, str | None]:
    explicit = _first(
        row,
        "direct_related",
        "is_directly_relevant",
        "relevance.direct_related",
    )
    if explicit is not None:
        return _parse_bool(explicit), _text(
            _first(row, "relevance_reason", "relevance.reason"), max_length=1_000
        )

    label = _text(
        _first(row, "relevance", "relevance_label", "relevance.label"),
        max_length=64,
    )
    if label is None:
        return None, _text(
            _first(row, "relevance_reason", "relevance.reason"), max_length=1_000
        )
    normalized = label.strip().lower().replace("_", " ").replace("-", " ")
    if normalized in {"direct", "directly relevant", "直接相关", "高度相关"}:
        return True, _text(
            _first(row, "relevance_reason", "relevance.reason"), max_length=1_000
        )
    return False, _text(
        _first(row, "relevance_reason", "relevance.reason"), max_length=1_000
    )


def _platform(value: Any, default: str) -> str:
    text = _text(value, max_length=64) or default
    normalized = text.strip().lower()
    aliases = {
        "抖音": "douyin",
        "dy": "douyin",
        "小红书": "xiaohongshu",
        "xhs": "xiaohongshu",
        "b站": "bilibili",
        "哔哩哔哩": "bilibili",
        "视频号": "wechat_channels",
    }
    return aliases.get(normalized, normalized)


def _normalize_content(
    row: Mapping[str, Any], input_index: int, default_platform: str
) -> dict[str, Any]:
    platform = _platform(_first(row, "platform", "source_platform"), default_platform)
    content_id = _identifier(
        _first(row, "content_id", "aweme_id", "video_id", "note_id", "id")
    )
    direct_related, relevance_reason = _direct_relevance(row)
    published_at = _iso(
        _first(row, "published_at", "create_time", "created_at", "publish_time")
    )
    collected_at = _iso(
        _first(row, "collected_at", "fetched_at", "crawl_time", "updated_at")
    )
    source_url = canonical_source_url(
        platform,
        content_id,
        _first(row, "source_url", "share_url", "url", "video_url", "web_url"),
    )
    relevance_label = _text(
        _first(row, "relevance", "relevance_label", "relevance.label"),
        max_length=64,
    )
    normalized_relevance = (
        relevance_label.strip().lower().replace("-", "_").replace(" ", "_")
        if relevance_label
        else "unknown"
    )
    relevance_aliases = {
        "directly_relevant": "direct",
        "直接相关": "direct",
        "高度相关": "direct",
        "相邻主题": "adjacent",
        "无关": "off_topic",
    }
    normalized_relevance = relevance_aliases.get(
        normalized_relevance, normalized_relevance
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "input_row": input_index,
        "platform": platform,
        "content_id": content_id,
        "title": _text(_first(row, "title", "desc", "description"), max_length=2_000),
        "caption": _text(
            _first(row, "description", "desc", "caption"), max_length=20_000
        ),
        "author_name": _text(
            _first(row, "author_name", "author.nickname", "nickname"),
            max_length=256,
        ),
        "author_id": _identifier(_first(row, "author_id", "author.uid", "author.sec_uid")),
        "content_type": _text(_first(row, "content_type", "media_type")),
        "collection_batch_id": _identifier(_first(row, "collection_batch_id", "batch_id")),
        "follower_snapshot_at": _iso(row.get("follower_snapshot_at")),
        "view_count_reliable": _parse_bool(row.get("view_count_reliable")) if row.get("view_count_reliable") is not None else None,
        "topic_id": _identifier(row.get("topic_id")),
        "follower_count": parse_count(
            _first(
                row,
                "follower_count",
                "fans",
                "author.follower_count",
                "author.stats.follower_count",
                "author_stats.follower_count",
            )
        ),
        "like_count": parse_count(
            _first(row, "like_count", "digg_count", "digg", "statistics.digg_count")
        ),
        "comment_count": parse_count(
            _first(row, "comment_count", "comm", "statistics.comment_count")
        ),
        "share_count": parse_count(
            _first(row, "share_count", "share", "statistics.share_count")
        ),
        "collect_count": parse_count(
            _first(
                row,
                "collect_count",
                "coll",
                "favorite_count",
                "statistics.collect_count",
            )
        ),
        "view_count": parse_count(
            _first(row, "view_count", "play_count", "statistics.play_count")
        ),
        "published_at": published_at,
        "collected_at": collected_at,
        "source_url": source_url,
        "source_file": _basename(_first(row, "source_file", "raw_file")),
        "search_query": _text(
            _first(row, "search_query", "matched_keyword", "keyword", "query"),
            max_length=512,
        ),
        "relevance": normalized_relevance,
        "direct_related": direct_related,
        "relevance_reason": relevance_reason,
    }


def _record_choice_key(record: Mapping[str, Any]) -> tuple[float, int, str]:
    collected = _parse_datetime(record.get("collected_at"))
    timestamp = collected.timestamp() if collected else float("-inf")
    completeness = sum(
        value is not None and value != ""
        for key, value in record.items()
        if key != "input_row"
    )
    stable = json.dumps(record, ensure_ascii=False, sort_keys=True)
    return timestamp, completeness, stable


def _deduplicate_content(
    records: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    with_ids: dict[tuple[str, str], dict[str, Any]] = {}
    missing: list[dict[str, Any]] = []
    for record in records:
        content_id = record.get("content_id")
        if not content_id:
            missing.append(record)
            continue
        key = (str(record.get("platform") or ""), str(content_id), record.get("collection_batch_id"))
        existing = with_ids.get(key)
        if existing is None or _record_choice_key(record) > _record_choice_key(existing):
            with_ids[key] = record

    deduplicated = list(with_ids.values()) + missing
    deduplicated.sort(key=lambda item: int(item["input_row"]))
    return deduplicated, len(records) - len(deduplicated)


def _as_of(value: str | None) -> datetime:
    if value:
        parsed = _parse_datetime(value)
        if parsed is None:
            raise PreparationError("--as-of 必须是 ISO 8601 时间或 Unix 时间戳")
        return parsed
    return datetime.now(tz=timezone.utc).replace(microsecond=0)


def _content_exclusions(record: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if record.get("platform") != "douyin":
        # V1 only has a confirmed low-follower viral definition for Douyin.
        # Other platforms may still be normalized, but must not be labelled as
        # qualified by silently borrowing Douyin thresholds.
        reasons.append("platform_gate_not_confirmed")
    if not record.get("content_id"):
        reasons.append("missing_content_id")
    direct = record.get("direct_related")
    if direct is None:
        reasons.append("missing_relevance_judgment")
    elif direct is not True:
        reasons.append("not_directly_relevant")

    followers = record.get("follower_count")
    if followers is None:
        reasons.append("missing_follower_count")
    elif followers < DOUYIN_MIN_FOLLOWERS:
        reasons.append("followers_below_100_anomaly")
    elif followers > DOUYIN_MAX_FOLLOWERS:
        reasons.append("followers_above_20000_reference_only")

    likes = record.get("like_count")
    if likes is None:
        reasons.append("missing_like_count")
    elif likes < DOUYIN_MIN_LIKES:
        reasons.append("likes_below_1000_unverified")
    return reasons


def _eligibility_label(record: Mapping[str, Any], reasons: Sequence[str]) -> str:
    if not reasons:
        return "eligible_low_follower_viral"
    relevance = str(record.get("relevance") or "unknown")
    if record.get("direct_related") is not True:
        if relevance == "adjacent":
            return "adjacent"
        if relevance == "off_topic":
            return "off_topic"
    followers = record.get("follower_count")
    likes = record.get("like_count")
    if followers is not None and int(followers) < DOUYIN_MIN_FOLLOWERS:
        return "anomaly_low_followers"
    if followers is not None and int(followers) > DOUYIN_MAX_FOLLOWERS:
        return "regular_viral_reference"
    if likes is not None and int(likes) < DOUYIN_MIN_LIKES:
        return "unverified_low_likes"
    return "missing_evidence"


def prepare_content_records(
    rows: Sequence[Mapping[str, Any]],
    *,
    platform: str = "douyin",
    as_of: str | None = None,
    eligible_only: bool = False,
    default_relevance: str | None = None,
    relevance_reason: str | None = None,
) -> dict[str, Any]:
    if default_relevance not in {None, "direct", "adjacent", "off_topic", "unknown"}:
        raise PreparationError("default_relevance 值无效")
    if default_relevance not in {None, "unknown"} and not relevance_reason:
        raise PreparationError("设置默认相关性时必须同时提供判断理由")
    reference_time = _as_of(as_of)
    prepared_rows: list[Mapping[str, Any]] = []
    for row in rows:
        if default_relevance is None or _first(
            row, "relevance", "relevance_label", "relevance.label", "direct_related"
        ) is not None:
            prepared_rows.append(row)
            continue
        clone = dict(row)
        clone["relevance"] = default_relevance
        clone["relevance_reason"] = relevance_reason
        prepared_rows.append(clone)
    normalized = [
        _normalize_content(row, index, platform)
        for index, row in enumerate(prepared_rows, 1)
    ]
    records, duplicate_count = _deduplicate_content(normalized)

    for record in records:
        published = _parse_datetime(record.get("published_at"))
        if published is None:
            age_days: int | None = None
            preferred_recent: bool | None = None
        else:
            age_seconds = (reference_time - published).total_seconds()
            age_days = math.floor(age_seconds / 86_400)
            preferred_recent = 0 <= age_days <= PREFERRED_AGE_DAYS
        reasons = _content_exclusions(record)
        record["age_days_at_research"] = age_days
        record["within_preferred_90_days"] = preferred_recent
        record["qualified"] = not reasons
        record["eligibility"] = _eligibility_label(record, reasons)
        record["exclusion_reasons"] = reasons
        record["evidence_issues"] = [
            issue
            for condition, issue in (
                (not record.get("source_url"), "missing_source_url"),
                (not record.get("source_file"), "missing_source_file"),
                (not record.get("collected_at"), "missing_collected_at"),
            )
            if condition
        ]

    eligible = [record for record in records if record["qualified"]]

    def ranking_key(record: Mapping[str, Any]) -> tuple[int, int, int, str]:
        recent = record.get("within_preferred_90_days")
        recent_order = 0 if recent is True else 1 if recent is False else 2
        return (
            recent_order,
            -int(record.get("like_count") or 0),
            int(record.get("follower_count") or 0),
            str(record.get("content_id") or ""),
        )

    eligible.sort(key=ranking_key)
    for rank, record in enumerate(eligible, 1):
        record["eligible_rank"] = rank
    for record in records:
        if not record["qualified"]:
            record["eligible_rank"] = None

    with_id = [record for record in records if record.get("content_id")]
    directly_relevant = [record for record in with_id if record["direct_related"] is True]
    in_follower_range = [
        record
        for record in directly_relevant
        if record["follower_count"] is not None
        and DOUYIN_MIN_FOLLOWERS
        <= int(record["follower_count"])
        <= DOUYIN_MAX_FOLLOWERS
    ]
    above_like_threshold = [
        record
        for record in in_follower_range
        if record["like_count"] is not None
        and int(record["like_count"]) >= DOUYIN_MIN_LIKES
    ]
    exclusion_counts = Counter(
        reason for record in records for reason in record["exclusion_reasons"]
    )

    if eligible_only:
        output_records = eligible
    else:
        eligible_ids = {
            (record["platform"], record["content_id"]) for record in eligible
        }
        output_records = eligible + [
            record
            for record in records
            if (record["platform"], record["content_id"]) not in eligible_ids
        ]

    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "content_research",
        "as_of": reference_time.replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "gate": {
            "platform": "douyin",
            "followers_min_inclusive": DOUYIN_MIN_FOLLOWERS,
            "followers_max_inclusive": DOUYIN_MAX_FOLLOWERS,
            "likes_min_inclusive": DOUYIN_MIN_LIKES,
            "direct_relevance_required": True,
            "preferred_age_days": PREFERRED_AGE_DAYS,
            "preferred_age_is_not_a_hard_gate": True,
        },
        "summary": {
            "input_rows": len(rows),
            "deduplicated_rows": len(records),
            "duplicates_removed": duplicate_count,
            "eligible_rows": len(eligible),
            "excluded_rows": len(records) - len(eligible),
            "exclusion_counts": dict(sorted(exclusion_counts.items())),
            "funnel": [
                {"stage": "input", "count": len(rows)},
                {"stage": "deduplicated", "count": len(records)},
                {"stage": "directly_relevant", "count": len(directly_relevant)},
                {"stage": "followers_100_to_20000", "count": len(in_follower_range)},
                {"stage": "likes_at_least_1000", "count": len(above_like_threshold)},
            ],
        },
        "records": output_records,
    }


def _normalize_categories(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list):
                value = decoded
            else:
                value = re.split(r"[,，;；|]", stripped)
        else:
            value = re.split(r"[,，;；|]", stripped)
    if not isinstance(value, Iterable) or isinstance(value, (bytes, Mapping)):
        return []
    result: list[str] = []
    for item in value:
        label = _text(item, max_length=128)
        if label and label not in result:
            result.append(label)
    return result


def _normalize_comment(
    row: Mapping[str, Any], input_index: int, default_platform: str
) -> dict[str, Any]:
    platform = _platform(_first(row, "platform", "source_platform"), default_platform)
    content_id = _identifier(
        _first(row, "content_id", "aweme_id", "video_id", "note_id")
    )
    primary = _text(
        _first(row, "primary_category", "category", "classification.primary"),
        max_length=128,
    ) or "未分类"
    secondary = _normalize_categories(
        _first(row, "secondary_categories", "classification.secondary")
    )
    secondary = [label for label in secondary if label != primary]
    raw_status = _text(
        _first(row, "classification_status", "classification.status"),
        max_length=64,
    )
    if primary == "未分类":
        classification_status = "unclassified"
    elif raw_status in {"ai_proposed", "user_confirmed"}:
        classification_status = raw_status
    else:
        classification_status = "ai_proposed"
    parent = _identifier(_first(row, "parent_comment_id", "reply_to_comment_id", "reply_id"))
    explicit_reply = row.get("is_reply")
    is_reply = (_parse_bool(explicit_reply) if explicit_reply is not None else
                (False if parent == "0" else True if parent else None))
    comment_id = _identifier(_first(row, "comment_id", "cid", "id"))
    coverage = row.get("reply_coverage")
    coverage = coverage if coverage in {"complete", "partial", "not_fetched", "unknown"} else "unknown"
    return {
        "schema_version": SCHEMA_VERSION,
        "input_row": input_index,
        "platform": platform,
        "content_id": content_id,
        "comment_id": comment_id,
        "parent_comment_id": parent if parent != "0" else None,
        "root_comment_id": _identifier(row.get("root_comment_id")) or (comment_id if is_reply is False else None),
        "is_reply": is_reply,
        "commenter_id": _identifier(_first(row, "commenter_id", "user.uid")),
        "content_author_id": _identifier(row.get("content_author_id")),
        "is_content_author": _parse_bool(row.get("is_content_author")) if row.get("is_content_author") is not None else None,
        "reply_coverage": coverage,
        "reply_count_reported": parse_count(_first(row, "reply_count_reported", "reply_comment_total")),
        "replies_fetched": parse_count(row.get("replies_fetched")),
        "collection_batch_id": _identifier(_first(row, "collection_batch_id", "batch_id")),
        "comment_text": _text(
            _first(row, "comment_text", "text", "content"), max_length=20_000
        ),
        "commented_at": _iso(
            _first(row, "commented_at", "create_time", "created_at")
        ),
        "digg_count": parse_count(
            _first(row, "digg_count", "like_count", "statistics.digg_count")
        ),
        "source_url": canonical_source_url(
            platform,
            content_id,
            _first(row, "source_url", "share_url", "video_url", "url"),
        ),
        "source_file": _basename(_first(row, "source_file", "raw_file")),
        "collected_at": _iso(
            _first(row, "collected_at", "fetched_at", "crawl_time")
        ),
        "primary_category": primary,
        "secondary_categories": secondary,
        "category_reason": _text(
            _first(row, "category_reason", "classification.reason"),
            max_length=2_000,
        ),
        "classification_status": classification_status,
        "is_noise": _parse_bool(
            _first(row, "is_noise", "noise", "classification.is_noise")
        ),
        "noise_reason": _text(
            _first(row, "noise_reason", "classification.noise_reason"),
            max_length=1_000,
        ),
    }


def _deduplicate_comments(
    records: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    chosen = {}
    missing = []
    for record in records:
        if not record.get("comment_id"):
            missing.append(record)
            continue
        key = (str(record.get("platform") or ""), str(record.get("content_id") or ""), str(record["comment_id"]))
        prior = chosen.get(key)
        def quality(r):
            return (str(r.get("collected_at") or ""), r.get("reply_coverage") == "complete",
                    r.get("replies_fetched") or 0, sum(v is not None for v in r.values()))
        if prior is None or quality(record) > quality(prior): chosen[key] = record
    result = sorted(list(chosen.values()) + missing, key=lambda r:r["input_row"])
    return result, len(records) - len(result)


def prepare_comment_records(
    rows: Sequence[Mapping[str, Any]],
    *,
    platform: str = "douyin",
    denominator: str = "top-level-non-noise",
) -> dict[str, Any]:
    normalized = [
        _normalize_comment(row, index, platform) for index, row in enumerate(rows, 1)
    ]
    records, duplicate_count = _deduplicate_comments(normalized)
    noise_count = sum(record["is_noise"] for record in records)
    if denominator == "all":
        counted = records
    elif denominator == "non-noise":
        counted = [record for record in records if not record["is_noise"]]
    elif denominator == "top-level-non-noise":
        counted = [record for record in records if record["is_reply"] is False and not record["is_noise"]]
    else:
        raise PreparationError("denominator 只能是 top-level-non-noise、all 或 non-noise")

    category_counts = Counter(record["primary_category"] for record in counted)
    denominator_count = len(counted)
    category_statistics = [
        {
            "primary_category": category,
            "count": count,
            "percentage": round(count / denominator_count * 100, 6)
            if denominator_count
            else 0.0,
        }
        for category, count in sorted(
            category_counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "comment_research",
        "summary": {
            "input_rows": len(rows),
            "deduplicated_rows": len(records),
            "duplicates_removed": duplicate_count,
            "noise_rows": noise_count,
            "non_noise_rows": len(records) - noise_count,
            "top_level_rows": sum(r["is_reply"] is False for r in records),
            "reply_rows": sum(r["is_reply"] is True for r in records),
            "hierarchy_unknown_rows": sum(r["is_reply"] is None for r in records),
            "reply_coverage_counts": dict(Counter(r["reply_coverage"] for r in records if r["is_reply"] is False)),
            "denominator_policy": denominator,
            "denominator": denominator_count,
            "category_statistics": category_statistics,
        },
        "records": records,
    }


def _write_json(payload: Mapping[str, Any], output: str) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output == "-":
        sys.stdout.write(serialized)
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
    except FileExistsError as exc:
        raise PreparationError(f"输出已存在，拒绝覆盖：{path}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="白名单整理内容研究数据，并输出可复算的筛选或评论统计。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    content = subparsers.add_parser(
        "content", help="整理内容记录并执行抖音低粉爆款硬门槛"
    )
    content.add_argument("input", help="JSON/JSONL/CSV 输入；- 表示 JSON stdin")
    content.add_argument("--output", "-o", required=True, help="JSON 输出；- 表示 stdout")
    content.add_argument("--platform", default="douyin", help="输入缺少平台时的默认值")
    content.add_argument(
        "--as-of",
        help="研究时点，ISO 8601 或 Unix 时间戳；不传则使用当前 UTC 时间",
    )
    content.add_argument(
        "--default-relevance",
        choices=("direct", "adjacent", "off_topic", "unknown"),
        help="仅为未逐条标注且整批判断一致的输入补默认相关性",
    )
    content.add_argument(
        "--relevance-reason",
        help="使用 --default-relevance 时必须提供的判断理由",
    )
    content.add_argument(
        "--eligible-only",
        action="store_true",
        help="输出记录区只保留合格项；summary 仍基于完整输入",
    )

    comments = subparsers.add_parser(
        "comments", help="整理逐条评论并按 primary_category 复算比例"
    )
    comments.add_argument("input", help="JSON/JSONL/CSV 输入；- 表示 JSON stdin")
    comments.add_argument("--output", "-o", required=True, help="JSON 输出；- 表示 stdout")
    comments.add_argument("--platform", default="douyin", help="输入缺少平台时的默认值")
    comments.add_argument(
        "--denominator",
        choices=("top-level-non-noise", "non-noise", "all"),
        default="top-level-non-noise",
        help="分类比例分母；噪声始终以独立字段统计",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rows = load_records(args.input)
        if args.command == "content":
            payload = prepare_content_records(
                rows,
                platform=args.platform,
                as_of=args.as_of,
                eligible_only=args.eligible_only,
                default_relevance=args.default_relevance,
                relevance_reason=args.relevance_reason,
            )
        else:
            payload = prepare_comment_records(
                rows,
                platform=args.platform,
                denominator=args.denominator,
            )
        _write_json(payload, args.output)
    except PreparationError as exc:
        parser.exit(2, f"错误：{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
