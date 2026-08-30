"""Structured logging setup.

Human-readable console output locally; single-line JSON in the cloud
(``APP_LOG_JSON=true``). Request-scoped context and PII redaction are added in
Phase 02.
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.typing import Processor


def configure_logging(*, level: str = "INFO", json_logs: bool = False) -> None:
    log_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if json_logs:
        processors += [structlog.processors.format_exc_info, structlog.processors.JSONRenderer()]
    else:
        processors += [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
