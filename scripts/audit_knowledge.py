#!/usr/bin/env python3
"""Semantic audit for the MC decision knowledge base.

`validate_knowledge.py` enforces the field contract. This script enforces the
consistency rules that span multiple files or cannot be expressed in JSON Schema:
stage conventions, recovery ladders, routing between overlapping failure cards,
vocabulary, readability limits and timestamp sanity.

Exit code is 0 only when no finding is produced, so it can gate a batch.

Usage:
    python3 scripts/audit_knowledge.py
    python3 scripts/audit_knowledge.py --root /path/to/project
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FEATURE_PLAIN_RE = re.compile(r"^[a-z][a-z0-9_]*$")
FEATURE_PATH_RE = re.compile(r"^(bot|furnace|movements|plan|runtime)(\.[A-Za-z0-9_]+)+$")
LADDER_RE = re.compile(r"^L([1-4])\s")
ASCII_CODE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
CODE_FORMAT_RE = re.compile(r"^[a-z][a-z0-9_]*(:[a-z][a-z0-9_]*)?$")
# Error names that must stay verbatim so a runtime can match the library's own strings.
VERBATIM_CODES = {"NoPath", "Timeout", "GoalChanged", "PathStopped", "diggingAborted"}
RETRY_COUNT_RE = re.compile(r"(\d+)\s*次")
POLICY_THRESHOLD_RE = re.compile(r"(生命|食物)\s*[<>≥≤]\s*\d+")
POLICY_MARK = "策略阈值"
PIN_RE = re.compile(r"（[^）]*）|[，,。；;：:]")

SUMMARY_LIMIT = 500
TOOL_STAGE = "general"


class Audit:
    def __init__(self) -> None:
        self.findings: list[str] = []
        self.checked = 0

    def add(self, scope: str, message: str) -> None:
        self.findings.append(f"[{scope}] {message}")


def load_items(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    items = []
    for path in sorted((root / "knowledge").glob("*/*.json")):
        items.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return items


def norm_condition(text: str) -> str:
    return PIN_RE.sub("", text).strip()


def audit_failures(items, audit: Audit) -> None:
    failures = [(p, i) for p, i in items if i.get("knowledge_type") == "failure_recovery"]

    for path, item in failures:
        name = item.get("id", path.stem)

        levels = []
        for step in item.get("recovery_steps", []):
            match = LADDER_RE.match(step)
            if not match:
                audit.add(name, f"recovery step is not graded with L1-L4 prefix: {step[:24]!r}")
                continue
            levels.append(int(match.group(1)))
        if levels != [1, 2, 3, 4]:
            audit.add(name, f"recovery ladder must be exactly L1,L2,L3,L4 in order, got {levels}")

        escalate = item.get("escalate_after")
        unit = item.get("escalation_unit")
        if not isinstance(escalate, int) or isinstance(escalate, bool) or escalate < 1:
            audit.add(name, "escalate_after must be a positive integer")
        if unit not in {"recovery_round", "attempt"}:
            audit.add(name, f"escalation_unit missing or unsupported: {unit!r}")
        if isinstance(escalate, int) and item.get("recovery_steps"):
            first = item["recovery_steps"][0]
            counts = [int(value) for value in RETRY_COUNT_RE.findall(first)]
            for value in counts:
                if value > escalate:
                    audit.add(
                        name,
                        f"L1 allows {value} attempts but escalate_after is {escalate}; "
                        "the retry budget is larger than the escalation budget",
                    )

        if not item.get("forbidden_actions"):
            audit.add(name, "failure card has no forbidden_actions")

        text = json.dumps(item, ensure_ascii=False)
        if not any(word in text for word in ("重试", "重复")):
            audit.add(name, "failure card never bounds retries in its text")

    # Routing: cards that share a trigger condition must point at each other.
    for (path_a, a), (path_b, b) in itertools.combinations(failures, 2):
        conds_a = {norm_condition(c) for c in a.get("trigger", {}).get("conditions", [])}
        conds_b = {norm_condition(c) for c in b.get("trigger", {}).get("conditions", [])}
        if not (conds_a & conds_b):
            continue
        disc_a = " ".join(a.get("diagnostics", [])[:1])
        disc_b = " ".join(b.get("diagnostics", [])[:1])
        if b["id"] not in disc_a and a["id"] not in disc_b:
            audit.add(
                a["id"],
                f"shares a trigger condition with {b['id']} but neither card routes to the other",
            )


def audit_playbooks(items, audit: Audit) -> None:
    """Playbooks must state when they do not apply and what to write back when done."""
    for path, item in items:
        if item.get("knowledge_type") != "playbook":
            continue
        name = item.get("id", path.stem)
        abort = " ".join(item.get("abort_condition", []))
        if "不适用" not in abort:
            audit.add(name, "abort_condition does not declare the non-applicable state")
        actions = " ".join(item.get("actions", []))
        if "回写" not in actions:
            audit.add(
                name,
                "actions never says which state facts must be written back after the scenario ends",
            )
        if len(item.get("failure_entry_points", [])) < 1:
            audit.add(name, "playbook has no failure entry points")


def audit_tools(items, audit: Audit) -> None:
    for path, item in items:
        if item.get("knowledge_type") != "tool_guide":
            continue
        name = item.get("id", path.stem)

        if item.get("stage") != TOOL_STAGE:
            audit.add(name, f"tool guide stage must be {TOOL_STAGE!r}, got {item.get('stage')!r}")

        for mode in item.get("failure_modes", []):
            code = re.split(r"\s+—\s+|—", mode, maxsplit=1)[0].strip()
            if not ASCII_CODE_RE.search(mode):
                audit.add(name, f"failure mode has no code-like token: {mode[:30]!r}")
                continue
            if code in VERBATIM_CODES or CODE_FORMAT_RE.match(code):
                continue
            audit.add(
                name,
                f"failure mode code {code!r} is neither lower_snake_case, a namespaced "
                "code (ns:code), nor an allowlisted verbatim library error name",
            )

        risks = " ".join(item.get("risk_notes", []))
        if not any(word in risks for word in ("不要", "禁止", "不应", "不得")):
            audit.add(name, "risk_notes do not state when the tool must not be used")

        if not item.get("abort_condition"):
            audit.add(name, "tool guide has no abort_condition (timeout/interrupt semantics)")
        else:
            abort = " ".join(item["abort_condition"])
            if not any(word in abort for word in ("超时", "中断", "timeout")):
                audit.add(name, "abort_condition does not describe timeout or interruption")

        for param in item.get("parameters", []):
            if "required" not in param:
                audit.add(name, f"parameter {param.get('name')!r} does not declare required")


def audit_common(items, audit: Audit) -> None:
    now = datetime.now(timezone.utc)

    for path, item in items:
        name = item.get("id", path.stem)

        for feature in item.get("trigger", {}).get("state_features", []):
            if FEATURE_PLAIN_RE.match(feature) or FEATURE_PATH_RE.match(feature):
                continue
            audit.add(name, f"state feature is neither snake_case nor a known dotted path: {feature!r}")

        summary = item.get("summary", "")
        if len(summary) > SUMMARY_LIMIT:
            audit.add(name, f"summary is {len(summary)} chars, over the {SUMMARY_LIMIT} readability limit")

        for field in ("created_at", "updated_at"):
            value = item.get(field)
            try:
                stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                audit.add(name, f"{field} is not ISO-8601: {value!r}")
                continue
            if stamp > now:
                audit.add(name, f"{field} is in the future: {value}")

        if item.get("validation_status") == "source_verified":
            scope = set(item.get("verified_scope", []))
            if not scope & {"api_contract", "error_codes", "default_values", "gameplay_mechanics"}:
                audit.add(name, "source_verified without any externally checkable verified_scope")

    failures = [i for _, i in items if i.get("knowledge_type") == "failure_recovery"]
    for a, b in itertools.combinations(failures, 2):
        sa = {norm_condition(s) for s in a.get("symptoms", [])}
        sb = {norm_condition(s) for s in b.get("symptoms", [])}
        if not sa or not sb:
            continue
        ratio = len(sa & sb) / len(sa | sb)
        if ratio >= 0.5:
            audit.add(a["id"], f"symptoms overlap {ratio:.0%} with {b['id']}; cards may be duplicates")


def audit_error_code_claims(items, sources: dict[str, dict[str, Any]], audit: Audit) -> None:
    """A card may claim error_codes evidence only if at least one of its codes is verbatim in a source."""
    for path, item in items:
        if item.get("knowledge_type") != "tool_guide":
            continue
        if "error_codes" not in item.get("verified_scope", []):
            continue
        excerpts = " ".join(
            str(sources.get(source_id, {}).get("content_excerpt", ""))
            for source_id in item.get("source_refs", [])
        ).lower()
        if not excerpts:
            audit.add(item.get("id", path.stem), "verified_scope claims error_codes but no source excerpt is available")
            continue
        codes = []
        for mode in item.get("failure_modes", []):
            token = re.split(r"\s+—\s+|—", mode, maxsplit=1)[0].strip()
            if token:
                codes.append(token.lower())
        if not any(code in excerpts for code in codes):
            audit.add(
                item.get("id", path.stem),
                "verified_scope claims error_codes, but none of its failure-mode codes appear "
                "verbatim in the cited sources (the codes are project-invented)",
            )


# 只有真正的官方文档才算 official_document。
# source_code / github_repository / benchmark / research_paper 都是一手但非官方文档，
# 把它们算作 "official-ish" 会让 official_document 成为几乎无法触发的声明。
OFFICIAL_EVIDENCE_TYPES = {
    "official_document",
}


def audit_evidence_typing(items, sources: dict[str, dict[str, Any]], audit: Audit) -> None:
    """`official_document` must be backed by at least one official-ish source."""
    for path, item in items:
        if item.get("evidence_type") != "official_document":
            continue
        source_types = {
            sources.get(ref, {}).get("source_type") for ref in item.get("source_refs", [])
        }
        if not source_types & OFFICIAL_EVIDENCE_TYPES:
            audit.add(
                item.get("id", path.stem),
                f"evidence_type is official_document but cited sources are {sorted(t for t in source_types if t)}; "
                "use community_consensus or cite an official source",
            )


def audit_threshold_labels(items, audit: Audit) -> None:
    """Literal health/food thresholds are project policy, not game rules, and must say so."""
    for path, item in items:
        name = item.get("id", path.stem)
        for field in ("preconditions", "abort_condition", "success_condition", "risk_notes"):
            values = item.get(field)
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, str):
                    continue
                if POLICY_THRESHOLD_RE.search(value) and POLICY_MARK not in value:
                    audit.add(
                        name,
                        f"{field} states a literal life/hunger threshold without the "
                        f"{POLICY_MARK!r} marker: {value[:32]!r}",
                    )


def audit_schema(root: Path, items, audit: Audit) -> None:
    try:
        import jsonschema
    except ImportError:
        # A skipped strict check must not look like a pass. Either install jsonschema
        # or run the audit in the project environment (WSL), where it is installed.
        audit.add(
            "repository",
            "strict JSON Schema validation was SKIPPED: jsonschema is not installed in this "
            "interpreter. Install it (pip install jsonschema) or run the audit in the project "
            "environment before treating this run as a clean pass",
        )
        return
    schema_path = root / "schemas" / "knowledge-item.schema.json"
    if not schema_path.exists():
        # Fall back to the schema shipped next to this script so the audit can run
        # against a knowledge-only directory (tests, exported bundles).
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "knowledge-item.schema.json"
    if not schema_path.exists():
        audit.add(
            "repository",
            f"strict JSON Schema validation was SKIPPED: schema file not found at {schema_path}",
        )
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for path, item in items:
        for error in validator.iter_errors(item):
            audit.add(item.get("id", path.stem), f"schema: {error.json_path} {error.message}")


def load_sources(root: Path) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "sources").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        source_id = data.get("source_id")
        if isinstance(source_id, str):
            sources[source_id] = data
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit MC decision knowledge consistency")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()

    root = args.root.resolve()
    items = load_items(root)
    sources = load_sources(root)
    audit = Audit()

    if not items:
        print("audit: knowledge base is empty")
        return 1

    audit.checked = len(items)
    audit_schema(root, items, audit)
    audit_failures(items, audit)
    audit_playbooks(items, audit)
    audit_tools(items, audit)
    audit_error_code_claims(items, sources, audit)
    audit_evidence_typing(items, sources, audit)
    audit_threshold_labels(items, audit)
    audit_common(items, audit)

    print(f"Audited items: {audit.checked}")
    print(f"Findings: {len(audit.findings)}")
    for finding in audit.findings:
        print(f"FINDING {finding}")

    if audit.findings:
        return 1
    print("Audit passed with no findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
