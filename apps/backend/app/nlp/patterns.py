"""Shared keyword/regex field-detection library (Section 9: "Use regex,
keyword/context detection, normalization, fuzzy matching").

This is the single place declaration-field regexes live, reused by both the
scraper's fallback-text-extraction strategy (over webpage visible text) and
the declaration-extraction engine (over OCR text). Keeping one copy avoids
the two subsystems silently drifting apart on what an "MRP-looking string"
is.

Each pattern captures the *value* in a named group `val`. Confidence is a
simple, documented heuristic (not a trained model) — see docs/compliance-engine.md
for the full explanation of why V1 is deliberately regex/keyword-first
rather than LLM-first (Section 46: "Do not use an LLM as final legal
authority").
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.rules import fields as F


@dataclass
class TextMatch:
    field_name: str
    value: str
    raw_snippet: str
    base_confidence: float


def _p(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


# (field_name, compiled_pattern, base_confidence)
_KEYWORD_PATTERNS: list[tuple[str, re.Pattern, float]] = [
    (
        F.MANUFACTURER_NAME,
        _p(r"(?:manufactured\s*by|manufacturer)\s*[:\-]?\s*(?P<val>[^|\n\r,]{3,120})"),
        0.75,
    ),
    (
        F.PACKER_NAME,
        _p(r"(?:packed\s*by|packer)\s*[:\-]?\s*(?P<val>[^|\n\r,]{3,120})"),
        0.75,
    ),
    (
        F.IMPORTER_NAME,
        _p(r"(?:imported\s*by|importer)\s*[:\-]?\s*(?P<val>[^|\n\r,]{3,120})"),
        0.75,
    ),
    (
        F.COUNTRY_OF_ORIGIN,
        _p(r"country\s*of\s*origin\s*[:\-]?\s*(?P<val>[A-Za-z][A-Za-z .]{1,40})"),
        0.8,
    ),
    (
        F.NET_QUANTITY,
        _p(
            r"(?:net\s*(?:quantity|qty|weight|wt|volume|vol)\.?)\s*[:\-]?\s*"
            r"(?P<val>\d+(?:\.\d+)?\s*(?:g|gm|gram|grams|kg|kgs|ml|l|lt|ltr|litre|liter|"
            r"pieces|pcs|units?|nos?)\b)"
        ),
        0.85,
    ),
    (
        F.NET_QUANTITY,
        _p(r"\b(?P<val>\d+(?:\.\d+)?\s*(?:g|gm|kg|ml|l|ltr|litre)\b)"),
        0.45,
    ),
    (
        F.MRP,
        _p(r"(?:mrp|m\.r\.p\.?|maximum\s*retail\s*price)\s*[:\-]?\s*(?:incl[^)]*\)?\s*)?"
           r"[₹]?\s*rs\.?\s*(?P<val>[\d,]+(?:\.\d{1,2})?)"),
        0.85,
    ),
    (
        F.MRP,
        _p(r"(?:mrp|₹)\s*[:\-]?\s*(?P<val>[\d,]+(?:\.\d{1,2})?)"),
        0.7,
    ),
    (
        F.CONSUMER_CARE_EMAIL,
        _p(r"(?P<val>[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})"),
        0.9,
    ),
    (
        F.CONSUMER_CARE_PHONE,
        _p(r"(?:customer\s*care|consumer\s*care|helpline|toll\s*free|call\s*us)\s*[:\-]?\s*"
           r"(?P<val>[\+]?[\d][\d\-\s]{7,14}\d)"),
        0.75,
    ),
    (
        F.CONSUMER_CARE_NAME,
        _p(r"(?:consumer\s*care|customer\s*care|marketed\s*by)\s*[:\-]?\s*(?P<val>[^|\n\r]{3,150})"),
        0.6,
    ),
    (
        F.MFG_DATE,
        _p(r"(?:mfg\.?\s*date|manufactured\s*on|packed\s*on|packaging\s*date)\s*[:\-]?\s*"
           r"(?P<val>[\w/\-\. ]{4,20})"),
        0.7,
    ),
    (
        F.BEST_BEFORE_DATE,
        _p(r"(?:best\s*before|use\s*by|expiry|exp\.?\s*date)\s*[:\-]?\s*(?P<val>[\w/\-\. ]{4,20})"),
        0.7,
    ),
    (
        F.UNIT_SALE_PRICE,
        _p(r"(?:unit\s*sale\s*price|price\s*per\s*(?:kg|g|l|ml))\s*[:\-]?\s*"
           r"[₹]?\s*(?P<val>[\d,]+(?:\.\d{1,2})?)"),
        0.75,
    ),
]


def find_field_candidates(text: str) -> list[TextMatch]:
    """Scans free text (webpage visible text OR OCR text) for candidate
    declaration values. Returns every match — including lower-confidence
    ones — never silently discarding a low-confidence candidate (Section 7:
    'Do not discard low-confidence results'; the compliance layer decides
    what to do with confidence, not the extractor)."""
    if not text:
        return []

    matches: list[TextMatch] = []
    for field_name, pattern, base_confidence in _KEYWORD_PATTERNS:
        for m in pattern.finditer(text):
            value = m.group("val").strip().strip(",;")
            if not value:
                continue
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 20)
            matches.append(
                TextMatch(
                    field_name=field_name,
                    value=value,
                    raw_snippet=text[start:end].strip(),
                    base_confidence=base_confidence,
                )
            )
    return matches
