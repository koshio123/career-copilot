from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.api.deps import (
    CsrfGuard,
    CurrentSession,
    CurrentUser,
    DbSession,
    Email,
    Otp,
    RateLimit,
    Sessions,
    client_ip,
)
from app.auth import tokens
from app.auth.sessions import SessionRecord
from app.core.config import settings
from app.core.errors import ValidationError
from app.schemas.auth import OtpRequestIn, OtpVerifyIn, SessionOut
from app.schemas.user import UserOut
from app.services.auth import AuthService, LoginResult

router = APIRouter(prefix="/auth", tags=["auth"])

_CHALLENGE_COOKIE = "cc_otp_challenge"


def _service(
    db: DbSession, otp: Otp, sessions: Sessions, limiter: RateLimit, email: Email
) -> AuthService:
    return AuthService(
        db, otp_store=otp, session_store=sessions, rate_limiter=limiter, email_sender=email
    )


def _set_cookie(
    response: Response, name: str, value: str, *, max_age: int, http_only: bool
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=http_only,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _set_auth_cookies(response: Response, result: LoginResult) -> None:
    max_age = settings.session_ttl_days * 86400
    _set_cookie(
        response,
        settings.session_cookie_name,
        result.session_token,
        max_age=max_age,
        http_only=True,
    )
    # Readable by JS so the SPA can echo it in the CSRF header (double-submit).
    _set_cookie(
        response,
        settings.csrf_cookie_name,
        result.csrf_token,
        max_age=max_age,
        http_only=False,
    )


def _clear_auth_cookies(response: Response) -> None:
    for name in (settings.session_cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(name, path="/")


@router.post("/otp/request", status_code=status.HTTP_202_ACCEPTED)
async def request_otp(
    body: OtpRequestIn,
    request: Request,
    response: Response,
    db: DbSession,
    otp: Otp,
    sessions: Sessions,
    limiter: RateLimit,
    email: Email,
) -> dict[str, str]:
    challenge = tokens.new_session_token()
    await _service(db, otp, sessions, limiter, email).request_otp(
        str(body.email), ip=client_ip(request), challenge=challenge
    )
    _set_cookie(
        response, _CHALLENGE_COOKIE, challenge, max_age=settings.otp_ttl_seconds, http_only=True
    )
    return {"status": "accepted"}


@router.post("/otp/verify")
async def verify_otp(
    body: OtpVerifyIn,
    request: Request,
    response: Response,
    db: DbSession,
    otp: Otp,
    sessions: Sessions,
    limiter: RateLimit,
    email: Email,
) -> UserOut:
    challenge = request.cookies.get(_CHALLENGE_COOKIE)
    if not challenge:
        raise ValidationError("Start the sign-in from this browser.")

    service = _service(db, otp, sessions, limiter, email)
    result = await service.verify_otp(
        str(body.email),
        body.code,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        challenge=challenge,
    )
    _set_auth_cookies(response, result)
    response.delete_cookie(_CHALLENGE_COOKIE, path="/")
    return UserOut.of(result.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[CsrfGuard])
async def logout(
    request: Request, response: Response, _: CurrentSession, sessions: Sessions
) -> None:
    await sessions.delete(request.cookies.get(settings.session_cookie_name, ""))
    _clear_auth_cookies(response)


def _session_out(record: SessionRecord, current: SessionRecord) -> SessionOut:
    return SessionOut(
        id=record.token_hash,
        created_at=record.created_at,
        last_seen_at=record.last_seen_at,
        user_agent=record.user_agent,
        ip=record.ip,
        current=record.token_hash == current.token_hash,
    )


@router.get("/sessions")
async def list_sessions(
    user: CurrentUser, current: CurrentSession, sessions: Sessions
) -> list[SessionOut]:
    return [_session_out(r, current) for r in await sessions.list_for_user(user.id)]


@router.delete(
    "/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[CsrfGuard]
)
async def revoke_session(
    session_id: str, user: CurrentUser, _: CurrentSession, sessions: Sessions
) -> None:
    owned = {r.token_hash for r in await sessions.list_for_user(user.id)}
    if session_id in owned:
        await sessions.delete_by_hash(session_id)


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT, dependencies=[CsrfGuard])
async def revoke_other_sessions(request: Request, user: CurrentUser, sessions: Sessions) -> None:
    await sessions.delete_all_for_user(
        user.id, keep_token=request.cookies.get(settings.session_cookie_name)
    )
