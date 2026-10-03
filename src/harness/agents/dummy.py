"""The dummy/no-memory agent: receives every event and does nothing."""

from __future__ import annotations

from harness.agent import Agent, AgentEvent, AgentResponse
from harness.tools import ToolBox


class NoMemoryAgent(Agent):
    kind = "dummy"
    role = "reference"

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:
        return AgentResponse()
