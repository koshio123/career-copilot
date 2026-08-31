"""Importing this package registers every task handler."""

from app.workers.tasks import ping

__all__ = ["ping"]
