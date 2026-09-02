"""Importing this package registers every task handler."""

from app.workers.tasks import job_source_fetch, ping, resume_process

__all__ = ["job_source_fetch", "ping", "resume_process"]
