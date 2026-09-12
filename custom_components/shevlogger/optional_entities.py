"""Presence helpers for optional profile entity groups."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def availability_anchor(description: Mapping[str, Any]) -> str | None:
    """Return a validated optional-group anchor from entity metadata."""
    anchor = description.get("availabilityAnchor")
    if not isinstance(anchor, str) or not anchor.strip():
        return None
    return anchor.strip()


def entity_is_active(
    description: Mapping[str, Any], state: Mapping[str, Any]
) -> bool:
    """Keep ordinary entities and expose optional ones only when present."""
    anchor = availability_anchor(description)
    if anchor is None:
        return True
    data = state.get("data")
    return isinstance(data, Mapping) and data.get(anchor) is not None


def active_entities(
    entities: Iterable[dict[str, Any]], state: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Filter the schema without losing metadata needed for later reloads."""
    return [entity for entity in entities if entity_is_active(entity, state)]


def optional_presence_signature(
    entities: Iterable[Mapping[str, Any]], state: Mapping[str, Any]
) -> tuple[tuple[str, bool], ...]:
    """Return a stable signature that changes when an optional device appears."""
    anchors = sorted(
        {
            anchor
            for entity in entities
            if (anchor := availability_anchor(entity)) is not None
        }
    )
    data = state.get("data")
    values = data if isinstance(data, Mapping) else {}
    return tuple((anchor, values.get(anchor) is not None) for anchor in anchors)


def entity_platform(description: Mapping[str, Any]) -> str:
    """Return the Home Assistant platform used by one profile entity."""
    platform = description.get("platform")
    if description.get("writable") is True and platform in {
        "number",
        "select",
        "switch",
    }:
        return str(platform)
    return "sensor"
