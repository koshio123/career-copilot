"""Fixed-window rate limiting on a DynamoDB counter item with a TTL.

Coarse and good enough for abuse control; API Gateway throttling is the outer
backstop.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Protocol

from app.auth.dynamo import RATELIMIT, table_name
from app.core.aws import dynamodb_resource


class RateLimiter(Protocol):
    async def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Record one hit; return True if still within ``limit`` for the window."""
        ...


class DynamoRateLimiter:
    def __init__(self) -> None:
        self._table = dynamodb_resource().Table(table_name(RATELIMIT))

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = int(datetime.now(UTC).timestamp())
        window_start = now - (now % window_seconds)
        item_key = f"{key}#{window_start}"
        resp = await asyncio.to_thread(
            self._table.update_item,
            Key={"key": item_key},
            UpdateExpression=("SET expires_at = if_not_exists(expires_at, :exp) ADD #c :one"),
            ExpressionAttributeNames={"#c": "count"},
            ExpressionAttributeValues={
                ":one": 1,
                ":exp": window_start + window_seconds * 2,
            },
            ReturnValues="UPDATED_NEW",
        )
        return int(resp["Attributes"]["count"]) <= limit


def get_rate_limiter() -> RateLimiter:
    return DynamoRateLimiter()
