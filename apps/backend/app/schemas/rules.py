from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import RuleSeverity, ValidationType


class RuleVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    rule_reference: str
    title: str
    description: str
    requirement: str
    applicability: str
    exceptions: str | None
    validation_type: ValidationType
    severity: RuleSeverity
    validator_config: dict
    applicable_categories: list[str]
    excluded_categories: list[str]
    gating_only: bool
    source_document: str
    source_locator: str
    effective_from: dt.date | None
    effective_until: dt.date | None
    notes: str | None
    is_current: bool
    created_at: dt.datetime


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_key: str
    active: bool
    current_version: RuleVersionOut | None


class RuleVersionCreate(BaseModel):
    rule_reference: str
    title: str
    description: str
    requirement: str
    applicability: str
    exceptions: str | None = None
    validation_type: ValidationType
    severity: RuleSeverity
    validator_config: dict = {}
    applicable_categories: list[str] = []
    excluded_categories: list[str] = []
    source_document: str
    source_locator: str
    effective_from: dt.date | None = None
    effective_until: dt.date | None = None
    notes: str | None = None


class RuleCreate(RuleVersionCreate):
    rule_key: str
