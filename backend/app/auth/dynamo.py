"""DynamoDB table names and local/test bootstrap.

In dev/prod the tables are created by Terraform (Phase 10). Locally and in tests
``ensure_tables()`` creates them (idempotent). All three use a numeric
``expires_at`` (epoch seconds) as the TTL attribute.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.aws import dynamodb_resource
from app.core.config import settings


def table_name(kind: str) -> str:
    return f"{settings.dynamodb_table_prefix}-{kind}"


SESSIONS = "sessions"
OTP = "otp"
RATELIMIT = "ratelimit"

_SPECS: list[dict[str, Any]] = [
    {
        "TableName": table_name(SESSIONS),
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [
            {"AttributeName": "token_hash", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        "KeySchema": [{"AttributeName": "token_hash", "KeyType": "HASH"}],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "user_id-index",
                "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    },
    {
        "TableName": table_name(OTP),
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [{"AttributeName": "email_hash", "AttributeType": "S"}],
        "KeySchema": [{"AttributeName": "email_hash", "KeyType": "HASH"}],
    },
    {
        "TableName": table_name(RATELIMIT),
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [{"AttributeName": "key", "AttributeType": "S"}],
        "KeySchema": [{"AttributeName": "key", "KeyType": "HASH"}],
    },
]


def _ensure_tables_sync() -> None:
    ddb = dynamodb_resource()
    existing = {t.name for t in ddb.tables.all()}
    for spec in _SPECS:
        name = spec["TableName"]
        if name in existing:
            continue
        ddb.create_table(**spec)
        ddb.Table(name).wait_until_exists()
        ddb.meta.client.update_time_to_live(
            TableName=name,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "expires_at"},
        )


async def ensure_tables() -> None:
    await asyncio.to_thread(_ensure_tables_sync)
