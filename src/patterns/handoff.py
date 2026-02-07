"""
Cross-agent handoff router.
Parses HANDOFF instructions from agents and re-routes to the target agent.
Includes loop prevention (max 1 handoff per turn).
"""

from __future__ import annotations

import re

from langchain_core.messages import AIMessage, RemoveMessage


# Patterns to detect and clean embedded internal commands
_INTERNAL_COMMAND_PATTERNS = [
    re.compile(r"\bHANDOFF:\s*\w+[^\n]*", re.IGNORECASE),
    re.compile(r"\bESCALATE:\s*\w+[^\n]*", re.IGNORECASE),
    re.compile(r"\bTRANSFER:\s*\w+[^\n]*", re.IGNORECASE),
]


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

    # Clean embedded commands from non-handoff messages (prevent info leaks)
    cleaned_msg = last_msg
    for pattern in _INTERNAL_COMMAND_PATTERNS:
        cleaned_msg = pattern.sub("", cleaned_msg)
    cleaned_msg = cleaned_msg.strip()

    # If message was cleaned, update it
    message_update = {}
    if cleaned_msg != last_msg and last_msg_id:
        message_update = {
            "messages": [
                RemoveMessage(id=last_msg_id),
                AIMessage(content=cleaned_msg, id=last_msg_id),
            ],
            "agent_reasoning": [
                "HANDOFF: Cleaned embedded internal commands from response"
            ],
        }

    return {
        **message_update,
        "handoff_target": "supervisor",
        "current_agent": "supervisor",
        "handoff_count_this_turn": count,
        "agent_reasoning": message_update.get("agent_reasoning", [
            "HANDOFF: Invalid format, falling back to supervisor"
        ]),
    }

