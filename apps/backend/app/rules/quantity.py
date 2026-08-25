"""Small helper to parse a declared net-quantity string into a normalized
(value, basis) pair, used only for the Rule 26 small-package exemption gate.
Deliberately conservative: returns None when the text can't be confidently
parsed, rather than guessing (Section 1: "document uncertainty instead of
inventing")."""
from __future__ import annotations

import re
from dataclasses import dataclass

_WEIGHT_UNITS = {"g": 1, "gm": 1, "gram": 1, "grams": 1, "kg": 1000, "kgs": 1000, "kilogram": 1000}
_VOLUME_UNITS = {
    "ml": 1,
    "millilitre": 1,
    "milliliter": 1,
    "l": 1000,
    "lt": 1000,
    "ltr": 1000,
    "litre": 1000,
    "liter": 1000,
}

_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z]+)")


@dataclass
class ParsedQuantity:
    basis: str  # "weight_g" | "volume_ml"
    normalized_value: float


def parse_net_quantity(text: str | None) -> ParsedQuantity | None:
    if not text:
        return None
    match = _PATTERN.search(text.lower())
    if not match:
        return None
    value = float(match.group("value"))
    unit = match.group("unit")
    if unit in _WEIGHT_UNITS:
        return ParsedQuantity(basis="weight_g", normalized_value=value * _WEIGHT_UNITS[unit])
    if unit in _VOLUME_UNITS:
        return ParsedQuantity(basis="volume_ml", normalized_value=value * _VOLUME_UNITS[unit])
    return None
