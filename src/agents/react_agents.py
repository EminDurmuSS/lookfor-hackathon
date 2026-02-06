"""
ReAct Sub-Agent factories.

Each agent gets a dynamically-built system prompt injected with customer context
and current date/day. We use LangGraph's create_react_agent for the reasoning loop.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage

from src.config import get_current_context, sonnet_llm
from src.prompts.account_prompt import build_account_prompt
from src.prompts.issue_prompt import build_issue_prompt
from src.prompts.wismo_prompt import build_wismo_prompt
from src.tools.tool_groups import account_tools, issue_tools, wismo_tools


def _build_system_message(builder_fn, state: dict) -> str:
    """Build a system prompt string from state + current context."""
    ctx = get_current_context()
    return builder_fn(
        first_name=state.get("customer_first_name", "there"),
        last_name=state.get("customer_last_name", ""),
        email=state.get("customer_email", ""),
        customer_shopify_id=state.get("customer_shopify_id", ""),
        current_date=ctx["current_date"],
        day_of_week=ctx["day_of_week"],
        wait_promise=ctx["wait_promise"],
    )


# ─── Thin wrappers that invoke the LLM with tools in a ReAct loop ───────────
# We use the model.bind_tools + manual loop approach for full control.

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
import json


async def _run_react_agent(
    llm,
    tools: list,
    system_prompt: str,
    state: dict,
    max_iterations: int = 6,
) -> dict:
    """
    Manual ReAct loop: system prompt → LLM (with tools bound) → tool calls → observe → repeat.
    Returns dict with messages, tool_calls_log, actions_taken, agent_reasoning.
    """
    tool_map = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    # Build conversation: system + all messages
    conversation = [SystemMessage(content=system_prompt)]
    for m in state.get("messages", []):
        conversation.append(m)

    tool_calls_log = list(state.get("tool_calls_log") or [])
    actions_taken = list(state.get("actions_taken") or [])
    reasoning = []

    for iteration in range(max_iterations):
        response = await llm_with_tools.ainvoke(conversation)
        conversation.append(response)

        # If no tool calls → we have the final answer
        if not response.tool_calls:
            reasoning.append(
                f"ReAct iteration {iteration + 1}: Final response generated"
            )
            return {
                "messages": [AIMessage(content=response.content)],
                "tool_calls_log": tool_calls_log,
                "actions_taken": actions_taken,
                "agent_reasoning": reasoning,
            }

        # Process tool calls
        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            reasoning.append(
                f"ReAct iteration {iteration + 1}: Calling {tool_name}({json.dumps(tool_args, default=str)[:200]})"
            )

            if tool_name in tool_map:
                try:
                    tool_result = await tool_map[tool_name].ainvoke(tool_args)
                except Exception as exc:
                    tool_result = {"success": False, "error": str(exc)}
            else:
                tool_result = {"success": False, "error": f"Unknown tool: {tool_name}"}

            # Log
            log_entry = {
                "tool_name": tool_name,
                "params": tool_args,
                "result": tool_result if isinstance(tool_result, dict) else str(tool_result),
            }
            tool_calls_log.append(log_entry)

            # Track actions
            destructive = {"shopify_cancel_order", "shopify_refund_order",
                           "shopify_create_store_credit", "shopify_create_discount_code",
                           "shopify_update_order_shipping_address", "shopify_create_return",
                           "skio_cancel_subscription", "skio_pause_subscription",
                           "skio_skip_next_order_subscription", "skio_unpause_subscription"}
            if tool_name in destructive:
                result_status = "success" if (isinstance(tool_result, dict) and tool_result.get("success")) else "failed"
                actions_taken.append(f"{tool_name}: {result_status}")

            # Add tool message to conversation
            result_str = json.dumps(tool_result, default=str) if isinstance(tool_result, dict) else str(tool_result)
            conversation.append(
                ToolMessage(content=result_str, tool_call_id=tc["id"])
            )

    # Max iterations reached — return last response
    last_ai = None
    for m in reversed(conversation):
        if isinstance(m, AIMessage) and m.content:
            last_ai = m
            break

    content = last_ai.content if last_ai else "I apologize, but I need a moment. Let me look into this further.\n\nCaz"
    return {
        "messages": [AIMessage(content=content)],
        "tool_calls_log": tool_calls_log,
        "actions_taken": actions_taken,
        "agent_reasoning": reasoning,
    }


# ─── Public Agent Node Functions ─────────────────────────────────────────────

async def wismo_agent_node(state: dict) -> dict:
    """WISMO Agent — shipping delay specialist."""
    prompt = _build_system_message(build_wismo_prompt, state)
    result = await _run_react_agent(sonnet_llm, wismo_tools, prompt, state)
    result["current_agent"] = "wismo_agent"
    return result


async def issue_agent_node(state: dict) -> dict:
    """Issue Agent — wrong/missing items, product issues, refunds."""
    prompt = _build_system_message(build_issue_prompt, state)
    result = await _run_react_agent(sonnet_llm, issue_tools, prompt, state)
    result["current_agent"] = "issue_agent"
    return result


async def account_agent_node(state: dict) -> dict:
    """Account Agent — cancellations, address, subscriptions, discounts, positive."""
    prompt = _build_system_message(build_account_prompt, state)
    result = await _run_react_agent(sonnet_llm, account_tools, prompt, state)
    result["current_agent"] = "account_agent"

    # Track discount code creation
    for log in (result.get("tool_calls_log") or []):
        if log.get("tool_name") == "shopify_create_discount_code":
            r = log.get("result", {})
            if isinstance(r, dict) and r.get("success"):
                result["discount_code_created"] = True

    return result