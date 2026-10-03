### Run `smoke_v1__baseline-k8+baseline-k32+baseline-k64+baseline-full__aba07cb294`

> **Fake model (machinery check).** The deterministic `fake-v1` test double chose these tool calls and reopens by hashing. The scores below say nothing about baseline quality.

> **Lexical embeddings.** Dense retrieval used `hash-ngram-v1` feature hashing, not a neural semantic embedding; such runs do not meet EXPERIMENT.md §7's semantic-search minimum (protocol deviation D1).

- scenario: `smoke_v1`, status: `completed`, protocol: `v0.2`
- model: `{"effort": null, "embedding_dims": 384, "embedding_model": "hash-ngram-v1", "embedding_provider": "hash", "max_output_tokens": null, "name": "fake-v1", "prompt_caching": false, "provider": "fake", "temperature": null}`
- model runtime: `{}`
- fingerprint: `da8378699d053a471335c5b8b39a1da984308c620b8c847b3036fc610cfbbd02`

| agent | recall | precision | FIR | fidelity | remediation | steps |
|---|---|---|---|---|---|---|
| baseline-full | 0.333 (1/3) | 0.167 (1/6) | 0.429 (3/7) | 0 | 0 (0/3) | ok: 10 |
| baseline-k32 | 0.333 (1/3) | 0.167 (1/6) | 0.429 (3/7) | 0 | 0 (0/3) | ok: 10 |
| baseline-k64 | 0.667 (2/3) | 0.286 (2/7) | 0.429 (3/7) | 0 | 0 (0/3) | ok: 10 |
| baseline-k8 | 0.333 (1/3) | 0.2 (1/5) | 0.286 (2/7) | 0 | 0 (0/3) | ok: 10 |

| agent | model calls | input tokens | output tokens | retrieval tokens | embedding tokens | cost (USD) | cache-neutral cost (USD) | tool calls | commands | tool-result chars | wall clock (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline-full | 49 | 252247 | 1551 | 173458 | 35640 | 0 | 0 | 72 | 2 | 166016 | 2.6 |
| baseline-k32 | 59 | 429831 | 1772 | 347894 | 36928 | 0 | 0 | 72 | 2 | 166016 | 3.2 |
| baseline-k64 | 59 | 736854 | 1823 | 654943 | 36953 | 0 | 0 | 72 | 2 | 166016 | 3.2 |
| baseline-k8 | 59 | 174527 | 1706 | 92446 | 36903 | 0 | 0 | 72 | 2 | 166016 | 3.1 |

| agent | served model(s) | tokens complete | cost basis | auxiliary tokens (in/out) | provider errors |
|---|---|---|---|---|---|
| baseline-full | fake-v1: 49 | True | price_table: 49 | 0/0 | 0 |
| baseline-k32 | fake-v1: 59 | True | price_table: 59 | 0/0 | 0 |
| baseline-k64 | fake-v1: 59 | True | price_table: 59 | 0/0 | 0 |
| baseline-k8 | fake-v1: 59 | True | price_table: 59 | 0/0 | 0 |

| agent | tool calls by tool |
|---|---|
| baseline-full | diff: 6, embed: 24, history: 10, list_files: 1, model_complete: 49, read_file: 53, run_command: 2 |
| baseline-k32 | diff: 6, embed: 24, history: 10, list_files: 1, model_complete: 59, read_file: 53, run_command: 2 |
| baseline-k64 | diff: 6, embed: 24, history: 10, list_files: 1, model_complete: 59, read_file: 53, run_command: 2 |
| baseline-k8 | diff: 6, embed: 24, history: 10, list_files: 1, model_complete: 59, read_file: 53, run_command: 2 |

| agent | reopens (seq, target, class) |
|---|---|
| baseline-full | 1 ADR-0003 false; 4 TCK-0102 false; 4 TCK-0107 false; 7 ADR-0001 false; 8 TCK-0107 true_positive; 10 TCK-0102 false |
| baseline-k32 | 1 ADR-0003 false; 4 TCK-0102 false; 4 TCK-0107 false; 7 ADR-0001 false; 8 TCK-0107 true_positive; 10 TCK-0102 false |
| baseline-k64 | 1 ADR-0003 false; 4 TCK-0102 false; 4 TCK-0107 false; 7 ADR-0001 false; 8 ADR-0002 true_positive; 8 TCK-0107 true_positive; 10 TCK-0102 false |
| baseline-k8 | 4 TCK-0102 false; 4 TCK-0107 false; 7 ADR-0001 false; 8 TCK-0107 true_positive; 10 TCK-0102 false |

