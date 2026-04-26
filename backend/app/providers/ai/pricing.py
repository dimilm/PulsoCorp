"""Coarse per-token pricing table for cost estimation.

Numbers are intentionally rough — we only need a ballpark figure to surface
in the AI history table so the user can spot when a single agent run costs
multiple cents. Update the constants as model pricing changes.
"""
from __future__ import annotations

# Price in USD per 1k tokens. Format: (input_per_1k, output_per_1k).
_OPENAI_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "gpt-4.1-mini": (0.0004, 0.0016),
    "gpt-4.1": (0.002, 0.008),
    "o4-mini": (0.0011, 0.0044),
}

_GEMINI_PRICES: dict[str, tuple[float, float]] = {
    "gemini-1.5-flash": (0.000075, 0.0003),
    "gemini-1.5-pro": (0.00125, 0.005),
    "gemini-2.0-flash": (0.0001, 0.0004),
    "gemini-2.0-pro": (0.00125, 0.005),
    # Gemini 3 preview pricing not officially published yet — placeholder
    # mirrors the 2.0 flash tier so cost estimates aren't ``None``. Update
    # once Google announces final pricing.
    "gemini-3-flash": (0.0001, 0.0004),
}


def _lookup(table: dict[str, tuple[float, float]], model: str) -> tuple[float, float] | None:
    if model in table:
        return table[model]
    # Match the longest known prefix so e.g. ``gpt-4o-mini-2024-07-18`` is
    # priced like the canonical model id.
    for known in sorted(table, key=len, reverse=True):
        if model.startswith(known):
            return table[known]
    return None


def estimate_cost(
    provider: str, model: str, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None
    table = _OPENAI_PRICES if provider == "openai" else _GEMINI_PRICES if provider == "gemini" else None
    if table is None:
        # Self-hosted (Ollama) and unknown providers report no cost.
        return 0.0
    prices = _lookup(table, model)
    if prices is None:
        return None
    in_price, out_price = prices
    cost = ((input_tokens or 0) / 1000.0) * in_price + ((output_tokens or 0) / 1000.0) * out_price
    return round(cost, 6)
