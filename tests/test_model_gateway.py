"""Model gateway, backends, estimator and pricing (protocol amendment A3)."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import random
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from harness.agent import ModelSettings
from harness.canonical import canonical_json
from harness.errors import ToolError
from harness.llm import ModelMessage, ModelRequest
from harness.model import create_gateway, request_sha256, texts_sha256
from harness.model.anthropic_backend import AnthropicBackend, build_request_kwargs
from harness.model.embeddings import HashEmbeddingBackend, embed_text
from harness.model.fake import FakeBackend
from harness.model.gateway import ModelGateway, RawCompletion, RawEmbedding
from harness.model.pricing import DEFAULT_SOURCE, Pricing
from harness.model.recorded import EXHAUSTED, MISMATCH, RecordedBackend, recorded_call_from_trace
from harness.model.tokens import (
    PER_MESSAGE_OVERHEAD_TOKENS,
    estimate_embedding_tokens,
    estimate_request_tokens,
    estimate_tokens,
)

SRC = Path(__file__).resolve().parents[1] / "src"
FAKE = ModelSettings(provider="fake", embedding_provider="hash")
SECRET = "sk-ant-api03-SECRET-do-not-leak-0123456789"


def req(*contents: str, system: str = "", **kw: Any) -> ModelRequest:
    roles = ["user", "assistant"]
    msgs = tuple(ModelMessage(roles[i % 2], c) for i, c in enumerate(contents))
    return ModelRequest(system=system, messages=msgs, **kw)


def h(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


# ---------------------------------------------------------------- estimator
@pytest.mark.parametrize(
    "text,expected",
    [("", 0), ("a", 1), ("abcd", 1), ("abcde", 2), ("é", 1), ("€", 1), ("😀", 1), ("€€", 2), ("x" * 4000, 1000),
     ("x" * 4001, 1001)],
)
def test_estimate_tokens(text: str, expected: int) -> None:
    assert estimate_tokens(text) == expected


def test_estimate_tokens_survives_lone_surrogate() -> None:
    assert estimate_tokens("\ud800") == 1


def test_estimate_request_and_embedding_tokens() -> None:
    r = req("abcdefgh", "ab", "a", system="abcd")
    assert estimate_request_tokens(r) == 1 + (2 + 1 + 1) + 3 * PER_MESSAGE_OVERHEAD_TOKENS
    assert estimate_request_tokens(req("a")) == 1 + PER_MESSAGE_OVERHEAD_TOKENS
    assert estimate_embedding_tokens(["abcde", "", "a"]) == 3
    assert estimate_embedding_tokens([]) == 0


# ------------------------------------------------------------------ pricing
def test_pricing_known_models() -> None:
    p = Pricing()
    assert p.cost("claude-opus-5-5", input_tokens=1_000_000) == 4.0
    assert p.cost("claude-opus-5-5", output_tokens=1_000_000) == 20.0
    assert p.cost("claude-opus-5-5", cache_read_input_tokens=1_000_000, cache_creation_input_tokens=1_000_000) == 5.2
    assert p.cost("claude-sonnet-5-5", input_tokens=1000, output_tokens=1000) == round((2000 + 10000) / 1e6, 8)
    assert p.cost("claude-haiku-4-5", input_tokens=3, output_tokens=7) == round((3 * 1 + 7 * 5) / 1e6, 8)
    assert p.cost("claude-fable-5-1", cache_creation_input_tokens=2_000_000) == 25.0
    assert p.cost("claude-opus-5", cache_read_input_tokens=1_000_000) == 0.5
    assert p.cost("fake-v1", input_tokens=10**9, output_tokens=10**9) == 0.0
    assert p.cost("hash-ngram-v1", input_tokens=10**9) == 0.0
    assert p.cost("claude-opus-5-5", input_tokens=1) == 0.000004
    assert p.source == DEFAULT_SOURCE == "Anthropic list prices as of 2026-09-25"


def test_pricing_rounds_to_8_decimals() -> None:
    c = Pricing().cost("claude-sonnet-5-5", cache_read_input_tokens=1)  # 0.2e-6
    assert c == 2e-07
    assert Pricing().cost("claude-haiku-4-5", cache_read_input_tokens=1) == 1e-07


def test_pricing_unknown_model_is_none() -> None:
    p = Pricing()
    assert p.cost("claude-imaginary-9", input_tokens=10) is None
    assert p.cost(None, input_tokens=10) is None


def test_pricing_override_from_environ() -> None:
    env = {"TAB_MODEL_PRICING": json.dumps({
        "my-model": {"input": 1, "output": 2, "cache_read": 0.5, "cache_write": 1.5},
        "claude-opus-5-5": {"input": 3, "output": 15, "cache_read": 0.3, "cache_write": 3.75},
    })}
    p = Pricing.from_environ(env)
    assert p.cost("my-model", input_tokens=1_000_000, output_tokens=1_000_000) == 3.0
    assert p.cost("claude-opus-5-5", input_tokens=1_000_000) == 3.0
    assert p.cost("claude-haiku-4-5", input_tokens=1_000_000) == 1.0  # untouched default
    assert "TAB_MODEL_PRICING" in p.source and "my-model" in p.source
    assert Pricing.from_environ({}).source == DEFAULT_SOURCE
    assert Pricing.from_environ({"TAB_MODEL_PRICING": " "}).source == DEFAULT_SOURCE


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        json.dumps({"m": {"input": 1, "output": 1}}),
        json.dumps({"m": {"input": -1, "output": 1, "cache_read": 0, "cache_write": 0}}),
        json.dumps({"m": {"input": "1", "output": 1, "cache_read": 0, "cache_write": 0}}),
        json.dumps({"m": {"input": True, "output": 1, "cache_read": 0, "cache_write": 0}}),
        json.dumps({"m": {"input": 1, "output": 1, "cache_read": 0, "cache_write": 0, "extra": 1}}),
        json.dumps({"m": 3}),
    ],
)
def test_pricing_override_rejects_malformed(raw: str) -> None:
    with pytest.raises(ValueError):
        Pricing.from_environ({"TAB_MODEL_PRICING": raw})


def test_create_gateway_reads_pricing_override() -> None:
    env = {"TAB_MODEL_PRICING": json.dumps({"fake-v1": {"input": 1, "output": 1, "cache_read": 0, "cache_write": 0}})}
    g = create_gateway(FAKE, environ=env)
    _, meter = g.lane("a").complete(req("<<start>>"), max_output_tokens=None, timeout_s=None)
    assert meter["cost_usd"] == round((meter["input_tokens"] + meter["output_tokens"]) / 1e6, 8) > 0
    assert "overridden" in g.describe()["pricing"]["source"]


# ------------------------------------------------------------------ gateway
class StubBackend:
    """Completion+embedding backend returning fixed usage; records what it was asked."""

    name = "stub"

    def __init__(self, model: str = "claude-opus-5-5", input_tokens: int = 1000, output_tokens: int = 100,
                 cache_read: int = 0, cache_write: int = 0) -> None:
        self.model, self.inp, self.out, self.cr, self.cw = model, input_tokens, output_tokens, cache_read, cache_write
        self.calls: list[dict[str, Any]] = []

    def complete(self, request, settings, *, max_output_tokens, timeout_s, lane):
        self.calls.append({"request": request, "settings": settings, "max_output_tokens": max_output_tokens,
                           "timeout_s": timeout_s, "lane": lane})
        return RawCompletion("ok", "end_turn", self.model, self.inp, self.out, self.cr, self.cw)

    def embed(self, texts, settings, *, timeout_s, lane):
        self.calls.append({"texts": texts, "lane": lane})
        return RawEmbedding([[1.0, 0.0]] * len(texts), self.model, 5 * len(texts))


def test_gateway_metering_record() -> None:
    backend = StubBackend(input_tokens=2000, output_tokens=300, cache_read=1000, cache_write=400)
    g = ModelGateway(ModelSettings(provider="anthropic", name="claude-opus-5-5"), backend, None)
    r = req("hello world", system="sys", purpose="loop", retrieval_chars=4)
    resp, meter = g.lane("lane-a").complete(r, max_output_tokens=100, timeout_s=5.0)
    assert resp.text == "ok" and resp.model == "claude-opus-5-5" and resp.input_tokens == 2000
    assert resp.cache_read_input_tokens == 1000 and resp.cache_creation_input_tokens == 400
    expected_cost = round((2000 * 4 + 300 * 20 + 1000 * 0.2 + 400 * 5) / 1e6, 8)
    lat = meter.pop("latency_ms")
    assert isinstance(lat, float) and lat >= 0
    assert meter == {
        "provider": "anthropic",
        "model": "claude-opus-5-5",
        "input_tokens": 2000,
        "output_tokens": 300,
        "cache_read_input_tokens": 1000,
        "cache_creation_input_tokens": 400,
        "retrieval_tokens": round(2000 * 4 / r.total_chars()),
        "cost_usd": expected_cost,
        "stop_reason": "end_turn",
        "purpose": "loop",
        "request_sha256": hashlib.sha256(canonical_json(r.to_dict()).encode()).hexdigest(),
        "max_output_tokens": 100,
    }
    assert meter["request_sha256"] == request_sha256(r)
    assert backend.calls[0]["lane"] == "lane-a" and backend.calls[0]["timeout_s"] == 5.0


@pytest.mark.parametrize("retrieval_chars", [0, 1, 7, 10, 14])
def test_retrieval_tokens_apportioning(retrieval_chars: int) -> None:
    g = create_gateway(FAKE)
    r = req("0123456789", system="abcd", retrieval_chars=retrieval_chars)
    _, meter = g.lane("a").complete(r, max_output_tokens=None, timeout_s=None)
    assert meter["retrieval_tokens"] == round(meter["input_tokens"] * retrieval_chars / 14)
    if retrieval_chars == 14:
        assert meter["retrieval_tokens"] == meter["input_tokens"]


def test_output_cap_is_min_of_request_and_settings() -> None:
    backend = StubBackend()
    lane = ModelGateway(ModelSettings(provider="anthropic", name="m", max_output_tokens=500), backend, None).lane("a")
    lane.complete(req("x"), max_output_tokens=None, timeout_s=None)
    lane.complete(req("x"), max_output_tokens=10_000, timeout_s=None)
    lane.complete(req("x"), max_output_tokens=7, timeout_s=None)
    assert [c["max_output_tokens"] for c in backend.calls] == [500, 500, 7]
    backend2 = StubBackend()
    ModelGateway(ModelSettings(provider="anthropic", name="m"), backend2, None).lane("a").complete(
        req("x"), max_output_tokens=None, timeout_s=None)
    assert backend2.calls[0]["max_output_tokens"] == 4096


def test_gateway_without_backends_raises_tool_error() -> None:
    g = create_gateway(ModelSettings())
    with pytest.raises(ToolError, match="no model provider is configured"):
        g.lane("a").complete(req("x"), max_output_tokens=None, timeout_s=None)
    with pytest.raises(ToolError, match="no embedding model is configured"):
        g.lane("a").embed(["x"], "", timeout_s=None)


def test_gateway_no_time_left() -> None:
    g = create_gateway(FAKE)
    with pytest.raises(ToolError, match="no wall-clock time left"):
        g.lane("a").complete(req("x"), max_output_tokens=None, timeout_s=0.0)
    with pytest.raises(ToolError, match="no wall-clock time left"):
        g.lane("a").embed(["x"], "", timeout_s=0.0)


class ExplodingBackend:
    name = "boom"

    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    def complete(self, *a: Any, **k: Any) -> RawCompletion:
        raise self.exc

    def embed(self, *a: Any, **k: Any) -> RawEmbedding:
        raise self.exc


def test_backend_exception_becomes_path_and_secret_free_tool_error() -> None:
    exc = RuntimeError(f"401 invalid x-api-key {SECRET} at /home/user/secret/path")
    g = ModelGateway(ModelSettings(provider="anthropic", name="m", embedding_provider="hash"),
                     ExplodingBackend(exc), ExplodingBackend(exc))
    with pytest.raises(ToolError) as info:
        g.lane("a").complete(req("x"), max_output_tokens=None, timeout_s=None)
    assert str(info.value) == "model provider error: RuntimeError"
    assert info.value.__cause__ is None and info.value.__suppress_context__
    with pytest.raises(ToolError, match=r"^model provider error: RuntimeError$"):
        g.lane("a").embed(["x"], "", timeout_s=None)


def test_backend_tool_error_passes_through() -> None:
    g = ModelGateway(ModelSettings(provider="anthropic", name="m"), ExplodingBackend(ToolError("replay: x")), None)
    with pytest.raises(ToolError, match=r"^replay: x$"):
        g.lane("a").complete(req("x"), max_output_tokens=None, timeout_s=None)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "text",
        RawCompletion("t", "end_turn", "", 1, 1),
        RawCompletion("t", "end_turn", "m", -1, 1),
        RawCompletion("t", "end_turn", "m", 1, True),
        RawCompletion(None, "end_turn", "m", 1, 1),  # type: ignore[arg-type]
        RawCompletion("t", "end_turn", "m", 1.5, 1),  # type: ignore[arg-type]
    ],
)
def test_malformed_completion_is_tool_error(raw: Any) -> None:
    class Bad:
        name = "bad"

        def complete(self, *a: Any, **k: Any) -> Any:
            return raw

    g = ModelGateway(ModelSettings(provider="anthropic", name="m"), Bad(), None)
    with pytest.raises(ToolError, match="malformed completion"):
        g.lane("a").complete(req("x"), max_output_tokens=None, timeout_s=None)


@pytest.mark.parametrize(
    "raw",
    [
        RawEmbedding([[1.0]], "m", 1),  # wrong count for two texts
        RawEmbedding([[1.0], [1.0, 2.0]], "m", 1),  # ragged
        RawEmbedding([[float("nan")], [1.0]], "m", 1),
        RawEmbedding([["a"], [1.0]], "m", 1),
        RawEmbedding([[True], [1.0]], "m", 1),
        RawEmbedding(None, "m", 1),  # type: ignore[arg-type]
        RawEmbedding([[1.0], [1.0]], "", 1),
        RawEmbedding([[1.0], [1.0]], "m", -3),
    ],
)
def test_malformed_embedding_is_tool_error(raw: RawEmbedding) -> None:
    class Bad:
        name = "bad"

        def embed(self, *a: Any, **k: Any) -> Any:
            return raw

    g = ModelGateway(ModelSettings(embedding_provider="hash"), None, Bad())
    with pytest.raises(ToolError, match="malformed embedding"):
        g.lane("a").embed(["x", "y"], "", timeout_s=None)


def test_equality_across_lanes() -> None:
    g = create_gateway(FAKE)
    r = req("<<start>>", system="<<tools: history>>")
    out = [g.lane(name).complete(r, max_output_tokens=None, timeout_s=None) for name in ("baseline", "tesseract")]
    (r1, m1), (r2, m2) = out
    assert r1 == r2
    m1.pop("latency_ms"), m2.pop("latency_ms")
    assert m1 == m2 and m1["provider"] == "fake" and m1["model"] == "fake-v1"
    e1 = g.lane("baseline").embed(["abc"], "p", timeout_s=None)[1]
    e2 = g.lane("tesseract").embed(["abc"], "p", timeout_s=None)[1]
    assert (e1["provider"], e1["model"]) == (e2["provider"], e2["model"]) == ("hash", "hash-ngram-v1")


@pytest.mark.parametrize(
    "extra",
    [{"model": "claude-fable-5-1"}, {"temperature": 1.0}, {"provider": "anthropic"}, {"effort": "max"}],
)
def test_request_cannot_choose_model_or_sampling(extra: dict[str, Any]) -> None:
    d = req("hi").to_dict() | extra
    from harness.llm import InvalidModelRequest

    with pytest.raises(InvalidModelRequest, match="unknown request field"):
        ModelRequest.from_dict(d)


def test_lane_service_implements_model_service_protocol() -> None:
    import inspect

    from harness.tools import ModelService

    lane = create_gateway(FAKE).lane("a")
    for name in ("estimate_input_tokens", "complete", "estimate_embedding_tokens", "embed"):
        proto = inspect.signature(getattr(ModelService, name))
        impl = inspect.signature(getattr(type(lane), name))
        assert list(proto.parameters) == list(impl.parameters), name
        assert [p.kind for p in proto.parameters.values()] == [p.kind for p in impl.parameters.values()], name
    r = req("abc")
    assert lane.estimate_input_tokens(r) == estimate_request_tokens(r)
    assert lane.estimate_embedding_tokens(["abcde"]) == 2


def test_lane_name_must_be_non_empty() -> None:
    with pytest.raises(ValueError):
        create_gateway(FAKE).lane("")


# ------------------------------------------------------------------ factory
@pytest.mark.parametrize(
    "settings",
    [
        ModelSettings(provider="openai"),
        ModelSettings(embedding_provider="neural"),
        ModelSettings(provider="anthropic"),
        ModelSettings(provider="anthropic", name=""),
        ModelSettings(provider="fake", name="claude-opus-5-5"),
        ModelSettings(embedding_provider="hash", embedding_model="text-embedding-3"),
        ModelSettings(embedding_provider="hash", embedding_dims=0),
        ModelSettings(embedding_provider="hash", embedding_dims=10**6),
        ModelSettings(provider="fake", max_output_tokens=0),
    ],
)
def test_create_gateway_rejects_invalid_settings(settings: ModelSettings) -> None:
    with pytest.raises(ValueError):
        create_gateway(settings, environ={})


def test_create_gateway_selects_backends() -> None:
    g = create_gateway(ModelSettings(provider="anthropic", name="claude-opus-5-5"), environ={})
    assert isinstance(g._backend, AnthropicBackend) and g._embedder is None
    g = create_gateway(FAKE, environ={})
    assert isinstance(g._backend, FakeBackend) and isinstance(g._embedder, HashEmbeddingBackend)
    g = create_gateway(ModelSettings(), environ={})
    assert g._backend is None and g._embedder is None


def test_create_gateway_recorded_replaces_configured_backends_only() -> None:
    g = create_gateway(FAKE, environ={}, recorded=[])
    assert isinstance(g._backend, RecordedBackend) and g._backend is g._embedder
    g = create_gateway(ModelSettings(provider="fake"), environ={}, recorded=[])
    assert isinstance(g._backend, RecordedBackend) and g._embedder is None
    g = create_gateway(ModelSettings(), environ={}, recorded=[])
    assert g._backend is None and g._embedder is None


def test_describe_is_public_config_without_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", SECRET)
    import os

    settings = ModelSettings(provider="anthropic", name="claude-opus-5-5", effort="high", prompt_caching=True,
                             embedding_provider="hash", embedding_dims=128)
    d = create_gateway(settings, environ=os.environ).describe()
    text = canonical_json(d)
    assert SECRET not in text and "SECRET" not in text and "API_KEY" not in text
    assert d["provider"] == "anthropic" and d["model"] == "claude-opus-5-5"
    assert d["settings"] == settings.to_dict()
    assert d["embedding_provider"] == "hash" and d["embedding_model"] == "hash-ngram-v1" and d["embedding_dims"] == 128
    assert "not a neural semantic embedding" in d["embedding_kind"]
    assert d["pricing"]["source"] == DEFAULT_SOURCE
    assert d["pricing"]["per_mtok_usd"]["claude-opus-5-5"] == {"input": 4.0, "output": 20.0, "cache_read": 0.2,
                                                               "cache_write": 5.0}
    # Replay from a recording describes the run identically (same fingerprint).
    assert create_gateway(settings, environ=os.environ, recorded=[]).describe() == d


def test_describe_unpriced_model() -> None:
    d = create_gateway(ModelSettings(provider="anthropic", name="claude-unknown"), environ={}).describe()
    assert d["pricing"]["per_mtok_usd"] == {"claude-unknown": None}


# --------------------------------------------------------------- fake policy
SYSTEM = "\n".join([
    "You maintain the repository. (harness instructions)",
    "Runtime rules: reply with exactly one JSON object.",
    "Tools:",
    "- read_file(path): Read a file.",
    "- history(): The world timeline.",
    "- diff(seq_a, seq_b, path): Unified diff.",
    "- run_command(command, timeout_s): Run pytest.",
    "- memory_search(query, k): Search your memory.",
    "<<tools: read_file, history, diff, run_command, memory_search>>",
])


def event_message(seq: int, eid: str, subject: str = "Vendor API v2 released", changed: str = "VENDOR.md (added)",
                  memory: str = "<<memory Related decisions>>\nADR-0001 batch limit\nTCK-0042 retries") -> str:
    lines = [f"<<event seq={seq} id={eid}>>", "Date: 2026-01-09T09:00:00Z", "Channel: changelog",
             "Author: Sam (Platform)", f"Subject: {subject}", f"Changed paths: {changed}", "",
             "The vendor shipped API v2 today. Body mentions ADR-0777 which is not memory.", ""]
    return "\n".join(lines) + memory


def event_id_with(mod4_zero: bool) -> str:
    for i in range(1000):
        eid = f"evt-{i:04d}"
        if (h(eid) % 4 == 0) == mod4_zero:
            return eid
    raise AssertionError


def fake_reply(messages: list[str], system: str = SYSTEM, **kw: Any) -> str:
    r = req(*messages, system=system, **kw)
    return FakeBackend().complete(r, FAKE, max_output_tokens=4096, timeout_s=None, lane="a").text


def test_fake_policy_step_by_step() -> None:
    eid = event_id_with(True)
    convo = [event_message(5, eid)]
    replies = []
    observations = [
        "<<observation tool=memory_search status=ok>>\n[ADR-0003, TCK-0042]",
        "<<observation tool=history status=ok>>\n[...]",
        "<<observation tool=diff status=ok>>\n+ see ADR-0010",
        "<<observation tool=run_command status=error>>\nfailed",
    ]
    for obs in observations:
        text = fake_reply(convo)
        replies.append(json.loads(text))
        convo += [text, obs]
    replies.append(json.loads(fake_reply(convo)))
    assert replies[0] == {"tool": "memory_search", "args": {"query": "Vendor API v2 released"}}
    assert replies[1] == {"tool": "history", "args": {}}
    assert replies[2] == {"tool": "diff", "args": {"seq_a": 4, "seq_b": 5}}
    assert replies[3] == {"tool": "run_command", "args": {"command": "pytest -q -x"}}
    final = replies[4]["final"]
    seen = sorted({"ADR-0001", "TCK-0042", "ADR-0003", "ADR-0010"})  # ADR-0777 is in the body only
    expected = [i for i in seen if h(f"{i}|{eid}") % 7 == 0]
    reopens = [a for a in final["actions"] if a["type"] == "reopen"]
    assert [a["target"] for a in reopens] == expected
    assert all(a["evidence"] == [eid] and a["historical_state"] is None and a["rationale"] for a in reopens)
    notes = [a for a in final["actions"] if a["type"] == "note"]
    assert len(notes) == 1 and eid in notes[0]["text"]
    assert final["memory"] == f"{eid}: Vendor API v2 released"


def test_fake_final_reopens_follow_hash_rule_over_many_ids() -> None:
    eid = "evt-0002"
    ids = [f"ADR-{i:04d}" for i in range(60)] + [f"TCK-{i:04d}" for i in range(60)]
    convo = [event_message(2, eid, memory="<<memory all>>\n" + " ".join(ids)), "{}", "<<observation tool=x status=ok>>",
             "{}", "<<observation tool=x status=ok>>", "{}", "<<observation tool=x status=ok>>",
             "{}", "<<observation tool=x status=ok>>"]
    final = json.loads(fake_reply(convo))["final"]
    expected = sorted(i for i in ids if h(f"{i}|{eid}") % 7 == 0)
    assert expected, "the rule should select some of 120 ids"
    assert [a["target"] for a in final["actions"] if a["type"] == "reopen"] == expected


def test_fake_skips_inapplicable_steps() -> None:
    eid = event_id_with(False)
    convo = [event_message(3, eid, changed="(none)")]
    first = json.loads(fake_reply(convo))
    assert first["tool"] == "memory_search"
    convo += [json.dumps(first), "<<observation tool=memory_search status=ok>>\nnothing"]
    second = json.loads(fake_reply(convo))
    assert second == {"tool": "history", "args": {}}
    convo += [json.dumps(second), "<<observation tool=history status=ok>>\n[]"]
    assert "final" in json.loads(fake_reply(convo))  # no diff (no changed paths), no run_command (hash rule)


def test_fake_only_uses_offered_tools() -> None:
    eid = event_id_with(True)
    sys_prompt = "rules\n- search(pattern, prefix): grep\n<<tools: search, read_file>>"
    assert "final" in json.loads(fake_reply([event_message(1, eid)], system=sys_prompt))
    sys2 = "- memory_search(text, k): s\n<<tools: memory_search>>"
    assert json.loads(fake_reply([event_message(1, eid)], system=sys2)) == {
        "tool": "memory_search", "args": {"text": "Vendor API v2 released"}}


def test_fake_start_returns_empty_final() -> None:
    assert json.loads(fake_reply(["<<start>>\nSeed repository loaded."])) == {"final": {"actions": [], "memory": ""}}


def test_fake_diff_requires_positive_seq() -> None:
    sys_prompt = "<<tools: diff>>"
    assert "final" in json.loads(fake_reply([event_message(0, "evt-0000")], system=sys_prompt))


def test_fake_query_expansion_and_summary() -> None:
    q = json.loads(fake_reply([event_message(2, "evt-0002", subject="Vendor API v2 released, vendor API")],
                              purpose="query_expansion"))
    assert q == {"queries": ["Vendor", "API", "v2", "released"]}
    q2 = json.loads(fake_reply(["expand: rate-limit retries"], purpose="query_expansion"))
    assert q2 == {"queries": ["expand", "rate-limit", "retries"]}
    s1 = fake_reply([event_message(2, "evt-0002"), "ok", "Subject: Other\nTCK-0001"], purpose="summary")
    s2 = fake_reply([event_message(2, "evt-0002"), "ok", "Subject: Other\nTCK-0001"], purpose="summary")
    assert s1 == s2 and s1.startswith("fake-v1 summary")
    assert "ADR-0001" in s1 and "TCK-0001" in s1 and "Vendor API v2 released; Other" in s1
    assert fake_reply(["a different conversation"], purpose="summary") != s1


def test_fake_is_deterministic_and_usage_uses_estimator() -> None:
    r = req(event_message(7, "evt-0007"), system=SYSTEM)
    outs = [FakeBackend().complete(r, FAKE, max_output_tokens=4096, timeout_s=None, lane=f"l{i}") for i in range(3)]
    assert outs[0] == outs[1] == outs[2]
    assert outs[0].input_tokens == estimate_request_tokens(r)
    assert outs[0].output_tokens == estimate_tokens(outs[0].text)
    assert outs[0].model == "fake-v1" and outs[0].stop_reason == "end_turn"


def test_fake_respects_max_output_tokens_and_stop_sequences() -> None:
    r = req(event_message(7, "evt-0007"), system=SYSTEM)
    raw = FakeBackend().complete(r, FAKE, max_output_tokens=3, timeout_s=None, lane="a")
    assert raw.stop_reason == "max_tokens" and raw.output_tokens <= 3 and len(raw.text) == 12
    r2 = req(event_message(7, "evt-0007"), system=SYSTEM, stop=('"args"',))
    raw2 = FakeBackend().complete(r2, FAKE, max_output_tokens=4096, timeout_s=None, lane="a")
    assert raw2.stop_reason == "stop_sequence" and raw2.text == "{"


GARBAGE_PIECES = ["<<", ">>", "<<event seq=", "<<event seq=x id=>>", "<<tools:", "<<memory", "<<observation",
                  "<<start>>", "Subject:", "Changed paths:", "\n", " ", "ADR-12", "TCK-0001", "{", "}", "\"", "\\",
                  "\ud800", "é", "😀", "\x00", "seq=-5 id=evt>>", "<<event seq=99999999999999999999 id=e>>", "-"]


def test_fake_never_crashes_on_garbage() -> None:
    rng = random.Random(1234)
    fake = FakeBackend()
    for i in range(400):
        n = rng.randint(1, 5) * 2 - 1
        msgs = ["".join(rng.choice(GARBAGE_PIECES) for _ in range(rng.randint(1, 30))) or "x" for _ in range(n)]
        msgs = [m if m else "x" for m in msgs]
        system = "".join(rng.choice(GARBAGE_PIECES) for _ in range(rng.randint(0, 20)))
        purpose = rng.choice(["", "loop", "summary", "query_expansion", "???"])
        r = req(*msgs, system=system, purpose=purpose)
        raw = fake.complete(r, FAKE, max_output_tokens=4096, timeout_s=None, lane="a")
        assert raw.stop_reason == "end_turn"
        if purpose != "summary":
            obj = json.loads(raw.text)
            assert isinstance(obj, dict) and len(obj) == 1


def test_fake_reply_is_one_json_object_per_protocol() -> None:
    eid = event_id_with(True)
    convo = [event_message(5, eid)]
    for _ in range(6):
        text = fake_reply(convo)
        obj = json.loads(text)
        assert set(obj) in ({"tool", "args"}, {"final"})
        if "final" in obj:
            assert set(obj["final"]) == {"actions", "memory"}
            for a in obj["final"]["actions"]:
                assert a["type"] in ("reopen", "note")
            break
        convo += [text, f"<<observation tool={obj['tool']} status=ok>>\nTCK-0099"]
    else:
        raise AssertionError("never reached a final answer")


# ------------------------------------------------------------ hash embedding
def cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def test_hash_embeddings_deterministic_unit_norm_and_dims() -> None:
    texts = ["Database migration failed on deploy", "", "   ", "naïve café 😀", "x"]
    raw = HashEmbeddingBackend().embed(texts, FAKE, timeout_s=None, lane="a")
    again = HashEmbeddingBackend().embed(texts, FAKE, timeout_s=None, lane="b")
    assert raw == again and raw.model == "hash-ngram-v1"
    assert raw.input_tokens == estimate_embedding_tokens(texts)
    assert all(len(v) == 384 for v in raw.vectors)
    for t, v in zip(texts, raw.vectors):
        norm = math.sqrt(sum(x * x for x in v))
        assert (norm == 0.0) if not t.strip() else abs(norm - 1.0) < 1e-9
    raw64 = HashEmbeddingBackend().embed(["abc"], ModelSettings(embedding_provider="hash", embedding_dims=64),
                                         timeout_s=None, lane="a")
    assert len(raw64.vectors[0]) == 64


def test_hash_embeddings_similarity_ordering() -> None:
    q = embed_text("the database migration failed")
    near = embed_text("database migration has failed again")
    case = embed_text("THE DATABASE MIGRATION FAILED")
    far = embed_text("pizza for lunch on friday")
    assert cos(q, case) > 0.999
    assert cos(q, near) > cos(q, far) + 0.2
    assert cos(q, q) == pytest.approx(1.0)
    # Bigrams carry word order.
    assert cos(embed_text("retry budget"), embed_text("retry budget")) > cos(embed_text("retry budget"),
                                                                                embed_text("budget retry"))


def test_hash_embeddings_independent_of_process_hash_seed() -> None:
    code = ("import hashlib,json;from harness.model.embeddings import embed_text;"
            "print(hashlib.sha256(json.dumps(embed_text('ADR-0001 batch limit of one record')).encode()).hexdigest())")
    outs = set()
    for seed in ("0", "1", "random"):
        env = {"PYTHONPATH": str(SRC), "PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"}
        outs.add(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                                check=True).stdout.strip())
    assert len(outs) == 1


def test_hash_embedding_through_gateway() -> None:
    resp, meter = create_gateway(FAKE).lane("a").embed(["alpha beta", "gamma"], "index", timeout_s=None)
    assert len(resp.vectors) == 2 and meter["dims"] == 384 and meter["count"] == 2
    assert meter["cost_usd"] == 0.0 and meter["purpose"] == "index" and meter["provider"] == "hash"
    assert meter["texts_sha256"] == texts_sha256(["alpha beta", "gamma"])
    empty, m2 = create_gateway(FAKE).lane("a").embed([], "", timeout_s=None)
    assert empty.vectors == () and m2["dims"] == 0 and m2["input_tokens"] == 0


# ----------------------------------------------------------- anthropic backend
class FakeMessages:
    def __init__(self, response: Any = None, exc: BaseException | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response, self.exc = response, exc

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.response


def sdk_message(text_blocks: list[str], *, usage: dict[str, Any] | None = None, stop: str = "end_turn",
                model: str = "claude-opus-5-5") -> Any:
    content = [SimpleNamespace(type="thinking", thinking="", signature="sig")]
    content += [SimpleNamespace(type="text", text=t) for t in text_blocks]
    u = {"input_tokens": 120, "output_tokens": 30, "cache_read_input_tokens": None,
         "cache_creation_input_tokens": None} | (usage or {})
    return SimpleNamespace(content=content, stop_reason=stop, model=model, usage=SimpleNamespace(**u))


def anthropic_client(response: Any = None, exc: BaseException | None = None) -> Any:
    return SimpleNamespace(messages=FakeMessages(response, exc))


ANTH = ModelSettings(provider="anthropic", name="claude-opus-5-5")


def test_anthropic_request_mapping_minimal() -> None:
    client = anthropic_client(sdk_message(["Hello ", "world"]))
    backend = AnthropicBackend(client)
    r = req("hi", "there", "go", system="")
    raw = backend.complete(r, ANTH, max_output_tokens=321, timeout_s=None, lane="a")
    kwargs = client.messages.calls[0]
    assert kwargs == {
        "model": "claude-opus-5-5",
        "max_tokens": 321,
        "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "there"},
                     {"role": "user", "content": "go"}],
    }
    assert raw == RawCompletion("Hello world", "end_turn", "claude-opus-5-5", 120, 30, 0, 0)


def test_anthropic_request_mapping_full() -> None:
    client = anthropic_client(sdk_message(["x"], usage={"cache_read_input_tokens": 900,
                                                        "cache_creation_input_tokens": 50}))
    settings = ModelSettings(provider="anthropic", name="claude-sonnet-5-5", temperature=0.0, effort="high",
                             prompt_caching=True, max_output_tokens=2000)
    raw = AnthropicBackend(client).complete(req("q", system="SYS", stop=("END",)), settings, max_output_tokens=64,
                                            timeout_s=12.5, lane="a")
    kwargs = client.messages.calls[0]
    assert kwargs["model"] == "claude-sonnet-5-5" and kwargs["max_tokens"] == 64
    assert kwargs["system"] == "SYS" and kwargs["stop_sequences"] == ["END"]
    assert kwargs["output_config"] == {"effort": "high"}
    assert kwargs["cache_control"] == {"type": "ephemeral"}
    assert kwargs["extra_body"] == {"temperature": 0.0}  # 0.0 is a setting, not "unset"
    assert kwargs["timeout"] == 12.5
    assert raw.cache_read_input_tokens == 900 and raw.cache_creation_input_tokens == 50


def test_anthropic_never_requests_fallbacks_or_unset_options() -> None:
    for settings in (ANTH, ModelSettings(provider="anthropic", name="m", temperature=0.7, effort="low",
                                         prompt_caching=True)):
        kwargs = build_request_kwargs(req("x"), settings, max_output_tokens=10, timeout_s=None)
        flat = json.dumps(kwargs)
        assert "fallback" not in flat and "betas" not in kwargs
        assert "temperature" not in kwargs  # never as a top-level SDK keyword
    kwargs = build_request_kwargs(req("x"), ANTH, max_output_tokens=10, timeout_s=None)
    for key in ("temperature", "extra_body", "output_config", "cache_control", "stop_sequences", "system", "timeout"):
        assert key not in kwargs


def test_anthropic_requires_model_name() -> None:
    client = anthropic_client(sdk_message(["x"]))
    with pytest.raises(ToolError, match="requires a model name"):
        AnthropicBackend(client).complete(req("x"), ModelSettings(provider="anthropic"), max_output_tokens=5,
                                          timeout_s=None, lane="a")
    assert client.messages.calls == []


def test_anthropic_response_edge_cases() -> None:
    refusal = sdk_message([], stop="refusal", usage={"output_tokens": 0})
    raw = AnthropicBackend(anthropic_client(refusal)).complete(req("x"), ANTH, max_output_tokens=5, timeout_s=None,
                                                               lane="a")
    assert raw.text == "" and raw.stop_reason == "refusal" and raw.output_tokens == 0
    odd = SimpleNamespace(content=None, stop_reason=None, model=None, usage=None)
    raw = AnthropicBackend(anthropic_client(odd)).complete(req("x"), ANTH, max_output_tokens=5, timeout_s=None,
                                                           lane="a")
    assert raw == RawCompletion("", "unknown", "claude-opus-5-5", 0, 0, 0, 0)
    bad = sdk_message(["x"], usage={"input_tokens": -4})
    with pytest.raises(ToolError, match="malformed usage"):
        AnthropicBackend(anthropic_client(bad)).complete(req("x"), ANTH, max_output_tokens=5, timeout_s=None, lane="a")


def test_anthropic_through_gateway_meters_and_prices() -> None:
    client = anthropic_client(sdk_message(["ok"], usage={"input_tokens": 1000, "output_tokens": 200,
                                                         "cache_read_input_tokens": 5000}))
    g = ModelGateway(ANTH, AnthropicBackend(client), None)
    resp, meter = g.lane("a").complete(req("x"), max_output_tokens=50, timeout_s=None)
    assert resp.text == "ok" and meter["provider"] == "anthropic" and meter["model"] == "claude-opus-5-5"
    assert meter["cost_usd"] == round((1000 * 4 + 200 * 20 + 5000 * 0.2) / 1e6, 8)
    assert client.messages.calls[0]["max_tokens"] == 50


def test_anthropic_sdk_errors_do_not_leak_secrets() -> None:
    class AuthenticationError(Exception):
        pass

    g = ModelGateway(ANTH, AnthropicBackend(anthropic_client(exc=AuthenticationError(f"bad key {SECRET}"))), None)
    with pytest.raises(ToolError) as info:
        g.lane("a").complete(req("x"), max_output_tokens=5, timeout_s=None)
    assert str(info.value) == "model provider error: AuthenticationError"

    def factory() -> Any:
        raise RuntimeError(f"could not resolve credentials {SECRET}")

    with pytest.raises(ToolError) as info2:
        AnthropicBackend(client_factory=factory).complete(req("x"), ANTH, max_output_tokens=5, timeout_s=None,
                                                          lane="a")
    assert SECRET not in str(info2.value) and str(info2.value).startswith("model provider error: RuntimeError")


def test_anthropic_sdk_missing_is_clear_tool_error_only_when_used(monkeypatch: pytest.MonkeyPatch) -> None:
    import harness.model.anthropic_backend as mod

    monkeypatch.setitem(sys.modules, "anthropic", None)  # makes `import anthropic` raise ImportError
    reloaded = importlib.reload(mod)  # the module itself imports fine without the SDK
    try:
        g = create_gateway(ANTH, environ={})  # constructing the backend does not import the SDK either
        with pytest.raises(ToolError, match=r"^model provider error: the 'anthropic' package is not installed"):
            g.lane("a").complete(req("x"), max_output_tokens=5, timeout_s=None)
        assert reloaded.AnthropicBackend is not None
    finally:
        monkeypatch.delitem(sys.modules, "anthropic")
        importlib.reload(mod)


def test_anthropic_module_imports_without_sdk_in_fresh_process() -> None:
    code = ("import sys; sys.modules['anthropic'] = None\n"
            "import harness.model.anthropic_backend, harness.model\n"
            "print('ok')")
    out = subprocess.run([sys.executable, "-c", code], env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "ok"


# --------------------------------------------------------------- recorded
def run_and_record(settings: ModelSettings, script: list[tuple[str, str, Any]]) -> tuple[list[Any], list[dict]]:
    """Run (lane, tool, arg) calls on a live gateway; return outcomes and trace-like recorded calls."""
    g = create_gateway(settings, environ={})
    outcomes, calls = [], []
    for lane, tool, arg in script:
        svc = g.lane(lane)
        if tool == "model_complete":
            resp, meter = svc.complete(arg, max_output_tokens=None, timeout_s=None)
        else:
            resp, meter = svc.embed(arg, "p", timeout_s=None)
        outcomes.append((resp, {k: v for k, v in meter.items() if k != "latency_ms"}))
        rec = {"type": "tool_call", "agent": lane, "tool": tool, "status": "ok", "meter": meter,
               "args": {"request": arg.to_dict()} if tool == "model_complete" else {"texts": arg}}
        calls.append(recorded_call_from_trace(rec, json.loads(canonical_json(resp.to_dict()))))
    return outcomes, calls


SCRIPT = [
    ("a", "model_complete", req(event_message(1, "evt-0001"), system=SYSTEM)),
    ("b", "embed", ["alpha", "beta gamma"]),
    ("a", "embed", ["delta"]),
    ("b", "model_complete", req("<<start>>", system=SYSTEM, purpose="loop")),
    ("a", "model_complete", req(event_message(1, "evt-0001"), "{}", "<<observation tool=x status=ok>>",
                                system=SYSTEM, retrieval_chars=5)),
]


def test_recorded_replay_reproduces_responses_and_meters() -> None:
    outcomes, calls = run_and_record(FAKE, SCRIPT)
    replay = RecordedBackend(json.loads(json.dumps(calls)))  # survives a JSON round trip
    g = create_gateway(FAKE, environ={}, recorded=replay)
    for (lane, tool, arg), (resp, meter) in zip(SCRIPT, outcomes):
        svc = g.lane(lane)
        got = (svc.complete(arg, max_output_tokens=None, timeout_s=None) if tool == "model_complete"
               else svc.embed(arg, "p", timeout_s=None))
        assert got[0] == resp
        assert {k: v for k, v in got[1].items() if k != "latency_ms"} == meter
    assert replay.unconsumed() == {}
    with pytest.raises(ToolError, match=f"^{EXHAUSTED}$"):
        g.lane("a").complete(SCRIPT[0][2], max_output_tokens=None, timeout_s=None)


def test_recorded_mismatch_and_lane_isolation() -> None:
    _, calls = run_and_record(FAKE, SCRIPT)
    replay = RecordedBackend(calls)
    g = create_gateway(FAKE, environ={}, recorded=replay)
    with pytest.raises(ToolError, match=f"^{MISMATCH}$"):  # different request content
        g.lane("a").complete(req("something else"), max_output_tokens=None, timeout_s=None)
    with pytest.raises(ToolError, match=f"^{MISMATCH}$"):  # right lane, wrong tool order
        g.lane("a").embed(["delta"], "p", timeout_s=None)
    with pytest.raises(ToolError, match=f"^{EXHAUSTED}$"):  # another lane's recording is not served
        g.lane("c").complete(SCRIPT[0][2], max_output_tokens=None, timeout_s=None)
    assert replay.unconsumed() == {"a": 3, "b": 2}  # mismatches do not advance the queue
    g.lane("a").complete(SCRIPT[0][2], max_output_tokens=None, timeout_s=None)
    assert replay.unconsumed() == {"a": 2, "b": 2}


def test_recorded_error_records_replay_the_error() -> None:
    r = req("x")
    rec = {"type": "tool_call", "agent": "a", "tool": "model_complete", "status": "error",
           "args": {"request": r.to_dict()}, "error": "model provider error: APITimeoutError"}
    call = recorded_call_from_trace(rec)
    assert call == {"lane": "a", "tool": "model_complete", "request_sha256": request_sha256(r),
                    "error": "model provider error: APITimeoutError"}
    g = create_gateway(ModelSettings(provider="anthropic", name="claude-opus-5-5"), environ={}, recorded=[call])
    with pytest.raises(ToolError, match="^model provider error: APITimeoutError$"):
        g.lane("a").complete(r, max_output_tokens=None, timeout_s=None)
    erec = {"agent": "a", "tool": "embed", "status": "error", "args": {"texts": ["q"], "purpose": ""},
            "error": "model provider error: malformed embedding from the backend"}
    assert recorded_call_from_trace(erec)["texts_sha256"] == texts_sha256(["q"])


@pytest.mark.parametrize(
    "rec",
    [
        {"agent": "a", "tool": "read_file", "status": "ok", "args": {"path": "x"}},
        {"agent": "a", "tool": "model_complete", "status": "budget_exceeded", "args": {"request": {}}},
        {"agent": "a", "tool": "model_complete", "status": "error", "args": {"request": {"model": "x"}},
         "error": "model_complete: invalid request: unknown request field(s): model"},
        {"agent": "a", "tool": "model_complete", "status": "error", "args": {"request": {}},
         "error": "no model provider is configured for this run"},
        {"agent": "a", "tool": "embed", "status": "error", "args": {"texts": ["x"]},
         "error": "embed: no wall-clock time left in this step"},
    ],
)
def test_recorded_skips_calls_that_never_reached_a_backend(rec: dict[str, Any]) -> None:
    assert recorded_call_from_trace(rec) is None


@pytest.mark.parametrize(
    "bad",
    [
        "not a mapping",
        {"lane": "", "tool": "embed", "texts_sha256": "0" * 64, "vectors": [], "model": "m", "input_tokens": 0},
        {"lane": "a", "tool": "read_file"},
        {"lane": "a", "tool": "model_complete", "request_sha256": "short", "error": "x"},
        {"lane": "a", "tool": "model_complete", "request_sha256": "0" * 64, "text": "t"},
        {"lane": "a", "tool": "model_complete", "request_sha256": "0" * 64, "error": 3},
    ],
)
def test_recorded_backend_rejects_malformed_records(bad: Any) -> None:
    with pytest.raises(ValueError):
        RecordedBackend([bad])
