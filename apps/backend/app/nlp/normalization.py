"""Value normalization used both when consolidating declarations and when
comparing values across sources for the consistency engine (Section 9/14).

Normalization is deliberately conservative: if a value can't be confidently
normalized, the original text is kept and normalization is skipped rather
than guessed at.
"""
from __future__ import annotations

import re

from dateutil import parser as dateutil_parser
from rapidfuzz import fuzz

from app.rules.quantity import parse_net_quantity

_WHITESPACE = re.compile(r"\s+")
_CURRENCY_NUMERIC = re.compile(r"[\d,]+(?:\.\d{1,2})?")


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _WHITESPACE.sub(" ", value).strip()


def normalize_currency(value: str | None) -> str | None:
    """Returns a canonical 'NNNN.NN' numeric string for comparison purposes,
    or None if no numeric amount could be found."""
    if not value:
        return None
    match = _CURRENCY_NUMERIC.search(value.replace(",", ""))
    if not match:
        return None
    try:
        return f"{float(match.group()):.2f}"
    except ValueError:
        return None


def normalize_quantity(value: str | None) -> str | None:
    """Returns a canonical '<grams>g' or '<ml>ml' string so 100 g and 0.1 kg
    compare equal, or None if unparseable."""
    parsed = parse_net_quantity(value)
    if parsed is None:
        return None
    unit = "g" if parsed.basis == "weight_g" else "ml"
    return f"{parsed.normalized_value:g}{unit}"


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = dateutil_parser.parse(value, fuzzy=True, default=None, dayfirst=True)
    except (ValueError, OverflowError, TypeError):
        return None
    return parsed.date().isoformat()


def fuzzy_equal(a: str | None, b: str | None, threshold: float = 85.0) -> bool:
    """True if two free-text values (e.g. manufacturer names) are 'the same'
    once minor formatting/spelling differences are accounted for. Used by
    the consistency engine so 'Tasty Foods Pvt Ltd' vs 'Tasty Foods Pvt. Ltd.'
    is not reported as a conflict."""
    if not a or not b:
        return False
    return fuzz.token_sort_ratio(normalize_text(a) or "", normalize_text(b) or "") >= threshold


NORMALIZERS = {
    "mrp": normalize_currency,
    "unit_sale_price": normalize_currency,
    "net_quantity": normalize_quantity,
    "mfg_date": normalize_date,
    "best_before_date": normalize_date,
}


def normalize_field_value(field_name: str, value: str | None) -> str | None:
    normalizer = NORMALIZERS.get(field_name, normalize_text)
    return normalizer(value)
