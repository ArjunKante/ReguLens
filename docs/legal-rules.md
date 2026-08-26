# Legal Metrology Rules — Structured Rule Database (Source-Traceable)

**Source document:** `legal/Book_on_Legal_Metrology_Packaged_Commodities_Rules,2011_with_all_amendments_whatsnews.pdf`
("the Source PDF") — a consolidated reprint of the **Legal Metrology (Packaged
Commodities) Rules, 2011** (G.S.R. 202(E), dated 7 March 2011, made under the
Legal Metrology Act, 2009), incorporating amendments up to and including
G.S.R. 226(E) dated 28 March 2022 (effective 1 October 2022), as reproduced in
the supplied PDF.

This document is the **only** authoritative legal source used by LM-SCAN V1.
No requirement in the rule database below was invented from general
knowledge — every rule text, exception, and effective date is traced to a
specific passage in the Source PDF. Where the Source PDF is ambiguous or a
provision could not be located with confidence, that is recorded explicitly
under **Limitations / Unsupported Requirements** rather than guessed at.

> ⚠️ This file — and the rule rows derived from it in the database — is a
> **compliance-assistance aid**, not a legal opinion. It condenses statutory
> text into machine-checkable fields for a *preliminary* screening tool. An
> authorized Legal Metrology officer must verify any flagged issue against the
> full text of the Rules (and any State/Central Government notifications not
> reproduced in the Source PDF) before treating it as a violation.

## How to read a rule row

Every rule implemented in `apps/backend/app/rules/seed_rules.py` (which is the
single place rules are loaded into the `rules` / `rule_versions` tables) has:

| Field | Meaning |
|---|---|
| `rule_id` | Stable machine ID, e.g. `LMPC-R6-1A-MFR-NAME` |
| `rule_reference` | The statutory citation, e.g. "Rule 6(1)(a)" |
| `source_document` | Always the Source PDF filename above |
| `source_locator` | Section/rule number as printed in the Source PDF (page numbers in the PDF's own table of contents are cited where useful; the reprint's internal pagination is inconsistent across amendment insertions, so the **rule/sub-rule number is the primary locator**, not a page number) |
| `effective_from` / `effective_until` | Taken from the amendment notification annotations printed inline in the Source PDF (e.g. "w.e.f. 1.1.2018"). Where the Source PDF shows a provision was substituted more than once, the row reflects the **latest substitution** and earlier text is noted under `notes` for historical traceability |
| `applicability` | Conditions under which the rule applies (commodity type, package type, sale channel) drawn from Rule 3, Rule 26 and the specific rule's own text |
| `exceptions` | Carved-out cases (e.g. bidi packages, LPG cylinders, packages ≤10g/10ml) |
| `validation_type` | One of `PRESENCE_CHECK`, `PATTERN_CHECK`, `NUMERIC_CHECK`, `DATE_CHECK`, `CROSS_FIELD_CHECK`, `CONSISTENCY_CHECK`, `MANUAL_REVIEW_CHECK` |
| `severity` | `CRITICAL` / `MAJOR` / `MINOR` — engineering triage weight, **not** a legal penalty classification |

---

## Scope note: why only a subset of the 34 rules is implemented

The Source PDF contains the full Rules 2011 (Chapters I–VII, Rules 1–34, plus
Schedules 1–7). LM-SCAN V1 is scoped to **online listing inspection** (Section
2 of the product brief). Rules that govern physical-premises inspection
procedures (Rules 19–22), export-only packages (Rule 25), wholesale-only
packages (Rules 18, 24), and manufacturer/packer/importer registration (Rules
27–30) are **not** things an officer can evaluate from a marketplace listing
page, so they are catalogued below as **out of scope for V1** rather than
implemented as automated checks. This is a deliberate scope decision, not a
gap — see `docs/limitations.md`.

The rule engine architecture (Section 11 of the brief) is generic
(`PRESENCE_CHECK`, `PATTERN_CHECK`, etc.), so these out-of-scope rules can be
added later without changing the compliance engine, evidence system, or
report generator — only new rows in `seed_rules.py`.

---

## Implemented rules (online-listing-checkable declarations)

### LMPC-R6-1A-MFR-NAME — Manufacturer / packer / importer name & address
- **Reference:** Rule 6(1)(a), as substituted by G.S.R. 629(E) dated 23 June 2017 (in force 1.1.2018); Explanation I–III of Rule 6(1)(a).
- **Source text (substance):** "Every package shall bear ... a definite, plain and conspicuous declaration ... as to (a) the name and address of the manufacturer, or where the manufacturer is not the packer, the name and address of the manufacturer and packer and for any imported package the name and address of the importer shall be mentioned."
- **Applicability:** All retail packages in scope of Chapter II (Rule 3) — i.e. commodity quantity ≤ 25 kg/25 L (unless cement/fertilizer bulk bags), not for industrial/institutional consumers.
- **Exceptions:** Explanation III — for **food articles**, this declaration is instead governed by the Food Safety and Standards Act, 2006, not this Rule (LM-SCAN flags this as `NOT_APPLICABLE` under the LMPC rule for FOOD-category products and records that FSSAI labeling rules apply, which are out of scope of the Source PDF). Rule 26 exemptions (≤10g/10ml, fast food sold by restaurants, certain drug formulations, thread coils) also apply.
- **Validation type:** `PRESENCE_CHECK` (manufacturer OR (manufacturer+packer) OR importer name+address present) combined with a `PATTERN_CHECK` that the value is not just a brand name (heuristic: contains an address-like token — PIN code, "Ltd"/"Pvt"/"India" etc., or comma-separated locality).
- **Severity:** MAJOR.

### LMPC-R6-1AA-COUNTRY-ORIGIN — Country of origin (imported products)
- **Reference:** Rule 6(1)(aa), inserted/substituted by G.S.R. 629(E) dated 23 June 2017 (in force 1.1.2018).
- **Source text:** "The name of the country of origin or manufacture or assembly in case of imported products shall be mentioned on the package."
- **Applicability:** Only when the product is identified (from listing text/images) as imported, or an importer name/address is present without a domestic manufacturer.
- **Validation type:** `CROSS_FIELD_CHECK` — if `importer` is present/declared and `country_of_origin` is absent → issue; if the product is positively identified as domestic (a manufacturer/packer was found and no importer), rule is `NOT_APPLICABLE` for a physical-package-only inspection; if origin cannot be determined at all (no evidence retrieved), the check is `UNABLE_TO_VERIFY` rather than assumed domestic.
- **2026 e-commerce update:** Rule 6(1)(aa) itself remains imported-products-only, but for an *online listing* specifically, current e-commerce policy/practice (per DPIIT's June 2020 direction to e-commerce entities, still standard marketplace practice as of 2026) expects country-of-origin display regardless of import status. For a domestic product with an online listing, the validator checks for a declared country of origin and reports its absence as `NEEDS_MANUAL_REVIEW` (an e-commerce-policy observation) — never as `POTENTIAL_NON_COMPLIANCE` against Rule 6(1)(aa), which does not require it for a domestic product.
- **Severity:** MAJOR.

### LMPC-R6-1B-GENERIC-NAME — Common/generic name of commodity
- **Reference:** Rule 6(1)(b).
- **Source text:** "The common or generic names of the commodity contained in the package ... shall be mentioned."
- **Applicability:** All in-scope retail packages.
- **Validation type:** `PRESENCE_CHECK`.
- **Severity:** MINOR (title/description on marketplace listings almost always carries this; low false-negative risk but retained for completeness).

### LMPC-R6-1C-NET-QUANTITY — Net quantity declaration
- **Reference:** Rule 6(1)(c); general provisions in Rule 11; units/format in Rule 13 (Statement of units — referenced in Source PDF table of contents; full body text of Rule 13 was not reproduced in the extracted excerpt used to build this database, so **format-level** checks beyond "a quantity + standard unit is present" are marked `UNABLE_TO_VERIFY` rather than invented — see Limitations).
- **Source text:** "The net quantity, in terms of the standard unit of weight or measure, of the commodity contained in the package or where the commodity is packed or sold by number, the number of the commodity contained in the package shall be mentioned."
- **Applicability:** All in-scope retail packages.
- **Exceptions:** Rule 26 — packages with net weight/measure ≤10g or ≤10ml are exempt from the Rules entirely (current text, proviso for the 10–20g/ml band was omitted by GSR 784(E) dated 24 Oct 2011; exemption does **not** apply to tobacco/tobacco products per proviso inserted by GSR 385(E) dated 14 May 2015, in force 1.7.2016).
- **Validation type:** `PRESENCE_CHECK` + `PATTERN_CHECK` (numeric value with a recognized unit: g, kg, ml, l/litre, or a count with "N" / "pieces"/"pcs").
- **Severity:** CRITICAL.

### LMPC-R6-1D-MFG-DATE — Month/year of manufacture, pre-packing or import
- **Reference:** Rule 6(1)(d). **Note:** the words "or pre-packed or imported" were **omitted** by G.S.R. 779(E) dated 2 November 2021, effective 1 April 2022 (postponed to 1 October 2022 by G.S.R. 226(E) dated 28 March 2022) — so, for inspections dated on/after **1 October 2022**, the requirement text is simply "month and year in which the commodity is manufactured."
- **Applicability:** All in-scope retail packages, subject to Explanation I/II and Proviso (A) exceptions.
- **Exceptions:** Not required on bidi/incense-stick packages, or 5kg/14.2kg domestic LPG cylinders (Proviso A); food articles are governed by FSS Act rules instead per the food-article proviso; cosmetics governed by Drugs and Cosmetics Rules, 1945.
- **Validation type:** `DATE_CHECK` (month/year format, not a future date, not implausibly old) — `MANUAL_REVIEW_CHECK` fallback because month/year of manufacture is frequently absent from marketplace listing text/images entirely (it is usually only visible on the physical package, which V1 cannot photograph), so an automated PASS is not asserted — see Section 13 status-logic notes below.
- **Severity:** MINOR (checked but defaults toward `NEEDS_MANUAL_REVIEW` rather than `POTENTIAL_NON_COMPLIANCE`, because online sources are known to under-report this field even for compliant physical packages).

### LMPC-R6-1DA-BEST-BEFORE — Best before / use-by date
- **Reference:** Rule 6(1)(da), substituted by G.S.R. 629(E) dated 23 June 2017 (in force 1.1.2018).
- **Source text:** "If a package contains a commodity which may become unfit for human consumption after a period of time, the 'best before or use by the date, month and year' shall also be mentioned on the label."
- **Applicability:** Perishable/consumable commodities — primarily FOOD category. Not applicable if another law already governs the point (proviso), and not applicable to non-perishable goods (HOUSEHOLD/durable COSMETIC items) unless the listing itself claims a shelf life.
- **Validation type:** `DATE_CHECK` for FOOD category; `NOT_APPLICABLE` for categories where perishability is not evident.
- **Severity:** MAJOR for FOOD, NOT_APPLICABLE otherwise.

### LMPC-R6-1E-MRP — Retail sale price (MRP)
- **Reference:** Rule 6(1)(e), as amended by G.S.R. 629(E) dated 23 June 2017 (in force 1.1.2018) and further amended by G.S.R. 779(E)/G.S.R. 226(E) (in force 1.10.2022, replacing the itemised illustrations with the requirement that price be stated "in Indian currency").
- **Source text (current, post 1.10.2022):** retail sale price must be declared, inclusive of all taxes, in Indian currency, rounded per the Rule; illustrative pre-2022 forms were "MRP Rs. xx.xx incl. of all taxes" etc.
- **Applicability:** All in-scope retail packages. Alcoholic beverages/spirituous liquor are governed by State Excise law instead (proviso), unless State law is silent on RSP, in which case these Rules apply. Essential-commodity RSP fixed under the Essential Commodities Act, 1955 prevails if notified (proviso inserted G.S.R. 858(E), 7 Sept 2016).
- **Validation type:** `PRESENCE_CHECK` + `PATTERN_CHECK` (currency symbol/₹/Rs. + numeric value) + `CONSISTENCY_CHECK` against any MRP value found via a second evidence source (webpage vs. image OCR).
- **Severity:** CRITICAL.

### LMPC-R6-2-CONSUMER-CARE — Consumer-care (name/address/phone/email)
- **Reference:** Rule 6(2), substituted by G.S.R. 385(E) dated 14 May 2015 (effective 1.1.2016, compliance dispensed with until 30.6.2016).
- **Source text:** "Every package shall bear the name, address, telephone number, e-mail address ... of the person who can be or the office which can be contacted, in case of consumer complaints."
- **Applicability:** All in-scope retail packages.
- **Validation type:** `PRESENCE_CHECK` for name/address component (`MANUAL_REVIEW_CHECK` fallback for phone/email, since the Rule text does not make e-mail mandatory in all cases — "if available" language appeared in an earlier substituted version — see `notes` below for the textual history) + `PATTERN_CHECK` for phone number / e-mail format when present.
- **Notes on textual history:** an earlier version of Rule 6(2) (pre-2015 text visible in the Source PDF) read "...telephone number, E-mail address, **if available**..."; the 2015 substitution removed "if available" from the printed clause. Because the Source PDF shows both versions inline without a clean single current-text extraction guarantee, LM-SCAN treats a **missing phone or email as NEEDS_MANUAL_REVIEW rather than an automatic MRP-grade violation**, and only flags **complete absence of any consumer-care contact route** (no name, no address, no phone, no email) as `POTENTIAL_NON_COMPLIANCE`.
- **Severity:** MAJOR (complete absence) / MINOR (partial).

### LMPC-R6-10-ECOMMERCE-DISPLAY — E-commerce mandatory display of declarations
- **Reference:** Rule 6(10), substituted by G.S.R. 629(E) dated 23 June 2017, in force **1 January 2018**.
- **Source text:** "An E-Commerce entity shall ensure that the mandatory declarations as specified in sub-rule (1), except the month and year in which the commodity is manufactured or packed, shall be displayed on the digital and electronic network used for e-commerce transactions." Provisos allocate responsibility for correctness of declarations to the manufacturer/seller/dealer/importer where the e-commerce entity is a pure marketplace intermediary meeting the due-diligence conditions listed in the Rule; the Explanation clarifies this does not exempt the physical package itself from carrying the declarations.
- **Why this rule matters for LM-SCAN specifically:** this is the rule that makes an **online listing itself** (not just the physical package) a legally relevant object — i.e., it is the statutory basis for LM-SCAN's entire V1 scope. All of `LMPC-R6-1A` through `LMPC-R6-1E` and `LMPC-R6-2` are cross-referenced by this rule as "mandatory declarations" that must appear **on the listing page**, with the single carve-out that month/year of manufacture need not be shown online.
- **Validation type:** `CROSS_FIELD_CHECK` — orchestrates the individual field rules above against the **webpage source only** (image-only declarations do not satisfy Rule 6(10), since it specifically requires display "on the digital and electronic network").
- **Severity:** CRITICAL.

### LMPC-R6-11-UNIT-SALE-PRICE — Unit sale price
- **Reference:** Rule 6(11), current text inserted by G.S.R. 226(E) dated 28 March 2022, effective 1 October 2022 (superseding an earlier version inserted by G.S.R. 779(E) dated 2 November 2021, effective 1 April 2022 — both versions are reproduced in the Source PDF; the 2022 version is later in time and is treated as current).
- **Source text (current):** unit sale price, in rupees rounded to two decimals, per gram/kg, per cm/metre, per ml/litre, or per number, as applicable; not required where alcoholic-beverage State Excise law applies; **not required where retail sale price equals unit sale price** (i.e., single-unit unbroken packs).
- **Applicability:** Multi-unit packages where RSP ≠ per-unit price is meaningful; single-item packages are exempt per the second proviso.
- **Validation type:** `MANUAL_REVIEW_CHECK` — LM-SCAN cannot reliably determine from a listing alone whether a package is a "multi-unit" pack requiring unit-price disclosure vs. a single-unit pack that is exempt, so this rule is never auto-failed; it is surfaced for officer attention when net quantity phrasing suggests a multi-pack (e.g. "Pack of 3", "x2") and no unit price is found.
- **Severity:** MINOR.

### LMPC-R9-MANNER — Manner of declaration (legible, prominent, correct script)
- **Reference:** Rule 9(1) and 9(4).
- **Source text:** declarations must be "legible and prominent"; numerals of RSP and net-quantity must contrast with the label background; declarations must be in Hindi (Devanagari) or English (other languages permitted in addition).
- **Applicability:** All in-scope packages/listings.
- **Validation type:** `MANUAL_REVIEW_CHECK` — legibility/prominence/contrast is a visual-design judgment call that OCR confidence can *inform* (very low OCR confidence on a required field is weak evidence of a legibility problem) but cannot *decide*; LM-SCAN never auto-fails this rule, it only lowers confidence on other findings when OCR confidence is poor and separately surfaces a note for officer attention.
- **Severity:** MINOR.

### LMPC-R10-NAME-ADDR-FORM — Name/address form and completeness
- **Reference:** Rule 10(1) and 10(2), as amended by G.S.R. 629(E) dated 23 June 2017 (Explanation 1 substitution) and G.S.R. 385(E) dated 14 May 2015.
- **Source text:** requires the manufacturer's/packer's/importer's **complete address** (postal address of factory or registered office, or street/city/state + PIN) sufficient for a consumer to "identify and locate" them; where a commodity is manufactured outside India and packed in India, the package must also show the Indian packer's/importer's name and address on the principal display panel; name must be the actual corporate name or trading name.
- **Applicability:** Same as `LMPC-R6-1A-MFR-NAME`; this rule adds a **completeness** test on top of the presence test.
- **Validation type:** `PATTERN_CHECK` (heuristic address-completeness: looks for a PIN code (6 digits) or city+state token in the address text extracted for manufacturer/packer/importer).
- **Severity:** MAJOR.

### LMPC-R11-QTY-BASIS — Net quantity computed on commodity only
- **Reference:** Rule 11(1)–(3).
- **Source text:** weight of wrappers/materials other than the commodity is excluded from declared net quantity; where the commodity does not vary with environmental conditions, the declared quantity must correspond to what the consumer actually receives ("when packed" qualifiers are disallowed); where negligible variation is expected, quantity must still be declared so the consumer receives not less than the declared quantity.
- **Applicability:** All in-scope packages.
- **Validation type:** `PATTERN_CHECK` — flags the literal string "when packed" (or Hindi/English equivalents) appearing next to a quantity declaration, since the Rule explicitly disallows that qualifier.
- **Severity:** MINOR.

### LMPC-R26-EXEMPT-SMALL — Small-package exemption
- **Reference:** Rule 26(a), together with the tobacco carve-out proviso (G.S.R. 385(E), 14 May 2015, in force 1.7.2016).
- **Source text:** the Rules do not apply at all to a package where net weight/measure is ≤10g or ≤10ml, **except** for tobacco and tobacco products, which remain covered regardless of size.
- **Applicability:** Used by the rule-selection step to mark `LMPC-R6-1A` .. `LMPC-R6-11` as `NOT_APPLICABLE` when the extracted net quantity is ≤10g/10ml and the product is not tobacco.
- **Validation type:** `CROSS_FIELD_CHECK` (gating rule, not a standalone finding).
- **Severity:** N/A (gating logic).

---

## Out of scope for V1 (catalogued, not implemented as automated checks)

| Rule(s) | Subject | Why out of scope for online listing inspection |
|---|---|---|
| Rule 5 (omitted 1.4.2022 per G.S.R. 779(E)/226(E)) | Standard package sizes (2nd Schedule) | Rule was omitted from the Rules effective 1 Oct 2022 per the Source PDF's own amendment note; retained here for historical traceability only. |
| Rule 7 | Principal display panel area/letter-height tables (Table I/II) | Requires physical measurement of the printed panel and numerals — needs the future physical-inspection module (camera/calibration), explicitly out of scope for V1 per the product brief. |
| Rule 8 | Where on the package the declaration must appear, spacing around quantity declaration | Physical layout requirement, not verifiable from a listing page/photo without calibrated measurement. |
| Rules 12–17 | Manner of quantity declaration, units of weight/measure/number, dimensions, sheet counts, container-type dimensions | Rule 13's full body text was not present in the extracted excerpt reviewed (see Limitations); Rules 14–17 concern physical dimensional declarations requiring measurement, deferred to the physical module. |
| Rule 18 | Wholesale/retail dealer obligations at point of sale | Concerns dealer conduct at brick-and-mortar premises, not the online listing itself. |
| Rules 19–22 | Premises inspection procedure, sampling, maximum permissible error determination | These describe the *physical audit procedure* an officer follows at a manufacturer's/packer's premises — this is the future physical-inspection module, not V1. |
| Rule 23 | Deceptive packages — repacking/seizure | An enforcement *action* (seizure/repacking order) following a finding, not a detection rule; LM-SCAN V1 stops at flagging `POTENTIAL_NON_COMPLIANCE` for human decision, consistent with the "not a legally binding autonomous decision maker" mandate. |
| Rule 24 | Wholesale package declarations | Wholesale packages are not the retail/consumer packages typically listed on quick-commerce platforms; deferred. |
| Rule 25 | Export package restrictions | Not applicable to domestic online retail listings. |
| Rules 27–30 | Registration of manufacturers/packers/importers | Registration-status verification would require a separate government registry lookup, not extractable from a product listing; a future integration point, not implemented in V1. |
| Rules 31–34, Schedules 1, 3–7 | Penalties, compounding, repeal/savings, error tables, sampling, equipment | Legal/administrative machinery and physical-measurement schedules; not applicable to automated online declaration screening. |

## Limitations / Unsupported Requirements

1. **Rule 13 (Statement of units of weight, measure or number) full body text** was
   not present in the excerpt of the Source PDF reviewed while building this
   database (only its table-of-contents entry was confirmed). LM-SCAN
   therefore does **not** implement fine-grained unit-format validation (e.g.
   exact permitted unit abbreviations) beyond a basic "numeric value + a
   recognized unit token" pattern check under `LMPC-R6-1C-NET-QUANTITY`. This
   is a known gap, not a silently invented rule — flagged here per the
   "document the uncertainty" instruction.
2. **Table I / Table II numeral-height requirements (Rule 7)** cannot be
   evaluated from marketplace listing text or a flat product photo without
   calibrated physical measurement (this is precisely the future physical
   module's job) — not implemented in V1, as noted in the out-of-scope table.
3. **Second, Third, Fourth Schedules** (standard package sizes, quantity
   declaration tables, Rule 12(2) exceptions) were not extracted in full
   structured form; where a rule's applicability might depend on them, LM-SCAN
   defaults to `UNABLE_TO_VERIFY` or `MANUAL_REVIEW_CHECK` rather than guessing.
4. Amendment notifications are reproduced in the Source PDF as inline
   footnote-style annotations rather than a clean changelog; where two
   substitutions of the same sub-rule appear, this document takes the one
   whose effective date is latest, and records the earlier text in the rule's
   `notes` field for audit purposes (see `LMPC-R6-11-UNIT-SALE-PRICE` and
   `LMPC-R6-2-CONSUMER-CARE` above for worked examples).
5. This document reflects only the Legal Metrology (Packaged Commodities)
   Rules, 2011 as consolidated in the Source PDF. It does **not** cover
   FSSAI labeling regulations, Drugs & Cosmetics Rules, BIS standards, or any
   State-level notification not reproduced in the Source PDF — these are
   referenced by cross-pointer (e.g. "food articles are governed by the FSS
   Act instead") but not independently implemented, because no such source
   document was supplied in `/legal/`.

## Traceability

Every row above maps 1:1 to a Python dict in
`apps/backend/app/rules/seed_rules.py::SEED_RULES`, which is loaded into the
`rules`/`rule_versions` tables by `apps/backend/app/rules/loader.py`. The
`rule_reference` and `source_document` fields on that model are populated
verbatim from the table above, so every automated finding an inspector sees
in the UI carries a citation back to this document and, through it, to the
Source PDF.
