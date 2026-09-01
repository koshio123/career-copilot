"""The real S3 ResumeStorage, against moto."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.aws import s3_client
from app.storage.bootstrap import _ensure_bucket_sync
from app.storage.s3 import ResumeStorage


@pytest.fixture
def bucket(moto_aws: object) -> None:
    _ensure_bucket_sync()


@pytest.mark.usefixtures("bucket")
async def test_upload_key_scoping_and_round_trip() -> None:
    storage = ResumeStorage()
    user_id = uuid4()

    upload = storage.create_upload(user_id=user_id, content_type="application/pdf")
    assert upload.key.startswith(f"resumes/{user_id}/")
    assert upload.key.endswith(".pdf")

    assert await storage.size(upload.key) is None  # nothing uploaded yet

    s3_client().put_object(Bucket="career-copilot-local-resumes", Key=upload.key, Body=b"%PDF-1.4")
    assert await storage.size(upload.key) == 8
    assert await storage.download(upload.key) == b"%PDF-1.4"

    await storage.delete(upload.key)
    assert await storage.size(upload.key) is None
