"""Server-side sessions (ADR-0010).

The cookie holds an opaque 256-bit token; DynamoDB stores only its SHA-256 hash.
30-day sliding expiry, with the refresh write throttled so steady traffic costs
~zero writes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from app.auth import tokens
from app.auth.dynamo import SESSIONS, table_name
from app.core.aws import dynamodb_resource
from app.core.config import settings


@dataclass(frozen=True, slots=True)
class SessionRecord:
    token_hash: str
    user_id: UUID
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    user_agent: str
    ip: str


class SessionStore(Protocol):
    async def create(self, *, user_id: UUID, user_agent: str, ip: str) -> str: ...
    async def get(self, token: str) -> SessionRecord | None: ...
    async def touch(self, record: SessionRecord) -> None: ...
    async def delete(self, token: str) -> None: ...
    async def delete_by_hash(self, token_hash: str) -> None: ...
    async def list_for_user(self, user_id: UUID) -> list[SessionRecord]: ...
    async def delete_all_for_user(
        self, user_id: UUID, *, keep_token: str | None = None
    ) -> None: ...


def _now() -> datetime:
    return datetime.now(UTC)


def _to_item(r: SessionRecord) -> dict[str, Any]:
    return {
        "token_hash": r.token_hash,
        "user_id": str(r.user_id),
        "created_at": r.created_at.isoformat(),
        "expires_at": int(r.expires_at.timestamp()),
        "last_seen_at": r.last_seen_at.isoformat(),
        "ua": r.user_agent,
        "ip": r.ip,
    }


def _from_item(item: dict[str, Any]) -> SessionRecord:
    return SessionRecord(
        token_hash=item["token_hash"],
        user_id=UUID(item["user_id"]),
        created_at=datetime.fromisoformat(item["created_at"]),
        expires_at=datetime.fromtimestamp(int(item["expires_at"]), tz=UTC),
        last_seen_at=datetime.fromisoformat(item["last_seen_at"]),
        user_agent=item.get("ua", ""),
        ip=item.get("ip", ""),
    )


class DynamoSessionStore:
    def __init__(self) -> None:
        self._table = dynamodb_resource().Table(table_name(SESSIONS))

    async def create(self, *, user_id: UUID, user_agent: str, ip: str) -> str:
        token = tokens.new_session_token()
        now = _now()
        record = SessionRecord(
            token_hash=tokens.hash_token(token),
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(days=settings.session_ttl_days),
            last_seen_at=now,
            user_agent=user_agent[:400],
            ip=ip,
        )
        await asyncio.to_thread(self._table.put_item, Item=_to_item(record))
        return token

    async def get(self, token: str) -> SessionRecord | None:
        resp = await asyncio.to_thread(
            self._table.get_item, Key={"token_hash": tokens.hash_token(token)}
        )
        item = resp.get("Item")
        if item is None:
            return None
        record = _from_item(item)
        if record.expires_at <= _now():  # TTL deletion can lag
            return None
        return record

    async def touch(self, record: SessionRecord) -> None:
        age = (_now() - record.last_seen_at).total_seconds()
        if age < settings.session_refresh_after_seconds:
            return
        now = _now()
        await asyncio.to_thread(
            self._table.update_item,
            Key={"token_hash": record.token_hash},
            UpdateExpression="SET last_seen_at = :s, expires_at = :e",
            ExpressionAttributeValues={
                ":s": now.isoformat(),
                ":e": int((now + timedelta(days=settings.session_ttl_days)).timestamp()),
            },
        )

    async def delete(self, token: str) -> None:
        await self.delete_by_hash(tokens.hash_token(token))

    async def delete_by_hash(self, token_hash: str) -> None:
        await asyncio.to_thread(self._table.delete_item, Key={"token_hash": token_hash})

    async def list_for_user(self, user_id: UUID) -> list[SessionRecord]:
        from boto3.dynamodb.conditions import Key

        resp = await asyncio.to_thread(
            self._table.query,
            IndexName="user_id-index",
            KeyConditionExpression=Key("user_id").eq(str(user_id)),
        )
        now = _now()
        return sorted(
            (r for r in map(_from_item, resp.get("Items", [])) if r.expires_at > now),
            key=lambda r: r.created_at,
            reverse=True,
        )

    async def delete_all_for_user(self, user_id: UUID, *, keep_token: str | None = None) -> None:
        keep_hash = tokens.hash_token(keep_token) if keep_token else None
        for record in await self.list_for_user(user_id):
            if record.token_hash != keep_hash:
                await self.delete_by_hash(record.token_hash)


def get_session_store() -> SessionStore:
    return DynamoSessionStore()
