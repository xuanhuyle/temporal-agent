"""BaselineMemory: persistence order, future-blindness, checkpoints and restarts, indexing, modes, budgets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.agent import ModelSettings, NoteAction, ReopenAction, StepBudget

from baseline.agent import BaselineAgent
from baseline.memory import BaselineMemory, _ingest_priority
from baseline.presets import resolve_config
from contestant_runtime.memory import EventOutcome
from test_contestant_runtime import FakeTools, hash_embed, make_context, make_event, scripted

SEED = {
    "README.md": "# Ledger service\n\nKeeps balances for customer accounts.\n",
    "docs/adr/0001-currency.md": "# ADR-0001: Store amounts as integer cents\n\n## Context\nFloating point rounding "
                                 "errors in invoices.\n\n## Decision\nAll amounts are integer cents.\n",
    "docs/adr/0002-region.md": "# ADR-0002: Single region deployment\n\n## Decision\nRun in one region only; the "
                               "vendor has no second region.\n",
    "config/app.json": json.dumps({"region": "eu-west", "retries": 3}, indent=2) + "\n",
    "ledger/core.py": "def add(a, b):\n    return a + b\n\n\ndef balance(entries):\n    return sum(entries)\n",
    "tests/test_core.py": "from ledger.core import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
}

EVENTS = [
    make_event(1, "Invoice rounding complaint", "A customer saw 0.01 differences in an invoice total."),
    make_event(2, "Vendor opens a second region", "Our hosting vendor now offers a second region, zebrafish-east.",
               changed=(("write_file", "docs/vendor.md"),)),
    make_event(3, "Retries config", "Please lower retries in config/app.json to 2.",
               changed=(("write_file", "config/app.json"), ("delete_file", "tests/test_core.py"))),
]
WORLD = {
    2: {"docs/vendor.md": "# Vendor\n\nRegions: eu-west, zebrafish-east.\n"},
    3: {"config/app.json": json.dumps({"region": "eu-west", "retries": 2}, indent=2) + "\n"},
}


def cfg(**kw):
    return resolve_config({"preset": "k8", **kw})


def open_memory(state: Path, config: dict, *, restart: bool = False) -> BaselineMemory:
    mem = BaselineMemory(config)
    mem.open(state, restart=restart)
    return mem


def outcome(event, memory="", actions=(), writes=None) -> EventOutcome:
    return EventOutcome(seq=event.seq, event_id=event.event_id, actions=list(actions), memory=memory,
                        stop_reason="final", turns=1, workspace_writes=dict(writes or {}))


def apply_world(tools: FakeTools, event) -> None:
    for cp in event.changed_paths:
        if cp.op == "delete_file":
            tools.files.pop(cp.path, None)
        else:
            tools.files[cp.path] = WORLD[event.seq][cp.path]


def run_memory(state: Path, config: dict, events=EVENTS, embedder=hash_embed):
    """Drive a memory through seed + events the way LLMAgent does (without the loop)."""
    tools = FakeTools(dict(SEED), embedder=embedder)
    mem = open_memory(state, config)
    mem.ingest_seed(tools)
    mem.after_start(EventOutcome(seq=0, event_id=None, memory="seed: amounts in cents; one region"), tools)
    mem.checkpoint()
    packs = []
    for ev in events:
        tools.new_step()
        apply_world(tools, ev)
        mem.record_event(ev)
        mem.observe_world(ev, tools)
        packs.append(mem.build_context(ev, tools))
        mem.after_event(ev, outcome(ev, memory=f"handled {ev.subject}"), tools)
        mem.checkpoint()
    return mem, tools, packs


def search(mem: BaselineMemory, tools, query, **filters):
    args = {"query": query, "kind": None, "since_seq": None, "until_seq": None, "path": None, **filters}
    return mem._tool_search(tools, args)


# ================================================================ persistence
def test_raw_event_is_persisted_before_the_model_is_called(tmp_path):
    state = tmp_path / "state"
    agent = BaselineAgent(config={"preset": "k8"})
    agent.setup(make_context(state))
    tools = FakeTools(dict(SEED), embedder=hash_embed)
    agent.on_start(tools)
    seen: list[list[str]] = []

    def inspect(req):
        lines = (state / "memory" / "events.jsonl").read_text().splitlines()
        seen.append([json.loads(l)["event_id"] for l in lines])

    tools.on_model = inspect
    tools.new_step()
    agent.on_event(EVENTS[0], tools)
    assert seen and all(ids == ["evt-0001"] for ids in seen)
    purposes = [r.purpose for r in tools.requests]
    assert purposes == ["loop", "query_expansion", "loop", "summary"]  # start turn, then one event


def test_record_event_is_first_even_if_later_processing_fails(tmp_path):
    state = tmp_path / "state"
    agent = BaselineAgent(config={"preset": "k8"})
    agent.setup(make_context(state))

    class Broken(FakeTools):
        def read_file(self, path):
            raise RuntimeError("disk on fire")

    tools = Broken({"x.md": "x"}, embedder=hash_embed)
    with pytest.raises(RuntimeError):
        agent.on_event(make_event(1, changed=(("write_file", "x.md"),)), tools)
    lines = (state / "memory" / "events.jsonl").read_text().splitlines()
    assert [json.loads(l)["event_id"] for l in lines] == ["evt-0001"]


def test_events_are_never_retrievable_before_they_are_recorded(tmp_path):
    tools = FakeTools(dict(SEED), embedder=hash_embed)
    mem = open_memory(tmp_path / "s", cfg())
    mem.ingest_seed(tools)
    assert "zebrafish" not in search(mem, tools, "zebrafish second region")
    ev1, ev2 = EVENTS[0], EVENTS[1]
    mem.record_event(ev1)
    pack = mem.build_context(ev1, tools)
    rendered = "\n".join(s.render() for s in pack.sections)
    assert "zebrafish" not in rendered and "evt-0002" not in rendered
    assert "evt-0001" not in rendered  # the current event is in the message, not in memory sections
    assert "zebrafish" not in search(mem, tools, "zebrafish")
    mem.record_event(ev2)
    assert "evt-0002" in search(mem, tools, "zebrafish")
    pack3 = mem.build_context(EVENTS[2], tools)  # before evt-0003 is recorded: earlier events only
    assert "evt-0003" not in "\n".join(s.render() for s in pack3.sections)
    with pytest.raises(Exception, match="no event 'evt-0003'"):
        mem._tool_get_event(tools, {"event_id": "evt-0003"})


def test_stores_layout_and_append_only_logs(tmp_path):
    mem, tools, _ = run_memory(tmp_path / "s", cfg())
    root = tmp_path / "s" / "memory"
    for name in ("events.jsonl", "notes.jsonl", "docs_index.json", "embeddings.jsonl", "summary.json",
                 "checkpoint.json"):
        assert (root / name).is_file(), name
    events = [json.loads(l) for l in (root / "events.jsonl").read_text().splitlines()]
    assert [e["event_id"] for e in events] == ["evt-0001", "evt-0002", "evt-0003"]
    assert events[2]["changed_paths"] == [{"op": "write_file", "path": "config/app.json"},
                                          {"op": "delete_file", "path": "tests/test_core.py"}]
    notes = [json.loads(l) for l in (root / "notes.jsonl").read_text().splitlines()]
    assert [n["event_id"] for n in notes] == [None, "evt-0001", "evt-0002", "evt-0003"]
    ck = json.loads((root / "checkpoint.json").read_text())
    assert ck["last_seq"] == 3 and ck["events"] == 3 and ck["notes"] == 4 and ck["seed_ingested"] is True
    assert not list(root.glob(".*.tmp"))  # atomic writes leave no temp files
    mem.record_event(EVENTS[0])  # re-delivery is idempotent
    assert len((root / "events.jsonl").read_text().splitlines()) == 3


# ============================================================ restart/rebuild
def test_checkpoint_and_restart_rebuild_give_identical_retrieval(tmp_path):
    state = tmp_path / "s"
    mem, tools, _ = run_memory(state, cfg())
    queries = ["invoice rounding cents", "second region vendor", "retries config", "zebrafish-east", "ADR-0002"]
    before = {q: [(h.doc.doc_id, h.score, h.channels) for h in mem.retriever.search([q], k=8, tools=tools)]
              for q in queries}
    tools2 = FakeTools(embedder=hash_embed)
    again = open_memory(state, cfg(), restart=True)
    # every vector came from the cache; only what was still pending before (the last note) stays pending
    assert again.dense is not None and again.dense.pending() == mem.dense.pending() == ["note:000003:evt-0003"]
    after = {q: [(h.doc.doc_id, h.score, h.channels) for h in again.retriever.search([q], k=8, tools=tools2)]
             for q in queries}
    assert before == after
    assert tools2.embedded == []  # queries embedded before were cached too
    assert again.summary == mem.summary and len(again.notes) == len(mem.notes)
    assert again.docs_index == mem.docs_index
    assert again.retriever.doc_ids() == mem.retriever.doc_ids()


def test_restart_recovers_from_a_torn_log_line_and_requeues_unindexed_changes(tmp_path):
    state = tmp_path / "s"
    mem, tools, _ = run_memory(state, cfg(), events=EVENTS[:2])
    ev3 = EVENTS[2]
    mem.record_event(ev3)  # crash after recording, before indexing and checkpoint
    with open(state / "memory" / "events.jsonl", "a") as fh:
        fh.write('{"event_id": "evt-9999", "trunc')
    again = open_memory(state, cfg(), restart=True)
    assert [e["event_id"] for e in again.events] == ["evt-0001", "evt-0002", "evt-0003"]
    assert (state / "memory" / "events.jsonl").read_text().endswith("\n")
    assert again.pending_paths[:2] == ["config/app.json", "tests/test_core.py"]
    apply_world(tools, ev3)
    tools.new_step()
    again.observe_world(make_event(4, "next"), tools)
    assert "config/app.json" in again.docs_index and "tests/test_core.py" not in again.docs_index
    assert '"retries": 2' in search(again, tools, "retries", path="config")


def test_fresh_open_discards_stale_memory(tmp_path):
    state = tmp_path / "s"
    run_memory(state, cfg())
    fresh = open_memory(state, cfg(), restart=False)
    assert fresh.events == [] and fresh.notes == [] and len(fresh.retriever) == 0
    assert not (state / "memory" / "events.jsonl").exists()


def test_embeddings_cache_avoids_re_embedding(tmp_path):
    state = tmp_path / "s"
    mem, tools, _ = run_memory(state, cfg())
    mem.dense.ensure(tools)  # the last note is still pending
    n = len(tools.embedded)
    mem._index_text("README.md", SEED["README.md"], 9)  # unchanged content: nothing to do
    mem.dense.ensure(tools)
    assert len(tools.embedded) == n
    mem._index_text("README.md", "# Ledger service\n\nNow with audit logs.\n", 10)
    mem.dense.ensure(tools)
    assert len(tools.embedded) == n + 1
    mem._index_text("README.md", SEED["README.md"], 11)  # reverted: the earlier vector is reused
    mem.dense.ensure(tools)
    assert len(tools.embedded) == n + 1 and mem.dense.pending() == []
    assert len(set(tools.embedded)) == len(tools.embedded)  # no text was ever embedded twice


# ================================================================== indexing
def test_seed_ingestion_prioritizes_docs_and_respects_the_tool_budget(tmp_path):
    files = {f"src/m{i}.py": f"def f{i}():\n    return {i}\n" for i in range(30)}
    files.update({"README.md": "# R\n", "docs/adr/0001-a.md": "# ADR-0001: A\n", "settings.toml": "a = 1\n",
                  "tests/test_x.py": "def test(): pass\n", "logo.png": "binary"})
    assert sorted(files, key=_ingest_priority)[:3] == ["README.md", "docs/adr/0001-a.md", "settings.toml"]
    tools = FakeTools(files, budget=StepBudget(max_tool_calls_per_event=20))
    mem = open_memory(tmp_path / "s", cfg(ingest_reserve_tool_calls=5))
    mem.ingest_seed(tools)
    assert tools.budget_remaining()["tool_calls"] == 5
    assert tools.calls[0][0] == "list_files"
    read = [a["path"] for t, a in tools.calls if t == "read_file"]
    assert read[:3] == ["README.md", "docs/adr/0001-a.md", "settings.toml"] and len(read) == 14
    assert "logo.png" not in read and "logo.png" not in mem.pending_paths
    assert len(mem.pending_paths) == 34 - 14 and mem.pending_paths[-1] == "tests/test_x.py"
    # the rest is indexed lazily at later events, lazy_index_per_event (20) at a time
    tools.new_step(StepBudget())
    mem.record_event(make_event(1))
    mem.observe_world(make_event(1), tools)
    assert mem.pending_paths == [] and len(mem.docs_index) == 34


def test_observe_world_reindexes_changed_paths_and_drops_deleted_ones(tmp_path):
    mem, tools, _ = run_memory(tmp_path / "s", cfg(), events=EVENTS[:2])
    assert "zebrafish-east" in search(mem, tools, "Regions", kind="doc")
    tools.new_step()
    apply_world(tools, EVENTS[2])
    mem.record_event(EVENTS[2])
    mem.observe_world(EVENTS[2], tools)
    assert mem.docs_index["config/app.json"]["seq"] == 3
    assert "tests/test_core.py" not in mem.docs_index
    out = search(mem, tools, "retries", kind="doc")
    assert '"retries": 2' in out and '"retries": 3' not in out
    assert "content as indexed at seq 3" in out


def test_the_agents_own_writes_are_reindexed_without_tool_calls(tmp_path):
    mem, tools, _ = run_memory(tmp_path / "s", cfg(), events=EVENTS[:1])
    ev = EVENTS[1]
    tools.new_step()
    mem.record_event(ev)
    calls = len(tools.calls)
    mem.after_event(ev, outcome(ev, writes={"ledger/region.py": "SECOND_REGION = 'kestrel-north'\n",
                                            "ledger/core.py": None}), tools)
    assert len(tools.calls) == calls
    assert "kestrel-north" in search(mem, tools, "SECOND_REGION")
    assert "ledger/core.py" not in mem.docs_index


# ===================================================================== context
def test_rag_context_sections_are_labelled_and_retrieval_chars_counted(tmp_path):
    _, _, packs = run_memory(tmp_path / "s", cfg())
    pack = packs[1]  # evt-0002
    titles = [s.title for s in pack.sections]
    assert titles[0].startswith("rolling summary (written after seq 1)")
    assert titles[1] == "most recent earlier events (1)"
    assert any(t.startswith("retrieved repository content") for t in titles)
    assert any(t.startswith("retrieved notes") for t in titles)
    assert pack.retrieval_chars == sum(len(s.render()) + 2 for s in pack.sections)
    text = "\n".join(s.text for s in pack.sections)
    assert "[evt-0001 | seq 1] 2026-01-02T09:00:00Z | ticket | Sam | Invoice rounding complaint" in text
    assert "[file docs/adr/0002-region.md | " in text


def test_full_mode_puts_every_earlier_event_and_note_in_context(tmp_path):
    _, tools, packs = run_memory(tmp_path / "s", resolve_config({"preset": "full"}))
    assert not [r for r in tools.requests if r.purpose == "query_expansion"]
    pack = packs[2]
    titles = [s.title for s in pack.sections]
    assert "all earlier events (2, oldest first)" in titles
    assert "your notes from earlier events (3, oldest first)" in titles
    text = "\n".join(s.text for s in pack.sections)
    assert "zebrafish-east" in text and "0.01 differences" in text
    assert "handled Vendor opens a second region" in text and "seed: amounts in cents" in text
    assert not any(t.startswith("retrieved repository") for t in titles)


def test_full_mode_caps_its_history_by_shortening_the_oldest_events(tmp_path):
    events = [make_event(i, f"Event {i}", f"body{i} " + "x" * 3000) for i in range(1, 8)]
    mem, _, packs = run_memory(tmp_path / "s", resolve_config({"preset": "full", "full_context_chars": 8000,
                                                               "summary": "none"}), events=events)
    history = packs[-1].sections[0].text
    assert len(history) < 8000 + 500
    assert history.count("x" * 2000) == 1 and "x" * 2000 in history.split("[evt-0006 | seq 6]")[1]
    oldest = history.split("[evt-0002 | seq 2]")[0]
    assert "[evt-0001 | seq 1]" in oldest and "x" * 1000 not in oldest and "characters truncated" in oldest


def test_none_mode_has_no_memory_context_tools_or_summary(tmp_path):
    mem, tools, packs = run_memory(tmp_path / "s", resolve_config({"preset": "k8", "mode": "none"}))
    assert all(p.sections == () and p.retrieval_chars == 0 for p in packs)
    assert mem.local_tools() == [] and mem.reserved_model_calls() == 0
    assert tools.requests == []
    assert [t for t, _ in tools.calls] == []  # no seed ingestion either
    assert (tmp_path / "s" / "memory" / "events.jsonl").is_file()  # raw events are still persisted


def test_dense_unavailable_falls_back_to_lexical_and_says_so_once(tmp_path):
    tools = FakeTools(dict(SEED))
    probe = open_memory(tmp_path / "p", cfg())
    probe.ingest_seed(tools)
    assert probe.start_context(tools).notes == ()  # step 0 returns no actions: the note waits for an event
    mem, tools, packs = run_memory(tmp_path / "s", cfg(), embedder=None)
    assert packs[0].notes  # reported at the first event
    notes = [n for p in packs for n in p.notes]
    assert len(notes) == 1 and "dense retrieval unavailable" in notes[0] and "no embedding model" in notes[0]
    assert "zebrafish" in search(mem, tools, "zebrafish")
    assert json.loads((tmp_path / "s" / "memory" / "checkpoint.json").read_text())["dense"]["failures"] >= 2


def test_lexical_retrieval_config_never_calls_embed(tmp_path):
    mem, tools, _ = run_memory(tmp_path / "s", cfg(retrieval="lexical"))
    assert tools.embedded == [] and mem.dense is None
    assert mem.describe()["channels"] == ["bm25", "entity"]


# ============================================================= model budgets
def test_summary_and_expansion_are_skipped_when_model_calls_run_low(tmp_path):
    tools = FakeTools(dict(SEED), embedder=hash_embed, budget=StepBudget(max_model_calls_per_event=3))
    mem = open_memory(tmp_path / "s", cfg())
    mem.ingest_seed(tools)
    ev = EVENTS[0]
    mem.record_event(ev)
    mem.build_context(ev, tools)
    assert tools.requests == []  # 3 calls left: expansion would leave fewer than 2 loop calls + summary
    tools.counts["model_calls"] = 3
    mem.after_event(ev, outcome(ev, memory="m"), tools)
    assert tools.requests == [] and mem.summary["text"] == ""


def test_summary_update_uses_only_information_available_now(tmp_path):
    mem, tools, _ = run_memory(tmp_path / "s", cfg(), events=EVENTS[:2])
    reqs = [r for r in tools.requests if r.purpose == "summary"]
    assert len(reqs) == 2
    assert "zebrafish" not in reqs[0].messages[0].content  # written after evt-0001, before evt-0002 existed
    assert "Subject: Vendor opens a second region" in reqs[1].messages[0].content
    assert reqs[0].retrieval_chars == len("seed: amounts in cents; one region")  # the summary after step 0
    assert reqs[1].retrieval_chars == len("summary 0123abcd")  # the summary written after evt-0001
    assert mem.summary["seq"] == 2


def test_memory_tools(tmp_path):
    mem, tools, _ = run_memory(tmp_path / "s", cfg())
    names = [t.name for t in mem.local_tools()]
    assert names == ["memory_search", "memory_get_event"]
    out = mem._tool_get_event(tools, {"event_id": "EVT-0002"})
    assert out.startswith("[evt-0002 | seq 2]\nDate: ") and "Changed paths: docs/vendor.md (write_file)" in out
    with pytest.raises(Exception, match="kind must be one of"):
        search(mem, tools, "x", kind="adr")
    only_events = search(mem, tools, "region", kind="event", since_seq=2, until_seq=2)
    assert "[evt-0002" in only_events and "[file" not in only_events and "[evt-0001" not in only_events
    assert search(mem, tools, "region", path="nowhere/") == "no matching memory"


def test_memory_search_describes_its_channels_and_seq_filters_accurately():
    def desc(provider, **kw):
        mem = BaselineMemory(cfg(**kw))
        mem.use_model_settings(ModelSettings(embedding_provider=provider))
        return {t.name: t.description for t in mem.local_tools()}["memory_search"]

    hashed = desc("hash")
    assert "semantic" not in hashed.replace("not semantic", "")
    assert "keyword match (BM25)" in hashed and "entity matching" in hashed
    assert "hashed word and character n-gram vectors (lexical, not semantic)" in hashed
    assert "since_seq/until_seq" in hashed and "events and notes by their event seq" in hashed
    assert "repository files by the seq at which their content was indexed" in hashed
    assert "vector" not in desc("none")  # no embedding model in this run: no vector channel is claimed
    assert "embedding-vector similarity" in desc("other-provider")
    assert "BM25" not in desc("hash", retrieval="dense") and "vector" not in desc("hash", retrieval="lexical")
    unset = BaselineMemory(cfg())  # before settings are known: a neutral description
    assert "semantic" not in {t.name: t.description for t in unset.local_tools()}["memory_search"]


def test_agent_edits_of_an_interrupted_step_are_reread_after_a_restart(tmp_path):
    state = tmp_path / "s"
    mem, tools, _ = run_memory(state, cfg(), events=EVENTS[:1])
    ev = EVENTS[1]
    tools.new_step()
    apply_world(tools, ev)
    mem.record_event(ev)
    mem.observe_world(ev, tools)
    # the loop announces each edit before executing it; then the step is cut short (no after_event, no checkpoint)
    mem.before_workspace_change("write_file", "ledger/region.py")
    tools.files["ledger/region.py"] = "SECOND_REGION = 'kestrel-north'\n"
    mem.before_workspace_change("delete_file", "./ledger//core.py")
    del tools.files["ledger/core.py"]
    mem.before_workspace_change("write_file", "../outside.py")  # refused by the workspace: not logged
    log = state / "memory" / "workspace_intents.jsonl"
    assert [json.loads(line)["path"] for line in log.read_text().splitlines()] == ["ledger/region.py", "ledger/core.py"]
    with open(log, "a") as fh:
        fh.write('{"op": "write_file", "pa')  # torn by the crash

    again = open_memory(state, cfg(), restart=True)
    assert log.read_text().endswith("\n") and len(log.read_text().splitlines()) == 2
    assert again.pending_paths[:2] == ["ledger/region.py", "ledger/core.py"]
    assert "ledger/core.py" in again.docs_index  # stale until it is re-read
    ev3 = make_event(3, "Next")
    tools.new_step()
    again.record_event(ev3)
    again.observe_world(ev3, tools)
    assert "ledger/core.py" not in again.docs_index
    assert "kestrel-north" in search(again, tools, "SECOND_REGION")
    again.checkpoint()
    # once a checkpoint covers the logged edits, a later restart does not re-read them
    third = open_memory(state, cfg(), restart=True)
    assert "ledger/region.py" not in third.pending_paths and "ledger/core.py" not in third.pending_paths
    assert third.docs_index == again.docs_index


def test_completed_steps_leave_no_stale_intents(tmp_path):
    state = tmp_path / "s"
    mem, tools, _ = run_memory(state, cfg(), events=EVENTS[:1])
    ev = EVENTS[1]
    tools.new_step()
    mem.record_event(ev)
    mem.before_workspace_change("write_file", "notes/x.md")
    tools.files["notes/x.md"] = "x\n"
    mem.after_event(ev, outcome(ev, writes={"notes/x.md": "x\n"}), tools)
    mem.checkpoint()
    again = open_memory(state, cfg(), restart=True)
    assert "notes/x.md" not in again.pending_paths and "notes/x.md" in again.docs_index
    none = open_memory(tmp_path / "n", cfg(mode="none"))
    none.before_workspace_change("write_file", "a.md")
    assert not (tmp_path / "n" / "memory" / "workspace_intents.jsonl").exists()


def test_notes_store_conclusions_and_actions(tmp_path):
    mem, tools, _ = run_memory(tmp_path / "s", cfg(), events=EVENTS[:1])
    ev = EVENTS[1]
    mem.record_event(ev)
    mem.after_event(ev, outcome(ev, memory="vendor now has two regions",
                                actions=[ReopenAction("ADR-0002", "vendor added a region", ("evt-0002",)),
                                         NoteAction("check config")]), tools)
    rec = mem.notes[-1]
    assert rec["actions"] == ["reopened ADR-0002: vendor added a region (evidence: evt-0002)", "note: check config"]
    assert "reopened ADR-0002" in search(mem, tools, "two regions", kind="note")
