"""BaselineAgent: presets, describe, end-to-end determinism, restart fidelity, import hygiene, in-process run."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from harness.agent import AgentResponse, NoteAction, ReopenAction, StepBudget
from harness.llm import ModelRequest

from baseline.agent import BaselineAgent
from baseline.presets import DEFAULTS, PRESETS, resolve_config
from test_baseline_memory import EVENTS, SEED, apply_world
from test_contestant_runtime import FakeTools, hash_embed, make_context

CONTESTANT_API = ("harness.agent", "harness.errors", "harness.llm", "harness.tool_specs")
OWN_PACKAGES = ("contestant_runtime", "baseline")


# =================================================================== presets
def test_presets_expand_with_shared_defaults():
    for name, top_k in (("k8", 8), ("k32", 32), ("k64", 64)):
        cfg = BaselineAgent(config={"preset": name}).describe()["config"]
        assert cfg["top_k"] == top_k and cfg["mode"] == "rag" and cfg["preset"] == name
        assert cfg["retrieval"] == "hybrid" and cfg["query_expansion"] is True and cfg["summary"] == "rolling"
        assert cfg["max_turns"] == 12 and cfg["observation_chars"] == 8000 and cfg["chunk_chars"] == 1500
        assert cfg["max_per_source"] == 4
    full = BaselineAgent(config={"preset": "full"}).describe()["config"]
    assert full["mode"] == "full" and full["query_expansion"] is False
    assert set(PRESETS) == {"k8", "k32", "k64", "full"}


def test_default_preset_explicit_overrides_and_validation():
    assert BaselineAgent().describe()["config"]["preset"] == "k32"
    assert BaselineAgent(config=None).config == BaselineAgent(config={"preset": "k32"}).config
    cfg = BaselineAgent(config={"preset": "k8", "top_k": 5, "retrieval": "lexical", "max_turns": 3}).config
    assert (cfg["top_k"], cfg["retrieval"], cfg["max_turns"]) == (5, "lexical", 3)
    for bad in ({"nope": 1}, {"preset": "k7"}, {"mode": "temporal"}, {"top_k": 0}, {"top_k": "8"},
                {"query_expansion": "yes"}, {"chunk_overlap": 5000}, {"max_turns": 0}, {"start_turn": 1},
                {"summary": "graph"}, {"max_output_tokens": -1}):
        with pytest.raises(ValueError):
            BaselineAgent(config=bad)


def test_describe_reports_the_full_effective_config_and_is_stable():
    d = BaselineAgent(name="b", config={"preset": "k64"}).describe()
    assert d["kind"] == "baseline" and d["role"] == "contestant"
    assert set(DEFAULTS) <= set(d["config"])
    assert d["config"]["memory_system"]["name"] == "baseline"
    assert d["config"]["memory_system"]["channels"] == ["bm25", "dense", "entity"]
    assert d["config"]["protocol"] == "tab.llm-protocol/1"
    assert json.dumps(d, sort_keys=True) == json.dumps(BaselineAgent(config={"preset": "k64"}).describe(), sort_keys=True)
    assert resolve_config({"preset": "k64"}) == {k: v for k, v in d["config"].items()
                                                 if k not in ("protocol", "runtime_guidance_sha256", "memory_system")}


# ============================================================== end to end
_ID = re.compile(r"\b(?:ADR|TCK)-\d{4}\b")


def _h(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


def policy(req: ModelRequest) -> str:
    """A deterministic tool-using model (a function of the request only)."""
    msgs = req.messages
    if req.purpose == "query_expansion":
        subject = re.search(r"^Subject: (.*)$", msgs[0].content, re.M)
        words = (subject.group(1) if subject else "").split()
        return json.dumps({"queries": [" ".join(words[:3]), "decision constraints"]})
    if req.purpose == "summary":
        return "Summary " + hashlib.sha256(msgs[0].content.encode()).hexdigest()[:12]
    first = msgs[0].content
    k = sum(m.role == "assistant" for m in msgs)
    if first.startswith("<<start>>"):
        if k == 0:
            return json.dumps({"tool": "read_file", "args": {"path": "README.md"}})
        return json.dumps({"final": {"actions": [], "memory": "Seed: ledger service; ADR-0001 cents; ADR-0002 region"}})
    m = re.match(r"<<event seq=(\d+) id=(\S+)>>", first)
    seq, eid = int(m.group(1)), m.group(2)
    subject = re.search(r"^Subject: (.*)$", first, re.M).group(1)
    changed = re.search(r"^Changed paths: (.*)$", first, re.M).group(1)
    plan = [{"tool": "memory_search", "args": {"query": subject}}, {"tool": "history", "args": {}}]
    written = [p.split(" (")[0] for p in changed.split(", ") if p.endswith("(write_file)")]
    if written:
        plan.append({"tool": "read_file", "args": {"path": written[0]}})
    if seq == 3:
        plan.append({"tool": "write_file", "args": {"path": "notes/seen.md", "content": f"seen {eid}\n"}})
        plan.append({"tool": "run_command", "args": {"command": "pytest -q"}})
    if k < len(plan):
        return "```json\n" + json.dumps(plan[k]) + "\n```"
    seen = sorted({i for msg in msgs if msg.role == "user" for i in _ID.findall(msg.content)})
    actions = [{"type": "reopen", "target": i, "rationale": f"policy {eid}", "evidence": [eid],
                "historical_state": {"known_then": ["seed"], "true_then": [], "known_now_about_then": [eid]}}
               for i in seen if _h(f"{i}|{eid}") % 2 == 0]
    actions.append({"type": "note", "text": f"handled {eid}"})
    actions.append({"type": "reopen", "target": "nonsense"})
    return json.dumps({"final": {"actions": actions, "memory": f"{eid}: {subject}; saw {', '.join(seen) or 'nothing'}"}})


def run_agent(state: Path, config: dict, *, restart_before: int | None = None):
    tools = FakeTools(dict(SEED), model=policy, embedder=hash_embed,
                      states={0: dict(SEED)}, budget=StepBudget(max_tool_calls_per_event=200))
    agent = BaselineAgent(name="b", config=config)
    agent.setup(make_context(state))
    agent.on_start(tools)
    requests: list[list[dict]] = [[r.to_dict() for r in tools.requests]]
    responses: list[AgentResponse] = []
    for ev in EVENTS:
        if restart_before == ev.seq:  # the contestant process died; a fresh one resumes from its state dir
            agent = BaselineAgent(name="b", config=config)
            agent.setup(make_context(state, restart_count=1))
        tools.new_step()
        tools.requests = []
        apply_world(tools, ev)
        tools.states[ev.seq] = dict(tools.files)
        responses.append(agent.on_event(ev, tools))
        requests.append([r.to_dict() for r in tools.requests])
    agent.teardown()
    return responses, requests, tools


@pytest.mark.parametrize("preset", ["k8", "full"])
def test_end_to_end_run_is_valid_and_deterministic(tmp_path, preset):
    r1, q1, tools = run_agent(tmp_path / "a" / "state", {"preset": preset})
    r2, q2, _ = run_agent(tmp_path / "b" / "state", {"preset": preset})
    assert [[a.to_dict() for a in r.actions] for r in r1] == [[a.to_dict() for a in r.actions] for r in r2]
    assert q1 == q2
    assert [r.usage for r in r1] == [r.usage for r in r2]
    for resp in r1:
        assert isinstance(resp, AgentResponse)
        assert all(isinstance(a, (ReopenAction, NoteAction)) for a in resp.actions)
        assert any(isinstance(a, NoteAction) and a.text.startswith("handled evt-") for a in resp.actions)
        runtime = [a for a in resp.actions if isinstance(a, NoteAction) and a.text.startswith("[runtime]")]
        assert len(runtime) == 1 and "nonsense" in runtime[0].text
        assert resp.usage.model_calls >= 2 and resp.usage.model_input_tokens > 0
        for a in resp.actions:
            if isinstance(a, ReopenAction):
                assert a.historical_state is not None and a.target in {"ADR-0001", "ADR-0002"}
    used = {name for name, _ in tools.calls}
    assert {"list_files", "read_file", "history", "write_file", "run_command"} <= used
    assert tools.files["notes/seen.md"] == "seen evt-0003\n"
    # no host path, state directory or test machinery reaches the model
    blob = json.dumps(q1)
    assert str(tmp_path) not in blob and "pytest-of" not in blob and "state" + "_dir" not in blob
    purposes = [r["purpose"] for r in q1[1]]
    assert purposes == (["query_expansion"] if preset == "k8" else []) + ["loop"] * (len(purposes) - 1 - (preset == "k8")) + ["summary"]


def test_restart_resumes_from_persistent_state_with_identical_behaviour(tmp_path):
    r1, q1, _ = run_agent(tmp_path / "a" / "state", {"preset": "k8"})
    r2, q2, _ = run_agent(tmp_path / "b" / "state", {"preset": "k8"}, restart_before=3)
    assert [[a.to_dict() for a in r.actions] for r in r1] == [[a.to_dict() for a in r.actions] for r in r2]
    assert q1 == q2


def test_event_context_is_built_from_memory_not_from_the_future(tmp_path):
    _, requests, _ = run_agent(tmp_path / "state", {"preset": "k32"})
    for i, ev in enumerate(EVENTS, start=1):
        text = json.dumps(requests[i])
        for later in EVENTS[i:]:
            assert later.event_id not in text, (ev.event_id, later.event_id)
            assert later.subject not in text


# ============================================================ import hygiene
def _stdlib(name: str) -> bool:
    return name.split(".")[0] in sys.stdlib_module_names or name == "__future__"


def _imports(path: Path) -> list[str]:
    names = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path}: relative import"
            names.append(node.module or "")
    return names


def test_contestant_packages_import_only_the_stdlib_the_contestant_api_and_each_other():
    files = [f for pkg in OWN_PACKAGES for f in sorted((REPO_ROOT / "src" / pkg).rglob("*.py"))]
    assert len(files) >= 10
    for f in files:
        for name in _imports(f):
            ok = _stdlib(name) or name in CONTESTANT_API or name.split(".")[0] in OWN_PACKAGES
            assert ok, f"{f.relative_to(REPO_ROOT)} imports {name}"
        text = f.read_text()
        for forbidden in ("ground_truth", "labels.json", "affected_targets", "smoke_v1", "world/events"):
            assert forbidden not in text, f"{f.relative_to(REPO_ROOT)} mentions {forbidden}"


# ============================================================ in-process run
def test_baseline_runs_under_the_harness_guard_without_a_model(mini_scenario, runs_dir):
    """With no model configured, every loop call fails cleanly; memory still works inside the guard."""
    from harness.runner import RunConfig, run

    agent = BaselineAgent(name="baseline", config={"preset": "k8"})
    result = run(mini_scenario, [agent], RunConfig(runs_dir=runs_dir, hygiene=False))
    assert result.status == "completed"
    assert result.scores["agents"]["baseline"]["step_status"] == {"ok": len(mini_scenario.load_events())}
    assert [e["event_id"] for e in agent.memory.events] == [f"evt-{i:04d}" for i in (1, 2, 3)]
    assert "VENDOR.md" in agent.memory.docs_index and "config.json" in agent.memory.docs_index
