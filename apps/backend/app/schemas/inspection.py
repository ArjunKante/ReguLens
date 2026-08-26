from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ComplianceStatus, InspectionStatus, PipelineStage, PipelineStageStatus, ReviewDecisionType


class InspectionCreate(BaseModel):
    # Optional: omit (or send null) to start a "manual scan" inspection —
    # evidence comes entirely from uploaded/captured photos, with no
    # marketplace listing to fetch. When provided, still must look like a
    # real URL (min_length enforced only on an actual value — Pydantic
    # doesn't run str constraints against None in an Optional field).
    source_url: str | None = Field(default=None, min_length=8, description="Product listing URL to inspect (omit for a manual, photo-only scan)")
    notes: str | None = None


class InspectionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inspection_number: str
    source_url: str | None
    platform: str | None
    status: InspectionStatus
    overall_status: ComplianceStatus | None
    officer_id: uuid.UUID
    officer_name: str | None = None
    product_title: str | None = None
    created_at: dt.datetime
    completed_at: dt.datetime | None
    is_demo: bool = False


class PipelineEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stage: PipelineStage
    status: PipelineStageStatus
    message: str | None
    duration_ms: int | None
    created_at: dt.datetime


class DeclarationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    field_name: str
    value: str | None
    normalized_value: str | None
    source_type: str
    confidence: float
    extraction_method: str | None
    # Exposed so the frontend can trace a declaration back to the exact
    # image/OCR block that produced it (e.g. to highlight the matching
    # bounding box) — the data already existed on the model, it just
    # wasn't serialized out before (Demo Hardening: "make rule -> evidence
    # -> finding traceability obvious").
    source_product_image_id: uuid.UUID | None = None
    source_ocr_result_id: uuid.UUID | None = None
    source_web_page_id: uuid.UUID | None = None


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    evidence_type: str
    description: str
    reference: dict
    declaration_id: uuid.UUID | None = None


class ViolationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    severity: str
    summary: str
    details: str


class ReviewDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewer_name: str | None = None
    decision: ReviewDecisionType
    automated_status: ComplianceStatus
    final_status: ComplianceStatus
    comment: str | None
    reason: str | None
    created_at: dt.datetime


class RuleVersionBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rule_key: str
    rule_reference: str
    title: str
    requirement: str
    severity: str
    source_document: str
    source_locator: str
    version_number: int


class ComplianceCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: ComplianceStatus
    reason: str
    confidence: float
    checked_fields: list[str]
    rule: RuleVersionBrief
    violation: ViolationOut | None
    evidence: list[EvidenceOut]
    review_decisions: list[ReviewDecisionOut]


class OCRResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    engine: str
    text: str
    confidence: float
    bounding_box: dict | None
    """{x, y, width, height} in source-image pixels, or None if the OCR
    engine didn't report a region for this block."""


class ProductImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_type: str
    original_url: str | None
    width: int | None
    height: int | None
    is_blurry: bool | None
    contrast_score: float | None
    glare_detected: bool | None
    quality_acceptable: bool | None
    quality_notes: str | None
    ocr_results: list[OCRResultOut] = []


class WebPageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    url: str
    fetch_status: str
    http_status_code: int | None
    error_message: str | None
    robots_txt_allowed: bool | None
    scraper_name: str | None
    fetched_at: dt.datetime


class InspectionDetail(InspectionSummary):
    notes: str | None
    declarations: list[DeclarationOut]
    compliance_checks: list[ComplianceCheckOut]
    images: list[ProductImageOut]
    web_pages: list[WebPageOut]
    pipeline_events: list[PipelineEventOut]
    pipeline_duration_ms: int | None = None


class ReviewDecisionCreate(BaseModel):
    compliance_check_id: uuid.UUID
    decision: ReviewDecisionType
    final_status: ComplianceStatus | None = None
    comment: str | None = None
    reason: str | None = None
    additional_evidence: str | None = None


class ManualDeclarationCreate(BaseModel):
    field_name: str
    value: str = Field(min_length=1)
