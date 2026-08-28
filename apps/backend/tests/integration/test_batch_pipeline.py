"""Bulk/batch scan integration test (Section 30/48 follow-on: "reduces
manual search" for real, not just per-URL verification).

Exercises the whole new surface end-to-end against saved HTML fixtures
(never a live network/Playwright call, per Section 36): batch creation
(including input validation), the fan-out runner
(`app/services/batch_pipeline.py`), and the triage ranking
(`app/services/triage.py`) that sorts the resulting queue worst-first.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models.enums import BatchStatus, ComplianceStatus, InspectionStatus
from app.models.inspection import Inspection
from app.models.user import User
from app.repositories.batch_repository import create_batch, get_batch
from app.rules.loader import load_rules
from app.scraping.blinkit import BlinkitScraper
from app.scraping.fetcher import StaticHTMLFetcher
from app.services import batch_pipeline as batch_pipeline_module
from app.services import pipeline as pipeline_module
from app.services.triage import triage_sort_key

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "html"


@pytest.fixture()
def loaded_rules(db: Session):
    load_rules(db)


def test_batch_rejects_invalid_urls_without_dropping_them_silently(db: Session, inspector_user: User):
    batch, rejected = create_batch(
        db, officer=inspector_user, name="Validation test",
        urls=["https://blinkit.com/prn/a/prid/1", "", "https://blinkit.com/prn/a/prid/1"],
    )
    assert batch.total_count == 1
    assert len(rejected) == 2  # the blank entry, and the exact duplicate
    assert batch.rejected_urls == rejected


def test_batch_scan_completes_and_ranks_worst_first(
    db: Session, inspector_user: User, loaded_rules, monkeypatch
):
    good_html = (FIXTURES / "success_listing.html").read_text(encoding="utf-8")
    bad_html = (FIXTURES / "missing_declaration.html").read_text(encoding="utf-8")
    good_url = "https://blinkit.com/prn/tasty-munch/prid/12345"
    bad_url = "https://blinkit.com/prn/incomplete-listing/prid/99999"

    def _scraper_for(url: str) -> BlinkitScraper:
        html = bad_html if url == bad_url else good_html
        return BlinkitScraper(fetcher=StaticHTMLFetcher(html=html, url=url))

    monkeypatch.setattr("app.services.scraping_service.get_scraper_for_url", _scraper_for)
    monkeypatch.setattr(pipeline_module, "download_image", lambda url: None)  # no real network in tests

    batch, rejected = create_batch(
        db, officer=inspector_user, name="Test sweep", urls=[good_url, bad_url]
    )
    assert rejected == []
    assert batch.total_count == 2
    assert batch.status == BatchStatus.CREATED.value

    batch_pipeline_module.run_batch_new_session(batch.id)

    db.refresh(batch)
    assert batch.status == BatchStatus.COMPLETED.value
    assert batch.completed_at is not None

    items = db.query(Inspection).filter(Inspection.batch_id == batch.id).all()
    assert len(items) == 2
    assert all(i.status == InspectionStatus.COMPLETED.value for i in items)
    assert all(i.overall_status is not None for i in items)

    loaded = get_batch(db, batch.id)
    assert loaded is not None
    ranked = sorted(loaded.inspections, key=triage_sort_key)

    # The incomplete listing (manufacturer/consumer-care absent, otherwise
    # complete evidence) must carry a POTENTIAL_NON_COMPLIANCE finding and
    # therefore rank ahead of the complete listing in the triage queue.
    assert ranked[0].source_url == bad_url
    assert ranked[0].overall_status == ComplianceStatus.POTENTIAL_NON_COMPLIANCE.value
