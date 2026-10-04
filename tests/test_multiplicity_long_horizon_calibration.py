"""Calibration generator: pressure levels are reachable and every episode passes the static validator."""

from __future__ import annotations

from multiplicity_experiments import long_horizon_calibration as cal


def test_pressure_levels_validate_and_hit_targets():
    for n, lo, hi in ((27, 0.72, 0.80), (57, 1.48, 1.60), (95, 2.45, 2.58), (153, 3.95, 4.08)):
        for seed in range(5):
            ep = cal.make_episode(f"T{n}", seed, n)  # validate(): schedule, entities, wording, probes, no leakage
            assert lo <= ep["R"] <= hi and cal.simulate_compactions(ep) == cal.COMPACTION_STAGES
            assert len(ep["scored"]) == cal.N_SCORED and len(ep["dev_probes"]) == 2 * cal.N_SCORED


def _fake_traj(ep):
    msgs = [{"id": m["id"], "text": m["text"]} for s in ep["stages"] for m in s["messages"]]
    final = {"id": "c12c", "stage": 12, "kind": "post_compaction", "memory": {"rules": []}, "context": []}
    wrong = {"decisions": [{"request_id": t["id"], "currency": "XXX", "approvers": [], "carrier": "none",
                            "notify": [], "hold": True} for t in ep["dev_probes"]]}
    return {"episode": ep["id"], "checkpoints": [{"id": "c1", "stage": 1, "kind": "stage_end", "memory": {},
                                                  "context": msgs}, final],
            "log": [], "probe_runs": [{"checkpoint": "c12c", "replicate": 0, "output": wrong}]}


def test_retrieval_selection_is_round_robin_and_scored_without_leakage():
    rows = [{"episode": "X", "units": [{"rule": f"R{i}", "regression": i != 2} for i in range(1, 6)]},
            {"episode": "Y", "units": [{"rule": "R9", "regression": True}]}]
    assert cal.select_failures(rows, 3) == [("X", "R1"), ("Y", "R9"), ("X", "R3")]
    ep = cal.make_episode("Z", 3, 57)
    rid = ep["scored"][0]
    script = cal.retrieval_script([(ep, _fake_traj(ep), rid)], "t")
    assert '"scored"' not in script and '"truth"' not in script and '"rule":' not in script
    probes = [t for t in ep["dev_probes"] if t["rule"] == rid]
    right = {"decisions": [{"request_id": t["id"], **cal.lh.truth(ep, t, 12)} for t in probes]}
    rule = next(r for r in ep["rules"] if r["id"] == rid)
    rule_msg = next(m["id"] for s in ep["stages"] for m in s["messages"] if cal.canonical_entity(rule) in m["text"])
    out = cal.retrieval_analyse({"Z": ep}, [{"unit": f"Z:{rid}", "retrieved": [rule_msg], "output": right}])
    assert out[0]["repaired"] and out[0]["top1_is_rule_message"] and out[0]["accuracy_after_retrieval"] == 1.0
    bad = cal.retrieval_analyse({"Z": ep}, [{"unit": f"Z:{rid}", "retrieved": [], "output": None}])
    assert not bad[0]["repaired"] and not bad[0]["top1_is_rule_message"]
