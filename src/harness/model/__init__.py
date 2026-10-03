"""Harness-metered model and embedding access (benchmark infrastructure, protocol amendment A3).

- :mod:`harness.model.gateway`: :class:`ModelGateway` (one per run),
  :class:`LaneModelService` (one per agent lane; a ``harness.tools.ModelService``),
  :func:`create_gateway`;
- :mod:`harness.model.tokens`: the deterministic token estimator;
- :mod:`harness.model.pricing`: per-model prices and cost;
- backends: :mod:`~harness.model.fake` (``fake-v1``),
  :mod:`~harness.model.anthropic_backend` (optional ``anthropic`` SDK),
  :mod:`~harness.model.embeddings` (``hash-ngram-v1``),
  :mod:`~harness.model.recorded` (replay).

This package is harness-side only; contestants reach it through the ToolBox.
"""

from __future__ import annotations

from harness.model.gateway import (
    PROVIDER_ERROR_PREFIX,
    CompletionBackend,
    EmbeddingBackend,
    LaneModelService,
    ModelGateway,
    RawCompletion,
    RawEmbedding,
    create_gateway,
    request_sha256,
    texts_sha256,
)
from harness.model.pricing import ModelPrice, Pricing
from harness.model.tokens import estimate_embedding_tokens, estimate_request_tokens, estimate_tokens

__all__ = [
    "PROVIDER_ERROR_PREFIX",
    "CompletionBackend",
    "EmbeddingBackend",
    "LaneModelService",
    "ModelGateway",
    "ModelPrice",
    "Pricing",
    "RawCompletion",
    "RawEmbedding",
    "create_gateway",
    "estimate_embedding_tokens",
    "estimate_request_tokens",
    "estimate_tokens",
    "request_sha256",
    "texts_sha256",
]
