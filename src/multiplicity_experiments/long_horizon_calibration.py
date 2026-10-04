"""tmk-long-horizon calibration v1: where does bounded long-horizon memory begin to fail naturally?

Reuses the PR #6 harness (truth, rendering, runtime.js, model compaction prompt, budgets) and makes compression
pressure an explicit independent variable:

    R = L / M,  L = chars of a canonical lossless line per active rule (+ defaults line),  M = MEM_MAX (1500, unchanged)

Pressure is raised only by the number of independent decision-relevant rules. Every rule uses the same templates; the
scored subset is drawn by a separate holdout seed fixed before any model call and never shown to the subject. Lifetimes
are 12 message-only stages sized so that exactly 3 compactions happen at every pressure level (stages 4, 8, 12); probes
run only at the 3 pre-compaction checkpoints and the final compacted state (7 calls per trajectory plus shorten
retries). No Temporal Multiplicity treatment is run here.
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
    """One sentence per rule; the same sentence templates are used for scored and unscored rules."""
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
    return lh.canonical_rule_line({**r, "qual": None})


def pressure(ep: dict[str, Any]) -> float:
    lines = ["Defaults: EUR; ops approves, finance >= EUR 20,000; standard carrier; hold only if instructed."]
    lines += [canonical_line(r) for r in ep["rules"]]
    return sum(len(x) for x in lines) / lh.MEM_MAX


def make_episode(ep_id: str, seed: int, n_rules: int, holdout_seed: int = 7919) -> dict[str, Any]:
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

    ep: dict[str, Any] = {"id": ep_id, "seed": seed, "n_rules": n_rules, "holdout_seed": holdout_seed,
                          "rules": rules, "stages": []}
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
            t.update(rule=rid, clause="main", eff_stage=r["stage"], text=lh.request_text(t))
            probes.append(t)
    ep["dev_probes"], ep["heldout"] = probes, []
    ep["R"] = round(pressure(ep), 3)
    validate(ep)
    return ep


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
        vals = {json.dumps(lh.truth(ep, t, s)[f]) for s in range(r["stage"], N_STAGES + 1)}
        assert len(vals) == 1 and lh.truth(ep, t, N_STAGES)[f] != lh.truth(ep, t, 0)[f], t["id"]
        others = [x for x in ep["rules"] if x["id"] != r["id"]]
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
    """Per scored unit: accuracy at its earlier (pre-compaction) checkpoint and at the final compacted state."""
    cps = {c["id"]: c for c in traj["checkpoints"]}
    final = traj["checkpoints"][-1]["id"]
    probed = sorted({r["checkpoint"] for r in traj["probe_runs"]}, key=lambda c: list(cps).index(c))
    units = []
    for rid in ep["scored"]:
        r = next(x for x in ep["rules"] if x["id"] == rid)
        unit = (rid, "main")
        curve = {c: lh.unit_accuracy(ep, traj["probe_runs"], unit, state_id=c) for c in probed
                 if cps[c]["stage"] >= r["stage"]}
        earlier = {c: a for c, a in curve.items() if c != final and a is not None}
        best = max(earlier.values()) if earlier else None
        fin = curve.get(final) or 0.0
        units.append({"rule": rid, "kind": r["kind"], "stage": r["stage"], "params": r["params"],
                      "canonical": canonical_line(r), "earlier": earlier, "final": fin,
                      "regression": best is not None and best - fin >= 0.5 and fin <= 0.5,
                      "in_final_memory": lh.retained(r, cps[final]["memory"])})
    comps = [e for e in traj["log"] if e["kind"] == "compact"]
    return {"episode": ep["id"], "R": ep["R"], "n_rules": ep["n_rules"], "compactions": len(comps),
            "mem_chars": [e["mem_chars"] for e in comps], "shorten_retries": sum(e["retried"] for e in comps),
            "final_accuracy": sum(u["final"] for u in units) / len(units),
            "regressions": sum(u["regression"] for u in units), "units": units,
            "null_probe_outputs": sum(1 for x in traj["probe_runs"] if not x["output"])}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("step", choices=["validate", "episode", "analyse"])
    p.add_argument("--targets", nargs="+", type=float, default=[0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 4.0])
    p.add_argument("--seeds", nargs="+", type=int, default=list(range(1, 201)))
    p.add_argument("--id")
    p.add_argument("--seed", type=int)
    p.add_argument("--n-rules", type=int)
    p.add_argument("--episodes", nargs="+", type=Path)
    p.add_argument("--trajectories", nargs="+", type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    if a.step == "validate":
        report = []
        for target in a.targets:
            n = n_for_pressure(target)
            rs, fails = [], 0
            for s in a.seeds:
                try:
                    rs.append(make_episode("v", s, n)["R"])
                except AssertionError:
                    fails += 1
            row = {"target_R": target, "n_rules": n, "seeds": len(a.seeds), "failures": fails,
                   "R_min": min(rs) if rs else None, "R_max": max(rs) if rs else None,
                   "R_mean": round(sum(rs) / len(rs), 3) if rs else None}
            report.append(row)
            print(row)
        if a.out:
            a.out.write_text(json.dumps(report, indent=1) + "\n")
    elif a.step == "episode":
        ep = make_episode(a.id, a.seed, a.n_rules)
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / f"episode_{a.id}.json").write_text(json.dumps(ep) + "\n")
        (a.out / f"trajectory_{a.id}.js").write_text(trajectory_script(ep))
        print(a.id, "R", ep["R"], "rules", a.n_rules, "scored", ep["scored"],
              "stage chars", [sum(len(m["text"]) for m in s["messages"]) for s in ep["stages"]])
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
