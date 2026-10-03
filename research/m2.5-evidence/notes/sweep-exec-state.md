# Lane sweep: exec-state (agent execution-state management, checkpoint/rollback/fork/replay)

Date: 2026-10-03. Method: WebSearch (server-side; results are search-engine extracts of arXiv/HTML pages, so
"snippet" lines marked [extract] may be lightly paraphrased by the search tool) plus git clones of three repos
(ActiveGraph, Agent-Git, Chronicle) whose text is quoted verbatim and marked [repo-verbatim].
The session's WebSearch budget ran out after about 45 lane queries; nothing below relies on recall alone.
Clones are under scratchpad/lit/repos/{activegraph,Agent-Git,chronicle}.

## Ranked works

### 1. The Log is the Agent / ActiveGraph (Nakajima, arXiv 2605.21997, May 2026). Threat: HIGH
- URL: https://arxiv.org/abs/2605.21997 ; code: https://github.com/yoheinakajima/activegraph (Apache-2.0, pip install activegraph)
- [extract] "deterministic replay of any run from its log, cheap forking that branches a run at any event without re-executing the shared prefix, and end-to-end lineage from a high-level goal down to the individual model call that produced each artifact."
- [extract] "The append-only event log is the source of truth; the working graph is a deterministic projection of that log"
- [extract] "a forking and structural-diff primitive that branches a run at any event and answers counterfactual 'what if I had done X differently' questions without re-executing the shared prefix."
- [repo-verbatim, runtime.py Runtime.fork docstring] "Branch this run at `at_event` into an independent new run. ... Copies events from the parent's log up to and including `at_event` into a fresh `run_id`, replays them into a new Graph, then returns a Runtime that operates on that Graph. Forks-of-forks work the same way"
- [repo-verbatim, README] "Fork-and-diff. Branch any run at any event into an independent fork, configure it differently, and structurally diff the result against the parent. Cache replay means the shared prefix doesn't re-execute (no new LLM calls)."
- [repo-verbatim, docs/quickstart.md] "ran the same starting state through a different decision, and got a structural comparison of the results. Hypothesis testing on an agentic system, without losing the parent run."
- Lineage is stored as (parent_run_id, forked_at_event_id).
- Capabilities: 1, 2, 3 (partly: the graph projection holds the agent's typed working objects as of event e, a strict prefix), 5, 6, 7, 8, 9, 19 (diff; as-of by fork-at-event). It has no prospective rollouts, no forecasts, no prevented futures.

### 2. Shepherd (Yu, Chong, Nandi, Soylu, Sun, Manning, Shi; arXiv 2605.10913). Threat: HIGH
- URL: https://arxiv.org/abs/2605.10913 (v3 title: "Shepherd: Enabling Programmable Meta-Agents via Reversible Agentic Execution Traces")
- [extract] "records every agent-environment interaction as a typed event in a Git-like execution trace where any past state can be cheaply forked and replayed."
- [extract] "forks the agent process and its filesystem 5x faster than Docker, with >95% prompt-cache reuse on replay."
- [extract] "Counterfactual meta-optimization: a meta-agent branches to explore alternative paths"; "core operations mechanized in Lean".
- Capabilities: 1, 2, 5, 6, 7, 8, 9. It restores the whole agent process, so in-process belief state comes back with it.

### 3. ChronoMem (Su, Xu, Zuo, Bertino; arXiv 2607.27773, Jul 2026). Threat: HIGH
- URL: https://arxiv.org/abs/2607.27773
- [extract] "commits whole-memory snapshots at each memory write, maintains structured version histories, and supports natural-language rollback requests by mapping undo intents to concrete historical versions"
- [extract] "Existing agent memory systems are designed around forward-only evolution, continuously accumulating, consolidating, and overwriting knowledge, with no principled mechanism to inspect, version, or revert prior states."
- [extract] "a post-exposure evaluation protocol that tests whether an agent can behave counterfactually after rollback -- answering queries and summarizing history as if future updates never occurred."
- [extract] "the first open-source system and benchmark for systematic, semantic, global memory rollback in LLM agents."
- Capabilities: 1 (snapshots), 3 (memory as of version v, evaluated for hindsight leakage), 5, 6, 19 (version selection, history summarization).
- Note: the post-exposure protocol is close to the project's "strict epistemic cutoff / no hindsight" test.

### 4. DeepRewind (Abaskohi, Dabiriaghdam, Wang, West, Carenini; arXiv 2609.36344, Sep 2026). Threat: HIGH
- URL: https://arxiv.org/abs/2609.36344
- [extract] "represents the agent's evolving epistemic state as a typed graph of sources, evidence, claims, hypotheses, assumptions, commitments, plans, and drafts. Before accepting an intermediate conclusion, a prompt-based world model predicts its impact and estimates reversibility based on hypothesis narrowing, information loss, recovery cost, and contradiction-trigger coverage."
- [extract] "A binary controller blocks risky commitments, while a consistency monitor performs dependency-aware rollback when later evidence invalidates them."
- [extract] "reduces premature commitments by 59.1% relative to Open Deep Research."
- Capabilities: 10, 11 (assumptions, hypotheses), 12 (impact prediction before commitment), 15 (partly: reversibility and option preservation used as a gate), 5/6 (rollback of commitments), 9 (dependency edges).
- Overlaps the benchmark's core behaviour: a later event invalidates an earlier commitment, and the agent reopens it.

### 5. AgentRewind (Zhuang, Chen, Duan, Zheng, Li, Zhang; arXiv 2608.14380, Aug 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2608.14380
- [extract] "records aligned checkpoints of the agent context and controlled environment, allowing agents to return to an earlier state and resume execution with information from previous attempts."
- [extract] "The recorded trajectory includes the task instruction, LLM inputs and outputs, tool calls, and tool results."
- [extract] "restores the selected checkpoint and injects agent-generated rewind memory into the restored context." It also contributes MettleBench (long-horizon engineering assignments with a series of related requirements).
- Capabilities: 1, 2, 3 (message-level), 5, 6. Hindsight is carried into the restored state on purpose.

### 6. Rollback-Induced Reflection, RIR (arXiv 2609.18304, Sep 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2609.18304
- [extract] "treats reliable recovery as a rollback-boundary control problem jointly determining when to intervene, where to resume, and what information should survive recovery."
- [extract] "state claims invalidated by restoration are removed, while reusable observations and lessons are distilled into reflective knowledge for the next attempt."
- [extract] "Rollback-Consistent Reflection Memory separates branch-local state restored with the checkpoint from reusable knowledge that persists across rollback ... deliberately excluding the agent's current state to avoid reintroducing stale claims after restoration."
- Capabilities: 3 (explicit control over which later knowledge crosses the restore boundary), 5, 6, 10, 18 (failure analysis from the abandoned suffix).

### 7. Planarian: Managing Agent State with Statepoints (arXiv 2609.35366, Sep 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2609.35366
- [extract] "agent statepoints, which are consistent, restorable point-in-time versions of the environment state."
- [extract] "(i) snapshot creates a new statepoint spanning local and remote state ... transparently records compensating actions to undo remote state changes; (ii) rollback restores the environment to a previous statepoint ... (iii) fork creates multiple isolated branches from a statepoint, enabling the agent to explore alternatives in parallel."
- [extract] "improving task quality by up to 15x ... with only 3% overhead."
- Capabilities: 2, 5, 6, 7, 8. Its scope is environment state, not belief state.

### 8. AgentGit (arXiv 2511.00628; AAAI-26 WMAC workshop). Threat: MEDIUM
- URL: https://arxiv.org/html/2511.00628 ; code: https://github.com/HKU-MAS-Infra-Layer/Agent-Git
- [extract] "improves upon existing frameworks like LangGraph, where its mechanism deletes subsequent results upon reverting to a previous state"
- [repo-verbatim] "Commit State : A saved snapshot of an agent's state (internal context + tool usage), persisted in the database."
- [repo-verbatim] "Non-Destructive Branching: Rollbacks create new branches, preserving all timelines"
- [repo-verbatim] "Tool Revert : Reverses tool effects based on commit records (simple reversion for state-independent tools, compensating actions for path-dependent tools)."
- Capabilities: 5, 6, 7, 8, 9. "Preserving all timelines" is essentially the slogan "never overwrite time, fork it".

### 9. Git Context Controller, GCC (arXiv 2508.00031, 2025). Threat: MEDIUM
- URL: https://arxiv.org/abs/2508.00031
- [extract] "elevates agent context from a transient token stream to a persistent, navigable memory workspace with explicit operations -- COMMIT, BRANCH, MERGE, and CONTEXT, that enable milestone-based checkpointing, isolated exploration of alternative reasoning paths, and hierarchical retrieval of historical context."
- [extract] "Each project maintains a global roadmap (main.md), while each branch contains its own commit summaries, execution traces, and structured metadata."
- Capabilities: 5, 7, 8, 9, 10 (roadmap), 19 (retrieval of historical context at different resolutions). The agent itself operates the versioning, so this is versioned reasoning state rather than only infrastructure.

### 10. GitOfThoughts (Shekar, H S, Krishnan; arXiv 2606.14470, Jun 2026). Threat: MEDIUM (negative evidence)
- URL: https://arxiv.org/abs/2606.14470
- [extract] "stores an agent's reasoning tree as a git repository: every scored thought is a commit, scores are notes, outcomes are tags, and retrieval is 'git log' over the agent's own history."
- [extract] "tested five memory stores (none, a markdown file, a vector database, a graph, and git) ... on new problems, memory didn't help."
- [extract] "Git delivers auditability, provenance, line-level diffs over reasoning text, deterministic replay, and mergeable memory, at accuracy parity with every other substrate."
- Capabilities: 1, 6, 9, 19 (diffs over reasoning).
- Undermining: it found accuracy parity between a versioned reasoning substrate and plain memory. That is a direct prior negative result for the claim that temporal navigation improves task performance.

### 11. OpenRath: Session-Centered Runtime State (Wen, Wang, Xu; arXiv 2606.19409, Jun 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2606.19409
- [extract] "transcripts, tool effects, memory events, workspace placement, branch provenance, and replay evidence are recorded separately and become difficult to inspect or reproduce."
- [extract] "A Session is branchable, inspectable, replayable, backend-aware, and composable, and it records conversation chunks, sandbox placement, lineage metadata, token usage, pending work, and tool evidence"
- [extract] "The same Session can be passed to agents, forked for independent work, merged after review, persisted as evidence, and replayed"
- Capabilities: 1, 5, 6, 7, 9.

### 12. OpenHands Software Agent SDK, event-sourced state (arXiv 2511.03690; earlier OpenHands ICLR 2025, arXiv 2407.16741). Threat: MEDIUM
- URL: https://arxiv.org/pdf/2511.03690 ; docs: https://docs.openhands.dev/sdk/arch/events
- [extract] "Rather than updating a database with the 'current' state of the agent, the SDK treats every interaction -- whether an LLM action or a tool observation -- as an immutable event appended to a log."
- [extract] "The system can reconstruct the state at any time by replaying the event log: S_t=f(S_(t-1),e_t)"
- [extract] "This event sourcing pattern provides deterministic replay, persistent auditability, and precise debugging"
- Capabilities: 1, 2, 5, 6, 19 (state at t via fold). This is the default architecture of a major open coding agent, and it is a natural strong baseline substrate.

### 13. Safe to Resume? Breaking Execution Continuity of Agent Execution via Rollback (Wu et al.; arXiv 2608.29381). Threat: MEDIUM (undermining)
- URL: https://arxiv.org/abs/2608.29381
- [extract] "A faithfully restored checkpoint may resume an execution whose states, assumptions, and external effects never coexisted in any valid history. In other words, correct rollback does not guarantee secure recovery."
- [extract] "five fundamental failure modes spanning incomplete or inconsistent internal state, stale external dependencies, nondeterministic replay, and unrecorded external effects ... three end-to-end attacks on Hermes, Cline, and LangGraph"
- Companions:
  - "When Can Agents Safely Checkpoint, Fork, Restore, and Merge? Exact Checking for Execution Edits", arXiv 2608.22928 (https://arxiv.org/abs/2608.22928). [extract] "An execution edit cannot undo an earlier authorization or a tool request already sent." Mechanized in Lean.
  - ACRFence, arXiv 2603.20625 (https://arxiv.org/abs/2603.20625). [extract] "records an effect log for each irreversible tool call, capturing thread and branch identifiers ... enforces replay-or-fork semantics upon restoration."
- Capabilities: 5, 6, 7, 9 (branch IDs in ACRFence).

### 14. Causal Agent Replay, CAR (Shah; arXiv 2606.08275, Jun 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2606.08275
- [extract] "models an agent run as a structural causal model, applies a do-operation to a step, and re-executes the trajectory forward under the same stochastic policy, measuring the shift in the outcome distribution."
- [extract] "a single-step contrastive estimator with a point-of-commitment rule ... a budget-bounded Monte-Carlo Shapley estimator"
- Capabilities: 6, 7, 8, 13, 14 (outcome distribution under interventions from a historical step).
- Related: "Localizing Emergent Failures in Agentic AI: Recovering Minimal Repair Families via Counterfactual Replay" (https://arxiv.org/html/2608.29228) and CausalFlow (https://arxiv.org/abs/2605.25338).

### 15. Claude Code checkpoints and /rewind (product, 2025-2026). Threat: LOW
- URL: https://theaiarchitects.com/blog/claude-code-checkpoints ; also https://github.com/luongnv89/claude-howto/blob/main/08-checkpoints/README.md
- [extract] "Claude Code creates a checkpoint after every prompt, capturing all file edits made through its editing tools." Options: "Restore code and conversation", "Restore conversation", "Restore code", "Summarize from here".
- [extract] "only 'Claude's file edits' are restored -- changes made by bash commands or outside Claude are not." (See also https://www.eon.io/blog/claude-code-rewind-bash)
- Capabilities: 5, 6 (partial), 3 (message-level only). Rewind is user-driven and does not keep branches.

## Also seen (lower relevance; URLs from search results)
- Fork, Explore, Commit: OS Primitives for Agentic Exploration (BranchFS, branch() syscall), https://arxiv.org/abs/2602.08199 . [extract] "first-commit-wins resolution that automatically invalidates sibling branches"
- StateFork + Waypoint, https://arxiv.org/abs/2609.38648 . [extract] "Branching from an intermediate point is correct only when restoration is observation-equivalent"
- DeltaBox, https://arxiv.org/abs/2605.22781 (14 ms checkpoint / 5 ms rollback); Crab, https://arxiv.org/abs/2604.28138 ([extract] "application-level recovery preserves chat history but misses OS-side effects")
- Atomix, transactional tool calls with epochs and compensation, https://arxiv.org/abs/2602.14849
- Recoverability as a System Primitive, https://arxiv.org/abs/2609.13672 ([extract] "A saved state is not necessarily a suitable place to resume.")
- Resume Means Resume (TLA+ resume contract: prefix continuation, effect exactly-once, fork determinism ...), https://arxiv.org/abs/2608.03836
- Chronicle cut-point replay, https://arxiv.org/abs/2609.20625 ; code https://github.com/theagentplane/chronicle . [repo-verbatim] "Cut-point replay: change one boundary, freeze the rest of the incident, and assert deterministically with no LLM calls."
- LogAct (shared log; intentions logged before execution; agentic introspection over its own history), https://arxiv.org/abs/2604.07988
- AgileLog (forkable shared log, continuous forks), https://arxiv.org/abs/2604.14590
- ESAA (event sourcing for SE agents, replay verification with hashing), https://arxiv.org/abs/2602.23193
- Janus (signed hash-chained evidence-before-effect log), https://arxiv.org/abs/2609.38266
- AGDebugger (CHI'25; reset to earlier message, edit, re-execute, with checkpointed agent state), https://arxiv.org/abs/2503.02068
- WebRollback, https://arxiv.org/abs/2504.11788 ; SWE-Replay (branch from archived intermediate steps), https://arxiv.org/abs/2601.22129
- Speculative Actions, https://arxiv.org/pdf/2510.04371 ; TomasuLLM (out-of-order speculative tool execution in CoW sandboxes), https://arxiv.org/html/2609.38201
- Durable execution: Temporal event-history replay for agents, https://temporal.io/blog/of-course-you-can-build-dynamic-ai-agents-with-temporal
- GoEX (undo + damage confinement, 2024), https://arxiv.org/abs/2404.06921
- StateAct (chain-of-states; 2024), https://arxiv.org/abs/2410.02810 . Only in-context state tracking; low relevance.
- STALE (implicit conflict: a later observation invalidates an earlier memory; memory lane), https://arxiv.org/abs/2605.06527
- From Agent Traces to Trust (provenance survey with typed "invalidate" relations), https://arxiv.org/abs/2606.04990
- PatchOptic (2607.05483) is about shared-state projected views and verified patches, not temporal state; low relevance. https://arxiv.org/abs/2607.05483

## Lane answers (short)
- Fork/replay/branch provenance already exists in ActiveGraph, Shepherd, AgentGit, OpenRath, Planarian, GCC, ACRFence (branch IDs in its effect log) and LangGraph (analyzed elsewhere). ActiveGraph adds structural diff between branches and goal-to-call lineage.
- Restoring belief or reasoning state, not just messages, at a historical point:
  - Partially done by ActiveGraph (a typed working graph replayed to a strict event prefix), Shepherd (the full agent process), ChronoMem (the memory store at a version, with a post-exposure no-hindsight test), DeepRewind (a typed epistemic graph with dependency-aware rollback of commitments) and RIR (strips invalidated state claims at the restore boundary).
  - None of them offers a first-class "what did I believe at t, excluding everything after t" query alongside prospective branches, prevented-forecast bookkeeping, or predicted-versus-realized comparison.
