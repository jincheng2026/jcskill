#!/usr/bin/env python3
"""Offline business-path tests for jc-media-research."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]
FIXTURES = SKILL_DIR / "tests" / "fixtures"


def load_module(name: str, relative_path: str):
    path = SKILL_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load_module("prepare_research", "scripts/prepare_research.py")
charts = load_module("render_charts", "scripts/render_charts.py")
transcribe = load_module("transcribe_segments", "scripts/transcribe_segments.py")
transcript_ready = load_module(
    "validate_transcript_ready", "scripts/validate_transcript_ready.py"
)
report_preview = load_module("render_report_preview", "scripts/render_report_preview.py")


class ContentPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (FIXTURES / "sanitized_baseline.json").read_text(encoding="utf-8")
        )

    def test_hard_gate_does_not_pad_results(self) -> None:
        result = prepare.prepare_content_records(
            self.fixture["records"], as_of="2026-01-15T10:00:00+08:00"
        )
        self.assertEqual(result["summary"]["eligible_rows"], 1)
        eligible = [row for row in result["records"] if row["qualified"]]
        self.assertEqual([row["content_id"] for row in eligible], ["synthetic-eligible-1"])
        labels = {row["content_id"]: row["eligibility"] for row in result["records"]}
        self.assertEqual(labels["synthetic-low-like"], "unverified_low_likes")
        self.assertEqual(labels["synthetic-anomaly"], "anomaly_low_followers")
        self.assertEqual(labels["synthetic-large-account"], "regular_viral_reference")
        self.assertEqual(labels["synthetic-off-topic"], "off_topic")

    def test_ninety_days_is_preference_not_gate(self) -> None:
        result = prepare.prepare_content_records(
            [self.fixture["records"][0]], as_of="2026-08-01T10:00:00+08:00"
        )
        record = result["records"][0]
        self.assertTrue(record["qualified"])
        self.assertFalse(record["within_preferred_90_days"])

    def test_normalized_record_uses_public_whitelist(self) -> None:
        row = dict(self.fixture["records"][0])
        row["author_id"] = "private-account-id"
        row["source_url"] += "?sign=temporary&device_id=example"
        row["source_file"] = "/private/task/raw/source.json"
        result = prepare.prepare_content_records(
            [row], as_of="2026-01-15T10:00:00+08:00"
        )
        record = result["records"][0]
        self.assertEqual(record["author_id"], "private-account-id")
        self.assertEqual(
            record["source_url"],
            "https://www.douyin.com/video/synthetic-eligible-1",
        )
        self.assertEqual(record["source_file"], "source.json")

    def test_deduplicate_uses_latest_snapshot(self) -> None:
        older = dict(self.fixture["records"][0])
        newer = dict(older)
        newer["collected_at"] = "2026-01-16T10:00:00+08:00"
        newer["digg_count"] = 5000
        result = prepare.prepare_content_records(
            [older, newer], as_of="2026-01-16T10:00:00+08:00"
        )
        self.assertEqual(result["summary"]["duplicates_removed"], 1)
        self.assertEqual(result["records"][0]["like_count"], 5000)

    def test_tikhub_search_raw_directory_is_unwrapped_with_provenance(self) -> None:
        def raw_payload(timestamp: int, likes: int) -> dict:
            return {
                "time_stamp": timestamp,
                "params": {"keyword": "合成关键词"},
                "data": {
                    "business_data": [
                        {
                            "data": {
                                "aweme_info": {
                                    "aweme_id": "synthetic-raw-1",
                                    "desc": "合成 AI 教程",
                                    "author": {
                                        "nickname": "示例作者",
                                        "follower_count": 1000,
                                    },
                                    "statistics": {
                                        "digg_count": likes,
                                        "comment_count": 10,
                                        "collect_count": 20,
                                        "share_count": 5,
                                    },
                                    "create_time": 1768006800,
                                    "share_url": "https://example.invalid/signed?sign=synthetic",
                                }
                            }
                        }
                    ]
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "page-1.json").write_text(
                json.dumps(raw_payload(1768442400, 1500)), encoding="utf-8"
            )
            (root / "page-2.json").write_text(
                json.dumps(raw_payload(1768446000, 1600)), encoding="utf-8"
            )
            rows = prepare.load_records(str(root))
        self.assertEqual(len(rows), 2)
        result = prepare.prepare_content_records(
            rows,
            as_of="2026-01-15T12:00:00Z",
            default_relevance="direct",
            relevance_reason="合成输入整批直接相关。",
        )
        self.assertEqual(result["summary"]["duplicates_removed"], 1)
        record = result["records"][0]
        self.assertEqual(record["like_count"], 1600)
        self.assertEqual(record["source_file"], "page-2.json")
        self.assertIsNotNone(record["collected_at"])
        self.assertEqual(record["evidence_issues"], [])


class CommentPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (FIXTURES / "edge_cases.json").read_text(encoding="utf-8")
        )

    def test_comment_percentages_are_row_based(self) -> None:
        result = prepare.prepare_comment_records(self.fixture["comments"], denominator="non-noise")
        summary = result["summary"]
        self.assertEqual(summary["deduplicated_rows"], 3)
        self.assertEqual(summary["noise_rows"], 1)
        self.assertEqual(summary["denominator"], 2)
        counts = {
            item["primary_category"]: item["count"]
            for item in summary["category_statistics"]
        }
        self.assertEqual(counts, {"使用问题": 1, "结果反馈": 1})
        self.assertTrue(all(row["source_url"] for row in result["records"]))

    def test_unclassified_is_explicit(self) -> None:
        row = dict(self.fixture["comments"][0])
        row.pop("primary_category")
        result = prepare.prepare_comment_records([row])
        record = result["records"][0]
        self.assertEqual(record["primary_category"], "未分类")
        self.assertEqual(record["classification_status"], "unclassified")


class ChartAndTranscriptTests(unittest.TestCase):
    def test_chart_has_svg_detail_and_manifest(self) -> None:
        payload = prepare.prepare_content_records(
            json.loads(
                (FIXTURES / "sanitized_baseline.json").read_text(encoding="utf-8")
            )["records"],
            as_of="2026-01-15T10:00:00+08:00",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "normalized.json"
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                result = charts.main(
                    [
                        str(input_path),
                        "--chart",
                        "scatter",
                        "--output-dir",
                        str(root / "charts"),
                        "--name",
                        "followers-likes",
                    ]
                )
            self.assertEqual(result, 0)
            chart_dir = root / "charts"
            self.assertTrue((chart_dir / "followers-likes.svg").is_file())
            self.assertTrue((chart_dir / "followers-likes.detail.csv").is_file())
            manifest = json.loads(
                (chart_dir / "followers-likes.manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["chart_type"], "scatter")
            self.assertEqual(manifest["status"], "ok")

    def test_transcript_layers_do_not_store_absolute_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media = root / "synthetic.wav"
            media.write_bytes(b"synthetic-media")
            output = root / "transcript"
            records = [
                {
                    "segment": 1,
                    "start_seconds": 0.0,
                    "end_seconds": 28.0,
                    "text": "合成转写文本",
                }
            ]
            manifest = transcribe.write_outputs(
                output_dir=output,
                media=media,
                records=records,
                duration=28.0,
                segment_seconds=28,
            )
            self.assertEqual(manifest["status"], "transcribed_pending_review")
            serialized = (output / "manifest.json").read_text(encoding="utf-8")
            self.assertNotIn(str(root), serialized)
            self.assertTrue((output / "raw" / "segments.jsonl").is_file())
            self.assertTrue((output / "review" / "transcript_review.md").is_file())
            self.assertTrue((output / "corrected" / "transcript_corrected.md").is_file())
            with self.assertRaises(FileExistsError):
                transcribe.write_outputs(
                    output_dir=output,
                    media=media,
                    records=records,
                    duration=28.0,
                    segment_seconds=28,
                )

    def test_pending_review_transcript_is_blocked_from_structure_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media = root / "synthetic.wav"
            media.write_bytes(b"synthetic-media")
            output = root / "transcript"
            transcribe.write_outputs(
                output_dir=output,
                media=media,
                records=[
                    {
                        "segment": 1,
                        "start_seconds": 0.0,
                        "end_seconds": 28.0,
                        "text": "这是只用于离线测试的合成转写文本。",
                    }
                ],
                duration=28.0,
                segment_seconds=28,
            )
            with self.assertRaisesRegex(
                transcript_ready.TranscriptNotReady, "校正复核"
            ):
                transcript_ready.validate_transcript(output)

    def test_validated_transcript_passes_structure_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media = root / "synthetic.wav"
            media.write_bytes(b"synthetic-media")
            output = root / "transcript"
            transcribe.write_outputs(
                output_dir=output,
                media=media,
                records=[
                    {
                        "segment": 1,
                        "start_seconds": 0.0,
                        "end_seconds": 28.0,
                        "text": "这是只用于离线测试的合成转写文本。",
                    }
                ],
                duration=28.0,
                segment_seconds=28,
            )
            manifest_path = output / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["status"] = "corrected_validated"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            corrected = "这是一段已经完成复核的合成校正版逐字稿。" * 8
            (output / "corrected" / "transcript_corrected.md").write_text(
                corrected, encoding="utf-8"
            )
            result = transcript_ready.validate_transcript(output)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["segment_count"], 1)

    def test_png_preview_validation_reads_real_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "preview.png"
            path.write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + b"\x00\x00\x00\x0dIHDR"
                + struct.pack(">II", 1440, 4200)
            )
            self.assertEqual(report_preview.png_dimensions(path), (1440, 4200))


class SkillContractTests(unittest.TestCase):
    def test_evals_cover_user_paths_stops_and_one_shot_contract(self) -> None:
        payload = json.loads((SKILL_DIR / "evals" / "evals.json").read_text(encoding="utf-8"))
        evals_by_id = {item["id"]: item for item in payload["evals"]}
        ids = set(evals_by_id)
        self.assertTrue(
            {
                "keyword-research-no-padding",
                "keyword-research-one-shot",
                "three-results-final-no-reconfirm",
                "zero-results-final-no-reconfirm",
                "cost-over-limit-one-question",
                "missing-topic-one-question",
                "real-failure-no-retry",
                "report-four-data-driven-charts",
                "report-chart-honest-fallback",
                "report-zero-input-no-fabrication",
                "report-preview-visible-in-chat",
                "video-pending-transcript-blocks-timeline",
                "single-video-needs-transcript",
                "account-pattern-boundary",
                "script-needs-user-material",
                "script-from-prior-research-one-shot",
                "script-quality-and-visual-plan",
                "paid-gate",
                "public-package-stop",
            }.issubset(ids)
        )

        no_followup_ids = {
            "keyword-research-no-padding",
            "keyword-research-one-shot",
            "three-results-final-no-reconfirm",
            "zero-results-final-no-reconfirm",
            "report-four-data-driven-charts",
            "report-chart-honest-fallback",
            "report-zero-input-no-fabrication",
            "report-preview-visible-in-chat",
            "script-from-prior-research-one-shot",
            "script-quality-and-visual-plan",
        }
        forbidden_phrases = {
            "APPROVE",
            "请确认计划",
            "要不要继续",
            "是否继续",
            "请选择要深挖",
            "你确认后我再",
        }
        for eval_id in no_followup_ids:
            contract = evals_by_id[eval_id]
            self.assertEqual(contract["max_followups"], 0)
            self.assertEqual(contract["allowed_followup_reasons"], [])
            self.assertEqual(contract["expected_status"], "completed")
            self.assertTrue(forbidden_phrases.issubset(set(contract["forbidden"])))

        chart_contract = "\n".join(
            evals_by_id["report-four-data-driven-charts"]["expected"]
        )
        for required_chart in (
            "筛选漏斗",
            "粉丝—点赞散点图",
            "粉丝分层梯形图",
            "排除原因水平条形图",
        ):
            self.assertIn(required_chart, chart_contract)
        fallback_contract = "\n".join(
            evals_by_id["report-zero-input-no-fabrication"]["expected"]
        )
        self.assertIn("真实空状态", fallback_contract)
        self.assertIn("不补造", fallback_contract)

        one_question_reasons = {
            "cost-over-limit-one-question": "cost_limit_exceeded",
            "missing-topic-one-question": "required_input_missing",
            "real-failure-no-retry": "execution_failed",
        }
        for eval_id, reason in one_question_reasons.items():
            contract = evals_by_id[eval_id]
            self.assertEqual(contract["max_followups"], 1)
            self.assertEqual(contract["allowed_followup_reasons"], [reason])
            self.assertEqual(contract["expected_status"], "needs_user_input")


if __name__ == "__main__":
    unittest.main()
