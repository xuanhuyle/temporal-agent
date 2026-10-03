"""Configurations of the conventional baseline (contestant code).

``{"preset": "k32"}`` expands to the shared defaults plus the preset; any
explicit key overrides both; an unknown key raises ``ValueError``. The
effective configuration (every key) is what ``describe()`` reports, so it is
part of the run's metadata and fingerprint.

Presets (milestone-2 design section 9):

- ``k8`` / ``k32`` / ``k64``: hybrid RAG with that top-k for the context pack
  and for ``memory_search``;
- ``full``: the long-context condition. Every stored event and note is in
  context; workspace documents are not retrieved into context but remain
  searchable through the memory tools. Query expansion is off because
  nothing is retrieved into context in this mode.
"""

from __future__ import annotations

from typing import Any

from contestant_runtime.agent import RUNTIME_DEFAULTS
from contestant_runtime.protocol import GUIDANCE_VARIANTS

__all__ = ["MEMORY_DEFAULTS", "DEFAULTS", "PRESETS", "DEFAULT_PRESET", "resolve_config"]

MEMORY_DEFAULTS: dict[str, Any] = {
    "mode": "rag",                    # rag | full | none
    "top_k": 32,                      # hits in the context pack and per memory_search
    "retrieval": "hybrid",            # hybrid (bm25 + dense + entity) | lexical (bm25 + entity) | dense (dense + entity)
    "query_expansion": True,          # one model call per event generating extra search queries
    "max_expansion_queries": 8,
    "summary": "rolling",             # rolling | none
    "summary_chars": 4000,
    "recent_events": 5,               # one-line headers of the most recent events, always in context
    "chunk_chars": 1500,
    "chunk_overlap": 200,
    "max_per_source": 4,              # diversity cap per file / event / note
    "rrf_k": 60,
    "hit_chars": 2000,                # display cap of one retrieved event or note in context
    "search_snippet_chars": 700,      # display cap of one memory_search hit
    "event_chars": 20000,             # display cap of one event in memory_get_event and full mode
    "full_context_chars": 300_000,    # cap of the event history in full mode (oldest bodies shortened first)
    "embed_chars": 2000,
    "embed_batch": 64,
    "max_file_chars": 200_000,
    "ingest_reserve_tool_calls": 40,  # tool calls left for the start turn after seed ingestion (at most half)
    "event_reserve_tool_calls": 40,   # tool calls left for the loop after re-indexing at an event (at most half)
    "lazy_index_per_event": 20,       # not-yet-indexed seed files read per event
}

DEFAULTS: dict[str, Any] = {**RUNTIME_DEFAULTS, **MEMORY_DEFAULTS}

PRESETS: dict[str, dict[str, Any]] = {
    "k8": {"top_k": 8},
    "k32": {"top_k": 32},
    "k64": {"top_k": 64},
    "full": {"mode": "full", "query_expansion": False},
}
DEFAULT_PRESET = "k32"

_CHOICES = {"mode": ("rag", "full", "none"), "retrieval": ("hybrid", "lexical", "dense"), "summary": ("rolling", "none"),
            "runtime_guidance": GUIDANCE_VARIANTS}
_BOOLS = ("query_expansion", "start_turn")
_NON_NEGATIVE = ("recent_events", "chunk_overlap", "max_protocol_retries", "ingest_reserve_tool_calls",
                 "event_reserve_tool_calls", "lazy_index_per_event", "max_expansion_queries")


def _check(cfg: dict[str, Any]) -> None:
    for key, choices in _CHOICES.items():
        if cfg[key] not in choices:
            raise ValueError(f"{key} must be one of {', '.join(choices)}, got {cfg[key]!r}")
    for key in _BOOLS:
        if not isinstance(cfg[key], bool):
            raise ValueError(f"{key} must be a boolean")
    for key, value in cfg.items():
        if key in _CHOICES or key in _BOOLS or key == "preset" or key == "max_output_tokens":
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{key} must be an integer")
        if value < (0 if key in _NON_NEGATIVE else 1):
            raise ValueError(f"{key} must be {'non-negative' if key in _NON_NEGATIVE else 'positive'}")
    if cfg["chunk_overlap"] >= cfg["chunk_chars"]:
        raise ValueError("chunk_overlap must be smaller than chunk_chars")


def resolve_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Effective configuration: defaults, then the preset, then explicit keys."""
    raw = dict(raw or {})
    preset = raw.pop("preset", DEFAULT_PRESET)
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; available: {', '.join(sorted(PRESETS))}")
    unknown = sorted(k for k in raw if k not in DEFAULTS)
    if unknown:
        raise ValueError(f"unknown baseline config key(s): {', '.join(unknown)}")
    cfg = dict(DEFAULTS)
    cfg.update(PRESETS[preset])
    cfg.update(raw)
    cfg["preset"] = preset
    _check(cfg)
    return cfg
