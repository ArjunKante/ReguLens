"""Declaration-extraction consolidation tests (Section 9/37)."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.models.enums import DeclarationSourceType, WebFetchStatus
from app.models.inspection import Inspection
from app.models.scraping import OCRResult, ProductImage, WebExtraction, WebPage
from app.models.user import User
from app.nlp.declaration_extractor import extract_declarations_from_ocr, extract_declarations_from_webpage


def _make_inspection(db: Session, officer: User) -> Inspection:
    inspection = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=officer.id,
        source_url="https://blinkit.com/prn/example/prid/1",
        platform="blinkit",
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


def _make_web_page(db: Session, inspection: Inspection) -> WebPage:
    wp = WebPage(
        inspection_id=inspection.id,
        url=inspection.source_url,
        platform="blinkit",
        fetch_status=WebFetchStatus.SUCCESS.value,
        fetched_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(wp)
    db.commit()
    db.refresh(wp)
    return wp


def test_webpage_extraction_dedupes_agreeing_candidates_keeps_best_confidence(db: Session, inspector_user: User):
    inspection = _make_inspection(db, inspector_user)
    web_page = _make_web_page(db, inspection)

    e1 = WebExtraction(
        web_page_id=web_page.id, strategy="FALLBACK_TEXT", field_name="mrp", field_value="Rs. 60.00", confidence=0.7
    )
    e2 = WebExtraction(
        web_page_id=web_page.id, strategy="JSON_LD", field_name="mrp", field_value="60.00", confidence=0.9
    )
    db.add_all([e1, e2])
    db.commit()

    declarations = extract_declarations_from_webpage(db, inspection.id, web_page, [e1, e2])

    mrp_decls = [d for d in declarations if d.field_name == "mrp"]
    assert len(mrp_decls) == 1
    assert mrp_decls[0].confidence == 0.9
    assert mrp_decls[0].source_type == DeclarationSourceType.STRUCTURED_METADATA.value


def test_webpage_extraction_keeps_genuinely_different_values_separate(db: Session, inspector_user: User):
    """This is exactly the situation the consistency engine needs to see —
    the extractor must not silently collapse disagreeing sources."""
    inspection = _make_inspection(db, inspector_user)
    web_page = _make_web_page(db, inspection)

    e1 = WebExtraction(
        web_page_id=web_page.id, strategy="FALLBACK_TEXT", field_name="mrp", field_value="Rs. 120.00", confidence=0.7
    )
    e2 = WebExtraction(
        web_page_id=web_page.id, strategy="JSON_LD", field_name="mrp", field_value="99.00", confidence=0.6
    )
    db.add_all([e1, e2])
    db.commit()

    declarations = extract_declarations_from_webpage(db, inspection.id, web_page, [e1, e2])
    mrp_values = {d.normalized_value for d in declarations if d.field_name == "mrp"}
    assert mrp_values == {"120.00", "99.00"}


def test_ocr_extraction_creates_declarations_with_image_ocr_source(db: Session, inspector_user: User):
    inspection = _make_inspection(db, inspector_user)
    image = ProductImage(
        inspection_id=inspection.id,
        source_type="USER_INPUT",
        storage_path="C:/fake/path.png",
        downloaded_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(image)
    db.flush()

    blocks = [
        OCRResult(
            product_image_id=image.id, engine="tesseract", engine_version="5.4",
            text="MRP", confidence=0.9, bounding_box={"x": 0, "y": 0, "width": 30, "height": 10},
            created_at=dt.datetime.now(dt.timezone.utc),
        ),
        OCRResult(
            product_image_id=image.id, engine="tesseract", engine_version="5.4",
            text="Rs. 60.00", confidence=0.85, bounding_box={"x": 35, "y": 0, "width": 60, "height": 10},
            created_at=dt.datetime.now(dt.timezone.utc),
        ),
        OCRResult(
            product_image_id=image.id, engine="tesseract", engine_version="5.4",
            text="Net Quantity 100 g", confidence=0.8, bounding_box={"x": 0, "y": 20, "width": 100, "height": 10},
            created_at=dt.datetime.now(dt.timezone.utc),
        ),
    ]
    db.add_all(blocks)
    db.commit()

    declarations = extract_declarations_from_ocr(db, inspection.id, image, blocks)
    by_field = {d.field_name: d for d in declarations}

    assert "mrp" in by_field
    assert by_field["mrp"].source_type == DeclarationSourceType.IMAGE_OCR.value
    assert by_field["mrp"].source_product_image_id == image.id
    assert "net_quantity" in by_field
    assert by_field["net_quantity"].normalized_value == "100g"


def test_ocr_extraction_returns_empty_list_for_no_results(db: Session, inspector_user: User):
    inspection = _make_inspection(db, inspector_user)
    image = ProductImage(
        inspection_id=inspection.id,
        source_type="USER_INPUT",
        storage_path="C:/fake/path2.png",
        downloaded_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(image)
    db.commit()

    assert extract_declarations_from_ocr(db, inspection.id, image, []) == []
