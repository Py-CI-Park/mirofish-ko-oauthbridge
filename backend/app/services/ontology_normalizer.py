from __future__ import annotations

import copy
import re
from typing import Any

_ASCII_ALNUM_RE = re.compile(r"[A-Za-z0-9]+")
_ASCII_ALPHA_RE = re.compile(r"[A-Za-z]+")


def _normalize_entity_base(name: Any, fallback_index: int) -> str:
    text = "" if name is None else str(name)
    parts = _ASCII_ALNUM_RE.findall(text)
    if not parts:
        return f"Entity{fallback_index}"
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _normalize_edge_base(name: Any, fallback_index: int) -> str:
    text = "" if name is None else str(name)
    parts = _ASCII_ALPHA_RE.findall(text.upper())
    if not parts:
        return "RELATION"
    return "_".join(parts)


def _alphabetic_suffix(index: int) -> str:
    letters: list[str] = []
    remaining = index

    while remaining > 0:
        remaining -= 1
        remaining, remainder = divmod(remaining, 26)
        letters.append(chr(ord("A") + remainder))

    return "".join(reversed(letters))


def _numeric_suffix(index: int) -> str:
    return str(index)


def _allocate_unique_names(
    bases: list[str],
    separator: str = "",
    suffix_formatter=_numeric_suffix,
    suffix_start: int = 2,
) -> list[str]:
    reserved_bases = set(bases)
    used_names: set[str] = set()
    occurrence_counts: dict[str, int] = {}
    next_suffix_by_base: dict[str, int] = {}
    allocated_names: list[str] = []

    for base in bases:
        occurrence_counts[base] = occurrence_counts.get(base, 0) + 1

        if occurrence_counts[base] == 1 and base not in used_names:
            candidate = base
        else:
            suffix = next_suffix_by_base.get(base, suffix_start)
            while True:
                candidate = f"{base}{separator}{suffix_formatter(suffix)}"
                suffix += 1
                if candidate in used_names or candidate in reserved_bases:
                    continue
                next_suffix_by_base[base] = suffix
                break

        used_names.add(candidate)
        allocated_names.append(candidate)

    return allocated_names


def _remap_entity_reference(
    reference: Any,
    original_name_map: dict[str, list[str]],
    normalized_name_map: dict[str, str],
) -> str:
    key = "" if reference is None else str(reference)

    original_matches = original_name_map.get(key)
    if original_matches is not None:
        if len(original_matches) != 1:
            raise ValueError(f"Ambiguous ontology entity reference: {reference!r}")
        return original_matches[0]

    try:
        return normalized_name_map[key]
    except KeyError as exc:
        raise ValueError(f"Unknown ontology entity reference: {reference!r}") from exc


def normalize_ontology_for_zep(ontology: dict) -> dict:
    normalized = copy.deepcopy(ontology)

    entity_types = normalized.setdefault("entity_types", [])
    edge_types = normalized.setdefault("edge_types", [])

    entity_bases = [
        _normalize_entity_base(entity.get("name", ""), index)
        for index, entity in enumerate(entity_types, start=1)
    ]
    normalized_entity_names = _allocate_unique_names(entity_bases)

    original_name_map: dict[str, list[str]] = {}
    normalized_name_map: dict[str, str] = {}

    for entity, normalized_name in zip(entity_types, normalized_entity_names):
        original_name = entity.get("name", "")
        entity["name"] = normalized_name

        original_name_key = str(original_name)
        original_name_map.setdefault(original_name_key, []).append(normalized_name)
        normalized_name_map[normalized_name] = normalized_name

    edge_bases = [
        _normalize_edge_base(edge.get("name", ""), index)
        for index, edge in enumerate(edge_types, start=1)
    ]
    normalized_edge_names = _allocate_unique_names(
        edge_bases,
        separator="_",
        suffix_formatter=_alphabetic_suffix,
        suffix_start=1,
    )

    for edge, normalized_name in zip(edge_types, normalized_edge_names):
        edge["name"] = normalized_name

        if "source_targets" not in edge:
            continue

        source_targets = edge["source_targets"]
        if not isinstance(source_targets, list):
            raise ValueError("Ontology edge source_targets must be a list")

        remapped_source_targets = []
        for source_target in source_targets:
            remapped_source_target = dict(source_target)
            remapped_source_target["source"] = _remap_entity_reference(
                source_target.get("source"),
                original_name_map,
                normalized_name_map,
            )
            remapped_source_target["target"] = _remap_entity_reference(
                source_target.get("target"),
                original_name_map,
                normalized_name_map,
            )
            remapped_source_targets.append(remapped_source_target)

        edge["source_targets"] = remapped_source_targets

    return normalized
