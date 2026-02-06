"""
Streamlit UI — Customer Chat + Trace Timeline side-by-side.
Features:
- Sidebar: Start new session OR Load past session from history.
- Main: Chat interface + Real-time trace visualization.
- Style: Clean white aesthetic.
"""

import json
import time
from datetime import datetime
import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="NatPat Support", layout="wide", page_icon="🏳️")

# ── Custom CSS for Clean White Theme ─────────────────────────────────────────
st.markdown("""
<style>
    /* Global Background */
    .stApp {
        background-color: #FFFFFF;
        color: #333333;
    }
    
    /* Sidebar Background */
    section[data-testid="stSidebar"] {
        background-color: #F8F9FA;
        border-right: 1px solid #E0E0E0;
    }
    
    /* Chat Bubbles */
    .stChatMessage {
        background-color: transparent;
        border: none;
    }
    
    /* User Message Bubble */
    div[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #F3F4F6;
        border-radius: 12px;
        padding: 10px;
    }

    /* Assistant Message Bubble */
    div[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 10px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    
    /* Buttons */
    .stButton button {
        background-color: #FFFFFF;
        color: #333333;
        border: 1px solid #D1D5DB;
        border-radius: 6px;
        transition: all 0.2s;
    }
    .stButton button:hover {
        border-color: #9CA3AF;
        background-color: #F9FAFB;
    }
    
    /* Primary Button */
    button[kind="primary"] {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    
    /* Inputs */
    .stTextInput input {
        border-radius: 6px;
        border: 1px solid #D1D5DB;
    }
    
    /* Typography */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        color: #111827;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏳️ NatPat Customer Support")

# ── Session State Init ───────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state["session_id"] = None
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "traces" not in st.session_state:
    st.session_state["traces"] = []
if "is_escalated" not in st.session_state:
    st.session_state["is_escalated"] = False

# ── Sidebar: Session Management ──────────────────────────────────────────────
with st.sidebar:
    st.header("New Session")
    
    with st.expander("Start New Chat", expanded=True):
        email = st.text_input("Email", value="sarah@example.com")
        first_name = st.text_input("First Name", value="Sarah")
        last_name = st.text_input("Last Name", value="Jones")
        shopify_id = st.text_input("Shopify ID", value="gid://shopify/Customer/7424155189325")
        
        if st.button("Start Chat", type="primary", use_container_width=True):
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
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    st.markdown("---")
    st.header("History")
    
    # Fetch History
    try:
        # Filter history by the email entered above
        params = {"email": email} if email else {}
        hist_resp = httpx.get(f"{API_BASE}/sessions", params=params, timeout=5.0)
        sessions = hist_resp.json()
    except Exception:
        sessions = []
        st.warning("Could not fetch history")

    for s in sessions:
        sid = s["session_id"]
        label = f"{s['created_at'][:10]} | {s['preview'] or 'New Chat'}"
        
        # Highlight active
        kind = "primary" if st.session_state["session_id"] == sid else "secondary"
        
        if st.button(label, key=sid, type=kind, use_container_width=True):
            st.session_state["session_id"] = sid
            st.session_state["messages"] = [] # Clear UI messages to force reload logic (if we implemented full reload)
            # NOTE: In this simplified version, we just switch the ID. 
            # Real re-hydration of messages requires fetching the full history from API.
            # Currently `graph` has history, but UI needs to display it.
            # Since user asked for "history visibility", we should ideally fetch messages.
            # But the backend doesn't have a "get messages" endpoint, only "get trace".
            # We will use "get trace" to rebuild messages!
            st.session_state["traces"] = [] # trace will be rebuilt
            st.rerun()

# ── Logic: Re-hydrate UI if session changed but messages empty ────────────────
if st.session_state["session_id"] and not st.session_state["messages"]:
    try:
        # Fetch full trace to rebuild UI state
        t_resp = httpx.get(
            f"{API_BASE}/session/{st.session_state['session_id']}/trace",
            timeout=10.0
        )
        if t_resp.status_code == 200:
            full_trace = t_resp.json()["trace"]
            
            # Use pre-serialized messages from Trace model
            # They already contain 'role': 'customer'/'assistant' and 'content'
            st.session_state["messages"] = full_trace.get("messages", [])
            
            # Set escalation status from trace
            st.session_state["is_escalated"] = full_trace.get("is_escalated", False)
        else:
            st.warning(f"Could not load chat history: {t_resp.status_code} - {t_resp.text}")
            
    except Exception as e:
        st.error(f"Failed to hydrate session: {e}")


# ── Main UI ──────────────────────────────────────────────────────────────────

if not st.session_state["session_id"]:
    st.info("👈 Select a chat from history or start a new one.")
    st.stop()

col_chat, col_trace = st.columns([1, 1])

with col_chat:
    st.subheader(f"Chat: {st.session_state['session_id']}")
    
    # Display History
    for msg in st.session_state["messages"]:
        role = msg["role"]
        icon = "👤" if role == "customer" else "🤖"
        with st.chat_message(role, avatar=icon):
            st.markdown(msg["content"])

    # Input Area
    if not st.session_state["is_escalated"]:
        customer_msg = st.chat_input("Type your message...")
        if customer_msg:
            # Add to UI immediately
            st.session_state["messages"].append({"role": "customer", "content": customer_msg})
            
            # Send to API
            # Note: We don't rerun immediately to show the spinner
            with st.spinner("Thinking..."):
                try:
                    resp = httpx.post(
                        f"{API_BASE}/session/message",
                        json={
                            "session_id": st.session_state["session_id"],
                            "message": customer_msg,
                        },
                        timeout=60.0
                    )
                    
                    if resp.status_code != 200:
                        st.error(f"❌ API Error ({resp.status_code}): {resp.text}")
                        st.stop()
                        
                    data = resp.json()
                    
                    # Add response
                    st.session_state["messages"].append({"role": "assistant", "content": data["response"]})
                    
                    if data.get("is_escalated"):
                        st.session_state["is_escalated"] = True
                        
                    # Add simple trace entry for the live view
                    st.session_state["traces"].append({
                        "agent": data.get("agent"),
                        "intent": data.get("intent"),
                        "actions": data.get("actions_taken")
                    })
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.error("🔒 Session locked (Escalated to Human Agent)")


# ── Trace View ───────────────────────────────────────────────────────────────
with col_trace:
    st.subheader("Live Trace")
    
    # Show active traces for current session (collected in this run)
    if st.session_state["traces"]:
        for t in st.session_state["traces"]:
            with st.container():
                st.caption(f"Agent: **{t['agent']}** | Intent: **{t['intent']}**")
                if t.get("actions"):
                    st.code("\n".join(t["actions"]), language="bash")
                st.markdown("---")
    
    if st.button("Load Full Graph State"):
         try:
             resp = httpx.get(f"{API_BASE}/session/{st.session_state['session_id']}/trace")
             if resp.status_code == 200:
                 st.json(resp.json())
             else:
                 st.error(f"Failed to load trace: {resp.status_code} - {resp.text}")
         except Exception as e:
             st.error(f"Trace request failed: {e}")