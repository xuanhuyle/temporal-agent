# MemoryArena: adversarial verification notes

Verifier pass, 2026-10-03. Sources: the official repo clone at `scratchpad/lit/repos/ZexueHe_MemoryArena`
(commit 6cd9de1, "Initial commit"; working tree clean), re-read independently. I re-checked every cited line
used for a rating.

I tried WebSearch once ("MemoryArena benchmarking agent memory interdependent multi-session agentic tasks
2602.16313", allowed_domains arxiv.org). It returned "Web search was not performed: this session has used its web
search budget (200 of 200 WebSearch calls)". **So no paper-side claim could be independently re-verified.** All
verification below is code-level.

## Rating changes

**None.** All 20 ratings survive. Each `partial` is weak and comes from offline harness logs or resume, not from
any agent-facing temporal feature. Each `no` was re-checked by grep and reading. A repo-wide grep (excluding
vendored MemoRAG, WebShop site and searcher code) for
`rollback|snapshot|checkpoint|fork|branch|as_of|valid_at|forecast|predict|simulat|imagin` finds only:
- zep.py:180-181 (valid_at/invalid_at display);
- "predicted_answer" in the search domain (the answer to a question, not a forecast);
- huggingface `snapshot_download`.

## Verified claims (verbatim evidence)

- **Memory API.** memory/server.py:106-119: `memory_system.add_chunk(req.chunk)` and
  `memory_system.wrap_user_prompt(req.question)`. No time, as-of or diff parameter.
- **long_context truncation.** long_context.py:20,29-30:
  `stamped = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {chunk}"` ...
  `if len(tokens) > self.max_tokens: self.context = self.tokenizer.decode(tokens[-self.max_tokens :])`
- **Travel revision prompt is dead code.** prompts.py:12 reads "You may adjust previous travelers' plans if needed
  to accommodate new constraints...". A grep shows that `SYSTEM_PROMPT` (bare) is defined only at prompts.py:8,
  and the only import from it is agent/travel_planner.py:11-12 (`AGENT_SYSTEM_PROMPT`). The extra top-level
  file `example_travel_planner.py` (not cited by the analyst) does not use it either; a grep for "adjust" matches
  only prompts.py.
- **parse_all_plans overwrites by name.** run_travel.py:49: `name_plan_pairs[name] = plan`. Confirmed.
- **Future steps withheld.** task_files.py:214-219 (docstring): "- Ignores future steps". Confirmed.
- **Shopping memory read once per step.** run_shopping.py:919-921: `if memory is not None and not memory_injected:`
  `prompt = memory.wrap_user_prompt(prompt_source)`. Confirmed.
- **Resume.** run_shopping.py:1080-1092 calls `build_resume_state` and then
  `backfill_memory_from_artifacts(memory, step_artifacts, start_step - 1)`, which does `memory.add(entry)` for
  each stored entry (lines 823-856). This is replay of memory writes, not restoration of a snapshot.
- **Artifact handling.**
  - run_shopping.py:866-873 writes `eval_{stem}_step_{n}_{timestamp}.json`, so each attempt gets a new
    timestamped file and earlier attempts are not overwritten.
  - run_shopping.py:1124-1127 then re-opens the same path with "w" and rewrites it with the step_summary.
  - The latest artifact is selected by `st_mtime` (run_shopping.py:477-478).
- **Run tag.** run_shopping.py:351-355: `f"{safe_model}-{mode}-{memory_tag}"`, so there is no branch identity.
- **Feedback flags off in shipped configs.**
  - web_shopping_configs/bm25.json: `"enable_feedback": false`, `"include_history": false`,
    `"temperature": 1.0`.
  - travel configs: `"judgement_mode": "none"`.
  - run_math.py:182-198: `reward=None` unless `cfg["memory"]["judge_result_in_memory"]`.
- **Search confidence and calibration.**
  - search_agent/prompts.py:9: "Confidence: {{your confidence score between 0% and 100% for your answer}}".
  - run_search.py:189: `calibration_error = abs(confidence / 100.0 - acc_val)`.
- **Zep validity display.** zep.py:180-186: `f"{fact} (Date range: {valid_at} - {invalid_at})"`. Zep is
  registered in MEMORY_FACTORIES (server.py:61). A grep finds no config referencing zep, amem or lightmem.
- **ReasoningBank.** It LLM-judges success or failure (reasoningbank.py:195-208) and extracts memory items,
  appending `{"timestamp","task_id","memory_items","status"}` to JSONL (lines 211-266). Confirmed.

## Corrections (no rating impact)

1. **"Memory instances live in server RAM (server.py:74) and vanish on restart" overgeneralizes.**
   - The registry `MEMORY_SYSTEMS` is RAM-only, but **ReasoningBank persists to disk and reloads at construction**.
     reasoningbank.py:94 sets `self.storage_path=os.path.join(self.storage_path , f"{self.user_id}_reasoning_bank.jsonl")`,
     and reasoningbank.py:101 does `self.memory_bank = self._load_jsonl(self.storage_path)`.
   - server.py:95-96 builds it with `ReasoningBankMemorySystem(user_id=req.user_id)`.
   - The user_id is deterministic: `f"shopping::{task_key}::{args.model_name}::{args.memory_system}"`
     (run_shopping.py:443-445) and `f"data_{data_idx}_{args.model_name}_{args.memory_system}"` (run_travel.py:194).
   - Consequences (inferred from the code; not executed):
     - (a) A second run of the same task, model and memory configuration starts with the previous run's lessons,
       which leaks across runs.
     - (b) On shopping resume, the reloaded JSONL already holds lessons for the completed steps, and
       `backfill_memory_from_artifacts` re-adds them, so they are duplicated.
   - Mem0, MIRIX and Letta are built via `factory()` without a user_id (server.py:100), so each init gets a fresh
     uuid4 (mem0.py:16; mirix.py:16) or a newly created Letta agent (letta.py:9). Their earlier data is orphaned in
     the cloud rather than lost, and is not reused.
2. **"Memory backends are not append-only" overgeneralizes.**
   - `RAGMemorySystem` (bm25 / text-embedding-3-small) only appends: rag.py:39-47
     `self._chunks.append(piece)`, with no delete or update method.
   - ReasoningBank appends to JSONL, but stores LLM-derived lessons, not raw observations.
   - The non-append-only ones are long_context (truncation), MemoRAG (re-memorize) and the cloud consolidators.
   - This does not change capability 1. The RAG store is RAM-only, not designed as a historical record, and not
     queryable as of a time.
3. **Shopping artifact immutability is better than the analysis implies.** Each attempt writes a new timestamped
   file, so earlier attempts survive. Only the current attempt's file is rewritten once, to add step_summary. This
   strengthens `partial` for capability 1 slightly; it does not upgrade it.

## Capability-by-capability verdicts

| # | key | analyst | verified | note |
|---|---|---|---|---|
| 1 | immutable_historical_observations | partial | partial | Timestamped per-attempt logs. Agent-facing memory is not an immutable store. |
| 2 | historical_world_state | no | no | Fresh env per shopping step; static CSV DBs; no as-of. |
| 3 | historical_epistemic_state | partial | partial (weak) | Offline logs of memory-wrapped prompts only. No reconstruction API. |
| 4 | historical_policy_objective_state | partial | partial (weak) | Static config and per-step instruction logged. No change tracking. |
| 5 | execution_checkpoints | partial | partial (weak) | Step-level resume by replaying writes. ReasoningBank duplication further weakens fidelity. |
| 6 | replay | partial | partial (weak) | Resume only; nondeterministic (temp 1.0, LLM judges). |
| 7-9 | fork / counterfactual / provenance | no | no | No branch concept (run tag, mtime selection). |
| 10 | explicit_current_belief_state | no | no | Text passthrough; backend structure is not exposed. |
| 11 | uncertainty_representation | partial | partial | Search-domain answer confidence only. |
| 12-17 | prospective capabilities | no | no | Nothing found. |
| 18 | predicted_vs_realized | no | no | Calibration is answer confidence vs correctness, not a forecast vs a realized future. |
| 19 | cross_time_state_querying | no | no | Zep shows validity dates; there is no as-of query. |
| 20 | unified_temporal_abstraction | no | no | None. |

## Not verifiable this pass

Paper tables, task counts, limitations section, venue and dataset contents. The causes are WebSearch budget
exhaustion and arXiv/HF being blocked. These remain as listed in the analyst's could_not_verify.
