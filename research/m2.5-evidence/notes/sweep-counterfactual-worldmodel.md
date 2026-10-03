# Sweep: counterfactual reasoning, world models, lookahead for LLM agents

Lane: counterfactual-worldmodel. Date: 2026-10-03.

## Method and evidence caveat (read first)

- WebSearch was unavailable for this lane: all 4 attempted WebSearch calls returned
  "this session has used its web search budget (200 of 200 WebSearch calls)". No search-engine results were obtained.
- Evidence therefore comes from (a) `git clone --depth 1` of official paper repos (READMEs and source code read locally),
  and (b) 15 curated paper lists cloned from GitHub and grepped locally (titles, arXiv URLs, maintainer-written TLDRs,
  and, for the AGI-Edgerunners list, abstracts stored in `parsed_v5/*.json`).
- Evidence tiers used below:
  - [REPO] official repo README and/or code read in this session.
  - [ABS] paper abstract text read from a list's JSON (AGI-Edgerunners/LLM-Agents-Papers parsed_v5).
  - [TLDR] maintainer-written TLDR from OSU-NLP-Group/GUI-Agents-Paper-List (not the authors' words).
  - [TITLE] only title + arXiv URL confirmed in a list; content description from recall and marked UNVERIFIED.
- Clones: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/repos/cf/ (papers) and .../cf/lists/ (curated lists).

## Local "queries" actually run (grep over cloned lists / repos)

1. WebSearch "WebDreamer LLM world model web agent simulate before act" -> budget exhausted
2. WebSearch "LLM agent counterfactual trajectory branching from past state learn alternative actions 2025" -> budget exhausted
3. WebSearch "Language Agent Tree Search LATS unifies reasoning acting planning" -> budget exhausted
4. WebSearch "hindsight relabeling LLM agents counterfactual experience replay 2025 arXiv" -> budget exhausted
5. grep lists: `counterfactual`
6. grep lists: `world model|world-model|dreamer|simulat` x `web|gui|tool|code agent|software|llm agent|computer-use|mobile`
7. grep lists: `hindsight|regret|what if|rollback|backtrack|undo|foresight|anticipat|prospect|premortem|early experience|dyna|lookahead|rewind|time-travel|fork`
8. grep lists: `relabel|rewriting trajector|imagin|mental simulation|experience replay|alternative action|branch|tree search|MCTS|monte carlo`
9. grep memory/self-evolving lists: `hindsight|ECHO|counterfactual|regret|alternative|branch|fork|rollback|replay|retrospect|future|forecast|foresight`
10. grep agentic-RL/planning lists: `world model|hindsight|regret|counterfactual|tree|branch|imagin|simulat|lookahead|rollback|backtrack`
11. grep lists: `retrospect|revisit|reopen|re-evaluat|belief revision|outdated|stale|invalidat|temporal memory|time-aware|versioned|as-of|bitemporal|future self|prospective memory|intention`
12. JSON abstract search (parsed_v5): Early Experience, Dyna-Think, SimuRA, WebEvolver, WebSynthesis, Hindsight Regeneration, Anticipatory Reflection, Stepwise Rollback, Lookahead Search, WebCoT, Counterfactual Reflection, Rollback, counterfactual, hindsight, regret, What if, world model
13. code grep: ExACT `rpolicy.py` (reflection DB, expected-vs-actual), Agent-R `path_collection.py` (splicing), C3 `rollout_generator.py` (parent_id), WebDreamer (persistence of simulations)

Repos cloned: OSU-NLP-Group/WebDreamer, kyle8581/WMA-Agents, andyz245/LanguageAgentTreeSearch, maitrix-org/llm-reasoners,
Ber666/RAP, kohjingyu/search-agents, aorwall/moatless-tree-search, microsoft/ExACT, sentient-engineering/agent-q, bytedance/Agent-R,
AMAP-ML/Tree-GRPO, dongguanting/ARPO, agentification/RAFA_code, QwenLM/Qwen-AgentWorld, facebookresearch/cwm, elated-sawyer/WALL-E,
langfengQ/CoSo, EIT-EAST-Lab/C3, vectorize-io/hindsight. (maitrix-org/SimuRA clone failed.)

Lists cloned: tsinghua-fib-lab/World-Model, WooooDyy/LLM-Agent-Paper-List, Shichun-Liu/Agent-Memory-Paper-List,
OSU-NLP-Group/GUI-Agents-Paper-List, zjunlp/LLMAgentPapers, hijkzzz/Awesome-LLM-Strawberry, AGI-Edgerunners/LLM-Agents-Papers,
knightnemo/Awesome-World-Models, showlab/Awesome-GUI-Agent, EvoAgentX/Awesome-Self-Evolving-Agents, CharlesQ9/Self-Evolving-Agents,
luo-junyu/Awesome-Agent-Papers, xhyumiracle/Awesome-AgenticLLM-RL-Papers, AGI-Edgerunners/LLM-Planning-Papers, nuster1128/LLM_Agent_Memory_Survey.

---

## Works

### 1. C3: Contextual Counterfactual Credit Assignment for Multi-Agent RL in LLM Collaboration (2026) [REPO]
- URL: https://arxiv.org/abs/2603.06859 ; code https://github.com/EIT-EAST-Lab/C3
- Verbatim (README TL;DR): "The usual answer is to guess it with a learned critic, because in most environments a decision point
  cannot be revisited. Agents that talk through a shared context are not most environments: the transcript is the whole state,
  so you can reset the run to any message, swap it, and play the rest out. **C3** does that. It samples alternatives at a decision
  point, replays each one to the final reward, and compares them against a leave-one-out baseline. No learned parameters, no fitted
  value function, and the counterfactual is executed rather than predicted."
- Code: `c3/protocol/rollout_generator.py` logs `parent_id` and `parent_id_true` per node ("true parent node_id (not collapsed)").
- Caps: execution_checkpoints (transcript-as-state), replay, fork_from_historical_state, counterfactual_action_branches, branch_provenance.
- Threat: HIGH for the mechanism "fork from a historical decision point, execute counterfactual, compare". Not lifelong, uses final reward (hindsight).

### 2. Agent-R: Training Language Model Agents to Reflect via Iterative Self-Training (2025) [REPO]
- URL: https://arxiv.org/abs/2501.11425 ; code https://github.com/bytedance/Agent-R
- Verbatim: "our approach leverages Monte Carlo Tree Search (MCTS) to construct training samples that recover correct trajectories from
  erroneous ones. A key challenge of agent task reflection lies in the necessity for timely revision rather than waiting until the end
  of a rollout to revise errors. ... the actor model identifies the first error step (within its current capability) in a failed
  trajectory. Starting from it, we splice it with the adjacent correct path, which shares the same parent node in the tree."
- Caps: fork_from_historical_state, counterfactual_action_branches, branch_provenance (tree parent), replay.
- Threat: MEDIUM-HIGH for "identify which earlier step was wrong and branch from it"; within-episode, hindsight, for training data.

### 3. ExACT: Reflective-MCTS and Exploratory Learning (2024/ICLR 2025) [REPO + code]
- URL: https://arxiv.org/abs/2410.02052 ; code https://github.com/microsoft/ExACT
- Verbatim: "Our **R-MCTS agent** extends traditional MCTS by 1) incorporating contrastive reflection, allowing agents to learn from
  past interactions and dynamically improve their search efficiency; and 2) using multi-agent debate to provide reliable state evaluation."
  "**Exploratory Learning** ... trains the models to explore the environment, evaluate a state, and backtrack to viable ones when it detects
  that the current state cannot lead to success."
- Code (`src/agentic/rpolicy.py`): `expected_v = task_record.V_next; actual_Qsa = task_record.Q; unexpected_score = [abs(v - q) ...]`;
  picks `most_unexpected_idx`; builds a `ReflectionRecord(intent, state_str, action_str, next_state_str, reflection, _from_task_hash)`;
  stores in a FAISS index under `db_path/policy_reflections` and `retrieve_reflections(curr_task_intent, curr_obs)` in later tasks.
- Caps: predicted_vs_realized (expected value vs realized Q), counterfactual_action_branches, multiple_prospective_branches,
  fork_from_historical_state (backtracking), branch_provenance (partial: _from_task_hash), immutable_historical_observations (task records).
- Threat: MEDIUM. Closest found to "keep what was learned from branches with provenance and reuse later", but stores distilled reflections, not branches.

### 4. WebDreamer: Is Your LLM Secretly a World Model of the Internet? Model-Based Planning for Web Agents (2024; TMLR-era follow-ups 2025) [REPO]
- URL: https://arxiv.org/abs/2411.06559 ; code https://github.com/OSU-NLP-Group/WebDreamer
- Verbatim: "using LLMs as a world model of the internet to predict the outcomes of actions on websites. Our method, **WebDreamer**, employs
  LLM-based simulation for speculative planning on the web, surpassing reactive baselines while offering greater safety and flexibility
  compared to tree search methods."; `evaluate_simulation(..., num_of_sim=3, ..., steps=2)`; "k: Number of imagination steps to simulate."
- Code: released modules (controller.py, simulation_scoring.py, world_model.py) contain no file persistence; simulations are returned in memory.
- Caps: future_state_rollout, multiple_prospective_branches, counterfactual_action_branches.
- Threat: MEDIUM (prospective-simulation pillar is prior art). Simulated futures are discarded after action selection.

### 5. WMA: Web Agents with World Models: Learning and Leveraging Environment Dynamics in Web Navigation (ICLR 2025) [REPO + ABS]
- URL: https://arxiv.org/abs/2410.13232 ; code https://github.com/kyle8581/WMA-Agents
- Verbatim: "current LLM-based web agents ... often yielding errors such as repeatedly buying a non-refundable flight ticket. By contrast,
  humans can avoid such an irreversible mistake, as we have an awareness of the potential outcomes (e.g., losing money) of our actions ...
  we present a World-model-augmented (WMA) web agent, which simulates the outcomes of its actions for better decision-making."
  "transition-focused observation abstraction, where the prediction objectives are free-form natural language descriptions exclusively
  highlighting important state differences between time steps."
- Caps: future_state_rollout, counterfactual_action_branches, multiple_prospective_branches.
- Threat: MEDIUM. Feared-future (irreversible harm) avoidance via simulation = one-step, action-filter form of "backward requirements from feared futures".

### 6. RAP: Reasoning with Language Model is Planning with World Model (2023, foundational) [ABS + REPO]
- URL: https://arxiv.org/abs/2305.14992 ; code https://github.com/Ber666/RAP , https://github.com/maitrix-org/llm-reasoners
- Verbatim (abstract): "LLMs lack an internal world model to predict the world state ... and simulate long-term outcomes of actions.
  This prevents LLMs from performing deliberate planning akin to human brains, which involves exploring alternative reasoning paths,
  anticipating future states and rewards, and iteratively refining existing reasoning steps. ... RAP repurposes the LLM as both a world
  model and a reasoning agent, and incorporates a principled planning algorithm (based on Monto Carlo Tree Search)"
- Caps: future_state_rollout, multiple_prospective_branches, counterfactual_action_branches.
- Threat: LOW-MEDIUM (establishes the abstraction "LLM as world model + search over imagined futures").

### 7. LATS: Language Agent Tree Search Unifies Reasoning Acting and Planning (ICML 2024, foundational) [REPO]
- URL: https://arxiv.org/abs/2310.04406 ; code https://github.com/andyz245/LanguageAgentTreeSearch (also a LangGraph LATS example)
- Verbatim: "Official implementation for ICML 2024 paper Language Agent Tree Search Unifies Reasoning Acting and Planing in Language Models";
  "``--iterations``: maximum number of trajectories to sample"; "``programming/root/`` contains all the trajectories from the paper's experiments".
- Caps: fork_from_historical_state, counterfactual_action_branches, branch_provenance (search tree), multiple_prospective_branches.
- Threat: MEDIUM-LOW (standard pattern; within-task; trees not a lifelong store).

### 8. WALL-E / WALL-E 2.0: World Alignment by NeuroSymbolic Learning improves World Model-based LLM Agents (2025, NeurIPS 2025 per README comment) [REPO]
- URL: https://arxiv.org/abs/2504.15785 ; code https://github.com/elated-sawyer/WALL-E
- Verbatim: "We further propose an RL-free, model-based agent "WALL-E" through the model-predictive control (MPC) framework ... we adopt an
  LLM agent as an efficient look-ahead optimizer of future steps' actions by interacting with the neurosymbolic world model."
  "WALL-E iteratively refines the symbolic knowledge with the agent's actual trajectories in the environment and the world model predicted
  trajectories. The NeuroSymbolic learning takes 4 stages: (1) comparing predicted and actual trajectories; (2) learning new symbolic
  knowledge from real trajectories; ..."
- Caps: future_state_rollout, predicted_vs_realized, counterfactual_action_branches.
- Threat: MEDIUM for "compare predicted vs realized futures and learn" (used to fix the world model, not to calibrate forecasts or preserve prevented ones).

### 9. Dyna-Think: Synergizing Reasoning, Acting, and World Model Simulation in AI Agents (2025) [ABS]
- URL: https://arxiv.org/abs/2506.00320
- Verbatim (abstract): "we propose Dyna-Think, a thinking framework that integrates planning with an internal world model with reasoning
  and acting ... DIT reconstructs the thinking process of R1 to focus on performing world model simulation relevant to the proposed (and planned)
  action ... DDT uses a two-stage training process to first improve the agent's world modeling ability via objectives such as state prediction
  or critique generation, and then improve the agent's action via policy training. We evaluate our methods on OSWorld"
- Caps: future_state_rollout, counterfactual_action_branches.
- Threat: LOW-MEDIUM (Dyna-style is standard).

### 10. WebEvolver (2025) and WebWorld (2026) and Qwen-AgentWorld (2026): scaled language world models for agents
- WebEvolver [ABS]: https://arxiv.org/abs/2504.21024 — "This world model predicts the next observation based on the current observation and
  action within the web environment. ... the World Model serves dual roles: (1) as a virtual web server generating self-instructed training data
  to continuously refine the agent's policy, and (2) as an imagination engine during inference, enabling look-ahead simulation to guide action
  selection for the agent LLM."
- WebWorld [TLDR]: https://arxiv.org/abs/2602.14721 — "WebWorld is a large-scale world model for web-agent training built from over one million
  real web interactions. It synthesizes long-horizon trajectories for training, improves WebArena performance".
- Qwen-AgentWorld [REPO]: https://arxiv.org/abs/2606.24597 ; https://github.com/QwenLM/Qwen-AgentWorld — "**Qwen-AgentWorld** is a native
  language world model that simulates agentic environments via long chain-of-thought reasoning across **seven unified domains**: MCP, Search,
  Terminal, SWE, Android, Web, and OS." "controllable perturbations and fictional-world construction surpass real-environment training."
- Also seen: R-WoM https://arxiv.org/abs/2510.11892 [TLDR: "simulation quality degrades sharply on full-procedure planning even when short-range
  prediction remains reasonable"], WM-R1 https://arxiv.org/abs/2608.27508, Discriminative World Models for Web Agents https://arxiv.org/abs/2609.02885,
  WAC https://arxiv.org/abs/2602.15384, WebSynthesis https://arxiv.org/abs/2507.04370, SimuRA https://arxiv.org/abs/2507.23773 [TITLE only],
  CWM https://github.com/facebookresearch/cwm ("mid-trained CWM on a large number of observation-action trajectories from Python execution traces and agentic interactions").
- Caps: future_state_rollout, multiple_prospective_branches.
- Threat: LOW-MEDIUM individually; collectively they make "simulate future states for tool/code/web agents" a commodity capability.

### 11. Agent Learning via Early Experience (2025) [TITLE only; content UNVERIFIED]
- URL: https://arxiv.org/abs/2510.08558 (listed in knightnemo/Awesome-World-Models under "Building World Models from Language Priors" and Shichun-Liu/Agent-Memory-Paper-List)
- From recall (UNVERIFIED this session): agent takes alternative actions at states of expert trajectories, observes resulting states, and trains on
  (i) implicit world modeling of those outcomes and (ii) self-reflection contrasting expert vs alternative actions.
- Caps (if recall is right): counterfactual_action_branches, fork_from_historical_state, future_state_rollout.
- Threat: MEDIUM (directly "explore alternative branches from past states and learn"), pending verification.

### 12. Explicit rollback / backtracking for web & GUI agents (2025-2026)
- WebRollback [ABS]: https://arxiv.org/abs/2504.11788 (EACL 2026 oral per list) — "we enhance web agents with an explicit rollback mechanism, enabling
  the agent to revert back to a previous state in its navigation trajectory."
- WebCoT [ABS]: https://arxiv.org/abs/2505.20013 — "key reasoning skills essential for effective web agents, i.e., reflection & lookahead, branching, and rollback"
- GA-Rollback [ABS]: https://arxiv.org/abs/2503.02519 — "the assistant triggers a rollback operation upon detection of incorrect actions."
- WebOperator [TLDR]: https://arxiv.org/abs/2512.12692 — "combining best-first exploration with safety-aware action ranking and verified backtracking before replaying prior paths."
- BEAP-Agent [TLDR]: https://arxiv.org/abs/2601.21352 — "explicit multi-level backtracking ... Its Planner, Executor, and Tracker jointly support state rollback and task updates".
- Caps: fork_from_historical_state, replay, execution_checkpoints (partial).
- Threat: LOW-MEDIUM (rollback = discard branch, not preserve it).

### 13. Tree-structured rollouts in agentic RL: Tree-GRPO (ICLR 2026), ARPO (2025), Agent Q (2024)
- Tree-GRPO [REPO]: https://arxiv.org/abs/2509.21240 ; https://github.com/AMAP-ML/Tree-GRPO — "adopting a tree-search rollout strategy in place of
  independent chain-based rollouts for LLM agent RL. Based on ReAct step-level nodes ... (ii) **Tree-based process supervion signal**." "[Jan 27, 2026]: ... accepted by ICLR 2026."
- ARPO [REPO]: https://arxiv.org/abs/2507.19849 ; AEPO https://arxiv.org/abs/2510.14545 ; https://github.com/dongguanting/ARPO
- Agent Q [REPO]: https://arxiv.org/abs/2408.07199 ; https://github.com/sentient-engineering/agent-q — "actor <> critic architecture + monte carlo tree search based reinforcement learning + dpo finetuning"; "generate dpo pairs for RL: python -m agentq.core.mcts.browser_mcts".
- ANCHOR [TLDR]: https://arxiv.org/abs/2602.07153 — "identifying branch points and generating verified alternative task continuations."
- Caps: fork_from_historical_state, counterfactual_action_branches, branch_provenance (tree), multiple_prospective_branches.
- Threat: MEDIUM-LOW (branching from earlier states is standard in training; branches consumed by gradient updates).

### 14. ToM-agent: LLMs as Theory of Mind Aware Generative Agents with Counterfactual Reflection (2025) [ABS]
- URL: https://arxiv.org/abs/2501.15355
- Verbatim: "ToM-agent disentangles the confidence from mental states ... can dynamically adjust counterparts' inferred BDIs, along with related confidence
  levels. We further put forth a counterfactual intervention method that reflects on the gap between the predicted responses of counterparts and their real utterances"
- Caps: explicit_current_belief_state, uncertainty_representation, predicted_vs_realized.
- Threat: LOW-MEDIUM (beliefs-with-confidence + predicted-vs-actual reflection in a dialogue agent).

### 15. Pre-execution consequence prediction for safety: SeerGuard (2026), MirrorGuard (2026)
- SeerGuard [TLDR]: https://arxiv.org/abs/2607.15550 — "Its safety-augmented world model jointly predicts likely next states and action risk so the agent can reject harmful actions before execution."
- MirrorGuard [TLDR]: https://arxiv.org/abs/2601.12822 — "trains on high-risk trajectories synthesized in a neural-symbolic text simulator called MirrorWorld, then corrects insecure reasoning before real computer-use agents act."
- Caps: future_state_rollout, uncertainty_representation (risk), counterfactual_action_branches.
- Threat: LOW-MEDIUM (feared-future -> veto action; prevented futures not preserved or scored).

## Other items seen (lower relevance)
- SWE-Search (MCTS for software agents): https://arxiv.org/abs/2410.20285 ; https://github.com/aorwall/moatless-tree-search
- Tree Search for Language Model Agents: http://arxiv.org/abs/2407.01476 ; https://github.com/kohjingyu/search-agents
- RAFA "Reason for Future, Act for Now" (ICML 2024): https://arxiv.org/abs/2309.17382
- Atomic Fact Augmentation and Lookahead Search: https://arxiv.org/abs/2506.09171 ("the LLM simulates potential trajectories and evaluates their outcomes")
- WebATLAS [TLDR]: https://arxiv.org/abs/2510.22732 ("reuses past interaction outcomes as persistent experience memory and simulates candidate actions before executing them")
- Interactive Dialogue Agents via RL on Hindsight Regenerations: https://arxiv.org/abs/2411.05194
- Gated Hindsight Distillation: https://arxiv.org/abs/2608.06065
- CoSo Counterfactual Soft RL (ICML 2025): https://arxiv.org/abs/2505.03792 ; https://github.com/langfengQ/CoSo
- TimeWarp: Evaluating Web Agents by Revisiting the Past: https://arxiv.org/abs/2603.04949 (historical UI versions; environment drift, not agent epistemic history)
- H2R Hierarchical Hindsight Reflection: https://doi.org/10.48550/arXiv.2509.12810 ; Hindsight agent memory https://arxiv.org/abs/2512.12818 (memory lane)
- Agent Alpha (MCTS for CUAs): https://arxiv.org/abs/2602.02995 ; Spine-Branch Coordination: https://arxiv.org/abs/2608.22077

## Lane answers (short)
Q1 standard? Yes within episodes/training: tree search with backtracking (LATS, ExACT, Agent Q, SWE-Search, WebOperator, Agent Alpha),
branch-from-earlier-step data synthesis (Agent-R, ANCHOR, Early Experience [unverified], Tree-GRPO/ARPO), executed counterfactual replay from any
historical decision point (C3), imagined branches via world models (RAP, WebDreamer, WMA, WebEvolver, Dyna-Think, WALL-E, Qwen-AgentWorld).
Q2 keep with provenance and reuse later? Partially: parent pointers inside search trees (LATS, Agent-R "same parent node", C3 parent_id_true);
ExACT persists reflection records with _from_task_hash in a FAISS DB and retrieves them in later tasks; datasets persist branches for training only.
Not found: lifelong, queryable branch store; branches evaluated with a strict epistemic cutoff; prevented/averted forecasts preserved and labelled.
