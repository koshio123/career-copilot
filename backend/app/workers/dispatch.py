from __future__ import annotations

import structlog

import app.workers.tasks  # noqa: F401  (registers handlers)
from app.queue.base import TaskMessage
from app.workers.idempotency import IdempotencyStore, get_idempotency_store
from app.workers.registry import get_handler

log = structlog.get_logger(__name__)


class UnknownTask(Exception):
    pass


async def dispatch(message: TaskMessage, *, idempotency: IdempotencyStore | None = None) -> None:
    handler = get_handler(message.task)
    if handler is None:
        raise UnknownTask(message.task)

    store = idempotency or get_idempotency_store()
    if await store.seen(message.idempotency_key):
        log.info("task.duplicate", task=message.task, key=message.idempotency_key)
        return

    log.info("task.start", task=message.task, key=message.idempotency_key)
    await handler(message.payload)
    await store.mark(message.idempotency_key)
    log.info("task.done", task=message.task, key=message.idempotency_key)
