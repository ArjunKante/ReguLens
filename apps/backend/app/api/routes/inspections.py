from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.audit.service import log_action
from app.auth.dependencies import require_any_authenticated, require_inspector, require_reviewer
from app.core.database import get_db
from app.demo_fixtures import DEMO_SOURCE_URL
from app.models.compliance import ComplianceCheck
from app.models.enums import ComplianceStatus, EvidenceSourceType, InspectionStatus
from app.models.inspection import Inspection
from app.models.review import ReviewDecision
from app.models.scraping import ProductImage
from app.models.user import User
from app.nlp.declaration_extractor import add_manual_declaration
from app.repositories.inspection_repository import create_inspection, get_inspection, list_inspections
from app.reports.service import generate_report
from app.schemas.inspection import (
    ComplianceCheckOut,
    DeclarationOut,
    EvidenceOut,
    InspectionCreate,
    InspectionDetail,
    InspectionSummary,
    ManualDeclarationCreate,
    PipelineEventOut,
    ProductImageOut,
    ReviewDecisionCreate,
    ReviewDecisionOut,
    RuleVersionBrief,
    ViolationOut,
    WebPageOut,
)
from app.services.image_service import UnsafeUploadError, process_image_bytes
from app.services.pipeline import run_inspection_pipeline_new_session

router = APIRouter(prefix="/inspections", tags=["inspections"])


def _to_summary(inspection: Inspection) -> InspectionSummary:
    return InspectionSummary(
        id=inspection.id,
        inspection_number=inspection.inspection_number,
        source_url=inspection.source_url,
        platform=inspection.platform,
        status=inspection.status,
        overall_status=inspection.overall_status,
        officer_id=inspection.officer_id,
        officer_name=inspection.officer.full_name if inspection.officer else None,
        product_title=inspection.product.title if inspection.product else None,
        created_at=inspection.created_at,
        completed_at=inspection.completed_at,
        is_demo=inspection.is_demo,
    )


def _to_check_out(check: ComplianceCheck) -> ComplianceCheckOut:
    rv = check.rule_version
    return ComplianceCheckOut(
        id=check.id,
        status=check.status,
        reason=check.reason,
        confidence=check.confidence,
        checked_fields=check.checked_fields,
        rule=RuleVersionBrief(
            rule_key=rv.rule.rule_key,
            rule_reference=rv.rule_reference,
            title=rv.title,
            requirement=rv.requirement,
            severity=rv.severity,
            source_document=rv.source_document,
            source_locator=rv.source_locator,
            version_number=rv.version_number,
        ),
        violation=ViolationOut.model_validate(check.violation) if check.violation else None,
        evidence=[EvidenceOut.model_validate(e) for e in check.evidence_items],
        review_decisions=[
            ReviewDecisionOut(
                id=r.id,
                reviewer_id=r.reviewer_id,
                reviewer_name=r.reviewer.full_name if r.reviewer else None,
                decision=r.decision,
                automated_status=r.automated_status,
                final_status=r.final_status,
                comment=r.comment,
                reason=r.reason,
                created_at=r.created_at,
            )
            for r in check.review_decisions
        ],
    )


def _to_detail(inspection: Inspection) -> InspectionDetail:
    summary = _to_summary(inspection)
    # The DONE-stage event recorded at the end of a successful pipeline run
    # carries the total wall-clock duration (Demo Hardening: "measure
    # pipeline execution time") — surfaced here rather than adding a column,
    # since it's already just another PipelineEvent. Older inspections that
    # completed before this existed simply have no such event, hence None.
    done_events = [p for p in inspection.pipeline_events if p.stage == "DONE" and p.duration_ms is not None]
    pipeline_duration_ms = done_events[-1].duration_ms if done_events else None
    return InspectionDetail(
        **summary.model_dump(),
        notes=inspection.notes,
        declarations=[DeclarationOut.model_validate(d) for d in inspection.declarations],
        compliance_checks=[_to_check_out(c) for c in inspection.compliance_checks],
        images=[ProductImageOut.model_validate(i) for i in inspection.images],
        web_pages=[WebPageOut.model_validate(w) for w in inspection.web_pages],
        pipeline_events=[PipelineEventOut.model_validate(p) for p in inspection.pipeline_events],
        pipeline_duration_ms=pipeline_duration_ms,
    )


@router.post("", response_model=InspectionSummary, status_code=status.HTTP_201_CREATED)
def create_new_inspection(
    payload: InspectionCreate,
    db: Session = Depends(get_db),
    officer: User = Depends(require_inspector),
) -> InspectionSummary:
    inspection = create_inspection(db, officer=officer, source_url=payload.source_url, notes=payload.notes)
    log_action(db, actor_id=officer.id, action="INSPECTION_CREATED", entity_type="inspection", entity_id=str(inspection.id))
    return _to_summary(inspection)


@router.post("/demo", response_model=InspectionSummary, status_code=status.HTTP_201_CREATED)
def create_demo_inspection(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    officer: User = Depends(require_inspector),
) -> InspectionSummary:
    """Demo Inspection mode (Demo Hardening): a controlled, reproducible
    inspection sourced from a bundled real-listing fixture instead of a
    live fetch, for demos where live scraping's inherent flakiness isn't
    acceptable. Runs the exact same pipeline/compliance engine as a real
    scan — only the evidence source differs — and the result is marked
    `is_demo=True` everywhere so it is never mistaken for a real finding."""
    inspection = create_inspection(
        db, officer=officer, source_url=DEMO_SOURCE_URL, notes="Demo Inspection — reproducible fixture data, not a live scan.",
        is_demo=True,
    )
    inspection.status = InspectionStatus.IN_PROGRESS.value
    db.commit()
    background_tasks.add_task(run_inspection_pipeline_new_session, inspection.id)
    log_action(db, actor_id=officer.id, action="DEMO_INSPECTION_STARTED", entity_type="inspection", entity_id=str(inspection.id))
    return _to_summary(inspection)


@router.get("", response_model=list[InspectionSummary])
def get_inspections(
    status_filter: str | None = Query(None, alias="status"),
    overall_status: str | None = None,
    platform: str | None = None,
    mine_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_authenticated),
) -> list[InspectionSummary]:
    officer_id = user.id if mine_only else None
    inspections = list_inspections(
        db, officer_id=officer_id, status=status_filter, overall_status=overall_status,
        platform=platform, limit=limit, offset=offset,
    )
    return [_to_summary(i) for i in inspections]


@router.get("/{inspection_id}", response_model=InspectionDetail)
def get_inspection_detail(
    inspection_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_any_authenticated)
) -> InspectionDetail:
    inspection = get_inspection(db, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Inspection not found.")
    return _to_detail(inspection)


def _require_inspection(db: Session, inspection_id: uuid.UUID) -> Inspection:
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Inspection not found.")
    return inspection


@router.post("/{inspection_id}/scan-url", status_code=status.HTTP_202_ACCEPTED)
def scan_url(
    inspection_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    officer: User = Depends(require_inspector),
) -> dict:
    inspection = _require_inspection(db, inspection_id)
    inspection.status = InspectionStatus.IN_PROGRESS.value
    db.commit()
    background_tasks.add_task(run_inspection_pipeline_new_session, inspection.id)
    log_action(db, actor_id=officer.id, action="SCAN_STARTED", entity_type="inspection", entity_id=str(inspection.id))
    return {"status": "accepted", "inspection_id": str(inspection.id)}


@router.post("/{inspection_id}/screenshots", response_model=list[ProductImageOut])
async def upload_screenshots(
    inspection_id: uuid.UUID,
    files: list[UploadFile],
    db: Session = Depends(get_db),
    officer: User = Depends(require_inspector),
) -> list[ProductImageOut]:
    inspection = _require_inspection(db, inspection_id)
    created = []
    for f in files:
        content = await f.read()
        try:
            image = process_image_bytes(
                db,
                inspection_id=inspection.id,
                content=content,
                source_type=EvidenceSourceType.USER_INPUT,
                original_url=None,
                original_filename=f.filename,
                content_type=f.content_type,
                run_ocr=False,
            )
        except UnsafeUploadError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        created.append(ProductImageOut.model_validate(image))

    log_action(
        db, actor_id=officer.id, action="SCREENSHOTS_UPLOADED", entity_type="inspection",
        entity_id=str(inspection.id), extra={"count": len(created)},
    )
    return created


_IMAGE_CONTENT_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


@router.get("/{inspection_id}/images/{image_id}/file")
def download_evidence_image(
    inspection_id: uuid.UUID, image_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_any_authenticated)
) -> Response:
    """Serves the raw bytes of one evidence image (Demo Hardening: "display
    actual evidence images" — images were stored and quality-assessed but
    never actually servable before this). Requires auth like every other
    read here; the frontend fetches this the same way it already fetches
    report downloads (through the authenticated API client, converted to a
    local object URL) rather than a plain <img src>, since a plain <img>
    tag can't carry an Authorization header."""
    image = db.get(ProductImage, image_id)
    if image is None or image.inspection_id != inspection_id:
        raise HTTPException(status_code=404, detail="Image not found on this inspection.")
    from pathlib import Path

    from app.storage.files import read_bytes

    try:
        content = read_bytes(image.storage_path)
    except OSError as exc:
        raise HTTPException(status_code=404, detail="Stored image file could not be read.") from exc
    ext = Path(image.storage_path).suffix.lower()
    media_type = _IMAGE_CONTENT_TYPES.get(ext, image.content_type or "application/octet-stream")
    return Response(content=content, media_type=media_type)


@router.post("/{inspection_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
def analyze_inspection(
    inspection_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    officer: User = Depends(require_inspector),
) -> dict:
    """Runs (or re-runs) the analysis pipeline — used after uploading
    screenshots as a fallback when automatic URL retrieval failed/was never
    attempted (Section 5/25), or to re-analyze after new evidence is added."""
    inspection = _require_inspection(db, inspection_id)
    inspection.status = InspectionStatus.IN_PROGRESS.value
    db.commit()
    background_tasks.add_task(run_inspection_pipeline_new_session, inspection.id)
    log_action(db, actor_id=officer.id, action="ANALYZE_STARTED", entity_type="inspection", entity_id=str(inspection.id))
    return {"status": "accepted", "inspection_id": str(inspection.id)}


@router.post("/{inspection_id}/declarations", response_model=DeclarationOut)
def add_declaration(
    inspection_id: uuid.UUID,
    payload: ManualDeclarationCreate,
    db: Session = Depends(get_db),
    officer: User = Depends(require_inspector),
) -> DeclarationOut:
    inspection = _require_inspection(db, inspection_id)
    decl = add_manual_declaration(
        db, inspection.id, field_name=payload.field_name, value=payload.value, user_id=officer.id
    )
    log_action(
        db, actor_id=officer.id, action="MANUAL_DECLARATION_ADDED", entity_type="inspection",
        entity_id=str(inspection.id), extra={"field": payload.field_name},
    )
    return DeclarationOut.model_validate(decl)


@router.get("/{inspection_id}/declarations", response_model=list[DeclarationOut])
def get_declarations(
    inspection_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_any_authenticated)
) -> list[DeclarationOut]:
    inspection = get_inspection(db, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Inspection not found.")
    return [DeclarationOut.model_validate(d) for d in inspection.declarations]


@router.get("/{inspection_id}/compliance", response_model=list[ComplianceCheckOut])
def get_compliance(
    inspection_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_any_authenticated)
) -> list[ComplianceCheckOut]:
    inspection = get_inspection(db, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Inspection not found.")
    return [_to_check_out(c) for c in inspection.compliance_checks]


@router.post("/{inspection_id}/review", response_model=ReviewDecisionOut)
def submit_review(
    inspection_id: uuid.UUID,
    payload: ReviewDecisionCreate,
    db: Session = Depends(get_db),
    reviewer: User = Depends(require_reviewer),
) -> ReviewDecisionOut:
    inspection = _require_inspection(db, inspection_id)
    check = db.get(ComplianceCheck, payload.compliance_check_id)
    if check is None or check.inspection_id != inspection.id:
        raise HTTPException(status_code=404, detail="Compliance check not found on this inspection.")

    final_status = payload.final_status or ComplianceStatus(check.status)
    review = ReviewDecision(
        compliance_check_id=check.id,
        reviewer_id=reviewer.id,
        decision=payload.decision.value,
        automated_status=check.status,  # the original AI result is preserved, never overwritten
        final_status=final_status.value,
        comment=payload.comment,
        reason=payload.reason,
        additional_evidence=payload.additional_evidence,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    log_action(
        db, actor_id=reviewer.id, action="REVIEW_SUBMITTED", entity_type="compliance_check",
        entity_id=str(check.id), extra={"decision": payload.decision.value, "final_status": final_status.value},
    )
    return ReviewDecisionOut(
        id=review.id, reviewer_id=review.reviewer_id, reviewer_name=reviewer.full_name,
        decision=review.decision, automated_status=review.automated_status, final_status=review.final_status,
        comment=review.comment, reason=review.reason, created_at=review.created_at,
    )


@router.post("/{inspection_id}/report")
def generate_inspection_report(
    inspection_id: uuid.UUID,
    fmt: str = "PDF",
    db: Session = Depends(get_db),
    user: User = Depends(require_any_authenticated),
) -> dict:
    inspection = get_inspection(db, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Inspection not found.")
    if fmt not in ("PDF", "HTML"):
        raise HTTPException(status_code=400, detail="fmt must be 'PDF' or 'HTML'.")

    report = generate_report(db, inspection, user, fmt=fmt)
    log_action(db, actor_id=user.id, action="REPORT_GENERATED", entity_type="inspection", entity_id=str(inspection.id), extra={"format": fmt})
    return {
        "report_id": str(report.id),
        "format": report.format,
        "generated_at": report.generated_at.isoformat(),
        "download_url": f"/api/v1/reports/{report.id}/download",
    }
