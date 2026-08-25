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


def test_country_of_origin_not_applicable_when_not_imported(db: Session, inspector_user: User, loaded_rules):
    inspection = _inspection(db, inspector_user)
    wp = _webpage(db, inspection)
    _declare(db, inspection, wp, "manufacturer_name", "Local Foods Pvt Ltd")
    checks = run_compliance_checks(db, inspection, ProductCategoryCode.FOOD)
    check = _check_for(checks, db, "LMPC-R6-1AA-COUNTRY-ORIGIN")
    assert check.status == ComplianceStatus.NOT_APPLICABLE.value


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
