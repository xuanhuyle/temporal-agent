from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .kernel import (
    Branch,
    BranchID,
    BranchRun,
    Comparison,
    RunResult,
    TemporalMultiplicityKernel,
)
from .state import AgentState, Mutation


class CognitiveBackend(Protocol):
    """Any reasoning engine capable of operating on explicit agent state.

    This is intentionally independent of model vendor, SDK and transport.
    A backend may wrap an LLM, a local model, a symbolic reasoner, a human,
    or a composite agent runtime.
    """

    def reason(self, state: AgentState, task: str, budget: int) -> RunResult: ...


@dataclass(frozen=True)
class BranchHandle:
    branch_id: BranchID


class TemporalMultiplicity:
    """Product-facing model-agnostic cognitive capability.

    The capability owns branching semantics; the injected backend owns reasoning.
    Swapping the backend must not change snapshot/fork/compare semantics.
    """

    def __init__(
        self,
        backend: CognitiveBackend,
        *,
        kernel: TemporalMultiplicityKernel | None = None,
    ) -> None:
        self.backend = backend
        self.kernel = kernel or TemporalMultiplicityKernel()

    def snapshot(self, state: AgentState) -> str:
        return self.kernel.snapshot(state).state_id

    def fork(
        self,
        state_id: str,
        *,
        epistemic_cutoff: int | None = None,
        mutations: tuple[Mutation, ...] = (),
    ) -> BranchHandle:
        branch = self.kernel.fork(
            state_id,
            epistemic_cutoff=epistemic_cutoff,
            mutations=mutations,
        )
        return BranchHandle(branch.branch_id)

    def run(
        self,
        branch: BranchHandle | str,
        task: str,
        *,
        budget: int = 1,
    ) -> BranchRun:
        branch_id = branch.branch_id if isinstance(branch, BranchHandle) else branch
        return self.kernel.run(
            branch_id,
            task=task,
            runner=self.backend.reason,
            budget=budget,
        )

    def compare(self, *branches: BranchHandle | str) -> Comparison:
        branch_ids = tuple(
            branch.branch_id if isinstance(branch, BranchHandle) else branch
            for branch in branches
        )
        return self.kernel.compare(*branch_ids)

    def branch_state(self, branch: BranchHandle | str) -> AgentState:
        branch_id = branch.branch_id if isinstance(branch, BranchHandle) else branch
        return self.kernel.get_branch(branch_id).state


class CallableBackend:
    """Adapter for any Python callable matching the reasoning contract."""

    def __init__(self, fn):
        self.fn = fn

    def reason(self, state: AgentState, task: str, budget: int) -> RunResult:
        return self.fn(state, task, budget)


__all__ = [
    "BranchHandle",
    "CallableBackend",
    "CognitiveBackend",
    "TemporalMultiplicity",
]
