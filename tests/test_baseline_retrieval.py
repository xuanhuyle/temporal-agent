"""Baseline retrieval components: tokenizer, entities, BM25, dense index, chunkers, fusion, filters.

Also a retrieval-strength check on a small synthetic corpus (not the smoke
scenario): a paraphrased event that shares no rare token with the target
decision record's title still retrieves it, and an entity mention retrieves
the chunk carrying that entity.
"""

from __future__ import annotations

import json

import pytest

from harness.agent import StepBudget

from baseline.bm25 import BM25Index
from baseline.chunking import chunk_file, split_by_size
from baseline.memory import BaselineMemory
from baseline.presets import resolve_config
from baseline.retrieval import Doc, Filters, Retriever, diversify, rrf_fuse
from baseline.text import extract_entities, stem, tokenize
from baseline.vectors import DenseIndex, EmbeddingCache, text_sha256
from test_contestant_runtime import FakeTools, hash_embed, make_context, make_event


# ================================================================ tokenizer
def test_tokenizer_splits_identifiers_and_keeps_wholes():
    toks = tokenize("retryPolicy batch_limit HTTPServer")
    for t in ("retrypolicy", "retry", "policy", "batch_limit", "batch", "limit", "httpserver", "http", "server"):
        assert t in toks, t


def test_tokenizer_ids_paths_versions_dotted_and_stopwords():
    toks = tokenize("The fix for ADR-4 and adr_0012 is in docs/adr/0004-x.md, client.retry_policy, v2.10.1")
    assert "adr-0004" in toks and "adr-0012" in toks
    assert "docs/adr/0004-x.md" in toks
    assert "client.retry_policy" in toks
    assert "2.10.1" in toks
    assert "the" not in toks and "and" not in toks and "is" not in toks


def test_stemmer_is_light_and_consistent():
    assert stem("policies") == stem("policy")
    assert stem("caches") == stem("cached") == stem("cache")
    assert stem("running") == "run"
    assert stem("status") == "status" and stem("analysis") == "analysis"
    assert stem("v2") == "v2" and stem("api") == "api"


def test_entity_extraction():
    ents = extract_entities("Per ADR-4 and TCK-0012, edit ./config/settings.json and docs/x.md; "
                            "client.retry_policy, batch_limit, retryPolicy, version v2.10.1; UTF-8 is fine.")
    assert ents == sorted(ents)
    for e in ("id:ADR-0004", "id:TCK-0012", "path:config/settings.json", "file:settings.json", "path:docs/x.md",
              "file:x.md", "sym:client.retry_policy", "sym:batch_limit", "sym:retrypolicy", "ver:2.10.1"):
        assert e in ents, e
    assert not any(e.startswith("id:UTF") for e in ents)


# ===================================================================== BM25
def test_bm25_ranks_relevant_documents_first_and_breaks_ties_by_id():
    idx = BM25Index()
    idx.add("d1", tokenize("sqlite database storage for persistence"))
    idx.add("d2", tokenize("password hashing with bcrypt cost factor"))
    idx.add("d3", tokenize("database migrations run at startup"))
    idx.add("d4", tokenize("bcrypt"))
    hits = idx.search(tokenize("bcrypt cost"), 10)
    assert [d for d, _ in hits][:2] == ["d2", "d4"]
    assert all(s > 0 for _, s in hits)
    assert idx.search(tokenize("unrelated words"), 10) == []
    tie = BM25Index()
    tie.add("b", ["x"])
    tie.add("a", ["x"])
    tie.add("c", ["y"])
    assert [d for d, _ in tie.search(["x"], 5)] == ["a", "b"]


def test_bm25_is_insertion_order_independent_and_supports_removal():
    docs = {f"d{i}": tokenize(f"term{i % 3} shared words number {i} " * (i % 4 + 1)) for i in range(20)}
    a, b = BM25Index(), BM25Index()
    for k in sorted(docs):
        a.add(k, docs[k])
    for k in sorted(docs, reverse=True):
        b.add(k, docs[k])
    q = tokenize("term1 shared number 7")
    assert a.search(q, 20) == b.search(q, 20)
    a.add("extra", tokenize("term1 term1 term1"))
    a.remove("extra")
    assert a.search(q, 20) == b.search(q, 20)
    a.add("d3", docs["d3"])  # re-adding replaces
    assert a.search(q, 20) == b.search(q, 20)
    assert len(a) == 20


# ===================================================================== fusion
def test_rrf_fusion():
    fused = rrf_fuse([["a", "b", "c"], ["b", "a"], ["c"]], k=60)
    scores = dict(fused)
    assert scores["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["c"] == pytest.approx(1 / 63 + 1 / 61)
    assert [d for d, _ in fused] == ["a", "b", "c"]  # a and b tie (broken by id), c is lower
    assert rrf_fuse([["a", "a", "b"]]) == rrf_fuse([["a", "b"]])  # duplicates in one list count once


def test_diversity_cap():
    ranked = [(f"{src}{i}", 1.0 - n / 100) for n, (src, i) in enumerate([("x", 1), ("x", 2), ("x", 3), ("y", 1), ("x", 4), ("z", 1)])]
    out = diversify(ranked, lambda d: d[0], max_per_source=2, k=4)
    assert [d for d, _ in out] == ["x1", "x2", "y1", "z1"]


def _corpus() -> Retriever:
    r = Retriever(max_per_source=10)
    r.add(Doc("event:evt-0001", "event", "event:evt-0001", "Subject: Lunch\nPizza Friday", seq=1))
    r.add(Doc("event:evt-0002", "event", "event:evt-0002", "Subject: Pizza review\nPizza was good", seq=2))
    r.add(Doc("note:2", "note", "note:evt-0002", "pizza noted", seq=2))
    r.add(Doc("doc:docs/a.md#0", "doc", "file:docs/a.md", "pizza policy", seq=0, path="docs/a.md"))
    r.add(Doc("doc:src/b.py#0", "doc", "file:src/b.py", "pizza = 1", seq=0, path="src/b.py"))
    r.add(Doc("doc:docsx/c.md#0", "doc", "file:docsx/c.md", "pizza", seq=0, path="docsx/c.md"))
    return r


def test_filters_by_kind_seq_range_path_prefix_and_exclusion():
    r = _corpus()
    ids = lambda flt: sorted(h.doc.doc_id for h in r.search(["pizza"], k=20, filters=flt))  # noqa: E731
    assert len(ids(None)) == 6
    assert ids(Filters(kinds=("event",))) == ["event:evt-0001", "event:evt-0002"]
    assert ids(Filters(since_seq=2)) == ["event:evt-0002", "note:2"]
    assert ids(Filters(until_seq=1, kinds=("event", "note"))) == ["event:evt-0001"]
    assert ids(Filters(path_prefix="docs")) == ["doc:docs/a.md#0"]
    assert ids(Filters(path_prefix="./docs/")) == ["doc:docs/a.md#0"]
    assert ids(Filters(path_prefix="src/b.py")) == ["doc:src/b.py#0"]
    assert "event:evt-0002" not in ids(Filters(exclude=frozenset({"event:evt-0002"})))


def test_retriever_diversity_cap_applies_per_source():
    r = Retriever(max_per_source=2)
    for i in range(6):
        r.add(Doc(f"doc:big.md#{i}", "doc", "file:big.md", f"alpha chunk {i}", seq=0, path="big.md"))
    r.add(Doc("doc:other.md#0", "doc", "file:other.md", "alpha elsewhere", seq=0, path="other.md"))
    hits = r.search(["alpha"], k=5)
    assert sum(h.doc.source == "file:big.md" for h in hits) == 2
    assert "doc:other.md#0" in [h.doc.doc_id for h in hits]


def test_retriever_entity_channel_and_remove():
    r = Retriever()
    r.add(Doc("doc:t#0", "doc", "file:t", "Ticket TCK-0042: export is blocked", seq=0, path="t"))
    r.add(Doc("doc:u#0", "doc", "file:u", "unrelated text", seq=0, path="u", extra_entities=("path:config/x.json",)))
    hits = r.search(["nothing lexical"], k=5, entities=["id:TCK-0042", "path:config/x.json"])
    assert [h.doc.doc_id for h in hits] == ["doc:t#0", "doc:u#0"] or [h.doc.doc_id for h in hits] == ["doc:u#0", "doc:t#0"]
    assert all("entity" in h.channels for h in hits)
    r.remove("doc:t#0")
    assert [h.doc.doc_id for h in r.search(["TCK-0042"], k=5)] == []


# =================================================================== chunkers
def test_markdown_chunker_by_heading_with_title_and_fences():
    md = "# ADR-0001: Use X\n\nStatus: accepted\n\n## Context\nWe need y.\n```\n# not a heading\n```\n## Decision\nUse X.\n"
    chunks = chunk_file("docs/adr/0001.md", md)
    assert [c.title for c in chunks] == ["ADR-0001: Use X", "ADR-0001: Use X > Context", "ADR-0001: Use X > Decision"]
    assert "# not a heading" in chunks[1].text
    assert "".join(c.text for c in chunks) == md
    assert chunks[0].chunk_id.startswith("docs/adr/0001.md#0:") and len(chunks[0].chunk_id.split(":")[-1]) == 12


def test_python_chunker_by_top_level_definition():
    py = '"""Doc."""\nimport os\n\n@decorator\ndef f():\n    return 1\n\n\nclass C:\n    def m(self):\n        pass\nY = 2\n'
    chunks = chunk_file("pkg/a.py", py)
    assert [c.title for c in chunks] == ["module header", "def f", "class C"]
    assert chunks[1].text.startswith("@decorator\ndef f")
    assert "Y = 2" in chunks[2].text
    broken = chunk_file("pkg/b.py", "def broken(:\n    pass\n")
    assert len(broken) == 1 and broken[0].title == ""


def test_size_chunker_overlaps_and_ids_are_stable():
    text = "".join(f"line {i} " + "x" * 50 + "\n" for i in range(100))
    a = chunk_file("data.json", text, chunk_chars=500, overlap=120)
    b = chunk_file("data.json", text, chunk_chars=500, overlap=120)
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert all(len(c.text) <= 500 for c in a)
    for prev, cur in zip(a, b[1:]):
        assert cur.start_line <= prev.end_line  # overlap of at least one line
    assert a[-1].end_line == 100
    changed = chunk_file("data.json", text.replace("line 99 ", "line 99!"), chunk_chars=500, overlap=120)
    assert [c.chunk_id for c in changed][:-1] == [c.chunk_id for c in a][:-1]
    assert changed[-1].chunk_id != a[-1].chunk_id
    assert chunk_file("empty.txt", "  \n") == []
    huge = split_by_size(["z" * 10_000 + "\n"], 1, 100, 10)
    assert len(huge) == 1 and len(huge[0][2]) == 200


# ================================================================ dense index
def test_dense_index_embeds_in_batches_caches_and_searches(tmp_path):
    tools = FakeTools(embedder=hash_embed)
    cache = EmbeddingCache(tmp_path / "emb.jsonl")
    dense = DenseIndex(cache, batch_size=2)
    dense.set_text("a", "sqlite storage database")
    dense.set_text("b", "password hashing bcrypt")
    dense.set_text("c", "sqlite storage database")  # same text: embedded once
    assert dense.pending() == ["a", "b", "c"]
    assert dense.ensure(tools) == 3
    assert sorted(tools.embedded) == ["password hashing bcrypt", "sqlite storage database"]
    q = dense.embed_queries(tools, ["sqlite database"])[0]
    hits = dense.search(q, 3)
    assert [d for d, _ in hits][:2] == ["a", "c"]
    # a new index over the same cache file re-embeds nothing
    tools2 = FakeTools(embedder=hash_embed)
    dense2 = DenseIndex(EmbeddingCache(tmp_path / "emb.jsonl"))
    for k, t in (("a", "sqlite storage database"), ("b", "password hashing bcrypt")):
        dense2.set_text(k, t)
    assert dense2.pending() == [] and dense2.ensure(tools2) == 0 and tools2.embedded == []
    q2 = dense2.embed_queries(tools2, ["sqlite database"])[0]
    assert q2 == q and tools2.embedded == []  # query vectors are cached too
    assert dense2.search(q2, 3) == [h for h in hits if h[0] != "c"]


def test_dense_index_budget_and_failure_fallback(tmp_path):
    dense = DenseIndex(EmbeddingCache(None), batch_size=8)
    dense.set_text("a", "word " * 400)
    tight = FakeTools(embedder=hash_embed, budget=StepBudget(max_embedding_tokens_per_event=100))
    assert dense.ensure(tight) == 0 and dense.pending() == ["a"] and tight.embedded == []
    broken = FakeTools(embedder=None)
    dense.begin_step()
    assert dense.ensure(broken) == 0
    assert dense.status()["status"] == "degraded" and "no embedding model" in dense.status()["reason"]
    dense.begin_step()
    dense.ensure(broken)
    assert dense.status()["status"] == "unavailable" and not dense.available
    ok = FakeTools(embedder=hash_embed)
    dense.begin_step()
    assert dense.ensure(ok) == 0 and ok.embedded == []  # stays off for the rest of the run


def test_embedding_cache_survives_a_torn_line(tmp_path):
    p = tmp_path / "emb.jsonl"
    cache = EmbeddingCache(p)
    cache.put_many([(text_sha256("t"), (0.5, 0.25))], "m")
    with open(p, "a") as fh:
        fh.write('{"sha256": "x", "vec')
    again = EmbeddingCache(p)
    assert again.get(text_sha256("t")) == (0.5, 0.25) and len(again) == 1


# ========================================================= retrieval strength
ADRS = {
    "docs/adr/0001-storage.md": "# ADR-0001: Keep records in SQLite\n\n## Context\nOne host, low write volume.\n\n"
                                "## Decision\nUse the sqlite3 module with a single file database.\n",
    "docs/adr/0002-hashing.md": "# ADR-0002: Password hashing cost\n\n## Context\nLogin latency budget is 250 ms.\n\n"
                                "## Decision\nbcrypt with cost factor 10.\n",
    "docs/adr/0003-status.md": "# ADR-0003: Poll the payment gateway for subscription status\n\n## Context\n"
                               "The processor cannot deliver webhook callbacks to us: inbound HTTP requests from the "
                               "internet are blocked by our firewall, so we cannot receive push notifications about "
                               "plan changes.\n\n## Decision\nA scheduled job queries the processor's API every ten "
                               "minutes and updates each account's plan.\n",
    "docs/adr/0004-logging.md": "# ADR-0004: Structured logging\n\n## Decision\nEmit JSON log lines with request ids.\n",
    "docs/adr/0005-queue.md": "# ADR-0005: Background jobs run in-process\n\n## Decision\nA thread pool runs jobs; "
                              "no external broker.\n",
    "docs/tickets/TCK-0042.md": "# TCK-0042: Bulk export of projects\n\nParked until the export size limit in "
                                "config/limits.json can be raised.\n",
    "config/limits.json": json.dumps({"export_max_rows": 1000, "upload_max_mb": 5}, indent=2) + "\n",
    "README.md": "# Tasklist app\n\nA small task tracker with accounts, projects and billing.\n",
    "app/billing.py": "def charge(account, amount):\n    return amount\n\n\ndef refund(account, amount):\n    return -amount\n",
    "app/export.py": "def export_projects(rows):\n    return rows[:1000]\n",
}

EVENT_SUBJECT = "Vendor announcement: real-time callbacks for plan changes"
EVENT_BODY = ("From next month the processor can call an endpoint we expose whenever a customer's plan changes, "
              "signed with a shared secret, instead of us asking for updates.")
EXPANSION = ["webhook callbacks inbound HTTP firewall", "how we learn about plan changes from the processor",
             "scheduled job queries processor API"]


def _memory(tmp_path, config: dict, expansion: list[str] | None):
    def model(req):
        if req.purpose == "query_expansion":
            return json.dumps({"queries": expansion or []})
        if req.purpose == "summary":
            return "summary"
        return json.dumps({"final": {"actions": [], "memory": ""}})

    tools = FakeTools(dict(ADRS), model=model, embedder=hash_embed)
    mem = BaselineMemory(resolve_config(config))
    mem.open(make_context(tmp_path / "state").state_dir, restart=False)
    mem.ingest_seed(tools)
    return mem, tools


def _ranked_paths(pack_text: str) -> list[str]:
    return [line.split(" | ")[0][len("[file "):] for line in pack_text.splitlines() if line.startswith("[file ")]


def test_paraphrased_event_retrieves_the_target_decision_via_expansion_and_body_text(tmp_path):
    title = ADRS["docs/adr/0003-status.md"].splitlines()[0]
    event_tokens = set(tokenize(f"{EVENT_SUBJECT}\n{EVENT_BODY}"))
    assert not (set(tokenize(title)) - {"adr", "0003", "adr-0003"}) & event_tokens  # a true paraphrase
    mem, tools = _memory(tmp_path, {"preset": "k8", "max_per_source": 1}, EXPANSION)
    event = make_event(1, EVENT_SUBJECT, EVENT_BODY)
    mem.record_event(event)
    tools.new_step()
    pack = mem.build_context(event, tools)
    text = "\n".join(s.text for s in pack.sections if s.title.startswith("retrieved repository"))
    ranked = _ranked_paths(text)
    assert "docs/adr/0003-status.md" in ranked[:3], ranked
    expansion_requests = [r for r in tools.requests if r.purpose == "query_expansion"]
    assert len(expansion_requests) == 1
    assert "Subject: " + EVENT_SUBJECT in expansion_requests[0].messages[0].content


def test_query_expansion_bridges_a_vocabulary_gap(tmp_path):
    subject, body = "Network rule revision approved", "Security opened the perimeter: outside systems may now reach the application directly."
    target = set(tokenize(ADRS["docs/adr/0003-status.md"]))
    assert not set(tokenize(f"{subject}\n{body}")) & target  # nothing lexical to match on

    def ranked(expansion, sub):
        mem, tools = _memory(tmp_path / sub, {"preset": "k8", "retrieval": "lexical", "max_per_source": 1}, expansion)
        event = make_event(1, subject, body)
        mem.record_event(event)
        tools.new_step()
        pack = mem.build_context(event, tools)
        return _ranked_paths("\n".join(s.text for s in pack.sections))

    assert "docs/adr/0003-status.md" not in ranked(None, "plain")
    assert "docs/adr/0003-status.md" in ranked(["inbound webhook callbacks blocked by the firewall"], "expanded")[:2]


def test_entity_mention_retrieves_the_chunk_that_carries_the_entity(tmp_path):
    mem, tools = _memory(tmp_path, {"preset": "k8", "query_expansion": False, "retrieval": "lexical"}, None)
    hits = mem.retriever.search(["Is TCK-0042 still blocked?"], k=3)
    assert hits[0].doc.path == "docs/tickets/TCK-0042.md" and "entity" in hits[0].channels
    hits = mem.retriever.search(["what does this cover"], k=3, entities=["path:config/limits.json"])
    assert hits[0].doc.path == "config/limits.json"
    # the ticket that mentions the config file is linked through the same entity
    assert "docs/tickets/TCK-0042.md" in [h.doc.path for h in hits]


def test_hybrid_retrieval_is_deterministic(tmp_path):
    results = []
    for i in range(2):
        mem, tools = _memory(tmp_path / str(i), {"preset": "k32"}, EXPANSION)
        hits = mem.retriever.search([EVENT_SUBJECT, EVENT_BODY] + EXPANSION, k=32, tools=tools,
                                    entities=["path:config/limits.json"])
        results.append([(h.doc.doc_id, h.score, h.channels) for h in hits])
    assert results[0] == results[1] and results[0]
    assert {c for _, _, chans in results[0] for c in chans} == {"bm25", "dense", "entity"}
