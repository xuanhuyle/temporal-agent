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
