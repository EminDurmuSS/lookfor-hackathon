"""
Tracing models and session trace builder.
Provides structured observability for every agent decision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class TraceEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent: str = ""
    action_type: str = ""  # guardrail_check, classification, routing, react_thought, tool_call, response, reflection, revision, escalation, handoff, intent_shift
    detail: str = ""
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[dict] = None
    confidence: Optional[int] = None
    passed: Optional[bool] = None


class SessionTrace(BaseModel):
    session_id: str = ""
    customer_email: str = ""
    customer_name: str = ""
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    intent: Optional[str] = None
    intent_confidence: Optional[int] = None
    current_agent: Optional[str] = None
    traces: list[TraceEntry] = Field(default_factory=list)
    agent_reasoning: list[str] = Field(default_factory=list)
    final_response: Optional[str] = None
    actions_taken: list[str] = Field(default_factory=list)
    is_escalated: bool = False
    was_revised: bool = False
    intent_shifted: bool = False
    handoffs: list[str] = Field(default_factory=list)
    reflection_violations: list[str] = Field(default_factory=list)
    guardrail_blocks: list[str] = Field(default_factory=list)
    model_calls: dict = Field(default_factory=dict)
    messages: list[dict] = Field(default_factory=list)
    escalation_payload: Optional[dict] = None


def build_session_trace(session_id: str, state: dict) -> SessionTrace:
    """Build a SessionTrace from the final graph state."""
    msgs = state.get("messages", [])
    
    # Serialize messages for UI hydration
    serialized_msgs = []
    for m in msgs:
        # Robustly handle LangChain message objects
        m_type = getattr(m, "type", "unknown")
        content = getattr(m, "content", "")
        if m_type == "human":
            serialized_msgs.append({"role": "customer", "content": content, "type": "human"})
        elif m_type == "ai":
            serialized_msgs.append({"role": "assistant", "content": content, "type": "ai"})
            
    final = ""
    for m in reversed(msgs):
        if hasattr(m, "type") and m.type == "ai" and m.content:
            final = m.content
            break

    # Build trace entries from agent_reasoning
    traces = []
    for r in (state.get("agent_reasoning") or []):
        entry = TraceEntry(detail=r)
        if "INPUT GUARDRAIL" in r:
            entry.action_type = "guardrail_check"
            entry.agent = "input_guardrails"
        elif "INTENT CLASSIFIER" in r or "INTENT SHIFT" in r:
            entry.action_type = "classification"
            entry.agent = "intent_classifier"
        elif "SUPERVISOR" in r:
            entry.action_type = "routing"
            entry.agent = "supervisor"
        elif "HANDOFF" in r:
            entry.action_type = "handoff"
            entry.agent = "handoff_router"
        elif "OUTPUT GUARDRAIL" in r:
            entry.action_type = "guardrail_check"
            entry.agent = "output_guardrails"
        elif "REFLECTION" in r:
            entry.action_type = "reflection"
            entry.agent = "reflection_validator"
        elif "REVISION" in r:
            entry.action_type = "revision"
            entry.agent = "revise_response"
        elif "ESCALAT" in r.upper():
            entry.action_type = "escalation"
            entry.agent = "escalation_handler"
        elif "SESSION LOCKED" in r:
            entry.action_type = "escalation"
            entry.agent = "post_escalation"
        elif "ReAct" in r:
            entry.action_type = "react_thought"
            entry.agent = state.get("current_agent", "unknown")
        elif "MULTI-TURN" in r:
            entry.action_type = "intent_shift"
            entry.agent = "intent_shift_check"
        traces.append(entry)

    # Add tool call traces
    for tc in (state.get("tool_calls_log") or []):
        traces.append(TraceEntry(
            action_type="tool_call",
            agent=state.get("current_agent", "unknown"),
            tool_name=tc.get("tool_name"),
            tool_input=tc.get("params"),
            tool_output=tc.get("result") if isinstance(tc.get("result"), dict) else {"raw": str(tc.get("result", ""))},
            detail=f"Tool: {tc.get('tool_name')}",
        ))

    return SessionTrace(
        session_id=session_id,
        customer_email=state.get("customer_email", ""),
        customer_name=f"{state.get('customer_first_name', '')} {state.get('customer_last_name', '')}".strip(),
        intent=state.get("ticket_category"),
        intent_confidence=state.get("intent_confidence"),
        current_agent=state.get("current_agent"),
        traces=traces,
        agent_reasoning=state.get("agent_reasoning", []),
        final_response=final,
        actions_taken=state.get("actions_taken", []),
        is_escalated=state.get("is_escalated", False),
        was_revised=state.get("was_revised", False),
        intent_shifted=state.get("intent_shifted", False),
        escalation_payload=state.get("escalation_payload"),
        messages=serialized_msgs,
    )
