"""FastAPI dependencies: DB session, current user, CSRF."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import tokens
from app.auth.otp import OtpStore, get_otp_store
from app.auth.ratelimit import RateLimiter, get_rate_limiter
from app.auth.sessions import SessionRecord, SessionStore, get_session_store
from app.core.config import settings
from app.core.errors import AuthRequiredError, CsrfError
from app.db.session import get_sessionmaker
from app.email import EmailSender, get_email_sender
from app.models import User
from app.queue.base import Queue
from app.queue.sqs import get_queue
from app.services.resumes import ResumeService
from app.storage import ResumeStorage, get_resume_storage

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]
Sessions = Annotated[SessionStore, Depends(get_session_store)]
Otp = Annotated[OtpStore, Depends(get_otp_store)]
RateLimit = Annotated[RateLimiter, Depends(get_rate_limiter)]
Email = Annotated[EmailSender, Depends(get_email_sender)]


def client_ip(request: Request) -> str:
    # API Gateway / CloudFront put the real client first in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_current_session(request: Request, store: Sessions) -> SessionRecord:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise AuthRequiredError("Not signed in.")
    record = await store.get(token)
    if record is None:
        raise AuthRequiredError("Session expired or invalid.")
    await store.touch(record)
    return record


CurrentSession = Annotated[SessionRecord, Depends(get_current_session)]


async def get_current_user(session: CurrentSession, db: DbSession) -> User:
    user = await db.get(User, session.user_id)
    if user is None:
        raise AuthRequiredError("Account no longer exists.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_csrf(request: Request) -> None:
    """Double-submit: the CSRF cookie must match the request header on unsafe methods."""
    if request.method in _SAFE_METHODS:
        return
    cookie = request.cookies.get(settings.csrf_cookie_name, "")
    header = request.headers.get(settings.csrf_header_name, "")
    if not cookie or not tokens.constant_time_equals(cookie, header):
        raise CsrfError("Missing or invalid CSRF token.")


CsrfGuard = Depends(require_csrf)


def get_default_queue() -> Queue:
    return get_queue("default")


Storage = Annotated[ResumeStorage, Depends(get_resume_storage)]
DefaultQueue = Annotated[Queue, Depends(get_default_queue)]


def get_resume_service(
    user: CurrentUser, db: DbSession, storage: Storage, queue: DefaultQueue
) -> ResumeService:
    return ResumeService(db, user_id=user.id, storage=storage, queue=queue)


ResumeSvc = Annotated[ResumeService, Depends(get_resume_service)]
