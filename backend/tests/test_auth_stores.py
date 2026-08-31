"""The real DynamoDB store implementations, against moto."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from moto import mock_aws

from app.auth.dynamo import _ensure_tables_sync
from app.auth.otp import DynamoOtpStore, OtpResult
from app.auth.ratelimit import DynamoRateLimiter
from app.auth.sessions import DynamoSessionStore
from app.core import aws as aws_mod


@pytest.fixture
def dynamo() -> Iterator[None]:
    with mock_aws():
        aws_mod.dynamodb_resource.cache_clear()
        aws_mod.ses_client.cache_clear()
        _ensure_tables_sync()
        yield
    aws_mod.dynamodb_resource.cache_clear()
    aws_mod.ses_client.cache_clear()


@pytest.mark.usefixtures("dynamo")
async def test_session_store_roundtrip() -> None:
    store = DynamoSessionStore()
    user_id = uuid4()
    token = await store.create(user_id=user_id, user_agent="pytest", ip="1.2.3.4")

    record = await store.get(token)
    assert record is not None
    assert record.user_id == user_id

    listed = await store.list_for_user(user_id)
    assert [r.token_hash for r in listed] == [record.token_hash]

    await store.delete(token)
    assert await store.get(token) is None


@pytest.mark.usefixtures("dynamo")
async def test_otp_store_verifies_once() -> None:
    store = DynamoOtpStore()
    code = await store.issue("x@example.com", challenge="ch")

    assert (
        await store.verify("x@example.com", "999999", challenge="ch")
    ).result is OtpResult.INVALID
    assert (
        await store.verify("x@example.com", code, challenge="wrong")
    ).result is OtpResult.INVALID
    assert (await store.verify("x@example.com", code, challenge="ch")).ok
    # consumed
    assert not (await store.verify("x@example.com", code, challenge="ch")).ok


@pytest.mark.usefixtures("dynamo")
async def test_otp_store_caps_attempts() -> None:
    store = DynamoOtpStore()
    await store.issue("y@example.com", challenge="ch")
    results = [
        (await store.verify("y@example.com", "000000", challenge="ch")).result for _ in range(6)
    ]
    assert OtpResult.TOO_MANY_ATTEMPTS in results


@pytest.mark.usefixtures("dynamo")
async def test_rate_limiter_fixed_window() -> None:
    limiter = DynamoRateLimiter()
    results = [await limiter.hit("k", limit=3, window_seconds=60) for _ in range(5)]
    assert results == [True, True, True, False, False]
