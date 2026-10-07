#!/usr/bin/env python3
"""Deterministic one-shot interaction policy for media research tasks.

A clear task runs without a planning pause.  Once execution has produced a
result set, including an empty set, the result is delivered without asking the
user to select or confirm samples.  Follow-up is reserved for the three cases
where execution cannot safely continue.
"""

from __future__ import annotations

from typing import Any


ALLOWED_FOLLOWUP_REASONS = frozenset(
    {
        "cost_limit_exceeded",
        "required_input_missing",
        "execution_failed",
    }
)


def decide_followup(
    *,
    result_count: int | None = None,
    cost_limit_exceeded: bool = False,
    required_input_missing: bool = False,
    execution_failed: bool = False,
) -> dict[str, Any]:
    """Return ``execute``, ``deliver``, or one tightly bounded follow-up.

    ``result_count=None`` means execution has not produced a result set yet.
    ``result_count=0`` is a completed, deliverable result, not missing input.
    """

    if result_count is not None and (
        not isinstance(result_count, int)
        or isinstance(result_count, bool)
        or result_count < 0
    ):
        raise ValueError("result_count must be a non-negative integer or None")

    reason = None
    if cost_limit_exceeded:
        reason = "cost_limit_exceeded"
    elif required_input_missing:
        reason = "required_input_missing"
    elif execution_failed:
        reason = "execution_failed"

    if reason is not None:
        if reason not in ALLOWED_FOLLOWUP_REASONS:
            raise AssertionError("interaction policy emitted an unsupported follow-up")
        return {"action": "follow_up", "reason": reason}
    if result_count is not None:
        return {"action": "deliver", "result_count": result_count}
    return {"action": "execute"}

