"""End-to-end compliance-engine tests (Section 13/37): for the key rules,
exercise PASS, POTENTIAL_NON_COMPLIANCE, NEEDS_MANUAL_REVIEW,
NOT_APPLICABLE, and UNABLE_TO_VERIFY outcomes against real rule rows loaded
into the test database (not mocked), so the whole rule-lookup -> validator
-> ComplianceCheck/Violation/Evidence persistence path is exercised.
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy.orm import Session

from app.compliance.engine import compute_overall_status, run_compliance_checks
from app.models.compliance import ComplianceCheck
from app.models.declaration import Declaration
from app.models.enums import ComplianceStatus, DeclarationSourceType, ProductCategoryCode, WebFetchStatus
from app.models.inspection import Inspection
from app.models.scraping import ProductImage, WebPage
from app.models.user import User
from app.rules.loader import load_rules


@pytest.fixture()
def loaded_rules(db: Session):
    load_rules(db)


def _inspection(db: Session, officer: User) -> Inspection:
    insp = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=officer.id,
        source_url="https://blinkit.com/prn/example/prid/1",
        platform="blinkit",
    )
    db.add(insp)
    db.commit()
    db.refresh(insp)
    return insp


def _webpage(db: Session, inspection: Inspection, status=WebFetchStatus.SUCCESS.value) -> WebPage:
    wp = WebPage(
        inspection_id=inspection.id,
        url=inspection.source_url,
        platform="blinkit",
        fetch_status=status,
        fetched_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(wp)
    db.commit()
    db.refresh(wp)
    return wp


def _declare(db: Session, inspection: Inspection, web_page: WebPage | None, field: str, value: str, source_type=DeclarationSourceType.WEBPAGE_TEXT, confidence=0.8, normalized=None):
    d = Declaration(
        inspection_id=inspection.id,
        field_name=field,
        value=value,
        normalized_value=normalized,
        source_type=source_type.value,
        source_web_page_id=web_page.id if web_page and source_type != DeclarationSourceType.IMAGE_OCR else None,
        confidence=confidence,
        extracted_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(d)
    db.commit()
    return d


def _check_for(checks: list[ComplianceCheck], db: Session, rule_key: str) -> ComplianceCheck:
    from app.models.rules import Rule, RuleVersion

    for c in checks:
        rv = db.get(RuleVersion, c.rule_version_id)
        rule = db.get(Rule, rv.rule_id)
        if rule.rule_key == rule_key:
            return c
    raise AssertionError(f"No compliance check found for {rule_key}")


def test_complete_high_quality_listing_passes_core_rules(db: Session, inspector_user: User, loaded_rules):
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)

    _declare(db, inspection, wp, "product_name", "Tasty Munch Chips 100g")
    _declare(db, inspection, wp, "manufacturer_name", "Tasty Foods Pvt Ltd")
    _declare(db, inspection, wp, "manufacturer_address", "Plot 12, Industrial Area, Pune, Maharashtra 411001")
    _declare(db, inspection, wp, "net_quantity", "100 g", normalized="100g")
    _declare(db, inspection, wp, "mrp", "Rs. 60.00", normalized="60.00")
    _declare(db, inspection, wp, "consumer_care_name", "Tasty Foods Care")
    _declare(db, inspection, wp, "consumer_care_phone", "1800-000-1111")

    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)

    net_qty_check = _check_for(checks, db, "LMPC-R6-1C-NET-QUANTITY")
    assert net_qty_check.status == ComplianceStatus.PASS.value

    mrp_check = _check_for(checks, db, "LMPC-R6-1E-MRP")
    assert mrp_check.status == ComplianceStatus.PASS.value

    name_check = _check_for(checks, db, "LMPC-R6-1A-MFR-NAME")
    assert name_check.status == ComplianceStatus.PASS.value


def test_missing_mrp_on_complete_listing_is_potential_non_compliance(db: Session, inspector_user: User, loaded_rules):
    """Section 13's worked example: MRP clearly absent on an otherwise
    high-quality, complete listing -> POTENTIAL_NON_COMPLIANCE."""
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)

    _declare(db, inspection, wp, "product_name", "Shine Bathroom Cleaner 500ml")
    _declare(db, inspection, wp, "manufacturer_name", "Shine Chemicals Pvt Ltd")
    _declare(db, inspection, wp, "manufacturer_address", "Sector 5, Gurugram, Haryana 122001")
    _declare(db, inspection, wp, "net_quantity", "500 ml", normalized="500ml")
    _declare(db, inspection, wp, "consumer_care_name", "Shine Care")
    _declare(db, inspection, wp, "consumer_care_phone", "1800-222-3333")
    # Deliberately no MRP declaration and a second image source present, to
    # push evidence_quality_score high enough to cross the 0.5 threshold.
    db.add(ProductImage(
        inspection_id=inspection.id, source_type="ONLINE_LISTING", storage_path="x.png",
        downloaded_at=dt.datetime.now(dt.timezone.utc),
    ))
    db.commit()

    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    mrp_check = _check_for(checks, db, "LMPC-R6-1E-MRP")
    assert mrp_check.status == ComplianceStatus.POTENTIAL_NON_COMPLIANCE.value
    assert mrp_check.violation is not None


def test_missing_mrp_with_no_evidence_at_all_is_unable_to_verify(db: Session, inspector_user: User, loaded_rules):
    inspection = _inspection(db, inspector_user)
    _webpage(db, inspection, status=WebFetchStatus.FAILED.value)
    # No declarations, no images: nothing was retrieved.

    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    mrp_check = _check_for(checks, db, "LMPC-R6-1E-MRP")
    assert mrp_check.status == ComplianceStatus.UNABLE_TO_VERIFY.value


def test_best_before_not_applicable_for_household_category(db: Session, inspector_user: User, loaded_rules):
    inspection = _inspection(db, inspector_user)
    _webpage(db, inspection)
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, "LMPC-R6-1DA-BEST-BEFORE")
    assert check.status == ComplianceStatus.NOT_APPLICABLE.value


def test_country_of_origin_not_applicable_for_domestic_online_listing(db: Session, inspector_user: User, loaded_rules):
    """A domestic product's online listing with no declared country of
    origin is NOT_APPLICABLE under Rule 6(1)(aa), which is strictly
    imported-products-only and does not extend to domestic products (an
    earlier version of this test/handler speculated a broader e-commerce
    policy obligation here, citing a general 2020 DPIIT direction that
    could not be precisely verified; that speculation has been removed —
    see LMPC-R6-10A-COO-FILTER for the real, precisely-cited 2026
    e-commerce country-of-origin requirement, which is *also*
    imported-products-only)."""
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "manufacturer_name", "Local Foods Pvt Ltd")
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.FOOD)
    check = _check_for(checks, db, "LMPC-R6-1AA-COUNTRY-ORIGIN")
    assert check.status == ComplianceStatus.NOT_APPLICABLE.value


def test_coo_filter_rule_not_applicable_for_domestic_product(db: Session, inspector_user: User, loaded_rules):
    """Rule 6(10A) (2026 e-commerce country-of-origin filter requirement)
    is imported-products-only, same as Rule 6(1)(aa) -- a domestic product
    must not be flagged under it."""
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "manufacturer_name", "Local Foods Pvt Ltd")
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.FOOD)
    check = _check_for(checks, db, "LMPC-R6-10A-COO-FILTER")
    assert check.status == ComplianceStatus.NOT_APPLICABLE.value


def test_coo_filter_rule_flags_missing_declaration_for_imported_product(db: Session, inspector_user: User, loaded_rules):
    """An imported product's online listing with no country-of-origin
    declaration at all fails Rule 6(10A)'s declaration prerequisite."""
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "importer_name", "Global Traders Pvt Ltd")
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.FOOD)
    check = _check_for(checks, db, "LMPC-R6-10A-COO-FILTER")
    assert check.status in (ComplianceStatus.POTENTIAL_NON_COMPLIANCE.value, ComplianceStatus.NEEDS_MANUAL_REVIEW.value)


def test_coo_filter_rule_needs_review_when_declared_but_filter_unverifiable(db: Session, inspector_user: User, loaded_rules):
    """Even with country of origin declared for an imported product's
    listing, Rule 6(10A) also requires an actual searchable/sortable filter
    on the platform -- something LM-SCAN cannot verify from page content,
    so this must never claim a confident PASS on the rule."""
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "importer_name", "Global Traders Pvt Ltd")
    _declare(db, inspection, wp, "country_of_origin", "China")
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.FOOD)
    check = _check_for(checks, db, "LMPC-R6-10A-COO-FILTER")
    assert check.status == ComplianceStatus.NEEDS_MANUAL_REVIEW.value
    assert check.status != ComplianceStatus.PASS.value


def test_country_of_origin_not_applicable_for_domestic_physical_only_inspection(db: Session, inspector_user: User, loaded_rules):
    """No WebPage at all (a manual/photo-only inspection, i.e. no online
    listing exists) with a domestic manufacturer declared: Rule 6(1)(aa)
    (imported-only) and the e-commerce display practice (online-listings-only)
    both agree this is genuinely NOT_APPLICABLE."""
    inspection = _inspection(db, inspector_user)
    inspection.source_url = None
    db.commit()
    image = ProductImage(
        inspection_id=inspection.id, source_type="USER_INPUT", storage_path="manual.png",
        downloaded_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(image)
    db.commit()
    _declare(db, inspection, None, "manufacturer_name", "Local Foods Pvt Ltd", source_type=DeclarationSourceType.IMAGE_OCR)
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.FOOD)
    check = _check_for(checks, db, "LMPC-R6-1AA-COUNTRY-ORIGIN")
    assert check.status == ComplianceStatus.NOT_APPLICABLE.value


def test_country_of_origin_unable_to_verify_when_origin_cannot_be_determined(db: Session, inspector_user: User, loaded_rules):
    """No importer AND no manufacturer/packer declared at all: origin is
    UNKNOWN, not "presumed domestic" (P0 audit fix: "imported/domestic/
    unknown classification" — the previous boolean `is_imported` collapsed
    this into the same NOT_APPLICABLE as a positively-identified domestic
    product)."""
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "product_name", "Some Snack")
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.FOOD)
    check = _check_for(checks, db, "LMPC-R6-1AA-COUNTRY-ORIGIN")
    assert check.status == ComplianceStatus.UNABLE_TO_VERIFY.value


def test_manufacturer_declaration_needs_manual_review_on_food_category_exclusion(db: Session, inspector_user: User, loaded_rules):
    """FOOD category is excluded from LMPC-R6-1A per Explanation III (FSS Act governs instead)."""
    inspection = _inspection(db, inspector_user)
    _webpage(db, inspection)
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.FOOD)
    check = _check_for(checks, db, "LMPC-R6-1A-MFR-NAME")
    assert check.status == ComplianceStatus.NOT_APPLICABLE.value


def test_small_package_exemption_gates_other_rules_not_applicable(db: Session, inspector_user: User, loaded_rules):
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "net_quantity", "8 g", normalized="8g")
    # No manufacturer declared at all — would normally be flagged, but the
    # small-package exemption should mark it NOT_APPLICABLE instead.
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, "LMPC-R6-1A-MFR-NAME")
    assert check.status == ComplianceStatus.NOT_APPLICABLE.value
    assert "26(a)" in check.reason


def test_mrp_inconsistency_between_listing_and_image_is_flagged(db: Session, inspector_user: User, loaded_rules):
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "mrp", "Rs. 120.00", normalized="120.00", source_type=DeclarationSourceType.WEBPAGE_TEXT)
    image = ProductImage(
        inspection_id=inspection.id, source_type="ONLINE_LISTING", storage_path="y.png",
        downloaded_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(image)
    db.flush()
    ocr_decl = Declaration(
        inspection_id=inspection.id, field_name="mrp", value="Rs. 110.00", normalized_value="110.00",
        source_type=DeclarationSourceType.IMAGE_OCR.value, source_product_image_id=image.id,
        confidence=0.8, extracted_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(ocr_decl)
    db.commit()

    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, "LMSCAN-CONSISTENCY-MRP")
    assert check.status == ComplianceStatus.POTENTIAL_NON_COMPLIANCE.value
    assert "Officer verification required" in check.reason
    assert len(check.evidence_items) == 2


def test_mrp_agreement_between_listing_and_image_passes(db: Session, inspector_user: User, loaded_rules):
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "mrp", "Rs. 120.00", normalized="120.00")
    image = ProductImage(
        inspection_id=inspection.id, source_type="ONLINE_LISTING", storage_path="z.png",
        downloaded_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(image)
    db.flush()
    db.add(Declaration(
        inspection_id=inspection.id, field_name="mrp", value="Rs. 120.00", normalized_value="120.00",
        source_type=DeclarationSourceType.IMAGE_OCR.value, source_product_image_id=image.id,
        confidence=0.8, extracted_at=dt.datetime.now(dt.timezone.utc),
    ))
    db.commit()

    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, "LMSCAN-CONSISTENCY-MRP")
    assert check.status == ComplianceStatus.PASS.value


def test_missing_mrp_with_partial_low_quality_evidence_needs_manual_review(db: Session, inspector_user: User, loaded_rules):
    """Section 13's other worked example: MRP not found, and the only
    evidence available is a low-quality screenshot (page fetch failed
    entirely, and OCR confidence on the uploaded screenshot was poor) ->
    NEEDS_MANUAL_REVIEW, not a confident POTENTIAL_NON_COMPLIANCE."""
    from app.models.scraping import OCRResult

    inspection = _inspection(db, inspector_user)
    _webpage(db, inspection, status=WebFetchStatus.FAILED.value)

    image = ProductImage(
        inspection_id=inspection.id, source_type="USER_INPUT", storage_path="low_quality.png",
        downloaded_at=dt.datetime.now(dt.timezone.utc), quality_acceptable=False,
    )
    db.add(image)
    db.flush()
    db.add(OCRResult(
        product_image_id=image.id, engine="tesseract", engine_version="5.4",
        text="...", confidence=0.15, bounding_box={"x": 0, "y": 0, "width": 5, "height": 5},
        created_at=dt.datetime.now(dt.timezone.utc),
    ))
    db.commit()

    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    mrp_check = _check_for(checks, db, "LMPC-R6-1E-MRP")
    assert mrp_check.status == ComplianceStatus.NEEDS_MANUAL_REVIEW.value


def test_mfg_date_passes_when_a_date_like_value_is_declared(db: Session, inspector_user: User, loaded_rules):
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "mfg_date", "07/2024")
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, "LMPC-R6-1D-MFG-DATE")
    assert check.status == ComplianceStatus.PASS.value


def test_consumer_care_passes_with_name_and_phone(db: Session, inspector_user: User, loaded_rules):
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "consumer_care_name", "Acme Consumer Care")
    _declare(db, inspection, wp, "consumer_care_phone", "1800-22-4020")
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, "LMPC-R6-2-CONSUMER-CARE")
    assert check.status == ComplianceStatus.PASS.value


def test_unit_sale_price_is_always_routed_for_manual_review(db: Session, inspector_user: User, loaded_rules):
    """MANUAL_REVIEW_CHECK: Rule 6(11) requires an arithmetic relationship
    (RSP / net quantity in the standard unit) that this V1 regex/keyword
    engine cannot itself verify, so it is always routed to an officer
    rather than auto-passed or auto-flagged (never a naive presence check)."""
    inspection = _inspection(db, inspector_user)
    _webpage(db, inspection)
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, "LMPC-R6-11-UNIT-SALE-PRICE")
    assert check.status == ComplianceStatus.NEEDS_MANUAL_REVIEW.value


def test_manner_of_declaration_is_always_routed_for_manual_review(db: Session, inspector_user: User, loaded_rules):
    """MANUAL_REVIEW_CHECK: legibility/prominence/script correctness (Rule
    9) is a visual judgment call this engine does not attempt to automate."""
    inspection = _inspection(db, inspector_user)
    _webpage(db, inspection)
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, "LMPC-R9-MANNER")
    assert check.status == ComplianceStatus.NEEDS_MANUAL_REVIEW.value


def test_name_address_form_passes_with_a_pin_coded_address(db: Session, inspector_user: User, loaded_rules):
    """P0 audit fix follow-through: manufacturer_address is now actually
    extractable (see test_patterns.py), so this rule can PASS instead of
    being permanently unsatisfiable."""
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "manufacturer_address", "DLF Qutab Enclave, Gurugram - 122002, Haryana")
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, "LMPC-R10-NAME-ADDR-FORM")
    assert check.status == ComplianceStatus.PASS.value


def test_when_packed_qualifier_is_flagged_as_potential_non_compliance(db: Session, inspector_user: User, loaded_rules):
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "net_quantity", "200g when packed", normalized="200g")
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, "LMPC-R11-QTY-BASIS")
    assert check.status == ComplianceStatus.POTENTIAL_NON_COMPLIANCE.value
    assert "when packed" in check.reason.lower()


def _assert_consistency_mismatch_flagged(
    db: Session, inspector_user: User, *, field: str, online_value: str, image_value: str, rule_key: str, normalized_online: str | None = None, normalized_image: str | None = None,
) -> None:
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, field, online_value, normalized=normalized_online)
    image = ProductImage(
        inspection_id=inspection.id, source_type="ONLINE_LISTING", storage_path="consistency.png",
        downloaded_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(image)
    db.flush()
    db.add(Declaration(
        inspection_id=inspection.id, field_name=field, value=image_value, normalized_value=normalized_image,
        source_type=DeclarationSourceType.IMAGE_OCR.value, source_product_image_id=image.id,
        confidence=0.8, extracted_at=dt.datetime.now(dt.timezone.utc),
    ))
    db.commit()

    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, rule_key)
    assert check.status == ComplianceStatus.POTENTIAL_NON_COMPLIANCE.value


def test_net_quantity_inconsistency_between_listing_and_image_is_flagged(db: Session, inspector_user: User, loaded_rules):
    _assert_consistency_mismatch_flagged(
        db, inspector_user, field="net_quantity", online_value="200g", image_value="150g",
        normalized_online="200g", normalized_image="150g", rule_key="LMSCAN-CONSISTENCY-NET-QUANTITY",
    )


def test_product_name_inconsistency_between_listing_and_image_is_flagged(db: Session, inspector_user: User, loaded_rules):
    _assert_consistency_mismatch_flagged(
        db, inspector_user, field="product_name", online_value="Acme Choco Bar", image_value="Zenith Vanilla Wafers",
        rule_key="LMSCAN-CONSISTENCY-PRODUCT-NAME",
    )


def test_manufacturer_inconsistency_between_listing_and_image_is_flagged(db: Session, inspector_user: User, loaded_rules):
    _assert_consistency_mismatch_flagged(
        db, inspector_user, field="manufacturer_name", online_value="Acme Foods Pvt Ltd", image_value="Totally Different Co Ltd",
        rule_key="LMSCAN-CONSISTENCY-MANUFACTURER",
    )


def test_importer_inconsistency_between_listing_and_image_is_flagged(db: Session, inspector_user: User, loaded_rules):
    _assert_consistency_mismatch_flagged(
        db, inspector_user, field="importer_name", online_value="Global Traders Pvt Ltd", image_value="Some Other Importer LLP",
        rule_key="LMSCAN-CONSISTENCY-IMPORTER",
    )


def test_country_of_origin_inconsistency_between_listing_and_image_is_flagged(db: Session, inspector_user: User, loaded_rules):
    _assert_consistency_mismatch_flagged(
        db, inspector_user, field="country_of_origin", online_value="India", image_value="China",
        rule_key="LMSCAN-CONSISTENCY-COUNTRY-ORIGIN",
    )


def test_overall_status_prioritizes_potential_non_compliance():
    class Fake:
        def __init__(self, status):
            self.status = status.value

    checks = [Fake(ComplianceStatus.PASS), Fake(ComplianceStatus.NEEDS_MANUAL_REVIEW), Fake(ComplianceStatus.POTENTIAL_NON_COMPLIANCE)]
    assert compute_overall_status(checks) == ComplianceStatus.POTENTIAL_NON_COMPLIANCE


def test_overall_status_all_not_applicable_is_unable_to_verify():
    class Fake:
        def __init__(self, status):
            self.status = status.value

    checks = [Fake(ComplianceStatus.NOT_APPLICABLE), Fake(ComplianceStatus.NOT_APPLICABLE)]
    assert compute_overall_status(checks) == ComplianceStatus.UNABLE_TO_VERIFY


def test_ecommerce_display_rule_not_applicable_for_manual_photo_only_inspection(db: Session, inspector_user: User, loaded_rules):
    """P0 audit fix: "online vs physical rule applicability" — Rule 6(10)'s
    e-commerce display duty only has something to say about an actual online
    listing. A manual/photo-only inspection (no WebPage was ever fetched)
    must not be flagged for failing to display declarations "on the digital
    and electronic network" it never had."""
    inspection = _inspection(db, inspector_user)
    inspection.source_url = None
    db.commit()
    image = ProductImage(
        inspection_id=inspection.id, source_type="USER_INPUT", storage_path="manual.png",
        downloaded_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(image)
    db.commit()
    # Even with plenty of declarations present (just not from a webpage —
    # there is none), the rule must be NOT_APPLICABLE, not scored as if a
    # listing omitted them.
    _declare(db, inspection, None, "product_name", "Test Snack", source_type=DeclarationSourceType.IMAGE_OCR)
    _declare(db, inspection, None, "mrp", "Rs. 20", source_type=DeclarationSourceType.IMAGE_OCR, normalized="20.00")

    checks = run_compliance_checks(db, inspection, ProductCategoryCode.FOOD)
    check = _check_for(checks, db, "LMPC-R6-10-ECOMMERCE-DISPLAY")
    assert check.status == ComplianceStatus.NOT_APPLICABLE.value


def test_total_ocr_failure_does_not_become_automatic_potential_non_compliance(db: Session, inspector_user: User, loaded_rules):
    """P0 audit fix: "failed OCR doesn't become automatic non-compliance" —
    images were supplied but OCR produced zero OCRResult rows for all of
    them (engine failure / blank image). The previous evidence-quality
    scoring treated "no OCR at all" the same as a neutral 0.5 average OCR
    confidence, which for a listing with no webpage evidence landed exactly
    at the POTENTIAL_NON_COMPLIANCE threshold instead of NEEDS_MANUAL_REVIEW."""
    inspection = _inspection(db, inspector_user)
    inspection.source_url = None
    db.commit()
    image = ProductImage(
        inspection_id=inspection.id, source_type="USER_INPUT", storage_path="manual.png",
        downloaded_at=dt.datetime.now(dt.timezone.utc), quality_acceptable=True,
    )
    db.add(image)
    db.commit()
    # No OCRResult rows at all for this image -- OCR completely failed.

    checks = run_compliance_checks(db, inspection, ProductCategoryCode.HOUSEHOLD)
    check = _check_for(checks, db, "LMPC-R6-1B-GENERIC-NAME")
    assert check.status != ComplianceStatus.POTENTIAL_NON_COMPLIANCE.value
    assert check.status in (ComplianceStatus.NEEDS_MANUAL_REVIEW.value, ComplianceStatus.UNABLE_TO_VERIFY.value)
