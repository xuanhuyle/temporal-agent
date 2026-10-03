"""Agents the harness can build by name.

Reference (non-contestant) agents, run in the harness process:

- ``dummy``: no memory, no actions. The null floor.
- ``keyword``: no memory; reopens any ADR/TCK id mentioned in the current
  event. A shortcut detector: if it scores well, the scenario is worded too
  explicitly.

Model-backed contestants (``baseline-k8``, ``baseline-k32``, ``baseline-k64``,
``baseline-full``) are registered in ``harness.contestants`` and run in their
own process.
"""

from __future__ import annotations

from harness.agent import Agent
from harness.agents.dummy import NoMemoryAgent
from harness.agents.keyword import KeywordAgent

REGISTRY: dict[str, type[Agent]] = {
    NoMemoryAgent.kind: NoMemoryAgent,
    KeywordAgent.kind: KeywordAgent,
}


def available_kinds() -> list[str]:
    from harness.contestants import CONTESTANTS

    return sorted(REGISTRY) + sorted(CONTESTANTS)


def create_agent(spec: str) -> Agent:
    """Build an agent from ``kind`` or ``kind:name`` (name must be unique per run)."""
    from harness.contestants import CONTESTANTS, create_contestant

    kind, _, name = spec.partition(":")
    if kind in REGISTRY:
        return REGISTRY[kind](name=name or None)
    if kind in CONTESTANTS:
        return create_contestant(kind, name or None)
    raise ValueError(f"unknown agent kind {kind!r}; available: {', '.join(available_kinds())}")
