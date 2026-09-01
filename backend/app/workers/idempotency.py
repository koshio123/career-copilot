"""At-least-once delivery guard.

DynamoDB table keyed by the message's idempotency key, TTL 24h. ``dispatch``
records a key after a handler succeeds and skips keys it has already seen. Two
concurrent first-deliveries can still both run, so handlers should also be
idempotent — this catches the common redelivery-after-success case.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Protocol

from app.core.aws import dynamodb_resource
from app.core.config import settings

_TTL_SECONDS = 86_400


def table_name() -> str:
    return f"{settings.dynamodb_table_prefix}-processed-tasks"


_SPEC: dict[str, Any] = {
    "TableName": table_name(),
    "BillingMode": "PAY_PER_REQUEST",
    "AttributeDefinitions": [{"AttributeName": "key", "AttributeType": "S"}],
    "KeySchema": [{"AttributeName": "key", "KeyType": "HASH"}],
}


def _ensure_sync() -> None:
    ddb = dynamodb_resource()
    if table_name() in {t.name for t in ddb.tables.all()}:
        return
    ddb.create_table(**_SPEC)
    ddb.Table(table_name()).wait_until_exists()
    ddb.meta.client.update_time_to_live(
        TableName=table_name(),
        TimeToLiveSpecification={"Enabled": True, "AttributeName": "expires_at"},
    )


async def ensure_table() -> None:
    await asyncio.to_thread(_ensure_sync)


class IdempotencyStore(Protocol):
    async def seen(self, key: str) -> bool: ...
    async def mark(self, key: str) -> None: ...


class DynamoIdempotencyStore:
    def __init__(self) -> None:
        self._table = dynamodb_resource().Table(table_name())

    async def seen(self, key: str) -> bool:
        resp = await asyncio.to_thread(self._table.get_item, Key={"key": key})
        return "Item" in resp

    async def mark(self, key: str) -> None:
        expires_at = int(datetime.now(UTC).timestamp()) + _TTL_SECONDS
        await asyncio.to_thread(self._table.put_item, Item={"key": key, "expires_at": expires_at})


def get_idempotency_store() -> IdempotencyStore:
    return DynamoIdempotencyStore()
