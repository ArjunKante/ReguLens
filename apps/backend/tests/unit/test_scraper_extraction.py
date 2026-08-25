"""Scraper extraction tests against saved HTML fixtures (Section 36).

No network access and no Playwright browser is used anywhere in this file —
`StaticHTMLFetcher` stands in for the live fetch step, so these tests are
fast and fully deterministic, exactly as Section 36 requires.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.models.enums import WebFetchStatus
from app.scraping.blinkit import BlinkitScraper
from app.scraping.fetcher import StaticHTMLFetcher
from app.scraping.registry import get_scraper_for_url

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "html"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _scraper_for(html: str, url: str) -> BlinkitScraper:
    return BlinkitScraper(fetcher=StaticHTMLFetcher(html=html, url=url))


def test_registry_selects_blinkit_adapter_for_blinkit_urls():
    scraper = get_scraper_for_url("https://blinkit.com/prn/tasty-munch/prid/12345")
    assert scraper.platform_name == "blinkit"


def test_registry_falls_back_to_generic_for_unknown_domain():
    scraper = get_scraper_for_url("https://some-random-quick-commerce.example/p/1")
    assert scraper.platform_name == "generic"


def test_successful_listing_extracts_all_expected_fields():
    html = _load("success_listing.html")
    scraper = _scraper_for(html, "https://blinkit.com/prn/tasty-munch/prid/12345")
    fetch_result = scraper.fetch_page("https://blinkit.com/prn/tasty-munch/prid/12345")
    assert fetch_result.status == WebFetchStatus.SUCCESS.value

    product = scraper.extract_product_data(fetch_result.html, fetch_result.url)

    assert product.title == "Tasty Munch Chips 100g"
    assert product.brand == "Tasty Munch"
    assert product.listed_price == 55.0
    assert len(product.images) == 2

    def best(field_name: str) -> str | None:
        c = product.best(field_name)
        return c.value if c else None

    assert best("product_name") is not None
    assert "Tasty Foods" in (best("manufacturer_name") or "")
    assert best("country_of_origin") == "India"
    assert "100" in (best("net_quantity") or "")
    assert "60.00" in (best("mrp") or "")
    assert best("consumer_care_email") == "care@tastymunch.example"


def test_json_ld_offer_price_is_not_conflated_with_mrp():
    """schema.org offers.price is the (possibly discounted) selling price,
    not the statutory MRP. The scraper must not manufacture a false
    MRP-mismatch by treating the two as the same field."""
    html = _load("success_listing.html")
    scraper = _scraper_for(html, "https://blinkit.com/x")
    fetch_result = scraper.fetch_page("https://blinkit.com/x")
    product = scraper.extract_product_data(fetch_result.html, fetch_result.url)

    assert product.listed_price == 55.0
    mrp_candidates = [c.value for c in product.all_for("mrp")]
    assert all("55" not in v for v in mrp_candidates), mrp_candidates


def test_missing_declaration_page_yields_no_manufacturer_candidate():
    html = _load("missing_declaration.html")
    scraper = _scraper_for(html, "https://blinkit.com/y")
    fetch_result = scraper.fetch_page("https://blinkit.com/y")
    product = scraper.extract_product_data(fetch_result.html, fetch_result.url)

    assert product.best("manufacturer_name") is None
    assert product.best("consumer_care_email") is None
    # But fields that ARE present must still be found:
    assert "500" in (product.best("net_quantity").value or "")  # type: ignore[union-attr]


def test_missing_quantity_page_yields_no_net_quantity_candidate():
    html = _load("missing_quantity.html")
    scraper = _scraper_for(html, "https://blinkit.com/z")
    fetch_result = scraper.fetch_page("https://blinkit.com/z")
    product = scraper.extract_product_data(fetch_result.html, fetch_result.url)

    assert product.best("net_quantity") is None
    assert product.best("manufacturer_name") is not None


def test_incomplete_page_does_not_crash_and_yields_minimal_data():
    html = _load("incomplete_page.html")
    scraper = _scraper_for(html, "https://blinkit.com/w")
    fetch_result = scraper.fetch_page("https://blinkit.com/w")
    product = scraper.extract_product_data(fetch_result.html, fetch_result.url)

    assert product is not None
    assert product.best("mrp") is None


def test_malformed_page_does_not_raise():
    """Section 27: scraper failures on real-world broken markup must degrade
    gracefully, never crash the pipeline."""
    html = _load("malformed_page.html")
    scraper = _scraper_for(html, "https://blinkit.com/broken")
    fetch_result = scraper.fetch_page("https://blinkit.com/broken")
    # Should not raise, even with invalid JSON-LD and unbalanced tags.
    product = scraper.extract_product_data(fetch_result.html, fetch_result.url)
    assert product is not None


@pytest.mark.parametrize(
    "status",
    [
        WebFetchStatus.BLOCKED_BY_ROBOTS.value,
        WebFetchStatus.ACCESS_DENIED.value,
        WebFetchStatus.TIMEOUT.value,
        WebFetchStatus.FAILED.value,
    ],
)
def test_scraper_failure_statuses_never_raise_and_have_no_html(status):
    """Section 4/26: scraper must stop gracefully (not crash, not bypass
    access controls) whenever the fetch layer reports a non-success status."""
    scraper = _scraper_for("<html></html>", "https://blinkit.com/blocked")
    scraper.fetcher = StaticHTMLFetcher(html="", url="https://blinkit.com/blocked", status=status)
    result = scraper.fetch_page("https://blinkit.com/blocked")
    assert result.status == status
    assert result.html is None
