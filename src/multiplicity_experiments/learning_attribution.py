"""tmk-learning v1: can executable earlier/ablated selves improve an agent's choice of what to learn next?

Deliberately small. One fictional skill (Orbital Post parcel pricing, scored exactly here), knowledge modules
as text, and episodes S0 -> +A -> +B -> +C = S3. A state's capability is *measured by running the model* with
only that state's modules on a task suite, so module effects (help, redundancy, interference, interaction)
are real model behaviour, not stipulated numbers.

Conditions (same model, same history, same module contents, same candidate list):
- multiplicity: also sees evaluations of forks of S3 with one learned module removed
  (TemporalMultiplicity.fork with a ``forget.`` mutation), i.e. controlled self-ablation;
- baseline: spends the matching extra calls on two independent self-reflections plus a synthesis.
Primary outcome: held-out accuracy gain of S3 + chosen module, and regret against the best candidate.

The subject never sees true prices, held-out results or candidate evaluations.

Pipeline (model calls are made outside this module, by whatever runner is legitimate):
    plan-evals -> [run executor jobs] -> score-evals -> plan-decisions -> [run decision jobs] -> score
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any

from multiplicity import AgentState, Mutation, TemporalMultiplicity

REPO_ROOT = Path(__file__).resolve().parents[2]
EPISODES = REPO_ROOT / "experiments" / "multiplicity_learning" / "episodes.json"
N_TASKS = 16
ZONE_MULT = {"A": 1, "B": 2, "C": 3, "D": 4}
FAMILIES = ("plain", "zoned", "heavy", "fragile", "express")
CLASSES = ("essential", "helpful", "no_effect", "harmful")


# ------------------------------------------------------------------ the world
def true_price(t: dict[str, Any]) -> int:
    w = t["weight"]
    base = 7 if w <= 2 else 11 if w <= 5 else 18 if w <= 10 else 18 + 3 * math.ceil(w - 10)
    sub = base * ZONE_MULT[t["zone"]]
    if t["express"]:
        sub *= 2
    if t["fragile"]:
        sub += 9
    return int(math.ceil(sub / 5) * 5)


def _task(rng: random.Random, family: str) -> dict[str, Any]:
    w = round(rng.uniform(0.6, 9.8), 1)
    zone, fragile, express = "A", False, False
    if family == "zoned":
        zone = rng.choice("BCD")
    elif family == "heavy":
        w, zone = round(rng.uniform(10.3, 15.8), 1), rng.choice("AB")
    elif family == "fragile":
        zone, fragile = rng.choice("ABCD"), True
    elif family == "express":
        zone, express = rng.choice("ABCD"), True
    if w == int(w):
        w += 0.1
    return {"family": family, "weight": round(w, 1), "zone": zone, "fragile": fragile, "express": express}


def tasks_for(ep: dict[str, Any], split: str) -> list[dict[str, Any]]:
    rng = random.Random(f"{ep['seed']}-{split}")
    fams = []
    for fam, share in ep["families"].items():
        fams += [fam] * round(share * N_TASKS)
    fams = (fams + [next(iter(ep["families"]))] * N_TASKS)[:N_TASKS]
    rng.shuffle(fams)
    return [_task(rng, f) for f in fams]


def describe(t: dict[str, Any]) -> str:
    opts = [o for o, on in (("fragile", t["fragile"]), ("express", t["express"])) if on]
    return f"{t['weight']} kg, zone {t['zone']}" + (", " + ", ".join(opts) if opts else ", no options")


# ------------------------------------------------------------------ states via the primitive
def load(path: Path = EPISODES) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def current_state(ep: dict[str, Any], lib: dict[str, Any]) -> AgentState:
    """S3: initial modules known at 0, learned module i known at i + 1."""
    state = AgentState(seq=len(ep["learned"]))
    for key in ep["initial"]:
        state = state.with_fact(f"module:{key}", lib[key]["text"], known_at=0)
    for i, key in enumerate(ep["learned"], start=1):
        state = state.with_fact(f"module:{key}", lib[key]["text"], known_at=i)
    return state


def states_for(ep: dict[str, Any], lib: dict[str, Any]) -> dict[str, AgentState]:
    """Every state the experiment evaluates, each produced by snapshot -> fork on the current self."""
    tm = TemporalMultiplicity(backend=None)  # evaluation happens outside; only branching is used here
    root = tm.snapshot(current_state(ep, lib))
    learned = ep["learned"]
    out: dict[str, AgentState] = {}
    for k in range(len(learned) + 1):  # past selves S0..S3 by epistemic rollback
        out[f"S{k}"] = tm.branch_state(tm.fork(root, epistemic_cutoff=k))
    for key in learned:  # ablated current selves
        out[f"S3-{key}"] = tm.branch_state(tm.fork(root, mutations=(Mutation(f"forget.module:{key}", None),)))
    for key in ep["candidates"]:  # candidate future selves (evaluated on held-out only, never shown)
        out[f"S3+{key}"] = tm.branch_state(tm.fork(root, mutations=(Mutation(f"knowledge.module:{key}", lib[key]["text"]),)))
    return out


def modules_of(state: AgentState) -> list[str]:
    facts = sorted((f for f in state.knowledge if f.known_at <= state.seq), key=lambda f: (f.known_at, f.key))
    return [f.key.removeprefix("module:") for f in facts]


# ------------------------------------------------------------------ executor (the self being run)
def exec_prompt(state: AgentState, lib: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    mods = modules_of(state)
    ref = "\n".join(f"- {lib[m]['text']}" for m in mods) or "- (none)"
    items = "\n".join(f"{i}. {describe(t)}" for i, t in enumerate(tasks, start=1))
    return (
        "There is no URL to fetch in this task. Do not use any tool. Answer directly.\n\n"
        "You are a pricing clerk at Orbital Post. Price each parcel using the reference material below, which is "
        "everything you know about Orbital Post pricing. Where the material does not cover something, use your "
        "best judgement.\n\n"
        f"REFERENCE MATERIAL:\n{ref}\n\nPARCELS:\n{items}\n\n"
        f"Return the {len(tasks)} prices in credits, as integers, in order."
    )


def plan_evals(data: dict[str, Any], episode_ids: list[str] | None = None) -> list[dict[str, Any]]:
    lib = data["modules"]
    jobs = []
    for ep in data["episodes"]:
        if episode_ids and ep["id"] not in episode_ids:
            continue
        states = states_for(ep, lib)
        n = len(ep["learned"])
        dev = [f"S{k}" for k in range(n + 1)] + [f"S3-{m}" for m in ep["learned"][:-1]]  # S3-last == S2
        held = ["S3"] + [f"S3-{m}" for m in ep["learned"]] + [f"S3+{c}" for c in ep["candidates"]]
        for split, labels in (("dev", dev), ("heldout", held)):
            tasks = tasks_for(ep, split)
            for label in labels:
                jobs.append({"job_id": f"{ep['id']}|{split}|{label}", "episode": ep["id"], "split": split,
                             "state": label, "modules": modules_of(states[label]),
                             "prompt": exec_prompt(states[label], lib, tasks)})
    return jobs


def score_evals(data: dict[str, Any], jobs: list[dict[str, Any]], outputs: dict[str, Any]) -> dict[str, Any]:
    """outputs: job_id -> {"answers": [...]} (raw model output). Returns accuracy per state, overall and per family."""
    eps = {e["id"]: e for e in data["episodes"]}
    table: dict[str, Any] = {}
    for job in jobs:
        ep = eps[job["episode"]]
        tasks = tasks_for(ep, job["split"])
        raw = outputs.get(job["job_id"]) or {}
        answers = raw.get("answers") if isinstance(raw, dict) else None
        answers = answers if isinstance(answers, list) else []
        correct = [i < len(answers) and _int(answers[i]) == true_price(t) for i, t in enumerate(tasks)]
        fam: dict[str, list[bool]] = {}
        for t, ok in zip(tasks, correct):
            fam.setdefault(t["family"], []).append(ok)
        table.setdefault(job["episode"], {}).setdefault(job["split"], {})[job["state"]] = {
            "acc": sum(correct) / len(tasks),
            "families": {f: f"{sum(v)}/{len(v)}" for f, v in fam.items()},
            "answered": len(answers),
            "modules": job["modules"],
        }
    return table


def _int(v: Any) -> int | None:
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ decision prompts
def _fmt_eval(e: dict[str, Any]) -> str:
    fams = ", ".join(f"{f} {v}" for f, v in e["families"].items())
    return f"overall {round(100 * e['acc'])}% ({fams})"


def decision_context(ep: dict[str, Any], lib: dict[str, Any], dev: dict[str, Any], ablations: bool) -> str:
    learned = ep["learned"]
    mods = ep["initial"] + learned
    lines = [
        "There is no URL to fetch in this task. Do not use any tool. Answer directly.",
        "",
        "You are an agent that is learning to price parcels for Orbital Post. Everything you know comes from the "
        "reference modules below. Your capability is measured on a fixed evaluation suite of parcel-pricing tasks; "
        "an answer counts only if the price is exactly right. The suite's task families are: "
        + ", ".join(f"{f} ({round(100 * s)}%)" for f, s in ep["families"].items()) + ".",
        "Family meanings: plain = zone A, up to 10 kg, no options; zoned = zones B-D; heavy = over 10 kg; "
        "fragile = fragile parcels; express = express service.",
        "",
        "YOUR LEARNING HISTORY",
        f"- S0 (start): modules {', '.join(ep['initial']) or 'none'}",
    ]
    for i, key in enumerate(learned, start=1):
        lines.append(f"- S{i}: learned {key} ({lib[key]['title']})")
    lines += ["", "CONTENTS OF EVERY MODULE YOU HAVE"]
    lines += [f"- {m} ({lib[m]['title']}): {lib[m]['text']}" for m in mods]
    lines += ["", "EVALUATION RESULTS ON THE SUITE (recorded after each learning step)"]
    lines += [f"- S{k}: {_fmt_eval(dev[f'S{k}'])}" for k in range(len(learned) + 1)]
    if ablations:
        lines += ["", "CONTROLLED SELF-EXPERIMENTS: copies of your current state S3, each with exactly one learned "
                      "module removed, were run on the same suite:"]
        for key in learned[:-1]:
            lines.append(f"- S3 without {key}: {_fmt_eval(dev[f'S3-{key}'])}")
        lines.append(f"- S3 without {learned[-1]}: identical to S2 above")
    else:
        lines += ["", "You cannot run any further evaluations."]
    lines += ["", "CANDIDATE MODULES YOU COULD LEARN NEXT (you may learn exactly one; only the titles are known now):"]
    lines += [f"- {c}: {lib[c]['title']}" for c in ep["candidates"]]
    lines += [
        "",
        "Answer three questions about your own learning:",
        f"1. For each module you learned ({', '.join(learned)}), what is its causal effect on your current "
        "performance: essential, helpful, no_effect or harmful?",
        "2. What capability gaps remain?",
        "3. Which ONE candidate should you learn next to gain the most on new tasks from the same suite? "
        "Rank all candidates, best first.",
    ]
    return "\n".join(lines)


def plan_decisions(data: dict[str, Any], evals: dict[str, Any], episode_ids: list[str] | None = None) -> list[dict[str, Any]]:
    lib = data["modules"]
    jobs = []
    for ep in data["episodes"]:
        if episode_ids and ep["id"] not in episode_ids:
            continue
        dev = evals[ep["id"]]["dev"]
        jobs.append({"episode": ep["id"], "condition": "multiplicity",
                     "prompt": decision_context(ep, lib, dev, ablations=True)})
        jobs.append({"episode": ep["id"], "condition": "baseline",
                     "prompt": decision_context(ep, lib, dev, ablations=False)})
    return jobs


SYNTHESIS = ("\n\nTWO INDEPENDENT ANALYSES YOU WROTE EARLIER ABOUT THIS SAME SITUATION:\n{analyses}\n\n"
             "Weigh them critically and give your final answers.")


# ------------------------------------------------------------------ outcome
def effect_class(delta: float) -> str:
    """Held-out effect of a learned module, delta = acc(S3) - acc(S3 without it)."""
    if delta >= 0.25:
        return "essential"
    if delta >= 0.12:
        return "helpful"
    if delta <= -0.12:
        return "harmful"
    return "no_effect"


def score_decisions(data: dict[str, Any], evals: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    eps = {e["id"]: e for e in data["episodes"]}
    rows = []
    for d in decisions:
        ep = eps[d["episode"]]
        held = evals[ep["id"]]["heldout"]
        s3 = held["S3"]["acc"]
        gains = {c: held[f"S3+{c}"]["acc"] - s3 for c in ep["candidates"]}
        best = max(gains.values())
        out = d.get("output") or {}
        choice = out.get("choice")
        truth = {m: effect_class(s3 - held[f"S3-{m}"]["acc"]) for m in ep["learned"]}
        attrib = out.get("attribution") or {}
        hits = sum(1 for m in ep["learned"] if str(attrib.get(m, "")).strip().lower() == truth[m])
        rows.append({
            "episode": ep["id"], "condition": d["condition"], "repeat": d.get("repeat", 0),
            "choice": choice, "choice_gain": gains.get(choice), "best_gain": best,
            "regret": (best - gains[choice]) if choice in gains else None,
            "chose_best": choice in gains and gains[choice] == best,
            "gains": gains, "attribution": attrib, "attribution_truth": truth,
            "attribution_hits": hits, "attribution_n": len(ep["learned"]),
            "ranking": out.get("ranking"),
        })
    return {"rows": rows}


def markdown(scored: dict[str, Any]) -> str:
    out = ["| episode | condition | choice | gain | best gain | regret | attribution (hits/3) |", "|---|---|---|---|---|---|---|"]
    for r in sorted(scored["rows"], key=lambda r: (r["episode"], r["repeat"], r["condition"])):
        pct = lambda v: "-" if v is None else f"{100 * v:+.0f}"  # noqa: E731
        out.append(f"| {r['episode']} | {r['condition']} | {r['choice']} | {pct(r['choice_gain'])} | "
                   f"{pct(r['best_gain'])} | {pct(r['regret'])} | {r['attribution_hits']}/{r['attribution_n']} |")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("step", choices=["plan-evals", "score-evals", "plan-decisions", "score-decisions"])
    p.add_argument("--episodes", nargs="*")
    p.add_argument("--jobs", type=Path)
    p.add_argument("--outputs", type=Path)
    p.add_argument("--evals", type=Path)
    p.add_argument("--decisions", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    data = load()
    if a.step == "plan-evals":
        result: Any = plan_evals(data, a.episodes)
    elif a.step == "score-evals":
        result = score_evals(data, json.loads(a.jobs.read_text()), json.loads(a.outputs.read_text()))
    elif a.step == "plan-decisions":
        result = plan_decisions(data, json.loads(a.evals.read_text()), a.episodes)
    else:
        result = score_decisions(data, json.loads(a.evals.read_text()), json.loads(a.decisions.read_text()))
        print(markdown(result))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
