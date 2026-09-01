"""Task name → handler registry.

A handler is ``async def handler(payload: dict) -> None``; it processes one
message and raises on failure (the caller decides retry vs. DLQ).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

Handler = Callable[[dict[str, Any]], Awaitable[None]]

_REGISTRY: dict[str, Handler] = {}


def task(name: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        if name in _REGISTRY:
            raise ValueError(f"task {name!r} is already registered")
        _REGISTRY[name] = fn
        return fn

    return register


def get_handler(name: str) -> Handler | None:
    return _REGISTRY.get(name)


def registered_tasks() -> list[str]:
    return sorted(_REGISTRY)
