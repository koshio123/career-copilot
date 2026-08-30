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

    # AWS / LocalStack — used from Phase 04 onward.
    aws_region: str = "ap-northeast-1"
    aws_endpoint_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
