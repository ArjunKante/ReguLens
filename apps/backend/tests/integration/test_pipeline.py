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
from app.models.enums import ComplianceStatus, InspectionStatus, PipelineStage
from app.models.inspection import Inspection, PipelineEvent
from app.models.scraping import WebPage
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


def test_pipeline_handles_manual_scan_with_no_source_url(db: Session, inspector_user: User, loaded_rules, monkeypatch):
    """A "manual scan" inspection (started from uploaded/captured photos
    alone, never given a listing URL — the new direct entry point, not just
    the post-failure fallback) must run the pipeline to completion without
    ever attempting a fetch."""

    def _fail_if_called(*args, **kwargs):
        raise AssertionError(f"scrape_product_page should never be called for a manual scan (args={args!r})")

    monkeypatch.setattr(pipeline_module, "scrape_product_page", _fail_if_called)

    inspection = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=inspector_user.id,
        source_url=None,
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    pipeline_module.run_inspection_pipeline(db, inspection.id)

    db.refresh(inspection)
    assert inspection.status == InspectionStatus.COMPLETED.value
    assert inspection.overall_status is not None
    assert inspection.product_id is None  # no listing was ever fetched, so no Product to link

    fetch_events = (
        db.query(PipelineEvent)
        .filter(PipelineEvent.inspection_id == inspection.id, PipelineEvent.stage == PipelineStage.FETCH.value)
        .all()
    )
    assert any("no listing url" in (e.message or "").lower() for e in fetch_events)


def test_reanalysis_does_not_duplicate_declarations_or_compliance_checks(
    db: Session, inspector_user: User, loaded_rules, monkeypatch
):
    """P0 audit fix: "re-analysis duplication" — re-running the pipeline for
    the same inspection (e.g. POST .../analyze after uploading another
    screenshot) must recompute declarations/compliance findings/auto-fetched
    evidence from scratch, not append a second copy of each alongside the
    first run's."""
    html = (FIXTURES / "success_listing.html").read_text(encoding="utf-8")
    url = "https://blinkit.com/prn/tasty-munch/prid/12345"

    monkeypatch.setattr(
        "app.services.scraping_service.get_scraper_for_url",
        lambda u: BlinkitScraper(fetcher=StaticHTMLFetcher(html=html, url=u)),
    )
    monkeypatch.setattr(pipeline_module, "download_image", lambda url: None)

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
    first_declaration_count = db.query(Declaration).filter(Declaration.inspection_id == inspection.id).count()
    first_check_count = db.query(ComplianceCheck).filter(ComplianceCheck.inspection_id == inspection.id).count()
    first_webpage_count = db.query(WebPage).filter(WebPage.inspection_id == inspection.id).count()
    assert first_declaration_count > 0
    assert first_check_count > 0

    # Re-run exactly as .../analyze would (same inspection, same evidence source).
    pipeline_module.run_inspection_pipeline(db, inspection.id)
    db.refresh(inspection)
    second_declaration_count = db.query(Declaration).filter(Declaration.inspection_id == inspection.id).count()
    second_check_count = db.query(ComplianceCheck).filter(ComplianceCheck.inspection_id == inspection.id).count()
    second_webpage_count = db.query(WebPage).filter(WebPage.inspection_id == inspection.id).count()

    assert second_declaration_count == first_declaration_count
    assert second_check_count == first_check_count
    assert second_webpage_count == first_webpage_count == 1
    assert inspection.status == InspectionStatus.COMPLETED.value


def test_pipeline_flags_hollow_success_when_fetch_succeeds_with_no_product_data(
    db: Session, inspector_user: User, loaded_rules, monkeypatch
):
    """Demo Hardening regression: a live-listing test found a real "false
    success" mode — the HTTP fetch returns 200 (fetch_status is honestly
    SUCCESS) but the page never actually rendered any product content at
    all (a real Blinkit listing that requires a delivery-location context a
    stateless fetch never provides, silently serving its generic app-shell/
    homepage instead — zero <h1>, zero usable declarations). This must be
    flagged with an actionable FETCH-stage event, not silently completed as
    if it were a normal, successful, near-empty inspection."""
    html = "<html><head><title>Generic App Homepage</title></head><body>Nothing product-specific here.</body></html>"
    monkeypatch.setattr(
        "app.services.scraping_service.get_scraper_for_url",
        lambda u: BlinkitScraper(fetcher=StaticHTMLFetcher(html=html, url=u)),
    )
    monkeypatch.setattr(pipeline_module, "download_image", lambda url: None)

    inspection = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=inspector_user.id,
        source_url="https://blinkit.com/prn/some-product/prid/1",
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    pipeline_module.run_inspection_pipeline(db, inspection.id)

    db.refresh(inspection)
    assert inspection.status == InspectionStatus.COMPLETED.value
    fetch_events = (
        db.query(PipelineEvent)
        .filter(PipelineEvent.inspection_id == inspection.id, PipelineEvent.stage == PipelineStage.FETCH.value)
        .all()
    )
    assert any(
        e.status == "FAILED" and "no product name/details could be extracted" in (e.message or "")
        for e in fetch_events
    )

    # The hollow flag must be persisted on the WebPage row (not just logged
    # as a PipelineEvent), and the compliance engine must actually treat it
    # as "no real evidence" rather than a genuinely successful, complete
    # scrape — with zero images either, that means UNABLE_TO_VERIFY across
    # the board, not a confident POTENTIAL_NON_COMPLIANCE against data that
    # was never really retrieved.
    web_page = db.query(WebPage).filter(WebPage.inspection_id == inspection.id).one()
    assert web_page.hollow is True
    assert inspection.overall_status == ComplianceStatus.UNABLE_TO_VERIFY.value


def test_pipeline_flags_hollow_success_even_when_a_generic_og_title_is_present(
    db: Session, inspector_user: User, loaded_rules, monkeypatch
):
    """Regression on the hollow-success detection itself: a real recurrence
    of the gated-Blinkit-homepage case had an og:title set to the site's
    own generic tagline ("30,000+ products delivered to your doorstep |
    Blinkit"), which the generic OpenGraph strategy dutifully reported as a
    product_name candidate — satisfying the original "no product_name
    candidate at all" check while still being zero real product data. Must
    still be flagged when product_name is the *only* field found."""
    html = (
        "<html><head>"
        '<meta property="og:title" content="30,000+ products delivered to your doorstep | Blinkit">'
        "</head><body>Nothing product-specific here.</body></html>"
    )
    monkeypatch.setattr(
        "app.services.scraping_service.get_scraper_for_url",
        lambda u: BlinkitScraper(fetcher=StaticHTMLFetcher(html=html, url=u)),
    )
    monkeypatch.setattr(pipeline_module, "download_image", lambda url: None)

    inspection = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=inspector_user.id,
        source_url="https://blinkit.com/prn/some-product/prid/1",
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    pipeline_module.run_inspection_pipeline(db, inspection.id)

    db.refresh(inspection)
    assert inspection.status == InspectionStatus.COMPLETED.value
    fetch_events = (
        db.query(PipelineEvent)
        .filter(PipelineEvent.inspection_id == inspection.id, PipelineEvent.stage == PipelineStage.FETCH.value)
        .all()
    )
    assert any(
        e.status == "FAILED" and "no product name/details could be extracted" in (e.message or "")
        for e in fetch_events
    )

    web_page = db.query(WebPage).filter(WebPage.inspection_id == inspection.id).one()
    assert web_page.hollow is True
    assert inspection.overall_status == ComplianceStatus.UNABLE_TO_VERIFY.value


def test_pipeline_does_not_flag_a_real_scrape_that_only_found_a_name_and_one_other_field(
    db: Session, inspector_user: User, loaded_rules, monkeypatch
):
    """The other side of the same fix: a real (if partial) scrape that
    found the product name plus at least one other field must NOT be
    flagged as hollow."""
    html = (
        "<html><head>"
        '<meta property="og:title" content="Amul Moti Toned Milk (90 Days Shelf Life)">'
        '<script type="application/ld+json">{"@type":"Product","name":"Amul Moti Toned Milk",'
        '"manufacturer":{"name":"Amul"}}</script>'
        "</head><body></body></html>"
    )
    monkeypatch.setattr(
        "app.services.scraping_service.get_scraper_for_url",
        lambda u: BlinkitScraper(fetcher=StaticHTMLFetcher(html=html, url=u)),
    )
    monkeypatch.setattr(pipeline_module, "download_image", lambda url: None)

    inspection = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=inspector_user.id,
        source_url="https://blinkit.com/prn/amul-moti-toned-milk/prid/34778",
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    pipeline_module.run_inspection_pipeline(db, inspection.id)

    db.refresh(inspection)
    assert inspection.status == InspectionStatus.COMPLETED.value
    fetch_events = (
        db.query(PipelineEvent)
        .filter(PipelineEvent.inspection_id == inspection.id, PipelineEvent.stage == PipelineStage.FETCH.value)
        .all()
    )
    assert not any("no product name/details could be extracted" in (e.message or "") for e in fetch_events)

    web_page = db.query(WebPage).filter(WebPage.inspection_id == inspection.id).one()
    assert web_page.hollow is False


def test_pipeline_records_total_duration_as_a_done_stage_event(
    db: Session, inspector_user: User, loaded_rules, monkeypatch
):
    """Demo Hardening: "measure pipeline execution time" — the total
    end-to-end wall-clock duration must be recorded and readable back."""
    html = (FIXTURES / "success_listing.html").read_text(encoding="utf-8")
    monkeypatch.setattr(
        "app.services.scraping_service.get_scraper_for_url",
        lambda u: BlinkitScraper(fetcher=StaticHTMLFetcher(html=html, url=u)),
    )
    monkeypatch.setattr(pipeline_module, "download_image", lambda url: None)

    inspection = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=inspector_user.id,
        source_url="https://blinkit.com/prn/tasty-munch/prid/12345",
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    pipeline_module.run_inspection_pipeline(db, inspection.id)

    done_events = (
        db.query(PipelineEvent)
        .filter(PipelineEvent.inspection_id == inspection.id, PipelineEvent.stage == PipelineStage.DONE.value)
        .all()
    )
    assert len(done_events) == 1
    assert done_events[0].status == "SUCCEEDED"
    assert done_events[0].duration_ms is not None
    assert done_events[0].duration_ms >= 0


def test_demo_inspection_pipeline_runs_end_to_end_with_no_network_mocking(
    db: Session, inspector_user: User, loaded_rules
):
    """Demo Hardening: "add a controlled Demo Inspection mode" — a demo
    inspection must run to completion using only the bundled fixture, with
    NO scraper/download mocking needed at all (unlike every other pipeline
    test here), proving it genuinely never touches the network."""
    from app.demo_fixtures import DEMO_SOURCE_URL

    inspection = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=inspector_user.id,
        source_url=DEMO_SOURCE_URL,
        is_demo=True,
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    pipeline_module.run_inspection_pipeline(db, inspection.id)

    db.refresh(inspection)
    assert inspection.status == InspectionStatus.COMPLETED.value
    assert inspection.overall_status is not None
    assert inspection.platform == "flipkart"

    web_pages = db.query(WebPage).filter(WebPage.inspection_id == inspection.id).all()
    assert len(web_pages) == 1
    assert web_pages[0].scraper_name == "StaticHTMLFetcher"

    declarations = db.query(Declaration).filter(Declaration.inspection_id == inspection.id).count()
    assert declarations > 0


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
