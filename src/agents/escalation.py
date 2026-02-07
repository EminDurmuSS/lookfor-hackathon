"""
Escalation Handler + Post-Escalation Session Lock.

Generates structured summary, customer message, and locks the session.
"""

from __future__ import annotations

from datetime import datetime, timezone
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


def _resolve_intent_context(state: dict, escalation_reason: str) -> tuple[str, int, str]:
    """
    Ensure escalation responses always carry intent/agent metadata.
    Falls back deterministically from escalation reason when missing.
    """
    ticket_category = state.get("ticket_category")
    current_agent = state.get("current_agent")
    intent_confidence = state.get("intent_confidence")

    if not ticket_category:
        if escalation_reason == "health_concern":
            ticket_category = "NO_EFFECT"
        elif escalation_reason == "reship":
            ticket_category = "WRONG_MISSING"
        elif escalation_reason == "chargeback_risk":
            ticket_category = "REFUND"
        else:
            ticket_category = "GENERAL"

    if not current_agent:
        if ticket_category in {"WISMO"}:
            current_agent = "wismo_agent"
        elif ticket_category in {"WRONG_MISSING", "NO_EFFECT", "REFUND"}:
            current_agent = "issue_agent"
        elif ticket_category in {"ORDER_MODIFY", "SUBSCRIPTION", "DISCOUNT", "POSITIVE"}:
            current_agent = "account_agent"
        else:
            current_agent = "supervisor"

    try:
        parsed_conf = int(intent_confidence)
    except (TypeError, ValueError):
        parsed_conf = 100

    return ticket_category, parsed_conf, current_agent


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
    ticket_category, intent_confidence, current_agent = _resolve_intent_context(state, category)
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
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    if category == "health_concern":
        customer_message = (
            f"Hey {first_name}, I'm really sorry this happened. Please stop using the product "
            f"right away and follow your healthcare provider's advice. "
            f"Because this is a health concern, I'm looping in Monica, our Head of CS, now "
            f"so she can take this forward urgently.\n\nCaz"
        )
    else:
        customer_message = (
            f"Hey {first_name}, to make sure you get the best help, "
            f"I'm looping in Monica, who is our Head of CS. "
            f"She'll take the conversation from here.\n\nCaz"
        )

    response = {
        "messages": [AIMessage(content=customer_message)],
        "is_escalated": True,
        "ticket_category": ticket_category,
        "intent_confidence": intent_confidence,
        "current_agent": current_agent,
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
