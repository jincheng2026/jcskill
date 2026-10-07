#!/usr/bin/env python3
"""Offline regression tests for the self-contained research brief."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "render_report.py"


def load_module():
    spec = importlib.util.spec_from_file_location("render_report", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


renderer = load_module()


def record(
    content_id: str,
    title: str,
    *,
    qualified: bool,
    rank: int | None,
    followers: int,
    likes: int,
    eligibility: str = "eligible_low_follower_viral",
    reasons: list[str] | None = None,
    within_90_days: bool | None = True,
    age_days: int | None = 9,
) -> dict:
    return {
        "schema_version": 1,
        "platform": "douyin",
        "content_id": content_id,
        "title": title,
        "caption": f"{title} 的合成说明",
        "author_name": f"作者-{content_id}",
        "follower_count": followers,
        "like_count": likes,
        "comment_count": 80 + likes % 7,
        "collect_count": 320 + likes % 11,
        "share_count": 45 + likes % 5,
        "published_at": "2026-08-01T10:00:00+08:00",
        "collected_at": "2026-08-10T10:00:00+08:00",
        "source_url": f"https://www.douyin.com/video/{content_id}",
        "source_file": f"raw/{content_id}-response.json",
        "relevance": "direct",
        "direct_related": True,
        "relevance_reason": "标题和正文直接解决 AI 教程制作问题。",
        "age_days_at_research": age_days,
        "within_preferred_90_days": within_90_days,
        "qualified": qualified,
        "eligibility": eligibility,
        "exclusion_reasons": reasons or [],
        "evidence_issues": [],
        "eligible_rank": rank,
    }


def payload_with_three_eligible() -> dict:
    records = [
        record(
            "eligible-3",
            "新样本原排序第三",
            qualified=True,
            rank=3,
            followers=1800,
            likes=2100,
            within_90_days=True,
            age_days=81,
        ),
        record(
            "low-like",
            "点赞不足样本",
            qualified=False,
            rank=None,
            followers=900,
            likes=999,
            eligibility="unverified_low_likes",
            reasons=["likes_below_1000_unverified"],
        ),
        record(
            "eligible-1",
            "旧样本原排序第一",
            qualified=True,
            rank=1,
            followers=1200,
            likes=5200,
            within_90_days=False,
            age_days=149,
        ),
        record(
            "large-account",
            "大账号参考样本",
            qualified=False,
            rank=None,
            followers=25_000,
            likes=9000,
            eligibility="regular_viral_reference",
            reasons=["followers_above_20000_reference_only"],
        ),
        record(
            "eligible-2",
            "新样本原排序第二",
            qualified=True,
            rank=2,
            followers=1500,
            likes=3600,
            within_90_days=True,
            age_days=3,
        ),
    ]
    return {
        "schema_version": 1,
        "record_type": "content_research",
        "as_of": "2026-08-10T10:00:00+08:00",
        "gate": {
            "platform": "douyin",
            "followers_min_inclusive": 100,
            "followers_max_inclusive": 20_000,
            "likes_min_inclusive": 1_000,
            "direct_relevance_required": True,
            "preferred_age_days": 90,
            "preferred_age_is_not_a_hard_gate": True,
        },
        "summary": {
            "input_rows": 7,
            "deduplicated_rows": 5,
            "duplicates_removed": 2,
            "eligible_rows": 3,
            "excluded_rows": 2,
            "exclusion_counts": {
                "followers_above_20000_reference_only": 1,
                "likes_below_1000_unverified": 1,
            },
            "funnel": [
                {"stage": "input", "count": 7},
                {"stage": "deduplicated", "count": 5},
                {"stage": "directly_relevant", "count": 5},
                {"stage": "followers_100_to_20000", "count": 4},
                {"stage": "likes_at_least_1000", "count": 3},
            ],
        },
        "records": records,
    }


class ReportRendererTests(unittest.TestCase):
    def test_report_embeds_four_distinct_data_driven_svg_charts(self) -> None:
        payload = payload_with_three_eligible()
        specs = renderer.chart_specs(payload)
        self.assertEqual([s["kind"] for s in specs], ["funnel", "scatter", "funnel", "bar"])
        self.assertEqual(specs[0]["values"], [7, 5, 5, 4, 3])
        self.assertEqual(len(specs[1]["points"]), 5)
        self.assertEqual(sum(p["eligible"] for p in specs[1]["points"]), 3)
        self.assertEqual(specs[3]["values"], [1, 1])
        rendered = renderer.render_report(payload)
        for spec in specs:
            self.assertIn('id="' + spec["id"] + '"', rendered)
        self.assertIn('echarts.init', rendered)
        self.assertIn('id="chart-data"', rendered)
        self.assertNotIn('<script src=', rendered)

    def test_follower_tiers_use_real_counts(self) -> None:
        records = []
        for prefix, followers, count in (
            ("low", 3_000, 3),
            ("small", 50_000, 6),
            ("medium", 500_000, 8),
            ("large", 2_000_000, 3),
        ):
            records.extend(
                record(
                    f"{prefix}-{index}",
                    f"{prefix}-{index}",
                    qualified=prefix == "low",
                    rank=index if prefix == "low" else None,
                    followers=followers,
                    likes=2_000,
                )
                for index in range(1, count + 1)
            )

        tiers, below_minimum, missing = renderer._follower_tiers(records)
        self.assertEqual([count for _, _, count in tiers], [3, 6, 8, 3])
        self.assertEqual(below_minimum, 0)
        self.assertEqual(missing, 0)
        rendered = renderer._follower_tiers_svg(records)
        for key, expected in zip(("low", "small", "medium", "large"), (3, 6, 8, 3)):
            self.assertRegex(
                rendered,
                rf'data-tier="{key}" data-count="{expected}"',
            )

    def test_zero_input_keeps_honest_chart_slots_without_fake_marks(self) -> None:
        payload = {
            "schema_version": 1,
            "record_type": "content_research",
            "as_of": "2026-08-10T10:00:00+08:00",
            "summary": {
                "input_rows": 0,
                "deduplicated_rows": 0,
                "duplicates_removed": 0,
                "eligible_rows": 0,
                "excluded_rows": 0,
                "exclusion_counts": {},
                "funnel": [
                    {"stage": "input", "count": 0},
                    {"stage": "deduplicated", "count": 0},
                    {"stage": "likes_at_least_1000", "count": 0},
                ],
            },
            "records": [],
        }

        rendered = renderer.render_report(payload)
        self.assertEqual(len(renderer.chart_specs(payload)), 4)
        self.assertEqual(renderer.chart_specs(payload)[1]["points"], [])
        self.assertEqual(renderer.chart_specs(payload)[3]["values"], [])
        self.assertIn("可用数据点为 0", rendered)
        self.assertIn("缺失字段或空样本未补值", rendered)
        self.assertNotIn('class="scatter-point ', rendered)
        self.assertNotIn('class="reason-bar"', rendered)
        self.assertNotRegex(json.dumps(renderer.chart_specs(payload), allow_nan=False), r"\b(?:NaN|Infinity)\b")

    def test_missing_numeric_fields_do_not_create_scatter_points(self) -> None:
        incomplete = record(
            "missing-numeric",
            "数值字段不完整",
            qualified=False,
            rank=None,
            followers=500,
            likes=2_000,
        )
        incomplete["follower_count"] = None
        payload = payload_with_three_eligible()
        payload["records"] = [incomplete]
        payload["summary"].update(
            {
                "input_rows": 1,
                "deduplicated_rows": 1,
                "eligible_rows": 0,
                "excluded_rows": 1,
            }
        )

        rendered = renderer.render_report(payload)
        self.assertEqual(renderer.chart_specs(payload)[1]["points"], [])
        self.assertEqual(renderer.chart_specs(payload)[1]["missing"], 1)
        self.assertNotIn('class="scatter-point ', rendered)

    def test_three_eligible_renders_summary_recency_and_original_metrics(self) -> None:
        rendered = renderer.render_report(payload_with_three_eligible(), "AI 教程低粉爆款")

        self.assertIn("AI 教程低粉爆款", rendered)
        self.assertIn("最终有 3 条同时达到", rendered)
        self.assertIn('data-stat="input"', rendered)
        self.assertIn('data-stat="deduplicated"', rendered)
        self.assertIn('data-stat="eligible"', rendered)
        self.assertIn('data-stat="excluded"', rendered)
        self.assertRegex(rendered, r'data-stat="input"[\s\S]*?<strong>7</strong>')
        self.assertRegex(rendered, r'data-stat="deduplicated"[\s\S]*?<strong>5</strong>')
        self.assertRegex(rendered, r'data-stat="eligible"[\s\S]*?<strong>3</strong>')
        self.assertRegex(rendered, r'data-stat="excluded"[\s\S]*?<strong>2</strong>')
        self.assertIn("搜索返回", rendered)
        self.assertIn("去重后", rendered)
        self.assertIn("合格低粉爆款", rendered)
        self.assertIn("排除样本", rendered)
        self.assertIn("stat-card--eligible", rendered)
        self.assertIn("stat-card--excluded", rendered)

        self.assertIn("筛选漏斗", rendered)
        self.assertIn('data-stage="input"', rendered)
        self.assertIn('data-stage="likes_at_least_1000"', rendered)
        self.assertIn("透明原始指标", rendered)
        self.assertIn("排除样本怎么看", rendered)
        self.assertIn("点赞少于 1,000", rendered)
        self.assertIn("研究范围与限制", rendered)
        self.assertIn("直接可见的限制", rendered)
        self.assertIn("来源链接", rendered)
        self.assertIn("https://www.douyin.com/video/eligible-1", rendered)
        self.assertIn("90 天内", rendered)
        self.assertIn("超 90 天", rendered)
        self.assertIn("距研究日 3 天", rendered)
        self.assertIn("距研究日 149 天", rendered)
        self.assertIn("查看原始标题", rendered)
        self.assertIn("评论只作次级观察", rendered)
        self.assertNotIn("PRIORITY", rendered.split("<script>",1)[0])
        self.assertNotIn("data-eligible-rank", rendered)

        recent_rank_two = rendered.index("新样本原排序第二")
        recent_rank_three = rendered.index("新样本原排序第三")
        old_rank_one = rendered.index("旧样本原排序第一")
        self.assertLess(recent_rank_two, recent_rank_three)
        self.assertLess(recent_rank_three, old_rank_one)

    def test_zero_eligible_generates_a_complete_report_without_padding(self) -> None:
        low_like = record(
            "only-low-like",
            "唯一候选但点赞不足",
            qualified=False,
            rank=None,
            followers=1100,
            likes=650,
            eligibility="unverified_low_likes",
            reasons=["likes_below_1000_unverified"],
        )
        payload = {
            "schema_version": 1,
            "record_type": "content_research",
            "as_of": "2026-08-10T10:00:00+08:00",
            "summary": {
                "input_rows": 1,
                "deduplicated_rows": 1,
                "duplicates_removed": 0,
                "eligible_rows": 0,
                "excluded_rows": 1,
                "exclusion_counts": {"likes_below_1000_unverified": 1},
                "funnel": [
                    {"stage": "input", "count": 1},
                    {"stage": "deduplicated", "count": 1},
                    {"stage": "directly_relevant", "count": 1},
                    {"stage": "followers_100_to_20000", "count": 1},
                    {"stage": "likes_at_least_1000", "count": 0},
                ],
            },
            "records": [low_like],
        }

        rendered = renderer.render_report(payload)
        self.assertIn("没有样本同时通过", rendered)
        self.assertIn("不降低标准凑数", rendered)
        self.assertIn("本轮没有合格选题", rendered)
        self.assertNotIn("PRIORITY", rendered.split("<script>",1)[0])
        self.assertIn("唯一候选但点赞不足", rendered)
        self.assertIn('data-stage="likes_at_least_1000"', rendered)

    def test_exclusions_show_only_three_closest_before_native_details(self) -> None:
        payload = payload_with_three_eligible()
        excluded = [
            record(
                "over-closest",
                "刚超过上限",
                qualified=False,
                rank=None,
                followers=20_001,
                likes=8000,
                eligibility="regular_viral_reference",
                reasons=["followers_above_20000_reference_only"],
            ),
            record(
                "under-closest",
                "略低于上限但因其他门槛排除",
                qualified=False,
                rank=None,
                followers=19_990,
                likes=600,
                eligibility="unverified_low_likes",
                reasons=["likes_below_1000_unverified"],
            ),
            record(
                "over-next",
                "其次接近上限",
                qualified=False,
                rank=None,
                followers=20_050,
                likes=7000,
                eligibility="regular_viral_reference",
                reasons=["followers_above_20000_reference_only"],
            ),
            record(
                "far-one",
                "距离上限很远一",
                qualified=False,
                rank=None,
                followers=80_000,
                likes=9000,
                eligibility="regular_viral_reference",
                reasons=["followers_above_20000_reference_only"],
            ),
            record(
                "far-two",
                "距离上限很远二",
                qualified=False,
                rank=None,
                followers=150_000,
                likes=10_000,
                eligibility="regular_viral_reference",
                reasons=["followers_above_20000_reference_only"],
            ),
        ]
        payload["records"] = excluded
        payload["summary"].update(
            {
                "input_rows": 5,
                "deduplicated_rows": 5,
                "eligible_rows": 0,
                "excluded_rows": 5,
                "exclusion_counts": {
                    "followers_above_20000_reference_only": 4,
                    "likes_below_1000_unverified": 1,
                },
            }
        )

        rendered = renderer.render_report(payload)
        before_details = rendered.split('<details class="all-exclusions">', 1)[0]
        self.assertIn("刚超过上限", before_details)
        self.assertIn("略低于上限但因其他门槛排除", before_details)
        self.assertIn("其次接近上限", before_details)
        self.assertNotIn("距离上限很远一", before_details)
        self.assertNotIn("距离上限很远二", before_details)
        self.assertIn('<details class="all-exclusions">', rendered)
        self.assertIn("查看全部排除明细", rendered)
        self.assertIn("5 条", rendered)
        self.assertIn("距离上限很远一", rendered)
        self.assertIn("距离上限很远二", rendered)

    def test_output_uses_a_field_allowlist_and_redacts_sensitive_text(self) -> None:
        unsafe = record(
            "safe-id",
            "<script>alert('x')</script>",
            qualified=True,
            rank=1,
            followers=800,
            likes=4000,
        )
        private_root = "/" + "Users/example/private"
        unsafe["source_file"] = f"{private_root}/raw/secret-response.json"
        unsafe["relevance_reason"] = (
            f"材料位于 {private_root}/raw/input.json ；"
            "另外 api" + "_key=" + "abcdefghijklmnop"
        )
        unsafe["response_body"] = "PRIVATE_RESPONSE_BODY_SENTINEL"
        unsafe["authentication_token"] = "PRIVATE_TOKEN_SENTINEL"
        unsafe["source_url"] = (
            "https://www.douyin.com/video/safe-id?" + "token=private-value"
        )
        payload = payload_with_three_eligible()
        payload["records"] = [unsafe]
        payload["summary"]["eligible_rows"] = 1
        payload["summary"]["excluded_rows"] = 0

        rendered = renderer.render_report(payload, f"{private_root}/report")
        self.assertNotIn(private_root, rendered)
        self.assertNotIn("secret-response.json", rendered)
        self.assertNotIn("PRIVATE_RESPONSE_BODY_SENTINEL", rendered)
        self.assertNotIn("PRIVATE_TOKEN_SENTINEL", rendered)
        self.assertNotIn("abcdefghijklmnop", rendered)
        self.assertNotIn("private-value", rendered)
        self.assertNotIn("<script>alert", rendered.lower())
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("【已隐藏本机路径】", rendered)
        self.assertIn("【已隐藏敏感信息】", rendered)
        self.assertIn("来源链接缺失", rendered)

    def test_html_is_single_file_responsive_and_has_no_ai_gradient_style(self) -> None:
        rendered = renderer.render_report(payload_with_three_eligible())
        lowered = rendered.lower()
        self.assertTrue(lowered.startswith("<!doctype html>"))
        self.assertIn('<meta name="viewport"', lowered)
        self.assertIn("<style>", lowered)
        self.assertIn("@media (max-width: 720px)", lowered)
        self.assertIn("overflow-wrap: anywhere", lowered)
        self.assertIn(".stats { grid-template-columns: repeat(2, 1fr); }", lowered)
        self.assertNotIn(".stats { grid-template-columns: 1fr; }", lowered)
        self.assertIn(".chart-grid, .topic-list, .closest-grid, .excluded-detail-grid { grid-template-columns: 1fr; }", lowered)
        self.assertIn(".chart-svg { display: block; width: 100%; max-width: 100%; height: auto;", lowered)
        self.assertIn(".scope-layout { display: grid; grid-template-columns:", lowered)
        self.assertNotIn("<link", lowered)
        self.assertNotRegex(lowered, r"<script[^>]+src=")
        self.assertNotRegex(lowered.split("</head>")[0], r"url\s*\(")
        self.assertNotIn("linear-gradient", lowered.split("</head>")[0])
        self.assertNotIn("radial-gradient", lowered.split("</head>")[0])
        self.assertNotIn("#7c3aed", lowered)
        self.assertIn("--paper: #f3eee4", lowered)
        self.assertIn("--ink: #10263c", lowered)
        self.assertIn("--red: #aa3b2e", lowered)

    def test_cli_accepts_required_arguments_and_custom_title(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "normalized.json"
            output_path = root / "brief.html"
            input_path.write_text(
                json.dumps(payload_with_three_eligible(), ensure_ascii=False),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--title",
                    "CLI 自定义标题",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output_path.is_file())
            self.assertIn("CLI 自定义标题", output_path.read_text(encoding="utf-8"))
            status = json.loads(result.stdout)
            self.assertTrue(status["ok"])
            self.assertEqual(status["output"], "brief.html")

    def test_invalid_top_level_is_rejected(self) -> None:
        with self.assertRaises(renderer.ReportError):
            renderer.render_report([])
        with self.assertRaises(renderer.ReportError):
            renderer.render_report({"records": "not-a-list"})


if __name__ == "__main__":
    unittest.main()
