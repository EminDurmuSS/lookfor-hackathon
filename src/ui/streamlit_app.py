"""
Streamlit UI — Customer Chat + Detailed Trace Timeline side-by-side.
Features:
- Sidebar: Start new session OR Load past session from history.
- Main: Chat interface + Real-time trace visualization.
- Style: Clean white aesthetic with detailed agent trace.
"""

import json
import time
from datetime import datetime
import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="NatPat Support", layout="wide", page_icon="🏳️")

# ── Custom CSS for Clean White Theme + Trace Cards ────────────────────────────
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

    /* ═══ Trace Cards Styling ═══ */
    .trace-card {
        background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%);
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: all 0.2s ease;
    }
    .trace-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-1px);
    }
    
    .state-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
        font-size: 13px;
    }
    .state-item {
        background: white;
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
    }
    .state-label {
        color: #6B7280;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 2px;
    }
    .state-value {
        color: #1F2937;
        font-weight: 500;
    }
    
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
    }
    .badge-success { background: #D1FAE5; color: #065F46; }
    .badge-warning { background: #FEF3C7; color: #92400E; }
    .badge-danger { background: #FEE2E2; color: #991B1B; }
    .badge-info { background: #DBEAFE; color: #1E40AF; }
    .badge-purple { background: #EDE9FE; color: #5B21B6; }
    
    .trace-step {
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 8px;
        border-left: 4px solid #3B82F6;
    }
    .trace-step.guardrail { border-left-color: #8B5CF6; }
    .trace-step.classification { border-left-color: #F59E0B; }
    .trace-step.routing { border-left-color: #10B981; }
    .trace-step.tool_call { border-left-color: #EF4444; }
    .trace-step.response { border-left-color: #3B82F6; }
    .trace-step.escalation { border-left-color: #DC2626; }
    .trace-step.handoff { border-left-color: #8B5CF6; }
    .trace-step.reflection { border-left-color: #6366F1; }
    
    .step-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;
    }
    .step-icon {
        font-size: 18px;
    }
    .step-type {
        font-weight: 600;
        color: #374151;
        text-transform: capitalize;
    }
    .step-agent {
        color: #6B7280;
        font-size: 12px;
    }
    .step-detail {
        color: #4B5563;
        font-size: 13px;
        margin-top: 6px;
        padding: 8px;
        background: #F9FAFB;
        border-radius: 6px;
        word-wrap: break-word;
    }
    
    .tool-box {
        background: #1E293B;
        color: #E2E8F0;
        border-radius: 8px;
        padding: 12px;
        margin-top: 8px;
        font-family: 'Monaco', 'Consolas', monospace;
        font-size: 12px;
    }
    .tool-name {
        color: #22D3EE;
        font-weight: 600;
    }
    .tool-label {
        color: #94A3B8;
        font-size: 11px;
    }
    .tool-success { color: #4ADE80; }
    .tool-error { color: #F87171; }
    
    .reasoning-step {
        padding: 8px 12px;
        background: #FAFAFA;
        border-radius: 8px;
        margin-bottom: 6px;
        font-size: 13px;
        border-left: 3px solid #CBD5E1;
    }
    .reasoning-step.handoff { border-left-color: #8B5CF6; background: #FAF5FF; }
    .reasoning-step.escalation { border-left-color: #DC2626; background: #FEF2F2; }
    .reasoning-step.locked { border-left-color: #F59E0B; background: #FFFBEB; }
    
    .alert-box {
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 8px;
        font-size: 13px;
    }
    .alert-warning {
        background: #FEF3C7;
        border: 1px solid #FCD34D;
        color: #92400E;
    }
    .alert-danger {
        background: #FEE2E2;
        border: 1px solid #FECACA;
        color: #991B1B;
    }
    .alert-info {
        background: #DBEAFE;
        border: 1px solid #93C5FD;
        color: #1E40AF;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏳️ NatPat Customer Support")

# ── Action Icons Map ──────────────────────────────────────────────────────────
ACTION_ICONS = {
    "guardrail_check": "🛡️",
    "input_guardrail": "🛡️",
    "output_guardrail": "🛡️",
    "classification": "🏷️",
    "intent_classification": "🏷️",
    "routing": "🔀",
    "agent_routing": "🔀",
    "react_thought": "💭",
    "thought": "💭",
    "tool_call": "🔧",
    "tool_execution": "🔧",
    "response": "💬",
    "agent_response": "💬",
    "reflection": "🔎",
    "revision": "✏️",
    "escalation": "🚨",
    "handoff": "🔄",
    "intent_shift": "↩️",
    "session_lock": "🔒",
    "pii_redaction": "🔐",
}

# ── Demo Sessions from Test Data ─────────────────────────────────────────────
DEMO_SESSIONS = [
    {
        "id": "demo-1",
        "title": "📦 Sipariş Takibi - Eksik Ürün",
        "description": "Müşteri siparişinin bir kısmının gönderildiğini sorgular",
        "customer": {
            "email": "user_8b7c460f@example.com",
            "first_name": "Customer",
            "last_name": "1",
            "customer_shopify_id": "gid://shopify/Customer/cust_8b7c460f"
        },
        "initial_message": "Hi,  Could you please confirm that only part of my order has been sent.  I have recieved the mood calming stickers and the tick repellent stickers only.  Many thanks  Parker Wilson Parker Wilson Sent from my Galaxy -------- Original message --------"
    },
    {
        "id": "demo-2",
        "title": "🔄 İade Talebi - Yanlış Ürün",
        "description": "Müşteri yanlış ürün aldığı için iade talebinde bulunur",
        "customer": {
            "email": "user_b80233f7@example.com",
            "first_name": "Customer",
            "last_name": "2",
            "customer_shopify_id": "gid://shopify/Customer/cust_b80233f7"
        },
        "initial_message": "Hello, my order number is  Order #NP6664669  My order was to include 2 packs for adults and i received all packs for kids. Also, the packs were the old version of buzzpatch. The packs barely had a scent as if they were dried out. Alls to say they didn't work and i would like a refund please.  Thank you Melissa Sent from my iPhone"
    },
    {
        "id": "demo-3",
        "title": "📍 Sipariş Durumu Sorgulama",
        "description": "Müşteri siparişinin nerede olduğunu sorar",
        "customer": {
            "email": "user_b1f341ae@example.com",
            "first_name": "Customer",
            "last_name": "6",
            "customer_shopify_id": "gid://shopify/Customer/cust_b1f341ae"
        },
        "initial_message": "Where is my order ?  Frédéric +19409061934"
    },
    {
        "id": "demo-4",
        "title": "❌ Abonelik İptali",
        "description": "Müşteri aboneliğini iptal etmek ister",
        "customer": {
            "email": "user_bb90b529@example.com",
            "first_name": "Customer",
            "last_name": "13",
            "customer_shopify_id": "gid://shopify/Customer/cust_bb90b529"
        },
        "initial_message": "Hello,  I'm not sure why I received another NatPat order but please cancel all future orders.  Please confirm that this has been done.  Thank you.  Rio Slaven  NATPAT Order #NP2361630 confirmed"
    },
    {
        "id": "demo-5",
        "title": "⚠️ Ürün Kalite Şikayeti",
        "description": "Müşteri ürünlerin yapışmadığından şikayet eder",
        "customer": {
            "email": "user_b7d0014c@example.com",
            "first_name": "Customer",
            "last_name": "5",
            "customer_shopify_id": "gid://shopify/Customer/cust_b7d0014c"
        },
        "initial_message": "Hello!  I'm reaching out regarding my most recent order, Order# NP7412770.  I have been using NATPAT for several years without any issues, but the MagicPatch Itch Relief Patches I received seem to be the old version and the packaging is different than what is advertised on the website. I have attached a photo of the packaging I received for all 8 packs of the MagicPatch Itch Relief Patches that I received in my order versus the one on the website. The ones I received state that there are 27 patches, while the website states there are 32 patches in each pack. The shape of the patches are different as well- I recall the ones I have are the style that was originally offered years ago.   The most glaring issue is the performance and staying power of the patches I received. They fall off almost immediately and are guaranteed gone after sleeping. In the past, the patches would stay on for several days even with swimming, showering, and regular daily activities.  Overall, I'm displeased with the patches I received and I would like to get them replaced with the new version that are advertised on the website.  Thank you, Jan Heyrana --  Jan Q. Heyrana, M.Ed. | AMI Certified Primary Guide"
    }
]

# ── Session State Init ───────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state["session_id"] = None
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "traces" not in st.session_state:
    st.session_state["traces"] = []
if "full_trace" not in st.session_state:
    st.session_state["full_trace"] = None
if "is_escalated" not in st.session_state:
    st.session_state["is_escalated"] = False
if "demo_mode" not in st.session_state:
    st.session_state["demo_mode"] = False
if "pending_demo_message" not in st.session_state:
    st.session_state["pending_demo_message"] = None

# ── Sidebar: Session Management ──────────────────────────────────────────────
with st.sidebar:
    # ═══ Demo Sessions Section ═══════════════════════════════════════════════
    st.header("🎯 Demo Sessions")
    st.caption("Hazır senaryolardan birini seçin")
    
    for demo in DEMO_SESSIONS:
        with st.container():
            is_active = st.session_state.get("active_demo") == demo["id"]
            btn_type = "primary" if is_active else "secondary"
            
            # Demo card
            st.markdown(f"""
            <div style="background: {'#E0F2FE' if is_active else '#F8FAFC'}; padding: 10px; border-radius: 8px; margin-bottom: 8px; border: 1px solid {'#0EA5E9' if is_active else '#E2E8F0'};">
                <div style="font-weight: 600; font-size: 14px;">{demo['title']}</div>
                <div style="font-size: 12px; color: #64748B;">{demo['description']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"▶️ Başlat", key=f"demo_{demo['id']}", use_container_width=True, type=btn_type):
                try:
                    # Start a new session with demo customer data
                    resp = httpx.post(
                        f"{API_BASE}/session/start",
                        json={
                            "email": demo["customer"]["email"],
                            "first_name": demo["customer"]["first_name"],
                            "last_name": demo["customer"]["last_name"],
                            "customer_shopify_id": demo["customer"]["customer_shopify_id"],
                        },
                        timeout=10.0,
                    )
                    data = resp.json()
                    st.session_state["session_id"] = data["session_id"]
                    st.session_state["messages"] = []
                    st.session_state["traces"] = []
                    st.session_state["full_trace"] = None
                    st.session_state["is_escalated"] = False
                    st.session_state["active_demo"] = demo["id"]
                    st.session_state["demo_mode"] = True
                    st.session_state["pending_demo_message"] = demo["initial_message"]
                    st.rerun()
                except Exception as e:
                    st.error(f"Başlatılamadı: {e}")
    
    st.markdown("---")
    
    # ═══ New Custom Session Section ══════════════════════════════════════════
    st.header("➕ Yeni Oturum")
    
    with st.expander("Özel Oturum Oluştur", expanded=False):
        email = st.text_input("Email", value="sarah@example.com")
        first_name = st.text_input("First Name", value="Sarah")
        last_name = st.text_input("Last Name", value="Jones")
        shopify_id = st.text_input("Shopify ID", value="gid://shopify/Customer/7424155189325")
        
        if st.button("🚀 Oturum Başlat", type="primary", use_container_width=True):
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
                st.session_state["full_trace"] = None
                st.session_state["is_escalated"] = False
                st.session_state["active_demo"] = None
                st.session_state["demo_mode"] = False
                st.session_state["pending_demo_message"] = None
                st.rerun()
            except Exception as e:
                st.error(f"Başlatılamadı: {e}")

    st.markdown("---")
    
    # ═══ History Section ═════════════════════════════════════════════════════
    st.header("📜 Geçmiş")
    
    # Fetch History
    try:
        params = {"email": email} if email else {}
        hist_resp = httpx.get(f"{API_BASE}/sessions", params=params, timeout=5.0)
        sessions = hist_resp.json()
    except Exception:
        sessions = []
        st.caption("Geçmiş yüklenemedi")

    if sessions:
        for s in sessions:
            sid = s["session_id"]
            label = f"{s['created_at'][:10]} | {s['preview'] or 'Yeni Chat'}"
            
            kind = "primary" if st.session_state["session_id"] == sid else "secondary"
            
            if st.button(label, key=sid, type=kind, use_container_width=True):
                st.session_state["session_id"] = sid
                st.session_state["messages"] = []
                st.session_state["traces"] = []
                st.session_state["full_trace"] = None
                st.session_state["active_demo"] = None
                st.session_state["demo_mode"] = False
                st.session_state["pending_demo_message"] = None
                st.rerun()
    else:
        st.caption("Henüz geçmiş oturum yok")

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
            st.session_state["messages"] = full_trace.get("messages", [])
            st.session_state["full_trace"] = full_trace
            
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
    st.subheader(f"💬 Chat")
    st.caption(f"Session: `{st.session_state['session_id']}`")
    
    # ═══ Auto-send pending demo message ══════════════════════════════════════
    pending_msg = st.session_state.get("pending_demo_message")
    if pending_msg and st.session_state.get("demo_mode"):
        # Clear pending message first to prevent re-send on rerun
        st.session_state["pending_demo_message"] = None
        
        # Add to UI immediately
        st.session_state["messages"].append({"role": "customer", "content": pending_msg})
        
        # Send to API
        try:
            resp = httpx.post(
                f"{API_BASE}/session/message",
                json={
                    "session_id": st.session_state["session_id"],
                    "message": pending_msg,
                },
                timeout=60.0
            )
            
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["messages"].append({"role": "assistant", "content": data["response"]})
                
                if data.get("is_escalated"):
                    st.session_state["is_escalated"] = True
                    
                st.session_state["traces"].append({
                    "agent": data.get("agent"),
                    "intent": data.get("intent"),
                    "actions": data.get("actions_taken"),
                    "was_revised": data.get("was_revised"),
                    "intent_shifted": data.get("intent_shifted"),
                })
                
                # Fetch full trace
                try:
                    trace_resp = httpx.get(
                        f"{API_BASE}/session/{st.session_state['session_id']}/trace",
                        timeout=10.0
                    )
                    if trace_resp.status_code == 200:
                        st.session_state["full_trace"] = trace_resp.json().get("trace", {})
                except:
                    pass
                    
            st.rerun()
        except Exception as e:
            st.error(f"Demo mesajı gönderilemedi: {e}")
    
    # Display History
    for msg in st.session_state["messages"]:
        role = msg["role"]
        icon = "👤" if role == "customer" else "🤖"
        with st.chat_message(role, avatar=icon):
            st.markdown(msg["content"], unsafe_allow_html=True)

    # Input Area
    if not st.session_state["is_escalated"]:
        customer_msg = st.chat_input("Mesajınızı yazın...")
        if customer_msg:
            # Add to UI immediately
            st.session_state["messages"].append({"role": "customer", "content": customer_msg})
            
            # Send to API
            with st.spinner("Agent is thinking..."):
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
                        "actions": data.get("actions_taken"),
                        "was_revised": data.get("was_revised"),
                        "intent_shifted": data.get("intent_shifted"),
                    })
                    
                    # Fetch full trace after message
                    try:
                        trace_resp = httpx.get(
                            f"{API_BASE}/session/{st.session_state['session_id']}/trace",
                            timeout=10.0
                        )
                        if trace_resp.status_code == 200:
                            st.session_state["full_trace"] = trace_resp.json().get("trace", {})
                    except:
                        pass
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.error("🔒 Session locked (Escalated to Human Agent)")


# ══════════════════════════════════════════════════════════════════════════════
# ── Detailed Trace View ───────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

with col_trace:
    st.subheader("📋 Agent Trace")
    
    trace = st.session_state.get("full_trace") or {}
    
    if not trace and st.session_state["traces"]:
        # Build minimal trace from live data
        trace = {
            "traces": [],
            "actions_taken": [],
        }
        for t in st.session_state["traces"]:
            if t.get("agent"):
                trace["current_agent"] = t["agent"]
            if t.get("intent"):
                trace["ticket_category"] = t["intent"]
            if t.get("actions"):
                trace["actions_taken"] = t["actions"]
    
    if trace:
        # ═══ State Snapshot ═══════════════════════════════════════════════════
        with st.container():
            st.markdown("#### 📊 State Snapshot")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                <div class="state-item">
                    <div class="state-label">Customer</div>
                    <div class="state-value">{trace.get('customer_name', 'N/A')} ({trace.get('customer_email', 'N/A')})</div>
                </div>
                """, unsafe_allow_html=True)
                
                intent = trace.get('intent') or trace.get('ticket_category') or 'Not classified'
                confidence = trace.get('intent_confidence') or 0
                st.markdown(f"""
                <div class="state-item">
                    <div class="state-label">Intent</div>
                    <div class="state-value">{intent} <span class="badge badge-info">{confidence}%</span></div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                agent = trace.get('current_agent') or 'N/A'
                st.markdown(f"""
                <div class="state-item">
                    <div class="state-label">Active Agent</div>
                    <div class="state-value"><span class="badge badge-purple">{agent}</span></div>
                </div>
                """, unsafe_allow_html=True)
                
                is_escalated = trace.get('is_escalated', False)
                esc_badge = '<span class="badge badge-danger">🚨 ESCALATED</span>' if is_escalated else '<span class="badge badge-success">✓ Normal</span>'
                st.markdown(f"""
                <div class="state-item">
                    <div class="state-label">Status</div>
                    <div class="state-value">{esc_badge}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Additional state flags
            flags = []
            if trace.get('was_revised'):
                flags.append('<span class="badge badge-warning">✏️ Revised</span>')
            if trace.get('intent_shifted'):
                flags.append('<span class="badge badge-info">↩️ Intent Shifted</span>')
            if flags:
                st.markdown(f"<div style='margin-top: 8px;'>{'  '.join(flags)}</div>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # ═══ Agent Reasoning Chain ════════════════════════════════════════════
        reasoning = trace.get("agent_reasoning", [])
        if reasoning:
            with st.expander("🧠 Agent Reasoning Chain", expanded=True):
                for i, step in enumerate(reasoning, 1):
                    step_class = ""
                    icon = "💭"
                    if "HANDOFF" in step:
                        step_class = "handoff"
                        icon = "🔄"
                    elif "ESCALAT" in step.upper():
                        step_class = "escalation"
                        icon = "🚨"
                    elif "SESSION LOCKED" in step:
                        step_class = "locked"
                        icon = "🔒"
                    
                    st.markdown(f"""
                    <div class="reasoning-step {step_class}">
                        <strong>{icon} [{i}]</strong> {step}
                    </div>
                    """, unsafe_allow_html=True)
        
        # ═══ Step-by-Step Trace Timeline ══════════════════════════════════════
        traces = trace.get("traces", [])
        if traces:
            with st.expander(f"🔍 Step-by-Step Trace ({len(traces)} steps)", expanded=True):
                for i, entry in enumerate(traces, 1):
                    action_type = entry.get("action_type", "unknown")
                    agent = entry.get("agent", "")
                    detail = entry.get("detail", "")
                    passed = entry.get("passed")
                    icon = ACTION_ICONS.get(action_type, "▪️")
                    
                    # Status indicator
                    status_html = ""
                    if passed is True:
                        status_html = ' ✅'
                    elif passed is False:
                        status_html = ' ❌'
                    
                    # Determine step class for border color
                    step_class = action_type.split("_")[0] if "_" in action_type else action_type
                    
                    # Build detail HTML
                    detail_html = ""
                    if detail:
                        # If detail contains HTML (e.g. tool call HTML), render it directly
                        if detail.strip().startswith("<div") or "<span" in detail:
                            detail_html = f'<div style="margin-top: 6px;">{detail}</div>'
                        else:
                            safe_detail = detail[:500].replace("<", "&lt;").replace(">", "&gt;")
                            detail_html = f'<div style="color: #4B5563; font-size: 13px; margin-top: 6px; padding: 8px; background: #F9FAFB; border-radius: 6px;">{safe_detail}{"..." if len(detail) > 500 else ""}</div>'
                    
                    # Build tool call HTML
                    tool_html = ""
                    tool_name = entry.get("tool_name")
                    if tool_name:
                        tool_input = entry.get("tool_input") or {}
                        tool_output = entry.get("tool_output") or {}
                        
                        # Check success
                        success = None
                        if isinstance(tool_output, dict):
                            success = tool_output.get("success")
                        
                        success_indicator = ""
                        if success is True:
                            success_indicator = ' ✅ Success'
                        elif success is False:
                            success_indicator = ' ❌ Failed'
                        
                        input_str = json.dumps(tool_input, ensure_ascii=False, default=str)[:200]
                        output_str = json.dumps(tool_output, ensure_ascii=False, default=str)[:300]
                        
                        tool_html = f'''
                        <div style="background: #1E293B; color: #E2E8F0; border-radius: 8px; padding: 12px; margin-top: 8px; font-family: monospace; font-size: 12px;">
                            <div><span style="color: #94A3B8;">TOOL:</span> <span style="color: #22D3EE; font-weight: 600;">{tool_name}</span>{success_indicator}</div>
                            <div style="margin-top: 6px;"><span style="color: #94A3B8;">INPUT:</span> {input_str}</div>
                            <div style="margin-top: 4px;"><span style="color: #94A3B8;">OUTPUT:</span> {output_str}</div>
                        </div>
                        '''
                    
                    # Build complete card HTML
                    border_colors = {
                        "guardrail": "#8B5CF6",
                        "classification": "#F59E0B",
                        "routing": "#10B981",
                        "tool": "#EF4444",
                        "response": "#3B82F6",
                        "escalation": "#DC2626",
                        "handoff": "#8B5CF6",
                        "reflection": "#6366F1",
                        "react": "#F59E0B",
                    }
                    border_color = border_colors.get(step_class, "#3B82F6")
                    
                    card_html = f'''
                    <div style="background: white; border: 1px solid #E5E7EB; border-radius: 10px; padding: 12px 16px; margin-bottom: 8px; border-left: 4px solid {border_color};">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 18px;">{icon}</span>
                            <span style="font-weight: 600; color: #374151; text-transform: capitalize;">{action_type.replace('_', ' ')}</span>
                            <span>{status_html}</span>
                            <span style="color: #6B7280; font-size: 12px;">• {agent}</span>
                        </div>
                        {detail_html}
                        {tool_html}
                    </div>
                    '''
                    
                    st.markdown(card_html, unsafe_allow_html=True)
        
        # ═══ Actions Taken ════════════════════════════════════════════════════
        actions = trace.get("actions_taken", [])
        if actions:
            with st.expander("⚡ Actions Taken", expanded=False):
                for action in actions:
                    st.markdown(f"• {action}")
        
        # ═══ Guardrail Issues ═════════════════════════════════════════════════
        guardrail_blocks = trace.get("guardrail_blocks", [])
        if guardrail_blocks:
            st.markdown("#### ⚠️ Guardrail Blocks")
            for issue in guardrail_blocks:
                st.markdown(f"""
                <div class="alert-box alert-warning">
                    🛡️ {issue}
                </div>
                """, unsafe_allow_html=True)
        
        # ═══ Escalation Payload ═══════════════════════════════════════════════
        esc_payload = trace.get("escalation_payload")
        if esc_payload:
            with st.expander("🚨 Escalation Payload", expanded=True):
                st.json(esc_payload)
        
        # ═══ Reflection Violations ════════════════════════════════════════════
        reflection_violations = trace.get("reflection_violations", [])
        if reflection_violations:
            with st.expander("🔎 Reflection Violations", expanded=False):
                for violation in reflection_violations:
                    st.markdown(f"""
                    <div class="alert-box alert-info">
                        {violation}
                    </div>
                    """, unsafe_allow_html=True)
    
    else:
        st.info("💡 Send a message to see the agent trace here.")
    
    # Manual reload button
    st.markdown("---")
    if st.button("🔄 Refresh Full Trace", use_container_width=True):
        try:
            resp = httpx.get(f"{API_BASE}/session/{st.session_state['session_id']}/trace", timeout=10.0)
            if resp.status_code == 200:
                st.session_state["full_trace"] = resp.json().get("trace", {})
                st.rerun()
            else:
                st.error(f"Failed to load trace: {resp.status_code} - {resp.text}")
        except Exception as e:
            st.error(f"Trace request failed: {e}")
    
    # Raw JSON toggle
    with st.expander("📦 Raw Trace JSON"):
        if trace:
            st.json(trace)
        else:
            st.info("No trace data available")