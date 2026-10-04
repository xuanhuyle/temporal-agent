"""tmk-long-horizon v1: does executing historical selves add information beyond memory, retrieval and inspection?

One generic environment (a fictional procurement desk, "Larkspur Robotics") with exact ground truth. A trajectory is
16 stages; each stage brings inbox messages and purchase requests that the agent must decide. The agent's live state
is a bounded persistent memory plus a bounded working context; when the context overflows, the *model itself* rewrites
its memory (generic compaction prompt, no knowledge of the future probes) and the working context is discarded. The
raw archive (every message, request and decision) is immutable and later searchable by every condition.

Model calls happen outside this module (Claude Code workflow subagents). This module generates episodes and their
ground truth, renders workflow scripts with the data embedded, converts checkpoints to ``AgentState`` / forks repairs
with the existing primitive, and scores everything.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import replace
from pathlib import Path
from typing import Any

from multiplicity import AgentState, Mutation, TemporalMultiplicity

REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = REPO_ROOT / "experiments" / "multiplicity_long_horizon"
N_STAGES = 16
CTX_MAX = 7000  # working-context budget (chars) before compaction
MEM_MAX = 1500  # persistent-memory budget (chars) the compactor must respect
FIELDS = ("currency", "approvers", "carrier", "notify", "hold")
CARRIERS = ("standard", "ColdLink", "Brightway Freight", "Tamar Couriers")
NOTIFY = ("client_site_lead", "harbour_master", "account_manager")

# ------------------------------------------------------------------ the world (fictional)
VENDORS = ["Halvorsen Marine", "Okafor Fasteners", "Brandt Hydraulik", "Tidewater Polymers", "Quill & Sons Electrical",
           "Meridian Bearings", "Saltash Castings", "Vintry Sensors", "Kestrel Pneumatics", "Ardent Optics",
           "Pell Industrial Supply", "Corbel Steelworks", "Lindqvist Tools", "Rowan Cable Co."]
CURRENCY_FOR = {"Halvorsen Marine": "NOK", "Brandt Hydraulik": "CHF", "Quill & Sons Electrical": "GBP",
                "Tidewater Polymers": "USD", "Lindqvist Tools": "SEK", "Saltash Castings": "GBP"}
CLIENTS = ["Project Tern", "Corvid Labs", "Ashgrove Hospital retrofit", "Port of Elsby works", "Fenwick Dairy line 3",
           "Hollin Water treatment", "Marrow Rail depot", "internal R&D"]
DEFAULT_SITE = "Larkspur main warehouse"
SITES = ["Pier 7", "Dock 4", "Hollin plant gate B", "Elsby container yard", "R&D lab (building C)"]
HARBOUR_SITES = ["Pier 7", "Dock 4", "Elsby container yard"]
ITEMS = {
    "fasteners": ["M12 hex bolts (box of 200)", "stainless rivets (box of 500)", "M8 flange nuts (box of 400)"],
    "bearings": ["6204 deep-groove bearings", "pillow-block bearings", "linear bearing carriages"],
    "cabling": ["shielded control cable (100 m)", "PUR drag-chain cable (50 m)", "patch leads (pack of 50)"],
    "sensors": ["inductive proximity sensors", "laser distance sensors", "pressure transducers"],
    "steel stock": ["S355 flat bar", "galvanised angle iron", "precision ground shafting"],
    "pneumatic fittings": ["push-in fittings 8 mm", "solenoid valve manifolds", "pneumatic tubing (100 m)"],
    "optics": ["M12 machine-vision lenses", "polarising filters", "ring lights"],
    "lifting gear": ["chain hoists (2 t)", "mooring shackles", "round lifting slings"],
    "pressure vessels": ["air receiver tanks (500 L)", "hydraulic accumulators", "nitrogen cylinders racks"],
    "fall-arrest harnesses": ["full-body harnesses", "self-retracting lifelines", "anchor straps"],
    "epoxy resins": ["two-part epoxy kits", "potting resin (5 kg)", "laminating resin drums"],
    "adhesive cartridges": ["structural adhesive cartridges", "anaerobic threadlocker packs", "MS-polymer cartridges"],
    "sealant kits": ["polysulphide sealant kits", "two-part silicone kits", "flange sealant tubes"],
}
NORMAL_CATS = ["fasteners", "bearings", "cabling", "sensors", "steel stock", "pneumatic fittings", "optics"]
SAFETY_POOL = ["lifting gear", "pressure vessels", "fall-arrest harnesses"]
COLD_POOL = ["epoxy resins", "adhesive cartridges", "sealant kits"]
PEOPLE = {"finance": "Priya Natarajan (Finance)", "ops": "Marco Bellini (Ops lead)", "safety": "Jun Takeda (Safety)",
          "logistics": "Aisha Rahman (Logistics)", "account": "Helen Oduya (Account management)",
          "qa": "Rui Costa (Quality)", "assembly": "Tomas Varga (Assembly)", "it": "IT Service Desk",
          "ceo": "Office of the COO"}
REQUESTERS = ["Dana Whitlock (Assembly)", "Ibrahim Saleh (Maintenance)", "Grace Lin (R&D)", "Owen Pryce (Field service)",
              "Mei Okonkwo (Projects)", "Lars Ek (Test lab)"]
DATES = ["Mon 3 Mar", "Mon 10 Mar", "Mon 17 Mar", "Mon 24 Mar", "Mon 31 Mar", "Mon 7 Apr", "Mon 14 Apr", "Tue 22 Apr",
         "Mon 28 Apr", "Tue 6 May", "Mon 12 May", "Mon 19 May", "Tue 27 May", "Mon 2 Jun", "Mon 9 Jun", "Mon 16 Jun"]

FILLER = [
    "The new label printer on the dock is finally working, so no more handwritten pallet tags.",
    "Reminder that the quarterly stock count is the last Friday of the month.",
    "Thanks again for turning the Fenwick request around so quickly last week.",
    "I'm out Thursday afternoon for a dentist appointment, Aisha can cover.",
    "Coffee machine on level 2 is fixed, for anyone who was wondering.",
    "The forecast meeting moved to 14:00 because of the board call.",
    "We're still waiting on the revised freight quote, should land tomorrow.",
    "Let me know if anything looks off in the shared tracker.",
    "Parking on the east side is closed Wednesday for resurfacing.",
    "Hope the move to the new ERP screens is going OK on your side.",
]
NOISE = [
    ("it", "Planned maintenance", "The ERP will be read-only on Saturday 06:00-10:00 for a database upgrade. Draft POs are saved automatically; nothing to do on your side."),
    ("ceo", "Q2 priorities", "Thanks all for a strong quarter. Priorities for Q2: shorten average PO turnaround to under two days, finish the supplier scorecard pilot, and keep the Elsby works on schedule. Town hall on Friday at 16:00."),
    ("finance", "Month-end close", "Month-end close starts Wednesday. Please make sure goods receipts are booked by Tuesday evening so accruals are right. Open POs older than 90 days will be reviewed."),
    ("logistics", "Dock schedule", "Inbound dock is tight this week: two container deliveries on Tuesday and the Saltash castings on Thursday morning. If you expect anything bulky, give me a shout so I can slot it."),
    ("assembly", "Line 2 status", "Line 2 is back up after the gearbox swap. We burned through more M8 fasteners than planned, so expect a top-up request from me soon."),
    ("qa", "Supplier scorecard", "First supplier scorecard draft is in the shared folder. On-time delivery is the weakest metric (81%). Comments welcome by Friday."),
    ("account", "Customer visit", "Corvid Labs are visiting on the 24th for a factory tour. Nothing needed from procurement, just a heads-up in case you see unfamiliar faces."),
    ("ops", "Team update", "Welcome to Freya, who joins Ops on Monday as a planner. She'll shadow the desk for a few days to learn how requests flow."),
    ("it", "Phishing test", "Reminder: we'll run a phishing simulation this month. Report suspicious emails with the button in your mail client; don't forward them."),
    ("finance", "Budget re-forecast", "Re-forecast submitted. Direct materials budget for the half is EUR 1.42M; we're at 46% spend. No action needed, just context."),
    ("logistics", "Forklift training", "Forklift refresher training is on the 15th. If anyone from the desk needs to sign for deliveries on the dock, you'll need the refresher."),
    ("assembly", "Kanban cards", "We're moving the small-parts kanban to the new cards next week. Reorder points don't change, only the card design."),
    ("qa", "Calibration", "Annual calibration of the torque tools is due. The lab will send them out in two batches so the line never runs short."),
    ("ceo", "Office move", "Facilities confirmed the procurement desk moves to the second floor on the 30th. Boxes arrive the week before."),
    ("account", "Pipeline", "Two quotes out this week: Marrow Rail depot phase 2 and a small retrofit for Ashgrove. If they land, materials demand jumps in June."),
    ("finance", "Expense tool", "The expense tool now requires a cost centre on every claim. This does not affect POs."),
    ("ops", "Holiday cover", "Easter cover: Marco on the 18th, Freya on the 21st. The desk stays staffed; turnaround targets don't change."),
    ("logistics", "Pallet returns", "We have 40 empty pallets to return to Rowan Cable Co. If a Rowan truck is coming anyway, ask them to take them back."),
    ("it", "Laptop refresh", "Laptop refresh for the procurement team is scheduled for May. You'll get a calendar invite for a 30-minute swap slot."),
    ("qa", "Incoming inspection", "Incoming inspection backlog is down to two days. Thanks to everyone who helped on Saturday."),
    ("assembly", "Overtime", "We'll run Saturday overtime on Line 1 for the next three weeks to catch up on the Tern build."),
    ("account", "Feedback", "Hollin Water sent a nice note about the last delivery arriving early. Passing it on!"),
    ("ceo", "Sustainability", "We're starting to track supplier carbon data. No change to purchasing decisions yet; the team will share a template later this year."),
    ("finance", "Duplicate invoices", "We caught two duplicate invoices last month. Please always quote the PO number in correspondence with vendors."),
]
DISTRACTOR_RULES = [
    ("finance", "PO template", "From Monday please use the new PO template (v3). It has a mandatory 'requester cost centre' field; the old template will be rejected by the ERP."),
    ("ops", "Vendor visits", "All vendor visits now need to be booked through reception at least 24 h ahead, so security can issue badges."),
    ("finance", "Spend report", "The monthly spend-by-category report is due on the 5th working day. Please export it from the ERP dashboard and drop it in the finance folder."),
    ("qa", "Certificates", "For castings, keep asking vendors for material certificates (3.1) with the delivery. File them under the PO number."),
    ("logistics", "Delivery windows", "Inbound deliveries should be booked between 07:00 and 15:00. Late trucks are turned away by the gatehouse."),
]


def _param_noise(rng: random.Random, date: str, past: list[str]) -> str:
    """Bulky, realistic procurement chatter with random specifics (no instructions that affect decisions)."""
    v = rng.sample(VENDORS, 4)
    k = rng.randrange(8)
    if k == 0 and past:
        ids = rng.sample(past, min(3, len(past)))
        lines = "\n".join(f"- {i} ({rng.choice(VENDORS)}): ETA slipped to {rng.choice(DATES)}, vendor blames "
                          f"{rng.choice(['raw material', 'a short shipment', 'customs paperwork', 'a machine breakdown'])}"
                          for i in ids)
        return _msg("ops", "Expediting list", f"Open items to chase this week:\n{lines}\nPlease nudge if you have "
                    f"contacts there.", date)
    if k == 1:
        slots = "\n".join(f"- {h}:00 {x} ({rng.choice(['2 pallets', 'a 20ft container', 'loose cartons', '1 crate'])})"
                           for h, x in zip(sorted(rng.sample(range(7, 15), 3)), v))
        return _msg("logistics", "Inbound dock plan", f"Inbound plan for {date}:\n{slots}\nGate opens 06:45.", date)
    if k == 2:
        cat = rng.choice(NORMAL_CATS)
        return _msg("finance", f"{v[0]} price list", f"{v[0]} sent their new price list: +{rng.randint(2, 9)}% on {cat} "
                    f"from next month, existing POs honoured. Worth checking whether {v[1]} can match before we "
                    f"reorder.", date)
    if k == 3:
        return _msg("assembly", f"Line {rng.randint(1, 3)} weekly", f"OEE last week {rng.randint(61, 88)}%. Downtime "
                    f"mostly {rng.choice(['changeovers', 'a jammed feeder', 'waiting for parts', 'a sensor fault'])}. "
                    f"Scrap rate {rng.randint(1, 4)}.{rng.randint(0, 9)}%. Nothing for the desk this week.", date)
    if k == 4:
        cat = rng.choice(NORMAL_CATS)
        return _msg("assembly", "Low stock", f"Low stock alert: {rng.choice(ITEMS[cat])} - {rng.randint(3, 15)} left, "
                    f"reorder point {rng.randint(16, 40)}. A request will follow once the planner confirms quantities.",
                    date)
    if k == 5:
        return _msg("account", f"{v[0]} account rep", f"{v[0]} has a new account rep, {rng.choice(['Nadia', 'Felix', 'Oskar', 'Leila', 'Bram'])} "
                    f"{rng.choice(['Moreau', 'Hartmann', 'Silva', 'Novak', 'Byrne'])}. Introductory call is next week; "
                    f"they want to discuss annual volumes.", date)
    if k == 6:
        return _msg("finance", "Invoice query", f"Invoice {rng.randint(10000, 99999)} from {v[0]} doesn't match the "
                    f"received quantity ({rng.randint(10, 90)} vs {rng.randint(10, 90)}). I've raised a query with them; "
                    f"no need to hold anything.", date)
    if k == 7:
        return _msg("logistics", f"{v[0]} closure", f"{v[0]} is closed on {rng.choice(DATES)} for a national holiday. "
                    f"Their lead times are +2 days that week. {rng.choice(FILLER)}", date)
    items = rng.sample(NOISE, 3)
    return _msg("ops", "Desk stand-up notes", f"- {items[0][2]}\n- {items[1][2]}\n- {items[2][2]}", date)


def _amount(rng: random.Random, lo: int, hi: int) -> int:
    return int(round(rng.uniform(lo, hi) / 10.0)) * 10


def _msg(sender_key: str, subject: str, body: str, date: str) -> str:
    return f"[{date}] From: {PEOPLE[sender_key]} | Subject: {subject}\n{body}"


# ------------------------------------------------------------------ rules (ground truth)
def _rule_messages(rule: dict[str, Any], rng: random.Random, date: str) -> str:
    k, p = rule["kind"], rule["params"]
    f1, f2 = rng.sample(FILLER, 2)
    aside = rule["style"] == "aside"
    if k == "CUR":
        if aside:
            return _msg("logistics", "re: pallet labels",
                        f"{f1} Also, small thing from {p['vendor']}'s accounts team: their bank keeps bouncing our "
                        f"EUR transfers, so from now on we pay {p['vendor']} in {p['currency']}. {f2}", date)
        return _msg("finance", f"{p['vendor']} payment currency",
                    f"Please note: purchases from {p['vendor']} are to be paid in {p['currency']} going forward "
                    f"(their banking arrangement changed). All other vendors stay on EUR.", date)
    if k == "SAFETY":
        items = rng.sample(NOISE, 3)
        return _msg("ops", "Ops weekly sync - notes",
                    f"1. {items[0][2]}\n2. {items[1][2]}\n3. Jun reminded everyone: any PO for {p['cats'][0]} or "
                    f"{p['cats'][1]} needs the safety officer's co-sign, whatever the amount.\n4. {items[2][2]}\n"
                    f"5. AOB: {f1}", date)
    if k == "CARRIER":
        if aside:
            return _msg("account", f"{p['client']} kickoff",
                        f"Kickoff with {p['client']} went well. {f1} One practical point from their contract: their "
                        f"sites only accept Brightway Freight's tracked service, so every delivery for {p['client']} "
                        f"has to go via Brightway Freight. {f2}", date)
        return _msg("account", f"{p['client']} contract - logistics clause",
                    f"Contract signed. One clause affects procurement directly: every delivery for {p['client']} must "
                    f"go through Brightway Freight. Please make sure POs for {p['client']} specify Brightway Freight.",
                    date)
    if k == "COLD":
        if aside:
            return _msg("qa", "re: incoming inspection",
                        f"{f1} By the way, we lost a batch of {p['cat']} last month because it sat in a hot trailer, so "
                        f"{p['cat']} should ship with ColdLink from now on. {f2}", date)
        return _msg("qa", f"{p['cat']} storage incident",
                    f"We lost a batch of {p['cat']} last month because it sat in a hot trailer. Effective immediately, "
                    f"all {p['cat']} ship via ColdLink, no exceptions.", date)
    if k == "SUB":
        return _msg("account", f"Call summary - {p['client']}",
                    f"- They're happy with lead times.\n- {f1}\n- They asked that if we ever substitute a part on one of "
                    f"their orders, their site lead is notified at least 48 h in advance. We agreed.\n- Next review in Q3.",
                    date)
    if k == "HARBOUR":
        return _msg("logistics", f"{p['site']} access",
                    f"{f1} Heads-up: the crane at {p['site']} is now booked through the port authority, so for any "
                    f"delivery to {p['site']} the harbour master has to be notified on the PO. {f2}", date)
    if k == "FIN_T":
        return _msg("finance", "Approval thresholds",
                    "To reduce bottlenecks, Finance co-approval now applies only to POs of EUR 50,000 or more "
                    "(previously 20,000). This is a threshold change only.", date)
    if k == "HOLD":
        return _msg("finance", f"{p['vendor']} - hold",
                    f"Don't place any new orders with {p['vendor']} until their quality audit closes. I'll tell you "
                    f"when it's done.", date)
    if k == "HOLD_END":
        return _msg("finance", f"re: {p['vendor']} - hold", f"Audit closed, all clear. {p['vendor']} is back to "
                    f"normal ordering.", date)
    if k == "STRIKE":
        return _msg("logistics", "Standard carrier strike",
                    "Our standard carrier is on strike; until I say otherwise, route shipments that would go standard "
                    "via Tamar Couriers instead.", date)
    if k == "STRIKE_END":
        return _msg("logistics", "re: Standard carrier strike", "Strike's over. Back to the standard carrier.", date)
    raise ValueError(k)


def truth(ep: dict[str, Any], task: dict[str, Any], t: int) -> dict[str, Any]:
    """Correct decision for ``task`` given every instruction received up to and including stage ``t``."""
    active = [r for r in ep["rules"] if r["stage"] <= t]
    fin_t = 50000 if any(r["kind"] == "FIN_T" for r in active) else 20000
    out = {"currency": "EUR", "approvers": ["ops"], "carrier": "standard", "notify": [], "hold": False}
    on = {r["kind"]: r for r in active}
    for r in active:
        p = r["params"]
        if r["kind"] == "CUR" and task["vendor"] == p["vendor"]:
            out["currency"] = p["currency"]
        if r["kind"] == "SAFETY" and task["category"] in p["cats"]:
            out["approvers"].append("safety")
        if r["kind"] == "CARRIER" and task["client"] == p["client"]:
            out["carrier"] = "Brightway Freight"
        if r["kind"] == "SUB" and task["client"] == p["client"] and task["substitution"]:
            out["notify"].append("client_site_lead")
        if r["kind"] == "HARBOUR" and task["site"] == p["site"]:
            out["notify"].append("harbour_master")
    for r in active:  # cold-chain wins over client carrier (never both in generated tasks)
        if r["kind"] == "COLD" and task["category"] == r["params"]["cat"]:
            out["carrier"] = "ColdLink"
    if task["amount"] >= fin_t:
        out["approvers"].append("finance")
    hold = [r for r in active if r["kind"] == "HOLD" and r["params"]["vendor"] == task["vendor"]]
    if hold and not any(r["kind"] == "HOLD_END" and r["params"]["vendor"] == task["vendor"] for r in active):
        out["hold"] = True
    if out["carrier"] == "standard" and "STRIKE" in on and "STRIKE_END" not in on:
        out["carrier"] = "Tamar Couriers"
    out["approvers"] = sorted(set(out["approvers"]))
    out["notify"] = sorted(set(out["notify"]))
    return out


def request_text(task: dict[str, Any]) -> str:
    sub = f"{task['substitution']}" if task["substitution"] else "none"
    return (f"{task['id']} | requester: {task['requester']} | vendor: {task['vendor']} | item: {task['qty']} x "
            f"{task['item']} (category: {task['category']}) | amount: EUR {task['amount']:,} | for: {task['client']} | "
            f"deliver to: {task['site']} | substitution: {sub}")


# ------------------------------------------------------------------ episode generation
def make_episode(ep_id: str, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    cur_vendors = rng.sample(list(CURRENCY_FOR), 2)
    others = [v for v in VENDORS if v not in cur_vendors]
    hold_vendor = rng.choice(others)
    plain_vendors = [v for v in others if v != hold_vendor]
    clients = rng.sample([c for c in CLIENTS if c != "internal R&D"], 2)
    carrier_client, sub_client = clients
    plain_clients = [c for c in CLIENTS if c not in clients]
    safety_cats = rng.sample(SAFETY_POOL, 2)
    cold_cat = rng.choice(COLD_POOL)
    harbour_site = rng.choice(HARBOUR_SITES)
    plain_sites = [DEFAULT_SITE] + [s for s in SITES if s != harbour_site and s not in HARBOUR_SITES]

    probe_rules = [
        {"kind": "CUR", "params": {"vendor": cur_vendors[0], "currency": CURRENCY_FOR[cur_vendors[0]]}},
        {"kind": "CUR", "params": {"vendor": cur_vendors[1], "currency": CURRENCY_FOR[cur_vendors[1]]}},
        {"kind": "SAFETY", "params": {"cats": safety_cats}},
        {"kind": "CARRIER", "params": {"client": carrier_client}},
        {"kind": "COLD", "params": {"cat": cold_cat}},
        {"kind": "SUB", "params": {"client": sub_client}},
        {"kind": "HARBOUR", "params": {"site": harbour_site}},
    ]
    rng.shuffle(probe_rules)
    intro_stages = sorted(rng.sample(range(1, 9), len(probe_rules)))  # all probe rules arrive in stages 1-8
    for i, (r, st) in enumerate(zip(probe_rules, intro_stages)):
        r.update(id=f"R{i + 1}", stage=st, probe=True, style=rng.choice(["aside", "formal"]),
                 reinforced=rng.random() < 0.4)
    fin_stage, hold_stage, strike_stage = rng.randint(9, 11), rng.randint(4, 7), rng.randint(9, 12)
    extra = [
        {"id": "X1", "kind": "FIN_T", "params": {}, "stage": fin_stage},
        {"id": "X2", "kind": "HOLD", "params": {"vendor": hold_vendor}, "stage": hold_stage},
        {"id": "X3", "kind": "HOLD_END", "params": {"vendor": hold_vendor}, "stage": hold_stage + rng.randint(4, 6)},
        {"id": "X4", "kind": "STRIKE", "params": {}, "stage": strike_stage},
        {"id": "X5", "kind": "STRIKE_END", "params": {}, "stage": strike_stage + 2},
    ]
    for r in extra:
        r.update(probe=False, style="formal", reinforced=False)
    rules = probe_rules + extra
    ep: dict[str, Any] = {"id": ep_id, "seed": seed, "rules": rules, "stages": []}

    distractors = rng.sample(DISTRACTOR_RULES, len(DISTRACTOR_RULES))
    noise = rng.sample(NOISE, len(NOISE))
    req_no = 400 + rng.randint(0, 50)
    msg_no = 0
    past_ids: list[str] = []

    def plain_task(force: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal req_no
        req_no += rng.randint(1, 4)
        cat = rng.choice(NORMAL_CATS)
        t = {"id": f"REQ-{req_no:04d}", "requester": rng.choice(REQUESTERS), "vendor": rng.choice(plain_vendors),
             "category": cat, "qty": rng.choice([5, 10, 12, 20, 24, 40, 50, 100]), "client": rng.choice(plain_clients),
             "site": rng.choice(plain_sites), "substitution": None, "amount": _amount(rng, 2000, 19000)}
        t.update(force or {})
        t["item"] = rng.choice(ITEMS[t["category"]])
        if t["substitution"]:
            t["substitution"] = f"{t['item']} replaced by an equivalent from another line (vendor shortage)"
        return t

    def trigger(rule: dict[str, Any]) -> dict[str, Any]:
        p = rule["params"]
        return {"CUR": {"vendor": p.get("vendor")}, "SAFETY": {"category": (p.get("cats") or [None])[0]},
                "CARRIER": {"client": p.get("client")}, "COLD": {"category": p.get("cat")},
                "SUB": {"client": p.get("client"), "substitution": True},
                "HARBOUR": {"site": p.get("site")}, "HOLD": {"vendor": p.get("vendor")}}.get(rule["kind"], {})

    for s in range(1, N_STAGES + 1):
        date = DATES[s - 1]
        msgs: list[str] = [_rule_messages(r, rng, date) for r in rules if r["stage"] == s]
        if s in (2, 5, 8, 11, 14) and distractors:
            d = distractors.pop()
            msgs.append(_msg(d[0], d[1], d[2], date))
        while len(msgs) < 5:
            if noise and rng.random() < 0.5:
                n = noise.pop()
                msgs.append(_msg(n[0], n[1], n[2], date))
            else:
                msgs.append(_param_noise(rng, date, past_ids))
        rng.shuffle(msgs)
        messages = []
        for m in msgs:
            msg_no += 1
            messages.append({"id": f"M-{msg_no:03d}", "text": m})
        # lifetime requests: mostly plain; salient/reinforced rules recur after introduction
        reqs = []
        live = [r for r in rules if r["stage"] < s and r["kind"] in ("CUR", "SAFETY", "CARRIER", "COLD", "SUB", "HARBOUR")
                and r["reinforced"]] + [r for r in rules if r["kind"] == "HOLD" and r["stage"] < s]
        for _ in range(2):
            force = None
            if live and rng.random() < 0.45:
                force = trigger(rng.choice(live))
            if rng.random() < 0.3:
                (force := force or {}).update(amount=_amount(rng, 21000, 95000))
            reqs.append(plain_task(force))
        past_ids += [r["id"] for r in reqs]
        ep["stages"].append({"stage": s, "date": date, "messages": messages,
                             "requests": [dict(r, text=request_text(r)) for r in reqs]})

    # probes (dev, shown at failure reveal / executed at checkpoints) and held-out tasks (final evaluation only)
    def probes_for(rule: dict[str, Any], n: int, base: int) -> list[dict[str, Any]]:
        out = []
        for j in range(n):
            force = trigger(rule)
            if rule["kind"] == "SAFETY":
                force = {"category": rule["params"]["cats"][j % 2]}
            t = plain_task(force)
            t["id"] = f"REQ-{base + 10 * int(rule['id'][1:]) + j + 1}"
            t["rule"], t["text"] = rule["id"], request_text(t)
            out.append(t)
        return out

    ep["dev_probes"] = [t for r in probe_rules for t in probes_for(r, 2, 8000)]
    ep["heldout"] = [t for r in probe_rules for t in probes_for(r, 3, 9000)]
    _check_invariance(ep)
    return ep


def _check_invariance(ep: dict[str, Any]) -> None:
    """Probe target fields must not depend on when (after the rule's introduction) the probe is asked."""
    rules = {r["id"]: r for r in ep["rules"]}
    for t in ep["dev_probes"] + ep["heldout"]:
        r = rules[t["rule"]]
        f = target_field(r)
        vals = {json.dumps(truth(ep, t, s)[f]) for s in range(r["stage"], N_STAGES + 1)}
        assert len(vals) == 1, (t["id"], f, vals)
        assert truth(ep, t, N_STAGES)[f] != truth(ep, t, 0)[f], (t["id"], "probe must differ from default")


def target_field(rule: dict[str, Any]) -> str:
    return {"CUR": "currency", "SAFETY": "approvers", "CARRIER": "carrier", "COLD": "carrier", "SUB": "notify",
            "HARBOUR": "notify"}[rule["kind"]]


S0_MEMORY = {
    "rules": ["Default payment currency is EUR.",
              "Ops approves every PO; Finance co-approves POs of EUR 20,000 or more.",
              "Default carrier is standard.",
              "Put a request on hold only if there is an active hold instruction for that vendor."],
    "commitments": [],
    "open_items": [],
    "notes": ["Role: procurement desk agent for Larkspur Robotics. Decide each purchase request."],
}


# ------------------------------------------------------------------ scoring
def norm(field: str, v: Any) -> Any:
    if field in ("approvers", "notify"):
        return sorted({str(x).strip().lower() for x in (v or []) if str(x).strip().lower() not in ("", "none")})
    if field == "hold":
        return bool(v) if not isinstance(v, str) else v.strip().lower() == "true"
    return str(v or "").strip().lower()


def field_ok(ep: dict[str, Any], task: dict[str, Any], decision: dict[str, Any] | None, field: str, t: int) -> bool:
    if not decision:
        return False
    return norm(field, decision.get(field)) == norm(field, truth(ep, task, t)[field])


def decisions_by_id(out: Any) -> dict[str, dict[str, Any]]:
    ds = (out or {}).get("decisions") if isinstance(out, dict) else None
    return {str(d.get("request_id", "")).strip(): d for d in ds or [] if isinstance(d, dict)}


# ------------------------------------------------------------------ checkpoints -> AgentState (existing primitive)
def checkpoint_state(cp: dict[str, Any]) -> AgentState:
    """Explicit executable state of one checkpoint: memory entries are facts, working context is context."""
    st = AgentState(seq=cp["stage"])
    for sec in ("rules", "notes"):
        for i, e in enumerate(cp["memory"].get(sec, [])):
            st = st.with_fact(f"mem:{sec}:{i}", e, known_at=cp["stage"])
    st = st.with_context("working_context", tuple(r["id"] for r in cp["context"]))
    return replace(st, commitments=tuple(cp["memory"].get("commitments", [])),
                   goals=tuple(cp["memory"].get("open_items", [])),
                   metadata=(("checkpoint", cp["id"]),))


def repaired(cp: dict[str, Any], entry: str, replace_key: str | None = None) -> dict[str, Any]:
    """Fork the current checkpoint with one restored memory entry (TemporalMultiplicity.fork + mutations)."""
    tm = TemporalMultiplicity(backend=None)
    root = tm.snapshot(checkpoint_state(cp))
    muts: tuple[Mutation, ...] = ((Mutation(f"forget.{replace_key}", None),) if replace_key else ()) + (
        Mutation("knowledge.mem:rules:restored", entry),)
    st = tm.branch_state(tm.fork(root, mutations=muts))
    mem = {k: list(v) for k, v in cp["memory"].items()}
    if replace_key:
        _, sec, idx = replace_key.split(":")
        mem[sec] = [e for i, e in enumerate(mem[sec]) if i != int(idx)]
    mem["rules"] = mem.get("rules", []) + [entry]
    facts = {f.key for f in st.knowledge}
    assert "mem:rules:restored" in facts and (not replace_key or replace_key not in facts)
    return {**cp, "id": cp["id"] + "+repair", "memory": mem}


# ------------------------------------------------------------------ workflow scripts (data embedded; no ground truth)
RUNTIME = EXP_DIR / "runtime.js"


def subject_view(ep: dict[str, Any]) -> dict[str, Any]:
    """Only what subject prompts are built from: message/request texts and ids. No rules, tags or answers."""
    return {"id": ep["id"],
            "stages": [{"stage": s["stage"], "date": s["date"], "messages": s["messages"],
                        "requests": [{"id": r["id"], "text": r["text"]} for r in s["requests"]]} for s in ep["stages"]],
            "dev_probes": [{"id": t["id"], "text": t["text"]} for t in ep["dev_probes"]]}


def workflow_script(name: str, description: str, phases: list[str], data: dict[str, Any], body: str) -> str:
    meta = {"name": name, "description": description, "phases": [{"title": p} for p in phases]}
    return (f"export const meta = {json.dumps(meta)}\nconst DATA = {json.dumps(data)}\n" + RUNTIME.read_text()
            + "\n" + body + "\n")


def trajectory_script(ep: dict[str, Any], eval_reps: int) -> str:
    data = {"ctx_max": CTX_MAX, "mem_max": MEM_MAX, "s0_memory": S0_MEMORY, "eval_reps": eval_reps,
            "episodes": [subject_view(ep)]}
    return workflow_script(f"tmk-lh-trajectory-{ep['id'].lower()}",
                           "Long-horizon agent lifetime with model compaction + probe battery at every checkpoint",
                           ["Lifetime", "Probe checkpoints"], data,
                           "return await runTrajectory(DATA.episodes[0], DATA.eval_reps)")


# ------------------------------------------------------------------ headroom analysis
RETENTION_KEYS = {"CUR": lambda p: [p["vendor"].split()[0], p["currency"]],
                  "SAFETY": lambda p: [p["cats"][0].split()[0], "safety"],
                  "CARRIER": lambda p: [p["client"].split()[0], "Brightway"],
                  "COLD": lambda p: [p["cat"].split()[0], "ColdLink"],
                  "SUB": lambda p: [p["client"].split()[0], "substitut"],
                  "HARBOUR": lambda p: [p["site"], "harbour"]}


def retained(rule: dict[str, Any], memory: dict[str, Any]) -> bool:
    """Crude string check: does the memory still mention both the rule's entity and its consequence?"""
    text = " ".join(e for v in memory.values() for e in v).lower()
    return all(k.lower() in text for k in RETENTION_KEYS[rule["kind"]](rule["params"]))


def probe_accuracy(ep: dict[str, Any], runs: list[dict[str, Any]], cp_id: str) -> dict[str, float]:
    """Target-field accuracy per probe rule at one checkpoint, pooled over its dev probes and replicates."""
    rules = {r["id"]: r for r in ep["rules"]}
    hits: dict[str, list[bool]] = {}
    for run in runs:
        if run["checkpoint"] != cp_id:
            continue
        dm = decisions_by_id(run["output"])
        for t in ep["dev_probes"]:
            r = rules[t["rule"]]
            hits.setdefault(r["id"], []).append(field_ok(ep, t, dm.get(t["id"]), target_field(r), N_STAGES))
    return {k: sum(v) / len(v) for k, v in hits.items()}


def headroom(ep: dict[str, Any], traj: dict[str, Any]) -> dict[str, Any]:
    cps = traj["checkpoints"]
    final = cps[-1]
    rows = []
    for r in (x for x in ep["rules"] if x.get("probe")):
        curve = [(cp["id"], cp["stage"], probe_accuracy(ep, traj["probe_runs"], cp["id"]).get(r["id"], 0.0),
                  retained(r, cp["memory"]) or any(k.lower() in " ".join(c["text"] for c in cp["context"]).lower()
                                                   for k in RETENTION_KEYS[r["kind"]](r["params"])[:1]))
                 for cp in cps]
        known = [c for c in curve if c[1] >= r["stage"]]
        earlier = [c for c in known if c[0] != final["id"]]
        best = max(earlier, key=lambda c: c[2]) if earlier else None
        cur = curve[-1][2]
        rows.append({"rule": r["id"], "kind": r["kind"], "stage": r["stage"], "style": r["style"],
                     "reinforced": r["reinforced"], "params": r["params"],
                     "pre_intro_acc": max([c[2] for c in curve if c[1] < r["stage"]] or [0.0]),
                     "best_earlier": best and {"checkpoint": best[0], "acc": best[2]}, "final_acc": cur,
                     "headroom": (best[2] - cur) if best else 0.0,
                     "retained_in_final_memory": retained(r, final["memory"]),
                     "curve": [(c[0], round(c[2], 2)) for c in curve]})
    lifetime = []
    stage_tasks = {s["stage"]: s["requests"] for s in ep["stages"]}
    for entry in traj["log"]:
        if entry["kind"] != "decide":
            continue
        dm = decisions_by_id(entry["output"])
        for t in stage_tasks[entry["stage"]]:
            lifetime.append(all(field_ok(ep, t, dm.get(t["id"]), f, entry["stage"]) for f in FIELDS))
    comp = [e for e in traj["log"] if e["kind"] == "compact"]
    return {"episode": ep["id"], "rules": rows, "compactions": len(comp),
            "compaction_stages": [e["stage"] for e in comp], "mem_chars": [e["mem_chars"] for e in comp],
            "lifetime_full_accuracy": sum(lifetime) / max(1, len(lifetime)), "final_checkpoint": final["id"]}


# ------------------------------------------------------------------ investigation cases (conditions A / B / C)
INVESTIGATE = EXP_DIR / "investigate.js"


def archive_of(traj: dict[str, Any]) -> list[dict[str, str]]:
    """Immutable raw record: every message, request and decision the agent ever had in its working context."""
    seen: dict[str, str] = {}
    for cp in traj["checkpoints"]:
        for r in cp["context"]:
            seen.setdefault(r["id"], r["text"])
    return [{"id": k, "text": v} for k, v in seen.items()]


def regressed_rules(hr: dict[str, Any], min_headroom: float = 0.5) -> list[dict[str, Any]]:
    return [r for r in hr["rules"] if r["headroom"] >= min_headroom and r["final_acc"] <= 0.5]


def make_cases(ep: dict[str, Any], traj: dict[str, Any], hr: dict[str, Any], conds: tuple[str, ...] = ("A", "B", "C"),
               steps: dict[str, int] | None = None, max_exec: int = 4) -> list[dict[str, Any]]:
    steps = steps or {"A": 8, "B": 8, "C": 4}
    rules = {r["id"]: r for r in ep["rules"]}
    final = traj["checkpoints"][-1]
    finals = [run for run in traj["probe_runs"] if run["checkpoint"] == final["id"]]
    out = []
    for reg in regressed_rules(hr):
        r = rules[reg["rule"]]
        failing = []
        for t in (x for x in ep["dev_probes"] if x["rule"] == r["id"]):
            for run in finals:  # first replicate in which the current agent got the target field wrong
                d = decisions_by_id(run["output"]).get(t["id"])
                if not field_ok(ep, t, d, target_field(r), N_STAGES):
                    failing.append({"id": t["id"], "text": t["text"], "current_decision": d})
                    break
        if not failing:
            continue
        truth_by_cp = {cp["id"]: {f["id"]: truth(ep, next(t for t in ep["dev_probes"] if t["id"] == f["id"]), cp["stage"])
                                  for f in failing} for cp in traj["checkpoints"]}
        for cond in conds:
            out.append({"id": f"{ep['id']}-{r['id']}", "episode": ep["id"], "rule": r["id"], "cond": cond,
                        "steps": steps[cond], "max_exec": max_exec if cond == "C" else 0, "stages": N_STAGES,
                        "current": final, "failing": failing, "archive": archive_of(traj),
                        "checkpoints": traj["checkpoints"] if cond != "A" else [], "truth": truth_by_cp})
    return out


def investigation_script(cases: list[dict[str, Any]], name: str) -> str:
    data = {"ctx_max": CTX_MAX, "mem_max": MEM_MAX, "s0_memory": S0_MEMORY, "cases": cases}
    body = INVESTIGATE.read_text() + "\nreturn await parallel(DATA.cases.map((c) => () => runCase(c)))"
    return workflow_script(name, "Regression investigation + one-item repair: conditions A/B/C with matched budgets",
                           ["Investigate", "Retrieval", "Execute history"], data, body)


def candidate_entries(ep: dict[str, Any], traj: dict[str, Any], rule_id: str) -> list[dict[str, Any]]:
    """Offline repair candidates for regret: the rule's own raw message plus every historical memory entry that
    mentions the rule's entity (deduplicated)."""
    r = next(x for x in ep["rules"] if x["id"] == rule_id)
    key = RETENTION_KEYS[r["kind"]](r["params"])[0].lower()
    arch = {a["id"]: a["text"] for a in archive_of(traj)}
    out = []
    for s in ep["stages"]:
        if s["stage"] == r["stage"]:
            for m in s["messages"]:
                if all(k.lower() in m["text"].lower() for k in RETENTION_KEYS[r["kind"]](r["params"])):
                    out.append({"source": "archive", "id": m["id"], "text": arch.get(m["id"], m["text"])})
    seen = set()
    for cp in traj["checkpoints"]:
        for sec, entries in cp["memory"].items():
            for i, e in enumerate(entries):
                if key in e.lower() and e not in seen:
                    seen.add(e)
                    out.append({"source": "checkpoint", "checkpoint": cp["id"], "section": sec, "index": i, "text": e})
    return out


def resolve_repair(traj: dict[str, Any], repair: dict[str, Any] | None) -> str | None:
    """Text of the item a condition chose to restore, or None if the choice is invalid."""
    if not repair:
        return None
    if repair.get("source") == "archive":
        return next((a["text"] for a in archive_of(traj) if a["id"] == str(repair.get("id", "")).strip()), None)
    cp = next((c for c in traj["checkpoints"] if c["id"] == repair.get("checkpoint")), None)
    try:
        return cp["memory"][repair["section"]][int(repair["index"])] if cp else None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def replace_key(final: dict[str, Any], repair: dict[str, Any]) -> str | None:
    rep = str((repair or {}).get("replace") or "").strip()
    try:
        sec, idx = rep.split(":")
        return f"mem:{sec}:{int(idx)}" if sec in ("rules", "notes") and int(idx) < len(final["memory"].get(sec, [])) else None
    except ValueError:
        return None


def heldout_script(ep: dict[str, Any], states: list[dict[str, Any]], reps: int, name: str) -> str:
    tasks = [{"id": t["id"], "text": t["text"]} for t in ep["heldout"]]
    data = {"ctx_max": CTX_MAX, "mem_max": MEM_MAX, "s0_memory": S0_MEMORY, "tasks": tasks, "states": states, "reps": reps}
    body = ("const jobs = []\nfor (const s of DATA.states) for (let r = 0; r < DATA.reps; r++) jobs.push({ s, r })\n"
            "const out = await parallel(jobs.map(({ s, r }) => () => callAgent(decidePrompt(s, DATA.tasks), DECISIONS, "
            "`heldout:${s.id}:r${r}`, 'Held-out').then((o) => ({ state: s.id, replicate: r, output: o }))))\n"
            "return out.filter(Boolean)")
    return workflow_script(name, "Held-out evaluation of current, repaired and candidate states", ["Held-out"], data, body)


def heldout_accuracy(ep: dict[str, Any], runs: list[dict[str, Any]], state_id: str, rule_id: str | None) -> float:
    rules = {r["id"]: r for r in ep["rules"]}
    hits = []
    for run in (x for x in runs if x["state"] == state_id):
        dm = decisions_by_id(run["output"])
        for t in ep["heldout"]:
            if rule_id is None or t["rule"] == rule_id:
                hits.append(field_ok(ep, t, dm.get(t["id"]), target_field(rules[t["rule"]]), N_STAGES))
    return sum(hits) / len(hits) if hits else 0.0


def load_result(path: Path) -> Any:
    raw = json.loads(path.read_text())
    res = raw.get("result", raw) if isinstance(raw, dict) else raw
    return json.loads(res) if isinstance(res, str) else res


# ------------------------------------------------------------------ CLI
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("step", choices=["episodes", "trajectory-scripts", "headroom"])
    p.add_argument("--trajectories", nargs="+", type=Path)
    p.add_argument("--ids", nargs="+")
    p.add_argument("--seeds", nargs="+", type=int)
    p.add_argument("--episodes", type=Path)
    p.add_argument("--eval-reps", type=int, default=2)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    if a.step == "episodes":
        eps = [make_episode(i, s) for i, s in zip(a.ids, a.seeds)]
        a.out.write_text(json.dumps({"ctx_max": CTX_MAX, "mem_max": MEM_MAX, "s0_memory": S0_MEMORY, "episodes": eps},
                                    indent=1) + "\n")
    elif a.step == "headroom":
        eps = {e["id"]: e for e in json.loads(a.episodes.read_text())["episodes"]}
        trajs = [load_result(t) for t in a.trajectories]
        out = [headroom(eps[t["episode"]], t) for t in trajs]
        for h in out:
            print(f"\n{h['episode']}: compactions {h['compactions']} at stages {h['compaction_stages']}, mem chars "
                  f"{h['mem_chars']}, lifetime full-decision accuracy {h['lifetime_full_accuracy']:.2f}")
            for r in h["rules"]:
                print(f"  {r['rule']} {r['kind']:8s} st{r['stage']:>2} {r['style']:6s} reinf={r['reinforced']!s:5s} "
                      f"pre={r['pre_intro_acc']:.2f} best={r['best_earlier']} final={r['final_acc']:.2f} "
                      f"headroom={r['headroom']:+.2f} mem={r['retained_in_final_memory']}")
        a.out.write_text(json.dumps(out, indent=1) + "\n")
    else:
        a.out.mkdir(parents=True, exist_ok=True)
        for ep in json.loads(a.episodes.read_text())["episodes"]:
            (a.out / f"trajectory_{ep['id']}.js").write_text(trajectory_script(ep, a.eval_reps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
