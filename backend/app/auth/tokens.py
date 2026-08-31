"""Token generation and hashing.

Session tokens and OTP codes are compared by SHA-256 hash with a constant-time
check. That is correct here: session tokens carry 256 bits of entropy, and OTPs
are protected by rate limiting + an attempt cap + a short TTL, not by hash cost
(so no argon2 — ADR-0010).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from app.core.config import settings

_DIGITS = "0123456789"


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def new_otp_code() -> str:
    return "".join(secrets.choice(_DIGITS) for _ in range(settings.otp_length))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_email(email: str) -> str:
    """Keyed hash so the OTP table's partition key is not a raw email address."""
    return hmac.new(
        settings.secret_key.encode(), normalize_email(email).encode(), hashlib.sha256
    ).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
