"""Command-line entry point.

    python -m harness smoke                       # smoke scenario, dummy agent, writes runs/<run_id>/
    python -m harness smoke-baseline              # smoke scenario, every baseline preset, fake model (machinery check)
    python -m harness smoke-baseline --model-provider anthropic --model claude-opus-5-5
    python -m harness run --scenario PATH --agent dummy [--agent baseline-k32] [--model-provider fake] ...
    python -m harness replay runs/<run_id>
    python -m harness report runs/<run_id> [--markdown]
    python -m harness validate --scenario PATH
    python -m harness freeze --scenario PATH

The model configuration belongs to the run (protocol amendment A3): every
agent in a run gets the same provider, model and settings. Credentials are
read by the provider backend from the harness environment (for ``anthropic``:
``ANTHROPIC_API_KEY``) and are never passed to contestants.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from harness.agent import ModelSettings, StepBudget
from harness.agents import available_kinds, create_agent
from harness.contestants import BASELINE_SMOKE_SET
from harness.runner import RunConfig, is_process_agent, run
from harness.scenario import freeze_scenario, load_scenario

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_MANIFEST = REPO_ROOT / "scenarios" / "smoke" / "smoke_v1.json"
DEFAULT_RUNS_DIR = REPO_ROOT / "runs"
FAKE_MODEL = "fake-v1"
DEFAULT_EMBEDDING_DIMS = 384


def _headline(scores: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for name, s in scores["agents"].items():
        eff = s.get("efficiency", {})
        out[name] = {
            "temporal_governance_recall": s["temporal_governance_recall"]["value"],
            "reopening_precision": s["reopening_precision"]["value"],
            "false_intervention_rate": s["false_intervention_rate"]["value"],
            "historical_state_fidelity": s["historical_state_fidelity"]["value"],
            "present_remediation_success": s["present_remediation_success"]["value"],
            "step_status": s["step_status"],
            "model_calls": eff.get("model_calls"),
            "model_input_tokens": eff.get("model_input_tokens"),
            "model_output_tokens": eff.get("model_output_tokens"),
            "cost_usd": eff.get("cost_usd") if eff.get("cost_known", True) else None,
            "tool_calls": eff.get("tool_calls"),
        }
    return out


def model_settings_from_args(args: argparse.Namespace) -> ModelSettings:
    provider = args.model_provider
    if provider == "none":
        return ModelSettings()
    name = args.model or (FAKE_MODEL if provider == "fake" else None)
    if name is None:
        raise SystemExit(f"--model is required with --model-provider {provider}")
    embedding = args.embedding_provider
    return ModelSettings(
        provider=provider,
        name=name,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        effort=args.effort,
        prompt_caching=args.prompt_caching,
        embedding_provider=embedding,
        embedding_model="hash-ngram-v1" if embedding == "hash" else None,
        embedding_dims=DEFAULT_EMBEDDING_DIMS if embedding == "hash" else None,
    )


def _execute(args: argparse.Namespace, agent_specs: list[str]) -> int:
    scenario = load_scenario(Path(args.scenario))
    agents = [create_agent(spec) for spec in agent_specs]
    model = model_settings_from_args(args)
    if model.provider == "none" and any(is_process_agent(a) for a in agents):
        raise SystemExit(
            "model-backed contestants need a model: pass --model-provider fake (deterministic machinery check) "
            "or --model-provider anthropic --model MODEL_ID"
        )
    budget = StepBudget(max_tool_calls_per_event=args.max_tool_calls) if args.max_tool_calls is not None else None
    config = RunConfig(
        runs_dir=Path(args.runs_dir),
        seed=args.seed,
        budget=budget,
        model=model,
        run_id=args.run_id,
        allow_draft=args.allow_draft,
    )
    result = run(scenario, agents, config)
    print(json.dumps({"run_id": result.run_id, "run_dir": str(result.run_dir), "status": result.status,
                      "fingerprint": result.fingerprint, "model": model.to_dict(),
                      "scores": _headline(result.scores) if result.scores else None}, indent=2))
    return 0 if result.status == "completed" else 1


def _cmd_run(args: argparse.Namespace) -> int:
    return _execute(args, args.agent or ["dummy"])


def _cmd_smoke_baseline(args: argparse.Namespace) -> int:
    return _execute(args, args.agent or list(BASELINE_SMOKE_SET))


def _cmd_replay(args: argparse.Namespace) -> int:
    from harness.replay import replay_run

    result, report = replay_run(Path(args.run_dir), runs_dir=Path(args.runs_dir) if args.runs_dir else None,
                                scenario_path=Path(args.scenario) if args.scenario else None)
    print(json.dumps({**report, "replay_run_dir": str(result.run_dir)}, indent=2))
    return 0 if report["match"] else 2


def _cmd_report(args: argparse.Namespace) -> int:
    from harness.report import render_markdown, summarize_run

    summary = summarize_run(Path(args.run_dir))
    print(render_markdown(summary) if args.markdown else json.dumps(summary, indent=2, sort_keys=True))
    return 0


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

    def add_run_args(sp: argparse.ArgumentParser, scenario_default: str | None, provider_default: str) -> None:
        sp.add_argument("--scenario", default=scenario_default, required=scenario_default is None)
        sp.add_argument("--agent", action="append", help=f"agent kind[:name]; kinds: {', '.join(available_kinds())}")
        sp.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
        sp.add_argument("--seed", type=int, default=0)
        sp.add_argument("--max-tool-calls", type=int, default=None)
        sp.add_argument("--run-id", default=None)
        sp.add_argument("--allow-draft", action="store_true")
        m = sp.add_argument_group("model (one configuration for every agent in the run)")
        m.add_argument("--model-provider", choices=("none", "fake", "anthropic"), default=provider_default)
        m.add_argument("--model", default=None, help=f"model id (default {FAKE_MODEL} for the fake provider)")
        m.add_argument("--max-output-tokens", type=int, default=None)
        m.add_argument("--temperature", type=float, default=None)
        m.add_argument("--effort", default=None, choices=("low", "medium", "high", "xhigh", "max"))
        m.add_argument("--prompt-caching", action="store_true")
        m.add_argument("--embedding-provider", choices=("none", "hash"), default="hash")

    rp_run = sub.add_parser("run", help="run agents through a scenario")
    add_run_args(rp_run, None, "none")
    rp_run.set_defaults(func=_cmd_run)
    rp_smoke = sub.add_parser("smoke", help="run the 10-event smoke scenario")
    add_run_args(rp_smoke, str(SMOKE_MANIFEST), "none")
    rp_smoke.set_defaults(func=_cmd_run)
    rp_base = sub.add_parser("smoke-baseline", help="run the baseline presets on the smoke scenario")
    add_run_args(rp_base, str(SMOKE_MANIFEST), "fake")
    rp_base.set_defaults(func=_cmd_smoke_baseline)

    rp = sub.add_parser("replay", help="replay a recorded run and verify it reproduces")
    rp.add_argument("run_dir")
    rp.add_argument("--runs-dir", default=None)
    rp.add_argument("--scenario", default=None)
    rp.set_defaults(func=_cmd_replay)

    rep = sub.add_parser("report", help="summarize a run directory (scores, metered usage, tool calls)")
    rep.add_argument("run_dir")
    rep.add_argument("--markdown", action="store_true")
    rep.set_defaults(func=_cmd_report)

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

