"""
Complete LangGraph graph for the multi-agent customer-support flow.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agents.escalation import escalation_handler_node, post_escalation_node
from src.agents.react_agents import (
    account_agent_node,
    issue_agent_node,
    wismo_agent_node,
)
from src.agents.supervisor import supervisor_node, supervisor_route
from src.graph.state import CustomerSupportState
from src.patterns.guardrails import input_guardrails_node, output_guardrails_node
from src.patterns.handoff import handoff_router_node
from src.patterns.intent_classifier import (
    intent_classifier_node,
    intent_shift_check_node,
    route_after_shift_check,
    route_by_confidence,
)
from src.patterns.reflection import reflection_validator_node, revise_response_node


async def escalation_lock_node(state: dict) -> dict:
    """Check escalation lock and reset per-turn volatile flags."""
    turn_reset = {
        "was_revised": False,
        "handoff_count_this_turn": 0,
        "output_guardrail_passed": True,
        "output_guardrail_issues": [],
        "is_handoff": False,
        "is_escalation": False,
        "reflection_passed": True,
        "reflection_feedback": None,
        "reflection_rule_violated": None,
        "reflection_suggested_fix": None,
        "input_blocked": False,
        "override_response": None,
        "flag_escalation_risk": False,
        "flag_chargeback_threat": False,
        "flag_health_concern": False,
        "flag_entire_order_wrong": False,
        "flag_reship_acceptance": False,
        "handoff_target": None,
        "intent_shifted": False,
    }

    if state.get("is_escalated"):
        return {
            **turn_reset,
            "is_escalated": True,
            "agent_reasoning": ["ESCALATION LOCK: Session is locked"],
        }
    return {
        **turn_reset,
        "agent_reasoning": ["ESCALATION LOCK: Session active"],
    }


def _route_escalation_lock(state: dict) -> str:
    if state.get("is_escalated"):
        return "post_escalation"
    return "input_guardrails"


def _route_after_input_guardrails(state: dict) -> str:
    if state.get("input_blocked"):
        return "__end__"

    if state.get("flag_health_concern"):
        return "auto_escalate_health"
    if state.get("flag_chargeback_threat"):
        return "auto_escalate_chargeback"
    if state.get("flag_entire_order_wrong") or state.get("flag_reship_acceptance"):
        return "auto_escalate_reship"

    human_count = sum(
        1 for m in state.get("messages", [])
        if hasattr(m, "type") and m.type == "human"
    )
    if human_count <= 1:
        return "intent_classifier"
    return "intent_shift_check"


async def auto_escalate_health_node(state: dict) -> dict:
    """Immediately escalate health/safety concerns."""
    return {
        "ticket_category": "NO_EFFECT",
        "intent_confidence": int(state.get("intent_confidence") or 100),
        "current_agent": "issue_agent",
        "escalation_reason": "health_concern",
        "agent_reasoning": [
            "AUTO-ESCALATE: Health/safety concern detected in input"
        ],
    }


async def auto_escalate_chargeback_node(state: dict) -> dict:
    """Immediately escalate chargeback threats."""
    return {
        "ticket_category": state.get("ticket_category") or "REFUND",
        "intent_confidence": int(state.get("intent_confidence") or 100),
        "current_agent": state.get("current_agent") or "issue_agent",
        "escalation_reason": "chargeback_risk",
        "agent_reasoning": [
            "AUTO-ESCALATE: Chargeback threat detected in input"
        ],
    }


async def auto_escalate_reship_node(state: dict) -> dict:
    """Immediately escalate deterministic reship-required scenarios."""
    return {
        "ticket_category": "WRONG_MISSING",
        "intent_confidence": int(state.get("intent_confidence") or 100),
        "current_agent": "issue_agent",
        "escalation_reason": "reship",
        "agent_reasoning": [
            "AUTO-ESCALATE: Reship required (entire order wrong or replacement accepted)"
        ],
    }


def _route_after_output_guardrails(state: dict) -> str:
    if state.get("is_escalation"):
        return "escalation_handler"
    if state.get("is_handoff"):
        return "handoff_router"
    if not state.get("output_guardrail_passed", True):
        return "revise_response"
    return "reflection_validator"


def _route_after_reflection(state: dict) -> str:
    if state.get("reflection_passed", True):
        return "__end__"
    if state.get("was_revised"):
        return "__end__"
    return "revise_response"


def _route_after_revision(state: dict) -> str:
    return "output_guardrails_final"


async def output_guardrails_final_node(state: dict) -> dict:
    return output_guardrails_node(state)


def _route_after_handoff(state: dict) -> str:
    target = state.get("handoff_target", "supervisor")
    valid = {"wismo_agent", "issue_agent", "account_agent", "supervisor"}
    return target if target in valid else "supervisor"


def build_graph() -> StateGraph:
    """Construct and compile the full multi-agent graph."""
    graph = StateGraph(CustomerSupportState)

    graph.add_node("escalation_lock", escalation_lock_node)
    graph.add_node("input_guardrails", input_guardrails_node)
    graph.add_node("auto_escalate_health", auto_escalate_health_node)
    graph.add_node("auto_escalate_chargeback", auto_escalate_chargeback_node)
    graph.add_node("auto_escalate_reship", auto_escalate_reship_node)
    graph.add_node("intent_classifier", intent_classifier_node)
    graph.add_node("intent_shift_check", intent_shift_check_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("wismo_agent", wismo_agent_node)
    graph.add_node("issue_agent", issue_agent_node)
    graph.add_node("account_agent", account_agent_node)
    graph.add_node("output_guardrails", output_guardrails_node)
    graph.add_node("output_guardrails_final", output_guardrails_final_node)
    graph.add_node("handoff_router", handoff_router_node)
    graph.add_node("reflection_validator", reflection_validator_node)
    graph.add_node("revise_response", revise_response_node)
    graph.add_node("escalation_handler", escalation_handler_node)
    graph.add_node("post_escalation", post_escalation_node)

    graph.add_edge(START, "escalation_lock")

    graph.add_conditional_edges(
        "escalation_lock",
        _route_escalation_lock,
        {"post_escalation": "post_escalation", "input_guardrails": "input_guardrails"},
    )

    graph.add_conditional_edges(
        "input_guardrails",
        _route_after_input_guardrails,
        {
            "__end__": END,
            "auto_escalate_health": "auto_escalate_health",
            "auto_escalate_chargeback": "auto_escalate_chargeback",
            "auto_escalate_reship": "auto_escalate_reship",
            "intent_classifier": "intent_classifier",
            "intent_shift_check": "intent_shift_check",
        },
    )

    graph.add_edge("auto_escalate_health", "escalation_handler")
    graph.add_edge("auto_escalate_chargeback", "escalation_handler")
    graph.add_edge("auto_escalate_reship", "escalation_handler")

    graph.add_conditional_edges(
        "intent_classifier",
        route_by_confidence,
        {
            "wismo_agent": "wismo_agent",
            "issue_agent": "issue_agent",
            "account_agent": "account_agent",
            "supervisor": "supervisor",
        },
    )

    graph.add_conditional_edges(
        "intent_shift_check",
        route_after_shift_check,
        {
            "wismo_agent": "wismo_agent",
            "issue_agent": "issue_agent",
            "account_agent": "account_agent",
            "supervisor": "supervisor",
        },
    )

    graph.add_conditional_edges(
        "supervisor",
        supervisor_route,
        {
            "wismo_agent": "wismo_agent",
            "issue_agent": "issue_agent",
            "account_agent": "account_agent",
            "respond_direct": "output_guardrails",
            "escalate": "escalation_handler",
        },
    )

    graph.add_edge("wismo_agent", "output_guardrails")
    graph.add_edge("issue_agent", "output_guardrails")
    graph.add_edge("account_agent", "output_guardrails")

    graph.add_conditional_edges(
        "output_guardrails",
        _route_after_output_guardrails,
        {
            "escalation_handler": "escalation_handler",
            "handoff_router": "handoff_router",
            "revise_response": "revise_response",
            "reflection_validator": "reflection_validator",
        },
    )

    graph.add_conditional_edges(
        "handoff_router",
        _route_after_handoff,
        {
            "wismo_agent": "wismo_agent",
            "issue_agent": "issue_agent",
            "account_agent": "account_agent",
            "supervisor": "supervisor",
        },
    )

    graph.add_conditional_edges(
        "reflection_validator",
        _route_after_reflection,
        {"__end__": END, "revise_response": "revise_response"},
    )

    graph.add_edge("revise_response", "output_guardrails_final")
    graph.add_edge("output_guardrails_final", END)
    graph.add_edge("escalation_handler", END)
    graph.add_edge("post_escalation", END)

    return graph


def compile_graph(checkpointer=None):
    """Build, compile, and return the runnable graph with checkpointer."""
    graph = build_graph()
    return graph.compile(checkpointer=checkpointer)
