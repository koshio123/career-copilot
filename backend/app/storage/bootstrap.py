"""Create the local résumé bucket (LocalStack). dev/prod is Terraform (Phase 10)."""

from __future__ import annotations

import asyncio

from botocore.exceptions import ClientError

from app.core.aws import s3_client
from app.core.config import settings

_CORS = {
    "CORSRules": [
        {
            "AllowedMethods": ["PUT"],
            "AllowedOrigins": ["http://localhost:3000"],
            "AllowedHeaders": ["*"],
            "MaxAgeSeconds": 3000,
        }
    ]
}


def _ensure_bucket_sync() -> None:
    client = s3_client()
    bucket = settings.s3_resume_bucket
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        kwargs: dict[str, object] = {"Bucket": bucket}
        if settings.aws_region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": settings.aws_region}
        client.create_bucket(**kwargs)
    client.put_bucket_cors(Bucket=bucket, CORSConfiguration=_CORS)


async def ensure_bucket() -> None:
    await asyncio.to_thread(_ensure_bucket_sync)
