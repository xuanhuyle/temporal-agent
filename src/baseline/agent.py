"""``BaselineAgent``: the strong conventional contestant (contestant code).

The shared contestant runtime (``contestant_runtime.agent.LLMAgent``) with
:class:`baseline.memory.BaselineMemory`: append-only event log, checkpoints,
hybrid retrieval (BM25 + dense + entities, RRF), LLM query expansion and a
rolling summary. Configurations: ``baseline.presets`` (``k8``, ``k32``,
``k64``, ``full``).
"""

from __future__ import annotations

from typing import Any

from baseline.memory import BaselineMemory
from baseline.presets import resolve_config
from contestant_runtime.agent import RUNTIME_DEFAULTS, LLMAgent
from contestant_runtime.memory import MemorySystem

__all__ = ["BaselineAgent"]


class BaselineAgent(LLMAgent):
    kind = "baseline"
    role = "contestant"

    def resolve_config(self, raw: dict[str, Any]) -> dict[str, Any]:
        cfg = resolve_config(raw)
        super().resolve_config({k: cfg[k] for k in RUNTIME_DEFAULTS})  # validates the runtime keys
        return cfg

    def make_memory(self, config: dict[str, Any]) -> MemorySystem:
        return BaselineMemory(config)
