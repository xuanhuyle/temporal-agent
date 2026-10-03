from __future__ import annotations

from dataclasses import replace
from typing import Any

from .kernel import RunResult
from .state import AgentState


class FactReasoner:
    """Deterministic runner used only to verify kernel state semantics."""

    def __call__(self, state: AgentState, task: str, budget: int) -> RunResult:
        facts = state.known_facts()
        trace: list[str] = [f"seq={state.seq}", f"task={task}"]

        if task.startswith("read:"):
            key = task.removeprefix("read:")
            answer: Any = facts.get(key)
            trace.append(f"read {key} -> {answer!r}")
        elif task == "diagnose-machine":
            if facts.get("inspection_result") == "bearing_failure":
                answer = "bearing_failure"
            elif (
                facts.get("vibration") == "high"
                and facts.get("temperature") == "normal"
            ):
                answer = "misalignment"
            else:
                answer = "insufficient_evidence"
            trace.append(f"diagnosis={answer}")
        else:
            raise ValueError(f"Unsupported task: {task}")

        new_state = replace(state, seq=state.seq + min(budget, 1))
        return RunResult(answer=answer, state=new_state, trace=tuple(trace))


class ScriptedRunner:
    def __init__(self, fn):
        self.fn = fn

    def __call__(self, state: AgentState, task: str, budget: int) -> RunResult:
        return self.fn(state, task, budget)
