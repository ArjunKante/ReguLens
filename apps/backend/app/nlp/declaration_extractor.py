"""Declaration extraction engine (Section 9).

Consolidates raw scraper output (WebExtraction rows) and raw OCR output
(OCRResult rows) into the unified `declarations` table, where every row
carries its field name, value, source type, source pointer, and confidence
-- exactly the shape described in Section 6 of the product brief. This is
regex/keyword-first by design (Section 46: an LLM, if used at all, may only
assist with normalization/classification, never invent or finalize a legal
declaration) — see docs/compliance-engine.md.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.models.declaration import Declaration
from app.models.enums import DeclarationSourceType, ExtractionStrategy
from app.models.scraping import OCRResult, ProductImage, WebExtraction, WebPage
from app.nlp.normalization import normalize_field_value
from app.nlp.patterns import find_field_candidates

_STRUCTURED_STRATEGIES = {
    ExtractionStrategy.JSON_LD.value,
    ExtractionStrategy.OPEN_GRAPH.value,
    ExtractionStrategy.STRUCTURED_METADATA.value,
    ExtractionStrategy.CSS_SELECTOR.value,
}


def _dedupe_keep_best(candidates: list[dict]) -> list[dict]:
    """Collapses candidates that agree (same field + same normalized value)
    to their highest-confidence representative, while keeping genuinely
    different values as separate rows (those are exactly what the
    consistency engine needs to see)."""
    best: dict[tuple[str, str | None], dict] = {}
    for c in candidates:
        key = (c["field_name"], c["normalized_value"] or c["value"])
        existing = best.get(key)
        if existing is None or c["confidence"] > existing["confidence"]:
            best[key] = c
    return list(best.values())


def extract_declarations_from_webpage(
    db: Session, inspection_id: uuid.UUID, web_page: WebPage, extractions: list[WebExtraction]
) -> list[Declaration]:
    candidates = []
    for ext in extractions:
        if not ext.field_value:
            continue
        source_type = (
            DeclarationSourceType.STRUCTURED_METADATA
            if ext.strategy in _STRUCTURED_STRATEGIES
            else DeclarationSourceType.WEBPAGE_TEXT
        )
        candidates.append(
            {
                "field_name": ext.field_name,
                "value": ext.field_value,
                "normalized_value": normalize_field_value(ext.field_name, ext.field_value),
                "confidence": ext.confidence,
                "source_type": source_type,
                "source_web_page_id": web_page.id,
                "source_web_extraction_id": ext.id,
                "extraction_method": ext.strategy,
            }
        )

    deduped = _dedupe_keep_best(candidates)
    now = dt.datetime.now(dt.timezone.utc)
    declarations = []
    for c in deduped:
        decl = Declaration(
            inspection_id=inspection_id,
            field_name=c["field_name"],
            value=c["value"],
            normalized_value=c["normalized_value"],
            source_type=c["source_type"].value,
            source_web_page_id=c["source_web_page_id"],
            source_web_extraction_id=c["source_web_extraction_id"],
            extraction_method=c["extraction_method"],
            confidence=c["confidence"],
            extracted_at=now,
        )
        db.add(decl)
        declarations.append(decl)
    db.commit()
    return declarations


_LINE_CLUSTER_HEIGHT_FRACTION = 0.6


def _group_into_lines(ocr_results: list[OCRResult]) -> list[list[OCRResult]]:
    """Reconstructs reading order from unordered OCR word/line boxes.

    A flat sort by (y, x) — the original approach — breaks on real-world
    output: Devanagari conjuncts and matras routinely shift one word's
    bounding-box top by 20-25px relative to its neighbors *on the same
    visual line* (verified against real Tesseract output on a Hindi label:
    "निर्माता:" at y=353 next to "भारत"/"फूड्स"/"प्रा." at y=371, all one
    line). A pure (y, x) sort treats that y gap as "a different line" and
    reorders purely by y first, scrambling the line's actual left-to-right
    text — e.g. "निर्माता: भारत फूड्स प्रा. लि., ..." became "निर्माता:
    लि., ..." with everything in between sorted elsewhere, so the
    manufacturer-name pattern captured only "लि." ("Ltd."). Clustering by
    y-*proximity* first (generous threshold, since the same conjunct/matra
    variance that causes the problem also means "same line" can't be a tight
    band) and only sorting by x *within* a cluster reconstructs the correct
    reading order instead.
    """
    by_y = sorted(ocr_results, key=lambda r: (r.bounding_box or {}).get("y", 0))
    lines: list[list[OCRResult]] = []
    for block in by_y:
        bbox = block.bounding_box or {}
        y = bbox.get("y", 0)
        height = bbox.get("height", 0) or 0
        for line in lines:
            ref_bbox = line[0].bounding_box or {}
            ref_y = ref_bbox.get("y", 0)
            ref_height = ref_bbox.get("height", 0) or 0
            if abs(y - ref_y) <= max(height, ref_height, 1) * _LINE_CLUSTER_HEIGHT_FRACTION:
                line.append(block)
                break
        else:
            lines.append([block])
    lines.sort(key=lambda line: min((b.bounding_box or {}).get("y", 0) for b in line))
    for line in lines:
        line.sort(key=lambda b: (b.bounding_box or {}).get("x", 0))
    return lines


def extract_declarations_from_ocr(
    db: Session, inspection_id: uuid.UUID, product_image: ProductImage, ocr_results: list[OCRResult]
) -> list[Declaration]:
    if not ocr_results:
        return []

    lines = _group_into_lines(ocr_results)
    ordered = [block for line in lines for block in line]

    # Lines are joined with a real "\n" (not a bare space) so "loose" value
    # patterns (a name, a date — anything not tightly bounded to digits)
    # can't run on past the end of their own line into the next
    # declaration's text. Found live testing Hindi labels (Section 46/48
    # follow-on): consumer_care_name and mfg_date both bled into the
    # following line's content this way — a pre-existing bug, not Hindi-
    # specific, just more likely to surface on Devanagari's looser
    # keyword-to-value patterns.
    blob_parts: list[str] = []
    offsets: list[tuple[int, int, OCRResult]] = []
    cursor = 0
    for line in lines:
        for block in line:
            start = cursor
            blob_parts.append(block.text)
            cursor += len(block.text)
            offsets.append((start, cursor, block))
            blob_parts.append(" ")
            cursor += 1
        blob_parts.append("\n")
        cursor += 1
    blob = "".join(blob_parts)

    matches = find_field_candidates(blob)
    candidates = []
    for match in matches:
        idx = blob.find(match.value)
        contributing = [b for (s, e, b) in offsets if idx != -1 and not (e < idx or s > idx + len(match.value))]
        if not contributing:
            contributing = ordered[:1]
        avg_ocr_conf = sum(b.confidence for b in contributing) / len(contributing)
        combined_confidence = round(match.base_confidence * max(avg_ocr_conf, 0.3), 3)
        best_block = max(contributing, key=lambda b: b.confidence)
        candidates.append(
            {
                "field_name": match.field_name,
                "value": match.value,
                "normalized_value": normalize_field_value(match.field_name, match.value),
                "confidence": combined_confidence,
                "source_ocr_result_id": best_block.id,
            }
        )

    deduped = _dedupe_keep_best(candidates)
    now = dt.datetime.now(dt.timezone.utc)
    declarations = []
    for c in deduped:
        decl = Declaration(
            inspection_id=inspection_id,
            field_name=c["field_name"],
            value=c["value"],
            normalized_value=c["normalized_value"],
            source_type=DeclarationSourceType.IMAGE_OCR.value,
            source_ocr_result_id=c["source_ocr_result_id"],
            source_product_image_id=product_image.id,
            extraction_method="OCR_TEXT_PATTERN",
            confidence=c["confidence"],
            extracted_at=now,
        )
        db.add(decl)
        declarations.append(decl)
    db.commit()
    return declarations


def add_manual_declaration(
    db: Session,
    inspection_id: uuid.UUID,
    *,
    field_name: str,
    value: str,
    user_id: uuid.UUID,
    confidence: float = 1.0,
) -> Declaration:
    """Records an officer-supplied value (Section 6: USER_INPUT source
    type) — e.g. when automatic extraction couldn't find a field but the
    officer can read it directly off a screenshot."""
    decl = Declaration(
        inspection_id=inspection_id,
        field_name=field_name,
        value=value,
        normalized_value=normalize_field_value(field_name, value),
        source_type=DeclarationSourceType.USER_INPUT.value,
        source_user_id=user_id,
        extraction_method="MANUAL_ENTRY",
        confidence=confidence,
        extracted_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(decl)
    db.commit()
    db.refresh(decl)
    return decl
