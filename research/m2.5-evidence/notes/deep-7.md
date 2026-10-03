# Deep-read 7: "Reasoning Provenance for Autonomous AI Agents: Structured Behavioral Analytics Beyond State Checkpoints and Execution Traces" (Agent Execution Record, AER), arXiv 2603.21692

## Bibliographic facts (verified)
- Canonical URL: https://arxiv.org/abs/2603.21692 (blocked here, not fetched directly).
- v1 announced 24 Mar 2026 (PDF header: "arXiv:2603.21692v1 [cs.AI] 23 Mar 2026"). 8 pages. Single author: Neelmani Vispute, Oracle Cloud Infrastructure.
- v2 announced Mon 13 Apr 2026 as "replace-cross". It adds a co-author (Aditya Kadam) and cross-lists to cs.DC and cs.SE. The v2 abstract is identical to v1.
  - Source: `ehijano/rss_fetch` arXiv RSS dump `rss_data/cs.SE/2026-04-13_cs.SE.xml`: `<guid ...>oai:arXiv.org:2603.21692v2</guid>`, `<dc:creator>Neelmani Vispute, Aditya Kadam</dc:creator>`.
  - Source: `Lyken17/arXiv-stats` `info/2026-April/13/paper_info.json` gives the same authors and categories.
- License (from RSS): CC BY-SA 4.0.
- **I read the v1 full text, not v2.** v2 body changes are unknown.

## Access and evidence tiers
- **[FT]** Full text of v1. It is a third-party PDF-to-markdown conversion (Jina-reader style header: "URL Source: https://arxiv.org/pdf/2603.21692v1 ... Number of Pages: 8").
  - Location: https://raw.githubusercontent.com/twenhui2-afk/daily-paper-reader/main/docs/202603/25/2603.21692v1-reasoning-provenance-for-autonomous-ai-agents-structured-behavioral-analytics-beyond-state-checkpoints-and-execution-traces.txt
  - Local copy: `scratchpad/lit/deep7_raw/dpr_main.txt` (4069 words; sha256 prefix 15436127556445a8).
  - The conversion ends at the "References" heading, so the reference list itself is missing. The memgrafter digest says "Reference count: 11".
- **[ABS]** Verbatim abstract. Also present in `scratchpad/lit/repos/pf/daily/24-Mar-2026/AI/README.md` and `scratchpad/lit/idrift/abs1.txt`.
- **[DIG]** An LLM digest (memgrafter/research-digests, model step-3.5-flash). Secondary only. Its Limitations section says: "The reference implementation/SDK location, installation instructions, and exact schema definitions are unspecified, blocking direct reproduction."
- **Code check.** I found no public SDK.
  - The v1 full text has no github, http or "pip install" string, and no "available at".
  - GitHub code search for the SDK's API names (`start_investigation log_plan log_step record_verdict`) hits only the two paper mirrors.
  - GitHub code search for the record files (`"plans.jsonl" "steps.jsonl" "verdict.json" envelope`) also hits only paper mirrors.
  - PyPI: `aer` is an unrelated EMR CLI (eganjs/aer). `aer-sdk`, `agent-execution-record` and `reasoning-provenance` all return 404.
  - A third party, Ala-ADN/gommage, builds an "AER ... inspired by Vispute (2026)" proxy with replay, a mock registry and a divergence tracker. It is not the authors' code.
- WebSearch budget was already exhausted (200/200) when this task started, so I made no web-search queries.

## What the work is (from [FT])
- **Contribution 1: two definitions.** "Definition 1 (Computational State)" is S_k = (M_k, C_k, T_k): messages, channel values and tool-call records, i.e. what LangGraph checkpoints. "Definition 2 (Reasoning Provenance)" is R_k = (I_k, O_k, N_k, P_k): intent, observation, inference and plan version.
- **Contribution 2: a non-identifiability proposition** with three sources: "Intent multiplicity", "Observation ambiguity" and "Inference volatility".
- **Contribution 3: the AER file layout.**
  - `envelope.json`: identity, trigger, delegation authority, and retrieval context snapshot.
  - `plans.jsonl`: versioned plans with `supersedes`, `revision_trigger` and `rationale`.
  - `steps.jsonl`: per-step `intent`, `tool_calls` (input and output), `observation`, `inference`, `plan_version` and tokens.
  - `verdict.json`: root cause, `confidence`, `evidence_chain`, `alternatives_rejected` with `rejected_by` step pointers, and `remediation`.
  - `metadata.json`.
- **Contribution 4: three replay modes.**
  - Narrate: read-only.
  - Mock: re-run the reasoning on recorded tool outputs with a new model or prompt, then diff per step and on the verdict.
  - Live: re-execute against live systems.
- **Contribution 5: reference implementation.** A local-first JSONL SDK, a Kafka/Avro scale-out design, and a "stylized" storage comparison.
- **Evaluation is a plan, not results.** "The paper's primary contribution is the AER abstraction and its formalization; empirical validation across diverse workloads is ongoing work."

## Verbatim snippets [FT]

Core claim, vs checkpoints and traces:
> "What current systems do not natively provide as a first-class, schema-level primitive is structured reasoning prove-nance —normalized, queryable records of why the agent chose each action, what it concluded from each observation, how each conclusion shaped its strategy, and which evidence supports its final verdict."

> "Proposition. Given only the persisted computa-tional state S1..K , reasoning provenance R1..K can-not in general be faithfully reconstructed as a normal-ized, schema-conforming, cross-run-comparable repre-sentation without contemporaneous capture at execu-tion time."

> "We do not claim that reasoning provenance is logically impossible to extract from computational state. Our argument concerns faithful reconstruction as a stable, queryable representation ."

> "(1) Intent multiplicity. ... In run A, the agent checks the listener because its plan is to system-atically check each infrastructure layer top-down. In run B, the agent checks the listener because it detected "TNS" in the error message. Both produce identical tool calls and state at step 2. The intent differs."

On LangGraph checkpoints:
> "A checkpoint for step 2 ... would contain the accumulated message history ... What the checkpoint does not contain as a structured field is why the agent chose to check the listener at this point (intent), that the agent concluded this directly explains the reported connectiv-ity failures (observation), or that this conclusion caused the agent to abandon its original plan and formulate a new one (inference + plan revision)."

Versioned plans, the closest overlap with "never overwrite, version it":
> {"plan_version":2, "supersedes":1, "revision_trigger":"step_002", "rationale":"Listener down on node 3. Deep-dive: instance status, logs, memory/reboot events.", ...}

> "The plan version chain captures adaptive reason-ing —the agent's strategic response to unexpected evi-dence. The revision_trigger pointer ( step_002 ) ex-plicitly links the re-plan to the observation that caused it."

Retrieval provenance, the closest analogue to an epistemic cutoff:
> "The retrieval context captures what actually entered the agent's context window (specific RAG chunk IDs, token counts) rather than what the agent could have queried—following a principle of re-trieval provenance over availability provenance ."

Authority and policy at the time of the run:
> "agent": {"agent_version":"rca-v2.4.1", "model":"codex-5.3", "prompt_version":"rca-prompt-v7.2"}, "authority": {"delegated_by":"oncall:sre-payments", "delegation_mechanism": "iam-policy:rca-agent-role-v3", ... "authority_chain": [...]}

> "The envelope is written once at investigation start."

Verdict, confidence and rejected alternatives:
> "confidence":0.95, ... "evidence_chain": ["step_002","step_003","step_004"], "alternatives_rejected":[ {"hypothesis":"SCAN DNS misconfiguration", "rejected_by":"step_001", "reason":"All 3VIPs resolving"}, ...], "remediation":["Start CRS on Node 3", "Investigate memory consumer", "Add OOM monitoring alert"]

Replay:
> "Narrate: Read-only step-by-step walkthrough. Zero cost, zero execution."

> "Mock: Re-runs reasoning with recorded tool outputs under a different model or prompt version. The agent receives exact same tool results but reasons with a new model. For each step, the report compares: did the new model reach the same observation? The same infer-ence? At the end: did it reach the same verdict? This is, to our knowledge, not natively provided by any existing system. LangGraph's time-travel resumes against live systems."

> "Live: Re-executes the original plan against live sys-tems. Different results (world has changed). Useful for verifying resolution."

> "step_002: "Proximate cause. Re-planning." new: "Listener down. Check CRS." >> Divergence: new model skips re-plan ... Summary: 3/4 matched. Verdict converged."

Not a checkpoint system (Table 1 row): "Fault tolerance / resumption", marked as not a design target for AER.

Retention: records are not kept forever by default.
> "Automatic lifecycle management: count-based eviction (default 50), time-based eviction (default 14 days), pin/promote workflow."

> "Core schema uses additive-only evolution (new fields, never removing old ones). ... Raw capture is configurable per-deployment with field-level redaction for promoted AERs."

Self-report limitation:
> "AER's reasoning fields are populated by the agent itself. They record what the agent reports about its reasoning, not a ground-truth ac-count of its internal computation."

Evaluation status:
> "This section describes our planned evaluation method-ology. Preliminary deployment informs the design; full empirical results are ongoing work."

> "The following analysis is based on a stylized 10-step investigation and should be treated as preliminary mo-tivation, not a validated empirical result."

Calibration (the predicted-vs-realized analogue):
> "(c) predictive validity of confidence (does higher AER confidence predict higher expert agree-ment?)"

Multi-agent:
> "Multi-agent investigations require a higher-order Inves-tigation Record composing multiple AERs ... We consider this important future work."

## Capability ratings (only what AER itself provides)

| # | capability | rating | evidence |
|---|---|---|---|
| 1 | immutable_historical_observations | partial | `steps.jsonl` keeps tool inputs and outputs plus the agent's observation per step. The envelope is "written once", and the schema is "additive-only". But by default records are evicted (50 records / 14 days), can be compacted or redacted, and come with no immutability or tamper-evidence guarantee. Scope is one investigation. |
| 2 | historical_world_state | no | There is no reconstruction of external world state as of t. Live replay notes "world has changed". Mock replay reuses recorded tool outputs only, i.e. the slice of the world the agent observed, not a queryable world model. |
| 3 | historical_epistemic_state | partial | Each step records the agent's self-reported observation, inference and plan_version in force. The envelope records "what actually entered the agent's context window", explicitly "retrieval provenance over availability provenance". There is no as-of belief reconstruction, no cutoff enforcement, and retrieval context is captured only at investigation start. |
| 4 | historical_policy_objective_state | partial (strong) | The envelope captures agent_version, model, prompt_version, IAM delegation mechanism, permissions scope and authority chain for each run. The plan chain has `supersedes`, `revision_trigger` and `rationale`. But the prompt is stored as an id only, the envelope is write-once (mid-run goal or instruction changes other than plan revisions are not modelled), and there is no lifetime lineage or diff of objectives or policies. |
| 5 | execution_checkpoints | no | Explicitly not a design target ("Fault tolerance / resumption"). The paper defers to the LangGraph checkpointer. |
| 6 | replay | yes | Three modes: Narrate, Mock (recorded tool outputs, new model or prompt, per-step and verdict diff) and Live. The CLI example is `aer replay DBINFRA-1458 --mode mock --model codex-6.0`. Replay runs over the whole investigation; resuming from step k is not described. The code is not public. |
| 7 | fork_from_historical_state | partial (weak) | Mock replay produces an alternative run against a preserved original, but only from the investigation start. No mid-trajectory fork is described, and the replay output is a comparison report, not a persisted branch record. |
| 8 | counterfactual_action_branches | partial | The counterfactual is over model or prompt version ("counterfactual model/prompt com-parison on real production data without live system access"), so nothing is committed. It is not over alternative actions at a decision point. `alternatives_rejected` lists rejected hypotheses, not explored action branches. |
| 9 | branch_provenance | partial | Plan versions record the parent (`supersedes`), the divergence point (`revision_trigger: step_002`) and the reason (`rationale`). The mock-replay report names per-step divergences between the original and new model. There is no branch tree of states. |
| 10 | explicit_current_belief_state | partial (weak) | It has a structured current plan, per-step observation and inference, and a final verdict with rejected alternatives. These are logged for analytics. They are not a maintained belief, assumption or requirement store that the agent consults. |
| 11 | uncertainty_representation | partial | A scalar `confidence` on the final verdict, used for calibration. There is no per-step uncertainty and no list of unresolved or open items. |
| 12 | future_state_rollout | no | `steps_intended` lists planned actions. No future states are simulated. |
| 13 | multiple_prospective_branches | no | One plan per version. No alternative futures. |
| 14 | probability_over_futures | no | Confidence applies to a diagnosis of a past cause, not to futures. |
| 15 | backward_requirements | no | The `remediation` list follows from the diagnosis. No present obligations are derived from a desired or feared future. |
| 16 | intervention_aware_forecasting | no | Not covered. |
| 17 | prevented_futures_preserved | no | Not covered. |
| 18 | predicted_vs_realized | partial | Verdict confidence is calibrated against human expert assessments. Mock replay compares an original verdict with a new-model verdict. These are diagnoses, not forecasts against realized futures, and the work is a planned method, not results. |
| 19 | cross_time_state_querying | partial (weak) | Population and step queries are possible ("why step 3?", "why plan changed?", re-plan frequency), and steps carry plan_version, so step-indexed lookup works. There is no state_at(t), diff(t1,t2) or as-of API. Diffs are between runs or models, not between times. |
| 20 | unified_temporal_abstraction | no | Covers the historical record plus counterfactual re-runs only. Nothing prospective. Not framed as temporal at all. |

## Threat to the project (precise)
1. **The "checkpoints are not enough" argument is prior art.** The project argues that checkpoints and traces must be supplemented with why-records: decision provenance, versioned plans, authority. AER (v1 Mar 2026, v2 Apr 2026) already makes this case explicitly against LangGraph's checkpointer and against LangSmith, Langfuse, Datadog, OTel GenAI and PROV-AGENT. It does so with a formal proposition and three named non-identifiability sources. The project cannot present this as its own motivation or contribution; it must cite AER.
2. **Plan versioning with lineage is already done.** "Versioned, not overwritten" plans carry `supersedes`, a `revision_trigger` pointing at the step that caused the change, and `rationale`. Delegation authority and per-run model and prompt version complete the "track policy and authority over time" record at investigation granularity. This overlaps the project's "never overwrite time, fork it" for plans, and its identity/policy-tracking lane.
3. **Its "retrieval provenance over availability provenance" is a close sibling of the strict epistemic cutoff.** The project wants "what the agent knew at t, not what it could have known". AER already states the principle, though only as logging, not as enforced reconstruction.
4. **Mock replay is counterfactual re-execution on recorded history.** It holds observations fixed, changes the policy, and diffs per step and on the verdict. This covers "replay" and the policy-counterfactual part of "counterfactual branches".
5. **Benchmark consequence (most important).** EXPERIMENT.md lists "decision provenance" as a temporal-contestant feature. The baseline gets only "decision records retrievable by semantic search". AER shows that rich, structured decision records are a non-temporal, checkpoint-adjacent technology:
   - intent, observation and inference per step;
   - plan versions with revision triggers;
   - evidence chains;
   - rejected alternatives;
   - confidence.

   A fair, strong baseline should therefore get AER-grade decision records too. Otherwise any advantage of the temporal contestant on "notice that a later event changes the significance of an earlier decision" may come from richer provenance logging, not from temporal navigation. That would be a confound under CLAUDE.md rule 4 (strong baseline).

## What AER does NOT cover (residual space for the project)
- **Nothing prospective.** No future-state rollout, no multiple futures, no probabilities over futures, no backward requirements, no intervention-aware forecasting, and no preservation of prevented forecasts (capabilities 12-17 are all "no").
- **No external world-state reconstruction at t, and no as-of or diff query API.** It is not a temporal data model; time appears only as step sequence and plan_version.
- **It is not agent-facing.** AER serves platform teams' population-level analytics: "AERs provide the BI layer for autonomous agent reasoning". The agent writes records but is never described as reading its own past records at decision time.
- **No reopening of earlier decisions.** Nothing makes the agent revisit and remediate completed decisions when a later event changes their significance. The `revision_trigger` link covers only forward plan revision within one short investigation; it never retroactively re-evaluates earlier actions. This is exactly the behaviour the project's benchmark scores, and AER neither tests nor enables it.
- **It is not a lifelong history.** Default eviction is 50 records / 14 days, the scope is single investigations "in seconds", and multi-agent composition is future work.
- **No empirical results.**
  - The evaluation is "planned".
  - Storage numbers come from a "stylized 10-step investigation".
  - Faithfulness of self-reported reasoning is acknowledged as an open risk: post-hoc rationalization, format gaming.
- **No public code found.** The SDK is described (`start_investigation()`, `log_plan()`, `log_step()`, `record_verdict()`) but is not locatable. The memgrafter digest independently notes the SDK location is unspecified.

## Sources
- https://arxiv.org/abs/2603.21692 (canonical; blocked, not fetched)
- https://raw.githubusercontent.com/twenhui2-afk/daily-paper-reader/main/docs/202603/25/2603.21692v1-reasoning-provenance-for-autonomous-ai-agents-structured-behavioral-analytics-beyond-state-checkpoints-and-execution-traces.txt (v1 full text conversion; fetched)
- https://raw.githubusercontent.com/twenhui2-afk/daily-paper-reader/main/docs/202603/25/2603.21692v1-reasoning-provenance-for-autonomous-ai-agents-structured-behavioral-analytics-beyond-state-checkpoints-and-execution-traces.md (metadata + abstract; fetched)
- https://raw.githubusercontent.com/ehijano/rss_fetch/master/rss_data/cs.SE/2026-04-13_cs.SE.xml (v2 replace-cross announcement; fetched)
- https://raw.githubusercontent.com/Lyken17/arXiv-stats/master/info/2026-April/13/paper_info.json (v2 authors and categories; fetched)
- https://raw.githubusercontent.com/memgrafter/research-digests/main/ml_research_analysis_2026/2603.21692_reasoning-provenance-for-autonomous-ai-agents-structured-behavioral-analytics-beyond-state-checkpoints-and-execution-traces_20260331_193147.md (secondary LLM digest; fetched)
- https://raw.githubusercontent.com/Ala-ADN/gommage/master/README.md (third-party AER-inspired implementation; fetched)
- https://pypi.org/pypi/aer/json (unrelated package; PyPI probe)
