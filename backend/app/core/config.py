"""Application configuration.

All settings come from environment variables prefixed ``APP_`` (or a local
``.env`` file). Access via ``get_settings()`` so the object is built once and
can be overridden in tests with ``get_settings.cache_clear()``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["local", "dev", "prod"] = "local"
    debug: bool = False

    # SQLAlchemy async URL, e.g. postgresql+asyncpg://user:pass@host:5433/db
    database_url: str = "postgresql+asyncpg://career:career@localhost:5433/career_copilot"

    log_level: str = "INFO"
    log_json: bool = False

    # AWS / LocalStack.
    aws_region: str = "ap-northeast-1"
    aws_endpoint_url: str | None = None  # set to LocalStack URL for local dev

    # --- auth (ADR-0010) ---
    secret_key: str = "dev-only-change-me"  # HMAC key for email hashing etc.
    dynamodb_table_prefix: str = "career-copilot-local"

    session_cookie_name: str = "cc_session"
    session_cookie_secure: bool = False  # True in dev/prod (served over HTTPS)
    session_ttl_days: int = 30
    session_refresh_after_seconds: int = 3600  # throttle sliding-expiry writes

    csrf_cookie_name: str = "cc_csrf"
    csrf_header_name: str = "x-csrf-token"

    otp_length: int = 6
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 5
    otp_max_requests_per_email_per_hour: int = 5
    otp_max_requests_per_ip_per_hour: int = 20

    # --- email ---
    email_backend: Literal["console", "smtp", "ses"] = "console"
    email_from: str = "Career Copilot <noreply@career-copilot.local>"
    smtp_host: str = "localhost"
    smtp_port: int = 1025

    @property
    def is_local(self) -> bool:
        return self.env == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
