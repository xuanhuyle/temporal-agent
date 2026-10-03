# Resume Gate — Native framework bakeoff

Date: 2026-10-03

## Question

Why should a developer install Resume Gate instead of using the native controls already exposed by LangGraph or the OpenAI Agents SDK?

This is the most important adversarial product test so far.

The comparison intentionally uses the **best native mechanism available in each framework**, not a strawman.

The bakeoff tests live in:

- `tests/test_native_bakeoff_langgraph.py`
- `tests/test_native_bakeoff_openai.py`

They run in the same CI jobs as the Resume Gate integrations.

## Result

### Short version

**Native controls are good enough for a single known authority check.**

Resume Gate does **not** currently justify itself on the claim that developers cannot re-check authority at resume time.

Its remaining advantages are:

1. automatic structural/deployment drift detection;
2. one validity vocabulary across frameworks;
3. centralized external policy/authority integration;
4. fail-closed treatment of legacy/unregistered resumptions;
5. consistent diagnostics and audit semantics.

Those are real advantages, but the bakeoff materially weakens the case for a standalone product.

## Scenario A — approval granted, authority revoked before resume

### Native LangGraph

LangGraph's `interrupt()` resumes by re-entering the node. The application can simply check live authority immediately after the interrupt returns and before returning state that allows the sensitive successor node to run.

The tested native pattern is effectively:

```python
approved = interrupt({"kind": "approval", "amount": state["amount"]})

if not live_authority_is_valid():
    raise NativeResumeBlocked("authority revoked")

return {"approved": bool(approved)}
```

The CI test proves the downstream refund node never executes.

**Verdict:** native solution is excellent for one explicit approval boundary.

Cost:

- a few lines per guarded path;
- no extra storage;
- no new dependency;
- semantics remain visible in the graph.

Weakness:

- application must remember to apply the check at every relevant resume path;
- there is no automatic discovery of which other old assumptions became stale;
- standardizing this across many graphs is application work.

### Native OpenAI Agents SDK

This result is even more threatening to Resume Gate.

OpenAI Agents SDK has `tool_input_guardrail` and a run option:

```python
RunConfig(
    tool_execution=ToolExecutionConfig(
        pre_approval_tool_input_guardrails=True
    )
)
```

The SDK explicitly reruns those guardrails after an approved serialized `RunState` is resumed.

The tested native pattern is:

```python
@tool_input_guardrail
def current_authority(_data):
    if not live_authority_is_valid():
        return ToolGuardrailFunctionOutput.reject_content("authority revoked")
    return ToolGuardrailFunctionOutput.allow()

@function_tool(
    needs_approval=True,
    tool_input_guardrails=[current_authority],
)
def refund_customer(...):
    ...
```

The test:

1. pauses for approval;
2. approves;
3. serializes/restores `RunState`;
4. revokes authority;
5. resumes;
6. native guardrail reruns;
7. tool body does not execute.

**Verdict:** for tool-level live authority, OpenAI native controls are at least as good as Resume Gate and arguably better because they are closer to the tool execution boundary.

This removes one of the strongest earlier product claims.

## Scenario B — tool removed while state is parked

### Native OpenAI Agents SDK

The bakeoff removes the approved tool from `agent.tools` after serializing the pending state.

Native `Runner.run(agent, restored_state)` fails rather than executing the removed tool.

So Resume Gate's `TOOL_REMOVED → BLOCK` adds:

- earlier / standardized diagnosis;
- a common cross-framework error model;

but **not the fundamental safety property** in this tested OpenAI case.

That is an important correction to our earlier framing.

### Native LangGraph

LangGraph does not expose an equivalent universal tool registry at the resume boundary because arbitrary nodes can contain arbitrary application code.

For one application, the developer can store an explicit deployment/tool contract in graph state and compare it after `interrupt()`:

```python
approved = interrupt(...)

if state["resume_contract"] != current_resume_contract():
    raise NativeResumeBlocked("deployment contract changed")
```

This works and passed CI.

But the developer must define, persist, version and maintain `resume_contract`.

Resume Gate v0.2 automates the common structural part by fingerprinting:

- graph topology;
- state schema;
- LangGraph version;
- registered `ToolNode` tools and schemas.

**Verdict:** Resume Gate has a clearer advantage on LangGraph structural/deployment drift than on OpenAI tool authority.

## Scenario C — tool schema changes under the same name

Resume Gate automatically fingerprints tool schemas in both adapters and emits `REVALIDATE` if the same named tool changes.

Framework-native behavior is more contextual:

- argument validation may fail if the old arguments are no longer valid;
- a compatible schema change may still execute;
- a semantic change that keeps the same input shape is invisible to any schema fingerprint;
- applications can add version checks manually.

Resume Gate improves consistency, but it cannot prove semantic equivalence either.

**Verdict:** modest advantage, not a decisive moat.

## Application-code comparison

These are qualitative integration burdens, not benchmark-grade LOC economics.

| Need | Native LangGraph | Native OpenAI Agents | Resume Gate |
|---|---|---|---|
| One live authority check | **Very small** inline check | **Small** tool guardrail | Small context provider |
| Recheck after approval resume | Manual by node design | **Native explicit support** | Automatic at wrapper |
| Tool removed | App/deployment dependent | Native fails safely in tested case | Automatic standardized `BLOCK` |
| Tool schema drift | Manual contract/version | Validation/framework-dependent | Automatic fingerprint |
| State/graph deployment drift | Manual persisted version/contract | SDK owns much RunState compatibility | Automatic fingerprints where observable |
| External policy/authority | Custom app check | Custom guardrail | One common provider |
| Cross-framework vocabulary | None | None | **Yes** |
| Cross-framework audit result | None | None | **Yes** |
| Extra dependency/runtime layer | No | No | **Yes** |

## Developer concepts required

### Native LangGraph

Developer must understand:

- interrupt replay/re-entry semantics;
- where sensitive action occurs after the interrupt;
- which current facts need revalidation;
- how to persist a deployment/version contract if desired.

### Native OpenAI Agents

Developer must understand:

- `needs_approval`;
- tool input guardrails;
- `ToolExecutionConfig(pre_approval_tool_input_guardrails=True)`;
- which current facts need revalidation.

This is not excessive for a production user of the framework.

### Resume Gate

Developer must understand:

- the resume-gate wrapper;
- verdict semantics;
- persistent manifest storage;
- the optional live context provider;
- how `BLOCK`, `REVALIDATE`, and `MIGRATE` map back into application UX.

Resume Gate therefore does **not** obviously win on conceptual simplicity for a single framework.

## Maintenance comparison

### Native approach

Pros:
- framework maintainers keep semantics aligned with their runtime;
- fewer dependencies;
- first-class integration with native approval/tool concepts.

Cons:
- policies are implemented differently in every framework;
- switching or mixing runtimes duplicates governance glue;
- each application decides its own deployment/version contract;
- audit outputs are not standardized.

### Resume Gate

Pros:
- same external validity contract across runtimes;
- framework adapters isolate runtime-specific mechanics;
- centralized policy/authority provider can be shared;
- consistent verdict/audit vocabulary.

Cons:
- adapters must track framework releases;
- may become redundant as frameworks absorb more validity checks;
- another persistence layer must remain aligned with each runtime;
- false positives from conservative fingerprints can create operational friction.

## Native absorption risk

The bakeoff increases native-absorption risk from "important" to **central**.

OpenAI is already implementing concepts extremely close to parts of Resume Gate:

- approval state bound to durable `RunState`;
- tool identity and invocation ledgers;
- guardrails that rerun after resume;
- fail-closed behavior around mismatched tool identity;
- current trusted configuration for sensitive sandbox authority.

LangGraph makes it easy to place domain validation directly after an interrupt, even if it does less automatically at the generic runtime level.

The likely future is that each major runtime keeps improving its own local resume safety.

## What still looks independent

The residual independent capability is not "resume validation."

It is:

> **one external validity / authority contract applied consistently across heterogeneous agent runtimes.**

That starts to look closer to a policy/control-plane product than a checkpoint product.

Possible value exists when an organization has:

- multiple agent frameworks;
- shared policy/identity systems;
- approvals whose validity changes independently of agent state;
- long-running workflows spanning deployments;
- a need for one audit language across them.

For a team with one framework and a few tools, native controls are likely sufficient.

## Test verdict

### Hypothesis tested

> Teams need Resume Gate because safe resume is hard to implement correctly with framework-native controls.

**Result: mostly rejected.**

For the concrete stale-authority case:

- native LangGraph solution is simple;
- native OpenAI solution is first-class and strong.

### Narrower hypothesis that survives

> Organizations operating heterogeneous long-running agents may benefit from a common external validity and authority layer rather than reimplementing equivalent policy glue separately in each framework.

**Status: unproven but technically supported.**

The unchanged Resume Gate validator now runs across LangGraph and OpenAI Agents, but the bakeoff shows that **cross-framework consistency**, not missing native primitives, is the principal remaining differentiator.

## Decision

Do **not** add another framework adapter merely to accumulate integrations.

Do **not** add more resume checks.

Do **not** claim native frameworks cannot solve stale authority.

The next experiment must test whether the surviving cross-framework advantage has real substance.

Without customer interviews, the cheapest falsification is an **enterprise policy portability test**:

1. define one realistic external policy source;
2. enforce the exact same policy on a LangGraph workflow and an OpenAI Agents workflow;
3. implement the best native version in each framework;
4. implement the Resume Gate version once;
5. change the policy while both workflows are parked;
6. compare duplication, policy semantics, audit outputs, failure modes, and maintenance surface.

If Resume Gate does not materially reduce duplicated policy logic or produce materially better cross-runtime guarantees, **stop the product experiment**.

If it does, the product has shifted from "safe resume" toward:

> **temporal policy enforcement for long-running agent execution.**
