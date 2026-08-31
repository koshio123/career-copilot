from __future__ import annotations

from httpx import AsyncClient

from tests.fakes import FakeEmailSender, InMemoryRateLimiter

REQUEST = "/api/v1/auth/otp/request"
VERIFY = "/api/v1/auth/otp/verify"


async def _login(
    client: AsyncClient, email: FakeEmailSender, addr: str = "user@example.com"
) -> str:
    r = await client.post(REQUEST, json={"email": addr})
    assert r.status_code == 202
    code = email.last_code
    assert code is not None
    r = await client.post(VERIFY, json={"email": addr, "code": code})
    assert r.status_code == 200, r.text
    return client.cookies["cc_csrf"]


async def test_otp_login_flow(client: AsyncClient, email: FakeEmailSender) -> None:
    r = await client.post(REQUEST, json={"email": "new@example.com"})
    assert r.status_code == 202
    assert r.json() == {"status": "accepted"}
    assert email.last_code is not None

    r = await client.post(VERIFY, json={"email": "new@example.com", "code": email.last_code})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "new@example.com"
    assert body["email_verified"] is True
    assert "cc_session" in client.cookies
    assert "cc_csrf" in client.cookies

    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == "new@example.com"

    out = await client.post(
        "/api/v1/auth/logout", headers={"x-csrf-token": client.cookies["cc_csrf"]}
    )
    assert out.status_code == 204
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_me_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "authentication-required"


async def test_verify_needs_challenge_cookie(client: AsyncClient) -> None:
    # verify without ever calling request → no challenge cookie
    r = await client.post(VERIFY, json={"email": "a@example.com", "code": "123456"})
    assert r.status_code == 422
    assert r.json()["code"] == "validation-error"


async def test_verify_rejects_wrong_code(client: AsyncClient, email: FakeEmailSender) -> None:
    await client.post(REQUEST, json={"email": "a@example.com"})
    r = await client.post(VERIFY, json={"email": "a@example.com", "code": "000000"})
    assert r.status_code == 401


async def test_logout_requires_csrf(client: AsyncClient, email: FakeEmailSender) -> None:
    await _login(client, email)
    r = await client.post("/api/v1/auth/logout")  # no x-csrf-token header
    assert r.status_code == 403
    assert r.json()["code"] == "csrf-check-failed"


async def test_otp_request_is_rate_limited(
    client: AsyncClient, email: FakeEmailSender, rate_limiter: InMemoryRateLimiter
) -> None:
    for _ in range(8):
        r = await client.post(REQUEST, json={"email": "spam@example.com"})
        assert r.status_code == 202  # always 202, even when throttled
    # settings.otp_max_requests_per_email_per_hour == 5
    assert len(email.sent) == 5


async def test_session_listing_and_revoke_all(client: AsyncClient, email: FakeEmailSender) -> None:
    csrf = await _login(client, email)
    sessions = (await client.get("/api/v1/auth/sessions")).json()
    assert len(sessions) == 1
    assert sessions[0]["current"] is True

    r = await client.delete("/api/v1/auth/sessions", headers={"x-csrf-token": csrf})
    assert r.status_code == 204
    # current session kept
    assert (await client.get("/api/v1/me")).status_code == 200
