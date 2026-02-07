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


def _resolve_order_id(state: dict) -> Optional[str]:
    """Resolve order GID from state first, then recent tool calls."""
    current = state.get("current_order_id")
    if isinstance(current, str) and current.startswith("gid://shopify/Order/"):
        return current

    for log in reversed(state.get("tool_calls_log") or []):
        params = log.get("params")
        if isinstance(params, dict):
            order_id = params.get("orderId")
            if isinstance(order_id, str) and order_id.startswith("gid://shopify/Order/"):
                return order_id

        result = log.get("result")
        if not isinstance(result, dict):
            continue
        data = result.get("data", {})
        if isinstance(data, dict):
            order_gid = data.get("id")
            if isinstance(order_gid, str) and order_gid.startswith("gid://shopify/Order/"):
                return order_gid

            orders = data.get("orders")
            if isinstance(orders, list):
                for order in orders:
                    if isinstance(order, dict):
                        order_gid = order.get("id")
                        if isinstance(order_gid, str) and order_gid.startswith("gid://shopify/Order/"):
                            return order_gid
    return None


def _resolve_subscription_id(state: dict) -> Optional[str]:
    """Resolve subscription id from state first, then recent tool calls."""
    current = state.get("current_subscription_id")
    if isinstance(current, str) and current:
        return current

    for log in reversed(state.get("tool_calls_log") or []):
        params = log.get("params")
        if isinstance(params, dict):
            sub_id = params.get("subscriptionId")
            if isinstance(sub_id, str) and sub_id:
                return sub_id

        result = log.get("result")
        if not isinstance(result, dict):
            continue
        data = result.get("data", {})
        if isinstance(data, dict):
            sub_id = data.get("subscriptionId")
            if isinstance(sub_id, str) and sub_id:
                return sub_id
    return None


def _resolve_draft_order_id(state: dict) -> Optional[str]:
    """Resolve created draft order id from tool call logs."""
    for log in reversed(state.get("tool_calls_log") or []):
        if log.get("tool_name") != "shopify_create_draft_order":
            continue
        result = log.get("result", {})
        if not isinstance(result, dict) or not result.get("success"):
            continue
        data = result.get("data", {})
        if not isinstance(data, dict):
            continue
        # API returns data.draftOrderId; keep data.id fallback for compatibility.
        draft_id = data.get("draftOrderId") or data.get("id")
        if isinstance(draft_id, str) and draft_id:
            return draft_id
    return None


async def escalation_handler_node(state: dict) -> dict:
    """Build structured escalation payload + customer message."""

    def _clean_for_summary(text: str) -> str:
        lines = text.split("\n")
        cleaned = [
            line
            for line in lines
            if not line.strip().lower().startswith(
                ("thought:", "action:", "observation:", "escalate:", "handoff:")
            )
        ]
        return "\n".join(cleaned).strip()

    raw_msgs = [m.content for m in state.get("messages", []) if hasattr(m, "content")]
    msgs = [_clean_for_summary(m) for m in raw_msgs]
    msgs = [m for m in msgs if m]

    summary_result = await sonnet_llm.ainvoke(
        "Summarize this customer support interaction in 2-3 sentences "
        "for handoff to a human agent. Include: what the customer wants, "
        "what was tried, and why it's being escalated.\n\n"
        f"Messages:\n{msgs}"
    )

    category = state.get("escalation_reason", "uncertain")
    priority = "high" if category in _HIGH_PRIORITY else "normal"
    first_name = state.get("customer_first_name", "there")
    resolved_order_id = _resolve_order_id(state)
    resolved_subscription_id = _resolve_subscription_id(state)

    payload = EscalationPayload(
        customer_name=f"{state.get('customer_first_name', '')} {state.get('customer_last_name', '')}".strip(),
        customer_email=state.get("customer_email", ""),
        order_id=resolved_order_id,
        subscription_id=resolved_subscription_id,
        category=category,
        priority=priority,
        summary=summary_result.content,
        actions_taken=state.get("actions_taken", []),
        conversation_history=msgs[-10:],
        created_at=datetime.utcnow().isoformat(),
    )

    draft_id = _resolve_draft_order_id(state)
    if draft_id:
        payload.summary += (
            f"\n\n**Draft Order Created:** {draft_id} - ready for review and completion."
        )

    customer_message = (
        f"Hey {first_name}, to make sure you get the best help, "
        f"I'm looping in Monica, who is our Head of CS. "
        f"She'll take the conversation from here.\n\nCaz"
    )

    response = {
        "messages": [AIMessage(content=customer_message)],
        "is_escalated": True,
        "escalation_payload": payload.model_dump(),
        "agent_reasoning": [
            f"ESCALATED [{priority.upper()}]: {category} - "
            f"{payload.summary[:120]}"
        ],
    }
    if resolved_order_id:
        response["current_order_id"] = resolved_order_id
    if resolved_subscription_id:
        response["current_subscription_id"] = resolved_subscription_id

    return response


async def post_escalation_node(state: dict) -> dict:
    """Auto-response for messages after escalation. Session is locked."""
    first_name = state.get("customer_first_name", "there")
    return {
        "messages": [
            AIMessage(
                content=(
                    f"Hey {first_name}, your issue has been escalated "
                    f"to Monica, our Head of CS. She'll be following up "
                    f"with you directly. Please hang tight!\n\nCaz"
                )
            )
        ],
        "agent_reasoning": ["SESSION LOCKED: Post-escalation auto-response"],
    }
