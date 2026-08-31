"""Outbound email.

``console`` logs the message (default, and what tests assert on), ``smtp`` talks
to MailHog locally, ``ses`` is used in the cloud (ADR-0010).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from typing import Protocol

import aiosmtplib
import structlog

from app.core.aws import ses_client
from app.core.config import settings

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    text: str


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleSender:
    async def send(self, message: EmailMessage) -> None:
        log.info("email.console", to=message.to, subject=message.subject, body=message.text)


class SmtpSender:
    async def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = settings.email_from
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        await aiosmtplib.send(
            mime, hostname=settings.smtp_host, port=settings.smtp_port, start_tls=False
        )


class SesSender:
    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(
            ses_client().send_email,
            Source=settings.email_from,
            Destination={"ToAddresses": [message.to]},
            Message={
                "Subject": {"Data": message.subject},
                "Body": {"Text": {"Data": message.text}},
            },
        )


def get_email_sender() -> EmailSender:
    match settings.email_backend:
        case "smtp":
            return SmtpSender()
        case "ses":
            return SesSender()
        case _:
            return ConsoleSender()
