"""Importing this package registers every task handler."""

from app.workers.tasks import ping, resume_process

__all__ = ["ping", "resume_process"]
