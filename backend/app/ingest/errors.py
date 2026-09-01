"""Errors raised while fetching a career URL.

These are worker-side (not API) errors: a task catches them, records the reason
on the ``job_source``, and stops rather than retrying blindly (ADR-0013).
"""

from __future__ import annotations


class FetchError(Exception):
    """Base for any failure to retrieve a URL."""


class BlockedHostError(FetchError):
    """The URL resolves to a private / loopback / link-local / metadata address."""


class RobotsDisallowedError(FetchError):
    """``robots.txt`` disallows fetching this path for our User-Agent."""


class FetchTooLargeError(FetchError):
    """The response body exceeded ``settings.fetch_max_bytes``."""


class FetchTimeoutError(FetchError):
    """The request did not complete within ``settings.fetch_timeout_seconds``."""
