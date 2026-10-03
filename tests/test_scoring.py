"""Scoring semantics (EXPERIMENT.md §11) on a synthetic ground truth."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.ground_truth import GroundTruthError, load_ground_truth
from evaluation.scorer import Evaluator, set_f1
from harness.agent import HistoricalState, NoteAction, ReopenAction
from harness.events import Event

N = 6
ROLES = {1: "distractor", 2: "trigger", 3: "distractor", 4: "decision_setup", 5: "trigger", 6: "distractor"}


def _events():
    return [
        Event("tab.event/1", f"evt-{i:04d}", i, f"2026-01-0{i}T00:00:00Z", "ticket", "a", "s", "b", ())
        for i in range(1, N + 1)
    ]


def _labels(**override):
    labels = {
        "schema_version": "tab.ground_truth/1",
        "scenario_id": "synthetic",
        "canary": "TAB-GT-CANARY-synthetic-123456",
        "targets": {
            "ADR-0001": {"kind": "decision", "introduced_by": "seed", "decided_on": "2025-12-01", "summary": ""},
            "ADR-0002": {"kind": "decision", "introduced_by": "seed", "decided_on": "2025-12-01", "summary": ""},
            "ADR-0003": {"kind": "decision", "introduced_by": "evt-0004", "decided_on": "2026-01-04", "summary": ""},
            "TCK-0005": {"kind": "work_item", "introduced_by": "evt-0001", "decided_on": "2026-01-01", "summary": ""},
        },
        "events": {
            f"evt-{i:04d}": {
                "role": role,
                "should_trigger_reconsideration": role == "trigger",
                "near_miss_of": None,
                "acceptable_reopens": ["ADR-0003"] if i == 6 else [],
                "notes": "",
            }
            for i, role in ROLES.items()
        },
        "reconsiderations": [
            {
                "id": "R1",
                "pattern": "A",
                "trigger_event": "evt-0002",
                "affected_targets": ["ADR-0001", "ADR-0002"],
                "window": {"from_seq": 2, "to_seq": 4},
                "abstention_acceptable": False,
                "evidence_locus": "workspace",
                "causal_path": [{"ref": "evt-0002", "kind": "event", "note": ""}, {"ref": "ADR-0001", "kind": "decision", "note": ""}],
                "historical_state": {"known_then": ["seed"], "true_then": [], "known_now_about_then": ["evt-0002"]},
                "remediation": {
                    "evaluate_at_seq": 4,
                    "acceptable": [
                        {"id": "flag", "checks": [{"type": "json_value", "path": "c.json", "pointer": "/on", "op": "eq", "value": True}]},
                        {"id": "file", "checks": [{"type": "file_exists", "path": "MIGRATED"}]},
                    ],
                    "reference": [],
                },
                "difficulty": {"causal_depth": 1, "temporal_lag": "near", "lag_events": 2, "lag_days": 32, "wording": "indirect"},
            },
            {
                "id": "R2",
                "pattern": "F",
                "trigger_event": "evt-0005",
                "affected_targets": ["TCK-0005"],
                "window": {"from_seq": 5, "to_seq": 6},
                "abstention_acceptable": True,
                "evidence_locus": "event_history",
                "causal_path": [{"ref": "evt-0005", "kind": "event", "note": ""}, {"ref": "TCK-0005", "kind": "work_item", "note": ""}],
                "historical_state": {"known_then": ["evt-0001"], "true_then": [], "known_now_about_then": ["evt-0005"]},
                "remediation": None,
                "difficulty": {"causal_depth": 1, "temporal_lag": "medium", "lag_events": 4, "lag_days": 4, "wording": "natural"},
            },
        ],
    }
    labels.update(override)
    return labels


def _gt(tmp_path: Path, labels=None):
    d = tmp_path / "gt"
    d.mkdir(exist_ok=True)
    (d / "labels.json").write_text(json.dumps(labels or _labels()))
    return load_ground_truth(d, {f"evt-{i:04d}": i for i in range(1, N + 1)})


def _score(tmp_path, steps: dict[int, list], workspace_files: dict[str, str] | None = None):
    gt = _gt(tmp_path)
    ev = Evaluator(gt, _events(), {"scenario_id": "synthetic"}, "h")
    ev.add_agent("a")
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    for rel, text in (workspace_files or {}).items():
        (ws / rel).write_text(text)
    for seq in range(1, N + 1):
        ev.observe_step("a", seq, steps.get(seq, []))
        if ev.needs_snapshot(seq):
            ev.snapshot("a", seq, ws)
    try:
        return ev.finalize({"a": {}}, {"a": {"ok": N}})["agents"]["a"]
    finally:
        ev.close()


def test_no_reopens_gives_zero_recall_and_null_precision(tmp_path):
    s = _score(tmp_path, {})
    assert s["temporal_governance_recall"] == {"value": 0.0, "numerator": 0, "denominator": 2}
    assert s["reopening_precision"] == {"value": None, "numerator": 0, "denominator": 0}
    assert s["false_intervention_rate"]["value"] == 0.0
    assert s["false_intervention_rate"]["denominator"] == 4  # events 1,3,4,6
    assert s["historical_state_fidelity"]["value"] is None
    assert s["present_remediation_success"] == {"value": 0.0, "numerator": 0, "denominator": 1}


def test_classification_rules(tmp_path):
    s = _score(
        tmp_path,
        {
            1: [ReopenAction("ADR-0001")],                 # before evidence -> false (distractor event)
            2: [ReopenAction("adr-1"), NoteAction("hi")],  # canonicalized, true positive
            3: [ReopenAction("ADR-0001"),                  # duplicate
                ReopenAction("ADR-0003")],                 # not affected -> false at distractor
            4: [ReopenAction("ADR-0002")],                 # true positive (late but in window)
            5: [ReopenAction("ADR-0002"),                  # after window -> late (not a false intervention)
                ReopenAction("not a ref")],                # invalid -> false
            6: [ReopenAction("TCK-0005"), ReopenAction("ZZZ-0009")],  # optional TP; unknown target false
        },
    )
    log = [(r["seq"], r["canonical_target"], r["classification"], r["reason"]) for r in s["reopen_log"]]
    assert log == [
        (1, "ADR-0001", "false", "before_evidence"),
        (2, "ADR-0001", "true_positive", "required"),
        (3, "ADR-0001", "duplicate", "already_reopened"),
        (3, "ADR-0003", "false", "not_affected"),
        (4, "ADR-0002", "true_positive", "required"),
        (5, "ADR-0002", "late", "after_window"),
        (5, None, "false", "invalid_target"),
        (6, "TCK-0005", "true_positive", "optional"),
        (6, "ZZZ-0009", "false", "unknown_target"),
    ]
    assert s["temporal_governance_recall"]["value"] == 1.0  # optional R2 not in denominator
    assert s["reopening_precision"] == {"value": 3 / 8, "numerator": 3, "denominator": 8}
    # false reopens at negative-control events 1, 3, 6 (4 is clean; 5 is a trigger)
    assert s["false_intervention_rate"] == {"value": 3 / 4, "numerator": 3, "denominator": 4}
    assert s["false_intervention_rate_distractors"] == {"value": 1.0, "numerator": 3, "denominator": 3}
    assert s["reopen_counts"] == {"true_positive": 3, "duplicate": 1, "neutral": 0, "late": 1, "false": 4,
                                  "optional_true_positive": 1}
    r1 = s["per_reconsideration"][0]
    assert r1["targets"] == {"ADR-0001": {"reopened_at": 2, "latency_events": 0},
                             "ADR-0002": {"reopened_at": 4, "latency_events": 2}}
    assert [e["false_reopens"] for e in s["per_event"]] == [1, 0, 1, 0, 1, 1]
    assert s["detection_latency_events"] == {"mean": 1.0, "values": [0, 2, 1]}


def test_neutral_reopens_are_excluded_from_precision_and_fir(tmp_path):
    s = _score(tmp_path, {
        4: [ReopenAction("ADR-0003")],  # introduced by this very event -> neutral review
        6: [ReopenAction("ADR-0003")],  # listed in evt-0006 acceptable_reopens -> neutral
        3: [ReopenAction("ADR-0003")],  # neither -> false
    })
    assert [(r["seq"], r["classification"], r["reason"]) for r in s["reopen_log"]] == [
        (3, "false", "not_affected"), (4, "neutral", "introduced_here"), (6, "neutral", "acceptable_at_event")]
    assert s["reopening_precision"] == {"value": 0.0, "numerator": 0, "denominator": 1}
    assert s["false_intervention_rate"]["numerator"] == 1


def test_abstention_acceptable_is_not_penalized(tmp_path):
    s = _score(tmp_path, {2: [ReopenAction("ADR-0001"), ReopenAction("ADR-0002")]})
    assert s["temporal_governance_recall"]["value"] == 1.0
    assert s["reopening_precision"]["value"] == 1.0


def test_fidelity_is_mean_set_f1_over_asserted_or_labelled_components(tmp_path):
    perfect = HistoricalState(known_then=("seed",), known_now_about_then=("evt-0002",))
    partial = HistoricalState(known_then=("seed", "evt-0001"))
    s = _score(tmp_path, {2: [ReopenAction("ADR-0001", historical_state=perfect),
                              ReopenAction("ADR-0002", historical_state=partial)]})
    fid = s["historical_state_fidelity"]
    # true_then is empty in both claim and label: not scored (no free credit).
    # perfect: (1 + 1) / 2 = 1.0; partial: known_then 2/3, known_now_about_then 0 -> 1/3
    assert fid["value"] == pytest.approx((1.0 + 1 / 3) / 2)
    assert fid["coverage"] == {"value": 1.0, "numerator": 2, "denominator": 2}
    assert fid["components_when_provided"]["known_now_about_then"] == pytest.approx(0.5)
    assert fid["components_when_provided"]["true_then"] is None
    assert set_f1([], []) is None and set_f1(["a"], []) == 0.0


def test_content_free_claims_earn_no_fidelity(tmp_path):
    s = _score(tmp_path, {2: [ReopenAction("ADR-0001", historical_state=HistoricalState())]})
    assert s["historical_state_fidelity"]["value"] == 0.0
    wrong_true_then = HistoricalState(known_then=("seed",), true_then=("evt-0002",), known_now_about_then=("evt-0002",))
    (tmp_path / "b").mkdir()
    s = _score(tmp_path / "b", {2: [ReopenAction("ADR-0001", historical_state=wrong_true_then)]})
    # asserting a retroactive fact the label does not have costs a zero component
    assert s["historical_state_fidelity"]["value"] == pytest.approx(2 / 3)


def test_missing_historical_state_scores_zero(tmp_path):
    claim = HistoricalState(known_then=("seed",), known_now_about_then=("evt-0002",))
    s = _score(tmp_path, {2: [ReopenAction("ADR-0001"), ReopenAction("ADR-0002", historical_state=claim)]})
    assert s["historical_state_fidelity"]["value"] == pytest.approx(0.5)
    assert s["historical_state_fidelity"]["coverage"] == {"value": 0.5, "numerator": 1, "denominator": 2}


@pytest.mark.parametrize(
    "files,passed,alt",
    [
        ({}, False, None),
        ({"c.json": '{"on": false}'}, False, None),
        ({"c.json": '{"on": true}'}, True, "flag"),
        ({"MIGRATED": "yes"}, True, "file"),
        ({"c.json": "not json"}, False, None),
    ],
)
def test_remediation_any_alternative_passes(tmp_path, files, passed, alt):
    s = _score(tmp_path, {2: [ReopenAction("ADR-0001"), ReopenAction("ADR-0002")]}, files)
    rem = s["per_reconsideration"][0]["remediation"]
    assert rem["evaluated"] and rem["passed"] is passed
    if alt:
        assert next(a for a in rem["alternatives"] if a["passed"])["id"] == alt
    assert s["present_remediation_success"]["value"] == (1.0 if passed else 0.0)
    assert s["present_remediation_success_given_reopen"]["denominator"] == 1


def test_remediation_without_reopen_is_reported(tmp_path):
    s = _score(tmp_path, {}, {"MIGRATED": "yes"})
    assert s["present_remediation_success"]["value"] == 1.0
    assert s["remediated_without_reopen"] == ["R1"]
    assert s["present_remediation_success_given_reopen"]["value"] is None


def test_breakdowns_by_axis(tmp_path):
    s = _score(tmp_path, {2: [ReopenAction("ADR-0001")]})
    b = s["breakdowns"]
    assert set(b) == {"pattern", "causal_depth", "temporal_lag", "wording", "evidence_locus"}
    assert b["evidence_locus"]["event_history"]["reconsiderations"] == ["R2"]
    assert b["pattern"]["A"]["temporal_governance_recall"] == {"value": 0.5, "numerator": 1, "denominator": 2}
    assert b["pattern"]["F"]["temporal_governance_recall"]["denominator"] == 0
    assert b["temporal_lag"]["near"]["reconsiderations"] == ["R1"]
    assert b["temporal_lag"]["medium"]["reconsiderations"] == ["R2"]


@pytest.mark.parametrize(
    "mutate,msg",
    [
        (lambda d: d["events"].pop("evt-0003"), "exactly the events"),
        (lambda d: d["events"]["evt-0002"].update(role="distractor"), "role=trigger"),
        (lambda d: d["events"]["evt-0003"].update(should_trigger_reconsideration=True), "exactly for role=trigger"),
        (lambda d: d["reconsiderations"][0].update(window={"from_seq": 1, "to_seq": 4}), "window"),
        (lambda d: d["reconsiderations"][0].update(affected_targets=["ADR-0009"]), "registry"),
        (lambda d: d["reconsiderations"][0]["historical_state"].update(known_then=["evt-0003"]), "postdates"),
        (lambda d: d["reconsiderations"][0]["historical_state"].update(known_now_about_then=[]), "must not be empty"),
        (lambda d: d["reconsiderations"][0].update(evidence_locus="somewhere"), "evidence_locus"),
        (lambda d: d["events"]["evt-0001"].update(acceptable_reopens=["ADR-0042"]), "acceptable_reopens"),
        (lambda d: d["reconsiderations"][0].update(pattern="Z"), "pattern"),
        (lambda d: d["reconsiderations"][0]["remediation"]["acceptable"][0]["checks"][0].update(type="shell"), "unknown check"),
        (lambda d: d["reconsiderations"][0]["remediation"]["acceptable"][0]["checks"][0].update(path="../x"), "bad path"),
        (lambda d: d["targets"].update({"adr-7": {"kind": "decision", "introduced_by": "seed", "decided_on": "2025-12-01", "summary": ""}}), "canonical"),
        (lambda d: d.update(canary="short"), "canary"),
        (lambda d: d.update(extra=1), "keys mismatch"),
    ],
)
def test_ground_truth_validation(tmp_path, mutate, msg):
    labels = _labels()
    mutate(labels)
    with pytest.raises(GroundTruthError, match=msg):
        _gt(tmp_path, labels)


def test_lag_days_checked_against_event_dates(tmp_path):
    d = tmp_path / "gt"
    d.mkdir()
    (d / "labels.json").write_text(json.dumps(_labels()))
    seqs = {f"evt-{i:04d}": i for i in range(1, N + 1)}
    dates = {f"evt-{i:04d}": f"2026-01-0{i}T00:00:00Z" for i in range(1, N + 1)}
    load_ground_truth(d, seqs, dates)  # R1: 2026-01-02 - 2025-12-01 = 32 days
    labels = _labels()
    labels["reconsiderations"][0]["difficulty"]["lag_days"] = 31
    (d / "labels.json").write_text(json.dumps(labels))
    with pytest.raises(GroundTruthError, match="lag_days must be 32"):
        load_ground_truth(d, seqs, dates)


def test_hidden_test_reference_must_stay_inside_ground_truth(tmp_path):
    labels = _labels()
    labels["reconsiderations"][0]["remediation"]["acceptable"][0]["checks"] = [
        {"type": "hidden_pytest", "files": ["../outside/test_x.py"]}
    ]
    with pytest.raises(GroundTruthError):
        _gt(tmp_path, labels)


def _score_labels(tmp_path, labels, steps):
    d = tmp_path / "custom_gt"
    d.mkdir(parents=True)
    (d / "labels.json").write_text(json.dumps(labels))
    gt = load_ground_truth(d, {f"evt-{i:04d}": i for i in range(1, N + 1)})
    ev = Evaluator(gt, _events(), {"scenario_id": "synthetic"}, "h")
    ev.add_agent("a")
    ws = tmp_path / "ws_custom"
    ws.mkdir()
    for seq in range(1, N + 1):
        ev.observe_step("a", seq, steps.get(seq, []))
        if ev.needs_snapshot(seq):
            ev.snapshot("a", seq, ws)
    try:
        return ev.finalize({"a": {}}, {"a": {"ok": N}})["agents"]["a"]
    finally:
        ev.close()


def _extra_r(rid, trigger, target, window):
    return {
        "id": rid, "pattern": "B", "trigger_event": trigger, "affected_targets": [target],
        "window": {"from_seq": window[0], "to_seq": window[1]}, "abstention_acceptable": False,
        "evidence_locus": "workspace",
        "causal_path": [{"ref": trigger, "kind": "event", "note": ""}, {"ref": target, "kind": "decision", "note": ""}],
        "historical_state": {"known_then": ["seed"], "true_then": [], "known_now_about_then": [trigger]},
        "remediation": None,
        "difficulty": {"causal_depth": 1, "temporal_lag": "medium" if int(trigger[-1]) > 2 else "near",
                       "lag_events": int(trigger[-1]), "lag_days": 0, "wording": "natural"},
    }


def test_near_miss_reopen_is_a_false_intervention(tmp_path):
    labels = _labels()
    labels["events"]["evt-0001"]["near_miss_of"] = "ADR-0001"
    s = _score_labels(tmp_path, labels, {1: [ReopenAction("ADR-0001")]})
    assert [(r["classification"], r["reason"]) for r in s["reopen_log"]] == [("false", "near_miss")]
    assert s["false_intervention_rate"]["numerator"] == 1


def test_near_miss_inside_a_same_target_window_is_rejected(tmp_path):
    labels = _labels()
    labels["events"]["evt-0003"]["near_miss_of"] = "ADR-0001"  # inside R1's window [2, 4]
    d = tmp_path / "gt"
    d.mkdir()
    (d / "labels.json").write_text(json.dumps(labels))
    with pytest.raises(GroundTruthError, match="near-miss"):
        load_ground_truth(d, {f"evt-{i:04d}": i for i in range(1, N + 1)})


def test_reopen_between_two_windows_is_premature_not_late(tmp_path):
    labels = _labels()
    labels["reconsiderations"][0]["window"] = {"from_seq": 2, "to_seq": 3}
    labels["reconsiderations"][0]["remediation"]["evaluate_at_seq"] = 3
    labels["reconsiderations"].append(_extra_r("R9", "evt-0005", "ADR-0001", (5, 6)))
    s = _score_labels(tmp_path, labels, {4: [ReopenAction("ADR-0001")]})
    assert [(r["classification"], r["reason"]) for r in s["reopen_log"]] == [("false", "before_evidence")]


def test_shared_target_matches_latest_trigger_and_repeats_earn_nothing(tmp_path):
    labels = _labels()
    labels["events"]["evt-0003"].update(role="trigger", should_trigger_reconsideration=True)
    labels["reconsiderations"].append(_extra_r("R9", "evt-0003", "ADR-0001", (3, 5)))
    order_a = _score_labels(tmp_path / "a", labels, {3: [ReopenAction("ADR-0001"), ReopenAction("ADR-0001")]})
    labels["reconsiderations"].reverse()
    order_b = _score_labels(tmp_path / "b", labels, {3: [ReopenAction("ADR-0001"), ReopenAction("ADR-0001")]})
    for s in (order_a, order_b):  # independent of ground-truth list order
        first, second = s["reopen_log"]
        assert first["classification"] == "true_positive" and first["reconsideration"] == "R9"
        assert first["also_matched"] == ["R1"] and first["latency_events"] == 0
        assert second["classification"] == "duplicate"
        assert s["temporal_governance_recall"]["numerator"] == 2  # R1/ADR-0001 and R9/ADR-0001
        assert s["reopening_precision"] == {"value": 1.0, "numerator": 1, "denominator": 1}


def _score_with_edits(tmp_path, steps, edits):
    """Like _score, but applies workspace edits right before the agent step at ``seq``.

    R2 gets its own remediation evaluated at seq 6, so the workspace is
    snapshotted at two different steps (4 for R1, 6 for R2).
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    labels = _labels()
    labels["reconsiderations"][1]["remediation"] = {
        "evaluate_at_seq": 6,
        "acceptable": [{"id": "r2", "checks": [{"type": "file_exists", "path": "R2DONE"}]}],
        "reference": [],
    }
    gt = _gt(tmp_path, labels)
    ev = Evaluator(gt, _events(), {"scenario_id": "synthetic"}, "h")
    ev.add_agent("a")
    ws = tmp_path / "ws"
    ws.mkdir()
    for seq in range(1, N + 1):
        for rel, text in edits.get(seq, {}).items():
            if text is None:
                (ws / rel).unlink()
            else:
                (ws / rel).write_text(text)
        ev.observe_step("a", seq, steps.get(seq, []))
        if ev.needs_snapshot(seq):
            ev.snapshot("a", seq, ws)
    try:
        return ev.finalize({"a": {}}, {"a": {"ok": N}})["agents"]["a"]
    finally:
        ev.close()


def test_remediation_is_judged_at_evaluate_at_seq(tmp_path):
    fixed = '{"on": true}'
    # R1 evaluates at seq 4: a fix that only lands at seq 5 is too late ...
    late = _score_with_edits(tmp_path / "late", {}, {5: {"c.json": fixed}})
    assert late["per_reconsideration"][0]["remediation"]["passed"] is False  # even though seq 6 has it
    # ... and a fix present at seq 4 counts even if it is reverted afterwards.
    reverted = _score_with_edits(tmp_path / "rev", {}, {4: {"c.json": fixed}, 5: {"c.json": None}})
    assert reverted["per_reconsideration"][0]["remediation"]["passed"] is True


def test_late_reopen_at_a_distractor_is_not_a_false_intervention(tmp_path):
    s = _score(tmp_path, {6: [ReopenAction("ADR-0001")]})  # R1's window [2, 4] closed; evt-0006 is a distractor
    assert [(r["classification"], r["reason"]) for r in s["reopen_log"]] == [("late", "after_window")]
    assert s["false_intervention_rate"]["numerator"] == 0
    assert s["reopening_precision"] == {"value": 0.0, "numerator": 0, "denominator": 1}


@pytest.mark.parametrize(
    "mutate,msg",
    [
        (lambda d: d["reconsiderations"][0]["difficulty"].update(lag_events=1), "lag_events"),  # same bucket
        (lambda d: d["reconsiderations"][0]["difficulty"].update(temporal_lag="far"), "temporal_lag must be 'near'"),
        (lambda d: d["reconsiderations"][0]["difficulty"].update(causal_depth=3), "causal_depth"),
        (lambda d: d["reconsiderations"][0]["causal_path"].reverse(), "start at the trigger"),
        (lambda d: d["targets"]["ADR-0001"].update(decided_on="last year"), "decided_on"),
        (lambda d: d["reconsiderations"][0]["historical_state"].update(known_now_about_then=["seed"]), "known_now_about_then"),
        (lambda d: d["reconsiderations"][0]["historical_state"].update(known_now_about_then=["evt-0003"]), "known_now_about_then"),
        (lambda d: d["reconsiderations"][0]["historical_state"].update(true_then=["evt-0005"]), "true_then"),
        (lambda d: d["reconsiderations"][0]["remediation"].update(evaluate_at_seq=1), "evaluate_at_seq"),
        (lambda d: d["events"]["evt-0006"].update(role="trigger", should_trigger_reconsideration=True), "no reconsideration uses it"),
        (lambda d: d["reconsiderations"][0]["causal_path"].insert(1, {"ref": "x", "kind": "assumption", "note": ""}), "causal_depth"),
    ],
)
def test_ground_truth_cross_validation_rules(tmp_path, mutate, msg):
    labels = _labels()
    mutate(labels)
    with pytest.raises(GroundTruthError, match=msg):
        _gt(tmp_path, labels)
