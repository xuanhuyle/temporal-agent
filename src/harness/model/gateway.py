"""Harness-metered model gateway (benchmark infrastructure, protocol amendment A3).

One :class:`ModelGateway` exists per run, built from the run's
:class:`~harness.agent.ModelSettings`. Each agent lane gets a
:class:`LaneModelService` (``gateway.lane(name)``), which implements
:class:`harness.tools.ModelService` and is handed to that lane's ``ToolBox``.
Every lane therefore reaches the same backend with the same settings; a
request cannot name a model, provider or temperature (``harness.llm``).

For every call the gateway returns the response together with a *metering
record*, which the ToolBox sums into the step's meter and writes to the trace:

``model_complete``::

    {"provider", "model", "usage_available", "input_tokens", "output_tokens",
     "cache_read_input_tokens", "cache_creation_input_tokens",
     "total_input_tokens", "auxiliary_input_tokens", "auxiliary_output_tokens",
     "retrieval_tokens", "cost_usd", "cost_basis", "stop_reason", "purpose",
     "request_sha256", "max_output_tokens", "latency_ms", ["provider_meta"]}

- ``input_tokens`` is the provider's uncached input count and the cache
  fields are its cache reads/writes; ``total_input_tokens`` is their sum,
  i.e. every prompt token processed. Budgets and efficiency use the total.
- If a backend cannot report usage (``usage_available: false``) every token
  field is ``null``: the gateway never invents numbers. Budgets then fall
  back to the deterministic estimate, and the run is marked as having
  incomplete usage.
- ``cost_basis`` says where ``cost_usd`` comes from: ``price_table`` (token
  counts times the list prices in :mod:`harness.model.pricing`),
  ``provider_reported`` (a figure the provider or CLI reported for the call),
  or ``null`` when the call is unpriced (then ``cost_usd`` is ``null``).
- ``auxiliary_*`` count tokens a provider spent on its own side calls (the
  Claude CLI makes small auxiliary model calls); they are reported apart from
  the contestant's call.
- ``provider_meta`` holds provider-specific, JSON-only details (for the
  Claude CLI: CLI version, per-model usage, thinking tokens, turn count).

``embed``::

    {"provider", "model", "input_tokens", "cost_usd", "purpose",
     "texts_sha256", "count", "dims", "latency_ms"}

``latency_ms`` is wall-clock and volatile; everything else is a pure function
of the request, the settings and the backend's (or recording's) answer.

Errors. Anything a backend raises becomes a :class:`ToolError` whose message
starts with :data:`PROVIDER_ERROR_PREFIX`; a non-``ToolError`` exception is
reported by class name only, so provider messages (which may echo request
headers or account details) never reach a contestant or the trace. Backends
raise ``ToolError`` with that prefix themselves for conditions they detect.
The one exception is the replay backend, whose ``"replay: ..."`` errors pass
through unchanged.
"""

from __future__ import annotations

import hashlib
import math
import os
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from harness.agent import ModelSettings
from harness.canonical import canonical_json
from harness.errors import ToolError
from harness.llm import EmbeddingResponse, ModelRequest, ModelResponse
from harness.model.pricing import Pricing
from harness.model.tokens import estimate_embedding_tokens, estimate_request_tokens

__all__ = [
    "RawCompletion",
    "RawEmbedding",
    "CompletionBackend",
    "EmbeddingBackend",
    "ModelGateway",
    "LaneModelService",
    "create_gateway",
    "request_sha256",
    "texts_sha256",
    "PROVIDER_ERROR_PREFIX",
    "ProviderUnavailable",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEFAULT_EMBEDDING_DIMS",
    "COMPLETION_PROVIDERS",
    "EMBEDDING_PROVIDERS",
]

PROVIDER_ERROR_PREFIX = "model provider error"
# How each provider is reached (part of the run description, so it is in the fingerprint).
PROVIDER_TRANSPORTS = {
    "fake": "harness-local deterministic test double (machinery checks only; outputs are not model outputs)",
    "anthropic": "Anthropic Messages API via the official SDK (credentials from the harness environment)",
    "claude-cli": (
        "Claude Code CLI in non-interactive mode (claude -p --output-format json) with the operator's existing "
        "Claude login; tools, MCP servers and customizations disabled; the CLI adds its own context to every request"
    ),
}
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_EMBEDDING_DIMS = 384
MAX_EMBEDDING_DIMS = 65536
COMPLETION_PROVIDERS = ("none", "fake", "anthropic", "claude-cli")
EMBEDDING_PROVIDERS = ("none", "hash")
# Model ids of the harness-local backends (fixed; settings may only repeat them).
FAKE_MODEL_ID = "fake-v1"
HASH_EMBEDDING_MODEL_ID = "hash-ngram-v1"


# ------------------------------------------------------------------ raw types
class ProviderUnavailable(ToolError):
    """The provider cannot serve this run any more (not logged in, usage limit, CLI missing or broken).

    Raised by a backend instead of an ordinary provider error. The agent sees
    it as a tool error like any other, and the gateway records it in
    ``fatal_error``, which the runner checks after every agent call: a run
    whose model became unavailable is stopped and marked failed rather than
    continued with degraded, incomparable steps.
    """


@dataclass(frozen=True)
class RawCompletion:
    """What a completion backend returns: text plus the provider's (or estimator's) usage.

    ``usage_available=False`` means the backend could not obtain token counts;
    the count fields must then be 0 and are reported as ``null``.
    ``reported_cost_usd`` is a cost figure the provider itself reported for the
    call (used instead of the price table). ``meta`` is JSON-only.
    """

    text: str
    stop_reason: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    usage_available: bool = True
    reported_cost_usd: float | None = None
    auxiliary_input_tokens: int = 0
    auxiliary_output_tokens: int = 0
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawEmbedding:
    """What an embedding backend returns: one vector per input text, in order."""

    vectors: Sequence[Sequence[float]]
    model: str
    input_tokens: int


@runtime_checkable
class CompletionBackend(Protocol):
    name: str

    def complete(
        self,
        request: ModelRequest,
        settings: ModelSettings,
        *,
        max_output_tokens: int,
        timeout_s: float | None,
        lane: str,
    ) -> RawCompletion: ...


@runtime_checkable
class EmbeddingBackend(Protocol):
    name: str

    def embed(self, texts: list[str], settings: ModelSettings, *, timeout_s: float | None, lane: str) -> RawEmbedding: ...


# -------------------------------------------------------------------- hashing
def request_sha256(request: ModelRequest) -> str:
    """Identity of a completion request: sha256 of its canonical ``to_dict()``."""
    return hashlib.sha256(canonical_json(request.to_dict()).encode("ascii")).hexdigest()


def texts_sha256(texts: Sequence[str]) -> str:
    """Identity of an embedding request: sha256 of the canonical JSON list of texts."""
    return hashlib.sha256(canonical_json(list(texts)).encode("ascii")).hexdigest()


def _is_count(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _is_json(v: Any) -> bool:
    if not isinstance(v, Mapping):
        return False
    try:
        canonical_json(dict(v))
    except (TypeError, ValueError):
        return False
    return True


def _malformed(what: str) -> ToolError:
    return ToolError(f"{PROVIDER_ERROR_PREFIX}: malformed {what} from the backend")


def _provider_failure(exc: BaseException) -> ToolError:
    return ToolError(f"{PROVIDER_ERROR_PREFIX}: {type(exc).__name__}")


# -------------------------------------------------------------------- gateway
class ModelGateway:
    """The run's single path to a model and an embedding model."""

    def __init__(
        self,
        settings: ModelSettings,
        backend: CompletionBackend | None,
        embedder: EmbeddingBackend | None,
        pricing: Pricing | None = None,
    ) -> None:
        self.settings = settings
        self._backend = backend
        self._embedder = embedder
        self.pricing = pricing if pricing is not None else Pricing()
        # Set when a backend reports that the provider can no longer serve the run.
        self.fatal_error: str | None = None

    # ------------------------------------------------------------ description
    @property
    def completion_model(self) -> str | None:
        """The model id the run is configured to use (``None`` without a completion provider)."""
        s = self.settings
        if s.provider == "none":
            return None
        if s.provider == "fake":
            return s.name or FAKE_MODEL_ID
        return s.name

    @property
    def embedding_model(self) -> str | None:
        s = self.settings
        if s.embedding_provider == "none":
            return None
        if s.embedding_provider == "hash":
            return s.embedding_model or HASH_EMBEDDING_MODEL_ID
        return s.embedding_model

    @property
    def embedding_dims(self) -> int | None:
        s = self.settings
        if s.embedding_provider == "hash":
            return s.embedding_dims or DEFAULT_EMBEDDING_DIMS
        return s.embedding_dims

    def describe(self) -> dict[str, Any]:
        """Public configuration for run metadata and the run fingerprint.

        Derived only from the settings and the price table, never from the
        environment, so it carries no credentials and is identical when the
        run is replayed from a recording.
        """
        s = self.settings
        embedding_kind = None
        if s.embedding_provider == "hash":
            embedding_kind = "lexical feature hashing (word 1-2-grams, char 3-5-grams); not a neural semantic embedding"
        return {
            "provider": s.provider,
            "model": self.completion_model,
            "transport": PROVIDER_TRANSPORTS.get(s.provider),
            "settings": s.to_dict(),
            "effective_max_output_tokens": s.max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS,
            "embedding_provider": s.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_dims": self.embedding_dims,
            "embedding_kind": embedding_kind,
            "pricing": self.pricing.describe([self.completion_model, self.embedding_model]),
        }

    def runtime_info(self) -> dict[str, Any]:
        """Facts about the live backend (e.g. the Claude CLI version) for run metadata.

        Not part of :meth:`describe` (and so not of the run fingerprint),
        because it is read from the machine, not from the settings.
        """
        info = getattr(self._backend, "runtime_info", None)
        return dict(info()) if callable(info) else {}

    def lane(self, name: str) -> "LaneModelService":
        """The ModelService for one agent lane (use the lane's trace name: replay is keyed by it)."""
        if not isinstance(name, str) or not name:
            raise ValueError("lane name must be a non-empty string")
        return LaneModelService(self, name)

    # ------------------------------------------------------------ completions
    def _complete(
        self, lane: str, request: ModelRequest, max_output_tokens: int | None, timeout_s: float | None
    ) -> tuple[ModelResponse, dict[str, Any]]:
        if self._backend is None:
            raise ToolError("no model provider is configured for this run")
        if not isinstance(request, ModelRequest):
            raise ToolError("model_complete: request must be a ModelRequest")
        ceiling = self.settings.max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS
        cap = ceiling if max_output_tokens is None else min(int(max_output_tokens), ceiling)
        if cap < 1:
            raise ToolError("model_complete: no output tokens left for this call")
        if timeout_s is not None and timeout_s <= 0:
            raise ToolError("model_complete: no wall-clock time left in this step")
        digest = request_sha256(request)
        started = time.monotonic()
        try:
            raw = self._backend.complete(request, self.settings, max_output_tokens=cap, timeout_s=timeout_s, lane=lane)
        except ProviderUnavailable as exc:
            self.fatal_error = self.fatal_error or str(exc)
            raise
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001 - provider faults are reported by class only
            raise _provider_failure(exc) from None
        latency_ms = round((time.monotonic() - started) * 1000.0, 3)
        counts = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens",
                  "auxiliary_input_tokens", "auxiliary_output_tokens")
        if not (
            isinstance(raw, RawCompletion)
            and isinstance(raw.text, str)
            and isinstance(raw.stop_reason, str)
            and isinstance(raw.model, str)
            and raw.model
            and isinstance(raw.usage_available, bool)
            and all(_is_count(getattr(raw, f)) for f in counts)
            and (raw.usage_available or all(getattr(raw, f) == 0 for f in counts[:4]))
            and (raw.reported_cost_usd is None or (
                isinstance(raw.reported_cost_usd, (int, float)) and not isinstance(raw.reported_cost_usd, bool)
                and math.isfinite(raw.reported_cost_usd) and raw.reported_cost_usd >= 0))
            and _is_json(raw.meta)
        ):
            raise _malformed("completion")
        known = raw.usage_available
        total_in = raw.input_tokens + raw.cache_read_input_tokens + raw.cache_creation_input_tokens
        total_chars = request.total_chars()
        retrieval_tokens = round(total_in * request.retrieval_chars / total_chars) if total_chars else 0
        if raw.reported_cost_usd is not None:
            cost, basis = round(float(raw.reported_cost_usd), 8), "provider_reported"
        elif known:
            cost = self.pricing.cost(
                raw.model,
                input_tokens=raw.input_tokens,
                output_tokens=raw.output_tokens,
                cache_read_input_tokens=raw.cache_read_input_tokens,
                cache_creation_input_tokens=raw.cache_creation_input_tokens,
            )
            basis = "price_table" if cost is not None else None
        else:
            cost, basis = None, None
        meter: dict[str, Any] = {
            "provider": self.settings.provider,
            "model": raw.model,
            "usage_available": known,
            "input_tokens": raw.input_tokens if known else None,
            "output_tokens": raw.output_tokens if known else None,
            "cache_read_input_tokens": raw.cache_read_input_tokens if known else None,
            "cache_creation_input_tokens": raw.cache_creation_input_tokens if known else None,
            "total_input_tokens": total_in if known else None,
            "auxiliary_input_tokens": raw.auxiliary_input_tokens,
            "auxiliary_output_tokens": raw.auxiliary_output_tokens,
            "retrieval_tokens": retrieval_tokens if known else None,
            "cost_usd": cost,
            "cost_basis": basis,
            "stop_reason": raw.stop_reason,
            "purpose": request.purpose,
            "request_sha256": digest,
            "max_output_tokens": cap,
            "latency_ms": latency_ms,
        }
        if raw.meta:
            meter["provider_meta"] = dict(raw.meta)
        response = ModelResponse(
            text=raw.text,
            stop_reason=raw.stop_reason,
            model=raw.model,
            input_tokens=raw.input_tokens,
            output_tokens=raw.output_tokens,
            cache_read_input_tokens=raw.cache_read_input_tokens,
            cache_creation_input_tokens=raw.cache_creation_input_tokens,
        )
        return response, meter

    # ------------------------------------------------------------- embeddings
    def _embed(
        self, lane: str, texts: list[str], purpose: str, timeout_s: float | None
    ) -> tuple[EmbeddingResponse, dict[str, Any]]:
        if self._embedder is None:
            raise ToolError("no embedding model is configured for this run")
        items = list(texts)
        if not all(isinstance(t, str) for t in items):
            raise ToolError("embed: texts must be strings")
        if timeout_s is not None and timeout_s <= 0:
            raise ToolError("embed: no wall-clock time left in this step")
        digest = texts_sha256(items)
        started = time.monotonic()
        try:
            raw = self._embedder.embed(items, self.settings, timeout_s=timeout_s, lane=lane)
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001 - provider faults are reported by class only
            raise _provider_failure(exc) from None
        latency_ms = round((time.monotonic() - started) * 1000.0, 3)
        if not (isinstance(raw, RawEmbedding) and isinstance(raw.model, str) and raw.model and _is_count(raw.input_tokens)):
            raise _malformed("embedding")
        try:
            vectors = [list(v) for v in raw.vectors]
            ok = len(vectors) == len(items) and len({len(v) for v in vectors}) <= 1 and all(
                isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for v in vectors for x in v
            )
            response = EmbeddingResponse(vectors=tuple(tuple(v) for v in vectors), model=raw.model, input_tokens=raw.input_tokens)
        except (TypeError, ValueError):
            ok = False
        if not ok:
            raise _malformed("embedding")
        cost = self.pricing.cost(raw.model, input_tokens=raw.input_tokens)
        meter = {
            "provider": self.settings.embedding_provider,
            "model": raw.model,
            "input_tokens": raw.input_tokens,
            "cost_usd": cost,
            "purpose": purpose,
            "texts_sha256": digest,
            "count": len(items),
            "dims": len(vectors[0]) if vectors else 0,
            "latency_ms": latency_ms,
        }
        return response, meter


class LaneModelService:
    """One lane's view of the gateway; implements :class:`harness.tools.ModelService` exactly."""

    def __init__(self, gateway: ModelGateway, lane: str) -> None:
        self._gateway = gateway
        self.lane = lane

    def estimate_input_tokens(self, request: ModelRequest) -> int:
        return estimate_request_tokens(request)

    def complete(
        self, request: ModelRequest, *, max_output_tokens: int | None, timeout_s: float | None
    ) -> tuple[ModelResponse, dict[str, Any]]:
        return self._gateway._complete(self.lane, request, max_output_tokens, timeout_s)

    def estimate_embedding_tokens(self, texts: list[str]) -> int:
        return estimate_embedding_tokens(texts)

    def embed(self, texts: list[str], purpose: str, *, timeout_s: float | None) -> tuple[EmbeddingResponse, dict[str, Any]]:
        return self._gateway._embed(self.lane, texts, purpose, timeout_s)


# -------------------------------------------------------------------- factory
def _check_settings(settings: ModelSettings) -> None:
    s = settings
    if s.provider not in COMPLETION_PROVIDERS:
        raise ValueError(f"unknown model provider {s.provider!r}; expected one of {', '.join(COMPLETION_PROVIDERS)}")
    if s.embedding_provider not in EMBEDDING_PROVIDERS:
        raise ValueError(
            f"unknown embedding provider {s.embedding_provider!r}; expected one of {', '.join(EMBEDDING_PROVIDERS)}"
        )
    if s.provider in ("anthropic", "claude-cli") and not (isinstance(s.name, str) and s.name):
        raise ValueError(f"model provider {s.provider!r} requires a model name")
    if s.provider == "claude-cli" and s.temperature is not None:
        raise ValueError("model provider 'claude-cli' cannot set a temperature (the Claude CLI has no such option)")
    if s.provider == "fake" and s.name not in (None, FAKE_MODEL_ID):
        raise ValueError(f"model provider 'fake' serves only {FAKE_MODEL_ID!r}")
    if s.embedding_provider == "hash" and s.embedding_model not in (None, HASH_EMBEDDING_MODEL_ID):
        raise ValueError(f"embedding provider 'hash' serves only {HASH_EMBEDDING_MODEL_ID!r}")
    mot = s.max_output_tokens
    if mot is not None and (isinstance(mot, bool) or not isinstance(mot, int) or mot < 1):
        raise ValueError("max_output_tokens must be a positive int or None")
    dims = s.embedding_dims
    if dims is not None and (isinstance(dims, bool) or not isinstance(dims, int) or not 1 <= dims <= MAX_EMBEDDING_DIMS):
        raise ValueError(f"embedding_dims must be an int between 1 and {MAX_EMBEDDING_DIMS} or None")


def create_gateway(
    settings: ModelSettings,
    *,
    environ: Mapping[str, str] = os.environ,
    recorded: Any = None,
) -> ModelGateway:
    """Build the run's gateway from its settings.

    - ``settings.provider``: ``none`` (no completion backend; calls fail with
      ``ToolError``), ``fake`` or ``anthropic``.
    - ``settings.embedding_provider``: ``none`` or ``hash``.
    - ``recorded``: a :class:`~harness.model.recorded.RecordedBackend` or an
      iterable of recorded calls. It replaces every configured backend (a
      ``none`` provider stays ``none``, so "not configured" errors replay
      verbatim). Pricing still comes from ``environ``.
    - ``environ`` is read only for ``TAB_MODEL_PRICING``. Provider credentials
      are resolved by the provider SDK from the harness process environment;
      the gateway never reads, stores or reports them.

    Raises ``ValueError`` for an invalid configuration.
    """
    _check_settings(settings)
    pricing = Pricing.from_environ(environ)
    backend: CompletionBackend | None = None
    embedder: EmbeddingBackend | None = None
    if recorded is not None:
        from harness.model.recorded import RecordedBackend

        replay = recorded if isinstance(recorded, RecordedBackend) else RecordedBackend(recorded)
        backend = replay if settings.provider != "none" else None
        embedder = replay if settings.embedding_provider != "none" else None
        return ModelGateway(settings, backend, embedder, pricing)
    if settings.provider == "fake":
        from harness.model.fake import FakeBackend

        backend = FakeBackend()
    elif settings.provider == "anthropic":
        from harness.model.anthropic_backend import AnthropicBackend

        backend = AnthropicBackend()
    elif settings.provider == "claude-cli":
        from harness.model.claude_cli import ClaudeCliBackend

        backend = ClaudeCliBackend(environ=environ)
    if settings.embedding_provider == "hash":
        from harness.model.embeddings import HashEmbeddingBackend

        embedder = HashEmbeddingBackend()
    return ModelGateway(settings, backend, embedder, pricing)
