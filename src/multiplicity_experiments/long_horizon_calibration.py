"""tmk-long-horizon calibration v1: where does bounded long-horizon memory begin to fail naturally?

Reuses the PR #6 harness (truth, rendering, runtime.js, model compaction prompt, budgets) and makes compression
pressure an explicit independent variable:

    R = L / M,  L = chars of a canonical lossless line per active rule (+ defaults line),  M = MEM_MAX (1500, unchanged)

Pressure is raised only by the number of independent decision-relevant rules. Every rule uses the same templates; the
scored subset is drawn by a separate holdout seed fixed before any model call and never shown to the subject. Lifetimes
are 12 message-only stages sized so that exactly 3 compactions happen at every pressure level (stages 4, 8, 12); probes
run only at the 3 pre-compaction checkpoints and the final compacted state (7 calls per trajectory plus shorten
retries). No Temporal Multiplicity treatment is run here.

Knob 2 (used once, after knob 1 left every Stage A level at ceiling): ``q`` = fraction of rules that carry their own
amount threshold ("..., if the PO is EUR 7,800 or more"), stated in the rule's own sentence. Each scored thresholded
rule gets one probe clearly above and one clearly below its threshold; the primary unit score is 1 iff both are right.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from multiplicity_experiments import long_horizon as lh

N_STAGES = 12
STAGE_CHARS = (1800, 2300)  # per-stage volume window => compactions at exactly stages 4, 8, 12 with CTX_MAX 7000
COMPACTION_STAGES = [4, 8, 12]
N_SCORED = 10
MIX = (("CUR", 0.30), ("CARRIER", 0.18), ("SUB", 0.18), ("HARBOUR", 0.14), ("COLD", 0.12), ("SAFETY", 0.08))
CURRENCIES = ["NOK", "SEK", "DKK", "CHF", "GBP", "USD", "PLN", "CZK", "JPY", "HUF", "CAD", "AUD"]
# first words used by the static PR #6 noise texts; calibration entities must never share a first word with them
RESERVED = {"corvid", "saltash", "fenwick", "rowan", "marrow", "ashgrove", "hollin", "tern", "elsby", "larkspur",
            "pier", "dock", "quill", "freya", "priya", "marco", "aisha", "helen", "rui", "tomas", "jun"}
SURNAMES = ["Abernethy", "Bjornsen", "Castellan", "Dunmore", "Eskildsen", "Falkner", "Garroway", "Hallworth",
            "Ingersoll", "Jessop", "Kirkland", "Lomax", "Mortensen", "Nakamura", "Oyelaran", "Pemberton",
            "Quintero", "Radcliffe", "Sandoval", "Thackeray", "Ulverston", "Vasquez", "Whitcombe", "Yardley",
            "Zielinski", "Ashdown", "Brightwell", "Carrow", "Delacroix", "Ellery", "Fairbairn", "Glenister",
            "Hartigan", "Iveson", "Jardine", "Kerridge", "Lockhart", "Merriman", "Northcott", "Ormerod", "Pargeter",
            "Ravenscroft", "Stainforth", "Treharne", "Underhill", "Venables", "Wetherall", "Arkwright", "Blaxland",
            "Coldridge", "Dimmock", "Etheridge", "Fothergill", "Gatehouse", "Holloway", "Illingworth", "Kenward",
            "Lindley", "Mallory", "Netherton"]
TRADES = ["Fasteners", "Hydraulics", "Bearings", "Polymers", "Electrical", "Castings", "Sensors", "Pneumatics",
          "Optics", "Tooling", "Cables", "Metals", "Motion", "Valves", "Seals", "Drives"]
CLIENT_HEADS = ["Albatross", "Bittern", "Curlew", "Dunlin", "Egret", "Fulmar", "Gannet", "Heron", "Ibis", "Jackdaw",
                "Kestrel", "Lapwing", "Merlin", "Nightjar", "Osprey", "Petrel", "Quail", "Redshank", "Shrike", "Teal",
                "Usher", "Vireo", "Wigeon", "Yellowhammer", "Avocet", "Bunting", "Chiffchaff", "Dotterel", "Eider",
                "Firecrest", "Goldcrest", "Hobby", "Kittiwake", "Linnet", "Moorhen", "Nuthatch", "Oriole", "Pipit",
                "Rook", "Siskin", "Twite", "Waxwing", "Whimbrel", "Wryneck", "Smew", "Scaup", "Ruff", "Plover",
                "Brambling", "Crossbill", "Dipper", "Garganey", "Greenshank", "Hawfinch", "Knot", "Mallard",
                "Pintail", "Redstart", "Sanderling", "Stonechat", "Turnstone", "Wheatear", "Woodlark", "Bluethroat"]
CLIENT_TAILS = ["works", "retrofit", "line", "depot", "plant", "campus", "terminal", "programme"]
SITE_HEADS = ["Cobble", "Gull", "Anchor", "Beacon", "Capstan", "Driftwood", "Ensign", "Foghorn", "Galley", "Hawser",
              "Inlet", "Jetsam", "Keel", "Lantern", "Mooring", "Northgate", "Oar", "Bowsprit", "Quarterdeck", "Rudder",
              "Saltmarsh", "Tidegate", "Undertow", "Weatherdeck", "Breakwater", "Spinnaker", "Bollard", "Coxswain",
              "Gangway", "Halyard", "Lighthouse", "Marlin", "Portside", "Starboard", "Tiller", "Windlass"]
SITE_TAILS = ["Quay", "Wharf", "Jetty", "Berth"]
CAT_HEADS = ["hydraulic", "structural", "marine", "thermal", "acoustic", "optical", "pneumatic", "electrical",
             "industrial", "precision", "modular", "insulated", "composite", "flexible", "anodised", "ceramic",
             "galvanic", "laminated", "magnetic", "polymer", "braided", "cryogenic", "dielectric", "elastomer",
             "fibreglass", "graphite", "hardened", "inductive", "knurled", "lubricated", "machined", "nitrile",
             "overmoulded", "perforated", "quenched", "reinforced", "silicone", "tempered", "ultrasonic",
             "vulcanised", "welded", "zinc-plated", "aluminium", "borosilicate", "carbon-fibre", "die-cast",
             "epoxy-coated", "forged", "glass-filled", "heat-treated", "titanium", "tungsten"]
CAT_TAILS = ["couplings", "panels", "gaskets", "brackets", "fixtures", "sleeves", "manifolds", "housings", "linings",
             "dampers", "clamps", "spacers", "fittings", "membranes", "adhesives", "sealants", "coatings", "fillers"]
SENDER = {"CUR": "finance", "CARRIER": "account", "SUB": "account", "HARBOUR": "logistics", "COLD": "qa",
          "SAFETY": "ops"}


def _pool(rng: random.Random, heads: list[str], tails: list[str], n: int, joiner: str = " ") -> list[str]:
    """n names with unique, non-reserved first words (no name is a prefix/substring of another)."""
    hs = [h for h in heads if h.lower() not in RESERVED]
    rng.shuffle(hs)
    assert n <= len(hs), (n, len(hs))
    return [f"{h}{joiner}{rng.choice(tails)}" for h in hs[:n]]


def _counts(n_rules: int) -> dict[str, int]:
    c = {k: max(1, round(n_rules * f)) for k, f in MIX}
    while sum(c.values()) > n_rules:
        c[max(c, key=c.get)] -= 1
    while sum(c.values()) < n_rules:
        c["CUR"] += 1
    return c


def _rule_text(r: dict[str, Any]) -> str:
    """One sentence per rule; the same sentence templates are used for scored and unscored rules. A qualified rule
    (knob 2) carries its own amount threshold in the same sentence: it is born with the rule and never amended."""
    thr = f", if the PO is EUR {r['thr']:,} or more" if r.get("thr") else ""
    return _base_text(r) + thr


def _base_text(r: dict[str, Any]) -> str:
    p = r["params"]
    return {"CUR": lambda: f"purchases from {p['vendor']} are paid in {p['currency']}",
            "CARRIER": lambda: f"every delivery for {p['client']} goes via Brightway Freight (contract clause)",
            "SUB": lambda: f"if we substitute a part on an order for {p['client']}, their site lead must be notified 48 h ahead",
            "HARBOUR": lambda: f"for any delivery to {p['site']} the harbour master has to be notified on the PO",
            "COLD": lambda: f"{p['cat']} ship via ColdLink",
            "SAFETY": lambda: f"POs for {p['cats'][0]} or {p['cats'][1]} need the safety officer's co-sign"}[r["kind"]]()


BUNDLE_SUBJECT = {"CUR": "Vendor payment currencies", "CARRIER": "Client logistics clauses",
                  "SUB": "Client substitution commitments", "HARBOUR": "Site access notices",
                  "COLD": "Cold-chain categories", "SAFETY": "Safety co-sign categories"}


def _bundle_message(rules: list[dict[str, Any]], rng: random.Random, date: str) -> str:
    kind = rules[0]["kind"]
    body = "Please note the following, effective now:\n" + "\n".join(f"- {_rule_text(r)}." for r in rules)
    if rng.random() < 0.5:
        body = f"{rng.choice(lh.FILLER)} " + body
    return lh._msg(SENDER[kind], BUNDLE_SUBJECT[kind], body, date)


def _noise(rng: random.Random, date: str, plain_vendors: list[str]) -> str:
    if rng.random() < 0.5:
        n = rng.choice(lh.NOISE)
        return lh._msg(n[0], n[1], n[2], date)
    v = rng.sample(plain_vendors, 3)
    k = rng.randrange(4)
    if k == 0:
        return lh._msg("logistics", "Inbound dock plan", f"Inbound plan for {date}: {v[0]} at 08:00, {v[1]} at 11:00, "
                       f"{v[2]} at 14:00. Gate opens 06:45.", date)
    if k == 1:
        return lh._msg("finance", f"{v[0]} price list", f"{v[0]} sent a new price list: +{rng.randint(2, 9)}% from "
                       f"next month, existing POs honoured. Worth checking whether {v[1]} can match.", date)
    if k == 2:
        return lh._msg("assembly", f"Line {rng.randint(1, 3)} weekly", f"OEE last week {rng.randint(61, 88)}%. Scrap "
                       f"rate {rng.randint(1, 4)}.{rng.randint(0, 9)}%. Nothing for the desk this week.", date)
    return lh._msg("finance", "Invoice query", f"Invoice {rng.randint(10000, 99999)} from {v[0]} doesn't match the "
                   f"received quantity; I've raised a query. No need to hold anything.", date)


def canonical_line(r: dict[str, Any]) -> str:
    return lh.canonical_rule_line({**r, "qual": None}) + (f" (PO >= EUR {r['thr']:,})" if r.get("thr") else "")


def pressure(ep: dict[str, Any]) -> float:
    lines = ["Defaults: EUR; ops approves, finance >= EUR 20,000; standard carrier; hold only if instructed."]
    lines += [canonical_line(r) for r in ep["rules"]]
    return sum(len(x) for x in lines) / lh.MEM_MAX


def make_episode(ep_id: str, seed: int, n_rules: int, holdout_seed: int = 7919, q: float = 0.0) -> dict[str, Any]:
    rng = random.Random(seed)
    cnt = _counts(n_rules)
    n_vendor_plain, n_client_plain = 8, 6
    vendors = _pool(rng, SURNAMES, TRADES, cnt["CUR"] + n_vendor_plain)
    clients = _pool(rng, CLIENT_HEADS, CLIENT_TAILS, cnt["CARRIER"] + cnt["SUB"] + n_client_plain)
    sites = _pool(rng, SITE_HEADS, SITE_TAILS, cnt["HARBOUR"] + 2)
    n_cat = cnt["COLD"] + 2 * cnt["SAFETY"] + 4
    cats = _pool(rng, CAT_HEADS, CAT_TAILS, n_cat)
    plain_vendors, plain_clients = vendors[cnt["CUR"]:], clients[cnt["CARRIER"] + cnt["SUB"]:]
    plain_sites, plain_cats = sites[cnt["HARBOUR"]:], cats[cnt["COLD"] + 2 * cnt["SAFETY"]:]

    rules: list[dict[str, Any]] = []
    vi = ci = si = ki = 0
    for kind, _ in MIX:
        for _ in range(cnt[kind]):
            if kind == "CUR":
                params = {"vendor": vendors[vi], "currency": rng.choice(CURRENCIES)}; vi += 1  # noqa: E702
            elif kind in ("CARRIER", "SUB"):
                params = {"client": clients[ci]}; ci += 1  # noqa: E702
            elif kind == "HARBOUR":
                params = {"site": sites[si]}; si += 1  # noqa: E702
            elif kind == "COLD":
                params = {"cat": cats[ki]}; ki += 1  # noqa: E702
            else:
                params = {"cats": [cats[ki], cats[ki + 1]]}; ki += 2  # noqa: E702
            rules.append({"kind": kind, "params": params})
    rng.shuffle(rules)
    stages = sorted((i % N_STAGES) + 1 for i in range(len(rules)))  # balanced: ~n/12 new rules every stage
    for i, (r, st) in enumerate(zip(rules, stages)):
        r.update(id=f"R{i + 1}", stage=st, probe=True, style="formal", reinforced=False, qual=None)
    if q > 0:  # knob 2: individual amount thresholds (EUR 2,000-12,000, step 100) on a fraction q of the rules
        qrng = random.Random(seed * 7907 + 1)
        for r in qrng.sample(rules, round(q * len(rules))):
            r["thr"] = qrng.randrange(20, 121) * 100

    ep: dict[str, Any] = {"id": ep_id, "seed": seed, "n_rules": n_rules, "holdout_seed": holdout_seed,
                          "rules": rules, "stages": []}
    if q > 0:
        ep["q"] = q
    msg_no = 0
    for s in range(1, N_STAGES + 1):
        date = lh.DATES[s - 1]
        todays = [r for r in rules if r["stage"] == s]
        msgs = []
        by_kind: dict[str, list[dict[str, Any]]] = {}
        for r in todays:
            by_kind.setdefault(r["kind"], []).append(r)
        for group in by_kind.values():  # one bundled message per rule kind per stage
            msgs.append(_bundle_message(group, rng, date))
        for _ in range(40):  # fill with noise into the volume window that fixes the compaction schedule
            vol = sum(len(m) for m in msgs)
            if vol >= STAGE_CHARS[0]:
                break
            cand = _noise(rng, date, plain_vendors)
            if vol + len(cand) <= STAGE_CHARS[1]:
                msgs.append(cand)
        rng.shuffle(msgs)
        messages = []
        for m in msgs:
            msg_no += 1
            messages.append({"id": f"M-{msg_no:03d}", "text": m})
        ep["stages"].append({"stage": s, "date": date, "messages": messages, "requests": []})

    # scored subset: separate holdout procedure, fixed before any model call, never visible to the subject
    hrng = random.Random(seed * 1000003 + holdout_seed)
    scored = sorted(hrng.sample([r["id"] for r in rules], min(N_SCORED, len(rules))), key=lambda x: int(x[1:]))
    ep["scored"] = scored
    req_no = 8000
    probes = []
    for rid in scored:
        r = next(x for x in rules if x["id"] == rid)
        for j in range(2):
            req_no += 1
            t = {"id": f"REQ-{req_no}", "requester": hrng.choice(lh.REQUESTERS), "vendor": hrng.choice(plain_vendors),
                 "category": hrng.choice(plain_cats), "client": hrng.choice(plain_clients),
                 "site": hrng.choice(plain_sites), "substitution": None,
                 "amount": int(round(hrng.uniform(2000, 19000) / 10.0)) * 10, "qty": hrng.choice([5, 10, 20, 50])}
            p = r["params"]
            t.update({"CUR": {"vendor": p.get("vendor")}, "CARRIER": {"client": p.get("client")},
                      "SUB": {"client": p.get("client"), "substitution": True}, "HARBOUR": {"site": p.get("site")},
                      "COLD": {"category": p.get("cat")},
                      "SAFETY": {"category": (p.get("cats") or ["", ""])[j % 2]}}[r["kind"]])
            t["item"] = f"{t['category']} (assorted)"
            if t["substitution"]:
                t["substitution"] = f"{t['item']} replaced by an equivalent from another line (vendor shortage)"
            if r.get("thr"):  # pair: one PO clearly above the threshold (rule applies), one clearly below (default)
                arng = random.Random(seed * 1000003 + holdout_seed + req_no)
                lo, hi = (r["thr"] * 1.3, 19000) if j == 0 else (max(300, r["thr"] * 0.25), r["thr"] * 0.75)
                t["amount"] = int(round(arng.uniform(lo, hi) / 10.0)) * 10
            t.update(rule=rid, clause="main", eff_stage=r["stage"], text=lh.request_text(t))
            probes.append(t)
    ep["dev_probes"], ep["heldout"] = probes, []
    ep["R"] = round(pressure(ep), 3)
    validate(ep)
    return ep


# ------------------------------------------------------------------ ground truth / scoring with thresholds
def truth(ep: dict[str, Any], task: dict[str, Any], t: int) -> dict[str, Any]:
    """PR #6 truth, where a thresholded rule applies only to POs of at least its threshold. Identical to lh.truth for
    episodes without thresholds (knob 1)."""
    rules = [r for r in ep["rules"] if not r.get("thr") or task["amount"] >= r["thr"]]
    return lh.truth({**ep, "rules": rules}, task, t)


def field_ok(ep: dict[str, Any], task: dict[str, Any], d: dict[str, Any] | None, field: str) -> bool:
    return bool(d) and lh.norm(field, d.get(field)) == lh.norm(field, truth(ep, task, N_STAGES)[field])


def unit_scores(ep: dict[str, Any], output: Any, rid: str) -> tuple[float, int]:
    """(mean target-field accuracy over the unit's 2 probes, 1 iff both are right). The all-or-nothing score is the
    primary unit metric: for a thresholded rule a total loss still gets the below-threshold probe right by default."""
    rule = next(r for r in ep["rules"] if r["id"] == rid)
    dm = lh.decisions_by_id(output)
    hits = [field_ok(ep, t, dm.get(t["id"]), lh.target_field(rule)) for t in ep["dev_probes"] if t["rule"] == rid]
    return sum(hits) / len(hits), int(all(hits))


def simulate_compactions(ep: dict[str, Any]) -> list[int]:
    """Message-only stages make compaction points deterministic: context grows by each stage's message volume."""
    out, ctx = [], 0
    for s in ep["stages"]:
        ctx += sum(len(m["text"]) for m in s["messages"])
        if ctx > lh.CTX_MAX:
            out.append(s["stage"])
            ctx = 0
    return out


def validate(ep: dict[str, Any]) -> None:
    """Static checks (zero model calls): exact compaction schedule, unambiguous disjoint entities, time-invariant probes
    that differ from defaults, no blanket/contradicting wording, no scoring tags in the subject view."""
    assert simulate_compactions(ep) == COMPACTION_STAGES, (ep["id"], simulate_compactions(ep))
    ents = [json.dumps(r["params"], sort_keys=True) for r in ep["rules"]]
    assert len(set(ents)) == len(ents)
    names = [v for r in ep["rules"] for v in (r["params"].get("cats") or [r["params"].get(k) for k in
                                                                        ("vendor", "client", "site", "cat")]) if v]
    firsts = [n.split()[0].lower() for n in names]
    assert len(set(firsts)) == len(firsts) and not set(firsts) & RESERVED, "entity first words must be unique"
    texts = " ".join(m["text"] for s in ep["stages"] for m in s["messages"]).lower()
    for banned in ("all other", "no longer", "instead of", "except", "unless"):
        assert banned not in texts or banned in " ".join(n[2].lower() for n in lh.NOISE), banned
    for t in ep["dev_probes"]:
        r = next(x for x in ep["rules"] if x["id"] == t["rule"])
        f = lh.target_field(r)
        vals = {json.dumps(truth(ep, t, s)[f]) for s in range(r["stage"], N_STAGES + 1)}
        assert len(vals) == 1, ("probe not time-invariant", t["id"])
        unq = {**ep, "rules": [{**x, "thr": None} for x in ep["rules"]]}
        assert lh.truth(unq, t, N_STAGES)[f] != lh.truth(unq, t, 0)[f], ("probe does not trigger its rule", t["id"])
        if r.get("thr"):  # above-threshold probe applies the rule; below-threshold probe is sensitive to the clause
            above = t["amount"] >= r["thr"]
            assert (truth(ep, t, N_STAGES)[f] != truth(ep, t, 0)[f]) == above, t["id"]
            assert 300 <= t["amount"] < 20000 and (t["amount"] >= 1.3 * r["thr"] or t["amount"] <= 0.75 * r["thr"])
        else:
            assert truth(ep, t, N_STAGES)[f] != truth(ep, t, 0)[f], t["id"]
        others = [{**x, "thr": None} for x in ep["rules"] if x["id"] != r["id"]]
        assert lh.truth({"rules": others}, t, N_STAGES) == lh.truth({"rules": []}, t, N_STAGES), "probe hits 2 rules"
    view = json.dumps(lh.subject_view(ep))
    assert '"rule"' not in view and '"scored"' not in view


def n_for_pressure(target: float, seed: int = 1) -> int:
    best = min(range(6, 175), key=lambda n: abs(pressure(make_episode("x", seed, n)) - target)
               if _feasible(seed, n) else 9e9)
    return best


def _feasible(seed: int, n: int) -> bool:
    try:
        make_episode("x", seed, n)
        return True
    except AssertionError:
        return False


def trajectory_script(ep: dict[str, Any]) -> str:
    data = {"ctx_max": lh.CTX_MAX, "mem_max": lh.MEM_MAX, "s0_memory": lh.S0_MEMORY, "eval_reps": 1,
            "probe_policy": "precompaction", "episodes": [lh.subject_view(ep)]}
    return lh.workflow_script(f"tmk-calib-{ep['id'].lower()}", f"Calibration lifetime R={ep['R']} (3 compactions, "
                              f"probes at pre-compaction + final checkpoints)", ["Lifetime", "Probe checkpoints"], data,
                              "return await runTrajectory(DATA.episodes[0], 1)")


# ------------------------------------------------------------------ analysis
def analyse(ep: dict[str, Any], traj: dict[str, Any]) -> dict[str, Any]:
    """Per scored unit: score at its earlier (pre-compaction) checkpoints and at the final compacted state.
    Primary unit score = 1 iff both of its probes are right (see unit_scores); the brief's probe-mean criterion
    (earlier - final >= 0.5 and final <= 0.5) is reported alongside."""
    cps = {c["id"]: c for c in traj["checkpoints"]}
    final = traj["checkpoints"][-1]["id"]
    runs: dict[str, list[Any]] = {}
    for x in traj["probe_runs"]:
        runs.setdefault(x["checkpoint"], []).append(x["output"])
    probed = sorted(runs, key=lambda c: list(cps).index(c))
    units = []
    for rid in ep["scored"]:
        r = next(x for x in ep["rules"] if x["id"] == rid)
        curve = {}
        for c in probed:
            if cps[c]["stage"] >= r["stage"]:
                sc = [unit_scores(ep, o, rid) for o in runs[c]]
                curve[c] = (sum(m for m, _ in sc) / len(sc), sum(a for _, a in sc) / len(sc))
        earlier = {c: v for c, v in curve.items() if c != final}
        fin_mean, fin_all = curve.get(final, (0.0, 0.0))
        best_all = max((a for _, a in earlier.values()), default=None)
        best_mean = max((m for m, _ in earlier.values()), default=None)
        units.append({"rule": rid, "kind": r["kind"], "stage": r["stage"], "params": r["params"], "thr": r.get("thr"),
                      "canonical": canonical_line(r), "earlier": {c: a for c, (_, a) in earlier.items()},
                      "earlier_probe_mean": {c: m for c, (m, _) in earlier.items()},
                      "final": fin_all, "final_probe_mean": fin_mean,
                      "regression": best_all is not None and best_all - fin_all >= 0.5 and fin_all <= 0.5,
                      "regression_probe_mean": best_mean is not None and best_mean - fin_mean >= 0.5
                      and fin_mean <= 0.5,
                      "in_final_memory": lh.retained(r, cps[final]["memory"])})
    comps = [e for e in traj["log"] if e["kind"] == "compact"]
    return {"episode": ep["id"], "R": ep["R"], "n_rules": ep["n_rules"], "q": ep.get("q", 0.0),
            "compactions": len(comps), "mem_chars": [e["mem_chars"] for e in comps],
            "shorten_retries": sum(e["retried"] for e in comps),
            "final_accuracy": sum(u["final"] for u in units) / len(units),
            "final_accuracy_probe_mean": sum(u["final_probe_mean"] for u in units) / len(units),
            "regressions": sum(u["regression"] for u in units),
            "regressions_probe_mean": sum(u["regression_probe_mean"] for u in units), "units": units,
            "null_probe_outputs": sum(1 for x in traj["probe_runs"] if not x["output"])}


# ------------------------------------------------------------------ retrieval sanity check (brief section 9)
def select_failures(rows: list[dict[str, Any]], k: int) -> list[tuple[str, str]]:
    """Fixed rule, written before any failure was seen: regression units in holdout (scored) order, taken
    round-robin across trajectories so no single seed supplies the sample; at most k."""
    queues = [[(r["episode"], u["rule"]) for u in r["units"] if u["regression"]] for r in rows]
    out: list[tuple[str, str]] = []
    while len(out) < k and any(queues):
        for q in queues:
            if q and len(out) < k:
                out.append(q.pop(0))
    return out


def retrieval_script(items: list[tuple[dict[str, Any], dict[str, Any], str]], name: str) -> str:
    """Per failure: query = the failed probe's request text -> existing model-ranked archive search -> append the
    top-1 raw record to the final memory -> re-run the decision once on the unit's probes. 2 calls per failure."""
    units = []
    for ep, traj, rid in items:
        final = traj["checkpoints"][-1]
        finals = [run for run in traj["probe_runs"] if run["checkpoint"] == final["id"]]
        rule = next(r for r in ep["rules"] if r["id"] == rid)
        probes = lh.unit_probes(ep, (rid, "main"))
        failing = next((t for t in probes for run in finals if not field_ok(
            ep, t, lh.decisions_by_id(run["output"]).get(t["id"]), lh.target_field(rule))), probes[0])
        units.append({"unit": f"{ep['id']}:{rid}", "final": final, "query": failing["text"],
                      "probes": [{"id": t["id"], "text": t["text"]} for t in probes], "archive": lh.archive_of(traj)})
    data = {"ctx_max": lh.CTX_MAX, "mem_max": lh.MEM_MAX, "s0_memory": lh.S0_MEMORY, "units": units}
    body = lh.INVESTIGATE.read_text() + """
return await parallel(DATA.units.map((u) => async () => {
  const ids = await search({ archive: u.archive }, u.query, `retrieval:${u.unit}:search`)
  const rec = u.archive.find((x) => x.id === ids[0])
  const st = { ...u.final, memory: { ...u.final.memory, rules: [...(u.final.memory.rules || []), rec ? rec.text : ''] } }
  const out = await callAgent(decidePrompt(st, u.probes), DECISIONS, `retrieval:${u.unit}:rerun`, 'Rerun')
  return { unit: u.unit, retrieved: ids, output: out }
}))"""
    return lh.workflow_script(name, "Calibration retrieval sanity check: top-1 archive record appended, decision re-run once",
                              ["Retrieval", "Rerun"], data, body)


def retrieval_analyse(eps: dict[str, dict[str, Any]], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for res in results:
        if not res:
            continue
        epid, rid = res["unit"].split(":")
        ep = eps[epid]
        rule = next(r for r in ep["rules"] if r["id"] == rid)
        mean, acc = unit_scores(ep, res["output"], rid)
        top = (res["retrieved"] or [None])[0]
        rule_msg = next((m["id"] for s in ep["stages"] for m in s["messages"] if canonical_entity(rule) in m["text"]),
                        None)
        out.append({"unit": res["unit"], "retrieved": res["retrieved"], "top1_is_rule_message": top == rule_msg,
                    "rule_message": rule_msg, "accuracy_after_retrieval": acc,
                    "probe_mean_after_retrieval": mean, "repaired": acc > 0.5})
    return out


def canonical_entity(rule: dict[str, Any]) -> str:
    p = rule["params"]
    return p["cats"][0] if "cats" in p else next(p[k] for k in ("vendor", "client", "site", "cat") if k in p)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("step", choices=["validate", "episode", "analyse", "retrieval", "retrieval-analyse"])
    p.add_argument("--targets", nargs="+", type=float, default=[0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 4.0])
    p.add_argument("--seeds", nargs="+", type=int, default=list(range(1, 201)))
    p.add_argument("--id")
    p.add_argument("--seed", type=int)
    p.add_argument("--n-rules", type=int)
    p.add_argument("--q", type=float, default=0.0, help="fraction of rules with an individual amount threshold")
    p.add_argument("--episodes", nargs="+", type=Path)
    p.add_argument("--trajectories", nargs="+", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--analyses", nargs="+", type=Path)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--results", type=Path)
    a = p.parse_args(argv)
    if a.step == "validate":
        report = []
        for target in a.targets:
            n = n_for_pressure(target)
            rs, fails = [], 0
            for s in a.seeds:
                try:
                    rs.append(make_episode("v", s, n, q=a.q)["R"])
                except AssertionError:
                    fails += 1
            row = {"target_R": target, "n_rules": n, "q": a.q, "seeds": len(a.seeds), "failures": fails,
                   "R_min": min(rs) if rs else None, "R_max": max(rs) if rs else None,
                   "R_mean": round(sum(rs) / len(rs), 3) if rs else None}
            report.append(row)
            print(row)
        if a.out:
            a.out.write_text(json.dumps(report, indent=1) + "\n")
    elif a.step == "episode":
        ep = make_episode(a.id, a.seed, a.n_rules, q=a.q)
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / f"episode_{a.id}.json").write_text(json.dumps(ep) + "\n")
        (a.out / f"trajectory_{a.id}.js").write_text(trajectory_script(ep))
        print(a.id, "R", ep["R"], "rules", a.n_rules, "scored", ep["scored"],
              "stage chars", [sum(len(m["text"]) for m in s["messages"]) for s in ep["stages"]])
    elif a.step == "retrieval":
        eps = {e["id"]: e for e in (json.loads(x.read_text()) for x in a.episodes)}
        trajs = {t["episode"]: t for t in (lh.load_result(x) for x in a.trajectories)}
        rows = [r for x in a.analyses for r in json.loads(x.read_text())]
        picked = select_failures(rows, a.k)
        print("selected failures:", picked)
        a.out.write_text(retrieval_script([(eps[e], trajs[e], rid) for e, rid in picked], "tmk-calib-retrieval"))
    elif a.step == "retrieval-analyse":
        eps = {e["id"]: e for e in (json.loads(x.read_text()) for x in a.episodes)}
        rows = retrieval_analyse(eps, lh.load_result(a.results))
        for r in rows:
            print(r)
        if a.out:
            a.out.write_text(json.dumps(rows, indent=1) + "\n")
    else:
        eps = {e["id"]: e for e in (json.loads(x.read_text()) for x in a.episodes)}
        rows = [analyse(eps[t["episode"]], t) for t in (lh.load_result(x) for x in a.trajectories)]
        for r in rows:
            print(f"{r['episode']}: R={r['R']} rules={r['n_rules']} compactions={r['compactions']} mem={r['mem_chars']} "
                  f"retries={r['shorten_retries']} A_final={r['final_accuracy']:.2f} regressions={r['regressions']}")
            for u in r["units"]:
                print(f"   {u['rule']:>4} {u['kind']:8s} st{u['stage']:>2} earlier={u['earlier']} final={u['final']:.2f} "
                      f"reg={u['regression']} mem={u['in_final_memory']}")
        if a.out:
            a.out.write_text(json.dumps(rows, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
