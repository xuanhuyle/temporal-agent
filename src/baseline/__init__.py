"""Strong conventional (checkpoint + RAG) baseline contestant (contestant code).

- ``text``: code-aware tokenizer and entity extraction;
- ``bm25``: incremental BM25 index;
- ``vectors``: dense index over harness-metered embeddings, cached by text hash;
- ``chunking``: markdown / Python / size-based chunkers;
- ``retrieval``: hybrid retrieval with reciprocal rank fusion, diversity cap and filters;
- ``memory``: ``BaselineMemory``, the ``MemorySystem`` of the baseline;
- ``presets``: configurations ``k8``, ``k32``, ``k64``, ``full``;
- ``agent``: ``BaselineAgent``.

It has no temporal-causal machinery (no fact graph, causal edges or
supersession tracking) and receives no evaluator labels: relevance is
rediscovered by ordinary retrieval and the model's reasoning.
"""
