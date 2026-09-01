"""Enqueue every job source that is due for a re-fetch (local manual testing).

    uv run python -m scripts.schedule_fetches

Stands in for the EventBridge Scheduler → Lambda dispatcher (Phase 10). Needs
`make up`; a worker (`make worker`) then processes the enqueued fetches.
"""

from __future__ import annotations

import asyncio

from app.db.session import get_sessionmaker
from app.ingest.scheduler import enqueue_due_sources
from app.queue.bootstrap import ensure_queues
from app.queue.sqs import SqsQueue


async def main() -> None:
    urls = await ensure_queues()
    queue = SqsQueue(urls["default"])
    async with get_sessionmaker()() as session:
        count = await enqueue_due_sources(session, queue)
    print(f"enqueued {count} due job source(s)")


if __name__ == "__main__":
    asyncio.run(main())
