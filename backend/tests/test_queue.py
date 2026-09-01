from __future__ import annotations

import pytest

from app.queue.base import TaskMessage
from app.queue.bootstrap import ensure_queues
from app.queue.sqs import LoggingQueue, SqsQueue, get_queue


def test_task_message_round_trips_through_a_body() -> None:
    msg = TaskMessage(task="ping", payload={"echo": "hi"})
    restored = TaskMessage.from_body(msg.to_body())
    assert restored.task == "ping"
    assert restored.payload == {"echo": "hi"}
    assert restored.idempotency_key == msg.idempotency_key


def test_get_queue_falls_back_to_logging_when_unconfigured() -> None:
    assert isinstance(get_queue("default"), LoggingQueue)


async def test_logging_queue_is_a_noop() -> None:
    await LoggingQueue().enqueue(TaskMessage(task="ping"))


@pytest.mark.usefixtures("moto_aws")
async def test_sqs_queue_enqueues_a_readable_message() -> None:
    urls = await ensure_queues()
    queue = SqsQueue(urls["default"])
    await queue.enqueue(TaskMessage(task="ping", payload={"echo": "x"}))

    from app.core.aws import sqs_client

    received = sqs_client().receive_message(QueueUrl=urls["default"], MaxNumberOfMessages=1)
    body = received["Messages"][0]["Body"]
    assert TaskMessage.from_body(body).payload == {"echo": "x"}
