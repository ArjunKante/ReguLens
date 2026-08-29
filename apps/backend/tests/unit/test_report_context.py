"""Report-context aggregation tests (report-layer bug fixes, 2026-08-29).

Covers the reconciliation invariant introduced by these fixes: for every
generated report, Status Summary counts, Priority Findings, Detailed
Findings (status_groups), the Officer Verification Checklist, and the
Cross-Source Consistency Checks section must all derive from the exact same
set of ComplianceCheck rows -- a consistency-check finding must never be
counted in one section and silently absent from another.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.models.compliance import ComplianceCheck
from app.models.inspection import Inspection
from app.models.rules import Rule, RuleVersion
from app.models.user import User
from app.reports.context import build_report_context

_RULE_DEFAULTS = dict(
    version_number=1,
    rule_reference="Rule X",
    description="Test description.",
    requirement="Test requirement.",
    applicability="All in-scope packages.",
    exceptions=None,
    applicable_categories=[],
    excluded_categories=[],
    gating_only=False,
    source_document="Test Source Document",
    source_locator="Rule X",
    is_current=True,
)


def _inspection(db: Session, officer: User) -> Inspection:
    insp = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=officer.id,
        source_url="https://www.flipkart.com/example/p/itm1",
    )
    db.add(insp)
    db.commit()
    db.refresh(insp)
    return insp


def _rule_version(db: Session, rule_key: str, validation_type: str, *, title: str) -> RuleVersion:
    rule = Rule(rule_key=rule_key, active=True)
    db.add(rule)
    db.flush()
    version = RuleVersion(
        rule_id=rule.id,
        title=title,
        validation_type=validation_type,
        severity="MAJOR",
        validator_config={"field": "mrp"} if validation_type == "CONSISTENCY_CHECK" else {},
        **_RULE_DEFAULTS,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def _check(db: Session, inspection: Inspection, rule_version: RuleVersion, status: str) -> ComplianceCheck:
    check = ComplianceCheck(
        inspection_id=inspection.id,
        rule_version_id=rule_version.id,
        status=status,
        reason=f"Test reason for {rule_version.title}.",
        confidence=0.9,
        checked_fields=[],
        engine_version="test",
        executed_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


def _assert_sections_reconcile(ctx) -> None:  # type: ignore[no-untyped-def]
    """The core invariant every one of these tests checks: every section
    that presents check results must agree on the same underlying set."""
    # Status Summary total must equal the number of checks actually shown
    # across all Detailed Findings status groups -- no check silently
    # dropped, none double-counted.
    assert ctx.total_findings == sum(len(v) for v in ctx.status_groups.values())
    for status, count in ctx.status_counts.items():
        assert len(ctx.status_groups.get(status, [])) == count, (
            f"Status Summary says {count} {status}, but Detailed Findings "
            f"shows {len(ctx.status_groups.get(status, []))}"
        )
    # Every POTENTIAL_NON_COMPLIANCE check shown in Detailed Findings must
    # also appear in Priority Findings (the "quick officer triage" list) --
    # regardless of whether it's a rule check or a consistency check.
    detailed_non_compliance_ids = {c.id for c in ctx.status_groups.get("POTENTIAL_NON_COMPLIANCE", [])}
    priority_ids = {c.id for c in ctx.priority_findings}
    assert detailed_non_compliance_ids == priority_ids
    # No check appears twice within priority_findings itself.
    assert len(ctx.priority_findings) == len(priority_ids)


def test_normal_rule_violation_only(db: Session, inspector_user: User):
    inspection = _inspection(db, inspector_user)
    rv = _rule_version(db, "TEST-RULE-VIOLATION", "PRESENCE_CHECK", title="Test rule violation")
    _check(db, inspection, rv, "POTENTIAL_NON_COMPLIANCE")

    db.refresh(inspection)
    ctx = build_report_context(inspection, "Test Officer")

    assert ctx.status_counts["POTENTIAL_NON_COMPLIANCE"] == 1
    assert len(ctx.priority_findings) == 1
    assert ctx.priority_findings[0].rule_version.title == "Test rule violation"
    assert ctx.consistency_rows == []
    _assert_sections_reconcile(ctx)


def test_consistency_violation_only(db: Session, inspector_user: User):
    """REPORT BUG 1 / 2 regression: a consistency-check mismatch must show
    up in the Status Summary count, in Priority Findings, and in the
    dedicated Cross-Source Consistency Checks section -- not silently drop
    out of Priority/Detailed Findings while still being counted above."""
    inspection = _inspection(db, inspector_user)
    rv = _rule_version(
        db, "LMSCAN-CONSISTENCY-MRP-TEST", "CONSISTENCY_CHECK", title="MRP consistency: listing vs. product image"
    )
    _check(db, inspection, rv, "POTENTIAL_NON_COMPLIANCE")

    db.refresh(inspection)
    ctx = build_report_context(inspection, "Test Officer")

    # 1. Status summary counts it.
    assert ctx.status_counts["POTENTIAL_NON_COMPLIANCE"] == 1
    assert ctx.total_findings == 1

    # 2. Priority Findings includes it (this is the bug: it used to be
    #    silently skipped here even though the status summary counted it).
    assert len(ctx.priority_findings) == 1
    assert ctx.priority_findings[0].rule_version.title == "MRP consistency: listing vs. product image"

    # 3. The dedicated consistency section still has its compact row too.
    assert len(ctx.consistency_rows) == 1
    assert ctx.consistency_rows[0]["field_label"] == "MRP"

    _assert_sections_reconcile(ctx)


def test_only_consistency_violations(db: Session, inspector_user: User):
    inspection = _inspection(db, inspector_user)
    rv1 = _rule_version(db, "LMSCAN-CONSISTENCY-MRP-TEST", "CONSISTENCY_CHECK", title="MRP consistency")
    rv2 = _rule_version(db, "LMSCAN-CONSISTENCY-QTY-TEST", "CONSISTENCY_CHECK", title="Net quantity consistency")
    _check(db, inspection, rv1, "POTENTIAL_NON_COMPLIANCE")
    _check(db, inspection, rv2, "POTENTIAL_NON_COMPLIANCE")

    db.refresh(inspection)
    ctx = build_report_context(inspection, "Test Officer")

    assert ctx.status_counts["POTENTIAL_NON_COMPLIANCE"] == 2
    assert len(ctx.priority_findings) == 2
    assert len(ctx.consistency_rows) == 2
    _assert_sections_reconcile(ctx)


def test_mixed_rule_and_consistency_violations(db: Session, inspector_user: User):
    inspection = _inspection(db, inspector_user)
    rule_rv = _rule_version(db, "TEST-RULE-VIOLATION", "PRESENCE_CHECK", title="Test rule violation")
    consistency_rv = _rule_version(
        db, "LMSCAN-CONSISTENCY-MRP-TEST", "CONSISTENCY_CHECK", title="MRP consistency"
    )
    passing_rv = _rule_version(db, "TEST-RULE-PASS", "PRESENCE_CHECK", title="Test rule pass")
    _check(db, inspection, rule_rv, "POTENTIAL_NON_COMPLIANCE")
    _check(db, inspection, consistency_rv, "POTENTIAL_NON_COMPLIANCE")
    _check(db, inspection, passing_rv, "PASS")

    db.refresh(inspection)
    ctx = build_report_context(inspection, "Test Officer")

    assert ctx.status_counts["POTENTIAL_NON_COMPLIANCE"] == 2
    assert ctx.status_counts["PASS"] == 1
    assert ctx.total_findings == 3
    assert len(ctx.priority_findings) == 2
    assert {c.rule_version.title for c in ctx.priority_findings} == {"Test rule violation", "MRP consistency"}
    assert len(ctx.consistency_rows) == 1
    _assert_sections_reconcile(ctx)


def test_no_violations(db: Session, inspector_user: User):
    inspection = _inspection(db, inspector_user)
    rv = _rule_version(db, "TEST-RULE-PASS", "PRESENCE_CHECK", title="Test rule pass")
    _check(db, inspection, rv, "PASS")

    db.refresh(inspection)
    ctx = build_report_context(inspection, "Test Officer")

    assert ctx.status_counts["POTENTIAL_NON_COMPLIANCE"] == 0
    assert ctx.priority_findings == []
    assert ctx.consistency_rows == []
    _assert_sections_reconcile(ctx)


def test_consistency_needs_manual_review_reaches_checklist(db: Session, inspector_user: User):
    """A consistency check that is UNABLE_TO_VERIFY (only one side had
    evidence) must still reach the Officer Verification Checklist like any
    other check in that status, not only rule checks."""
    inspection = _inspection(db, inspector_user)
    rv = _rule_version(
        db, "LMSCAN-CONSISTENCY-MRP-TEST", "CONSISTENCY_CHECK", title="MRP consistency"
    )
    _check(db, inspection, rv, "UNABLE_TO_VERIFY")

    db.refresh(inspection)
    ctx = build_report_context(inspection, "Test Officer")

    assert ctx.status_counts["UNABLE_TO_VERIFY"] == 1
    assert len(ctx.checklist_items) == 1
    assert ctx.checklist_items[0]["item"] == "MRP consistency"
    _assert_sections_reconcile(ctx)
