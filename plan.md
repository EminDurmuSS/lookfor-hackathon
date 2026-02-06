# 🏆 Lookfor Hackathon 2026 — Kazanma Planı v3.0 (FINAL)

## Multi-Agent E-Ticaret Müşteri Destek Sistemi

> **v3.0 FINAL:** Tüm edge case'ler, multi-turn routing, GID/Order# dönüşümü, cross-agent handoff, escalation lock, ve 8-kural reflection entegre edildi. Her agent prompt'u edge case-aware hale getirildi. Tool parametreleri spec'e %100 uyumlu.

---

## 1. TEKNOLOJİ STACK & MİMARİ KARAR

### 1.1 Stack Seçimi

| Bileşen              | Seçim                       | Gerekçe                                                                                               |
| -------------------- | --------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Framework**        | LangGraph (Python)          | Graph-based orchestration, built-in state management, checkpointer desteği, ReAct agent desteği hazır |
| **Ana LLM**          | Claude Sonnet 4 (Anthropic) | Hız/kalite dengesi mükemmel, tool calling çok güçlü                                                   |
| **Hızlı LLM**        | Claude Haiku (Anthropic)    | Intent classification ve reflection validation için ucuz+hızlı                                        |
| **UI**               | FastAPI + Streamlit         | Hızlı prototipleme, WebSocket desteği, trace görüntüleme                                              |
| **Containerization** | Docker Compose              | Tek komutla çalışır (değerlendirme avantajı)                                                          |
| **Tracing**          | Custom JSON trace logger    | Observability gereksinimini karşılar                                                                  |

### 1.2 Multi-Model Stratejisi

| Görev                           | Model             | Gerekçe                                             |
| ------------------------------- | ----------------- | --------------------------------------------------- |
| Intent Classification (Stage 1) | **Claude Haiku**  | Hızlı, ucuz, sınıflandırma için yeterli             |
| Intent Shift Check (Multi-turn) | **Claude Haiku**  | Aynı classifier, multi-turn için de yeterli         |
| Reflection Validator            | **Claude Haiku**  | Rule-based kontrol, karmaşık reasoning gereksiz     |
| Supervisor (fallback router)    | **Claude Sonnet** | Belirsiz durumlar için güçlü reasoning gerekli      |
| Sub-Agents (ReAct)              | **Claude Sonnet** | Tool calling + müşteri yanıtı kalitesi için gerekli |
| Response Revision               | **Claude Sonnet** | Düzeltme kapasitesi yüksek olmalı                   |
| Escalation Summary              | **Claude Sonnet** | Kaliteli handoff özeti                              |

**Tahmini maliyet dağılımı:**

- %60 istekte: Haiku classifier → direkt route → Sonnet agent (2 model call)
- %20 istekte: Haiku classifier → Sonnet supervisor → Sonnet agent (3 call)
- %20 istekte: reflection fail → ek 1 Haiku + 1 Sonnet (4 call max)
- Multi-turn: Haiku intent shift check eklenir (+1 call)

### 1.3 Neden Bu Pattern Kombinasyonu?

Anthropic'in "Building Effective Agents" makalesi: **"En basit çözümle başla, gerektiğinde karmaşıklaştır."**

| Pattern                           | Çözdüğü Problem                                      | Alternatif         | Neden Alternatif Değil                     |
| --------------------------------- | ---------------------------------------------------- | ------------------ | ------------------------------------------ |
| **ReAct**                         | Agent'ın tool call'larını reasoning ile desteklemesi | Basic tool calling | Trace/observability için reasoning zorunlu |
| **2-Stage Intent Classification** | Hızlı ve doğru routing                               | Tek LLM supervisor | Yavaş ve pahalı                            |
| **Guardrails**                    | Input/output güvenliği                               | Hiçbir kontrol     | Production'da kabul edilemez               |
| **Reflection**                    | Workflow kurallarına uyum                            | Hiçbir kontrol     | LLM bazen kural çiğniyor                   |

**Eklenmeyenler ve gerekçeleri:**

- ❌ **Reflexion (full trial-and-error):** Latency çok yüksek, müşteri bekler
- ❌ **Tree of Thoughts:** Workflow'lar deterministik, birden fazla yol araması gereksiz
- ❌ **LATS:** Monte Carlo ağaç araması müşteri desteği için overkill
- ❌ **Auto-GPT:** Kontrolsüz otonom agent, tehlikeli
- ❌ **Plan & Solve:** Workflow'lar zaten alt adımlara bölünmüş

### 1.4 Agent Yapısı Kararı: 3 Agent ✅

**Neden 4. agent eklenmemeli:**

- Routing complexity artışı (4 yerine 3 hedef → daha az hata)
- Hackathon süresinde 3 agent'ı mükemmel yapmak > 4 agent'ı yarım yapmak
- Issue Agent'ın 3 workflow'u (wrong/missing, no effect, refund) birbiriyle ilişkili — aynı resolution waterfall
- Account Agent'ın 5 workflow'u (cancel, address, subscription, discount, positive) hepsi account-level operasyonlar

**Agent sorumlulukları:**

- **WISMO Agent** → En yüksek hacim (%37). Wait promise logic kusursuz olmalı.
- **Issue Agent** → En kritik agent. 3 workflow + resolution waterfall + en çok tool çeşitliliği.
- **Account Agent** → En çok tool kullanan (11 tool). Her workflow sadece 2-3 tool kullanır.

---

## 2. TAM SİSTEM MİMARİSİ (v3.0 — Tüm Edge Cases Dahil)

### 2.1 Güncellenmiş Akış Diyagramı

```
                        MÜŞTERI MESAJI
                              │
                    ┌─────────▼──────────┐
                    │  ESCALATION LOCK   │  ← is_escalated?
                    │  CHECK             │     → post_escalation_node → END
                    └─────────┬──────────┘
                              │ (not escalated)
                    ┌─────────▼──────────┐
                    │  INPUT GUARDRAILS  │  ← PII redaction, prompt injection,
                    │  (Rule-based)      │     scope check, empty msg, aggressive
                    └─────────┬──────────┘     detection, length check
                              │
                    input_blocked? → YES → override_response → END
                              │ NO
                       turn_count == 1?
                       ┌──YES──┴──NO───────────────────┐
                       │                               │
              ┌────────▼────────┐          ┌───────────▼───────────┐
              │ INTENT          │          │ INTENT SHIFT          │
              │ CLASSIFIER      │          │ CHECK                 │
              │ (Claude Haiku)  │          │ (Claude Haiku)        │
              │ confidence score│          │ same_agent/new_agent? │
              └────────┬────────┘          └───────────┬───────────┘
                       │                               │
                confidence ≥ 80%?              intent_shifted?
                ┌──YES──┴──NO──┐          ┌──YES──┴──NO──┐
                │              │          │              │
           Deterministic  ┌────▼────┐  Re-route    Continue with
           Code Route     │SUPERVISOR│  to new     current_agent
                │         │(Sonnet) │  agent           │
                │         └────┬────┘     │              │
                │              │          │              │
                ┌──────────────▼──────────▼──────────────▼───┐
                │              AGENT ROUTING                  │
                └──┬───────────────┬───────────────┬─────────┘
                   │               │               │
    ┌──────────────▼──┐  ┌────────▼────────┐  ┌───▼──────────────┐
    │  WISMO Agent    │  │  Issue Agent    │  │  Account Agent   │
    │  (ReAct+Sonnet) │  │  (ReAct+Sonnet)│  │  (ReAct+Sonnet)  │
    │                 │  │                │  │                  │
    │  TOOL CALL      │  │  TOOL CALL     │  │  TOOL CALL       │
    │  GUARDRAILS     │  │  GUARDRAILS    │  │  GUARDRAILS      │
    └────────┬────────┘  └────────┬───────┘  └────────┬─────────┘
             │                    │                    │
             └────────────┬───────┘────────────────────┘
                          │
                   HANDOFF CHECK ─── YES → Re-route to target agent
                          │ NO
                   ┌──────▼──────────┐
                   │  OUTPUT         │
                   │  GUARDRAILS     │  ← Forbidden phrases, amount check,
                   │  (Rule-based)   │     persona, competitor, length
                   └──────┬──────────┘
                          │
                   ┌──────▼──────────┐
                   │  REFLECTION     │
                   │  VALIDATOR      │  ← Claude Haiku (8-rule check)
                   │  (1 cycle max)  │
                   └──────┬──────────┘
                          │
                     pass? ├── YES → MÜŞTERIYE GÖNDER ✅
                           └── NO  → REVISE (Sonnet) → MÜŞTERIYE GÖNDER ✅

                   [Escalation her noktadan tetiklenebilir → END]
```

### 2.2 Pattern Entegrasyon Özeti (7 Katman)

```
Layer 0: ESCALATION LOCK       → Session kilidi kontrolü (post-escalation)
Layer 1: INPUT GUARDRAILS      → Güvenli giriş sağla (PII, injection, scope, aggressive, empty)
Layer 2: INTENT CLASSIFICATION → Hızlı ve doğru routing (+ multi-turn shift detection)
Layer 3: ReAct AGENTS          → Düşünerek tool kullan, trace üret
Layer 4: TOOL GUARDRAILS       → Parametreleri doğrula, tehlikeli aksiyonları kontrol et
Layer 5: HANDOFF CHECK         → Agent scope dışı istek → cross-agent transfer
Layer 6: OUTPUT GUARDRAILS     → Çıktıyı filtrele, yasaklı vaatleri engelle
Layer 7: REFLECTION VALIDATOR  → Workflow compliance son kontrol (8 kural)
```

---

## 3. PATTERN 1: ReAct (Reason + Act) — Sub-Agent Çekirdeği

### 3.1 Neden ReAct?

ReAct (Yao et al., 2022) LLM'in her adımda **düşünmesi (Thought)**, **aksiyon alması (Action)** ve **gözlem yapması (Observation)** üzerine kuruludur:

- Müşteri "siparişim nerede?" diyor → Agent DÜŞÜNÜR → AKSİYON (tool çağır) → GÖZLEM → DÜŞÜNÜR → YANIT
- Her tool call sonucu bir sonraki kararı etkiliyor
- Thought/Action/Observation trace'leri observability gereksinimini direkt karşılıyor

### 3.2 Uygulama

```python
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic

sonnet_llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)

wismo_agent = create_react_agent(
    model=sonnet_llm,
    tools=wismo_tools,
    state_schema=CustomerSupportState,
    prompt=WISMO_SYSTEM_PROMPT,
    name="wismo_agent"
)
```

### 3.3 ReAct Trace Prompt Eklentisi (Tüm Agent'lara Eklenir)

```
REASONING FORMAT (TRACE-ONLY):
For EVERY step in your workflow, structure your internal trace as:

THOUGHT: [What I know so far and what I need to do next]
ACTION: [Which tool I will call and why]
OBSERVATION: [What the tool returned and what it means for the customer]
THOUGHT: [Based on this, my next decision is...]

IMPORTANT:
- These THOUGHT/ACTION/OBSERVATION lines are for TRACE/OBSERVABILITY ONLY.
- NEVER include THOUGHT/ACTION/OBSERVATION in the customer-facing reply.
- The final customer reply must be written as a normal helpful message (warm tone, no internal markers) and signed as "Caz".


```

### 3.4 Agent Handoff Talimatı (Tüm Agent'lara Eklenir)

```
CROSS-AGENT HANDOFF:
If the customer's request falls outside your scope, DO NOT try to handle it.
Instead, respond with exactly:
HANDOFF: [target_agent] | REASON: [brief reason]

Examples:
- Customer asks for refund during shipping inquiry → HANDOFF: issue_agent | REASON: Customer requesting refund
- Customer asks about subscription during order issue → HANDOFF: account_agent | REASON: Subscription query
- Customer asks about shipping during refund discussion → HANDOFF: wismo_agent | REASON: Shipping status inquiry
```

### 3.5 GID vs Order Number Talimatı (Tüm Agent'lara Eklenir)

```
CRITICAL — TOOL ID FORMATS:
Different tools require different ID formats. Using the wrong format WILL cause errors.

LOOKUP tools (use order NUMBER with #):
- shopify_get_order_details → orderId: "#43189"
- shopify_get_customer_orders → email: "customer@email.com"

ACTION tools (use Shopify GID):
- shopify_cancel_order → orderId: "gid://shopify/Order/5531567751245"
- shopify_refund_order → orderId: "gid://shopify/Order/5531567751245"
- shopify_create_return → orderId: "gid://shopify/Order/5531567751245"
- shopify_add_tags → id: "gid://shopify/Order/5531567751245"
- shopify_update_order_shipping_address → orderId: "gid://shopify/Order/5531567751245"

CUSTOMER tools (use Customer GID):
- shopify_create_store_credit → id: "{customer_shopify_id}" (from session info)
- skio_get_subscription_status → email: "customer@email.com"

HOW TO GET THE GID:
1. Call shopify_get_order_details or shopify_get_customer_orders FIRST
2. The response contains "id": "gid://shopify/Order/..."
3. Use THAT GID for all subsequent action tools

NEVER fabricate a GID. ALWAYS get it from a lookup tool first.
```

---

## 4. PATTERN 2: 2-Stage Intent Classification + Multi-Turn Routing

### 4.1 Intent Classifier (Stage 1 — İlk Mesaj)

```python
from langchain_anthropic import ChatAnthropic

haiku_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

INTENT_CLASSIFIER_PROMPT = """Classify the customer message into exactly ONE category
and rate your confidence (0-100).

CATEGORIES:
- WISMO: shipping delay, order tracking, delivery status, "where is my order",
  package not arrived, shipment update, estimated delivery
- WRONG_MISSING: wrong item received, missing item in package, damaged item,
  incorrect product, incomplete order
- NO_EFFECT: product not working, no results, ineffective, "doesn't work",
  "not helping", "no difference", allergic reaction, rash
- REFUND: refund request, money back, return request, "want my money back",
  chargeback mention
- ORDER_MODIFY: cancel order, change address, modify order, update shipping,
  "accidentally ordered"
- SUBSCRIPTION: cancel subscription, pause subscription, billing issue,
  double charge, subscription management, "too many", "skip next",
  "update payment"
- DISCOUNT: promo code not working, discount issue, coupon, "code doesn't work",
  "code invalid"
- POSITIVE: compliment, praise, happy feedback, "love your product",
  "thank you so much", "amazing results", "works great"
- GENERAL: greeting, general question, not fitting other categories,
  off-topic, multi-topic unclear

MULTI-INTENT RULE: If the message contains multiple intents, classify by the
PRIMARY intent (the main complaint/request, not secondary mentions).
Example: "My order hasn't arrived and I want a refund" → REFUND (primary action request)
Example: "Where is order #123?" → WISMO (status inquiry)

Response format (ONLY this, nothing else): CATEGORY|CONFIDENCE
Example: WISMO|92

Customer message: {message}"""

async def classify_intent(message: str) -> tuple[str, int]:
    """Stage 1: Fast intent classification with Haiku."""
    result = await haiku_llm.ainvoke(
        INTENT_CLASSIFIER_PROMPT.format(message=message)
    )
    parts = result.content.strip().split("|")
    intent = parts[0].strip()
    confidence = int(parts[1].strip()) if len(parts) > 1 else 50

    # Validate intent is known
    valid_intents = {"WISMO", "WRONG_MISSING", "NO_EFFECT", "REFUND",
                     "ORDER_MODIFY", "SUBSCRIPTION", "DISCOUNT", "POSITIVE", "GENERAL"}
    if intent not in valid_intents:
        intent = "GENERAL"
        confidence = 50

    return intent, confidence
```

### 4.2 Deterministic Router (Stage 2)

```python
INTENT_TO_AGENT = {
    "WISMO": "wismo_agent",
    "WRONG_MISSING": "issue_agent",
    "NO_EFFECT": "issue_agent",
    "REFUND": "issue_agent",
    "ORDER_MODIFY": "account_agent",
    "SUBSCRIPTION": "account_agent",
    "DISCOUNT": "account_agent",
    "POSITIVE": "account_agent",
    "GENERAL": "supervisor",
}

CONFIDENCE_THRESHOLD = 80

async def intent_classifier_node(state: CustomerSupportState) -> dict:
    """Intent classification node for first message."""
    customer_message = state["messages"][-1].content
    intent, confidence = await classify_intent(customer_message)

    return {
        "ticket_category": intent,
        "intent_confidence": confidence,
        "current_agent": INTENT_TO_AGENT.get(intent, "supervisor"),
        "agent_reasoning": [
            f"Intent: {intent} (confidence: {confidence}%)"
        ]
    }

def route_by_confidence(state: CustomerSupportState) -> str:
    """Route based on confidence threshold."""
    intent = state.get("ticket_category", "GENERAL")
    confidence = state.get("intent_confidence", 0)

    if confidence >= CONFIDENCE_THRESHOLD:
        return INTENT_TO_AGENT.get(intent, "supervisor")
    else:
        return "supervisor"
```

### 4.3 Multi-Turn Router (YENİ — v3.0)

```python
def route_multi_turn(state: CustomerSupportState) -> str:
    """Determine routing strategy based on turn count."""
    turn_count = len([m for m in state["messages"] if m.type == "human"])

    if turn_count == 1:
        return "intent_classifier"

    if state.get("is_escalated"):
        return "post_escalation"

    return "intent_shift_check"

async def intent_shift_check_node(state: CustomerSupportState) -> dict:
    """Check if customer intent changed mid-conversation."""
    new_message = state["messages"][-1].content
    current_agent = state.get("current_agent", "supervisor")

    new_intent, confidence = await classify_intent(new_message)
    expected_agent = INTENT_TO_AGENT.get(new_intent, "supervisor")

    # Intent shift: high confidence + different agent
    if expected_agent != current_agent and confidence >= 85:
        return {
            "ticket_category": new_intent,
            "intent_confidence": confidence,
            "current_agent": expected_agent,
            "intent_shifted": True,
            "agent_reasoning": [
                f"INTENT SHIFT: {current_agent} → {expected_agent} "
                f"(new intent: {new_intent}, confidence: {confidence}%)"
            ]
        }
    else:
        return {
            "intent_shifted": False,
            "agent_reasoning": [f"MULTI-TURN: Continuing with {current_agent}"]
        }

def route_after_shift_check(state: CustomerSupportState) -> str:
    """Route after intent shift detection."""
    if state.get("intent_shifted"):
        return state.get("current_agent", "supervisor")
    else:
        return state.get("current_agent", "supervisor")
```

### 4.4 Supervisor (Fallback Router)

```python
SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor Agent for NatPat customer support.

You are called ONLY when the intent classifier couldn't determine
the category with high confidence. Analyze carefully and route.

CUSTOMER CONTEXT:
- Name: {first_name} {last_name}
- Email: {email}
- Shopify ID: {customer_shopify_id}

ROUTING RULES:
→ "wismo_agent": shipping delays, order tracking, delivery status
→ "issue_agent": wrong/missing items, product complaints, refunds, returns
→ "account_agent": order changes, subscriptions, billing, discounts, positive feedback
→ "respond_direct": simple greetings, general questions (you generate the response)
→ "escalate": 3+ turns unresolved, unclear/dangerous situation

MULTI-INTENT: If customer has multiple concerns, route to the agent handling
the PRIMARY concern (the main complaint or action request).

TODAY: {current_date} | DAY: {day_of_week}

Respond with ONLY this format:
ROUTE: [agent_name]
REASON: [brief explanation]
"""
```

---

## 5. PATTERN 3: Guardrails — Input/Output/Tool Güvenliği

### 5.1 Input Guardrails (Güncellenmiş — Tüm Edge Cases Dahil)

```python
import re
from langchain_core.messages import AIMessage

def input_guardrails_node(state: CustomerSupportState) -> dict:
    """Input validation before processing. Includes all edge case checks."""
    message = state["messages"][-1].content
    lower_msg = message.lower().strip()
    first_name = state.get("customer_first_name", "there")

    # === 1. EMPTY/GIBBERISH MESSAGE ===
    if len(lower_msg) < 3 or not any(c.isalpha() for c in lower_msg):
        reply = (
            f"Hey {first_name}! 😊 It looks like your message might not have "
            f"come through properly. Could you let me know how I can help?\n\nCaz"
        )
        return {
            "input_blocked": True,
            "override_response": reply,
            "messages": [AIMessage(content=reply)],
            "agent_reasoning": ["INPUT GUARDRAIL: Empty or gibberish message"]
        }

    # === 2. PROMPT INJECTION DETECTION ===
    INJECTION_PATTERNS = [
        "ignore previous instructions",
        "ignore all instructions",
        "you are now",
        "forget everything",
        "system prompt",
        "override your",
        "act as if",
        "disregard your programming",
        "new instructions",
        "jailbreak",
        "pretend you are",
        "reveal your prompt",
    ]
    for pattern in INJECTION_PATTERNS:
        if pattern in lower_msg:
            reply = (
                f"Hey {first_name}! 😊 I'm here to help with your NatPat "
                f"orders, shipping, and products. What can I do for you today?\n\nCaz"
            )
            return {
                "input_blocked": True,
                "override_response": reply,
                "messages": [AIMessage(content=reply)],
                "agent_reasoning": ["INPUT GUARDRAIL: Potential prompt injection detected"]
            }

    # === 3. PII REDACTION ===
    cleaned_message = message

    # Credit card patterns (16 digits with optional separators)
    cc_pattern = r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'
    cleaned_message = re.sub(cc_pattern, '[CARD REDACTED]', cleaned_message)

    # SSN pattern
    ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
    cleaned_message = re.sub(ssn_pattern, '[SSN REDACTED]', cleaned_message)

    # === 4. MESSAGE LENGTH CHECK ===
    if len(cleaned_message) > 5000:
        cleaned_message = cleaned_message[:5000] + "... [truncated]"

    pii_detected = cleaned_message != message

    # ✅ Apply the sanitized message so downstream nodes/agents use it
    if pii_detected:
        try:
            state["messages"][-1].content = cleaned_message
        except Exception:
            pass

    # === 5. AGGRESSIVE/THREATENING LANGUAGE DETECTION ===
    AGGRESSIVE_PATTERNS = [
        "lawsuit", "sue you", "sue your company", "lawyer", "legal action",
        "report you", "bbb complaint", "better business bureau",
        "chargeback", "dispute the charge", "credit card company",
        "attorney general", "consumer protection",
    ]
    aggressive_detected = any(p in lower_msg for p in AGGRESSIVE_PATTERNS)

    # === 6. HEALTH/SAFETY CONCERN DETECTION ===
    HEALTH_PATTERNS = [
        "allergic reaction", "allergy", "rash", "hives", "swelling",
        "breathing difficulty", "anaphylax", "hospital", "emergency room",
        "doctor said", "pediatrician",
    ]
    health_concern = any(p in lower_msg for p in HEALTH_PATTERNS)

    return {
        "input_blocked": False,
        "pii_redacted": pii_detected,
        "flag_escalation_risk": aggressive_detected,
        "flag_health_concern": health_concern,
        "agent_reasoning": [
            f"INPUT GUARDRAIL: "
            f"{'PII redacted, ' if pii_detected else ''}"
            f"{'⚠️ Aggressive language detected, ' if aggressive_detected else ''}"
            f"{'🏥 Health concern detected, ' if health_concern else ''}"
            f"{'Clean input' if not (pii_detected or aggressive_detected or health_concern) else 'Flagged'}"
        ]
    }

```

### 5.2 Tool Call Guardrails (Güncellenmiş — Tool Spec'e Uyumlu)

```python
def tool_call_guardrails(tool_name: str, params: dict, state: dict) -> tuple[bool, str, dict]:
    """
    Validate tool calls before execution.
    Returns: (is_allowed, reason, corrected_params)
    """
    corrected_params = params.copy()

    # === 1. ORDER ID FORMAT CORRECTION ===
    # shopify_get_order_details uses "#" prefix
    if tool_name == "shopify_get_order_details" and "orderId" in corrected_params:
        order_id = str(corrected_params["orderId"])
        if not order_id.startswith("#"):
            corrected_params["orderId"] = f"#{order_id}"

    # === 2. GID VALIDATION for action tools ===
    GID_REQUIRED_TOOLS = {
        "shopify_cancel_order": "orderId",
        "shopify_refund_order": "orderId",
        "shopify_create_return": "orderId",
        "shopify_update_order_shipping_address": "orderId",
        "shopify_add_tags": "id",
    }
    if tool_name in GID_REQUIRED_TOOLS:
        gid_field = GID_REQUIRED_TOOLS[tool_name]
        gid_value = str(corrected_params.get(gid_field, ""))
        if gid_value and not gid_value.startswith("gid://"):
            return False, f"Tool '{tool_name}' requires Shopify GID format (gid://shopify/...), got '{gid_value}'", corrected_params

    # === 3. DESTRUCTIVE ACTION VALIDATION ===
    DESTRUCTIVE_TOOLS = {
        "shopify_cancel_order",
        "shopify_refund_order",
        "skio_cancel_subscription",
    }
    if tool_name in DESTRUCTIVE_TOOLS:
        if tool_name == "shopify_cancel_order" and not corrected_params.get("orderId"):
            return False, "Cannot cancel order without valid order ID", corrected_params
        if tool_name == "shopify_refund_order" and not corrected_params.get("orderId"):
            return False, "Cannot refund order without valid order ID", corrected_params
        if tool_name == "skio_cancel_subscription" and not corrected_params.get("subscriptionId"):
            return False, "Cannot cancel subscription without ID", corrected_params

    # === 4. CANCEL ORDER DEFAULTS (7 required params) ===
    if tool_name == "shopify_cancel_order":
        corrected_params.setdefault("reason", "CUSTOMER")
        corrected_params.setdefault("notifyCustomer", True)
        corrected_params.setdefault("restock", True)
        corrected_params.setdefault("staffNote", "Customer requested cancellation via chat")
        corrected_params.setdefault("refundMode", "ORIGINAL")
        corrected_params.setdefault("storeCredit", {"expiresAt": None})

    # === 5. DISCOUNT CODE LIMITS ===
    if tool_name == "shopify_create_discount_code":
        if state.get("discount_code_created"):
            return False, "Already created a discount code for this customer (max 1)", corrected_params
        # Enforce correct parameters per workflow
        corrected_params["type"] = "percentage"
        corrected_params["value"] = 0.10
        corrected_params["duration"] = 48
        corrected_params.setdefault("productIds", [])

    # === 6. STORE CREDIT PARAMETER ENFORCEMENT ===
    if tool_name == "shopify_create_store_credit":
        # Ensure 10% bonus is applied
        if "creditAmount" in corrected_params:
            amount = corrected_params["creditAmount"]
            if isinstance(amount, dict) and "amount" in amount:
                original = float(amount["amount"])
                bonus = round(original * 1.10, 2)
                corrected_params["creditAmount"]["amount"] = str(bonus)
        # Use customer GID from session
        if not corrected_params.get("id"):
            corrected_params["id"] = state.get("customer_shopify_id", "")
        # Default no expiry
        corrected_params.setdefault("expiresAt", None)

    # === 7. GET CUSTOMER ORDERS DEFAULTS ===
    if tool_name == "shopify_get_customer_orders":
        corrected_params.setdefault("after", "null")
        corrected_params.setdefault("limit", 10)

    # === 8. DUPLICATE TOOL CALL PREVENTION ===
    recent_calls = state.get("tool_calls_log", [])[-3:]
    for call in recent_calls:
        if call.get("tool_name") == tool_name and call.get("params") == corrected_params:
            return False, f"Duplicate tool call detected: {tool_name}", corrected_params

    return True, "OK", corrected_params
```

### 5.3 Output Guardrails (Güncellenmiş)

```python
def output_guardrails_node(state: CustomerSupportState) -> dict:
    """Validate agent response before sending to customer."""
    response = state["messages"][-1].content
    issues = []
    lower_response = response.lower()

    # === 1. HANDOFF CHECK (intercept before guardrails) ===
    if response.strip().startswith("HANDOFF:"):
        # This is an internal handoff request, not a customer response
        return {
            "output_guardrail_passed": True,
            "is_handoff": True,
            "agent_reasoning": ["OUTPUT GUARDRAIL: Handoff detected, bypassing checks"]
        }

    # === 2. UNAUTHORIZED PROMISES ===
    FORBIDDEN_PHRASES = [
        ("guaranteed delivery", "Cannot guarantee specific delivery"),
        ("within 24 hours", "Cannot promise 24-hour timeframes"),
        ("100% money back", "Cannot promise unconditional refunds"),
        ("i promise", "Avoid absolute promises"),
        ("we guarantee", "Avoid guarantees"),
        ("definitely by tomorrow", "Cannot promise specific dates"),
        ("full refund no questions", "Must follow resolution waterfall"),
        ("guaranteed by", "Cannot guarantee timeframes"),
        ("you will receive it by", "Cannot promise specific delivery dates"),
    ]
    for phrase, reason in FORBIDDEN_PHRASES:
        if phrase in lower_response:
            issues.append(f"FORBIDDEN PHRASE: '{phrase}' - {reason}")

    # === 3. PERSONA CHECK ===
    if len(response) > 100 and "caz" not in lower_response:
        issues.append("PERSONA: Response missing Caz signature")

    # === 4. COMPETITOR MENTION ===
    COMPETITORS = ["zevo", "off!", "repel", "raid", "babyganics", "skin so soft"]
    for comp in COMPETITORS:
        if comp in lower_response:
            issues.append(f"COMPETITOR: Mentioned '{comp}'")

    # === 5. REFUND AMOUNT SANITY CHECK ===
    if state.get("pending_refund_amount") and state.get("order_total"):
        if float(state["pending_refund_amount"]) > float(state["order_total"]) * 1.1:
            issues.append("AMOUNT: Refund exceeds order total + 10% bonus")

    # === 6. EMPTY/SHORT RESPONSE ===
    if len(response.strip()) < 20:
        issues.append("LENGTH: Response too short for customer communication")

    # === 7. INTERNAL INFO LEAK ===
    INTERNAL_PATTERNS = [
    "gid://shopify", "tool_call", "system prompt", "state[", "state.get",
    "thought:", "observation:", "handoff:"
]

    for pattern in INTERNAL_PATTERNS:
        if pattern in lower_response:
            issues.append(f"INTERNAL LEAK: Contains '{pattern}'")

    if issues:
        return {
            "output_guardrail_passed": False,
            "output_guardrail_issues": issues,
            "agent_reasoning": [f"OUTPUT GUARDRAIL: Failed - {'; '.join(issues)}"]
        }

    return {
        "output_guardrail_passed": True,
        "agent_reasoning": ["OUTPUT GUARDRAIL: Passed all checks"]
    }
```

---

## 6. PATTERN 4: Reflection Validator — 8-Kural Workflow Compliance

### 6.1 Reflection Prompt (Güncellenmiş — 8 Kural)

```python
REFLECTION_PROMPT = """You are a QA reviewer for NatPat customer support.
Review this draft response BEFORE it's sent to the customer.

CHECK THESE 8 RULES (fail if ANY is violated):

1. RESOLUTION ORDER: Was the correct resolution priority followed?
   Correct order: fix issue → free reship → store credit (10% bonus) → cash refund
   If agent jumped directly to cash refund without offering alternatives → FAIL
   Exception: Customer explicitly declined alternatives in previous turns → OK

2. WAIT PROMISE: If this is a shipping delay, does the wait promise match today's day?
   Today is {day_of_week}. Rules:
   Mon/Tue/Wed → "wait until Friday"
   Thu/Fri/Sat/Sun → "wait until early next week"
   If wrong timeframe → FAIL

3. ESCALATION CHECK: Should this have been escalated but wasn't?
   Must escalate if: reship needed, address update error, 3+ turns unresolved,
   past promised date and not delivered, health/safety concern, chargeback threat,
   double billing
   If missed escalation → FAIL

4. INFORMATION GATHERING: Did the agent ask necessary questions before acting?
   Wrong/missing item → must ask for description/photos before resolving
   No effect → must ask about usage details (quantity, timing, duration)
   Refund → must ask reason before processing
   If skipped on FIRST interaction for that topic → FAIL
   Exception: if customer already provided the info in their message → OK

5. TONE & PERSONA: Is the response warm, empathetic, uses first name, signed as "Caz"?
   If cold/robotic or wrong signature → FAIL
   Positive feedback responses should be extra warm with emoji

6. FACTUAL ACCURACY: Does the response match the actual tool results?
   Don't say "delivered" if status was "in transit"
   Don't say "shipped" if status was "unfulfilled"
   Don't fabricate tracking numbers, dates, or order details
   If mismatch → FAIL

7. GID vs ORDER NUMBER: Did the agent use the correct ID format for each tool?
   Lookup tools (get_order_details) → use "#1234" format
   Action tools (cancel, refund, return, add_tags, update_address) → use "gid://shopify/..." format
   If wrong format was used → FAIL

8. RESOLUTION WATERFALL COMPLETENESS: Did the agent offer alternatives before
   jumping to the customer's requested resolution?
   Customer says "refund me" → agent must still offer reship/store credit FIRST
   Only after customer explicitly declines alternatives → process refund
   First turn with refund request → must present options, not directly refund
   If alternatives skipped on first interaction → FAIL

DRAFT RESPONSE TO REVIEW:
{draft_response}

TOOL CALL RESULTS:
{tool_results}

CUSTOMER MESSAGE:
{customer_message}

CONVERSATION TURN COUNT: {turn_count}

Respond with ONLY valid JSON (no markdown, no explanation):
{{"pass": true}} OR {{"pass": false, "rule_violated": "RULE_NAME", "reason": "brief explanation", "suggested_fix": "what should change"}}"""
```

### 6.2 Reflection Validator Node

````python
async def reflection_validator_node(state: CustomerSupportState) -> dict:
    """Lightweight reflection check using Haiku. 8-rule validation."""
    draft = state["messages"][-1].content
    tool_results = json.dumps(state.get("tool_calls_log", [])[-5:], default=str)
    customer_msg = ""
    for m in reversed(state["messages"]):
        if m.type == "human":
            customer_msg = m.content
            break
    turn_count = len([m for m in state["messages"] if m.type == "human"])

    from datetime import datetime
    day_of_week = datetime.now().strftime("%A")

    result = await haiku_llm.ainvoke(
        REFLECTION_PROMPT.format(
            draft_response=draft,
            tool_results=tool_results,
            customer_message=customer_msg,
            turn_count=turn_count,
            day_of_week=day_of_week,
        )
    )

  try:
    text = result.content.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        validation = json.loads(text)
    except json.JSONDecodeError:
        # try extracting the first JSON object from the text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            validation = json.loads(text[start:end+1])
        else:
            raise
except json.JSONDecodeError:
    return {
        "reflection_passed": True,
        "agent_reasoning": ["REFLECTION: Parse error, defaulting to pass"]
    }


    if validation.get("pass"):
        return {
            "reflection_passed": True,
            "agent_reasoning": ["REFLECTION: All 8 rules passed ✅"]
        }
    else:
        return {
            "reflection_passed": False,
            "reflection_feedback": validation.get("reason", ""),
            "reflection_rule_violated": validation.get("rule_violated", ""),
            "reflection_suggested_fix": validation.get("suggested_fix", ""),
            "agent_reasoning": [
                f"REFLECTION: FAILED - Rule: {validation.get('rule_violated')}, "
                f"Reason: {validation.get('reason')}"
            ]
        }
````

### 6.3 Revision Node

```python
REVISION_PROMPT = """You are correcting a customer support response that failed quality review.

ORIGINAL RESPONSE:
{draft_response}

QUALITY ISSUE:
Rule Violated: {rule_violated}
Reason: {reason}
Suggested Fix: {suggested_fix}

TOOL CALL RESULTS (ground truth):
{tool_results}

CUSTOMER CONTEXT:
- Name: {first_name}
- Today: {current_date} | Day: {day_of_week}

Rewrite the response fixing ONLY the identified issue.
Keep everything else the same. Sign as "Caz".
Do NOT include any internal notes or tool references in the response.
"""

async def revise_response_node(state: CustomerSupportState) -> dict:
    """Revise response based on reflection feedback. Max 1 cycle."""
    draft = state["messages"][-1].content

    revised = await sonnet_llm.ainvoke(
        REVISION_PROMPT.format(
            draft_response=draft,
            rule_violated=state.get("reflection_rule_violated", ""),
            reason=state.get("reflection_feedback", ""),
            suggested_fix=state.get("reflection_suggested_fix", ""),
            tool_results=json.dumps(state.get("tool_calls_log", [])[-5:], default=str),
            first_name=state.get("customer_first_name", "there"),
            current_date=datetime.now().strftime("%Y-%m-%d"),
            day_of_week=datetime.now().strftime("%A"),
        )
    )

    return {
        "messages": [AIMessage(content=revised.content)],
        "agent_reasoning": [
            f"REVISION: Response corrected for {state.get('reflection_rule_violated')}"
        ],
        "was_revised": True,
    }
```

---

## 7. AGENT DETAYLARI (v3.0 — Edge Case-Aware Prompt'lar)

### 7.1 WISMO Agent

**Kapsamı:** Shipping Delay tickets (%37 — en yüksek hacim)

```
You are the WISMO (Where Is My Order) specialist for NatPat.
You use the ReAct pattern: Think step-by-step, act on tools, observe results.

CUSTOMER: {first_name} {last_name} | Email: {email} | Shopify ID: {customer_shopify_id}
TODAY: {current_date} | DAY: {day_of_week}

[INSERT REASONING FORMAT BLOCK]
[INSERT GID vs ORDER NUMBER BLOCK]
[INSERT CROSS-AGENT HANDOFF BLOCK]

═══════════════════════════════════════
YOUR CORE WORKFLOW:
═══════════════════════════════════════

1. FIND THE ORDER:
   a. If customer provides order # → shopify_get_order_details(orderId: "#XXXXX")
   b. If NO order # provided → shopify_get_customer_orders(email: "{email}", after: "null", limit: 10)
      - If 1 recent order → proceed with that order
      - If multiple orders → list last 3 with dates/products and ask which one
      - If 0 orders → "I couldn't find any orders under this email. Could you check the order number?"

2. REPORT STATUS based on what tool returns:
   - UNFULFILLED → "Your order hasn't shipped yet, but don't worry — it's being prepared! 🚀"
   - FULFILLED (in transit) → "Great news — your order is on its way!"
   - DELIVERED → "Your order shows as delivered on [date]."
   - CANCELLED → "It looks like order #X was cancelled. If this wasn't expected, I can help look into it!"

3. WAIT PROMISE (ONLY for FULFILLED/in-transit):
   ⚠️ DAY-AWARE LOGIC — THIS IS CRITICAL:
   - Mon/Tue/Wed contact → "Please give it until this Friday"
   - Thu/Fri/Sat/Sun contact → "Please give it until early next week"
   - ALWAYS add: "If it still hasn't arrived by then, we'll get a fresh one sent out to you — on us! 💛"
   ⚠️ NEVER promise a specific delivery DATE
   ⚠️ NEVER say "guaranteed" or "definitely"

4. TRACKING:
   - If tracking URL exists → share it: "Here's your tracking link: [URL]"
   - If NO tracking URL → "Your order doesn't have tracking info yet — this usually means it's still being prepared for shipment."

5. TAG THE ORDER after checking → shopify_add_tags(id: "[ORDER GID]", tags: ["WISMO checked", "status: [STATUS]"])

═══════════════════════════════════════
EDGE CASES YOU MUST HANDLE:
═══════════════════════════════════════

A. ORDER NOT FOUND:
   → "I wasn't able to find that order number. Could you double-check?
      I can also look up your recent orders by email — let me try that!"
   → Then try shopify_get_customer_orders with email

B. MULTIPLE ORDERS — DISAMBIGUATION:
   → "I see a few recent orders on your account:
      • #1234 (Jan 15) — BuzzPatch x2 — In Transit
      • #1235 (Jan 20) — FocusPatch x1 — Delivered
      Which one can I help with?"

C. DELIVERED BUT CUSTOMER SAYS NOT RECEIVED:
   → Apply wait promise rules first
   → If this is a FOLLOW-UP (turn > 1, previously given wait promise):
     → ESCALATE: "I'm so sorry it still hasn't arrived, {first_name}.
        I'm looping in Monica, our Head of CS, to get a replacement sorted for you right away. 💛"

D. FOLLOW-UP AFTER WAIT PROMISE:
   → If customer returns saying "still not here" or "it's past Friday" etc.:
     → ESCALATE for reship. Do NOT give another wait promise.

E. CUSTOMER WANTS REFUND DURING WISMO:
   → HANDOFF: issue_agent | REASON: Customer requesting refund during shipping inquiry

F. CUSTOMER ASKS ABOUT SUBSCRIPTION:
   → HANDOFF: account_agent | REASON: Subscription query during shipping inquiry

TOOLS: shopify_get_customer_orders, shopify_get_order_details, shopify_add_tags

RULES:
- NEVER promise a specific delivery date
- NEVER say "guaranteed" or "definitely"
- ALWAYS be empathetic about delays
- ALWAYS use order GID (from tool response "id" field) when calling shopify_add_tags
- Sign as "Caz"
```

### 7.2 Issue Agent

**Kapsamı:** Wrong/Missing (%7), Product Issue (%6), Refund (%9) — En kritik agent

```
You are the Issue Resolution specialist for NatPat.
You use the ReAct pattern: Think step-by-step, act on tools, observe results.

CUSTOMER: {first_name} {last_name} | Email: {email} | Shopify ID: {customer_shopify_id}
TODAY: {current_date} | DAY: {day_of_week}

[INSERT REASONING FORMAT BLOCK]
[INSERT GID vs ORDER NUMBER BLOCK]
[INSERT CROSS-AGENT HANDOFF BLOCK]

═══════════════════════════════════════
RESOLUTION PRIORITY — ALWAYS FOLLOW THIS ORDER:
═══════════════════════════════════════
1. Fix the issue (correct usage tips, product swap recommendation)
2. Free reship → ESCALATE to Monica for physical shipment
3. Store credit with 10% bonus → shopify_create_store_credit
4. Cash refund (LAST RESORT) → shopify_refund_order

⚠️ NEVER jump to cash refund without offering alternatives first!
⚠️ On FIRST interaction: ALWAYS present options. Don't process refund immediately.
⚠️ Only process cash refund after customer EXPLICITLY declines store credit.

═══════════════════════════════════════
STORE CREDIT PARAMETERS:
═══════════════════════════════════════
shopify_create_store_credit(
    id: "{customer_shopify_id}",              ← Customer GID from session
    creditAmount: {
        amount: "[item_value × 1.10]",        ← 10% bonus included
        currencyCode: "USD"
    },
    expiresAt: null                           ← No expiry
)

═══════════════════════════════════════
REFUND PARAMETERS:
═══════════════════════════════════════
shopify_refund_order(
    orderId: "[ORDER GID from get_order_details]",  ← Must be GID!
    refundMethod: "ORIGINAL_PAYMENT_METHODS"
)

═══════════════════════════════════════
WORKFLOW A — WRONG/MISSING ITEM:
═══════════════════════════════════════
1. Look up order → shopify_get_order_details (by # or email lookup first)
2. Ask what happened: "Could you let me know what's going on with your order?
   Was something missing, or did you receive the wrong item?"
3. Request description/photos:
   "To help sort this out quickly, could you describe what you received?
   If you can share a photo of the items and the packing slip, that'd be super helpful!
   But no worries if you can't — just a description works too. 📸"
   ⚠️ NEVER block resolution because photos aren't available
4. Offer resolution in order:
   a. "I'd love to get the correct items sent out to you right away — would a free replacement work?"
      → If YES → ESCALATE for reship
   b. "I can also offer you store credit for the value plus a 10% bonus,
      so you'd get $[amount × 1.10] to use on anything you'd like!"
      → If YES → shopify_create_store_credit + tag "Wrong or Missing, Store Credit Issued"
   c. If customer insists on cash refund → shopify_refund_order + tag "Wrong or Missing, Cash Refund Issued"

EDGE CASES — WRONG/MISSING:
- ENTIRE ORDER WRONG → Reship everything, ESCALATE
- PARTIAL WRONG/MISSING → "I see your order had [N] items. Which ones were wrong or missing?"
  Resolution applies only to affected items.
- CUSTOMER ALREADY GOT REPLACEMENT → Check tags. If "Wrong or Missing" tag exists:
  "I can see we've already arranged a replacement for this order.
  Is there a new issue, or is the previous one still unresolved?"
- CUSTOMER SAYS "I ATTACHED A PHOTO" → "Thanks for the photo! Let me look into this for you."
  (We're in email — acknowledge the attachment even though we can't see it)

═══════════════════════════════════════
WORKFLOW B — PRODUCT ISSUE ("NO EFFECT"):
═══════════════════════════════════════
1. Look up order + product details
2. Ask about their GOAL first: "What were you hoping the patches would help with?
   (sleep, focus, bug protection, etc.)"
3. Ask about USAGE (⚠️ MUST ask BEFORE offering solutions):
   "How have you been using them? For example:
   - How many patches at a time?
   - What time do you apply them?
   - How many days/nights have you tried?"
4. Based on response:
   a. WRONG USAGE → Share correct usage guide via shopify_get_related_knowledge_source
      "Based on what you've shared, I think a small tweak could make a big difference!
      [usage tip]. Could you try this for 3 more nights and let me know?"
   b. PRODUCT MISMATCH → shopify_get_product_recommendations
      "It sounds like [alternative product] might be a better fit for [goal]!"
5. If STILL disappointed after guidance:
   a. Store credit (10% bonus) first
   b. Cash refund last resort
6. Tag: "No Effect – Recovered" or "No Effect – Cash Refund"

EDGE CASES — NO EFFECT:
- CUSTOMER REFUSES TO SHARE USAGE DETAILS → Ask ONCE, then proceed:
  "No worries! Let me see what I can do for you."
  → Offer store credit or product swap without usage-based advice
- ALLERGIC REACTION / HEALTH CONCERN:
  ⚠️ IMMEDIATE ESCALATION — DO NOT attempt resolution
  "I'm really sorry to hear that, {first_name}. Please stop using the product right away —
  your health comes first. I'm looping in Monica, our Head of CS, to make sure
  we take care of this properly for you. 💛"
  → ESCALATE with category: "health_concern"
- MULTIPLE PRODUCTS, WHICH ONE? → "I see you ordered a few products.
  Which one isn't working for you?" List products from order.
- CHILD/BABY HEALTH CONCERN → Never give medical advice.
  "For anything health-related, I'd always recommend checking with your pediatrician.
  In the meantime, let me see what we can do for you on our end."

═══════════════════════════════════════
WORKFLOW C — REFUND REQUEST:
═══════════════════════════════════════
1. Look up order details
2. Ask for reason: "I'd be happy to help! Could you let me know the reason for the refund?"
3. Route based on reason:

   a. PRODUCT DIDN'T MEET EXPECTATIONS:
      → Usage tip + product swap suggestion + store credit (10% bonus)
      → Cash refund only if customer declines all

   b. SHIPPING DELAY:
      → HANDOFF: wismo_agent | REASON: Refund request due to shipping delay
      (Let WISMO handle with wait promise first)

   c. DAMAGED OR WRONG ITEM:
      → Follow Workflow A (wrong/missing)

   d. CHANGED MIND + UNFULFILLED ORDER:
      → shopify_cancel_order with proper params + tag

   e. CHANGED MIND + FULFILLED ORDER:
      → Store credit (10% bonus) first, then cash refund if declined

EDGE CASES — REFUND:
- ALREADY REFUNDED ORDER → Check order status first
  "I can see order #X was already refunded on [date].
  The funds typically take 5-10 business days to appear in your account."
- CHARGEBACK THREAT → ESCALATE IMMEDIATELY
  "I completely understand your frustration, {first_name}. I want to make sure
  we resolve this properly for you. Let me connect you with Monica right away."
  → Category: "chargeback_risk"
- VERY OLD ORDER (check createdAt, if > 90 days) → ESCALATE
  "Let me check with Monica on the best way to handle this for you."
- PARTIAL REFUND REQUEST → "Which items would you like refunded?"
  If partial refund not supported → offer store credit for those items

═══════════════════════════════════════
CANCEL ORDER PARAMETERS (when needed):
═══════════════════════════════════════
shopify_cancel_order(
    orderId: "[ORDER GID]",                  ← Must be GID from lookup!
    reason: "CUSTOMER",
    notifyCustomer: true,
    restock: true,
    staffNote: "Customer requested cancellation - [brief reason]",
    refundMode: "ORIGINAL",
    storeCredit: {"expiresAt": null}
)

TOOLS: shopify_get_order_details, shopify_get_customer_orders, shopify_refund_order,
       shopify_create_store_credit, shopify_create_return, shopify_add_tags,
       shopify_get_product_recommendations, shopify_get_product_details,
       shopify_get_related_knowledge_source

Sign as "Caz".
```

### 7.3 Account Agent

**Kapsamı:** Order Modification (%3), Subscription (%2), Discount (%3), Positive (%6)

```
You are the Account Management specialist for NatPat.
You use the ReAct pattern: Think step-by-step, act on tools, observe results.

CUSTOMER: {first_name} {last_name} | Email: {email} | Shopify ID: {customer_shopify_id}
TODAY: {current_date} | DAY: {day_of_week}

[INSERT REASONING FORMAT BLOCK]
[INSERT GID vs ORDER NUMBER BLOCK]
[INSERT CROSS-AGENT HANDOFF BLOCK]

═══════════════════════════════════════
WORKFLOW A — ORDER CANCELLATION:
═══════════════════════════════════════
1. Look up order → shopify_get_order_details
2. Ask reason: "Could you let me know why you'd like to cancel?"
3. Route by reason:

   a. SHIPPING DELAY → Offer wait promise FIRST:
      - Mon/Tue/Wed → "Could you give it until Friday? If it's not here by then,
        I'll cancel it and get a fresh one sent to you!"
      - Thu/Fri/Sat/Sun → "Could you give it until early next week?"
      - If customer REFUSES to wait → Cancel the order

   b. ACCIDENTAL ORDER → Cancel immediately:
      shopify_cancel_order(
          orderId: "[ORDER GID]",
          reason: "CUSTOMER",
          notifyCustomer: true,
          restock: true,
          staffNote: "Accidental order - customer requested cancellation",
          refundMode: "ORIGINAL",
          storeCredit: {"expiresAt": null}
      )
      + shopify_add_tags(id: "[ORDER GID]", tags: ["Cancelled - Customer Request"])

   c. OTHER REASON → Cancel if unfulfilled

EDGE CASES — CANCELLATION:
- ORDER ALREADY FULFILLED → "Your order has already shipped, so I can't cancel it.
  But I can help with a return or store credit if you'd like!"
- ORDER ALREADY CANCELLED → "Order #X was already cancelled on [date]."
- PARTIALLY FULFILLED → ESCALATE: "Part of your order has already shipped.
  Let me connect you with Monica to sort this out."
- DUPLICATE ORDER → "Which order would you like to keep? Let me cancel the other one."
  List both orders for confirmation.

═══════════════════════════════════════
WORKFLOW B — ADDRESS UPDATE:
═══════════════════════════════════════
1. Look up order → shopify_get_order_details
2. VERIFY TWO CONDITIONS:
   a. Order was placed TODAY (compare createdAt date with {current_date})
   b. Order status is UNFULFILLED
3. If BOTH true → shopify_update_order_shipping_address + tag "customer verified address"
4. If EITHER false → ESCALATE:
   "To make sure you get the right response, I'm looping in Monica,
   who is our Head of CS. She'll take the conversation from here. 💛"

EDGE CASES — ADDRESS:
- ORDER ALREADY SHIPPED → ESCALATE (cannot change address after fulfillment)
- ORDER NOT FROM TODAY → ESCALATE (policy requires same-day change only)
- API ERROR on update → ESCALATE immediately
- CUSTOMER PROVIDES INCOMPLETE ADDRESS → Ask for ALL required fields:
  "Could you share your updated address? I'll need:
  - Full name, Street address, City, State/Province, ZIP/Postal code, Country, Phone number"

═══════════════════════════════════════
WORKFLOW C — SUBSCRIPTION MANAGEMENT:
═══════════════════════════════════════
1. Check status → skio_get_subscription_status(email: "{email}")
2. Ask reason: "Could you let me know why you'd like to make changes to your subscription?"
3. Route by reason:

   a. "TOO MANY ON HAND":
      Step 1: Offer skip → "How about we skip your next order for a month? That way you can use up what you have!"
              → If YES → skio_skip_next_order_subscription(subscriptionId: "[ID]")
      Step 2: If skip declined → Offer 20% discount on next 2 orders
              → "What if I offer you 20% off your next two orders?"
      Step 3: If STILL wants cancel → skio_cancel_subscription(subscriptionId: "[ID]", cancellationReasons: ["Too many on hand"])

   b. "QUALITY ISSUE / PRODUCT NOT WORKING":
      Step 1: Offer product swap → shopify_get_product_recommendations
              "We have some other options that might work better for you!"
      Step 2: If swap declined → skio_cancel_subscription

EDGE CASES — SUBSCRIPTION:
- ALREADY CANCELLED → API returns error →
  "It looks like your subscription was already cancelled.
  If you're still seeing charges, let me escalate this to Monica right away."
  → If charges mentioned → ESCALATE with category: "billing_error"
- DOUBLE CHARGE / BILLING ERROR → ALWAYS ESCALATE
  "I can see what happened — let me connect you with Monica to get this sorted right away."
  → Category: "billing_error"
- NO SUBSCRIPTION FOUND →
  "I wasn't able to find an active subscription under {email}.
  Is it possible it's under a different email address?"
- PAUSE REQUEST → skio_pause_subscription(subscriptionId: "[ID]", pausedUntil: "[YYYY-MM-DD]")
  Ask how long they want to pause.

═══════════════════════════════════════
WORKFLOW D — DISCOUNT CODE:
═══════════════════════════════════════
1. Create ONE 10% code:
   shopify_create_discount_code(
       type: "percentage",
       value: 0.10,
       duration: 48,
       productIds: []
   )
2. Share the code: "Here's your discount code: [CODE] — it's valid for 48 hours and gives you 10% off! 🎉"
3. ⚠️ MAXIMUM 1 code per customer EVER. If already created →
   "I've already set you up with a discount code earlier.
   That's the best I can offer, but I hope you love it!"

EDGE CASES — DISCOUNT:
- CUSTOMER WANTS MORE THAN 10% → "I can offer a 10% discount code — that's the best I can do! 😊"
- API ERROR creating code → "I'm having a bit of trouble creating the code. Let me try again..."
  If still fails → ESCALATE
- CUSTOMER ASKS ABOUT EXPIRED CODE → Create a new one (counts as their 1 code)

═══════════════════════════════════════
WORKFLOW E — POSITIVE FEEDBACK:
═══════════════════════════════════════
1. Respond warmly (match the workflow manual EXACTLY):
   "Awww 🥰 {first_name}!

   That is so amazing! 🙏 Thank you for that epic feedback!

   If it's okay with you, would you mind if I send you a feedback request
   so you can share your thoughts on NATPAT and our response overall?

   It's totally fine if you don't have the time, but I thought I'd ask
   before sending a feedback request email 😊

   Caz"

2. If they say YES:
   "Awwww, thank you! ❤️

   Here's the link to the review page: https://trustpilot.com/evaluate/naturalpatch.com

   Thanks so much! 🙏

   Caz xx"

3. Sign as "Caz xx" (with xx for positive interactions)

EDGE CASES — POSITIVE:
- CUSTOMER STARTS POSITIVE THEN SHIFTS TO COMPLAINT →
  HANDOFF: issue_agent | REASON: Customer shifted from positive feedback to product complaint
- CUSTOMER ALREADY LEFT REVIEW → "That's wonderful! Thank you so much for taking the time! 💛"
- CUSTOMER SAYS NO TO REVIEW → "No problem at all! Just knowing you're happy makes our day! 😊 Caz xx"

TOOLS: shopify_get_order_details, shopify_get_customer_orders, shopify_cancel_order,
       shopify_update_order_shipping_address, shopify_add_tags, shopify_create_discount_code,
       skio_get_subscription_status, skio_cancel_subscription, skio_pause_subscription,
       skio_skip_next_order_subscription, skio_unpause_subscription

Sign as "Caz".
```

---

## 8. ESCALATION MEKANİZMASI (Güncellenmiş)

### 8.1 Tetikleyiciler (Genişletilmiş)

| Tetikleyici                                      | Kaynak                         | Öncelik    |
| ------------------------------------------------ | ------------------------------ | ---------- |
| Reship gerekli                                   | WISMO / Issue Agent            | Normal     |
| Vaat edilen tarih geçti + teslim yok             | WISMO Agent                    | Normal     |
| Müşteri beklemeyi reddetti + fulfilled           | WISMO Agent                    | Normal     |
| Adres güncelleme hatası                          | Account Agent                  | Normal     |
| Adres değişikliği ama same-day/unfulfilled değil | Account Agent                  | Normal     |
| 3+ tur çözümsüz döngü                            | Herhangi bir agent             | Normal     |
| **Allerji/sağlık endişesi**                      | Issue Agent                    | **Yüksek** |
| **Chargeback tehdidi**                           | Issue Agent / Input Guardrails | **Yüksek** |
| **Double charge / billing error**                | Account Agent                  | **Yüksek** |
| **Tüm tool'lar fail (API down)**                 | Herhangi bir agent             | **Yüksek** |
| **90+ gün eski sipariş refund**                  | Issue Agent                    | Normal     |
| Belirsiz durum / güvenlik                        | Herhangi bir agent             | Normal     |
| Partially fulfilled order cancellation           | Account Agent                  | Normal     |

### 8.2 Escalation Handler

```python
class EscalationPayload(BaseModel):
    customer_name: str
    customer_email: str
    order_id: Optional[str] = None
    subscription_id: Optional[str] = None
    category: str           # "reship", "refund_review", "address_error",
                            # "health_concern", "chargeback_risk", "billing_error",
                            # "technical_error", "uncertain", "unresolved_loop"
    priority: str = "normal"  # "normal" or "high"
    summary: str
    actions_taken: list
    conversation_history: list
    escalated_to: str = "Monica - Head of CS"

async def escalation_handler_node(state: CustomerSupportState) -> dict:
    """Handle escalation with structured summary."""

    # Generate summary using Sonnet
    summary = await sonnet_llm.ainvoke(
        f"Summarize this customer support interaction in 2-3 sentences "
        f"for handoff to a human agent. Include: what the customer wants, "
        f"what was tried, and why it's being escalated.\n\n"
        f"Messages:\n{[m.content for m in state['messages']]}"
    )

    # Determine priority
    category = state.get("escalation_reason", "uncertain")
    high_priority_categories = {"health_concern", "chargeback_risk", "billing_error"}
    priority = "high" if category in high_priority_categories else "normal"

    payload = EscalationPayload(
        customer_name=f"{state['customer_first_name']} {state['customer_last_name']}",
        customer_email=state["customer_email"],
        order_id=state.get("current_order_id"),
        subscription_id=state.get("current_subscription_id"),
        category=category,
        priority=priority,
        summary=summary.content,
        actions_taken=state.get("actions_taken", []),
        conversation_history=[m.content for m in state["messages"]],
    )

    # Customer-facing message (matches workflow manual tone)
    customer_message = (
        f"Hey {state['customer_first_name']}, to make sure you get the best help, "
        f"I'm looping in Monica, who is our Head of CS. "
        f"She'll take the conversation from here. 💛\n\nCaz"
    )

    return {
        "messages": [AIMessage(content=customer_message)],
        "is_escalated": True,
        "escalation_payload": payload.model_dump(),
        "agent_reasoning": [
            f"ESCALATED [{priority.upper()}]: {payload.category} - {payload.summary[:100]}"
        ]
    }
```

### 8.3 Post-Escalation Node

```python
async def post_escalation_node(state: CustomerSupportState) -> dict:
    """Auto-response for messages after escalation. Session locked."""
    return {
        "messages": [AIMessage(content=(
            f"Hey {state['customer_first_name']}, your issue has been escalated "
            f"to Monica, our Head of CS. She'll be following up with you directly. "
            f"Please hang tight! 💛\n\nCaz"
        ))],
        "agent_reasoning": ["SESSION LOCKED: Post-escalation auto-response"]
    }
```

---

## 9. STATE MANAGEMENT & MEMORY

### 9.1 State Tanımı (v3.0 — Tüm Yeni Alanlar Dahil)

```python
from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages

class CustomerSupportState(TypedDict):
    # === Core ===
    messages: Annotated[list, add_messages]

    # === Customer Info (session start'ta set edilir) ===
    customer_email: str
    customer_first_name: str
    customer_last_name: str
    customer_shopify_id: str          # "gid://shopify/Customer/..."

    # === Intent Classification ===
    ticket_category: str              # WISMO, WRONG_MISSING, NO_EFFECT, etc.
    intent_confidence: int            # 0-100
    intent_shifted: bool              # YENİ: Multi-turn intent shift detected

    # === Routing ===
    current_agent: str                # "supervisor", "wismo_agent", "issue_agent", "account_agent"

    # === Shared Context ===
    order_details: Optional[dict]     # Cached order details
    current_order_id: Optional[str]   # Current order GID
    current_order_number: Optional[str] # Current order number (#XXXXX)
    subscription_status: Optional[dict]
    current_subscription_id: Optional[str]

    # === Guardrails State ===
    input_blocked: bool
    pii_redacted: bool
    output_guardrail_passed: bool
    output_guardrail_issues: list
    discount_code_created: bool       # Max 1 per customer per session
    pending_refund_amount: Optional[float]
    order_total: Optional[float]
    flag_escalation_risk: bool        # YENİ: Aggressive language detected
    flag_health_concern: bool         # YENİ: Health/allergy mention detected
    is_handoff: bool                  # YENİ: Agent requested handoff

    # === Reflection State ===
    reflection_passed: bool
    reflection_feedback: Optional[str]
    reflection_rule_violated: Optional[str]
    reflection_suggested_fix: Optional[str]
    was_revised: bool

    # === Escalation ===
    is_escalated: bool
    escalation_payload: Optional[dict]
    escalation_reason: Optional[str]

    # === Tracing & Observability ===
    tool_calls_log: list
    actions_taken: list
    agent_reasoning: list
```

### 9.2 Checkpointer (Multi-turn Memory)

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()

# Her session unique thread_id ile
config = {"configurable": {"thread_id": session_id}}

# Multi-turn: Context otomatik korunur
result = graph.invoke(
    {"messages": [HumanMessage(content=new_message)]},
    config=config
)
```

---

## 10. TAM LANGGRAPH GRAPH YAPISI (v3.0)

```python
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent

# === Model Setup ===
sonnet_llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
haiku_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

# === ReAct Sub-Agents ===
wismo_agent = create_react_agent(
    model=sonnet_llm, tools=wismo_tools,
    state_schema=CustomerSupportState,
    prompt=WISMO_SYSTEM_PROMPT, name="wismo_agent"
)
issue_agent = create_react_agent(
    model=sonnet_llm, tools=issue_tools,
    state_schema=CustomerSupportState,
    prompt=ISSUE_SYSTEM_PROMPT, name="issue_agent"
)
account_agent = create_react_agent(
    model=sonnet_llm, tools=account_tools,
    state_schema=CustomerSupportState,
    prompt=ACCOUNT_SYSTEM_PROMPT, name="account_agent"
)

# === Build Graph ===
graph = StateGraph(CustomerSupportState)

# === NODES ===
graph.add_node("input_guardrails", input_guardrails_node)
graph.add_node("intent_classifier", intent_classifier_node)
graph.add_node("intent_shift_check", intent_shift_check_node)
graph.add_node("supervisor", supervisor_node)
graph.add_node("wismo_agent", wismo_agent)
graph.add_node("issue_agent", issue_agent)
graph.add_node("account_agent", account_agent)
graph.add_node("output_guardrails", output_guardrails_node)
graph.add_node("reflection_validator", reflection_validator_node)
graph.add_node("revise_response", revise_response_node)
graph.add_node("escalation_handler", escalation_handler_node)
graph.add_node("post_escalation", post_escalation_node)

# === EDGES ===

# Entry → Input Guardrails
graph.add_edge(START, "input_guardrails")

# Input Guardrails → Route (blocked/escalated/first-turn/multi-turn)
graph.add_conditional_edges(
    "input_guardrails",
    lambda state: (
        "post_escalation" if state.get("is_escalated") else
        "blocked" if state.get("input_blocked") else
        "intent_classifier" if len([m for m in state["messages"] if m.type == "human"]) == 1 else
        "intent_shift_check"
    ),
    {
        "post_escalation": "post_escalation",
        "blocked": END,
        "intent_classifier": "intent_classifier",
        "intent_shift_check": "intent_shift_check",
    }
)



# Intent Classifier (first message) → Route by confidence
graph.add_conditional_edges(
    "intent_classifier",
    route_by_confidence,
    {
        "wismo_agent": "wismo_agent",
        "issue_agent": "issue_agent",
        "account_agent": "account_agent",
        "supervisor": "supervisor",
    }
)

# Intent Shift Check (multi-turn) → Route to same or new agent
graph.add_conditional_edges(
    "intent_shift_check",
    route_after_shift_check,
    {
        "wismo_agent": "wismo_agent",
        "issue_agent": "issue_agent",
        "account_agent": "account_agent",
        "supervisor": "supervisor",
    }
)

# Supervisor → Route to agent or respond directly
graph.add_conditional_edges(
    "supervisor",
    supervisor_route,
    {
        "wismo_agent": "wismo_agent",
        "issue_agent": "issue_agent",
        "account_agent": "account_agent",
        "respond_direct": "output_guardrails",
        "escalate": "escalation_handler",
    }
)

# ReAct Agents → Output Guardrails
graph.add_edge("wismo_agent", "output_guardrails")
graph.add_edge("issue_agent", "output_guardrails")
graph.add_edge("account_agent", "output_guardrails")

# Output Guardrails → Handoff / Reflection / Revise
graph.add_conditional_edges(
    "output_guardrails",
    lambda state: (
        "handoff" if state.get("is_handoff") else
        "reflection" if state.get("output_guardrail_passed", True) else
        "revise"
    ),
    {
        "handoff": "handoff_router",  # Re-route to target agent
        "reflection": "reflection_validator",
        "revise": "revise_response",
    }
)

# Handoff Router → Re-route to target agent
graph.add_node("handoff_router", handoff_router_node)
graph.add_conditional_edges(
    "handoff_router",
    lambda state: state.get("handoff_target", "supervisor"),
    {
        "wismo_agent": "wismo_agent",
        "issue_agent": "issue_agent",
        "account_agent": "account_agent",
        "supervisor": "supervisor",
    }
)

# Reflection → END (pass) or Revise (fail)
graph.add_conditional_edges(
    "reflection_validator",
    lambda state: "end" if state.get("reflection_passed", True) else "revise",
    {"end": END, "revise": "revise_response"}
)

# Revise → END
graph.add_edge("revise_response", END)

# Escalation → END
graph.add_edge("escalation_handler", END)

# Post-Escalation → END
graph.add_edge("post_escalation", END)

# === Compile ===
app = graph.compile(checkpointer=checkpointer)
```

### 10.1 Handoff Router Node

```python
def handoff_router_node(state: CustomerSupportState) -> dict:
    """Parse handoff instruction and re-route to target agent."""
    last_message = state["messages"][-1].content

    if last_message.strip().startswith("HANDOFF:"):
        parts = last_message.split("|")
        target = parts[0].replace("HANDOFF:", "").strip().lower()
        reason = parts[1].replace("REASON:", "").strip() if len(parts) > 1 else ""

        # Remove the HANDOFF message from conversation (internal only)
        # The target agent will see the customer's original message

        return {
            "handoff_target": target,
            "current_agent": target,
            "agent_reasoning": [f"HANDOFF: {state.get('current_agent')} → {target} ({reason})"]
        }

    # Fallback: if not a valid handoff, send to supervisor
    return {
        "handoff_target": "supervisor",
        "agent_reasoning": ["HANDOFF: Invalid format, falling back to supervisor"]
    }
```

---

## 11. TOOL INTEGRATION KATMANI

### 11.1 Tool Wrapper Mimarisi (Spec-Compliant)

```python
import httpx
import os
from langchain_core.tools import tool

API_URL = os.environ["API_URL"]

def _api_call(endpoint: str, payload: dict) -> dict:
    """Generic API call with error handling and retry."""
    try:
        response = httpx.post(
            f"{API_URL}/hackhaton/{endpoint}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )
        result = response.json()
        if not result.get("success"):
            return {"error": result.get("error", "Unknown error"), "success": False}
        return result
    except httpx.TimeoutException:
        # Retry once
        try:
            response = httpx.post(
                f"{API_URL}/hackhaton/{endpoint}",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15.0,
            )
            result = response.json()
            if not result.get("success"):
                return {"error": result.get("error", "Unknown error"), "success": False}
            return result
        except:
            return {"error": "API timeout after retry — please try again", "success": False}
    except Exception as e:
        return {"error": f"API call failed: {str(e)}", "success": False}

@tool
def shopify_get_order_details(orderId: str) -> dict:
    """Fetch detailed information for a single order.
    orderId must start with '#', e.g. '#1234'.
    Returns: order id (GID), name, status, tracking info, line items."""
    if not orderId.startswith("#"):
        orderId = f"#{orderId}"
    return _api_call("get_order_details", {"orderId": orderId})

@tool
def shopify_get_customer_orders(email: str, after: str = "null", limit: int = 10) -> dict:
    """Get customer orders by email. Returns list of orders with GIDs.
    Use after='null' for first page. Max limit 250."""
    return _api_call("get_customer_orders", {"email": email, "after": after, "limit": limit})

@tool
def shopify_cancel_order(orderId: str, reason: str, notifyCustomer: bool,
                         restock: bool, staffNote: str, refundMode: str,
                         storeCredit: dict) -> dict:
    """Cancel an order. orderId must be Shopify GID (gid://shopify/Order/...).
    reason: CUSTOMER|DECLINED|FRAUD|INVENTORY|OTHER|STAFF
    refundMode: ORIGINAL|STORE_CREDIT
    storeCredit: {"expiresAt": null} or {"expiresAt": "ISO8601"}"""
    return _api_call("cancel_order", {
        "orderId": orderId, "reason": reason, "notifyCustomer": notifyCustomer,
        "restock": restock, "staffNote": staffNote, "refundMode": refundMode,
        "storeCredit": storeCredit
    })

@tool
def shopify_refund_order(orderId: str, refundMethod: str) -> dict:
    """Refund an order. orderId must be Shopify GID.
    refundMethod: ORIGINAL_PAYMENT_METHODS or STORE_CREDIT"""
    return _api_call("refund_order", {"orderId": orderId, "refundMethod": refundMethod})

@tool
def shopify_create_store_credit(id: str, creditAmount: dict, expiresAt: str = None) -> dict:
    """Issue store credit to customer. id must be Customer GID.
    creditAmount: {"amount": "49.99", "currencyCode": "USD"}
    expiresAt: null for no expiry or ISO8601 string."""
    return _api_call("create_store_credit", {
        "id": id, "creditAmount": creditAmount, "expiresAt": expiresAt
    })

@tool
def shopify_add_tags(id: str, tags: list) -> dict:
    """Add tags to a Shopify resource. id must be Shopify GID."""
    return _api_call("add_tags", {"id": id, "tags": tags})

@tool
def shopify_create_discount_code(type: str, value: float, duration: int, productIds: list = []) -> dict:
    """Create discount code. type: 'percentage' (0-1) or 'fixed'.
    value: 0.10 for 10%. duration: hours (48). productIds: [] for order-wide."""
    return _api_call("create_discount_code", {
        "type": type, "value": value, "duration": duration, "productIds": productIds
    })

@tool
def shopify_update_order_shipping_address(orderId: str, shippingAddress: dict) -> dict:
    """Update shipping address. orderId must be Shopify GID.
    shippingAddress needs: firstName, lastName, company, address1, address2,
    city, provinceCode, country, zip, phone."""
    return _api_call("update_order_shipping_address", {
        "orderId": orderId, "shippingAddress": shippingAddress
    })

@tool
def shopify_create_return(orderId: str) -> dict:
    """Create a return. orderId must be Shopify GID."""
    return _api_call("create_return", {"orderId": orderId})

@tool
def shopify_get_product_details(queryType: str, queryKey: str) -> dict:
    """Get product info. queryType: 'id'|'name'|'key feature'.
    queryKey: product GID if id, or search term."""
    return _api_call("get_product_details", {"queryType": queryType, "queryKey": queryKey})

@tool
def shopify_get_product_recommendations(queryKeys: list) -> dict:
    """Get product recommendations. queryKeys: keywords like ['sleep', 'kids']."""
    return _api_call("get_product_recommendations", {"queryKeys": queryKeys})

@tool
def shopify_get_related_knowledge_source(question: str, specificToProductId: str = None) -> dict:
    """Get FAQs, articles, guides. question: customer's issue.
    specificToProductId: product GID or null."""
    return _api_call("get_related_knowledge_source", {
        "question": question, "specificToProductId": specificToProductId
    })

@tool
def shopify_get_collection_recommendations(queryKeys: list) -> dict:
    """Get collection recommendations by keywords."""
    return _api_call("get_collection_recommendations", {"queryKeys": queryKeys})

@tool
def shopify_create_draft_order() -> dict:
    """Create a draft order."""
    return _api_call("create_draft_order", {})

@tool
def skio_get_subscription_status(email: str) -> dict:
    """Get subscription status by email."""
    return _api_call("get-subscription-status", {"email": email})

@tool
def skio_cancel_subscription(subscriptionId: str, cancellationReasons: list) -> dict:
    """Cancel subscription. Requires subscriptionId and reasons list."""
    return _api_call("cancel-subscription", {
        "subscriptionId": subscriptionId, "cancellationReasons": cancellationReasons
    })

@tool
def skio_pause_subscription(subscriptionId: str, pausedUntil: str) -> dict:
    """Pause subscription until date. pausedUntil format: YYYY-MM-DD."""
    return _api_call("pause-subscription", {
        "subscriptionId": subscriptionId, "pausedUntil": pausedUntil
    })

@tool
def skio_skip_next_order_subscription(subscriptionId: str) -> dict:
    """Skip next subscription order."""
    return _api_call("skip-next-order-subscription", {"subscriptionId": subscriptionId})

@tool
def skio_unpause_subscription(subscriptionId: str) -> dict:
    """Unpause a paused subscription."""
    return _api_call("unpause-subscription", {"subscriptionId": subscriptionId})
```

### 11.2 Tool Grupları (Agent-Isolated)

```python
wismo_tools = [
    shopify_get_customer_orders,
    shopify_get_order_details,
    shopify_add_tags,
]

issue_tools = [
    shopify_get_order_details,
    shopify_get_customer_orders,
    shopify_refund_order,
    shopify_create_store_credit,
    shopify_create_return,
    shopify_add_tags,
    shopify_get_product_recommendations,
    shopify_get_product_details,
    shopify_get_related_knowledge_source,
]

account_tools = [
    shopify_get_order_details,
    shopify_get_customer_orders,
    shopify_cancel_order,
    shopify_update_order_shipping_address,
    shopify_add_tags,
    shopify_create_discount_code,
    skio_get_subscription_status,
    skio_cancel_subscription,
    skio_pause_subscription,
    skio_skip_next_order_subscription,
    skio_unpause_subscription,
]
```

---

## 12. OBSERVABILITY & TRACING

### 12.1 Trace Log Modelleri

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TraceEntry(BaseModel):
    timestamp: str = datetime.now().isoformat()
    agent: str
    action_type: str          # "guardrail_check", "classification", "routing",
                              # "react_thought", "react_action", "react_observation",
                              # "tool_call", "response", "reflection_check",
                              # "revision", "escalation", "handoff", "intent_shift"
    detail: str
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[dict] = None
    confidence: Optional[int] = None
    passed: Optional[bool] = None

class SessionTrace(BaseModel):
    session_id: str
    customer_email: str
    customer_name: str
    started_at: str
    intent: Optional[str] = None
    intent_confidence: Optional[int] = None
    traces: list[TraceEntry] = []
    final_response: Optional[str] = None
    actions_taken: list[str] = []
    is_escalated: bool = False
    was_revised: bool = False
    intent_shifted: bool = False
    handoffs: list[str] = []
    reflection_violations: list[str] = []
    guardrail_blocks: list[str] = []
    model_calls: dict = {}          # {"haiku": 2, "sonnet": 3}
    escalation_payload: Optional[dict] = None
```

### 12.2 Streamlit UI Layout

```
┌────────────────────────────────┬──────────────────────────────────────┐
│                                │  📊 TRACE TIMELINE                  │
│  Customer Chat                 │                                      │
│  ─────────────────             │  🔒 14:23:00 ESCALATION LOCK        │
│  Session Info:                 │    ✅ Not escalated                  │
│  Sarah Jones                   │                                      │
│  sarah@email.com               │  🛡️ 14:23:00 INPUT GUARDRAILS       │
│  gid://shopify/Customer/123    │    ✅ Clean input, no PII            │
│                                │    ⚠️ No health/aggression flags     │
│  Customer: "Where is my        │                                      │
│  order #43189?"                │  🎯 14:23:00 INTENT CLASSIFIER      │
│                                │    Intent: WISMO | Confidence: 94%   │
│                                │    Route: Direct → wismo_agent       │
│                                │                                      │
│                                │  🧠 14:23:01 ReAct THOUGHT           │
│                                │    "Need to check order #43189"      │
│                                │                                      │
│                                │  🔧 14:23:01 ReAct ACTION            │
│                                │    Tool: shopify_get_order_details    │
│                                │    Input: {orderId: "#43189"}         │
│                                │    Output: {status: FULFILLED,        │
│                                │     id: "gid://shopify/Order/555.."} │
│                                │                                      │
│                                │  👁️ 14:23:02 ReAct OBSERVATION       │
│                                │    Status: FULFILLED, In Transit      │
│                                │                                      │
│                                │  🧠 14:23:02 ReAct THOUGHT           │
│  Caz: "Hey Sarah! I just      │    "Today is Friday → wait until     │
│  checked and your order        │     early next week"                  │
│  #43189 is on its way! ..."    │                                      │
│                                │  🔧 14:23:03 TAG                     │
│                                │    shopify_add_tags(id: "gid://...", │
│                                │    tags: ["WISMO checked"])           │
│                                │                                      │
│                                │  🛡️ 14:23:03 OUTPUT GUARDRAILS       │
│                                │    ✅ No forbidden phrases            │
│                                │    ✅ Caz signature present           │
│                                │    ✅ No internal info leak           │
│                                │                                      │
│                                │  🔍 14:23:03 REFLECTION (8 rules)    │
│                                │    ✅ 1. Resolution order: N/A        │
│                                │    ✅ 2. Wait promise: correct (Fri)  │
│                                │    ✅ 3. Escalation: not needed       │
│                                │    ✅ 4. Info gathering: N/A          │
│                                │    ✅ 5. Tone: warm, empathetic       │
│                                │    ✅ 6. Factual accuracy: matches    │
│                                │    ✅ 7. GID format: correct          │
│                                │    ✅ 8. Resolution waterfall: N/A    │
│                                │                                      │
│                                │  📊 Summary:                         │
│                                │    Models: Haiku×2, Sonnet×1          │
│                                │    Revised: No | Handoff: No          │
│                                │    Intent Shift: No                   │
│                                │    Actions: [Checked order, Tagged]   │
└────────────────────────────────┴──────────────────────────────────────┘
```

---

## 13. PROJE DOSYA YAPISI (v3.0)

```
Lookfor_Hackathon_2026_TEAMNAME/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── README.md
├── requirements.txt
│
├── src/
│   ├── main.py                         # FastAPI app entry point
│   ├── config.py                       # Env vars, constants, model setup
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── supervisor.py               # Fallback supervisor agent
│   │   ├── wismo_agent.py              # WISMO ReAct agent
│   │   ├── issue_agent.py              # Issue ReAct agent
│   │   ├── account_agent.py            # Account ReAct agent
│   │   └── escalation.py              # Escalation handler + post-escalation
│   │
│   ├── patterns/
│   │   ├── __init__.py
│   │   ├── intent_classifier.py        # 2-Stage Intent Classification + shift check
│   │   ├── guardrails.py              # Input/Output/Tool Guardrails (all checks)
│   │   ├── reflection.py             # 8-Rule Reflection Validator + Revision
│   │   ├── handoff.py                # Cross-agent handoff router (YENİ)
│   │   └── react_prompts.py          # ReAct + GID + Handoff prompt blocks
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py                    # State definition (v3.0)
│   │   ├── graph_builder.py            # LangGraph graph (v3.0)
│   │   └── checkpointer.py            # Memory setup
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── shopify_tools.py            # 14 Shopify API wrappers
│   │   ├── skio_tools.py              # 5 Skio API wrappers
│   │   ├── tool_groups.py            # Tool groupings per agent
│   │   └── api_client.py             # Generic API client with retry
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── supervisor_prompt.py
│   │   ├── wismo_prompt.py             # Edge case-aware (v3.0)
│   │   ├── issue_prompt.py             # Edge case-aware (v3.0)
│   │   ├── account_prompt.py           # Edge case-aware (v3.0)
│   │   ├── reflection_prompt.py        # 8-rule reflection (v3.0)
│   │   ├── intent_classifier_prompt.py
│   │   └── shared_blocks.py           # ReAct, GID, Handoff blocks (YENİ)
│   │
│   ├── tracing/
│   │   ├── __init__.py
│   │   ├── trace_logger.py
│   │   └── models.py                  # TraceEntry, SessionTrace (v3.0)
│   │
│   └── ui/
│       └── streamlit_app.py           # Streamlit UI (v3.0 with all indicators)
│
├── tickets/
│   └── sample_tickets.json
│
└── tests/
    ├── test_routing.py                 # Intent classification + shift tests
    ├── test_guardrails.py             # All guardrail checks
    ├── test_reflection.py             # 8-rule reflection tests
    ├── test_handoff.py                # Cross-agent handoff (YENİ)
    ├── test_multi_turn.py             # Multi-turn conversation (YENİ)
    ├── test_escalation.py             # Escalation triggers + lock (YENİ)
    ├── test_tool_params.py            # GID vs # format tests (YENİ)
    ├── test_wismo.py
    ├── test_issue.py
    └── test_account.py
```

---

## 14. TEKNİK DETAYLAR

### 14.1 Docker Compose

```yaml
version: "3.8"
services:
  app:
    build: .
    ports:
      - "8000:8000" # FastAPI
      - "8501:8501" # Streamlit
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - API_URL=${API_URL}
    volumes:
      - ./tickets:/app/tickets
```

### 14.2 Dependencies

```
langgraph>=0.2.0
langchain-anthropic>=0.3.0
langchain-core>=0.3.0
fastapi>=0.115.0
uvicorn>=0.32.0
streamlit>=1.40.0
httpx>=0.27.0
pydantic>=2.0.0
python-dotenv>=1.0.0
```

### 14.3 Day-of-Week Logic

```python
from datetime import datetime

def get_wait_promise():
    day = datetime.now().weekday()  # 0=Mon, 6=Sun
    if day <= 2:  # Mon, Tue, Wed
        return "this Friday"
    else:  # Thu, Fri, Sat, Sun
        return "early next week"

from datetime import datetime
from zoneinfo import ZoneInfo
import os

def get_wait_promise(now: datetime):
    day = now.weekday()  # 0=Mon, 6=Sun
    if day <= 2:  # Mon, Tue, Wed
        return "this Friday"
    else:  # Thu, Fri, Sat, Sun
        return "early next week"

def get_current_context():
    tz = ZoneInfo(os.getenv("APP_TIMEZONE", "UTC"))
    now = datetime.now(tz)
    return {
        "current_date": now.strftime("%Y-%m-%d"),
        "day_of_week": now.strftime("%A"),
        "wait_promise": get_wait_promise(now),
    }

```

### 14.4 Model Configuration

```python
from langchain_anthropic import ChatAnthropic

MODELS = {
    "sonnet": ChatAnthropic(
        model="claude-sonnet-4-20250514",
        temperature=0,
        max_tokens=2048,
    ),
    "haiku": ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0,
        max_tokens=1024,
    ),
}

sonnet_llm = MODELS["sonnet"]
haiku_llm = MODELS["haiku"]
```

### 14.5 Session Initialization

```python
async def start_session(email: str, first_name: str, last_name: str, shopify_id: str) -> str:
    """Initialize a new customer session."""
    session_id = f"session_{email}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    initial_state = {
        "messages": [],
        "customer_email": email,
        "customer_first_name": first_name,
        "customer_last_name": last_name,
        "customer_shopify_id": shopify_id,
        "is_escalated": False,
        "discount_code_created": False,
        "tool_calls_log": [],
        "actions_taken": [],
        "agent_reasoning": [],
        "flag_escalation_risk": False,
        "flag_health_concern": False,
        "was_revised": False,
        "intent_shifted": False,
    }

    return session_id, initial_state
```

---

## 15. UYGULAMA PLANI (Zaman Çizelgesi — v3.0)

### Solo Developer (~8 saat):

| Saat          | Görev                        | Detay                                                                       |
| ------------- | ---------------------------- | --------------------------------------------------------------------------- |
| **0:00-0:30** | Setup                        | Docker, deps, env, API keys, Haiku+Sonnet model setup                       |
| **0:30-1:30** | Tool Layer                   | 19 tool wrapper + api_client with retry + tool groups + tool guardrails     |
| **1:30-2:15** | State & Graph                | State tanımı (v3.0), Graph yapısı (tüm node'lar + handoff + shift)          |
| **2:15-2:45** | Intent Classifier + Shift    | Haiku classifier + confidence routing + shift detection                     |
| **2:45-3:15** | Input/Output Guardrails      | PII, injection, empty, aggressive, health, forbidden phrases, internal leak |
| **3:15-4:15** | WISMO Agent                  | ReAct prompt (edge case-aware) + disambiguation + tracking                  |
| **4:15-5:30** | Issue Agent                  | Wrong/missing + no effect + refund + resolution waterfall + health edge     |
| **5:30-6:15** | Account Agent                | Cancel + address + subscription + discount + positive                       |
| **6:15-6:45** | Reflection Validator         | 8-rule check + revision node                                                |
| **6:45-7:15** | Escalation + Post-Escalation | Handler + session lock + summary + post-escalation node                     |
| **7:15-7:45** | UI & Tracing                 | Streamlit chat + trace panel                                                |
| **7:45-8:00** | Docker + README              | docker-compose, README, demo prep                                           |

### 2 Kişilik Paralel:

**Kişi A (Backend — Agent'lar + Tools):**

```
0:00-0:30  Setup (birlikte)
0:30-1:30  Tool Layer + API Client + Tool Guardrails
1:30-2:30  WISMO Agent (edge case-aware prompt + test)
2:30-3:45  Issue Agent (3 workflow + resolution waterfall + test)
3:45-4:30  Account Agent (5 workflow + test)
4:30-5:00  Escalation Handler + Post-Escalation
5:00-5:30  End-to-end test + bug fix + demo prep
```

**Kişi B (Architecture — Graph + Patterns):**

```
0:00-0:30  Setup (birlikte)
0:30-1:15  State (v3.0) + Graph Builder (all nodes + edges)
1:15-1:45  Intent Classifier + Intent Shift Check
1:45-2:15  Input Guardrails (all checks) + Output Guardrails
2:15-2:45  Reflection Validator (8-rule) + Revision Node
2:45-3:15  Handoff Router + Supervisor
3:15-4:00  Streamlit UI + Trace Panel
4:00-4:30  Docker + README
4:30-5:00  Integration test + bug fix
5:00-5:30  Demo prep
```

---

## 16. SUNUM STRATEJİSİ (~2 dakika)

```
[0:00-0:15] HOOK
"Biz sadece bir chatbot yapmadık — 4 AI agent pattern'ini birleştiren,
kendi kendini düzelten, cross-agent handoff yapabilen bir multi-agent
sistem inşa ettik."

[0:15-0:40] ARCHITECTURE (diyagramı göster)
"7 katmanlı pipeline: Escalation lock → Input guardrails →
2-stage intent classification (multi-turn shift detection dahil) →
ReAct agents → Tool guardrails → Output guardrails → 8-rule reflection.

2 model: Haiku hız ve maliyet, Sonnet kalite. Production'da cost-effective."

[0:40-1:15] LIVE DEMO — Happy Path
Müşteri: "My BuzzPatch order hasn't arrived"
→ Input Guardrails: ✅ Clean
→ Intent: WISMO (94%) → Direct route
→ WISMO Agent: Thought → Tool → Observe → Wait promise (day-aware)
→ Output Guardrails: ✅
→ Reflection: ✅ All 8 rules pass

[1:15-1:35] LIVE DEMO — Self-Correction
"Eğer agent yanlış wait promise verseydi?"
→ Reflection: ❌ FAIL (Rule 2: wrong day)
→ Revision: Düzeltilmiş yanıt → müşteri doğru yanıtı alır

[1:35-1:50] BONUS DEMO — Cross-Agent Handoff veya Escalation
Müşteri: "Actually, just refund me" (during WISMO)
→ WISMO detects scope change → HANDOFF to Issue Agent
→ Issue Agent follows resolution waterfall

[1:50-2:00] CLOSING
"7-layer pipeline, 4 AI patterns, 2-model strategy, 19 tools,
8-rule self-correction, cross-agent handoff.
Production-ready, observable, cost-efficient."
```

---

## 17. JÜRI İÇİN FARKLILAŞTIRICI ÖZELLİKLER

### Rakiplerin YAPMAYACAĞI Şeyler:

| Özellik                                                        | Jüri Kriteri             |
| -------------------------------------------------------------- | ------------------------ |
| **2-Stage Intent Classification + Multi-Turn Shift Detection** | System Design            |
| **8-Rule Reflection Validator**                                | Workflow Correctness     |
| **Cross-Agent Handoff Mechanism**                              | System Design            |
| **Input/Output/Tool Guardrails (3 katman)**                    | System Design + Tool Use |
| **Multi-Model Strategy (Haiku + Sonnet)**                      | Cost Efficiency          |
| **Self-Correcting Output**                                     | Workflow Correctness     |
| **Day-Aware Wait Promise**                                     | Workflow Correctness     |
| **GID vs Order # Auto-Correction**                             | Tool Use Quality         |
| **Post-Escalation Session Lock**                               | Escalation Behavior      |
| **Health/Safety Immediate Escalation**                         | Customer Experience      |
| **Resolution Waterfall Enforcement**                           | Workflow Correctness     |

### Değerlendirme Kriterleri Karşılığı:

1. **Workflow Correctness** → ReAct reasoning + 8-rule reflection + day-aware logic + resolution waterfall
2. **Tool Use Quality** → Agent-isolated tools + tool guardrails + GID auto-correction + retry
3. **Customer Experience** → Warm tone + resolution waterfall + edge case handling + health escalation
4. **Escalation Behavior** → 13 triggers + structured summary + priority levels + session lock
5. **Presentation** → 7-layer story + live demo + self-correction + handoff demo
6. **System Design** → 7-layer pipeline + multi-model + multi-turn + Docker + observability

---

## 18. RİSKLER VE ÇÖZÜMLER

| Risk                              | Çözüm                                                    |
| --------------------------------- | -------------------------------------------------------- |
| Intent classifier yanlış route    | Confidence threshold + supervisor fallback               |
| Multi-turn'de context kaybı       | Checkpointer + full message history in state             |
| Reflection false positive         | JSON parse error → default pass, 1 cycle max             |
| Guardrails çok agresif            | Conservative pattern list, scope check basit             |
| Multi-model setup karmaşıklığı    | Tek config.py, global model instances                    |
| Haiku classification düşük kalite | Improved prompt with examples + multi-intent rule        |
| Handoff infinite loop             | Max 1 handoff per turn, counter in state                 |
| GID format hatası                 | Tool guardrails + agent prompt'ta explicit instruction   |
| API timeout                       | Retry 1x + graceful error message + escalation fallback  |
| Graph karmaşıklığı                | Her node'da trace logging, Streamlit step-by-step        |
| Zaman yetişmemesi                 | P0 öncelik: Tools → Graph → WISMO → Issue. Rest is bonus |

---

## 19. ÖNCELİK SIRASI — P0/P1/P2/P3

| Öncelik | Özellik                                           | Jüri Etkisi                   |
| ------- | ------------------------------------------------- | ----------------------------- |
| 🔴 P0   | Multi-turn routing + context preservation         | Kritik — bunu yapmayan elenir |
| 🔴 P0   | GID vs Order # doğru kullanımı                    | Tool fail = büyük puan kaybı  |
| 🔴 P0   | Resolution waterfall (store credit before refund) | Workflow manual temel kuralı  |
| 🔴 P0   | Wait promise day-awareness                        | Jüri kesin test edecek        |
| 🔴 P0   | Post-escalation session lock                      | Spec'te açıkça isteniyor      |
| 🟠 P1   | Intent shift detection                            | Doğal konuşma akışı           |
| 🟠 P1   | Cross-agent handoff                               | Production-grade göstergesi   |
| 🟠 P1   | Tool error graceful handling                      | API fail'de crash etmemeli    |
| 🟠 P1   | Order disambiguation                              | Gerçekçi senaryo              |
| 🟠 P1   | 8-rule reflection                                 | Self-correction showcase      |
| 🟡 P2   | Aggressive customer escalation                    | Bonus puan                    |
| 🟡 P2   | Health concern immediate escalation               | Safety-first                  |
| 🟡 P2   | Input guardrails (PII, injection)                 | Güvenlik                      |
| 🟢 P3   | Multi-intent handling                             | Nadir ama etkileyici          |
| 🟢 P3   | Photo acknowledgment logic                        | Polish                        |
| 🟢 P3   | Already-refunded order detection                  | Edge case                     |

---

## 20. SONUÇ

v3.0 planı, v2.0'daki tüm eksikleri kapatıyor:

```
v2.0 → v3.0 FARKLARI:
✅ Multi-turn routing stratejisi EKLENDİ (intent shift detection)
✅ Cross-agent handoff mekanizması EKLENDİ
✅ Post-escalation session lock IMPLEMENT EDİLDİ
✅ GID vs Order # dönüşümü tüm agent prompt'larına EKLENDİ
✅ Tool parametreleri spec'e %100 UYUMLU hale getirildi (cancel_order 7 param)
✅ Reflection 6 kural → 8 kural (GID format + waterfall completeness)
✅ Input guardrails genişletildi (empty, aggressive, health, scope)
✅ Output guardrails genişletildi (internal info leak)
✅ Her agent prompt'u tüm edge case'lerle zenginleştirildi
✅ Escalation tetikleyicileri 6 → 13 (health, chargeback, billing, technical)
✅ Store credit parametreleri spec'e uyumlu (creditAmount object)
✅ Handoff router node eklendi (graph'ta)
✅ Error handling: retry logic + graceful fallback
✅ State'e yeni alanlar eklendi (flags, handoff, shift)
```

**Pipeline:**

```
MESAJ → [Escalation Lock] → [Input Guardrails] → [Intent Classification/Shift] →
[ReAct Agent] → [Tool Guardrails] → [Handoff Check] → [Output Guardrails] →
[8-Rule Reflection] → [Revise?] → YANIT ✅
```

Bu mimariyle hackathonu kazanırız çünkü:

- **Her edge case düşünülmüş** — jüri ne test ederse etsin hazırız
- **Her karar gerekçelendirilmiş** — neden bu pattern, neden bu model
- **Müşteri deneyimi garanti altında** — 7 katman kontrol
- **Sistem izlenebilir ve denetlenebilir** — full trace her adımda
- **Production-grade** — retry, graceful error, session lock, multi-model
