"""Token accounting and model inference cost calculation engine.

Maintains configurable pricing rate cards per provider/model.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from app.observability.schema import TokenCostSummary


@dataclass(frozen=True)
class ModelRateCard:
    """Rate card per 1,000,000 tokens in USD."""

    provider: str
    model: str
    input_rate_per_1m: float
    output_rate_per_1m: float


# ── Known Pricing Rate Cards ──────────────────────────────────────────────────
_RATE_CARDS: dict[tuple[str, str], ModelRateCard] = {
    ("ollama", "llama3.2"): ModelRateCard(
        provider="ollama", model="llama3.2", input_rate_per_1m=0.0, output_rate_per_1m=0.0
    ),
    ("azure_openai", "gpt-4o-mini"): ModelRateCard(
        provider="azure_openai", model="gpt-4o-mini", input_rate_per_1m=0.15, output_rate_per_1m=0.60
    ),
    ("azure_openai", "gpt-4o"): ModelRateCard(
        provider="azure_openai", model="gpt-4o", input_rate_per_1m=2.50, output_rate_per_1m=10.00
    ),
    ("local", "sentence-transformers/all-MiniLM-L6-v2"): ModelRateCard(
        provider="local", model="sentence-transformers/all-MiniLM-L6-v2", input_rate_per_1m=0.0, output_rate_per_1m=0.0
    ),
    ("cross-encoder", "cross-encoder/ms-marco-MiniLM-L-6-v2"): ModelRateCard(
        provider="cross-encoder", model="cross-encoder/ms-marco-MiniLM-L-6-v2", input_rate_per_1m=0.0, output_rate_per_1m=0.0
    ),
}


def estimate_tokens_from_text(text: str) -> int:
    """Estimate token count from character length using the standard 4 char/token heuristic."""
    if not text:
        return 0
    return math.ceil(len(text) / 4.0)


def calculate_token_cost(
    *,
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    token_source: Literal["exact", "estimated"] = "exact",
) -> TokenCostSummary:
    """Calculate token consumption and estimated dollar cost for model execution.

    Unknown models safely default to $0.00 cost without failing.
    """
    total_tokens = max(0, input_tokens) + max(0, output_tokens)
    key = (provider.lower().strip(), model.lower().strip())
    rate_card = _RATE_CARDS.get(key)

    if rate_card is None:
        # Check by model name only if provider didn't match exactly
        for (p, m), rc in _RATE_CARDS.items():
            if m.lower() in model.lower() or model.lower() in m.lower():
                rate_card = rc
                break

    if rate_card is not None:
        input_cost = (max(0, input_tokens) / 1_000_000.0) * rate_card.input_rate_per_1m
        output_cost = (max(0, output_tokens) / 1_000_000.0) * rate_card.output_rate_per_1m
        total_cost = round(input_cost + output_cost, 6)
    else:
        input_cost = 0.0
        output_cost = 0.0
        total_cost = 0.0

    return TokenCostSummary(
        provider=provider,
        model=model,
        input_tokens=max(0, input_tokens),
        output_tokens=max(0, output_tokens),
        total_tokens=total_tokens,
        input_cost_usd=round(input_cost, 6),
        output_cost_usd=round(output_cost, 6),
        estimated_cost_usd=total_cost,
        token_source=token_source,
    )
