from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from typing import Any, Protocol

from .state import AgentState, Mutation, apply_mutations


StateID = str
BranchID = str


class BranchRunner(Protocol):
    def __call__(self, state: AgentState, task: str, budget: int) -> "RunResult": ...


@dataclass(frozen=True)
class Snapshot:
    state_id: StateID
    state: AgentState


@dataclass(frozen=True)
class Branch:
    branch_id: BranchID
    parent_state_id: StateID
    root_state_id: StateID
    state: AgentState
    epistemic_cutoff: int | None = None
    mutations: tuple[Mutation, ...] = ()
    status: str = "ready"


@dataclass(frozen=True)
class RunResult:
    answer: Any
    state: AgentState
    trace: tuple[str, ...] = ()
    cost: dict[str, Any] | None = None


@dataclass(frozen=True)
class BranchRun:
    branch_id: BranchID
    before_state_id: StateID
    after_state_id: StateID
    task: str
    result: RunResult


@dataclass(frozen=True)
class Comparison:
    branch_ids: tuple[BranchID, ...]
    answers: dict[BranchID, Any]
    knowledge_only: dict[BranchID, dict[str, Any]]
    belief_only: dict[BranchID, dict[str, Any]]
    goal_only: dict[BranchID, tuple[str, ...]]
    commitment_only: dict[BranchID, tuple[str, ...]]


class TemporalMultiplicityKernel:
    """Minimal executable-state branching over explicit agent state."""

    def __init__(self) -> None:
        self._snapshots: dict[StateID, AgentState] = {}
        self._branches: dict[BranchID, Branch] = {}
        self._runs: dict[BranchID, BranchRun] = {}
        self._counter = 0

    @staticmethod
    def _canonical_state(state: AgentState) -> str:
        return json.dumps(
            asdict(state), sort_keys=True, separators=(",", ":"), default=str
        )

    @classmethod
    def _state_id(cls, state: AgentState) -> StateID:
        digest = hashlib.sha256(
            cls._canonical_state(state).encode("utf-8")
        ).hexdigest()
        return f"state:{digest[:20]}"

    def snapshot(self, state: AgentState) -> Snapshot:
        state_id = self._state_id(state)
        self._snapshots[state_id] = state
        return Snapshot(state_id=state_id, state=state)

    def get_state(self, state_id: StateID) -> AgentState:
        return self._snapshots[state_id]

    def fork(
        self,
        state_id: StateID,
        *,
        epistemic_cutoff: int | None = None,
        mutations: tuple[Mutation, ...] = (),
    ) -> Branch:
        parent = self.get_state(state_id)
        state = parent
        if epistemic_cutoff is not None:
            if epistemic_cutoff > parent.seq:
                raise ValueError("epistemic_cutoff cannot be later than parent state")
            state = state.epistemic_cutoff(epistemic_cutoff)
        state = apply_mutations(state, mutations)

        root_snapshot = self.snapshot(state)
        self._counter += 1
        branch_id = f"branch:{self._counter:04d}"
        branch = Branch(
            branch_id=branch_id,
            parent_state_id=state_id,
            root_state_id=root_snapshot.state_id,
            state=state,
            epistemic_cutoff=epistemic_cutoff,
            mutations=mutations,
        )
        self._branches[branch_id] = branch
        return branch

    def get_branch(self, branch_id: BranchID) -> Branch:
        return self._branches[branch_id]

    def run(
        self,
        branch_id: BranchID,
        *,
        task: str,
        runner: BranchRunner,
        budget: int = 1,
    ) -> BranchRun:
        if budget <= 0:
            raise ValueError("budget must be positive")
        branch = self.get_branch(branch_id)
        before = self.snapshot(branch.state)
        result = runner(branch.state, task, budget)
        after = self.snapshot(result.state)
        self._branches[branch_id] = replace(
            branch, state=result.state, status="ran"
        )
        run = BranchRun(
            branch_id=branch_id,
            before_state_id=before.state_id,
            after_state_id=after.state_id,
            task=task,
            result=result,
        )
        self._runs[branch_id] = run
        return run

    def compare(self, *branch_ids: BranchID) -> Comparison:
        if len(branch_ids) < 2:
            raise ValueError("compare requires at least two branches")

        states = {bid: self.get_branch(bid).state for bid in branch_ids}
        runs = {bid: self._runs.get(bid) for bid in branch_ids}
        knowledge_maps = {
            bid: state.known_facts() for bid, state in states.items()
        }
        belief_maps = {bid: dict(state.beliefs) for bid, state in states.items()}

        def common_keys(maps: dict[str, dict[str, Any]]) -> set[str]:
            if not maps:
                return set()
            candidates = set.intersection(*(set(values) for values in maps.values()))
            return {
                key
                for key in candidates
                if len(
                    {
                        json.dumps(values[key], sort_keys=True, default=str)
                        for values in maps.values()
                    }
                )
                == 1
            }

        common_knowledge = common_keys(knowledge_maps)
        common_beliefs = common_keys(belief_maps)

        return Comparison(
            branch_ids=tuple(branch_ids),
            answers={
                bid: runs[bid].result.answer if runs[bid] is not None else None
                for bid in branch_ids
            },
            knowledge_only={
                bid: {
                    key: value
                    for key, value in values.items()
                    if key not in common_knowledge
                }
                for bid, values in knowledge_maps.items()
            },
            belief_only={
                bid: {
                    key: value
                    for key, value in values.items()
                    if key not in common_beliefs
                }
                for bid, values in belief_maps.items()
            },
            goal_only={bid: state.goals for bid, state in states.items()},
            commitment_only={
                bid: state.commitments for bid, state in states.items()
            },
        )
