"""Per-model prices used to turn metered tokens into cost (benchmark infrastructure).

Prices are USD per million tokens. The built-in table carries its source and
date; a run may override or extend it with the ``TAB_MODEL_PRICING``
environment variable (JSON ``{model: {input, output, cache_read,
cache_write}}``). The effective source note is part of the gateway's public
description, so a run's fingerprint changes when its prices do.

A model missing from the table has no price: its cost is ``None`` (reported
as ``cost_usd: null``), never a guess.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping

__all__ = ["ModelPrice", "Pricing", "DEFAULT_PRICES", "DEFAULT_SOURCE", "PRICING_ENV_VAR"]

PRICING_ENV_VAR = "TAB_MODEL_PRICING"
DEFAULT_SOURCE = "Anthropic list prices as of 2026-09-25"
_FIELDS = ("input", "output", "cache_read", "cache_write")


@dataclass(frozen=True)
class ModelPrice:
    """USD per million tokens for each token class."""

    input: float
    output: float
    cache_read: float
    cache_write: float

    def __post_init__(self) -> None:
        for name in _FIELDS:
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError(f"price field {name!r} must be a non-negative finite number")
            object.__setattr__(self, name, float(v))

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


DEFAULT_PRICES: dict[str, ModelPrice] = {
    "claude-opus-5-5": ModelPrice(4.0, 20.0, 0.20, 5.00),
    "claude-sonnet-5-5": ModelPrice(2.0, 10.0, 0.20, 2.50),
    "claude-haiku-4-5": ModelPrice(1.0, 5.0, 0.10, 1.25),
    "claude-fable-5-1": ModelPrice(10.0, 50.0, 0.25, 12.50),
    "claude-opus-5": ModelPrice(5.0, 25.0, 0.50, 6.25),
    # Harness-local backends cost nothing.
    "fake-v1": ModelPrice(0.0, 0.0, 0.0, 0.0),
    "hash-ngram-v1": ModelPrice(0.0, 0.0, 0.0, 0.0),
}


class Pricing:
    """An immutable price table plus a note saying where it came from."""

    def __init__(self, table: Mapping[str, ModelPrice] | None = None, source: str = DEFAULT_SOURCE) -> None:
        self._table = dict(DEFAULT_PRICES if table is None else table)
        self.source = source

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "Pricing":
        """Built-in prices, overridden per model by ``TAB_MODEL_PRICING`` if set.

        Raises ``ValueError`` for malformed JSON or prices: a run must not start
        with a pricing table it cannot interpret.
        """
        raw = environ.get(PRICING_ENV_VAR)
        if raw is None or raw.strip() == "":
            return cls()
        try:
            data = json.loads(raw)
        except ValueError:
            raise ValueError(f"{PRICING_ENV_VAR} is not valid JSON") from None
        if not isinstance(data, dict):
            raise ValueError(f"{PRICING_ENV_VAR} must be a JSON object {{model: {{input, output, cache_read, cache_write}}}}")
        table = dict(DEFAULT_PRICES)
        for model in sorted(data):
            entry = data[model]
            if not isinstance(model, str) or not model:
                raise ValueError(f"{PRICING_ENV_VAR}: model ids must be non-empty strings")
            if not isinstance(entry, dict) or set(entry) != set(_FIELDS):
                raise ValueError(f"{PRICING_ENV_VAR}: {model!r} must have exactly the fields {', '.join(_FIELDS)}")
            table[model] = ModelPrice(**{k: entry[k] for k in _FIELDS})
        source = f"{DEFAULT_SOURCE}; overridden by {PRICING_ENV_VAR} for: {', '.join(sorted(data))}" if data else DEFAULT_SOURCE
        return cls(table, source)

    def price(self, model: str | None) -> ModelPrice | None:
        if model is None:
            return None
        return self._table.get(model)

    def cost(
        self,
        model: str | None,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_input_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
    ) -> float | None:
        """USD cost of one call, rounded to 8 decimals; ``None`` if the model has no price."""
        p = self.price(model)
        if p is None:
            return None
        micro = (
            input_tokens * p.input
            + output_tokens * p.output
            + cache_read_input_tokens * p.cache_read
            + cache_creation_input_tokens * p.cache_write
        )
        return round(micro / 1_000_000, 8)

    def describe(self, models: list[str | None]) -> dict[str, Any]:
        """Public description: the source note and the prices of the given models (``None`` if unpriced)."""
        prices: dict[str, Any] = {}
        for m in sorted({m for m in models if m}):
            p = self.price(m)
            prices[m] = None if p is None else p.to_dict()
        return {"source": self.source, "per_mtok_usd": prices}
