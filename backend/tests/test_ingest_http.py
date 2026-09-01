"""SSRF guarding in app.ingest.http.safe_get."""

from __future__ import annotations

import socket

import httpx
import pytest

from app.core.config import settings
from app.ingest.errors import BlockedHostError, FetchError, FetchTooLargeError
from app.ingest.http import _ip_is_blocked, safe_get


@pytest.mark.parametrize(
    "ip",
    ["127.0.0.1", "10.0.0.1", "192.168.1.1", "169.254.169.254", "::1", "100.64.1.1"],
)
def test_private_and_special_ips_are_blocked(ip: str) -> None:
    import ipaddress

    assert _ip_is_blocked(ipaddress.ip_address(ip)) is True


@pytest.mark.parametrize("ip", ["93.184.216.34", "1.1.1.1", "2606:4700:4700::1111"])
def test_public_ips_pass(ip: str) -> None:
    import ipaddress

    assert _ip_is_blocked(ipaddress.ip_address(ip)) is False


async def test_rejects_non_http_scheme() -> None:
    with pytest.raises(BlockedHostError):
        await safe_get("file:///etc/passwd")


async def test_blocks_loopback_literal() -> None:
    with pytest.raises(BlockedHostError):
        await safe_get("http://127.0.0.1/")


async def test_blocks_metadata_endpoint() -> None:
    with pytest.raises(BlockedHostError):
        await safe_get("http://169.254.169.254/latest/meta-data/")


async def test_blocks_host_that_resolves_private(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, None, 0, "", ("10.1.2.3", 0))],
    )
    with pytest.raises(BlockedHostError):
        await safe_get("http://internal.example.com/")


def _client(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)  # type: ignore[arg-type]


async def test_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, None, 0, "", ("93.184.216.34", 0))]
    )
    client = _client(
        lambda req: httpx.Response(200, headers={"content-type": "text/html"}, text="<h1>hi</h1>")
    )
    result = await safe_get("http://example.com/jobs", client=client)
    assert result.status_code == 200
    assert "hi" in result.text
    await client.aclose()


async def test_redirect_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, None, 0, "", ("93.184.216.34", 0))]
    )
    monkeypatch.setattr(settings, "fetch_max_redirects", 2)
    client = _client(
        lambda req: httpx.Response(302, headers={"location": "http://example.com/next"})
    )
    with pytest.raises(FetchError, match="redirect"):
        await safe_get("http://example.com/start", client=client)
    await client.aclose()


async def test_redirect_to_private_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, None, 0, "", ("93.184.216.34", 0))]
    )
    client = _client(lambda req: httpx.Response(302, headers={"location": "http://127.0.0.1/"}))
    with pytest.raises(BlockedHostError):
        await safe_get("http://example.com/start", client=client)
    await client.aclose()


async def test_size_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, None, 0, "", ("93.184.216.34", 0))]
    )
    monkeypatch.setattr(settings, "fetch_max_bytes", 16)
    client = _client(lambda req: httpx.Response(200, text="x" * 1000))
    with pytest.raises(FetchTooLargeError):
        await safe_get("http://example.com/big", client=client)
    await client.aclose()
