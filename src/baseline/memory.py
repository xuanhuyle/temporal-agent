"""``BaselineMemory``: the conventional memory system (contestant code, milestone-2 design section 9).

A strong, ordinary long-lived-agent memory with no temporal-causal machinery:

- **raw event log**: every received event is appended to ``events.jsonl``
  (and fsynced) in ``record_event``, before any other processing;
- **notes**: the agent's own per-event conclusions (final memory text and a
  compact list of its actions), append-only in ``notes.jsonl``;
- **document index**: the workspace, chunked (``baseline.chunking``) and kept
  current: seed ingestion, re-indexing of each event's changed paths, and of
  the agent's own writes; file texts are stored content-addressed in
  ``blobs/`` with a ``docs_index.json`` snapshot. Every ``write_file`` /
  ``delete_file`` of the agent is logged (path and op) to the append-only
  ``workspace_intents.jsonl`` *before* it is executed, so that edits of a
  step cut short by a timeout or crash are re-read after the restart;
- **hybrid retrieval** over events, notes and document chunks
  (``baseline.retrieval``), optional LLM query expansion (one call);
- **rolling summary**: rewritten once per event (one call) from what is known
  at that point;
- **checkpoint**: ``checkpoint.json``, ``docs_index.json`` and
  ``summary.json`` are written atomically (temp file + ``os.replace``); on a
  restart the indexes are rebuilt deterministically from the stores, and
  every path changed after the last checkpoint (by an event or by the agent)
  is queued to be re-read from the workspace.

Modes: ``rag`` (retrieved context), ``full`` (every stored event and note in
context; documents searchable through the memory tools only) and ``none``
(diagnostic: only the current event; no summary, no memory tools).

It holds only what the agent has received: the seed repository, events
already delivered, and its own conclusions. It has no labels and no mapping
from new facts to old decisions; relevance is rediscovered by retrieval and
by the model's reasoning.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from harness.agent import AgentEvent, ChangedPath, ModelSettings
from harness.errors import AccessDenied, ToolError
from harness.llm import ModelMessage, ModelRequest
from harness.tool_specs import ArgSpec

from baseline.chunking import chunk_file
from baseline.retrieval import KINDS, Doc, Filters, Hit, Retriever
from baseline.text import extract_entities
from baseline.vectors import DenseIndex, EmbeddingCache, text_sha256
from contestant_runtime.loop import estimate_request_tokens, remaining, response_text
from contestant_runtime.memory import ContextPack, EventOutcome, LocalTool, MemorySystem
from contestant_runtime.protocol import (
    MemorySection,
    extract_json_object,
    render_event_header,
    truncate_text,
)

__all__ = ["BaselineMemory", "MEMORY_VERSION"]

MEMORY_VERSION = "baseline-memory/1"
TOKEN_SAFETY = 1.25
_BINARY_EXTS = (
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".tgz", ".tar", ".whl", ".so", ".dylib",
    ".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".bin", ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".mp4",
)
_CONFIG_EXTS = (".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".env")

EXPANSION_SYSTEM = (
    "You write search queries for a software maintainer's memory of a project: past events, decision "
    "records, tickets, notes, code and configuration."
)
EXPANSION_TASK = (
    "Write search queries that would find what in that memory this event could affect or that bears on how "
    "to handle it: related earlier decisions and their stated reasons, constraints and assumptions, earlier "
    "discussions, open, parked or blocked work, and the code and configuration involved. Use different "
    "wordings and related technical terms, not only the event's own words. Reply with JSON only: "
    '{{"queries": ["...", "..."]}} with at most {n} queries.'
)
SUMMARY_SYSTEM = (
    "You keep the running summary that a software maintainer reads before handling each new event. It is "
    "their long-term memory between events."
)
SUMMARY_TASK = (
    "Rewrite the running summary so that it reflects everything above. Keep what matters for future work: "
    "the project's current state; decisions in force with their stated reasons and assumptions; constraints "
    "and requirements; open, parked or blocked work and what it is waiting for; notable recent changes; what "
    "you reopened or changed and why. Drop what no longer matters. Plain text, at most about {words} words."
)


# ----------------------------------------------------------------- file utils
def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    line = json.dumps(record, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Records of an append-only log; a torn trailing line (crash mid-write) is cut off the file."""
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    good_bytes = 0
    with open(path, "rb") as fh:
        data = fh.read()
    for raw in data.splitlines(keepends=True):
        try:
            rec = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            break
        if not raw.endswith(b"\n") or not isinstance(rec, dict):
            break
        out.append(rec)
        good_bytes += len(raw)
    if good_bytes != len(data):
        with open(path, "r+b") as fh:
            fh.truncate(good_bytes)
    return out


def _read_json(path: Path, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, indent=1) + "\n"


def _norm_path(path: str) -> str:
    return "/".join(p for p in path.split("/") if p not in ("", "."))


def _ingest_priority(path: str) -> tuple[int, str]:
    """Documentation and decision records first, then configuration, source, tests, everything else."""
    p = path.lower()
    parts = p.split("/")
    base = parts[-1]
    is_test = "tests" in parts[:-1] or "test" in parts[:-1] or base.startswith("test_") or base.endswith("_test.py")
    if base.startswith("readme") or "docs" in parts[:-1] or "doc" in parts[:-1] or "adr" in parts[:-1] or (
        p.endswith((".md", ".rst", ".txt")) and not is_test
    ):
        return 0, path
    if p.endswith(_CONFIG_EXTS) or base in ("requirements.txt", "setup.cfg", "makefile", "dockerfile"):
        return 1, path
    if p.endswith(".py") and not is_test:
        return 2, path
    if is_test:
        return 3, path
    return 4, path


# --------------------------------------------------------------------- memory
class BaselineMemory(MemorySystem):
    def __init__(self, config: dict[str, Any]) -> None:
        self.cfg = dict(config)
        self.mode: str = self.cfg["mode"]
        self.top_k: int = self.cfg["top_k"]
        self.root: Path | None = None
        self.events: list[dict[str, Any]] = []
        self._event_pos: dict[str, int] = {}
        self.notes: list[dict[str, Any]] = []
        self.summary: dict[str, Any] = {"seq": -1, "text": ""}
        self.docs_index: dict[str, dict[str, Any]] = {}
        self._path_chunks: dict[str, list[str]] = {}
        self.pending_paths: list[str] = []
        self.unreadable: set[str] = set()
        self.seed_ingested = False
        self.last_checkpoint_seq = -1
        self.dense_note_emitted = False
        self.dense: DenseIndex | None = None
        self.retriever = Retriever()
        self.intent_count = 0  # records in workspace_intents.jsonl
        self.embedding_provider: str | None = None  # from the run's ModelSettings, if given

    # ---------------------------------------------------------------- static
    def describe(self) -> dict[str, Any]:
        retrieval = self.cfg["retrieval"]
        channels = {"hybrid": ["bm25", "dense", "entity"], "lexical": ["bm25", "entity"],
                    "dense": ["dense", "entity"]}[retrieval]
        return {
            "name": "baseline",
            "version": MEMORY_VERSION,
            "mode": self.mode,
            "channels": channels if self.mode != "none" else [],
            "fusion": "rrf",
            "stores": ["events.jsonl", "notes.jsonl", "workspace_intents.jsonl", "docs_index.json", "blobs/",
                       "embeddings.jsonl", "summary.json", "checkpoint.json"],
        }

    def reserved_model_calls(self) -> int:
        return 1 if self._summary_on() else 0

    def use_model_settings(self, settings: ModelSettings) -> None:
        provider = getattr(settings, "embedding_provider", None)
        self.embedding_provider = provider if isinstance(provider, str) else None

    def _summary_on(self) -> bool:
        return self.cfg["summary"] == "rolling" and self.mode != "none"

    def _dense_on(self) -> bool:
        return self.cfg["retrieval"] in ("hybrid", "dense") and self.mode != "none"

    # ------------------------------------------------------------------ open
    def _p(self, name: str) -> Path:
        assert self.root is not None, "open() has not been called"
        return self.root / name

    def open(self, state_dir: Path, *, restart: bool) -> None:
        root = Path(state_dir) / "memory"
        if not restart and root.exists():
            shutil.rmtree(root)  # a fresh start never inherits stale memory
        (root / "blobs").mkdir(parents=True, exist_ok=True)
        self.root = root
        self.intent_count = 0
        if self._dense_on():
            cache = EmbeddingCache(root / "embeddings.jsonl")
            self.dense = DenseIndex(cache, embed_chars=self.cfg["embed_chars"], batch_size=self.cfg["embed_batch"])
        self.retriever = Retriever(
            dense=self.dense,
            rrf_k=self.cfg["rrf_k"],
            max_per_source=self.cfg["max_per_source"],
            use_bm25=self.cfg["retrieval"] != "dense",
        )
        if restart:
            self._recover()

    def _recover(self) -> None:
        ck = _read_json(self._p("checkpoint.json"), {})
        if not isinstance(ck, dict):
            ck = {}
        self.seed_ingested = bool(ck.get("seed_ingested", False))
        self.pending_paths = [p for p in ck.get("pending_paths", []) if isinstance(p, str)]
        self.unreadable = {p for p in ck.get("unreadable", []) if isinstance(p, str)}
        self.last_checkpoint_seq = int(ck.get("last_seq", -1)) if isinstance(ck.get("last_seq", -1), int) else -1
        self.dense_note_emitted = bool(ck.get("dense_note_emitted", False))
        dense_state = ck.get("dense") if isinstance(ck.get("dense"), dict) else {}
        if self.dense is not None:
            self.dense.restore_status(dense_state.get("failures", 0), dense_state.get("reason", ""))
        summary = _read_json(self._p("summary.json"), {})
        if isinstance(summary, dict) and isinstance(summary.get("text"), str):
            self.summary = {"seq": summary.get("seq", -1), "text": summary["text"]}

        for rec in _read_jsonl(self._p("events.jsonl")):
            self._remember_event(rec)
            if int(rec.get("seq", -1)) > self.last_checkpoint_seq:
                # processed after the last checkpoint: its world changes may not be indexed yet
                for cp in rec.get("changed_paths", []):
                    if isinstance(cp, dict) and isinstance(cp.get("path"), str):
                        self._queue(cp["path"], front=False)
        for rec in _read_jsonl(self._p("notes.jsonl")):
            self._remember_note(rec)
        # the agent's own writes and deletes after the last checkpoint: the step may have been cut
        # short before after_event re-indexed them, so re-read each path from the workspace
        intents = _read_jsonl(self._p("workspace_intents.jsonl"))
        self.intent_count = len(intents)
        covered = ck.get("intents", 0)
        covered = covered if isinstance(covered, int) and not isinstance(covered, bool) and covered >= 0 else 0
        for rec in reversed(intents[covered:]):
            if isinstance(rec.get("path"), str):
                self._queue(rec["path"], front=True)
        index = _read_json(self._p("docs_index.json"), {})
        paths = index.get("paths", {}) if isinstance(index, dict) else {}
        for path in sorted(paths):
            entry = paths[path]
            try:
                with open(self._p("blobs") / f"{entry['sha256']}.txt", "r", encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, KeyError, TypeError, ValueError):
                self._queue(path, front=False)
                continue
            self._index_text(path, text, int(entry.get("seq", 0)))

    # --------------------------------------------------------------- events
    def _event_doc(self, rec: dict[str, Any]) -> Doc:
        changed = [cp for cp in rec.get("changed_paths", []) if isinstance(cp, dict)]
        paths = sorted({_norm_path(str(cp.get("path", ""))) for cp in changed} - {""})
        extra = tuple(sorted({f"path:{p}" for p in paths} | {f"file:{p.rsplit('/', 1)[-1]}" for p in paths}))
        changed_text = ", ".join(f"{cp.get('path')} ({cp.get('op')})" for cp in changed) or "(none)"
        return Doc(
            doc_id=f"event:{rec['event_id']}",
            kind="event",
            source=f"event:{rec['event_id']}",
            label=f"{rec['event_id']} {rec.get('channel', '')} {rec.get('author', '')}",
            text=f"Subject: {rec.get('subject', '')}\n{rec.get('body', '')}\nChanged paths: {changed_text}",
            seq=int(rec.get("seq", 0)),
            extra_entities=extra,
        )

    def _remember_event(self, rec: dict[str, Any]) -> None:
        eid = rec.get("event_id")
        if not isinstance(eid, str) or eid in self._event_pos:
            return
        self._event_pos[eid] = len(self.events)
        self.events.append(rec)
        self.retriever.add(self._event_doc(rec))

    def record_event(self, event: AgentEvent) -> None:
        rec = event.to_dict()
        if event.event_id in self._event_pos:
            return  # already recorded (idempotent on re-delivery)
        _append_jsonl(self._p("events.jsonl"), rec)
        self._remember_event(rec)

    # ---------------------------------------------------------------- notes
    def _note_doc(self, rec: dict[str, Any]) -> Doc | None:
        body = rec.get("memory", "") or ""
        acts = rec.get("actions", []) or []
        if not body.strip() and not acts:
            return None
        text = body + (("\nActions: " + "; ".join(str(a) for a in acts)) if acts else "")
        eid = rec.get("event_id") or "seed"
        return Doc(
            doc_id=f"note:{int(rec.get('seq', 0)):06d}:{eid}",
            kind="note",
            source=f"note:{eid}",
            label=f"note after {eid} {rec.get('subject', '')}",
            text=text,
            seq=int(rec.get("seq", 0)),
        )

    def _remember_note(self, rec: dict[str, Any]) -> None:
        self.notes.append(rec)
        doc = self._note_doc(rec)
        if doc is not None:
            self.retriever.add(doc)

    @staticmethod
    def _compact_actions(outcome: EventOutcome) -> list[str]:
        out = []
        for a in outcome.actions:
            d = a.to_dict()
            if d["type"] == "reopen":
                ev = ", ".join(d["evidence"])
                out.append(f"reopened {d['target']}: {d['rationale'][:300]}" + (f" (evidence: {ev})" if ev else ""))
            else:
                out.append(f"note: {d['text'][:300]}")
        return out

    def _store_note(self, seq: int, event_id: str | None, timestamp: str, subject: str, outcome: EventOutcome) -> None:
        rec = {
            "seq": seq,
            "event_id": event_id,
            "timestamp": timestamp,
            "subject": subject,
            "memory": outcome.memory,
            "actions": self._compact_actions(outcome),
            "stop_reason": outcome.stop_reason,
        }
        _append_jsonl(self._p("notes.jsonl"), rec)
        self._remember_note(rec)

    def before_workspace_change(self, op: str, path: str) -> None:
        """Log the agent's write/delete durably before it happens (re-read after a restart if need be)."""
        if self.mode == "none" or self.root is None:
            return
        path = _norm_path(path)
        if not path or path.startswith("/") or ".." in path.split("/"):
            return  # refused by the workspace anyway: nothing can become stale
        _append_jsonl(self._p("workspace_intents.jsonl"), {"op": op, "path": path, "seq": self._current_seq()})
        self.intent_count += 1

    # ------------------------------------------------------------ documents
    def _queue(self, path: str, *, front: bool) -> None:
        path = _norm_path(path)
        if not path:
            return
        if path in self.pending_paths:
            self.pending_paths.remove(path)
        if front:
            self.pending_paths.insert(0, path)
        else:
            self.pending_paths.append(path)

    def _drop_path(self, path: str) -> None:
        path = _norm_path(path)
        for doc_id in self._path_chunks.pop(path, []):
            self.retriever.remove(doc_id)
        self.docs_index.pop(path, None)
        if path in self.pending_paths:
            self.pending_paths.remove(path)

    def _index_text(self, path: str, text: str, seq: int) -> None:
        path = _norm_path(path)
        text = text[: self.cfg["max_file_chars"]]
        sha = text_sha256(text)
        if self.docs_index.get(path, {}).get("sha256") == sha and path in self._path_chunks:
            return
        for doc_id in self._path_chunks.pop(path, []):
            self.retriever.remove(doc_id)
        blob = self._p("blobs") / f"{sha}.txt"
        if not blob.exists():
            _atomic_write(blob, text)
        base = path.rsplit("/", 1)[-1]
        ids: list[str] = []
        for c in chunk_file(path, text, self.cfg["chunk_chars"], self.cfg["chunk_overlap"]):
            doc = Doc(
                doc_id=f"doc:{c.chunk_id}",
                kind="doc",
                source=f"file:{path}",
                label=f"{path} {c.title}",
                text=c.text,
                seq=seq,
                path=path,
                extra_entities=(f"file:{base}", f"path:{path}"),
            )
            self.retriever.add(doc)
            ids.append(doc.doc_id)
        self._path_chunks[path] = ids
        self.docs_index[path] = {"sha256": sha, "seq": seq, "chunks": len(ids)}

    def _index_pending(self, tools: Any, *, seq: int, limit: int | None, reserve: int) -> None:
        done = 0
        while self.pending_paths and (limit is None or done < limit):
            if remaining(tools)["tool_calls"] <= reserve:
                break
            path = self.pending_paths.pop(0)
            done += 1
            try:
                text = tools.read_file(path)
            except AccessDenied:
                self.unreadable.add(path)
                self._drop_path(path)
                continue
            except ToolError as exc:
                msg = str(exc)
                if "no such file" in msg or "not a file" in msg:
                    self._drop_path(path)
                else:
                    self.unreadable.add(path)
                    self._drop_path(path)
                continue
            if not isinstance(text, str):
                continue
            self.unreadable.discard(path)
            self._index_text(path, text, seq)

    @staticmethod
    def _reserve(tools: Any, configured: int) -> int:
        """Tool calls kept for the model loop: the configured reserve, but at most half of what is left."""
        return min(configured, remaining(tools)["tool_calls"] // 2)

    def _current_seq(self) -> int:
        return int(self.events[-1].get("seq", 0)) if self.events else 0

    def ingest_seed(self, tools: Any) -> None:
        if self.mode == "none":
            self.seed_ingested = True
            return
        if self.dense is not None:
            self.dense.begin_step()
        if remaining(tools)["tool_calls"] < 1:
            return
        try:
            files = tools.list_files()
        except ToolError:
            return
        wanted = [f for f in files if isinstance(f, str) and not f.lower().endswith(_BINARY_EXTS)]
        for path in sorted(wanted, key=_ingest_priority):
            if path not in self.docs_index and path not in self.unreadable:
                self._queue(path, front=False)
        self.seed_ingested = True
        self._index_pending(tools, seq=self._current_seq(), limit=None,
                            reserve=self._reserve(tools, self.cfg["ingest_reserve_tool_calls"]))
        if self.dense is not None:
            self.dense.ensure(tools)

    def observe_world(self, event: AgentEvent, tools: Any) -> None:
        if self.mode == "none":
            return
        if self.dense is not None:
            self.dense.begin_step()
        if not self.seed_ingested:
            self.ingest_seed(tools)
        changed = 0
        for cp in reversed(event.changed_paths):
            if cp.op == "delete_file":
                self._drop_path(cp.path)
            else:
                self.unreadable.discard(_norm_path(cp.path))
                self._queue(cp.path, front=True)
                changed += 1
        self._index_pending(tools, seq=event.seq, limit=changed + self.cfg["lazy_index_per_event"],
                            reserve=self._reserve(tools, self.cfg["event_reserve_tool_calls"]))

    # -------------------------------------------------------------- context
    def _render_event(self, rec: dict[str, Any], body_chars: int) -> str:
        changed = tuple(
            ChangedPath(op=str(cp.get("op", "")), path=str(cp.get("path", "")))
            for cp in rec.get("changed_paths", [])
            if isinstance(cp, dict)
        )
        ev = AgentEvent(
            schema_version=str(rec.get("schema_version", "")),
            event_id=str(rec.get("event_id", "")),
            seq=int(rec.get("seq", 0)),
            timestamp=str(rec.get("timestamp", "")),
            channel=str(rec.get("channel", "")),
            author=str(rec.get("author", "")),
            subject=str(rec.get("subject", "")),
            body=truncate_text(str(rec.get("body", "")), body_chars),
            changed_paths=changed,
        )
        return f"[{ev.event_id} | seq {ev.seq}]\n" + render_event_header(ev)

    def _event_line(self, rec: dict[str, Any]) -> str:
        return (f"[{rec.get('event_id')} | seq {rec.get('seq')}] {rec.get('timestamp')} | {rec.get('channel')} | "
                f"{rec.get('author')} | {rec.get('subject')}")

    def _render_hit(self, hit: Hit, chars: int) -> str:
        d = hit.doc
        if d.kind == "event":
            rec = self.events[self._event_pos[d.doc_id.split(":", 1)[1]]]
            return self._render_event(rec, chars)
        if d.kind == "note":
            eid = d.source.split(":", 1)[1]
            return f"[note after {eid} | seq {d.seq}]\n{truncate_text(d.text, chars)}"
        entry = self.docs_index.get(d.path or "", {})
        return (f"[file {d.path} | {d.label[len(d.path or '') + 1:].strip() or 'part'} | content as indexed at seq "
                f"{entry.get('seq', d.seq)}]\n{truncate_text(d.text, chars)}")

    def _summary_section(self) -> list[MemorySection]:
        if not self._summary_on() or not self.summary.get("text", "").strip():
            return []
        return [MemorySection(f"rolling summary (written after seq {self.summary.get('seq')})", self.summary["text"])]

    def _expansion_queries(self, event: AgentEvent, tools: Any) -> list[str]:
        if not self.cfg["query_expansion"] or self.cfg["max_expansion_queries"] < 1:
            return []
        rem = remaining(tools)
        # keep at least two loop calls and the summary call
        if rem["model_calls"] < 3 + self.reserved_model_calls():
            return []
        summary = self.summary.get("text", "") if self._summary_on() else ""
        parts = [f"<<event seq={event.seq} id={event.event_id}>>",
                 render_event_header(dataclasses.replace(event, body=truncate_text(event.body, 3000)))]
        if summary.strip():
            parts.append(f"<<memory rolling summary>>\n{summary}")
        parts.append(EXPANSION_TASK.format(n=self.cfg["max_expansion_queries"]))
        content = "\n\n".join(parts)
        req = ModelRequest(
            system=EXPANSION_SYSTEM,
            messages=(ModelMessage("user", content),),
            max_output_tokens=600,
            purpose="query_expansion",
            retrieval_chars=len(summary) if summary.strip() else 0,
        )
        if estimate_request_tokens(req) * TOKEN_SAFETY > rem["model_input_tokens"]:
            return []
        try:
            resp = tools.model_complete(req)
        except ToolError:
            return []
        obj = extract_json_object(response_text(resp))
        raw = obj.get("queries") if isinstance(obj, dict) else None
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for q in raw:
            if isinstance(q, str) and q.strip():
                q = " ".join(q.split())[:300]
                if q not in out:
                    out.append(q)
            if len(out) >= self.cfg["max_expansion_queries"]:
                break
        return out

    def _dense_notes(self) -> list[str]:
        if self.dense is None or self.dense_note_emitted:
            return []
        st = self.dense.status()
        if st["status"] == "ok":
            return []
        self.dense_note_emitted = True
        return [f"dense retrieval {st['status']} ({st['reason']}); lexical and entity retrieval continue"]

    def build_context(self, event: AgentEvent, tools: Any) -> ContextPack:
        if self.mode == "none":
            return ContextPack()
        if self.dense is not None:
            self.dense.ensure(tools)
        sections = list(self._summary_section())
        current = f"event:{event.event_id}"
        earlier = [r for r in self.events if r.get("event_id") != event.event_id]
        if self.mode == "full":
            sections += self._full_sections(earlier)
        else:
            recent_n = self.cfg["recent_events"]
            if recent_n and earlier:
                lines = [self._event_line(r) for r in earlier[-recent_n:]]
                sections.append(MemorySection(f"most recent earlier events ({len(lines)})", "\n".join(lines)))
            queries = [event.subject, f"{event.subject}\n{event.body[:2000]}"]
            queries += self._expansion_queries(event, tools)
            hints = set(extract_entities(f"{event.subject}\n{event.body}"))
            for cp in event.changed_paths:
                p = _norm_path(cp.path)
                hints.update({f"path:{p}", f"file:{p.rsplit('/', 1)[-1]}"})
            hits = self.retriever.search(queries, k=self.top_k, filters=Filters(exclude=frozenset({current})),
                                         entities=sorted(hints), tools=tools)
            sections += self._hit_sections(hits)
        notes = self._dense_notes()
        chars = sum(len(s.render()) + 2 for s in sections)
        return ContextPack(tuple(sections), chars, tuple(notes))

    def _hit_sections(self, hits: list[Hit]) -> list[MemorySection]:
        chars = self.cfg["hit_chars"]
        groups: dict[str, list[str]] = {"event": [], "note": [], "doc": []}
        for h in hits:
            groups[h.doc.kind].append(self._render_hit(h, chars))
        titles = {
            "event": "retrieved earlier events (best match first)",
            "note": "retrieved notes you wrote after earlier events (best match first)",
            "doc": "retrieved repository content (best match first; read the file for its current state)",
        }
        return [MemorySection(f"{titles[k]} ({len(v)})", "\n\n".join(v)) for k, v in groups.items() if v]

    def _full_sections(self, earlier: list[dict[str, Any]]) -> list[MemorySection]:
        cap = self.cfg["full_context_chars"]
        body_chars = self.cfg["event_chars"]
        blocks = [self._render_event(r, body_chars) for r in earlier]
        total = sum(len(b) + 2 for b in blocks)
        i = 0
        while total > cap and i < len(blocks):  # shorten the oldest bodies first
            short = self._render_event(earlier[i], 300)
            total -= len(blocks[i]) - len(short)
            blocks[i] = short
            i += 1
        dropped = 0
        while total > cap and blocks:
            total -= len(blocks[0]) + 2
            blocks.pop(0)
            dropped += 1
        out: list[MemorySection] = []
        text = "\n\n".join(blocks)
        if dropped:
            text = f"[{dropped} oldest events omitted for length; use memory_search or memory_get_event]\n\n" + text
        if earlier:
            out.append(MemorySection(f"all earlier events ({len(earlier)}, oldest first)", text))
        note_cap = max(1, cap // 4)
        note_blocks = []
        for rec in self.notes:
            doc = self._note_doc(rec)
            if doc is not None:
                note_blocks.append(f"[note after {rec.get('event_id') or 'seed'} | seq {rec.get('seq')}]\n{doc.text}")
        note_text = "\n\n".join(note_blocks)
        if len(note_text) > note_cap:
            note_text = "[older notes omitted for length]\n" + note_text[-note_cap:]
        if note_blocks:
            out.append(MemorySection(f"your notes from earlier events ({len(note_blocks)}, oldest first)", note_text))
        return out

    def start_context(self, tools: Any) -> ContextPack:
        if self.mode == "none":
            return ContextPack()
        paths = sorted(set(self.docs_index) | set(self.pending_paths))
        if not paths:
            return ContextPack()
        listing = "\n".join(paths[:400]) + (f"\n[... {len(paths) - 400} more]" if len(paths) > 400 else "")
        section = MemorySection(f"repository files ({len(paths)})", listing)
        # no runtime notes here: step 0 returns no actions, so they are left for the first event
        return ContextPack((section,), len(section.render()) + 2)

    # ---------------------------------------------------------- memory tools
    def local_tools(self) -> list[LocalTool]:
        if self.mode == "none":
            return []
        snippet = self.cfg["search_snippet_chars"]
        return [
            LocalTool(
                name="memory_search",
                args=(ArgSpec("query", "str"), ArgSpec("kind", "opt_str", None), ArgSpec("since_seq", "opt_int", None),
                      ArgSpec("until_seq", "opt_int", None), ArgSpec("path", "opt_str", None)),
                description=self._search_description(),
                handler=self._tool_search,
                max_chars=min(64_000, self.top_k * (snippet + 200) + 1000),
            ),
            LocalTool(
                name="memory_get_event",
                args=(ArgSpec("event_id", "str"),),
                description="The full stored text of an event you received earlier (or of the current one).",
                handler=self._tool_get_event,
                max_chars=self.cfg["event_chars"] + 2000,
            ),
        ]

    def _vector_channel_text(self) -> str | None:
        """What the dense channel really is, given the run's embedding provider (None: no vector channel)."""
        provider = self.embedding_provider
        if provider == "none":
            return None  # no embedding model in this run: the channel cannot work
        if provider == "hash":
            return "similarity of hashed word and character n-gram vectors (lexical, not semantic)"
        return "embedding-vector similarity (the run's embedding model)"

    def _search_description(self) -> str:
        channels: list[str] = []
        if self.cfg["retrieval"] != "dense":
            channels.append("keyword match (BM25)")
        if self.cfg["retrieval"] != "lexical":
            vector = self._vector_channel_text()
            if vector:
                channels.append(vector)
        channels.append("entity matching (ids, file paths, versions)")
        return (
            f"Search your memory: earlier events, your notes from earlier events, and indexed repository "
            f"files. Retrieval: {', '.join(channels)}, fused by rank. Optional filters: kind (event, note or doc), "
            f"a path prefix, and since_seq/until_seq, which filter events and notes by their event seq and "
            f"repository files by the seq at which their content was indexed. Returns up to {self.top_k} hits, "
            f"best first."
        )

    def _tool_search(self, tools: Any, args: dict[str, Any]) -> str:
        kind = args["kind"]
        if kind is not None and kind not in KINDS:
            raise ToolError(f"memory_search: kind must be one of {', '.join(KINDS)} or null")
        query = args["query"].strip()
        if not query:
            raise ToolError("memory_search: query must not be empty")
        flt = Filters(kinds=(kind,) if kind else None, since_seq=args["since_seq"], until_seq=args["until_seq"],
                      path_prefix=args["path"])
        hits = self.retriever.search([query], k=self.top_k, filters=flt, tools=tools)
        if not hits:
            return "no matching memory"
        chars = self.cfg["search_snippet_chars"]
        return f"{len(hits)} hit(s)\n\n" + "\n\n".join(
            f"{n}. {self._render_hit(h, chars)}" for n, h in enumerate(hits, start=1)
        )

    def _tool_get_event(self, tools: Any, args: dict[str, Any]) -> str:
        eid = args["event_id"].strip()
        pos = self._event_pos.get(eid)
        if pos is None:
            lowered = {k.lower(): v for k, v in self._event_pos.items()}
            pos = lowered.get(eid.lower())
        if pos is None:
            span = f"{self.events[0]['event_id']} .. {self.events[-1]['event_id']}" if self.events else "none"
            raise ToolError(f"memory_get_event: no event {eid!r} in memory (events received: {span})")
        return self._render_event(self.events[pos], self.cfg["event_chars"])

    # ------------------------------------------------------------ after event
    def _apply_writes(self, outcome: EventOutcome, seq: int) -> None:
        if self.mode == "none":
            return
        for path, content in outcome.workspace_writes.items():
            if content is None:
                self._drop_path(path)
            else:
                self._index_text(path, content, seq)

    def _update_summary(self, event: AgentEvent, outcome: EventOutcome, tools: Any) -> None:
        rem = remaining(tools)
        if rem["model_calls"] < 1:
            return
        previous = self.summary.get("text", "")
        acts = self._compact_actions(outcome)
        parts = [f"<<previous summary>>\n{previous if previous.strip() else '(none yet)'}",
                 f"<<event seq={event.seq} id={event.event_id}>>\n"
                 + render_event_header(dataclasses.replace(event, body=truncate_text(event.body, 3000))),
                 "<<your conclusions for this event>>\n" + (outcome.memory or "(no notes)")
                 + ("\nActions: " + "; ".join(acts) if acts else "\nActions: none"),
                 SUMMARY_TASK.format(words=max(50, self.cfg["summary_chars"] // 7))]
        req = ModelRequest(
            system=SUMMARY_SYSTEM,
            messages=(ModelMessage("user", "\n\n".join(parts)),),
            max_output_tokens=max(64, self.cfg["summary_chars"] // 3),
            purpose="summary",
            retrieval_chars=len(previous),
        )
        if estimate_request_tokens(req) * TOKEN_SAFETY > rem["model_input_tokens"]:
            return
        if rem["model_output_tokens"] < 64:
            return
        try:
            resp = tools.model_complete(req)
        except ToolError:
            return
        text = response_text(resp).strip()
        if text:
            self.summary = {"seq": event.seq, "text": text[: self.cfg["summary_chars"]]}

    def after_event(self, event: AgentEvent, outcome: EventOutcome, tools: Any) -> None:
        self._apply_writes(outcome, event.seq)
        self._store_note(event.seq, event.event_id, event.timestamp, event.subject, outcome)
        if self._summary_on():
            self._update_summary(event, outcome, tools)

    def after_start(self, outcome: EventOutcome, tools: Any) -> None:
        self._apply_writes(outcome, 0)
        self._store_note(0, None, "", "initial repository", outcome)
        if self._summary_on() and outcome.memory.strip():
            self.summary = {"seq": 0, "text": outcome.memory[: self.cfg["summary_chars"]]}

    # ------------------------------------------------------------ checkpoint
    def checkpoint(self) -> None:
        if self.root is None:
            return
        _atomic_write(self._p("docs_index.json"), _dumps({"paths": self.docs_index}))
        _atomic_write(self._p("summary.json"), _dumps(self.summary))
        dense = self.dense.status() if self.dense is not None else {"failures": 0, "reason": ""}
        _atomic_write(
            self._p("checkpoint.json"),
            _dumps({
                "version": MEMORY_VERSION,
                "last_seq": self._current_seq() if self.events else -1,
                "events": len(self.events),
                "notes": len(self.notes),
                "seed_ingested": self.seed_ingested,
                "pending_paths": list(self.pending_paths),
                "intents": self.intent_count,
                "unreadable": sorted(self.unreadable),
                "dense": {"failures": dense["failures"], "reason": dense["reason"]},
                "dense_note_emitted": self.dense_note_emitted,
            }),
        )
        self.last_checkpoint_seq = self._current_seq() if self.events else -1
