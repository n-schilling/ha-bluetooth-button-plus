"""The German translation covers every key of strings.json."""

from __future__ import annotations

import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "custom_components" / "bluetooth_button_plus"


def _paths(node: object, prefix: str = "") -> set[str]:
    if not isinstance(node, dict):
        return {prefix}
    return set().union(*(_paths(value, f"{prefix}/{key}") for key, value in node.items()))


def test_german_matches_strings() -> None:
    """Same keys, no more and no less, so nothing silently falls back to English."""
    strings = json.loads((PACKAGE / "strings.json").read_text(encoding="utf-8"))
    german = json.loads((PACKAGE / "translations" / "de.json").read_text(encoding="utf-8"))
    assert _paths(german) == _paths(strings)
