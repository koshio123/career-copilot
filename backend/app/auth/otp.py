"""Email one-time codes (ADR-0010).

6 digits, 10-minute TTL, one active code per email, only the hash stored,
capped attempts. Delivery is handled by the caller (email sender).
"""

from __future__ import annotations

import asyncio
import enum
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from app.auth import tokens
from app.auth.dynamo import OTP, table_name
from app.core.aws import dynamodb_resource
from app.core.config import settings


class OtpResult(enum.StrEnum):
    OK = "ok"
    INVALID = "invalid"  # wrong code, no active code, or expired
    TOO_MANY_ATTEMPTS = "too_many_attempts"


@dataclass(frozen=True, slots=True)
class OtpVerification:
    result: OtpResult

    @property
    def ok(self) -> bool:
        return self.result is OtpResult.OK


class OtpStore(Protocol):
    async def issue(self, email: str, *, challenge: str) -> str: ...
    async def verify(self, email: str, code: str, *, challenge: str) -> OtpVerification: ...


def _now() -> datetime:
    return datetime.now(UTC)


class DynamoOtpStore:
    def __init__(self) -> None:
        self._table = dynamodb_resource().Table(table_name(OTP))

    async def issue(self, email: str, *, challenge: str) -> str:
        code = tokens.new_otp_code()
        now = _now()
        item: dict[str, Any] = {
            "email_hash": tokens.hash_email(email),
            "code_hash": tokens.hash_token(code),
            "challenge_hash": tokens.hash_token(challenge),
            "attempts": 0,
            "created_at": now.isoformat(),
            "expires_at": int((now + timedelta(seconds=settings.otp_ttl_seconds)).timestamp()),
        }
        await asyncio.to_thread(self._table.put_item, Item=item)
        return code

    async def verify(self, email: str, code: str, *, challenge: str) -> OtpVerification:
        key = {"email_hash": tokens.hash_email(email)}
        resp = await asyncio.to_thread(self._table.get_item, Key=key)
        item = resp.get("Item")
        if item is None or int(item["expires_at"]) <= int(_now().timestamp()):
            return OtpVerification(OtpResult.INVALID)
        if not tokens.constant_time_equals(
            item.get("challenge_hash", ""), tokens.hash_token(challenge)
        ):
            return OtpVerification(OtpResult.INVALID)

        if int(item["attempts"]) >= settings.otp_max_attempts:
            await asyncio.to_thread(self._table.delete_item, Key=key)
            return OtpVerification(OtpResult.TOO_MANY_ATTEMPTS)

        if tokens.constant_time_equals(item["code_hash"], tokens.hash_token(code)):
            await asyncio.to_thread(self._table.delete_item, Key=key)
            return OtpVerification(OtpResult.OK)

        new_attempts = int(item["attempts"]) + 1
        if new_attempts >= settings.otp_max_attempts:
            await asyncio.to_thread(self._table.delete_item, Key=key)
            return OtpVerification(OtpResult.TOO_MANY_ATTEMPTS)
        await asyncio.to_thread(
            self._table.update_item,
            Key=key,
            UpdateExpression="SET attempts = :a",
            ExpressionAttributeValues={":a": new_attempts},
        )
        return OtpVerification(OtpResult.INVALID)


def get_otp_store() -> OtpStore:
    return DynamoOtpStore()
