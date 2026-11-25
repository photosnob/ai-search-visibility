"""URL extraction and host matching.

Host matching is a suffix check against the configured domain. It is not a
public-suffix lookup: `shop.northwind.example` belongs to `northwind.example`,
and `northwind.example.evil.test` does not.
"""

import re
from urllib.parse import urlparse

_URL = re.compile(r"https?://[^\s<>\[\]()\"']+", re.IGNORECASE)
_TRAILING = ".,;:)\"'"


def redact_urls(text: str) -> str:
    """Remove URLs so a host that contains the brand name is not also a mention."""
    return _URL.sub(" ", text)


def extract_urls(text: str) -> tuple[str, ...]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _URL.finditer(text):
        canonical = canonicalize(match.group(0))
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)
        found.append(canonical)
    return tuple(found)


def canonicalize(url: str) -> str | None:
    """Return a cleaned http(s) URL, or None when the value is not one."""
    cleaned = url.strip()
    while cleaned and cleaned[-1] in _TRAILING:
        cleaned = cleaned[:-1]
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in {"http", "https"} or parsed.hostname is None:
        return None
    host = parsed.hostname.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    port = parsed.port
    default_port = (parsed.scheme.lower() == "http" and port == 80) or (
        parsed.scheme.lower() == "https" and port == 443
    )
    netloc = host if port is None or default_port else f"{host}:{port}"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme.lower()}://{netloc}{parsed.path}{query}"


def host_of(url: str) -> str | None:
    canonical = canonicalize(url)
    if canonical is None:
        return None
    hostname = urlparse(canonical).hostname
    if hostname is None:
        return None
    return display_host(hostname)


def display_host(hostname: str) -> str:
    host = hostname.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def host_matches(hostname: str, domain: str) -> bool:
    host = display_host(hostname)
    owned = display_host(domain)
    return host == owned or host.endswith("." + owned)
