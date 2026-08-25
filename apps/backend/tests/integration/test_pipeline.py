"""End-to-end pipeline test (Section 30/52): FETCH through REPORT-readiness,
using a static HTML fixture instead of a live network/Playwright call (per
Section 36, live scraping is never exercised by the normal test suite)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models.compliance import ComplianceCheck
from app.models.declaration import Declaration
from app.models.enums import InspectionStatus, PipelineStage
from app.models.inspection import Inspection, PipelineEvent
from app.models.user import User
from app.rules.loader import load_rules
from app.scraping.blinkit import BlinkitScraper
from app.scraping.fetcher import StaticHTMLFetcher
from app.services import pipeline as pipeline_module

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "html"


@pytest.fixture()
def loaded_rules(db: Session):
    load_rules(db)


def test_full_pipeline_runs_all_stages_and_produces_compliance_checks(
    db: Session, inspector_user: User, loaded_rules, monkeypatch
):
    html = (FIXTURES / "success_listing.html").read_text(encoding="utf-8")
    url = "https://blinkit.com/prn/tasty-munch/prid/12345"

    monkeypatch.setattr(
        "app.services.scraping_service.get_scraper_for_url",
        lambda u: BlinkitScraper(fetcher=StaticHTMLFetcher(html=html, url=u)),
    )
    monkeypatch.setattr(pipeline_module, "download_image", lambda url: None)  # no real network in tests

    inspection = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=inspector_user.id,
        source_url=url,
        platform=None,
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    pipeline_module.run_inspection_pipeline(db, inspection.id)

    db.refresh(inspection)
    assert inspection.status == InspectionStatus.COMPLETED.value
    assert inspection.overall_status is not None
    assert inspection.product_id is not None

    events = db.query(PipelineEvent).filter(PipelineEvent.inspection_id == inspection.id).all()
    stages_seen = {e.stage for e in events}
    expected_stages = {s.value for s in PipelineStage if s != PipelineStage.DONE}
    assert expected_stages.issubset(stages_seen)

    declarations = db.query(Declaration).filter(Declaration.inspection_id == inspection.id).all()
    assert len(declarations) > 0
    field_names = {d.field_name for d in declarations}
    assert "mrp" in field_names
    assert "net_quantity" in field_names

    checks = db.query(ComplianceCheck).filter(ComplianceCheck.inspection_id == inspection.id).all()
    assert len(checks) >= 14  # at least the LMPC rules; consistency rules mostly UNABLE_TO_VERIFY (no images)


def test_pipeline_handles_fetch_failure_gracefully(db: Session, inspector_user: User, loaded_rules, monkeypatch):
    """Section 25/26: a failed fetch must not crash the pipeline or leave
    the inspection stuck — it should complete with UNABLE_TO_VERIFY-heavy
    results, ready for the officer to fall back to screenshot upload."""
    from app.models.enums import WebFetchStatus

    monkeypatch.setattr(
        "app.services.scraping_service.get_scraper_for_url",
        lambda u: BlinkitScraper(fetcher=StaticHTMLFetcher(html="", url=u, status=WebFetchStatus.BLOCKED_BY_ROBOTS.value)),
    )
    monkeypatch.setattr(pipeline_module, "download_image", lambda url: None)

    inspection = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=inspector_user.id,
        source_url="https://blinkit.com/blocked",
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    pipeline_module.run_inspection_pipeline(db, inspection.id)

    db.refresh(inspection)
    assert inspection.status == InspectionStatus.COMPLETED.value
    assert inspection.overall_status is not None
