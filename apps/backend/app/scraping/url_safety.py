"""SSRF protection (Section 4/26 audit fix): the single place every network
call this app makes to a URL that ultimately traces back to user input (a
submitted listing URL) or to attacker-influenced page content (an <img src>
found on a fetched page) is validated before the request goes out.

Before this module existed, nothing stopped a submitted `source_url` (or an
image URL scraped out of a fetched page's HTML) from pointing at
`http://169.254.169.254/...` (cloud metadata), `http://localhost:8000/...`,
or any other internal-only address — Playwright and httpx would both happily
fetch it and hand the response back to the officer as "scraped product
data"/"a product image". `ensure_safe_to_fetch` closes that off; `safe_get`
additionally re-validates on every redirect hop, since an initial
public-looking URL can otherwise be used to reach an internal service via a
3xx Location header.
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.parse

_ALLOWED_SCHEMES = {"http", "https"}
_LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}


class UnsafeURLError(ValueError):
    """Raised when a URL must not be fetched (SSRF protection)."""


def _is_public_ip(raw_ip: str) -> bool:
    addr = ipaddress.ip_address(raw_ip)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def ensure_safe_to_fetch(url: str) -> None:
    """Raises UnsafeURLError if `url` must not be fetched: a non-http(s)
    scheme, no hostname, a local/loopback hostname, or a hostname that
    resolves (any of its A/AAAA records — every one is checked, not just
    the first) to a private/loopback/link-local/reserved/multicast address.
    Resolving and checking every IP (rather than trusting the hostname
    alone) is what stops DNS-rebinding: a public-looking hostname whose DNS
    record has been pointed at an internal address.
    """
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Unsupported URL scheme: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL has no hostname")
    hostname = hostname.lower()
    if hostname in _LOCAL_HOSTNAMES or hostname.endswith(".local"):
        raise UnsafeURLError(f"Refusing to fetch local hostname: {hostname}")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        raise UnsafeURLError(f"Could not resolve hostname: {hostname}") from exc

    for info in infos:
        ip = info[4][0]
        if not _is_public_ip(ip):
            raise UnsafeURLError(f"Refusing to fetch {hostname!r}: resolves to a non-public address ({ip})")


def safe_get(url: str, *, max_redirects: int = 5, client_kwargs: dict | None = None, **request_kwargs):
    """httpx GET that re-validates the target host on every redirect hop, so
    an initial safe/public URL can't be used to reach an internal service
    via a Location header (httpx's own `follow_redirects=True` does not
    re-check anything about the redirect target)."""
    import httpx

    kwargs = dict(client_kwargs or {})
    kwargs["follow_redirects"] = False
    current_url = url
    with httpx.Client(**kwargs) as client:
        for _ in range(max_redirects + 1):
            ensure_safe_to_fetch(current_url)
            response = client.get(current_url, **request_kwargs)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    return response
                current_url = str(httpx.URL(current_url).join(location))
                continue
            return response
    raise UnsafeURLError(f"Too many redirects (> {max_redirects}) while fetching {url}")
