"""robots.txt compliance and simple per-domain rate limiting.

Per the product brief Section 4, the scraper MUST respect robots.txt and use
reasonable request rates, and MUST NOT attempt to bypass access controls.
This module is the single place that decision is made, so every fetch path
goes through it.
"""
from __future__ import annotations

import time
import urllib.parse

import httpx
from protego import Protego

from app.core.config import get_settings

settings = get_settings()

_robots_cache: dict[str, Protego] = {}
_last_request_at: dict[str, float] = {}


def _domain_of(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def get_robots_parser(url: str, timeout: float = 10.0) -> Protego | None:
    domain = _domain_of(url)
    if domain in _robots_cache:
        return _robots_cache[domain]

    robots_url = urllib.parse.urljoin(domain, "/robots.txt")
    try:
        response = httpx.get(
            robots_url,
            timeout=timeout,
            headers={"User-Agent": settings.scraper_user_agent},
            follow_redirects=True,
        )
        if response.status_code >= 400:
            # No robots.txt (or inaccessible) is conventionally treated as "allow all".
            parser = Protego.parse("")
        else:
            parser = Protego.parse(response.text)
    except httpx.HTTPError:
        # Network failure while checking robots.txt: fail closed on the side of
        # NOT scraping rather than assuming permission (Section 4).
        return None

    _robots_cache[domain] = parser
    return parser


def is_allowed(url: str) -> bool | None:
    """Returns True/False, or None if robots.txt could not be checked at all
    (caller should then refuse to proceed rather than assume permission)."""
    parser = get_robots_parser(url)
    if parser is None:
        return None
    return parser.can_fetch(url, settings.scraper_user_agent)


def enforce_rate_limit(url: str) -> None:
    """Blocks the current call until at least
    SCRAPER_MIN_REQUEST_INTERVAL_SECONDS has passed since the last request to
    this domain, so LM-SCAN never hammers a marketplace (Section 4: "use
    reasonable request rates", "avoid brute-force crawling")."""
    domain = _domain_of(url)
    last = _last_request_at.get(domain)
    now = time.monotonic()
    if last is not None:
        elapsed = now - last
        wait_for = settings.scraper_min_request_interval_seconds - elapsed
        if wait_for > 0:
            time.sleep(wait_for)
    _last_request_at[domain] = time.monotonic()


def reset_caches_for_tests() -> None:
    _robots_cache.clear()
    _last_request_at.clear()
