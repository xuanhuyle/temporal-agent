"""Harness-side registry of model-backed contestants.

Contestants run in their own process (``harness.process.ProcessAgent``,
protocol amendment A4). The harness knows only how to start them: an entry
point, a configuration, and the source packages that make up the contestant's
code bundle. The configuration's meaning belongs to the contestant, which
reports its effective configuration through ``describe()``.

Every preset here gets the same model, tools and budgets; they differ only in
contestant configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.agent import Agent

RUNTIME_PACKAGES = ("contestant_runtime",)


@dataclass(frozen=True)
class ContestantSpec:
    kind: str
    entry: str
    config: dict[str, Any] = field(default_factory=dict)
    packages: tuple[str, ...] = ()
    description: str = ""


_BASELINE = ("baseline.agent:BaselineAgent", RUNTIME_PACKAGES + ("baseline",))

CONTESTANTS: dict[str, ContestantSpec] = {
    "baseline-k8": ContestantSpec("baseline", _BASELINE[0], {"preset": "k8"}, _BASELINE[1],
                                  "conventional baseline: hybrid RAG, top-8"),
    "baseline-k32": ContestantSpec("baseline", _BASELINE[0], {"preset": "k32"}, _BASELINE[1],
                                   "conventional baseline: hybrid RAG, top-32"),
    "baseline-k64": ContestantSpec("baseline", _BASELINE[0], {"preset": "k64"}, _BASELINE[1],
                                   "conventional baseline: hybrid RAG, top-64"),
    "baseline-full": ContestantSpec("baseline", _BASELINE[0], {"preset": "full"}, _BASELINE[1],
                                    "conventional baseline: long-context replay of every event and note"),
}

# The configurations run on the smoke scenario as a machinery check (Milestone 2).
BASELINE_SMOKE_SET = ("baseline-k8", "baseline-k32", "baseline-k64", "baseline-full")


def create_contestant(kind: str, name: str | None = None) -> Agent:
    from harness.process import ProcessAgent  # imported lazily: only needed when a contestant is requested

    spec = CONTESTANTS[kind]
    return ProcessAgent(
        name or kind,
        kind=spec.kind,
        entry=spec.entry,
        config=dict(spec.config),
        packages=spec.packages,
    )
