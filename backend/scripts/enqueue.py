"""Enqueue a task for local manual testing.

    uv run python -m scripts.enqueue ping '{"echo": "hi"}'
    uv run python -m scripts.enqueue ping '{"fail": true}'
    uv run python -m scripts.enqueue somejob '{}' --browser

Creates the local LocalStack queues if needed. Needs `make up`.
"""

from __future__ import annotations

import asyncio
import json
import sys

from app.queue.base import TaskMessage
from app.queue.bootstrap import ensure_queues
from app.queue.sqs import QueueName, SqsQueue

_USAGE = "usage: python -m scripts.enqueue <task> [json-payload] [--browser]"


async def main() -> None:
    args = sys.argv[1:]
    if not args:
        raise SystemExit(_USAGE)

    task = args[0]
    queue: QueueName = "browser" if "--browser" in args else "default"
    payload_args = [a for a in args[1:] if not a.startswith("--")]
    payload = json.loads(payload_args[0]) if payload_args else {}

    message = TaskMessage(task=task, payload=payload)
    urls = await ensure_queues()
    await SqsQueue(urls[queue]).enqueue(message)
    print(f"enqueued {task} to {queue} (key {message.idempotency_key})")


if __name__ == "__main__":
    asyncio.run(main())
