"""Common agent interface (``tab.action/1``).

This module is contestant-facing. It must not import ``evaluation`` or any
harness module that knows where scenarios, events, or ground truth live.

Lifecycle, identical for every contestant::

    agent.setup(context)
    agent.on_start(tools)                         # optional seed ingestion (step 0)
    for each event, in order:
        response = agent.on_event(event, tools)   # tools: harness.tools.ToolBox
    agent.teardown()

Agents signal autonomous reconsideration with :class:`ReopenAction`. Nothing
in the event stream tells them when to do so.

Failure semantics: if ``on_event`` raises, the step's actions are lost, but
workspace edits already made through tools persist. During every agent call
the working directory is the agent's private ``state_dir``, and direct
filesystem access to workspaces, evaluator files, scenarios and run outputs
(and subprocess creation) is refused by ``harness.guard``; workspace access
goes through the traced, budgeted ``ToolBox``.
"""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:  # pragma: no cover
    from harness.tools import ToolBox

ACTION_SCHEMA_VERSION = "tab.action/1"

_TARGET_RE = re.compile(r"^([A-Za-z]{2,12})-0*([0-9]{1,6})$")


def canonical_target(raw: object) -> str | None:
    """Canonical form of a reopen target (``adr-4`` -> ``ADR-0004``); ``None`` if invalid."""
    if not isinstance(raw, str):
        return None
    m = _TARGET_RE.match(raw.strip())
    if not m:
        return None
    return f"{m.group(1).upper()}-{int(m.group(2)):04d}"


# --------------------------------------------------------------------- events
@dataclass(frozen=True)
class ChangedPath:
    op: str
    path: str


@dataclass(frozen=True)
class AgentEvent:
    """What a contestant sees of one event. Contains no evaluator labels."""

    schema_version: str
    event_id: str
    seq: int
    timestamp: str
    channel: str
    author: str
    subject: str
    body: str
    changed_paths: tuple[ChangedPath, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["changed_paths"] = [asdict(c) for c in self.changed_paths]
        return d


# -------------------------------------------------------------------- actions
class InvalidAction(ValueError):
    pass


def _str_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        raise InvalidAction(f"{field_name} must be a list of strings")
    try:
        items = tuple(value)  # type: ignore[arg-type]  # materialize once: generators are one-shot
    except TypeError:
        raise InvalidAction(f"{field_name} must be a list of strings") from None
    if not all(isinstance(v, str) for v in items):
        raise InvalidAction(f"{field_name} must be a list of strings")
    return items


HISTORICAL_STATE_KEYS = ("known_then", "true_then", "known_now_about_then")


@dataclass(frozen=True)
class HistoricalState:
    """An agent's account of a reopened item's information state (EXPERIMENT.md §11).

    Items are event ids (``evt-NNNN``) or ``"seed"`` for the initial repository:

    - ``known_then``: what the decision relied on when it was made;
    - ``true_then``: evidence about how the world actually was at decision time
      where that differed from what was believed (a retroactive fact; often empty);
    - ``known_now_about_then``: what has been learned since that bears on it.
    """

    known_then: tuple[str, ...] = ()
    true_then: tuple[str, ...] = ()
    known_now_about_then: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in HISTORICAL_STATE_KEYS:
            object.__setattr__(self, name, _str_tuple(getattr(self, name), name))

    def to_dict(self) -> dict[str, list[str]]:
        return {name: list(getattr(self, name)) for name in HISTORICAL_STATE_KEYS}


@dataclass(frozen=True)
class ReopenAction:
    """Declare that an earlier decision (``ADR-*``) or parked work item (``TCK-*``) is reopened."""

    target: str
    rationale: str = ""
    evidence: tuple[str, ...] = ()
    historical_state: HistoricalState | None = None

    type = "reopen"

    def __post_init__(self) -> None:
        if not isinstance(self.target, str):
            raise InvalidAction("reopen target must be a string")
        if not isinstance(self.rationale, str):
            raise InvalidAction("rationale must be a string")
        object.__setattr__(self, "evidence", _str_tuple(self.evidence, "evidence"))
        if self.historical_state is not None and not isinstance(self.historical_state, HistoricalState):
            raise InvalidAction("historical_state must be a HistoricalState")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "target": self.target,
            "canonical_target": canonical_target(self.target),
            "rationale": self.rationale,
            "evidence": list(self.evidence),
            "historical_state": None if self.historical_state is None else self.historical_state.to_dict(),
        }


@dataclass(frozen=True)
class NoteAction:
    """Free-form note recorded in the trace; never scored."""

    text: str

    type = "note"

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise InvalidAction("note text must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text}


Action = Union[ReopenAction, NoteAction]
ACTION_TYPES = (ReopenAction, NoteAction)


def action_from_dict(d: dict[str, Any]) -> Action:
    """Inverse of ``Action.to_dict`` (used by replay)."""
    kind = d.get("type")
    if kind == "reopen":
        hs = d.get("historical_state")
        return ReopenAction(
            target=d["target"],
            rationale=d.get("rationale", ""),
            evidence=tuple(d.get("evidence") or ()),
            historical_state=None if hs is None else HistoricalState(**hs),
        )
    if kind == "note":
        return NoteAction(text=d["text"])
    raise InvalidAction(f"unknown action type: {kind!r}")


# ---------------------------------------------------------------------- usage
@dataclass(frozen=True)
class Usage:
    """Inference accounting reported by the agent (placeholders for non-LLM agents)."""

    model_input_tokens: int = 0
    model_output_tokens: int = 0
    retrieval_tokens: int = 0
    model_calls: int = 0
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        for name in ("model_input_tokens", "model_output_tokens", "retrieval_tokens", "model_calls"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise InvalidAction(f"usage.{name} must be a non-negative int")
        c = self.cost_usd
        if isinstance(c, bool) or not isinstance(c, (int, float)) or c < 0 or not math.isfinite(c):
            raise InvalidAction("usage.cost_usd must be a non-negative finite number")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentResponse:
    actions: list[Action] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


# -------------------------------------------------------------------- context
@dataclass(frozen=True)
class StepBudget:
    """Per-event budget applied identically to every contestant."""

    max_tool_calls_per_event: int = 200

    def __post_init__(self) -> None:
        n = self.max_tool_calls_per_event
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError("max_tool_calls_per_event must be a positive integer")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelSettings:
    """Shared foundation-model settings (placeholder until LLM contestants exist)."""

    name: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentContext:
    """Everything an agent receives at setup.

    ``state_dir`` is a private directory, persistent across events within a
    run, where the agent may keep its own memory. It is outside the workspace
    and outside the benchmark repository, and it is the working directory
    during every agent call. ``instructions`` is the harness-owned task
    description, identical for every agent (see ``harness.instructions``).
    The scenario's identity is deliberately not exposed.
    """

    agent_name: str
    seed: int
    state_dir: Path
    budget: StepBudget
    model: ModelSettings
    instructions: str
    instructions_version: str


# ---------------------------------------------------------------------- agent
class Agent(ABC):
    """Base class for every agent driven by the harness."""

    kind = "agent"
    # "contestant" for benchmark contestants; "reference" for non-contestant
    # sanity agents (dummy, keyword); "oracle" for the evaluator's solvability check.
    role = "contestant"

    def __init__(self, name: str | None = None) -> None:
        self.name = name or self.kind
        self.context: AgentContext | None = None

    def setup(self, context: AgentContext) -> None:
        self.context = context

    def on_start(self, tools: "ToolBox") -> None:
        """Optional ingestion of the initial (seed) world before the first event.

        Runs once, after ``setup``, with the same per-event tool budget as any
        event. Typical use: index the seed repository into private memory.
        """
        return None

    @abstractmethod
    def on_event(self, event: AgentEvent, tools: "ToolBox") -> AgentResponse:
        """Process one event. Use ``tools`` for all workspace access."""

    def teardown(self) -> None:
        return None

    def describe(self) -> dict[str, Any]:
        """Static description recorded in run metadata and the run-id hash."""
        return {"kind": self.kind, "role": self.role, "config": {}}
