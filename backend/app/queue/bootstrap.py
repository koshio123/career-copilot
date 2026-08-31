"""Create the local SQS queues + DLQs (LocalStack).

dev/prod queues are Terraform (Phase 10). ``ensure_queues()`` is idempotent and
runs from ``make worker`` and the test fixtures.
"""

from __future__ import annotations

import asyncio
import json

from app.core.aws import sqs_client
from app.core.config import settings

_QUEUES = {
    "default": f"{settings.dynamodb_table_prefix}-tasks",
    "browser": f"{settings.dynamodb_table_prefix}-browser",
}
_MAX_RECEIVE = 3


def _ensure_queues_sync() -> dict[str, str]:
    sqs = sqs_client()
    urls: dict[str, str] = {}
    for name, base in _QUEUES.items():
        dlq_url = sqs.create_queue(QueueName=f"{base}-dlq")["QueueUrl"]
        dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])[
            "Attributes"
        ]["QueueArn"]
        urls[name] = sqs.create_queue(
            QueueName=base,
            Attributes={
                "VisibilityTimeout": str(settings.worker_visibility_timeout),
                "RedrivePolicy": json.dumps(
                    {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": str(_MAX_RECEIVE)}
                ),
            },
        )["QueueUrl"]
    return urls


async def ensure_queues() -> dict[str, str]:
    return await asyncio.to_thread(_ensure_queues_sync)
