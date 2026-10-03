"""Command-line entry point.

    python -m harness smoke                       # smoke scenario, dummy agent, writes runs/<run_id>/
    python -m harness run --scenario PATH --agent dummy [--agent keyword] [--runs-dir runs] [--seed 0]
    python -m harness replay runs/<run_id>
    python -m harness validate --scenario PATH
    python -m harness freeze --scenario PATH
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from harness.agent import StepBudget
from harness.agents import REGISTRY, create_agent
from harness.runner import RunConfig, run
from harness.scenario import freeze_scenario, load_scenario

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_MANIFEST = REPO_ROOT / "scenarios" / "smoke" / "smoke_v1.json"
DEFAULT_RUNS_DIR = REPO_ROOT / "runs"


def _headline(scores: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for name, s in scores["agents"].items():
        out[name] = {
            "temporal_governance_recall": s["temporal_governance_recall"]["value"],
            "reopening_precision": s["reopening_precision"]["value"],
            "false_intervention_rate": s["false_intervention_rate"]["value"],
            "historical_state_fidelity": s["historical_state_fidelity"]["value"],
            "present_remediation_success": s["present_remediation_success"]["value"],
            "step_status": s["step_status"],
        }
    return out


def _cmd_run(args: argparse.Namespace) -> int:
    scenario = load_scenario(Path(args.scenario))
    agents = [create_agent(spec) for spec in (args.agent or ["dummy"])]
    budget = StepBudget(max_tool_calls_per_event=args.max_tool_calls) if args.max_tool_calls else None
    config = RunConfig(
        runs_dir=Path(args.runs_dir),
        seed=args.seed,
        budget=budget,
        run_id=args.run_id,
        allow_draft=args.allow_draft,
    )
    result = run(scenario, agents, config)
    print(json.dumps({"run_id": result.run_id, "run_dir": str(result.run_dir), "status": result.status,
                      "fingerprint": result.fingerprint, "scores": _headline(result.scores)}, indent=2))
    return 0 if result.status == "completed" else 1


def _cmd_replay(args: argparse.Namespace) -> int:
    from harness.replay import replay_run

    result, report = replay_run(Path(args.run_dir), runs_dir=Path(args.runs_dir) if args.runs_dir else None,
                                scenario_path=Path(args.scenario) if args.scenario else None)
    print(json.dumps({**report, "replay_run_dir": str(result.run_dir)}, indent=2))
    return 0 if report["match"] else 2


def _cmd_validate(args: argparse.Namespace) -> int:
    from evaluation.validate import validate_scenario

    report = validate_scenario(load_scenario(Path(args.scenario)), run_agents=not args.static_only)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _cmd_freeze(args: argparse.Namespace) -> int:
    from evaluation.validate import validate_scenario

    validate_scenario(load_scenario(Path(args.scenario)))
    scenario = freeze_scenario(Path(args.scenario))
    print(json.dumps({"scenario_id": scenario.scenario_id, "status": scenario.status,
                      "content_hashes": scenario.data["content_hashes"]}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m harness", description="Temporal agent benchmark harness")
    sub = p.add_subparsers(dest="command", required=True)

    def add_run_args(sp: argparse.ArgumentParser, scenario_default: str | None) -> None:
        sp.add_argument("--scenario", default=scenario_default, required=scenario_default is None)
        sp.add_argument("--agent", action="append", help=f"agent kind[:name]; kinds: {', '.join(sorted(REGISTRY))}")
        sp.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
        sp.add_argument("--seed", type=int, default=0)
        sp.add_argument("--max-tool-calls", type=int, default=None)
        sp.add_argument("--run-id", default=None)
        sp.add_argument("--allow-draft", action="store_true")
        sp.set_defaults(func=_cmd_run)

    add_run_args(sub.add_parser("run", help="run agents through a scenario"), None)
    add_run_args(sub.add_parser("smoke", help="run the 10-event smoke scenario"), str(SMOKE_MANIFEST))

    rp = sub.add_parser("replay", help="replay a recorded run and verify it reproduces")
    rp.add_argument("run_dir")
    rp.add_argument("--runs-dir", default=None)
    rp.add_argument("--scenario", default=None)
    rp.set_defaults(func=_cmd_replay)

    vp = sub.add_parser("validate", help="validate a scenario (lint, integrity, solvability)")
    vp.add_argument("--scenario", default=str(SMOKE_MANIFEST))
    vp.add_argument("--static-only", action="store_true")
    vp.set_defaults(func=_cmd_validate)

    fp = sub.add_parser("freeze", help="validate and freeze a draft scenario")
    fp.add_argument("--scenario", required=True)
    fp.set_defaults(func=_cmd_freeze)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
