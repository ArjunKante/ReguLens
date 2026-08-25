"""The network I/O boundary of the scraping subsystem.

This is deliberately the ONLY module that touches Playwright / makes live
HTTP requests to a marketplace. Everything downstream (extraction logic)
operates on plain HTML strings, so it can be tested with saved fixtures
(Section 36) without a browser or network access.
"""
from __future__ import annotations

import hashlib
from typing import Protocol

from app.core.config import get_settings
from app.models.enums import WebFetchStatus
from app.scraping.data import FetchResult
from app.scraping.robots import enforce_rate_limit, is_allowed

settings = get_settings()

SCRAPER_VERSION = "1.0.0"


class PageFetcher(Protocol):
    def fetch(self, url: str) -> FetchResult: ...


class PlaywrightPageFetcher:
    """Fetches a page with a real (headless) browser so client-rendered
    marketplace listings resolve, while still respecting robots.txt, using a
    clearly-identifying User-Agent, and applying a per-domain rate limit
    (Section 3/4)."""

    def fetch(self, url: str) -> FetchResult:
        allowed = is_allowed(url)
        if allowed is None:
            return FetchResult(
                status=WebFetchStatus.FAILED.value,
                url=url,
                error_message="robots.txt could not be retrieved/parsed; refusing to scrape as a precaution.",
                robots_txt_allowed=None,
                scraper_version=SCRAPER_VERSION,
            )
        if allowed is False:
            return FetchResult(
                status=WebFetchStatus.BLOCKED_BY_ROBOTS.value,
                url=url,
                error_message="robots.txt disallows automated access to this URL.",
                robots_txt_allowed=False,
                scraper_version=SCRAPER_VERSION,
            )

        enforce_rate_limit(url)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return FetchResult(
                status=WebFetchStatus.FAILED.value,
                url=url,
                error_message="Playwright is not installed in this environment.",
                robots_txt_allowed=True,
                scraper_version=SCRAPER_VERSION,
            )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=settings.playwright_headless)
                try:
                    context = browser.new_context(user_agent=settings.scraper_user_agent)
                    page = context.new_page()
                    response = page.goto(
                        url,
                        timeout=settings.scraper_request_timeout_seconds * 1000,
                        wait_until="domcontentloaded",
                    )
                    page.wait_for_timeout(1500)  # let client-rendered content settle
                    html = page.content()
                    status_code = response.status if response else None

                    if status_code is not None and status_code in (401, 403):
                        return FetchResult(
                            status=WebFetchStatus.ACCESS_DENIED.value,
                            url=url,
                            http_status_code=status_code,
                            error_message=f"Server returned HTTP {status_code}; access appears restricted.",
                            robots_txt_allowed=True,
                            scraper_version=SCRAPER_VERSION,
                        )
                    if status_code is not None and status_code == 429:
                        return FetchResult(
                            status=WebFetchStatus.ACCESS_DENIED.value,
                            url=url,
                            http_status_code=status_code,
                            error_message="Server returned HTTP 429 (rate limited); stopping gracefully.",
                            robots_txt_allowed=True,
                            scraper_version=SCRAPER_VERSION,
                        )
                    if status_code is not None and status_code >= 400:
                        return FetchResult(
                            status=WebFetchStatus.FAILED.value,
                            url=url,
                            http_status_code=status_code,
                            error_message=f"Server returned HTTP {status_code}.",
                            robots_txt_allowed=True,
                            scraper_version=SCRAPER_VERSION,
                        )

                    return FetchResult(
                        status=WebFetchStatus.SUCCESS.value,
                        url=page.url,
                        html=html,
                        http_status_code=status_code,
                        robots_txt_allowed=True,
                        scraper_name="PlaywrightPageFetcher",
                        scraper_version=SCRAPER_VERSION,
                        raw_metadata={"final_url": page.url, "page_hash": hashlib.sha256(html.encode()).hexdigest()},
                    )
                finally:
                    browser.close()
        except Exception as exc:  # noqa: BLE001 — any Playwright/browser failure must degrade gracefully
            message = str(exc)
            status = WebFetchStatus.TIMEOUT.value if "Timeout" in message else WebFetchStatus.FAILED.value
            return FetchResult(
                status=status,
                url=url,
                error_message=f"Automatic page extraction unavailable: {message[:500]}",
                robots_txt_allowed=True,
                scraper_version=SCRAPER_VERSION,
            )


class StaticHTMLFetcher:
    """Test/offline fetcher that returns pre-loaded HTML instead of making a
    live request — used by the scraper fixture test suite (Section 36) so
    unit tests never touch the network or a real browser."""

    def __init__(self, html: str, url: str, status: str = WebFetchStatus.SUCCESS.value):
        self._html = html
        self._url = url
        self._status = status

    def fetch(self, url: str) -> FetchResult:
        return FetchResult(
            status=self._status,
            url=self._url,
            html=self._html if self._status == WebFetchStatus.SUCCESS.value else None,
            http_status_code=200 if self._status == WebFetchStatus.SUCCESS.value else None,
            robots_txt_allowed=True,
            scraper_name="StaticHTMLFetcher",
            scraper_version=SCRAPER_VERSION,
        )
