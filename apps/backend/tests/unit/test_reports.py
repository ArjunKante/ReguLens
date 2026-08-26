"""Report-rendering tests (Demo Hardening: verify officer review + PDF/HTML
report generation, and that a Demo Inspection is unmistakably labeled in
the generated report — a report can be shared/printed independently of the
app UI, so the "DEMO" label must live in the document itself, not just the
inspection-detail page)."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.inspection import Inspection
from app.models.user import User
from app.reports.service import html_to_pdf_bytes, render_report_html


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
