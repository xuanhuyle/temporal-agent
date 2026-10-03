from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

agents = pytest.importorskip("agents")

from agents import Agent, RunState, function_tool
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call

from resume_gate import (
    GuardedOpenAIRunner,
    InMemoryManifestStore,
    ResumeGateRefused,
    Verdict,
)


def _build_agent(executions: list[int]):
    @function_tool(name_override="refund_customer", needs_approval=True)
    def refund_customer(amount: int) -> str:
        """Refund a customer order."""
        executions.append(amount)
        return f"refunded:{amount}"

    model = ScriptedModel(
        [
            ModelStep(
                output=[
                    function_call(
                        "refund_customer",
                        {"amount": 100},
                        call_id="refund-call-1",
                    )
                ]
            ),
            ModelStep(output=[assistant_message("done")]),
        ]
    )
    agent = Agent(
        name="refund-agent",
        model=model,
        tools=[refund_customer],
    )
    return agent, refund_customer


def _authority_environment():
    return {
        "policy_version": "refund-policy-v1",
        "authorities": [
            {
                "id": "approval-381",
                "scope": "refund:order-77",
                "status": "active",
                "policy_version": "refund-policy-v1",
            }
        ],
    }


async def _pause_and_serialize(runner, agent):
    first = await runner.run(agent, "refund the customer")
    assert len(first.interruptions) == 1

    state = first.to_state()
    state.approve(first.interruptions[0])

    serialized = state.to_string()
    restored = await RunState.from_string(agent, serialized)
    assert len(restored.get_interruptions()) == 1
    return restored


def test_openai_approved_runstate_is_blocked_if_authority_revoked_before_resume():
    executions: list[int] = []
    agent, _tool = _build_agent(executions)
    environment = _authority_environment()

    def live_context(state, current_agent):
        return deepcopy(environment)

    runner = GuardedOpenAIRunner(
        store=InMemoryManifestStore(),
        context_provider=live_context,
    )

    async def scenario():
        restored = await _pause_and_serialize(runner, agent)

        # The human approval is already embedded in the serialized RunState.
        # Current authority changes while the run is parked.
        environment["authorities"][0]["status"] = "revoked"

        with pytest.raises(ResumeGateRefused) as exc:
            await runner.run(agent, restored)
        return exc.value

    refused = asyncio.run(scenario())

    assert refused.decision.result.verdict is Verdict.BLOCK
    assert "AUTHORITY_NOT_ACTIVE" in {
        issue.code for issue in refused.decision.result.issues
    }
    assert executions == []


def test_openai_same_serialized_runstate_executes_if_current_authority_still_valid():
    executions: list[int] = []
    agent, _tool = _build_agent(executions)
    environment = _authority_environment()

    def live_context(state, current_agent):
        return deepcopy(environment)

    store = InMemoryManifestStore()
    runner = GuardedOpenAIRunner(store=store, context_provider=live_context)

    async def scenario():
        restored = await _pause_and_serialize(runner, agent)
        return await runner.run(agent, restored)

    result = asyncio.run(scenario())

    assert result.final_output == "done"
    assert executions == [100]


def test_openai_tool_removed_after_pause_is_detected_without_context_provider():
    executions: list[int] = []
    agent, _tool = _build_agent(executions)
    runner = GuardedOpenAIRunner(store=InMemoryManifestStore())

    async def scenario():
        restored = await _pause_and_serialize(runner, agent)

        # Same Agent object, new deployment/runtime surface: the tool is no
        # longer available. Resume Gate discovers the static tool drift.
        agent.tools = []

        with pytest.raises(ResumeGateRefused) as exc:
            await runner.run(agent, restored)
        return exc.value

    refused = asyncio.run(scenario())

    assert refused.decision.result.verdict is Verdict.BLOCK
    assert "TOOL_REMOVED" in {
        issue.code for issue in refused.decision.result.issues
    }
    assert executions == []


def test_openai_tool_schema_change_requires_revalidation():
    executions: list[int] = []
    agent, _tool = _build_agent(executions)
    runner = GuardedOpenAIRunner(store=InMemoryManifestStore())

    @function_tool(name_override="refund_customer", needs_approval=True)
    def changed_refund_customer(amount: int, reason: str = "customer_request") -> str:
        """Refund a customer order with an explicit reason."""
        executions.append(amount)
        return f"refunded:{amount}:{reason}"

    async def scenario():
        restored = await _pause_and_serialize(runner, agent)
        agent.tools = [changed_refund_customer]

        with pytest.raises(ResumeGateRefused) as exc:
            await runner.run(agent, restored)
        return exc.value

    refused = asyncio.run(scenario())

    assert refused.decision.result.verdict is Verdict.REVALIDATE
    assert "TOOL_VERSION_CHANGED" in {
        issue.code for issue in refused.decision.result.issues
    }
    assert executions == []


def test_openai_resume_fails_closed_for_state_created_without_gate_manifest():
    executions: list[int] = []
    agent, _tool = _build_agent(executions)

    async def scenario():
        from agents import Runner

        first = await Runner.run(agent, "refund the customer")
        state = first.to_state()
        state.approve(first.interruptions[0])
        restored = await RunState.from_string(agent, state.to_string())

        guarded = GuardedOpenAIRunner(store=InMemoryManifestStore())
        with pytest.raises(ResumeGateRefused) as exc:
            await guarded.run(agent, restored)
        return exc.value

    refused = asyncio.run(scenario())

    assert refused.decision.result.verdict is Verdict.BLOCK
    assert "MANIFEST_MISSING" in {
        issue.code for issue in refused.decision.result.issues
    }
    assert executions == []
