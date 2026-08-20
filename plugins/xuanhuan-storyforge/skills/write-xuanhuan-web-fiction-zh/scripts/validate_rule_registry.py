#!/usr/bin/env python3
"""Fail-closed structural validation for the shadow rule registry.

This validator proves only registry integrity and source traceability.  It never
marks a fiction rule as semantically satisfied.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
REQUIRED_TOP_LEVEL = {"schema_version", "rules"}
REQUIRED_RULE_FIELDS = {
    "id",
    "name",
    "family",
    "ordinal",
    "kind",
    "source",
    "source_heading",
    "routes",
    "checkability",
    "relations",
    "control_aliases",
}
ALLOWED_KINDS = {"atomic", "workflow", "aggregate"}
ALLOWED_ROUTES = {
    "planning",
    "opening",
    "chapter_prose",
    "continuation",
    "rewrite",
    "audit",
    "worldbuilding",
    "character_design",
    "long_form",
}
ALLOWED_PURITY = {"deterministic", "assisted", "manual", "not_applicable"}
ALLOWED_RELATIONS = {"requires", "refines", "aggregates", "conflicts_with"}
ALIAS_CLASSES = {"strong", "weak", "formula"}
ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$")
FAMILY_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
HEADING_RE = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*$")


class RegistryValidationError(ValueError):
    """Raised when the registry cannot be trusted."""


def _fail(message: str) -> None:
    raise RegistryValidationError(message)


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    _fail(f"non-standard JSON constant: {value}")


def load_registry(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        _fail(f"cannot read registry {path}: {exc}")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        _fail(f"invalid JSON in {path}: {exc}")
    if not isinstance(value, dict):
        _fail("registry root must be an object")
    return value


def _closed_object(value: Any, required: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{label} must be an object")
    keys = set(value)
    missing = sorted(required - keys)
    extra = sorted(keys - required)
    if missing:
        _fail(f"{label} missing fields: {', '.join(missing)}")
    if extra:
        _fail(f"{label} has unknown fields: {', '.join(extra)}")
    return value


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        _fail(f"{label} must be a non-empty single-line string")
    return value


def _unique_string_list(value: Any, label: str, *, allow_empty: bool) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "a list" if allow_empty else "a non-empty list"
        _fail(f"{label} must be {qualifier}")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_nonempty_string(item, f"{label}[{index}]"))
    if len(result) != len(set(result)):
        _fail(f"{label} contains duplicates")
    return result


def _resolve_source(skill_root: Path, source: str, label: str) -> Path:
    if "\\" in source or "\x00" in source:
        _fail(f"{label} must use a safe POSIX relative path")
    pure = PurePosixPath(source)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        _fail(f"{label} must be a safe relative path without traversal")
    if not pure.parts or pure.parts[0] != "references" or pure.suffix != ".md":
        _fail(f"{label} must point to a Markdown file under references/")
    root = skill_root.resolve()
    candidate = (root / Path(*pure.parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        _fail(f"{label} escapes the skill root")
    if not candidate.is_file():
        _fail(f"{label} does not exist: {source}")
    return candidate


def _headings(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fail(f"cannot read source {path}: {exc}")
    headings: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            continue
        if in_fence:
            continue
        match = HEADING_RE.fullmatch(line)
        if match:
            headings.append(match.group(1))
    return headings


def validate_registry(registry_path: Path, *, skill_root: Path | None = None) -> dict[str, Any]:
    registry_path = Path(registry_path)
    root = Path(skill_root) if skill_root is not None else Path(__file__).resolve().parent.parent
    data = _closed_object(load_registry(registry_path), REQUIRED_TOP_LEVEL, "registry")
    if data["schema_version"] != SCHEMA_VERSION:
        _fail(f"schema_version must equal {SCHEMA_VERSION}")
    rules = data["rules"]
    if not isinstance(rules, list) or not rules:
        _fail("rules must be a non-empty list")

    ids: set[str] = set()
    number_slots: set[tuple[str, int]] = set()
    source_slots: set[tuple[str, str]] = set()
    ordinals_by_family: dict[str, list[int]] = defaultdict(list)
    families: set[str] = set()
    normalized: list[dict[str, Any]] = []
    heading_cache: dict[Path, list[str]] = {}

    for index, raw_rule in enumerate(rules):
        label = f"rules[{index}]"
        rule = _closed_object(raw_rule, REQUIRED_RULE_FIELDS, label)
        rule_id = _nonempty_string(rule["id"], f"{label}.id")
        if not ID_RE.fullmatch(rule_id):
            _fail(f"{label}.id has invalid format: {rule_id}")
        if rule_id in ids:
            _fail(f"duplicate rule id: {rule_id}")
        ids.add(rule_id)

        _nonempty_string(rule["name"], f"{label}.name")
        family = _nonempty_string(rule["family"], f"{label}.family")
        if not FAMILY_RE.fullmatch(family):
            _fail(f"{label}.family has invalid format: {family}")
        ordinal = rule["ordinal"]
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1:
            _fail(f"{label}.ordinal must be a positive integer")
        slot = (family, ordinal)
        if slot in number_slots:
            _fail(f"duplicate numbering slot: {family}#{ordinal}")
        number_slots.add(slot)
        ordinals_by_family[family].append(ordinal)
        families.add(family)

        kind = rule["kind"]
        if kind not in ALLOWED_KINDS:
            _fail(f"{label}.kind must be one of {sorted(ALLOWED_KINDS)}")

        source = _nonempty_string(rule["source"], f"{label}.source")
        source_path = _resolve_source(root, source, f"{label}.source")
        source_heading = _nonempty_string(rule["source_heading"], f"{label}.source_heading")
        source_slot = (source, source_heading)
        if source_slot in source_slots:
            _fail(f"duplicate source heading registration: {source} :: {source_heading}")
        source_slots.add(source_slot)
        headings = heading_cache.setdefault(source_path, _headings(source_path))
        count = headings.count(source_heading)
        if count != 1:
            _fail(
                f"{label}.source_heading must occur exactly once in {source}; "
                f"found {count}: {source_heading}"
            )

        routes = _unique_string_list(rule["routes"], f"{label}.routes", allow_empty=False)
        unknown_routes = sorted(set(routes) - ALLOWED_ROUTES)
        if unknown_routes:
            _fail(f"{label}.routes contains unknown routes: {', '.join(unknown_routes)}")

        checkability = _closed_object(
            rule["checkability"], {"purity", "semantic"}, f"{label}.checkability"
        )
        if checkability["purity"] not in ALLOWED_PURITY:
            _fail(f"{label}.checkability.purity has an invalid value")
        if checkability["semantic"] != "manual":
            _fail(f"{label}.checkability.semantic must be manual")

        relations = rule["relations"]
        if not isinstance(relations, list):
            _fail(f"{label}.relations must be a list")
        checked_relations: list[dict[str, str]] = []
        for relation_index, raw_relation in enumerate(relations):
            relation_label = f"{label}.relations[{relation_index}]"
            relation = _closed_object(raw_relation, {"kind", "target"}, relation_label)
            relation_kind = relation["kind"]
            if relation_kind not in ALLOWED_RELATIONS:
                _fail(f"{relation_label}.kind has an invalid value")
            target = _nonempty_string(relation["target"], f"{relation_label}.target")
            checked_relations.append({"kind": relation_kind, "target": target})

        aliases = _closed_object(rule["control_aliases"], ALIAS_CLASSES, f"{label}.control_aliases")
        for alias_class in sorted(ALIAS_CLASSES):
            _unique_string_list(
                aliases[alias_class], f"{label}.control_aliases.{alias_class}", allow_empty=True
            )

        normalized.append(
            {
                "id": rule_id,
                "family": family,
                "ordinal": ordinal,
                "kind": kind,
                "relations": checked_relations,
            }
        )

    for family, ordinals in sorted(ordinals_by_family.items()):
        ordered = sorted(ordinals)
        expected = list(range(1, ordered[-1] + 1))
        if ordered != expected:
            _fail(f"numbering family {family} must be contiguous from 1; found {ordered}")

    for rule in normalized:
        for relation in rule["relations"]:
            target = relation["target"]
            if target.startswith("family:"):
                target_family = target.removeprefix("family:")
                if target_family not in families:
                    _fail(f"relation from {rule['id']} targets unknown family: {target_family}")
                if target_family == rule["family"]:
                    _fail(f"relation from {rule['id']} cannot target its own family")
            else:
                if target not in ids:
                    _fail(f"relation from {rule['id']} targets unknown rule: {target}")
                if target == rule["id"]:
                    _fail(f"rule {rule['id']} cannot relate to itself")

    return {
        "schema_version": SCHEMA_VERSION,
        "rule_count": len(normalized),
        "family_count": len(families),
        "families": {family: len(values) for family, values in sorted(ordinals_by_family.items())},
        "semantic_validation": "not_performed",
    }


def _build_parser() -> argparse.ArgumentParser:
    default_registry = Path(__file__).resolve().parent.parent / "references" / "rule-registry.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", nargs="?", type=Path, default=default_registry)
    parser.add_argument("--skill-root", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="emit the structural report as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = validate_registry(args.registry, skill_root=args.skill_root)
    except RegistryValidationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"PASS: {report['rule_count']} rules across {report['family_count']} families; "
            "semantic validation not performed"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
