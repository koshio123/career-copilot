"""AWS Lambda entrypoint for the short-job queue.

Uses SQS partial batch responses: failed messages come back in
``batchItemFailures`` so only they are retried / dead-lettered.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.queue.base import TaskMessage
from app.workers.dispatch import dispatch

log = structlog.get_logger(__name__)


def lambda_handler(event: dict[str, Any], _context: object = None) -> dict[str, Any]:
    return asyncio.run(_process(event.get("Records", [])))


async def _process(records: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    for record in records:
        message_id = str(record.get("messageId", ""))
        try:
            await dispatch(TaskMessage.from_body(record["body"]))
        except Exception:
            log.exception("task.failed", message_id=message_id)
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
