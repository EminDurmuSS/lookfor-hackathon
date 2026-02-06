"""
Complete LangGraph graph (v3.0) — 7-layer pipeline.

Layer 0: Escalation Lock
Layer 1: Input Guardrails
Layer 2: Intent Classification (+ multi-turn shift detection)
Layer 3: ReAct Agents
Layer 4: Tool Guardrails (inside agents)
Layer 5: Output Guardrails (+ handoff / escalation intercept)
Layer 6: Reflection Validator
Layer 7: Revision (if needed)

Bug fixes applied from code review:
  - Output guardrails fail → populates reflection fields for revise node
  - Revision → output_guardrails → reflection (1-cycle max, tracked by was_revised)
  - Escalation detectable from any agent via ESCALATE: format
  - Escalation lock as first real check (before input guardrails)
  - Handoff loop prevention via handoff_count_this_turn
  - Health/chargeback flags → auto-escalation
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
from src.graph.checkpointer import checkpointer
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


# ═════════════════════════════════════════════════════════════════════════════
# Escalation lock node (Layer 0)
# ═════════════════════════════════════════════════════════════════════════════

async def escalation_lock_node(state: dict) -> dict:
    """Check if session is already escalated. If so, skip everything."""
    if state.get("is_escalated"):
        return {
            "agent_reasoning": ["ESCALATION LOCK: Session is locked"],
        }
    return {
        "agent_reasoning": ["ESCALATION LOCK: Session active"],
    }


def _route_escalation_lock(state: dict) -> str:
    if state.get("is_escalated"):
        return "post_escalation"
    return "input_guardrails"


# ═════════════════════════════════════════════════════════════════════════════
# Input guardrails routing
# ═════════════════════════════════════════════════════════════════════════════

def _route_after_input_guardrails(state: dict) -> str:
    if state.get("input_blocked"):
        return "__end__"

    # Health concern or chargeback → auto-escalate
    if state.get("flag_health_concern"):
        return "auto_escalate_health"
    if state.get("flag_escalation_risk"):
        # We don't auto-escalate for aggressive language on first message;
        # we flag it and let the agent handle. But if combined with health → escalate.
        pass

    # First turn vs multi-turn
    human_count = sum(
        1 for m in state.get("messages", [])
        if hasattr(m, "type") and m.type == "human"
    )
    if human_count <= 1:
        return "intent_classifier"
    return "intent_shift_check"


# ═════════════════════════════════════════════════════════════════════════════
# Auto-escalation for health concerns
# ═════════════════════════════════════════════════════════════════════════════

async def auto_escalate_health_node(state: dict) -> dict:
    """Immediately escalate health/safety concerns."""
    return {
        "escalation_reason": "health_concern",
        "agent_reasoning": [
            "AUTO-ESCALATE: Health/safety concern detected in input"
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Output guardrails routing
# ═════════════════════════════════════════════════════════════════════════════

def _route_after_output_guardrails(state: dict) -> str:
    # Escalation detected
    if state.get("is_escalation"):
        return "escalation_handler"

    # Handoff detected
    if state.get("is_handoff"):
        return "handoff_router"

    # Failed output guardrails → revise
    if not state.get("output_guardrail_passed", True):
        return "revise_response"

    # Passed → reflection
    return "reflection_validator"


# ═════════════════════════════════════════════════════════════════════════════
# Reflection routing
# ═════════════════════════════════════════════════════════════════════════════

def _route_after_reflection(state: dict) -> str:
    if state.get("reflection_passed", True):
        return "__end__"
    # Only revise once (tracked by was_revised)
    if state.get("was_revised"):
        return "__end__"  # Already revised once, ship it
    return "revise_response"


# ═════════════════════════════════════════════════════════════════════════════
# Post-revision routing — send back through output guardrails (1 cycle max)
# ═════════════════════════════════════════════════════════════════════════════

def _route_after_revision(state: dict) -> str:
    """After revision, go through output guardrails one more time, then end."""
    return "output_guardrails_final"


async def output_guardrails_final_node(state: dict) -> dict:
    """Second pass of output guardrails after revision. Minimal — just safety."""
    result = output_guardrails_node(state)
    # Even if it fails again, we ship it (1-cycle max)
    result["output_guardrail_passed"] = True
    return result


# ═════════════════════════════════════════════════════════════════════════════
# Handoff routing
# ═════════════════════════════════════════════════════════════════════════════

def _route_after_handoff(state: dict) -> str:
    target = state.get("handoff_target", "supervisor")
    valid = {"wismo_agent", "issue_agent", "account_agent", "supervisor"}
    return target if target in valid else "supervisor"


# ═════════════════════════════════════════════════════════════════════════════
# Build Graph
# ═════════════════════════════════════════════════════════════════════════════

def build_graph() -> StateGraph:
    """Construct and compile the full multi-agent graph."""
    graph = StateGraph(CustomerSupportState)

    # ── Nodes ────────────────────────────────────────────────────────────
    graph.add_node("escalation_lock", escalation_lock_node)
    graph.add_node("input_guardrails", input_guardrails_node)
    graph.add_node("auto_escalate_health", auto_escalate_health_node)
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

    # ── Edges ────────────────────────────────────────────────────────────

    # Entry → Escalation Lock
    graph.add_edge(START, "escalation_lock")

    # Escalation Lock → post_escalation | input_guardrails
    graph.add_conditional_edges(
        "escalation_lock",
        _route_escalation_lock,
        {"post_escalation": "post_escalation", "input_guardrails": "input_guardrails"},
    )

    # Input Guardrails → end | auto_escalate | classifier | shift_check
    graph.add_conditional_edges(
        "input_guardrails",
        _route_after_input_guardrails,
        {
            "__end__": END,
            "auto_escalate_health": "auto_escalate_health",
            "intent_classifier": "intent_classifier",
            "intent_shift_check": "intent_shift_check",
        },
    )

    # Auto-escalate health → escalation handler
    graph.add_edge("auto_escalate_health", "escalation_handler")

    # Intent Classifier → agent or supervisor
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

    # Intent Shift Check → agent or supervisor
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

    # Supervisor → agent | direct | escalate
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

    # ReAct Agents → Output Guardrails
    graph.add_edge("wismo_agent", "output_guardrails")
    graph.add_edge("issue_agent", "output_guardrails")
    graph.add_edge("account_agent", "output_guardrails")

    # Output Guardrails → escalation | handoff | revise | reflection
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

    # Handoff Router → target agent or supervisor
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

    # Reflection → end | revise
    graph.add_conditional_edges(
        "reflection_validator",
        _route_after_reflection,
        {"__end__": END, "revise_response": "revise_response"},
    )

    # Revision → output_guardrails_final (1 cycle)
    graph.add_edge("revise_response", "output_guardrails_final")

    # Output guardrails final → end
    graph.add_edge("output_guardrails_final", END)

    # Escalation → end
    graph.add_edge("escalation_handler", END)

    # Post-escalation → end
    graph.add_edge("post_escalation", END)

    return graph


def compile_graph():
    """Build, compile, and return the runnable graph with checkpointer."""
    graph = build_graph()
    return graph.compile(checkpointer=checkpointer)