#!/usr/bin/env python3
"""Render deterministic, auditable SVG charts from normalized JSON or CSV.

Every invocation creates three sibling files: SVG, detail CSV, and a JSON
manifest. Insufficient data still produces all three files with an explicit
status and reason, so a report can fall back to the detail table without hiding
the limitation. Existing outputs are never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


WIDTH = 960
MARGIN_LEFT = 180
MARGIN_RIGHT = 70
MARGIN_TOP = 90
MARGIN_BOTTOM = 90
COLORS = (
    "#2563EB",
    "#0F766E",
    "#7C3AED",
    "#C2410C",
    "#BE123C",
    "#4D7C0F",
    "#0369A1",
    "#A16207",
)


class ChartError(ValueError):
    """Raised when input or output paths are invalid."""


def _nested_get(row: Mapping[str, Any], path: str) -> Any:
    current: Any = row
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    raw = str(value).strip().lower().replace(",", "").replace("，", "")
    if not raw:
        return None
    multiplier = 1.0
    for suffix, factor in (("万", 10_000.0), ("w", 10_000.0), ("k", 1_000.0)):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].strip()
            multiplier = factor
            break
    try:
        number = float(raw) * multiplier
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


def _extract_records(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if not isinstance(payload, Mapping):
        raise ChartError("JSON 顶层必须是对象或对象数组")
    for key in ("records", "items", "videos", "comments"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, Mapping)]
    return []


def load_input(path_text: str) -> tuple[Any, list[Mapping[str, Any]], str]:
    if path_text == "-":
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            raise ChartError(f"stdin 不是有效 JSON：{exc}") from exc
        return payload, _extract_records(payload), "stdin"

    path = Path(path_text)
    if not path.is_file():
        raise ChartError(f"输入文件不存在：{path}")
    try:
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                records = list(csv.DictReader(handle))
            return records, records, path.name
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload, _extract_records(payload), path.name
    except (OSError, csv.Error, json.JSONDecodeError) as exc:
        raise ChartError(f"读取输入失败：{exc}") from exc


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-")
    if not name:
        raise ChartError("--name 必须包含字母、数字、点、下划线或连字符")
    return name[:128]


def _fmt_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _truncate(value: Any, limit: int = 30) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _csv_text(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def _svg_shell(title: str, body: str, height: int, subtitle: str | None = None) -> str:
    subtitle_element = ""
    if subtitle:
        subtitle_element = (
            f'<text x="{MARGIN_LEFT}" y="62" font-size="14" fill="#64748B">'
            f"{escape(subtitle)}</text>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(title)}">\n'
        '<rect width="100%" height="100%" fill="#FFFFFF"/>\n'
        f'<text x="{MARGIN_LEFT}" y="38" font-family="sans-serif" font-size="24" '
        f'font-weight="700" fill="#0F172A">{escape(title)}</text>\n'
        f"{subtitle_element}\n{body}\n</svg>\n"
    )


def _insufficient_svg(title: str, reason: str) -> str:
    body = (
        '<rect x="180" y="120" width="710" height="150" rx="12" '
        'fill="#F8FAFC" stroke="#CBD5E1"/>\n'
        '<text x="535" y="180" text-anchor="middle" font-family="sans-serif" '
        'font-size="20" font-weight="600" fill="#334155">数据不足，未绘制数据图形</text>\n'
        f'<text x="535" y="220" text-anchor="middle" font-family="sans-serif" '
        f'font-size="14" fill="#64748B">{escape(_truncate(reason, 90))}</text>'
    )
    return _svg_shell(title, body, 360)


def _funnel_data(payload: Any, records: Sequence[Mapping[str, Any]]) -> list[tuple[str, float]]:
    if isinstance(payload, Mapping):
        funnel = _nested_get(payload, "summary.funnel")
        if isinstance(funnel, list):
            result: list[tuple[str, float]] = []
            for item in funnel:
                if not isinstance(item, Mapping):
                    continue
                label = item.get("label") or item.get("stage")
                count = _number(item.get("count"))
                if label is not None and count is not None and count >= 0:
                    result.append((str(label), count))
            if result:
                return result

    total = len(records)
    if total == 0:
        return []
    direct = [row for row in records if _bool(row.get("direct_related"))]
    follower = [
        row
        for row in direct
        if (value := _number(row.get("follower_count"))) is not None
        and 100 <= value <= 20_000
    ]
    liked = [
        row
        for row in follower
        if (value := _number(row.get("like_count"))) is not None and value >= 1_000
    ]
    return [
        ("input", float(total)),
        ("directly_relevant", float(len(direct))),
        ("followers_100_to_20000", float(len(follower))),
        ("likes_at_least_1000", float(len(liked))),
    ]


def render_funnel(
    payload: Any, records: Sequence[Mapping[str, Any]], title: str
) -> tuple[str, str, dict[str, Any]]:
    data = _funnel_data(payload, records)
    detail = _csv_text(
        ("stage_order", "stage", "count"),
        [(index, label, int(value) if value.is_integer() else value) for index, (label, value) in enumerate(data, 1)],
    )
    if not data or max(value for _, value in data) <= 0:
        reason = "没有可用的漏斗阶段，或所有阶段计数均为 0"
        return _insufficient_svg(title, reason), detail, {
            "status": "insufficient_data",
            "reason": reason,
            "fields": ["summary.funnel.stage", "summary.funnel.count"],
            "denominator": None,
        }

    height = max(390, MARGIN_TOP + len(data) * 58 + MARGIN_BOTTOM)
    plot_width = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    maximum = max(value for _, value in data)
    body_parts: list[str] = []
    for index, (label, value) in enumerate(data):
        y = MARGIN_TOP + index * 58
        bar_width = max(2.0, plot_width * value / maximum)
        color = COLORS[index % len(COLORS)]
        body_parts.extend(
            [
                f'<text x="{MARGIN_LEFT - 12}" y="{y + 23}" text-anchor="end" '
                f'font-family="sans-serif" font-size="13" fill="#334155">{escape(_truncate(label, 24))}</text>',
                f'<rect x="{MARGIN_LEFT}" y="{y}" width="{bar_width:.2f}" height="34" '
                f'rx="5" fill="{color}"/>',
                f'<text x="{MARGIN_LEFT + bar_width + 8:.2f}" y="{y + 23}" '
                f'font-family="sans-serif" font-size="13" fill="#0F172A">{escape(_fmt_number(value))}</text>',
            ]
        )
    return _svg_shell(title, "\n".join(body_parts), height), detail, {
        "status": "ok",
        "reason": None,
        "fields": ["summary.funnel.stage", "summary.funnel.count"],
        "denominator": data[0][1],
    }


def _bar_data(
    records: Sequence[Mapping[str, Any]],
    category_field: str,
    value_field: str | None,
    include_noise: bool,
) -> tuple[list[tuple[str, float, int]], int]:
    totals: dict[str, float] = {}
    row_counts: dict[str, int] = {}
    denominator = 0
    for row in records:
        if not include_noise and _bool(row.get("is_noise")):
            continue
        category = _nested_get(row, category_field)
        if category is None or not str(category).strip():
            category = "unclassified"
        label = str(category).strip()
        if value_field:
            value = _number(_nested_get(row, value_field))
            if value is None:
                continue
        else:
            value = 1.0
        totals[label] = totals.get(label, 0.0) + value
        row_counts[label] = row_counts.get(label, 0) + 1
        denominator += 1
    data = [
        (label, total, row_counts[label]) for label, total in totals.items()
    ]
    data.sort(key=lambda item: (-item[1], item[0]))
    return data, denominator


def render_bar(
    records: Sequence[Mapping[str, Any]],
    title: str,
    category_field: str,
    value_field: str | None,
    include_noise: bool,
) -> tuple[str, str, dict[str, Any]]:
    data, denominator = _bar_data(
        records, category_field, value_field, include_noise
    )
    detail = _csv_text(
        ("category", "value", "row_count", "percentage_of_counted_rows"),
        [
            (
                label,
                int(value) if value.is_integer() else value,
                count,
                round(count / denominator * 100, 6) if denominator else 0.0,
            )
            for label, value, count in data
        ],
    )
    if not data or max(value for _, value, _ in data) <= 0:
        reason = (
            f"字段 {category_field} 没有可用分类"
            if not value_field
            else f"字段 {category_field} 与 {value_field} 没有可配对的数值"
        )
        return _insufficient_svg(title, reason), detail, {
            "status": "insufficient_data",
            "reason": reason,
            "fields": [category_field] + ([value_field] if value_field else []),
            "denominator": denominator,
            "noise_policy": "include" if include_noise else "exclude",
        }

    visible = data[:20]
    height = max(390, MARGIN_TOP + len(visible) * 42 + MARGIN_BOTTOM)
    plot_width = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    maximum = max(value for _, value, _ in visible)
    body_parts: list[str] = []
    for index, (label, value, _) in enumerate(visible):
        y = MARGIN_TOP + index * 42
        bar_width = max(2.0, plot_width * value / maximum)
        color = COLORS[index % len(COLORS)]
        body_parts.extend(
            [
                f'<text x="{MARGIN_LEFT - 12}" y="{y + 20}" text-anchor="end" '
                f'font-family="sans-serif" font-size="13" fill="#334155">{escape(_truncate(label, 22))}</text>',
                f'<rect x="{MARGIN_LEFT}" y="{y}" width="{bar_width:.2f}" height="28" '
                f'rx="4" fill="{color}"/>',
                f'<text x="{MARGIN_LEFT + bar_width + 8:.2f}" y="{y + 20}" '
                f'font-family="sans-serif" font-size="13" fill="#0F172A">{escape(_fmt_number(value))}</text>',
            ]
        )
    subtitle = None
    if len(data) > len(visible):
        subtitle = f"图中显示前 {len(visible)} 类；完整 {len(data)} 类见 detail CSV"
    return _svg_shell(title, "\n".join(body_parts), height, subtitle), detail, {
        "status": "ok",
        "reason": None,
        "fields": [category_field] + ([value_field] if value_field else []),
        "denominator": denominator,
        "noise_policy": "include" if include_noise else "exclude",
        "displayed_categories": len(visible),
        "total_categories": len(data),
    }


def _scatter_data(
    records: Sequence[Mapping[str, Any]], x_field: str, y_field: str, label_field: str
) -> tuple[list[tuple[str, float, float, str | None]], int]:
    data: list[tuple[str, float, float, str | None]] = []
    skipped = 0
    for index, row in enumerate(records, 1):
        x_value = _number(_nested_get(row, x_field))
        y_value = _number(_nested_get(row, y_field))
        if x_value is None or y_value is None:
            skipped += 1
            continue
        label_value = _nested_get(row, label_field)
        label = str(label_value).strip() if label_value not in (None, "") else f"row-{index}"
        source_url = row.get("source_url")
        source = str(source_url) if isinstance(source_url, str) else None
        data.append((label, x_value, y_value, source))
    data.sort(key=lambda item: (item[1], item[2], item[0]))
    return data, skipped


def _domain(values: Sequence[float]) -> tuple[float, float]:
    minimum, maximum = min(values), max(values)
    if minimum == maximum:
        padding = abs(minimum) * 0.1 or 1.0
    else:
        padding = (maximum - minimum) * 0.08
    return minimum - padding, maximum + padding


def render_scatter(
    records: Sequence[Mapping[str, Any]],
    title: str,
    x_field: str,
    y_field: str,
    label_field: str,
) -> tuple[str, str, dict[str, Any]]:
    data, skipped = _scatter_data(records, x_field, y_field, label_field)
    detail = _csv_text(
        ("label", x_field, y_field, "source_url"),
        [(label, x, y, source or "") for label, x, y, source in data],
    )
    if len(data) < 2:
        reason = f"需要至少 2 个同时包含 {x_field} 和 {y_field} 的点，当前只有 {len(data)} 个"
        return _insufficient_svg(title, reason), detail, {
            "status": "insufficient_data",
            "reason": reason,
            "fields": [x_field, y_field, label_field, "source_url"],
            "denominator": len(data),
            "skipped_rows": skipped,
        }

    height = 600
    plot_width = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    plot_height = height - MARGIN_TOP - MARGIN_BOTTOM
    x_min, x_max = _domain([item[1] for item in data])
    y_min, y_max = _domain([item[2] for item in data])

    def x_position(value: float) -> float:
        return MARGIN_LEFT + (value - x_min) / (x_max - x_min) * plot_width

    def y_position(value: float) -> float:
        return MARGIN_TOP + (y_max - value) / (y_max - y_min) * plot_height

    body_parts = [
        f'<line x1="{MARGIN_LEFT}" y1="{MARGIN_TOP + plot_height}" x2="{MARGIN_LEFT + plot_width}" '
        f'y2="{MARGIN_TOP + plot_height}" stroke="#94A3B8"/>',
        f'<line x1="{MARGIN_LEFT}" y1="{MARGIN_TOP}" x2="{MARGIN_LEFT}" '
        f'y2="{MARGIN_TOP + plot_height}" stroke="#94A3B8"/>',
    ]
    for tick in range(6):
        fraction = tick / 5
        x_value = x_min + fraction * (x_max - x_min)
        x = MARGIN_LEFT + fraction * plot_width
        y_value = y_max - fraction * (y_max - y_min)
        y = MARGIN_TOP + fraction * plot_height
        body_parts.extend(
            [
                f'<line x1="{x:.2f}" y1="{MARGIN_TOP}" x2="{x:.2f}" '
                f'y2="{MARGIN_TOP + plot_height}" stroke="#E2E8F0"/>',
                f'<text x="{x:.2f}" y="{MARGIN_TOP + plot_height + 24}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="11" fill="#64748B">{escape(_fmt_number(x_value))}</text>',
                f'<line x1="{MARGIN_LEFT}" y1="{y:.2f}" x2="{MARGIN_LEFT + plot_width}" '
                f'y2="{y:.2f}" stroke="#E2E8F0"/>',
                f'<text x="{MARGIN_LEFT - 10}" y="{y + 4:.2f}" text-anchor="end" '
                f'font-family="sans-serif" font-size="11" fill="#64748B">{escape(_fmt_number(y_value))}</text>',
            ]
        )
    for index, (label, x_value, y_value, _) in enumerate(data):
        x, y = x_position(x_value), y_position(y_value)
        color = COLORS[index % len(COLORS)]
        tooltip = f"{label}: {x_field}={_fmt_number(x_value)}, {y_field}={_fmt_number(y_value)}"
        body_parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="{color}" '
            f'fill-opacity="0.78" stroke="#FFFFFF" stroke-width="1"><title>{escape(tooltip)}</title></circle>'
        )
    body_parts.extend(
        [
            f'<text x="{MARGIN_LEFT + plot_width / 2:.2f}" y="{height - 28}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="14" fill="#334155">{escape(x_field)}</text>',
            f'<text x="28" y="{MARGIN_TOP + plot_height / 2:.2f}" text-anchor="middle" '
            f'transform="rotate(-90 28 {MARGIN_TOP + plot_height / 2:.2f})" '
            f'font-family="sans-serif" font-size="14" fill="#334155">{escape(y_field)}</text>',
        ]
    )
    return _svg_shell(title, "\n".join(body_parts), height), detail, {
        "status": "ok",
        "reason": None,
        "fields": [x_field, y_field, label_field, "source_url"],
        "denominator": len(data),
        "skipped_rows": skipped,
        "x_domain": [x_min, x_max],
        "y_domain": [y_min, y_max],
    }


def _write_new(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise ChartError(f"输出已存在，拒绝覆盖：{path}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从 normalized JSON/CSV 生成确定性 SVG、明细 CSV 和追溯 manifest。"
    )
    parser.add_argument("input", help="normalized JSON/CSV；- 表示 JSON stdin")
    parser.add_argument("--chart", choices=("funnel", "bar", "scatter"), required=True)
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--name", required=True, help="三个输出文件共用的安全文件名")
    parser.add_argument("--title", help="图表标题；默认根据 chart 类型生成")
    parser.add_argument("--category-field", default="primary_category")
    parser.add_argument("--value-field", help="柱状图数值字段；省略时按行计数")
    parser.add_argument(
        "--include-noise",
        action="store_true",
        help="柱状图包含 is_noise=true 的行；默认排除但不改其分类",
    )
    parser.add_argument("--x-field", default="follower_count")
    parser.add_argument("--y-field", default="like_count")
    parser.add_argument("--label-field", default="content_id")
    parser.add_argument(
        "--filter-description",
        default="none",
        help="写入 manifest 的筛选说明；脚本不会把说明冒充已执行过滤",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload, records, input_name = load_input(args.input)
        title = args.title or {
            "funnel": "Research selection funnel",
            "bar": "Category distribution",
            "scatter": f"{args.x_field} vs {args.y_field}",
        }[args.chart]
        if args.chart == "funnel":
            svg, detail, metadata = render_funnel(payload, records, title)
        elif args.chart == "bar":
            svg, detail, metadata = render_bar(
                records,
                title,
                args.category_field,
                args.value_field,
                args.include_noise,
            )
        else:
            svg, detail, metadata = render_scatter(
                records, title, args.x_field, args.y_field, args.label_field
            )

        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        name = _safe_name(args.name)
        svg_path = output_dir / f"{name}.svg"
        detail_path = output_dir / f"{name}.detail.csv"
        manifest_path = output_dir / f"{name}.manifest.json"
        targets = (svg_path, detail_path, manifest_path)
        existing = [str(path) for path in targets if path.exists()]
        if existing:
            raise ChartError("以下输出已存在，拒绝覆盖：" + ", ".join(existing))

        manifest = {
            "schema_version": "1.0",
            "chart_type": args.chart,
            "status": metadata.pop("status"),
            "reason": metadata.pop("reason"),
            "title": title,
            "input_file": input_name,
            "input_row_count": len(records),
            "filter_description": args.filter_description,
            "outputs": {
                "svg": svg_path.name,
                "detail_csv": detail_path.name,
                "manifest": manifest_path.name,
            },
            **metadata,
        }
        manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        _write_new(svg_path, svg)
        _write_new(detail_path, detail)
        _write_new(manifest_path, manifest_text)
        sys.stdout.write(json.dumps(manifest, ensure_ascii=False) + "\n")
    except ChartError as exc:
        parser.exit(2, f"错误：{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
