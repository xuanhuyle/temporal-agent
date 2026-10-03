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

Protocol v0.2 (``docs/protocol-amendments.md``) adds, identically for every agent:
the shared world history (a private world-only copy of the repository is
advanced in lockstep and each state is revealed to the history service only
when its event is applied), ``run_command``, harness-metered model access
through one run-level gateway, and contestant processes
(``harness.process.ProcessAgent``) with a per-event wall-clock budget.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import platform
import random
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import evaluation
import harness
from evaluation.ground_truth import GT_SCHEMA_VERSION, load_ground_truth
from evaluation.scorer import EVALUATOR_VERSION, SCORES_SCHEMA_VERSION, Evaluator
from harness import HARNESS_VERSION, guard
from harness.commands import CommandRunner
from harness.history import WorldHistory
from harness.model import create_gateway
from harness.process import ContestantCrashed, InvalidContestantResponse, StepTimeout
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
from harness.tools import BudgetExceeded, ToolBox, empty_meter
from harness.trace import TRACE_SCHEMA_VERSION, JsonlWriter, TraceWriter, run_fingerprint, write_json_atomic
from harness.workspace import Workspace
from harness.world import apply_event

RUN_SCHEMA_VERSION = "tab.run/1"
PROTOCOL_VERSION = "v0.2"
# Default output root of the CLI; always protected, even when a run writes elsewhere.
DEFAULT_RUNS_ROOT = Path(__file__).resolve().parents[2] / "runs"
AGENT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
OUTPUT_FILES = (
    "metadata.json", "events.jsonl", "actions.jsonl", "scores.json", "trace.jsonl", "evaluation.jsonl", "process.jsonl",
)
# Source packages whose code determines contestant behaviour (part of the run's code hashes).
CONTESTANT_PACKAGES = ("contestant_runtime", "baseline")
USAGE_KEYS = ("model_input_tokens", "model_output_tokens", "retrieval_tokens", "model_calls", "cost_usd")
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
    # Replay only: recorded model/embedding calls served instead of a live provider.
    recorded_model_calls: tuple[dict[str, Any], ...] | None = None
    # Replay only: the time limit each tool call had in the original run, agent -> seq -> call index -> seconds.
    recorded_time_limits: Mapping[str, Mapping[int, Mapping[int, float]]] | None = None
    # Replay only: the price table the original run used (otherwise built-in prices + TAB_MODEL_PRICING).
    model_pricing: Any = None
    # Contestants (role "contestant") must run in their own process (protocol amendment A4). Tests may allow
    # in-process contestants explicitly; the run records it.
    allow_in_process_contestants: bool = False


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
    commands: CommandRunner | None = None
    enabled: bool = True
    expected_tree: str = ""
    # Harness-metered usage (protocol amendment A3), summed over steps.
    usage: dict[str, Any] = field(default_factory=empty_meter)
    # What the agent reported itself (kept for reference; not used for efficiency).
    reported: dict[str, Any] = field(default_factory=lambda: {k: 0 for k in USAGE_KEYS} | {"cost_usd": 0.0})
    wall_clock_ms: float = 0.0
    status_counts: dict[str, int] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.agent.name

    @property
    def process(self) -> bool:
        return is_process_agent(self.agent)

    def add_meter(self, meter: dict[str, Any]) -> None:
        for k, v in meter.items():
            if isinstance(v, bool):  # cost_known / tokens_known: false once any step lacked the figure
                self.usage[k] = bool(self.usage.get(k, True) and v)
            elif isinstance(v, (int, float)):
                self.usage[k] = self.usage.get(k, 0) + v

    def add_reported(self, usage: dict[str, Any]) -> None:
        for k in USAGE_KEYS:
            self.reported[k] += usage.get(k, 0)


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
    """Content hashes of the harness, evaluator and contestant source trees."""
    out = {
        "harness": tree_hash(Path(harness.__file__).resolve().parent),
        "evaluation": tree_hash(Path(evaluation.__file__).resolve().parent),
    }
    src = Path(harness.__file__).resolve().parents[1]
    for pkg in CONTESTANT_PACKAGES:
        if (src / pkg).is_dir():
            out[pkg] = tree_hash(src / pkg)
    return out


def is_process_agent(agent: Agent) -> bool:
    """True for contestants that run in their own process (``harness.process.ProcessAgent``)."""
    return getattr(agent, "isolation", "in_process") == "process"


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
    """``describe()`` is agent code too: run it under the guard in a throwaway directory.

    A process agent's proxy is harness code; it asks its own contestant process.
    """
    if is_process_agent(agent):
        return _describe(agent)
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


def _is_unrecordable(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"unrecordable_type"}


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


def remove_tree(path: Path) -> None:
    """Remove a lane or scratch tree even if agent code or a command made directories non-writable."""
    path = Path(path)
    if not path.exists():
        return
    for dirpath, dirnames, _ in os.walk(path, followlinks=False):
        for d in dirnames:
            full = os.path.join(dirpath, d)
            try:
                if not os.path.islink(full):
                    os.chmod(full, stat.S_IRWXU)
            except OSError:
                pass
    try:
        os.chmod(path, stat.S_IRWXU)
    except OSError:
        pass
    shutil.rmtree(path, ignore_errors=True)


@contextlib.contextmanager
def _terminate_as_interrupt():
    """While a run is in progress, SIGTERM and SIGHUP end it like Ctrl-C, so finalization still runs."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def handler(signum: int, frame: Any) -> None:
        raise KeyboardInterrupt(f"received signal {signum}")

    previous = {}
    for sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            previous[sig] = signal.signal(sig, handler)
        except (ValueError, OSError):
            pass
    try:
        yield
    finally:
        for sig, old in previous.items():
            signal.signal(sig, old)


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
    with _terminate_as_interrupt():
        return _run(scenario, agents, config, replay_of=replay_of)


def _run(
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
    # One gateway per run: every agent gets the same model settings (protocol amendment A3).
    gateway = create_gateway(config.model, recorded=config.recorded_model_calls, pricing=config.model_pricing)
    agent_specs = [{"name": a.name, **_describe_guarded(a, denied_base)} for a in agents]
    if scenario.status != "frozen":
        contestants = [s["name"] for s in agent_specs if s["role"] not in NON_CONTESTANT_ROLES]
        if contestants:
            raise ScenarioError(f"contestants {contestants} may only run on frozen scenarios (EXPERIMENT.md §14)")
    in_process_contestants = [
        s["name"] for s, a in zip(agent_specs, agents)
        if s["role"] not in NON_CONTESTANT_ROLES and not is_process_agent(a)
    ]
    if in_process_contestants and replay_of is None and not config.allow_in_process_contestants:
        raise ValueError(
            f"contestants {in_process_contestants} must run in their own process (protocol amendment A4); "
            "use harness.process.ProcessAgent"
        )

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
        "protocol_version": PROTOCOL_VERSION,
        "seed": config.seed,
        "budget": budget.to_dict(),
        "model": config.model.to_dict(),
        "model_gateway": gateway.describe(),
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
        "protocol_version": PROTOCOL_VERSION,
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
        "isolation": {a.name: ("process" if is_process_agent(a) else "in_process") for a in agents},
        "config": {**run_config, "allow_draft": config.allow_draft,
                   "allow_in_process_contestants": config.allow_in_process_contestants},
        "config_hash": config_hash,
        "token_accounting": (
            "harness-metered (protocol v0.2, amendment A3): model and embedding usage is counted by the harness "
            "gateway; agents' self-reported Usage is kept as reported_usage and not used for efficiency"
        ),
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
    # Facts read from the machine (e.g. the Claude CLI version); not part of the run's configuration hash.
    metadata["model_runtime"] = gateway.runtime_info() if config.recorded_model_calls is None else {"backend": "recorded"}
    write_json_atomic(run_dir / "metadata.json", metadata)

    trace = TraceWriter(run_dir / "trace.jsonl")
    events_out = JsonlWriter(run_dir / "events.jsonl")
    actions_out = JsonlWriter(run_dir / "actions.jsonl")
    evaluation_out = JsonlWriter(run_dir / "evaluation.jsonl")
    # Contestant-process lifecycle (spawns, restarts, exits). Volatile, so not fingerprinted.
    process_out = JsonlWriter(run_dir / "process.jsonl")
    blobs_dir = run_dir / "blobs"
    blobs_dir.mkdir()
    redact = _Redactor()
    guard_stack = contextlib.ExitStack()
    lanes: list[_Lane] = []
    world_tmp: Path | None = None
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
            logs = lane.root / "logs"
            if logs.is_dir():
                copy_tree(logs, dest / "logs", regular_only=True)

    def close_processes() -> None:
        for lane in lanes:
            close = getattr(lane.agent, "close", None)
            if lane.process and callable(close):
                close()

    try:
        evaluator.open()
        for agent in agents:
            lane_root = Path(tempfile.mkdtemp(prefix="tab-lane-"))
            ws_root, state_dir = lane_root / "workspace", lane_root / "state"
            copy_tree(scenario.seed_dir, ws_root)
            state_dir.mkdir()
            lanes.append(
                _Lane(
                    agent=agent,
                    root=lane_root,
                    workspace=Workspace(ws_root),
                    state_dir=state_dir,
                    commands=CommandRunner(ws_root, lane_root / "cmd"),
                )
            )
            evaluator.add_agent(agent.name)
            redact.add(ws_root, f"<workspace:{agent.name}>")
            redact.add(state_dir, f"<state:{agent.name}>")
            redact.add(lane_root, f"<lane:{agent.name}>")
        # The world-only copy behind the shared history (protocol amendment A1). No agent can reach it.
        world_tmp = Path(tempfile.mkdtemp(prefix="tab-world-"))
        world_root = world_tmp / "world"
        copy_tree(scenario.seed_dir, world_root)
        world_ws = Workspace(world_root)
        history = WorldHistory()
        # A frozen scenario records the world state after every event; a draft's record may be stale.
        expected_states = (scenario.data.get("world_state_hashes") or []) if scenario.status == "frozen" else []
        redact.add(world_tmp, "<world>")
        redact.add(run_dir, "<run>")
        redact.add(runs_dir, "<runs>")
        redact.add(scenario.base_dir, "<repo>")
        redact.add(Path(harness.__file__).resolve().parents[1], "<src>")
        redact.add(Path.home(), "<home>")
        redact.add(tempfile.gettempdir(), "<tmp>")

        protected = denied_base + [run_dir, world_tmp] + evaluator.private_paths
        for lane in lanes:
            lane.workspace = Workspace(lane.workspace.root, protected)
        # Agent code may not touch evaluator data, run outputs, the world sources,
        # any workspace (ToolBox only) or other lanes; it may write only to its state.
        guard_stack.enter_context(guard.armed(protected + [lane.root for lane in lanes]))
        for lane in lanes:
            guard.register_lane(lane.name, lane.state_dir)

        def reveal_world(seq: int, event: Event | None) -> None:
            changed = [] if event is None else [asdict(c) for c in event.agent_view().changed_paths]
            digest = history.reveal(
                seq,
                WorldHistory.snapshot_files(world_root),
                event_id=None if event is None else event.event_id,
                timestamp=None if event is None else event.timestamp,
                changed_paths=changed,
            )
            expected = content_hashes.get("seed_repo") if seq == 0 else (
                expected_states[seq - 1] if len(expected_states) >= seq else None
            )
            if expected is not None and digest != expected:
                raise RuntimeError(f"world state after seq {seq} differs from the scenario's recorded world state")
            trace.emit("world_state_revealed", seq=seq, tree_sha256=digest)

        def guarded(lane: _Lane, fn: Callable[[], Any]) -> tuple[Any, BaseException | None, list[str]]:
            """Run agent code; returns (result, exception, guard violations). Only Ctrl-C escapes."""
            if lane.process:
                # The proxy is harness code; the contestant runs in its own process under a tripwire.
                try:
                    return fn(), None, list(getattr(lane.agent, "last_violations", []))
                except KeyboardInterrupt:
                    raise
                except BaseException as exc:  # noqa: BLE001 - contestant faults are data
                    return None, exc, list(getattr(lane.agent, "last_violations", []))
            collected: list[str] = []
            try:
                with guard.agent_call(lane.name, lane.state_dir, guard.lane_env(lane.state_dir)) as collected:
                    return fn(), None, collected
            except KeyboardInterrupt:
                raise
            except BaseException as exc:  # noqa: BLE001 - agent faults (even SystemExit) are data
                return None, exc, collected

        def describe_exc(exc: BaseException) -> tuple[str | None, str | None]:
            child_tb = getattr(exc, "child_traceback", None)
            text = child_tb if isinstance(child_tb, str) else "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )
            return redact(f"{type(exc).__name__}: {exc}"), redact(text)

        def classify(exc: BaseException | None) -> tuple[str, str | None, str | None]:
            """Step status, error and traceback for an agent call's outcome."""
            if exc is None:
                return "ok", None, None
            if isinstance(exc, BudgetExceeded):
                return "budget_exceeded", redact(str(exc)), None
            if isinstance(exc, StepTimeout):
                return "timeout", redact(str(exc)), None
            if isinstance(exc, InvalidContestantResponse):
                return "invalid_response", redact(str(exc)), None
            if isinstance(exc, ContestantCrashed):
                return "crashed", redact(f"{type(exc).__name__}: {exc}"), None
            error, tb = describe_exc(exc)
            return "agent_error", error, tb

        def check_provider() -> None:
            """Stop the run if the model provider can no longer serve it (login, usage limit, CLI missing)."""
            if gateway.fatal_error:
                raise RuntimeError(f"model provider unavailable; run stopped: {gateway.fatal_error}")

        def drain_notices(lane: _Lane, seq: int | None) -> None:
            drain = getattr(lane.agent, "drain_notices", None)
            if lane.process and callable(drain):
                for notice in drain():
                    process_out.write({"seq": seq, "agent": lane.name, **notice})

        def make_recorder(lane: _Lane, seq: int, calls: list[dict[str, Any]]) -> Callable[[dict[str, Any]], None]:
            def recorder(rec: dict[str, Any]) -> None:
                rec = dict(rec)
                result_sha = store_blob(rec.pop("result")) if "result" in rec else None
                if "error" in rec:
                    rec["error"] = redact(rec["error"])
                # Structured arguments (model requests, embedding inputs) are stored content-addressed.
                rec["args"] = {
                    k: ({"blob": store_blob(v)} if isinstance(v, (list, dict)) and not _is_unrecordable(v) else v)
                    for k, v in rec["args"].items()
                }
                full = {"seq": seq, "agent": lane.name, "call_index": len(calls), **rec}
                if result_sha is not None:
                    full["result_sha256"] = result_sha
                trace.emit("tool_call", **full)
                calls.append({"tool": rec["tool"], "args": _summarize_args(rec["args"]), "status": rec["status"]})

            return recorder

        def make_tools(lane: _Lane, seq: int, calls: list[dict[str, Any]]) -> ToolBox:
            deadline = time.monotonic() + budget.wall_clock_s_per_event if lane.process else None
            limits = None
            if config.recorded_time_limits is not None:
                step_limits = config.recorded_time_limits.get(lane.name, {}).get(seq, {})
                limits = step_limits.get
            return ToolBox(
                lane.workspace,
                budget,
                make_recorder(lane, seq, calls),
                history=history,
                commands=lane.commands,
                model=gateway.lane(lane.name),
                deadline=deadline,
                time_limits=limits,
            )

        trace.emit(
            "run_start",
            schema_version=TRACE_SCHEMA_VERSION,
            protocol_version=PROTOCOL_VERSION,
            harness_version=HARNESS_VERSION,
            evaluator_version=EVALUATOR_VERSION,
            code_hashes=code,
            environment=env,
            scenario=scenario_info,
            agents=agent_specs,
            config=run_config,
            initial={lane.name: {"workspace_tree": tree_hash(lane.workspace.root)} for lane in lanes},
        )
        reveal_world(0, None)  # state 0 (the seed) exists before any agent code runs

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
            drain_notices(lane, None)
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

        # Step 0: optional ingestion of the seed world, same budget for every agent, in a seeded order
        # (like every event step), so no agent is systematically first (e.g. to warm a provider cache).
        by_name0 = {lane.name: lane for lane in lanes}
        order0 = step_order([lane.name for lane in lanes], config.seed, 0)
        trace.emit("step_order", seq=0, order=order0)
        for lane in [by_name0[n] for n in order0]:
            if lane.enabled:
                start_calls: list[dict[str, Any]] = []
                tools = make_tools(lane, 0, start_calls)
                t0 = time.perf_counter()
                _, exc, violations = guarded(lane, lambda: lane.agent.on_start(tools))
                tools.close()
                lane.wall_clock_ms += (time.perf_counter() - t0) * 1000.0
                drain_notices(lane, 0)
                status_s, error, tb = classify(exc)
                if tools.exhausted and status_s == "ok":
                    status_s, error = "budget_exceeded", "tool-call budget exhausted (exception caught by agent)"
                meter = tools.meter()
                lane.add_meter(meter)
                trace.emit(
                    "agent_start",
                    agent=lane.name,
                    status=status_s,
                    error=error,
                    traceback=tb,
                    guard_violations=violations,
                    tool_calls=tools.calls_made,
                    usage=meter,
                    workspace_tree=tree_hash(lane.workspace.root),
                    state_tree=tree_hash(lane.state_dir),
                )
                check_provider()
            lane.expected_tree = tree_hash(lane.workspace.root)

        for event in events:
            view = event.agent_view()
            view_dict = view.to_dict()
            conflicts: dict[str, list[dict[str, Any]]] = {}
            # 1. apply the event to every isolated world, and to the world-only copy behind the history
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
            apply_event(event, world_ws)
            reveal_world(event.seq, event)
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
                            "usage": empty_meter(),
                            "reported_usage": Usage().to_dict(),
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
                tools = make_tools(lane, event.seq, calls)
                t0 = time.perf_counter()
                response, exc, violations = guarded(lane, lambda: lane.agent.on_event(view, tools))
                tools.close()
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                drain_notices(lane, event.seq)
                status_s, error, tb = classify(exc)
                if exc is not None:
                    response = AgentResponse()
                else:
                    try:
                        _validate_response(response)
                    except TypeError as invalid:
                        status_s, error, response = "invalid_response", str(invalid), AgentResponse()
                if tools.exhausted and status_s == "ok":
                    status_s, error = "budget_exceeded", "tool-call budget exhausted (exception caught by agent)"

                meter = tools.meter()
                lane.status_counts[status_s] = lane.status_counts.get(status_s, 0) + 1
                lane.wall_clock_ms += elapsed_ms
                lane.add_meter(meter)
                reported = response.usage.to_dict()
                lane.add_reported(reported)
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
                    usage=meter,
                    reported_usage=reported,
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
                        "usage": meter,
                        "reported_usage": reported,
                        "tool_calls": calls,
                        "wall_clock_ms": round(elapsed_ms, 3),
                    }
                )
                check_provider()

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
            drain_notices(lane, None)
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
        close_processes()

        alive = guard.live_agent_threads()
        if alive:
            # Threads outliving teardown are no longer guarded once the run ends.
            trace.emit("agent_threads_alive", counts=dict(sorted(alive.items())))
        guard_stack.close()

        copy_final_state()
        efficiency = {
            lane.name: {
                **{k: (round(v, 8) if k == "cost_usd" else v) for k, v in lane.usage.items()},
                "steps": len(events),
                "wall_clock_ms": round(lane.wall_clock_ms, 3),
                "reported_usage": {k: (round(v, 8) if k == "cost_usd" else v) for k, v in lane.reported.items()},
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

        attempt("stop contestant processes", close_processes)
        attempt("close model gateway", gateway.close)
        attempt("disarm guard", guard_stack.close)
        attempt("copy final state", copy_final_state)
        for writer in (trace, events_out, actions_out, evaluation_out, process_out):
            attempt(f"close {writer.path.name}", writer.close)
        for lane in lanes:
            remove_tree(lane.root)
        if world_tmp is not None:
            remove_tree(world_tmp)
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
