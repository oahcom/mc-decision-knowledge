import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("validate_knowledge.py")
SPEC = importlib.util.spec_from_file_location("validate_knowledge", SCRIPT)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VALIDATOR)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def valid_source() -> dict:
    return {
        "source_id": "src_official_example",
        "title": "Official example source",
        "url": "https://example.com/minecraft",
        "platform": "example",
        "source_type": "official_document",
        "reliability": "A",
        "license": "unknown_needs_verification",
        "retrieved_at": "2026-11-01T00:00:00+08:00",
        "content_excerpt": "A short excerpt that supports the tested knowledge item.",
        "evidence_notes": "Used to test the validator.",
        "related_game_versions": ["1.20.1"],
        "access_method": "public_page",
        "compliance": {
            "publicly_accessible": True,
            "robots_or_terms_respected": True,
            "personal_data_excluded": True,
            "no_auth_bypass": True,
        },
    }


def valid_strategy() -> dict:
    return {
        "id": "strategy_iron_route_selection",
        "knowledge_type": "strategy",
        "title": "Iron route selection",
        "summary": "Select an iron acquisition route based on verified state and risk.",
        "game_edition": "java",
        "game_versions": ["1.20.1"],
        "stage": "iron_age",
        "trigger": {
            "conditions": ["Iron equipment is the current goal"],
            "state_features": ["inventory", "health", "food"],
        },
        "actions": ["Compare candidate routes", "Select the lowest-risk route"],
        "preconditions": ["Basic tools are available"],
        "success_condition": "Iron ingot count reaches the planned amount",
        "abort_condition": ["Supplies are insufficient", "Route fails repeatedly"],
        "risk_notes": ["Do not treat one route as universal"],
        "source_refs": ["src_official_example"],
        "evidence_type": "official_document",
        "confidence": "medium",
        "evidence_strength": "medium",
        "validation_status": "source_verified",
        "verified_scope": ["gameplay_mechanics"],
        "created_at": "2026-11-01T00:00:00+08:00",
        "updated_at": "2026-11-01T00:00:00+08:00",
        "candidate_routes": ["Cave exploration", "Branch mining"],
        "decision_tradeoffs": ["Cave exploration is faster but riskier"],
        "tags": ["test"],
    }


def valid_failure() -> dict:
    item = valid_strategy()
    item.update(
        {
            "id": "failure_example_resource_not_found",
            "knowledge_type": "failure_recovery",
            "title": "Resource not found",
            "summary": "Diagnose and recover when target resources do not increase.",
            "symptoms": ["count does not grow"],
            "possible_causes": ["wrong layer"],
            "diagnostics": ["check layer"],
            "recovery_steps": ["L1 retry with new target"],
            "escalate_after": 2,
            "escalation_unit": "recovery_round",
            "forbidden_actions": ["blind retry"],
        }
    )
    item.pop("candidate_routes")
    item.pop("decision_tradeoffs")
    return item


class ValidateKnowledgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "knowledge" / "strategies").mkdir(parents=True)
        (self.root / "sources").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_valid_strategy_passes(self) -> None:
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(
            self.root / "knowledge" / "strategies" / "item.json",
            valid_strategy(),
        )
        report = VALIDATOR.validate_repository(self.root)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.item_count, 1)
        self.assertEqual(report.source_count, 1)

    def test_confidence_not_matching_evidence_composition_fails(self) -> None:
        """confidence 手工填成与推导结果不符的值，应被拒绝。"""
        item = valid_strategy()
        item["confidence"] = "high"  # 该来源构成只支撑 medium
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "strategies" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(
            any("evidence composition grades it" in error for error in report.errors),
            f"应报出 confidence 与证据构成不符，实际：{report.errors}",
        )

    def test_evidence_strength_must_match_evidence_composition(self) -> None:
        """evidence_strength 也必须与来源构成一致，不可手工填。"""
        item = valid_strategy()
        item["evidence_strength"] = "low"  # 该来源构成实际是 medium
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "strategies" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(
            any("evidence_strength is" in error for error in report.errors),
            f"应报出 evidence_strength 与证据构成不符，实际：{report.errors}",
        )

    def test_high_confidence_requires_review_gate(self) -> None:
        """项目策略（project.json）：未过 replay_verified 闸门不得标 high confidence。

        这条规则由 grade_confidence.py 的闸门实现，因此表现为「confidence 与
        推导结果不符」——推导在 draft 状态下最高只给 medium。
        """
        item = valid_strategy()
        item["validation_status"] = "draft"
        item["confidence"] = "high"
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "strategies" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(
            any("evidence composition grades it" in error for error in report.errors),
            f"draft 状态标 high 应被拒绝，实际：{report.errors}",
        )

    def test_confidence_and_evidence_strength_passes_when_consistent(self) -> None:
        """两个字段都与推导一致时不报错。"""
        item = valid_strategy()
        write_json(self.root / "sources" / "source.json", valid_source())

        from grade_confidence import grade

        conf, strength, _score, _notes = grade(
            item, {"src_official_example": valid_source()}
        )
        item["confidence"] = conf
        item["evidence_strength"] = strength
        write_json(self.root / "knowledge" / "strategies" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(
            any("evidence composition grades it" in error for error in report.errors),
            f"与推导一致的两个字段不应报错：{report.errors}",
        )
        self.assertFalse(
            any("evidence_strength is" in error for error in report.errors),
            f"与推导一致的两个字段不应报错：{report.errors}",
        )

    def test_unknown_source_reference_fails(self) -> None:
        item = valid_strategy()
        item["source_refs"] = ["src_missing"]
        write_json(self.root / "knowledge" / "strategies" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(any("unknown source" in error for error in report.errors))

    def test_failure_recovery_requires_escalation_limit(self) -> None:
        item = valid_strategy()
        item.update(
            {
                "id": "failure_resource_not_found",
                "knowledge_type": "failure_recovery",
                "title": "Resource not found",
                "summary": "Diagnose and recover when target resources do not increase.",
                "stage": "iron_age",
                "source_refs": ["src_official_example"],
            }
        )
        item.pop("candidate_routes")
        item.pop("decision_tradeoffs")
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "failures" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(
            any("failure_recovery requires field" in error for error in report.errors)
        )

    def test_tool_guide_accepts_string_tool_name(self) -> None:
        item = valid_strategy()
        item.update(
            {
                "id": "tool_example_block_break",
                "knowledge_type": "tool_guide",
                "title": "Block break tool contract",
                "summary": "Documents a tool contract with a string tool name and typed parameters.",
                "tool_name": "mine / dig",
                "parameters": [
                    {"name": "target", "type": "block_pos", "required": True},
                ],
                "expected_effects": ["Target block becomes air"],
                "failure_modes": ["dig_aborted"],
                "verification": ["Block type at target is air"],
            }
        )
        item.pop("candidate_routes")
        item.pop("decision_tradeoffs")
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "tool_guides" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertEqual(report.errors, [])

    def test_tool_guide_rejects_empty_tool_name(self) -> None:
        item = valid_strategy()
        item.update(
            {
                "id": "tool_example_block_break",
                "knowledge_type": "tool_guide",
                "title": "Block break tool contract",
                "summary": "Documents a tool contract with a string tool name and typed parameters.",
                "tool_name": "   ",
                "parameters": [{"name": "target", "type": "block_pos"}],
                "expected_effects": ["Target block becomes air"],
                "failure_modes": ["dig_aborted"],
                "verification": ["Block type at target is air"],
            }
        )
        item.pop("candidate_routes")
        item.pop("decision_tradeoffs")
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "tool_guides" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(any("tool_name must be a non-empty string" in e for e in report.errors))

    def test_failure_recovery_requires_escalation_unit(self) -> None:
        item = valid_strategy()
        item.update(
            {
                "id": "failure_resource_not_found",
                "knowledge_type": "failure_recovery",
                "title": "Resource not found",
                "summary": "Diagnose and recover when target resources do not increase.",
                "symptoms": ["count does not grow"],
                "possible_causes": ["wrong layer"],
                "diagnostics": ["check layer"],
                "recovery_steps": ["L1 retry with new target"],
                "escalate_after": 2,
                "forbidden_actions": ["blind retry"],
            }
        )
        item.pop("candidate_routes")
        item.pop("decision_tradeoffs")
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "failures" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(
            any("escalation_unit" in error for error in report.errors)
        )

    def test_source_verified_requires_verified_scope(self) -> None:
        item = valid_strategy()
        item.pop("verified_scope")
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "strategies" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(any("verified_scope" in error for error in report.errors))

    def test_project_policy_only_scope_cannot_be_source_verified(self) -> None:
        item = valid_strategy()
        item["verified_scope"] = ["project_policy"]
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "strategies" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(
            any("externally checkable scope" in error for error in report.errors)
        )

    def test_tool_guide_rejects_unknown_parameter_type(self) -> None:
        item = valid_strategy()
        item.update(
            {
                "id": "tool_example_block_break",
                "knowledge_type": "tool_guide",
                "title": "Block break tool contract",
                "summary": "Documents a tool contract with a string tool name and typed parameters.",
                "tool_name": "mine / dig",
                "parameters": [{"name": "target", "type": "coordinate_tuple_ish"}],
                "expected_effects": ["Target block becomes air"],
                "failure_modes": ["dig_aborted"],
                "verification": ["Block type at target is air"],
            }
        )
        item.pop("candidate_routes")
        item.pop("decision_tradeoffs")
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "tool_guides" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(any("unsupported type" in error for error in report.errors))

    def test_playbook_accepts_string_scenario(self) -> None:
        item = valid_strategy()
        item.update(
            {
                "id": "playbook_first_night",
                "knowledge_type": "playbook",
                "title": "First night playbook",
                "summary": "Cover sealing a shelter before nightfall and surviving until dawn.",
                "scenario": "首次夜晚：入夜前完成封闭",
                "checklist": ["封闭材料是否够用"],
                "continue_condition": ["封闭工作持续推进"],
                "exit_condition": ["空间已封闭"],
                "failure_entry_points": ["failure_example_resource_not_found"],
            }
        )
        item.pop("candidate_routes")
        item.pop("decision_tradeoffs")
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "failures" / "failure.json", valid_failure())
        write_json(self.root / "knowledge" / "playbooks" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertEqual(report.errors, [])

    def test_playbook_rejects_list_scenario(self) -> None:
        item = valid_strategy()
        item.update(
            {
                "id": "playbook_first_night",
                "knowledge_type": "playbook",
                "title": "First night playbook",
                "summary": "Cover sealing a shelter before nightfall and surviving until dawn.",
                "scenario": ["首次夜晚"],
                "checklist": ["封闭材料是否够用"],
                "continue_condition": ["封闭工作持续推进"],
                "exit_condition": ["空间已封闭"],
                "failure_entry_points": ["failure_night_exposure"],
            }
        )
        item.pop("candidate_routes")
        item.pop("decision_tradeoffs")
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "playbooks" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(any("scenario must be a non-empty string" in e for e in report.errors))

    def test_playbook_failure_entry_point_must_exist(self) -> None:
        failure_item = valid_failure()

        playbook_item = valid_strategy()
        playbook_item.update(
            {
                "id": "playbook_first_night",
                "knowledge_type": "playbook",
                "title": "First night playbook",
                "summary": "Cover sealing a shelter before nightfall and surviving until dawn.",
                "scenario": "首次夜晚：入夜前完成封闭",
                "checklist": ["封闭材料是否够用"],
                "continue_condition": ["封闭工作持续推进"],
                "exit_condition": ["空间已封闭"],
                "failure_entry_points": ["failure_example_does_not_exist"],
            }
        )
        playbook_item.pop("candidate_routes")
        playbook_item.pop("decision_tradeoffs")

        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "failures" / "failure.json", failure_item)
        write_json(self.root / "knowledge" / "playbooks" / "item.json", playbook_item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(
            any("failure_entry_points references an unknown failure id" in e for e in report.errors)
        )

    def test_playbook_failure_entry_point_must_point_at_a_failure(self) -> None:
        failure_item = valid_failure()

        playbook_item = valid_strategy()
        playbook_item.update(
            {
                "id": "playbook_first_night",
                "knowledge_type": "playbook",
                "title": "First night playbook",
                "summary": "Cover sealing a shelter before nightfall and surviving until dawn.",
                "scenario": "首次夜晚：入夜前完成封闭",
                "checklist": ["封闭材料是否够用"],
                "continue_condition": ["封闭工作持续推进"],
                "exit_condition": ["空间已封闭"],
                "failure_entry_points": ["strategy_iron_route_selection"],
            }
        )
        playbook_item.pop("candidate_routes")
        playbook_item.pop("decision_tradeoffs")

        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "strategies" / "item.json", valid_strategy())
        write_json(self.root / "knowledge" / "failures" / "failure.json", failure_item)
        write_json(self.root / "knowledge" / "playbooks" / "item.json", playbook_item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(any("must reference failure_recovery items" in e for e in report.errors))

    def test_dangling_link_tag_fails(self) -> None:
        item = valid_strategy()
        item["tags"] = ["link_playbook:pb_does_not_exist"]
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "strategies" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(any("unknown target" in error for error in report.errors))

    def test_link_tag_resolves_through_registry(self) -> None:
        item = valid_strategy()
        item["tags"] = ["link_playbook:pb_reserved_later"]
        (self.root / "knowledge" / "registry.json").write_text(
            json.dumps(
                {
                    "reserved_playbooks": ["pb_reserved_later"],
                    "reserved_strategies": [],
                }
            ),
            encoding="utf-8",
        )
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "strategies" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertEqual(report.errors, [])

    def test_ai_heuristic_accepts_string_decision_rule_and_guidance(self) -> None:
        item = valid_strategy()
        item.update(
            {
                "id": "ai_uncertain_prefer_conservative",
                "knowledge_type": "ai_heuristic",
                "title": "Prefer conservative plan when uncertain",
                "summary": "When state is incomplete choose a reversible low-loss plan.",
                "decision_rule": "Prefer conservative plans when uncertain.",
                "alternative_comparison": ["Risky vs conservative"],
                "anti_patterns": ["Gambling on irreversible actions"],
                "model_guidance": "Pick a reversible plan and mark uncertainty.",
                "validation_status": "draft",
            }
        )
        item.pop("candidate_routes")
        item.pop("decision_tradeoffs")
        item.pop("verified_scope")
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "ai_heuristics" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertEqual(report.errors, [])

    def test_ai_heuristic_rejects_empty_decision_rule(self) -> None:
        item = valid_strategy()
        item.update(
            {
                "id": "ai_uncertain_prefer_conservative",
                "knowledge_type": "ai_heuristic",
                "title": "Prefer conservative plan when uncertain",
                "summary": "When state is incomplete choose a reversible low-loss plan.",
                "decision_rule": "   ",
                "alternative_comparison": ["Risky vs conservative"],
                "anti_patterns": ["Gambling on irreversible actions"],
                "model_guidance": "Pick a reversible plan and mark uncertainty.",
                "validation_status": "draft",
            }
        )
        item.pop("candidate_routes")
        item.pop("decision_tradeoffs")
        item.pop("verified_scope")
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "ai_heuristics" / "item.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(
            any("decision_rule must be a non-empty string" in e for e in report.errors)
        )

    def test_wrong_directory_fails(self) -> None:
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "strategies" / "item.json", valid_strategy())
        item = valid_strategy()
        item["knowledge_type"] = "playbook"
        item["id"] = "playbook_night"
        write_json(self.root / "knowledge" / "strategies" / "wrong_dir.json", item)
        report = VALIDATOR.validate_repository(self.root)
        self.assertFalse(report.passed)
        self.assertTrue(any("belongs in" in error for error in report.errors))


if __name__ == "__main__":
    unittest.main()
