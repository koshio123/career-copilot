"""S3 access for uploaded résumé files.

Uploads go straight from the browser to S3 with a presigned PUT (the API and
Lambda never see the bytes). The worker downloads by key for text extraction.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from botocore.exceptions import ClientError

from app.core.aws import s3_client
from app.core.config import settings

_EXT = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


@dataclass(frozen=True, slots=True)
class Upload:
    key: str
    url: str
    max_bytes: int


class ResumeStorage:
    def __init__(self) -> None:
        self._bucket = settings.s3_resume_bucket

    def create_upload(self, *, user_id: uuid.UUID, content_type: str) -> Upload:
        ext = _EXT.get(content_type, "bin")
        key = f"resumes/{user_id}/{uuid.uuid4().hex}.{ext}"
        url = s3_client().generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=settings.upload_url_ttl_seconds,
        )
        return Upload(key=key, url=url, max_bytes=settings.upload_max_bytes)

    async def size(self, key: str) -> int | None:
        try:
            head = await asyncio.to_thread(s3_client().head_object, Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return int(head["ContentLength"])

    async def download(self, key: str) -> bytes:
        obj = await asyncio.to_thread(s3_client().get_object, Bucket=self._bucket, Key=key)
        body: bytes = await asyncio.to_thread(obj["Body"].read)
        return body

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(s3_client().delete_object, Bucket=self._bucket, Key=key)


def get_resume_storage() -> ResumeStorage:
    return ResumeStorage()
