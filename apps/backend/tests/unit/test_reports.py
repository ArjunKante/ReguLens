"""Report-rendering tests (Demo Hardening: verify officer review + PDF/HTML
report generation, and that a Demo Inspection is unmistakably labeled in
the generated report — a report can be shared/printed independently of the
app UI, so the "DEMO" label must live in the document itself, not just the
inspection-detail page)."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.models.compliance import ComplianceCheck
from app.models.inspection import Inspection
from app.models.rules import Rule, RuleVersion
from app.models.user import User
from app.reports import service as report_service
from app.reports.service import generate_report, html_to_pdf_bytes, render_report_html


def _inspection(db: Session, officer: User, *, is_demo: bool) -> Inspection:
    insp = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=officer.id,
        source_url="https://www.flipkart.com/example/p/itm1",
        is_demo=is_demo,
    )
    db.add(insp)
    db.commit()
    db.refresh(insp)
    return insp


def test_demo_inspection_report_carries_an_unmistakable_demo_banner(db: Session, inspector_user: User):
    inspection = _inspection(db, inspector_user, is_demo=True)
    html = render_report_html(inspection, "Test Officer")
    assert "DEMO" in html
    assert "DEMO INSPECTION" in html
    assert "not a finding about a real, currently-live listing" in html.lower() or "not a finding about a real" in html


def test_real_inspection_report_has_no_demo_banner(db: Session, inspector_user: User):
    inspection = _inspection(db, inspector_user, is_demo=False)
    html = render_report_html(inspection, "Test Officer")
    assert "DEMO INSPECTION" not in html
    # The CSS class is always defined in <style> (harmless either way) —
    # what must be absent is the div that actually uses it.
    assert '<div class="demo-banner">' not in html


def test_report_html_converts_to_a_nonempty_pdf(db: Session, inspector_user: User):
    inspection = _inspection(db, inspector_user, is_demo=False)
    html = render_report_html(inspection, "Test Officer")
    pdf_bytes = html_to_pdf_bytes(html)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def _consistency_check(db: Session, inspection: Inspection, *, status: str) -> ComplianceCheck:
    rule = Rule(rule_key="LMSCAN-CONSISTENCY-MRP-TEST", active=True)
    db.add(rule)
    db.flush()
    version = RuleVersion(
        rule_id=rule.id,
        version_number=1,
        rule_reference="Rule X",
        title="MRP consistency: listing vs. product image",
        description="Test.",
        requirement="Test.",
        applicability="All.",
        exceptions=None,
        validation_type="CONSISTENCY_CHECK",
        severity="MAJOR",
        validator_config={"field": "mrp"},
        applicable_categories=[],
        excluded_categories=[],
        gating_only=False,
        source_document="LM-SCAN internal engineering rule",
        source_locator="N/A",
        is_current=True,
    )
    db.add(version)
    db.flush()
    check = ComplianceCheck(
        inspection_id=inspection.id,
        rule_version_id=version.id,
        status=status,
        reason="Potential inconsistency detected for 'mrp': listing page shows Rs. 100, image shows Rs. 120.",
        confidence=0.9,
        checked_fields=["mrp"],
        engine_version="test",
        executed_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


def test_rendered_report_shows_consistency_violation_in_priority_findings(db: Session, inspector_user: User):
    """REPORT BUG 1/2 regression at the HTML-render level: a consistency
    mismatch must appear in the rendered Priority Findings section, and the
    report must not simultaneously claim (in the same document) that no
    potential non-compliance findings were identified."""
    inspection = _inspection(db, inspector_user, is_demo=False)
    _consistency_check(db, inspection, status="POTENTIAL_NON_COMPLIANCE")

    db.refresh(inspection)
    html = render_report_html(inspection, "Test Officer")

    priority_section = html.split("Priority Findings</h2>", 1)[1].split("Officer Verification Checklist", 1)[0]
    assert "MRP consistency: listing vs. product image" in priority_section
    assert "No potential non-compliance findings were identified" not in priority_section

    # The Status Summary block must also show a nonzero count for the same
    # status this finding carries, not just Priority Findings.
    assert '<div class="status-block-count">1</div><div class="status-block-label">POTENTIAL NON-COMPLIANCE</div>' in html


def test_generate_report_builds_context_exactly_once(db: Session, inspector_user: User, monkeypatch):
    """REPORT BUG 4 regression: generate_report must call build_report_context
    exactly once per report, not once inside HTML rendering and again for
    app_version/disclaimer/rule_version_snapshot metadata."""
    inspection = _inspection(db, inspector_user, is_demo=False)

    call_count = 0
    original = report_service.build_report_context

    def _counting_build_report_context(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(report_service, "build_report_context", _counting_build_report_context)

    generate_report(db, inspection, inspector_user, fmt="HTML")

    assert call_count == 1
