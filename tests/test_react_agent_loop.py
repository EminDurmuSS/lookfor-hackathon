"""
Tests for the internal ReAct loop guardrail state behavior.
"""

import asyncio

from langchain_core.messages import AIMessage, HumanMessage

from src.agents.react_agents import _run_react_agent


class _DiscountTool:
    name = "shopify_create_discount_code"

    async def ainvoke(self, _args):
        return {"success": True, "data": {"code": "DISCOUNT_LF_TEST123"}}


class _StubLLM:
    def __init__(self):
        self._turn = 0

    def bind_tools(self, _tools):
        return self

    async def ainvoke(self, _conversation):
        self._turn += 1
        if self._turn == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "shopify_create_discount_code",
                        "args": {"type": "percentage", "value": 0.10, "duration": 48},
                    },
                    {
                        "id": "call_2",
                        "name": "shopify_create_discount_code",
                        "args": {"type": "percentage", "value": 0.10, "duration": 48},
                    },
                ],
            )
        return AIMessage(content="Done.\n\nCaz")


def test_react_loop_uses_live_guardrail_state_for_discount_limit():
    state = {
        "messages": [HumanMessage(content="Can I get a discount?")],
        "tool_calls_log": [],
        "actions_taken": [],
        "discount_code_created": False,
        "discount_code_created_count": 0,
    }

    result = asyncio.run(
        _run_react_agent(
            llm=_StubLLM(),
            tools=[_DiscountTool()],
            system_prompt="You are a support agent.",
            state=state,
            max_iterations=2,
        )
    )

    assert len(result["tool_calls_log"]) == 2
    assert result["tool_calls_log"][0]["result"]["success"] is True
    assert result["tool_calls_log"][1]["result"]["success"] is False
    assert "Already created a discount code" in result["tool_calls_log"][1]["result"]["error"]
    assert result["discount_code_created"] is True
    assert result["discount_code_created_count"] == 1
