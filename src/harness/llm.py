"""Provider-neutral model request/response types (contestant-facing, ``tab.model/1``).

Contestants never talk to a model provider directly. They build a
:class:`ModelRequest` and pass it to ``tools.model_complete(...)``. The
harness sends it to the run's configured backend, applies the run's model
settings (identical for every contestant), meters usage, and returns a
:class:`ModelResponse`. Embeddings work the same way through
``tools.embed(...)``.

The request deliberately has no ``model``, ``temperature`` or provider field:
those belong to the run, not to the contestant (protocol amendment A3).

This module imports nothing outside the standard library, so it can be
copied into a contestant process.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

MODEL_SCHEMA_VERSION = "tab.model/1"
ROLES = ("user", "assistant")
MAX_PURPOSE_CHARS = 64


class InvalidModelRequest(ValueError):
    pass


@dataclass(frozen=True)
class ModelMessage:
    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise InvalidModelRequest(f"message role must be one of {ROLES}, got {self.role!r}")
        if not isinstance(self.content, str) or not self.content:
            raise InvalidModelRequest("message content must be a non-empty string")

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class ModelRequest:
    """One text-completion request.

    - ``system``: system prompt (may be empty).
    - ``messages``: alternating conversation; must start and end with ``user``
      (assistant prefill is not supported by every provider).
    - ``max_output_tokens``: optional lower cap; the run's setting is the ceiling.
    - ``purpose``: free label used only for accounting breakdowns.
    - ``retrieval_chars``: how many characters of this request are retrieved
      memory (self-attributed by the contestant; used to apportion metered input
      tokens to "retrieval tokens", EXPERIMENT.md §11). Must not exceed the
      request's total characters.
    """

    system: str
    messages: tuple[ModelMessage, ...]
    max_output_tokens: int | None = None
    stop: tuple[str, ...] = ()
    purpose: str = ""
    retrieval_chars: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.system, str):
            raise InvalidModelRequest("system must be a string")
        msgs = tuple(self.messages)
        if not msgs or not all(isinstance(m, ModelMessage) for m in msgs):
            raise InvalidModelRequest("messages must be a non-empty sequence of ModelMessage")
        if msgs[0].role != "user" or msgs[-1].role != "user":
            raise InvalidModelRequest("messages must start and end with a user message")
        for a, b in zip(msgs, msgs[1:]):
            if a.role == b.role:
                raise InvalidModelRequest("messages must alternate between user and assistant")
        object.__setattr__(self, "messages", msgs)
        mot = self.max_output_tokens
        if mot is not None and (isinstance(mot, bool) or not isinstance(mot, int) or mot < 1):
            raise InvalidModelRequest("max_output_tokens must be a positive int or None")
        stop = tuple(self.stop)
        if not all(isinstance(s, str) and s for s in stop) or len(stop) > 4:
            raise InvalidModelRequest("stop must be at most 4 non-empty strings")
        object.__setattr__(self, "stop", stop)
        if not isinstance(self.purpose, str) or len(self.purpose) > MAX_PURPOSE_CHARS:
            raise InvalidModelRequest(f"purpose must be a string of at most {MAX_PURPOSE_CHARS} chars")
        rc = self.retrieval_chars
        if isinstance(rc, bool) or not isinstance(rc, int) or rc < 0 or rc > self.total_chars():
            raise InvalidModelRequest("retrieval_chars must be an int between 0 and the request's total chars")

    def total_chars(self) -> int:
        return len(self.system) + sum(len(m.content) for m in self.messages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MODEL_SCHEMA_VERSION,
            "system": self.system,
            "messages": [m.to_dict() for m in self.messages],
            "max_output_tokens": self.max_output_tokens,
            "stop": list(self.stop),
            "purpose": self.purpose,
            "retrieval_chars": self.retrieval_chars,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "ModelRequest":
        if not isinstance(d, dict):
            raise InvalidModelRequest("request must be an object")
        allowed = {"schema_version", "system", "messages", "max_output_tokens", "stop", "purpose", "retrieval_chars"}
        extra = set(d) - allowed
        if extra:
            raise InvalidModelRequest(f"unknown request field(s): {', '.join(sorted(extra))}")
        if d.get("schema_version", MODEL_SCHEMA_VERSION) != MODEL_SCHEMA_VERSION:
            raise InvalidModelRequest("unsupported request schema_version")
        raw_msgs = d.get("messages")
        if not isinstance(raw_msgs, list):
            raise InvalidModelRequest("messages must be a list")
        msgs = []
        for m in raw_msgs:
            if not isinstance(m, dict) or set(m) != {"role", "content"}:
                raise InvalidModelRequest("each message must be {role, content}")
            msgs.append(ModelMessage(m["role"], m["content"]))
        stop = d.get("stop") or []
        if not isinstance(stop, list):
            raise InvalidModelRequest("stop must be a list")
        return cls(
            system=d.get("system", ""),
            messages=tuple(msgs),
            max_output_tokens=d.get("max_output_tokens"),
            stop=tuple(stop),
            purpose=d.get("purpose", ""),
            retrieval_chars=d.get("retrieval_chars", 0),
        )


@dataclass(frozen=True)
class ModelResponse:
    """What the contestant gets back. Usage numbers are the harness-metered ones."""

    text: str
    stop_reason: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "stop_reason": self.stop_reason,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ModelResponse":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass(frozen=True)
class EmbeddingResponse:
    vectors: tuple[tuple[float, ...], ...]
    model: str
    input_tokens: int = 0

    def __post_init__(self) -> None:
        vecs = tuple(tuple(float(x) for x in v) for v in self.vectors)
        for v in vecs:
            if not all(math.isfinite(x) for x in v):
                raise ValueError("embedding vectors must be finite")
        object.__setattr__(self, "vectors", vecs)

    def to_dict(self) -> dict[str, Any]:
        return {"vectors": [list(v) for v in self.vectors], "model": self.model, "input_tokens": self.input_tokens}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EmbeddingResponse":
        return cls(vectors=tuple(tuple(v) for v in d["vectors"]), model=d["model"], input_tokens=d.get("input_tokens", 0))

