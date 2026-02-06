"""
Supervisor Agent + Cross-Agent Handoff Router.

Supervisor Agent:
- Fallback router for low-confidence intent classification
- Uses LLM to analyze and route to appropriate agent

Handoff Router:
- Parses HANDOFF instructions from agents and re-routes to the target agent
- Includes loop prevention (max 1 handoff per turn)
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from src.config import get_current_context, sonnet_llm
from src.prompts.supervisor_prompt import build_supervisor_prompt


# ─── Supervisor Agent ────────────────────────────────────────────────────────

async def supervisor_node(state: dict) -> dict:
    """Supervisor agent for low-confidence routing or complex queries."""
    ctx = get_current_context()
    prompt = build_supervisor_prompt(
        first_name=state.get("customer_first_name", "there"),
        last_name=state.get("customer_last_name", ""),
        email=state.get("customer_email", ""),
        customer_shopify_id=state.get("customer_shopify_id", ""),
        current_date=ctx["current_date"],
        day_of_week=ctx["day_of_week"],
    )

    # Get the last customer message
    customer_msg = ""
    for m in reversed(state.get("messages", [])):
        if hasattr(m, "type") and m.type == "human":
            customer_msg = m.content
            break

    full_prompt = f"{prompt}\n\nCustomer message: {customer_msg}"

    result = await sonnet_llm.ainvoke(full_prompt)
    response_text = result.content.strip()

    # Parse the supervisor response
    lines = response_text.split("\n")
    route_to = "respond_direct"
    reason = ""
    direct_response = ""

    for line in lines:
        line = line.strip()
        if line.startswith("ROUTE:"):
            route_to = line.replace("ROUTE:", "").strip().lower()
        elif line.startswith("REASON:"):
            reason = line.replace("REASON:", "").strip()
        elif line.startswith("RESPONSE:"):
            direct_response = line.replace("RESPONSE:", "").strip()

    # Map route names
    route_map = {
        "wismo_agent": "wismo_agent",
        "issue_agent": "issue_agent",
        "account_agent": "account_agent",
        "respond_direct": "respond_direct",
        "escalate": "escalate",
    }
    route_to = route_map.get(route_to, "respond_direct")

    output = {
        "current_agent": "supervisor",
        "supervisor_route_decision": route_to,
        "agent_reasoning": [f"SUPERVISOR: Routing to {route_to} — {reason}"],
    }

    # If responding directly, add the message
    if route_to == "respond_direct" and direct_response:
        output["messages"] = [AIMessage(content=direct_response)]
    elif route_to == "respond_direct":
        # Default greeting response
        first_name = state.get("customer_first_name", "there")
        output["messages"] = [AIMessage(
            content=f"Hey {first_name}! Thanks for reaching out. How can I help you today? 💛\n\nCaz"
        )]

    # If escalating, set the flag
    if route_to == "escalate":
        output["escalation_reason"] = "uncertain"

    return output


def supervisor_route(state: dict) -> str:
    """Route decision from supervisor node."""
    decision = state.get("supervisor_route_decision", "respond_direct")
    valid = {"wismo_agent", "issue_agent", "account_agent", "respond_direct", "escalate"}
    return decision if decision in valid else "respond_direct"


# ─── Handoff Router ──────────────────────────────────────────────────────────

def handoff_router_node(state: dict) -> dict:
    """Parse HANDOFF instruction and prepare re-routing state."""
    last_msg = state["messages"][-1].content.strip()
    count = state.get("handoff_count_this_turn", 0)

    if count >= 1:
        # Loop prevention — fall back to supervisor
        return {
            "handoff_target": "supervisor",
            "current_agent": "supervisor",
            "handoff_count_this_turn": count,
            "agent_reasoning": [
                "HANDOFF: Max handoffs per turn reached, falling back to supervisor"
            ],
        }

    if last_msg.startswith("HANDOFF:"):
        parts = last_msg.split("|")
        target = parts[0].replace("HANDOFF:", "").strip().lower()
        reason = ""
        if len(parts) > 1:
            reason = parts[1].replace("REASON:", "").strip()

        valid = {"wismo_agent", "issue_agent", "account_agent"}
        if target not in valid:
            target = "supervisor"

        return {
            "handoff_target": target,
            "current_agent": target,
            "handoff_count_this_turn": count + 1,
            "agent_reasoning": [
                f"HANDOFF: {state.get('current_agent', '?')} → {target} ({reason})"
            ],
        }

    # Not a valid handoff — fallback
    return {
        "handoff_target": "supervisor",
        "current_agent": "supervisor",
        "handoff_count_this_turn": count,
        "agent_reasoning": [
            "HANDOFF: Invalid format, falling back to supervisor"
        ],
    }