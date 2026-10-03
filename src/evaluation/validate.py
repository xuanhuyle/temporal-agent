"""Scenario validation: well-formedness, wording lint, leakage canary, solvability.

A scenario is valid when:

- the manifest, event stream, and ground truth load and cross-validate
  (including derived difficulty labels, see ``evaluation.ground_truth``);
- (if frozen) content and world-only replay hashes match the manifest;
- no event pairs a reconsideration verb with a decision reference, no trigger
  names its affected target unless labelled ``wording=explicit``, and no event
  or payload uses temporal-contestant vocabulary (EXPERIMENT.md §14);
- the ground-truth canary is present in every ground-truth file and appears
  nowhere else (seed, events, manifests, docs, prompts, source);
- at least half of the events are distractors;
- no world change touches a reconsideration's remediation paths between its
  trigger and its evaluation step (world edits must not undo or perform fixes);
- the seed's own test suite stays green after every event of a world-only replay;
- the oracle reaches perfect scores (solvable; the scorer can reach 1.0) and
  the no-op dummy passes no remediation (the world alone cannot satisfy it).
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

from evaluation.checks import run_workspace_tests
from evaluation.ground_truth import CANARY_FILE, LABELS_FILE, GroundTruth, load_ground_truth
from evaluation.oracle import OracleAgent
from harness.agents.dummy import NoMemoryAgent
from harness.agents.keyword import KeywordAgent
from harness.canonical import copy_tree, iter_tree
from harness.events import Event
from harness.instructions import INSTRUCTIONS
from harness.runner import RunConfig, run
from harness.scenario import Scenario
from harness.workspace import Workspace
from harness.world import apply_event

HINT_RE = re.compile(
    r"\b(revisit|reconsider|re-?open|re-?evaluat|supersed|overturn|walk back|rethink)\w*", re.IGNORECASE
)
DECISION_REF_RE = re.compile(r"\b(?:ADR|TCK)-[0-9]+\b|\bdecision\b", re.IGNORECASE)
CONTESTANT_VOCAB_RE = re.compile(
    r"\b(tesseract|chronicle|historian|bitemporal|temporal navigation|causal edge|time travel)\b", re.IGNORECASE
)
CONCRETE_REF_RE = re.compile(r"\b(?:ADR|TCK)-[0-9]+\b|\bevt-[0-9]+\b")


class ScenarioValidationError(ValueError):
    pass


def lint_events(scenario: Scenario, events: list[Event], gt: GroundTruth) -> list[str]:
    problems = []
    by_id = {e.event_id: e for e in events}
    for ev in events:
        text = f"{ev.subject}\n{ev.body}"
        if HINT_RE.search(text) and DECISION_REF_RE.search(text):
            problems.append(f"{ev.event_id}: text pairs a reconsideration verb with a decision reference")
        if CONTESTANT_VOCAB_RE.search(text):
            problems.append(f"{ev.event_id}: text uses temporal-contestant vocabulary")
        for change in ev.world_changes:
            if change.data is not None and CONTESTANT_VOCAB_RE.search(change.data.decode("utf-8", "replace")):
                problems.append(f"{ev.event_id}: payload {change.path} uses temporal-contestant vocabulary")
    for r in gt.reconsiderations:
        if r.difficulty["wording"] == "explicit":
            continue
        ev = by_id[r.trigger_event]
        text = f"{ev.subject}\n{ev.body}".upper()
        for t in r.affected_targets:
            if t in text:
                problems.append(f"{ev.event_id}: trigger names its affected target {t} but wording is not 'explicit'")
    if CONCRETE_REF_RE.search(INSTRUCTIONS) or CONTESTANT_VOCAB_RE.search(INSTRUCTIONS):
        problems.append("harness instructions reference concrete targets/events or contestant vocabulary")
    return problems


# Ground-truth files whose format cannot carry a comment are exempt from the
# canary requirement (e.g. a reference settings.json must stay loadable).
CANARY_EXEMPT_SUFFIXES = (".json",)


def canary_problems(scenario: Scenario, gt: GroundTruth) -> list[str]:
    problems = []
    needle = gt.canary.encode("utf-8")
    for rel, full in iter_tree(scenario.ground_truth_dir):
        exempt = rel != LABELS_FILE and rel.endswith(CANARY_EXEMPT_SUFFIXES)
        if not exempt and needle not in full.read_bytes():
            problems.append(f"ground-truth file without canary: {rel}")
    if not (scenario.ground_truth_dir / CANARY_FILE).is_file():
        problems.append(f"ground truth lacks a {CANARY_FILE} file")
    gt_root = scenario.ground_truth_dir.resolve()
    for rel, full in iter_tree(scenario.base_dir):
        top = rel.split("/", 1)[0]
        if top in (".git", "runs") or full.resolve() == gt_root or gt_root in full.resolve().parents:
            continue
        if not full.is_symlink() and full.is_file() and needle in full.read_bytes():
            problems.append(f"canary found outside ground truth: {rel}")
    return problems


def clobber_problems(events: list[Event], gt: GroundTruth) -> list[str]:
    problems = []
    for r in gt.reconsiderations:
        if r.remediation is None:
            continue
        paths = {op["path"] for op in r.remediation.reference}
        paths |= {c["path"] for alt in r.remediation.acceptable for c in alt.checks if "path" in c}
        for ev in events:
            if r.trigger_seq <= ev.seq <= r.remediation.evaluate_at_seq:
                touched = {c.path for c in ev.world_changes} & paths
                if touched and ev.event_id != r.trigger_event:
                    problems.append(f"{ev.event_id} touches {sorted(touched)} inside {r.id}'s remediation window")
    return problems


def world_suite_problems(scenario: Scenario, events: list[Event]) -> list[str]:
    """The seed test suite must pass on the pristine world after every event."""
    problems = []
    with tempfile.TemporaryDirectory(prefix="tab-world-suite-") as tmp:
        root = Path(tmp) / "world"
        copy_tree(scenario.seed_dir, root)
        ws = Workspace(root)
        result = run_workspace_tests(root)
        if not result["passed"]:
            problems.append(f"seed test suite fails before any event: {result['detail']}")
        for ev in events:
            apply_event(ev, ws)
            result = run_workspace_tests(root)
            if not result["passed"]:
                problems.append(f"seed test suite fails after {ev.event_id}: {result['detail']}")
    return problems


def _value(scores: dict[str, Any], key: str) -> Any:
    return scores[key]["value"]


def validate_scenario(scenario: Scenario, *, run_agents: bool = True, world_suite: bool = True) -> dict[str, Any]:
    """Validate ``scenario``; raises :class:`ScenarioValidationError` listing every problem."""
    problems: list[str] = []
    scenario.verify(allow_draft=True)
    if scenario.status == "frozen":
        scenario.verify_world_states()
    events = scenario.load_events()
    gt = load_ground_truth(
        scenario.ground_truth_dir, {e.event_id: e.seq for e in events}, {e.event_id: e.timestamp for e in events}
    )
    if gt.scenario_id != scenario.scenario_id:
        problems.append("ground truth scenario_id does not match the manifest")
    problems += lint_events(scenario, events, gt)
    problems += canary_problems(scenario, gt)
    problems += clobber_problems(events, gt)
    n_distractors = sum(1 for lab in gt.events.values() if lab.role == "distractor")
    if n_distractors * 2 < len(events):
        problems.append(f"only {n_distractors}/{len(events)} events are distractors (EXPERIMENT.md requires >= 50%)")
    if world_suite:
        problems += world_suite_problems(scenario, events)

    report: dict[str, Any] = {
        "scenario_id": scenario.scenario_id,
        "status": scenario.status,
        "n_events": len(events),
        "n_distractors": n_distractors,
        "reconsiderations": [r.id for r in gt.reconsiderations],
    }
    if run_agents:
        with tempfile.TemporaryDirectory(prefix="tab-validate-") as tmp:
            result = run(
                scenario,
                [OracleAgent(gt), NoMemoryAgent(name="dummy"), KeywordAgent(name="keyword")],
                RunConfig(runs_dir=Path(tmp), allow_draft=True, hygiene=False),
            )
            agents = result.scores["agents"]
        oracle, dummy = agents["oracle"], agents["dummy"]
        expectations = {
            "oracle recall == 1": _value(oracle, "temporal_governance_recall") == 1.0,
            "oracle precision == 1": _value(oracle, "reopening_precision") == 1.0,
            "oracle false intervention == 0": _value(oracle, "false_intervention_rate") == 0.0,
            "oracle remediation == 1": _value(oracle, "present_remediation_success") in (1.0, None),
            "oracle fidelity == 1": oracle["historical_state_fidelity"]["value"] == 1.0,
            "dummy remediation == 0": _value(dummy, "present_remediation_success") in (0.0, None),
            "dummy recall == 0": _value(dummy, "temporal_governance_recall") == 0.0,
            "oracle and dummy completed every step": all(
                set(a["step_status"]) == {"ok"} for a in (oracle, dummy)
            ),
        }
        problems += [f"solvability check failed: {k}" for k, ok in expectations.items() if not ok]
        report["solvability"] = expectations
        report["agents"] = {
            name: {
                k: s[k]["value"]
                for k in (
                    "temporal_governance_recall",
                    "reopening_precision",
                    "false_intervention_rate",
                    "present_remediation_success",
                    "historical_state_fidelity",
                )
            }
            for name, s in agents.items()
        }
        report["remediation"] = {
            name: {r["id"]: r["remediation"]["passed"] if r["remediation"] else None for r in s["per_reconsideration"]}
            for name, s in agents.items()
        }
    report["problems"] = problems
    if problems:
        raise ScenarioValidationError("; ".join(problems))
    return report
