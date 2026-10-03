"""Analysis of a tmk-hindsight result file, with the pre-registered verdict rule.

Pure functions over the JSON rows written by :mod:`hindsight_eval`, so a result
file can be re-analysed without the code that produced it:

    PYTHONPATH=src python -m multiplicity_experiments.hindsight_analysis RESULT.json

The thresholds below were fixed before any real-model run (protocol v0.1).
They must not be changed after a result has been seen; a change is a new
protocol version, and the earlier analysis is kept.

Unit of analysis: a *pair*, i.e. the baseline and the isolated answer to the
same case in the same repeat. Only pairs where both answers are valid enter
the discordance counts; invalid answers are limited by a validity gate instead
of being counted as reasoning errors.

- ``b``: baseline wrong, isolated correct (isolation helped);
- ``c``: baseline correct, isolated wrong (isolation hurt);
- ``b_leak``: the subset of ``b`` where the baseline chose the later answer.

Verdict (exactly one of three):

1. ``INCONCLUSIVE`` if a validity gate fails: the run is not complete, or more
   than ``MAX_INVALID_RATE`` of either condition's answers are invalid.
2. ``SUPPORTED_FOR_NEXT_TEST`` if isolation wins: exact one-sided McNemar
   p <= ``ALPHA`` on (b, c), b - c >= 2, the b pairs come from at least
   ``MIN_DISCORDANT_CASES`` distinct cases, at least half of them are
   hindsight leaks, and isolated accuracy >= ``MIN_ISOLATED_ACCURACY``.
3. ``NO_DISTINCT_ADVANTAGE`` if the baseline matches or beats isolation:
   b - c <= ``NO_ADVANTAGE_MARGIN``, at comparable cost (baseline tokens per
   call <= ``MAX_COST_RATIO`` x isolated), and either isolated accuracy >=
   ``MIN_ISOLATED_ACCURACY`` (the task works without hindsight; the baseline
   simply matches it) or c > b (isolation is worse).
4. ``INCONCLUSIVE`` otherwise (for example a small, non-significant isolation
   advantage, or both conditions failing).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

CONDITIONS = ("baseline", "isolated")
VERDICTS = ("SUPPORTED_FOR_NEXT_TEST", "NO_DISTINCT_ADVANTAGE", "INCONCLUSIVE")

# Pre-registered thresholds (protocol v0.1). Do not tune after seeing results.
MAX_INVALID_RATE = 0.125
MIN_ISOLATED_ACCURACY = 0.85
ALPHA = 0.05
MIN_DISCORDANT_CASES = 2
NO_ADVANTAGE_MARGIN = 1
MAX_COST_RATIO = 1.25

THRESHOLDS = {
    "max_invalid_rate": MAX_INVALID_RATE,
    "min_isolated_accuracy": MIN_ISOLATED_ACCURACY,
    "alpha_one_sided": ALPHA,
    "min_discordant_cases": MIN_DISCORDANT_CASES,
    "no_advantage_margin": NO_ADVANTAGE_MARGIN,
    "max_cost_ratio": MAX_COST_RATIO,
}


# ------------------------------------------------------------------ statistics
def binomial_tail(k: int, n: int) -> float:
    """P(X >= k) for X ~ Binomial(n, 0.5)."""
    if n < 0 or k > n:
        return 0.0 if k > n else 1.0
    k = max(k, 0)
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2**n


def mcnemar_exact(b: int, c: int) -> dict[str, float | int]:
    """Exact McNemar test on discordant pairs: one-sided for b > c, and two-sided."""
    n = b + c
    one_sided = binomial_tail(b, n) if n else 1.0
    two_sided = min(1.0, 2 * min(binomial_tail(b, n), binomial_tail(c, n))) if n else 1.0
    return {"b": b, "c": c, "discordant": n, "p_one_sided_isolated_better": one_sided, "p_two_sided": two_sided}


# -------------------------------------------------------------------- summaries
def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _tokens(meter: Mapping[str, Any], key: str) -> int | None:
    v = meter.get(key)
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def summarize(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate metrics per condition. Invalid answers count as not correct."""
    rows = list(rows)
    out: dict[str, Any] = {}
    for condition in CONDITIONS:
        sel = [r for r in rows if r["condition"] == condition]
        valid = [r for r in sel if r.get("choice") is not None]
        confidences = [float(r["confidence"]) for r in sel if r.get("confidence") is not None]
        meters = [r.get("meter") or {} for r in sel]
        tin = [_tokens(m, "total_input_tokens") for m in meters]
        tout = [_tokens(m, "output_tokens") for m in meters]
        thinking = [
            (m.get("provider_meta") or {}).get("thinking_tokens") for m in meters
        ]
        costs = [m.get("cost_usd") for m in meters]
        n = len(sel)
        out[condition] = {
            "n": n,
            "valid_structured_answers": len(valid),
            "strict_json_answers": sum(1 for r in sel if r.get("parse_mode") == "json"),
            "invalid_answers": n - len(valid),
            "errors": sum(1 for r in sel if r.get("error")),
            "accuracy": (sum(1 for r in sel if r.get("correct")) / n) if n else None,
            "accuracy_among_valid": (sum(1 for r in valid if r.get("correct")) / len(valid)) if valid else None,
            "hindsight_leak_rate": (sum(1 for r in sel if r.get("hindsight_leak")) / n) if n else None,
            "hindsight_leaks": sum(1 for r in sel if r.get("hindsight_leak")),
            "other_wrong": sum(1 for r in valid if not r.get("correct") and not r.get("hindsight_leak")),
            "mean_confidence": _mean(confidences),
            "input_tokens_total": sum(v for v in tin if v is not None),
            "output_tokens_total": sum(v for v in tout if v is not None),
            "thinking_tokens_total": sum(v for v in thinking if isinstance(v, int) and not isinstance(v, bool)),
            "calls_with_unknown_usage": sum(1 for a, b in zip(tin, tout) if a is None or b is None),
            "cost_usd_total": round(sum(v for v in costs if isinstance(v, (int, float))), 8),
            "mean_prompt_chars": _mean([float(r.get("prompt_chars") or 0) for r in sel]),
        }
    return out


def _mean_tokens_per_call(rows: list[Mapping[str, Any]], condition: str) -> float | None:
    vals = []
    for r in rows:
        if r["condition"] != condition:
            continue
        m = r.get("meter") or {}
        tin, tout = _tokens(m, "total_input_tokens"), _tokens(m, "output_tokens")
        if tin is not None and tout is not None:
            vals.append(float(tin + tout))
    return _mean(vals)


def cost_ratio(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Baseline / isolated mean tokens per call; falls back to prompt characters if usage is unknown."""
    rows = list(rows)
    b, i = _mean_tokens_per_call(rows, "baseline"), _mean_tokens_per_call(rows, "isolated")
    if b is not None and i:
        return {"basis": "reported_tokens", "baseline_per_call": b, "isolated_per_call": i, "ratio": b / i}
    pb = _mean([float(r.get("prompt_chars") or 0) for r in rows if r["condition"] == "baseline"])
    pi = _mean([float(r.get("prompt_chars") or 0) for r in rows if r["condition"] == "isolated"])
    if pb is not None and pi:
        return {"basis": "prompt_chars", "baseline_per_call": pb, "isolated_per_call": pi, "ratio": pb / pi}
    return {"basis": None, "baseline_per_call": None, "isolated_per_call": None, "ratio": None}


def pairs(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Baseline/isolated pairs keyed by (case, repeat), with their category."""
    by_key: dict[tuple[str, int], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for r in rows:
        by_key[(r["case_id"], int(r.get("repeat", 0)))][r["condition"]] = r
    out = []
    for (case_id, repeat), d in sorted(by_key.items()):
        base, iso = d.get("baseline"), d.get("isolated")
        if base is None or iso is None:
            category = "incomplete"
        elif base.get("choice") is None or iso.get("choice") is None:
            category = "invalid"
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
    """One line per case, aggregated over repeats (for the paired table)."""
    rows = list(rows)
    cases: dict[str, dict[str, Any]] = {}
    for r in rows:
        c = cases.setdefault(r["case_id"], {
            "case_id": r["case_id"],
            "correct_at_cutoff": r.get("correct_at_cutoff"),
            "later_answer": r.get("later_answer"),
            "baseline": [], "isolated": [],
        })
        c[r["condition"]].append(r)
    out = []
    for cid in sorted(cases):
        c = cases[cid]
        line = {"case_id": cid, "correct_at_cutoff": c["correct_at_cutoff"], "later_answer": c["later_answer"]}
        for cond in CONDITIONS:
            rs = sorted(c[cond], key=lambda r: int(r.get("repeat", 0)))
            line[f"{cond}_choices"] = [r.get("choice") for r in rs]
            line[f"{cond}_correct"] = sum(1 for r in rs if r.get("correct"))
            line[f"{cond}_leaks"] = sum(1 for r in rs if r.get("hindsight_leak"))
            line[f"{cond}_n"] = len(rs)
        out.append(line)
    return out


def pattern_of(counts: Mapping[str, int]) -> str:
    """The run-level pattern named in the experiment brief (A/B/C/D)."""
    b = counts.get("baseline_wrong_isolated_correct", 0)
    c = counts.get("baseline_correct_isolated_wrong", 0)
    if c > b:
        return "D_baseline_beats_isolated"
    if b > c:
        return "B_isolated_beats_baseline"
    if counts.get("both_wrong", 0) > 0:
        return "C_both_fail"
    return "A_both_correct"


# ---------------------------------------------------------------------- verdict
def decide(
    *,
    status: str,
    summary: Mapping[str, Any],
    pair_list: list[Mapping[str, Any]],
    cost: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the pre-registered verdict rule. Returns the verdict and the reasons that decided it."""
    reasons: list[str] = []
    counts: dict[str, int] = defaultdict(int)
    for p in pair_list:
        counts[p["category"]] += 1
    b = counts["baseline_wrong_isolated_correct"]
    c = counts["baseline_correct_isolated_wrong"]
    b_pairs = [p for p in pair_list if p["category"] == "baseline_wrong_isolated_correct"]
    b_leak = sum(1 for p in b_pairs if p["baseline_leak"])
    b_cases = len({p["case_id"] for p in b_pairs})
    test = mcnemar_exact(b, c)
    iso_acc = summary.get("isolated", {}).get("accuracy")
    ratio = cost.get("ratio")
    facts = {
        "pairs": len(pair_list),
        "pair_categories": dict(sorted(counts.items())),
        "b": b, "c": c, "b_leak": b_leak, "b_distinct_cases": b_cases,
        "mcnemar": test,
        "isolated_accuracy": iso_acc,
        "baseline_accuracy": summary.get("baseline", {}).get("accuracy"),
        "cost_ratio": ratio,
        "pattern": pattern_of(counts),
        "thresholds": dict(THRESHOLDS),
    }

    gate_ok = True
    if status != "complete":
        gate_ok = False
        reasons.append(f"run status is {status!r}, not 'complete'")
    for cond in CONDITIONS:
        s = summary.get(cond) or {}
        n = s.get("n") or 0
        if n == 0:
            gate_ok = False
            reasons.append(f"no {cond} answers")
            continue
        rate = (s.get("invalid_answers") or 0) / n
        if rate > MAX_INVALID_RATE:
            gate_ok = False
            reasons.append(f"{cond} invalid-answer rate {rate:.3f} > {MAX_INVALID_RATE}")
    if counts.get("incomplete"):
        gate_ok = False
        reasons.append(f"{counts['incomplete']} unpaired answers")
    if not gate_ok:
        return {"verdict": "INCONCLUSIVE", "reasons": ["validity gate failed: " + "; ".join(reasons)], **facts}

    supported = (
        test["p_one_sided_isolated_better"] <= ALPHA
        and b - c >= 2
        and b_cases >= MIN_DISCORDANT_CASES
        and 2 * b_leak >= b
        and iso_acc is not None and iso_acc >= MIN_ISOLATED_ACCURACY
    )
    if supported:
        reasons.append(
            f"isolation better on {b} pairs vs {c} (one-sided exact p={test['p_one_sided_isolated_better']:.4f}), "
            f"across {b_cases} cases, {b_leak} of them hindsight leaks; isolated accuracy {iso_acc:.3f}"
        )
        return {"verdict": "SUPPORTED_FOR_NEXT_TEST", "reasons": reasons, **facts}

    comparable_cost = ratio is not None and ratio <= MAX_COST_RATIO
    isolation_works = iso_acc is not None and iso_acc >= MIN_ISOLATED_ACCURACY
    if b - c <= NO_ADVANTAGE_MARGIN and comparable_cost and (isolation_works or c > b):
        if c > b:
            reasons.append(f"baseline better than isolation on net {c - b} pairs (b={b}, c={c})")
        else:
            reasons.append(
                f"baseline matches isolation: net isolation advantage {b - c} pair(s) <= margin {NO_ADVANTAGE_MARGIN}; "
                f"isolated accuracy {iso_acc:.3f}"
            )
        reasons.append(f"cost ratio baseline/isolated {ratio:.3f} <= {MAX_COST_RATIO}")
        return {"verdict": "NO_DISTINCT_ADVANTAGE", "reasons": reasons, **facts}

    if b - c > NO_ADVANTAGE_MARGIN:
        reasons.append(
            f"isolation ahead by {b - c} pairs but the pre-registered support criteria are not met "
            f"(p={test['p_one_sided_isolated_better']:.4f}, cases={b_cases}, leaks={b_leak}, isolated accuracy={iso_acc})"
        )
    if not isolation_works and c <= b:
        reasons.append(f"isolated accuracy {iso_acc} < {MIN_ISOLATED_ACCURACY}: the isolated condition itself fails")
    if not comparable_cost:
        reasons.append(f"cost not comparable (ratio {ratio})")
    return {"verdict": "INCONCLUSIVE", "reasons": reasons, **facts}


def analyze(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Full analysis of a result payload (as written by hindsight_eval)."""
    rows = list(payload.get("results") or [])
    summary = summarize(rows)
    pair_list = pairs(rows)
    cost = cost_ratio(rows)
    decision = decide(status=str(payload.get("status")), summary=summary, pair_list=pair_list, cost=cost)
    return {
        "summary": summary,
        "cost": cost,
        "pairs": pair_list,
        "per_case": per_case(rows),
        "decision": decision,
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
    lines = [
        f"# {payload.get('experiment', 'tmk-hindsight')} {payload.get('protocol_version', '')}".rstrip(),
        "",
        f"- status: {payload.get('status')}",
        f"- provider / model / effort: {model.get('provider')} / {model.get('name')} / {model.get('effort')}",
        f"- served model(s): {', '.join(payload.get('served_models') or []) or '-'}",
        f"- git commit: {(payload.get('code') or {}).get('git_commit')}"
        f" (dirty: {(payload.get('code') or {}).get('git_dirty')})",
        f"- dataset sha256: {(payload.get('dataset') or {}).get('sha256')}",
        f"- inside Claude Code: {(payload.get('environment') or {}).get('inside_claude_code')}",
        f"- repeats: {(payload.get('protocol') or {}).get('repeats')}",
        "",
        "## Aggregate metrics",
        "",
        "| metric | baseline | isolated |",
        "|---|---|---|",
    ]
    for key in ("n", "valid_structured_answers", "strict_json_answers", "accuracy", "hindsight_leak_rate",
                "hindsight_leaks", "other_wrong", "mean_confidence", "input_tokens_total", "output_tokens_total",
                "thinking_tokens_total", "calls_with_unknown_usage", "cost_usd_total", "mean_prompt_chars"):
        lines.append(f"| {key} | {_fmt(s['baseline'].get(key))} | {_fmt(s['isolated'].get(key))} |")
    lines += [
        "",
        f"Cost ratio (baseline / isolated, {a['cost'].get('basis')}): {_fmt(a['cost'].get('ratio'))}",
        "",
        "## Paired case results",
        "",
        "| case | baseline | isolated | correct at cutoff | baseline leak? | isolated leak? |",
        "|---|---|---|---|---|---|",
    ]
    for c in a["per_case"]:
        lines.append(
            f"| {c['case_id']} | {_choices(c['baseline_choices'])} | {_choices(c['isolated_choices'])} | "
            f"{c['correct_at_cutoff']} | {c['baseline_leaks']}/{c['baseline_n']} | {c['isolated_leaks']}/{c['isolated_n']} |"
        )
    lines += [
        "",
        "## Pre-registered verdict",
        "",
        f"- pair categories: {d['pair_categories']}",
        f"- pattern: {d['pattern']}",
        f"- McNemar exact: b={d['b']}, c={d['c']}, one-sided p={_fmt(d['mcnemar']['p_one_sided_isolated_better'], 4)}",
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
