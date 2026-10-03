"""Contestants that fail before they can serve a call."""

from __future__ import annotations

from typing import Any

from harness.agent import Agent, AgentEvent, AgentResponse


class RaisesInInit(Agent):
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        raise RuntimeError("cannot start")

    def on_event(self, event: AgentEvent, tools: Any) -> AgentResponse:  # pragma: no cover - never constructed
        return AgentResponse()


class NotAnAgent:
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name


class FailsInSetup(Agent):
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name)

    def setup(self, context: Any) -> None:
        raise OSError("state directory unusable")

    def on_event(self, event: AgentEvent, tools: Any) -> AgentResponse:  # pragma: no cover
        return AgentResponse()


class UnsendableDescribe(Agent):
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name)

    def describe(self) -> dict[str, Any]:
        return {"config": {"weights": {1.5, 2.5}}}  # a set cannot cross the wire

    def on_event(self, event: AgentEvent, tools: Any) -> AgentResponse:  # pragma: no cover
        return AgentResponse()


class ListDescribe(UnsendableDescribe):
    def describe(self) -> Any:
        return ["not", "a", "dict"]
