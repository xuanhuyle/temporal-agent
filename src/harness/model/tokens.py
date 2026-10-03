"""Deterministic token estimator (benchmark infrastructure, protocol amendment A3).

The harness needs token counts *before* a call (budget pre-checks) and, for
the fake and hash backends, *instead of* a provider's count. Both use this
estimator: ``ceil(utf8_bytes / 4)``. It is not any provider's tokenizer; it is
a fixed, documented, provider-neutral rule, so budget decisions are identical
for every contestant and reproducible on every machine.

Real providers report their own usage, and the gateway meters that; the
estimate is then used only for the pre-check.
"""

from __future__ import annotations

from typing import Iterable

from harness.llm import ModelRequest

__all__ = [
    "BYTES_PER_TOKEN",
    "PER_MESSAGE_OVERHEAD_TOKENS",
    "estimate_tokens",
    "estimate_request_tokens",
    "estimate_embedding_tokens",
]

BYTES_PER_TOKEN = 4
# Role markers and turn framing cost a few tokens per message with any
# provider; a fixed allowance keeps many short messages from looking free.
PER_MESSAGE_OVERHEAD_TOKENS = 4


def _utf8_len(text: str) -> int:
    # ``surrogatepass`` so that a lone surrogate is counted, never a crash.
    return len(text.encode("utf-8", "surrogatepass"))


def estimate_tokens(text: str) -> int:
    """``ceil(utf8_bytes / 4)``; 0 for the empty string."""
    n = _utf8_len(text)
    return -(-n // BYTES_PER_TOKEN)


def estimate_request_tokens(request: ModelRequest) -> int:
    """Estimated input tokens of a request: system prompt plus each message and its fixed overhead."""
    total = estimate_tokens(request.system)
    for message in request.messages:
        total += estimate_tokens(message.content) + PER_MESSAGE_OVERHEAD_TOKENS
    return total


def estimate_embedding_tokens(texts: Iterable[str]) -> int:
    """Estimated input tokens of an embedding call (sum over texts, no overhead)."""
    return sum(estimate_tokens(t) for t in texts)
