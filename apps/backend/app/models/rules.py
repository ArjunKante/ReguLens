from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import RuleSeverity, ValidationType
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Rule(Base, UUIDPKMixin, TimestampMixin):
    """The stable identity of a rule (e.g. LMPC-R6-1E-MRP). The content that
    can legally change over time (requirement text, effective dates, ...)
    lives on RuleVersion so historical inspections stay reproducible
    (Section 12)."""

    __tablename__ = "rules"
    __table_args__ = (
        # Defense in depth alongside the API-layer pattern validation
        # (app/schemas/rules.py::RULE_KEY_PATTERN) — report rendering
        # (app/reports/context.py::break_identifier) renders rule_key with
        # HTML-escaping bypassed on the assumption it is always an
        # uppercase/digit/hyphen identifier, so that assumption must hold at
        # the database layer too, not only at the one API endpoint that
        # currently creates rows here. POSIX ERE via Postgres's `~`, since
        # SQLAlchemy has no cross-dialect regex-match construct.
        CheckConstraint(
            r"rule_key ~ '^[A-Z0-9]+(-[A-Z0-9]+)*$'",
            name="ck_rules_rule_key_format",
        ),
    )

    rule_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    versions: Mapped[list["RuleVersion"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan", order_by="RuleVersion.version_number"
    )


class RuleVersion(Base, UUIDPKMixin):
    """An immutable snapshot of a rule's content. Every ComplianceCheck
    stores a foreign key to the exact RuleVersion that was evaluated, so
    editing a rule later (via the Rule Management UI) never changes what a
    past inspection shows (Section 12: rule versioning)."""

    __tablename__ = "rule_versions"
    __table_args__ = (UniqueConstraint("rule_id", "version_number", name="uq_rule_version"),)

    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rules.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    rule_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirement: Mapped[str] = mapped_column(Text, nullable=False)
    applicability: Mapped[str] = mapped_column(Text, nullable=False)
    exceptions: Mapped[str | None] = mapped_column(Text, nullable=True)

    validation_type: Mapped[ValidationType] = mapped_column(String(32), nullable=False)
    severity: Mapped[RuleSeverity] = mapped_column(String(16), nullable=False)

    # Validator configuration, e.g. {"field": "mrp", "pattern": "..."}. Interpreted by
    # app/rules/validators.py — keeps validator logic generic/data-driven (Section 11).
    validator_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    applicable_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    """Empty list == applies to all categories."""

    excluded_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    """Categories this rule explicitly does NOT apply to (e.g. FOOD, per Explanation III)."""

    gating_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """If true, this rule is applied internally (e.g. small-package exemption) and never
    surfaced as its own standalone ComplianceCheck row."""

    source_document: Mapped[str] = mapped_column(Text, nullable=False)
    source_locator: Mapped[str] = mapped_column(String(255), nullable=False)

    effective_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    effective_until: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rule: Mapped[Rule] = relationship(back_populates="versions")
