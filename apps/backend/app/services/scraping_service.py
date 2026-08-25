"""Glues the pure scraping logic (app/scraping) to persistence: creates the
WebPage / WebExtraction rows an inspection needs, and raw HTML is saved to
storage for auditability (Section 27: "raw page metadata should be retained
where appropriate")."""
from __future__ import annotations

import datetime as dt
import hashlib

from sqlalchemy.orm import Session

from app.models.enums import WebFetchStatus
from app.models.inspection import Inspection
from app.models.scraping import WebExtraction, WebPage
from app.scraping.data import ScrapedProduct
from app.scraping.registry import get_scraper_for_url
from app.storage.files import save_raw_html


def scrape_product_page(db: Session, inspection: Inspection, url: str) -> tuple[WebPage, ScrapedProduct | None]:
    scraper = get_scraper_for_url(url)
    fetch_result = scraper.fetch_page(url)

    raw_html_path = None
    page_hash = None
    if fetch_result.html:
        page_hash = hashlib.sha256(fetch_result.html.encode()).hexdigest()
        raw_html_path = save_raw_html(inspection.id, fetch_result.html)

    web_page = WebPage(
        inspection_id=inspection.id,
        url=fetch_result.url,
        platform=scraper.platform_name,
        fetch_status=fetch_result.status,
        http_status_code=fetch_result.http_status_code,
        error_message=fetch_result.error_message,
        robots_txt_allowed=fetch_result.robots_txt_allowed,
        robots_txt_checked_at=dt.datetime.now(dt.timezone.utc) if fetch_result.robots_txt_allowed is not None else None,
        scraper_name=fetch_result.scraper_name or scraper.__class__.__name__,
        scraper_version=fetch_result.scraper_version,
        page_hash=page_hash,
        raw_html_path=raw_html_path,
        raw_metadata=fetch_result.raw_metadata,
        fetched_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(web_page)
    db.flush()

    if fetch_result.status != WebFetchStatus.SUCCESS.value or not fetch_result.html:
        db.commit()
        return web_page, None

    product = scraper.extract_product_data(fetch_result.html, fetch_result.url)

    for candidate in product.field_candidates:
        db.add(
            WebExtraction(
                web_page_id=web_page.id,
                strategy=candidate.strategy.value,
                field_name=candidate.field_name,
                field_value=candidate.value,
                confidence=candidate.confidence,
                raw_snippet=candidate.raw_snippet,
            )
        )

    db.commit()
    db.refresh(web_page)
    return web_page, product
