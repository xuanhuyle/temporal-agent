"""Incremental Okapi BM25 index (contestant code).

``k1 = 1.2``, ``b = 0.75``, ``idf = ln(1 + (N - df + 0.5) / (df + 0.5))``.
Documents can be added and removed at any time. Scores depend only on the
set of indexed documents, never on insertion order: per-document sums run
over query terms in sorted order, and ties are broken by document id, so a
rebuilt index ranks exactly like the original.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Callable, Iterable

__all__ = ["BM25Index"]


class BM25Index:
    def __init__(self, k1: float = 1.2, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._postings: dict[str, dict[str, int]] = {}
        self._doc_terms: dict[str, Counter[str]] = {}
        self._doc_len: dict[str, int] = {}
        self._total_len = 0

    def __len__(self) -> int:
        return len(self._doc_len)

    def __contains__(self, doc_id: object) -> bool:
        return doc_id in self._doc_len

    def add(self, doc_id: str, tokens: Iterable[str]) -> None:
        """Index (or re-index) ``doc_id``."""
        if doc_id in self._doc_len:
            self.remove(doc_id)
        tf = Counter(tokens)
        self._doc_terms[doc_id] = tf
        length = sum(tf.values())
        self._doc_len[doc_id] = length
        self._total_len += length
        for term, n in tf.items():
            self._postings.setdefault(term, {})[doc_id] = n

    def remove(self, doc_id: str) -> None:
        tf = self._doc_terms.pop(doc_id, None)
        if tf is None:
            return
        self._total_len -= self._doc_len.pop(doc_id)
        for term in tf:
            posting = self._postings.get(term)
            if posting is None:
                continue
            posting.pop(doc_id, None)
            if not posting:
                del self._postings[term]

    def idf(self, term: str) -> float:
        n = len(self._doc_len)
        df = len(self._postings.get(term, ()))
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def search(
        self,
        query_tokens: Iterable[str],
        k: int,
        allowed: Callable[[str], bool] | None = None,
    ) -> list[tuple[str, float]]:
        """Top ``k`` ``(doc_id, score)`` with a positive score, best first, ties by doc id."""
        if k < 1 or not self._doc_len:
            return []
        qtf = Counter(t for t in query_tokens if t in self._postings)
        if not qtf:
            return []
        avgdl = self._total_len / len(self._doc_len) if self._total_len else 1.0
        scores: dict[str, float] = {}
        k1, b = self.k1, self.b
        for term in sorted(qtf):
            idf = self.idf(term)
            weight = idf * qtf[term]
            for doc_id, f in self._postings[term].items():
                if allowed is not None and not allowed(doc_id):
                    continue
                dl = self._doc_len[doc_id]
                s = weight * (f * (k1 + 1.0)) / (f + k1 * (1.0 - b + b * dl / avgdl))
                scores[doc_id] = scores.get(doc_id, 0.0) + s
        ranked = sorted(((d, s) for d, s in scores.items() if s > 0.0), key=lambda item: (-item[1], item[0]))
        return ranked[:k]
