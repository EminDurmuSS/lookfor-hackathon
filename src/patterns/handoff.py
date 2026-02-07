"""
Cross-agent handoff router.
Parses HANDOFF instructions from agents and re-routes to the target agent.
Includes loop prevention (max 1 handoff per turn).
"""

from __future__ import annotations

from langchain_core.messages import RemoveMessage


def handoff_router_node(state: dict) -> dict:
    """Parse HANDOFF instruction and prepare re-routing state."""
    last_message = state["messages"][-1]
    last_msg = (last_message.content or "").strip()
    last_msg_id = getattr(last_message, "id", None)
    count = state.get("handoff_count_this_turn", 0)

    remove_update = {}
    if last_msg.startswith("HANDOFF:") and isinstance(last_msg_id, str) and last_msg_id:
        remove_update = {"messages": [RemoveMessage(id=last_msg_id)]}

    if count >= 1:
        return {
            **remove_update,
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
            **remove_update,
            "handoff_target": target,
            "current_agent": target,
            "handoff_count_this_turn": count + 1,
            "agent_reasoning": [
                f"HANDOFF: {state.get('current_agent', '?')} -> {target} ({reason})"
            ],
        }

    return {
        "handoff_target": "supervisor",
        "current_agent": "supervisor",
        "handoff_count_this_turn": count,
        "agent_reasoning": [
            "HANDOFF: Invalid format, falling back to supervisor"
        ],
    }
