"""
Input / Output / Tool-Call Guardrails.
Covers: PII redaction, prompt injection, empty messages, aggressive language,
health concern detection, forbidden phrases, persona check, internal leak, etc.

Design goals:
- Works even if langchain_core is not installed (safe fallback AIMessage).
- Does not duplicate dict keys (fixes the earlier "messages" overwrite bug).
- Keeps your public API: input_guardrails_node, output_guardrails_node, tool_call_guardrails
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from typing import Any


# ── Optional AIMessage (langchain) ────────────────────────────────────────────
@dataclass
class _FallbackAIMessage:
    """Lightweight message object used when langchain is unavailable."""
    content: str


def _build_ai_message(content: str) -> Any:
    """Create an AI message even when langchain is unavailable."""
    if importlib.util.find_spec("langchain_core") is not None:
        messages_module = importlib.import_module("langchain_core.messages")
        AIMessage = getattr(messages_module, "AIMessage")
        return AIMessage(content=content)
    return _FallbackAIMessage(content=content)


# ═════════════════════════════════════════════════════════════════════════════
# 1) INPUT GUARDRAILS
# ═════════════════════════════════════════════════════════════════════════════

# Keep patterns simple/fast and do substring match on normalized text.
_INJECTION_PATTERNS: list[str] = [
    "ignore previous instructions",
    "ignore all instructions",
    "forget everything",
    "system prompt",
    "reveal your prompt",
    "override your",
    "disregard your programming",
    "jailbreak",
    "act as if",
    "pretend you are",
    "you are now",
    "new instructions",
    "developer message",
    "tool instructions",
]

_AGGRESSIVE_PATTERNS: list[str] = [
    "lawsuit",
    "sue you",
    "sue your company",
    "lawyer",
    "legal action",
    "report you",
    "bbb complaint",
    "better business bureau",
    "chargeback",
    "dispute the charge",
    "credit card company",
    "attorney general",
    "consumer protection",
]

_HEALTH_PATTERNS: list[str] = [
    "allergic reaction",
    "allergy",
    "rash",
    "hives",
    "swelling",
    "breathing difficulty",
    "difficulty breathing",
    "anaphylax",
    "anaphylaxis",
    "hospital",
    "emergency room",
    "urgent care",
    "doctor said",
    "pediatrician",
]

# Common PII patterns (best-effort)
_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b")
_CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")  # rough; catches many digit sequences
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# street address heuristics: keep conservative (avoid too many false positives)
_ADDRESS_RE = re.compile(r"\b\d{1,5}\s+[A-Za-z0-9.\-]+\s+(?:st|street|ave|avenue|rd|road|blvd|boulevard|ln|lane|dr|drive)\b", re.IGNORECASE)

# phrases you never want user to see in output, but also block if user tries to inject
_INTERNAL_KEYWORDS: list[str] = [
    "gid://shopify",
    "tool_call",
    "system prompt",
    "developer message",
    "state[",
    "state.get",
    "thought:",
    "observation:",
    "action:",
]

_MAX_INPUT_CHARS = 5000


def _normalize_text(s: str) -> str:
    return " ".join((s or "").lower().strip().split())


def _redact_pii(text: str) -> tuple[str, bool]:
    """Return (redacted_text, pii_detected). Conservative best-effort redaction."""
    if not text:
        return text, False

    cleaned = text

    # Card numbers first (largest digit sequences)
    cleaned2 = _CC_RE.sub("[CARD REDACTED]", cleaned)
    # SSN
    cleaned2 = _SSN_RE.sub("[SSN REDACTED]", cleaned2)
    # Email
    cleaned2 = _EMAIL_RE.sub("[EMAIL REDACTED]", cleaned2)
    # Phone (after CC so we don't partially mask CC)
    cleaned2 = _PHONE_RE.sub("[PHONE REDACTED]", cleaned2)
    # Address heuristic
    cleaned2 = _ADDRESS_RE.sub("[ADDRESS REDACTED]", cleaned2)

    return cleaned2, (cleaned2 != cleaned)


def input_guardrails_node(state: dict) -> dict:
    """
    Validate & sanitise customer message before routing.
    Expects: state["messages"][-1].content exists.
    """
    message: str = state["messages"][-1].content
    norm = _normalize_text(message)
    first_name = state.get("customer_first_name", "there")

    # ── 1) Empty / gibberish ──────────────────────────────────────────────
    if len(norm) < 3 or not any(c.isalpha() for c in norm):
        reply = (
            f"Hey {first_name}! 😊 It looks like your message might not have "
            f"come through properly. Could you tell me what you need help with?\n\nCaz"
        )
        return {
            "input_blocked": True,
            "override_response": reply,
            "messages": [_build_ai_message(reply)],
            "agent_reasoning": ["INPUT GUARDRAIL: Empty or gibberish message"],
        }

    # ── 2) Prompt injection / internal probing ───────────────────────────
    if any(pat in norm for pat in _INJECTION_PATTERNS) or any(k in norm for k in _INTERNAL_KEYWORDS):
        reply = (
            f"Hey {first_name}! 😊 I’m here to help with your orders, shipping, "
            f"and product questions. What can I do for you today?\n\nCaz"
        )
        return {
            "input_blocked": True,
            "override_response": reply,
            "messages": [_build_ai_message(reply)],
            "agent_reasoning": ["INPUT GUARDRAIL: Potential prompt injection detected"],
        }

    # ── 3) PII redaction ─────────────────────────────────────────────────
    cleaned, pii_detected = _redact_pii(message)

    # ── 4) Length cap ────────────────────────────────────────────────────
    if len(cleaned) > _MAX_INPUT_CHARS:
        cleaned = cleaned[:_MAX_INPUT_CHARS] + "... [truncated]"

    # write sanitized content back into the message object (best effort)
    if cleaned != message:
        try:
            state["messages"][-1].content = cleaned
        except Exception:  # noqa: BLE001
            pass

    # ── 5) Aggressive language flag ──────────────────────────────────────
    aggressive = any(p in norm for p in _AGGRESSIVE_PATTERNS)

    # ── 6) Health / safety flag ──────────────────────────────────────────
    health = any(p in norm for p in _HEALTH_PATTERNS)

    reasons: list[str] = []
    if pii_detected:
        reasons.append("PII redacted")
    if aggressive:
        reasons.append("⚠️ Aggressive language detected")
    if health:
        reasons.append("🏥 Health concern detected")

    return {
        "input_blocked": False,
        "pii_redacted": pii_detected,
        "flag_escalation_risk": aggressive,
        "flag_health_concern": health,
        "agent_reasoning": [f"INPUT GUARDRAIL: {', '.join(reasons) if reasons else 'Clean input'}"],
    }


# ═════════════════════════════════════════════════════════════════════════════
# 2) OUTPUT GUARDRAILS
# ═════════════════════════════════════════════════════════════════════════════

_FORBIDDEN_PHRASES: list[tuple[str, str]] = [
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

# Case-insensitive substring list; keep short.
_COMPETITORS: list[str] = [
    "zevo",
    "off!",
    "repel",
    "raid",
    "babyganics",
    "skin so soft",
]

_INTERNAL_PATTERNS: list[str] = [
    "gid://shopify",
    "tool_call",
    "system prompt",
    "developer message",
    "state[",
    "state.get",
    "thought:",
    "observation:",
    "action:",
]


def output_guardrails_node(state: dict) -> dict:
    """
    Validate agent response before it reaches the customer.
    Expects: state["messages"][-1].content exists (the draft response).
    """
    response: str = state["messages"][-1].content
    lower = _normalize_text(response)
    issues: list[str] = []

    # ── Allow control messages to pass through ────────────────────────────
    stripped = (response or "").strip()
    if stripped.startswith("HANDOFF:"):
        return {
            "output_guardrail_passed": True,
            "is_handoff": True,
            "agent_reasoning": ["OUTPUT GUARDRAIL: Handoff detected, bypassing checks"],
        }
    if stripped.startswith("ESCALATE:"):
        parts = stripped.split("|")
        cat = parts[0].replace("ESCALATE:", "").strip().lower()
        reason = parts[1].replace("REASON:", "").strip() if len(parts) > 1 else ""
        return {
            "output_guardrail_passed": True,
            "is_escalation": True,
            "escalation_reason": cat,
            "escalation_detail": reason,
            "agent_reasoning": [f"OUTPUT GUARDRAIL: Escalation detected — {cat}: {reason}"],
        }

    # ── Forbidden phrases ────────────────────────────────────────────────
    for phrase, reason in _FORBIDDEN_PHRASES:
        if phrase in lower:
            issues.append(f"FORBIDDEN PHRASE: '{phrase}' — {reason}")

    # ── Persona signature ────────────────────────────────────────────────
    # Your style: responses end with "\n\nCaz". We enforce presence of "caz" anywhere.
    if "caz" not in lower:
        issues.append("PERSONA: Response missing Caz signature")

    # ── Competitor mentions ──────────────────────────────────────────────
    for comp in _COMPETITORS:
        if comp in lower:
            issues.append(f"COMPETITOR: Mentioned '{comp}'")

    # ── Refund amount sanity ─────────────────────────────────────────────
    pending = state.get("pending_refund_amount")
    total = state.get("order_total")
    if pending is not None and total is not None:
        try:
            if float(pending) > float(total) * 1.10:
                issues.append("AMOUNT: Refund exceeds order total + 10% bonus")
        except (ValueError, TypeError):
            pass

    # ── Too short ────────────────────────────────────────────────────────
    if len(stripped) < 20:
        issues.append("LENGTH: Response too short for customer communication")

    # ── Internal info leak ───────────────────────────────────────────────
    for pat in _INTERNAL_PATTERNS:
        if pat in lower:
            issues.append(f"INTERNAL LEAK: Contains '{pat}'")

    if issues:
        return {
            "output_guardrail_passed": False,
            "output_guardrail_issues": issues,
            "reflection_rule_violated": "OUTPUT_GUARDRAILS",
            "reflection_feedback": "; ".join(issues),
            "reflection_suggested_fix": (
                "Remove forbidden/internal content, ensure Caz signature, "
                "and revise any problematic claims or mentions."
            ),
            "agent_reasoning": [f"OUTPUT GUARDRAIL: FAILED — {'; '.join(issues)}"],
        }

    return {
        "output_guardrail_passed": True,
        "agent_reasoning": ["OUTPUT GUARDRAIL: Passed all checks"],
    }


# ═════════════════════════════════════════════════════════════════════════════
# 3) TOOL CALL GUARDRAILS (called from a wrapper around every tool)
# ═════════════════════════════════════════════════════════════════════════════

_GID_REQUIRED_TOOLS: dict[str, str] = {
    "shopify_cancel_order": "orderId",
    "shopify_refund_order": "orderId",
    "shopify_create_return": "orderId",
    "shopify_update_order_shipping_address": "orderId",
    "shopify_add_tags": "id",
}

_DESTRUCTIVE_TOOLS: set[str] = {
    "shopify_cancel_order",
    "shopify_refund_order",
    "skio_cancel_subscription",
}

_MAX_DISCOUNT_CODES_PER_CONVO = 1


def tool_call_guardrails(
    tool_name: str,
    params: dict,
    state: dict,
) -> tuple[bool, str, dict]:
    """
    Validate / correct tool parameters before execution.
    Returns (is_allowed, reason, corrected_params).
    """
    cp = dict(params or {})

    # ── 1) Order ID format auto-correction ───────────────────────────────
    if tool_name == "shopify_get_order_details" and "orderId" in cp:
        oid = str(cp["orderId"])
        if oid and not oid.startswith("#") and not oid.startswith("gid://"):
            cp["orderId"] = f"#{oid}"

    # ── 2) GID validation for action tools ───────────────────────────────
    if tool_name in _GID_REQUIRED_TOOLS:
        field = _GID_REQUIRED_TOOLS[tool_name]
        val = str(cp.get(field, "") or "")
        if val and not val.startswith("gid://"):
            return (
                False,
                f"Tool '{tool_name}' requires Shopify GID (gid://shopify/…), got '{val}'",
                cp,
            )

    # ── 3) Destructive action validation ─────────────────────────────────
    if tool_name in _DESTRUCTIVE_TOOLS:
        if tool_name == "shopify_cancel_order" and not cp.get("orderId"):
            return False, "Cannot cancel order without valid order ID", cp
        if tool_name == "shopify_refund_order" and not cp.get("orderId"):
            return False, "Cannot refund order without valid order ID", cp
        if tool_name == "skio_cancel_subscription" and not cp.get("subscriptionId"):
            return False, "Cannot cancel subscription without ID", cp

    # ── 4) Cancel order defaults (7 required params) ─────────────────────
    if tool_name == "shopify_cancel_order":
        cp.setdefault("reason", "CUSTOMER")
        cp.setdefault("notifyCustomer", True)
        cp.setdefault("restock", True)
        cp.setdefault("staffNote", "Customer requested cancellation via chat")
        cp.setdefault("refundMode", "ORIGINAL")
        cp.setdefault("storeCredit", {"expiresAt": None})

    # ── 5) Discount code limits ──────────────────────────────────────────
    if tool_name == "shopify_create_discount_code":
        created = int(state.get("discount_code_created_count") or 0)
        if created >= _MAX_DISCOUNT_CODES_PER_CONVO:
            return (
                False,
                "Already created a discount code for this customer (max 1)",
                cp,
            )
        # enforce your fixed policy
        cp["type"] = "percentage"
        cp["value"] = 0.10
        cp["duration"] = 48
        cp.setdefault("productIds", [])

    # ── 6) Store credit 10% bonus enforcement ────────────────────────────
    if tool_name == "shopify_create_store_credit":
        if "creditAmount" in cp:
            amt = cp["creditAmount"]
            if isinstance(amt, dict) and "amount" in amt:
                try:
                    original = float(amt["amount"])
                    bonus = round(original * 1.10, 2)
                    cp["creditAmount"]["amount"] = str(bonus)
                except (ValueError, TypeError):
                    pass
        if not cp.get("id"):
            cp["id"] = state.get("customer_shopify_id", "")
        cp.setdefault("expiresAt", None)

    # ── 7) Get customer orders defaults ──────────────────────────────────
    if tool_name == "shopify_get_customer_orders":
        # NOTE: some APIs expect None instead of "null". Keep your original behavior.
        cp.setdefault("after", "null")
        cp.setdefault("limit", 10)

    # ── 8) Duplicate call prevention (last 3) ────────────────────────────
    recent = (state.get("tool_calls_log") or [])[-3:]
    for call in recent:
        if call.get("tool_name") == tool_name and call.get("params") == cp:
            return False, f"Duplicate tool call detected: {tool_name}", cp

    return True, "OK", cp
