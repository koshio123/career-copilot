"""In-memory doubles for the auth stores and email sender.

Used by the ``client`` fixture so the HTTP tests are fast and deterministic. The
real DynamoDB implementations are exercised separately against moto.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.auth import tokens
from app.auth.otp import OtpResult, OtpVerification
from app.auth.sessions import SessionRecord
from app.core.config import settings
from app.email import EmailMessage
from app.queue.base import TaskMessage
from app.storage.s3 import Upload


class InMemorySessionStore:
    def __init__(self) -> None:
        self._by_hash: dict[str, SessionRecord] = {}

    async def create(self, *, user_id: UUID, user_agent: str, ip: str) -> str:
        token = tokens.new_session_token()
        now = datetime.now(UTC)
        record = SessionRecord(
            token_hash=tokens.hash_token(token),
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(days=settings.session_ttl_days),
            last_seen_at=now,
            user_agent=user_agent,
            ip=ip,
        )
        self._by_hash[record.token_hash] = record
        return token

    async def get(self, token: str) -> SessionRecord | None:
        record = self._by_hash.get(tokens.hash_token(token))
        if record and record.expires_at > datetime.now(UTC):
            return record
        return None

    async def touch(self, record: SessionRecord) -> None:
        return None

    async def delete(self, token: str) -> None:
        self._by_hash.pop(tokens.hash_token(token), None)

    async def delete_by_hash(self, token_hash: str) -> None:
        self._by_hash.pop(token_hash, None)

    async def list_for_user(self, user_id: UUID) -> list[SessionRecord]:
        return [r for r in self._by_hash.values() if r.user_id == user_id]

    async def delete_all_for_user(self, user_id: UUID, *, keep_token: str | None = None) -> None:
        keep = tokens.hash_token(keep_token) if keep_token else None
        for h in [h for h, r in self._by_hash.items() if r.user_id == user_id and h != keep]:
            del self._by_hash[h]


class InMemoryOtpStore:
    def __init__(self) -> None:
        self._by_email: dict[str, dict[str, object]] = {}

    async def issue(self, email: str, *, challenge: str) -> str:
        code = tokens.new_otp_code()
        self._by_email[tokens.hash_email(email)] = {
            "code": code,
            "challenge": challenge,
            "attempts": 0,
            "expires_at": datetime.now(UTC) + timedelta(seconds=settings.otp_ttl_seconds),
        }
        return code

    async def verify(self, email: str, code: str, *, challenge: str) -> OtpVerification:
        key = tokens.hash_email(email)
        rec = self._by_email.get(key)
        if rec is None or rec["expires_at"] <= datetime.now(UTC):  # type: ignore[operator]
            return OtpVerification(OtpResult.INVALID)
        if rec["challenge"] != challenge:
            return OtpVerification(OtpResult.INVALID)
        if int(rec["attempts"]) >= settings.otp_max_attempts:  # type: ignore[call-overload]
            del self._by_email[key]
            return OtpVerification(OtpResult.TOO_MANY_ATTEMPTS)
        if tokens.constant_time_equals(str(rec["code"]), code):
            del self._by_email[key]
            return OtpVerification(OtpResult.OK)
        rec["attempts"] = int(rec["attempts"]) + 1  # type: ignore[call-overload]
        if int(rec["attempts"]) >= settings.otp_max_attempts:  # type: ignore[call-overload]
            del self._by_email[key]
            return OtpVerification(OtpResult.TOO_MANY_ATTEMPTS)
        return OtpVerification(OtpResult.INVALID)


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self.enabled = True
        self._counts: dict[str, int] = defaultdict(int)

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        if not self.enabled:
            return True
        self._counts[key] += 1
        return self._counts[key] <= limit


class FakeEmailSender:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)

    @property
    def last_code(self) -> str | None:
        if not self.sent:
            return None
        match = re.search(r"\b(\d{6})\b", self.sent[-1].text)
        return match.group(1) if match else None


class RecordingQueue:
    def __init__(self) -> None:
        self.messages: list[TaskMessage] = []

    async def enqueue(self, message: TaskMessage) -> None:
        self.messages.append(message)


class FakeResumeStorage:
    """In-memory résumé object store."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def create_upload(self, *, user_id: uuid.UUID, content_type: str) -> Upload:
        ext = "pdf" if "pdf" in content_type else "docx"
        key = f"resumes/{user_id}/{uuid.uuid4().hex}.{ext}"
        return Upload(key=key, url=f"https://s3.test/{key}", max_bytes=settings.upload_max_bytes)

    def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def size(self, key: str) -> int | None:
        obj = self.objects.get(key)
        return len(obj) if obj is not None else None

    async def download(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class FakeLlmClient:
    """Duck-types LlmClient for worker tests (no anthropic SDK involved)."""

    def __init__(self, *, data: dict[str, object] | None = None, error: Exception | None = None):
        from decimal import Decimal

        self.model = "claude-sonnet-5-fake"
        self._data = data or {"summary": "s", "companies": [], "skills": ["python"]}
        self._error = error
        self._cost = Decimal("0.001")

    async def structured(self, *, prompt: str, schema: dict[str, object], **_: object):  # type: ignore[no-untyped-def]
        from app.llm.client import StructuredResult

        if self._error is not None:
            raise self._error
        return StructuredResult(
            data=dict(self._data), input_tokens=100, output_tokens=20, cost_usd=self._cost
        )

    def usage_row(self, result, *, purpose: str, **fields: object):  # type: ignore[no-untyped-def]
        from app.models import LlmUsage

        return LlmUsage(
            purpose=purpose,
            model=self.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
            user_id=fields.get("user_id"),
            related_kind=fields.get("related_kind"),
            related_id=fields.get("related_id"),
        )
