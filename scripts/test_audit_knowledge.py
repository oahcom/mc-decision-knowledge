"""Tests for the semantic audit script.

The audit is a batch gate, so the important behaviours are:
  1. a clean repository produces no findings and exit code 0;
  2. a skipped strict schema check (jsonschema missing) is a finding, not a pass.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("audit_knowledge.py")
SPEC = importlib.util.spec_from_file_location("audit_knowledge", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(AUDIT)


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
        "evidence_notes": "Used to test the audit.",
        "related_game_versions": ["26.3"],
        "access_method": "public_page",
        "compliance": {
            "publicly_accessible": True,
            "robots_or_terms_respected": True,
            "personal_data_excluded": True,
            "no_auth_bypass": True,
        },
    }


def community_wiki_source() -> dict:
    """社区维基来源：它是一手资料，但不是官方文档。"""
    s = valid_source()
    s["source_id"] = "src_community_wiki_example"
    s["source_type"] = "community_wiki"
    s["platform"] = "Minecraft Wiki"
    s["title"] = "Minecraft Wiki example"
    return s


def github_repository_source() -> dict:
    s = valid_source()
    s["source_id"] = "src_github_repo_example"
    s["source_type"] = "github_repository"
    s["platform"] = "GitHub"
    s["title"] = "Example repository"
    return s


def valid_strategy() -> dict:
    return {
        "id": "strategy_iron_route_selection",
        "knowledge_type": "strategy",
        "title": "Iron route selection",
        "summary": "Select an iron acquisition route based on verified state and risk.",
        "game_edition": "java",
        "game_versions": ["26.3"],
        "stage": "iron_age",
        "trigger": {
            "conditions": ["Iron equipment is the current goal"],
            "state_features": ["bot.inventory", "bot.health", "bot.food"],
        },
        "actions": ["Compare candidate routes", "Select the lowest-risk route"],
        "preconditions": ["Basic tools are available"],
        "success_condition": "Iron ingot count reaches the planned amount",
        "abort_condition": ["Supplies are insufficient"],
        "risk_notes": ["Do not treat one route as universal"],
        "source_refs": ["src_official_example"],
        "evidence_type": "official_document",
        "confidence": "medium",
        "validation_status": "source_verified",
        "verified_scope": ["gameplay_mechanics"],
        "created_at": "2026-11-01T00:00:00+08:00",
        "updated_at": "2026-11-01T00:00:00+08:00",
        "candidate_routes": ["Cave exploration", "Branch mining"],
        "decision_tradeoffs": ["Cave exploration is faster but riskier"],
        "tags": ["test"],
    }


class AuditKnowledgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        write_json(self.root / "sources" / "source.json", valid_source())
        write_json(self.root / "knowledge" / "strategies" / "item.json", valid_strategy())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_clean_repository_has_no_findings(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root)],
            capture_output=True,
            text=True,
        )
        self.assertIn("Findings: 0", result.stdout)
        self.assertEqual(result.returncode, 0)

    def test_missing_jsonschema_is_reported_as_a_finding(self) -> None:
        items = AUDIT.load_items(self.root)
        audit = AUDIT.Audit()
        sentinel = object()
        original = sys.modules.get("jsonschema", sentinel)
        sys.modules["jsonschema"] = None  # makes `import jsonschema` raise ImportError
        try:
            AUDIT.audit_schema(self.root, items, audit)
        finally:
            if original is sentinel:
                sys.modules.pop("jsonschema", None)
            else:
                sys.modules["jsonschema"] = original
        self.assertEqual(len(audit.findings), 1)
        self.assertIn("SKIPPED", audit.findings[0])

    def test_missing_jsonschema_makes_the_gate_fail(self) -> None:
        """A skipped strict check must never look like a clean pass."""
        result = subprocess.run(
            [sys.executable, "-c", (
                "import sys, runpy;"
                "sys.modules['jsonschema'] = None;"
                f"sys.argv = ['audit', '--root', {str(self.root)!r}];"
                "runpy.run_path(%r, run_name='__main__')" % str(SCRIPT)
            )],
            capture_output=True,
            text=True,
        )
        self.assertIn("SKIPPED", result.stdout)
        self.assertNotEqual(result.returncode, 0)


    def test_official_document_requires_an_official_source(self) -> None:
        """仅引用社区维基却声称 official_document —— 必须被判为发现。

        回归用例：此前 github_repository / source_code 被算作 official-ish，
        这类错标会静默通过。
        """
        write_json(self.root / "sources" / "source.json", community_wiki_source())
        item = valid_strategy()
        item["source_refs"] = ["src_community_wiki_example"]
        write_json(self.root / "knowledge" / "strategies" / "item.json", item)

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root)],
            capture_output=True,
            text=True,
        )
        self.assertNotIn("Findings: 0", result.stdout)
        self.assertIn("official_document", result.stdout)
        self.assertNotEqual(result.returncode, 0)

    def test_github_repository_does_not_satisfy_official_document(self) -> None:
        """仓库主页是一手资料，但不是官方文档，不能为 official_document 背书。"""
        write_json(self.root / "sources" / "source.json", github_repository_source())
        item = valid_strategy()
        item["source_refs"] = ["src_github_repo_example"]
        write_json(self.root / "knowledge" / "strategies" / "item.json", item)

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root)],
            capture_output=True,
            text=True,
        )
        self.assertNotIn("Findings: 0", result.stdout)
        self.assertIn("official_document", result.stdout)
        self.assertNotEqual(result.returncode, 0)

    def test_official_document_with_official_source_still_passes(self) -> None:
        """正向对照：真的引用了官方文档，就不该被这条规则误伤。"""
        items = AUDIT.load_items(self.root)
        sources = AUDIT.load_sources(self.root)
        audit = AUDIT.Audit()
        AUDIT.audit_evidence_typing(items, sources, audit)
        self.assertEqual(audit.findings, [])



if __name__ == "__main__":
    unittest.main()
