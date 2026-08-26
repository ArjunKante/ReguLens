"""SSRF protection unit tests (P0 audit fix: "SSRF protection on URL/image
fetching", "proper marketplace hostname validation"). No live network
access (Section 36) — IP-literal URLs resolve without any real DNS lookup,
and the one case that needs a hostname-to-IP mapping (a safe public
hostname) mocks `socket.getaddrinfo` instead of relying on live DNS."""
from __future__ import annotations

import socket

import pytest

from app.scraping.base import hostname_matches
from app.scraping.url_safety import UnsafeURLError, ensure_safe_to_fetch


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://127.0.0.1:8000/api/v1/secret",
        "http://localhost/",
        "http://localhost.localdomain/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://10.0.0.5/internal",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://[::1]/",
        "ftp://example.com/",
        "file:///etc/passwd",
    ],
)
def test_ensure_safe_to_fetch_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(UnsafeURLError):
        ensure_safe_to_fetch(url)


def test_ensure_safe_to_fetch_rejects_url_with_no_hostname() -> None:
    with pytest.raises(UnsafeURLError):
        ensure_safe_to_fetch("http:///no-host")


def test_ensure_safe_to_fetch_allows_a_public_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mocked resolution (no live DNS/network — Section 36) mapping a
    # plausible marketplace hostname to a public IP.
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
    )
    ensure_safe_to_fetch("https://example.com/product/1")


def test_ensure_safe_to_fetch_rejects_dns_rebinding_to_a_private_address(monkeypatch: pytest.MonkeyPatch) -> None:
    # A hostname that looks public but whose DNS record resolves to an
    # internal address must still be rejected.
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, None, None, "", ("10.0.0.7", 0))]
    )
    with pytest.raises(UnsafeURLError):
        ensure_safe_to_fetch("https://looks-public.example.com/product/1")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://blinkit.com/prn/x/prid/1", True),
        ("https://www.blinkit.com/prn/x/prid/1", True),
        ("https://blinkit.com.attacker.net/", False),  # suffix trick
        ("https://evil.example/?next=blinkit.com", False),  # substring in query, not host
        ("https://notblinkit.com/", False),
        ("https://blinkit.com", True),
    ],
)
def test_hostname_matches_is_not_a_substring_check(url: str, expected: bool) -> None:
    assert hostname_matches(url, "blinkit.com") is expected
