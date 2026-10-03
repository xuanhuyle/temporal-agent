from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .validator import ValidationResult, Verdict, validate_resume


Manifest = dict[str, Any]
CheckpointManifestFactory = Callable[[Any, Mapping[str, Any]], Manifest]
CurrentManifestFactory = Callable[[Any, Mapping[str, Any]], Manifest]


class ManifestStore(Protocol):
    def get(self, key: str) -> Manifest | None: ...
    def put(self, key: str, manifest: Manifest) -> None: ...
    def delete(self, key: str) -> None: ...


class InMemoryManifestStore:
    """Small default store for demos and tests.

    Production integrations should back this with storage that has the same
    durability scope as the LangGraph checkpointer.
    """

    def __init__(self) -> None:
        self._items: dict[str, Manifest] = {}

    def get(self, key: str) -> Manifest | None:
        value = self._items.get(key)
        return None if value is None else dict(value)

    def put(self, key: str, manifest: Manifest) -> None:
        self._items[key] = dict(manifest)

    def delete(self, key: str) -> None:
        self._items.pop(key, None)


@dataclass(frozen=True)
class ResumeGateDecision:
    key: str
    result: ValidationResult


class ResumeGateRefused(RuntimeError):
    """Raised before LangGraph executes a resume that is not SAFE."""

    def __init__(self, decision: ResumeGateDecision) -> None:
        self.decision = decision
        result = decision.result
        details = "; ".join(f"{issue.code}: {issue.message}" for issue in result.issues)
        super().__init__(f"Resume Gate {result.verdict.value} for {decision.key}: {details}")


def _resume_command(value: Any) -> bool:
    try:
        from langgraph.types import Command
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "LangGraph integration requires the 'langgraph' extra: "
            "pip install -e '.[langgraph]'"
        ) from exc
    return isinstance(value, Command) and value.resume is not None


def _configurable(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not config:
        return {}
    value = config.get("configurable", {})
    return value if isinstance(value, Mapping) else {}


def _manifest_key(config: Mapping[str, Any] | None) -> str:
    configurable = _configurable(config)
    thread_id = configurable.get("thread_id")
    if thread_id is None:
        raise ValueError(
            "Resume Gate requires LangGraph config['configurable']['thread_id'] "
            "so the checkpoint manifest can be bound to one persisted thread."
        )
    checkpoint_ns = configurable.get("checkpoint_ns") or ""
    return f"{thread_id}::{checkpoint_ns}"


def _has_pending_interrupt(snapshot: Any) -> bool:
    for task in getattr(snapshot, "tasks", ()) or ():
        if getattr(task, "interrupts", ()) or ():
            return True
    return False


class GuardedLangGraph:
    """Wrap a compiled LangGraph with fail-closed resume validation.

    The wrapper does not alter LangGraph checkpoint data. It stores a separate
    Resume Gate manifest whenever the graph is paused at an interrupt. Before a
    later Command(resume=...) is forwarded to LangGraph, it compares that
    checkpoint-time manifest with a freshly materialized current manifest.

    Any non-SAFE verdict is refused by default. The caller can catch
    ResumeGateRefused, perform migration or revalidation, and retry after
    updating the current environment.
    """

    def __init__(
        self,
        graph: Any,
        *,
        checkpoint_manifest: CheckpointManifestFactory,
        current_manifest: CurrentManifestFactory,
        store: ManifestStore | None = None,
    ) -> None:
        self.graph = graph
        self.checkpoint_manifest = checkpoint_manifest
        self.current_manifest = current_manifest
        self.store = store or InMemoryManifestStore()

    def _snapshot(self, config: Mapping[str, Any]) -> Any:
        return self.graph.get_state(config)

    def _missing_manifest_decision(self, key: str) -> ResumeGateDecision:
        from .validator import Issue
        return ResumeGateDecision(
            key=key,
            result=ValidationResult(
                verdict=Verdict.BLOCK,
                checkpoint_id=None,
                issues=(
                    Issue(
                        code="MANIFEST_MISSING",
                        verdict=Verdict.BLOCK,
                        message="No Resume Gate manifest exists for this persisted thread.",
                        subject="checkpoint_manifest",
                    ),
                ),
            ),
        )

    def _validate_before_resume(
        self, input: Any, config: Mapping[str, Any]
    ) -> ResumeGateDecision | None:
        if not _resume_command(input):
            return None
        key = _manifest_key(config)
        saved = self.store.get(key)
        if saved is None:
            raise ResumeGateRefused(self._missing_manifest_decision(key))
        snapshot = self._snapshot(config)
        current = self.current_manifest(snapshot, config)
        result = validate_resume(saved, current)
        decision = ResumeGateDecision(key=key, result=result)
        if result.verdict is not Verdict.SAFE:
            raise ResumeGateRefused(decision)
        return decision

    def _capture_after_run(self, config: Mapping[str, Any]) -> None:
        key = _manifest_key(config)
        snapshot = self._snapshot(config)
        if _has_pending_interrupt(snapshot):
            manifest = self.checkpoint_manifest(snapshot, config)
            self.store.put(key, manifest)
        else:
            self.store.delete(key)

    def invoke(
        self,
        input: Any,
        config: Mapping[str, Any],
        **kwargs: Any,
    ) -> Any:
        self._validate_before_resume(input, config)
        result = self.graph.invoke(input, config, **kwargs)
        self._capture_after_run(config)
        return result

    async def ainvoke(
        self,
        input: Any,
        config: Mapping[str, Any],
        **kwargs: Any,
    ) -> Any:
        self._validate_before_resume(input, config)
        result = await self.graph.ainvoke(input, config, **kwargs)
        self._capture_after_run(config)
        return result

    def stream(
        self,
        input: Any,
        config: Mapping[str, Any],
        **kwargs: Any,
    ) -> Iterator[Any]:
        self._validate_before_resume(input, config)
        try:
            yield from self.graph.stream(input, config, **kwargs)
        finally:
            self._capture_after_run(config)

    async def astream(
        self,
        input: Any,
        config: Mapping[str, Any],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        self._validate_before_resume(input, config)
        try:
            async for item in self.graph.astream(input, config, **kwargs):
                yield item
        finally:
            self._capture_after_run(config)

    def __getattr__(self, name: str) -> Any:
        """Delegate non-resume APIs such as get_state to the wrapped graph."""
        return getattr(self.graph, name)
