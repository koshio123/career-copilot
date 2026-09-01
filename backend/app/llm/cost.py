"""Approximate Anthropic pricing, USD per 1M tokens (input, output).

Rough on purpose — it feeds cost dashboards and budget alerts, not billing.
Update when pricing changes.
"""

from __future__ import annotations

from decimal import Decimal

_PER_MILLION: dict[str, tuple[Decimal, Decimal]] = {
    "claude-opus-5": (Decimal("15"), Decimal("75")),
    "claude-sonnet-5": (Decimal("3"), Decimal("15")),
    "claude-haiku-4-5": (Decimal("1"), Decimal("5")),
}
_FALLBACK = (Decimal("3"), Decimal("15"))
_MILLION = Decimal(1_000_000)


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    key = next((m for m in _PER_MILLION if model.startswith(m)), None)
    input_rate, output_rate = _PER_MILLION[key] if key else _FALLBACK
    return (input_rate * input_tokens + output_rate * output_tokens) / _MILLION
