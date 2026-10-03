"""No-memory keyword agent: a surface-matching shortcut detector.

It reopens every decision/work-item id (``ADR-NNNN``, ``TCK-NNNN``) mentioned in
the current event's subject or body. It has no memory and never reads the
workspace, so a high score means the scenario leaks its answers lexically.
"""

from __future__ import annotations

import re

from harness.agent import Agent, AgentEvent, AgentResponse, ReopenAction, canonical_target
from harness.tools import ToolBox

_REF_RE = re.compile(r"\b(?:ADR|TCK)-[0-9]{1,6}\b", re.IGNORECASE)


class KeywordAgent(Agent):
    kind = "keyword"
    role = "reference"

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:
        refs: list[str] = []
        for m in _REF_RE.finditer(f"{event.subject}\n{event.body}"):
            ref = canonical_target(m.group(0))
            if ref is not None and ref not in refs:
                refs.append(ref)
        actions = [
            ReopenAction(target=ref, rationale="mentioned in the current event", evidence=(event.event_id,))
            for ref in refs
        ]
        return AgentResponse(actions=actions)
