"""Task queue abstraction.

A ``TaskMessage`` is the JSON envelope that travels on SQS: a task name, its
payload, and an idempotency key the worker uses to skip redeliveries.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class TaskMessage:
    task: str
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = field(default_factory=lambda: uuid.uuid4().hex)
    enqueued_at: str = field(default_factory=_now_iso)

    def to_body(self) -> str:
        return json.dumps(
            {
                "task": self.task,
                "payload": self.payload,
                "idempotency_key": self.idempotency_key,
                "enqueued_at": self.enqueued_at,
            }
        )

    @classmethod
    def from_body(cls, body: str) -> TaskMessage:
        data = json.loads(body)
        return cls(
            task=data["task"],
            payload=data.get("payload", {}),
            idempotency_key=data.get("idempotency_key") or uuid.uuid4().hex,
            enqueued_at=data.get("enqueued_at") or _now_iso(),
        )


class Queue(Protocol):
    async def enqueue(self, message: TaskMessage) -> None: ...
