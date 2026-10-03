"""Regression tests for the Milestone 2 adversarial review (harness side).

Each test names the finding it covers. No real Claude CLI is used: a fake
``claude`` executable simulates the behaviours involved, including the CLI's
expansion of ``@path`` mentions when attachments are not disabled.
"""

from __future__ import annotations

import json
import os
import signal
import stat
import sys
from pathlib import Path

import pytest

from harness.agent import Agent, AgentResponse, ModelSettings, StepBudget
from harness.errors import ToolError
from harness.llm import ModelMessage, ModelRequest
from harness.model import create_gateway
from harness.model.claude_cli import ClaudeCliBackend, build_env
from harness.model.gateway import (
    MAX_CONSECUTIVE_PROVIDER_ERRORS,
    ModelGateway,
    ProviderError,
    ProviderUnavailable,
    RawCompletion,
)
from harness.model.pricing import Pricing
from harness.process import ProcessAgent
from harness.replay import replay_run
from harness.runner import RunConfig, _terminate_as_interrupt, remove_tree, run
from harness.scenario import freeze_scenario, load_scenario
from harness.trace import read_jsonl

FIXTURES = Path(__file__).parent / "fixtures" / "claude_cli"
PKG = Path(__file__).parent / "contestant_pkgs" / "tab_test_contestants"
CLI = ModelSettings(provider="claude-cli", name="claude-sonnet-5-5")

FAKE = r'''#!{python}
import json, os, re, sys
args = sys.argv[1:]
if args == ["--version"]:
    print("9.9.9 (Claude Code)"); sys.exit(0)
mode = os.environ.get("FAKE_MODE", "success")
stdin = sys.stdin.read()
data = json.load(open(os.path.join(os.environ["FAKE_FIXTURES"], "success.json")))
data["result"] = "ready"
if mode == "mentions" or os.environ.get("CLAUDE_CODE_DISABLE_ATTACHMENTS") != "1":
    # what the real CLI does without CLAUDE_CODE_DISABLE_ATTACHMENTS: read @-mentioned files into context
    seen = []
    for path in re.findall(r"@(/[^\s)]+)", stdin):
        try:
            seen.append(open(path).read().strip())
        except OSError:
            pass
    if seen:
        data["result"] = " ".join(seen)
if mode == "error_with_usage":
    data.update(is_error=True, result="API Error: something odd", api_error_status=400)
elif mode == "overloaded":
    data.update(is_error=True, result="API Error: Overloaded", api_error_status=529)
elif mode == "other_model":
    mu = data["modelUsage"].pop("claude-sonnet-5-5")
    mu["canonicalModel"] = "claude-haiku-4-5"
    data["modelUsage"]["claude-haiku-4-5-x"] = mu
print(json.dumps(data))
sys.exit(1 if data.get("is_error") else 0)
'''


@pytest.fixture
def fake_cli(tmp_path, monkeypatch):
    path = tmp_path / "bin" / "claude"
    path.parent.mkdir()
    path.write_text(FAKE.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("TAB_CLAUDE_BIN", str(path))
    monkeypatch.setenv("FAKE_FIXTURES", str(FIXTURES))
    return path


def req(text: str = "hi") -> ModelRequest:
    return ModelRequest(system="sys", messages=(ModelMessage("user", text),), purpose="loop")


# ------------------------------------------------ claude-cli: file mentions
def test_cli_file_mentions_are_always_disabled_even_if_the_operator_enables_them():
    env = build_env({"CLAUDE_CODE_DISABLE_ATTACHMENTS": "0", "HOME": "/h"}, CLI)
    assert env["CLAUDE_CODE_DISABLE_ATTACHMENTS"] == "1"


def test_cli_mention_of_a_host_file_does_not_reach_the_model(fake_cli, tmp_path):
    secret = tmp_path / "labels.json"
    secret.write_text("SECRET-GROUND-TRUTH")
    g = create_gateway(CLI)
    resp, _ = g.lane("a").complete(req(f"look at @{secret}"), max_output_tokens=None, timeout_s=30)
    assert "SECRET" not in resp.text
    g.close()


def test_preflight_refuses_a_cli_that_still_expands_mentions(fake_cli, monkeypatch):
    backend = ClaudeCliBackend(environ=os.environ)
    assert backend.check(CLI)["file_mentions_disabled"] is True
    monkeypatch.setenv("FAKE_MODE", "mentions")  # simulate a CLI version where the switch no longer works
    with pytest.raises(ProviderUnavailable, match="expands @file mentions"):
        ClaudeCliBackend(environ=os.environ).check(CLI)
    backend.close()


# ------------------------------------------- failed calls are not free
def test_failed_cli_call_meters_the_usage_it_consumed(fake_cli, monkeypatch, tmp_path):
    from harness.tools import ToolBox
    from harness.workspace import Workspace

    monkeypatch.setenv("FAKE_MODE", "error_with_usage")
    g = create_gateway(CLI)
    records: list = []
    (tmp_path / "ws").mkdir()
    tools = ToolBox(Workspace(tmp_path / "ws"), StepBudget(), records.append, model=g.lane("a"))
    with pytest.raises(ToolError):
        tools.model_complete(req())
    meter = tools.meter()
    assert meter["model_calls"] == 1 and meter["model_input_tokens"] == 1230 and meter["model_output_tokens"] == 9
    assert meter["cost_usd"] == 0.005968 and meter["tokens_known"] and meter["cost_known"]
    assert meter["model_provider_errors"] == 1
    (rec,) = records
    assert rec["status"] == "error" and rec["meter"]["failed"] is True and rec["meter"]["total_input_tokens"] == 1230
    g.close()


def test_failed_call_with_unknown_usage_marks_tokens_and_cost_unknown(tmp_path):
    from harness.tools import ToolBox
    from harness.workspace import Workspace

    class Timeout:
        name = "t"

        def complete(self, request, settings, **kw):
            raise ProviderError("model provider error: timed out", usage_unknown=True)

    g = ModelGateway(ModelSettings(provider="anthropic", name="m"), Timeout(), None)
    (tmp_path / "ws").mkdir()
    tools = ToolBox(Workspace(tmp_path / "ws"), StepBudget(), lambda r: None, model=g.lane("a"))
    with pytest.raises(ToolError):
        tools.model_complete(req())
    meter = tools.meter()
    assert meter["tokens_known"] is False and meter["cost_known"] is False and meter["model_input_tokens"] == 0


# ----------------------------------------------------- one model per run
class _Serving:
    name = "serving"

    def __init__(self, models):
        self.models = list(models)

    def complete(self, request, settings, **kw):
        return RawCompletion("ok", "end_turn", self.models.pop(0), 10, 2)


def test_a_served_model_other_than_the_configured_one_stops_the_run():
    g = ModelGateway(ModelSettings(provider="anthropic", name="claude-opus-5-5"), _Serving(["claude-haiku-4-5"]), None)
    with pytest.raises(ProviderUnavailable, match="configured for"):
        g.lane("a").complete(req(), max_output_tokens=None, timeout_s=None)
    assert g.fatal_error


def test_a_model_change_mid_run_stops_the_run_and_dated_ids_are_accepted():
    g = ModelGateway(ModelSettings(provider="anthropic", name="claude-opus-5-5"),
                     _Serving(["claude-opus-5-5-20260901", "claude-opus-5-5-20260901", "claude-opus-5"]), None)
    lane = g.lane("a")
    lane.complete(req(), max_output_tokens=None, timeout_s=None)
    lane.complete(req(), max_output_tokens=None, timeout_s=None)
    with pytest.raises(ProviderUnavailable, match="changed mid-run"):
        lane.complete(req(), max_output_tokens=None, timeout_s=None)


def test_an_alias_is_pinned_to_the_first_model_that_serves_it():
    g = ModelGateway(ModelSettings(provider="claude-cli", name="opus"), _Serving(["claude-opus-5-5", "claude-sonnet-5-5"]), None)
    g.lane("a").complete(req(), max_output_tokens=None, timeout_s=None)
    with pytest.raises(ProviderUnavailable):
        g.lane("b").complete(req(), max_output_tokens=None, timeout_s=None)


def test_cli_reports_another_model_and_the_run_is_stopped(fake_cli, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "other_model")
    g = create_gateway(CLI)
    with pytest.raises(ProviderUnavailable):
        g.lane("a").complete(req(), max_output_tokens=None, timeout_s=30)
    g.close()


def test_repeated_transient_failures_stop_the_run(fake_cli, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "overloaded")
    g = create_gateway(CLI)
    for i in range(MAX_CONSECUTIVE_PROVIDER_ERRORS):
        assert g.fatal_error is None
        with pytest.raises(ToolError):
            g.lane("a").complete(req(), max_output_tokens=None, timeout_s=30)
    assert g.fatal_error and "consecutive" in g.fatal_error
    g.close()


# ------------------------------------------- honest configuration record
def test_claude_cli_settings_record_what_the_cli_actually_does():
    with pytest.raises(ValueError, match="prompt caching"):
        create_gateway(ModelSettings(provider="claude-cli", name="m", prompt_caching=True))
    d = create_gateway(CLI).describe()
    assert d["output_cap_enforced_per_call"] is False and d["effective_max_output_tokens"] is None
    assert d["prompt_caching"].startswith("always on")


def test_unknown_usage_charges_the_output_budget_by_the_reply_not_the_whole_cap(tmp_path):
    from harness.tools import ToolBox
    from harness.workspace import Workspace

    class NoUsage:
        name = "n"

        def complete(self, request, settings, **kw):
            return RawCompletion("short reply", "end_turn", "m", 0, 0, usage_available=False)

    g = ModelGateway(ModelSettings(provider="anthropic", name="m"), NoUsage(), None)
    (tmp_path / "ws").mkdir()
    tools = ToolBox(Workspace(tmp_path / "ws"), StepBudget(max_model_output_tokens_per_event=100), lambda r: None,
                    model=g.lane("a"))
    for _ in range(5):  # a whole-cap charge would refuse the second call
        tools.model_complete(req())
    assert tools.meter()["tokens_known"] is False


# --------------------------------------------- integers and the trace
class HugeSeq(Agent):
    kind = "hugeseq"
    role = "reference"

    def on_event(self, event, tools) -> AgentResponse:
        for seq in (10**5000, 2**70):
            try:
                tools.read_at(seq, "app.py")
            except ToolError:
                pass
        return AgentResponse()


def test_oversized_integer_arguments_are_traced_tool_errors_and_replay(mini_scenario, runs_dir):
    result = run(mini_scenario, [HugeSeq("h")], RunConfig(runs_dir=runs_dir, hygiene=False))
    calls = [r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "tool_call" and r["seq"] == 1]
    assert [c["status"] for c in calls] == ["error", "error"]
    assert calls[0]["args"]["seq"] == {"unrecordable_type": "int"}
    _, report = replay_run(result.run_dir)
    assert report["match"], report


# ------------------------------------------------------- A4 enforcement
class InProcessContestant(Agent):
    kind = "inproc"

    def on_event(self, event, tools) -> AgentResponse:
        return AgentResponse()


def test_contestants_must_run_in_their_own_process(mini_scenario, runs_dir):
    with pytest.raises(ValueError, match="own process"):
        run(mini_scenario, [InProcessContestant("c")], RunConfig(runs_dir=runs_dir, hygiene=False))
    result = run(mini_scenario, [InProcessContestant("c")],
                 RunConfig(runs_dir=runs_dir, hygiene=False, allow_in_process_contestants=True))
    meta = json.loads((result.run_dir / "metadata.json").read_text())
    assert meta["config"]["allow_in_process_contestants"] is True


# ------------------------------------- replay of crashes and deadlines
def _scenario_with_subjects(tmp_path, subjects):
    from conftest import build_mini_repo

    manifest = build_mini_repo(tmp_path / "repo")
    events = Path(manifest).parent.parent.parent / "world" / "events" / "mini_v1" / "events.jsonl"
    lines = [json.loads(line) for line in events.read_text().splitlines()]
    for ev, subject in zip(lines, subjects):
        ev["subject"] = subject
    events.write_text("".join(json.dumps(ev) + "\n" for ev in lines))
    return freeze_scenario(manifest)


def test_crashed_and_deadline_limited_steps_replay_exactly(tmp_path, runs_dir):
    scenario = _scenario_with_subjects(tmp_path, ["cmd", "crash", "state"])
    agent = ProcessAgent("scripted", kind="scripted", entry="tab_test_contestants.scripted:ScriptedAgent",
                         config={"cmd_delay": 1}, packages=[PKG])
    budget = StepBudget(max_tool_calls_per_event=50, wall_clock_s_per_event=4)
    result = run(scenario, [agent], RunConfig(runs_dir=runs_dir, budget=budget, hygiene=False))
    statuses = [r["status"] for r in read_jsonl(result.run_dir / "actions.jsonl")]
    assert statuses[1] == "crashed" and statuses[2] == "ok"
    cmd = [r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "tool_call" and r["tool"] == "run_command"]
    assert cmd and cmd[0]["time_limit_s"] < 4
    _, report = replay_run(result.run_dir)
    assert report["match"], report


# ----------------------------------------------- signals and cleanup
def test_sigterm_during_a_run_is_handled_like_ctrl_c():
    before = signal.getsignal(signal.SIGTERM)
    with pytest.raises(KeyboardInterrupt):
        with _terminate_as_interrupt():
            os.kill(os.getpid(), signal.SIGTERM)
            for _ in range(10_000):  # the Python-level handler runs at the next bytecode boundary
                pass
    assert signal.getsignal(signal.SIGTERM) == before


def test_remove_tree_clears_directories_made_unwritable(tmp_path):
    root = tmp_path / "lane"
    locked = root / "a" / "b"
    locked.mkdir(parents=True)
    (locked / "f").write_text("x")
    os.chmod(locked, 0)
    os.chmod(root / "a", 0o500)
    remove_tree(root)
    assert not root.exists()


# ------------------------------------------------------------- pricing
def test_dated_model_ids_are_priced_and_replays_use_the_recorded_prices(monkeypatch):
    p = Pricing()
    assert p.price("claude-opus-5-5-20260901") == p.price("claude-opus-5-5")
    from harness.replay import recorded_pricing

    meta = {"config": {"model_gateway": {"pricing": {"source": "s", "per_mtok_usd": {
        "claude-opus-5-5": {"input": 1.0, "output": 2.0, "cache_read": 0.1, "cache_write": 1.25}, "unpriced-x": None}}}}}
    monkeypatch.setenv("TAB_MODEL_PRICING", json.dumps({"claude-opus-5-5": {"input": 99, "output": 99,
                                                                            "cache_read": 99, "cache_write": 99}}))
    rp = recorded_pricing(meta)
    assert rp.price("claude-opus-5-5").input == 1.0 and rp.price("unpriced-x") is None
    assert rp.price("claude-sonnet-5-5") is not None  # the rest of the built-in table stays available
