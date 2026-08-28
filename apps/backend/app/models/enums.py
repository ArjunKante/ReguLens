"""Shared enumerations used across models, schemas, and the compliance engine.

Keeping these in one module means the rule engine, compliance engine, API
schemas, and frontend TypeScript types (mirrored by hand in
apps/frontend/src/types) all agree on the same vocabulary.
"""
from __future__ import annotations

import enum


class RoleName(str, enum.Enum):
    ADMIN = "ADMIN"
    INSPECTOR = "INSPECTOR"
    REVIEWER = "REVIEWER"


class ProductCategoryCode(str, enum.Enum):
    FOOD = "FOOD"
    COSMETIC_PERSONAL_CARE = "COSMETIC_PERSONAL_CARE"
    HOUSEHOLD = "HOUSEHOLD"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class InspectionStatus(str, enum.Enum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PipelineStage(str, enum.Enum):
    FETCH = "FETCH"
    PARSE = "PARSE"
    IMAGE_DOWNLOAD = "IMAGE_DOWNLOAD"
    IMAGE_QUALITY = "IMAGE_QUALITY"
    OCR = "OCR"
    DECLARATION_EXTRACTION = "DECLARATION_EXTRACTION"
    CLASSIFICATION = "CLASSIFICATION"
    RULE_SELECTION = "RULE_SELECTION"
    COMPLIANCE = "COMPLIANCE"
    CONSISTENCY = "CONSISTENCY"
    REPORT = "REPORT"
    DONE = "DONE"


class PipelineStageStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class EvidenceSourceType(str, enum.Enum):
    """The abstraction referenced in the product brief Section 15 —
    designed so a future PHYSICAL_IMAGE / PHYSICAL_MEASUREMENT source can be
    added without changing any downstream consumer of evidence."""

    ONLINE_LISTING = "ONLINE_LISTING"
    PHYSICAL_IMAGE = "PHYSICAL_IMAGE"  # reserved for future physical module
    USER_INPUT = "USER_INPUT"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class DeclarationSourceType(str, enum.Enum):
    WEBPAGE_TEXT = "WEBPAGE_TEXT"
    STRUCTURED_METADATA = "STRUCTURED_METADATA"
    IMAGE_OCR = "IMAGE_OCR"
    USER_INPUT = "USER_INPUT"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class WebFetchStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED_BY_ROBOTS = "BLOCKED_BY_ROBOTS"
    ACCESS_DENIED = "ACCESS_DENIED"
    TIMEOUT = "TIMEOUT"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


class ExtractionStrategy(str, enum.Enum):
    JSON_LD = "JSON_LD"
    OPEN_GRAPH = "OPEN_GRAPH"
    STRUCTURED_METADATA = "STRUCTURED_METADATA"
    DOM_VISIBLE = "DOM_VISIBLE"
    CSS_SELECTOR = "CSS_SELECTOR"
    FALLBACK_TEXT = "FALLBACK_TEXT"


class ValidationType(str, enum.Enum):
    PRESENCE_CHECK = "PRESENCE_CHECK"
    PATTERN_CHECK = "PATTERN_CHECK"
    NUMERIC_CHECK = "NUMERIC_CHECK"
    DATE_CHECK = "DATE_CHECK"
    CROSS_FIELD_CHECK = "CROSS_FIELD_CHECK"
    CONSISTENCY_CHECK = "CONSISTENCY_CHECK"
    MANUAL_REVIEW_CHECK = "MANUAL_REVIEW_CHECK"


class RuleSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class BatchStatus(str, enum.Enum):
    """Lifecycle of an InspectionBatch (bulk/batch scan + triage queue).

    No FAILED state here — individual items already self-report FAILED via
    InspectionStatus, and the batch as a whole simply finishes once every
    item has resolved, matching the existing "a stage failure never crashes
    the whole run" philosophy in services/pipeline.py."""

    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class ComplianceStatus(str, enum.Enum):
    PASS = "PASS"
    POTENTIAL_NON_COMPLIANCE = "POTENTIAL_NON_COMPLIANCE"
    NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"


class ReviewDecisionType(str, enum.Enum):
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"
    OVERRIDE = "OVERRIDE"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"


class ReportFormat(str, enum.Enum):
    HTML = "HTML"
    PDF = "PDF"
