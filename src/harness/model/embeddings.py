"""Deterministic hashed n-gram embeddings, model ``hash-ngram-v1`` (benchmark infrastructure).

This is a *lexical* channel, not a neural semantic embedding, and the gateway
reports it as such. Each text becomes a bag of features:

- lowercased word unigrams (``w:``) and bigrams (``b:``), where a word is a
  run of Unicode word characters;
- character 3-, 4- and 5-grams (``c:``) of the lowercased text with
  whitespace collapsed to single spaces and the ends padded with a space.

Each feature's weight is sublinear in its count (``1 + ln(tf)``). Features are
hashed with BLAKE2b (8-byte digest, fixed personalization) into
``settings.embedding_dims`` buckets (default 384); one digest bit gives a
sign, so collisions cancel instead of accumulating. The vector is
L2-normalized; a text with no features maps to the zero vector.

No randomness, no process hash seed and no platform-dependent iteration
order is involved, so vectors are identical on every machine and run.
Input tokens come from the harness estimator; cost is 0.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from harness.agent import ModelSettings
from harness.model.gateway import DEFAULT_EMBEDDING_DIMS, HASH_EMBEDDING_MODEL_ID, RawEmbedding
from harness.model.tokens import estimate_embedding_tokens

__all__ = ["HashEmbeddingBackend", "HASH_EMBEDDING_MODEL_ID", "embed_text", "features"]

_WORD = re.compile(r"\w+", re.UNICODE)
_SPACE = re.compile(r"\s+")
_PERSON = b"tab-hash-ngram1"  # BLAKE2b personalization (<= 16 bytes)
CHAR_NGRAM_SIZES = (3, 4, 5)


def features(text: str) -> Counter[str]:
    """Feature counts of one text (word 1-2-grams and char 3-5-grams)."""
    low = text.lower()
    counts: Counter[str] = Counter()
    words = _WORD.findall(low)
    counts.update("w:" + w for w in words)
    counts.update(f"b:{a} {b}" for a, b in zip(words, words[1:]))
    norm = _SPACE.sub(" ", low).strip()
    if norm:
        padded = f" {norm} "
        for n in CHAR_NGRAM_SIZES:
            counts.update("c:" + padded[i : i + n] for i in range(len(padded) - n + 1))
    return counts


def _bucket(feature: str, dims: int) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8", "surrogatepass"), digest_size=8, person=_PERSON).digest()
    value = int.from_bytes(digest, "big")
    return (value >> 1) % dims, (1.0 if value & 1 else -1.0)


def embed_text(text: str, dims: int = DEFAULT_EMBEDDING_DIMS) -> list[float]:
    """The ``hash-ngram-v1`` vector of one text."""
    vec = [0.0] * dims
    # Sorted so the floating-point summation order is fixed.
    for feature, tf in sorted(features(text).items()):
        index, sign = _bucket(feature, dims)
        vec[index] += sign * (1.0 + math.log(tf))
    norm = math.sqrt(math.fsum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


class HashEmbeddingBackend:
    """Embedding backend for ``embedding_provider = "hash"``."""

    name = "hash"
    model = HASH_EMBEDDING_MODEL_ID

    def embed(self, texts: list[str], settings: ModelSettings, *, timeout_s: float | None, lane: str) -> RawEmbedding:
        dims = settings.embedding_dims or DEFAULT_EMBEDDING_DIMS
        return RawEmbedding(
            vectors=[embed_text(t, dims) for t in texts],
            model=HASH_EMBEDDING_MODEL_ID,
            input_tokens=estimate_embedding_tokens(texts),
        )
