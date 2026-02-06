"""
FastAPI application — multi-agent customer support system.

Endpoints:
  POST /session/start     → Start a new email session
  POST /session/message   → Send a message in an existing session
  GET  /session/{id}/trace → Get session trace
  GET  /health            → Health check
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from src.graph.graph_builder import compile_graph
from src.tracing.models import build_session_trace

app = FastAPI(
    title="NatPat Multi-Agent Customer Support",
    description="Lookfor Hackathon 2026 — Multi-Agent E-Commerce Customer Support System",
    version="3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Compile graph (singleton) ────────────────────────────────────────────────
graph = compile_graph()

# ── In-memory session store ──────────────────────────────────────────────────
sessions: dict[str, dict] = {}


# ── Models ───────────────────────────────────────────────────────────────────

class SessionStartRequest(BaseModel):
    email: str
    first_name: str
    last_name: str
    customer_shopify_id: str


class SessionStartResponse(BaseModel):
    session_id: str
    message: str


class MessageRequest(BaseModel):
    session_id: str
    message: str


class MessageResponse(BaseModel):
    session_id: str
    response: str
    is_escalated: bool = False
    actions_taken: list[str] = []
    agent: str = ""
    intent: str = ""
    intent_confidence: int = 0
    was_revised: bool = False
    intent_shifted: bool = False


class TraceResponse(BaseModel):
    session_id: str
    trace: dict


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0"}


@app.post("/session/start", response_model=SessionStartResponse)
async def start_session(req: SessionStartRequest):
    """Start a new customer support email session."""
    session_id = f"session_{uuid.uuid4().hex[:12]}"

    sessions[session_id] = {
        "customer_email": req.email,
        "customer_first_name": req.first_name,
        "customer_last_name": req.last_name,
        "customer_shopify_id": req.customer_shopify_id,
        "thread_id": session_id,
        "created_at": datetime.utcnow().isoformat(),
    }

    return SessionStartResponse(
        session_id=session_id,
        message=f"Session started for {req.first_name} {req.last_name} ({req.email})",
    )


@app.post("/session/message", response_model=MessageResponse)
async def send_message(req: MessageRequest):
    """Send a customer message and get an agent response."""
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found. Start a session first.")

    config = {"configurable": {"thread_id": session["thread_id"]}}

    # Build input state
    input_state = {
        "messages": [HumanMessage(content=req.message)],
        "customer_email": session["customer_email"],
        "customer_first_name": session["customer_first_name"],
        "customer_last_name": session["customer_last_name"],
        "customer_shopify_id": session["customer_shopify_id"],
    }

    # Invoke graph
    result = await graph.ainvoke(input_state, config=config)

    # Extract final AI response
    final_response = ""
    for m in reversed(result.get("messages", [])):
        if hasattr(m, "type") and m.type == "ai" and m.content:
            final_response = m.content
            break

    return MessageResponse(
        session_id=req.session_id,
        response=final_response,
        is_escalated=result.get("is_escalated", False),
        actions_taken=result.get("actions_taken", []),
        agent=result.get("current_agent", ""),
        intent=result.get("ticket_category", ""),
        intent_confidence=result.get("intent_confidence", 0),
        was_revised=result.get("was_revised", False),
        intent_shifted=result.get("intent_shifted", False),
    )


@app.get("/session/{session_id}/trace", response_model=TraceResponse)
async def get_trace(session_id: str):
    """Get the full session trace for observability."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    config = {"configurable": {"thread_id": session["thread_id"]}}

    # Get current state from checkpointer
    state_snapshot = await graph.aget_state(config)
    state = state_snapshot.values if state_snapshot else {}

    trace = build_session_trace(session_id, state)

    return TraceResponse(session_id=session_id, trace=trace.model_dump())


@app.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    return {
        sid: {
            "email": s["customer_email"],
            "name": f"{s['customer_first_name']} {s['customer_last_name']}",
            "created_at": s["created_at"],
        }
        for sid, s in sessions.items()
    }