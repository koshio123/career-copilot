"""Trivial task used for smoke tests and to exercise the dispatch path."""

from __future__ import annotations

from typing import Any

import structlog

from app.workers.registry import task

log = structlog.get_logger(__name__)


@task("ping")
async def ping(payload: dict[str, Any]) -> None:
    log.info("task.ping", echo=payload.get("echo"))
    if payload.get("fail"):
        raise RuntimeError("ping was asked to fail")
