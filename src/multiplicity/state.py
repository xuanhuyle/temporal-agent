from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class Fact:
    key: str
    value: Any
    known_at: int
    source: str | None = None


@dataclass(frozen=True)
class AgentState:
    """Explicit executable state surrounding a model, not hidden model state."""

    seq: int
    knowledge: tuple[Fact, ...] = ()
    beliefs: tuple[tuple[str, Any], ...] = ()
    goals: tuple[str, ...] = ()
    commitments: tuple[str, ...] = ()
    context: tuple[tuple[str, Any], ...] = ()
    metadata: tuple[tuple[str, Any], ...] = ()

    def known_facts(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for fact in sorted(self.knowledge, key=lambda item: item.known_at):
            if fact.known_at <= self.seq:
                out[fact.key] = fact.value
        return out

    def with_seq(self, seq: int) -> "AgentState":
        return replace(self, seq=seq)

    def with_fact(
        self,
        key: str,
        value: Any,
        *,
        known_at: int | None = None,
        source: str | None = None,
    ) -> "AgentState":
        at = self.seq if known_at is None else known_at
        return replace(
            self,
            knowledge=self.knowledge
            + (Fact(key=key, value=value, known_at=at, source=source),),
        )

    def with_belief(self, key: str, value: Any) -> "AgentState":
        beliefs = dict(self.beliefs)
        beliefs[key] = value
        return replace(self, beliefs=tuple(sorted(beliefs.items())))

    def with_context(self, key: str, value: Any) -> "AgentState":
        context = dict(self.context)
        context[key] = value
        return replace(self, context=tuple(sorted(context.items())))

    def epistemic_cutoff(self, cutoff: int) -> "AgentState":
        """Physically remove knowledge acquired after the requested time."""
        return replace(
            self,
            seq=cutoff,
            knowledge=tuple(f for f in self.knowledge if f.known_at <= cutoff),
        )


@dataclass(frozen=True)
class Mutation:
    path: str
    value: Any


def apply_mutations(state: AgentState, mutations: tuple[Mutation, ...]) -> AgentState:
    out = state
    for mutation in mutations:
        if mutation.path.startswith("beliefs."):
            out = out.with_belief(
                mutation.path.removeprefix("beliefs."), mutation.value
            )
        elif mutation.path.startswith("context."):
            out = out.with_context(
                mutation.path.removeprefix("context."), mutation.value
            )
        elif mutation.path.startswith("knowledge."):
            out = out.with_fact(
                mutation.path.removeprefix("knowledge."),
                mutation.value,
                known_at=out.seq,
                source="branch-mutation",
            )
        elif mutation.path == "seq":
            out = out.with_seq(int(mutation.value))
        else:
            raise ValueError(f"Unsupported mutation path: {mutation.path}")
    return out
