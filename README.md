# 🏳️ NatPat Multi-Agent Customer Support System

> **Lookfor Hackathon 2026** — An AI-powered, multi-agent e-commerce customer support pipeline built with LangGraph, Claude (Anthropic), Shopify & Skio APIs.

---

## 📋 Table of Contents

- [Executive Summary](#-executive-summary)
- [System Architecture Overview](#-system-architecture-overview)
- [7-Layer Pipeline Architecture](#-7-layer-pipeline-architecture)
- [Agent Deep Dives](#-agent-deep-dives)
  - [Intent Classifier](#1-intent-classifier)
  - [Supervisor Agent](#2-supervisor-agent)
  - [WISMO Agent](#3-wismo-agent-where-is-my-order)
  - [Issue Agent](#4-issue-agent)
  - [Account Agent](#5-account-agent)
- [Guardrails System](#-guardrails-system)
  - [Input Guardrails](#input-guardrails-layer-1)
  - [Tool Call Guardrails](#tool-call-guardrails-layer-4)
  - [Output Guardrails](#output-guardrails-layer-5)
- [Reflection & Revision](#-reflection--revision-system)
- [Escalation & Handoff Mechanism](#-escalation--handoff-mechanism)
- [State Management](#-state-management)
- [Tool Ecosystem](#-tool-ecosystem)
- [Tracing & Observability](#-tracing--observability)
- [Tech Stack](#-tech-stack)
- [API Reference](#-api-reference)
- [Project Structure](#-project-structure)

---

## 🎯 Executive Summary

NatPat Multi-Agent CS is a **production-grade, multi-agent customer support system** that autonomously handles e-commerce support tickets for the NatPat brand. The system features:

- **3 Specialized ReAct Agents** — each with domain-specific workflows, tools, and prompt engineering
- **7-Layer Processing Pipeline** — from input sanitization to reflection-based quality assurance
- **3-Tier Guardrail System** — input, tool-call, and output guardrails preventing unsafe or incorrect responses
- **Autonomous Escalation** — health concerns, chargeback threats, and unresolvable issues are automatically escalated to human agents
- **Cross-Agent Handoff** — seamless routing between agents when customer intent shifts mid-conversation
- **Full Observability** — every decision, tool call, and reasoning step is traced for debugging and auditing

The system uses **Claude Sonnet** for complex reasoning and agent responses, and **Claude Haiku** for fast, cheap classification and reflection tasks.

---

## 🏗 System Architecture Overview

```mermaid
graph TB
    subgraph CLIENT["Client Layer"]
        UI["Streamlit UI<br/>Chat + Trace Timeline"]
    end

    subgraph API["API Layer"]
        FAST["FastAPI Server<br/>v3.0"]
    end

    subgraph GRAPH["LangGraph Pipeline"]
        direction TB
        L0["Layer 0: Escalation Lock"]
        L1["Layer 1: Input Guardrails"]
        L2["Layer 2: Intent Classification"]
        L3["Layer 3: ReAct Agents"]
        L4["Layer 4: Tool Call Guardrails"]
        L5["Layer 5: Output Guardrails"]
        L6["Layer 6: Reflection Validator"]
        L7["Layer 7: Revision"]
    end

    subgraph TOOLS["External APIs"]
        SHOP["Shopify Admin API<br/>14 Tools"]
        SKIO["Skio Subscription API<br/>5 Tools"]
    end

    subgraph STORAGE["Persistence"]
        SQLITE_HIST["history.db<br/>Session Metadata"]
        SQLITE_CP["history.db<br/>LangGraph Checkpointer"]
    end

    subgraph MODELS["AI Models"]
        SONNET["Claude Sonnet 4<br/>Reasoning + Responses"]
        HAIKU["Claude Haiku 4.5<br/>Classification + Reflection"]
    end

    UI <-->|HTTP| FAST
    FAST <--> GRAPH
    GRAPH <-->|Tool Calls| TOOLS
    GRAPH <-->|State| STORAGE
    GRAPH <-->|Inference| MODELS
```

---

## 🔄 7-Layer Pipeline Architecture

The core of the system is a **7-layer processing pipeline** implemented as a LangGraph `StateGraph`. Each customer message passes through these layers sequentially, with conditional routing at each stage.

```mermaid
flowchart TD
    START([Customer Message]) --> L0

    L0[Layer 0: Escalation Lock]
    L0 -->|Session Escalated| PE[Post-Escalation Response]
    L0 -->|Not Escalated| L1
    PE --> END1([END])

    L1[Layer 1: Input Guardrails]
    L1 -->|Blocked| END2([END])
    L1 -->|Health Concern| AEH[Auto-Escalate Health]
    L1 -->|Chargeback| AEC[Auto-Escalate Chargeback]
    L1 -->|Clean - Turn 1| L2A
    L1 -->|Clean - Turn N| L2B
    
    AEH --> ESC[Escalation Handler]
    AEC --> ESC
    ESC --> END3([END])

    L2A[Intent Classifier]
    L2B[Intent Shift Check]
    
    L2A -->|High Confidence| L3
    L2A -->|Low Confidence| SUP[Supervisor Agent]
    L2B -->|Same Agent| L3
    L2B -->|New Agent| L3
    
    SUP -->|Route to Agent| L3
    SUP -->|Direct Response| L5
    SUP -->|Escalate| ESC

    L3[Layer 3: ReAct Agents]
    L3 --> L5

    L5[Layer 5: Output Guardrails]
    L5 -->|Escalation Detected| ESC
    L5 -->|Handoff Detected| HANDOFF[Handoff Router]
    L5 -->|Failed| L7
    L5 -->|Passed| L6
    
    HANDOFF --> L3

    L6[Layer 6: Reflection Validator]
    L6 -->|Pass| END4([END])
    L6 -->|Fail + Not Revised| L7
    L6 -->|Fail + Already Revised| END5([END])

    L7[Layer 7: Revision]
    L7 --> OGF[Output Guardrails Final]
    OGF --> END6([END])
```

### Layer Summary

| Layer | Name                  | Purpose                                                      | Model Used   |
| ----- | --------------------- | ------------------------------------------------------------ | ------------ |
| **0** | Escalation Lock       | Prevents further processing if session is already escalated  | None         |
| **1** | Input Guardrails      | PII redaction, injection detection, health/chargeback flags  | None (regex) |
| **2** | Intent Classification | Classifies customer intent + detects mid-conversation shifts | Haiku        |
| **3** | ReAct Agents          | Domain-specific reasoning, tool calling, response generation | Sonnet       |
| **4** | Tool Call Guardrails  | Validates parameters, enforces limits, prevents duplicates   | None (code)  |
| **5** | Output Guardrails     | Checks for forbidden phrases, persona, internal leaks        | None (regex) |
| **6** | Reflection Validator  | 8-rule quality check on final response                       | Haiku        |
| **7** | Revision              | Rewrites response to fix identified quality issues           | Sonnet       |

---

## 🤖 Agent Deep Dives

### 1. Intent Classifier

The intent classifier is a **2-stage system** using Claude Haiku for fast, cheap classification.

```mermaid
flowchart LR
    MSG[Customer Message] --> HAIKU[Claude Haiku Classify]
    HAIKU --> PARSE[Parse Output]
    PARSE --> VALID{Valid Intent?}
    VALID -->|Yes| CONF{Confidence ≥ 80?}
    VALID -->|No| GEN[GENERAL 50%]
    CONF -->|Yes| AGENT[Route to Specialist]
    CONF -->|No| SUPER[Route to Supervisor]
```

**Supported Intent Categories:**

| Intent          | Agent         | Description                                |
| --------------- | ------------- | ------------------------------------------ |
| `WISMO`         | wismo_agent   | Shipping delays, tracking, delivery status |
| `WRONG_MISSING` | issue_agent   | Wrong/missing items in package             |
| `NO_EFFECT`     | issue_agent   | Product not working, no results            |
| `REFUND`        | issue_agent   | Refund requests, money back                |
| `ORDER_MODIFY`  | account_agent | Cancel order, change address               |
| `SUBSCRIPTION`  | account_agent | Subscription management, billing           |
| `DISCOUNT`      | account_agent | Discount codes, promo issues               |
| `POSITIVE`      | account_agent | Compliments, happy feedback                |
| `GENERAL`       | supervisor    | Greetings, unclear, multi-topic            |

**Multi-Turn Shift Detection:**

On messages after the first, the system runs a **shift check** instead of full classification. If the new intent maps to a different agent and confidence ≥ 85%, the conversation is routed to the new agent.

---

### 2. Supervisor Agent

The Supervisor acts as a **fallback router** when the intent classifier has low confidence (< 80%).

```mermaid
flowchart TD
    LOW[Low Confidence Classification] --> SUP[Supervisor Agent]
    SUP --> ANALYZE[Analyze Customer Message]
    ANALYZE --> DECIDE{Decision}

    DECIDE -->|Shipping/Tracking| WA[wismo_agent]
    DECIDE -->|Issues/Refunds| IA[issue_agent]
    DECIDE -->|Account/Subs| AA[account_agent]
    DECIDE -->|Simple Query| RD[respond_direct]
    DECIDE -->|Dangerous/Unclear| ESC[escalate]
```

The Supervisor uses **Claude Sonnet** to deeply analyze the message and outputs a structured routing decision in `ROUTE: | REASON:` format. If routing directly, it generates a response signed as "Caz".

---

### 3. WISMO Agent (Where Is My Order)

The WISMO Agent is the **shipping delay specialist**, handling all order tracking and delivery inquiries.

```mermaid
flowchart TD
    START[Where is my order?] --> FIND{Order # provided?}

    FIND -->|Yes| LOOKUP[Get Order Details]
    FIND -->|No| EMAIL[Get Customer Orders]

    EMAIL --> COUNT{How many orders?}
    COUNT -->|0| NOT_FOUND[No orders found]
    COUNT -->|1| LOOKUP
    COUNT -->|Multiple| DISAMBIG[List orders, ask which one]
    DISAMBIG --> LOOKUP

    LOOKUP --> STATUS{Order Status?}

    STATUS -->|UNFULFILLED| MSG_PREP[Order not shipped yet]
    STATUS -->|FULFILLED/In Transit| WAIT
    STATUS -->|DELIVERED| DELIVERED_CHECK{Customer says not received?}
    STATUS -->|CANCELLED| MSG_CANCEL[Order cancelled]

    WAIT[Day-Aware Wait Promise]
    WAIT --> TAG[Add WISMO tag]
    TAG --> RESPONSE[Send Response]

    DELIVERED_CHECK -->|First contact| WAIT
    DELIVERED_CHECK -->|Follow-up| RESHIP[Create Draft Order + ESCALATE]
```

**WISMO Tools:** `shopify_get_customer_orders`, `shopify_get_order_details`, `shopify_add_tags`, `shopify_create_draft_order`

**Key Rules:**

- NEVER promise a specific delivery date
- NEVER say "guaranteed" or "definitely"
- Day-aware wait promise changes based on the day of the week
- Follow-up after wait promise → create draft order + escalate for reship

---

### 4. Issue Agent

The Issue Agent handles **wrong/missing items, product issues, and refunds** following a strict resolution priority waterfall.

```mermaid
flowchart TD
    START[Customer reports issue] --> CLASSIFY{Issue Type?}

    CLASSIFY -->|Wrong/Missing| WF_A[Workflow A]
    CLASSIFY -->|No Effect| WF_B[Workflow B]
    CLASSIFY -->|Refund Request| WF_C[Workflow C]

    WF_A --> A1[Look up order]
    A1 --> A2[Ask what happened + photos]
    A2 --> A3[Resolution Waterfall]
    A3 --> A3a[Option 1: Free Reship]
    A3 --> A3b[Option 2: Store Credit +10%]
    A3 --> A3c[Option 3: Cash Refund]

    WF_B --> B1[Look up order]
    B1 --> B2[Ask customer's GOAL]
    B2 --> B3[Ask about USAGE]
    B3 --> B4{Usage Issue?}
    B4 -->|Wrong usage| B4a[Share usage guide]
    B4 -->|Product mismatch| B4b[Recommend alternative]
    B4 -->|Still unhappy| B4c[Store Credit → Refund]

    WF_C --> C1[Look up order]
    C1 --> C2[Ask for reason]
    C2 --> C3{Reason?}
    C3 -->|Didn't meet expectations| C3a[Usage tips + Swap]
    C3 -->|Shipping delay| C3b[Wait Promise]
    C3 -->|Damaged/Wrong| C3c[Workflow A]
    C3 -->|Changed mind unfulfilled| C3d[Handoff to account_agent]
    C3 -->|Changed mind fulfilled| C3e[Store Credit → Refund]
```

**Issue Tools:** `shopify_get_order_details`, `shopify_get_customer_orders`, `shopify_refund_order`, `shopify_create_store_credit`, `shopify_create_return`, `shopify_add_tags`, `shopify_get_product_recommendations`, `shopify_get_product_details`, `shopify_get_related_knowledge_source`, `shopify_create_draft_order`

**Resolution Priority (NEVER skip steps):**

1. 🔧 **Fix the issue** — correct usage tips, product swap recommendation
2. 📦 **Free reship** — escalate to Monica for physical shipment
3. 💳 **Store credit** — with 10% bonus on item value
4. 💰 **Cash refund** — LAST RESORT only after customer declines all alternatives

---

### 5. Account Agent

The Account Agent manages **order modifications, subscriptions, discounts, and positive feedback**.

```mermaid
flowchart TD
    START[Account Request] --> TYPE{Request Type?}

    TYPE -->|Cancel Order| WF_A[Workflow A]
    TYPE -->|Address Update| WF_B[Workflow B]
    TYPE -->|Subscription| WF_C[Workflow C]
    TYPE -->|Discount Code| WF_D[Workflow D]
    TYPE -->|Positive Feedback| WF_E[Workflow E]

    WF_A --> A1[Look up order]
    A1 --> A2[Ask cancellation reason]
    A2 --> A3{Reason?}
    A3 -->|Shipping Delay| A3a[Offer wait promise first]
    A3a --> A3a2[Cancel if refused]
    A3 -->|Accidental| A3b[Cancel + refund]
    A3 -->|Other| A3c[Cancel if unfulfilled]

    WF_B --> B1[Look up order]
    B1 --> B2{Same-day + UNFULFILLED?}
    B2 -->|Both true| B3[Update address]
    B2 -->|Either false| B4[ESCALATE]

    WF_C --> C1[Check subscription]
    C1 --> C2[Ask reason]
    C2 --> C3{Reason?}
    C3 -->|Too many| C3a[Skip → 20% off → Cancel]
    C3 -->|Quality issue| C3b[Product swap → Cancel]

    WF_D --> D1[Create 10% code]
    D1 --> D2[Share code 48hr validity]

    WF_E --> E1[Warm response]
    E1 --> E2[Ask for Trustpilot review]
    E2 -->|Yes| E3[Share review link]
    E2 -->|No| E4[No problem]
```

**Account Tools:** `shopify_get_order_details`, `shopify_get_customer_orders`, `shopify_cancel_order`, `shopify_update_order_shipping_address`, `shopify_add_tags`, `shopify_create_discount_code`, `shopify_get_product_recommendations`, `skio_get_subscription_status`, `skio_cancel_subscription`, `skio_pause_subscription`, `skio_skip_next_order_subscription`, `skio_unpause_subscription`

---

## 🛡 Guardrails System

The system implements a **3-tier guardrail architecture** that protects against unsafe inputs, incorrect tool usage, and inappropriate outputs.

```mermaid
flowchart LR
    INPUT[Customer Message] --> TIER1
    
    subgraph TIER1[Tier 1: Input Guardrails]
        I1[Empty/Gibberish Detection]
        I2[Prompt Injection Detection]
        I3[PII Redaction]
        I4[Length Cap]
        I5[Aggressive Language Flag]
        I6[Chargeback Threat Flag]
        I7[Health Concern Flag]
    end
    
    TIER1 --> AGENT[Agent Processing]
    
    subgraph TIER2[Tier 2: Tool Call Guardrails]
        T1[Order ID Format]
        T2[GID Validation]
        T3[Destructive Action Validation]
        T4[Cancel Order Defaults]
        T5[Discount Code Limit]
        T6[Store Credit Defaults]
        T7[Duplicate Call Prevention]
    end
    
    AGENT <--> TIER2
    AGENT --> TIER3
    
    subgraph TIER3[Tier 3: Output Guardrails]
        O1[HANDOFF/ESCALATE Detection]
        O2[Forbidden Phrase Check]
        O3[Persona Signature]
        O4[Competitor Mention Block]
        O5[Refund Amount Check]
        O6[Response Length Minimum]
        O7[Internal Info Leak Prevention]
    end
    
    TIER3 --> OUTPUT[Customer Response]
```

### Input Guardrails (Layer 1)

| Check                          | Action                                           | Outcome                       |
| ------------------------------ | ------------------------------------------------ | ----------------------------- |
| Empty/Gibberish                | Block + friendly re-prompt                       | `input_blocked = True`        |
| Prompt Injection (14 patterns) | Block + redirect to CS scope                     | `input_blocked = True`        |
| PII Detection                  | Redact in-place (CC, SSN, email, phone, address) | Continue with cleaned input   |
| Length > 5000 chars            | Truncate                                         | Continue                      |
| Aggressive Language            | Flag for agent context                           | `flag_escalation_risk = True` |
| Chargeback Threat              | Auto-escalate                                    | → Escalation Handler          |
| Health Concern                 | Auto-escalate                                    | → Escalation Handler          |

### Tool Call Guardrails (Layer 4)

| Check                                        | Action                                  |
| -------------------------------------------- | --------------------------------------- |
| `shopify_get_order_details` with bare number | Auto-prefix with `#`                    |
| Action tools without `gid://shopify/...`     | **Block** execution                     |
| Cancel/refund without order ID               | **Block** execution                     |
| Discount code when already created (max 1)   | **Block** execution                     |
| Discount code values                         | **Force** to 10%, 48hr, percentage type |
| Store credit missing customer ID             | **Auto-fill** from session state        |
| Duplicate tool call (last 3 calls)           | **Block** execution                     |

### Output Guardrails (Layer 5)

| Check                                           | Action                      |
| ----------------------------------------------- | --------------------------- |
| `HANDOFF:` prefix detected                      | Route to Handoff Router     |
| `ESCALATE:` prefix detected                     | Route to Escalation Handler |
| Embedded HANDOFF/ESCALATE in body               | Flag as internal leak       |
| Forbidden phrases (9 patterns)                  | Fail → revision             |
| Missing "Caz" signature                         | Fail → revision             |
| Competitor brand mentions (6 brands)            | Fail → revision             |
| Refund > order total × 1.10                     | Fail → revision             |
| Response < 20 characters                        | Fail → revision             |
| Internal keywords (`gid://`, `tool_call`, etc.) | Fail → revision             |

---

## 🪞 Reflection & Revision System

After output guardrails pass, the response undergoes an **8-rule quality check** using Claude Haiku, followed by optional revision using Claude Sonnet.

```mermaid
flowchart TD
    DRAFT[Draft Response from Agent] --> RV[Reflection Validator]

    RV --> R1[Rule 1: Resolution Order]
    RV --> R2[Rule 2: Wait Promise]
    RV --> R3[Rule 3: Escalation Check]
    RV --> R4[Rule 4: Information Gathering]
    RV --> R5[Rule 5: Tone & Persona]
    RV --> R6[Rule 6: Factual Accuracy]
    RV --> R7[Rule 7: GID vs Order Number]
    RV --> R8[Rule 8: Resolution Waterfall]

    R1 & R2 & R3 & R4 & R5 & R6 & R7 & R8 --> CHECK{All Pass?}

    CHECK -->|All Pass| SEND[Send to Customer]
    CHECK -->|Rule Failed| REVISE[Revision Node]
    REVISE --> OG_FINAL[Output Guardrails Final]
    OG_FINAL --> SEND2[Send to Customer]
```

**Important:** The revision cycle runs **at most once** (tracked by `was_revised` flag) to prevent infinite loops.

---

## 🔀 Escalation & Handoff Mechanism

### Cross-Agent Handoff

When a customer's request shifts outside an agent's domain, the agent emits a structured handoff command:

```
HANDOFF: target_agent | REASON: brief explanation
```

```mermaid
flowchart LR
    WA[WISMO Agent] -->|Customer wants refund| HR[Handoff Router]
    IA[Issue Agent] -->|Subscription query| HR
    AA[Account Agent] -->|Shipping status| HR

    HR --> PARSE[Parse HANDOFF]
    PARSE --> VALID{Valid Target?}
    VALID -->|Yes| ROUTE[Route to Target Agent]
    VALID -->|No| SUP[Fallback to Supervisor]

    LIMIT{Handoff Count ≥ 1?} -->|Yes| SUP
    LIMIT -->|No| ROUTE
```

**Loop Prevention:** Maximum **1 handoff per turn** (`handoff_count_this_turn`). If exceeded, falls back to Supervisor.

### Escalation Flow

Escalation happens via structured commands or automatic triggers:

```mermaid
flowchart TD
    subgraph TRIGGERS[Escalation Triggers]
        T1[Health Concern]
        T2[Chargeback Threat]
        T3[Reship Needed]
        T4[Address Error]
        T5[Billing Error]
        T6[Unresolved Loop]
        T7[Uncertain]
    end

    TRIGGERS --> ESC[Escalation Handler]

    ESC --> SUMMARY[Generate Summary]
    SUMMARY --> PAYLOAD[Build Escalation Payload]
    PAYLOAD --> MSG[Customer Message]
    MSG --> LOCK[Session Locked]
    LOCK --> POST[Post-Escalation Auto-Response]
```

**Escalation Payload includes:**

- Customer name, email, Shopify ID
- Order ID / Subscription ID (auto-resolved from tool call logs)
- Category, Priority (high if health/chargeback/billing)
- AI-generated summary of the conversation
- List of actions taken
- Last 10 conversation messages
- Draft order ID (if reship was prepared)

---

## 📦 State Management

The system uses a comprehensive `CustomerSupportState` TypedDict with **LangGraph's `add_messages` reducer** for message accumulation and **custom reducers** for reasoning logs.

```python
class CustomerSupportState(TypedDict):
    # Message history
    messages: Annotated[list, add_messages]
    
    # Customer info
    customer_email: str
    customer_first_name: str
    customer_last_name: str
    customer_shopify_id: str
    
    # Intent & routing
    ticket_category: str
    intent_confidence: int
    intent_shifted: bool
    current_agent: str
    
    # Order/subscription tracking
    current_order_id: str  # GID
    current_order_number: str  # #XXXXX
    current_subscription_id: str
    order_total: float
    
    # Guardrails
    input_blocked: bool
    pii_redacted: bool
    output_guardrail_passed: bool
    output_guardrail_issues: list[str]
    
    # Business logic
    discount_code_created: bool
    discount_code_created_count: int
    pending_refund_amount: float
    
    # Flags
    flag_escalation_risk: bool
    flag_chargeback_threat: bool
    flag_health_concern: bool
    
    # Handoff/escalation
    is_handoff: bool
    handoff_target: str
    handoff_count_this_turn: int
    is_escalated: bool
    escalation_payload: dict
    escalation_reason: str
    
    # Reflection
    reflection_passed: bool
    reflection_feedback: str
    reflection_rule_violated: str
    was_revised: bool
    
    # Tracing
    tool_calls_log: list[dict]
    actions_taken: list[str]
    agent_reasoning: Annotated[list[str], append]
```

**Persistence:** The state is checkpointed via `AsyncSqliteSaver` (LangGraph) into `history.db`, enabling full conversation history across sessions. Session metadata is separately stored in a SQLite table for the sidebar history UI.

---

## 🔧 Tool Ecosystem

### Shopify Tools (14 Tools)

| Tool                                     | Type   | ID Format                    | Description                      |
| ---------------------------------------- | ------ | ---------------------------- | -------------------------------- |
| `shopify_get_order_details`              | Lookup | `#XXXXX`                     | Fetch single order details       |
| `shopify_get_customer_orders`            | Lookup | Email                        | List customer orders (paginated) |
| `shopify_get_product_details`            | Lookup | Name/ID                      | Get product information          |
| `shopify_get_product_recommendations`    | Lookup | Keywords                     | Product recommendations          |
| `shopify_get_related_knowledge_source`   | Lookup | Question                     | FAQs, guides, articles           |
| `shopify_get_collection_recommendations` | Lookup | Keywords                     | Collection recommendations       |
| `shopify_cancel_order`                   | Action | `gid://shopify/Order/...`    | Cancel order (7 params)          |
| `shopify_refund_order`                   | Action | `gid://shopify/Order/...`    | Process refund                   |
| `shopify_create_store_credit`            | Action | `gid://shopify/Customer/...` | Issue store credit               |
| `shopify_add_tags`                       | Action | `gid://shopify/...`          | Add tags to resource             |
| `shopify_create_discount_code`           | Action | —                            | Create discount code             |
| `shopify_update_order_shipping_address`  | Action | `gid://shopify/Order/...`    | Update shipping address          |
| `shopify_create_return`                  | Action | `gid://shopify/Order/...`    | Create return                    |
| `shopify_create_draft_order`             | Action | —                            | Create draft order (reship prep) |

### Skio Subscription Tools (5 Tools)

| Tool                                | Description                        |
| ----------------------------------- | ---------------------------------- |
| `skio_get_subscription_status`      | Check subscription status by email |
| `skio_cancel_subscription`          | Cancel subscription with reasons   |
| `skio_pause_subscription`           | Pause until specific date          |
| `skio_skip_next_order_subscription` | Skip next subscription order       |
| `skio_unpause_subscription`         | Resume paused subscription         |

### Tool Assignment per Agent

**🚚 WISMO Agent — 4 Tools**
- `get_customer_orders`
- `get_order_details`
- `add_tags`
- `create_draft_order`

**🔧 Issue Agent — 11 Tools**
- `get_order_details`
- `get_customer_orders`
- `refund_order`
- `create_store_credit`
- `create_return`
- `add_tags`
- `get_product_recommendations`
- `get_collection_recommendations`
- `get_product_details`
- `get_related_knowledge_source`
- `create_draft_order`

**👤 Account Agent — 12 Tools**
- `get_order_details`
- `get_customer_orders`
- `cancel_order`
- `update_order_shipping_address`
- `add_tags`
- `create_discount_code`
- `get_product_recommendations`
- `skio_get_subscription_status`
- `skio_cancel_subscription`
- `skio_pause_subscription`
- `skio_skip_next_order`
- `skio_unpause_subscription`

---

## 📊 Tracing & Observability

Every decision, tool call, and reasoning step is captured in a structured `SessionTrace` object.

```python
@dataclass
class SessionTrace:
    session_id: str
    customer_email: str
    customer_name: str
    started_at: datetime
    
    # Intent tracking
    intent: str
    intent_confidence: int
    intent_shifted: bool
    
    # Trace entries (chronological log)
    entries: list[TraceEntry]
    
    # Final outcome
    final_response: str
    actions_taken: list[str]
    is_escalated: bool
    was_revised: bool
    
    # Conversation history
    messages: list[dict]

@dataclass
class TraceEntry:
    timestamp: datetime
    agent: str
    action_type: str  # guardrail_check, classification, routing, react_thought, tool_call, response, reflection, revision, escalation, handoff, intent_shift
    detail: str
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None
```

**Action Types:**
- `guardrail_check`
- `classification`
- `routing`
- `react_thought`
- `tool_call`
- `response`
- `reflection`
- `revision`
- `escalation`
- `handoff`
- `intent_shift`

The Streamlit UI displays traces in **real-time** alongside the chat interface, with a "Load Full Graph State" button for deep debugging.

---

## 🛠 Tech Stack

| Component                | Technology                                     |
| ------------------------ | ---------------------------------------------- |
| **Orchestration**        | LangGraph (StateGraph)                         |
| **LLM - Reasoning**      | Claude Sonnet 4 (`claude-sonnet-4-20250514`)   |
| **LLM - Classification** | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) |
| **API Framework**        | FastAPI                                        |
| **Frontend**             | Streamlit                                      |
| **State Persistence**    | AsyncSqliteSaver (LangGraph) + SQLite          |
| **HTTP Client**          | httpx (async + sync)                           |
| **E-Commerce**           | Shopify Admin API                              |
| **Subscriptions**        | Skio API                                       |
| **Schema Validation**    | Pydantic v2                                    |
| **Agent Pattern**        | ReAct (Reasoning + Acting)                     |
| **Language**             | Python 3.11+                                   |

---

## 📡 API Reference

| Endpoint              | Method | Description                                     |
| --------------------- | ------ | ----------------------------------------------- |
| `/health`             | GET    | Health check                                    |
| `/session/start`      | POST   | Start new support session                       |
| `/session/message`    | POST   | Send customer message, get agent response       |
| `/session/{id}/trace` | GET    | Get full session trace for observability        |
| `/sessions`           | GET    | List past sessions (optionally filter by email) |
| `/debug/set-time`     | POST   | Override system time for testing wait promises  |
| `/debug/clear-time`   | POST   | Clear time override                             |

### Example: Start Session

```json
POST /session/start
{
  "email": "sarah@example.com",
  "first_name": "Sarah",
  "last_name": "Jones",
  "customer_shopify_id": "gid://shopify/Customer/7424155189325"
}
```

### Example: Send Message

```json
POST /session/message
{
  "session_id": "session_abc123def456",
  "message": "Where is my order #43189?"
}
```

### Response

```json
{
  "session_id": "session_abc123def456",
  "response": "Hey Sarah! Let me look into order #43189 for you...\n\nCaz",
  "is_escalated": false,
  "actions_taken": [],
  "agent": "wismo_agent",
  "intent": "WISMO",
  "intent_confidence": 95,
  "was_revised": false,
  "intent_shifted": false
}
```

---

## 📁 Project Structure

```
natpat-multi-agent-cs/
├── main.py                          # FastAPI application & endpoints
├── history.db                       # SQLite — session metadata + LangGraph checkpoints
│
├── src/
│   ├── config.py                    # Environment, model instances, constants, time helpers
│   ├── database.py                  # Session metadata persistence (SQLite)
│   │
│   ├── graph/
│   │   ├── graph_builder.py         # LangGraph StateGraph — 7-layer pipeline
│   │   └── state.py                 # CustomerSupportState TypedDict
│   │
│   ├── agents/
│   │   ├── react_agents.py          # ReAct loop: WISMO, Issue, Account agents
│   │   ├── supervisor.py            # Supervisor fallback router
│   │   └── escalation.py            # Escalation handler + post-escalation lock
│   │
│   ├── patterns/
│   │   ├── guardrails.py            # Input / Output / Tool-call guardrails
│   │   ├── handoff.py               # Cross-agent handoff router
│   │   ├── intent_classifier.py     # 2-stage intent classification + shift detection
│   │   └── reflection.py            # 8-rule reflection validator + revision node
│   │
│   ├── prompts/
│   │   ├── wismo_prompt.py          # WISMO agent system prompt
│   │   ├── issue_prompt.py          # Issue agent system prompt
│   │   ├── account_prompt.py        # Account agent system prompt
│   │   ├── supervisor_prompt.py     # Supervisor agent prompt
│   │   ├── intent_classifier_prompt.py  # Haiku classification prompt
│   │   ├── reflection_prompt.py     # Reflection + revision prompts
│   │   └── shared_blocks.py         # Reusable prompt components
│   │
│   ├── tools/
│   │   ├── api_client.py            # Generic HTTP client with retry logic
│   │   ├── shopify_tools.py         # 14 Shopify tool wrappers
│   │   ├── skio_tools.py            # 5 Skio subscription tool wrappers
│   │   └── tool_groups.py           # Tool assignments per agent
│   │
│   └── tracing/
│       └── models.py                # TraceEntry, SessionTrace, build_session_trace
│
└── ui/
    └── app.py                       # Streamlit chat UI + trace timeline
```

---

## 🔑 Key Design Decisions

1. **Haiku for Classification, Sonnet for Reasoning** — Cost-optimized: fast/cheap Haiku handles classification and reflection, while powerful Sonnet handles complex agent reasoning and response generation.

2. **Manual ReAct Loop** — Instead of using LangGraph's `create_react_agent`, we implemented a custom ReAct loop for full control over tool call guardrails, state updates, and reasoning traces within each iteration.

3. **1-Cycle Revision Limit** — The reflection → revision loop runs at most once to prevent infinite correction cycles while still catching quality issues.

4. **Per-Turn State Reset** — Flags like `was_revised`, `handoff_count_this_turn`, and `is_handoff` are reset at the start of each turn (Layer 0) to prevent state pollution across turns.

5. **GID Auto-Resolution** — The escalation handler automatically resolves Shopify GIDs and subscription IDs from tool call logs, ensuring accurate escalation payloads even when agents don't explicitly track them.

6. **Day-Aware Wait Promises** — Different wait promise rules for WISMO vs. Cancellation/Refund contexts, with the current day injected into every prompt dynamically.

---

> **Built with ❤️ for the Lookfor Hackathon 2026**
