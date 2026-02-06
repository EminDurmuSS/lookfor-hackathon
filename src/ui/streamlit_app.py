"""
Streamlit UI — Customer Chat + Trace Timeline side-by-side.
"""

import json
import time
from datetime import datetime

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="NatPat Customer Support", layout="wide")
st.title("🐛 NatPat Multi-Agent Customer Support")

# ── Sidebar: Session Management ──────────────────────────────────────────────
with st.sidebar:
    st.header("📧 Email Session")

    email = st.text_input("Customer Email", value="sarah@example.com")
    first_name = st.text_input("First Name", value="Sarah")
    last_name = st.text_input("Last Name", value="Jones")
    shopify_id = st.text_input(
        "Shopify Customer ID",
        value="gid://shopify/Customer/7424155189325",
    )

    if st.button("🚀 Start New Session", type="primary"):
        try:
            resp = httpx.post(
                f"{API_BASE}/session/start",
                json={
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "customer_shopify_id": shopify_id,
                },
                timeout=10.0,
            )
            data = resp.json()
            st.session_state["session_id"] = data["session_id"]
            st.session_state["messages"] = []
            st.session_state["traces"] = []
            st.session_state["is_escalated"] = False
            st.success(f"Session started: {data['session_id']}")
        except Exception as e:
            st.error(f"Failed to start session: {e}")

    if "session_id" in st.session_state:
        st.info(f"Session: `{st.session_state['session_id']}`")
        if st.session_state.get("is_escalated"):
            st.warning("⚠️ Session ESCALATED — locked to human agent")

    st.markdown("---")
    st.markdown(
        "**Architecture:** 7-layer pipeline\n\n"
        "Escalation Lock → Input Guardrails → "
        "Intent Classification → ReAct Agents → "
        "Output Guardrails → Reflection → Revision"
    )


# ── Main Layout ──────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.info("👈 Start a session from the sidebar to begin.")
    st.stop()

col_chat, col_trace = st.columns([1, 1])

# ── Chat Column ──────────────────────────────────────────────────────────────
with col_chat:
    st.subheader("💬 Customer Chat")

    # Display message history
    for msg in st.session_state.get("messages", []):
        role = msg["role"]
        icon = "👤" if role == "customer" else "🤖"
        with st.chat_message(role, avatar=icon):
            st.markdown(msg["content"])

    # Input
    customer_msg = st.chat_input(
        "Type customer message...",
        disabled=st.session_state.get("is_escalated", False),
    )

    if customer_msg:
        # Show customer message
        st.session_state["messages"].append(
            {"role": "customer", "content": customer_msg}
        )
        with st.chat_message("customer", avatar="👤"):
            st.markdown(customer_msg)

        # Send to API
        with st.spinner("Agent thinking..."):
            start_time = time.time()
            try:
                resp = httpx.post(
                    f"{API_BASE}/session/message",
                    json={
                        "session_id": st.session_state["session_id"],
                        "message": customer_msg,
                    },
                    timeout=60.0,
                )
                data = resp.json()
                elapsed = time.time() - start_time

                # Show agent response
                st.session_state["messages"].append(
                    {"role": "assistant", "content": data["response"]}
                )
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(data["response"])

                # Update escalation status
                if data.get("is_escalated"):
                    st.session_state["is_escalated"] = True

                # Store trace info
                trace_entry = {
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                    "intent": data.get("intent", ""),
                    "confidence": data.get("intent_confidence", 0),
                    "agent": data.get("agent", ""),
                    "actions": data.get("actions_taken", []),
                    "was_revised": data.get("was_revised", False),
                    "intent_shifted": data.get("intent_shifted", False),
                    "is_escalated": data.get("is_escalated", False),
                    "elapsed_s": round(elapsed, 2),
                }
                st.session_state.setdefault("traces", []).append(trace_entry)

            except Exception as e:
                st.error(f"Error: {e}")

# ── Trace Column ─────────────────────────────────────────────────────────────
with col_trace:
    st.subheader("📊 Trace Timeline")

    if not st.session_state.get("traces"):
        st.info("Send a message to see the trace.")
    else:
        for i, t in enumerate(st.session_state["traces"]):
            with st.expander(
                f"Turn {i + 1} — {t['timestamp']} "
                f"({'🔴 ESCALATED' if t['is_escalated'] else '✅'})",
                expanded=(i == len(st.session_state["traces"]) - 1),
            ):
                c1, c2, c3 = st.columns(3)
                c1.metric("Intent", t["intent"] or "—")
                c2.metric("Confidence", f"{t['confidence']}%")
                c3.metric("Agent", t["agent"] or "—")

                c4, c5, c6 = st.columns(3)
                c4.metric("Revised", "Yes" if t["was_revised"] else "No")
                c5.metric("Shifted", "Yes" if t["intent_shifted"] else "No")
                c6.metric("Time", f"{t['elapsed_s']}s")

                if t["actions"]:
                    st.markdown("**Actions taken:**")
                    for a in t["actions"]:
                        st.markdown(f"- `{a}`")

                if t["is_escalated"]:
                    st.error("⚠️ Session escalated to Monica (Head of CS)")

    # Full trace button
    st.markdown("---")
    if st.button("🔍 Load Full Trace"):
        try:
            resp = httpx.get(
                f"{API_BASE}/session/{st.session_state['session_id']}/trace",
                timeout=10.0,
            )
            trace_data = resp.json()
            st.json(trace_data["trace"])
        except Exception as e:
            st.error(f"Failed to load trace: {e}")