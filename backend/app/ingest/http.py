"""SSRF-safe HTTP GET.

A user gives us a URL and the server fetches it — the classic SSRF sink. Before
every connection we:

- require an ``http`` / ``https`` scheme;
- resolve the host and reject any answer that is a private, loopback,
  link-local, CGNAT, reserved, or multicast address (this covers the cloud
  metadata endpoint ``169.254.169.254``);
- follow redirects manually, re-validating every hop, up to a small limit;
- cap the response body size and the total time.

DNS rebinding (the address changing between this check and the socket connect)
is a known residual gap; pinning the validated IP into the connection is a
Phase 09 hardening tracked in ADR-0013. For part 1 we resolve-then-request and
re-check on every redirect.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from app.core.config import settings
from app.ingest.errors import (
    BlockedHostError,
    FetchError,
    FetchTimeoutError,
    FetchTooLargeError,
)

log = structlog.get_logger(__name__)

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


@dataclass(frozen=True, slots=True)
class FetchResult:
    url: str  # final URL after redirects
    status_code: int
    headers: httpx.Headers
    content: bytes
    content_type: str

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding, errors="replace")

    @property
    def encoding(self) -> str:
        # charset from Content-Type, else UTF-8.
        for part in self.content_type.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                return part.split("=", 1)[1].strip() or "utf-8"
        return "utf-8"


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        return True
    if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    # Carrier-grade NAT (RFC 6598) — not caught by is_private.
    return isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT


def _assert_host_allowed(host: str) -> None:
    if settings.fetch_allow_private_hosts:
        return
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _ip_is_blocked(literal):
            raise BlockedHostError(f"{host} is not a public address")
        return

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError(f"could not resolve {host}: {exc}") from exc
    addrs = {info[4][0] for info in infos}
    if not addrs:
        raise FetchError(f"{host} did not resolve")
    for addr in addrs:
        if _ip_is_blocked(ipaddress.ip_address(addr)):
            raise BlockedHostError(f"{host} resolves to a non-public address ({addr})")


def _assert_url_allowed(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise BlockedHostError(f"unsupported scheme: {parsed.scheme or '(none)'}")
    if not parsed.hostname:
        raise BlockedHostError("URL has no host")
    _assert_host_allowed(parsed.hostname)
    return url


async def _read_capped(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > settings.fetch_max_bytes:
            raise FetchTooLargeError(f"response exceeded {settings.fetch_max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


async def safe_get(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    headers: dict[str, str] | None = None,
) -> FetchResult:
    """GET ``url`` with SSRF checks, manual redirects, and size/time caps."""
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(settings.fetch_timeout_seconds),
        follow_redirects=False,
    )
    request_headers = {"user-agent": settings.fetch_user_agent, **(headers or {})}
    try:
        current = _assert_url_allowed(url)
        for _ in range(settings.fetch_max_redirects + 1):
            try:
                async with client.stream("GET", current, headers=request_headers) as response:
                    is_redirect = (
                        response.status_code in _REDIRECT_STATUSES
                        and "location" in response.headers
                    )
                    if is_redirect:
                        current = _assert_url_allowed(
                            urljoin(current, response.headers["location"])
                        )
                        continue
                    body = await _read_capped(response)
                    return FetchResult(
                        url=str(response.url),
                        status_code=response.status_code,
                        headers=response.headers,
                        content=body,
                        content_type=response.headers.get("content-type", ""),
                    )
            except httpx.TimeoutException as exc:
                raise FetchTimeoutError(f"{current} timed out") from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"{current}: {exc}") from exc
        raise FetchError(f"too many redirects (> {settings.fetch_max_redirects})")
    finally:
        if owns_client:
            await client.aclose()
