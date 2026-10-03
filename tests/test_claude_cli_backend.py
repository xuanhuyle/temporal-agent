"""Claude CLI backend (provider ``claude-cli``): command construction, parsing, isolation, metering.

No real Claude CLI is needed: a fake ``claude`` executable records exactly what
the backend sends (arguments, stdin, system-prompt file, working directory,
environment) and answers with fixtures captured from a real
``claude -p --output-format json`` call (``tests/fixtures/claude_cli``).
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from harness.agent import Agent, AgentResponse, ModelSettings
from harness.errors import ToolError
from harness.llm import ModelMessage, ModelRequest
from harness.model import create_gateway
from harness.model.claude_cli import (
    TRANSCRIPT_PREAMBLE,
    ClaudeCliBackend,
    build_command,
    build_env,
    parse_cli_output,
    render_prompt,
)
from harness.model.gateway import ProviderUnavailable
from harness.model.recorded import RecordedBackend, recorded_call_from_trace
from harness.runner import RunConfig, run

FIXTURES = Path(__file__).parent / "fixtures" / "claude_cli"
SETTINGS = ModelSettings(provider="claude-cli", name="claude-sonnet-5-5")

FAKE_CLAUDE = r'''#!{python}
import json, os, sys, time
args = sys.argv[1:]
if args == ["--version"]:
    print("9.9.9 (Claude Code)")
    sys.exit(0)
mode = os.environ.get("FAKE_CLAUDE_MODE", "success")
log = os.environ["FAKE_CLAUDE_LOG"]
stdin = sys.stdin.read()
spf = args[args.index("--system-prompt-file") + 1] if "--system-prompt-file" in args else None
record = {{
    "argv": args, "stdin": stdin, "cwd": os.getcwd(), "cwd_listing": sorted(os.listdir(".")),
    "system_prompt": open(spf, encoding="utf-8").read() if spf else None,
    "env": {{k: os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
                                         "FAKE_CLAUDE_KEEP", "TAB_CLAUDE_BIN")}},
}}
with open(log, "a") as fh:
    fh.write(json.dumps(record) + "\n")
fixtures = os.environ["FAKE_CLAUDE_FIXTURES"]
if mode == "sleep":
    time.sleep(60)
if mode == "unknown_option":
    sys.stderr.write("error: unknown option '--safe-mode'\n")
    sys.exit(1)
if mode == "nonjson":
    print("something went wrong")
    sys.exit(3)
data = json.load(open(os.path.join(fixtures, "success.json")))
if mode == "success":
    data["result"] = os.environ.get("FAKE_CLAUDE_RESULT", data["result"])
elif mode == "no_usage":
    data.pop("usage")
    data.pop("modelUsage")
elif mode == "usage_limit":
    data.update(is_error=True, result="Claude AI usage limit reached|1791100000", api_error_status=429)
elif mode == "auth":
    data.update(is_error=True, result="Invalid API key · Please run /login", api_error_status=401)
elif mode == "output_limit":
    data = json.load(open(os.path.join(fixtures, "error_output_limit.json")))
print(json.dumps(data))
sys.exit(1 if data.get("is_error") else 0)
'''


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    path = tmp_path / "bin" / "claude"
    path.parent.mkdir()
    path.write_text(FAKE_CLAUDE.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("TAB_CLAUDE_BIN", str(path))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("FAKE_CLAUDE_FIXTURES", str(FIXTURES))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-reach-the-cli")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok-should-not-reach-the-cli")

    def calls() -> list[dict]:
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    return calls


def req(*contents: str, system: str = "SYS: be a maintainer", stop: tuple[str, ...] = (), retrieval_chars: int = 0):
    roles = ["user", "assistant"]
    msgs = tuple(ModelMessage(roles[i % 2], c) for i, c in enumerate(contents))
    return ModelRequest(system=system, messages=msgs, stop=stop, purpose="loop", retrieval_chars=retrieval_chars)


# ------------------------------------------------------------ pure functions
def test_single_message_is_sent_verbatim_and_turns_are_serialized_in_order():
    assert render_prompt(req("<<event seq=1 id=evt-0001>>\nhello")) == "<<event seq=1 id=evt-0001>>\nhello"
    text = render_prompt(req("first", '{"tool": "history", "args": {}}', "<<observation tool=history status=ok>>\n[]"))
    assert text == "\n\n".join([
        TRANSCRIPT_PREAMBLE,
        "=== user ===\nfirst",
        '=== assistant ===\n{"tool": "history", "args": {}}',
        "=== user ===\n<<observation tool=history status=ok>>\n[]",
    ])


def test_command_disables_tools_customizations_and_fallbacks():
    cmd = build_command("claude", SETTINGS, Path("/x/system.txt"))
    assert cmd[:2] == ["claude", "-p"]
    joined = " ".join(cmd)
    for flag in ("--output-format json", "--model claude-sonnet-5-5", "--system-prompt-file /x/system.txt",
                 "--safe-mode", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in joined
    i = cmd.index("--tools")
    assert cmd[i + 1] == ""  # no tools at all: the model cannot read files or run commands
    assert "--fallback-model" not in cmd and "--effort" not in cmd and "--mcp-config" not in cmd
    assert "--dangerously-skip-permissions" not in cmd and "--bare" not in cmd
    with_effort = build_command("claude", ModelSettings(provider="claude-cli", name="claude-opus-5-5", effort="high"), Path("f"))
    assert with_effort[with_effort.index("--effort") + 1] == "high"


def test_environment_drops_api_keys_and_sets_output_cap_only_when_configured():
    environ = {"ANTHROPIC_API_KEY": "k", "ANTHROPIC_AUTH_TOKEN": "t", "HOME": "/home/x", "PATH": "/usr/bin",
               "TAB_CLAUDE_BIN": "/opt/claude", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "5"}
    env = build_env(environ, SETTINGS)
    assert "ANTHROPIC_API_KEY" not in env and "ANTHROPIC_AUTH_TOKEN" not in env and "TAB_CLAUDE_BIN" not in env
    assert env["HOME"] == "/home/x" and env["PATH"] == "/usr/bin"  # the login lives in the operator's home
    assert "CLAUDE_CODE_MAX_OUTPUT_TOKENS" not in env
    capped = build_env(environ, ModelSettings(provider="claude-cli", name="m", max_output_tokens=8000))
    assert capped["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "8000"
    kept = build_env({**environ, "TAB_CLAUDE_CLI_KEEP_API_KEY": "1"}, SETTINGS)
    assert kept["ANTHROPIC_API_KEY"] == "k"


def test_real_cli_output_is_parsed_without_inventing_numbers():
    raw = parse_cli_output((FIXTURES / "success.json").read_text(), SETTINGS, req("hi"), cli_version="2.1.288")
    assert raw.text == '{"ok": true}' and raw.stop_reason == "end_turn"
    assert raw.model == "claude-sonnet-5-5"  # the modelUsage entry whose counts match usage
    assert (raw.input_tokens, raw.output_tokens, raw.cache_read_input_tokens, raw.cache_creation_input_tokens) == (2, 9, 0, 1228)
    assert raw.usage_available is True
    assert (raw.auxiliary_input_tokens, raw.auxiliary_output_tokens) == (907, 11)  # the CLI's own Haiku side call
    assert raw.reported_cost_usd == 0.005968
    meta = raw.meta
    assert meta["cli_version"] == "2.1.288" and meta["num_turns"] == 1 and meta["thinking_tokens"] == 0
    assert set(meta["models"]) == {"claude-haiku-4-5-20251001", "claude-sonnet-5-5"}
    assert "not subscription billing" in meta["cost_note"]
    assert "session_id" not in json.dumps(meta)


def test_missing_usage_is_reported_as_unavailable_not_zero():
    data = json.loads((FIXTURES / "success.json").read_text())
    data.pop("usage")
    data.pop("modelUsage")
    raw = parse_cli_output(json.dumps(data), SETTINGS, req("hi"))
    assert raw.usage_available is False and raw.model == "claude-sonnet-5-5"
    g = create_gateway(SETTINGS)
    g._backend = _Canned(raw)  # serve the parsed answer through the real gateway
    _, meter = g.lane("a").complete(req("hi"), max_output_tokens=None, timeout_s=None)
    for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens",
              "total_input_tokens", "retrieval_tokens"):
        assert meter[k] is None, k
    assert meter["usage_available"] is False
    assert meter["cost_usd"] == 0.005968 and meter["cost_basis"] == "provider_reported"


class _Canned:
    name = "canned"

    def __init__(self, raw):
        self.raw = raw

    def complete(self, request, settings, *, max_output_tokens, timeout_s, lane):
        return self.raw


@pytest.mark.parametrize("result,status,fatal", [
    ("Claude AI usage limit reached|1791100000", 429, True),
    ("Invalid API key · Please run /login", 401, True),
    ("API Error: Claude's response exceeded the 64 output token maximum.", None, False),
    ("API Error: Overloaded", 529, False),
    ("something else", 400, False),
])
def test_error_results_are_classified(result, status, fatal):
    data = json.loads((FIXTURES / "success.json").read_text())
    data.update(is_error=True, result=result, api_error_status=status)
    with pytest.raises(ToolError) as exc:
        parse_cli_output(json.dumps(data), SETTINGS, req("hi"))
    assert isinstance(exc.value, ProviderUnavailable) is fatal
    assert str(exc.value).startswith("model provider error: claude-cli")
    assert "sk-" not in str(exc.value)


def test_real_output_limit_error_fixture_is_a_non_fatal_provider_error():
    with pytest.raises(ToolError) as exc:
        parse_cli_output((FIXTURES / "error_output_limit.json").read_text(), SETTINGS, req("hi"))
    assert not isinstance(exc.value, ProviderUnavailable)
    assert "CLAUDE_CODE_MAX_OUTPUT_TOKENS" in str(exc.value)


def test_stop_sequences_are_emulated_on_the_returned_text():
    data = json.loads((FIXTURES / "success.json").read_text())
    data["result"] = "keep this STOP drop this"
    raw = parse_cli_output(json.dumps(data), SETTINGS, req("hi", stop=("STOP",)))
    assert raw.text == "keep this " and raw.stop_reason == "stop_sequence" and raw.meta["stop_sequences_emulated"]


def test_settings_the_cli_cannot_honour_are_rejected_up_front():
    with pytest.raises(ValueError, match="temperature"):
        create_gateway(ModelSettings(provider="claude-cli", name="m", temperature=0.0))
    with pytest.raises(ValueError, match="model name"):
        create_gateway(ModelSettings(provider="claude-cli"))


# ------------------------------------------------- the backend, end to end
def test_backend_sends_exactly_the_request_in_isolation(fake_claude):
    g = create_gateway(SETTINGS)
    request = req("<<event seq=3 id=evt-0003>>\nbody", '{"tool": "history", "args": {}}', "<<observation tool=history status=ok>>\n[]",
                  system="SYSTEM PROMPT\nwith lines and unicode: é—", retrieval_chars=10)
    resp, meter = g.lane("baseline-k8").complete(request, max_output_tokens=500, timeout_s=60)
    (call,) = fake_claude()
    assert call["system_prompt"] == request.system  # byte for byte
    assert call["stdin"] == render_prompt(request)
    assert call["cwd_listing"] == []  # an empty private directory
    repo = str(REPO_ROOT)
    assert not call["cwd"].startswith(repo) and repo not in json.dumps(call["argv"])
    assert call["env"]["ANTHROPIC_API_KEY"] is None and call["env"]["ANTHROPIC_AUTH_TOKEN"] is None
    assert call["env"]["TAB_CLAUDE_BIN"] is None and call["env"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] is None
    spf = Path(call["argv"][call["argv"].index("--system-prompt-file") + 1])
    assert not spf.exists()  # removed after the call
    assert resp.text == '{"ok": true}'
    assert meter["provider"] == "claude-cli" and meter["model"] == "claude-sonnet-5-5"
    assert meter["total_input_tokens"] == 1230 and meter["output_tokens"] == 9
    assert meter["auxiliary_input_tokens"] == 907 and meter["cost_basis"] == "provider_reported"
    assert meter["provider_meta"]["cli_version"] == "9.9.9 (Claude Code)"
    assert meter["retrieval_tokens"] == round(1230 * 10 / request.total_chars())
    info = g.runtime_info()
    assert info["claude_cli_version"] == "9.9.9 (Claude Code)" and info["api_key_env_removed"] is True
    described = json.dumps(g.describe())
    assert "sk-should-not" not in described and "claude -p" in described
    g.close()


def test_timeouts_kill_the_cli_and_are_ordinary_provider_errors(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep")
    g = create_gateway(SETTINGS)
    t0 = time.monotonic()
    with pytest.raises(ToolError, match="timed out") as exc:
        g.lane("a").complete(req("hi"), max_output_tokens=None, timeout_s=1.5)
    assert time.monotonic() - t0 < 15
    assert not isinstance(exc.value, ProviderUnavailable) and g.fatal_error is None


@pytest.mark.parametrize("mode,fatal", [("usage_limit", True), ("auth", True), ("unknown_option", True),
                                        ("nonjson", False), ("output_limit", False)])
def test_process_level_failures(fake_claude, monkeypatch, mode, fatal):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    g = create_gateway(SETTINGS)
    with pytest.raises(ToolError) as exc:
        g.lane("a").complete(req("hi"), max_output_tokens=None, timeout_s=30)
    assert (g.fatal_error is not None) is fatal
    assert str(exc.value).startswith("model provider error: claude-cli")


def test_missing_executable_is_fatal(monkeypatch, tmp_path):
    monkeypatch.setenv("TAB_CLAUDE_BIN", str(tmp_path / "no-such-claude"))
    g = create_gateway(SETTINGS)
    with pytest.raises(ProviderUnavailable, match="not found"):
        g.lane("a").complete(req("hi"), max_output_tokens=None, timeout_s=10)
    assert g.fatal_error


def test_recorded_claude_cli_calls_replay_to_the_same_meter(fake_claude):
    g = create_gateway(SETTINGS)
    request = req("hello", retrieval_chars=3)
    resp, meter = g.lane("lane-a").complete(request, max_output_tokens=100, timeout_s=30)
    record = {"agent": "lane-a", "tool": "model_complete", "status": "ok", "args": {"request": request.to_dict()},
              "meter": meter}
    call = recorded_call_from_trace(record, resp.to_dict())
    replay = create_gateway(SETTINGS, recorded=RecordedBackend([call]))
    resp2, meter2 = replay.lane("lane-a").complete(request, max_output_tokens=100, timeout_s=30)
    strip = lambda m: {k: v for k, v in m.items() if k != "latency_ms"} | {
        "provider_meta": {k: v for k, v in m["provider_meta"].items() if k != "latency_ms"}}
    assert resp2 == resp and strip(meter2) == strip(meter)
    assert len(fake_claude()) == 1  # the replay never ran the CLI


def test_preflight_check_reports_what_the_cli_returned(fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_RESULT", "ready")
    info = ClaudeCliBackend(environ=os.environ).check(SETTINGS)
    assert info["ok"] and info["reply"] == "ready" and info["served_model"] == "claude-sonnet-5-5"
    assert info["cli_reported_cost_usd"] == 0.005968


class _ModelCaller(Agent):
    kind = "modelcaller"
    role = "reference"

    def on_event(self, event, tools) -> AgentResponse:
        try:
            tools.model_complete(req(f"event {event.seq}"))
        except ToolError:
            pass
        return AgentResponse()


def test_runner_stops_a_run_when_the_provider_becomes_unavailable(fake_claude, monkeypatch, mini_scenario, runs_dir):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "usage_limit")
    with pytest.raises(RuntimeError, match="model provider unavailable"):
        run(mini_scenario, [_ModelCaller("m")], RunConfig(runs_dir=runs_dir, model=SETTINGS, hygiene=False))
    (run_dir,) = [p for p in runs_dir.iterdir() if p.is_dir()]
    meta = json.loads((run_dir / "metadata.json").read_text())
    assert meta["status"] == "failed" and "usage limit" in meta["error"]
    assert meta["last_completed_seq"] is None  # stopped inside the first step
    assert len(fake_claude()) == 1  # no further calls after the fatal one


def test_runner_completes_with_the_cli_backend_and_records_runtime_facts(fake_claude, mini_scenario, runs_dir):
    result = run(mini_scenario, [_ModelCaller("m")], RunConfig(runs_dir=runs_dir, model=SETTINGS, hygiene=False))
    assert result.status == "completed"
    meta = json.loads((result.run_dir / "metadata.json").read_text())
    assert meta["model_runtime"]["claude_cli_version"] == "9.9.9 (Claude Code)"
    assert meta["config"]["model_gateway"]["provider"] == "claude-cli"
    eff = result.scores["agents"]["m"]["efficiency"]
    assert eff["model_calls"] == 3 and eff["model_auxiliary_input_tokens"] == 3 * 907
    assert eff["cost_known"] is True and eff["tokens_known"] is True
