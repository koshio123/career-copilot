"""Anthropic client wrapper.

Structured extraction via forced tool use: the model must call one tool whose
``input_schema`` is the JSON Schema we want back. Token counts and an estimated
cost go to ``llm_usage``. SDK errors (after its own retries) map to
``ServiceUnavailableError``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

import anthropic
import structlog
from anthropic.types import ToolUseBlock
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ServiceUnavailableError
from app.llm.cost import estimate_cost_usd
from app.models import LlmUsage

log = structlog.get_logger(__name__)

_DEFAULT_SYSTEM = "You return only the requested structured data. Do not invent values."


class LlmRequestError(Exception):
    """A non-retryable LLM failure — a 4xx: bad request, auth, or (commonly)
    an exhausted credit balance. Retrying the same call will not help."""


def _status_message(exc: anthropic.APIStatusError) -> str:
    body = exc.body if isinstance(exc.body, dict) else {}
    err = body.get("error", {}) if isinstance(body.get("error"), dict) else {}
    return str(err.get("message") or exc.message or f"HTTP {exc.status_code}")


@dataclass(frozen=True, slots=True)
class StructuredResult:
    data: dict[str, Any]
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class LlmClient:
    def __init__(self, *, client: anthropic.AsyncAnthropic | None = None) -> None:
        self._client = client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            default_headers=(
                {"anthropic-workspace-id": settings.anthropic_workspace_id}
                if settings.anthropic_workspace_id
                else None
            ),
        )
        self.model = settings.llm_model

    async def structured(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        tool_name: str = "extract",
        system: str = _DEFAULT_SYSTEM,
        max_tokens: int = 4096,
    ) -> StructuredResult:
        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                tools=[
                    {
                        "name": tool_name,
                        "description": "Return the structured result.",
                        "input_schema": schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
            )
        except anthropic.APIStatusError as exc:
            log.warning("llm.api_error", status=exc.status_code, error=str(exc))
            if exc.status_code == 429 or exc.status_code >= 500:
                raise ServiceUnavailableError("The language model is unavailable.") from exc
            # 400/401/403/404/422 — our request or the account is the problem;
            # retrying won't help.
            raise LlmRequestError(_status_message(exc)) from exc
        except anthropic.APIError as exc:  # connection / timeout
            log.warning("llm.api_error", error=str(exc))
            raise ServiceUnavailableError("The language model is unavailable.") from exc

        block = next((b for b in response.content if isinstance(b, ToolUseBlock)), None)
        if block is None:
            raise ServiceUnavailableError("The language model returned no structured output.")

        usage = response.usage
        return StructuredResult(
            data=cast(dict[str, Any], block.input),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=estimate_cost_usd(self.model, usage.input_tokens, usage.output_tokens),
        )

    def usage_row(
        self,
        result: StructuredResult,
        *,
        purpose: str,
        user_id: uuid.UUID | None = None,
        related_kind: str | None = None,
        related_id: uuid.UUID | None = None,
    ) -> LlmUsage:
        return LlmUsage(
            user_id=user_id,
            purpose=purpose,
            model=self.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
            related_kind=related_kind,
            related_id=related_id,
        )

    async def record_usage(
        self, session: AsyncSession, result: StructuredResult, *, purpose: str, **fields: Any
    ) -> None:
        session.add(self.usage_row(result, purpose=purpose, **fields))
        await session.flush()


def get_llm_client() -> LlmClient:
    return LlmClient()
