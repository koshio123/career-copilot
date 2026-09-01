"""boto3 client/resource factory.

When ``APP_AWS_ENDPOINT_URL`` is set (LocalStack) we inject dummy credentials so
boto3 does not go looking for a real credential chain.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import boto3

from app.core.config import settings


def _client_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs.update(
            endpoint_url=settings.aws_endpoint_url,
            aws_access_key_id="local",
            aws_secret_access_key="local",
        )
    return kwargs


@lru_cache
def dynamodb_resource() -> Any:
    return boto3.resource("dynamodb", **_client_kwargs())


@lru_cache
def ses_client() -> Any:
    return boto3.client("ses", **_client_kwargs())


@lru_cache
def sqs_client() -> Any:
    return boto3.client("sqs", **_client_kwargs())


@lru_cache
def s3_client() -> Any:
    kwargs = _client_kwargs()
    if settings.aws_endpoint_url:
        # LocalStack: path-style addressing so presigned URLs resolve on localhost.
        from botocore.config import Config

        kwargs["config"] = Config(s3={"addressing_style": "path"})
    return boto3.client("s3", **kwargs)
