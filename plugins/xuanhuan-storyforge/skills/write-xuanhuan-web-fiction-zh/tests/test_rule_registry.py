import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = SKILL_ROOT / "references" / "rule-registry.json"
VALIDATOR_PATH = SKILL_ROOT / "scripts" / "validate_rule_registry.py"

SPEC = importlib.util.spec_from_file_location("validate_rule_registry", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import infrastructure guard
    raise RuntimeError(f"cannot import validator: {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class RuleRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def assert_invalid(self, mutation, expected_message):
        payload = copy.deepcopy(self.registry)
        mutation(payload)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rule-registry.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(VALIDATOR.RegistryValidationError, expected_message):
                VALIDATOR.validate_registry(path, skill_root=SKILL_ROOT)

    def test_current_registry_is_complete_and_source_backed(self):
        report = VALIDATOR.validate_registry(REGISTRY_PATH, skill_root=SKILL_ROOT)
        self.assertEqual(report["rule_count"], 105)
        self.assertEqual(
            report["families"],
            {
                "chapter-rhythm": 60,
                "continuity-lock": 10,
                "core-impact": 19,
                "opening-retention": 9,
                "opening-three": 7,
            },
        )
        self.assertEqual(report["semantic_validation"], "not_performed")

    def test_aggregate_records_cannot_claim_semantic_pass(self):
        aggregates = [rule for rule in self.registry["rules"] if rule["kind"] == "aggregate"]
        self.assertEqual({rule["id"] for rule in aggregates}, {"CORE-AGGREGATE-18", "CORE-AGGREGATE-19"})
        for rule in aggregates:
            self.assertEqual(rule["checkability"]["semantic"], "manual")
            self.assertEqual(rule["checkability"]["purity"], "not_applicable")

    def test_duplicate_id_fails_closed(self):
        self.assert_invalid(
            lambda data: data["rules"][1].update({"id": data["rules"][0]["id"]}),
            "duplicate rule id",
        )

    def test_duplicate_numbering_slot_fails_closed(self):
        def mutate(data):
            data["rules"][1]["family"] = data["rules"][0]["family"]
            data["rules"][1]["ordinal"] = data["rules"][0]["ordinal"]

        self.assert_invalid(mutate, "duplicate numbering slot")

    def test_missing_source_fails_closed(self):
        self.assert_invalid(
            lambda data: data["rules"][0].update({"source": "references/does-not-exist.md"}),
            "does not exist",
        )

    def test_absolute_source_path_fails_closed(self):
        self.assert_invalid(
            lambda data: data["rules"][0].update({"source": "/tmp/rule.md"}),
            "safe relative path",
        )

    def test_missing_source_heading_fails_closed(self):
        self.assert_invalid(
            lambda data: data["rules"][0].update({"source_heading": "不存在的规则标题"}),
            "must occur exactly once",
        )

    def test_empty_routes_fail_closed(self):
        self.assert_invalid(
            lambda data: data["rules"][0].update({"routes": []}),
            "must be a non-empty list",
        )

    def test_automatic_semantic_claim_fails_closed(self):
        def mutate(data):
            data["rules"][0]["checkability"]["semantic"] = "deterministic"

        self.assert_invalid(mutate, "semantic must be manual")

    def test_unknown_relation_target_fails_closed(self):
        self.assert_invalid(
            lambda data: data["rules"][0].update(
                {"relations": [{"kind": "requires", "target": "MISSING-RULE"}]}
            ),
            "targets unknown rule",
        )


if __name__ == "__main__":
    unittest.main()
