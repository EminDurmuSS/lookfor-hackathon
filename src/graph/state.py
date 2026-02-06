"""
State definition for the multi-agent customer support graph (v3.0).
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

from langgraph.graph.message import add_messages


# Using TypedDict for LangGraph compatibility
from typing_extensions import TypedDict


class CustomerSupportState(TypedDict, total=False):
    """Complete state schema for every node in the graph."""

    # ── Core ─────────────────────────────────────────────────────────────────
    messages: Annotated[list, add_messages]

    # ── Customer Info (set at session start) ─────────────────────────────────
    customer_email: str
    customer_first_name: str
    customer_last_name: str
    customer_shopify_id: str  # "gid://shopify/Customer/…"

    # ── Intent Classification ────────────────────────────────────────────────
    ticket_category: str  # WISMO, WRONG_MISSING, NO_EFFECT, …
    intent_confidence: int  # 0-100
    intent_shifted: bool  # multi-turn intent shift detected

    # ── Routing ──────────────────────────────────────────────────────────────
    current_agent: str  # supervisor | wismo_agent | issue_agent | account_agent

    # ── Shared Context ───────────────────────────────────────────────────────
    order_details: Optional[dict]
    current_order_id: Optional[str]  # GID
    current_order_number: Optional[str]  # #XXXXX
    subscription_status: Optional[dict]
    current_subscription_id: Optional[str]

    # ── Guardrails State ─────────────────────────────────────────────────────
    input_blocked: bool
    override_response: Optional[str]
    pii_redacted: bool
    output_guardrail_passed: bool
    output_guardrail_issues: list[str]
    discount_code_created: bool  # max 1 per session
    pending_refund_amount: Optional[float]
    order_total: Optional[float]
    flag_escalation_risk: bool  # aggressive language
    flag_health_concern: bool  # health / allergy mention
    is_handoff: bool  # agent requested cross-agent handoff
    handoff_target: Optional[str]
    handoff_count_this_turn: int

    # ── Reflection State ─────────────────────────────────────────────────────
    reflection_passed: bool
    reflection_feedback: Optional[str]
    reflection_rule_violated: Optional[str]
    reflection_suggested_fix: Optional[str]
    was_revised: bool

    # ── Escalation ───────────────────────────────────────────────────────────
    is_escalated: bool
    escalation_payload: Optional[dict]
    escalation_reason: Optional[str]

    # ── Tracing / Observability ──────────────────────────────────────────────
    tool_calls_log: list[dict]
    actions_taken: list[str]
    agent_reasoning: Annotated[list[str], lambda a, b: (a or []) + (b or [])]