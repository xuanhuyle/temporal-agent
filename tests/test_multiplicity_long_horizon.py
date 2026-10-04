"""tmk-long-horizon: generator invariants (probe time-invariance, capacity guard, disjoint entities) and no leakage."""

from __future__ import annotations

import json

from multiplicity_experiments import long_horizon as lh

LEAK_KEYS = ('"rule"', '"clause"', '"qual"', '"eff_stage"', '"params"', '"style"', '"reinforced"', '"kind"')


def test_invariance_and_capacity_hold_across_seeds():
    for seed in range(200):
        ep = lh.make_episode(f"T{seed}", seed)  # asserts invariance, clause sensitivity and capacity internally
        assert ep["lossless_ratio"] <= 0.5


def test_rule_entities_are_disjoint_and_qualifiers_are_two_born_two_amended():
    ep = lh.make_episode("T", 101)
    probe = [r for r in ep["rules"] if r.get("probe")]
    ents = [json.dumps(r["params"], sort_keys=True) for r in probe]
    assert len(ents) == len(set(ents)) == 10
    modes = sorted(r["qual"]["mode"] for r in probe if r.get("qual"))
    assert modes == ["amended", "amended", "born", "born"]


def test_subject_scripts_carry_no_ground_truth_tags():
    ep = lh.make_episode("T", 102)
    script = lh.trajectory_script(ep, 2)
    view = json.dumps(lh.subject_view(ep))
    for k in LEAK_KEYS:
        assert k not in view and k not in script.split("const DATA = ", 1)[1].split("\n", 1)[0]


def test_qual_probes_are_sensitive_to_their_clause():
    ep = lh.make_episode("T", 103)
    quals = [t for t in ep["dev_probes"] + ep["heldout"] if t["clause"] == "qual"]
    assert quals and all(lh.truth(ep, t, lh.N_STAGES) != lh.truth(ep, t, lh.N_STAGES, drop_qual=True) for t in quals)


def test_analysis_path_runs_on_a_fake_trajectory():
    ep = lh.make_episode("T", 101)
    unit = lh.units_of(ep)[0]
    good = {"decisions": [dict(lh.truth(ep, t, lh.N_STAGES), request_id=t["id"]) for t in ep["dev_probes"]]}
    bad = {"decisions": [dict(lh.truth(ep, t, 0), request_id=t["id"]) for t in ep["dev_probes"]]}
    mem = {"rules": ["x"], "commitments": [], "open_items": [], "notes": []}
    cps = [{"id": f"c{s}", "stage": s, "kind": "stage_end", "memory": mem, "context": [{"id": f"M-{s}", "text": "m"}]}
           for s in (10, 20)]
    traj = {"episode": "T", "checkpoints": cps, "log": [], "probe_runs": [
        {"checkpoint": "c10", "replicate": 0, "output": good}, {"checkpoint": "c20", "replicate": 0, "output": bad}]}
    hr = lh.headroom(ep, traj)
    assert any(r["headroom"] == 1.0 for r in hr["rules"]) and lh.candidates(hr)
    assert lh.confirm_script(ep, traj, hr)
    cases = lh.make_cases(ep, traj, [unit])
    assert {c["cond"] for c in cases} == {"A", "B", "C"} and lh.investigation_script(cases, "t")
    assert all(not c["checkpoints"] for c in cases if c["cond"] == "A")
