"""The memory-system interface of the shared contestant runtime (contestant code).

Every model-backed contestant runs the same loop (``contestant_runtime.loop``)
with the same prompts, environment tools and budgets; contestants differ only
in the :class:`MemorySystem` they plug in (milestone-2 design section 8).

``tools`` is whatever the harness passed to the agent for the current step:
``harness.tools.ToolBox`` in-process, or the contestant-process proxy. Both
expose the methods of ``harness.tool_specs.TOOL_SPECS`` plus
``budget_remaining()``. This module deliberately does not import either.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from harness.agent import Action, AgentEvent
from harness.errors import ToolError
from harness.tool_specs import REQUIRED, ArgSpec, check_arg

from contestant_runtime.protocol import CatalogueEntry, MemorySection

__all__ = ["MemorySystem", "ContextPack", "MemorySection", "LocalTool", "EventOutcome"]


@dataclass(frozen=True)
class ContextPack:
    """What a memory system adds to the first message of a step.

    ``retrieval_chars`` is the number of characters of retrieved or stored
    memory in ``sections`` (used to attribute metered input tokens to
    retrieval, EXPERIMENT.md section 11). ``notes`` are short runtime notes
    (for example "dense retrieval unavailable") that the agent records as
    ``note`` actions.
    """

    sections: tuple[MemorySection, ...] = ()
    retrieval_chars: int = 0
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "sections", tuple(self.sections))
        object.__setattr__(self, "notes", tuple(self.notes))
        if self.retrieval_chars < 0:
            raise ValueError("retrieval_chars must be non-negative")


LocalHandler = Callable[[Any, dict[str, Any]], str]


@dataclass(frozen=True)
class LocalTool:
    """A memory tool executed in the contestant, offered to the model next to the environment tools.

    ``handler(tools, args)`` returns the observation text. It may call
    ``tools`` (for example ``tools.embed``); those calls are metered by the
    harness like any other. Argument types use the ``tool_specs`` vocabulary
    (``str``, ``int``, ``opt_str``, ``opt_int``). ``max_chars`` overrides the
    loop's observation size limit for this tool.
    """

    name: str
    args: tuple[ArgSpec, ...]
    description: str
    handler: LocalHandler
    max_chars: int | None = None

    def catalogue_entry(self) -> CatalogueEntry:
        return CatalogueEntry(self.name, self.args, self.description)

    def bind(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Validate model-supplied arguments; raises ``ToolError`` on unknown, missing or mistyped ones."""
        names = [a.name for a in self.args]
        unknown = sorted(k for k in raw if k not in names)
        if unknown:
            raise ToolError(f"{self.name}: unknown argument(s) {', '.join(unknown)}; expected {', '.join(names)}")
        bound: dict[str, Any] = {}
        for a in self.args:
            if a.name in raw:
                value = raw[a.name]
            elif a.default is REQUIRED:
                raise ToolError(f"{self.name}: missing required argument {a.name}")
            else:
                value = a.default
            problem = check_arg(self.name, a, value)
            if problem:
                raise ToolError(problem)
            bound[a.name] = value
        return bound


@dataclass
class EventOutcome:
    """What the loop produced for one step, handed to ``MemorySystem.after_event``.

    ``workspace_writes`` maps each workspace path the agent wrote (to its new
    content) or deleted (to ``None``) during the step, in call order, so a
    memory system can re-index its own edits without extra tool calls.
    """

    seq: int
    event_id: str | None
    actions: list[Action] = field(default_factory=list)
    memory: str = ""
    stop_reason: str = ""
    turns: int = 0
    protocol_errors: int = 0
    tool_log: list[dict[str, str]] = field(default_factory=list)
    workspace_writes: dict[str, str | None] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class MemorySystem(ABC):
    """A contestant's memory. Lifecycle (driven by ``contestant_runtime.agent.LLMAgent``)::

        open(state_dir, restart=...)
        ingest_seed(tools); start_context(tools); after_start(outcome, tools); checkpoint()   # step 0
        for each event:
            record_event(event)            # first, before anything else (persist the raw event)
            observe_world(event, tools)
            build_context(event, tools)
            ... model loop with local_tools() ...
            after_event(event, outcome, tools)
            checkpoint()
        checkpoint()                        # teardown

    A memory system may hold only what the agent has received so far: the
    seed repository, events already delivered, and its own conclusions.
    """

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        """Static, JSON-serializable description (no filesystem access)."""

    @abstractmethod
    def open(self, state_dir: Path, *, restart: bool) -> None:
        """Open (or, on ``restart``, recover) the stores under the agent's private ``state_dir``."""

    @abstractmethod
    def ingest_seed(self, tools: Any) -> None:
        """Index the initial repository within the step's budget."""

    @abstractmethod
    def record_event(self, event: AgentEvent) -> None:
        """Persist the raw event durably. Called before any other processing of the event."""

    @abstractmethod
    def observe_world(self, event: AgentEvent, tools: Any) -> None:
        """React to the world change that came with the event (e.g. re-index changed paths)."""

    @abstractmethod
    def build_context(self, event: AgentEvent, tools: Any) -> ContextPack:
        """Memory sections for the event's first message."""

    @abstractmethod
    def local_tools(self) -> list[LocalTool]:
        """Memory tools offered to the model (may be empty)."""

    @abstractmethod
    def after_event(self, event: AgentEvent, outcome: EventOutcome, tools: Any) -> None:
        """Store the step's conclusions; update derived memory."""

    @abstractmethod
    def checkpoint(self) -> None:
        """Make the current state durable (atomic)."""

    # Optional hooks for step 0 ----------------------------------------------
    def start_context(self, tools: Any) -> ContextPack:
        """Memory sections for the ``<<start>>`` message (default: none)."""
        return ContextPack()

    def after_start(self, outcome: EventOutcome, tools: Any) -> None:
        """Store what the agent concluded from the seed repository (default: nothing)."""
        return None

    def reserved_model_calls(self) -> int:
        """Model calls ``after_event`` may need; the loop leaves them unused."""
        return 0
