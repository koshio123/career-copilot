from __future__ import annotations

import pytest

from app.queue.base import TaskMessage
from app.workers.dispatch import UnknownTask, dispatch
from app.workers.lambda_handler import _process
from app.workers.registry import registered_tasks


class FakeIdempotency:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def seen(self, key: str) -> bool:
        return key in self.keys

    async def mark(self, key: str) -> None:
        self.keys.add(key)


def test_ping_is_registered() -> None:
    assert "ping" in registered_tasks()


async def test_dispatch_runs_the_handler_then_marks_it() -> None:
    store = FakeIdempotency()
    msg = TaskMessage(task="ping", payload={"echo": "hi"})
    await dispatch(msg, idempotency=store)
    assert msg.idempotency_key in store.keys


async def test_dispatch_skips_a_seen_key() -> None:
    store = FakeIdempotency()
    # A failing ping would raise if it ran; a seen key must skip it.
    msg = TaskMessage(task="ping", payload={"fail": True})
    store.keys.add(msg.idempotency_key)
    await dispatch(msg, idempotency=store)  # no exception


async def test_dispatch_rejects_an_unknown_task() -> None:
    with pytest.raises(UnknownTask):
        await dispatch(TaskMessage(task="nope"), idempotency=FakeIdempotency())


@pytest.mark.usefixtures("moto_aws")
async def test_lambda_handler_returns_only_failed_message_ids() -> None:
    from app.workers.idempotency import ensure_table

    await ensure_table()
    event = {
        "Records": [
            {
                "messageId": "ok-1",
                "body": TaskMessage(task="ping", payload={"echo": "a"}).to_body(),
            },
            {
                "messageId": "bad-1",
                "body": TaskMessage(task="ping", payload={"fail": True}).to_body(),
            },
        ]
    }
    result = await _process(event["Records"])
    assert result == {"batchItemFailures": [{"itemIdentifier": "bad-1"}]}


@pytest.mark.usefixtures("moto_aws")
async def test_enqueue_then_worker_deletes_success_and_leaves_failure() -> None:
    from app.core.aws import sqs_client
    from app.queue.bootstrap import ensure_queues
    from app.queue.sqs import SqsQueue
    from app.workers.idempotency import ensure_table
    from app.workers.runner import _poll_once

    await ensure_table()
    url = (await ensure_queues())["default"]
    queue = SqsQueue(url)
    await queue.enqueue(TaskMessage(task="ping", payload={"echo": "ok"}))
    await queue.enqueue(TaskMessage(task="ping", payload={"fail": True}))

    await _poll_once(sqs_client(), url)

    attrs = sqs_client().get_queue_attributes(
        QueueUrl=url,
        AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
    )["Attributes"]
    # success deleted; failure still in flight (visibility timeout → redrive → DLQ)
    assert attrs["ApproximateNumberOfMessages"] == "0"
    assert attrs["ApproximateNumberOfMessagesNotVisible"] == "1"
