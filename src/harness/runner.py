"""Lockstep event runner (EXPERIMENT.md §9).

For every event, in order:

1. apply the event's world changes to every agent's isolated workspace;
2. deliver the contestant view of the event to each agent (in a seeded,
   recorded per-step order) with a fresh, budgeted ToolBox; no temporal hints,
   nothing from ground truth;
3. record actions, tool calls, usage, and failures;
4. only after *all* agents have completed the step, classify their reopen
   actions and snapshot workspaces that are due for remediation checks.

Remediation checks and scoring run after every agent has been torn down.
Agent failures never abort a run; run directories are never overwritten; on
any failure the trace, partial outputs and final agent state are preserved.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import platform
import random
import re
import shutil
import subprocess
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import evaluation
import harness
from evaluation.ground_truth import GT_SCHEMA_VERSION, load_ground_truth
from evaluation.scorer import EVALUATOR_VERSION, SCORES_SCHEMA_VERSION, Evaluator
from harness import HARNESS_VERSION, guard
from harness.agent import (
    ACTION_SCHEMA_VERSION,
    ACTION_TYPES,
    Agent,
    AgentContext,
    AgentResponse,
    ModelSettings,
    StepBudget,
    Usage,
)
from harness.canonical import canonical_json, copy_tree, sha256_json, tree_hash
from harness.events import EVENT_SCHEMA_VERSION, Event
from harness.instructions import INSTRUCTIONS, INSTRUCTIONS_VERSION
from harness.scenario import SCENARIO_SCHEMA_VERSION, Scenario, ScenarioError
from harness.tools import BudgetExceeded, ToolBox
from harness.trace import TRACE_SCHEMA_VERSION, JsonlWriter, TraceWriter, run_fingerprint, write_json_atomic
from harness.workspace import Workspace
from harness.world import apply_event

RUN_SCHEMA_VERSION = "tab.run/1"
# Default output root of the CLI; always protected, even when a run writes elsewhere.
DEFAULT_RUNS_ROOT = Path(__file__).resolve().parents[2] / "runs"
AGENT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
OUTPUT_FILES = ("metadata.json", "events.jsonl", "actions.jsonl", "scores.json", "trace.jsonl", "evaluation.jsonl")
NON_CONTESTANT_ROLES = ("reference", "oracle")


@dataclass(frozen=True)
class RunConfig:
    runs_dir: Path
    seed: int = 0
    budget: StepBudget | None = None  # None: use the scenario's budgets
    model: ModelSettings = field(default_factory=ModelSettings)
    run_id: str | None = None
    allow_draft: bool = False
    hygiene: bool = True  # run each agent's own test suite on its final workspace


@dataclass
class RunResult:
    run_id: str
    run_dir: Path
    status: str
    scores: dict[str, Any] | None
    fingerprint: str | None


@dataclass
class _Lane:
    agent: Agent
    root: Path
    workspace: Workspace
    state_dir: Path
    enabled: bool = True
    expected_tree: str = ""
    usage: dict[str, Any] = field(
        default_factory=lambda: {
            "model_input_tokens": 0,
            "model_output_tokens": 0,
            "retrieval_tokens": 0,
            "model_calls": 0,
            "cost_usd": 0.0,
        }
    )
    tool_calls: int = 0
    wall_clock_ms: float = 0.0
    status_counts: dict[str, int] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.agent.name


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_info(cwd: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=10
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, timeout=10
            ).stdout.strip()
        )
        return {"commit": commit or None, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None}


def code_hashes() -> dict[str, str]:
    """Content hashes of the harness and evaluator source trees."""
    return {
        "harness": tree_hash(Path(harness.__file__).resolve().parent),
        "evaluation": tree_hash(Path(evaluation.__file__).resolve().parent),
    }


def environment_info() -> dict[str, Any]:
    try:
        import pytest

        pytest_version = pytest.__version__
    except ImportError:  # pragma: no cover
        pytest_version = None
    return {"python": platform.python_version(), "pytest": pytest_version}


def _describe(agent: Agent) -> dict[str, Any]:
    d = dict(agent.describe())
    d.setdefault("config", {})
    d.setdefault("role", "contestant")
    return d


def _describe_guarded(agent: Agent, denied: list[Path]) -> dict[str, Any]:
    """``describe()`` is agent code too: run it under the guard in a throwaway directory."""
    with tempfile.TemporaryDirectory(prefix="tab-describe-") as scratch, guard.armed(denied):
        lane = f"describe:{agent.name}"
        guard.register_lane(lane, Path(scratch))
        with guard.agent_call(lane, Path(scratch), guard.lane_env(Path(scratch))):
            return _describe(agent)


def _allocate_run_dir(runs_dir: Path, run_id: str) -> tuple[str, Path]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    candidate, n = run_id, 1
    while True:
        path = runs_dir / candidate
        try:
            path.mkdir()
            return candidate, path
        except FileExistsError:
            n += 1
            candidate = f"{run_id}__{n}"


def _summarize_args(args: dict[str, Any]) -> dict[str, Any]:
    out = dict(args)
    if isinstance(out.get("content"), str):
        content = out.pop("content")
        out["content_sha256"] = sha256_json(content)
        out["content_chars"] = len(content)
    return out


def _validate_response(resp: Any) -> None:
    if not isinstance(resp, AgentResponse):
        raise TypeError(f"on_event must return AgentResponse, got {type(resp).__name__}")
    if not isinstance(resp.actions, list) or not all(isinstance(a, ACTION_TYPES) for a in resp.actions):
        raise TypeError("AgentResponse.actions must be a list of Action objects")
    if not isinstance(resp.usage, Usage):
        raise TypeError("AgentResponse.usage must be a Usage")


class _Redactor:
    """Replaces host-specific absolute paths in error text with stable placeholders."""

    def __init__(self) -> None:
        self._pairs: list[tuple[str, str]] = []

    def add(self, path: Path | str, placeholder: str) -> None:
        for variant in {str(path), os.path.realpath(path)}:
            if variant and variant != os.sep:
                self._pairs.append((variant, placeholder))
        self._pairs.sort(key=lambda p: len(p[0]), reverse=True)

    def __call__(self, text: str | None) -> str | None:
        if text is None:
            return None
        for raw, placeholder in self._pairs:
            text = text.replace(raw, placeholder)
        return text


def step_order(names: list[str], seed: int, seq: int) -> list[str]:
    """Deterministic, seed-dependent agent order for one step (recorded in the trace)."""
    rng = random.Random(int(hashlib.sha256(f"{seed}:{seq}".encode()).hexdigest()[:16], 16))
    order = sorted(names)
    rng.shuffle(order)
    return order


def write_manifest(run_dir: Path) -> None:
    tmp = Path(run_dir) / ".MANIFEST.sha256.tmp"
    tmp.write_text(manifest_listing(run_dir), encoding="utf-8")
    os.replace(tmp, Path(run_dir) / "MANIFEST.sha256")


def manifest_listing(run_dir: Path) -> str:
    """``sha256  relative/path`` for every file in a run directory except the listing itself."""
    lines = []
    for path in sorted(p for p in Path(run_dir).rglob("*") if p.is_file() and not p.is_symlink()):
        rel = path.relative_to(run_dir).as_posix()
        if rel in ("MANIFEST.sha256", ".MANIFEST.sha256.tmp"):
            continue
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {rel}")
    return "\n".join(lines) + "\n"


def run(
    scenario: Scenario,
    agents: Sequence[Agent],
    config: RunConfig,
    *,
    replay_of: str | None = None,
) -> RunResult:
    if not agents:
        raise ValueError("at least one agent is required")
    names = [a.name for a in agents]
    for n in names:
        if not isinstance(n, str) or not AGENT_NAME_RE.match(n):
            raise ValueError(f"invalid agent name {n!r}")
    if len(set(names)) != len(names):
        raise ValueError(f"agent names must be unique: {names}")
    runs_dir = Path(config.runs_dir).resolve()
    tmp_root = Path(tempfile.gettempdir()).resolve()
    if tmp_root == runs_dir or runs_dir in tmp_root.parents:
        raise ValueError("runs_dir must not contain the system temp directory (agent lanes live there)")
    denied_base = scenario.protected_paths() + [
        runs_dir,
        scenario.base_dir / "runs",
        DEFAULT_RUNS_ROOT,
        scenario.base_dir / "world",
        scenario.base_dir / ".git",
    ]
    agent_specs = [{"name": a.name, **_describe_guarded(a, denied_base)} for a in agents]
    if scenario.status != "frozen":
        contestants = [s["name"] for s in agent_specs if s["role"] not in NON_CONTESTANT_ROLES]
        if contestants:
            raise ScenarioError(f"contestants {contestants} may only run on frozen scenarios (EXPERIMENT.md §14)")

    content_hashes = scenario.verify(allow_draft=config.allow_draft)
    events: list[Event] = scenario.load_events()
    gt = load_ground_truth(
        scenario.ground_truth_dir,
        {e.event_id: e.seq for e in events},
        {e.event_id: e.timestamp for e in events},
    )
    budget = config.budget or StepBudget(**scenario.budgets)
    scenario_info = {**scenario.public_info(), "content_hashes": content_hashes}
    evaluator = Evaluator(gt, events, scenario_info, content_hashes["ground_truth"])

    code = code_hashes()
    env = environment_info()
    run_config = {
        "seed": config.seed,
        "budget": budget.to_dict(),
        "model": config.model.to_dict(),
        "instructions_version": INSTRUCTIONS_VERSION,
        "instructions_sha256": sha256_json(INSTRUCTIONS),
        "hygiene": config.hygiene,
    }
    config_hash = sha256_json(
        {
            "scenario": scenario.scenario_id,
            "content_hashes": content_hashes,
            "agents": agent_specs,
            "config": run_config,
            "harness_version": HARNESS_VERSION,
            "evaluator_version": EVALUATOR_VERSION,
            "code_hashes": code,
            "environment": env,
        }
    )
    base_id = config.run_id or (
        f"{replay_of}__replay" if replay_of else f"{scenario.scenario_id}__{'+'.join(names)}__{config_hash[:10]}"
    )
    run_id, run_dir = _allocate_run_dir(runs_dir, base_id)

    try:
        manifest_rel = scenario.manifest_path.relative_to(scenario.base_dir).as_posix()
    except ValueError:
        manifest_rel = scenario.manifest_path.name
    metadata: dict[str, Any] = {
        "schema_version": RUN_SCHEMA_VERSION,
        "run_id": run_id,
        "status": "running",
        "replay_of": replay_of,
        "harness_version": HARNESS_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "code_hashes": code,
        "environment": env,
        "schemas": {
            "event": EVENT_SCHEMA_VERSION,
            "action": ACTION_SCHEMA_VERSION,
            "trace": TRACE_SCHEMA_VERSION,
            "scores": SCORES_SCHEMA_VERSION,
            "scenario": SCENARIO_SCHEMA_VERSION,
            "ground_truth": GT_SCHEMA_VERSION,
        },
        "scenario": {**scenario_info, "manifest": manifest_rel},
        "agents": agent_specs,
        "config": {**run_config, "allow_draft": config.allow_draft},
        "config_hash": config_hash,
        "token_accounting": "placeholder: agents self-report Usage; non-LLM agents report zeros",
        "last_completed_seq": None,
        "started_at": _now_iso(),
        "finished_at": None,
        "host": {
            "platform": platform.platform(),
            "pid": os.getpid(),
            "manifest_path": str(scenario.manifest_path),
        },
        "git": _git_info(scenario.base_dir),
        "outputs": list(OUTPUT_FILES),
        "integrity": None,
        "fingerprint": None,
        "error": None,
    }
    write_json_atomic(run_dir / "metadata.json", metadata)

    trace = TraceWriter(run_dir / "trace.jsonl")
    events_out = JsonlWriter(run_dir / "events.jsonl")
    actions_out = JsonlWriter(run_dir / "actions.jsonl")
    evaluation_out = JsonlWriter(run_dir / "evaluation.jsonl")
    blobs_dir = run_dir / "blobs"
    blobs_dir.mkdir()
    redact = _Redactor()
    guard_stack = contextlib.ExitStack()
    lanes: list[_Lane] = []
    final_copied = False
    scores: dict[str, Any] | None = None
    status = "failed"

    def store_blob(obj: Any) -> str:
        text = canonical_json(obj)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        path = blobs_dir / f"{digest}.json"
        if not path.exists():
            tmp = blobs_dir / f".{digest}.tmp"
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
        return digest

    def copy_final_state() -> None:
        nonlocal final_copied
        if final_copied:
            return
        final_copied = True
        for lane in lanes:
            dest = run_dir / "final_state" / lane.name
            copy_tree(lane.workspace.root, dest / "workspace", regular_only=True)
            copy_tree(lane.state_dir, dest / "state", regular_only=True)

    try:
        evaluator.open()
        for agent in agents:
            lane_root = Path(tempfile.mkdtemp(prefix="tab-lane-"))
            ws_root, state_dir = lane_root / "workspace", lane_root / "state"
            copy_tree(scenario.seed_dir, ws_root)
            state_dir.mkdir()
            lanes.append(_Lane(agent=agent, root=lane_root, workspace=Workspace(ws_root), state_dir=state_dir))
            evaluator.add_agent(agent.name)
            redact.add(ws_root, f"<workspace:{agent.name}>")
            redact.add(state_dir, f"<state:{agent.name}>")
            redact.add(lane_root, f"<lane:{agent.name}>")
        redact.add(run_dir, "<run>")
        redact.add(runs_dir, "<runs>")
        redact.add(scenario.base_dir, "<repo>")
        redact.add(Path(harness.__file__).resolve().parents[1], "<src>")
        redact.add(Path.home(), "<home>")
        redact.add(tempfile.gettempdir(), "<tmp>")

        protected = denied_base + [run_dir] + evaluator.private_paths
        for lane in lanes:
            lane.workspace = Workspace(lane.workspace.root, protected)
        # Agent code may not touch evaluator data, run outputs, the world sources,
        # any workspace (ToolBox only) or other lanes; it may write only to its state.
        guard_stack.enter_context(guard.armed(protected + [lane.root for lane in lanes]))
        for lane in lanes:
            guard.register_lane(lane.name, lane.state_dir)

        def guarded(lane: _Lane, fn: Callable[[], Any]) -> tuple[Any, BaseException | None, list[str]]:
            """Run agent code; returns (result, exception, guard violations). Only Ctrl-C escapes."""
            collected: list[str] = []
            try:
                with guard.agent_call(lane.name, lane.state_dir, guard.lane_env(lane.state_dir)) as collected:
                    return fn(), None, collected
            except KeyboardInterrupt:
                raise
            except BaseException as exc:  # noqa: BLE001 - agent faults (even SystemExit) are data
                return None, exc, collected

        def describe_exc(exc: BaseException) -> tuple[str | None, str | None]:
            text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            return redact(f"{type(exc).__name__}: {exc}"), redact(text)

        def make_recorder(lane: _Lane, seq: int, calls: list[dict[str, Any]]) -> Callable[[dict[str, Any]], None]:
            def recorder(rec: dict[str, Any]) -> None:
                rec = dict(rec)
                result_sha = store_blob(rec.pop("result")) if "result" in rec else None
                if "error" in rec:
                    rec["error"] = redact(rec["error"])
                full = {"seq": seq, "agent": lane.name, "call_index": len(calls), **rec}
                if result_sha is not None:
                    full["result_sha256"] = result_sha
                trace.emit("tool_call", **full)
                calls.append({"tool": rec["tool"], "args": _summarize_args(rec["args"]), "status": rec["status"]})

            return recorder

        trace.emit(
            "run_start",
            schema_version=TRACE_SCHEMA_VERSION,
            harness_version=HARNESS_VERSION,
            evaluator_version=EVALUATOR_VERSION,
            code_hashes=code,
            environment=env,
            scenario=scenario_info,
            agents=agent_specs,
            config=run_config,
            initial={lane.name: {"workspace_tree": tree_hash(lane.workspace.root)} for lane in lanes},
        )

        # Setup: identical context for every agent.
        for lane in lanes:
            ctx = AgentContext(
                agent_name=lane.name,
                seed=config.seed,
                state_dir=lane.state_dir,
                budget=budget,
                model=config.model,
                instructions=INSTRUCTIONS,
                instructions_version=INSTRUCTIONS_VERSION,
            )
            _, exc, violations = guarded(lane, lambda: lane.agent.setup(ctx))
            if exc is None:
                trace.emit("agent_setup", agent=lane.name, status="ok", error=None, guard_violations=violations)
            else:
                lane.enabled = False
                error, tb = describe_exc(exc)
                trace.emit(
                    "agent_setup",
                    agent=lane.name,
                    status="agent_error",
                    error=error,
                    traceback=tb,
                    guard_violations=violations,
                )

        # Step 0: optional ingestion of the seed world, same budget for every agent.
        for lane in lanes:
            if lane.enabled:
                start_calls: list[dict[str, Any]] = []
                tools = ToolBox(lane.workspace, budget, make_recorder(lane, 0, start_calls))
                status_s, error, tb = "ok", None, None
                _, exc, violations = guarded(lane, lambda: lane.agent.on_start(tools))
                tools.close()
                if isinstance(exc, BudgetExceeded):
                    status_s, error = "budget_exceeded", redact(str(exc))
                elif exc is not None:
                    status_s = "agent_error"
                    error, tb = describe_exc(exc)
                if tools.exhausted and status_s == "ok":
                    status_s, error = "budget_exceeded", "tool-call budget exhausted (exception caught by agent)"
                lane.tool_calls += tools.calls_made
                trace.emit(
                    "agent_start",
                    agent=lane.name,
                    status=status_s,
                    error=error,
                    traceback=tb,
                    guard_violations=violations,
                    tool_calls=tools.calls_made,
                    workspace_tree=tree_hash(lane.workspace.root),
                    state_tree=tree_hash(lane.state_dir),
                )
            lane.expected_tree = tree_hash(lane.workspace.root)

        for event in events:
            view = event.agent_view()
            view_dict = view.to_dict()
            conflicts: dict[str, list[dict[str, Any]]] = {}
            # 1. apply the event to every isolated world
            for lane in lanes:
                before = tree_hash(lane.workspace.root)
                if before != lane.expected_tree:
                    trace.emit(
                        "out_of_band_mutation", seq=event.seq, agent=lane.name, expected=lane.expected_tree, actual=before
                    )
                applied = apply_event(event, lane.workspace)
                conflicts[lane.name] = applied.conflicts
                trace.emit(
                    "world_event_applied",
                    seq=event.seq,
                    event_id=event.event_id,
                    agent=lane.name,
                    ops=applied.ops,
                    conflicts=applied.conflicts,
                    tree_before=before,
                    tree_after=tree_hash(lane.workspace.root),
                )
            events_out.write(
                {
                    "seq": event.seq,
                    "event_id": event.event_id,
                    "delivered": view_dict,
                    "delivered_sha256": store_blob(view_dict),
                    "world_changes": [c.summary() for c in event.world_changes],
                    "conflicts": conflicts,
                }
            )

            # 2. give each agent the event, in a seeded per-step order
            order = step_order([lane.name for lane in lanes], config.seed, event.seq)
            trace.emit("step_order", seq=event.seq, order=order)
            by_name = {lane.name: lane for lane in lanes}
            step_actions: dict[str, list] = {lane.name: [] for lane in lanes}
            for name in order:
                lane = by_name[name]
                if not lane.enabled:
                    lane.status_counts["disabled"] = lane.status_counts.get("disabled", 0) + 1
                    actions_out.write(
                        {
                            "seq": event.seq,
                            "event_id": event.event_id,
                            "agent": lane.name,
                            "status": "disabled",
                            "error": None,
                            "actions": [],
                            "usage": Usage().to_dict(),
                            "tool_calls": [],
                        }
                    )
                    lane.expected_tree = tree_hash(lane.workspace.root)
                    continue
                trace.emit(
                    "event_delivered",
                    seq=event.seq,
                    event_id=event.event_id,
                    agent=lane.name,
                    event_sha256=sha256_json(view_dict),
                )
                calls: list[dict[str, Any]] = []
                tools = ToolBox(lane.workspace, budget, make_recorder(lane, event.seq, calls))
                status_s, error, tb = "ok", None, None
                t0 = time.perf_counter()
                response, exc, violations = guarded(lane, lambda: lane.agent.on_event(view, tools))
                tools.close()
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if isinstance(exc, BudgetExceeded):
                    status_s, error, response = "budget_exceeded", redact(str(exc)), AgentResponse()
                elif exc is not None:
                    status_s, response = "agent_error", AgentResponse()
                    error, tb = describe_exc(exc)
                else:
                    try:
                        _validate_response(response)
                    except TypeError as invalid:
                        status_s, error, response = "invalid_response", str(invalid), AgentResponse()
                if tools.exhausted and status_s == "ok":
                    status_s, error = "budget_exceeded", "tool-call budget exhausted (exception caught by agent)"

                lane.status_counts[status_s] = lane.status_counts.get(status_s, 0) + 1
                lane.tool_calls += tools.calls_made
                lane.wall_clock_ms += elapsed_ms
                for k, v in response.usage.to_dict().items():
                    lane.usage[k] += v
                actions_dicts = [a.to_dict() for a in response.actions]
                step_actions[lane.name] = list(response.actions)
                trace.emit(
                    "agent_response",
                    seq=event.seq,
                    agent=lane.name,
                    status=status_s,
                    error=error,
                    traceback=tb,
                    guard_violations=violations,
                    actions=actions_dicts,
                    usage=response.usage.to_dict(),
                    tool_calls=tools.calls_made,
                    wall_clock_ms=round(elapsed_ms, 3),
                )
                lane.expected_tree = tree_hash(lane.workspace.root)
                trace.emit(
                    "step_complete",
                    seq=event.seq,
                    agent=lane.name,
                    workspace_tree=lane.expected_tree,
                    state_tree=tree_hash(lane.state_dir),
                )
                actions_out.write(
                    {
                        "seq": event.seq,
                        "event_id": event.event_id,
                        "agent": lane.name,
                        "status": status_s,
                        "error": error,
                        "actions": actions_dicts,
                        "usage": response.usage.to_dict(),
                        "tool_calls": calls,
                        "wall_clock_ms": round(elapsed_ms, 3),
                    }
                )

            # 3. evaluator observation only after every agent completed this step
            for lane in lanes:
                reopens = evaluator.observe_step(lane.name, event.seq, step_actions[lane.name])
                record: dict[str, Any] = {"seq": event.seq, "agent": lane.name, "reopens": reopens}
                if evaluator.needs_snapshot(event.seq):
                    record["snapshot"] = evaluator.snapshot(lane.name, event.seq, lane.workspace.root)
                evaluation_out.write(record)
            metadata["last_completed_seq"] = event.seq
            write_json_atomic(run_dir / "metadata.json", metadata)

        for lane in lanes:
            if not lane.enabled:
                continue
            _, exc, violations = guarded(lane, lane.agent.teardown)
            if exc is None:
                trace.emit("agent_teardown", agent=lane.name, status="ok", error=None, guard_violations=violations)
            else:
                error, tb = describe_exc(exc)
                trace.emit(
                    "agent_teardown",
                    agent=lane.name,
                    status="agent_error",
                    error=error,
                    traceback=tb,
                    guard_violations=violations,
                )
            final_tree = tree_hash(lane.workspace.root)
            if final_tree != lane.expected_tree:
                trace.emit(
                    "out_of_band_mutation", seq=None, agent=lane.name, expected=lane.expected_tree, actual=final_tree
                )

        alive = guard.live_agent_threads()
        if alive:
            # Threads outliving teardown are no longer guarded once the run ends.
            trace.emit("agent_threads_alive", counts=dict(sorted(alive.items())))
        guard_stack.close()

        copy_final_state()
        efficiency = {
            lane.name: {
                **lane.usage,
                "tool_calls": lane.tool_calls,
                "steps": len(events),
                "wall_clock_ms": round(lane.wall_clock_ms, 3),
            }
            for lane in lanes
        }
        final_ws = (
            {lane.name: run_dir / "final_state" / lane.name / "workspace" for lane in lanes} if config.hygiene else None
        )
        scores = evaluator.finalize(efficiency, {lane.name: lane.status_counts for lane in lanes}, final_ws)
        write_json_atomic(run_dir / "scores.json", scores)

        # Ground truth and events must be byte-identical to what the run started with.
        if scenario.compute_content_hashes() != content_hashes:
            metadata["integrity"] = "scenario content changed during the run"
            trace.emit("run_end", status="integrity_failed", error=metadata["integrity"])
            status = "integrity_failed"
        else:
            metadata["integrity"] = "ok"
            trace.emit("run_end", status="completed", error=None)
            status = "completed"
    except BaseException as exc:
        status = "aborted" if isinstance(exc, KeyboardInterrupt) else "failed"
        metadata["error"] = redact(f"{type(exc).__name__}: {exc}")
        try:
            trace.emit("run_end", status=status, error=metadata["error"], traceback=redact(traceback.format_exc()))
        except Exception:  # noqa: BLE001 - never mask the original failure
            pass
        raise
    finally:
        # Every finalization step runs even if an earlier one fails, and none of
        # them may replace the exception that ended the run.
        finalization_errors: list[str] = []

        def attempt(label: str, fn: Callable[[], Any]) -> None:
            try:
                fn()
            except Exception as fin_exc:  # noqa: BLE001
                finalization_errors.append(redact(f"{label}: {type(fin_exc).__name__}: {fin_exc}") or label)

        attempt("disarm guard", guard_stack.close)
        attempt("copy final state", copy_final_state)
        for writer in (trace, events_out, actions_out, evaluation_out):
            attempt(f"close {writer.path.name}", writer.close)
        for lane in lanes:
            shutil.rmtree(lane.root, ignore_errors=True)
        attempt("evaluator cleanup", evaluator.close)
        metadata["status"] = status
        metadata["finished_at"] = _now_iso()
        if status == "completed":
            attempt("fingerprint", lambda: metadata.__setitem__("fingerprint", run_fingerprint(run_dir)))
        if finalization_errors:
            metadata["finalization_errors"] = finalization_errors
        attempt("metadata", lambda: write_json_atomic(run_dir / "metadata.json", metadata))
        attempt("manifest", lambda: write_manifest(run_dir))

    return RunResult(run_id=run_id, run_dir=run_dir, status=status, scores=scores, fingerprint=metadata["fingerprint"])
