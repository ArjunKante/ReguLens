from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RuleSeverity, ValidationType

# Every rule_key actually in use (app/rules/seed_rules.py::SEED_RULES) is an
# uppercase, hyphen-separated identifier, e.g. "LMPC-R6-1E-MRP" or
# "LMSCAN-CONSISTENCY-MRP" -- never anything containing markup. Report
# rendering (app/reports/context.py::break_identifier) relies on exactly
# this shape to justify rendering rule_key with Jinja2 autoescaping bypassed
# (`|safe`) in the generated PDF/HTML report's audit appendix. That reliance
# used to be an unenforced comment; this pattern is what actually makes it
# true, so a rule created/edited via the API can never introduce HTML/script
# content into a rule_key that later gets rendered unescaped.
RULE_KEY_PATTERN = r"^[A-Z0-9]+(-[A-Z0-9]+)*$"


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
    rule_key: str = Field(pattern=RULE_KEY_PATTERN)
