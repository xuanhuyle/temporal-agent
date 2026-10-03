from dataclasses import replace
from pathlib import Path

from multiplicity import (
    AgentState,
    RunResult,
    TemporalMultiplicity,
)


class BackendA:
    def reason(self, state, task, budget):
        facts = state.known_facts()
        answer = facts.get(task)
        return RunResult(
            answer=answer,
            state=replace(state, seq=state.seq + 1),
            trace=("backend-a",),
        )


class BackendB:
    def reason(self, state, task, budget):
        facts = state.known_facts()
        answer = facts.get(task)
        return RunResult(
            answer=answer,
            state=replace(state, seq=state.seq + 1),
            trace=("backend-b",),
        )


def _state():
    state = AgentState(seq=1)
    state = state.with_fact("known_then", "A", known_at=1)
    state = state.with_seq(3)
    state = state.with_fact("known_later", "B", known_at=3)
    return state


def test_same_capability_semantics_with_two_different_reasoning_backends():
    outputs = []
    branch_facts = []

    for backend in (BackendA(), BackendB()):
        capability = TemporalMultiplicity(backend)
        state_id = capability.snapshot(_state())
        past = capability.fork(state_id, epistemic_cutoff=1)

        run = capability.run(past, "known_then")
        outputs.append(run.result.answer)
        branch_facts.append(capability.branch_state(past).known_facts())

    assert outputs == ["A", "A"]
    assert branch_facts == [
        {"known_then": "A"},
        {"known_then": "A"},
    ]


def test_backend_cannot_recover_fact_removed_by_epistemic_fork():
    class CuriousBackend:
        def reason(self, state, task, budget):
            return RunResult(
                answer=state.known_facts().get("known_later"),
                state=state,
                trace=("looked-for-later-fact",),
            )

    capability = TemporalMultiplicity(CuriousBackend())
    state_id = capability.snapshot(_state())
    past = capability.fork(state_id, epistemic_cutoff=1)

    result = capability.run(past, "try-to-cheat")

    assert result.result.answer is None


def test_core_package_has_no_model_vendor_or_benchmark_harness_imports():
    root = Path(__file__).parents[1] / "src" / "multiplicity"
    forbidden = (
        "from harness",
        "import harness",
        "anthropic",
        "openai",
        "langgraph",
        "google.generativeai",
    )

    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text, f"{path.name} depends on {token!r}"
