"""Analysis of a tmk-hindsight result file, with the pre-registered verdict rule (protocol v0.1).

Pure functions over the JSON rows written by :mod:`hindsight_eval`, so a result
file can be re-analysed without the code that produced it:

    PYTHONPATH=src python -m multiplicity_experiments.hindsight_analysis RESULT.json

Everything in this module was fixed before any real-model run. Changing a
threshold, the unit of analysis or the decision order after a result has been
seen is a new protocol version, and the earlier analysis is kept.

Row classes:

- an *error* row has ``error`` set: no scorable model reply was obtained
  (timeout, over-length reply, provider failure). Some of these may depend on
  the condition (a long deliberation), so they are excluded from the scores,
  limited by their own validity gate, and the verdict must survive re-scoring
  them as wrong in each condition in turn (sensitivity rule below);
- a *model-invalid* row has a reply but no listed choice could be parsed. It
  counts as wrong (and not as a hindsight leak), exactly as in the accuracy
  metric;
- otherwise the row is scored correct, a hindsight leak (the later answer), or
  another wrong answer.

Unit of analysis: the **case**. Repeats of one case resend the same prompt to
the same model and are not independent, so for each case and condition the
score is the mean correctness over the case's *complete pairs* (repeats where
neither condition's row is an error; this keeps the choice-order
counterbalance matched). A case is *isolation-better* if its isolated score is
higher, *baseline-better* if lower, otherwise a *tie*. Pair-level
(case x repeat) McNemar counts are reported as descriptive statistics only.

Verdict (exactly one of three), applied in this order:

1. ``INCONCLUSIVE`` if a validity gate fails: the run is not complete; the
   protocol version, system prompt, user template, choice-order or parse rule,
   dataset, case set or repeat count is not the registered one; the source
   tree was not clean (``git_dirty`` must be false); an error rate or a
   model-invalid rate above ``MAX_ERROR_RATE`` / ``MAX_MODEL_INVALID_RATE`` in
   either condition; or a registered case without a complete pair.
2. ``SUPPORTED_FOR_NEXT_TEST`` if isolation wins across cases: exact one-sided
   sign test p <= ``ALPHA`` on (isolation-better, baseline-better) cases (with
   8 cases this is met by 5-0, 6-0, 7-0, 7-1 or 8-0); in at least half of the
   isolation-better cases most baseline errors are hindsight leaks; and
   isolated accuracy >= ``MIN_ISOLATED_ACCURACY``.
3. ``NO_DISTINCT_ADVANTAGE`` if a *strong* baseline (accuracy >=
   ``MIN_ISOLATED_ACCURACY``) matches or beats isolation: (isolation-better
   cases) - (baseline-better cases) <= ``NO_ADVANTAGE_MARGIN``, cost comparable
   (median per-pair *reported-token* ratio baseline/isolated <=
   ``MAX_COST_RATIO``; unknown token usage is not comparable), and either
   isolated accuracy >= ``MIN_ISOLATED_ACCURACY`` (the task is solvable without
   hindsight and the baseline matches it) or baseline-better cases outnumber
   isolation-better ones (the baseline beats isolation).
4. ``INCONCLUSIVE`` otherwise (a non-significant isolation edge, a weak
   baseline, both conditions failing, cost not comparable or unknown).

Sensitivity rule: if any error rows exist, a verdict other than
``INCONCLUSIVE`` stands only if the same verdict results when the error rows
are re-scored as wrong answers in the baseline only, and again in the
isolated condition only. Otherwise the verdict is ``INCONCLUSIVE``.

Accuracy in the gates and rules is correct / scored rows (complete pairs).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

CONDITIONS = ("baseline", "isolated")
VERDICTS = ("SUPPORTED_FOR_NEXT_TEST", "NO_DISTINCT_ADVANTAGE", "INCONCLUSIVE")

# Registered design (protocol v0.1). hindsight_eval imports these; tests check the prompt hashes match its text.
REGISTERED_PROTOCOL_VERSION = "v0.1"
REGISTERED_DATASET_SHA256 = "e435fa60ebaa8ce719fec2056c149c0de5ed1f01980f4f1c9343671907591973"
REGISTERED_REPEATS = 2
REGISTERED_SYSTEM_PROMPT_SHA256 = "9275528a47f4fa4ae2ed936295bc08b5c3c2ddb7dceb8e4c52dd9f0f6aa47c26"
REGISTERED_USER_TEMPLATE_SHA256 = "10bd61a30a525f7ea24ec6b8dcb8fd461d74a211233243adacaaa792b5780253"
REGISTERED_CHOICE_ORDER_RULE = "sorted on even repeats, reverse-sorted on odd repeats; identical in both conditions of a pair"
REGISTERED_PARSE_RULE_SHA256 = "9cd05d4bfd58c003efddd59d3cffb34bcc586475353740dc8f564e5dc62dc971"

# Pre-registered thresholds (protocol v0.1). Do not tune after seeing results.
MAX_ERROR_RATE = 0.125
MAX_MODEL_INVALID_RATE = 0.125
MIN_ISOLATED_ACCURACY = 0.85
ALPHA = 0.05
NO_ADVANTAGE_MARGIN = 1
MAX_COST_RATIO = 1.25
CEILING_ACCURACY = 1.0  # descriptive flag ("both conditions perfect on scored rows"); never changes the verdict

THRESHOLDS = {
    "unit_of_analysis": "case (repeats averaged)",
    "max_error_rate": MAX_ERROR_RATE,
    "max_model_invalid_rate": MAX_MODEL_INVALID_RATE,
    "min_isolated_accuracy": MIN_ISOLATED_ACCURACY,
    "alpha_one_sided_sign_test": ALPHA,
    "no_advantage_margin_cases": NO_ADVANTAGE_MARGIN,
    "max_cost_ratio_median_pair": MAX_COST_RATIO,
    "registered_repeats": REGISTERED_REPEATS,
    "registered_dataset_sha256": REGISTERED_DATASET_SHA256,
    "registered_system_prompt_sha256": REGISTERED_SYSTEM_PROMPT_SHA256,
    "registered_user_template_sha256": REGISTERED_USER_TEMPLATE_SHA256,
    "error_sensitivity_rule": "verdict must be unchanged with error rows scored wrong in each condition in turn",
}

# Descriptive strata of the registered dataset (never used by the verdict).
STRATA = {
    "post_cutoff_content": {
        # seq 3 records the action actually taken at the cutoff (it equals the justified answer); seq 4 points away
        "decision_recorded": ["vendor-sanction-backfill", "fraud-device-later-takeover", "credit-data-restatement",
                              "routing-map-later-closure", "capacity-forecast-revision"],
        # every post-cutoff event points toward the later answer
        "one_sided": ["incident-network-backfill", "release-policy-changed-later", "access-policy-revision"],
    },
    "kind_of_later_information": {
        "fact_revision": ["incident-network-backfill", "vendor-sanction-backfill", "fraud-device-later-takeover",
                          "credit-data-restatement", "routing-map-later-closure", "capacity-forecast-revision"],
        "rule_change": ["release-policy-changed-later", "access-policy-revision"],
    },
}


# ------------------------------------------------------------------ statistics
def binomial_tail(k: int, n: int) -> float:
    """P(X >= k) for X ~ Binomial(n, 0.5)."""
    if k > n:
        return 0.0
    k = max(k, 0)
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2**n


def mcnemar_exact(b: int, c: int) -> dict[str, float | int]:
    """Exact McNemar / sign test on discordant units: one-sided for b > c, and two-sided."""
    n = b + c
    one_sided = binomial_tail(b, n) if n else 1.0
    two_sided = min(1.0, 2 * min(binomial_tail(b, n), binomial_tail(c, n))) if n else 1.0
    return {"b": b, "c": c, "discordant": n, "p_one_sided_isolated_better": one_sided, "p_two_sided": two_sided}


# ------------------------------------------------------------------- row kinds
def is_error(row: Mapping[str, Any]) -> bool:
    return bool(row.get("error"))


def is_model_invalid(row: Mapping[str, Any]) -> bool:
    return not is_error(row) and row.get("choice") is None


def _tokens(meter: Mapping[str, Any], key: str) -> int | None:
    v = meter.get(key)
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


# -------------------------------------------------------------------- summaries
def summarize(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate metrics per condition.

    ``accuracy`` and ``hindsight_leak_rate`` are over all rows (errors and invalid answers count as not
    correct); ``scored_accuracy`` is over non-error rows, as used by the verdict. For the isolated condition the
    "leak" rate is the no-hindsight base rate of choosing the later answer.
    """
    rows = list(rows)
    out: dict[str, Any] = {}
    for condition in CONDITIONS:
        sel = [r for r in rows if r["condition"] == condition]
        scored = [r for r in sel if not is_error(r)]
        valid = [r for r in sel if r.get("choice") is not None]
        confidences = [float(r["confidence"]) for r in sel if r.get("confidence") is not None]
        meters = [r.get("meter") or {} for r in sel]
        tin = [_tokens(m, "total_input_tokens") for m in meters]
        tout = [_tokens(m, "output_tokens") for m in meters]
        thinking = [(m.get("provider_meta") or {}).get("thinking_tokens") for m in meters]
        thinking = [t for t in thinking if isinstance(t, int) and not isinstance(t, bool)]
        costs = [m.get("cost_usd") for m in meters]
        n = len(sel)
        out[condition] = {
            "n": n,
            "valid_structured_answers": len(valid),
            "strict_json_answers": sum(1 for r in sel if r.get("parse_mode") == "json"),
            "model_invalid_answers": sum(1 for r in sel if is_model_invalid(r)),
            "errors": sum(1 for r in sel if is_error(r)),
            "truncated": sum(1 for r in sel if r.get("truncated")),
            "accuracy": (sum(1 for r in sel if r.get("correct")) / n) if n else None,
            "scored_accuracy": (sum(1 for r in scored if r.get("correct")) / len(scored)) if scored else None,
            "hindsight_leak_rate": (sum(1 for r in sel if r.get("hindsight_leak")) / n) if n else None,
            "hindsight_leaks": sum(1 for r in sel if r.get("hindsight_leak")),
            "other_wrong": sum(1 for r in valid if not r.get("correct") and not r.get("hindsight_leak")),
            "mean_confidence": _mean(confidences),
            "input_tokens_total": sum(v for v in tin if v is not None),
            "output_tokens_total": sum(v for v in tout if v is not None),
            "thinking_tokens_total": sum(thinking) if thinking else None,
            "calls_with_unknown_usage": sum(1 for a, b in zip(tin, tout) if a is None or b is None),
            "cost_usd_total": round(sum(v for v in costs if isinstance(v, (int, float))), 8),
            "mean_prompt_chars": _mean([float(r.get("prompt_chars") or 0) for r in sel]),
        }
    return out


def _by_pair(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, int], dict[str, Mapping[str, Any]]]:
    out: dict[tuple[str, int], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for r in rows:
        out[(r["case_id"], int(r.get("repeat", 0)))][r["condition"]] = r
    return out


def cost_ratio(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Median over pairs of (baseline tokens / isolated tokens), tokens = total input + output.

    Only pairs where both calls succeeded and reported usage enter. If fewer than half of the pairs qualify,
    the prompt-character ratio is used instead (basis ``prompt_chars``) and flagged.
    """
    pairs_ = _by_pair(rows)
    ratios, char_ratios = [], []
    for d in pairs_.values():
        base, iso = d.get("baseline"), d.get("isolated")
        if base is None or iso is None:
            continue
        if base.get("prompt_chars") and iso.get("prompt_chars"):
            char_ratios.append(base["prompt_chars"] / iso["prompt_chars"])
        if is_error(base) or is_error(iso):
            continue
        mb, mi = base.get("meter") or {}, iso.get("meter") or {}
        tb = (_tokens(mb, "total_input_tokens"), _tokens(mb, "output_tokens"))
        ti = (_tokens(mi, "total_input_tokens"), _tokens(mi, "output_tokens"))
        if None in tb or None in ti or sum(ti) == 0:  # type: ignore[arg-type]
            continue
        ratios.append(sum(tb) / sum(ti))  # type: ignore[arg-type]
    total = len(pairs_)
    if ratios and 2 * len(ratios) >= total:
        return {"basis": "reported_tokens", "pairs_used": len(ratios), "pairs": total,
                "ratio": statistics.median(ratios), "min": min(ratios), "max": max(ratios)}
    if char_ratios:
        return {"basis": "prompt_chars", "pairs_used": len(char_ratios), "pairs": total,
                "ratio": statistics.median(char_ratios), "min": min(char_ratios), "max": max(char_ratios)}
    return {"basis": None, "pairs_used": 0, "pairs": total, "ratio": None, "min": None, "max": None}


def pairs(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Descriptive baseline/isolated pairs keyed by (case, repeat). Model-invalid answers count as wrong."""
    out = []
    for (case_id, repeat), d in sorted(_by_pair(rows).items()):
        base, iso = d.get("baseline"), d.get("isolated")
        if base is None or iso is None:
            category = "incomplete"
        elif is_error(base) or is_error(iso):
            category = "error"
        elif base.get("correct") and iso.get("correct"):
            category = "both_correct"
        elif not base.get("correct") and iso.get("correct"):
            category = "baseline_wrong_isolated_correct"
        elif base.get("correct") and not iso.get("correct"):
            category = "baseline_correct_isolated_wrong"
        else:
            category = "both_wrong"
        out.append({
            "case_id": case_id,
            "repeat": repeat,
            "category": category,
            "baseline_choice": base.get("choice") if base else None,
            "isolated_choice": iso.get("choice") if iso else None,
            "baseline_leak": bool(base and base.get("hindsight_leak")),
            "isolated_leak": bool(iso and iso.get("hindsight_leak")),
        })
    return out


def per_case(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One line per case: each condition's score over the case's complete pairs, and the case direction."""
    cases: dict[str, dict[str, Any]] = {}
    for r in rows:
        c = cases.setdefault(r["case_id"], {
            "case_id": r["case_id"],
            "correct_at_cutoff": r.get("correct_at_cutoff"),
            "later_answer": r.get("later_answer"),
            "baseline": {}, "isolated": {},
        })
        c[r["condition"]][int(r.get("repeat", 0))] = r
    out = []
    for cid in sorted(cases):
        c = cases[cid]
        repeats = sorted(set(c["baseline"]) | set(c["isolated"]))
        complete = [k for k in repeats
                    if k in c["baseline"] and k in c["isolated"]
                    and not is_error(c["baseline"][k]) and not is_error(c["isolated"][k])]
        line: dict[str, Any] = {"case_id": cid, "correct_at_cutoff": c["correct_at_cutoff"],
                                "later_answer": c["later_answer"], "complete_pairs": len(complete)}
        for cond in CONDITIONS:
            rs = [c[cond][k] for k in repeats if k in c[cond]]
            scored = [c[cond][k] for k in complete]
            line[f"{cond}_choices"] = ["ERROR" if is_error(r) else r.get("choice") for r in rs]
            line[f"{cond}_n"] = len(rs)
            line[f"{cond}_scored"] = len(scored)
            line[f"{cond}_correct"] = sum(1 for r in scored if r.get("correct"))
            line[f"{cond}_wrong"] = sum(1 for r in scored if not r.get("correct"))
            line[f"{cond}_leaks"] = sum(1 for r in scored if r.get("hindsight_leak"))
            line[f"{cond}_score"] = (line[f"{cond}_correct"] / len(scored)) if scored else None
        bs, iscore = line["baseline_score"], line["isolated_score"]
        if bs is None or iscore is None:
            line["direction"] = "unscored"
        elif iscore > bs:
            line["direction"] = "isolation_better"
        elif bs > iscore:
            line["direction"] = "baseline_better"
        else:
            line["direction"] = "tie"
        line["baseline_errors_mostly_leaks"] = line["baseline_wrong"] > 0 and 2 * line["baseline_leaks"] >= line["baseline_wrong"]
        out.append(line)
    return out


def strata(case_lines: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Descriptive accuracy and leaks per registered stratum (no effect on the verdict)."""
    by_id = {c["case_id"]: c for c in case_lines}
    out: dict[str, Any] = {}
    for family, groups in STRATA.items():
        out[family] = {}
        for group, ids in groups.items():
            lines = [by_id[i] for i in ids if i in by_id]
            entry: dict[str, Any] = {"cases": len(lines)}
            for cond in CONDITIONS:
                scored = sum(c[f"{cond}_scored"] for c in lines)
                entry[f"{cond}_accuracy"] = (sum(c[f"{cond}_correct"] for c in lines) / scored) if scored else None
                entry[f"{cond}_leaks"] = sum(c[f"{cond}_leaks"] for c in lines)
            out[family][group] = entry
    return out


def pattern_of(*, b_cases: int, c_cases: int, leak_cases: int, iso_acc: float | None, base_acc: float | None,
               all_perfect: bool, scored_cases: int) -> str:
    """The run-level pattern named in the experiment brief, from the same case-level facts as the verdict.

    The pattern is descriptive. The verdict for each pattern is set by :func:`decide` (see the results document's
    pattern table): it also depends on significance, baseline strength and cost.
    """
    if scored_cases == 0:
        return "none_no_scored_cases"
    if iso_acc is not None and base_acc is not None and iso_acc < MIN_ISOLATED_ACCURACY and base_acc < MIN_ISOLATED_ACCURACY:
        return "C_both_fail"
    if c_cases > b_cases:
        return "D_baseline_beats_isolated"
    if b_cases - c_cases > NO_ADVANTAGE_MARGIN:
        return "B_isolated_beats_baseline" if 2 * leak_cases >= b_cases else "mixed_isolated_ahead_without_leaks"
    if b_cases > c_cases:
        return "B_within_margin"
    if all_perfect:
        return "A_both_correct"
    return "tie"


# ---------------------------------------------------------------------- verdict
REGISTERED_CASE_IDS = frozenset(i for groups in STRATA["post_cutoff_content"].values() for i in groups)


def _scored_accuracy(case_lines: list[Mapping[str, Any]], cond: str) -> float | None:
    scored = sum(c[f"{cond}_scored"] for c in case_lines)
    return sum(c[f"{cond}_correct"] for c in case_lines) / scored if scored else None


def _gate(payload: Mapping[str, Any], summary: Mapping[str, Any], case_lines: list[Mapping[str, Any]],
          pair_counts: Mapping[str, int]) -> list[str]:
    gate: list[str] = []
    if payload.get("status") != "complete":
        gate.append(f"run status is {payload.get('status')!r}, not 'complete'")
    if payload.get("protocol_version") != REGISTERED_PROTOCOL_VERSION:
        gate.append(f"protocol version {payload.get('protocol_version')!r} is not {REGISTERED_PROTOCOL_VERSION!r}")
    protocol = payload.get("protocol") or {}
    for key, registered in (("system_prompt_sha256", REGISTERED_SYSTEM_PROMPT_SHA256),
                            ("user_template_sha256", REGISTERED_USER_TEMPLATE_SHA256),
                            ("parse_rule_sha256", REGISTERED_PARSE_RULE_SHA256),
                            ("choice_order", REGISTERED_CHOICE_ORDER_RULE)):
        if protocol.get(key) != registered:
            gate.append(f"protocol {key} is not the registered one")
    if (payload.get("code") or {}).get("git_dirty") is not False:
        gate.append("source tree not verified clean (code.git_dirty must be false)")
    dataset = payload.get("dataset") or {}
    if dataset.get("sha256") != REGISTERED_DATASET_SHA256:
        gate.append("dataset is not the registered one (sha256 differs)")
    repeats = protocol.get("repeats")
    if repeats != REGISTERED_REPEATS:
        gate.append(f"repeats {repeats!r} is not the registered {REGISTERED_REPEATS}")
    ids = {c["case_id"] for c in case_lines}
    if ids != REGISTERED_CASE_IDS:
        gate.append(f"case set differs from the registered {len(REGISTERED_CASE_IDS)} cases")
    unscored = [c["case_id"] for c in case_lines if c["direction"] == "unscored"]
    if unscored:
        gate.append(f"{len(unscored)} case(s) without a complete pair")
    for cond in CONDITIONS:
        s = summary.get(cond) or {}
        n = s.get("n") or 0
        if n == 0:
            gate.append(f"no {cond} answers")
            continue
        expected = len(REGISTERED_CASE_IDS) * REGISTERED_REPEATS
        if n != expected:
            gate.append(f"{cond} has {n} rows, expected {expected}")
        if (s.get("errors") or 0) / n > MAX_ERROR_RATE:
            gate.append(f"{cond} error rate {(s.get('errors') or 0) / n:.3f} > {MAX_ERROR_RATE}")
        if (s.get("model_invalid_answers") or 0) / n > MAX_MODEL_INVALID_RATE:
            gate.append(f"{cond} model-invalid rate {(s.get('model_invalid_answers') or 0) / n:.3f} > {MAX_MODEL_INVALID_RATE}")
    if pair_counts.get("incomplete"):
        gate.append(f"{pair_counts['incomplete']} unpaired answers")
    return gate


def _rule(case_lines: list[Mapping[str, Any]], cost: Mapping[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    """The verdict rule proper (after the gates): returns (verdict, reasons, case-level facts)."""
    scored = [c for c in case_lines if c["direction"] != "unscored"]
    b_cases = sum(1 for c in scored if c["direction"] == "isolation_better")
    c_cases = sum(1 for c in scored if c["direction"] == "baseline_better")
    leak_cases = sum(1 for c in scored if c["direction"] == "isolation_better" and c["baseline_errors_mostly_leaks"])
    test = mcnemar_exact(b_cases, c_cases)
    iso_acc, base_acc = _scored_accuracy(case_lines, "isolated"), _scored_accuracy(case_lines, "baseline")
    all_perfect = bool(scored) and all(c["baseline_score"] == 1.0 and c["isolated_score"] == 1.0 for c in scored)
    ratio = cost.get("ratio")
    facts = {
        "cases": len(case_lines),
        "scored_cases": len(scored),
        "case_directions": {d: sum(1 for c in case_lines if c["direction"] == d)
                            for d in ("isolation_better", "baseline_better", "tie", "unscored")},
        "b_cases": b_cases,
        "c_cases": c_cases,
        "leak_cases": leak_cases,
        "sign_test": test,
        "isolated_accuracy": iso_acc,
        "baseline_accuracy": base_acc,
        "cost_ratio": ratio,
        "cost_basis": cost.get("basis"),
        "ceiling": (iso_acc is not None and base_acc is not None
                    and iso_acc >= CEILING_ACCURACY and base_acc >= CEILING_ACCURACY),
        "pattern": pattern_of(b_cases=b_cases, c_cases=c_cases, leak_cases=leak_cases, iso_acc=iso_acc,
                              base_acc=base_acc, all_perfect=all_perfect, scored_cases=len(scored)),
    }
    reasons: list[str] = []
    p = test["p_one_sided_isolated_better"]
    isolation_works = iso_acc is not None and iso_acc >= MIN_ISOLATED_ACCURACY
    strong_baseline = base_acc is not None and base_acc >= MIN_ISOLATED_ACCURACY
    if p <= ALPHA and b_cases > c_cases and 2 * leak_cases >= b_cases and isolation_works:
        reasons.append(
            f"isolation better in {b_cases} of {len(scored)} cases, baseline better in {c_cases} "
            f"(one-sided exact sign test p={p:.4f}); baseline errors are mostly hindsight leaks in {leak_cases} "
            f"of those cases; isolated accuracy {iso_acc:.3f}"
        )
        return "SUPPORTED_FOR_NEXT_TEST", reasons, facts

    comparable_cost = cost.get("basis") == "reported_tokens" and ratio is not None and ratio <= MAX_COST_RATIO
    if (b_cases - c_cases <= NO_ADVANTAGE_MARGIN and comparable_cost and strong_baseline
            and (isolation_works or c_cases > b_cases)):
        if c_cases > b_cases:
            reasons.append(f"a strong baseline (accuracy {base_acc:.3f}) is better than isolation in {c_cases} "
                           f"case(s) and worse in {b_cases}; isolated accuracy {iso_acc:.3f}")
            dr = set(STRATA["post_cutoff_content"]["decision_recorded"])
            if all(c["case_id"] in dr for c in scored if c["direction"] == "baseline_better"):
                reasons.append("note: every baseline-better case records the decision taken in its post-cutoff "
                               "events, which only the baseline sees (threat 11.2; descriptive)")
        else:
            reasons.append(f"a strong baseline matches isolation: isolation better in {b_cases} case(s), baseline "
                           f"better in {c_cases}, net {b_cases - c_cases} <= margin {NO_ADVANTAGE_MARGIN}; isolated "
                           f"accuracy {iso_acc:.3f}, baseline accuracy {base_acc:.3f}")
        reasons.append(f"cost comparable: median pair token ratio baseline/isolated {ratio:.3f} <= {MAX_COST_RATIO}")
        if facts["ceiling"]:
            reasons.append("both conditions are perfect on these items (ceiling; descriptive flag)")
        return "NO_DISTINCT_ADVANTAGE", reasons, facts

    if b_cases - c_cases > NO_ADVANTAGE_MARGIN:
        reasons.append(f"isolation ahead in {b_cases} vs {c_cases} cases, but the support criteria are not met "
                       f"(sign test p={p:.4f}, leak cases {leak_cases}, isolated accuracy {iso_acc})")
    if not strong_baseline:
        reasons.append(f"baseline accuracy {base_acc} < {MIN_ISOLATED_ACCURACY}: not a strong baseline, so a match "
                       "cannot be claimed")
    if not isolation_works and not (c_cases > b_cases and strong_baseline):
        reasons.append(f"isolated accuracy {iso_acc} < {MIN_ISOLATED_ACCURACY} and no strong baseline beats it: "
                       "the comparison is not informative")
    if not comparable_cost:
        reasons.append(f"cost not established as comparable (median pair ratio {ratio}, basis {cost.get('basis')}; "
                       "reported token usage is required)")
    return "INCONCLUSIVE", reasons, facts


def _rescore_errors(rows: list[Mapping[str, Any]], condition: str) -> list[dict[str, Any]]:
    """Copy of the rows with the given condition's error rows scored as wrong, non-leak answers."""
    out = []
    for r in rows:
        r = dict(r)
        if r["condition"] == condition and is_error(r):
            r.update(error=None, choice="<error scored wrong>", correct=False, hindsight_leak=False)
        out.append(r)
    return out


def decide(payload: Mapping[str, Any], summary: Mapping[str, Any], case_lines: list[Mapping[str, Any]],
           pair_list: list[Mapping[str, Any]], cost: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the pre-registered verdict rule. Returns the verdict, the reasons that decided it, and the facts."""
    pair_counts: dict[str, int] = defaultdict(int)
    for p in pair_list:
        pair_counts[p["category"]] += 1
    pb, pc = pair_counts["baseline_wrong_isolated_correct"], pair_counts["baseline_correct_isolated_wrong"]
    verdict, reasons, facts = _rule(case_lines, cost)
    facts.update({
        "pair_categories": dict(sorted(pair_counts.items())),
        "pair_mcnemar_descriptive": mcnemar_exact(pb, pc),
        "thresholds": dict(THRESHOLDS),
        "error_sensitivity": None,
    })
    gate = _gate(payload, summary, case_lines, pair_counts)
    if gate:
        return {"verdict": "INCONCLUSIVE", "reasons": ["validity gate failed: " + "; ".join(gate)], **facts}

    rows = list(payload.get("results") or [])
    if verdict != "INCONCLUSIVE" and any(is_error(r) for r in rows):
        alt = {}
        for cond in CONDITIONS:
            rescored = _rescore_errors(rows, cond)
            alt[cond] = _rule(per_case(rescored), cost_ratio(rescored))[0]
        facts["error_sensitivity"] = {f"errors_scored_wrong_in_{k}": v for k, v in alt.items()}
        if any(v != verdict for v in alt.values()):
            return {"verdict": "INCONCLUSIVE",
                    "reasons": [f"error sensitivity: the rule gives {verdict} as scored, but "
                                + ", ".join(f"{v} with {k} errors scored wrong" for k, v in alt.items())
                                + "; the verdict depends on how errors are treated"],
                    **facts}
    return {"verdict": verdict, "reasons": reasons, **facts}


def analyze(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Full analysis of a result payload (as written by hindsight_eval)."""
    rows = list(payload.get("results") or [])
    summary = summarize(rows)
    case_lines = per_case(rows)
    pair_list = pairs(rows)
    cost = cost_ratio(rows)
    return {
        "summary": summary,
        "cost": cost,
        "per_case": case_lines,
        "strata": strata(case_lines),
        "pairs": pair_list,
        "decision": decide(payload, summary, case_lines, pair_list, cost),
    }


# --------------------------------------------------------------------- markdown
def _fmt(v: Any, digits: int = 3) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def _choices(values: list[Any]) -> str:
    return ", ".join("invalid" if v is None else str(v) for v in values) or "-"


def render_markdown(payload: Mapping[str, Any], analysis: Mapping[str, Any] | None = None) -> str:
    a = analysis or analyze(payload)
    s, d = a["summary"], a["decision"]
    model = payload.get("model") or {}
    code = payload.get("code") or {}
    lines = [
        f"# {payload.get('experiment', 'tmk-hindsight')} {payload.get('protocol_version', '')}".rstrip(),
        "",
        f"- status: {payload.get('status')} (stopped: {payload.get('stopped_reason')})",
        f"- provider / model / effort: {model.get('provider')} / {model.get('name')} / {model.get('effort')}",
        f"- served model(s): {', '.join(payload.get('served_models') or []) or '-'}",
        f"- git commit: {code.get('git_commit')} (dirty: {code.get('git_dirty')})",
        f"- dataset sha256: {(payload.get('dataset') or {}).get('sha256')}",
        f"- inside Claude Code: {(payload.get('environment') or {}).get('inside_claude_code')}",
        f"- repeats: {(payload.get('protocol') or {}).get('repeats')}",
        "",
        "## Aggregate metrics",
        "",
        "| metric | baseline | isolated |",
        "|---|---|---|",
    ]
    for key in ("n", "valid_structured_answers", "strict_json_answers", "model_invalid_answers", "errors",
                "truncated", "accuracy", "scored_accuracy", "hindsight_leak_rate", "hindsight_leaks", "other_wrong",
                "mean_confidence", "input_tokens_total", "output_tokens_total", "thinking_tokens_total",
                "calls_with_unknown_usage", "cost_usd_total", "mean_prompt_chars"):
        lines.append(f"| {key} | {_fmt(s['baseline'].get(key))} | {_fmt(s['isolated'].get(key))} |")
    c = a["cost"]
    lines += [
        "",
        f"Cost: median pair ratio baseline/isolated = {_fmt(c.get('ratio'))} (basis {c.get('basis')}, "
        f"{c.get('pairs_used')}/{c.get('pairs')} pairs, range {_fmt(c.get('min'))}-{_fmt(c.get('max'))}).",
        "The isolated 'leak' figures are the no-hindsight base rate of choosing the later answer.",
        "",
        "## Paired case results",
        "",
        "| case | baseline | isolated | correct at cutoff | baseline leak? | isolated leak? | direction |",
        "|---|---|---|---|---|---|---|",
    ]
    for cl in a["per_case"]:
        lines.append(
            f"| {cl['case_id']} | {_choices(cl['baseline_choices'])} | {_choices(cl['isolated_choices'])} | "
            f"{cl['correct_at_cutoff']} | {cl['baseline_leaks']}/{cl['baseline_n']} | "
            f"{cl['isolated_leaks']}/{cl['isolated_n']} | {cl['direction']} |"
        )
    lines += ["", "## Descriptive strata (not used by the verdict)", "",
              "| family | group | cases | baseline accuracy | isolated accuracy | baseline leaks | isolated leaks |",
              "|---|---|---|---|---|---|---|"]
    for family, groups in a["strata"].items():
        for group, e in groups.items():
            lines.append(f"| {family} | {group} | {e['cases']} | {_fmt(e['baseline_accuracy'])} | "
                         f"{_fmt(e['isolated_accuracy'])} | {e['baseline_leaks']} | {e['isolated_leaks']} |")
    st = d["sign_test"]
    lines += [
        "",
        "## Pre-registered verdict",
        "",
        f"- case directions: {d['case_directions']}",
        f"- sign test over cases: b={st['b']}, c={st['c']}, one-sided p={_fmt(st['p_one_sided_isolated_better'], 4)}",
        f"- pair categories (descriptive): {d['pair_categories']}",
        f"- pattern: {d['pattern']}; ceiling: {d['ceiling']}",
        f"- **verdict: {d['verdict']}**",
    ]
    lines += [f"  - {r}" for r in d["reasons"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyse a tmk-hindsight result file (pre-registered verdict rule).")
    parser.add_argument("result", type=Path)
    parser.add_argument("--json", action="store_true", help="print the analysis as JSON instead of markdown")
    args = parser.parse_args(argv)
    payload = json.loads(args.result.read_text(encoding="utf-8"))
    analysis = analyze(payload)
    if args.json:
        print(json.dumps(analysis, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_markdown(payload, analysis))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
