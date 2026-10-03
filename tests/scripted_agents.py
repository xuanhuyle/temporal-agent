"""Scripted agents used only by tests."""

from __future__ import annotations

from pathlib import Path

from harness.agent import Agent, AgentContext, AgentEvent, AgentResponse, NoteAction, ReopenAction, Usage
from harness.tools import ToolBox
from harness.workspace import ToolError


class _TestAgent(Agent):
    """Scripted test agents are reference agents (allowed on draft scenarios)."""

    role = "reference"


class RecordingAgent(_TestAgent):
    """Remembers what it saw: event order and the workspace file set per step."""

    kind = "recording"

    def __init__(self, name: str = "recording") -> None:
        super().__init__(name)
        self.seen: list[int] = []
        self.files_at: dict[int, list[str]] = {}
        self.contexts: list[AgentContext] = []

    def setup(self, context: AgentContext) -> None:
        super().setup(context)
        self.contexts.append(context)

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:
        self.seen.append(event.seq)
        self.files_at[event.seq] = tools.list_files()
        return AgentResponse(actions=[NoteAction(f"saw {event.event_id}")], usage=Usage(model_calls=1, model_input_tokens=10))


class WriterAgent(_TestAgent):
    kind = "writer"

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:
        tools.write_file(f"notes/{self.name}-{event.seq}.md", f"{self.name} was here at {event.event_id}\n")
        assert self.context is not None
        (self.context.state_dir / f"memory-{event.seq}.txt").write_text(event.subject)
        return AgentResponse()


class ReopenOnTriggerAgent(_TestAgent):
    """Reopens a fixed target when it sees a given event id; optionally remediates."""

    kind = "reopener"

    def __init__(self, name: str, event_id: str, target: str, writes: dict[str, str] | None = None) -> None:
        super().__init__(name)
        self.event_id, self.target, self.writes = event_id, target, writes or {}

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:
        if event.event_id != self.event_id:
            return AgentResponse()
        for path, content in self.writes.items():
            tools.write_file(path, content)
        return AgentResponse(actions=[ReopenAction(self.target, rationale="scripted", evidence=(event.event_id,))])


class RaisingAgent(_TestAgent):
    kind = "raising"

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:
        if event.seq == 2:
            tools.read_file("app.py")
            raise RuntimeError("model API exploded")
        return AgentResponse()


class GreedyAgent(_TestAgent):
    """Exceeds the tool budget on every event."""

    kind = "greedy"

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:
        while True:
            tools.list_files()


class InvalidResponseAgent(_TestAgent):
    kind = "invalid"

    def on_event(self, event: AgentEvent, tools: ToolBox):  # type: ignore[override]
        return {"actions": ["reopen ADR-0001"]}


class SetupFailAgent(_TestAgent):
    kind = "setupfail"

    def setup(self, context: AgentContext) -> None:
        raise ValueError("cannot load model weights")

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:  # pragma: no cover
        raise AssertionError("must not be called after failed setup")


class ProbeAgent(_TestAgent):
    """Actively tries to reach evaluator files through every tool. Records anything it gets."""

    kind = "probe"

    def __init__(self, targets: list[Path], name: str = "probe") -> None:
        super().__init__(name)
        self.targets = [Path(t) for t in targets]
        self.leaked: list[str] = []
        self.denied = 0

    def _attempt(self, fn, *args) -> None:
        try:
            result = fn(*args)
        except ToolError:
            self.denied += 1
            return
        self.leaked.append(repr(result))

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:
        if event.seq != 1:
            return AgentResponse()
        for target in self.targets:
            abs_path = str(target)
            parts = target.parts[1:]
            self._attempt(tools.read_file, abs_path)
            self._attempt(tools.list_files, abs_path)
            self._attempt(tools.search, ".", abs_path)
            for depth in range(1, 14):
                rel = "../" * depth + "/".join(parts)
                self._attempt(tools.read_file, rel)
                self._attempt(tools.list_files, rel)
            for sneaky in ("~/" + "/".join(parts), "./" + abs_path, abs_path.replace("/", "\\")):
                self._attempt(tools.read_file, sneaky)
        # Legitimate listings/searches must not surface anything outside the workspace.
        self.leaked.extend(tools.list_files())
        self.leaked.append(repr(tools.search(".")))
        return AgentResponse()


class IndexingAgent(_TestAgent):
    """Ingests the seed world in on_start and keeps an index in its private state."""

    kind = "indexer"

    def __init__(self, name: str = "indexer") -> None:
        super().__init__(name)
        self.indexed: list[str] = []

    def on_start(self, tools: ToolBox) -> None:
        for path in tools.list_files():
            tools.read_file(path)
            self.indexed.append(path)
        assert self.context is not None
        (self.context.state_dir / "index.txt").write_text("\n".join(self.indexed))

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:
        return AgentResponse()
