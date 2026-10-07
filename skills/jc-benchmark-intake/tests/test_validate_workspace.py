from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_workspace.py"
SPEC = importlib.util.spec_from_file_location("validate_workspace", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


CORRECTED = "# 校正版逐字稿\n\n完整校正版内容。\n"
GOOD_SRT = "1\n00:00:00,500 --> 00:00:02,000\n完整校正版内容。\n"


def note_text(item_id: str, link: str) -> str:
    return f"""# 测试作品

> 入库日期：2025-01-01
> 平台：抖音
> 作品 ID：{item_id}

## 基础信息

| 字段 | 内容 |
| --- | --- |
| 作品链接 | {link} |
| 作品描述 | 这是一段用于验证入库脚本的真实输入占位文本，不承担内容判断。 |

## 原始复制内容

这里保留用户复制的原始作品信息。为了满足可读正文检查，本段包含足够长度的测试文字，并明确它只属于测试夹具，不代表真实平台内容或用户结论。
"""


def video_note_text(item_id: str, link: str, *, include_validation_link: bool = False) -> str:
    validation_link = "- 转写证据：[[转写/validation.json]]\n" if include_validation_link else ""
    return note_text(item_id, link) + f"""

## 本地媒体

- 视频：`视频.mp4`
- SHA-256：`{'a' * 64}`

## 校正版逐字稿

{validation_link}- 校正版文件：[[转写/校正版逐字稿/校正版逐字稿.md]]

这是经过复核的完整校正版逐字稿，用于验证正式目录只保留校正版文件。
"""


class ValidateWorkspaceTests(unittest.TestCase):
    def make_work(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        work = Path(temp.name)
        for status in ("已参考", "未参考"):
            for platform in ("抖音", "小红书"):
                (work / MODULE.CONTENT_DIR / status / platform).mkdir(parents=True)
        return temp, work

    def test_valid_text_item_passes(self) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        folder = work / MODULE.CONTENT_DIR / "未参考" / "抖音" / "抖音_测试作品_123456789"
        folder.mkdir()
        (folder / "笔记信息.md").write_text(
            note_text("123456789", "https://www.douyin.com/video/123456789"), encoding="utf-8"
        )
        report = MODULE.build_report(work, str(folder), strict=True)
        self.assertTrue(report["ok"], report)

    def test_duplicate_id_is_blocked(self) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        first = work / MODULE.CONTENT_DIR / "已参考" / "抖音" / "抖音_甲_123456789"
        second = work / MODULE.CONTENT_DIR / "未参考" / "抖音" / "抖音_乙_123456789"
        first.mkdir()
        second.mkdir()
        (first / "笔记信息.md").write_text(
            note_text("123456789", "https://www.douyin.com/video/123456789"), encoding="utf-8"
        )
        (second / "笔记信息.md").write_text(
            note_text("123456789", "https://example.com/video/123456789"), encoding="utf-8"
        )
        report = MODULE.build_report(work, str(second), strict=True)
        self.assertFalse(report["ok"])
        codes = {item["code"] for item in report["results"][0]["issues"]}
        self.assertIn("duplicate_id", codes)

    def test_missing_note_is_blocked(self) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        folder = work / MODULE.CONTENT_DIR / "未参考" / "抖音" / "抖音_空目录_999999999"
        folder.mkdir()
        report = MODULE.build_report(work, str(folder), strict=True)
        self.assertFalse(report["ok"])
        self.assertEqual(report["results"][0]["issues"][0]["code"], "missing_note")

    def test_default_scan_reads_both_reference_states(self) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        for status, item_id in (("已参考", "123456789"), ("未参考", "987654321")):
            folder = work / MODULE.CONTENT_DIR / status / "抖音" / f"抖音_测试_{item_id}"
            folder.mkdir()
            (folder / "笔记信息.md").write_text(
                note_text(item_id, f"https://www.douyin.com/video/{item_id}"), encoding="utf-8"
            )
        report = MODULE.build_report(work, target=None, strict=True)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["checked"], 2)

    @patch.object(MODULE, "sha256_file", return_value="a" * 64)
    @patch.object(MODULE, "validate_video", return_value=(True, "duration=10.000s"))
    def test_formal_video_with_corrected_only_passes(self, _video: object, _hash: object) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        folder = work / MODULE.CONTENT_DIR / "已参考" / "抖音" / "抖音_校正版_123456789"
        corrected = folder / "转写" / "校正版逐字稿" / "校正版逐字稿.md"
        corrected.parent.mkdir(parents=True)
        corrected.write_text("# 校正版逐字稿\n\n完整校正版内容。\n", encoding="utf-8")
        (folder / "视频.mp4").write_bytes(b"video")
        (folder / "笔记信息.md").write_text(
            video_note_text("123456789", "https://www.douyin.com/video/123456789"), encoding="utf-8"
        )
        report = MODULE.build_report(work, str(folder), strict=True)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["results"][0]["counts"]["transcript_intermediates"], 0)

    @patch.object(MODULE, "sha256_file", return_value="a" * 64)
    @patch.object(MODULE, "validate_video", return_value=(True, "duration=10.000s"))
    def test_formal_video_with_intermediates_is_blocked(self, _video: object, _hash: object) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        folder = work / MODULE.CONTENT_DIR / "未参考" / "抖音" / "抖音_残留版本_123456789"
        corrected = folder / "转写" / "校正版逐字稿" / "校正版逐字稿.md"
        corrected.parent.mkdir(parents=True)
        corrected.write_text("# 校正版逐字稿\n\n完整校正版内容。\n", encoding="utf-8")
        raw = folder / "转写" / "原始识别" / "001.txt"
        raw.parent.mkdir()
        raw.write_text("原始识别内容", encoding="utf-8")
        (folder / "转写" / "validation.json").write_text("{}\n", encoding="utf-8")
        (folder / "视频.mp4").write_bytes(b"video")
        (folder / "笔记信息.md").write_text(
            video_note_text(
                "123456789", "https://www.douyin.com/video/123456789", include_validation_link=True
            ),
            encoding="utf-8",
        )
        report = MODULE.build_report(work, str(folder), strict=True)
        self.assertFalse(report["ok"])
        codes = {item["code"] for item in report["results"][0]["issues"]}
        self.assertIn("transcript_intermediates_retained", codes)
        self.assertIn("stale_transcript_link", codes)

    @patch.object(MODULE, "sha256_file", return_value="a" * 64)
    @patch.object(MODULE, "validate_video", return_value=(True, "duration=10.000s"))
    def test_staging_video_keeps_evidence_until_validation(self, _video: object, _hash: object) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        folder = work / MODULE.CONTENT_DIR / ".staging" / "抖音_待验收_123456789"
        corrected = folder / "转写" / "校正版逐字稿" / "校正版逐字稿.md"
        corrected.parent.mkdir(parents=True)
        corrected.write_text("# 校正版逐字稿\n\n完整校正版内容。\n", encoding="utf-8")
        raw = folder / "转写" / "原始识别" / "001.txt"
        raw.parent.mkdir()
        raw.write_text("原始识别内容", encoding="utf-8")
        (folder / "转写" / "validation.json").write_text("{}\n", encoding="utf-8")
        corrected.with_suffix(".srt").write_text(GOOD_SRT, encoding="utf-8")
        (folder / "视频.mp4").write_bytes(b"video")
        (folder / "笔记信息.md").write_text(
            video_note_text(
                "123456789", "https://www.douyin.com/video/123456789", include_validation_link=True
            ),
            encoding="utf-8",
        )
        report = MODULE.build_report(work, str(folder), strict=True)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["results"][0]["counts"]["srt_files"], 1)

    def make_video_item(self, work: Path, place: str, *, srt: str | None) -> Path:
        folder = work / MODULE.CONTENT_DIR / place / "抖音_字幕_123456789"
        corrected = folder / "转写" / "校正版逐字稿" / "校正版逐字稿.md"
        corrected.parent.mkdir(parents=True)
        corrected.write_text(CORRECTED, encoding="utf-8")
        if place == ".staging":
            (folder / "转写" / "validation.json").write_text("{}\n", encoding="utf-8")
        if srt is not None:
            corrected.with_suffix(".srt").write_text(srt, encoding="utf-8")
        (folder / "视频.mp4").write_bytes(b"video")
        (folder / "笔记信息.md").write_text(
            video_note_text("123456789", "https://www.douyin.com/video/123456789"), encoding="utf-8"
        )
        return folder

    def codes(self, report: dict[str, object]) -> set[str]:
        return {item["code"] for item in report["results"][0]["issues"]}

    @patch.object(MODULE, "sha256_file", return_value="a" * 64)
    @patch.object(MODULE, "validate_video", return_value=(True, "duration=10.000s"))
    def test_staging_video_without_srt_is_blocked(self, _video: object, _hash: object) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        folder = self.make_video_item(work, ".staging", srt=None)
        report = MODULE.build_report(work, str(folder), strict=True)
        self.assertFalse(report["ok"])
        self.assertIn("srt_missing", self.codes(report))

    @patch.object(MODULE, "sha256_file", return_value="a" * 64)
    @patch.object(MODULE, "validate_video", return_value=(True, "duration=10.000s"))
    def test_legacy_formal_item_without_srt_passes_unless_required(self, _video: object, _hash: object) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        folder = self.make_video_item(work, "未参考/抖音", srt=None)
        self.assertTrue(MODULE.build_report(work, str(folder), strict=True)["ok"])
        required = MODULE.build_report(work, str(folder), strict=True, require_srt=True)
        self.assertFalse(required["ok"])
        self.assertIn("srt_missing", self.codes(required))

    @patch.object(MODULE, "sha256_file", return_value="a" * 64)
    @patch.object(MODULE, "validate_video", return_value=(True, "duration=10.000s"))
    def test_formal_item_with_good_srt_passes_when_required(self, _video: object, _hash: object) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        folder = self.make_video_item(work, "未参考/抖音", srt=GOOD_SRT)
        report = MODULE.build_report(work, str(folder), strict=True, require_srt=True)
        self.assertTrue(report["ok"], report)

    @patch.object(MODULE, "sha256_file", return_value="a" * 64)
    @patch.object(MODULE, "validate_video", return_value=(True, "duration=10.000s"))
    def test_srt_with_overlapping_times_is_blocked(self, _video: object, _hash: object) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        bad = "1\n00:00:01,000 --> 00:00:03,000\n完整校正版\n\n2\n00:00:02,000 --> 00:00:04,000\n内容。\n"
        folder = self.make_video_item(work, "未参考/抖音", srt=bad)
        report = MODULE.build_report(work, str(folder), strict=True, require_srt=True)
        self.assertFalse(report["ok"])
        self.assertIn("srt_not_increasing", self.codes(report))

    @patch.object(MODULE, "sha256_file", return_value="a" * 64)
    @patch.object(MODULE, "validate_video", return_value=(True, "duration=10.000s"))
    def test_srt_past_video_end_or_stale_text_is_blocked(self, _video: object, _hash: object) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        bad = "1\n00:00:09,000 --> 00:00:15,000\n完整校正版改过的内容。\n"
        folder = self.make_video_item(work, "未参考/抖音", srt=bad)
        report = MODULE.build_report(work, str(folder), strict=True, require_srt=True)
        self.assertFalse(report["ok"])
        self.assertTrue({"srt_exceeds_video", "srt_text_mismatch"} <= self.codes(report), report)

    @patch.object(MODULE, "sha256_file", return_value="a" * 64)
    @patch.object(MODULE, "validate_video", return_value=(True, "duration=600.000s"))
    def test_srt_with_too_few_cues_is_blocked(self, _video: object, _hash: object) -> None:
        temp, work = self.make_work()
        self.addCleanup(temp.cleanup)
        # 28 秒一段的粗时间段冒充字幕：每分钟约 2 条
        coarse = "".join(
            f"{k + 1}\n00:0{k // 2}:{(k % 2) * 28:02d},000 --> 00:0{k // 2}:{(k % 2) * 28 + 28:02d},000\n"
            f"{'完整校正版内容。' if k == 0 else '啊'}\n\n"
            for k in range(6)
        )
        folder = self.make_video_item(work, "未参考/抖音", srt=coarse)
        (folder / "转写" / "校正版逐字稿" / "校正版逐字稿.md").write_text(
            "# 校正版逐字稿\n\n完整校正版内容。啊啊啊啊啊\n", encoding="utf-8"
        )
        report = MODULE.build_report(work, str(folder), strict=True, require_srt=True)
        self.assertFalse(report["ok"])
        self.assertIn("srt_cue_count_unreasonable", self.codes(report))


if __name__ == "__main__":
    unittest.main()
