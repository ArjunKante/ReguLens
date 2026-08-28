"""Unit tests for app.nlp.patterns (P0 audit fix: "manufacturer/packer/
importer validation logic" — manufacturer_address/packer_address/
importer_address previously had no extractor at all, so
LMPC-R6-1A-MFR-NAME and LMPC-R10-NAME-ADDR-FORM (both of which require an
address field) could never PASS regardless of how complete a package's
declaration was)."""
from __future__ import annotations

from app.nlp.patterns import find_field_candidates
from app.rules import fields as F
from app.rules.quantity import parse_net_quantity


def _values_for(text: str, field: str) -> list[str]:
    return [m.value for m in find_field_candidates(text) if m.field_name == field]


def test_manufacturer_name_and_address_extracted_from_real_label_wording():
    # Real packaging text (from a genuine Lay's packet back-of-pack OCR
    # capture), which previously matched neither "manufactured by" nor
    # "manufacturer" at all.
    text = "Mfg. & Mktg. by: PEPSICO INDIA HOLDINGS PVT. LTD., P.O. BOX 27, DLF QUTAB ENCLAVE, PHASE-1, GURUGRAM - 122002, HARYANA, INDIA."
    names = _values_for(text, F.MANUFACTURER_NAME)
    addresses = _values_for(text, F.MANUFACTURER_ADDRESS)
    assert names and "PEPSICO" in names[0].upper()
    assert addresses, "expected an address candidate once a 6-digit PIN code follows the name"
    assert "122002" in addresses[0]


def test_manufacturer_name_rejects_an_adjacent_license_number_line():
    """Real Parle biscuit label OCR: "MFD.BY:" sits on its own line
    immediately above a closely-spaced "FSSAI LIC. No.: 1013022002253"
    line — close enough that OCR line-reconstruction reads them as
    adjacent, so the value right after "MFD.BY:" is the license number,
    not a name. No real company name starts with "LIC."/"FSSAI"/etc., so
    this must be rejected rather than reported as the manufacturer."""
    text = "MFD.BY: LIC. No.: 1013022002253 (NT)- SUNSHINE BAKERY FOODS PVT LTD, 333/1 BATLAGUNDU ROAD, NILAKOTTAI, TN - 624208"
    assert not _values_for(text, F.MANUFACTURER_NAME)
    # A genuine name right after the keyword must still work.
    assert _values_for("MFD.BY: Acme Foods Pvt Ltd", F.MANUFACTURER_NAME) == ["Acme Foods Pvt Ltd"]


def test_manufacturer_abbreviations_mfd_and_mfg_by_are_recognized():
    assert _values_for("Mfd by: Acme Foods Ltd", F.MANUFACTURER_NAME)
    assert _values_for("Mfg by: Acme Foods Ltd", F.MANUFACTURER_NAME)
    assert _values_for("Manufactured by: Acme Foods Ltd", F.MANUFACTURER_NAME)


def test_no_address_candidate_when_no_pin_code_follows_the_name():
    text = "Manufactured by: Acme Foods Ltd, Some Street, Some City"
    assert _values_for(text, F.MANUFACTURER_NAME)
    assert not _values_for(text, F.MANUFACTURER_ADDRESS)


def test_packer_and_importer_address_extraction():
    packer_text = "Packed by: Acme Packers Pvt Ltd, Industrial Area, Pune - 411001, Maharashtra"
    assert _values_for(packer_text, F.PACKER_NAME)
    assert _values_for(packer_text, F.PACKER_ADDRESS)

    importer_text = "Imported by: Global Traders Pvt Ltd, MG Road, Bengaluru - 560001, Karnataka"
    assert _values_for(importer_text, F.IMPORTER_NAME)
    assert _values_for(importer_text, F.IMPORTER_ADDRESS)


# --- Demo Hardening regressions: found live, against real Flipkart listing text ---


def test_manufacturer_bare_noun_without_separator_is_not_matched():
    """Live-listing test found this matching Flipkart's "Manufacturer info"
    details-panel section label (a UI toggle, not a name:value pair) as
    manufacturer_name="info". The bare noun form now requires an explicit
    colon/dash separator; "by"-anchored phrasings are unaffected."""
    assert not _values_for("Manufacturer info | In the Box | Pack", F.MANUFACTURER_NAME)
    assert not _values_for("Packer details | Warranty", F.PACKER_NAME)
    assert not _values_for("Importer info", F.IMPORTER_NAME)
    # Still matches with an explicit separator or a "by" phrasing.
    assert _values_for("Manufacturer: Acme Foods Pvt Ltd", F.MANUFACTURER_NAME)
    assert _values_for("Manufactured by Acme Foods Ltd", F.MANUFACTURER_NAME)  # no colon, but "by" anchors it
    assert _values_for("Packer: Acme Packers Ltd", F.PACKER_NAME)
    assert _values_for("Importer: Global Traders Pvt Ltd", F.IMPORTER_NAME)


def test_net_quantity_recognizes_net_content_wording():
    """User-reported: a real Amul milk pouch declares quantity under "Net
    Content" (verified against the physical pack), which the keyword list
    (quantity/qty/weight/wt/volume/vol) didn't cover — a correctly-declared
    pack was reported as missing the declaration entirely
    (POTENTIAL_NON_COMPLIANCE) just because of the accepted-synonym gap."""
    assert _values_for("Net Content: 450 ml", F.NET_QUANTITY) == ["450 ml"]
    assert _values_for("Net Contents 450 ml", F.NET_QUANTITY) == ["450 ml"]
    assert _values_for("NET CONTENT 450ML", F.NET_QUANTITY)


def test_net_quantity_unanchored_number_unit_is_not_matched():
    """Live-listing test found the old unanchored net_quantity fallback
    (bare "\\d+\\s*(?:g|kg|ml|...)", no "net"/"quantity" keyword required)
    matching a real Flipkart page's nutrition-facts panel ("Total Fat: 8
    g", "Protein: 2 g") and other recommended products' weights in a
    "similar products" carousel ("Real Spinach Chips 125 g") — 9 wrong
    candidates against the listing's one real, correctly-labeled "163 g".
    That unanchored pattern has been removed entirely; the keyword-anchored
    one still matches real declarations fine."""
    assert not _values_for("Total Fat: 8 g, Saturated Fat: 1 g, Cholesterol: 0 mg", F.NET_QUANTITY)
    assert not _values_for("Real Spinach Chips 125 g | 21% OFF | ₹225", F.NET_QUANTITY)
    assert not _values_for("(₹193/100g)", F.NET_QUANTITY)
    # Still matches real, keyword-anchored declarations.
    assert _values_for("Net Quantity: 500 g", F.NET_QUANTITY)
    assert _values_for("Net Wt. 250g", F.NET_QUANTITY)


def test_mrp_bare_currency_symbol_is_not_matched():
    """Live-listing test found the bare "₹" trigger matching every rupee
    amount on a real Flipkart page — a "similar products" recommendation
    carousel's unrelated prices, per-100g unit-price mentions, etc. — 12+
    noisy MRP candidates for one listing, which pushed a real MRP finding
    into a false POTENTIAL_NON_COMPLIANCE via ctx.best() picking one of the
    unrelated numbers. The literal "mrp"/"m.r.p" keyword is now required."""
    assert not _values_for("(₹193/100g)", F.MRP)
    assert not _values_for("349 | ₹314 | Buy at ₹239 | Apply offers", F.MRP)
    # Still matches real MRP declarations.
    assert _values_for("MRP: Rs. 60.00", F.MRP)
    assert _values_for("M.R.P ₹120", F.MRP)


# --- Hindi/Devanagari declaration wording (Rule 9(4) permits Hindi or
# English) — a label whose required field is printed only in Hindi must be
# recognized the same way its English equivalent already is. ---


def test_hindi_mrp_is_recognized():
    assert _values_for("अधिकतम खुदरा मूल्य: ₹120", F.MRP) == ["120"]
    assert _values_for("एम.आर.पी. रु. 60.00", F.MRP) == ["60.00"]


def test_hindi_mrp_recognizes_a_latin_currency_marker_on_a_bilingual_label():
    """Real bilingual packaging mixes scripts mid-line: "MRP / अधिकतम
    खुदरा मूल्य: Rs. 150.00" — the currency marker after the Hindi keyword
    may itself be Latin-script, not just रु./₹."""
    assert _values_for("अधिकतम खुदरा मूल्य: Rs. 150.00", F.MRP) == ["150.00"]


def test_hindi_net_quantity_is_recognized_and_parses_for_the_exemption_gate():
    values = _values_for("शुद्ध मात्रा: 500 ग्राम", F.NET_QUANTITY)
    assert values == ["500 ग्राम"]
    parsed = parse_net_quantity(values[0])
    assert parsed is not None
    assert parsed.basis == "weight_g"
    assert parsed.normalized_value == 500

    volume = _values_for("निवल मात्रा: 1 लीटर", F.NET_QUANTITY)
    assert volume == ["1 लीटर"]
    parsed_volume = parse_net_quantity(volume[0])
    assert parsed_volume is not None
    assert parsed_volume.basis == "volume_ml"
    assert parsed_volume.normalized_value == 1000


def test_hindi_manufacturer_and_country_of_origin_are_recognized():
    assert _values_for("निर्माता: एकमे फूड्स प्राइवेट लिमिटेड", F.MANUFACTURER_NAME)
    assert _values_for("आयातक: ग्लोबल ट्रेडर्स", F.IMPORTER_NAME)
    assert _values_for("मूल देश: भारत", F.COUNTRY_OF_ORIGIN)


def test_hindi_bare_noun_without_separator_is_not_matched():
    """Same anchoring discipline as the English bare-noun regression test
    above: a Hindi label word without an explicit separator must not match."""
    assert not _values_for("निर्माता विवरण अनुभाग", F.MANUFACTURER_NAME)
