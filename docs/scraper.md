# Scraping Subsystem

## Interface (Section 26)

`app/scraping/base.py::ProductScraper` is the abstract interface:

```python
class ProductScraper(ABC):
    platform_name: str
    def can_handle(self, url: str) -> bool: ...
    def fetch_page(self, url: str) -> FetchResult: ...
    def extract_structured_data(self, html: str, url: str) -> list[FieldExtraction]: ...
    def extract_product_data(self, html: str, url: str) -> ScrapedProduct: ...
    def extract_images(self, html: str, url: str) -> list[ScrapedImage]: ...
```

`GenericProductPageScraper` implements every method using only strategies
that work on any e-commerce page. `BlinkitScraper` subclasses it and adds a
`CSS_SELECTOR` layer on top via a centralized `SELECTORS` dict
(`app/scraping/blinkit.py`) — if Blinkit changes its markup, only that dict
needs updating, and even a completely stale selector degrades to "slightly
lower confidence," not "zero data," because the generic strategies still
run underneath. `app/scraping/registry.py::get_scraper_for_url` resolves a
URL to the most specific adapter, falling back to `GenericProductPageScraper`
(Section 26: "at least one working adapter" plus an architecture that
supports Amazon/Flipkart/Zepto/BigBasket later without touching the
compliance engine — adding one is: subclass, override `can_handle` and add
a `SELECTORS` dict, register in `_ADAPTERS`).

## Extraction strategies (Section 3)

In priority order, highest-confidence first:

1. **JSON-LD** (`schema.org/Product`) — `app/scraping/extractors.py::parse_json_ld`
2. **OpenGraph** meta tags
3. **Structured metadata** (`<title>`, `<meta name="description">`)
4. **CSS selectors** (platform-specific, e.g. Blinkit's `SELECTORS`)
5. **Visible DOM text** + **fallback regex/keyword extraction**
   (`app/nlp/patterns.py::find_field_candidates`, shared with OCR-text
   declaration extraction)

Every candidate is kept (`ScrapedProduct.field_candidates`), not just the
"winning" one — disagreement between strategies is exactly the signal the
consistency engine and declaration-extraction dedup logic need to see
(Section 27: never rely on a single CSS selector).

One deliberate correctness decision: `schema.org Product.offers.price` is
the (possibly discounted) **selling** price shown to the buyer, not the
statutory **MRP** — these are legally distinct. It is captured separately
as `ScrapedProduct.listed_price` and is **not** emitted as an `mrp` field
candidate, specifically to avoid manufacturing a false MRP-mismatch finding
against the real MRP text on the page. See
`tests/unit/test_scraper_extraction.py::test_json_ld_offer_price_is_not_conflated_with_mrp`.

## Fetch layer / safety (Section 4)

`app/scraping/fetcher.py::PlaywrightPageFetcher` is the **only** module that
makes a live network request or launches a browser. Before every fetch:

1. `app/scraping/robots.py::is_allowed` fetches and parses `robots.txt`
   (via `protego`) for the target domain, caching per-domain. If
   `robots.txt` itself can't be retrieved, the fetch is refused
   (`WebFetchStatus.FAILED`) rather than assuming permission.
2. `enforce_rate_limit` blocks until at least
   `SCRAPER_MIN_REQUEST_INTERVAL_SECONDS` has elapsed since the last
   request to that domain (per-domain, in-process).
3. The browser is launched with a clearly-identifying User-Agent
   (`SCRAPER_USER_AGENT`, includes a contact string).

If the server returns 401/403 → `ACCESS_DENIED`; 429 → `ACCESS_DENIED`
(rate-limited, stop gracefully); other 4xx/5xx → `FAILED`; a Playwright
timeout → `TIMEOUT`. None of these raise an exception up to the caller —
`scrape_product_page` (`app/services/scraping_service.py`) always returns a
`WebPage` row recording exactly what happened, and the pipeline continues
gracefully (Section 26: "DO NOT crash... provide 'Automatic page extraction
unavailable.' Then allow Upload screenshots").

**Explicitly not implemented, per Section 4:** CAPTCHA bypass, browser
fingerprint spoofing, proxy rotation for evasion, credential bypass,
anti-bot circumvention. If a marketplace blocks the fetch, LM-SCAN reports
that and stops — it does not try to get around the block.

## Testing (Section 35/36)

`tests/unit/test_scraper_extraction.py` uses `StaticHTMLFetcher`
(`app/scraping/fetcher.py`) — a fetcher that returns pre-loaded HTML instead
of a live request — against six saved fixtures in
`tests/fixtures/html/`: a successful listing, a page missing manufacturer
declarations, one with a webpage/JSON-LD price/MRP distinction, a page
missing net quantity, an "incomplete/loading" page, and a page with
deliberately malformed markup/JSON-LD. None of these tests touch the
network or a real browser. Live scraping (a real Playwright launch against
a real site) is exercised only outside the normal suite — see
`docs/testing.md`.
