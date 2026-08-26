"""Bundled fixture data for Demo Inspection mode (Demo Hardening).

Not synthetic: `listing.html` and the images in `images/` are a real
capture from a real, live-scraped Flipkart listing during this session's
live-listing testing (a genuine Lay's Stax product page, including its real
Legal Metrology declarations, MRP, net quantity, and manufacturer
address) — the same kind of raw-HTML/image capture the app already keeps
for every real inspection (`WebPage.raw_html_path`, `ProductImage`), just
copied into the source tree so a demo never depends on network access,
Playwright, or a live marketplace's current uptime/anti-bot behavior.

Demo Inspection mode replays this fixture through the exact same
FlipkartScraper + compliance engine + OCR pipeline a real Flipkart
inspection uses (see app/services/scraping_service.py::scrape_demo_fixture
and app/services/pipeline.py's `is_demo` branches) — nothing about the
*analysis* is mocked, only the network fetch is swapped for a local file
read, via the same `StaticHTMLFetcher` the test suite already uses for
exactly this purpose (app/scraping/fetcher.py).
"""
from __future__ import annotations

from pathlib import Path

_FIXTURE_DIR = Path(__file__).resolve().parent

# A real (now-historical) Flipkart listing URL, kept only as an honest
# "where this came from" reference -- Demo Inspection mode never fetches
# it live. Inspections created this way are always marked `is_demo=True`
# and labeled "DEMO" everywhere they're displayed (Section: never present
# a demo result as a real finding).
DEMO_SOURCE_URL = "https://www.flipkart.com/lay-s-stax-original-potato-crisps-chips-can-pack/p/itmc2a629c332177"


def load_demo_html() -> str:
    return (_FIXTURE_DIR / "listing.html").read_text(encoding="utf-8")


def list_demo_image_paths() -> list[Path]:
    return sorted((_FIXTURE_DIR / "images").glob("*.jpg"))
