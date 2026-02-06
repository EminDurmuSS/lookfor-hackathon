"""
Escalation Handler + Post-Escalation Session Lock.

Generates structured summary, customer message, and locks the session.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from langchain_core.messages import AIMessage
from pydantic import BaseModel

from src.config import sonnet_llm


class EscalationPayload(BaseModel):
    customer_name: str
    customer_email: str
    order_id: Optional[str] = None
    subscription_id: Optional[str] = None
    category: str
    priority: str = "normal"
    summary: str
    actions_taken: list[str]
    conversation_history: list[str]
    escalated_to: str = "Monica - Head of CS"
    created_at: str = ""


_HIGH_PRIORITY = {"health_concern", "chargeback_risk", "billing_error", "technical_error"}


async def escalation_handler_node(state: dict) -> dict:
    """Build structured escalation payload + customer message."""
    # Generate summary with Sonnet
    msgs = [m.content for m in state.get("messages", []) if hasattr(m, "content")]
    summary_result = await sonnet_llm.ainvoke(
        "Summarize this customer support interaction in 2-3 sentences "
        "for handoff to a human agent. Include: what the customer wants, "
        "what was tried, and why it's being escalated.\n\n"
        f"Messages:\n{msgs}"
    )

    category = state.get("escalation_reason", "uncertain")
    priority = "high" if category in _HIGH_PRIORITY else "normal"
    first_name = state.get("customer_first_name", "there")

    payload = EscalationPayload(
        customer_name=f"{state.get('customer_first_name', '')} {state.get('customer_last_name', '')}".strip(),
        customer_email=state.get("customer_email", ""),
        order_id=state.get("current_order_id"),
        subscription_id=state.get("current_subscription_id"),
        category=category,
        priority=priority,
        summary=summary_result.content,
        actions_taken=state.get("actions_taken", []),
        conversation_history=msgs[-10:],  # last 10 messages
        created_at=datetime.utcnow().isoformat(),
    )

    customer_message = (
        f"Hey {first_name}, to make sure you get the best help, "
        f"I'm looping in Monica, who is our Head of CS. "
        f"She'll take the conversation from here. 💛\n\nCaz"
    )

    return {
        "messages": [AIMessage(content=customer_message)],
        "is_escalated": True,
        "escalation_payload": payload.model_dump(),
        "agent_reasoning": [
            f"ESCALATED [{priority.upper()}]: {category} — "
            f"{payload.summary[:120]}"
        ],
    }


async def post_escalation_node(state: dict) -> dict:
    """Auto-response for messages after escalation. Session is locked."""
    first_name = state.get("customer_first_name", "there")
    return {
        "messages": [
            AIMessage(
                content=(
                    f"Hey {first_name}, your issue has been escalated "
                    f"to Monica, our Head of CS. She'll be following up "
                    f"with you directly. Please hang tight! 💛\n\nCaz"
                )
            )
        ],
        "agent_reasoning": ["SESSION LOCKED: Post-escalation auto-response"],
    }