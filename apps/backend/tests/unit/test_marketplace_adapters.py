"""Amazon.in and Flipkart adapter tests against saved HTML fixtures (Section
36), mirroring test_scraper_extraction.py's approach for Blinkit: no network
and no Playwright browser anywhere here — StaticHTMLFetcher stands in for
the live fetch step.
"""
from __future__ import annotations

from pathlib import Path

from app.scraping.amazon import AmazonScraper
from app.scraping.fetcher import StaticHTMLFetcher
from app.scraping.flipkart import FlipkartScraper
from app.scraping.registry import get_scraper_for_url

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "html"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_registry_selects_amazon_adapter_for_amazon_in_urls():
    scraper = get_scraper_for_url("https://www.amazon.in/dp/B0EXAMPLE1")
    assert scraper.platform_name == "amazon"


def test_registry_selects_flipkart_adapter_for_flipkart_urls():
    scraper = get_scraper_for_url("https://www.flipkart.com/tasty-munch-chips/p/itmexample1")
    assert scraper.platform_name == "flipkart"


def test_amazon_listing_extracts_declaration_bullets():
    html = _load("amazon_success_listing.html")
    scraper = AmazonScraper(fetcher=StaticHTMLFetcher(html=html, url="https://www.amazon.in/dp/B0EXAMPLE1"))
    fetch_result = scraper.fetch_page("https://www.amazon.in/dp/B0EXAMPLE1")
    product = scraper.extract_product_data(fetch_result.html, fetch_result.url)

    assert product.title == "Tasty Munch Chips 100g"

    def best(field_name: str) -> str | None:
        c = product.best(field_name)
        return c.value if c else None

    assert "Tasty Foods" in (best("manufacturer_name") or "")
    assert best("country_of_origin") == "India"
    assert "100" in (best("net_quantity") or "")
    # MRP comes from the explicit "M.R.P ‏ : ‎ ₹60.00" bullet, not a raw
    # price-element selector (see amazon.py's module docstring for why that
    # approach was tried against a live page and abandoned as unreliable).
    # The page also shows the (lower) selling price as bare "₹55.00" text,
    # which the generic fallback-text MRP pattern also matches with no
    # label context — best("mrp") must resolve to the labeled ₹60.00, not
    # that ambiguous ₹55.00.
    assert "60.00" in (best("mrp") or "")
    # Regression (caught live against a real Amazon.in page): a "compare
    # with similar items" carousel can carry a completely different
    # product's price. It has no recognized label here, so the label:value
    # extraction correctly ignores it — best("mrp") must never resolve to it.
    assert "999.99" not in (best("mrp") or "")
    # "Customer Care ‏ : ‎ care@tastymunch.example, +91-..." is read as one
    # consumer_care_name candidate off the detail-bullets row; the email
    # itself is additionally caught by the platform-agnostic fallback-text
    # regex (app/nlp/patterns.py) that the base scraper always runs too.
    assert "care@tastymunch.example" in (best("consumer_care_name") or "") or best("consumer_care_email") == (
        "care@tastymunch.example"
    )


def test_amazon_missing_bullets_degrades_to_generic_strategies():
    """A grocery listing with no #detailBullets_feature_div (common in
    practice — verified live) must not crash, and must still surface
    whatever the generic JSON-LD/OpenGraph/text strategies can find."""
    html = "<html><head><title>Plain Product</title></head><body><h1>Plain Product</h1></body></html>"
    scraper = AmazonScraper(fetcher=StaticHTMLFetcher(html=html, url="https://www.amazon.in/dp/B0PLAIN"))
    fetch_result = scraper.fetch_page("https://www.amazon.in/dp/B0PLAIN")
    product = scraper.extract_product_data(fetch_result.html, fetch_result.url)
    assert product is not None
    assert product.best("manufacturer_name") is None


def test_flipkart_listing_extracts_specification_table():
    html = _load("flipkart_success_listing.html")
    scraper = FlipkartScraper(fetcher=StaticHTMLFetcher(html=html, url="https://www.flipkart.com/x/p/itm1"))
    fetch_result = scraper.fetch_page("https://www.flipkart.com/x/p/itm1")
    product = scraper.extract_product_data(fetch_result.html, fetch_result.url)

    assert product.title == "Tasty Munch Chips 100g"

    def best(field_name: str) -> str | None:
        c = product.best(field_name)
        return c.value if c else None

    assert "Tasty Foods" in (best("manufacturer_name") or "")
    assert best("country_of_origin") == "India"
    assert "100" in (best("net_quantity") or "")
    assert best("consumer_care_name") is not None  # from the "Marketed By" row
    # MRP comes from the "MRP" row in the Product Details table, not a raw
    # price-element selector (see flipkart.py's module docstring for why
    # that approach was deliberately not attempted here). The page also
    # shows the (lower) selling price as bare "₹55" text, which the generic
    # fallback-text MRP pattern also matches with no label context —
    # best("mrp") must resolve to the labeled ₹60, not that ambiguous ₹55.
    assert "60" in (best("mrp") or "")


def test_flipkart_unrelated_tables_are_not_mistaken_for_a_spec_sheet():
    """A page with some other, unrelated 2-column table (e.g. a "customers
    also viewed" comparison layout) must not have its rows misread as
    product declarations — only tables that are mostly clean 2-cell rows
    qualify (see extract_table_label_value_pairs)."""
    html = """
    <html><body>
    <table><tr><td>See also</td><td><a>Other product</a></td></tr></table>
    </body></html>
    """
    scraper = FlipkartScraper(fetcher=StaticHTMLFetcher(html=html, url="https://www.flipkart.com/y/p/itm2"))
    fetch_result = scraper.fetch_page("https://www.flipkart.com/y/p/itm2")
    product = scraper.extract_product_data(fetch_result.html, fetch_result.url)
    assert product.best("manufacturer_name") is None
