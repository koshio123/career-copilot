from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import anthropic
import pytest
from anthropic.types import ToolUseBlock

from app.core.errors import ServiceUnavailableError
from app.llm.client import LlmClient
from app.llm.cost import estimate_cost_usd


class FakeMessages:
    def __init__(self, *, response: Any = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


class FakeAnthropic:
    def __init__(self, **kw: Any) -> None:
        self.messages = FakeMessages(**kw)


def _response(data: dict[str, Any], *, in_tok: int = 100, out_tok: int = 20) -> Any:
    return SimpleNamespace(
        content=[ToolUseBlock(type="tool_use", id="tu_1", name="extract", input=data)],
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok),
    )


def test_cost_estimate_is_positive_and_model_aware() -> None:
    sonnet = estimate_cost_usd("claude-sonnet-5", 1_000_000, 1_000_000)
    haiku = estimate_cost_usd("claude-haiku-4-5", 1_000_000, 1_000_000)
    assert sonnet == 18  # 3 + 15 per 1M
    assert haiku < sonnet


async def test_structured_returns_tool_input_and_usage() -> None:
    fake = FakeAnthropic(response=_response({"title": "Backend Engineer"}))
    client = LlmClient(client=fake)  # type: ignore[arg-type]

    result = await client.structured(prompt="extract the title", schema={"type": "object"})

    assert result.data == {"title": "Backend Engineer"}
    assert result.input_tokens == 100
    assert result.output_tokens == 20
    assert result.cost_usd > 0
    # forced tool use
    call = fake.messages.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "extract"}


class _FakeApiError(anthropic.APIError):
    def __init__(self) -> None:
        Exception.__init__(self, "the model is down")


async def test_api_error_maps_to_service_unavailable() -> None:
    client = LlmClient(client=FakeAnthropic(error=_FakeApiError()))  # type: ignore[arg-type]

    with pytest.raises(ServiceUnavailableError):
        await client.structured(prompt="x", schema={"type": "object"})


async def test_missing_tool_use_block_is_service_unavailable() -> None:
    empty = SimpleNamespace(content=[], usage=SimpleNamespace(input_tokens=1, output_tokens=1))
    client = LlmClient(client=FakeAnthropic(response=empty))  # type: ignore[arg-type]

    with pytest.raises(ServiceUnavailableError):
        await client.structured(prompt="x", schema={"type": "object"})


async def test_record_usage_writes_a_row(db: Any) -> None:
    from sqlalchemy import select

    from app.models import LlmUsage

    fake = FakeAnthropic(response=_response({"ok": True}))
    client = LlmClient(client=fake)  # type: ignore[arg-type]
    result = await client.structured(prompt="x", schema={"type": "object"})

    await client.record_usage(db, result, purpose="job_structure")
    rows = (await db.execute(select(LlmUsage))).scalars().all()
    assert len(rows) == 1
    assert rows[0].purpose == "job_structure"
    assert rows[0].model == client.model
