"""Resolves a URL to the most specific scraper adapter available, falling
back to the generic scraper (Section 26: "support Amazon/Flipkart/Zepto/...
without changing the core compliance engine — for now implement the
architecture and at least one working adapter")."""
from __future__ import annotations

from app.scraping.base import GenericProductPageScraper, ProductScraper
from app.scraping.blinkit import BlinkitScraper

_ADAPTERS: list[type[ProductScraper]] = [BlinkitScraper]


def get_scraper_for_url(url: str) -> ProductScraper:
    for adapter_cls in _ADAPTERS:
        adapter = adapter_cls()
        if adapter.can_handle(url):
            return adapter
    return GenericProductPageScraper()


def detect_platform_name(url: str) -> str:
    return get_scraper_for_url(url).platform_name
