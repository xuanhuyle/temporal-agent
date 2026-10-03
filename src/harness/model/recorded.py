"""Replay backend: serves recorded model and embedding answers (benchmark infrastructure).

During replay the contestant is not re-run; the replay agent re-issues each
recorded ``model_complete``/``embed`` call through a fresh ToolBox and gateway.
This backend stands in for the provider so that the replayed run reproduces
the original's responses and metering without network access or cost.

Recorded call format (one mapping per call that reached a backend, in the
order the original run made them):

``model_complete``, answered::

    {"lane": str, "tool": "model_complete", "request_sha256": hex,
     "text": str, "stop_reason": str, "model": str,
     "input_tokens": int, "output_tokens": int,
     "cache_read_input_tokens": int, "cache_creation_input_tokens": int,
     # optional (defaults in brackets):
     "usage_available": bool [true], "reported_cost_usd": float|null [null],
     "auxiliary_input_tokens": int [0], "auxiliary_output_tokens": int [0],
     "meta": {...} [{}]}

``embed``, answered::

    {"lane": str, "tool": "embed", "texts_sha256": hex,
     "vectors": [[float, ...], ...], "model": str, "input_tokens": int}

A call that failed inside the backend replaces the answer fields with
``"error": str`` (the exact ToolError message the original run recorded);
replaying it raises that error again.

``request_sha256`` is :func:`harness.model.gateway.request_sha256` and
``texts_sha256`` is :func:`harness.model.gateway.texts_sha256`; both appear
in the gateway's metering record. :func:`recorded_calls_from_trace` builds
the list from a run's trace (``tool_call`` records with their ``meter`` and
the blob-stored ``result``).

Serving rules:
- each lane has one queue holding its completion and embedding calls in
  their original interleaving;
- the next call of the lane must be of the same tool and have the same
  request hash, else ``ToolError("replay: model request differs from the
  recorded one")`` and the queue does not advance;
- an exhausted queue raises ``ToolError("replay: no recorded model call left
  for this lane")``.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Callable, Iterable, Mapping

from harness.agent import ModelSettings
from harness.errors import ToolError
from harness.llm import InvalidModelRequest, ModelRequest
from harness.model.gateway import (
    PROVIDER_ERROR_PREFIX,
    ProviderError,
    ProviderUnavailable,
    RawCompletion,
    RawEmbedding,
    request_sha256,
    texts_sha256,
)

__all__ = ["RecordedBackend", "recorded_call_from_trace", "recorded_calls_from_trace", "MISMATCH", "EXHAUSTED"]

MISMATCH = "replay: model request differs from the recorded one"
EXHAUSTED = "replay: no recorded model call left for this lane"
MODEL_TOOLS = ("model_complete", "embed")
_HASH_KEY = {"model_complete": "request_sha256", "embed": "texts_sha256"}
_COMPLETION_FIELDS = (
    "text",
    "stop_reason",
    "model",
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)
_EMBEDDING_FIELDS = ("vectors", "model", "input_tokens")
# Completion fields that older recordings may lack, with the value they had then.
_OPTIONAL_COMPLETION_FIELDS: dict[str, Any] = {
    "usage_available": True,
    "reported_cost_usd": None,
    "auxiliary_input_tokens": 0,
    "auxiliary_output_tokens": 0,
    "meta": {},
    "model_verified": True,
}


def _validate(call: Any, index: int) -> dict[str, Any]:
    where = f"recorded call #{index}"
    if not isinstance(call, Mapping):
        raise ValueError(f"{where} must be a mapping")
    call = dict(call)
    lane, tool = call.get("lane"), call.get("tool")
    if not isinstance(lane, str) or not lane:
        raise ValueError(f"{where}: 'lane' must be a non-empty string")
    if tool not in MODEL_TOOLS:
        raise ValueError(f"{where}: 'tool' must be one of {', '.join(MODEL_TOOLS)}")
    digest = call.get(_HASH_KEY[tool])
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError(f"{where}: {_HASH_KEY[tool]!r} must be a sha256 hex digest")
    if "error" in call:
        if not isinstance(call["error"], str):
            raise ValueError(f"{where}: 'error' must be a string")
        return call
    needed = _COMPLETION_FIELDS if tool == "model_complete" else _EMBEDDING_FIELDS
    missing = [f for f in needed if f not in call]
    if missing:
        raise ValueError(f"{where}: missing field(s) {', '.join(missing)}")
    return call


class RecordedBackend:
    """Completion *and* embedding backend that serves a recording, per lane, in order."""

    name = "recorded"

    def __init__(self, calls: Iterable[Mapping[str, Any]]) -> None:
        self._queues: dict[str, deque[dict[str, Any]]] = {}
        for i, call in enumerate(calls):
            c = _validate(call, i)
            self._queues.setdefault(c["lane"], deque()).append(c)

    def unconsumed(self) -> dict[str, int]:
        """Recorded calls not yet served, per lane (lanes with none left are omitted)."""
        return {lane: len(q) for lane, q in sorted(self._queues.items()) if q}

    def _next(self, lane: str, tool: str, digest: str) -> dict[str, Any]:
        queue = self._queues.get(lane)
        if not queue:
            raise ToolError(EXHAUSTED)
        head = queue[0]
        if head["tool"] != tool or head[_HASH_KEY[tool]] != digest:
            raise ToolError(MISMATCH)
        queue.popleft()
        if "error" in head:
            failure = head.get("failure")
            if not isinstance(failure, Mapping):
                raise ToolError(head["error"])
            # A provider failure: re-raise it with the usage it consumed, so the replayed meter matches.
            cls = ProviderUnavailable if failure.get("fatal") else ProviderError
            usage = failure.get("usage")
            raise cls(head["error"], usage=None if usage is None else RawCompletion(**usage),
                      usage_unknown=bool(failure.get("usage_unknown")))
        return head

    def complete(
        self,
        request: ModelRequest,
        settings: ModelSettings,
        *,
        max_output_tokens: int,
        timeout_s: float | None,
        lane: str,
    ) -> RawCompletion:
        rec = self._next(lane, "model_complete", request_sha256(request))
        optional = {f: rec.get(f, default) for f, default in _OPTIONAL_COMPLETION_FIELDS.items()}
        return RawCompletion(**{f: rec[f] for f in _COMPLETION_FIELDS}, **optional)

    def embed(self, texts: list[str], settings: ModelSettings, *, timeout_s: float | None, lane: str) -> RawEmbedding:
        rec = self._next(lane, "embed", texts_sha256(texts))
        return RawEmbedding(vectors=rec["vectors"], model=rec["model"], input_tokens=rec["input_tokens"])


def recorded_call_from_trace(record: Mapping[str, Any], result: Any = None) -> dict[str, Any] | None:
    """The recorded call for one trace ``tool_call`` record, or ``None`` if it never reached a backend.

    ``record`` is the trace record (``agent``, ``tool``, ``args``, ``status``,
    and ``meter`` or ``error``); ``result`` is its blob-stored result (the
    ``ModelResponse``/``EmbeddingResponse`` dict) for ``ok`` records.

    Calls refused or rejected before the backend (budget, invalid request, no
    provider, no time left) are not part of the recording: replay reproduces
    them from the ToolBox and gateway logic itself. Failed calls are included
    only when the error came from the backend (prefix ``model provider error``).
    """
    tool = record.get("tool")
    if tool not in MODEL_TOOLS:
        return None
    lane = record.get("agent")
    status = record.get("status")
    if status == "ok":
        meter = record.get("meter")
        if not isinstance(meter, Mapping) or not isinstance(result, Mapping):
            raise ValueError(f"ok {tool} record needs its meter and result")
        out: dict[str, Any] = {"lane": lane, "tool": tool, _HASH_KEY[tool]: meter[_HASH_KEY[tool]]}
        fields = _COMPLETION_FIELDS if tool == "model_complete" else _EMBEDDING_FIELDS
        out.update({f: result[f] for f in fields})
        if tool == "model_complete":
            # What the meter shows beyond the response: usage availability, a
            # provider-reported cost, auxiliary usage and provider details.
            out["usage_available"] = bool(meter.get("usage_available", True))
            out["reported_cost_usd"] = meter.get("cost_usd") if meter.get("cost_basis") == "provider_reported" else None
            out["auxiliary_input_tokens"] = meter.get("auxiliary_input_tokens", 0)
            out["auxiliary_output_tokens"] = meter.get("auxiliary_output_tokens", 0)
            out["meta"] = dict(meter.get("provider_meta") or {})
            out["model_verified"] = meter.get("model_verified", True)
        return out
    error = record.get("error")
    if status != "error" or not isinstance(error, str) or not error.startswith(PROVIDER_ERROR_PREFIX):
        return None
    failure = _failure_from_meter(record.get("meter"))
    args = record.get("args") or {}
    if tool == "model_complete":
        raw = args.get("request")
        try:
            digest = request_sha256(ModelRequest.from_dict(raw))
        except (InvalidModelRequest, TypeError, KeyError):
            return None  # an invalid request never reaches a backend
    else:
        texts = args.get("texts")
        if not isinstance(texts, list):
            return None
        digest = texts_sha256(texts)
    out = {"lane": lane, "tool": tool, _HASH_KEY[tool]: digest, "error": error}
    if failure is not None:
        out["failure"] = failure
    return out


def _failure_from_meter(meter: Any) -> dict[str, Any] | None:
    """Usage a failed call consumed, from its metering record (see ProviderError)."""
    if not isinstance(meter, Mapping) or not meter.get("failed"):
        return None
    failure: dict[str, Any] = {"fatal": bool(meter.get("fatal"))}
    if not meter.get("usage_available", True):
        failure["usage"] = None
        failure["usage_unknown"] = True
        return failure
    failure["usage_unknown"] = False
    tokens = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    if any(not isinstance(meter.get(k), int) for k in tokens):
        failure["usage"] = None
        return failure
    failure["usage"] = {
        "text": "",
        "stop_reason": meter.get("stop_reason") or "error",
        "model": meter.get("model") or "unknown",
        **{k: meter[k] for k in tokens},
        "reported_cost_usd": meter.get("cost_usd") if meter.get("cost_basis") == "provider_reported" else None,
        "auxiliary_input_tokens": meter.get("auxiliary_input_tokens") or 0,
        "auxiliary_output_tokens": meter.get("auxiliary_output_tokens") or 0,
        "meta": dict(meter.get("provider_meta") or {}),
        "model_verified": meter.get("model_verified", True),
    }
    return failure


def recorded_calls_from_trace(
    records: Iterable[Mapping[str, Any]], load_result: Callable[[str], Any]
) -> list[dict[str, Any]]:
    """All recorded calls of a trace, in trace order. ``load_result(sha256)`` returns a stored blob."""
    calls: list[dict[str, Any]] = []
    for rec in records:
        if rec.get("type", "tool_call") != "tool_call" or rec.get("tool") not in MODEL_TOOLS:
            continue
        result = load_result(rec["result_sha256"]) if rec.get("status") == "ok" else None
        call = recorded_call_from_trace(rec, result)
        if call is not None:
            calls.append(call)
    return calls
