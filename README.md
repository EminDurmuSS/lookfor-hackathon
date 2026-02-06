# 🏆 Lookfor Hackathon 2026 — Multi-Agent E-Commerce Customer Support

## High-Level Architecture

```
CUSTOMER MESSAGE
       │
  ┌────▼─────────────┐
  │ ESCALATION LOCK   │  → Session already escalated? → Auto-response → END
  └────┬──────────────┘
  ┌────▼─────────────┐
  │ INPUT GUARDRAILS  │  → PII redaction, prompt injection, health/safety detection
  └────┬──────────────┘
  ┌────▼─────────────┐
  │ INTENT CLASSIFIER │  → Haiku (fast, cheap) + confidence score
  │ or SHIFT CHECK    │  → Multi-turn: detect topic change mid-conversation
  └────┬──────────────┘
  ┌────▼─────────────┐
  │ ReAct AGENT       │  → WISMO / Issue / Account (Sonnet for quality)
  │ + TOOL CALLS      │  → 19 tools (Shopify + Skio)
  └────┬──────────────┘
  ┌────▼─────────────┐
  │ OUTPUT GUARDRAILS │  → Forbidden phrases, persona, internal leak check
  └────┬──────────────┘
  ┌────▼─────────────┐
  │ 8-RULE REFLECTION │  → Haiku validates workflow compliance
  └────┬──────────────┘
  ┌────▼─────────────┐
  │ REVISION (if fail)│  → Sonnet rewrites fixing the violation (max 1 cycle)
  └────┬──────────────┘
       ▼
  CUSTOMER RESPONSE ✅
```

## Agents

| Agent             | Scope                                                                       | Tools    |
| ----------------- | --------------------------------------------------------------------------- | -------- |
| **WISMO Agent**   | Shipping delays, order tracking, delivery status                            | 3 tools  |
| **Issue Agent**   | Wrong/missing items, product issues, refunds                                | 9 tools  |
| **Account Agent** | Cancellations, address changes, subscriptions, discounts, positive feedback | 11 tools |

## Routing & Orchestration

- **2-Stage Intent Classification**: Haiku classifier (fast/cheap) → deterministic code router
- **Confidence threshold**: ≥80% → direct route; <80% → Supervisor (Sonnet) fallback
- **Multi-turn**: Intent shift detection on subsequent messages
- **Cross-agent handoff**: Agents can transfer to each other mid-conversation
- **Multi-model strategy**: Haiku for classification/reflection, Sonnet for agents/revision

## Tool Calls

19 tools across Shopify and Skio APIs with:

- Automatic GID vs Order# format handling
- Tool call guardrails (parameter validation, destructive action checks)
- Duplicate call prevention
- Retry logic with graceful error handling

## Escalation

Triggers include: reship needed, health concerns, chargeback threats, billing errors, unresolved loops, address errors, API failures.

When escalation occurs:

1. Customer receives a warm handoff message to "Monica, Head of CS"
2. Structured summary is generated (category, priority, actions taken, conversation history)
3. Session is **locked** — no further automatic replies

## How to Run

### Docker (recommended)

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Fill in your keys
#    ANTHROPIC_API_KEY=sk-ant-...
#    API_URL=https://...

# 3. Start
docker compose up --build
```

- **FastAPI**: http://localhost:8000
- **Streamlit UI**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs

### Local Development

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys

# Terminal 1: FastAPI
uvicorn src.main:app --reload --port 8000

# Terminal 2: Streamlit
streamlit run src/ui/streamlit_app.py --server.port 8501
```

### API Usage

```bash
# Start session
curl -X POST http://localhost:8000/session/start \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@example.com","first_name":"Sarah","last_name":"Jones","customer_shopify_id":"gid://shopify/Customer/7424155189325"}'

# Send message
curl -X POST http://localhost:8000/session/message \
  -H "Content-Type: application/json" \
  -d '{"session_id":"SESSION_ID_HERE","message":"Where is my order #43189?"}'

# Get trace
curl http://localhost:8000/session/SESSION_ID_HERE/trace
```

## Observability

Every session produces a structured trace showing:

- Intent classification (category + confidence)
- Agent reasoning steps (ReAct thought/action/observation)
- Tool calls with inputs and outputs
- Guardrail checks (pass/fail)
- Reflection validation (8 rules)
- Revision details (if applied)
- Escalation payload (if triggered)

Visible in Streamlit UI trace panel or via `/session/{id}/trace` API endpoint.

## Environment Variables

| Variable            | Description                                   |
| ------------------- | --------------------------------------------- |
| `ANTHROPIC_API_KEY` | Anthropic API key                             |
| `API_URL`           | Hackathon tool API base URL                   |
| `APP_TIMEZONE`      | Timezone for day-of-week logic (default: UTC) |
