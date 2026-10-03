"""The ToolBox driving the model gateway: budgets, metering and trace records (amendment A3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from harness.agent import ModelSettings, StepBudget
from harness.errors import BudgetExceeded, ToolError
from harness.llm import ModelMessage, ModelRequest
from harness.model import create_gateway, request_sha256, texts_sha256
from harness.model.gateway import ModelGateway, RawCompletion, RawEmbedding
from harness.model.tokens import estimate_embedding_tokens, estimate_request_tokens
from harness.tools import ToolBox
from harness.workspace import Workspace

FAKE = ModelSettings(provider="fake", embedding_provider="hash")


def req(*contents: str, system: str = "", **kw: Any) -> ModelRequest:
    roles = ["user", "assistant"]
    return ModelRequest(system=system, messages=tuple(ModelMessage(roles[i % 2], c) for i, c in enumerate(contents)), **kw)


class CountingBackend:
    """Fixed usage; records each call's cap so tests can see what the ToolBox passed through."""

    name = "counting"

    def __init__(self, model: str = "claude-opus-5-5", input_tokens: int = 1000, output_tokens: int = 100) -> None:
        self.model, self.inp, self.out = model, input_tokens, output_tokens
        self.caps: list[int] = []
        self.embeds = 0

    def complete(self, request, settings, *, max_output_tokens, timeout_s, lane):
        self.caps.append(max_output_tokens)
        return RawCompletion("ok", "end_turn", self.model, self.inp, min(self.out, max_output_tokens))

    def embed(self, texts, settings, *, timeout_s, lane):
        self.embeds += 1
        return RawEmbedding([[0.0, 1.0] for _ in texts], "hash-ngram-v1", estimate_embedding_tokens(texts))


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "README.md").write_text("# hello\n", encoding="utf-8")
    return Workspace(root)


def make_box(workspace: Workspace, model: Any, **budget: int) -> tuple[ToolBox, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    return ToolBox(workspace, StepBudget(**budget), records.append, model=model), records


def test_model_call_budget_refusal(workspace: Workspace) -> None:
    backend = CountingBackend()
    lane = ModelGateway(ModelSettings(provider="anthropic", name="claude-opus-5-5"), backend, None).lane("a")
    box, records = make_box(workspace, lane, max_model_calls_per_event=2)
    box.model_complete(req("one"))
    box.model_complete(req("two"))
    assert not box.exhausted
    with pytest.raises(BudgetExceeded, match="model-call budget of 2"):
        box.model_complete(req("three"))
    assert box.exhausted
    assert len(backend.caps) == 2  # the refused call never reached the backend
    assert [r["status"] for r in records] == ["ok", "ok", "budget_exceeded"]
    assert "meter" not in records[-1] and records[-1]["args"]["request"] == req("three").to_dict()
    assert box.meter()["model_calls"] == 2


def test_input_token_budget_pre_check_uses_estimator(workspace: Workspace) -> None:
    backend = CountingBackend(input_tokens=1)
    lane = ModelGateway(ModelSettings(provider="anthropic", name="m"), backend, None).lane("a")
    small = req("abcd")
    limit = estimate_request_tokens(small)
    box, records = make_box(workspace, lane, max_model_input_tokens_per_event=limit)
    box.model_complete(small)  # estimate == remaining: allowed
    assert box.meter()["model_input_tokens"] == 1  # metered from the backend, not the estimate
    big = req("x" * 4 * limit)
    with pytest.raises(BudgetExceeded, match="input-token budget"):
        box.model_complete(big)
    assert box.exhausted and records[-1]["status"] == "budget_exceeded" and len(backend.caps) == 1


def test_output_cap_passed_through(workspace: Workspace) -> None:
    backend = CountingBackend(output_tokens=40)
    lane = ModelGateway(ModelSettings(provider="anthropic", name="m", max_output_tokens=1000), backend, None).lane("a")
    box, records = make_box(workspace, lane, max_model_output_tokens_per_event=100)
    box.model_complete(req("a"))  # cap = min(remaining 100, settings 1000)
    box.model_complete(req("b", max_output_tokens=5))  # request asks for less
    box.model_complete(req("c"))  # remaining 100 - 40 - 5 = 55
    assert backend.caps == [100, 5, 55]
    assert [r["meter"]["max_output_tokens"] for r in records] == [100, 5, 55]
    assert box.meter()["model_output_tokens"] == 40 + 5 + 40
    box2, _ = make_box(workspace, ModelGateway(ModelSettings(provider="anthropic", name="m", max_output_tokens=30),
                                               backend, None).lane("a"))
    box2.model_complete(req("d"))
    assert backend.caps[-1] == 30  # the run's setting is the ceiling


def test_output_budget_exhausted(workspace: Workspace) -> None:
    backend = CountingBackend(output_tokens=10)
    lane = ModelGateway(ModelSettings(provider="anthropic", name="m"), backend, None).lane("a")
    box, records = make_box(workspace, lane, max_model_output_tokens_per_event=10)
    box.model_complete(req("a"))
    with pytest.raises(BudgetExceeded, match="output-token budget"):
        box.model_complete(req("b"))
    assert records[-1]["status"] == "budget_exceeded"


def test_meter_sums_and_cost(workspace: Workspace) -> None:
    backend = CountingBackend(model="claude-opus-5-5", input_tokens=1000, output_tokens=100)
    lane = ModelGateway(ModelSettings(provider="anthropic", name="claude-opus-5-5", embedding_provider="hash"),
                        backend, backend).lane("a")
    box, records = make_box(workspace, lane)
    r1 = req("abcdefghij", retrieval_chars=5)
    box.model_complete(r1)
    box.model_complete(req("x"))
    box.embed(["alpha", "beta"], "index")
    m = box.meter()
    assert m["model_calls"] == 2
    assert m["model_input_tokens"] == 2000 and m["model_output_tokens"] == 200
    assert m["retrieval_tokens"] == 500
    assert m["embedding_calls"] == 1 and m["embedding_tokens"] == estimate_embedding_tokens(["alpha", "beta"])
    assert m["cost_usd"] == round(2 * (1000 * 4 + 100 * 20) / 1e6, 8) and m["cost_known"] is True
    assert m["tool_calls"] == 0 and m["tool_result_chars"] == 0
    assert sum(r["meter"]["input_tokens"] for r in records if r["tool"] == "model_complete") == m["model_input_tokens"]


def test_unpriced_model_marks_cost_unknown(workspace: Workspace) -> None:
    backend = CountingBackend(model="claude-unknown")
    lane = ModelGateway(ModelSettings(provider="anthropic", name="claude-unknown"), backend, None).lane("a")
    box, records = make_box(workspace, lane)
    box.model_complete(req("x"))
    assert records[0]["meter"]["cost_usd"] is None
    assert box.meter()["cost_known"] is False and box.meter()["cost_usd"] == 0.0


def test_embed_budget(workspace: Workspace) -> None:
    gateway = create_gateway(FAKE, environ={})
    texts = ["a" * 40, "b" * 40]  # 10 + 10 estimated tokens
    box, records = make_box(workspace, gateway.lane("a"), max_embedding_tokens_per_event=30)
    box.embed(texts)
    assert box.meter()["embedding_tokens"] == 20
    with pytest.raises(BudgetExceeded, match="embedding-token budget of 30"):
        box.embed(texts)
    assert box.exhausted and records[-1]["status"] == "budget_exceeded"
    assert box.meter()["embedding_calls"] == 1


def test_trace_record_carries_meter(workspace: Workspace) -> None:
    gateway = create_gateway(FAKE, environ={})
    box, records = make_box(workspace, gateway.lane("lane-x"))
    r = req("<<start>>", system="<<tools: history>>", purpose="loop", retrieval_chars=3)
    resp = box.model_complete(r)
    rec = records[-1]
    assert rec["tool"] == "model_complete" and rec["status"] == "ok"
    assert rec["args"] == {"request": r.to_dict()}
    assert rec["result"] == resp.to_dict()
    meter = rec["meter"]
    assert meter["request_sha256"] == request_sha256(r)
    assert meter["provider"] == "fake" and meter["model"] == "fake-v1" and meter["purpose"] == "loop"
    assert meter["input_tokens"] == resp.input_tokens == estimate_request_tokens(r)
    assert "latency_ms" in meter
    emb = box.embed(["q"], "query")
    erec = records[-1]
    assert erec["meter"]["texts_sha256"] == texts_sha256(["q"]) and erec["meter"]["purpose"] == "query"
    assert erec["result"] == emb.to_dict()


def test_dict_request_accepted_and_model_choice_rejected(workspace: Workspace) -> None:
    gateway = create_gateway(FAKE, environ={})
    box, records = make_box(workspace, gateway.lane("a"))
    ok = box.model_complete({"system": "", "messages": [{"role": "user", "content": "<<start>>"}]})
    assert ok.model == "fake-v1"
    for extra in ({"model": "claude-fable-5-1"}, {"temperature": 2.0}):
        bad = {"system": "", "messages": [{"role": "user", "content": "hi"}], **extra}
        with pytest.raises(ToolError, match="invalid request: unknown request field"):
            box.model_complete(bad)
        assert records[-1]["status"] == "error"
    assert box.meter()["model_calls"] == 1  # rejected requests are not metered


def test_model_calls_do_not_consume_tool_call_budget(workspace: Workspace) -> None:
    gateway = create_gateway(FAKE, environ={})
    box, _ = make_box(workspace, gateway.lane("a"), max_tool_calls_per_event=1)
    for _ in range(3):
        box.model_complete(req("<<start>>"))
    box.embed(["x"])
    assert box.calls_made == 0 and box.calls_remaining == 1
    assert box.list_files() == ["README.md"]
    with pytest.raises(BudgetExceeded, match="tool-call budget"):
        box.read_file("README.md")
    # The tool-call budget being spent does not block model access.
    box2, _ = make_box(workspace, gateway.lane("a"), max_tool_calls_per_event=1)
    box2.list_files()
    box2.model_complete(req("<<start>>"))


def test_provider_error_is_recorded_without_secrets(workspace: Workspace) -> None:
    class Boom:
        name = "boom"

        def complete(self, *a: Any, **k: Any) -> RawCompletion:
            raise ConnectionError("proxy auth failed for sk-ant-SECRET at /home/user/.config")

    lane = ModelGateway(ModelSettings(provider="anthropic", name="m"), Boom(), None).lane("a")
    box, records = make_box(workspace, lane)
    with pytest.raises(ToolError, match="^model provider error: ConnectionError$"):
        box.model_complete(req("x"))
    assert records[-1]["status"] == "error" and records[-1]["error"] == "model provider error: ConnectionError"
    assert box.meter()["model_calls"] == 1  # the attempt counts against the call budget


def test_no_provider_configured(workspace: Workspace) -> None:
    box, records = make_box(workspace, create_gateway(ModelSettings(), environ={}).lane("a"))
    with pytest.raises(ToolError, match="no model provider is configured"):
        box.model_complete(req("x"))
    with pytest.raises(ToolError, match="no embedding model is configured"):
        box.embed(["x"])
    assert [r["status"] for r in records] == ["error", "error"]


def test_fake_loop_end_to_end_through_toolbox(workspace: Workspace) -> None:
    """A miniature agent loop: the fake model asks for tools until it answers, all through one ToolBox."""
    import json

    gateway = create_gateway(FAKE, environ={})
    box, records = make_box(workspace, gateway.lane("a"))
    system = "- memory_search(query): s\n<<tools: memory_search, history, diff, list_files>>"
    first = ("<<event seq=2 id=evt-0002>>\nSubject: Vendor API v2\nChanged paths: VENDOR.md (added)\n\nbody\n"
             "<<memory Related>>\nADR-0001")
    messages = [first]
    for _ in range(10):
        reply = json.loads(box.model_complete(req(*messages, system=system)).text)
        if "final" in reply:
            break
        messages += [json.dumps(reply), f"<<observation tool={reply['tool']} status=ok>>\n(stub)"]
    else:
        raise AssertionError("no final answer")
    assert box.meter()["model_calls"] == 4  # memory_search, history, diff, final
    assert [json.loads(r["result"]["text"]).get("tool") for r in records][:3] == ["memory_search", "history", "diff"]
