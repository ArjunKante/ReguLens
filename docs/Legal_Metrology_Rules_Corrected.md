# Legal Metrology Rules — Corrected Structured Rule Database

## Source and legal basis

**Source PDF:** `d91ce802-30ed-4e80-a662-afad00cd4c90.pdf`

This database is based **only on the supplied consolidated PDF** of the **Legal Metrology (Packaged Commodities) Rules, 2011 with amendments reproduced in that PDF**.

The supplied PDF records, among other amendments, G.S.R. 629(E) dated 23 June 2017 and G.S.R. 226(E) dated 28 March 2022. The latter moved the relevant 2021 amendment effective date to **1 October 2022**.

> **Important:** This file is a compliance-assistance database for a screening system. It is not a legal opinion. A Legal Metrology officer should verify any flagged case against the complete applicable law, notifications and product-specific legislation.

---

# 1. Database model

Each rule record used by LM-SCAN should contain:

| Field | Meaning |
|---|---|
| `rule_id` | Stable machine identifier |
| `rule_reference` | Statutory rule/sub-rule reference |
| `source_document` | Supplied Legal Metrology PDF |
| `source_locator` | Rule/sub-rule and PDF page |
| `effective_from` | Effective date of current version represented |
| `effective_until` | End date where known |
| `title` | Human-readable rule title |
| `requirement` | What the rule requires |
| `applicability` | Conditions under which the rule applies |
| `exceptions` | Express exclusions/exemptions |
| `validation_type` | Automated, cross-field or manual validation method |
| `severity` | Engineering triage weight only |
| `status` | `IMPLEMENTED`, `MANUAL_REVIEW`, `OUT_OF_SCOPE`, or `NOT_APPLICABLE` |
| `notes` | Historical/amendment/automation notes |

### Validation types

- `PRESENCE_CHECK`
- `PATTERN_CHECK`
- `NUMERIC_CHECK`
- `DATE_CHECK`
- `CROSS_FIELD_CHECK`
- `CONSISTENCY_CHECK`
- `MANUAL_REVIEW_CHECK`

`severity` is an engineering priority and **must not be presented as a statutory penalty classification**.

---

# 2. Scope of LM-SCAN V1

The supplied project design targets inspection of **online/e-commerce product listings**, with package images used as supporting evidence.

The following are suitable for online screening:

- Rule 3 applicability
- Rule 6 declaration checks
- Rule 6(10) e-commerce display
- Rule 6(11) unit sale price
- Rule 9 visual/readability checks as review items
- Rule 10 name/address completeness
- Rule 11 quantity-basis checks
- Rule 26 applicability/exemption gating
- Rule 31 advertisement checks

The following should **not** be falsely claimed as fully automated from an ordinary marketplace listing:

- physical principal-display-panel dimensions and numeral heights under Rule 7
- physical declaration placement/spacing under Rule 8
- physical quantity verification and maximum permissible error under Rules 19–22
- wholesale-package compliance where only a retail listing is supplied
- registration-status verification under Rules 27–30 without a registry integration
- legal enforcement actions under Rule 23
- exact Schedule-dependent physical measurements

These may be represented as `MANUAL_REVIEW` or `OUT_OF_SCOPE`.

---

# 3. Rule 3 — Applicability of Chapter II

## `LMPC-R3-APPLICABILITY`

**Reference:** Rule 3

**Source:** PDF page 9, Rule 3.

### Requirement

Chapter II does not apply to:

1. packages containing a quantity of more than **25 kg or 25 litre**;
2. **cement, fertilizer and agricultural farm produce sold in bags above 50 kg**;
3. packaged commodities meant for **industrial consumers or institutional consumers**.

The current text shown in the PDF was substituted/amended by G.S.R. 629(E), effective 1 January 2018.

### Correct machine logic

```text
if package_quantity > 25 kg or > 25 litre:
    NOT_APPLICABLE

except:
    cement/fertilizer/agricultural farm produce in bags > 50 kg
    -> NOT_APPLICABLE

if industrial_consumer:
    NOT_APPLICABLE

if institutional_consumer:
    NOT_APPLICABLE
```

### Important correction

Do **not** implement the rule as simply:

```text
quantity <= 25 kg / 25 litre
```

because the PDF separately provides the **above-50-kg condition for cement, fertilizer and agricultural farm produce**.

---

# 4. Rule 6 — Declarations to be made on every package

## `LMPC-R6-1A-MFR-NAME`

**Reference:** Rule 6(1)(a)

**Source:** PDF pages 11–12.

### Requirement

Every package must bear a definite, plain and conspicuous declaration relating to:

- name and address of the manufacturer;
- where the manufacturer is not the packer, name and address of the manufacturer and packer;
- for imported packages, name and address of the importer.

### Validation

`PRESENCE_CHECK` + `PATTERN_CHECK`

### Correct interpretation

The scanner may detect the presence of manufacturer/packer/importer information, but **responsibility between entities** should remain evidence-backed and reviewable.

### Food exception

The PDF states that for packages containing food articles, this particular clause is governed instead by the **Food Safety and Standards Act, 2006 and its rules**.

LM-SCAN should therefore label its Rule 6(1)(a) result as `NOT_APPLICABLE` where the product is confidently classified as food and should state that food-labelling compliance is outside this rule dataset.

---

## `LMPC-R6-1AA-COUNTRY-ORIGIN`

**Reference:** Rule 6(1)(aa)

**Source:** PDF page 11.

### Requirement

For imported products, the **name of the country of origin or manufacture or assembly** must be mentioned on the package.

### Validation

`CROSS_FIELD_CHECK`

### Machine logic

```text
if imported_product:
    if country_of_origin is absent:
        POTENTIAL_NON_COMPLIANCE
    else:
        PASS
else:
    NOT_APPLICABLE
```

Do not decide that a product is imported solely because the brand sounds foreign. Use available listing/package evidence.

---

## `LMPC-R6-1B-GENERIC-NAME`

**Reference:** Rule 6(1)(b)

**Source:** PDF page 11.

### Requirement

The **common or generic name** of the commodity must be mentioned.

For a package containing more than one product, the **name and number or quantity of each product** must be mentioned.

### Validation

`PRESENCE_CHECK`

---

## `LMPC-R6-1C-NET-QUANTITY`

**Reference:** Rule 6(1)(c)

**Source:** PDF page 12.

### Requirement

The net quantity must be declared:

- by the standard unit of weight or measure; or
- by number where the commodity is packed or sold by number.

### Validation

`PRESENCE_CHECK` + `PATTERN_CHECK`

### Suggested extraction patterns

Examples:

```text
500 g
1 kg
250 ml
1 litre
6 pieces
Pack of 6
```

The exact statutory unit-format rules should not be invented here. Detailed unit-format validation belongs to Rule 13 and the relevant provisions/schedules.

---

## `LMPC-R6-1D-MFG-DATE`

**Reference:** Rule 6(1)(d)

**Source:** PDF page 12.

### Current version represented by the PDF

The PDF records that the words **“or pre-packed or imported”** were omitted by G.S.R. 779(E), with the effective date moved to **1 October 2022** by G.S.R. 226(E).

Therefore, for the current version represented here, the declaration is the **month and year in which the commodity is manufactured**.

### Validation

`DATE_CHECK`

### Exceptions recorded in the PDF

No declaration of month and year applies to:

- bidi or incense-stick packages;
- 5 kg or 14.2 kg domestic LPG cylinders bottled and marketed by a public-sector undertaking.

The PDF also points to other laws for food and cosmetics.

### E-commerce point

Rule 6(10) separately excludes the month/year manufacturing declaration from the mandatory **online display** requirement.

Therefore:

```text
physical_package_check:
    manufacturing month/year -> applicable subject to exceptions

ecommerce_listing_check:
    manufacturing month/year -> NOT_REQUIRED_BY_RULE_6_10
```

---

## `LMPC-R6-1DA-BEST-BEFORE`

**Reference:** Rule 6(1)(da)

**Source:** PDF pages 12–13.

### Requirement

Where a package contains a commodity that may become unfit for human consumption after a period of time, the label must mention:

- the best-before date, month and year; or
- the use-by date, month and year.

The provision does not apply where another law makes a provision for the same matter.

### Validation

`DATE_CHECK`

### Scope

For food products, LM-SCAN should coordinate with the applicable FSSAI requirements rather than pretending that this Legal Metrology rule alone is the complete food-labelling standard.

---

## `LMPC-R6-1E-MRP`

**Reference:** Rule 6(1)(e)

**Source:** PDF page 13.

### Requirement

The retail sale price is the **maximum price** at which the packaged commodity may be sold to the consumer, **inclusive of all taxes**, and the current version represented in the PDF requires it to be stated **in Indian currency**.

### Validation

`PRESENCE_CHECK` + `PATTERN_CHECK` + optional `CONSISTENCY_CHECK`

### Examples that may be recognized

```text
MRP ₹100
MRP Rs. 100
Maximum Retail Price ₹100
```

Do not require one exact string; the rule is about the required declaration, not a single OCR phrase.

### Exceptions/qualifications

The PDF states:

- alcoholic beverages/spirituous liquor are subject to State Excise law; the LMPC rule applies where the State law does not provide for retail sale price;
- an RSP fixed and notified for an essential commodity under the Essential Commodities Act prevails.

---

# 5. Rule 6(2) — Consumer-care details

## `LMPC-R6-2-CONSUMER-CARE`

**Reference:** Rule 6(2)

**Source:** PDF page 13.

### Current requirement

The current substituted text shown in the PDF states that every package shall bear the:

- **name**
- **address**
- **telephone number**
- **e-mail address**

of the person or office that can be contacted in case of consumer complaints.

### Correct validation

`PRESENCE_CHECK` + `PATTERN_CHECK`

### IMPORTANT CORRECTION

The database must **not** treat telephone number or e-mail as legally optional merely because an older version visible in the PDF contains the phrase **“if available”**.

The older wording is historical text. The PDF separately shows the 2015 substituted version without that phrase.

Therefore the current rule represented by the PDF should be modelled as:

```text
consumer_care.name       = REQUIRED
consumer_care.address    = REQUIRED
consumer_care.phone      = REQUIRED
consumer_care.email      = REQUIRED
```

OCR uncertainty may still result in:

```text
NEEDS_MANUAL_REVIEW
```

rather than an automatic legal conclusion.

---

# 6. Rule 6(10) — E-commerce display

## `LMPC-R6-10-ECOMMERCE-DISPLAY`

**Reference:** Rule 6(10)

**Source:** PDF page 15.

### Requirement

An e-commerce entity must ensure that mandatory declarations specified in Rule 6(1), **except the month and year in which the commodity is manufactured or packed**, are displayed on the digital and electronic network used for e-commerce transactions.

### Key point for LM-SCAN

This is the central provision that makes an e-commerce listing a compliance object.

### Online checks

For an ordinary in-scope listing, LM-SCAN should check the online display of the relevant Rule 6(1) declarations, including:

- manufacturer/packer/importer information;
- country of origin for imported products;
- common/generic name;
- net quantity;
- best-before/use-by where applicable;
- retail sale price;
- consumer-care information.

### Manufacturing month/year

Do **not** fail an e-commerce listing solely because the manufacturing month/year is absent from the webpage under Rule 6(10).

### Marketplace responsibility

The PDF contains provisos dealing with responsibility in a marketplace model and intermediary conditions.

LM-SCAN should report the **declaration finding and evidence**, not automatically assign legal liability to the marketplace unless the relevant conditions have been established.

---

# 7. Rule 6(11) — Unit sale price

## `LMPC-R6-11-UNIT-SALE-PRICE`

**Reference:** Rule 6(11)

**Source:** PDF pages 16–17.

### Current version

The PDF shows the 2022 substituted version effective **1 October 2022**.

The unit sale price is expressed in rupees, rounded to **two decimal places**, using the applicable basis prescribed by the rule.

The PDF specifies bases including:

- per gram / per kilogram for quantity by weight;
- per centimetre / per metre for length;
- per millilitre / per litre for volume;
- per number/unit where an item is sold by number.

### Explicit exception

The PDF states that unit sale price is **not required where the retail sale price is equal to the unit sale price**.

### IMPORTANT CORRECTION

Do **not** hard-code:

```text
single item = automatically exempt
```

That is an interpretation that does not follow directly from the stated exception.

### Recommended validation

`MANUAL_REVIEW_CHECK` with deterministic assistance:

```text
if applicable_under_rule_6_11:
    if retail_sale_price == unit_sale_price:
        PASS / NOT_REQUIRED
    elif unit_sale_price missing:
        NEEDS_MANUAL_REVIEW or POTENTIAL_NON_COMPLIANCE
```

The applicability decision can depend on the nature of the packaged commodity and its declared pricing structure.

---

# 8. Rule 9 — Manner in which declaration shall be made

## `LMPC-R9-MANNER`

**Reference:** Rule 9(1), Rule 9(4)

**Source:** PDF pages 20–22.

### Requirements

Declarations must be:

- **legible and prominent**.

The numerals of:

- retail sale price; and
- net quantity

must be printed, painted or inscribed in a colour that contrasts conspicuously with the label background, subject to the exceptions stated in the rule.

The PDF also states that declarations must be in:

- Hindi in Devanagari script; or
- English.

Other languages may be used in addition.

### Validation

`MANUAL_REVIEW_CHECK`

### Reason

OCR confidence can help indicate possible readability problems, but ordinary OCR cannot legally determine all questions of legibility, prominence and contrast.

---

# 9. Rule 10 — Name and address

## `LMPC-R10-NAME-ADDR-FORM`

**Reference:** Rule 10(1) and Rule 10(2)

**Source:** PDF pages 21–22.

### Requirement

Every package kept, offered, exposed for sale or sold must bear conspicuously:

- name and complete address of manufacturer;
- where manufacturer is not packer, manufacturer and packer;
- for imported packages, importer name and address.

The PDF also provides a special provision for packages of capacity **10 cubic centimetres or less**, where a mark/inscription enabling the consumer to identify the relevant party may be sufficient.

### Complete-address explanation

The PDF explains complete address in terms sufficient for the consumer to **identify and locate** the manufacturer/packer/importer, including the relevant premises/street/city/state/PIN information specified there.

### Important correction

Do **not** implement:

```text
PIN OR city+state = complete address
```

as a universal legal test.

Instead use a layered heuristic:

```text
address_present
    AND
address_is_location_identifiable
    AND
required locality/address components appear where applicable
```

and send uncertain cases to manual review.

### Shorter address

Rule 28 allows a manufacturer/packer to apply for registration of a shorter address where the authority is satisfied that it is sufficient.

Therefore a scanner should **not automatically fail every address that is shorter than the ordinary address pattern**.

---

# 10. Rule 11 — General provisions relating to quantity

## `LMPC-R11-QTY-BASIS`

**Reference:** Rule 11(1)–(3)

**Source:** PDF page 22.

### Requirements

1. Wrappers and materials other than the commodity are excluded from net quantity.
2. Where the commodity is not likely to vary because of environmental conditions, the declared quantity must correspond to what the consumer will receive.
3. In the relevant cases, the declaration must not be qualified by words such as **“when packed”**.

### Validation

`PATTERN_CHECK`

Possible finding:

```text
quantity declaration contains "when packed"
    -> POTENTIAL_NON_COMPLIANCE / REVIEW
```

The scanner should not attempt to determine the actual net quantity deficiency from a listing photograph alone.

---

# 11. Rule 26 — Exemptions

## `LMPC-R26-EXEMPT-SMALL`

**Reference:** Rule 26(a)

**Source:** PDF pages 35–36.

### Small-package exemption

The Rules do not apply to a package where the net weight or measure is:

- **10 grams or less**, or
- **10 millilitres or less**,

when sold by weight or measure.

### Tobacco exception

The PDF expressly states that this exemption does **not** apply to tobacco and tobacco products.

### Important historical note

The PDF contains an older 10g–20g / 10ml–20ml proviso, and explicitly marks it as omitted by G.S.R. 784(E). That old proviso must **not** be implemented as current law.

---

## `LMPC-R26-EXEMPT-FAST-FOOD`

**Reference:** Rule 26(b)

The Rules do not apply to a package containing fast food items packed by a restaurant or hotel and the like.

### Validation

`CROSS_FIELD_CHECK`

---

## `LMPC-R26-EXEMPT-DRUG-FORMULATIONS`

**Reference:** Rule 26(c)

The PDF states that certain scheduled and non-scheduled formulations covered by the **Drugs (Price Control) Order, 2013** are exempt.

The PDF also states:

> No exemption shall be applicable to medical devices declared as drugs.

### Validation

`MANUAL_REVIEW_CHECK`

Do not classify a product as a qualifying drug formulation using OCR keywords alone.

---

## Agricultural farm produce — IMPORTANT CORRECTION

The supplied PDF shows that **Rule 26(d)**, which previously contained an agricultural farm produce exemption, was **omitted** by G.S.R. 629(E), effective 1 January 2018.

Therefore:

```text
Rule 26(d) agricultural-farm-produce exemption
= NOT CURRENTLY IMPLEMENTED
```

Agricultural farm produce instead appears in the **Rule 3 applicability gate**, where the Chapter II threshold is treated separately for bags above 50 kg.

This distinction is important.

---

## `LMPC-R26-EXEMPT-THREAD-COIL`

**Reference:** Rule 26(e)

The PDF states that the Rules do not apply to **thread sold in coil to handloom weavers**.

### Validation

`MANUAL_REVIEW_CHECK`

because the specific transaction/use condition is unlikely to be established reliably from OCR alone.

---

# 12. Rule 31 — Advertisement mentioning retail sale price

## `LMPC-R31-ADVERTISEMENT-NET-QTY`

**Reference:** Rule 31(1)–(2)

**Source:** PDF page 37.

### Requirement

Any advertisement mentioning the retail sale price of a pre-packaged commodity must also contain a declaration of:

- the net quantity; or
- the number of the commodity contained in the package.

The PDF further states that the **font size of the net quantity in the advertisement shall be the same as that of the retail sale price**.

### Why this is important for LM-SCAN

Because the system examines online commerce and listing/advertising content, Rule 31 should not be buried under “out of scope”.

### Validation

`PRESENCE_CHECK` for net quantity/number.

`MANUAL_REVIEW_CHECK` for exact font-size equality unless reliable webpage DOM/CSS measurement is available.

### Machine logic

```text
if advertisement_mentions_RSP:
    if net_quantity_or_number absent:
        POTENTIAL_NON_COMPLIANCE
    else:
        PASS

    font_size_equality:
        REVIEW
```

---

# 13. Rules intentionally not automated from an ordinary online listing

## Rule 7 — Principal display panel

Rule 7 deals with:

- principal display panel;
- numeral/letter height;
- Table I / Table II requirements.

The PDF places these requirements on the physical package.

**Status:** `MANUAL_REVIEW` / `OUT_OF_SCOPE` for ordinary online-only inspection.

A calibrated physical-inspection module may implement them later.

---

## Rule 8 — Declaration where to appear

Rule 8 requires declarations to appear on the principal display panel and imposes spacing around the quantity declaration.

This is a physical-layout requirement.

**Status:** `MANUAL_REVIEW` / `OUT_OF_SCOPE` for ordinary online-only inspection.

---

## Rules 12–17

These cover matters including:

- manner of quantity declaration;
- statement of units;
- dimensions;
- special quantity/dimensional declarations;
- usable sheet counts;
- container-type commodities.

These should be implemented only where the exact applicable provision and schedule data are available.

**Status:** `MANUAL_REVIEW` / `OUT_OF_SCOPE` where the online evidence is insufficient.

Do not invent fine-grained unit rules where the source extraction is incomplete.

---

## Rule 18 — Wholesale/retail dealer provisions

These concern dealer obligations.

**Status:** `OUT_OF_SCOPE` for a scanner limited to retail e-commerce listing declarations.

---

## Rules 19–22 — Inspection and physical quantity/error determination

The PDF describes:

- inspection at manufacturer/packer premises;
- sampling;
- testing;
- maximum permissible error;
- inspection results and corrective action.

These require physical packages, samples and specified procedures.

**Status:** `OUT_OF_SCOPE` for an online listing-only V1.

---

## Rule 23 — Deceptive packages

Rule 23 concerns enforcement action such as repacking/seizure.

The scanner may provide evidence and flag a potential issue, but should not autonomously execute or declare a legal enforcement action.

**Status:** `MANUAL_REVIEW`.

---

## Rule 24 — Wholesale package declarations

Rule 24 concerns wholesale packages.

It is outside a retail e-commerce listing scanner unless the input is specifically a wholesale package.

**Status:** `OUT_OF_SCOPE` / conditional module.

---

## Rule 25 — Export packages

Rule 25 concerns restrictions on sale of export packages in India.

A domestic retail listing scanner generally cannot establish all export-package facts from a listing alone.

**Status:** `MANUAL_REVIEW` / `OUT_OF_SCOPE`.

---

## Rules 27–30 — Registration

These rules concern registration of manufacturers, packers and importers.

Registration status cannot be proven merely from package OCR.

**Status:** `OUT_OF_SCOPE` until a government-registration lookup is integrated.

---

# 14. Schedules

The supplied PDF includes schedules dealing with:

- maximum permissible errors;
- quantity declarations;
- exceptions;
- sampling;
- determination of quantity;
- equipment;
- inspection data sheets.

These are important for physical inspection, but they should not be reduced to simplistic online checks.

### Recommended status

```text
Schedules requiring physical/sample measurement
    -> OUT_OF_SCOPE for online-only V1

Schedule-dependent legal determination
    -> MANUAL_REVIEW or UNABLE_TO_VERIFY
```

---

# 15. Corrected rule-selection flow

LM-SCAN should select rules in this order:

```text
INPUT
  |
  v
Identify package / listing
  |
  v
Determine sale channel
  |
  +---- not retail/e-commerce scope ----> appropriate module/review
  |
  v
Rule 3 applicability gate
  |
  +---- exempt from Chapter II ----> NOT_APPLICABLE
  |
  v
Determine product category
  |
  +---- food ----> apply LMPC rules only where they remain applicable;
  |                use FSSAI for food-specific requirements
  |
  +---- cosmetic/drug/etc. ----> account for stated cross-references
  |
  v
Rule 26 exemption gate
  |
  +---- exempt ----> NOT_APPLICABLE
  |
  v
Extract declarations
  |
  v
Apply Rule 6 declaration checks
  |
  +---- imported ----> country-of-origin cross-check
  |
  v
Rule 6(10) e-commerce display check
  |
  +---- manufacturing month/year is NOT failed online
  |
  v
Rule 6(11) unit sale price
  |
  v
Rule 9 visual/readability review
  |
  v
Rule 10 address completeness
  |
  v
Rule 11 quantity-basis check
  |
  v
Rule 31 advertisement check
  |
  v
Evidence + confidence
  |
  v
PASS / POTENTIAL_NON_COMPLIANCE / NEEDS_MANUAL_REVIEW / NOT_APPLICABLE /
UNABLE_TO_VERIFY
```

---

# 16. Corrected automated-check policy

The scanner should distinguish between **missing evidence** and **proven non-compliance**.

### Recommended result meanings

| Result | Meaning |
|---|---|
| `PASS` | Required information was found and the automated check succeeded |
| `POTENTIAL_NON_COMPLIANCE` | Evidence suggests a likely violation |
| `NEEDS_MANUAL_REVIEW` | The rule may apply but the available evidence is insufficient for an automated conclusion |
| `NOT_APPLICABLE` | The rule does not apply based on established facts |
| `UNABLE_TO_VERIFY` | The source/evidence is insufficient to evaluate the requirement |

Do not treat low OCR confidence by itself as proof of a legal violation.

---

# 17. Corrected implementation summary

| Rule | Subject | V1 treatment |
|---|---|---|
| Rule 3 | Chapter II applicability | `IMPLEMENTED` |
| 6(1)(a) | Manufacturer/packer/importer | `IMPLEMENTED` |
| 6(1)(aa) | Country of origin | `IMPLEMENTED` |
| 6(1)(b) | Generic name | `IMPLEMENTED` |
| 6(1)(c) | Net quantity | `IMPLEMENTED` |
| 6(1)(d) | Manufacturing month/year | `IMPLEMENTED` + review when not visible |
| 6(1)(da) | Best-before/use-by | `IMPLEMENTED` where applicable |
| 6(1)(e) | MRP | `IMPLEMENTED` |
| 6(2) | Consumer care | `IMPLEMENTED` |
| 6(10) | E-commerce declarations | `IMPLEMENTED` |
| 6(11) | Unit sale price | `MANUAL_REVIEW` with automated assistance |
| 7 | Physical font/PD panel | `OUT_OF_SCOPE` |
| 8 | Physical placement/spacing | `OUT_OF_SCOPE` |
| 9 | Legibility/prominence/script | `MANUAL_REVIEW` |
| 10 | Address completeness | `IMPLEMENTED` + manual fallback |
| 11 | Quantity basis | `IMPLEMENTED` |
| 12–17 | Quantity/unit/dimension specifics | `MANUAL_REVIEW` / `OUT_OF_SCOPE` |
| 18 | Dealer obligations | `OUT_OF_SCOPE` |
| 19–22 | Physical inspection/error | `OUT_OF_SCOPE` |
| 23 | Enforcement action | `MANUAL_REVIEW` |
| 24 | Wholesale packages | `OUT_OF_SCOPE` |
| 25 | Export packages | `OUT_OF_SCOPE` |
| 26(a) | ≤10g/10ml exemption | `IMPLEMENTED` |
| 26(b) | Restaurant/hotel fast food | `IMPLEMENTED`/conditional |
| 26(c) | Certain drug formulations | `MANUAL_REVIEW` |
| 26(d) | Agricultural farm produce | **OMITTED in current text** |
| 26(e) | Thread coil to handloom weavers | `MANUAL_REVIEW` |
| 27–30 | Registration | `OUT_OF_SCOPE` |
| 31 | RSP advertisement + net quantity | `IMPLEMENTED` + font review |
| 32–34 | Penalty/compounding/relaxation/repeal | `OUT_OF_SCOPE` for detection engine |
| Schedules | Physical/sample/error tables | `OUT_OF_SCOPE` / `MANUAL_REVIEW` |

---

# 18. Important corrections from the previous database

The following earlier statements must not be retained:

### Correction 1 — Rule 6(2)

**Old approach:** missing phone/e-mail could be treated as legally optional because older PDF wording said “if available”.

**Correct approach:** the current substituted wording represented in the PDF requires name, address, telephone number and e-mail address. The old wording is historical.

---

### Correction 2 — Rule 10

**Old approach:**

```text
PIN OR city+state = complete address
```

**Correct approach:** use a fuller address-identifiability heuristic and allow manual review, including the Rule 28 shorter-address possibility.

---

### Correction 3 — Rule 6(11)

**Old approach:**

```text
single item = exempt
```

**Correct approach:** use the express exception shown in the rule: unit sale price is not required where the **retail sale price is equal to the unit sale price**. Do not invent a blanket single-item exemption.

---

### Correction 4 — Rule 3

**Old approach:** only a simple 25 kg/25 litre gate.

**Correct approach:** also handle the separate **above-50-kg rule for cement, fertilizer and agricultural farm produce** and industrial/institutional consumers.

---

### Correction 5 — Rule 26(d)

**Old approach:** agricultural farm produce treated as a Rule 26 exemption.

**Correct approach:** the supplied PDF shows Rule 26(d) was omitted by G.S.R. 629(E). Agricultural farm produce is instead addressed in the amended Rule 3 applicability provision.

---

### Correction 6 — Rule 31

**Old approach:** grouped with out-of-scope Rules 31–34.

**Correct approach:** Rule 31 is highly relevant to an online/advertising scanner because it expressly regulates advertisements that mention retail sale price.

---

# 19. Source limitations

This database is intentionally conservative.

The supplied PDF is a consolidated reproduction containing historical text and amendment annotations. Therefore:

1. the latest effective text shown in the PDF is used for current-rule modelling;
2. old text that is visibly struck through or identified as substituted/omitted is treated as historical;
3. missing extraction of a detailed provision must not be replaced with guessed requirements;
4. product-specific laws such as FSSAI and Drugs & Cosmetics requirements are referenced where the LMPC Rules point to them, but are not silently implemented as LMPC rules;
5. visual and physical requirements should be reported as `MANUAL_REVIEW` unless the system has adequate calibrated evidence.

---

# 20. Traceability requirement

Every finding produced by LM-SCAN should retain:

```text
rule_id
rule_reference
source_document
source_locator
evidence_source
extracted_value
validation_result
confidence
timestamp
review_status
```

This keeps the result traceable from:

```text
Product
  -> extracted declaration
  -> rule
  -> evidence
  -> compliance result
```

The website should present these results as **AI-assisted compliance screening**, not as an autonomous statutory/legal decision.

