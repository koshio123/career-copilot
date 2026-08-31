from __future__ import annotations

from httpx import AsyncClient


async def test_api_responses_get_a_strict_csp(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert "x-request-id" in resp.headers


async def test_swagger_ui_renders_with_a_relaxed_csp(client: AsyncClient) -> None:
    resp = await client.get("/docs")
    assert resp.status_code == 200
    assert "swagger-ui" in resp.text
    csp = resp.headers["content-security-policy"]
    assert "cdn.jsdelivr.net" in csp
    assert "default-src 'none'" not in csp


async def test_request_id_is_echoed_when_supplied(client: AsyncClient) -> None:
    resp = await client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["x-request-id"] == "abc-123"
