"""Completion backend for ``provider = "anthropic"`` (benchmark infrastructure).

Uses the official ``anthropic`` Python SDK, an optional dependency
(``pip install 'temporal-agent-benchmark[anthropic]'``). The SDK is imported
lazily, on the first call, so this module imports fine without it and runs
that never use the provider do not need it.

Credentials are resolved by the SDK from the *harness* process environment
(``ANTHROPIC_API_KEY``, an auth token or a CLI profile). This module never
reads, logs or returns them, and contestant processes never receive them.

Request mapping (non-streaming ``client.messages.create``):

- ``model=settings.name`` (required);
- ``max_tokens`` = the gateway's cap for this call;
- ``system`` (omitted when empty), ``messages`` as ``{role, content}`` text;
- ``stop_sequences`` only when the request has any;
- ``temperature`` only when the run sets one, sent as
  ``extra_body={"temperature": t}``: SDK 1.x dropped the ``temperature``
  keyword from ``messages.create`` (current models reject sampling
  parameters), while ``extra_body`` works on every SDK version and lets the
  API decide. A run that sets a temperature for a model that rejects it
  fails loudly with a provider error instead of silently running unsampled;
- ``output_config={"effort": ...}`` only when the run sets an effort;
- top-level ``cache_control={"type": "ephemeral"}`` only with ``prompt_caching``;
- ``timeout`` = the step's remaining wall-clock time, when there is a deadline.

Server-side model fallbacks are never requested: a fallback would switch the
model in mid-run and break the equality of contestants (EXPERIMENT.md §6). A
refusal therefore comes back as ``stop_reason: "refusal"`` and is metered
like any other answer.

Response mapping: the text blocks joined in order (thinking and other block
types are not part of the protocol), ``stop_reason``, the response's model
id, and ``usage.input_tokens`` / ``output_tokens`` /
``cache_read_input_tokens`` / ``cache_creation_input_tokens`` (``None`` read
as 0).
"""

from __future__ import annotations

from typing import Any, Callable

from harness.agent import ModelSettings
from harness.errors import ToolError
from harness.llm import ModelRequest
from harness.model.gateway import PROVIDER_ERROR_PREFIX, RawCompletion

__all__ = ["AnthropicBackend", "build_request_kwargs", "parse_response"]


def _default_client() -> Any:
    try:
        import anthropic  # optional dependency, imported only when the provider is used
    except ImportError:
        raise ToolError(
            f"{PROVIDER_ERROR_PREFIX}: the 'anthropic' package is not installed in the harness "
            "(pip install 'temporal-agent-benchmark[anthropic]')"
        ) from None
    return anthropic.Anthropic()


def build_request_kwargs(
    request: ModelRequest, settings: ModelSettings, *, max_output_tokens: int, timeout_s: float | None
) -> dict[str, Any]:
    """Keyword arguments for ``client.messages.create`` (see the module docstring)."""
    if not (isinstance(settings.name, str) and settings.name):
        raise ToolError(f"{PROVIDER_ERROR_PREFIX}: provider 'anthropic' requires a model name in the run settings")
    kwargs: dict[str, Any] = {
        "model": settings.name,
        "max_tokens": max_output_tokens,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
    }
    if request.system:
        kwargs["system"] = request.system
    if request.stop:
        kwargs["stop_sequences"] = list(request.stop)
    if settings.temperature is not None:
        kwargs["extra_body"] = {"temperature": settings.temperature}
    if settings.effort:
        kwargs["output_config"] = {"effort": settings.effort}
    if settings.prompt_caching:
        kwargs["cache_control"] = {"type": "ephemeral"}
    if timeout_s is not None:
        kwargs["timeout"] = float(timeout_s)
    return kwargs


def _count(usage: Any, name: str) -> int:
    value = getattr(usage, name, None) if usage is not None else None
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ToolError(f"{PROVIDER_ERROR_PREFIX}: malformed usage in the provider response")
    return value


def parse_response(message: Any, settings: ModelSettings) -> RawCompletion:
    """Map an SDK ``Message`` (or any object of the same shape) to a :class:`RawCompletion`."""
    parts: list[str] = []
    for block in getattr(message, "content", None) or []:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", "")
            if isinstance(text, str):
                parts.append(text)
    usage = getattr(message, "usage", None)
    stop_reason = getattr(message, "stop_reason", None)
    model = getattr(message, "model", None)
    return RawCompletion(
        text="".join(parts),
        stop_reason=stop_reason if isinstance(stop_reason, str) and stop_reason else "unknown",
        model=model if isinstance(model, str) and model else str(settings.name),
        input_tokens=_count(usage, "input_tokens"),
        output_tokens=_count(usage, "output_tokens"),
        cache_read_input_tokens=_count(usage, "cache_read_input_tokens"),
        cache_creation_input_tokens=_count(usage, "cache_creation_input_tokens"),
    )


class AnthropicBackend:
    """Anthropic Messages API backend. ``client`` may be injected (tests); otherwise built lazily."""

    name = "anthropic"

    def __init__(self, client: Any = None, *, client_factory: Callable[[], Any] | None = None) -> None:
        self._client = client
        self._factory = client_factory or _default_client

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                self._client = self._factory()
            except ToolError:
                raise
            except Exception as exc:  # noqa: BLE001 - never surface SDK messages (may name credentials)
                raise ToolError(f"{PROVIDER_ERROR_PREFIX}: {type(exc).__name__} while creating the client") from None
        return self._client

    def complete(
        self,
        request: ModelRequest,
        settings: ModelSettings,
        *,
        max_output_tokens: int,
        timeout_s: float | None,
        lane: str,
    ) -> RawCompletion:
        kwargs = build_request_kwargs(request, settings, max_output_tokens=max_output_tokens, timeout_s=timeout_s)
        client = self._get_client()
        message = client.messages.create(**kwargs)
        return parse_response(message, settings)
