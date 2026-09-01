"""Local / Fargate worker: poll SQS and dispatch to the same handlers Lambda uses.

``make worker`` runs this against LocalStack. On failure a message is left for
its visibility timeout to expire → redrive → DLQ.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from typing import Any

import structlog

from app.core.aws import sqs_client
from app.core.config import settings
from app.core.logging import configure_logging
from app.queue.base import TaskMessage
from app.queue.bootstrap import ensure_queues
from app.queue.sqs import queue_url
from app.workers.dispatch import dispatch
from app.workers.idempotency import ensure_table

log = structlog.get_logger(__name__)


async def _poll_once(client: Any, url: str) -> None:
    resp = await asyncio.to_thread(
        client.receive_message,
        QueueUrl=url,
        MaxNumberOfMessages=settings.worker_batch_size,
        WaitTimeSeconds=settings.worker_poll_wait_seconds,
    )
    for msg in resp.get("Messages", []):
        try:
            await dispatch(TaskMessage.from_body(msg["Body"]))
        except Exception:
            log.exception("task.failed", message_id=msg.get("MessageId"))
            continue  # leave it: visibility timeout → redrive → DLQ
        await asyncio.to_thread(
            client.delete_message, QueueUrl=url, ReceiptHandle=msg["ReceiptHandle"]
        )


async def _resolve_queue_url() -> str:
    if settings.is_local:
        await ensure_table()
        return (await ensure_queues())["default"]
    url = queue_url("default")
    if not url:
        raise SystemExit("APP_SQS_DEFAULT_QUEUE_URL is not set")
    return url


async def run() -> None:
    configure_logging(level=settings.log_level, json_logs=settings.log_json)
    url = await _resolve_queue_url()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    log.info("worker.start", queue=url)
    client = sqs_client()
    while not stop.is_set():
        await _poll_once(client, url)
    log.info("worker.stop")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
