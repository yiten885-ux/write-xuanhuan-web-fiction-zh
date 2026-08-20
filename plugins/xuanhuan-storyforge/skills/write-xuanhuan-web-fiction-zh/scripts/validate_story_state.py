#!/usr/bin/env python3
"""Deterministically validate the internal JSON state for a fiction project.

This validator checks structural and referential invariants only. It cannot
prove literary continuity, character motivation, point-of-view fidelity, or
the semantic quality of a plot. Reader-facing prose must remain in a separate
file; this state file and the emitted report are internal sidecars.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


REPORT_SCHEMA_VERSION = "1.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_TOP_LEVEL: dict[str, type] = {
    "schema_version": str,
    "state_version": int,
    "previous_state_sha256": str,
    "text_sha256": str,
    "canon_revision": str,
    "facts": list,
    "characters": list,
    "items": list,
    "locations": list,
    "knowledge": list,
    "timeline": list,
    "foreshadowing": list,
    "plot_states": list,
    "chapter_transactions": list,
    "keyframes": list,
    "unresolved_conflicts": list,
}

COLLECTION_ID_FIELDS = {
    "facts": "fact_id",
    "characters": "character_id",
    "items": "item_id",
    "locations": "location_id",
    "knowledge": "knowledge_id",
    "timeline": "event_id",
    "foreshadowing": "foreshadow_id",
    "plot_states": "plot_state_id",
    "chapter_transactions": "transaction_id",
    "keyframes": "keyframe_id",
    "unresolved_conflicts": "conflict_id",
}

FACT_STATUSES = {"candidate", "draft", "canon", "superseded", "rejected"}
KNOWLEDGE_STATES = {"unknown", "suspects", "believes", "knows", "misbelieves"}
EVENT_STATUSES = {"planned", "draft", "committed"}
FORESHADOW_STATUSES = {"seeded", "echoed", "paid_off", "abandoned"}
TRANSACTION_STATUSES = {"draft", "committed", "rejected"}
HOLDER_TYPES = {"character", "location", "none"}
OWNERSHIP_MODELS = {"unique", "stackable", "shared", "replicated"}
KEYFRAME_STATUSES = {"active", "invalidated"}
CONFLICT_SEVERITIES = {"hard", "warning"}


class StateValidator:
    def __init__(
        self,
        document: Any,
        prefix: str = "state",
        prose_paragraph_sha256s: list[str] | None = None,
    ) -> None:
        self.document = document
        self.prefix = prefix
        self.prose_paragraph_sha256s = prose_paragraph_sha256s
        self.errors: list[dict[str, str]] = []
        self.indexes: dict[str, dict[str, dict[str, Any]]] = {}
        self.transition_ids: set[str] = set()

    def error(self, code: str, path: str, message: str) -> None:
        self.errors.append({"code": code, "path": path, "message": message})

    def path(self, suffix: str = "") -> str:
        return self.prefix + (f".{suffix}" if suffix else "")

    def require_string(
        self, value: dict[str, Any], key: str, path: str, *, allow_empty: bool = False
    ) -> str | None:
        if key not in value:
            self.error("missing_required_field", f"{path}.{key}", "required field is missing")
            return None
        result = value[key]
        if not isinstance(result, str):
            self.error("invalid_type", f"{path}.{key}", "must be a string")
            return None
        if not allow_empty and not result.strip():
            self.error("empty_identifier", f"{path}.{key}", "must not be empty")
            return None
        return result

    def require_list(
        self, value: dict[str, Any], key: str, path: str
    ) -> list[Any] | None:
        if key not in value:
            self.error("missing_required_field", f"{path}.{key}", "required field is missing")
            return None
        result = value[key]
        if not isinstance(result, list):
            self.error("invalid_type", f"{path}.{key}", "must be an array")
            return None
        return result

    def require_sha256(
        self,
        value: dict[str, Any],
        key: str,
        path: str,
        *,
        allow_empty: bool = False,
    ) -> str | None:
        result = self.require_string(value, key, path, allow_empty=allow_empty)
        if result is None or (allow_empty and not result):
            return result
        if not SHA256_RE.fullmatch(result):
            self.error(
                "invalid_sha256",
                f"{path}.{key}",
                "must be a lowercase 64-character SHA256 digest",
            )
        return result

    def validate_source_anchor(self, anchor: Any, path: str) -> None:
        if not isinstance(anchor, dict):
            self.error(
                "source_anchor_required",
                path,
                "must contain a chapter/scene/paragraph anchor and excerpt digest",
            )
            return
        self.require_string(anchor, "chapter_id", path)
        self.require_string(anchor, "scene_id", path)
        paragraph_index = anchor.get("paragraph_index")
        if (
            not isinstance(paragraph_index, int)
            or isinstance(paragraph_index, bool)
            or paragraph_index < 1
        ):
            self.error(
                "invalid_paragraph_index",
                f"{path}.paragraph_index",
                "must be a positive 1-based integer",
            )
        excerpt_sha256 = self.require_sha256(anchor, "excerpt_sha256", path)
        if (
            self.prose_paragraph_sha256s is not None
            and isinstance(paragraph_index, int)
            and not isinstance(paragraph_index, bool)
            and paragraph_index >= 1
            and isinstance(excerpt_sha256, str)
            and SHA256_RE.fullmatch(excerpt_sha256)
        ):
            if paragraph_index > len(self.prose_paragraph_sha256s):
                self.error(
                    "source_paragraph_missing",
                    f"{path}.paragraph_index",
                    "paragraph index is outside the supplied final prose",
                )
            elif self.prose_paragraph_sha256s[paragraph_index - 1] != excerpt_sha256:
                self.error(
                    "source_excerpt_sha256_mismatch",
                    f"{path}.excerpt_sha256",
                    "digest does not match the referenced final-prose paragraph",
                )

    def validate_top_level(self) -> bool:
        if not isinstance(self.document, dict):
            self.error("invalid_root_type", self.prefix, "root value must be an object")
            return False

        for key, expected in REQUIRED_TOP_LEVEL.items():
            path = self.path(key)
            if key not in self.document:
                self.error("missing_top_level_key", path, "required top-level key is missing")
                continue
            value = self.document[key]
            if expected is int:
                valid = isinstance(value, int) and not isinstance(value, bool)
            else:
                valid = isinstance(value, expected)
            if not valid:
                self.error("invalid_top_level_type", path, f"must be {expected.__name__}")

        version = self.document.get("state_version")
        if isinstance(version, int) and not isinstance(version, bool) and version < 0:
            self.error("negative_state_version", self.path("state_version"), "must be non-negative")

        schema_version = self.document.get("schema_version")
        if isinstance(schema_version, str) and not schema_version.strip():
            self.error("empty_schema_version", self.path("schema_version"), "must not be empty")

        canon_revision = self.document.get("canon_revision")
        if isinstance(canon_revision, str) and not canon_revision.strip():
            self.error("empty_canon_revision", self.path("canon_revision"), "must not be empty")

        previous_hash = self.document.get("previous_state_sha256")
        if isinstance(version, int) and not isinstance(version, bool) and isinstance(previous_hash, str):
            if version == 0 and previous_hash:
                self.error(
                    "initial_state_has_previous_hash",
                    self.path("previous_state_sha256"),
                    "state_version 0 must not claim a previous state",
                )
            elif version > 0 and not SHA256_RE.fullmatch(previous_hash):
                self.error(
                    "invalid_previous_state_sha256",
                    self.path("previous_state_sha256"),
                    "non-initial states require a lowercase raw SHA256 digest",
                )

        text_hash = self.document.get("text_sha256")
        has_bound_content = any(
            bool(self.document.get(key))
            for key in ("timeline", "chapter_transactions", "keyframes")
        )
        if isinstance(text_hash, str):
            if has_bound_content and not SHA256_RE.fullmatch(text_hash):
                self.error(
                    "text_sha256_required",
                    self.path("text_sha256"),
                    "states containing events, transactions, or keyframes require a final-text digest",
                )
            elif text_hash and not SHA256_RE.fullmatch(text_hash):
                self.error(
                    "invalid_text_sha256",
                    self.path("text_sha256"),
                    "must be empty or a lowercase raw SHA256 digest",
                )
        return True

    def build_indexes(self) -> None:
        if not isinstance(self.document, dict):
            return
        for collection, id_field in COLLECTION_ID_FIELDS.items():
            values = self.document.get(collection)
            index: dict[str, dict[str, Any]] = {}
            self.indexes[collection] = index
            if not isinstance(values, list):
                continue
            for position, entry in enumerate(values):
                path = self.path(f"{collection}[{position}]")
                if not isinstance(entry, dict):
                    self.error("invalid_entry_type", path, "collection entry must be an object")
                    continue
                identifier = self.require_string(entry, id_field, path)
                if identifier is None:
                    continue
                if identifier in index:
                    self.error(
                        "duplicate_id",
                        f"{path}.{id_field}",
                        f"duplicate {id_field}: {identifier}",
                    )
                    continue
                index[identifier] = entry

    def require_reference(
        self, identifier: Any, collection: str, path: str, *, nullable: bool = False
    ) -> None:
        if nullable and identifier is None:
            return
        if not isinstance(identifier, str) or not identifier:
            self.error("invalid_reference", path, f"must reference {collection} with a non-empty string")
            return
        if identifier not in self.indexes.get(collection, {}):
            self.error("missing_reference", path, f"unknown {collection} id: {identifier}")

    def validate_transitions(self, transitions: Any, path: str) -> None:
        if not isinstance(transitions, list):
            self.error("invalid_type", path, "transitions must be an array")
            return
        for position, transition in enumerate(transitions):
            transition_path = f"{path}[{position}]"
            if not isinstance(transition, dict):
                self.error("invalid_entry_type", transition_path, "transition must be an object")
                continue
            transition_id = self.require_string(
                transition, "transition_id", transition_path
            )
            if transition_id is not None:
                if transition_id in self.transition_ids:
                    self.error(
                        "duplicate_transition_id",
                        f"{transition_path}.transition_id",
                        f"duplicate transition_id: {transition_id}",
                    )
                self.transition_ids.add(transition_id)
            self.require_string(transition, "from_state", transition_path)
            self.require_string(transition, "to_state", transition_path)
            if "trigger_event_id" not in transition or not transition.get("trigger_event_id"):
                self.error(
                    "transition_trigger_required",
                    f"{transition_path}.trigger_event_id",
                    "state transitions require a trigger event",
                )
            else:
                self.require_reference(
                    transition.get("trigger_event_id"),
                    "timeline",
                    f"{transition_path}.trigger_event_id",
                )

    def validate_facts(self) -> None:
        for fact_id, fact in self.indexes.get("facts", {}).items():
            path = self.path(f"facts[{fact_id}]")
            status = self.require_string(fact, "status", path)
            if status is not None and status not in FACT_STATUSES:
                self.error("invalid_fact_status", f"{path}.status", f"unsupported status: {status}")
            self.validate_source_anchor(fact.get("source_anchor"), f"{path}.source_anchor")
            superseded_by = fact.get("superseded_by_fact_id")
            if superseded_by is not None:
                self.require_reference(superseded_by, "facts", f"{path}.superseded_by_fact_id")
            if status == "superseded" and not superseded_by:
                self.error(
                    "superseded_fact_missing_replacement",
                    f"{path}.superseded_by_fact_id",
                    "superseded facts require a replacement fact reference",
                )

    def validate_locations(self) -> None:
        for location_id, location in self.indexes.get("locations", {}).items():
            parent = location.get("parent_location_id")
            if parent is not None:
                self.require_reference(
                    parent, "locations", self.path(f"locations[{location_id}].parent_location_id")
                )

    def validate_timeline(self) -> None:
        conflict_ids = set(self.indexes.get("unresolved_conflicts", {}))
        seen_sequences: set[int] = set()
        for event_id, event in self.indexes.get("timeline", {}).items():
            path = self.path(f"timeline[{event_id}]")
            status = self.require_string(event, "status", path)
            if status is not None and status not in EVENT_STATUSES:
                self.error("invalid_event_status", f"{path}.status", f"unsupported status: {status}")
            self.require_string(event, "kind", path)
            self.require_string(event, "story_time_start", path)
            sequence = event.get("sequence")
            if (
                not isinstance(sequence, int)
                or isinstance(sequence, bool)
                or sequence < 0
            ):
                self.error(
                    "invalid_event_sequence",
                    f"{path}.sequence",
                    "must be a non-negative integer",
                )
            elif sequence in seen_sequences:
                self.error(
                    "duplicate_event_sequence",
                    f"{path}.sequence",
                    "event sequence values must be unique",
                )
            else:
                seen_sequences.add(sequence)
            self.validate_source_anchor(event.get("source_anchor"), f"{path}.source_anchor")
            if "story_time_end" in event and event["story_time_end"] is not None and not isinstance(event["story_time_end"], str):
                self.error("invalid_type", f"{path}.story_time_end", "must be a string or null")
            self.require_reference(event.get("location_id"), "locations", f"{path}.location_id", nullable=True)

            participant_ids = self.require_list(event, "participant_ids", path)
            if participant_ids is not None:
                for position, character_id in enumerate(participant_ids):
                    self.require_reference(
                        character_id,
                        "characters",
                        f"{path}.participant_ids[{position}]",
                    )

            fact_ids = self.require_list(event, "depends_on_fact_ids", path)
            if fact_ids is not None:
                for position, fact_id in enumerate(fact_ids):
                    self.require_reference(fact_id, "facts", f"{path}.depends_on_fact_ids[{position}]")

            depends_on_conflicts = self.require_list(event, "depends_on_conflict_ids", path)
            if depends_on_conflicts is not None:
                for position, conflict_id in enumerate(depends_on_conflicts):
                    reference_path = f"{path}.depends_on_conflict_ids[{position}]"
                    self.require_reference(conflict_id, "unresolved_conflicts", reference_path)
                    if status == "committed" and conflict_id in conflict_ids:
                        self.error(
                            "committed_event_depends_on_unresolved_conflict",
                            reference_path,
                            "a committed event cannot consume an unresolved conflict",
                        )

            movement = event.get("movement")
            if movement is not None:
                if not isinstance(movement, dict):
                    self.error("invalid_type", f"{path}.movement", "must be an object")
                    continue
                self.require_reference(
                    movement.get("character_id"), "characters", f"{path}.movement.character_id"
                )
                self.require_reference(
                    movement.get("from_location_id"), "locations", f"{path}.movement.from_location_id"
                )
                self.require_reference(
                    movement.get("to_location_id"), "locations", f"{path}.movement.to_location_id"
                )
                duration = movement.get("duration_minutes")
                valid_number = (
                    isinstance(duration, (int, float))
                    and not isinstance(duration, bool)
                    and math.isfinite(duration)
                )
                if not valid_number:
                    self.error(
                        "invalid_movement_duration",
                        f"{path}.movement.duration_minutes",
                        "must be a finite number",
                    )
                elif duration < 0:
                    self.error(
                        "negative_movement_duration",
                        f"{path}.movement.duration_minutes",
                        "movement duration must be non-negative",
                    )

    def validate_characters(self) -> None:
        knowledge_ids = self.indexes.get("knowledge", {})
        item_ids = self.indexes.get("items", {})
        for character_id, character in self.indexes.get("characters", {}).items():
            path = self.path(f"characters[{character_id}]")
            self.require_reference(character.get("location_id"), "locations", f"{path}.location_id", nullable=True)
            state_machine = character.get("state_machine")
            if not isinstance(state_machine, dict):
                self.error("character_state_machine_required", f"{path}.state_machine", "must be an object")
            else:
                self.require_string(state_machine, "current_state", f"{path}.state_machine")
                self.validate_transitions(
                    state_machine.get("transitions"), f"{path}.state_machine.transitions"
                )
            for field, available in (("knowledge_ids", knowledge_ids), ("item_ids", item_ids)):
                values = character.get(field, [])
                if not isinstance(values, list):
                    self.error("invalid_type", f"{path}.{field}", "must be an array")
                    continue
                for position, identifier in enumerate(values):
                    if not isinstance(identifier, str) or identifier not in available:
                        self.error("missing_reference", f"{path}.{field}[{position}]", f"unknown id: {identifier}")

    def validate_knowledge(self) -> None:
        for knowledge_id, knowledge in self.indexes.get("knowledge", {}).items():
            path = self.path(f"knowledge[{knowledge_id}]")
            self.require_reference(knowledge.get("holder_id"), "characters", f"{path}.holder_id")
            self.require_reference(knowledge.get("fact_id"), "facts", f"{path}.fact_id")
            state = self.require_string(knowledge, "state", path)
            if state is not None and state not in KNOWLEDGE_STATES:
                self.error("invalid_knowledge_state", f"{path}.state", f"unsupported state: {state}")
            if "source_event_id" not in knowledge or not knowledge.get("source_event_id"):
                self.error(
                    "knowledge_source_required",
                    f"{path}.source_event_id",
                    "knowledge requires an acquisition/source event",
                )
            else:
                self.require_reference(
                    knowledge.get("source_event_id"), "timeline", f"{path}.source_event_id"
                )
            self.require_string(knowledge, "acquired_at", path)

    def validate_items(self) -> None:
        for item_id, item in self.indexes.get("items", {}).items():
            path = self.path(f"items[{item_id}]")
            ownership_model = self.require_string(item, "ownership_model", path)
            if ownership_model is not None and ownership_model not in OWNERSHIP_MODELS:
                self.error(
                    "invalid_ownership_model",
                    f"{path}.ownership_model",
                    f"unsupported ownership model: {ownership_model}",
                )
            holders = self.require_list(item, "holders", path)
            if holders is None:
                continue
            active_count = 0
            for position, holder in enumerate(holders):
                holder_path = f"{path}.holders[{position}]"
                if not isinstance(holder, dict):
                    self.error("invalid_entry_type", holder_path, "holder must be an object")
                    continue
                holder_type = self.require_string(holder, "holder_type", holder_path)
                active = holder.get("active")
                if not isinstance(active, bool):
                    self.error("invalid_type", f"{holder_path}.active", "must be a boolean")
                elif active:
                    active_count += 1
                holder_id = holder.get("holder_id")
                if holder_type is not None and holder_type not in HOLDER_TYPES:
                    self.error("invalid_holder_type", f"{holder_path}.holder_type", f"unsupported holder type: {holder_type}")
                elif holder_type == "character":
                    self.require_reference(holder_id, "characters", f"{holder_path}.holder_id")
                elif holder_type == "location":
                    self.require_reference(holder_id, "locations", f"{holder_path}.holder_id")
                elif holder_type == "none" and holder_id is not None:
                    self.error("none_holder_has_id", f"{holder_path}.holder_id", "holder_type none requires null holder_id")
                since_event = holder.get("since_event_id")
                if since_event is not None:
                    self.require_reference(since_event, "timeline", f"{holder_path}.since_event_id")
            if ownership_model == "unique" and active_count > 1:
                self.error(
                    "item_multiple_active_holders",
                    f"{path}.holders",
                    "a unique item may have at most one active holder",
                )

    def validate_foreshadowing(self) -> None:
        for foreshadow_id, entry in self.indexes.get("foreshadowing", {}).items():
            path = self.path(f"foreshadowing[{foreshadow_id}]")
            status = self.require_string(entry, "status", path)
            if status is not None and status not in FORESHADOW_STATUSES:
                self.error("invalid_foreshadow_status", f"{path}.status", f"unsupported status: {status}")
            self.require_reference(entry.get("seed_event_id"), "timeline", f"{path}.seed_event_id")
            if entry.get("payoff_event_id") is not None:
                self.require_reference(entry.get("payoff_event_id"), "timeline", f"{path}.payoff_event_id")

    def validate_plot_states(self) -> None:
        for plot_state_id, entry in self.indexes.get("plot_states", {}).items():
            path = self.path(f"plot_states[{plot_state_id}]")
            self.require_string(entry, "current_state", path)
            self.validate_transitions(entry.get("transitions"), f"{path}.transitions")

    def validate_transactions(self) -> None:
        for transaction_id, entry in self.indexes.get("chapter_transactions", {}).items():
            path = self.path(f"chapter_transactions[{transaction_id}]")
            self.require_string(entry, "chapter_id", path)
            status = self.require_string(entry, "status", path)
            if status is not None and status not in TRANSACTION_STATUSES:
                self.error("invalid_transaction_status", f"{path}.status", f"unsupported status: {status}")
            for field in ("input_state_version", "output_state_version"):
                value = entry.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    self.error("invalid_state_version", f"{path}.{field}", "must be a non-negative integer")
            if not isinstance(entry.get("delta"), dict):
                self.error("invalid_type", f"{path}.delta", "must be an object")
            self.require_sha256(entry, "text_sha256", path)
            self.require_reference(
                entry.get("keyframe_id"), "keyframes", f"{path}.keyframe_id"
            )
            keyframe = self.indexes.get("keyframes", {}).get(entry.get("keyframe_id"))
            if isinstance(keyframe, dict):
                if entry.get("text_sha256") != keyframe.get("text_sha256"):
                    self.error(
                        "transaction_keyframe_text_sha256_mismatch",
                        f"{path}.text_sha256",
                        "transaction and referenced keyframe must bind the same final prose",
                    )
                if entry.get("chapter_id") != keyframe.get("chapter_id"):
                    self.error(
                        "transaction_keyframe_chapter_mismatch",
                        f"{path}.chapter_id",
                        "transaction and referenced keyframe must name the same chapter",
                    )
                if entry.get("output_state_version") != keyframe.get("state_version"):
                    self.error(
                        "transaction_keyframe_state_version_mismatch",
                        f"{path}.output_state_version",
                        "transaction output version must equal referenced keyframe version",
                    )
            if (
                status == "committed"
                and isinstance(entry.get("input_state_version"), int)
                and isinstance(entry.get("output_state_version"), int)
                and entry["output_state_version"] != entry["input_state_version"] + 1
            ):
                self.error(
                    "invalid_committed_transaction_version",
                    f"{path}.output_state_version",
                    "committed transactions must advance the state by exactly one version",
                )

    def validate_keyframes(self) -> None:
        current_version = self.document.get("state_version") if isinstance(self.document, dict) else None
        current_text_sha256 = self.document.get("text_sha256") if isinstance(self.document, dict) else None
        current_matches = 0
        for keyframe_id, entry in self.indexes.get("keyframes", {}).items():
            path = self.path(f"keyframes[{keyframe_id}]")
            self.require_string(entry, "chapter_id", path)
            text_sha256 = self.require_sha256(entry, "text_sha256", path)
            state_version = entry.get("state_version")
            if (
                not isinstance(state_version, int)
                or isinstance(state_version, bool)
                or state_version < 0
            ):
                self.error(
                    "invalid_state_version",
                    f"{path}.state_version",
                    "must be a non-negative integer",
                )
            status = self.require_string(entry, "status", path)
            if status is not None and status not in KEYFRAME_STATUSES:
                self.error(
                    "invalid_keyframe_status",
                    f"{path}.status",
                    f"unsupported status: {status}",
                )
            previous_keyframe_id = entry.get("previous_keyframe_id")
            if previous_keyframe_id is not None:
                self.require_reference(
                    previous_keyframe_id,
                    "keyframes",
                    f"{path}.previous_keyframe_id",
                )
                if previous_keyframe_id == keyframe_id:
                    self.error(
                        "keyframe_self_reference",
                        f"{path}.previous_keyframe_id",
                        "a keyframe cannot reference itself",
                    )
            invalidated_by = entry.get("invalidated_by_transaction_id")
            if status == "invalidated":
                self.require_reference(
                    invalidated_by,
                    "chapter_transactions",
                    f"{path}.invalidated_by_transaction_id",
                )
            elif invalidated_by is not None:
                self.error(
                    "active_keyframe_has_invalidator",
                    f"{path}.invalidated_by_transaction_id",
                    "only invalidated keyframes may name an invalidating transaction",
                )

            snapshot = entry.get("state_snapshot")
            if not isinstance(snapshot, dict):
                self.error(
                    "keyframe_snapshot_required",
                    f"{path}.state_snapshot",
                    "must be an object",
                )
            snapshot_sha256 = self.require_sha256(entry, "snapshot_sha256", path)
            if isinstance(snapshot, dict) and isinstance(snapshot_sha256, str) and SHA256_RE.fullmatch(snapshot_sha256):
                canonical = json.dumps(
                    snapshot,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                if hashlib.sha256(canonical).hexdigest() != snapshot_sha256:
                    self.error(
                        "keyframe_snapshot_sha256_mismatch",
                        f"{path}.snapshot_sha256",
                        "digest must match canonical JSON bytes of state_snapshot",
                    )

            if (
                status == "active"
                and state_version == current_version
                and text_sha256 == current_text_sha256
            ):
                current_matches += 1

        committed_content = any(
            isinstance(entry, dict) and entry.get("status") == "committed"
            for collection in ("timeline", "chapter_transactions")
            for entry in self.document.get(collection, [])
            if isinstance(self.document, dict)
            and isinstance(self.document.get(collection), list)
        )
        if committed_content and not self.indexes.get("keyframes"):
            self.error(
                "keyframe_required",
                self.path("keyframes"),
                "committed content requires a final-text-bound keyframe",
            )
        elif self.indexes.get("keyframes") and current_matches != 1:
            self.error(
                "current_keyframe_binding_invalid",
                self.path("keyframes"),
                "exactly one active keyframe must bind the current state version and final-text digest",
            )

    def validate_conflicts(self) -> None:
        for conflict_id, conflict in self.indexes.get("unresolved_conflicts", {}).items():
            path = self.path(f"unresolved_conflicts[{conflict_id}]")
            status = self.require_string(conflict, "status", path)
            if status is not None and status != "unresolved":
                self.error("invalid_unresolved_conflict_status", f"{path}.status", "must be unresolved")
            severity = self.require_string(conflict, "severity", path)
            if severity is not None and severity not in CONFLICT_SEVERITIES:
                self.error(
                    "invalid_conflict_severity",
                    f"{path}.severity",
                    f"unsupported severity: {severity}",
                )
            elif severity == "hard":
                self.error(
                    "unresolved_hard_conflict",
                    path,
                    "hard continuity conflicts must be resolved before validation can pass",
                )
            fact_ids = self.require_list(conflict, "fact_ids", path)
            if fact_ids is not None:
                for position, fact_id in enumerate(fact_ids):
                    self.require_reference(fact_id, "facts", f"{path}.fact_ids[{position}]")

    def validate(self) -> list[dict[str, str]]:
        if not self.validate_top_level():
            return self.errors
        self.build_indexes()
        self.validate_facts()
        self.validate_locations()
        self.validate_timeline()
        self.validate_characters()
        self.validate_knowledge()
        self.validate_items()
        self.validate_foreshadowing()
        self.validate_plot_states()
        self.validate_transactions()
        self.validate_keyframes()
        self.validate_conflicts()
        return self.errors


def read_json_document(path: Path) -> tuple[Any | None, bytes | None, dict[str, str] | None]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, None, {"code": "read_error", "path": path.name, "message": str(exc)}
    try:
        return json.loads(raw.decode("utf-8")), raw, None
    except UnicodeDecodeError as exc:
        return None, raw, {"code": "utf8_error", "path": path.name, "message": str(exc)}
    except json.JSONDecodeError as exc:
        return None, raw, {
            "code": "json_parse_error",
            "path": path.name,
            "message": f"line {exc.lineno}, column {exc.colno}: {exc.msg}",
        }


def read_prose_document(
    path: Path,
) -> tuple[bytes | None, list[str] | None, dict[str, str] | None]:
    """Read final prose and hash 1-based non-empty, non-heading source lines."""

    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, None, {"code": "prose_read_error", "path": path.name, "message": str(exc)}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return raw, None, {"code": "prose_utf8_error", "path": path.name, "message": str(exc)}
    paragraph_hashes = [
        hashlib.sha256(line.strip().encode("utf-8")).hexdigest()
        for line in text.splitlines()
        if line.strip() and not re.match(r"^\s{0,3}#{1,6}(?:\s|$)", line)
    ]
    return raw, paragraph_hashes, None


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(rendered)
        temporary = Path(handle.name)
    temporary.replace(path)


def validate_chain(
    current: Any,
    previous: Any,
    previous_raw: bytes,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(current, dict) or not isinstance(previous, dict):
        return errors
    current_version = current.get("state_version")
    previous_version = previous.get("state_version")
    if (
        isinstance(current_version, int)
        and not isinstance(current_version, bool)
        and isinstance(previous_version, int)
        and not isinstance(previous_version, bool)
        and current_version != previous_version + 1
    ):
        errors.append(
            {
                "code": "state_version_chain_mismatch",
                "path": "state.state_version",
                "message": "current state_version must equal previous state_version + 1",
            }
        )
    expected_hash = hashlib.sha256(previous_raw).hexdigest()
    if current.get("previous_state_sha256") != expected_hash:
        errors.append(
            {
                "code": "previous_state_sha256_mismatch",
                "path": "state.previous_state_sha256",
                "message": "digest must match the raw bytes of --previous",
            }
        )
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path, help="story .state.json file")
    parser.add_argument("--previous", type=Path, help="previous raw state for chain validation")
    parser.add_argument(
        "--prose",
        type=Path,
        help="final UTF-8 reader-facing prose whose raw SHA256 and paragraph anchors are bound",
    )
    parser.add_argument("--json-out", type=Path, help="optional JSON validation report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    errors: list[dict[str, str]] = []
    prose_raw: bytes | None = None
    prose_paragraph_sha256s: list[str] | None = None
    if args.prose is not None:
        if args.prose.resolve() == args.state.resolve():
            errors.append(
                {
                    "code": "prose_state_path_collision",
                    "path": args.prose.name,
                    "message": "--prose must be a separate reader-facing file",
                }
            )
        prose_raw, prose_paragraph_sha256s, prose_read_error = read_prose_document(
            args.prose
        )
        if prose_read_error:
            errors.append(prose_read_error)

    state, _, state_read_error = read_json_document(args.state)
    if state_read_error:
        errors.append(state_read_error)
    else:
        bound_content = isinstance(state, dict) and (
            bool(state.get("keyframes"))
            or any(
                isinstance(entry, dict) and entry.get("status") == "committed"
                for collection in ("timeline", "chapter_transactions")
                for entry in state.get(collection, [])
                if isinstance(state.get(collection), list)
            )
        )
        if bound_content and args.prose is None:
            errors.append(
                {
                    "code": "prose_required",
                    "path": "state.text_sha256",
                    "message": "states with committed content or keyframes require --prose",
                }
            )
        if (
            prose_raw is not None
            and isinstance(state, dict)
            and (bound_content or bool(state.get("text_sha256")))
            and state.get("text_sha256") != hashlib.sha256(prose_raw).hexdigest()
        ):
            errors.append(
                {
                    "code": "prose_sha256_mismatch",
                    "path": "state.text_sha256",
                    "message": "digest must match the raw bytes of --prose",
                }
            )
        errors.extend(
            StateValidator(
                state,
                prose_paragraph_sha256s=prose_paragraph_sha256s,
            ).validate()
        )
        if (
            args.previous is None
            and isinstance(state, dict)
            and isinstance(state.get("state_version"), int)
            and not isinstance(state.get("state_version"), bool)
            and state["state_version"] > 0
        ):
            errors.append(
                {
                    "code": "previous_state_required",
                    "path": "state.previous_state_sha256",
                    "message": "non-initial states require --previous for raw-hash verification",
                }
            )

    previous_name: str | None = None
    if args.previous is not None:
        previous_name = args.previous.name
        previous, previous_raw, previous_read_error = read_json_document(args.previous)
        if previous_read_error:
            errors.append(previous_read_error)
        elif previous_raw is not None:
            errors.extend(StateValidator(previous, prefix="previous").validate())
            errors.extend(validate_chain(state, previous, previous_raw))

    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "validator": "validate_story_state.py",
        "source": args.state.name,
        "previous": previous_name,
        "prose": args.prose.name if args.prose is not None else None,
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "limitations": [
            "Structural checks do not prove literary continuity, motive, POV fidelity, or plot quality.",
            "Semantic R1-R10 review remains required in a separate internal QA sidecar.",
        ],
    }

    if args.json_out is not None:
        output = args.json_out.resolve()
        protected = {args.state.resolve()}
        if args.previous is not None:
            protected.add(args.previous.resolve())
        if args.prose is not None:
            protected.add(args.prose.resolve())
        if not args.json_out.name.endswith(".qa.json"):
            report["passed"] = False
            report["errors"].append(
                {
                    "code": "invalid_report_suffix",
                    "path": args.json_out.name,
                    "message": "validation reports must use the .qa.json sidecar suffix",
                }
            )
            report["error_count"] = len(report["errors"])
        elif output in protected:
            report["passed"] = False
            report["errors"].append(
                {
                    "code": "report_overwrite_forbidden",
                    "path": args.json_out.name,
                    "message": "report must not overwrite a state input",
                }
            )
            report["error_count"] = len(report["errors"])
        else:
            try:
                write_json_atomic(args.json_out, report)
            except OSError as exc:
                report["passed"] = False
                report["errors"].append(
                    {"code": "report_write_error", "path": args.json_out.name, "message": str(exc)}
                )
                report["error_count"] = len(report["errors"])

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
