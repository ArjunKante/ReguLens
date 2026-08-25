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
        "exceptions": "Not applicable to domestically manufactured products.",
        "validation_type": "CROSS_FIELD_CHECK",
        "severity": "MAJOR",
        "validator_config": {"handler": "country_of_origin_gate"},
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(1)(aa)",
        "effective_from": "2018-01-01",
        "effective_until": None,
        "notes": "Substituted by G.S.R. 629(E) dated 23 June 2017, in force 1.1.2018.",
    },
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
            "patterns": [
                r"\d+(\.\d+)?\s*(g|gm|gram|grams|kg|kgs|kilogram)\b",
                r"\d+(\.\d+)?\s*(ml|millilitre|milliliter|l|lt|ltr|litre|liter)\b",
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
            "patterns": [r"(₹|rs\.?|inr|mrp)\s*\.?\s*\d+(\.\d{1,2})?"],
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
            "'...if available...' for phone/email; because the Source PDF shows both "
            "versions inline, LM-SCAN treats a missing phone/email as NEEDS_MANUAL_REVIEW "
            "and only flags complete absence of any contact route as POTENTIAL_NON_COMPLIANCE."
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
        "validation_type": "MANUAL_REVIEW_CHECK",
        "severity": "MINOR",
        "validator_config": {
            "multipack_hint_patterns": [r"pack of\s*\d+", r"\bx\s*\d+\b", r"\d+\s*x\s*\d+"],
            "reason_default": (
                "LM-SCAN cannot reliably determine multi-unit-pack status from a listing "
                "alone; officer should confirm whether unit sale price disclosure applies."
            ),
            "reason_multipack_hint": (
                "Listing text suggests a multi-unit pack (e.g. 'Pack of N') but no "
                "distinct unit sale price was detected; officer verification requested."
            ),
        },
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 6(11)",
        "effective_from": "2022-10-01",
        "effective_until": None,
        "notes": (
            "Current text inserted by G.S.R. 226(E) dated 28 March 2022 (effective "
            "1.10.2022), superseding an earlier version inserted by G.S.R. 779(E) dated "
            "2 November 2021 (effective 1.4.2022); both reproduced in the Source PDF."
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
        "exceptions": None,
        "validation_type": "PATTERN_CHECK",
        "severity": "MAJOR",
        "validator_config": {
            "any_of_fields": [F.MANUFACTURER_ADDRESS, F.PACKER_ADDRESS, F.IMPORTER_ADDRESS],
            "patterns": [r"\b\d{6}\b", r"\b[A-Za-z\s]+,\s*[A-Za-z\s]+\b"],
        },
        "excluded_categories": [Cat.FOOD.value],
        "source_document": SOURCE_DOC,
        "source_locator": "Rule 10(1), 10(2), Explanation 1",
        "effective_from": "2018-01-01",
        "effective_until": None,
        "notes": "Explanation 1 substituted by G.S.R. 629(E) dated 23 June 2017, in force 1.1.2018.",
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
