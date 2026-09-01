from __future__ import annotations

import asyncio
from typing import Literal

import structlog

from app.core.aws import sqs_client
from app.core.config import settings
from app.queue.base import Queue, TaskMessage

log = structlog.get_logger(__name__)

QueueName = Literal["default", "browser"]


class SqsQueue:
    def __init__(self, queue_url: str) -> None:
        self._url = queue_url

    async def enqueue(self, message: TaskMessage) -> None:
        await asyncio.to_thread(
            sqs_client().send_message, QueueUrl=self._url, MessageBody=message.to_body()
        )


class LoggingQueue:
    """Fallback when no queue URL is configured — logs instead of enqueuing."""

    async def enqueue(self, message: TaskMessage) -> None:
        log.warning("queue.not_configured", task=message.task, key=message.idempotency_key)


def queue_url(name: QueueName) -> str | None:
    return settings.sqs_browser_queue_url if name == "browser" else settings.sqs_default_queue_url


def get_queue(name: QueueName = "default") -> Queue:
    url = queue_url(name)
    return SqsQueue(url) if url else LoggingQueue()
