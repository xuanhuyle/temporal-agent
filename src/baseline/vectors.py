"""Dense vector index fed by the harness-metered ``tools.embed`` (contestant code).

- Vectors are cached by ``sha256(text)`` in an append-only JSONL file in the
  agent's state directory, so restarts and re-indexing never re-embed a text
  that was embedded before.
- Vector components are rounded to 6 decimals before they are cached and
  normalized, so a vector read back from the cache is bit-identical to a
  freshly received one, and retrieval after a restart ranks identically.
- Embedding is budget-aware: a batch is sent only if its estimated tokens
  (``ceil(utf8_bytes / 4)`` per text, times a safety factor) fit the step's
  remaining embedding budget; what does not fit stays pending for a later
  step.
- If embedding fails (``ToolError``, e.g. no embedding model in this run),
  no more embedding calls are made in the current step, and after
  ``max_failures`` failed steps the index is marked unavailable for the rest
  of the run. Retrieval then falls back to the lexical channels; the status
  and reason are reported by :meth:`DenseIndex.status`.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from harness.errors import ToolError
from harness.llm import EmbeddingResponse

__all__ = ["EmbeddingCache", "DenseIndex", "text_sha256"]

DECIMALS = 6


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def _tokens(text: str) -> int:
    return -(-len(text.encode("utf-8", "surrogatepass")) // 4)


def _round(vector: Iterable[float]) -> tuple[float, ...]:
    return tuple(round(float(x), DECIMALS) for x in vector)


def _normalize(vector: tuple[float, ...]) -> tuple[float, ...] | None:
    norm = math.sqrt(sum(x * x for x in vector))
    if not math.isfinite(norm) or norm == 0.0:
        return None
    return tuple(x / norm for x in vector)


class EmbeddingCache:
    """``sha256(text) -> rounded vector``, persisted as append-only JSONL (``None`` path: memory only)."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._vectors: dict[str, tuple[float, ...]] = {}
        self.model: str | None = None
        if path is not None and path.is_file():
            self._load(path)

    def _load(self, path: Path) -> None:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                    sha, vec = rec["sha256"], rec["vector"]
                    if not isinstance(sha, str) or not isinstance(vec, list) or not vec:
                        continue
                    vector = _round(vec)
                except (ValueError, KeyError, TypeError):
                    continue  # a torn last line after a crash
                if not all(math.isfinite(x) for x in vector):
                    continue
                self._vectors.setdefault(sha, vector)
                if isinstance(rec.get("model"), str):
                    self.model = rec["model"]

    def __len__(self) -> int:
        return len(self._vectors)

    def get(self, sha: str) -> tuple[float, ...] | None:
        return self._vectors.get(sha)

    def put_many(self, items: Sequence[tuple[str, tuple[float, ...]]], model: str) -> None:
        new = [(sha, vec) for sha, vec in items if sha not in self._vectors]
        for sha, vec in new:
            self._vectors[sha] = vec
        self.model = model or self.model
        if self.path is None or not new:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = "".join(
            json.dumps({"sha256": sha, "model": model, "vector": list(vec)}, separators=(",", ":")) + "\n"
            for sha, vec in new
        )
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())


def _remaining_embedding_tokens(tools: Any) -> int:
    getter = getattr(tools, "budget_remaining", None)
    raw = getter() if callable(getter) else {}
    v = raw.get("embedding_tokens") if isinstance(raw, dict) else None
    return v if isinstance(v, int) and not isinstance(v, bool) else 10**12


class DenseIndex:
    def __init__(
        self,
        cache: EmbeddingCache,
        *,
        embed_chars: int = 2000,
        batch_size: int = 64,
        token_safety: float = 1.1,
        max_failures: int = 2,
    ) -> None:
        self.cache = cache
        self.embed_chars = embed_chars
        self.batch_size = batch_size
        self.token_safety = token_safety
        self.max_failures = max_failures
        self.failures = 0
        self.reason = ""
        self.embedded_texts = 0  # texts sent to tools.embed by this instance (for tests and accounting)
        self._failed_this_step = False
        self._vectors: dict[str, tuple[float, ...]] = {}
        self._pending: dict[str, str] = {}

    # ------------------------------------------------------------------ state
    @property
    def available(self) -> bool:
        return self.failures < self.max_failures

    def status(self) -> dict[str, Any]:
        return {
            "status": "ok" if self.available and self.failures == 0 else ("degraded" if self.available else "unavailable"),
            "failures": self.failures,
            "reason": self.reason,
            "vectors": len(self._vectors),
            "pending": len(self._pending),
        }

    def restore_status(self, failures: int, reason: str) -> None:
        self.failures = max(0, int(failures))
        self.reason = str(reason)

    def begin_step(self) -> None:
        self._failed_this_step = False

    def __len__(self) -> int:
        return len(self._vectors)

    def has(self, doc_id: str) -> bool:
        return doc_id in self._vectors

    def _clip(self, text: str) -> str:
        return text[: self.embed_chars]

    def set_text(self, doc_id: str, text: str) -> None:
        """Declare the text of ``doc_id``; its vector is attached from the cache or embedded later."""
        clipped = self._clip(text)
        self._vectors.pop(doc_id, None)
        self._pending.pop(doc_id, None)
        vec = self.cache.get(text_sha256(clipped))
        normalized = _normalize(vec) if vec is not None else None
        if normalized is not None:
            self._vectors[doc_id] = normalized
        else:
            self._pending[doc_id] = clipped

    def remove(self, doc_id: str) -> None:
        self._vectors.pop(doc_id, None)
        self._pending.pop(doc_id, None)

    def pending(self) -> list[str]:
        return sorted(self._pending)

    # -------------------------------------------------------------- embedding
    def _embed(self, tools: Any, texts: list[str], purpose: str) -> list[tuple[float, ...]] | None:
        """Embed ``texts`` (all already uncached); ``None`` on failure or lack of budget."""
        if not texts or not self.available or self._failed_this_step:
            return None
        need = sum(_tokens(t) for t in texts)
        if need * self.token_safety > _remaining_embedding_tokens(tools):
            return None
        try:
            response = tools.embed(list(texts), purpose)
        except ToolError as exc:
            self._fail(str(exc))
            return None
        if isinstance(response, dict):
            try:
                response = EmbeddingResponse.from_dict(response)
            except (KeyError, TypeError, ValueError):
                self._fail("malformed embedding response")
                return None
        vectors = getattr(response, "vectors", None)
        if not isinstance(vectors, (list, tuple)) or len(vectors) != len(texts):
            self._fail("embedding response has the wrong number of vectors")
            return None
        rounded = [_round(v) for v in vectors]
        if any(not v or not all(math.isfinite(x) for x in v) for v in rounded):
            self._fail("embedding response has invalid vectors")
            return None
        self.embedded_texts += len(texts)
        self.cache.put_many([(text_sha256(t), v) for t, v in zip(texts, rounded)], str(getattr(response, "model", "")))
        return rounded

    def _fail(self, reason: str) -> None:
        self._failed_this_step = True
        self.failures += 1
        self.reason = reason[:300]

    def ensure(self, tools: Any, purpose: str = "index") -> int:
        """Embed pending texts in deterministic order within the budget; returns how many got vectors."""
        done = 0
        ids = self.pending()
        i = 0
        while i < len(ids):
            batch_ids: list[str] = []
            texts: list[str] = []
            seen: set[str] = set()
            while i < len(ids) and len(texts) < self.batch_size:
                doc_id = ids[i]
                i += 1
                text = self._pending[doc_id]
                cached = self.cache.get(text_sha256(text))
                if cached is not None:  # embedded meanwhile (e.g. same text in another doc)
                    self._attach(doc_id, cached)
                    done += 1
                    continue
                batch_ids.append(doc_id)
                if text not in seen:
                    seen.add(text)
                    texts.append(text)
            if not texts:
                continue
            vectors = self._embed(tools, texts, purpose)
            if vectors is None:
                break
            by_text = dict(zip(texts, vectors))
            for doc_id in batch_ids:
                self._attach(doc_id, by_text[self._pending[doc_id]])
                done += 1
        return done

    def _attach(self, doc_id: str, vector: tuple[float, ...]) -> None:
        self._pending.pop(doc_id, None)
        normalized = _normalize(vector)
        if normalized is not None:
            self._vectors[doc_id] = normalized

    def embed_queries(self, tools: Any, queries: Sequence[str]) -> list[tuple[float, ...] | None]:
        """Normalized query vectors (cached by text); ``None`` where unavailable."""
        clipped = [self._clip(q) for q in queries]
        missing = sorted({q for q in clipped if self.cache.get(text_sha256(q)) is None})
        if missing:
            self._embed(tools, missing, "query")
        out: list[tuple[float, ...] | None] = []
        for q in clipped:
            vec = self.cache.get(text_sha256(q))
            out.append(_normalize(vec) if vec is not None else None)
        return out

    # ----------------------------------------------------------------- search
    def search(
        self, query: tuple[float, ...], k: int, allowed: Callable[[str], bool] | None = None
    ) -> list[tuple[str, float]]:
        """Top ``k`` by cosine similarity (positive only), ties by doc id."""
        if k < 1:
            return []
        scored = []
        for doc_id, vec in self._vectors.items():
            if allowed is not None and not allowed(doc_id):
                continue
            if len(vec) != len(query):
                continue
            s = sum(a * b for a, b in zip(vec, query))
            if s > 0.0:
                scored.append((doc_id, s))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:k]
