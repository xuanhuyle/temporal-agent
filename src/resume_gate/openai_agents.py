from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from .langgraph import (
    InMemoryManifestStore,
    ManifestStore,
    ResumeGateDecision,
    ResumeGateRefused,
)
from .validator import Issue, ValidationResult, Verdict, validate_resume


OpenAIContextProvider = Callable[[Any, Any], Mapping[str, Any] | None]


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _package_version() -> str | None:
    try:
        return version("openai-agents")
    except PackageNotFoundError:
        return None


def _model_identity(model: Any) -> str:
    if model is None:
        return "default"
    if isinstance(model, str):
        return model
    cls = type(model)
    return f"{cls.__module__}.{cls.__qualname__}"


def _callable_identity(value: Any) -> str:
    if value is None or isinstance(value, (str, bool, int, float)):
        return str(value)
    module = getattr(value, "__module__", type(value).__module__)
    qualname = getattr(value, "__qualname__", type(value).__qualname__)
    return f"{module}.{qualname}"


def _tool_record(tool: Any) -> dict[str, Any]:
    name = str(getattr(tool, "name", type(tool).__name__))
    payload = {
        "class": f"{type(tool).__module__}.{type(tool).__qualname__}",
        "name": name,
        "description": getattr(tool, "description", None),
        "params_json_schema": getattr(tool, "params_json_schema", None),
        "needs_approval": _callable_identity(getattr(tool, "needs_approval", None)),
        "is_enabled": _callable_identity(getattr(tool, "is_enabled", None)),
    }
    return {"version": f"sha256:{_digest(payload)}"}


def _tool_surface(agent: Any) -> dict[str, dict[str, Any]]:
    tools: dict[str, dict[str, Any]] = {}
    for tool in getattr(agent, "tools", ()) or ():
        name = str(getattr(tool, "name", type(tool).__name__))
        tools[name] = _tool_record(tool)
    return dict(sorted(tools.items()))


def _runstate_schema_fingerprint() -> str:
    try:
        from agents.run_state import RunState
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "OpenAI Agents integration requires the 'openai-agents' extra: "
            "pip install -e '.[openai-agents]'"
        ) from exc

    fields = []
    if dataclasses.is_dataclass(RunState):
        for field in dataclasses.fields(RunState):
            fields.append((field.name, str(field.type)))
    return f"sha256:{_digest(fields)}"


def _agent_version_fingerprint(agent: Any) -> str:
    payload = {
        "sdk": _package_version(),
        "name": getattr(agent, "name", None),
        "instructions": _callable_identity(getattr(agent, "instructions", None)),
        "tool_use_behavior": _callable_identity(getattr(agent, "tool_use_behavior", None)),
        "handoffs": [
            getattr(item, "name", getattr(item, "tool_name", type(item).__name__))
            for item in (getattr(agent, "handoffs", ()) or ())
        ],
    }
    return f"sha256:{_digest(payload)}"


def _deep_merge(base: dict[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in overlay.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, Mapping):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _interrupt_identity(item: Any) -> dict[str, Any]:
    raw_item = getattr(item, "raw_item", None)
    return {
        "agent": getattr(getattr(item, "agent", None), "name", None),
        "tool_name": getattr(item, "tool_name", None),
        "tool_call_id": getattr(item, "tool_call_id", None),
        "tool_lookup_key": getattr(item, "tool_lookup_key", None),
        "raw_type": (
            raw_item.get("type")
            if isinstance(raw_item, Mapping)
            else getattr(raw_item, "type", None)
        ),
    }


def _state_key(state: Any) -> str:
    interruptions = list(state.get_interruptions())
    if not interruptions:
        raise ValueError("Resume Gate can only key an OpenAI RunState with pending interruptions")
    identities = sorted(
        (_interrupt_identity(item) for item in interruptions),
        key=lambda item: _canonical(item),
    )
    return f"openai-runstate::{_digest(identities)}"


class OpenAIManifestBuilder:
    """Build the shared Resume Gate manifest from an OpenAI Agent + RunState."""

    def __init__(
        self,
        agent: Any,
        context_provider: OpenAIContextProvider | None = None,
    ) -> None:
        self.agent = agent
        self.context_provider = context_provider

    def __call__(self, state: Any) -> dict[str, Any]:
        manifest: dict[str, Any] = {
            "checkpoint_id": _state_key(state),
            "runtime": {
                "agent_version": _agent_version_fingerprint(self.agent),
                "state_schema": _runstate_schema_fingerprint(),
                "model": _model_identity(getattr(self.agent, "model", None)),
                "framework": "openai-agents",
                "framework_version": _package_version(),
            },
            "tools": _tool_surface(self.agent),
            "authorities": [],
            "dependencies": [],
            "side_effects": [],
        }
        if self.context_provider is not None:
            overlay = self.context_provider(state, self.agent)
            if overlay:
                manifest = _deep_merge(manifest, overlay)
        return manifest


class GuardedOpenAIRunner:
    """Resume Gate wrapper for OpenAI Agents SDK approval RunState.

    Initial runs are delegated to the SDK. If they pause for tool approval, the
    wrapper records a checkpoint-time manifest. When a serialized/restored
    RunState is later supplied, the current manifest is rebuilt and validated
    before the SDK sees the state. Thus an already-approved tool cannot execute
    from stale authority merely because its RunState was durably restored.
    """

    def __init__(
        self,
        *,
        store: ManifestStore | None = None,
        context_provider: OpenAIContextProvider | None = None,
    ) -> None:
        self.store = store or InMemoryManifestStore()
        self.context_provider = context_provider

    @staticmethod
    def _is_run_state(value: Any) -> bool:
        try:
            from agents.run_state import RunState
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "OpenAI Agents integration requires the 'openai-agents' extra"
            ) from exc
        return isinstance(value, RunState)

    def _validate_resume(self, agent: Any, state: Any) -> ResumeGateDecision:
        key = _state_key(state)
        saved = self.store.get(key)
        if saved is None:
            decision = ResumeGateDecision(
                key=key,
                result=ValidationResult(
                    verdict=Verdict.BLOCK,
                    checkpoint_id=key,
                    issues=(
                        Issue(
                            code="MANIFEST_MISSING",
                            verdict=Verdict.BLOCK,
                            message="No Resume Gate manifest exists for this OpenAI RunState.",
                            subject="checkpoint_manifest",
                        ),
                    ),
                ),
            )
            raise ResumeGateRefused(decision)

        current = OpenAIManifestBuilder(agent, self.context_provider)(state)
        result = validate_resume(saved, current)
        decision = ResumeGateDecision(key=key, result=result)
        if result.verdict is not Verdict.SAFE:
            raise ResumeGateRefused(decision)
        return decision

    def _capture_result(self, agent: Any, result: Any) -> None:
        interruptions = list(getattr(result, "interruptions", ()) or ())
        if not interruptions:
            return
        state = result.to_state()
        key = _state_key(state)
        manifest = OpenAIManifestBuilder(agent, self.context_provider)(state)
        self.store.put(key, manifest)

    async def run(self, agent: Any, input: Any, **kwargs: Any) -> Any:
        try:
            from agents import Runner
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "OpenAI Agents integration requires the 'openai-agents' extra"
            ) from exc

        key: str | None = None
        if self._is_run_state(input):
            key = _state_key(input)
            self._validate_resume(agent, input)

        result = await Runner.run(agent, input, **kwargs)
        if key is not None and not getattr(result, "interruptions", None):
            self.store.delete(key)
        self._capture_result(agent, result)
        return result

    def run_sync(self, agent: Any, input: Any, **kwargs: Any) -> Any:
        try:
            from agents import Runner
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "OpenAI Agents integration requires the 'openai-agents' extra"
            ) from exc

        key: str | None = None
        if self._is_run_state(input):
            key = _state_key(input)
            self._validate_resume(agent, input)

        result = Runner.run_sync(agent, input, **kwargs)
        if key is not None and not getattr(result, "interruptions", None):
            self.store.delete(key)
        self._capture_result(agent, result)
        return result


__all__ = [
    "GuardedOpenAIRunner",
    "OpenAIContextProvider",
    "OpenAIManifestBuilder",
]
