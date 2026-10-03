"""Shared contestant runtime: protocol rendering/parsing, the model loop, and the LLMAgent lifecycle.

Uses :class:`FakeTools`, a scripted test double of the contestant tool
surface (the methods of ``harness.tool_specs.TOOL_SPECS`` plus
``budget_remaining()``) over an in-memory workspace. Other contestant test
modules import it from here.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Callable

import pytest

from harness.agent import (
    AgentContext,
    AgentEvent,
    ChangedPath,
    HistoricalState,
    ModelSettings,
    NoteAction,
    ReopenAction,
    StepBudget,
)
from harness.errors import AccessDenied, BudgetExceeded, ToolError
from harness.llm import EmbeddingResponse, ModelRequest, ModelResponse
from harness.tool_specs import TOOL_SPECS, ArgSpec

from contestant_runtime.agent import LLMAgent
from contestant_runtime.loop import ENV_TOOLS, LoopConfig, convert_actions, format_tool_result, run_event
from contestant_runtime.memory import ContextPack, EventOutcome, LocalTool, MemorySystem
from contestant_runtime.protocol import (
    PROTOCOL_VERSION,
    CatalogueEntry,
    Final,
    MemorySection,
    ProtocolError,
    ToolCall,
    extract_json_object,
    parse_reply,
    render_event_message,
    render_observation,
    render_start_message,
    render_system_prompt,
    truncate_text,
)


# ============================================================== test doubles
def est_tokens(text: str) -> int:
    return -(-len(text.encode("utf-8", "surrogatepass")) // 4)


def hash_embed(text: str, dims: int = 64) -> list[float]:
    """Deterministic bag-of-words feature hashing (a lexical stand-in for an embedding model)."""
    vec = [0.0] * dims
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.sha256(w.encode()).hexdigest(), 16)
        vec[h % dims] += 1.0 if (h >> 8) % 2 else -1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


Model = Callable[[ModelRequest], str]


def scripted(*replies: Any) -> Model:
    """A loop model that returns ``replies`` in order (dicts are JSON-encoded); then empty finals."""
    queue = list(replies)

    def model(req: ModelRequest) -> str:
        if req.purpose != "loop":
            return default_aux(req)
        if not queue:
            return json.dumps({"final": {"actions": [], "memory": ""}})
        r = queue.pop(0)
        return r if isinstance(r, str) else json.dumps(r)

    return model


def default_aux(req: ModelRequest) -> str:
    if req.purpose == "query_expansion":
        return json.dumps({"queries": []})
    if req.purpose == "summary":
        return "summary " + hashlib.sha256(req.messages[-1].content.encode()).hexdigest()[:8]
    return json.dumps({"final": {"actions": [], "memory": ""}})


class FakeTools:
    """In-memory stand-in for ``harness.tools.ToolBox`` (same method names, budgets and error types)."""

    def __init__(
        self,
        files: dict[str, str] | None = None,
        *,
        model: Model | None = None,
        embedder: Callable[[str], list[float]] | None = None,
        budget: StepBudget | None = None,
        states: dict[int, dict[str, str]] | None = None,
        command_output: str = "1 passed in 0.01s",
    ) -> None:
        self.files = dict(files or {})
        self.model = model or scripted()
        self.embedder = embedder
        self.budget = budget or StepBudget()
        self.states = states if states is not None else {0: dict(self.files)}
        self.command_output = command_output
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.requests: list[ModelRequest] = []
        self.embedded: list[str] = []
        self.counts = {"tool_calls": 0, "commands": 0, "model_calls": 0, "model_input_tokens": 0,
                       "model_output_tokens": 0, "embedding_tokens": 0}
        self.on_model: Callable[[ModelRequest], None] | None = None

    # ---------------------------------------------------------------- budget
    def budget_remaining(self) -> dict[str, int]:
        b, c = self.budget, self.counts
        return {
            "tool_calls": max(0, b.max_tool_calls_per_event - c["tool_calls"]),
            "commands": max(0, b.max_commands_per_event - c["commands"]),
            "model_calls": max(0, b.max_model_calls_per_event - c["model_calls"]),
            "model_input_tokens": max(0, b.max_model_input_tokens_per_event - c["model_input_tokens"]),
            "model_output_tokens": max(0, b.max_model_output_tokens_per_event - c["model_output_tokens"]),
            "embedding_tokens": max(0, b.max_embedding_tokens_per_event - c["embedding_tokens"]),
        }

    def new_step(self, budget: StepBudget | None = None) -> "FakeTools":
        """Reset per-step counters (a new ToolBox for the next event)."""
        for k in self.counts:
            self.counts[k] = 0
        if budget is not None:
            self.budget = budget
        return self

    def _count(self, tool: str, args: dict[str, Any]) -> None:
        self.calls.append((tool, args))
        if self.counts["tool_calls"] >= self.budget.max_tool_calls_per_event:
            raise BudgetExceeded("tool-call budget exhausted")
        if tool == "run_command" and self.counts["commands"] >= self.budget.max_commands_per_event:
            raise BudgetExceeded("command budget exhausted")
        self.counts["tool_calls"] += 1
        if tool == "run_command":
            self.counts["commands"] += 1

    @staticmethod
    def _path(path: str, allow_root: bool = False) -> str:
        if not isinstance(path, str) or path.startswith("/") or ".." in path.split("/"):
            raise AccessDenied(f"invalid path: {path!r}")
        norm = "/".join(p for p in path.split("/") if p not in ("", "."))
        if not norm and not allow_root:
            raise AccessDenied(f"path refers to the workspace root: {path!r}")
        return norm

    # --------------------------------------------------------- workspace tools
    def list_files(self, prefix: str = ".") -> list[str]:
        self._count("list_files", {"prefix": prefix})
        p = self._path(prefix, allow_root=True)
        return sorted(f for f in self.files if not p or f == p or f.startswith(p + "/"))

    def read_file(self, path: str) -> str:
        self._count("read_file", {"path": path})
        p = self._path(path)
        if p not in self.files:
            raise ToolError(f"no such file: {path!r}")
        return self.files[p]

    def write_file(self, path: str, content: str) -> None:
        self._count("write_file", {"path": path, "content": content})
        self.files[self._path(path)] = content

    def delete_file(self, path: str) -> None:
        self._count("delete_file", {"path": path})
        p = self._path(path)
        if p not in self.files:
            raise ToolError(f"no such file: {path!r}")
        del self.files[p]

    def search(self, pattern: str, prefix: str = ".") -> dict[str, Any]:
        self._count("search", {"pattern": pattern, "prefix": prefix})
        rx = re.compile(pattern)
        matches = []
        for f in sorted(self.files):
            for n, line in enumerate(self.files[f].splitlines(), 1):
                if rx.search(line):
                    matches.append({"path": f, "line": n, "text": line})
        return {"matches": matches, "truncated": False}

    # ----------------------------------------------------------- history tools
    def _state(self, seq: int) -> dict[str, str]:
        if seq not in self.states:
            raise ToolError(f"no repository state at seq {seq}; available: 0..{max(self.states)}")
        return self.states[seq]

    def history(self) -> list[dict[str, Any]]:
        self._count("history", {})
        return [{"seq": s, "event_id": None if s == 0 else f"evt-{s:04d}", "timestamp": None, "changed_paths": [],
                 "tree_sha256": hashlib.sha256(json.dumps(self.states[s], sort_keys=True).encode()).hexdigest()}
                for s in sorted(self.states)]

    def list_at(self, seq: int, prefix: str = ".") -> list[str]:
        self._count("list_at", {"seq": seq, "prefix": prefix})
        return sorted(self._state(seq))

    def read_at(self, seq: int, path: str) -> str:
        self._count("read_at", {"seq": seq, "path": path})
        st = self._state(seq)
        if path not in st:
            raise ToolError(f"no such file at seq {seq}: {path!r}")
        return st[path]

    def diff(self, seq_a: int, seq_b: int, path: str | None = None) -> dict[str, Any]:
        self._count("diff", {"seq_a": seq_a, "seq_b": seq_b, "path": path})
        a, b = self._state(seq_a), self._state(seq_b)
        files = [{"path": p, "status": "modified"} for p in sorted(set(a) & set(b)) if a[p] != b[p]]
        return {"seq_a": seq_a, "seq_b": seq_b, "path": path, "files": files, "diff": "", "truncated": False}

    def run_command(self, command: str, timeout_s: int | None = None) -> dict[str, Any]:
        self._count("run_command", {"command": command, "timeout_s": timeout_s})
        return {"argv": command.split(), "exit_code": 0, "output": self.command_output, "truncated": False,
                "timed_out": False, "violations": []}

    # ------------------------------------------------------------- model tools
    def model_complete(self, request: ModelRequest) -> ModelResponse:
        assert isinstance(request, ModelRequest)
        b, c = self.budget, self.counts
        if c["model_calls"] >= b.max_model_calls_per_event:
            raise BudgetExceeded("model-call budget exhausted")
        est = est_tokens(request.system) + sum(est_tokens(m.content) + 4 for m in request.messages)
        if est > b.max_model_input_tokens_per_event - c["model_input_tokens"]:
            raise BudgetExceeded("model input-token budget exhausted")
        if self.on_model is not None:
            self.on_model(request)
        self.requests.append(request)
        c["model_calls"] += 1
        text = self.model(request)
        c["model_input_tokens"] += est
        c["model_output_tokens"] += est_tokens(text)
        return ModelResponse(text=text, stop_reason="end_turn", model="test-model", input_tokens=est,
                             output_tokens=est_tokens(text))

    def embed(self, texts: list[str], purpose: str = "") -> EmbeddingResponse:
        if self.embedder is None:
            raise ToolError("no embedding model is configured for this run")
        need = sum(est_tokens(t) for t in texts)
        if self.counts["embedding_tokens"] + need > self.budget.max_embedding_tokens_per_event:
            raise BudgetExceeded("embedding-token budget exhausted")
        self.counts["embedding_tokens"] += need
        self.embedded.extend(texts)
        return EmbeddingResponse(vectors=tuple(tuple(self.embedder(t)) for t in texts), model="test-embed",
                                 input_tokens=need)

    def tool_names(self) -> list[str]:
        return [name for name, _ in self.calls]


def make_event(seq: int, subject: str = "Subject", body: str = "Body text.", *, channel: str = "ticket",
               changed: tuple[tuple[str, str], ...] = ()) -> AgentEvent:
    return AgentEvent(
        schema_version="tab.event/1",
        event_id=f"evt-{seq:04d}",
        seq=seq,
        timestamp=f"2026-01-{seq + 1:02d}T09:00:00Z",
        channel=channel,
        author="Sam",
        subject=subject,
        body=body,
        changed_paths=tuple(ChangedPath(op=op, path=p) for op, p in changed),
    )


def make_context(state_dir: Path, restart_count: int = 0, budget: StepBudget | None = None) -> AgentContext:
    state_dir.mkdir(parents=True, exist_ok=True)
    return AgentContext(agent_name="agent", seed=0, state_dir=state_dir, budget=budget or StepBudget(),
                        model=ModelSettings(), instructions="You maintain a repository.",
                        instructions_version="test", restart_count=restart_count)


def final(*actions: dict[str, Any], memory: str = "") -> dict[str, Any]:
    return {"final": {"actions": list(actions), "memory": memory}}


SYSTEM = "system prompt"


def run(tools: FakeTools, first: str = "<<event seq=1 id=evt-0001>>\nSubject: x", **kw: Any):
    kw.setdefault("config", LoopConfig())
    return run_event(tools, system=SYSTEM, first_message=first, **kw)


# ================================================================== protocol
def test_system_prompt_has_instructions_rules_catalogue_and_one_tools_line():
    catalogue = [CatalogueEntry(n, TOOL_SPECS[n].args, TOOL_SPECS[n].doc) for n in ENV_TOOLS]
    catalogue.append(CatalogueEntry("memory_search", (ArgSpec("query", "str"), ArgSpec("kind", "opt_str", None)),
                                    "Search memory."))
    text = render_system_prompt("HARNESS INSTRUCTIONS", catalogue)
    assert text.startswith("HARNESS INSTRUCTIONS\n")
    assert "## How to respond" in text and "## How to work" in text
    assert "- read_file(path): " in text
    assert '- list_files(prefix="."): ' in text
    assert "- diff(seq_a, seq_b, path=null): " in text
    assert "- memory_search(query, kind=null): Search memory." in text
    tools_lines = [l for l in text.splitlines() if l.startswith("<<tools:")]
    assert tools_lines == [f"<<tools: {', '.join(list(ENV_TOOLS) + ['memory_search'])}>>"]
    assert text.rstrip().endswith(tools_lines[0])
    assert "model_complete" not in tools_lines[0] and "embed" not in tools_lines[0].split(": ")[1].split(", ")
    # the guidance never names benchmark internals
    for word in ("benchmark", "ground truth", "scenario", "evaluator", "label"):
        assert word not in text.lower()


def test_env_tools_are_exactly_the_counted_harness_tools():
    assert set(ENV_TOOLS) == {"list_files", "read_file", "write_file", "delete_file", "search", "history",
                              "list_at", "read_at", "diff", "run_command"}


def test_event_message_rendering():
    ev = make_event(3, "Vendor notice", "Line one.\nLine two.", changed=(("write_file", "a/b.md"), ("delete_file", "c.py")))
    msg = render_event_message(ev, [MemorySection("rolling summary", "S1"), MemorySection("retrieved", "")])
    lines = msg.split("\n")
    assert lines[0] == "<<event seq=3 id=evt-0003>>"
    assert lines[1:6] == ["Date: 2026-01-04T09:00:00Z", "Channel: ticket", "Author: Sam", "Subject: Vendor notice",
                          "Changed paths: a/b.md (write_file), c.py (delete_file)"]
    assert lines[6] == "" and lines[7:9] == ["Line one.", "Line two."]
    assert "\n\n<<memory rolling summary>>\nS1" in msg
    assert "\n\n<<memory retrieved>>\n(empty)" in msg
    plain = render_event_message(make_event(1, "Hi\nthere", ""))
    assert "Subject: Hi there" in plain and "Changed paths: (none)" in plain and "(no body)" in plain
    assert render_start_message().startswith("<<start>>\n")


def test_observation_rendering_and_truncation():
    text = "".join(f"line {i}\n" for i in range(2000))
    obs = render_observation("read_file", "ok", text, 1000)
    assert obs.startswith("<<observation tool=read_file status=ok>>\n")
    assert "characters truncated" in obs
    assert "line 0\n" in obs and obs.rstrip().endswith("line 1999")
    assert len(obs) < 1200
    assert render_observation("history", "error", "", 100).endswith("(no output)")
    with pytest.raises(ValueError):
        render_observation("x", "weird", "t", 10)
    assert truncate_text("short", 100) == "short"


@pytest.mark.parametrize(
    "reply,expected",
    [
        ('```json\n{"tool": "history", "args": {}}\n```', ToolCall("history", {})),
        ('```\n{"tool": "read_file", "args": {"path": "a.md"}}\n```', ToolCall("read_file", {"path": "a.md"})),
        ('I will look.\n{"tool": "read_file", "args": {"path": "x"}} thanks', ToolCall("read_file", {"path": "x"})),
        ('{"tool": "history"}', ToolCall("history", {})),
        ('{"final": {"actions": [], "memory": "use {braces} and } stray"}}', Final([], "use {braces} and } stray")),
        ('{"final": {"memory": null}}', Final([], "")),
        ('first {not json} then {"tool": "history", "args": null}', ToolCall("history", {})),
        ('```python\n{"tool": "x"}\n```\n```json\n{"tool": "history"}\n```', ToolCall("history", {})),
    ],
)
def test_parse_reply_accepts(reply, expected):
    assert parse_reply(reply) == expected


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "   ",
        "no json here",
        "{broken",
        '["tool", "history"]',
        '{"tool": "history", "final": {}}',
        '{"tool": 3}',
        '{"tool": "read_file", "args": ["a"]}',
        '{"final": "done"}',
        '{"final": {"actions": {"type": "note"}}}',
        '{"final": {"actions": [], "memory": 5}}',
        '{"something": "else"}',
        "{" * 5000,
    ],
)
def test_parse_reply_rejects_garbage(reply):
    assert isinstance(parse_reply(reply), ProtocolError)


def test_fenced_block_is_preferred_and_extraction_is_string_aware():
    text = 'Plan: {"tool": "list_files"}\n```json\n{"tool": "history"}\n```'
    assert parse_reply(text) == ToolCall("history", {})
    assert extract_json_object('x {"a": "}{", "b": {"c": 1}} y') == {"a": "}{", "b": {"c": 1}}


# ================================================================ conversion
def test_convert_actions_reopen_with_historical_state_note_and_malformed():
    raw = [
        {"type": "reopen", "target": "adr-7", "rationale": "premise changed", "evidence": ["evt-0003", "evt-0001"],
         "historical_state": {"known_then": ["seed"], "true_then": [], "known_now_about_then": ["evt-0003"]}},
        {"type": "note", "text": "checked the config"},
        {"type": "reopen", "target": "ADR-0007", "rationale": "dup"},
        {"type": "reopen", "target": "not an id"},
        {"type": "reopen", "target": 7},
        "string action",
        {"type": "explode"},
        {"type": "note"},
        {"type": "reopen", "target": "TCK-12", "evidence": "evt-0002", "historical_state": "bad",
         "rationale": None},
        {"type": "reopen", "target": "TCK-0013", "evidence": ["evt-1", 5], "rationale": 3,
         "historical_state": {"known_then": "seed", "bogus": 1}},
    ]
    actions, notes = convert_actions(raw)
    assert actions[0] == ReopenAction("ADR-0007", "premise changed", ("evt-0003", "evt-0001"),
                                      HistoricalState(("seed",), (), ("evt-0003",)))
    assert actions[1] == NoteAction("checked the config")
    assert actions[2] == ReopenAction("TCK-0012", "", ("evt-0002",), None)
    assert actions[3] == ReopenAction("TCK-0013", "", ("evt-1",), HistoricalState(("seed",), (), ()))
    assert len(actions) == 4
    joined = " | ".join(notes)
    for fragment in ("duplicate reopen of ADR-0007", "not an id", "not an object", "unknown action type",
                     "note without text", "historical_state is not an object", "rationale is not a string",
                     "non-string item", "unknown key"):
        assert fragment in joined, fragment


def test_convert_actions_caps_the_number_of_actions():
    actions, notes = convert_actions([{"type": "note", "text": f"n{i}"} for i in range(10)], max_actions=3)
    assert [a.text for a in actions] == ["n0", "n1", "n2"]
    assert "dropped 7 action(s)" in notes[0]


# ====================================================================== loop
def test_loop_executes_tools_and_feeds_observations_back():
    tools = FakeTools({"docs/a.md": "alpha content", "b.py": "x = 1\n"}, model=scripted(
        {"tool": "read_file", "args": {"path": "docs/a.md"}},
        {"tool": "search", "args": {"pattern": "x ="}},
        {"tool": "history", "args": {}},
        {"tool": "run_command", "args": {"command": "pytest -q"}},
        final({"type": "note", "text": "done"}, memory="remember alpha"),
    ))
    res = run(tools)
    assert res.final and res.stop_reason == "final" and res.turns == 5
    assert res.actions == [NoteAction("done")]
    assert res.memory == "remember alpha"
    assert tools.tool_names() == ["read_file", "search", "history", "run_command"]
    msgs = [r.messages for r in tools.requests]
    assert msgs[1][-1].content == "<<observation tool=read_file status=ok>>\nalpha content"
    assert msgs[2][-1].content == "<<observation tool=search status=ok>>\n1 match(es)\nb.py:1: x = 1"
    assert msgs[3][-1].content.startswith("<<observation tool=history status=ok>>\n1 state(s)\nseq=0 event=-")
    assert msgs[4][-1].content.startswith("<<observation tool=run_command status=ok>>\nexit_code: 0  timed_out: false")
    for r in tools.requests:
        assert r.system == SYSTEM and r.purpose == "loop"
        assert [m.role for m in r.messages][::2] == ["user"] * ((len(r.messages) + 1) // 2)
    assert [e["status"] for e in res.tool_log] == ["ok"] * 4


def test_loop_reports_tool_errors_denials_unknown_tools_and_bad_args_as_observations():
    tools = FakeTools({"a.md": "x"}, model=scripted(
        {"tool": "read_file", "args": {"path": "missing.md"}},
        {"tool": "read_file", "args": {"path": "../etc/passwd"}},
        {"tool": "model_complete", "args": {}},
        {"tool": "read_file", "args": {}},
        {"tool": "read_at", "args": {"seq": "1", "path": "a.md"}},
        {"tool": "read_at", "args": {"seq": 99, "path": "a.md"}},
        final(),
    ))
    res = run(tools)
    statuses = [e["status"] for e in res.tool_log]
    assert statuses == ["error", "denied", "error", "error", "error", "error"]
    obs = [r.messages[-1].content for r in tools.requests[1:]]
    assert obs[0].startswith("<<observation tool=read_file status=error>>\nno such file")
    assert obs[1].startswith("<<observation tool=read_file status=denied>>")
    assert "unknown tool 'model_complete'" in obs[2]
    assert "missing required argument 'path'" in obs[3]
    assert "argument seq must be an integer" in obs[4]
    assert "no repository state at seq 99" in obs[5]
    # bad arguments never reach the tool surface (no budget spent)
    assert tools.tool_names() == ["read_file", "read_file", "read_at"]


def test_protocol_error_is_reported_and_retried():
    tools = FakeTools(model=scripted("I think we should look around.", final(memory="m")))
    res = run(tools)
    assert res.final and res.protocol_errors == 1 and res.memory == "m"
    second = tools.requests[1].messages
    assert second[1].content == "I think we should look around."
    assert second[2].content.startswith("<<observation tool=protocol status=error>>\nno JSON object found")


def test_consecutive_protocol_errors_end_the_step_without_actions():
    tools = FakeTools(model=scripted("junk", "junk", "junk", "junk", final({"type": "note", "text": "late"})))
    res = run(tools, config=LoopConfig(max_protocol_retries=2))
    assert not res.final and res.stop_reason == "protocol_errors" and res.actions == []
    assert len(tools.requests) == 3


def test_turn_limit_requests_a_final_answer_and_does_not_execute_further_tools():
    tools = FakeTools(model=scripted(*[{"tool": "history", "args": {}}] * 10))
    res = run(tools, config=LoopConfig(max_turns=3))
    assert not res.final and res.stop_reason == "turns_exhausted"
    assert tools.tool_names() == ["history", "history"]
    assert len(tools.requests) == 4  # max_turns plus one grace request
    assert "<<final-only>>" in tools.requests[2].messages[-1].content
    assert "<<final-only>>" not in tools.requests[1].messages[-1].content
    assert "A final answer is required now" in tools.requests[3].messages[-1].content


def test_turn_limit_final_answer_is_accepted():
    tools = FakeTools(model=scripted({"tool": "history", "args": {}}, final({"type": "note", "text": "ok"})))
    res = run(tools, config=LoopConfig(max_turns=2))
    assert res.final and res.actions == [NoteAction("ok")]
    assert "<<final-only>>" in tools.requests[1].messages[-1].content


def test_budget_aware_finalization_and_reserved_calls():
    tools = FakeTools(model=scripted({"tool": "history"}, final(memory="x")),
                      budget=StepBudget(max_model_calls_per_event=2))
    res = run(tools)
    assert res.final and len(tools.requests) == 2
    assert "<<final-only>>" not in tools.requests[0].messages[-1].content
    assert "<<final-only>>" in tools.requests[1].messages[-1].content

    tools = FakeTools(model=scripted(final(memory="y")), budget=StepBudget(max_model_calls_per_event=2))
    res = run(tools, reserve_model_calls=1)
    assert res.final and len(tools.requests) == 1
    assert "<<final-only>>" in tools.requests[0].messages[0].content
    assert tools.budget_remaining()["model_calls"] == 1  # the reserved call is left for the memory system

    tools = FakeTools(budget=StepBudget(max_model_calls_per_event=1))
    res = run(tools, reserve_model_calls=1)
    assert res.stop_reason == "model_budget" and tools.requests == []


def test_exhausted_tool_budget_gives_a_budget_observation_instead_of_a_call():
    tools = FakeTools({"a": "1"}, budget=StepBudget(max_tool_calls_per_event=1, max_commands_per_event=1),
                      model=scripted({"tool": "read_file", "args": {"path": "a"}},
                                     {"tool": "read_file", "args": {"path": "a"}}, final()))
    res = run(tools)
    assert res.final
    assert [e["status"] for e in res.tool_log] == ["ok", "budget"]
    assert tools.tool_names() == ["read_file"]
    assert "status=budget" in tools.requests[2].messages[-1].content


def test_command_budget_is_checked_separately():
    tools = FakeTools(budget=StepBudget(max_commands_per_event=1),
                      model=scripted({"tool": "run_command", "args": {"command": "pytest"}},
                                     {"tool": "run_command", "args": {"command": "pytest"}}, final()))
    res = run(tools)
    assert [e["status"] for e in res.tool_log] == ["ok", "budget"]


def test_budget_exceeded_propagates():
    class Exploding(FakeTools):
        def history(self):
            raise BudgetExceeded("refused")

    tools = Exploding(model=scripted({"tool": "history"}))
    with pytest.raises(BudgetExceeded):
        run(tools)


def test_input_token_budget_stops_before_an_oversized_request():
    tools = FakeTools(budget=StepBudget(max_model_input_tokens_per_event=50))
    res = run(tools, first="<<event seq=1 id=e>>\n" + "x" * 1000)
    assert res.stop_reason == "input_budget" and tools.requests == []


def test_model_tool_error_is_retried_once_then_ends_the_step():
    class Flaky(FakeTools):
        failures = 0

        def model_complete(self, request):
            if self.failures < self.limit:
                self.failures += 1
                self.counts["model_calls"] += 1
                raise ToolError("model provider error: overloaded")
            return super().model_complete(request)

    once = Flaky(model=scripted(final(memory="ok")))
    once.limit = 1
    assert run(once).final
    always = Flaky()
    always.limit = 99
    res = run(always)
    assert res.stop_reason == "model_error" and not res.final


def test_transcript_is_bounded_but_first_message_and_recent_exchanges_survive():
    big = {f"f{i}.txt": f"file {i} " + "y" * 3000 for i in range(8)}
    replies = [{"tool": "read_file", "args": {"path": f"f{i}.txt"}} for i in range(8)] + [final()]
    tools = FakeTools(big, model=scripted(*replies))
    first = "<<event seq=1 id=evt-0001>>\n" + "Z" * 5000
    res = run(tools, first=first, config=LoopConfig(transcript_chars=8000, observation_chars=4000, max_turns=12))
    assert res.final
    last = tools.requests[-1].messages
    assert last[0].content == first
    assert sum(len(m.content) for m in last[1:]) < 8000 + 2 * 3200
    assert "[elided to save context" in last[2].content
    assert last[-1].content.startswith("<<observation tool=read_file status=ok>>\nfile 7")
    assert last[-3].content.startswith("<<observation tool=read_file status=ok>>\nfile 6")


def test_long_tool_call_replies_are_abbreviated_when_elided():
    content = "w" * 5000
    replies = [{"tool": "write_file", "args": {"path": f"o{i}.txt", "content": content}} for i in range(5)] + [final()]
    tools = FakeTools(model=scripted(*replies))
    res = run(tools, config=LoopConfig(transcript_chars=6000, keep_recent_exchanges=1))
    assert res.final
    first_reply = tools.requests[-1].messages[1].content
    assert json.loads(first_reply) == {"tool": "write_file", "args": {"content": "<5000 characters elided>",
                                                                       "path": "o0.txt"}}


def test_workspace_writes_are_tracked_in_call_order():
    tools = FakeTools({"a.md": "x"}, model=scripted(
        {"tool": "write_file", "args": {"path": "./docs//new.md", "content": "N"}},
        {"tool": "delete_file", "args": {"path": "a.md"}},
        {"tool": "write_file", "args": {"path": "../bad", "content": "N"}},
        {"tool": "delete_file", "args": {"path": "missing"}},
        final(),
    ))
    res = run(tools)
    assert res.workspace_writes == {"docs/new.md": "N", "a.md": None}
    assert tools.files == {"docs/new.md": "N"}


def test_local_tools_are_validated_and_count_as_retrieval():
    seen = []

    def handler(tools, args):
        seen.append(args)
        return "memory hit " * 10

    lt = LocalTool("memory_search", (ArgSpec("query", "str"), ArgSpec("kind", "opt_str", None)), "Search.", handler)
    tools = FakeTools(model=scripted(
        {"tool": "memory_search", "args": {"query": "q"}},
        {"tool": "memory_search", "args": {"query": 3}},
        {"tool": "memory_search", "args": {"query": "q", "bogus": 1}},
        final(),
    ))
    first = "<<event seq=1 id=e>>\nSubject: s\n\n<<memory x>>\nabc"
    res = run(tools, first=first, local_tools=[lt], retrieval_chars=len("<<memory x>>\nabc"))
    assert seen == [{"query": "q", "kind": None}]
    assert [e["status"] for e in res.tool_log] == ["ok", "error", "error"]
    obs_len = len(tools.requests[1].messages[-1].content)
    assert tools.requests[0].retrieval_chars == len("<<memory x>>\nabc")
    assert tools.requests[1].retrieval_chars == len("<<memory x>>\nabc") + obs_len
    assert tools.requests[2].retrieval_chars == tools.requests[1].retrieval_chars  # error observations are not memory


def test_format_tool_result_shapes():
    assert format_tool_result("list_files", ["a", "b"]) == "2 file(s)\na\nb"
    assert format_tool_result("read_file", "") == "(empty file)"
    d = format_tool_result("diff", {"seq_a": 0, "seq_b": 1, "path": None, "files": [{"path": "a", "status": "added"}],
                                    "diff": "+x", "truncated": True})
    assert d.startswith("diff seq 0 -> 1; 1 file(s) changed\nadded: a\n\n+x") and "truncated" in d
    assert format_tool_result("write_file", None) == "ok"
    assert json.loads(format_tool_result("other", {"b": 1, "a": [1]})) == {"a": [1], "b": 1}


def test_loop_is_deterministic():
    def go():
        tools = FakeTools({"a.md": "alpha"}, model=scripted({"tool": "read_file", "args": {"path": "a.md"}},
                                                            final({"type": "note", "text": "n"}, memory="m")))
        res = run(tools)
        return [r.to_dict() for r in tools.requests], [a.to_dict() for a in res.actions]

    assert go() == go()


# ================================================================== LLMAgent
class RecordingMemory(MemorySystem):
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.stored: list[str] = []

    def describe(self):
        return {"name": "recording"}

    def open(self, state_dir, *, restart):
        self.log.append(f"open restart={restart}")

    def ingest_seed(self, tools):
        self.log.append("ingest_seed")

    def record_event(self, event):
        self.stored.append(event.event_id)
        self.log.append(f"record {event.event_id}")

    def observe_world(self, event, tools):
        self.log.append("observe")

    def build_context(self, event, tools):
        self.log.append("context")
        return ContextPack((MemorySection("note", "remember X"),), 25, ("dense retrieval unavailable",))

    def local_tools(self):
        return [LocalTool("memory_get_event", (ArgSpec("event_id", "str"),), "Get an event.",
                          lambda tools, args: "stored")]

    def after_event(self, event, outcome, tools):
        assert isinstance(outcome, EventOutcome)
        self.log.append(f"after {outcome.event_id} {outcome.stop_reason} turns={outcome.turns}")

    def after_start(self, outcome, tools):
        self.log.append(f"after_start {outcome.stop_reason}")

    def checkpoint(self):
        self.log.append("checkpoint")

    def reserved_model_calls(self):
        return 1


class RecordingAgent(LLMAgent):
    kind = "recording-llm"

    def __init__(self, name=None, config=None, log=None):
        self.log = log if log is not None else []
        super().__init__(name, config)

    def make_memory(self, config):
        return RecordingMemory(self.log)


def test_llm_agent_lifecycle_order_and_response(tmp_path):
    agent = RecordingAgent()
    agent.setup(make_context(tmp_path / "state"))
    tools = FakeTools(model=scripted(final(memory="seed notes"),
                                     {"tool": "memory_get_event", "args": {"event_id": "evt-0001"}},
                                     final({"type": "reopen", "target": "ADR-1", "rationale": "r", "evidence": ["evt-0001"]},
                                           {"type": "bogus"}, memory="m")))
    agent.on_start(tools)
    tools.new_step()
    resp = agent.on_event(make_event(1), tools)
    agent.teardown()
    assert agent.log == [
        "open restart=False", "ingest_seed", "after_start final", "checkpoint",
        "record evt-0001", "observe", "context", "after evt-0001 final turns=2", "checkpoint", "checkpoint",
    ]
    assert resp.actions[0] == ReopenAction("ADR-0001", "r", ("evt-0001",))
    assert isinstance(resp.actions[-1], NoteAction) and resp.actions[-1].text.startswith("[runtime] ")
    assert "dense retrieval unavailable" in resp.actions[-1].text and "unknown action type" in resp.actions[-1].text
    assert resp.usage.model_calls == 2 and resp.usage.model_input_tokens > 0
    assert 0 < resp.usage.retrieval_tokens < resp.usage.model_input_tokens
    req = tools.requests[1]
    assert req.messages[0].content.startswith("<<event seq=1 id=evt-0001>>")
    assert "<<memory note>>\nremember X" in req.messages[0].content
    assert req.system.startswith("You maintain a repository.")
    assert req.system.rstrip().splitlines()[-1] == f"<<tools: {', '.join(list(ENV_TOOLS) + ['memory_get_event'])}>>"
    assert tools.requests[0].messages[0].content.startswith("<<start>>")


def test_llm_agent_restart_flag_and_describe(tmp_path):
    agent = RecordingAgent(config={"max_turns": 4})
    agent.setup(make_context(tmp_path / "s", restart_count=2))
    assert agent.log == ["open restart=True"]
    d = agent.describe()
    assert d["kind"] == "recording-llm" and d["role"] == "contestant"
    assert d["config"]["max_turns"] == 4 and d["config"]["protocol"] == PROTOCOL_VERSION
    assert d["config"]["memory_system"] == {"name": "recording"}
    json.dumps(d)
    with pytest.raises(ValueError):
        RecordingAgent(config={"nope": 1})
    with pytest.raises(ValueError):
        RecordingAgent(config={"max_turns": 0})


def test_llm_agent_start_turn_can_be_disabled(tmp_path):
    agent = RecordingAgent(config={"start_turn": False})
    agent.setup(make_context(tmp_path / "s"))
    tools = FakeTools()
    agent.on_start(tools)
    assert tools.requests == [] and agent.log[-1] == "checkpoint"
