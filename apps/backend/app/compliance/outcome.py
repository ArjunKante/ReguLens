"""The generic result type every validator returns. The compliance engine
turns this into ComplianceCheck / Violation / Evidence rows — validators
never touch the ORM directly, keeping rule logic testable in isolation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.enums import ComplianceStatus


@dataclass
class EvidenceRef:
    evidence_type: str  # WEBPAGE_TEXT | IMAGE_OCR | SCREENSHOT | MANUAL
    description: str
    reference: dict[str, Any] = field(default_factory=dict)
    declaration_id: str | None = None


@dataclass
class ValidationOutcome:
    status: ComplianceStatus
    reason: str
    confidence: float
    checked_fields: list[str] = field(default_factory=list)
    evidence: list[EvidenceRef] = field(default_factory=list)
