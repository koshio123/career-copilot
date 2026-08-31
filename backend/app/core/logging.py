"""Structured logging setup.

Human-readable console output locally; single-line JSON in the cloud
(``APP_LOG_JSON=true``). Request context is bound by the request middleware; a
processor here redacts obviously-sensitive keys.
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

# Keys whose values must never reach a log line.
_SENSITIVE_KEYS = frozenset(
    {"password", "code", "otp", "token", "session", "authorization", "cookie", "secret"}
)
_REDACTED = "***"


def _redact_sensitive(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    for key in list(event_dict):
        lowered = key.lower()
        if any(marker in lowered for marker in _SENSITIVE_KEYS):
            event_dict[key] = _REDACTED
        elif lowered in {"email", "ip"} and isinstance(event_dict[key], str):
            event_dict[key] = _mask(event_dict[key])
    return event_dict


def _mask(value: str) -> str:
    if "@" in value:  # email
        name, _, domain = value.partition("@")
        head = name[:1]
        return f"{head}***@{domain}"
    return value


def configure_logging(*, level: str = "INFO", json_logs: bool = False) -> None:
    log_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_sensitive,
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
