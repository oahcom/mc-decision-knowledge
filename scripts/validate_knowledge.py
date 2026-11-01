#!/usr/bin/env python3
"""Validate MC decision knowledge items and source records.

The project intentionally uses only the Python standard library so the validator can run
in any environment. The schemas in ../schemas are the authoritative field contract;
this script adds cross-file checks that JSON Schema alone cannot express.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

KNOWLEDGE_TYPE_DIRS = {
    "strategy": "strategies",
    "playbook": "playbooks",
    "failure_recovery": "failures",
    "tool_guide": "tool_guides",
    "ai_heuristic": "ai_heuristics",
}

ID_PREFIXES = {
    "strategy": "strategy_",
    "playbook": "playbook_",
    "failure_recovery": "failure_",
    "tool_guide": "tool_",
    "ai_heuristic": "ai_",
}

COMMON_ITEM_REQUIRED = {
    "id",
    "knowledge_type",
    "title",
    "summary",
    "game_edition",
    "game_versions",
    "stage",
    "trigger",
    "actions",
    "preconditions",
    "success_condition",
    "abort_condition",
    "risk_notes",
    "source_refs",
    "evidence_type",
    "confidence",
    "validation_status",
    "created_at",
    "updated_at",
}

TYPE_REQUIRED = {
    "strategy": {"candidate_routes", "decision_tradeoffs"},
    "playbook": {
        "scenario",
        "checklist",
        "continue_condition",
        "exit_condition",
        "failure_entry_points",
    },
    "failure_recovery": {
        "symptoms",
        "possible_causes",
        "diagnostics",
        "recovery_steps",
        "escalate_after",
        "escalation_unit",
        "forbidden_actions",
    },
    "tool_guide": {
        "tool_name",
        "parameters",
        "expected_effects",
        "failure_modes",
        "verification",
    },
    "ai_heuristic": {
        "decision_rule",
        "alternative_comparison",
        "anti_patterns",
        "model_guidance",
    },
}

SOURCE_REQUIRED = {
    "source_id",
    "title",
    "url",
    "platform",
    "source_type",
    "reliability",
    "license",
    "retrieved_at",
    "content_excerpt",
    "evidence_notes",
    "related_game_versions",
    "access_method",
    "compliance",
}

ITEM_ENUMS = {
    "knowledge_type": set(KNOWLEDGE_TYPE_DIRS),
    "game_edition": {"java", "bedrock", "both"},
    "stage": {
        "spawn",
        "wood_age",
        "stone_age",
        "iron_age",
        "diamond_age",
        "nether",
        "end",
        "general",
    },
    "evidence_type": {
        "official_document",
        "code_behavior",
        "community_consensus",
        "expert_heuristic",
        "replay_observation",
        "ai_synthesis",
    },
    "confidence": {"low", "medium", "high"},
    "validation_status": {
        "draft",
        "source_verified",
        "replay_verified",
        "human_verified",
        "deprecated",
    },
}

SOURCE_ENUMS = {
    "source_type": {
        "official_document",
        "community_wiki",
        "github_repository",
        "source_code",
        "issue_or_pr",
        "forum_or_social",
        "video",
        "research_paper",
        "benchmark",
        "internal_design",
    },
    "reliability": {"A", "B", "C", "D"},
    "access_method": {"public_page", "official_api", "search_result", "local_file"},
}

ESCALATION_UNITS = {"recovery_round", "attempt"}

VERIFIED_SCOPES = {
    "api_contract",
    "error_codes",
    "default_values",
    "gameplay_mechanics",
    "project_policy",
}

# Scopes that represent evidence from outside this project. A item whose verified
# scope is only project_policy has not been checked against any external source.
EXTERNAL_SCOPES = {"api_contract", "error_codes", "default_values", "gameplay_mechanics"}

PARAMETER_TYPES = {
    "string",
    "integer",
    "number",
    "boolean",
    "boolean_or_ignore",
    "object",
    "block_pos",
    "entity_ref",
    "item_id",
    "list<string>",
    "map",
}

LINK_PREFIXES = ("link_playbook:", "link_strategy:")

# Fields the schema defines as a single string. Every one of them previously
# tripped the generic "list of strings" branch of the type-field loop.
STRING_FIELDS = {"tool_name", "decision_rule", "model_guidance", "scenario"}

REGISTRY_KEYS = ("reserved_playbooks", "reserved_strategies")

COMPLIANCE_REQUIRED = {
    "publicly_accessible",
    "robots_or_terms_respected",
    "personal_data_excluded",
    "no_auth_bypass",
}

ID_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")
SOURCE_ID_RE = re.compile(r"^src_[a-z0-9]+(?:_[a-z0-9]+)+$")
URL_RE = re.compile(r"^(https?://|local://).+")


class ValidationReport:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.item_count = 0
        self.source_count = 0

    def error(self, path: Path, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def warn(self, path: Path, message: str) -> None:
        self.warnings.append(f"{path}: {message}")

    @property
    def passed(self) -> bool:
        return not self.errors


def parse_datetime(value: str) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_string_list(value: Any, *, allow_empty: bool = False) -> bool:
    if not isinstance(value, list):
        return False
    if not allow_empty and not value:
        return False
    return all(validate_nonempty_string(item) for item in value)


def load_json_files(directory: Path) -> list[tuple[Path, dict[str, Any]]]:
    if not directory.exists():
        return []
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot load {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Top-level JSON must be an object: {path}")
        records.append((path, data))
    return records


def validate_source(source: dict[str, Any], path: Path, report: ValidationReport) -> None:
    missing = SOURCE_REQUIRED - set(source)
    if missing:
        report.error(path, f"missing required fields: {sorted(missing)}")

    source_id = source.get("source_id")
    if not validate_nonempty_string(source_id) or not SOURCE_ID_RE.fullmatch(str(source_id)):
        report.error(path, "source_id must match src_lower_snake_case")

    for field in ("title", "platform", "license", "evidence_notes"):
        if not validate_nonempty_string(source.get(field)):
            report.error(path, f"{field} must be a non-empty string")

    url = source.get("url")
    if not validate_nonempty_string(url) or not URL_RE.fullmatch(str(url)):
        report.error(path, "url must start with http://, https://, or local://")

    for field, allowed in SOURCE_ENUMS.items():
        if field in source and source[field] not in allowed:
            report.error(path, f"{field} has unsupported value: {source[field]!r}")

    retrieved = parse_datetime(source.get("retrieved_at", ""))
    if retrieved is None:
        report.error(path, "retrieved_at must be an ISO-8601 date-time")

    excerpt = source.get("content_excerpt")
    if not validate_nonempty_string(excerpt):
        report.error(path, "content_excerpt must be a non-empty string")
    elif len(excerpt) > 1200:
        report.error(path, "content_excerpt must not exceed 1200 characters")

    if not validate_string_list(source.get("related_game_versions"), allow_empty=True):
        report.error(path, "related_game_versions must be a list of non-empty strings")

    compliance = source.get("compliance")
    if not isinstance(compliance, dict):
        report.error(path, "compliance must be an object")
    else:
        missing_compliance = COMPLIANCE_REQUIRED - set(compliance)
        if missing_compliance:
            report.error(path, f"compliance missing fields: {sorted(missing_compliance)}")
        for field in COMPLIANCE_REQUIRED:
            if field in compliance and compliance[field] is not True:
                report.error(path, f"compliance.{field} must be true")

    quality = source.get("quality")
    if quality is not None:
        if not isinstance(quality, dict):
            report.error(path, "quality must be an object")
        else:
            for field, value in quality.items():
                if field not in {
                    "decision_relevance",
                    "specificity",
                    "version_clarity",
                    "reproducibility",
                }:
                    report.error(path, f"quality has unsupported field: {field}")
                elif not isinstance(value, int) or not 1 <= value <= 5:
                    report.error(path, f"quality.{field} must be an integer from 1 to 5")



def _load_confidence_grader():
    """加载 scripts/grade_confidence.py 的 grade() 函数（不依赖包路径）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_grade_confidence", str(Path(__file__).resolve().parent / "grade_confidence.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.grade


def validate_item(
    item: dict[str, Any],
    path: Path,
    source_records: dict[str, tuple[dict[str, Any], Path]],
    report: ValidationReport,
    known_ids: set[str] | None = None,
    registry_ids: set[str] | None = None,
    known_failure_ids: set[str] | None = None,
) -> None:
    known_ids = known_ids or set()
    registry_ids = registry_ids or set()
    known_failure_ids = known_failure_ids or set()
    missing = COMMON_ITEM_REQUIRED - set(item)
    if missing:
        report.error(path, f"missing required fields: {sorted(missing)}")

    knowledge_type = item.get("knowledge_type")
    if knowledge_type not in KNOWLEDGE_TYPE_DIRS:
        report.error(path, f"unsupported knowledge_type: {knowledge_type!r}")
        return

    expected_dir = KNOWLEDGE_TYPE_DIRS[knowledge_type]
    if path.parent.name != expected_dir:
        report.error(
            path,
            f"knowledge_type {knowledge_type} belongs in knowledge/{expected_dir}, "
            f"but file is in knowledge/{path.parent.name}",
        )

    item_id = item.get("id")
    if not validate_nonempty_string(item_id) or not ID_RE.fullmatch(str(item_id)):
        report.error(path, "id must use lower_snake_case")
    elif not str(item_id).startswith(ID_PREFIXES[knowledge_type]):
        report.error(
            path,
            f"id must start with {ID_PREFIXES[knowledge_type]!r} for {knowledge_type}",
        )

    for field in ("title", "summary", "success_condition"):
        if not validate_nonempty_string(item.get(field)):
            report.error(path, f"{field} must be a non-empty string")

    for field, allowed in ITEM_ENUMS.items():
        if field in item and item[field] not in allowed:
            report.error(path, f"{field} has unsupported value: {item[field]!r}")

    if not validate_string_list(item.get("game_versions")):
        report.error(path, "game_versions must be a non-empty list of strings")

    trigger = item.get("trigger")
    if not isinstance(trigger, dict):
        report.error(path, "trigger must be an object with conditions and state_features")
    else:
        if not validate_string_list(trigger.get("conditions")):
            report.error(path, "trigger.conditions must be a non-empty list of strings")
        if not validate_string_list(trigger.get("state_features"), allow_empty=True):
            report.error(path, "trigger.state_features must be a list of strings")

    for field in ("actions", "abort_condition"):
        if not validate_string_list(item.get(field)):
            report.error(path, f"{field} must be a non-empty list of strings")

    for field in ("preconditions", "risk_notes"):
        if not validate_string_list(item.get(field), allow_empty=True):
            report.error(path, f"{field} must be a list of strings")

    for field in TYPE_REQUIRED[knowledge_type]:
        if field not in item:
            report.error(path, f"{knowledge_type} requires field: {field}")
        elif field == "escalate_after":
            value = item[field]
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                report.error(path, "escalate_after must be an integer >= 1")
        elif field == "escalation_unit":
            if item[field] not in ESCALATION_UNITS:
                report.error(path, f"escalation_unit has unsupported value: {item[field]!r}")
        elif field == "parameters":
            parameters = item[field]
            if not isinstance(parameters, list):
                report.error(path, "parameters must be a list of objects")
            else:
                for parameter in parameters:
                    if not isinstance(parameter, dict) or not validate_nonempty_string(
                        parameter.get("name")
                    ):
                        report.error(path, "each parameter must be an object with a name")
                        continue
                    if parameter.get("type") not in PARAMETER_TYPES:
                        report.error(
                            path,
                            f"parameter {parameter.get('name')!r} has unsupported type: "
                            f"{parameter.get('type')!r}",
                        )
        elif field in STRING_FIELDS:
            # The schema defines these fields as a single string, not a list.
            if not validate_nonempty_string(item[field]):
                report.error(path, f"{field} must be a non-empty string")
        elif not validate_string_list(item[field], allow_empty=True):
            report.error(path, f"{field} must be a list of non-empty strings")

    source_refs = item.get("source_refs")
    if not validate_string_list(source_refs):
        report.error(path, "source_refs must be a non-empty list of strings")
    else:
        for source_id in source_refs:
            if source_id not in source_records:
                report.error(path, f"source_refs references unknown source: {source_id}")

    confidence = item.get("confidence")
    validation_status = item.get("validation_status")

    # confidence 表示「证据强度」，不是「评审进度」——两者正交。
    # 它必须与 grade_confidence.py 按来源构成推导的结果一致，不可手工填写；
    # 评审进度由 validation_status 单独表达。
    _grade_fn = _load_confidence_grader()
    _srcs = {sid: doc for sid, (doc, _p) in source_records.items()}
    _expected_conf, _expected_strength, _score, _notes = _grade_fn(item, _srcs)
    if confidence != _expected_conf:
        report.error(
            path,
            f"confidence is {confidence!r} but the evidence composition grades it as "
            f"{_expected_conf!r} (score {_score}); run scripts/grade_confidence.py --apply",
        )
    if item.get("evidence_strength") != _expected_strength:
        report.error(
            path,
            f"evidence_strength is {item.get('evidence_strength')!r} but the evidence "
            f"composition grades it as {_expected_strength!r}; "
            f"run scripts/grade_confidence.py --apply",
        )

    if validation_status == "source_verified":
        external = [
            source_id
            for source_id in source_refs or []
            if source_id in source_records
            and source_records[source_id][0].get("source_type") != "internal_design"
        ]
        if not external:
            report.error(
                path,
                "source_verified requires at least one non-internal source reference",
            )
        scope = item.get("verified_scope")
        if not validate_string_list(scope):
            report.error(path, "source_verified requires a non-empty verified_scope list")
        else:
            unknown = sorted({value for value in scope if value not in VERIFIED_SCOPES})
            if unknown:
                report.error(path, f"verified_scope has unsupported values: {unknown}")
            elif not EXTERNAL_SCOPES & set(scope):
                report.error(
                    path,
                    "verified_scope must include at least one externally checkable scope "
                    "(project_policy alone cannot justify source_verified)",
                )

    created = parse_datetime(item.get("created_at", ""))
    updated = parse_datetime(item.get("updated_at", ""))
    if created is None or updated is None:
        report.error(path, "created_at and updated_at must be ISO-8601 date-times")
    elif updated < created:
        report.error(path, "updated_at cannot be earlier than created_at")

    if "tags" in item and not validate_string_list(item["tags"], allow_empty=True):
        report.error(path, "tags must be a list of strings")
    else:
        for tag in item.get("tags", []):
            if not validate_nonempty_string(tag):
                continue
            for prefix in LINK_PREFIXES:
                if tag.startswith(prefix):
                    target = tag[len(prefix) :].strip()
                    if target not in known_ids and target not in registry_ids:
                        report.error(
                            path,
                            f"tag {tag!r} points to an unknown target: it is neither an existing "
                            f"knowledge item nor declared in knowledge/registry.json",
                        )

    if knowledge_type == "playbook":
        entry_points = item.get("failure_entry_points", [])
        if not validate_string_list(entry_points):
            report.error(path, "playbook requires a non-empty failure_entry_points list")
        else:
            for ref in entry_points:
                if ref not in known_ids:
                    report.error(
                        path,
                        f"failure_entry_points references an unknown failure id: {ref}",
                    )
                elif known_failure_ids and ref not in known_failure_ids:
                    report.error(
                        path,
                        f"failure_entry_points must reference failure_recovery items, "
                        f"but {ref} is not one",
                    )

    if "supersedes" in item and not validate_string_list(item["supersedes"], allow_empty=True):
        report.error(path, "supersedes must be a list of strings")


def load_registry(root: Path, report: ValidationReport) -> tuple[set[str], dict[str, str]]:
    """Reserved ids for artifacts that are referenced by tags before they exist."""
    path = root / "knowledge" / "registry.json"
    if not path.exists():
        return set(), {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        report.error(path, f"cannot load registry: {exc}")
        return set(), {}
    if not isinstance(data, dict):
        report.error(path, "registry must be a JSON object")
        return set(), {}
    ids: set[str] = set()
    for key in REGISTRY_KEYS:
        values = data.get(key, [])
        if not isinstance(values, list) or not all(
            validate_nonempty_string(value) for value in values
        ):
            report.error(path, f"{key} must be a list of non-empty strings")
            continue
        ids.update(values)

    entity_map = data.get("entity_map", {})
    if not isinstance(entity_map, dict) or not all(
        validate_nonempty_string(key) and validate_nonempty_string(value)
        for key, value in entity_map.items()
    ):
        report.error(path, "entity_map must map non-empty strings to non-empty strings")
        entity_map = {}
    for canonical, target in entity_map.items():
        if canonical not in ids:
            report.error(
                path,
                f"entity_map key {canonical!r} is not declared in reserved_playbooks/reserved_strategies",
            )
    return ids, entity_map


def validate_repository(root: Path) -> ValidationReport:
    report = ValidationReport()
    sources_dir = root / "sources"
    knowledge_dir = root / "knowledge"

    try:
        source_files = load_json_files(sources_dir)
    except ValueError as exc:
        report.errors.append(str(exc))
        return report

    source_ids: dict[str, Path] = {}
    source_records: dict[str, tuple[dict[str, Any], Path]] = {}
    for path, source in source_files:
        validate_source(source, path, report)
        source_id = source.get("source_id")
        if isinstance(source_id, str):
            if source_id in source_ids:
                report.error(path, f"duplicate source_id: {source_id}")
            else:
                source_ids[source_id] = path
                source_records[source_id] = (source, path)
        report.source_count += 1

    loaded_items: list[tuple[Path, dict[str, Any]]] = []
    for type_dir in set(KNOWLEDGE_TYPE_DIRS.values()):
        directory = knowledge_dir / type_dir
        if not directory.exists():
            report.warn(root, f"knowledge directory missing: knowledge/{type_dir}")
            continue
        try:
            loaded_items.extend(load_json_files(directory))
        except ValueError as exc:
            report.errors.append(str(exc))

    known_ids = {
        item["id"] for _, item in loaded_items if isinstance(item.get("id"), str)
    }
    registry_ids, entity_map = load_registry(root, report)

    known_failure_ids = {
        item["id"]
        for _, item in loaded_items
        if isinstance(item.get("id"), str)
        and item.get("knowledge_type") == "failure_recovery"
    }

    for canonical, target in entity_map.items():
        if target not in known_ids:
            report.error(
                root / "knowledge" / "registry.json",
                f"entity_map declares {canonical!r} -> {target!r} but no such knowledge item exists; "
                "either create the item or remove the mapping",
            )

    for path, item in loaded_items:
        validate_item(
            item, path, source_records, report, known_ids, registry_ids, known_failure_ids
        )
        report.item_count += 1

    if report.item_count == 0:
        report.warn(root, "knowledge base is empty")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MC decision knowledge repository")
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root directory")
    parser.add_argument(
        "--require-nonempty",
        action="store_true",
        help="Fail when the knowledge base contains no items",
    )
    args = parser.parse_args()

    try:
        report = validate_repository(args.root.resolve())
    except Exception as exc:  # Keep the CLI deterministic even on unexpected input.
        print(f"Validation failed to run: {exc}", file=sys.stderr)
        return 2

    print(f"Knowledge items: {report.item_count}")
    print(f"Source records: {report.source_count}")
    print(f"Errors: {len(report.errors)}")
    print(f"Warnings: {len(report.warnings)}")

    for message in report.errors:
        print(f"ERROR {message}")
    for message in report.warnings:
        print(f"WARNING {message}")

    if not report.passed:
        return 1
    if args.require_nonempty and report.item_count == 0:
        print("ERROR knowledge base must not be empty when --require-nonempty is set")
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
