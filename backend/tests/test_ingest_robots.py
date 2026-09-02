"""RobotsCache — allow / disallow / crawl-delay / missing file."""

from __future__ import annotations

import httpx
import pytest

from app.ingest import robots as robots_mod
from app.ingest.http import FetchResult
from app.ingest.robots import RobotsCache
from app.models.enums import RobotsState

ROBOTS = """
User-agent: *
Disallow: /private/
Crawl-delay: 7
""".strip()


def _result(status: int, body: str = "") -> FetchResult:
    return FetchResult(
        url="http://x/robots.txt",
        status_code=status,
        headers=httpx.Headers({"content-type": "text/plain"}),
        content=body.encode(),
        content_type="text/plain",
    )


def _stub(monkeypatch: pytest.MonkeyPatch, result: FetchResult | Exception) -> None:
    async def fake(url: str, *, client: object = None) -> FetchResult:
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(robots_mod, "safe_get", fake)


async def test_allows_and_disallows(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _result(200, ROBOTS))
    cache = RobotsCache()

    allowed = await cache.check("https://acme.example/careers")
    assert allowed.allowed is True
    assert allowed.crawl_delay == 7
    assert allowed.state is RobotsState.ALLOWED

    blocked = await cache.check("https://acme.example/private/secret")
    assert blocked.allowed is False


async def test_missing_robots_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _result(404))
    decision = await RobotsCache().check("https://acme.example/careers")
    assert decision.allowed is True
    assert decision.state is RobotsState.ALLOWED


async def test_fetch_error_is_unknown_but_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ingest.errors import FetchError

    _stub(monkeypatch, FetchError("boom"))
    decision = await RobotsCache().check("https://acme.example/careers")
    assert decision.allowed is True
    assert decision.state is RobotsState.UNKNOWN


async def test_result_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def fake(url: str, *, client: object = None) -> FetchResult:
        nonlocal calls
        calls += 1
        return _result(200, ROBOTS)

    monkeypatch.setattr(robots_mod, "safe_get", fake)
    cache = RobotsCache()
    await cache.check("https://acme.example/a")
    await cache.check("https://acme.example/b")
    assert calls == 1
