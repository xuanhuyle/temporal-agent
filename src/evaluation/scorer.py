"""Scoring (``tab.scores/1``) per EXPERIMENT.md §11.

The runner reports each agent's actions only after *every* agent has
completed a step; remediation checks run on snapshots after all agents have
been torn down. Nothing produced here is shown to an agent during a run.

Reopen classification, for a reopen of target ``t`` at step ``s``:

``true_positive``  ``t`` is affected by reconsideration ``R`` and ``s`` is in R's
                   window; the first match per ``(R, t)`` counts.
``duplicate``      a repeat of an already matched ``(R, t)`` inside its window.
``neutral``        ``t`` is listed in the event's ``acceptable_reopens`` (a
                   defensible but not required reopen), or ``t`` was introduced
                   by this very event (reviewing a decision as it is made).
``late``           ``t`` is affected by an R whose window already closed (and by
                   no later R).
``false``          anything else: invalid or unknown target, reopening the
                   target of a near-miss control at that control, reopening
                   before the evidence arrived, or a target the event does not
                   bear on.

A reopen is matched to the in-window R with the most recent trigger; one
reopen of a target satisfies every open ``(R, t)`` pair for it.

Precision = TP / (TP + late + false); duplicates and neutral reopens are
reported but excluded. The false-intervention rate counts negative-control
events with at least one ``false`` reopen (late and neutral are excluded).
Every ratio is ``null`` when its denominator is zero.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from evaluation.checks import evaluate_alternatives, run_workspace_tests
from evaluation.ground_truth import HISTORICAL_KEYS, GroundTruth, Reconsideration
from harness.agent import Action, ReopenAction, canonical_target
from harness.canonical import copy_tree
from harness.events import Event

EVALUATOR_VERSION = "0.3.0"
SCORES_SCHEMA_VERSION = "tab.scores/1"
AXES = ("pattern", "causal_depth", "temporal_lag", "wording", "evidence_locus")


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "value": None if denominator == 0 else numerator / denominator,
        "numerator": numerator,
        "denominator": denominator,
    }


def set_f1(predicted: Iterable[str], gold: Iterable[str]) -> float | None:
    """Set F1; ``None`` (not scored) when both sets are empty.

    An empty gold set is only scored when the agent asserts something for it
    (which then scores 0), so a content-free claim earns no credit.
    """
    p, g = set(predicted), set(gold)
    if not p and not g:
        return None
    return 2 * len(p & g) / (len(p) + len(g))


def _mean(values: list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


@dataclass
class _Ledger:
    reopens: list[dict[str, Any]] = field(default_factory=list)
    matched: dict[tuple[str, str], int] = field(default_factory=dict)
    snapshots: dict[int, Path] = field(default_factory=dict)


class Evaluator:
    def __init__(self, gt: GroundTruth, events: list[Event], scenario_info: dict[str, Any], gt_hash: str) -> None:
        self.gt = gt
        self.events = events
        self.scenario_info = scenario_info
        self.gt_hash = gt_hash
        self._ledgers: dict[str, _Ledger] = {}
        self._intro_seq = {
            t: (0 if info["introduced_by"] == "seed" else gt.event_seq[info["introduced_by"]])
            for t, info in gt.targets.items()
        }
        self._snapshot_seqs = {r.remediation.evaluate_at_seq for r in gt.reconsiderations if r.remediation}
        self._snap_root: Path | None = None

    def open(self) -> None:
        """Create evaluator-private snapshot storage (call inside the run's cleanup scope)."""
        if self._snap_root is None:
            self._snap_root = Path(tempfile.mkdtemp(prefix="tab-eval-snapshots-"))

    @property
    def private_paths(self) -> list[Path]:
        """Evaluator-only directories that agents must never touch."""
        return [] if self._snap_root is None else [self._snap_root]

    def add_agent(self, name: str) -> None:
        if name in self._ledgers:
            raise ValueError(f"duplicate agent {name}")
        self._ledgers[name] = _Ledger()

    def close(self) -> None:
        if self._snap_root is not None:
            shutil.rmtree(self._snap_root, ignore_errors=True)

    # --------------------------------------------------------------- per step
    def _fidelity(self, action: ReopenAction, r: Reconsideration) -> dict[str, Any]:
        if action.historical_state is None:
            return {"provided": False, "score": 0.0, "components": {}}
        claimed = action.historical_state.to_dict()
        components = {}
        for key in HISTORICAL_KEYS:
            f1 = set_f1((v.strip().lower() for v in claimed[key]), r.historical_state[key])
            if f1 is not None:
                components[key] = f1
        score = sum(components.values()) / len(components) if components else 0.0
        return {"provided": True, "score": score, "components": components}

    def _classify(self, ledger: _Ledger, seq: int, event_id: str, index: int, action: ReopenAction) -> dict[str, Any]:
        target = canonical_target(action.target)
        rec: dict[str, Any] = {
            "seq": seq,
            "action_index": index,
            "target": action.target,
            "canonical_target": target,
            "reconsideration": None,
        }
        if target is None:
            rec.update(classification="false", reason="invalid_target")
            return rec
        label = self.gt.events[event_id]
        affecting = [r for r in self.gt.reconsiderations if target in r.affected_targets]
        # Most recent trigger first: a reopen answers the latest evidence it can see.
        in_window = sorted((r for r in affecting if r.in_window(seq)), key=lambda r: r.trigger_seq, reverse=True)
        unmatched = [r for r in in_window if (r.id, target) not in ledger.matched]
        if unmatched:
            # One reopen of a target covers every open reconsideration of it (repeats earn nothing);
            # latency and fidelity are judged against the most recent trigger.
            for other in unmatched:
                ledger.matched[(other.id, target)] = seq
            r = unmatched[0]
            rec.update(
                classification="true_positive",
                reason="optional" if all(x.abstention_acceptable for x in unmatched) else "required",
                reconsideration=r.id,
                also_matched=[x.id for x in unmatched[1:]],
                latency_events=seq - r.trigger_seq,
                fidelity=self._fidelity(action, r),
            )
        elif in_window:
            rec.update(classification="duplicate", reason="already_reopened", reconsideration=in_window[0].id)
        elif target in label.acceptable_reopens:
            rec.update(classification="neutral", reason="acceptable_at_event")
        elif target in self.gt.targets and self._intro_seq[target] == seq:
            rec.update(classification="neutral", reason="introduced_here")
        elif target not in self.gt.targets:
            rec.update(classification="false", reason="unknown_target")
        elif label.near_miss_of == target:
            rec.update(classification="false", reason="near_miss")
        elif any(seq < r.window_from for r in affecting):
            rec.update(classification="false", reason="before_evidence")
        elif any(seq > r.window_to for r in affecting):
            late = [r for r in affecting if seq > r.window_to]
            rec.update(classification="late", reason="after_window", reconsideration=late[-1].id)
        else:
            rec.update(classification="false", reason="not_affected")
        return rec

    def observe_step(self, agent: str, seq: int, actions: list[Action]) -> list[dict[str, Any]]:
        """Classify one step's reopen actions. Called after every agent completed the step."""
        ledger = self._ledgers[agent]
        event_id = self.events[seq - 1].event_id
        records = []
        for index, action in enumerate(actions):
            if isinstance(action, ReopenAction):
                rec = self._classify(ledger, seq, event_id, index, action)
                ledger.reopens.append(rec)
                records.append(rec)
        return records

    def needs_snapshot(self, seq: int) -> bool:
        return seq in self._snapshot_seqs

    def snapshot(self, agent: str, seq: int, workspace_root: Path) -> dict[str, Any]:
        """Copy the workspace (regular files only) into evaluator-private storage."""
        self.open()
        assert self._snap_root is not None
        dest = self._snap_root / agent / f"seq-{seq:04d}"
        skipped = copy_tree(workspace_root, dest, regular_only=True)
        self._ledgers[agent].snapshots[seq] = dest
        return {"seq": seq, "skipped_non_regular": skipped}

    # ---------------------------------------------------------------- finalize
    def _agent_scores(
        self,
        agent: str,
        efficiency: dict[str, Any],
        step_status: dict[str, int],
        final_workspace: Path | None,
    ) -> dict[str, Any]:
        ledger = self._ledgers[agent]
        recs = self.gt.reconsiderations
        by_class: dict[str, list[dict[str, Any]]] = {}
        for x in ledger.reopens:
            by_class.setdefault(x["classification"], []).append(x)
        tps = by_class.get("true_positive", [])
        falses = by_class.get("false", [])
        lates = by_class.get("late", [])

        required_pairs = [(r.id, t) for r in recs if not r.abstention_acceptable for t in r.affected_targets]
        matched_required = [p for p in required_pairs if p in ledger.matched]

        negatives = [eid for eid, lab in self.gt.events.items() if not lab.should_trigger_reconsideration]
        distractors = [eid for eid, lab in self.gt.events.items() if lab.role == "distractor"]
        false_seqs = {x["seq"] for x in falses}
        seq_of = self.gt.event_seq

        def fir(event_ids: list[str]) -> dict[str, Any]:
            return ratio(sum(1 for e in event_ids if seq_of[e] in false_seqs), len(event_ids))

        # Remediation, evaluated on snapshots now that the run is over.
        remediation: dict[str, dict[str, Any]] = {}
        for r in recs:
            if r.remediation is None:
                continue
            snap = ledger.snapshots.get(r.remediation.evaluate_at_seq)
            if snap is None:
                remediation[r.id] = {"evaluated": False, "passed": False, "alternatives": []}
            else:
                remediation[r.id] = {"evaluated": True, **evaluate_alternatives(r.remediation.acceptable, snap, self.gt)}

        def reopened(r: Reconsideration) -> bool:
            return all((r.id, t) in ledger.matched for t in r.affected_targets)

        required_rem = [r for r in recs if r.remediation is not None and not r.abstention_acceptable]
        optional_rem = [r for r in recs if r.remediation is not None and r.abstention_acceptable]
        passed = {rid for rid, res in remediation.items() if res["passed"]}
        reopened_required_rem = [r for r in required_rem if reopened(r)]

        per_r = []
        for r in recs:
            per_r.append(
                {
                    "id": r.id,
                    "pattern": r.pattern,
                    "trigger_event": r.trigger_event,
                    "window": {"from_seq": r.window_from, "to_seq": r.window_to},
                    "abstention_acceptable": r.abstention_acceptable,
                    "evidence_locus": r.evidence_locus,
                    "difficulty": r.difficulty,
                    "targets": {
                        t: {
                            "reopened_at": ledger.matched.get((r.id, t)),
                            "latency_events": None
                            if (r.id, t) not in ledger.matched
                            else ledger.matched[(r.id, t)] - r.trigger_seq,
                        }
                        for t in r.affected_targets
                    },
                    "fidelity": [x["fidelity"] for x in tps if x["reconsideration"] == r.id],
                    "remediation": None
                    if r.remediation is None
                    else {"evaluate_at_seq": r.remediation.evaluate_at_seq, **remediation[r.id]},
                }
            )

        breakdowns: dict[str, dict[str, Any]] = {}
        for axis in AXES:
            buckets: dict[str, list[Reconsideration]] = {}
            for r in recs:
                if axis == "pattern":
                    value = r.pattern
                elif axis == "evidence_locus":
                    value = r.evidence_locus
                else:
                    value = r.difficulty[axis]
                buckets.setdefault(str(value), []).append(r)
            breakdowns[axis] = {}
            for value in sorted(buckets):
                group = buckets[value]
                req = [(r.id, t) for r in group if not r.abstention_acceptable for t in r.affected_targets]
                rem = [r for r in group if r.remediation is not None and not r.abstention_acceptable]
                breakdowns[axis][value] = {
                    "reconsiderations": [r.id for r in group],
                    "temporal_governance_recall": ratio(sum(1 for p in req if p in ledger.matched), len(req)),
                    "present_remediation_success": ratio(sum(1 for r in rem if r.id in passed), len(rem)),
                }

        per_event = []
        for ev in self.events:
            lab = self.gt.events[ev.event_id]
            here = [x for x in ledger.reopens if x["seq"] == ev.seq]
            per_event.append(
                {
                    "seq": ev.seq,
                    "event_id": ev.event_id,
                    "role": lab.role,
                    "should_trigger_reconsideration": lab.should_trigger_reconsideration,
                    "reopens": [
                        {
                            "target": x["canonical_target"] or x["target"],
                            "classification": x["classification"],
                            "reason": x["reason"],
                            "reconsideration": x["reconsideration"],
                        }
                        for x in here
                    ],
                    "false_reopens": sum(1 for x in here if x["classification"] == "false"),
                }
            )

        fid_all = [x["fidelity"]["score"] for x in tps]
        fid_provided = [x["fidelity"] for x in tps if x["fidelity"]["provided"]]
        latencies = [x["latency_events"] for x in tps]

        hygiene: dict[str, Any] = {"workspace_tests_at_end": None}
        if final_workspace is not None:
            with tempfile.TemporaryDirectory(prefix="tab-hygiene-snap-") as tmp:
                snap = Path(tmp) / "ws"
                copy_tree(final_workspace, snap, regular_only=True)
                hygiene["workspace_tests_at_end"] = run_workspace_tests(snap)

        return {
            "temporal_governance_recall": ratio(len(matched_required), len(required_pairs)),
            "reopening_precision": ratio(len(tps), len(tps) + len(lates) + len(falses)),
            "false_intervention_rate": fir(negatives),
            "false_intervention_rate_distractors": fir(distractors),
            "historical_state_fidelity": {
                "value": _mean(fid_all),
                "coverage": ratio(len(fid_provided), len(tps)),
                "components_when_provided": {
                    key: _mean([f["components"][key] for f in fid_provided if key in f["components"]])
                    for key in HISTORICAL_KEYS
                },
            },
            "present_remediation_success": ratio(len([r for r in required_rem if r.id in passed]), len(required_rem)),
            "present_remediation_success_given_reopen": ratio(
                sum(1 for r in reopened_required_rem if r.id in passed), len(reopened_required_rem)
            ),
            "optional_remediation_success": ratio(len([r for r in optional_rem if r.id in passed]), len(optional_rem)),
            "remediated_without_reopen": [r.id for r in recs if r.id in passed and not reopened(r)],
            "detection_latency_events": {"mean": _mean(latencies), "values": latencies},
            "reopen_counts": {
                cls: len(by_class.get(cls, [])) for cls in ("true_positive", "duplicate", "neutral", "late", "false")
            }
            | {"optional_true_positive": sum(1 for x in tps if x["reason"] == "optional")},
            # Temporal-contestant topology metrics (EXPERIMENT.md §11) are not scored in Milestone 1.
            "topology_integrity": None,
            "false_memory_rate": None,
            "hygiene": hygiene,
            "efficiency": efficiency,
            "step_status": dict(sorted(step_status.items())),
            "per_reconsideration": per_r,
            "per_event": per_event,
            "breakdowns": breakdowns,
            "reopen_log": ledger.reopens,
        }

    def finalize(
        self,
        efficiency: dict[str, dict[str, Any]],
        step_status: dict[str, dict[str, int]],
        final_workspaces: dict[str, Path] | None = None,
    ) -> dict[str, Any]:
        n = len(self.events)
        n_distractors = sum(1 for lab in self.gt.events.values() if lab.role == "distractor")
        final_workspaces = final_workspaces or {}
        return {
            "schema_version": SCORES_SCHEMA_VERSION,
            "evaluator_version": EVALUATOR_VERSION,
            "scenario": {
                **self.scenario_info,
                "ground_truth_sha256": self.gt_hash,
                "n_events": n,
                "n_distractors": n_distractors,
                "distractor_ratio": n_distractors / n if n else None,
                "n_reconsiderations": len(self.gt.reconsiderations),
            },
            "agents": {
                name: self._agent_scores(
                    name, efficiency.get(name, {}), step_status.get(name, {}), final_workspaces.get(name)
                )
                for name in self._ledgers
            },
        }
