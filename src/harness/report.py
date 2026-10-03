"""Human-readable summary of a run directory (scores, usage, step status).

Reads only the run's own outputs (``metadata.json``, ``scores.json``,
``trace.jsonl``); it never touches ground truth.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from harness.trace import read_jsonl

METRICS = (
    ("temporal_governance_recall", "recall"),
    ("reopening_precision", "precision"),
    ("false_intervention_rate", "FIR"),
    ("historical_state_fidelity", "fidelity"),
    ("present_remediation_success", "remediation"),
)


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".") if value else "0"
    return str(value)


def _ratio(m: dict[str, Any]) -> str:
    v = m.get("value")
    return f"{_fmt(v)} ({m.get('numerator')}/{m.get('denominator')})" if v is not None else "n/a"


def summarize_run(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    scores = json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))
    tool_counts: dict[str, Counter] = {}
    for rec in read_jsonl(run_dir / "trace.jsonl"):
        if rec.get("type") == "tool_call":
            tool_counts.setdefault(rec["agent"], Counter())[rec["tool"]] += 1
    agents = {}
    for name, s in scores["agents"].items():
        eff = s.get("efficiency", {})
        agents[name] = {
            "metrics": {key: s[key] for key, _ in METRICS},
            "step_status": s["step_status"],
            "efficiency": eff,
            "tool_counts": dict(sorted(tool_counts.get(name, Counter()).items())),
            "reopens": [
                {k: r.get(k) for k in ("seq", "target", "classification")} for r in s.get("reopen_log", [])
            ],
        }
    return {
        "run_id": meta["run_id"],
        "status": meta["status"],
        "protocol_version": meta.get("protocol_version"),
        "fingerprint": meta.get("fingerprint"),
        "scenario": meta["scenario"]["scenario_id"],
        "model": meta["config"].get("model"),
        "isolation": meta.get("isolation"),
        "agents": agents,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"### Run `{summary['run_id']}`",
        "",
        f"- scenario: `{summary['scenario']}`, status: `{summary['status']}`, protocol: `{summary['protocol_version']}`",
        f"- model: `{json.dumps(summary['model'], sort_keys=True)}`",
        f"- fingerprint: `{summary['fingerprint']}`",
        "",
        "| agent | " + " | ".join(label for _, label in METRICS) + " | steps |",
        "|---|" + "---|" * (len(METRICS) + 1),
    ]
    for name, a in summary["agents"].items():
        cells = [_ratio(a["metrics"][key]) for key, _ in METRICS]
        steps = ", ".join(f"{k}: {v}" for k, v in sorted(a["step_status"].items()))
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {steps} |")
    lines += [
        "",
        "| agent | model calls | input tokens | output tokens | retrieval tokens | embedding tokens | cost (USD) "
        "| tool calls | commands | tool-result chars | wall clock (s) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, a in summary["agents"].items():
        e = a["efficiency"]
        cost = _fmt(e.get("cost_usd")) if e.get("cost_known", True) else "unpriced"
        lines.append(
            f"| {name} | {e.get('model_calls', 0)} | {e.get('model_input_tokens', 0)} | {e.get('model_output_tokens', 0)} "
            f"| {e.get('retrieval_tokens', 0)} | {e.get('embedding_tokens', 0)} | {cost} | {e.get('tool_calls', 0)} "
            f"| {e.get('commands', 0)} | {e.get('tool_result_chars', 0)} | {round(e.get('wall_clock_ms', 0) / 1000, 1)} |"
        )
    lines += ["", "| agent | tool calls by tool |", "|---|---|"]
    for name, a in summary["agents"].items():
        lines.append(f"| {name} | " + ", ".join(f"{k}: {v}" for k, v in a["tool_counts"].items()) + " |")
    lines += ["", "| agent | reopens (seq, target, class) |", "|---|---|"]
    for name, a in summary["agents"].items():
        items = "; ".join(f"{r['seq']} {r['target']} {r['classification']}" for r in a["reopens"]) or "none"
        lines.append(f"| {name} | {items} |")
    return "\n".join(lines) + "\n"
