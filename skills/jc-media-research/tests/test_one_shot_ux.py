#!/usr/bin/env python3
"""Offline tests for one-shot execution and task-budget approval."""

from __future__ import annotations

from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SKILL_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = SKILL_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load_module("tikhub_guard_one_shot", "scripts/tikhub_guard.py")
interaction = load_module("interaction_policy", "scripts/interaction_policy.py")


class InteractionPolicyTests(unittest.TestCase):
    def test_clear_task_executes_without_confirmation(self) -> None:
        self.assertEqual(interaction.decide_followup(), {"action": "execute"})

    def test_three_results_are_delivered_without_sample_selection(self) -> None:
        self.assertEqual(
            interaction.decide_followup(result_count=3),
            {"action": "deliver", "result_count": 3},
        )

    def test_zero_results_are_delivered_without_confirmation(self) -> None:
        self.assertEqual(
            interaction.decide_followup(result_count=0),
            {"action": "deliver", "result_count": 0},
        )

    def test_only_three_followup_reasons_exist(self) -> None:
        decisions = {
            interaction.decide_followup(cost_limit_exceeded=True)["reason"],
            interaction.decide_followup(required_input_missing=True)["reason"],
            interaction.decide_followup(execution_failed=True)["reason"],
        }
        self.assertEqual(decisions, interaction.ALLOWED_FOLLOWUP_REASONS)
        self.assertTrue(
            all(
                interaction.decide_followup(**flags)["action"] == "follow_up"
                for flags in (
                    {"cost_limit_exceeded": True},
                    {"required_input_missing": True},
                    {"execution_failed": True},
                )
            )
        )


class TaskBudgetTests(unittest.TestCase):
    def make_plan(
        self,
        name: str,
        costs: tuple[str, ...],
        *,
        max_requests: int = 200,
        max_cost: str = "2",
    ) -> dict:
        spec = {
            "api_base": "https://api.tikhub.io",
            "pricing": {
                "source": "synthetic-offline-price",
                "checked_at": "2026-01-15T10:00:00Z",
            },
            "requests": [
                {
                    "name": f"{name}-{index}",
                    "method": "GET",
                    "path": "/api/v1/synthetic/check",
                    "params": {"keyword": f"private-task-term-{name}-{index}"},
                    "json_body": None,
                    "estimated_cost_usd": cost,
                }
                for index, cost in enumerate(costs, start=1)
            ],
        }
        return guard.create_plan(
            spec,
            max_requests,
            Decimal(max_cost),
            created_at=f"2026-01-15T10:00:{len(costs):02d}Z",
        )

    def test_same_ledger_accumulates_at_most_120_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "task-budget.jsonl"
            for index in range(120):
                plan = self.make_plan(f"plan-{index}", ("0.001",))
                approval, budget, reserved = guard.create_auto_approval(plan, ledger)
                self.assertTrue(reserved)
                self.assertEqual(approval["kind"], "tikhub-task-auto-approval")
                self.assertEqual(
                    guard.validate_approval(plan, approval)["plan_hash"],
                    plan["plan_hash"],
                )
            self.assertEqual(budget["request_count"], 120)
            with self.assertRaisesRegex(guard.GuardError, "request limit exceeded"):
                guard.create_auto_approval(self.make_plan("fourth", ("0.01",)), ledger)

    def test_same_ledger_accumulates_at_most_one_dollar(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "task-budget.jsonl"
            first = self.make_plan("first", ("0.50", "0.50"))
            guard.create_auto_approval(first, ledger)
            with self.assertRaisesRegex(guard.GuardError, "cost limit exceeded"):
                guard.create_auto_approval(self.make_plan("second", ("0.02",)), ledger)

    def test_auto_approval_is_bound_to_the_exact_plan_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "task-budget.jsonl"
            first = self.make_plan("first", ("0.01",))
            second = self.make_plan("second", ("0.01",))
            approval, _, _ = guard.create_auto_approval(first, ledger)
            with self.assertRaises(guard.GuardError):
                guard.validate_approval(second, approval)

    def test_auto_approval_requires_its_real_budget_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = root / "task-budget.jsonl"
            plan = self.make_plan("proof", ("0.01",))
            approval, _, _ = guard.create_auto_approval(plan, ledger)
            budget = guard.validate_auto_approval_reservation(plan, approval, ledger)
            self.assertEqual(budget["request_count"], 1)

            forged = dict(approval)
            forged["budget_reservation_hash"] = "0" * 64
            material = dict(forged)
            material.pop("approval_hash")
            forged["approval_hash"] = guard.sha256_bytes(guard.canonical_json(material))
            guard.validate_approval(plan, forged)
            with self.assertRaisesRegex(guard.GuardError, "does not match"):
                guard.validate_auto_approval_reservation(plan, forged, ledger)

            with self.assertRaisesRegex(guard.GuardError, "no unique"):
                guard.validate_auto_approval_reservation(
                    plan, approval, root / "missing-budget.jsonl"
                )

    def test_unknown_charge_never_releases_reserved_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "task-budget.jsonl"
            request_ledger = Path(temp_dir) / "request-ledger.jsonl"
            plan = self.make_plan("unknown", ("1.00",))
            guard.create_auto_approval(plan, ledger)
            item = plan["requests"][0]
            guard.append_ledger(
                request_ledger,
                guard.safe_event(plan, item, "timeout_unknown_charge"),
            )
            states = guard.latest_request_states(
                guard.read_ledger(request_ledger, plan["plan_hash"])
            )
            self.assertEqual(states[item["fingerprint"]], "timeout_unknown_charge")
            # The request ledger records the uncertainty, while the separate
            # task reservation remains fully consumed.
            with self.assertRaisesRegex(guard.GuardError, "cost limit exceeded"):
                guard.create_auto_approval(self.make_plan("later", ("0.01",)), ledger)
            summary = guard.summarize_task_budget(guard.read_task_budget_ledger(ledger))
            self.assertEqual(Decimal(summary["estimated_cost_usd"]), Decimal("1.00"))

    def test_explicit_approval_remains_available_above_default_limit(self) -> None:
        plan = self.make_plan("explicit", ("0.001",) * 121)
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(guard.GuardError, "request limit exceeded"):
                guard.create_auto_approval(plan, Path(temp_dir) / "task-budget.jsonl")
        explicit = guard.create_approval(plan, f"APPROVE {plan['plan_hash']}")
        self.assertEqual(explicit["kind"], "tikhub-plan-approval")
        self.assertEqual(
            guard.validate_approval(plan, explicit)["plan_hash"], plan["plan_hash"]
        )

    def test_auto_approval_is_offline_and_budget_ledger_is_content_free(self) -> None:
        plan = self.make_plan("private", ("0.01",))
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "task-budget.jsonl"
            with patch.object(
                guard,
                "urlopen",
                side_effect=AssertionError("network called"),
            ) as mocked:
                approval, _, _ = guard.create_auto_approval(plan, ledger)
            mocked.assert_not_called()
            serialized = ledger.read_text(encoding="utf-8")
            serialized_approval = json.dumps(approval, sort_keys=True)
            self.assertNotIn("private-task-term", serialized)
            self.assertNotIn("keyword", serialized)
            self.assertNotIn("response", serialized)
            self.assertNotIn("private-task-term", serialized_approval)
            self.assertNotIn("keyword", serialized_approval)
            self.assertNotIn("credential", serialized_approval)
            self.assertNotIn("response", serialized_approval)
            event = json.loads(serialized)
            self.assertEqual(set(event), guard.TASK_BUDGET_EVENT_KEYS)


if __name__ == "__main__":
    unittest.main()
