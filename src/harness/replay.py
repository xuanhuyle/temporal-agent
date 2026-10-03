"""Replay a recorded run and verify it reproduces exactly.

A :class:`ReplayAgent` re-issues each recorded tool call (including failed and
denied ones) and returns the recorded actions and usage, reproducing recorded
agent failures and timeouts. The replay is written to a *new* run directory and
compared record-by-record with the original (volatile keys excluded). Private
agent state (``state_tree``) is not reproducible by replay and is excluded.

Workspace, history and command calls are re-executed for real (so their
results are verified). Model and embedding calls are re-issued too, but the
run's gateway serves the *recorded* responses instead of calling a provider,
after checking that each request is byte-identical to the recorded one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.agent import (
    USAGE_FIELDS,
    Agent,
    AgentEvent,
    AgentResponse,
    ModelSettings,
    StepBudget,
    Usage,
    action_from_dict,
)
from harness.model.recorded import recorded_calls_from_trace
from harness.process import StepTimeout
from harness.runner import RunConfig, RunResult, run, write_manifest
from harness.scenario import ScenarioError, load_scenario
from harness.tools import BudgetExceeded, ToolBox
from harness.trace import FINGERPRINT_FILES, canonical_records, read_jsonl, run_fingerprint, write_json_atomic
from harness.workspace import ToolError

# Private agent state and out-of-band accesses caught by the guard are agent
# internals that replay (which re-issues only ToolBox calls) cannot reproduce.
REPLAY_EXEMPT_KEYS = ("state_tree", "guard_violations")
SWALLOWED_BUDGET = "tool-call budget exhausted (exception caught by agent)"


class ReplayError(RuntimeError):
    pass


def _recreate_exception(error: str) -> Exception:
    """Rebuild an exception whose ``f"{type}: {msg}"`` rendering equals ``error``."""
    name, sep, message = error.partition(": ")
    if not sep or not name.isidentifier():
        name, message = "AgentError", error
    return type(name, (Exception,), {})(message)


def _reconstruct_arg(value: Any) -> Any:
    """Recorded non-string arguments come back as an object of the same type name."""
    if isinstance(value, dict) and set(value) == {"unrecordable_type"}:
        return type(value["unrecordable_type"], (), {})()
    return value


class _Unexpected:
    """Stand-in for a non-AgentResponse return value."""


def _recreate_invalid_response(error: str) -> Any:
    prefix = "on_event must return AgentResponse, got "
    if error.startswith(prefix):
        type_name = error[len(prefix):]
        if type_name == "NoneType":
            return None
        return type(type_name, (_Unexpected,), {})()
    if "usage" in error:
        return AgentResponse(usage=None)  # type: ignore[arg-type]
    return AgentResponse(actions=[None])  # type: ignore[list-item]


class ReplayAgent(Agent):
    kind = "replay"

    def __init__(
        self, name: str, description: dict[str, Any], records: list[dict[str, Any]], blobs_dir: Path | None = None
    ) -> None:
        super().__init__(name)
        self._blobs_dir = blobs_dir
        self._description = {k: v for k, v in description.items() if k != "name"}
        self._setup: dict[str, Any] | None = None
        self._start: dict[str, Any] | None = None
        self._teardown: dict[str, Any] | None = None
        self._calls: dict[int, list[dict[str, Any]]] = {}
        self._responses: dict[int, dict[str, Any]] = {}
        for rec in records:
            if rec.get("agent") != name:
                continue
            t = rec["type"]
            if t == "agent_setup":
                self._setup = rec
            elif t == "agent_start":
                self._start = rec
            elif t == "agent_teardown":
                self._teardown = rec
            elif t == "tool_call":
                # Resolve blob-stored arguments now: during the replayed run this agent's
                # code runs under the guard, which forbids reading the run directory.
                rec = {**rec, "args": {k: self._arg(v) for k, v in rec["args"].items()}}
                self._calls.setdefault(rec["seq"], []).append(rec)
            elif t == "agent_response":
                self._responses[rec["seq"]] = rec

    def describe(self) -> dict[str, Any]:
        return self._description

    def setup(self, context) -> None:  # type: ignore[override]
        super().setup(context)
        if self._setup and self._setup["status"] != "ok":
            raise _recreate_exception(self._setup["error"])

    def _arg(self, value: Any) -> Any:
        if isinstance(value, dict) and set(value) == {"blob"}:
            if self._blobs_dir is None:
                raise ReplayError("recorded argument is stored as a blob but no blob directory was given")
            return load_blob(self._blobs_dir, value["blob"])
        return _reconstruct_arg(value)

    def _replay_calls(self, seq: int, rec: dict[str, Any] | None, tools: ToolBox) -> None:
        """Re-issue every recorded call of a step, then reproduce a budget overrun or timeout that ended it."""
        for call in self._calls.get(seq, []):
            fn = getattr(tools, call["tool"])
            try:
                fn(**call["args"])
            except (ToolError, BudgetExceeded):
                pass
        if rec and rec["status"] == "budget_exceeded" and rec["error"] != SWALLOWED_BUDGET:
            raise BudgetExceeded(rec["error"])
        if rec and rec["status"] == "timeout":
            raise StepTimeout(rec["error"])

    def on_start(self, tools: ToolBox) -> None:
        self._replay_calls(0, self._start, tools)
        if self._start and self._start["status"] == "agent_error":
            raise _recreate_exception(self._start["error"])

    def teardown(self) -> None:
        if self._teardown and self._teardown["status"] != "ok":
            raise _recreate_exception(self._teardown["error"])

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:
        resp = self._responses.get(event.seq)
        if resp is None:
            raise ReplayError(f"no recorded response for {self.name} at seq {event.seq}")
        self._replay_calls(event.seq, resp, tools)
        if resp["status"] == "agent_error":
            raise _recreate_exception(resp["error"])
        if resp["status"] == "invalid_response":
            return _recreate_invalid_response(resp["error"])  # type: ignore[return-value]
        reported = resp.get("reported_usage", resp["usage"])  # Milestone-1 traces have only "usage"
        return AgentResponse(
            actions=[action_from_dict(a) for a in resp["actions"]],
            usage=Usage(**{k: reported[k] for k in USAGE_FIELDS if k in reported}),
        )


def load_blob(blobs_dir: Path, digest: str) -> Any:
    if not isinstance(digest, str) or len(digest) != 64 or not all(c in "0123456789abcdef" for c in digest):
        raise ReplayError(f"invalid blob reference {digest!r}")
    return json.loads((Path(blobs_dir) / f"{digest}.json").read_text(encoding="utf-8"))


def recorded_model_calls(records: list[dict[str, Any]], blobs_dir: Path) -> tuple[dict[str, Any], ...]:
    """The run's model and embedding calls that reached a backend, in the gateway's recording format.

    Blob-stored arguments are resolved first, so failed calls can be matched by
    their request hash (see :mod:`harness.model.recorded`).
    """
    resolved = []
    for rec in records:
        if rec.get("type") != "tool_call" or rec.get("tool") not in ("model_complete", "embed"):
            continue
        args = {
            k: (load_blob(blobs_dir, v["blob"]) if isinstance(v, dict) and set(v) == {"blob"} else v)
            for k, v in rec.get("args", {}).items()
        }
        resolved.append({**rec, "args": args})
    return tuple(recorded_calls_from_trace(resolved, lambda sha: load_blob(blobs_dir, sha)))


def compare_runs(original: Path, replayed: Path) -> list[dict[str, Any]]:
    mismatches = []
    for name in FINGERPRINT_FILES:
        a = canonical_records(Path(original) / name, REPLAY_EXEMPT_KEYS)
        b = canonical_records(Path(replayed) / name, REPLAY_EXEMPT_KEYS)
        if a == b:
            continue
        first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        mismatches.append({"file": name, "first_differing_record": first, "records": [len(a), len(b)]})
    return mismatches


def replay_run(run_dir: Path, *, runs_dir: Path | None = None, scenario_path: Path | None = None) -> tuple[RunResult, dict[str, Any]]:
    run_dir = Path(run_dir).resolve()
    meta = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    if meta.get("status") != "completed":
        raise ReplayError(f"run {meta.get('run_id')} did not complete (status={meta.get('status')}); its trace is preserved for inspection")
    candidates = [scenario_path] if scenario_path else [Path(meta["host"]["manifest_path"]), Path(meta["scenario"]["manifest"])]
    scenario = None
    for c in candidates:
        if c and Path(c).exists():
            scenario = load_scenario(Path(c))
            break
    if scenario is None:
        raise ReplayError("scenario manifest not found; pass scenario_path")
    if scenario.compute_content_hashes() != meta["scenario"]["content_hashes"]:
        raise ScenarioError("scenario content differs from the one the run used; replay would not be faithful")

    records = read_jsonl(run_dir / "trace.jsonl")
    blobs_dir = run_dir / "blobs"
    agents = [ReplayAgent(spec["name"], spec, records, blobs_dir) for spec in meta["agents"]]
    cfg = meta["config"]
    config = RunConfig(
        runs_dir=Path(runs_dir) if runs_dir else run_dir.parent,
        seed=cfg["seed"],
        budget=StepBudget(**cfg["budget"]),
        model=ModelSettings(**cfg["model"]),
        allow_draft=cfg["allow_draft"],
        hygiene=cfg.get("hygiene", True),
        recorded_model_calls=recorded_model_calls(records, blobs_dir),
    )
    result = run(scenario, agents, config, replay_of=meta["run_id"])
    mismatches = compare_runs(run_dir, result.run_dir)
    replay_meta = json.loads((result.run_dir / "metadata.json").read_text(encoding="utf-8"))
    report = {
        "replay_of": meta["run_id"],
        "code_hashes_match": replay_meta.get("code_hashes") == meta.get("code_hashes"),
        "replay_run_id": result.run_id,
        "match": not mismatches,
        "mismatches": mismatches,
        "original_fingerprint": run_fingerprint(run_dir, REPLAY_EXEMPT_KEYS),
        "replay_fingerprint": run_fingerprint(result.run_dir, REPLAY_EXEMPT_KEYS),
    }
    write_json_atomic(result.run_dir / "replay_report.json", report)
    write_manifest(result.run_dir)  # keep the manifest complete
    return result, report
