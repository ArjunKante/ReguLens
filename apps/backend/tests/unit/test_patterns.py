"""Unit tests for app.nlp.patterns (P0 audit fix: "manufacturer/packer/
importer validation logic" — manufacturer_address/packer_address/
importer_address previously had no extractor at all, so
LMPC-R6-1A-MFR-NAME and LMPC-R10-NAME-ADDR-FORM (both of which require an
address field) could never PASS regardless of how complete a package's
declaration was)."""
from __future__ import annotations

from app.nlp.patterns import find_field_candidates
from app.rules import fields as F


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
