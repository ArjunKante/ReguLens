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
        # Real packaging almost always abbreviates ("Mfg. by:", "Mfd by:",
        # "Mfg. & Mktg. by:") rather than spelling out "manufactured by" —
        # e.g. a real Lay's packet reads "Mfg. & Mktg. by: PEPSICO INDIA
        # HOLDINGS PVT. LTD.", which the previous pattern never matched at
        # all (P0 audit fix: "manufacturer/packer/importer validation logic").
        # The "by" here doubles as the separator, so it stays optional after
        # it — unlike the bare-noun form below, "by" already scopes the match.
        _p(r"(?:manufactured\s*by|mfd\.?\s*by|mfg\.?\s*(?:(?:&|and)\s*mkt(?:d|g)?\.?\s*)?by)\s*[:\-]?\s*(?P<val>[^|\n\r,]{3,120})"),
        0.75,
    ),
    (
        # Bare "manufacturer"/"packer"/"importer" (no "by") REQUIRES an
        # explicit colon/dash separator, unlike the "by"-anchored forms
        # above. A live-listing test (Demo Hardening) found this matching
        # Flipkart's "Manufacturer info" details-panel section label (a UI
        # toggle, not a name:value declaration) as manufacturer_name="info"
        # when the separator was optional here too.
        F.MANUFACTURER_NAME,
        _p(r"manufacturer\s*[:\-]\s*(?P<val>[^|\n\r,]{3,120})"),
        0.75,
    ),
    (
        F.PACKER_NAME,
        _p(r"(?:packed\s*by|pkd\.?\s*by)\s*[:\-]?\s*(?P<val>[^|\n\r,]{3,120})"),
        0.75,
    ),
    (
        F.PACKER_NAME,
        _p(r"packer\s*[:\-]\s*(?P<val>[^|\n\r,]{3,120})"),
        0.75,
    ),
    (
        F.IMPORTER_NAME,
        _p(r"imported\s*by\s*[:\-]?\s*(?P<val>[^|\n\r,]{3,120})"),
        0.75,
    ),
    (
        F.IMPORTER_NAME,
        _p(r"importer\s*[:\-]\s*(?P<val>[^|\n\r,]{3,120})"),
        0.75,
    ),
    (
        F.COUNTRY_OF_ORIGIN,
        _p(r"country\s*of\s*origin\s*[:\-]?\s*(?P<val>[A-Za-z][A-Za-z .]{1,40})"),
        0.8,
    ),
    (
        F.NET_QUANTITY,
        # "Net Content(s)" is real, common packaging wording — verified on
        # an actual Amul milk pouch this session — not a synonym the
        # original "quantity/qty/weight/wt/volume/vol" list covered, so a
        # pack correctly declaring quantity under that name was reported as
        # a missing declaration (POTENTIAL_NON_COMPLIANCE) when it was
        # right there on the pack, just under a different accepted term.
        _p(
            r"(?:net\s*(?:quantity|qty|weight|wt|volume|vol|content(?:s)?)\.?)\s*[:\-]?\s*"
            r"(?P<val>\d+(?:\.\d+)?\s*(?:g|gm|gram|grams|kg|kgs|ml|l|lt|ltr|litre|liter|"
            r"pieces|pcs|units?|nos?)\b)"
        ),
        0.85,
    ),
    # A previous, unanchored fallback here — bare "\d+\s*(?:g|kg|ml|...)"
    # with no "net"/"quantity" keyword required, matching anywhere on the
    # page — was removed after a live-listing test (Demo Hardening) found
    # it matching a real Flipkart page's nutrition-facts panel ("Total Fat:
    # 8 g", "Protein: 2 g", "Total Carbohydrate: 17 g", ...) and other
    # recommended products' weights in a "similar products" carousel
    # ("Real Spinach Chips 125 g"), producing 9 wrong net_quantity
    # candidates against the listing's one real, correctly-labeled "163 g"
    # (same root cause and same fix philosophy as the MRP bare-"₹" bug:
    # never trust a bare number+unit with no declaration-context anchor).
    # Platform CSS selectors and each adapter's label:value table
    # extraction still independently catch quantity that has no "Net
    # Quantity:" text label anywhere but does have a DOM structure hook.
    (
        F.MRP,
        _p(r"(?:mrp|m\.r\.p\.?|maximum\s*retail\s*price)\s*[:\-]?\s*(?:incl[^)]*\)?\s*)?"
           r"[₹]?\s*rs\.?\s*(?P<val>[\d,]+(?:\.\d{1,2})?)"),
        0.85,
    ),
    (
        F.MRP,
        # No bare "₹" trigger — a live-listing test (Demo Hardening) found
        # this matching every rupee amount anywhere on the page (a "similar
        # products" recommendation carousel's unrelated prices, per-100g
        # unit-price mentions, etc.), producing a dozen+ noisy MRP
        # candidates for one listing and pushing a real, correctly-declared
        # MRP into a false POTENTIAL_NON_COMPLIANCE via ctx.best() picking
        # an unrelated bare number over it. Requiring the literal "mrp"/
        # "m.r.p" keyword text (same anchoring discipline every other
        # fallback pattern here already uses) is what actually scopes this
        # to the product's own MRP declaration.
        _p(r"(?:mrp|m\.r\.p\.?)\s*[:\-]?\s*[₹]?\s*(?P<val>[\d,]+(?:\.\d{1,2})?)"),
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


# Rule 6(1)(a) and Rule 10 both require an *address*, not just a name, for
# the manufacturer/packer/importer — but nothing ever produced
# manufacturer_address/packer_address/importer_address candidates, so
# `LMPC-R6-1A-MFR-NAME` and `LMPC-R10-NAME-ADDR-FORM` (both of which require
# an address field) could never PASS regardless of how complete a package's
# declaration actually was (P0 audit fix: "manufacturer/packer/importer
# validation logic"). Real labels present name and address as one
# contiguous line ("Mfg. by: X, P.O. Box ..., PIN - 122002, State") rather
# than under a separate "address:" label, so there is no independent
# keyword to anchor a standalone address pattern on — instead, the text
# immediately following a name match is checked for an Indian 6-digit PIN
# code (a strong, low-false-positive signal that a postal address follows)
# and captured as that role's address.
_ADDRESS_FIELD_FOR_NAME = {
    F.MANUFACTURER_NAME: F.MANUFACTURER_ADDRESS,
    F.PACKER_NAME: F.PACKER_ADDRESS,
    F.IMPORTER_NAME: F.IMPORTER_ADDRESS,
}
_PIN_CODE_PATTERN = re.compile(r"\b\d{6}\b")
_ADDRESS_WINDOW_CHARS = 220
_ADDRESS_BASE_CONFIDENCE = 0.55


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

            address_field = _ADDRESS_FIELD_FOR_NAME.get(field_name)
            if address_field is not None:
                window_end = min(len(text), m.end() + _ADDRESS_WINDOW_CHARS)
                window = text[m.end() : window_end]
                pin_match = _PIN_CODE_PATTERN.search(window)
                if pin_match:
                    address_value = window[: pin_match.end()].strip().strip(",;")
                    if address_value:
                        matches.append(
                            TextMatch(
                                field_name=address_field,
                                value=address_value,
                                raw_snippet=text[max(0, m.start() - 20) : window_end].strip(),
                                base_confidence=_ADDRESS_BASE_CONFIDENCE,
                            )
                        )
    return matches
