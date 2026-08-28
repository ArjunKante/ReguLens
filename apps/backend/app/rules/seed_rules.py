"""Structured rule database — the single source of truth loaded into the
`rules` / `rule_versions` tables.

Every entry here is traced to docs/legal-rules.md, which is in turn traced to
the Source PDF in /legal/. Do not add a rule here without a corresponding,
source-cited entry in docs/legal-rules.md (Section 1 / Section 11 of the
product brief: "Do not invent requirements that are not supported by the
supplied source documents").
"""
from __future__ import annotations

from typing import Any, TypedDict

from app.models.enums import ProductCategoryCode as Cat
from app.rules import fields as F

SOURCE_DOC = (
    "Book_on_Legal_Metrology_Packaged_Commodities_Rules,2011_with_all_amendments_whatsnews.pdf"
)

CONSISTENCY_SOURCE_DOC = (
    "LM-SCAN internal engineering rule (Section 14 of the product brief) — this is NOT a "
    "citation to the Legal Metrology (Packaged Commodities) Rules, 2011. It implements the "
    "cross-source consistency check the product brief requires; any finding it produces is "
    "worded as a potential inconsistency requiring officer verification, never as a rule "
    "violation in its own right."
)


class SeedRule(TypedDict, total=False):
    rule_key: str
    rule_reference: str
    title: str
    description: str
    requirement: str
    applicability: str
    exceptions: str | None
    validation_type: str
    severity: str
    validator_config: dict[str, Any]
    applicable_categories: list[str]
    excluded_categories: list[str]
    source_document: str
    source_locator: str
    effective_from: str | None
    effective_until: str | None
    notes: str | None
    gating_only: bool


SEED_RULES: list[SeedRule] = [
    {
        "rule_key": "LMPC-R3-APPLICABILITY",
        "rule_reference": "Rule 3",
        "title": "Chapter II applicability gate",
        "description": (
            "Chapter II (the mandatory-declaration rules) does not apply to packages "
            "above 25 kg/25 litre (with a separate 50 kg carve-out for cement, fertilizer, "
            "and agricultural farm produce sold in bags), or to packages meant for "
            "industrial or institutional consumers."
        ),
        "requirement": (
            "Chapter II does not apply to: (1) packages containing a quantity of more "
            "than 25 kg or 25 litre; (2) cement, fertilizer, and agricultural farm "
            "produce sold in bags above 50 kg; (3) packaged commodities meant for "
            "industrial consumers or institutional consumers."
        ),
        "applicability": "Gating logic only -- used to mark all other in-scope rules NOT_APPLICABLE when Chapter II does not apply.",
        "exceptions": (
            "Must NOT be implemented as a flat 'quantity <= 25kg/25 litre' test -- the "
            "PDF separately provides an above-50-kg condition for cement, fertilizer, "
            "and agricultural farm produce sold in bags (see notes)."
        ),
        "validation_type": "CROSS_FIELD_CHECK",
        "severity": "INFO",
        "validator_config": {"handler": "chapter2_applicability_gate"},
        "gating_only": True,
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 3",
        "effective_from": "2018-01-01",
        "effective_until": None,
        "notes": (
            "Current text substituted by G.S.R. 629(E) dated 23 June 2017, in force "
            "1.1.2018. Added 2026-08-28 per docs/Legal_Metrology_Rules_Corrected.md "
            "Section 3 / Section 18 Correction 4 -- this gate did not previously exist "
            "in the codebase at all, so every rule below ran unconditionally regardless "
            "of package size or consumer type. LM-SCAN has no commodity-type classifier "
            "(cement/fertilizer/agricultural farm produce) or industrial/institutional-"
            "consumer classifier beyond an explicit self-description in listing text "
            "(see app/nlp/classification.py::is_institutional_or_industrial_context), so "
            "this gate only asserts a confident exemption where the evidence supports it "
            "unambiguously (net quantity > 50kg, or > 25 litre, or an explicit "
            "institutional/industrial self-description) -- it never guesses a false "
            "exemption in the ambiguous 25-50kg band where the cement/fertilizer/"
            "farm-produce carve-out would matter; see "
            "evaluate_chapter2_applicability()'s docstring in app/rules/validators.py "
            "for the full band-by-band reasoning."
        ),
    },
    {
        "rule_key": "LMPC-R6-1A-MFR-NAME",
        "rule_reference": "Rule 6(1)(a)",
        "title": "Manufacturer / packer / importer name & address",
        "description": (
            "Every package must declare the name and address of the manufacturer, or "
            "(where the manufacturer is not the packer) the manufacturer AND packer, "
            "and for imported packages the importer's name and address."
        ),
        "requirement": (
            "The name and address of the manufacturer, or where the manufacturer is not "
            "the packer, the name and address of the manufacturer and packer and for any "
            "imported package the name and address of the importer shall be mentioned."
        ),
        "applicability": "All retail packages in scope of Chapter II (Rule 3).",
        "exceptions": (
            "Explanation III: for food articles this declaration is governed by the FSS "
            "Act, 2006 instead of this Rule. Rule 26 small-package exemption also applies."
        ),
        "validation_type": "PRESENCE_CHECK",
        "severity": "MAJOR",
        "validator_config": {
            "require_any_group": [
                [F.MANUFACTURER_NAME, F.MANUFACTURER_ADDRESS],
                [F.PACKER_NAME, F.PACKER_ADDRESS],
                [F.IMPORTER_NAME, F.IMPORTER_ADDRESS],
            ]
        },
        "excluded_categories": [Cat.FOOD.value],
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(1)(a), Explanations I-III",
        "effective_from": "2018-01-01",
        "effective_until": None,
        "notes": (
            "Substituted by G.S.R. 629(E) dated 23 June 2017, in force 1.1.2018. "
            "Excluded for FOOD category per Explanation III (FSS Act governs instead)."
        ),
    },
    {
        "rule_key": "LMPC-R6-1AA-COUNTRY-ORIGIN",
        "rule_reference": "Rule 6(1)(aa)",
        "title": "Country of origin (imported products)",
        "description": "Imported products must state country of origin/manufacture/assembly.",
        "requirement": (
            "The name of the country of origin or manufacture or assembly in case of "
            "imported products shall be mentioned on the package."
        ),
        "applicability": "Only when the product is identified as imported (importer declared).",
        "exceptions": "Not applicable to domestically manufactured products under Rule 6(1)(aa) itself.",
        "validation_type": "CROSS_FIELD_CHECK",
        "severity": "MAJOR",
        "validator_config": {"handler": "country_of_origin_gate"},
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(1)(aa)",
        "effective_from": "2018-01-01",
        "effective_until": None,
        "notes": (
            "Substituted by G.S.R. 629(E) dated 23 June 2017, in force 1.1.2018. Rule "
            "6(1)(aa) itself is imported-products-only and package-level (\"mentioned on the "
            "package\") -- it does not extend to domestic products or to any e-commerce-specific "
            "display duty. (Correction, 2026-08-28: an earlier revision of this note cross-"
            "referenced a purported 'Rule 6(10A)' e-commerce country-of-origin filter "
            "requirement said to derive from a 2026 amendment; that citation could not be "
            "traced to the authoritative supplied source and has been removed -- see "
            "LMPC-R6-10A-COO-FILTER's removal note above. No e-commerce-specific extension of "
            "6(1)(aa) is currently supported by the authoritative specification.)"
        ),
    },
    # NOTE: a rule previously seeded here as "LMPC-R6-10A-COO-FILTER" (a
    # purported "Rule 6(10A)" searchable/sortable country-of-origin filter
    # requirement, citing a "2026 amendment") was REMOVED on 2026-08-28.
    #
    # Correction note (dated 2026-08-28): that rule was never traceable to
    # the authoritative supplied consolidated source (the Legal Metrology
    # (Packaged Commodities) Rules, 2011 PDF, as corrected/re-confirmed in
    # docs/Legal_Metrology_Rules_Corrected.md). It was sourced from secondary
    # web summaries ("SCC Online, Mondaq, TeamLease RegTech, Digital Policy
    # Alert") that this codebase's own prior comments admitted were never
    # independently verified against a primary gazette text. The corrected,
    # authoritative specification contains no Rule 6(10A) and no such
    # amendment. It has been removed here (dropped from SEED_RULES) rather
    # than reworded, and `app/rules/loader.py` deactivates the corresponding
    # `Rule.active` row for any rule_key that disappears from this list —
    # see `load_rules()`'s deactivation pass. The row and its full version
    # history remain in the `rules`/`rule_versions` tables (Rule.active =
    # False) for audit purposes; it is not hard-deleted. Do not re-add a
    # country-of-origin e-commerce filter requirement unless it is supported
    # by the authoritative supplied source document.
    {
        "rule_key": "LMPC-R6-1B-GENERIC-NAME",
        "rule_reference": "Rule 6(1)(b)",
        "title": "Common / generic name of commodity",
        "description": "Every package must declare the common or generic name of the commodity.",
        "requirement": (
            "The common or generic names of the commodity contained in the package "
            "shall be mentioned on the package."
        ),
        "applicability": "All in-scope retail packages.",
        "exceptions": None,
        "validation_type": "PRESENCE_CHECK",
        "severity": "MINOR",
        "validator_config": {"require_any_group": [[F.PRODUCT_NAME]]},
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(1)(b)",
        "effective_from": "2011-04-01",
        "effective_until": None,
        "notes": None,
    },
    {
        "rule_key": "LMPC-R6-1C-NET-QUANTITY",
        "rule_reference": "Rule 6(1)(c); Rule 11",
        "title": "Net quantity declaration",
        "description": "Every package must declare net quantity in a standard unit or count.",
        "requirement": (
            "The net quantity, in terms of the standard unit of weight or measure, of the "
            "commodity contained in the package (or, where sold by number, the number of "
            "the commodity) shall be mentioned."
        ),
        "applicability": "All in-scope retail packages.",
        "exceptions": (
            "Rule 26: packages with net weight/measure of 10g/10ml or less are exempt "
            "entirely, except tobacco and tobacco products."
        ),
        "validation_type": "PATTERN_CHECK",
        "severity": "CRITICAL",
        "validator_config": {
            "field": F.NET_QUANTITY,
            # Devanagari unit alternatives (ग्राम/किलो/मिली/लीटर) mirror
            # app/nlp/patterns.py's Hindi net-quantity extraction and
            # app/rules/quantity.py's exemption-gate parsing — Rule 9(4)
            # permits declarations in Hindi, so a value extracted from a
            # Hindi-only label must not fail this rule's own format check
            # just because it wasn't written in English.
            "patterns": [
                r"\d+(\.\d+)?\s*(g|gm|gram|grams|kg|kgs|kilogram|ग्राम|ग्रा\.?|किलोग्राम|किलो)\b",
                r"\d+(\.\d+)?\s*(ml|millilitre|milliliter|l|lt|ltr|litre|liter|मिलीलीटर|मिली|लीटर)\b",
                r"\d+\s*(pieces|pcs|pc|units?|nos?\.?|count)\b",
                r"pack of\s*\d+",
            ],
        },
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(1)(c); general provisions in Rule 11",
        "effective_from": "2011-04-01",
        "effective_until": None,
        "notes": (
            "Rule 13's full unit-format text was not present in the reviewed excerpt of "
            "the Source PDF; fine-grained unit-format validation is therefore out of "
            "scope (see docs/legal-rules.md Limitations #1)."
        ),
    },
    {
        "rule_key": "LMPC-R6-1D-MFG-DATE",
        "rule_reference": "Rule 6(1)(d)",
        "title": "Month/year of manufacture, pre-packing, or import",
        "description": "Package must state month and year of manufacture/pre-packing/import.",
        "requirement": (
            "The month and year in which the commodity is manufactured or pre-packed or "
            "imported shall be mentioned on the package."
        ),
        "applicability": "All in-scope retail packages, subject to Proviso (A) exceptions.",
        "exceptions": (
            "Not required on bidi/incense-stick packages or domestic LPG cylinders "
            "(Proviso A); food articles governed by FSS Act rules instead; cosmetics "
            "governed by Drugs and Cosmetics Rules, 1945."
        ),
        "validation_type": "DATE_CHECK",
        "severity": "MINOR",
        "validator_config": {
            "field": F.MFG_DATE,
            "absence_status": "NEEDS_MANUAL_REVIEW",
            "absence_reason": (
                "Month/year of manufacture is usually printed only on the physical "
                "package and is frequently absent from marketplace listing text/images; "
                "absence here is not treated as a confirmed violation."
            ),
        },
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(1)(d)",
        "effective_from": "2011-04-01",
        "effective_until": None,
        "notes": (
            "Words 'or pre-packed or imported' omitted by G.S.R. 779(E)/226(E) effective "
            "1 October 2022; for inspections on/after that date the requirement text is "
            "simply 'month and year of manufacture'."
        ),
    },
    {
        "rule_key": "LMPC-R6-1DA-BEST-BEFORE",
        "rule_reference": "Rule 6(1)(da)",
        "title": "Best before / use-by date",
        "description": "Perishable commodities must declare a best-before or use-by date.",
        "requirement": (
            "If a package contains a commodity which may become unfit for human "
            "consumption after a period of time, the 'best before or use by the date, "
            "month and year' shall also be mentioned on the label."
        ),
        "applicability": "Perishable/consumable commodities — primarily FOOD category.",
        "exceptions": "Not applicable where another law already governs the point.",
        "validation_type": "DATE_CHECK",
        "severity": "MAJOR",
        "validator_config": {"field": F.BEST_BEFORE_DATE, "absence_status": "POTENTIAL_NON_COMPLIANCE"},
        "applicable_categories": [Cat.FOOD.value],
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(1)(da)",
        "effective_from": "2018-01-01",
        "effective_until": None,
        "notes": "Substituted by G.S.R. 629(E) dated 23 June 2017, in force 1.1.2018.",
    },
    {
        "rule_key": "LMPC-R6-1E-MRP",
        "rule_reference": "Rule 6(1)(e)",
        "title": "Retail sale price (MRP)",
        "description": "Package must declare MRP inclusive of all taxes, in Indian currency.",
        "requirement": (
            "The retail sale price of the package shall be declared, inclusive of all "
            "taxes, in Indian currency, rounded per the Rule."
        ),
        "applicability": "All in-scope retail packages.",
        "exceptions": (
            "Alcoholic beverages/spirituous liquor governed by State Excise law instead "
            "(unless silent on RSP); essential-commodity RSP fixed under the Essential "
            "Commodities Act, 1955 prevails if notified."
        ),
        "validation_type": "PATTERN_CHECK",
        "severity": "CRITICAL",
        "validator_config": {
            "field": F.MRP,
            # The currency marker is optional, not required: app/nlp/patterns.py
            # deliberately captures only the numeric portion into a declaration's
            # `value` (the ₹/Rs./MRP keyword that gates extraction lives in the
            # surrounding text, not the captured value itself — see the MRP
            # patterns there) — so a real, correctly-extracted MRP declaration
            # is a bare number like "120.00", never "Rs. 120.00". Requiring the
            # marker *inside* the value made this rule fail for every real
            # extracted MRP (found live-testing a genuinely compliant Hindi
            # label that should have PASSed this CRITICAL rule); still matches
            # a value that does carry the marker too (e.g. hand-supplied text).
            "patterns": [r"(?:₹|rs\.?|inr|mrp)?\s*\.?\s*\d+(\.\d{1,2})?"],
        },
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(1)(e)",
        "effective_from": "2022-10-01",
        "effective_until": None,
        "notes": (
            "Current text per G.S.R. 226(E) dated 28 March 2022 (in force 1.10.2022), "
            "superseding the itemised illustrations from G.S.R. 629(E) (2017)."
        ),
    },
    {
        "rule_key": "LMPC-R6-2-CONSUMER-CARE",
        "rule_reference": "Rule 6(2)",
        "title": "Consumer-care details",
        "description": "Package must declare a contactable person/office for consumer complaints.",
        "requirement": (
            "Every package shall bear the name, address, telephone number, e-mail address "
            "of the person or office who can be contacted for consumer complaints."
        ),
        "applicability": "All in-scope retail packages.",
        "exceptions": None,
        "validation_type": "CROSS_FIELD_CHECK",
        "severity": "MAJOR",
        "validator_config": {"handler": "consumer_care_check"},
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(2)",
        "effective_from": "2016-01-01",
        "effective_until": None,
        "notes": (
            "Substituted by G.S.R. 385(E) dated 14 May 2015 (effective 1.1.2016, "
            "compliance dispensed with until 30.6.2016). An earlier printed version read "
            "'...if available...' for phone/email; that wording is historical and does not "
            "apply to the current substituted text. Correction (2026-08-28, per "
            "docs/Legal_Metrology_Rules_Corrected.md Section 18 Correction 1): name, "
            "address, telephone number, AND e-mail address are each independently required "
            "-- none is an accepted substitute for another. A prior version of this rule's "
            "validator treated name-OR-address plus phone-OR-email as sufficient for a PASS; "
            "that was incorrect and has been fixed. Missing field(s) still route through the "
            "same evidence-quality-aware logic as every other rule (POTENTIAL_NON_COMPLIANCE "
            "under strong evidence, NEEDS_MANUAL_REVIEW under weak/uncertain evidence, "
            "UNABLE_TO_VERIFY with no usable evidence) -- OCR uncertainty alone is still "
            "never turned into an automatic violation."
        ),
    },
    {
        "rule_key": "LMPC-R6-10-ECOMMERCE-DISPLAY",
        "rule_reference": "Rule 6(10)",
        "title": "E-commerce mandatory display of declarations",
        "description": (
            "An e-commerce entity must ensure mandatory Rule 6(1) declarations (except "
            "month/year of manufacture) are displayed on the digital/electronic network."
        ),
        "requirement": (
            "An E-Commerce entity shall ensure that the mandatory declarations as "
            "specified in sub-rule (1), except the month and year in which the commodity "
            "is manufactured or packed, shall be displayed on the digital and electronic "
            "network used for e-commerce transactions."
        ),
        "applicability": "All products sold via an online marketplace/quick-commerce listing.",
        "exceptions": (
            "Marketplace e-commerce entities meeting the due-diligence conditions in the "
            "provisos are not themselves liable; liability rests with the "
            "manufacturer/seller/dealer/importer."
        ),
        "validation_type": "CROSS_FIELD_CHECK",
        "severity": "CRITICAL",
        "validator_config": {"handler": "ecommerce_display_aggregate"},
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(10)",
        "effective_from": "2018-01-01",
        "effective_until": None,
        "notes": (
            "This is the statutory basis for treating the online listing itself as a "
            "regulated object — it is why LM-SCAN's V1 scope (online listing inspection) "
            "is legally meaningful on its own, ahead of any physical-package check."
        ),
    },
    {
        "rule_key": "LMPC-R6-11-UNIT-SALE-PRICE",
        "rule_reference": "Rule 6(11)",
        "title": "Unit sale price",
        "description": "Multi-unit packages must declare a per-unit sale price.",
        "requirement": (
            "Unit sale price, in rupees rounded to two decimals, per gram/kg, per "
            "cm/metre, per ml/litre, or per number, as applicable; not required where "
            "retail sale price equals unit sale price."
        ),
        "applicability": "Multi-unit packages where RSP != per-unit price is meaningful.",
        "exceptions": (
            "Not required for alcoholic beverages under State Excise law, or where MRP "
            "equals the unit sale price (single-unit packs)."
        ),
        "validation_type": "CROSS_FIELD_CHECK",
        "severity": "MINOR",
        "validator_config": {
            "handler": "unit_sale_price_check",
            "multipack_hint_patterns": [r"pack of\s*\d+", r"\bx\s*\d+\b", r"\d+\s*x\s*\d+"],
            "reason_default": (
                "LM-SCAN cannot reliably determine multi-unit-pack status from a listing "
                "alone; officer should confirm whether unit sale price disclosure applies."
            ),
            "reason_multipack_hint": (
                "Listing text suggests a multi-unit pack (e.g. 'Pack of N') and no distinct "
                "unit sale price was detected, and the retail sale price does not appear to "
                "already equal a declared unit price; officer verification requested."
            ),
        },
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(11)",
        "effective_from": "2022-10-01",
        "effective_until": None,
        "notes": (
            "Current text inserted by G.S.R. 226(E) dated 28 March 2022 (effective "
            "1.10.2022), superseding an earlier version inserted by G.S.R. 779(E) dated "
            "2 November 2021 (effective 1.4.2022); both reproduced in the Source PDF. "
            "Correction (2026-08-28, per docs/Legal_Metrology_Rules_Corrected.md Section 7 "
            "/ Section 18 Correction 3): the previous validator never consulted the "
            "already-extracted `unit_sale_price` field at all, always returning "
            "NEEDS_MANUAL_REVIEW unconditionally. Moved from MANUAL_REVIEW_CHECK to "
            "CROSS_FIELD_CHECK (architecturally necessary for the cross-field RSP-vs-unit-"
            "price comparison the specification recommends) so that a declared unit sale "
            "price equal to the retail sale price now deterministically PASSes (the "
            "specification's express exception), and a detected multi-pack hint with a "
            "missing unit price now goes through the same evidence-quality-aware logic as "
            "every other absence finding, instead of a fixed status regardless of evidence "
            "quality. No blanket 'single item = exempt' rule is implemented, per the "
            "specification's explicit warning against that shortcut."
        ),
    },
    {
        "rule_key": "LMPC-R9-MANNER",
        "rule_reference": "Rule 9(1), 9(4)",
        "title": "Manner of declaration (legible, prominent, correct script)",
        "description": "Declarations must be legible, prominent, contrasting, in Hindi/English.",
        "requirement": (
            "Every declaration shall be legible and prominent; RSP/net-quantity numerals "
            "shall contrast with the label background; declarations shall be in Hindi "
            "(Devanagari) or English."
        ),
        "applicability": "All in-scope packages/listings.",
        "exceptions": None,
        "validation_type": "MANUAL_REVIEW_CHECK",
        "severity": "MINOR",
        "validator_config": {
            "reason_default": (
                "Legibility, prominence, and colour-contrast are visual-design judgments "
                "that OCR confidence can inform but not decide; officer review requested."
            ),
            "use_ocr_confidence_hint": True,
        },
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 9(1), 9(4)",
        "effective_from": "2011-04-01",
        "effective_until": None,
        "notes": None,
    },
    {
        "rule_key": "LMPC-R10-NAME-ADDR-FORM",
        "rule_reference": "Rule 10(1), 10(2)",
        "title": "Name/address form and completeness",
        "description": "Manufacturer/packer/importer address must be complete enough to locate them.",
        "requirement": (
            "The declared address must be a complete postal address (factory/registered "
            "office, or street/city/state + PIN) sufficient for a consumer to identify "
            "and locate the manufacturer, packer, or importer."
        ),
        "applicability": "Same scope as Rule 6(1)(a); adds a completeness test.",
        "exceptions": (
            "Rule 28 allows registration of a shorter address where the authority is "
            "satisfied it is sufficient; an address that doesn't clearly show both a PIN "
            "and a locality is routed to manual review rather than auto-failed, since it "
            "may be a legitimately registered shorter address."
        ),
        "validation_type": "CROSS_FIELD_CHECK",
        "severity": "MAJOR",
        "validator_config": {
            "handler": "name_address_form_check",
            "any_of_fields": [F.MANUFACTURER_ADDRESS, F.PACKER_ADDRESS, F.IMPORTER_ADDRESS],
        },
        "excluded_categories": [Cat.FOOD.value],
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 10(1), 10(2), Explanation 1",
        "effective_from": "2018-01-01",
        "effective_until": None,
        "notes": (
            "Explanation 1 substituted by G.S.R. 629(E) dated 23 June 2017, in force "
            "1.1.2018. Correction (2026-08-28, per docs/Legal_Metrology_Rules_Corrected.md "
            "Section 18 Correction 2): the previous validator PASSed on a PIN code ALONE OR "
            "a 'word, word' locality pattern ALONE -- the corrected specification names "
            "'PIN OR city+state = complete address' directly as an incorrect universal test. "
            "Replaced with a layered heuristic (both a PIN AND a locality token required for "
            "PASS; anything short of that routes to NEEDS_MANUAL_REVIEW, never an automatic "
            "violation, since Rule 28 permits a registered shorter address this heuristic "
            "cannot distinguish from an incomplete one)."
        ),
    },
    {
        "rule_key": "LMPC-R11-QTY-BASIS",
        "rule_reference": "Rule 11(1)-(3)",
        "title": "Net quantity computed on commodity only ('when packed' disallowed)",
        "description": "Declared quantity must not be qualified by 'when packed' or similar.",
        "requirement": (
            "The declaration of quantity shall not be qualified by the words 'when "
            "packed' or the like; declared quantity must correspond to what the consumer "
            "actually receives."
        ),
        "applicability": "All in-scope packages.",
        "exceptions": None,
        "validation_type": "CROSS_FIELD_CHECK",
        "severity": "MINOR",
        "validator_config": {"handler": "when_packed_phrase"},
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 11(1)-(3)",
        "effective_from": "2011-04-01",
        "effective_until": None,
        "notes": None,
    },
    {
        "rule_key": "LMPC-R31-ADVERTISEMENT-NET-QTY",
        "rule_reference": "Rule 31(1)-(2)",
        "title": "Advertisement mentioning RSP must also declare net quantity",
        "description": (
            "Any advertisement mentioning the retail sale price of a pre-packaged commodity "
            "must also declare the net quantity or number of the commodity, in a font size "
            "matching the retail sale price."
        ),
        "requirement": (
            "Any advertisement which mentions the retail sale price of a pre-packaged "
            "commodity shall also contain a declaration of the net quantity, or the "
            "number of the commodity contained in the package, and the font size of the "
            "net quantity in the advertisement shall be the same as that of the retail "
            "sale price."
        ),
        "applicability": "Online listings that display a retail sale price (the listing itself functions as the advertisement).",
        "exceptions": "Not applicable where no retail sale price is displayed, or to manual/photo-only inspections with no online listing.",
        "validation_type": "CROSS_FIELD_CHECK",
        "severity": "MINOR",
        "validator_config": {"handler": "advertisement_net_quantity_check"},
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 31(1), 31(2)",
        "effective_from": "2011-04-01",
        "effective_until": None,
        "notes": (
            "Added 2026-08-28 per docs/Legal_Metrology_Rules_Corrected.md Section 12 / "
            "Section 18 Correction 6, which explicitly warns against grouping Rule 31 with "
            "the out-of-scope Rules 32-34 -- Rule 31 directly regulates advertisements that "
            "mention retail sale price and is squarely relevant to an online listing "
            "scanner. Net-quantity presence is a deterministic, evidence-quality-aware "
            "check; font-size equality between the RSP and net-quantity numerals can never "
            "be verified from scraped page content (no DOM/CSS measurement available), so "
            "this rule never reports a full PASS once RSP is displayed -- the best outcome "
            "is NEEDS_MANUAL_REVIEW for the font-size sub-requirement."
        ),
    },
    {
        "rule_key": "LMPC-R26-EXEMPT-SMALL",
        "rule_reference": "Rule 26(a)",
        "title": "Small-package exemption gate",
        "description": (
            "Packages of net weight/measure <=10g/10ml are exempt from these Rules "
            "entirely, except tobacco and tobacco products."
        ),
        "requirement": (
            "Nothing in these rules shall apply to a package where net weight or measure "
            "is ten gram/ten millilitre or less if sold by weight or measure, except "
            "tobacco and tobacco products."
        ),
        "applicability": "Gating logic only — used to mark other rules NOT_APPLICABLE.",
        "exceptions": "Does not apply to tobacco/tobacco products (proviso, G.S.R. 385(E), 2015).",
        "validation_type": "CROSS_FIELD_CHECK",
        "severity": "INFO",
        "validator_config": {"handler": "small_package_exemption_gate"},
        "gating_only": True,
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 26(a) and proviso",
        "effective_from": "2015-07-01",
        "effective_until": None,
        "notes": "Not surfaced as a standalone finding; applied internally by the rule engine.",
    },
    {
        "rule_key": "LMPC-R26-EXEMPT-FAST-FOOD",
        "rule_reference": "Rule 26(b)",
        "title": "Restaurant/hotel-packed fast food exemption",
        "description": (
            "The Rules do not apply to a package containing fast food items packed by a "
            "restaurant or hotel and the like."
        ),
        "requirement": (
            "Nothing in these rules shall apply to a package containing fast food items "
            "packed by a restaurant or hotel and the like."
        ),
        "applicability": "Standalone advisory finding -- never gates other rules NOT_APPLICABLE automatically.",
        "exceptions": None,
        "validation_type": "CROSS_FIELD_CHECK",
        "severity": "MINOR",
        "validator_config": {
            "handler": "fast_food_restaurant_gate",
            "hint_fields": [F.PRODUCT_NAME],
            "hint_patterns": [
                r"\bfast food\b", r"\brestaurant\b", r"\bhotel\b", r"\bready[\s-]?to[\s-]?eat\b",
                r"\bcloud kitchen\b", r"\bQSR\b", r"\btakeaway\b", r"\btake[\s-]?out\b",
            ],
        },
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 26(b)",
        "effective_from": "2011-04-01",
        "effective_until": None,
        "notes": (
            "Added 2026-08-28 per docs/Legal_Metrology_Rules_Corrected.md Section 11 "
            "('IMPLEMENTED/conditional' in the Section 17 summary). LM-SCAN cannot confirm "
            "a seller's actual restaurant/hotel-packer status from a marketplace listing, "
            "so this never asserts a confident exemption -- a narrow keyword hint only "
            "decides whether the question is even plausibly in play (NOT_APPLICABLE when "
            "absent, NEEDS_MANUAL_REVIEW when present); it never marks sibling rules "
            "NOT_APPLICABLE on its own."
        ),
    },
    {
        "rule_key": "LMPC-R26-EXEMPT-DRUG-FORMULATIONS",
        "rule_reference": "Rule 26(c)",
        "title": "Certain drug formulations exemption",
        "description": (
            "Certain scheduled and non-scheduled formulations covered by the Drugs (Price "
            "Control) Order, 2013 are exempt; medical devices declared as drugs are not."
        ),
        "requirement": (
            "Nothing in these rules shall apply to such scheduled formulations and "
            "non-scheduled formulations covered under the Drugs (Price Control) Order, "
            "2013. No exemption shall be applicable to medical devices declared as drugs."
        ),
        "applicability": "Standalone advisory finding -- never a confident exemption from OCR keywords alone.",
        "exceptions": "No exemption for medical devices declared as drugs.",
        "validation_type": "MANUAL_REVIEW_CHECK",
        "severity": "MINOR",
        "validator_config": {
            "applicability_hint_fields": [F.PRODUCT_NAME],
            "applicability_hint_patterns": [
                r"\btablet(s)?\b", r"\bcapsule(s)?\b", r"\bsyrup\b", r"\bformulation\b",
                r"\bpharmaceutical\b", r"\bdrug(s)?\b", r"\bmedicine\b", r"\bmedicament\b",
                r"\bschedule[d]?\s+formulation\b", r"\bI\.?P\.?\b", r"\bU\.?S\.?P\.?\b",
            ],
            "applicability_absent_reason": (
                "No evidence was found that this product is a scheduled or non-scheduled "
                "drug formulation under the Drugs (Price Control) Order, 2013."
            ),
            "reason_default": (
                "Listing text suggests this may be a drug formulation potentially covered by "
                "the Rule 26(c) exemption -- but LM-SCAN must not classify a product as a "
                "qualifying drug formulation (or rule out the medical-device carve-out) from "
                "OCR/listing keywords alone; an officer should confirm."
            ),
        },
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 26(c)",
        "effective_from": "2011-04-01",
        "effective_until": None,
        "notes": (
            "Added 2026-08-28 per docs/Legal_Metrology_Rules_Corrected.md Section 11, which "
            "explicitly warns: 'Do not classify a product as a qualifying drug formulation "
            "using OCR keywords alone.' A keyword hint only decides whether to surface a "
            "NEEDS_MANUAL_REVIEW flag at all (NOT_APPLICABLE when no hint is present); it "
            "never asserts a confident exemption on its own, and the medical-device carve-out "
            "is left entirely to officer judgment."
        ),
    },
    {
        "rule_key": "LMPC-R26-EXEMPT-THREAD-COIL",
        "rule_reference": "Rule 26(e)",
        "title": "Thread sold in coil to handloom weavers exemption",
        "description": "The Rules do not apply to thread sold in coil to handloom weavers.",
        "requirement": "Nothing in these rules shall apply to thread sold in coil to handloom weavers.",
        "applicability": "Standalone advisory finding -- never a confident exemption from OCR keywords alone.",
        "exceptions": None,
        "validation_type": "MANUAL_REVIEW_CHECK",
        "severity": "MINOR",
        "validator_config": {
            "applicability_hint_fields": [F.PRODUCT_NAME],
            "applicability_hint_patterns": [r"\bthread\b", r"\bcoil\b", r"\bhandloom\b", r"\bweaver(s)?\b", r"\byarn\b"],
            "applicability_absent_reason": (
                "No evidence was found that this product is thread sold in coil to handloom weavers."
            ),
            "reason_default": (
                "Listing text suggests this may be thread sold in coil to handloom weavers "
                "(Rule 26(e) exemption) -- but the specific transaction/use condition (sale "
                "to a handloom weaver specifically) is unlikely to be established reliably "
                "from a marketplace listing or OCR alone; an officer should confirm."
            ),
        },
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 26(e)",
        "effective_from": "2011-04-01",
        "effective_until": None,
        "notes": (
            "Added 2026-08-28 per docs/Legal_Metrology_Rules_Corrected.md Section 11, which "
            "notes the specific transaction/use condition (sale to a handloom weaver) is "
            "unlikely to be established reliably from OCR alone. A keyword hint only decides "
            "whether to surface a NEEDS_MANUAL_REVIEW flag (NOT_APPLICABLE when no hint is "
            "present); it never asserts a confident exemption on its own."
        ),
    },
]

CONSISTENCY_SEED_RULES: list[SeedRule] = [
    {
        "rule_key": "LMSCAN-CONSISTENCY-MRP",
        "rule_reference": "LM-SCAN cross-source check (Section 14)",
        "title": "MRP consistency: listing vs. product image",
        "description": "Compares the declared MRP on the listing page against the MRP visible in product images.",
        "requirement": "MRP found on the listing page and MRP found via image OCR should agree.",
        "applicability": "Whenever both a listing-page and an image-derived MRP value exist.",
        "exceptions": "Not applicable if only one source has an MRP value.",
        "validation_type": "CONSISTENCY_CHECK",
        "severity": "MAJOR",
        "validator_config": {"field": "mrp"},
        "source_document": CONSISTENCY_SOURCE_DOC,
        "source_locator": "N/A — engineering rule, not a statutory citation",
        "effective_from": "2026-01-01",
        "effective_until": None,
        "notes": None,
    },
    {
        "rule_key": "LMSCAN-CONSISTENCY-NET-QUANTITY",
        "rule_reference": "LM-SCAN cross-source check (Section 14)",
        "title": "Net quantity consistency: listing vs. product image",
        "description": "Compares declared net quantity on the listing page against images.",
        "requirement": "Net quantity found on the listing page and via image OCR should agree.",
        "applicability": "Whenever both sources have a net-quantity value.",
        "exceptions": "Not applicable if only one source has a value.",
        "validation_type": "CONSISTENCY_CHECK",
        "severity": "MAJOR",
        "validator_config": {"field": "net_quantity"},
        "source_document": CONSISTENCY_SOURCE_DOC,
        "source_locator": "N/A — engineering rule, not a statutory citation",
        "effective_from": "2026-01-01",
        "effective_until": None,
        "notes": None,
    },
    {
        "rule_key": "LMSCAN-CONSISTENCY-PRODUCT-NAME",
        "rule_reference": "LM-SCAN cross-source check (Section 14)",
        "title": "Product name consistency: listing vs. product image",
        "description": "Compares the declared product/generic name on the listing page against images.",
        "requirement": "Product name found on the listing page and via image OCR should agree (fuzzy match).",
        "applicability": "Whenever both sources have a product-name value.",
        "exceptions": "Not applicable if only one source has a value.",
        "validation_type": "CONSISTENCY_CHECK",
        "severity": "MINOR",
        "validator_config": {"field": "product_name"},
        "source_document": CONSISTENCY_SOURCE_DOC,
        "source_locator": "N/A — engineering rule, not a statutory citation",
        "effective_from": "2026-01-01",
        "effective_until": None,
        "notes": None,
    },
    {
        "rule_key": "LMSCAN-CONSISTENCY-MANUFACTURER",
        "rule_reference": "LM-SCAN cross-source check (Section 14)",
        "title": "Manufacturer consistency: listing vs. product image",
        "description": "Compares declared manufacturer name on the listing page against images.",
        "requirement": "Manufacturer name found on the listing page and via image OCR should agree (fuzzy match).",
        "applicability": "Whenever both sources have a manufacturer-name value.",
        "exceptions": "Not applicable if only one source has a value.",
        "validation_type": "CONSISTENCY_CHECK",
        "severity": "MAJOR",
        "validator_config": {"field": "manufacturer_name"},
        "source_document": CONSISTENCY_SOURCE_DOC,
        "source_locator": "N/A — engineering rule, not a statutory citation",
        "effective_from": "2026-01-01",
        "effective_until": None,
        "notes": None,
    },
    {
        "rule_key": "LMSCAN-CONSISTENCY-IMPORTER",
        "rule_reference": "LM-SCAN cross-source check (Section 14)",
        "title": "Importer consistency: listing vs. product image",
        "description": "Compares declared importer name on the listing page against images.",
        "requirement": "Importer name found on the listing page and via image OCR should agree (fuzzy match).",
        "applicability": "Whenever both sources have an importer-name value.",
        "exceptions": "Not applicable if only one source has a value.",
        "validation_type": "CONSISTENCY_CHECK",
        "severity": "MAJOR",
        "validator_config": {"field": "importer_name"},
        "source_document": CONSISTENCY_SOURCE_DOC,
        "source_locator": "N/A — engineering rule, not a statutory citation",
        "effective_from": "2026-01-01",
        "effective_until": None,
        "notes": None,
    },
    {
        "rule_key": "LMSCAN-CONSISTENCY-COUNTRY-ORIGIN",
        "rule_reference": "LM-SCAN cross-source check (Section 14)",
        "title": "Country of origin consistency: listing vs. product image",
        "description": "Compares declared country of origin on the listing page against images.",
        "requirement": "Country of origin found on the listing page and via image OCR should agree.",
        "applicability": "Whenever both sources have a country-of-origin value.",
        "exceptions": "Not applicable if only one source has a value.",
        "validation_type": "CONSISTENCY_CHECK",
        "severity": "MAJOR",
        "validator_config": {"field": "country_of_origin"},
        "source_document": CONSISTENCY_SOURCE_DOC,
        "source_locator": "N/A — engineering rule, not a statutory citation",
        "effective_from": "2026-01-01",
        "effective_until": None,
        "notes": None,
    },
]

SEED_RULES = SEED_RULES + CONSISTENCY_SEED_RULES
