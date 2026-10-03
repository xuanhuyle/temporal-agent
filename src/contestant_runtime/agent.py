"""``LLMAgent``: the memory-agnostic model-backed contestant (contestant code).

Lifecycle (milestone-2 design section 8)::

    setup(ctx)          memory.use_model_settings(ctx.model); memory.open(state_dir, restart=ctx.restart_count > 0)
    on_start(tools)     memory.ingest_seed -> optional <<start>> loop -> memory.after_start -> checkpoint
    on_event(e, tools)  memory.record_event (first) -> observe_world -> build_context -> loop
                        -> after_event -> checkpoint
    teardown()          checkpoint

Subclasses provide :meth:`make_memory` and, usually, :meth:`resolve_config`.
Everything else (prompts, environment tools, the runtime's ``read_lines``,
loop limits, action conversion) is shared, so contestants differ only in
their memory system. The standing working guidance in the system prompt is a
recorded configuration choice (``runtime_guidance``: ``maintainer`` or
``minimal``); ``describe()`` records the variant, its full text and its hash.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from harness.agent import Agent, AgentContext, AgentEvent, AgentResponse, NoteAction, Usage
from harness.llm import ModelRequest

from contestant_runtime.loop import RUNTIME_TOOLS, LoopConfig, LoopResult, env_catalogue, run_event
from contestant_runtime.memory import ContextPack, EventOutcome, MemorySystem
from contestant_runtime.protocol import (
    GUIDANCE_VARIANTS,
    PROTOCOL_VERSION,
    guidance_sha256,
    runtime_rules,
    render_event_message,
    render_start_message,
    render_system_prompt,
)

__all__ = ["LLMAgent", "RUNTIME_DEFAULTS", "loop_config_from"]

# Runtime (loop) configuration keys and their defaults. Subclasses merge
# these with their memory-system keys in ``resolve_config``.
RUNTIME_DEFAULTS: dict[str, Any] = {
    "max_turns": 20,
    "observation_chars": 24000,
    "transcript_chars": 120_000,
    "max_protocol_retries": 2,
    "max_actions": 32,
    "memory_chars": 6000,
    "max_output_tokens": None,
    "start_turn": True,
    "runtime_guidance": "maintainer",  # maintainer | minimal (protocol.WORK_GUIDANCE)
}
_LOOP_KEYS = ("max_turns", "observation_chars", "transcript_chars", "max_protocol_retries", "max_actions",
              "memory_chars", "max_output_tokens")


def loop_config_from(config: dict[str, Any]) -> LoopConfig:
    return LoopConfig(**{k: config[k] for k in _LOOP_KEYS if k in config})


class _CountingTools:
    """Delegates to the step's ``tools`` and counts model usage for the agent's self-reported ``Usage``.

    The harness meters usage independently; this count is for reference only.
    """

    def __init__(self, tools: Any) -> None:
        self._tools = tools
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.retrieval_chars = 0
        self.total_chars = 0

    def model_complete(self, request: ModelRequest) -> Any:
        response = self._tools.model_complete(request)
        self.calls += 1
        self.input_tokens += int(getattr(response, "input_tokens", 0) or 0)
        self.output_tokens += int(getattr(response, "output_tokens", 0) or 0)
        if isinstance(request, ModelRequest):
            self.retrieval_chars += request.retrieval_chars
            self.total_chars += request.total_chars()
        return response

    def retrieval_tokens(self) -> int:
        if self.total_chars <= 0:
            return 0
        return round(self.input_tokens * self.retrieval_chars / self.total_chars)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._tools, name)


class LLMAgent(Agent):
    """A model-backed contestant: the shared loop plus a pluggable :class:`MemorySystem`."""

    kind = "llm"
    role = "contestant"

    def __init__(self, name: str | None = None, config: dict[str, Any] | None = None) -> None:
        super().__init__(name)
        if config is not None and not isinstance(config, dict):
            raise ValueError("config must be a dict or None")
        self.config: dict[str, Any] = self.resolve_config(dict(config or {}))
        self.loop_config = loop_config_from(self.config)
        self.memory: MemorySystem | None = None

    # ------------------------------------------------------------ for subclasses
    def resolve_config(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Effective configuration from ``raw``; unknown keys raise ``ValueError``."""
        unknown = sorted(k for k in raw if k not in RUNTIME_DEFAULTS)
        if unknown:
            raise ValueError(f"unknown config key(s) for {self.kind}: {', '.join(unknown)}")
        cfg = dict(RUNTIME_DEFAULTS)
        cfg.update(raw)
        if not isinstance(cfg["start_turn"], bool):
            raise ValueError("start_turn must be a boolean")
        if cfg["runtime_guidance"] not in GUIDANCE_VARIANTS:
            raise ValueError(f"runtime_guidance must be one of {', '.join(GUIDANCE_VARIANTS)}, "
                             f"got {cfg['runtime_guidance']!r}")
        loop_config_from(cfg)  # validates the loop keys
        return cfg

    @abstractmethod
    def make_memory(self, config: dict[str, Any]) -> MemorySystem:
        """Build this contestant's memory system from the effective config (no filesystem access)."""

    def describe(self) -> dict[str, Any]:
        config = dict(self.config)
        config["protocol"] = PROTOCOL_VERSION
        config["runtime_tools"] = list(RUNTIME_TOOLS)
        config["runtime_guidance_text"] = runtime_rules(self.config["runtime_guidance"])
        config["runtime_guidance_sha256"] = guidance_sha256(self.config["runtime_guidance"])
        config["memory_system"] = self.make_memory(self.config).describe()
        return {"kind": self.kind, "role": self.role, "config": config}

    # -------------------------------------------------------------- lifecycle
    def _mem(self) -> MemorySystem:
        if self.memory is None:
            raise RuntimeError("setup() has not been called")
        return self.memory

    def setup(self, context: AgentContext) -> None:
        super().setup(context)
        self.memory = self.make_memory(self.config)
        self.memory.use_model_settings(context.model)
        self.memory.open(context.state_dir, restart=context.restart_count > 0)

    def _system_prompt(self) -> str:
        assert self.context is not None
        catalogue = env_catalogue() + [t.catalogue_entry() for t in self._mem().local_tools()]
        return render_system_prompt(self.context.instructions, catalogue, self.config["runtime_guidance"])

    def _loop(self, tools: Any, first_message: str, pack: ContextPack) -> LoopResult:
        memory = self._mem()
        return run_event(
            tools,
            system=self._system_prompt(),
            first_message=first_message,
            local_tools=memory.local_tools(),
            config=self.loop_config,
            retrieval_chars=pack.retrieval_chars,
            reserve_model_calls=memory.reserved_model_calls(),
            before_workspace_change=memory.before_workspace_change,
        )

    @staticmethod
    def _outcome(seq: int, event_id: str | None, result: LoopResult, extra_notes: tuple[str, ...]) -> EventOutcome:
        return EventOutcome(
            seq=seq,
            event_id=event_id,
            actions=list(result.actions),
            memory=result.memory,
            stop_reason=result.stop_reason,
            turns=result.turns,
            protocol_errors=result.protocol_errors,
            tool_log=list(result.tool_log),
            workspace_writes=dict(result.workspace_writes),
            notes=list(extra_notes) + list(result.notes),
        )

    def on_start(self, tools: Any) -> None:
        memory = self._mem()
        counting = _CountingTools(tools)
        memory.ingest_seed(counting)
        if self.config.get("start_turn", True):
            pack = memory.start_context(counting)
            first = render_start_message(pack.sections)
            result = self._loop(counting, first, pack)
            memory.after_start(self._outcome(0, None, result, pack.notes), counting)
        memory.checkpoint()

    def on_event(self, event: AgentEvent, tools: Any) -> AgentResponse:
        memory = self._mem()
        memory.record_event(event)  # durable before anything else can fail
        counting = _CountingTools(tools)
        memory.observe_world(event, counting)
        pack = memory.build_context(event, counting)
        first = render_event_message(event, pack.sections)
        result = self._loop(counting, first, pack)
        outcome = self._outcome(event.seq, event.event_id, result, pack.notes)
        memory.after_event(event, outcome, counting)
        memory.checkpoint()
        actions = list(result.actions)
        runtime_notes = list(pack.notes) + list(result.notes)
        if runtime_notes:
            actions.append(NoteAction(text="[runtime] " + " | ".join(runtime_notes)))
        usage = Usage(
            model_input_tokens=counting.input_tokens,
            model_output_tokens=counting.output_tokens,
            retrieval_tokens=counting.retrieval_tokens(),
            model_calls=counting.calls,
        )
        return AgentResponse(actions=actions, usage=usage)

    def teardown(self) -> None:
        if self.memory is not None:
            self.memory.checkpoint()
