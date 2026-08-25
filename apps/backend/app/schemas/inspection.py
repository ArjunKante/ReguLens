from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ComplianceStatus, InspectionStatus, PipelineStage, PipelineStageStatus, ReviewDecisionType


class InspectionCreate(BaseModel):
    source_url: str = Field(min_length=8, description="Product listing URL to inspect")
    notes: str | None = None


class InspectionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inspection_number: str
    source_url: str
    platform: str | None
    status: InspectionStatus
    overall_status: ComplianceStatus | None
    officer_id: uuid.UUID
    officer_name: str | None = None
    product_title: str | None = None
    created_at: dt.datetime
    completed_at: dt.datetime | None


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


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    evidence_type: str
    description: str
    reference: dict


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
