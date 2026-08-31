"""Authentication flow (ADR-0010): request OTP → verify → session."""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import tokens
from app.auth.otp import OtpResult, OtpStore
from app.auth.ratelimit import RateLimiter
from app.auth.sessions import SessionStore
from app.core.config import settings
from app.core.errors import AuthRequiredError, RateLimitedError
from app.email import EmailMessage, EmailSender
from app.models import User
from app.repositories.users import UserRepository

log = structlog.get_logger(__name__)

_HOUR = 3600


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: User
    session_token: str
    csrf_token: str


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        otp_store: OtpStore,
        session_store: SessionStore,
        rate_limiter: RateLimiter,
        email_sender: EmailSender,
    ) -> None:
        self._db = session
        self._otp = otp_store
        self._sessions = session_store
        self._limiter = rate_limiter
        self._email = email_sender
        self._users = UserRepository(session)

    async def request_otp(self, email: str, *, ip: str, challenge: str) -> None:
        email_key = f"otp-req:email:{tokens.hash_email(email)}"
        ip_key = f"otp-req:ip:{ip}"
        allowed_email = await self._limiter.hit(
            email_key, limit=settings.otp_max_requests_per_email_per_hour, window_seconds=_HOUR
        )
        allowed_ip = await self._limiter.hit(
            ip_key, limit=settings.otp_max_requests_per_ip_per_hour, window_seconds=_HOUR
        )
        if not (allowed_email and allowed_ip):
            # Caller still returns 202; just don't send.
            log.info("otp.request_rate_limited", email=email, ip=ip)
            return

        code = await self._otp.issue(email, challenge=challenge)
        await self._email.send(
            EmailMessage(
                to=email,
                subject="Your Career Copilot sign-in code",
                text=(
                    f"Your sign-in code is {code}\n\n"
                    f"It expires in {settings.otp_ttl_seconds // 60} minutes. "
                    "If you didn't request this, ignore this email."
                ),
            )
        )
        log.info("otp.issued", email=email)

    async def verify_otp(
        self, email: str, code: str, *, ip: str, user_agent: str, challenge: str
    ) -> LoginResult:
        allowed = await self._limiter.hit(
            f"otp-verify:ip:{ip}",
            limit=settings.otp_max_requests_per_ip_per_hour,
            window_seconds=_HOUR,
        )
        if not allowed:
            raise RateLimitedError("Too many attempts. Try again later.")

        verification = await self._otp.verify(email, code, challenge=challenge)
        if verification.result is OtpResult.TOO_MANY_ATTEMPTS:
            raise RateLimitedError("Too many attempts for this code. Request a new one.")
        if not verification.ok:
            raise AuthRequiredError("That code is invalid or expired.")

        user = await self._users.get_or_create_verified(email)
        await self._db.flush()

        session_token = await self._sessions.create(user_id=user.id, user_agent=user_agent, ip=ip)
        log.info("auth.login", user_id=str(user.id))
        return LoginResult(
            user=user, session_token=session_token, csrf_token=tokens.new_csrf_token()
        )

    async def logout(self, session_token: str) -> None:
        await self._sessions.delete(session_token)
