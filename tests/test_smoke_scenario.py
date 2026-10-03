"""The frozen 10-event smoke scenario meets the milestone requirements and is solvable."""

from __future__ import annotations

import json
import re

import pytest

from conftest import REPO_ROOT, SMOKE_MANIFEST
from evaluation.checks import run_workspace_tests
from evaluation.ground_truth import load_ground_truth
from evaluation.oracle import OracleAgent
from evaluation.validate import canary_problems, clobber_problems, lint_events, validate_scenario
from harness.agents import create_agent
from harness.canonical import copy_tree
from harness.replay import replay_run
from harness.runner import OUTPUT_FILES, RunConfig, run
from harness.scenario import load_scenario
from harness.trace import read_jsonl


@pytest.fixture(scope="module")
def smoke():
    scenario = load_scenario(SMOKE_MANIFEST)
    events = scenario.load_events()
    gt = load_ground_truth(
        scenario.ground_truth_dir, {e.event_id: e.seq for e in events}, {e.event_id: e.timestamp for e in events}
    )
    return scenario, events, gt


@pytest.fixture(scope="module")
def reference_run(smoke, tmp_path_factory):
    scenario, _, gt = smoke
    runs = tmp_path_factory.mktemp("smoke_runs")
    agents = [OracleAgent(gt), create_agent("dummy"), create_agent("keyword")]
    return run(scenario, agents, RunConfig(runs_dir=runs))


def test_smoke_is_frozen_and_intact(smoke):
    scenario, events, _ = smoke
    assert scenario.status == "frozen" and scenario.data["held_out"] is False
    scenario.verify()
    scenario.verify_world_states()
    assert len(events) == 10


def test_smoke_meets_prompt_requirements(smoke):
    _, events, gt = smoke
    roles = [gt.events[e.event_id].role for e in events]
    assert roles.count("distractor") >= 5
    assert roles.count("distractor") * 2 >= len(events)  # EXPERIMENT.md: >= 50% irrelevant
    decision_recs = [r for r in gt.reconsiderations if all(gt.targets[t]["kind"] == "decision" for t in r.affected_targets)]
    assert len(decision_recs) >= 2  # >= 2 causal events reconsidering an earlier decision
    delayed = [r for r in gt.reconsiderations if r.pattern == "C"]
    assert delayed and all(r.difficulty["lag_days"] >= 30 for r in delayed)  # delayed observation
    parked = [r for r in gt.reconsiderations if r.pattern == "F"]
    assert parked
    for r in parked:  # a parked dependency that later resolves
        (target,) = r.affected_targets
        assert gt.targets[target]["kind"] == "work_item"
        assert gt.events[gt.targets[target]["introduced_by"]].role == "parked_setup"
    # no trigger is the last event, and negative controls follow the last trigger
    last_trigger = max(r.trigger_seq for r in gt.reconsiderations)
    assert sum(1 for e in events if e.seq > last_trigger and not gt.events[e.event_id].should_trigger_reconsideration) >= 2
    # uniform windows
    assert {r.window_to - r.window_from for r in gt.reconsiderations} == {2}


def test_smoke_wording_canary_and_clobber_lint(smoke):
    scenario, events, gt = smoke
    assert lint_events(scenario, events, gt) == []
    assert canary_problems(scenario, gt) == []
    assert clobber_problems(events, gt) == []
    for e in events:
        assert not re.search(r"\b(revisit|reconsider|reopen)\w*", f"{e.subject} {e.body}", re.IGNORECASE), e.event_id


def test_smoke_validates_including_world_suite(smoke):
    report = validate_scenario(smoke[0], run_agents=False, world_suite=True)
    assert report["problems"] == []


def test_seed_application_test_suite_passes(tmp_path):
    copy_tree(REPO_ROOT / "world" / "seed_repo", tmp_path / "seed")
    result = run_workspace_tests(tmp_path / "seed")
    assert result["passed"], result
    assert result["detail"]["junit"]["tests"] >= 50


def test_oracle_is_perfect_and_null_agents_score_zero(reference_run):
    agents = reference_run.scores["agents"]
    oracle, dummy, keyword = agents["oracle"], agents["dummy"], agents["keyword"]
    for key in ("temporal_governance_recall", "reopening_precision", "present_remediation_success"):
        assert oracle[key]["value"] == 1.0, key
    assert oracle["false_intervention_rate"]["value"] == 0.0
    assert oracle["historical_state_fidelity"]["value"] == 1.0
    assert oracle["hygiene"]["workspace_tests_at_end"]["passed"] is True
    assert dummy["temporal_governance_recall"]["value"] == 0.0
    assert dummy["reopening_precision"]["value"] is None
    assert dummy["present_remediation_success"]["value"] == 0.0
    assert dummy["hygiene"]["workspace_tests_at_end"]["passed"] is True
    # the ID-keyword shortcut cannot solve the smoke scenario
    assert keyword["temporal_governance_recall"]["value"] == 0.0
    assert keyword["false_intervention_rate"]["value"] > 0.0


def test_smoke_breakdowns_cover_every_axis(reference_run):
    oracle = reference_run.scores["agents"]["oracle"]
    assert set(oracle["breakdowns"]) == {"pattern", "causal_depth", "temporal_lag", "wording", "evidence_locus"}
    assert set(oracle["breakdowns"]["pattern"]) == {"A", "C", "F"}
    assert set(oracle["breakdowns"]["evidence_locus"]) == {"workspace", "event_history"}
    assert [r["id"] for r in oracle["per_reconsideration"]] == ["R1", "R2", "R3"]


def test_smoke_run_outputs_and_replay(reference_run):
    for name in OUTPUT_FILES:
        assert (reference_run.run_dir / name).is_file()
    meta = json.loads((reference_run.run_dir / "metadata.json").read_text())
    assert meta["status"] == "completed" and meta["fingerprint"]
    assert len(read_jsonl(reference_run.run_dir / "events.jsonl")) == 10
    _, report = replay_run(reference_run.run_dir)
    assert report["match"], report


def test_docs_do_not_quote_smoke_ground_truth(smoke):
    _, _, gt = smoke
    texts = [p.read_text() for d in ("docs", "prompts") for p in (REPO_ROOT / d).rglob("*.md")]
    texts += [(REPO_ROOT / f).read_text() for f in ("README.md", "EXPERIMENT.md", "CLAUDE.md")]
    for text in texts:
        assert gt.canary not in text
        for r in gt.reconsiderations:
            for t in r.affected_targets:
                for m in re.finditer(re.escape(r.trigger_event), text):
                    assert t not in text[max(0, m.start() - 200): m.end() + 200]


def _world_at(smoke, seq, dest):
    from harness.workspace import Workspace
    from harness.world import apply_event

    scenario, events, _ = smoke
    copy_tree(scenario.seed_dir, dest)
    ws = Workspace(dest)
    for ev in events[:seq]:
        apply_event(ev, ws)
    return dest


def _edit(root, rel, old, new):
    path = root / rel
    text = path.read_text()
    assert old in text, (rel, old)
    path.write_text(text.replace(old, new, 1))


R1_GRACE_7_DAYS = (
    "tasklane/billing.py",
    "    if status == \"incomplete\":",
    "    if status == \"past_due\" and now - subscription.current_period_end <= timedelta(days=7):\n"
    "        return _entitlements(subscription.plan_id, \"past_due_grace\")\n\n    if status == \"incomplete\":",
)


@pytest.mark.parametrize(
    "rid,edits,expected",
    [
        # R1: any bounded grace passes; a revert (no grace at all) or no change fails
        ("R1", [("tasklane/billing.py", '"active", "trialing", "past_due"', '"active", "trialing"'), R1_GRACE_7_DAYS], True),
        ("R1", [("tasklane/billing.py", '"active", "trialing", "past_due"', '"active", "trialing"')], False),
        ("R1", [], False),
        # R2: any provider method returning the SDK's PDF passes; a fake PDF does not
        ("R2", [("tasklane/providers/payments.py", "    @staticmethod\n    def _call(",
                 "    def download_invoice_pdf(self, invoice_id: str) -> bytes:\n"
                 "        return self._call(self._client.invoices.download_pdf, invoice_id)\n\n"
                 "    @staticmethod\n    def _call(")], True),
        ("R2", [("tasklane/providers/payments.py", "    @staticmethod\n    def _call(",
                 "    def invoice_pdf(self, invoice_id: str) -> bytes:\n"
                 "        return b'%PDF-1.4 ' + invoice_id.encode()\n\n"
                 "    @staticmethod\n    def _call(")], False),
        # R3: OWASP cost or above passes; a compromise below it does not
        ("R3", [("config/settings.json", '"pbkdf2_iterations": 120000', '"pbkdf2_iterations": 1000000')], True),
        ("R3", [("config/settings.json", '"pbkdf2_iterations": 120000', '"pbkdf2_iterations": 400000')], False),
    ],
)
def test_remediation_checks_accept_reasonable_fixes_and_reject_degenerate_ones(smoke, tmp_path, rid, edits, expected):
    from evaluation.checks import evaluate_alternatives

    _, _, gt = smoke
    r = next(x for x in gt.reconsiderations if x.id == rid)
    world = _world_at(smoke, r.remediation.evaluate_at_seq, tmp_path / "world")
    for rel, old, new in edits:
        _edit(world, rel, old, new)
    assert evaluate_alternatives(r.remediation.acceptable, world, gt)["passed"] is expected
