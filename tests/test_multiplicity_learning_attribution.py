"""tmk-learning: world arithmetic, subject isolation (no ground truth in prompts), and regret scoring."""

from __future__ import annotations

import pytest

from multiplicity_experiments import learning_attribution as la

DATA = la.load()
LIB = DATA["modules"]
V2 = [e for e in DATA["episodes"] if e.get("design") == "v2"]


def _fake_evals(ep: dict, acc: dict[str, float]) -> dict:
    cell = lambda a: {"acc": a, "runs": [a, a, a], "families": {"plain": "3/3"}}  # noqa: E731
    dev = {f"S{k}": cell(0.5) for k in range(4)} | {f"S3-{m}": cell(0.5) for m in ep["learned"]}
    held = {k: cell(v) for k, v in acc.items()}
    return {ep["id"]: {"dev": dev, "heldout": held}}


def test_true_price_matches_the_worked_examples_module():
    def t(w, z):
        return {"weight": w, "zone": z, "fragile": False, "express": False}

    assert [la.true_price(t(3.0, "B")), la.true_price(t(7.0, "A")), la.true_price(t(1.0, "C"))] == [25, 20, 25]
    assert la.true_price({"weight": 12.2, "zone": "B", "fragile": True, "express": True}) == 120  # (18+9)*2*2+9


def test_task_suites_are_deterministic_and_dev_differs_from_heldout():
    ep = V2[0]
    assert la.tasks_for(ep, "dev") == la.tasks_for(ep, "dev")
    assert la.tasks_for(ep, "dev") != la.tasks_for(ep, "heldout")
    assert len(la.tasks_for(ep, "heldout")) == la.N_TASKS


def test_forked_states_carry_exactly_the_intended_modules():
    ep = V2[0]
    states = la.states_for(ep, LIB)
    x, c = ep["learned"][0], ep["candidates"][0]
    assert set(la.modules_of(states["S3"])) == set(ep["initial"] + ep["learned"])
    assert set(la.modules_of(states["S0"])) == set(ep["initial"])
    assert set(la.modules_of(states[f"S3-{x}+{c}"])) == set(ep["initial"] + ep["learned"]) - {x} | {c}
    prompt = la.exec_prompt(states[f"S3-{x}"], LIB, la.tasks_for(ep, "dev"))
    assert LIB[x]["text"] not in prompt


@pytest.mark.parametrize("ep", V2, ids=lambda e: e["id"])
def test_decision_prompts_never_contain_ground_truth(ep):
    evals = _fake_evals(ep, {})
    jobs = la.plan_decisions(DATA, evals, [ep["id"]])
    for job in jobs:
        p = job["prompt"]
        assert ep["note"] not in p and "heldout" not in p.lower() and "held-out" not in p.lower()
        for c in ep["candidates"]:  # candidates are known by title only
            if c not in ep["initial"] + ep["learned"]:
                assert LIB[c]["text"] not in p
        assert not any(la.describe(t) in p for t in la.tasks_for(ep, "heldout"))
    multi, base = (j["prompt"] for j in jobs)
    assert "CONTROLLED SELF-EXPERIMENTS" in multi and "CONTROLLED SELF-EXPERIMENTS" not in base
    assert multi.split("CONTROLLED SELF-EXPERIMENTS")[0] == base.split("You cannot run any further")[0]


def test_v2_regret_is_against_the_best_learn_forget_pair():
    ep = V2[0]
    s3 = 0.5
    acc = {"S3": s3} | {f"S3-{m}": 0.4 for m in ep["learned"]}
    acc |= {f"S3-{x}+{c}": 0.5 for x in ep["learned"] for c in ep["candidates"]}
    best_c, best_x = ep["candidates"][1], ep["learned"][2]
    acc[f"S3-{best_x}+{best_c}"] = 0.9
    evals = _fake_evals(ep, acc)
    decisions = [{"episode": ep["id"], "condition": "multiplicity",
                  "output": {"choice": best_c, "forget": best_x, "attribution": {}}},
                 {"episode": ep["id"], "condition": "baseline",
                  "output": {"choice": ep["candidates"][0], "forget": best_x, "attribution": {}}}]
    rows = {r["condition"]: r for r in la.score_decisions(DATA, evals, decisions)["rows"]}
    assert rows["multiplicity"]["regret"] == pytest.approx(0) and rows["multiplicity"]["chose_best"]
    assert rows["baseline"]["regret"] == pytest.approx(0.4) and not rows["baseline"]["chose_best"]
    assert rows["baseline"]["attribution_truth"] == {m: "no_effect" for m in ep["learned"]}


def test_resolve_key_maps_sentences_to_exactly_one_named_key():
    keys = ["EXPR", "HEAVY", "MEMO"]
    assert la.resolve_key("EXPR", keys) == "EXPR"
    assert la.resolve_key("Learn EXPR and forget EXAMPLES.", keys) == "EXPR"
    assert la.resolve_key("EXPR or HEAVY", keys) is None  # ambiguous: never guessed
    assert la.resolve_key("nothing", keys) is None
    assert la.resolve_key("MEMO_R", ["MEMO", "BASE"]) is None  # no partial-token matches
    assert la.resolve_key("forget MEMO_R", ["MEMO_R", "BASE"]) == "MEMO_R"
