#!/usr/bin/env python3
"""Validate ``jc-media-research`` and build a privacy-gated public ZIP.

The public archive is always built from the Skill directory that contains this
script.  Task runs, caches and generated reports are excluded.  Every included
text file is scanned before packaging, JSON examples use path-specific field
allowlists, and test fixtures must declare that they are synthetic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlsplit


SKILL_NAME = "jc-media-research"
SOURCE_ROOT = Path(__file__).resolve().parent.parent
MAX_PUBLIC_FILE_BYTES = 5 * 1024 * 1024
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".backup",
        ".cache",
        ".git",
        "vendor",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "cache",
        "downloads",
        "media",
        "normalized",
        "outputs",
        "raw",
        "reports",
        "runs",
        "task-data",
        "tasks",
        "transcripts",
        "work",
    }
)
EXCLUDED_FILE_NAMES = frozenset({".DS_Store"})
EXCLUDED_SUFFIXES = frozenset(
    {".log", ".pyc", ".pyo", ".sqlite", ".sqlite3", ".tmp", ".zip"}
)
PUBLIC_DEPENDENCIES = frozenset({"assets/vendor/echarts.min.js", "assets/vendor/LICENSE.echarts.txt", "assets/vendor/NOTICE.echarts.txt"})
PUBLIC_TEXT_SUFFIXES = frozenset(
    {".csv", ".html", ".json", ".md", ".mjs", ".py", ".svg", ".txt", ".yaml", ".yml"}
)

SENSITIVE_KEY_PARTS = frozenset(
    {
        "accesstoken",
        "apikey",
        "authenticationtoken",
        "authorization",
        "bearertoken",
        "cacheurl",
        "clientsecret",
        "cookie",
        "decodekey",
        "password",
        "privatetoken",
        "refreshtoken",
        "secret",
        "sessionid",
        "sessionkey",
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
        "device_id",
        "key",
        "ms_token",
        "secret",
        "session",
        "sign",
        "signature",
        "token",
        "verifyfp",
        "x-bogus",
        "x-signature",
    }
)

TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "bearer-token",
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}={0,2}\b"),
    ),
    ("openai-style-token", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    (
        "jwt",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
        ),
    ),
    (
        "assigned-secret",
        re.compile(
            r"(?i)(?:api[_-]?key|access[_-]?token|authentication[_-]?token|"
            r"decode[_-]?key|client[_-]?secret|password)\s*[:=]\s*[\"']?"
            r"[A-Za-z0-9._~+/-]{12,}"
        ),
    ),
)

# Build path expressions in pieces so this scanner does not match its own source.
ABSOLUTE_PATH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "mac-home-path",
        re.compile(r"/" + r"Users/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._~+ -]+)+"),
    ),
    (
        "linux-home-path",
        re.compile(r"/" + r"home/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._~+ -]+)+"),
    ),
    (
        "windows-home-path",
        re.compile(r"[A-Za-z]:\\" + r"Users\\[^\\\s]+(?:\\[^\r\n\"']+)+"),
    ),
    ("file-uri", re.compile(r"(?i)file:" + r"//(?:localhost)?/[^\s)>'\"]+")),
)

URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]{}\"']+")
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
RESOURCE_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_./-])((?:references|scripts|assets|evals|tests)/"
    r"[A-Za-z0-9_.\-/]+)"
)


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def normalized_keys(values: Iterable[str]) -> frozenset[str]:
    return frozenset(normalize_key(value) for value in values)


EVAL_FIELD_ALLOWLIST = normalized_keys(
    {
        "skill",
        "skill_name",
        "version",
        "groups",
        "group",
        "name",
        "description",
        "evals",
        "id",
        "prompt",
        "expected",
        "expected_output",
        "max_followups",
        "allowed_followup_reasons",
        "forbidden",
        "expected_status",
        "files",
        "tags",
        "metadata",
        "synthetic",
        "_meta",
    }
)
PROFILE_FIELD_ALLOWLIST = normalized_keys(
    {
        "profile_version",
        "schema_version",
        "synthetic",
        "_meta",
        "display_name",
        "creator",
        "audience",
        "topics",
        "confirmed_positions",
        "statement",
        "content_focus",
        "audiences",
        "platforms",
        "experience_items",
        "experience",
        "public_experiences",
        "summary",
        "evidence",
        "allowed_for_publication",
        "prohibited_claims",
        "opinions",
        "claims",
        "evidence_refs",
        "source_refs",
        "confirmed_by_user",
        "updated_at",
        "status",
        "text",
        "source",
        "date",
        "notes",
    }
)
FIXTURE_FIELD_ALLOWLIST = normalized_keys(
    {
        "schema_version",
        "synthetic",
        "_meta",
        "fixture_meta",
        "description",
        "caption",
        "case",
        "case_id",
        "cases",
        "invalid_records",
        "input",
        "expected",
        "records",
        "items",
        "contents",
        "comments",
        "accounts",
        "platform",
        "content_id",
        "comment_id",
        "comment_text",
        "video_id",
        "aweme_id",
        "account_id",
        "author_id",
        "author_name",
        "title",
        "text",
        "description_text",
        "published_at",
        "commented_at",
        "collected_at",
        "source_url",
        "canonical_url",
        "source_file",
        "keyword",
        "query",
        "sort",
        "time_window",
        "followers",
        "follower_count",
        "likes",
        "like_count",
        "digg_count",
        "favorite_count",
        "collect_count",
        "comment_count",
        "share_count",
        "view_count",
        "duration_seconds",
        "relevance",
        "relevance_label",
        "relevance_reason",
        "eligible",
        "exclusion_reason",
        "exclusion_reasons",
        "sample_class",
        "primary_category",
        "secondary_categories",
        "category_reason",
        "is_noise",
        "noise_reason",
        "denominator",
        "numerator",
        "count",
        "percentage",
        "metrics",
        "filters",
        "columns",
        "value",
        "values",
        "missing",
        "null",
        "empty",
        "duplicate",
        "status",
        "reason",
        "label",
        "labels",
        "tags",
    }
)
EVIDENCE_MANIFEST_FIELDS = normalized_keys(
    {
        "schema_version",
        "items",
        "evidence",
        "evidence_id",
        "source_url",
        "source_file",
        "collected_at",
        "claim_type",
        "content_id",
        "description",
        "synthetic",
        "_meta",
    }
)
CHART_MANIFEST_FIELDS = normalized_keys(
    {
        "schema_version",
        "items",
        "charts",
        "chart_id",
        "chart_type",
        "title",
        "file",
        "data_file",
        "filters",
        "columns",
        "denominator",
        "source",
        "collected_at",
        "evidence_issues",
        "fallback",
        "description",
        "synthetic",
        "_meta",
    }
)


class PackageError(RuntimeError):
    """Expected validation or packaging failure."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        raise PackageError(f"invalid JSON file: {path.name}") from None


def relative_display(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def has_synthetic_marker(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("synthetic") is True:
        return True
    for metadata_key in ("_meta", "fixture_meta"):
        metadata = value.get(metadata_key)
        if isinstance(metadata, dict) and metadata.get("synthetic") is True:
            return True
    return False


def validate_json_fields(value: Any, allowlist: frozenset[str], location: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            normalized = normalize_key(key_text)
            if normalized in SENSITIVE_KEY_PARTS or any(
                part in normalized for part in SENSITIVE_KEY_PARTS
            ):
                raise PackageError(f"sensitive JSON key at {location}.{key_text}")
            if normalized not in allowlist:
                raise PackageError(f"non-whitelisted JSON field at {location}.{key_text}")
            validate_json_fields(child, allowlist, f"{location}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_json_fields(child, allowlist, f"{location}[{index}]")


FIXTURE_FIELD_ALLOWLIST = FIXTURE_FIELD_ALLOWLIST | normalized_keys({
    "id", "sources", "source_id", "paragraphs", "paragraph_id", "time_precision", "analysis", "evolution",
    "operation", "from", "to", "quote", "logic", "expression", "fact_change", "recommendation",
    "draft_sections", "references", "own_facts", "borrowed_logic", "expression_change", "material_gap"
})

def json_allowlist_for(relative_path: PurePosixPath) -> frozenset[str] | None:
    parts = relative_path.parts
    name = relative_path.name.lower()
    if len(parts) >= 2 and parts[0] == "evals":
        return EVAL_FIELD_ALLOWLIST
    if len(parts) >= 2 and parts[0] == "assets":
        return PROFILE_FIELD_ALLOWLIST
    if len(parts) >= 3 and parts[:2] == ("tests", "fixtures"):
        return FIXTURE_FIELD_ALLOWLIST
    if name in {"evidence-manifest.json", "evidence_manifest.json"}:
        return EVIDENCE_MANIFEST_FIELDS
    if name in {"chart-manifest.json", "chart_manifest.json"}:
        return CHART_MANIFEST_FIELDS
    return None


def scan_text(text: str, relative_path: PurePosixPath) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for code, pattern in TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                {
                    "file": relative_path.as_posix(),
                    "line": text.count("\n", 0, match.start()) + 1,
                    "code": code,
                }
            )
    for code, pattern in ABSOLUTE_PATH_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                {
                    "file": relative_path.as_posix(),
                    "line": text.count("\n", 0, match.start()) + 1,
                    "code": code,
                }
            )
    for match in URL_PATTERN.finditer(text.replace("&amp;", "&")):
        url = match.group(0).rstrip(".,;:!?，。；：！？")
        parsed = urlsplit(url)
        sensitive_query = sorted(
            {
                key.lower()
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                if key.lower() in SENSITIVE_URL_QUERY_KEYS
                and value.lower() not in {"", "example", "placeholder", "redacted", "synthetic"}
            }
        )
        if sensitive_query:
            findings.append(
                {
                    "file": relative_path.as_posix(),
                    "line": text.count("\n", 0, match.start()) + 1,
                    "code": "signed-or-tracking-url",
                }
            )
    return findings


def should_exclude(relative_path: Path) -> bool:
    if relative_path.as_posix() in PUBLIC_DEPENDENCIES:
        return False
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative_path.parts[:-1]):
        return True
    if relative_path.name in EXCLUDED_FILE_NAMES:
        return True
    if relative_path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    return False


def collect_public_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(directory)
        relative_directory = current.relative_to(root)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in EXCLUDED_DIRECTORY_NAMES
            and not (current / name).is_symlink()
        )
        for name in sorted(file_names):
            path = current / name
            relative_path = relative_directory / name
            if should_exclude(relative_path):
                continue
            if path.is_symlink():
                raise PackageError(f"symlink is not allowed in public package: {relative_path.as_posix()}")
            if not path.is_file():
                continue
            if path.suffix.lower() not in PUBLIC_TEXT_SUFFIXES:
                raise PackageError(f"unsupported public file type: {relative_path.as_posix()}")
            if path.stat().st_size > MAX_PUBLIC_FILE_BYTES:
                raise PackageError(f"public file exceeds size limit: {relative_path.as_posix()}")
            files.append(path)
    for relative in sorted(PUBLIC_DEPENDENCIES):
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise PackageError(f"missing or unsafe required dependency: {relative}")
        if path.stat().st_size > MAX_PUBLIC_FILE_BYTES:
            raise PackageError(f"dependency exceeds size limit: {relative}")
        if path not in files: files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def validate_skill_entry(root: Path) -> None:
    entry = root / "SKILL.md"
    if not entry.is_file():
        raise PackageError("SKILL.md is missing")
    try:
        text = entry.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise PackageError("SKILL.md is unreadable") from None
    if not text.startswith("---\n"):
        raise PackageError("SKILL.md frontmatter is missing")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise PackageError("SKILL.md frontmatter is not closed")
    frontmatter = text[4:end]
    name_match = re.search(r"(?m)^name:\s*([^\s]+)\s*$", frontmatter)
    description_match = re.search(r"(?m)^description:\s*(.+?)\s*$", frontmatter)
    if not name_match or name_match.group(1) != SKILL_NAME:
        raise PackageError("SKILL.md name does not match the public Skill name")
    if not description_match or "TODO" in description_match.group(1):
        raise PackageError("SKILL.md description is missing or unfinished")
    if "[TODO" in text or "TODO:" in text:
        raise PackageError("SKILL.md still contains TODO content")


def resolve_local_reference(root: Path, source: Path, value: str) -> None:
    candidate_text = value.strip().split(maxsplit=1)[0].strip("<>")
    if not candidate_text or candidate_text.startswith(("#", "http://", "https://", "mailto:")):
        return
    if candidate_text.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", candidate_text):
        raise PackageError(
            f"absolute local reference in {source.relative_to(root).as_posix()}"
        )
    candidate_text = candidate_text.split("#", 1)[0]
    if not candidate_text:
        return
    candidate = (source.parent / candidate_text).resolve()
    if not is_relative_to(candidate, root.resolve()):
        raise PackageError(
            f"local reference escapes the Skill in {source.relative_to(root).as_posix()}"
        )
    if not candidate.exists():
        raise PackageError(
            f"missing local reference in {source.relative_to(root).as_posix()}: {candidate_text}"
        )


def validate_markdown_references(root: Path, files: Iterable[Path]) -> int:
    checked: set[tuple[Path, str]] = set()
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_PATTERN.finditer(text):
            value = match.group(1)
            key = (path, value)
            if key not in checked:
                resolve_local_reference(root, path, value)
                checked.add(key)
        for match in RESOURCE_PATH_PATTERN.finditer(text):
            value = match.group(1).rstrip(".,;:，。；：")
            key = (path, value)
            if key not in checked:
                # Resource paths are written relative to the Skill root, even
                # when mentioned from a file inside references/.
                resolve_local_reference(root, root / "SKILL.md", value)
                checked.add(key)
    return len(checked)


def manifest_items(value: Any, names: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, dict):
        items = None
        for name in names:
            if isinstance(value.get(name), list):
                items = value[name]
                break
        if items is None:
            raise PackageError("manifest does not contain an item list")
    else:
        raise PackageError("manifest root must be an object or list")
    if not items or not all(isinstance(item, dict) for item in items):
        raise PackageError("manifest item list is empty or invalid")
    return items


def validate_manifest_reference(manifest_path: Path, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PackageError(f"manifest file reference is missing: {manifest_path.name}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise PackageError(f"manifest file reference is unsafe: {manifest_path.name}")
    target = (manifest_path.parent / Path(*pure.parts)).resolve()
    if not target.is_file():
        raise PackageError(f"manifest references a missing file: {manifest_path.name}")


def validate_evidence_manifest(path: Path) -> int:
    value = read_json(path)
    validate_json_fields(value, EVIDENCE_MANIFEST_FIELDS)
    items = manifest_items(value, ("items", "evidence"))
    seen: set[str] = set()
    for item in items:
        evidence_id = item.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id or evidence_id in seen:
            raise PackageError(f"evidence manifest has a missing or duplicate ID: {path.name}")
        seen.add(evidence_id)
        if not isinstance(item.get("collected_at"), str) or not item["collected_at"]:
            raise PackageError(f"evidence item lacks collected_at: {path.name}")
        if item.get("claim_type") not in {
            "fact",
            "computed",
            "inference",
            "user_judgment",
            "to_validate",
        }:
            raise PackageError(f"evidence item has an invalid claim_type: {path.name}")
        source_url = item.get("source_url")
        source_file = item.get("source_file")
        if not source_url and not source_file:
            raise PackageError(f"evidence item lacks a source: {path.name}")
        if source_url:
            parsed = urlsplit(str(source_url))
            if parsed.scheme != "https" or not parsed.netloc:
                raise PackageError(f"evidence source_url is invalid: {path.name}")
        if source_file:
            validate_manifest_reference(path, source_file)
    return len(items)


def validate_chart_manifest(path: Path) -> int:
    value = read_json(path)
    validate_json_fields(value, CHART_MANIFEST_FIELDS)
    items = manifest_items(value, ("items", "charts"))
    seen: set[str] = set()
    for item in items:
        chart_id = item.get("chart_id")
        if not isinstance(chart_id, str) or not chart_id or chart_id in seen:
            raise PackageError(f"chart manifest has a missing or duplicate ID: {path.name}")
        seen.add(chart_id)
        for key in ("filters", "columns", "denominator", "source"):
            if key not in item or item[key] in (None, "", []):
                raise PackageError(f"chart item lacks {key}: {path.name}")
        collected_at = item.get("collected_at")
        evidence_issues = item.get("evidence_issues") or []
        if collected_at in (None, "") and "missing_collected_at" not in evidence_issues:
            raise PackageError(
                f"chart item lacks collected_at without an explicit evidence issue: {path.name}"
            )
        validate_manifest_reference(path, item.get("file"))
        validate_manifest_reference(path, item.get("data_file"))
        source = item.get("source")
        if isinstance(source, str) and not source.startswith(("http://", "https://")):
            validate_manifest_reference(path, source)
    return len(items)


def find_and_validate_manifests(roots: Iterable[Path], require_each_root: bool) -> tuple[int, int]:
    evidence_count = 0
    chart_count = 0
    for root in roots:
        if not root.is_dir():
            raise PackageError("artifact root does not exist or is not a directory")
        candidates = sorted(
            path
            for path in root.rglob("*.json")
            if path.name.lower()
            in {
                "chart-manifest.json",
                "chart_manifest.json",
                "evidence-manifest.json",
                "evidence_manifest.json",
            }
        )
        if require_each_root and not candidates:
            raise PackageError("artifact root contains no evidence or chart manifest")
        for path in candidates:
            name = path.name.lower()
            if "evidence" in name:
                evidence_count += validate_evidence_manifest(path)
            else:
                chart_count += validate_chart_manifest(path)
    return evidence_count, chart_count


def validate_source(root: Path, artifact_roots: Iterable[Path] = ()) -> dict[str, Any]:
    root = root.resolve()
    validate_skill_entry(root)
    files = collect_public_files(root)
    if not files:
        raise PackageError("public package would be empty")

    findings: list[dict[str, Any]] = []
    json_files_checked = 0
    synthetic_fixtures_checked = 0
    for path in files:
        relative = PurePosixPath(path.relative_to(root).as_posix())
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            raise PackageError(f"public file is not readable UTF-8 text: {relative.as_posix()}") from None
        findings.extend(scan_text(text, relative))
        if path.suffix.lower() == ".json":
            value = read_json(path)
            allowlist = json_allowlist_for(relative)
            if allowlist is None:
                raise PackageError(f"JSON file has no public field allowlist: {relative.as_posix()}")
            validate_json_fields(value, allowlist)
            json_files_checked += 1
            if relative.parts[:2] == ("tests", "fixtures"):
                if not has_synthetic_marker(value):
                    raise PackageError(
                        f"test fixture lacks synthetic=true marker: {relative.as_posix()}"
                    )
                synthetic_fixtures_checked += 1
    if findings:
        first = findings[0]
        raise PackageError(
            f"privacy scan failed: {first['file']}:{first['line']} [{first['code']}] "
            f"({len(findings)} finding(s))"
        )

    local_reference_count = validate_markdown_references(root, files)
    source_evidence, source_charts = find_and_validate_manifests((root,), False)
    external_roots = tuple(path.resolve() for path in artifact_roots)
    external_evidence, external_charts = find_and_validate_manifests(external_roots, True)
    return {
        "root": root,
        "files": files,
        "file_count": len(files),
        "json_files_checked": json_files_checked,
        "synthetic_fixtures_checked": synthetic_fixtures_checked,
        "local_references_checked": local_reference_count,
        "evidence_items_checked": source_evidence + external_evidence,
        "chart_items_checked": source_charts + external_charts,
        "privacy_findings": 0,
    }


def zip_info(archive_name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(archive_name, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.flag_bits |= 0x800
    return info


def build_zip(root: Path, files: Iterable[Path], output: Path, force: bool) -> dict[str, Any]:
    root = root.resolve()
    output = output.expanduser().resolve()
    if is_relative_to(output, root):
        raise PackageError("public ZIP output must be outside the Skill source directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    existed = output.exists()
    if existed and not force:
        raise PackageError("public ZIP already exists; pass --force to replace it explicitly")

    temp_path: Path | None = None
    expected_entries: list[str] = []
    expected_hashes: dict[str, str] = {}
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, delete=False
        ) as temp_handle:
            temp_path = Path(temp_handle.name)
        with zipfile.ZipFile(
            temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
                relative = path.relative_to(root).as_posix()
                archive_name = f"{SKILL_NAME}/{relative}"
                payload = path.read_bytes()
                archive.writestr(zip_info(archive_name), payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
                expected_entries.append(archive_name)
                expected_hashes[archive_name] = hashlib.sha256(payload).hexdigest()

        with zipfile.ZipFile(temp_path, "r") as archive:
            actual_entries = archive.namelist()
            if actual_entries != expected_entries or len(actual_entries) != len(set(actual_entries)):
                raise PackageError("ZIP entry verification failed")
            for entry in actual_entries:
                payload = archive.read(entry)
                if hashlib.sha256(payload).hexdigest() != expected_hashes[entry]:
                    raise PackageError("ZIP content verification failed")
                relative = PurePosixPath(entry).relative_to(SKILL_NAME)
                try:
                    text = payload.decode("utf-8")
                except UnicodeDecodeError:
                    raise PackageError("ZIP contains a non-text public file") from None
                findings = scan_text(text, relative)
                if findings:
                    raise PackageError("ZIP privacy re-scan failed")

        with tempfile.TemporaryDirectory(prefix="jc-public-check-") as check_dir:
            with zipfile.ZipFile(temp_path, "r") as archive:
                archive.extractall(check_dir)
            snapshot = Path(check_dir) / SKILL_NAME
            snapshot_files = [snapshot / p.relative_to(root) for p in files]
            validate_markdown_references(snapshot, snapshot_files)
            for dependency in PUBLIC_DEPENDENCIES:
                if not (snapshot / dependency).is_file():
                    raise PackageError(f"ZIP missing required dependency: {dependency}")
        if force:
            os.replace(temp_path, output)
            temp_path = None
        else:
            try:
                os.link(temp_path, output)
            except FileExistsError:
                raise PackageError("public ZIP appeared during build; refusing to overwrite") from None
            temp_path.unlink()
            temp_path = None
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        return {
            "output": output,
            "file_count": len(expected_entries),
            "sha256": digest,
            "replaced_existing": existed and force,
        }
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def safe_validation_result(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "action": "validated",
        "file_count": report["file_count"],
        "json_files_checked": report["json_files_checked"],
        "synthetic_fixtures_checked": report["synthetic_fixtures_checked"],
        "local_references_checked": report["local_references_checked"],
        "evidence_items_checked": report["evidence_items_checked"],
        "chart_items_checked": report["chart_items_checked"],
        "privacy_findings": report["privacy_findings"],
    }


def validate_command(args: argparse.Namespace) -> dict[str, Any]:
    report = validate_source(SOURCE_ROOT, args.artifact_root)
    return safe_validation_result(report)


def package_command(args: argparse.Namespace) -> dict[str, Any]:
    report = validate_source(SOURCE_ROOT, args.artifact_root)
    package = build_zip(report["root"], report["files"], args.out, args.force)
    result = safe_validation_result(report)
    result.update(
        {
            "action": "packaged",
            "output": str(package["output"]),
            "zip_sha256": package["sha256"],
            "replaced_existing": package["replaced_existing"],
        }
    )
    return result


def self_test_command(_: argparse.Namespace) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="jc-media-research-package-") as temp:
        base = Path(temp)
        root = base / SKILL_NAME
        (root / "scripts").mkdir(parents=True)
        (root / "tests" / "fixtures").mkdir(parents=True)
        (root / "SKILL.md").write_text(
            "---\nname: jc-media-research\n"
            "description: Offline synthetic packaging test.\n---\n\n"
            "# Test\n\nUse `scripts/example.py`.\n",
            encoding="utf-8",
        )
        (root / "scripts" / "example.py").write_text("print('synthetic')\n", encoding="utf-8")
        (root / "tests" / "fixtures" / "sample.json").write_text(
            json.dumps(
                {
                    "_meta": {"synthetic": True},
                    "records": [
                        {
                            "content_id": "synthetic-001",
                            "source_url": "https://example.invalid/video/synthetic-001",
                            "likes": 1000,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        report = validate_source(root)
        first = build_zip(root, report["files"], base / "first.zip", False)
        second = build_zip(root, report["files"], base / "second.zip", False)
        if first["sha256"] != second["sha256"]:
            raise AssertionError("reproducible ZIP check failed")
        bad = scan_text(
            "Authorization: " + "Bear" + "er abcdefghijklmnopqrstuvwxyz",
            PurePosixPath("synthetic.txt"),
        )
        if not bad:
            raise AssertionError("token scan check failed")
        try:
            build_zip(root, report["files"], base / "first.zip", False)
            raise AssertionError("non-overwrite check failed")
        except PackageError:
            pass
    return {
        "ok": True,
        "action": "self_test",
        "network_requests_made": 0,
        "checks": 4,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate jc-media-research and build a reproducible public ZIP."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate without creating a ZIP")
    validate_parser.add_argument(
        "--artifact-root",
        type=Path,
        action="append",
        default=[],
        help="Optional task artifact directory whose evidence/chart manifests must validate",
    )
    validate_parser.set_defaults(handler=validate_command)

    package_parser = subparsers.add_parser("package", help="Validate and create the public ZIP")
    package_parser.add_argument("--out", type=Path, required=True)
    package_parser.add_argument("--force", action="store_true")
    package_parser.add_argument(
        "--artifact-root",
        type=Path,
        action="append",
        default=[],
        help="Optional task artifact directory whose evidence/chart manifests must validate",
    )
    package_parser.set_defaults(handler=package_command)

    self_test_parser = subparsers.add_parser("self-test", help="Run offline packaging checks")
    self_test_parser.set_defaults(handler=self_test_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.handler(args)
    except (PackageError, OSError, AssertionError) as error:
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
