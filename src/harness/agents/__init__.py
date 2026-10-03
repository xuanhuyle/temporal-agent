"""Reference (non-contestant) agents.

- ``dummy``: no memory, no actions. The null floor.
- ``keyword``: no memory; reopens any ADR/TCK id mentioned in the current
  event. A shortcut detector: if it scores well, the scenario is worded too
  explicitly.

Real contestants (``baseline``, ``tesseract``) are not registered here in
Milestone 1.
"""

from __future__ import annotations

from harness.agent import Agent
from harness.agents.dummy import NoMemoryAgent
from harness.agents.keyword import KeywordAgent

REGISTRY: dict[str, type[Agent]] = {
    NoMemoryAgent.kind: NoMemoryAgent,
    KeywordAgent.kind: KeywordAgent,
}


def create_agent(spec: str) -> Agent:
    """Build an agent from ``kind`` or ``kind:name`` (name must be unique per run)."""
    kind, _, name = spec.partition(":")
    if kind not in REGISTRY:
        raise ValueError(f"unknown agent kind {kind!r}; available: {', '.join(sorted(REGISTRY))}")
    return REGISTRY[kind](name=name or None)
