"""
FastAPI application — multi-agent customer support system.

Endpoints:
  POST /session/start     → Start a new email session
  POST /session/message   → Send a message in an existing session
  GET  /session/{id}/trace → Get session trace
  GET  /sessions          → List past sessions (history)
  GET  /health            → Health check
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.graph.graph_builder import compile_graph
from src.tracing.models import build_session_trace
from src.config import set_time_override, clear_time_override
from src import database  # <--- Persistence module

# ── Global Graph (Initialized in lifespan) ──────────────────────────────────
graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    - Initialize DB
    - Setup AsyncSqliteSaver with aiosqlite connection
    - Compile graph with the async checkpointer
    """
    # 1. Init Session DB (Sync)
    database.init_db()
    
    # 2. Setup Async LangGraph Checkpointer
    # from_conn_string uses aiosqlite internally
    async with AsyncSqliteSaver.from_conn_string("history.db") as checkpointer:
        global graph
        graph = compile_graph(checkpointer)
        print("✅ Graph compiled with AsyncSqliteSaver connected to history.db")
        yield
        print("🛑 Graph checkpointer closed")

app = FastAPI(
    title="NatPat Multi-Agent Customer Support",
    description="Lookfor Hackathon 2026 — Multi-Agent E-Commerce Customer Support System",
    version="3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── In-memory session store (Maintained for fast metadata lookup) ────────────
# We still keep this for active session metadata, but we also rely on DB.
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


class SessionListItem(BaseModel):
    session_id: str
    email: str
    name: str
    created_at: str
    preview: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    print("HEALTH CHECK HIT")
    return {"status": "ok", "version": "3.0"}


@app.post("/session/start", response_model=SessionStartResponse)
async def start_session(req: SessionStartRequest):
    """Start a new customer support email session."""
    session_id = f"session_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()

    # 1. Store in memory (for fast active lookup)
    sessions[session_id] = {
        "customer_email": req.email,
        "customer_first_name": req.first_name,
        "customer_last_name": req.last_name,
        "customer_shopify_id": req.customer_shopify_id,
        "thread_id": session_id,
        "created_at": created_at,
    }

    # 2. Store in SQLite (for sidebar history)
    database.add_session(
        session_id=session_id,
        email=req.email,
        name=f"{req.first_name} {req.last_name}",
        created_at=created_at
    )

    return SessionStartResponse(
        session_id=session_id,
        message=f"Session started for {req.first_name} {req.last_name} ({req.email})",
    )


@app.post("/session/message", response_model=MessageResponse)
async def send_message(req: MessageRequest):
    """Send a customer message and get an agent response."""
    if graph is None:
        raise HTTPException(503, "Graph not initialized")

    # Try to get from memory first
    session = sessions.get(req.session_id)
    
    if not session:
        session = {
            "customer_email": "unknown",
            "customer_first_name": "Customer",
            "customer_last_name": "",
            "customer_shopify_id": "",
            "thread_id": req.session_id
        }

    config = {"configurable": {"thread_id": session["thread_id"]}}

    # Build input state
    input_state = {
        "messages": [HumanMessage(content=req.message)],
        "customer_email": session["customer_email"],
        "customer_first_name": session["customer_first_name"],
        "customer_last_name": session["customer_last_name"],
        "customer_shopify_id": session["customer_shopify_id"],
    }

    # Update preview in DB (async, best effort)
    try:
        database.update_preview(req.session_id, req.message)
    except Exception:
        pass

    # Invoke graph (State is automatically loaded/saved via AsyncSqliteSaver)
    try:
        result = await graph.ainvoke(input_state, config=config)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Graph execution failed: {e}")

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
    if graph is None:
        raise HTTPException(503, "Graph not initialized")
        
    try:
        config = {"configurable": {"thread_id": session_id}}

        # Get current state from AsyncSqliteSaver
        state_snapshot = await graph.aget_state(config)
        state = state_snapshot.values if state_snapshot else {}

        trace = build_session_trace(session_id, state)

        return TraceResponse(session_id=session_id, trace=trace.model_dump())
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Trace error: {str(e)}")


@app.get("/sessions", response_model=List[SessionListItem])
async def list_past_sessions(email: Optional[str] = None):
    """List all available chat sessions from history."""
    rows = database.list_sessions(email)
    return [
        SessionListItem(
            session_id=r["session_id"],
            email=r["customer_email"] or "",
            name=r["customer_name"] or "Unknown",
            created_at=r["created_at"],
            preview=r["preview"]
        ) for r in rows
    ]


# ── Debug Endpoints (for testing) ─────────────────────────────────────────────

class TimeOverrideRequest(BaseModel):
    date: str          # "2026-02-09"
    day_of_week: str   # "Monday"
    wait_promise: str  # "this Friday"


@app.post("/debug/set-time")
async def debug_set_time(req: TimeOverrideRequest):
    """Set time override for testing wait promise logic."""
    set_time_override(req.date, req.day_of_week, req.wait_promise)
    return {"status": "ok", "message": f"Time set to {req.day_of_week}, wait_promise={req.wait_promise}"}


@app.post("/debug/clear-time")
async def debug_clear_time():
    """Clear time override, revert to real server time."""
    clear_time_override()
    return {"status": "ok", "message": "Time override cleared"}
