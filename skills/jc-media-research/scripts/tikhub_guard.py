#!/usr/bin/env python3
"""Guarded TikHub request planner and executor.

The script deliberately separates six actions:

1. ``plan`` creates an immutable, cost-bounded request plan.
2. ``auto-approve`` reserves a small task budget for that exact plan hash.
3. ``approve`` records an explicit confirmation for that exact plan hash.
4. ``run --dry-run`` validates the plan without credentials or network access.
5. ``run`` executes each request at most once, storing the response locally.
6. ``resolve`` is required before retrying a request whose charge is unknown.

No command prints credentials or response bodies.  The executor has no automatic
retry loop.  Raw responses live only in the caller-provided cache directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


SCHEMA_VERSION = "1"
ALLOWED_HOSTS = frozenset({"api.tikhub.io", "api.tikhub.dev"})
FIXED_CREDENTIAL_ENVS = (
    "TIKHUB_API_KEY",
    "TIKHUB_TOKEN",
    "TIKHUB_BEARER_TOKEN",
)
MACOS_KEYCHAIN_SERVICE = "tikhub-api"
MACOS_KEYCHAIN_ACCOUNT = "tikhub"
DEFAULT_MAX_REQUESTS = 120
DEFAULT_MAX_COST_USD = Decimal("1.00")
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RESPONSE_BYTES = 200 * 1024 * 1024
TASK_BUDGET_EVENT_KEYS = frozenset(
    {
        "kind",
        "schema_version",
        "created_at",
        "plan_hash",
        "request_count",
        "estimated_cost_usd",
        "status",
        "event_hash",
    }
)
EXPLICIT_APPROVAL_KEYS = frozenset(
    {
        "kind",
        "schema_version",
        "created_at",
        "plan_hash",
        "approved_request_count",
        "approved_cost_usd",
        "confirmation_digest",
        "approval_hash",
    }
)
AUTO_APPROVAL_KEYS = frozenset(
    {
        "kind",
        "schema_version",
        "created_at",
        "plan_hash",
        "approved_request_count",
        "approved_cost_usd",
        "budget_reservation_hash",
        "approval_hash",
    }
)

SENSITIVE_KEY_PARTS = frozenset(
    {
        "accesstoken",
        "apikey",
        "authenticationtoken",
        "authorization",
        "bearertoken",
        "cookie",
        "decodekey",
        "password",
        "refreshtoken",
        "secret",
        "sessionid",
        "signature",
    }
)
SENSITIVE_URL_QUERY_KEYS = frozenset(
    {
        "access_token",
        "auth",
        "authorization",
        "cookie",
        "decode_key",
        "key",
        "secret",
        "session",
        "sign",
        "signature",
        "token",
        "x-signature",
    }
)

PLAN_KEYS = frozenset(
    {
        "kind",
        "schema_version",
        "created_at",
        "api_base",
        "pricing",
        "limits",
        "total_estimated_cost_usd",
        "requests",
        "plan_hash",
    }
)
REQUEST_KEYS = frozenset(
    {
        "name",
        "method",
        "path",
        "params",
        "json_body",
        "estimated_cost_usd",
        "fingerprint",
    }
)


class GuardError(RuntimeError):
    """Expected, safe-to-display guard failure."""


class UnknownChargeError(GuardError):
    """The request may have reached the service; an explicit resolution is needed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def decimal_value(value: Any, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise GuardError(f"{field_name} must be a non-negative decimal")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise GuardError(f"{field_name} must be a non-negative decimal") from None
    if not parsed.is_finite() or parsed < 0:
        raise GuardError(f"{field_name} must be a non-negative decimal")
    return parsed


def decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value.normalize(), "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise GuardError("required JSON file does not exist") from None
    except (OSError, json.JSONDecodeError):
        raise GuardError("required JSON file is unreadable or invalid") from None


def write_bytes_exclusive(path: Path, payload: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        raise GuardError("refusing to overwrite an existing output") from None
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def write_json_exclusive(path: Path, payload: Any) -> None:
    write_bytes_exclusive(path, canonical_json(payload) + b"\n")


def append_ledger(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = canonical_json(event) + b"\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "ab") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def validate_api_base(value: Any) -> str:
    if not isinstance(value, str):
        raise GuardError("api_base must be a string")
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise GuardError("api_base must be exactly an approved TikHub HTTPS host")
    return f"https://{parsed.hostname}"


def validate_path(value: Any) -> str:
    if not isinstance(value, str):
        raise GuardError("request path must be a string")
    parsed = urlsplit(value)
    if (
        not value.startswith("/api/")
        or value.startswith("//")
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or any(part == ".." for part in parsed.path.split("/"))
    ):
        raise GuardError("request path must be an absolute /api/ path without a host or query")
    return parsed.path


def ensure_json_value(value: Any, field_name: str) -> Any:
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        raise GuardError(f"{field_name} must contain finite JSON values") from None
    return value


def find_sensitive_input(value: Any, path: str = "$") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            normalized = normalize_key(key_text)
            if normalized in SENSITIVE_KEY_PARTS or any(
                part in normalized for part in SENSITIVE_KEY_PARTS
            ):
                return f"{path}.{key_text}"
            found = find_sensitive_input(child, f"{path}.{key_text}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = find_sensitive_input(child, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(value, str):
        parsed = urlsplit(value)
        if parsed.query:
            for pair in parsed.query.split("&"):
                key = pair.split("=", 1)[0].lower()
                if key in SENSITIVE_URL_QUERY_KEYS:
                    return path
        if re.search(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}", value):
            return path
        if re.search(r"\b(?:sk-|gh[pousr]_)[A-Za-z0-9_-]{16,}\b", value):
            return path
    return None


def request_fingerprint(
    api_base: str,
    method: str,
    path: str,
    params: dict[str, Any],
    json_body: Any,
) -> str:
    material = {
        "api_base": api_base,
        "method": method,
        "path": path,
        "params": params,
        "json_body": json_body,
    }
    return sha256_bytes(canonical_json(material))


def normalize_request(raw: Any, api_base: str, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise GuardError("every request must be an object")
    allowed_input = REQUEST_KEYS - {"fingerprint"}
    unknown = set(raw) - allowed_input
    if unknown:
        raise GuardError("request contains unsupported fields")

    name = raw.get("name", f"request-{index:03d}")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", name):
        raise GuardError("request name must use 1-80 safe filename characters")
    method = str(raw.get("method", "GET")).upper()
    if method not in {"GET", "POST"}:
        raise GuardError("only GET and POST requests are supported")
    path = validate_path(raw.get("path"))
    params = raw.get("params", {})
    if not isinstance(params, dict):
        raise GuardError("request params must be an object")
    params = ensure_json_value(params, "request params")
    json_body = raw.get("json_body")
    json_body = ensure_json_value(json_body, "request json_body")
    if method == "GET" and json_body is not None:
        raise GuardError("GET requests cannot contain json_body")
    sensitive_path = find_sensitive_input({"params": params, "json_body": json_body})
    if sensitive_path:
        raise GuardError("request plan contains a credential or signed URL")

    cost = decimal_value(raw.get("estimated_cost_usd"), "estimated_cost_usd")
    fingerprint = request_fingerprint(api_base, method, path, params, json_body)
    return {
        "name": name,
        "method": method,
        "path": path,
        "params": params,
        "json_body": json_body,
        "estimated_cost_usd": decimal_text(cost),
        "fingerprint": fingerprint,
    }


def calculate_plan_hash(plan_without_hash: dict[str, Any]) -> str:
    material = dict(plan_without_hash)
    material.pop("plan_hash", None)
    return sha256_bytes(canonical_json(material))


def create_plan(
    spec: Any,
    max_requests: int,
    max_cost_usd: Decimal,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise GuardError("request specification must be a JSON object")
    allowed_spec = {"api_base", "pricing", "requests"}
    if set(spec) - allowed_spec:
        raise GuardError("request specification contains unsupported fields")
    if max_requests < 1:
        raise GuardError("max_requests must be at least 1")
    if max_cost_usd < 0:
        raise GuardError("max_cost must be non-negative")

    api_base = validate_api_base(spec.get("api_base", "https://api.tikhub.io"))
    pricing = spec.get("pricing")
    if not isinstance(pricing, dict) or set(pricing) != {"source", "checked_at"}:
        raise GuardError("pricing must contain exactly source and checked_at")
    if not all(isinstance(pricing[key], str) and pricing[key].strip() for key in pricing):
        raise GuardError("pricing source and checked_at must be non-empty strings")

    raw_requests = spec.get("requests")
    if not isinstance(raw_requests, list) or not raw_requests:
        raise GuardError("request specification must contain at least one request")
    if len(raw_requests) > max_requests:
        raise GuardError("request count exceeds max_requests")

    requests = [
        normalize_request(raw, api_base, index)
        for index, raw in enumerate(raw_requests, start=1)
    ]
    fingerprints = [item["fingerprint"] for item in requests]
    if len(set(fingerprints)) != len(fingerprints):
        raise GuardError("request plan contains duplicate request fingerprints")
    total_cost = sum(
        (decimal_value(item["estimated_cost_usd"], "estimated_cost_usd") for item in requests),
        Decimal("0"),
    )
    if total_cost > max_cost_usd:
        raise GuardError("estimated request cost exceeds max_cost")

    plan: dict[str, Any] = {
        "kind": "tikhub-request-plan",
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at or utc_now(),
        "api_base": api_base,
        "pricing": {"source": pricing["source"], "checked_at": pricing["checked_at"]},
        "limits": {
            "max_requests": max_requests,
            "max_cost_usd": decimal_text(max_cost_usd),
        },
        "total_estimated_cost_usd": decimal_text(total_cost),
        "requests": requests,
    }
    plan["plan_hash"] = calculate_plan_hash(plan)
    return plan


def validate_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or set(plan) != PLAN_KEYS:
        raise GuardError("plan has an invalid top-level schema")
    if plan.get("kind") != "tikhub-request-plan" or plan.get("schema_version") != SCHEMA_VERSION:
        raise GuardError("plan kind or schema version is unsupported")
    api_base = validate_api_base(plan.get("api_base"))
    if not isinstance(plan.get("created_at"), str) or not plan["created_at"]:
        raise GuardError("plan created_at is missing")
    pricing = plan.get("pricing")
    if not isinstance(pricing, dict) or set(pricing) != {"source", "checked_at"}:
        raise GuardError("plan pricing metadata is invalid")
    limits = plan.get("limits")
    if not isinstance(limits, dict) or set(limits) != {"max_requests", "max_cost_usd"}:
        raise GuardError("plan limits are invalid")
    max_requests = limits.get("max_requests")
    if not isinstance(max_requests, int) or isinstance(max_requests, bool) or max_requests < 1:
        raise GuardError("plan max_requests is invalid")
    max_cost = decimal_value(limits.get("max_cost_usd"), "plan max_cost_usd")
    raw_requests = plan.get("requests")
    if not isinstance(raw_requests, list) or not raw_requests or len(raw_requests) > max_requests:
        raise GuardError("plan request count is invalid")

    total = Decimal("0")
    seen: set[str] = set()
    for index, request_item in enumerate(raw_requests, start=1):
        if not isinstance(request_item, dict) or set(request_item) != REQUEST_KEYS:
            raise GuardError("plan request schema is invalid")
        normalized = normalize_request(
            {key: request_item[key] for key in REQUEST_KEYS if key != "fingerprint"},
            api_base,
            index,
        )
        if request_item != normalized:
            raise GuardError("plan request content or fingerprint was modified")
        if normalized["fingerprint"] in seen:
            raise GuardError("plan contains duplicate request fingerprints")
        seen.add(normalized["fingerprint"])
        total += decimal_value(normalized["estimated_cost_usd"], "estimated_cost_usd")
    if total > max_cost or decimal_text(total) != plan.get("total_estimated_cost_usd"):
        raise GuardError("plan total cost is inconsistent with its requests")
    expected_hash = calculate_plan_hash(plan)
    if not isinstance(plan.get("plan_hash"), str) or plan["plan_hash"] != expected_hash:
        raise GuardError("plan hash verification failed")
    return plan


def create_approval(plan: dict[str, Any], confirmation: str) -> dict[str, Any]:
    expected = f"APPROVE {plan['plan_hash']}"
    if confirmation.strip() != expected:
        raise GuardError("approval text does not match this exact plan hash")
    approval: dict[str, Any] = {
        "kind": "tikhub-plan-approval",
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "plan_hash": plan["plan_hash"],
        "approved_request_count": len(plan["requests"]),
        "approved_cost_usd": plan["total_estimated_cost_usd"],
        "confirmation_digest": sha256_bytes(expected.encode("utf-8")),
    }
    approval["approval_hash"] = sha256_bytes(canonical_json(approval))
    return approval


def validate_task_budget_event(event: Any) -> dict[str, Any]:
    """Validate a content-free task-budget reservation event."""

    if not isinstance(event, dict) or set(event) != TASK_BUDGET_EVENT_KEYS:
        raise GuardError("task budget ledger contains an invalid event schema")
    material = dict(event)
    actual_hash = material.pop("event_hash")
    if not isinstance(actual_hash, str) or actual_hash != sha256_bytes(
        canonical_json(material)
    ):
        raise GuardError("task budget ledger event hash verification failed")
    if (
        event.get("kind") != "tikhub-task-budget-reservation"
        or event.get("schema_version") != SCHEMA_VERSION
        or event.get("status") != "reserved"
    ):
        raise GuardError("task budget ledger event is unsupported")
    if not isinstance(event.get("created_at"), str) or not event["created_at"]:
        raise GuardError("task budget ledger event is missing created_at")
    if not isinstance(event.get("plan_hash"), str) or not re.fullmatch(
        r"[0-9a-f]{64}", event["plan_hash"]
    ):
        raise GuardError("task budget ledger event has an invalid plan hash")
    request_count = event.get("request_count")
    if (
        not isinstance(request_count, int)
        or isinstance(request_count, bool)
        or request_count < 1
    ):
        raise GuardError("task budget ledger event has an invalid request count")
    decimal_value(event.get("estimated_cost_usd"), "estimated_cost_usd")
    return event


def read_task_budget_ledger(path: Path) -> list[dict[str, Any]]:
    """Read all task reservations without exposing plan content."""

    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = validate_task_budget_event(json.loads(line))
                if event["plan_hash"] in seen:
                    raise GuardError("task budget ledger contains a duplicate plan reservation")
                seen.add(event["plan_hash"])
                events.append(event)
    except GuardError:
        raise
    except (OSError, json.JSONDecodeError, ValueError):
        raise GuardError(
            "task budget ledger is unreadable or contains invalid JSONL"
        ) from None
    return events


def summarize_task_budget(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    request_count = 0
    estimated_cost = Decimal("0")
    plan_count = 0
    for raw_event in events:
        event = validate_task_budget_event(raw_event)
        plan_count += 1
        request_count += event["request_count"]
        estimated_cost += decimal_value(
            event["estimated_cost_usd"], "estimated_cost_usd"
        )
    return {
        "plan_count": plan_count,
        "request_count": request_count,
        "estimated_cost_usd": decimal_text(estimated_cost),
    }


def create_task_budget_event(plan: dict[str, Any]) -> dict[str, Any]:
    """Create a reservation containing no query, credential, or response data."""

    event: dict[str, Any] = {
        "kind": "tikhub-task-budget-reservation",
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "plan_hash": plan["plan_hash"],
        "request_count": len(plan["requests"]),
        "estimated_cost_usd": plan["total_estimated_cost_usd"],
        "status": "reserved",
    }
    event["event_hash"] = sha256_bytes(canonical_json(event))
    return event


def create_task_auto_approval(
    plan: dict[str, Any], budget_event: dict[str, Any]
) -> dict[str, Any]:
    event = validate_task_budget_event(budget_event)
    if (
        event["plan_hash"] != plan["plan_hash"]
        or event["request_count"] != len(plan["requests"])
        or event["estimated_cost_usd"] != plan["total_estimated_cost_usd"]
    ):
        raise GuardError("task budget reservation does not match this exact plan")
    approval: dict[str, Any] = {
        "kind": "tikhub-task-auto-approval",
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "plan_hash": plan["plan_hash"],
        "approved_request_count": len(plan["requests"]),
        "approved_cost_usd": plan["total_estimated_cost_usd"],
        "budget_reservation_hash": event["event_hash"],
    }
    approval["approval_hash"] = sha256_bytes(canonical_json(approval))
    return approval


def create_auto_approval(
    plan: dict[str, Any],
    budget_ledger: Path,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Reserve the default task budget and approve one exact plan.

    Reservations are deliberately never released here.  A success, failure, or
    unknown-charge outcome therefore still consumes the task's bounded budget.
    Plans above the default task limit must use the explicit ``approve`` mode.
    """

    plan = validate_plan(plan)
    events = read_task_budget_ledger(budget_ledger)
    for event in events:
        if event["plan_hash"] == plan["plan_hash"]:
            if (
                event["request_count"] != len(plan["requests"])
                or event["estimated_cost_usd"] != plan["total_estimated_cost_usd"]
            ):
                raise GuardError("task budget reservation does not match this exact plan")
            approval = create_task_auto_approval(plan, event)
            return approval, summarize_task_budget(events), False

    current = summarize_task_budget(events)
    next_requests = current["request_count"] + len(plan["requests"])
    next_cost = decimal_value(
        current["estimated_cost_usd"], "estimated_cost_usd"
    ) + decimal_value(plan["total_estimated_cost_usd"], "estimated_cost_usd")
    if next_requests > DEFAULT_MAX_REQUESTS:
        raise GuardError(
            "task auto-approval request limit exceeded; use explicit APPROVE for a larger plan"
        )
    if next_cost > DEFAULT_MAX_COST_USD:
        raise GuardError(
            "task auto-approval cost limit exceeded; use explicit APPROVE for a larger plan"
        )

    event = create_task_budget_event(plan)
    append_ledger(budget_ledger, event)
    updated = summarize_task_budget([*events, event])
    approval = create_task_auto_approval(plan, event)
    return approval, updated, True


def validate_approval(plan: dict[str, Any], approval: Any) -> dict[str, Any]:
    if not isinstance(approval, dict):
        raise GuardError("approval has an invalid schema")
    kind = approval.get("kind")
    required = (
        EXPLICIT_APPROVAL_KEYS
        if kind == "tikhub-plan-approval"
        else AUTO_APPROVAL_KEYS
        if kind == "tikhub-task-auto-approval"
        else frozenset()
    )
    if not required or set(approval) != required:
        raise GuardError("approval has an invalid schema")
    material = dict(approval)
    actual_hash = material.pop("approval_hash")
    if actual_hash != sha256_bytes(canonical_json(material)):
        raise GuardError("approval hash verification failed")
    common_checks = (
        approval.get("schema_version") == SCHEMA_VERSION,
        approval.get("plan_hash") == plan["plan_hash"],
        approval.get("approved_request_count") == len(plan["requests"]),
        approval.get("approved_cost_usd") == plan["total_estimated_cost_usd"],
    )
    mode_checks: tuple[bool, ...]
    if kind == "tikhub-plan-approval":
        expected_confirmation = f"APPROVE {plan['plan_hash']}"
        mode_checks = (
            approval.get("confirmation_digest")
            == sha256_bytes(expected_confirmation.encode("utf-8")),
        )
    else:
        mode_checks = (
            isinstance(approval.get("budget_reservation_hash"), str),
            bool(re.fullmatch(r"[0-9a-f]{64}", approval["budget_reservation_hash"])),
        )
    if not all((*common_checks, *mode_checks)):
        raise GuardError("approval does not authorize this exact plan")
    return approval


def validate_auto_approval_reservation(
    plan: dict[str, Any], approval: dict[str, Any], budget_ledger: Path
) -> dict[str, Any]:
    """Prove that an auto approval came from this task's bounded ledger."""

    if approval.get("kind") != "tikhub-task-auto-approval":
        raise GuardError("task budget proof is only valid for an auto approval")
    events = read_task_budget_ledger(budget_ledger)
    budget = summarize_task_budget(events)
    if budget["request_count"] > DEFAULT_MAX_REQUESTS or decimal_value(
        budget["estimated_cost_usd"], "estimated_cost_usd"
    ) > DEFAULT_MAX_COST_USD:
        raise GuardError("task budget ledger exceeds the automatic approval limit")
    matching = [event for event in events if event["plan_hash"] == plan["plan_hash"]]
    if len(matching) != 1:
        raise GuardError("auto approval has no unique task budget reservation")
    event = matching[0]
    if (
        event["event_hash"] != approval.get("budget_reservation_hash")
        or event["request_count"] != len(plan["requests"])
        or event["estimated_cost_usd"] != plan["total_estimated_cost_usd"]
    ):
        raise GuardError("auto approval does not match the task budget reservation")
    return budget


def read_ledger(path: Path, plan_hash: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError
                if event.get("plan_hash") == plan_hash:
                    events.append(event)
    except (OSError, json.JSONDecodeError, ValueError):
        raise GuardError("ledger is unreadable or contains invalid JSONL") from None
    return events


def latest_request_states(events: Iterable[dict[str, Any]]) -> dict[str, str]:
    states: dict[str, str] = {}
    for event in events:
        fingerprint = event.get("request_fingerprint")
        status = event.get("status")
        if isinstance(fingerprint, str) and isinstance(status, str):
            states[fingerprint] = status
    return states


def safe_event(plan: dict[str, Any], item: dict[str, Any], status: str, **extra: Any) -> dict[str, Any]:
    event = {
        "at": utc_now(),
        "plan_hash": plan["plan_hash"],
        "request_name": item["name"],
        "request_fingerprint": item["fingerprint"],
        "estimated_cost_usd": item["estimated_cost_usd"],
        "status": status,
    }
    event.update(extra)
    return event


def cache_paths(cache_dir: Path, fingerprint: str) -> tuple[Path, Path]:
    return (
        cache_dir / f"{fingerprint}.response",
        cache_dir / f"{fingerprint}.meta.json",
    )


def validate_cache(cache_dir: Path, item: dict[str, Any]) -> bool:
    response_path, meta_path = cache_paths(cache_dir, item["fingerprint"])
    if not response_path.exists() and not meta_path.exists():
        return False
    if not response_path.is_file() or not meta_path.is_file():
        raise GuardError("cache is incomplete; refusing to overwrite or rerun")
    meta = read_json(meta_path)
    if not isinstance(meta, dict):
        raise GuardError("cache metadata is invalid")
    try:
        digest = hashlib.sha256(response_path.read_bytes()).hexdigest()
    except OSError:
        raise GuardError("cached response is unreadable") from None
    if (
        meta.get("request_fingerprint") != item["fingerprint"]
        or meta.get("sha256") != digest
        or meta.get("size_bytes") != response_path.stat().st_size
    ):
        raise GuardError("cached response integrity check failed")
    return True


def normalize_credential(value: str) -> str:
    value = value.strip()
    if "\n" in value or "\r" in value:
        raise GuardError("credential contains invalid control characters")
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    if not value:
        raise GuardError("credential is empty")
    return value


def read_macos_keychain() -> str:
    if platform.system() != "Darwin" or os.environ.get("TIKHUB_DISABLE_KEYCHAIN") == "1":
        return ""
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                MACOS_KEYCHAIN_SERVICE,
                "-a",
                MACOS_KEYCHAIN_ACCOUNT,
                "-w",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return normalize_credential(result.stdout)


def choose_credential(explicit_name: str | None) -> tuple[str, str]:
    candidates = (explicit_name,) if explicit_name else FIXED_CREDENTIAL_ENVS
    for name in candidates:
        if name not in FIXED_CREDENTIAL_ENVS:
            raise GuardError("credential environment name is not allowed")
        value = os.environ.get(name, "").strip()
        if value:
            return f"environment:{name}", normalize_credential(value)
    if explicit_name is None:
        value = read_macos_keychain()
        if value:
            return "macos_keychain", value
    raise GuardError("no supported TikHub credential is available")


def encode_query(params: dict[str, Any]) -> str:
    flattened: list[tuple[str, Any]] = []
    for key in sorted(params):
        value = params[key]
        values = value if isinstance(value, list) else [value]
        for child in values:
            if child is None:
                flattened.append((key, ""))
            elif isinstance(child, bool):
                flattened.append((key, "true" if child else "false"))
            elif isinstance(child, (str, int, float)):
                flattened.append((key, child))
            else:
                raise GuardError("request params may only contain scalar values or lists")
    return urlencode(flattened, doseq=True)


def execute_once(
    plan: dict[str, Any],
    item: dict[str, Any],
    token: str,
    cache_dir: Path,
    timeout_seconds: float,
    max_response_bytes: int,
) -> dict[str, Any]:
    response_path, meta_path = cache_paths(cache_dir, item["fingerprint"])
    if response_path.exists() or meta_path.exists():
        raise GuardError("refusing to overwrite an existing cache output")
    query = encode_query(item["params"])
    url = f"{plan['api_base']}{item['path']}"
    if query:
        url = f"{url}?{query}"
    body = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "jc-media-research/1",
    }
    if item["method"] == "POST":
        body = canonical_json(item["json_body"])
        headers["Content-Type"] = "application/json"
    request = Request(url=url, data=body, headers=headers, method=item["method"])

    cache_dir.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{item['fingerprint']}.", dir=cache_dir, delete=False
        ) as temp_handle:
            temp_path = Path(temp_handle.name)
            digest = hashlib.sha256()
            size = 0
            with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310
                status = int(getattr(response, "status", 200))
                content_type = response.headers.get("Content-Type", "")
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_response_bytes:
                        raise UnknownChargeError("response exceeded the local byte limit")
                    digest.update(chunk)
                    temp_handle.write(chunk)
            temp_handle.flush()
            os.fsync(temp_handle.fileno())
        try:
            os.link(temp_path, response_path)
        except FileExistsError:
            raise GuardError("refusing to overwrite an existing cache output") from None
        finally:
            try:
                temp_path.unlink()
            except OSError:
                pass
            temp_path = None
        meta = {
            "request_fingerprint": item["fingerprint"],
            "received_at": utc_now(),
            "http_status": status,
            "content_type": content_type,
            "size_bytes": size,
            "sha256": digest.hexdigest(),
            "response_file": response_path.name,
        }
        try:
            write_json_exclusive(meta_path, meta)
        except Exception:
            try:
                response_path.unlink()
            except OSError:
                pass
            raise
        return meta
    except HTTPError:
        raise UnknownChargeError("service returned an HTTP error; charge status is unknown") from None
    except (TimeoutError, socket.timeout):
        raise UnknownChargeError("request timed out; charge status is unknown") from None
    except URLError:
        raise UnknownChargeError("transport failed; charge status is unknown") from None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def plan_command(args: argparse.Namespace) -> dict[str, Any]:
    spec = read_json(args.spec)
    plan = create_plan(
        spec,
        args.max_requests,
        decimal_value(args.max_cost, "max_cost"),
    )
    write_json_exclusive(args.out, plan)
    return {
        "ok": True,
        "action": "plan_created",
        "plan_hash": plan["plan_hash"],
        "request_count": len(plan["requests"]),
        "estimated_cost_usd": plan["total_estimated_cost_usd"],
    }


def approve_command(args: argparse.Namespace) -> dict[str, Any]:
    plan = validate_plan(read_json(args.plan))
    approval = create_approval(plan, args.confirmation)
    write_json_exclusive(args.out, approval)
    return {
        "ok": True,
        "action": "approval_created",
        "plan_hash": plan["plan_hash"],
        "request_count": len(plan["requests"]),
        "approved_cost_usd": plan["total_estimated_cost_usd"],
    }


def auto_approve_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.out.exists():
        raise GuardError("refusing to overwrite an existing output")
    if args.plan.resolve() in {args.budget_ledger.resolve(), args.out.resolve()}:
        raise GuardError("plan, budget ledger, and approval output must be separate files")
    if args.budget_ledger.resolve() == args.out.resolve():
        raise GuardError("plan, budget ledger, and approval output must be separate files")
    plan = validate_plan(read_json(args.plan))
    approval, budget, reserved = create_auto_approval(plan, args.budget_ledger)
    write_json_exclusive(args.out, approval)
    return {
        "ok": True,
        "action": "auto_approval_created",
        "plan_hash": plan["plan_hash"],
        "request_count": len(plan["requests"]),
        "approved_cost_usd": plan["total_estimated_cost_usd"],
        "new_budget_reservation": reserved,
        "task_budget": budget,
        "network_requests_made": 0,
    }


def run_command(args: argparse.Namespace) -> dict[str, Any]:
    plan = validate_plan(read_json(args.plan))
    if args.dry_run:
        return {
            "ok": True,
            "action": "dry_run",
            "plan_hash": plan["plan_hash"],
            "request_count": len(plan["requests"]),
            "estimated_cost_usd": plan["total_estimated_cost_usd"],
            "network_requests_made": 0,
        }
    if args.approval is None:
        raise GuardError("an approval file is required for network execution")
    if args.ledger is None or args.cache_dir is None:
        raise GuardError("ledger and cache_dir are required for network execution")
    approval = validate_approval(plan, read_json(args.approval))
    if approval["kind"] == "tikhub-task-auto-approval":
        budget_ledger = getattr(args, "budget_ledger", None)
        if budget_ledger is None:
            raise GuardError("task budget ledger is required for auto-approved execution")
        validate_auto_approval_reservation(plan, approval, budget_ledger)
    if args.timeout <= 0 or args.max_response_bytes < 1:
        raise GuardError("timeout and max_response_bytes must be positive")
    _, token = choose_credential(args.credential_env)

    events = read_ledger(args.ledger, plan["plan_hash"])
    states = latest_request_states(events)
    completed = 0
    cache_hits = 0
    executed = 0
    for item in plan["requests"]:
        fingerprint = item["fingerprint"]
        cached = validate_cache(args.cache_dir, item)
        state = states.get(fingerprint)
        if cached:
            cache_hits += 1
            completed += 1
            if state not in {"success", "cache_hit"}:
                append_ledger(args.ledger, safe_event(plan, item, "cache_hit"))
            continue
        if state in {"success", "cache_hit"}:
            raise GuardError("completed request is missing its cache; investigate before rerun")
        if state in {"timeout_unknown_charge", "http_unknown_charge", "transport_unknown_charge"}:
            raise GuardError("request has unresolved charge status; use resolve before rerun")

        append_ledger(args.ledger, safe_event(plan, item, "started"))
        try:
            meta = execute_once(
                plan,
                item,
                token,
                args.cache_dir,
                args.timeout,
                args.max_response_bytes,
            )
        except UnknownChargeError as error:
            message = str(error)
            if message.startswith("request timed out"):
                status = "timeout_unknown_charge"
            elif message.startswith("service returned"):
                status = "http_unknown_charge"
            else:
                status = "transport_unknown_charge"
            append_ledger(args.ledger, safe_event(plan, item, status))
            raise
        append_ledger(
            args.ledger,
            safe_event(
                plan,
                item,
                "success",
                response_file=meta["response_file"],
                response_sha256=meta["sha256"],
                response_size_bytes=meta["size_bytes"],
                http_status=meta["http_status"],
            ),
        )
        completed += 1
        executed += 1
        states[fingerprint] = "success"
    return {
        "ok": True,
        "action": "run_complete",
        "plan_hash": plan["plan_hash"],
        "completed": completed,
        "executed": executed,
        "cache_hits": cache_hits,
        "response_bodies_printed": 0,
    }


def resolve_command(args: argparse.Namespace) -> dict[str, Any]:
    plan = validate_plan(read_json(args.plan))
    requests_by_fingerprint = {item["fingerprint"]: item for item in plan["requests"]}
    item = requests_by_fingerprint.get(args.fingerprint)
    if item is None:
        raise GuardError("fingerprint is not part of this plan")
    states = latest_request_states(read_ledger(args.ledger, plan["plan_hash"]))
    if states.get(args.fingerprint) not in {
        "timeout_unknown_charge",
        "http_unknown_charge",
        "transport_unknown_charge",
    }:
        raise GuardError("request does not have an unresolved charge status")
    if args.confirmation.strip() != f"RESOLVE {args.fingerprint}":
        raise GuardError("resolution text does not match the exact request fingerprint")
    append_ledger(args.ledger, safe_event(plan, item, "unknown_charge_resolved"))
    return {
        "ok": True,
        "action": "unknown_charge_resolved",
        "plan_hash": plan["plan_hash"],
        "request_fingerprint": args.fingerprint,
    }


def status_command(args: argparse.Namespace) -> dict[str, Any]:
    plan = validate_plan(read_json(args.plan))
    states = latest_request_states(read_ledger(args.ledger, plan["plan_hash"]))
    counts: dict[str, int] = {}
    for item in plan["requests"]:
        status = states.get(item["fingerprint"], "pending")
        counts[status] = counts.get(status, 0) + 1
    return {
        "ok": True,
        "action": "status",
        "plan_hash": plan["plan_hash"],
        "request_count": len(plan["requests"]),
        "states": dict(sorted(counts.items())),
    }


def credential_status_command(_: argparse.Namespace) -> dict[str, Any]:
    try:
        source, _ = choose_credential(None)
    except GuardError:
        source = "none"
    return {
        "ok": True,
        "action": "credential_status",
        "configured": source != "none",
        "source": source,
        "credential_value_printed": False,
        "network_requests_made": 0,
    }


def self_test_command(_: argparse.Namespace) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="jc-media-research-guard-") as temp:
        root = Path(temp)
        spec = {
            "api_base": "https://api.tikhub.io",
            "pricing": {
                "source": "synthetic-offline-test",
                "checked_at": "2026-01-01T00:00:00+00:00",
            },
            "requests": [
                {
                    "name": "sample-001",
                    "method": "GET",
                    "path": "/api/v1/example",
                    "params": {"keyword": "synthetic"},
                    "estimated_cost_usd": "0.01",
                }
            ],
        }
        plan = create_plan(spec, 3, Decimal("0.05"), created_at="2026-01-01T00:00:00+00:00")
        validate_plan(plan)
        approval = create_approval(plan, f"APPROVE {plan['plan_hash']}")
        validate_approval(plan, approval)
        budget_ledger = root / "task-budget.jsonl"
        auto_approval, budget, reserved = create_auto_approval(plan, budget_ledger)
        validate_approval(plan, auto_approval)
        if not reserved or budget["request_count"] != 1:
            raise AssertionError("task auto-approval reservation failed")
        _, repeated_budget, repeated_reservation = create_auto_approval(
            plan, budget_ledger
        )
        if repeated_reservation or repeated_budget != budget:
            raise AssertionError("task auto-approval is not idempotent")
        plan_path = root / "plan.json"
        write_json_exclusive(plan_path, plan)
        try:
            write_json_exclusive(plan_path, plan)
            raise AssertionError("overwrite protection did not trigger")
        except GuardError:
            pass
        if find_sensitive_input({"authentication_token": "synthetic"}) is None:
            raise AssertionError("sensitive-key detection did not trigger")
        if validate_api_base("https://api.tikhub.io") != "https://api.tikhub.io":
            raise AssertionError("allowlist validation failed")
        try:
            validate_api_base("https://example.invalid")
            raise AssertionError("host allowlist did not trigger")
        except GuardError:
            pass
        previous_key = os.environ.get("TIKHUB_API_KEY")
        try:
            os.environ["TIKHUB_API_KEY"] = "synthetic-self-test-key"
            source, value = choose_credential(None)
            if source != "environment:TIKHUB_API_KEY" or value != "synthetic-self-test-key":
                raise AssertionError("environment credential resolution failed")
            status = credential_status_command(argparse.Namespace())
            if not status["configured"] or status["credential_value_printed"]:
                raise AssertionError("credential status redaction failed")
        finally:
            if previous_key is None:
                os.environ.pop("TIKHUB_API_KEY", None)
            else:
                os.environ["TIKHUB_API_KEY"] = previous_key
    return {
        "ok": True,
        "action": "self_test",
        "network_requests_made": 0,
        "checks": 10,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan, approve and execute cost-bounded TikHub requests safely."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Create a non-overwriting request plan")
    plan_parser.add_argument("--spec", type=Path, required=True)
    plan_parser.add_argument("--out", type=Path, required=True)
    plan_parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS)
    plan_parser.add_argument("--max-cost", default=decimal_text(DEFAULT_MAX_COST_USD))
    plan_parser.set_defaults(handler=plan_command)

    approve_parser = subparsers.add_parser("approve", help="Approve an exact plan hash")
    approve_parser.add_argument("--plan", type=Path, required=True)
    approve_parser.add_argument("--confirmation", required=True)
    approve_parser.add_argument("--out", type=Path, required=True)
    approve_parser.set_defaults(handler=approve_command)

    auto_approve_parser = subparsers.add_parser(
        "auto-approve",
        help="Reserve the bounded task budget and approve an exact plan hash",
    )
    auto_approve_parser.add_argument("--plan", type=Path, required=True)
    auto_approve_parser.add_argument("--budget-ledger", type=Path, required=True)
    auto_approve_parser.add_argument("--out", type=Path, required=True)
    auto_approve_parser.set_defaults(handler=auto_approve_command)

    run_parser = subparsers.add_parser("run", help="Validate or execute an approved plan")
    run_parser.add_argument("--plan", type=Path, required=True)
    run_parser.add_argument("--approval", type=Path)
    run_parser.add_argument(
        "--budget-ledger",
        type=Path,
        help="Task budget ledger required when the approval was created by auto-approve",
    )
    run_parser.add_argument("--ledger", type=Path)
    run_parser.add_argument("--cache-dir", type=Path)
    run_parser.add_argument("--credential-env", choices=FIXED_CREDENTIAL_ENVS)
    run_parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    run_parser.add_argument("--max-response-bytes", type=int, default=DEFAULT_MAX_RESPONSE_BYTES)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.set_defaults(handler=run_command)

    resolve_parser = subparsers.add_parser(
        "resolve", help="Explicitly resolve an unknown-charge request before retrying"
    )
    resolve_parser.add_argument("--plan", type=Path, required=True)
    resolve_parser.add_argument("--ledger", type=Path, required=True)
    resolve_parser.add_argument("--fingerprint", required=True)
    resolve_parser.add_argument("--confirmation", required=True)
    resolve_parser.set_defaults(handler=resolve_command)

    status_parser = subparsers.add_parser("status", help="Show safe ledger status counts")
    status_parser.add_argument("--plan", type=Path, required=True)
    status_parser.add_argument("--ledger", type=Path, required=True)
    status_parser.set_defaults(handler=status_command)

    credential_status_parser = subparsers.add_parser(
        "credential-status",
        help="Check whether a TikHub credential is available without printing it",
    )
    credential_status_parser.set_defaults(handler=credential_status_command)

    self_test_parser = subparsers.add_parser("self-test", help="Run offline guard checks")
    self_test_parser.set_defaults(handler=self_test_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except (GuardError, OSError) as error:
        print(
            json.dumps(
                {"ok": False, "error": str(error)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
