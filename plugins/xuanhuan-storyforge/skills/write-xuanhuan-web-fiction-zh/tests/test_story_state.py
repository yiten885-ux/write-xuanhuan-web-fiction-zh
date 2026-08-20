from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_story_state.py"
TEMPLATE = ROOT / "assets" / "story-state-template.json"
PROSE_RAW = "# 第一章 测试\n\n正文基线\n".encode("utf-8")
TEXT_SHA256 = hashlib.sha256(PROSE_RAW).hexdigest()
EXCERPT_SHA256 = hashlib.sha256("正文基线".encode("utf-8")).hexdigest()


def source_anchor() -> dict:
    return {
        "chapter_id": "chapter-1",
        "scene_id": "scene-1",
        "paragraph_index": 1,
        "excerpt_sha256": EXCERPT_SHA256,
    }


def keyframe(version: int = 0) -> dict:
    snapshot = {"chapter_id": "chapter-1", "state_version": version}
    canonical = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "keyframe_id": "keyframe-1",
        "chapter_id": "chapter-1",
        "text_sha256": TEXT_SHA256,
        "state_version": version,
        "status": "active",
        "previous_keyframe_id": None,
        "invalidated_by_transaction_id": None,
        "state_snapshot": snapshot,
        "snapshot_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def valid_state() -> dict:
    return {
        "schema_version": "1.0",
        "state_version": 0,
        "previous_state_sha256": "",
        "text_sha256": TEXT_SHA256,
        "canon_revision": "draft-0",
        "facts": [
            {
                "fact_id": "fact-1",
                "status": "canon",
                "source_anchor": source_anchor(),
            }
        ],
        "characters": [
            {
                "character_id": "character-1",
                "location_id": "location-2",
                "knowledge_ids": ["knowledge-1"],
                "item_ids": ["item-1"],
                "state_machine": {
                    "current_state": "alert",
                    "transitions": [
                        {
                            "transition_id": "character-transition-1",
                            "from_state": "calm",
                            "to_state": "alert",
                            "trigger_event_id": "event-1",
                        }
                    ],
                },
            },
            {
                "character_id": "character-2",
                "location_id": "location-1",
                "knowledge_ids": [],
                "item_ids": [],
                "state_machine": {"current_state": "waiting", "transitions": []},
            },
        ],
        "items": [
            {
                "item_id": "item-1",
                "ownership_model": "unique",
                "holders": [
                    {
                        "holder_type": "character",
                        "holder_id": "character-1",
                        "active": True,
                        "since_event_id": "event-1",
                    }
                ],
            }
        ],
        "locations": [
            {"location_id": "location-1", "parent_location_id": None},
            {"location_id": "location-2", "parent_location_id": None},
        ],
        "knowledge": [
            {
                "knowledge_id": "knowledge-1",
                "holder_id": "character-1",
                "fact_id": "fact-1",
                "state": "knows",
                "source_event_id": "event-1",
                "acquired_at": "day-1 noon",
            }
        ],
        "timeline": [
            {
                "event_id": "event-1",
                "status": "committed",
                "kind": "movement",
                "sequence": 1,
                "source_anchor": source_anchor(),
                "story_time_start": "day-1 morning",
                "story_time_end": "day-1 noon",
                "location_id": "location-2",
                "participant_ids": ["character-1"],
                "depends_on_fact_ids": ["fact-1"],
                "depends_on_conflict_ids": [],
                "movement": {
                    "character_id": "character-1",
                    "from_location_id": "location-1",
                    "to_location_id": "location-2",
                    "duration_minutes": 30,
                },
            }
        ],
        "foreshadowing": [
            {
                "foreshadow_id": "foreshadow-1",
                "status": "seeded",
                "seed_event_id": "event-1",
                "payoff_event_id": None,
            }
        ],
        "plot_states": [
            {
                "plot_state_id": "plot-1",
                "current_state": "active",
                "transitions": [
                    {
                        "transition_id": "plot-transition-1",
                        "from_state": "seeded",
                        "to_state": "active",
                        "trigger_event_id": "event-1",
                    }
                ],
            }
        ],
        "chapter_transactions": [],
        "keyframes": [keyframe()],
        "unresolved_conflicts": [],
    }


class StoryStateValidatorTests(unittest.TestCase):
    def run_validator(
        self,
        state: dict,
        *,
        previous_raw: bytes | None = None,
        prose_raw: bytes | None = PROSE_RAW,
        json_out: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], dict, dict | None]:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            state_path = directory / "current.state.json"
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            command = [sys.executable, str(VALIDATOR), str(state_path)]
            if prose_raw is not None:
                prose_path = directory / "chapter.md"
                prose_path.write_bytes(prose_raw)
                command.extend(["--prose", str(prose_path)])
            if previous_raw is not None:
                previous_path = directory / "previous.state.json"
                previous_path.write_bytes(previous_raw)
                command.extend(["--previous", str(previous_path)])
            report_path = directory / "report.qa.json"
            if json_out:
                command.extend(["--json-out", str(report_path)])
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            report = json.loads(result.stdout)
            sidecar = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
            return result, report, sidecar

    def assert_error(self, report: dict, code: str) -> None:
        self.assertIn(code, {error["code"] for error in report["errors"]})

    def test_template_is_valid_json_and_contains_no_project_data(self) -> None:
        raw = TEMPLATE.read_text(encoding="utf-8")
        payload = json.loads(raw)
        self.assertEqual(set(payload), set(valid_state()))
        self.assertNotIn("/Users/", raw)
        self.assertNotIn("outputs/", raw)
        result, report, _ = self.run_validator(payload, prose_raw=None)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report["passed"])

    def test_valid_state_passes_and_writes_json_report(self) -> None:
        result, report, sidecar = self.run_validator(valid_state(), json_out=True)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report["passed"])
        self.assertIsNotNone(sidecar)
        self.assertEqual(report, sidecar)
        self.assertNotIn("/Users/", json.dumps(report, ensure_ascii=False))

    def test_raw_sha256_and_version_chain_pass_then_mismatch_fails(self) -> None:
        previous = valid_state()
        previous_raw = (json.dumps(previous, ensure_ascii=False, indent=4) + "\n").encode("utf-8")
        current = copy.deepcopy(previous)
        current["state_version"] = 1
        current["previous_state_sha256"] = hashlib.sha256(previous_raw).hexdigest()
        current["keyframes"] = [keyframe(1)]
        result, report, _ = self.run_validator(current, previous_raw=previous_raw)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report["passed"])

        current["previous_state_sha256"] = "0" * 64
        result, report, _ = self.run_validator(current, previous_raw=previous_raw)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "previous_state_sha256_mismatch")

    def test_unique_item_cannot_have_two_active_holders(self) -> None:
        state = valid_state()
        state["items"][0]["holders"].append(
            {
                "holder_type": "character",
                "holder_id": "character-2",
                "active": True,
                "since_event_id": "event-1",
            }
        )
        result, report, _ = self.run_validator(state)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "item_multiple_active_holders")

    def test_knowledge_without_source_event_fails(self) -> None:
        state = valid_state()
        del state["knowledge"][0]["source_event_id"]
        result, report, _ = self.run_validator(state)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "knowledge_source_required")

    def test_character_or_plot_transition_without_trigger_event_fails(self) -> None:
        state = valid_state()
        del state["characters"][0]["state_machine"]["transitions"][0]["trigger_event_id"]
        result, report, _ = self.run_validator(state)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "transition_trigger_required")

    def test_negative_movement_duration_fails(self) -> None:
        state = valid_state()
        state["timeline"][0]["movement"]["duration_minutes"] = -1
        result, report, _ = self.run_validator(state)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "negative_movement_duration")

    def test_committed_event_cannot_consume_unresolved_conflict(self) -> None:
        state = valid_state()
        state["unresolved_conflicts"].append(
            {
                "conflict_id": "conflict-1",
                "status": "unresolved",
                "severity": "warning",
                "fact_ids": ["fact-1"],
            }
        )
        state["timeline"][0]["depends_on_conflict_ids"] = ["conflict-1"]
        result, report, _ = self.run_validator(state)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "committed_event_depends_on_unresolved_conflict")

    def test_candidate_and_rejected_fact_states_are_valid_but_planned_is_not(self) -> None:
        for status in ("candidate", "rejected"):
            state = valid_state()
            state["facts"][0]["status"] = status
            result, report, _ = self.run_validator(state)
            self.assertEqual(result.returncode, 0, report)
        state = valid_state()
        state["facts"][0]["status"] = "planned"
        result, report, _ = self.run_validator(state)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "invalid_fact_status")

    def test_non_initial_state_requires_previous_for_hash_verification(self) -> None:
        state = valid_state()
        state["state_version"] = 1
        state["previous_state_sha256"] = "c" * 64
        state["keyframes"] = [keyframe(1)]
        result, report, _ = self.run_validator(state)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "previous_state_required")

    def test_unresolved_hard_conflict_fails(self) -> None:
        state = valid_state()
        state["unresolved_conflicts"].append(
            {
                "conflict_id": "conflict-hard",
                "status": "unresolved",
                "severity": "hard",
                "fact_ids": ["fact-1"],
            }
        )
        result, report, _ = self.run_validator(state)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "unresolved_hard_conflict")

    def test_shared_item_may_have_multiple_active_holders(self) -> None:
        state = valid_state()
        state["items"][0]["ownership_model"] = "shared"
        state["items"][0]["holders"].append(
            {
                "holder_type": "character",
                "holder_id": "character-2",
                "active": True,
                "since_event_id": "event-1",
            }
        )
        result, report, _ = self.run_validator(state)
        self.assertEqual(result.returncode, 0, report)

    def test_source_anchor_and_current_keyframe_binding_are_required(self) -> None:
        state = valid_state()
        del state["facts"][0]["source_anchor"]
        state["keyframes"][0]["text_sha256"] = "d" * 64
        result, report, _ = self.run_validator(state)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "source_anchor_required")
        self.assert_error(report, "current_keyframe_binding_invalid")

    def test_committed_content_requires_keyframe_and_final_prose(self) -> None:
        state = valid_state()
        state["keyframes"] = []
        result, report, _ = self.run_validator(state)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "keyframe_required")

        result, report, _ = self.run_validator(valid_state(), prose_raw=None)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "prose_required")

    def test_prose_and_source_anchor_hashes_are_computed_from_actual_file(self) -> None:
        result, report, _ = self.run_validator(valid_state(), prose_raw=b"different prose\n")
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "prose_sha256_mismatch")
        self.assert_error(report, "source_excerpt_sha256_mismatch")

    def test_transaction_must_bind_the_same_keyframe_text_and_version(self) -> None:
        state = valid_state()
        state["chapter_transactions"] = [
            {
                "transaction_id": "transaction-1",
                "chapter_id": "chapter-1",
                "status": "draft",
                "input_state_version": 0,
                "output_state_version": 0,
                "text_sha256": "e" * 64,
                "keyframe_id": "keyframe-1",
                "delta": {},
            }
        ]
        result, report, _ = self.run_validator(state)
        self.assertNotEqual(result.returncode, 0)
        self.assert_error(report, "transaction_keyframe_text_sha256_mismatch")

    def test_report_requires_qa_json_suffix_and_does_not_write_other_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            state_path = directory / "current.state.json"
            report_path = directory / "reader.md"
            state_path.write_text(
                json.dumps(valid_state(), ensure_ascii=False), encoding="utf-8"
            )
            prose_path = directory / "chapter.md"
            prose_path.write_bytes(PROSE_RAW)
            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    str(state_path),
                    "--prose",
                    str(prose_path),
                    "--json-out",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            report = json.loads(result.stdout)
            self.assertNotEqual(result.returncode, 0)
            self.assert_error(report, "invalid_report_suffix")
            self.assertFalse(report_path.exists())


if __name__ == "__main__":
    unittest.main()
