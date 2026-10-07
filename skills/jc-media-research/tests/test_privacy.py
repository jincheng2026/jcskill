#!/usr/bin/env python3
"""Offline cost-gate and public-package safety tests."""

from __future__ import annotations

import argparse
from decimal import Decimal
import importlib.util
import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = SKILL_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load_module("tikhub_guard", "scripts/tikhub_guard.py")
packager = load_module("validate_and_package", "scripts/validate_and_package.py")


class CostGateTests(unittest.TestCase):
    def make_spec(self, count: int = 1) -> dict:
        return {
            "api_base": "https://api.tikhub.io",
            "pricing": {
                "source": "official-openapi-synthetic-check",
                "checked_at": "2026-01-15T10:00:00Z",
            },
            "requests": [
                {
                    "name": f"synthetic-{index}",
                    "method": "GET",
                    "path": "/api/v1/synthetic/check",
                    "params": {"item": index},
                    "json_body": None,
                    "estimated_cost_usd": "0.01",
                }
                for index in range(count)
            ],
        }

    def test_default_sample_and_cost_limits_are_enforced(self) -> None:
        plan = guard.create_plan(
            self.make_spec(3), 3, Decimal("0.05"), created_at="2026-01-15T10:00:00Z"
        )
        self.assertEqual(len(plan["requests"]), 3)
        self.assertEqual(plan["total_estimated_cost_usd"], "0.03")
        with self.assertRaises(guard.GuardError):
            guard.create_plan(self.make_spec(4), 3, Decimal("0.05"))
        with self.assertRaises(guard.GuardError):
            guard.create_plan(self.make_spec(3), 3, Decimal("0.02"))

    def test_plan_hash_and_approval_are_exact(self) -> None:
        plan = guard.create_plan(self.make_spec(), 3, Decimal("0.05"))
        guard.validate_plan(plan)
        with self.assertRaises(guard.GuardError):
            guard.create_approval(plan, "APPROVE wrong-plan")
        approval = guard.create_approval(plan, f"APPROVE {plan['plan_hash']}")
        self.assertEqual(guard.validate_approval(plan, approval)["plan_hash"], plan["plan_hash"])

    def test_unapproved_dry_run_makes_no_network_request(self) -> None:
        plan = guard.create_plan(self.make_spec(), 3, Decimal("0.05"))
        with tempfile.TemporaryDirectory() as temp_dir:
            plan_path = Path(temp_dir) / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            result = guard.run_command(
                argparse.Namespace(
                    plan=plan_path,
                    dry_run=True,
                    approval=None,
                    ledger=None,
                    cache_dir=None,
                    credential_env=None,
                    timeout=1.0,
                    max_response_bytes=1024,
                )
            )
        self.assertEqual(result["network_requests_made"], 0)

    def test_task_budget_ledger_contains_only_safe_reservation_metadata(self) -> None:
        spec = self.make_spec()
        spec["requests"][0]["params"] = {
            "keyword": "synthetic-private-task-phrase"
        }
        plan = guard.create_plan(spec, 3, Decimal("0.05"))
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "task-budget.jsonl"
            approval, budget, reserved = guard.create_auto_approval(plan, ledger)
            serialized = ledger.read_text(encoding="utf-8")
            serialized_approval = json.dumps(approval, sort_keys=True)
        self.assertTrue(reserved)
        self.assertEqual(budget["request_count"], 1)
        self.assertEqual(approval["kind"], "tikhub-task-auto-approval")
        self.assertEqual(
            guard.validate_approval(plan, approval)["plan_hash"], plan["plan_hash"]
        )
        self.assertNotIn("synthetic-private-task-phrase", serialized)
        self.assertNotIn("keyword", serialized)
        self.assertNotIn("credential", serialized)
        self.assertNotIn("response", serialized)
        self.assertNotIn("synthetic-private-task-phrase", serialized_approval)
        self.assertNotIn("keyword", serialized_approval)
        self.assertNotIn("credential", serialized_approval)
        self.assertNotIn("response", serialized_approval)
        event = json.loads(serialized)
        self.assertEqual(set(event), guard.TASK_BUDGET_EVENT_KEYS)

    def test_host_and_sensitive_inputs_are_blocked(self) -> None:
        with self.assertRaises(guard.GuardError):
            guard.validate_api_base("https://example.invalid")
        private_key = "authentication" + "_token"
        self.assertIsNotNone(guard.find_sensitive_input({private_key: "synthetic-value"}))
        signed_url = "https://example.invalid/video?" + "sign=not-a-placeholder-value"
        self.assertIsNotNone(guard.find_sensitive_input({"url": signed_url}))


class PublicPackageTests(unittest.TestCase):
    def test_source_passes_full_public_validation(self) -> None:
        report = packager.validate_source(SKILL_DIR)
        self.assertEqual(report["privacy_findings"], 0)
        self.assertEqual(report["synthetic_fixtures_checked"], 3)
        self.assertGreaterEqual(report["file_count"], 20)

    def test_scanner_detects_secret_path_and_signed_url(self) -> None:
        token_text = "Authorization: " + "Bear" + "er abcdefghijklmnopqrstuvwxyz"
        home_path = "/" + "Users/example/private/file.txt"
        signed_url = "https://example.invalid/video?" + "x-signature=real-test-value"
        findings = packager.scan_text(
            "\n".join((token_text, home_path, signed_url)),
            PurePosixPath("synthetic.txt"),
        )
        codes = {item["code"] for item in findings}
        self.assertIn("bearer-token", codes)
        self.assertIn("mac-home-path", codes)
        self.assertIn("signed-or-tracking-url", codes)

    def test_fixture_marker_and_json_allowlist_are_enforced(self) -> None:
        self.assertFalse(packager.has_synthetic_marker({"records": []}))
        self.assertTrue(packager.has_synthetic_marker({"synthetic": True}))
        forbidden = "authentication" + "_token"
        with self.assertRaises(packager.PackageError):
            packager.validate_json_fields(
                {forbidden: "synthetic-value"}, packager.FIXTURE_FIELD_ALLOWLIST
            )

    def test_zip_is_reproducible_and_non_overwriting(self) -> None:
        report = packager.validate_source(SKILL_DIR)
        with tempfile.TemporaryDirectory() as temp_dir:
            first = packager.build_zip(
                SKILL_DIR, report["files"], Path(temp_dir) / "first.zip", False
            )
            second = packager.build_zip(
                SKILL_DIR, report["files"], Path(temp_dir) / "second.zip", False
            )
            self.assertEqual(first["sha256"], second["sha256"])
            with self.assertRaises(packager.PackageError):
                packager.build_zip(
                    SKILL_DIR, report["files"], Path(temp_dir) / "first.zip", False
                )


if __name__ == "__main__":
    unittest.main()
