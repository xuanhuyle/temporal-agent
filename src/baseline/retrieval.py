"""Hybrid retrieval over the baseline's memory (contestant code).

Channels, each producing a ranked list of documents:

- ``bm25``: one list per query, over code-aware tokens (``baseline.text``);
- ``dense``: one list per query, cosine similarity over ``tools.embed``
  vectors (when enabled and available);
- ``entity``: documents sharing entities (record ids, file paths, versions,
  identifiers) with the queries or with explicit hints such as an event's
  changed paths, weighted by entity rarity.

Lists are fused with reciprocal rank fusion (``sum 1 / (rrf_k + rank)``,
``rrf_k = 60``), then a per-source diversity cap keeps at most
``max_per_source`` documents from one source (one file, one event, one
note). Filters (kind, sequence range, path prefix, exclusions) apply before
ranking. Every step breaks ties by document id, so results are a pure
function of the indexed documents and the query.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from baseline.bm25 import BM25Index
from baseline.text import extract_entities, tokenize
from baseline.vectors import DenseIndex

__all__ = ["Doc", "Filters", "Hit", "Retriever", "rrf_fuse", "diversify", "KINDS"]

KINDS = ("event", "doc", "note")


@dataclass(frozen=True)
class Doc:
    """One retrievable unit: an event, a chunk of a workspace file, or one of the agent's notes."""

    doc_id: str
    kind: str
    source: str
    text: str
    label: str = ""
    seq: int | None = None
    path: str | None = None
    extra_entities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown doc kind {self.kind!r}")

    def entities(self) -> list[str]:
        return sorted(set(extract_entities(f"{self.label}\n{self.text}")) | set(self.extra_entities))


def _under(path: str, prefix: str) -> bool:
    prefix = "/".join(p for p in prefix.split("/") if p not in ("", "."))
    if not prefix:
        return True
    return path == prefix or path.startswith(prefix + "/")


@dataclass(frozen=True)
class Filters:
    kinds: tuple[str, ...] | None = None
    since_seq: int | None = None
    until_seq: int | None = None
    path_prefix: str | None = None
    exclude: frozenset[str] = field(default_factory=frozenset)

    def allows(self, doc: Doc) -> bool:
        if doc.doc_id in self.exclude:
            return False
        if self.kinds is not None and doc.kind not in self.kinds:
            return False
        if self.since_seq is not None and (doc.seq is None or doc.seq < self.since_seq):
            return False
        if self.until_seq is not None and (doc.seq is None or doc.seq > self.until_seq):
            return False
        if self.path_prefix is not None and (doc.path is None or not _under(doc.path, self.path_prefix)):
            return False
        return True


@dataclass(frozen=True)
class Hit:
    doc: Doc
    score: float
    channels: tuple[str, ...]


def rrf_fuse(rankings: Sequence[Sequence[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal rank fusion of ranked id lists; best first, ties by id."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(dict.fromkeys(ranking), start=1):  # distinct ids, first occurrence ranks
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def diversify(
    ranked: Sequence[tuple[str, float]], source_of: Callable[[str], str], max_per_source: int, k: int
) -> list[tuple[str, float]]:
    """The first ``k`` items of ``ranked`` with at most ``max_per_source`` per source."""
    out: list[tuple[str, float]] = []
    per: dict[str, int] = {}
    for doc_id, score in ranked:
        if len(out) >= k:
            break
        src = source_of(doc_id)
        if per.get(src, 0) >= max_per_source:
            continue
        per[src] = per.get(src, 0) + 1
        out.append((doc_id, score))
    return out


class Retriever:
    def __init__(
        self,
        *,
        dense: DenseIndex | None = None,
        rrf_k: int = 60,
        max_per_source: int = 4,
        use_bm25: bool = True,
        use_entities: bool = True,
    ) -> None:
        self.dense = dense
        self.rrf_k = rrf_k
        self.max_per_source = max_per_source
        self.use_bm25 = use_bm25
        self.use_entities = use_entities
        self.bm25 = BM25Index()
        self._docs: dict[str, Doc] = {}
        self._doc_entities: dict[str, tuple[str, ...]] = {}
        self._entity_postings: dict[str, set[str]] = {}

    # ---------------------------------------------------------------- content
    def __len__(self) -> int:
        return len(self._docs)

    def __contains__(self, doc_id: object) -> bool:
        return doc_id in self._docs

    def get(self, doc_id: str) -> Doc | None:
        return self._docs.get(doc_id)

    def doc_ids(self) -> list[str]:
        return sorted(self._docs)

    def add(self, doc: Doc) -> None:
        if doc.doc_id in self._docs:
            self.remove(doc.doc_id)
        self._docs[doc.doc_id] = doc
        self.bm25.add(doc.doc_id, tokenize(f"{doc.label}\n{doc.text}"))
        ents = tuple(doc.entities())
        self._doc_entities[doc.doc_id] = ents
        for e in ents:
            self._entity_postings.setdefault(e, set()).add(doc.doc_id)
        if self.dense is not None:
            self.dense.set_text(doc.doc_id, f"{doc.label}\n{doc.text}" if doc.label else doc.text)

    def remove(self, doc_id: str) -> None:
        if self._docs.pop(doc_id, None) is None:
            return
        self.bm25.remove(doc_id)
        for e in self._doc_entities.pop(doc_id, ()):
            posting = self._entity_postings.get(e)
            if posting is not None:
                posting.discard(doc_id)
                if not posting:
                    del self._entity_postings[e]
        if self.dense is not None:
            self.dense.remove(doc_id)

    # ---------------------------------------------------------------- channels
    def entity_ranking(self, entities: Iterable[str], allowed: Callable[[str], bool], depth: int) -> list[str]:
        scores: dict[str, float] = {}
        for e in sorted(set(entities)):
            posting = self._entity_postings.get(e)
            if not posting:
                continue
            weight = 1.0 / (1.0 + math.log(len(posting)))
            for doc_id in sorted(posting):
                if allowed(doc_id):
                    scores[doc_id] = scores.get(doc_id, 0.0) + weight
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return [d for d, _ in ranked[:depth]]

    def search(
        self,
        queries: Sequence[str],
        *,
        k: int,
        filters: Filters | None = None,
        entities: Iterable[str] = (),
        tools: Any = None,
    ) -> list[Hit]:
        """Fused top ``k`` hits for ``queries`` (plus entity hints), after filters and the diversity cap."""
        if k < 1 or not self._docs:
            return []
        flt = filters or Filters()
        docs = self._docs

        def allowed(doc_id: str) -> bool:
            d = docs.get(doc_id)
            return d is not None and flt.allows(d)

        depth = max(50, 3 * k)
        qs = [q for q in dict.fromkeys(q.strip() for q in queries) if q]
        rankings: list[list[str]] = []
        channel_of: dict[str, set[str]] = {}

        def take(name: str, ids: list[str]) -> None:
            if ids:
                rankings.append(ids)
                for d in ids:
                    channel_of.setdefault(d, set()).add(name)

        if self.use_bm25:
            for q in qs:
                take("bm25", [d for d, _ in self.bm25.search(tokenize(q), depth, allowed)])
        if self.dense is not None and tools is not None and qs and len(self.dense):
            for vec in self.dense.embed_queries(tools, qs):
                if vec is not None:
                    take("dense", [d for d, _ in self.dense.search(vec, depth, allowed)])
        if self.use_entities:
            ents = set(entities)
            for q in qs:
                ents.update(extract_entities(q))
            take("entity", self.entity_ranking(ents, allowed, depth))

        fused = rrf_fuse(rankings, self.rrf_k)
        picked = diversify(fused, lambda d: docs[d].source, self.max_per_source, k)
        return [Hit(docs[d], s, tuple(sorted(channel_of.get(d, ())))) for d, s in picked]
