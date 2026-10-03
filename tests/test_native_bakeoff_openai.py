from __future__ import annotations

import asyncio

import pytest

agents = pytest.importorskip("agents")

from agents import (
    Agent,
    RunConfig,
    RunState,
    Runner,
    ToolExecutionConfig,
    ToolGuardrailFunctionOutput,
    function_tool,
    tool_input_guardrail,
)
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call


def test_native_openai_guardrail_rechecks_authority_after_serialized_approval_resume():
    environment = {"authority_active": True}
    executions: list[int] = []

    @tool_input_guardrail
    def current_authority(_data):
        if not environment["authority_active"]:
            return ToolGuardrailFunctionOutput.reject_content("authority revoked")
        return ToolGuardrailFunctionOutput.allow()

    @function_tool(
        name_override="refund_customer",
        needs_approval=True,
        tool_input_guardrails=[current_authority],
    )
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
                        call_id="refund-native-1",
                    )
                ]
            ),
            ModelStep(output=[assistant_message("blocked")]),
        ]
    )
    agent = Agent(name="native-openai", model=model, tools=[refund_customer])
    run_config = RunConfig(
        tool_execution=ToolExecutionConfig(
            pre_approval_tool_input_guardrails=True
        )
    )

    async def scenario():
        first = await Runner.run(
            agent,
            "refund the customer",
            run_config=run_config,
        )
        assert len(first.interruptions) == 1

        state = first.to_state()
        state.approve(first.interruptions[0])
        restored = await RunState.from_string(agent, state.to_string())

        environment["authority_active"] = False

        resumed = await Runner.run(
            agent,
            restored,
            run_config=run_config,
        )
        return resumed

    result = asyncio.run(scenario())

    assert executions == []
    assert result.final_output == "blocked"


def test_native_openai_missing_tool_does_not_execute_removed_tool():
    executions: list[int] = []

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
                        call_id="refund-native-2",
                    )
                ]
            )
        ]
    )
    agent = Agent(name="native-openai-missing-tool", model=model, tools=[refund_customer])

    async def scenario():
        first = await Runner.run(agent, "refund the customer")
        state = first.to_state()
        state.approve(first.interruptions[0])
        restored = await RunState.from_string(agent, state.to_string())

        agent.tools = []

        with pytest.raises(Exception):
            await Runner.run(agent, restored)

    asyncio.run(scenario())
    assert executions == []
