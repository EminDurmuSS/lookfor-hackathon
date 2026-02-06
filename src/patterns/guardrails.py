"""
Input / Output / Tool-Call Guardrails.
Covers: PII redaction, prompt injection, empty messages, aggressive language,
health concern detection, forbidden phrases, persona check, internal leak, etc.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage


# ═════════════════════════════════════════════════════════════════════════════
# 1.  INPUT GUARDRAILS
# ═════════════════════════════════════════════════════════════════════════════

_INJECTION_PATTERNS: list[str] = [
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

_AGGRESSIVE_PATTERNS: list[str] = [
    "lawsuit", "sue you", "sue your company", "lawyer", "legal action",
    "report you", "bbb complaint", "better business bureau",
    "chargeback", "dispute the charge", "credit card company",
    "attorney general", "consumer protection",
]

_HEALTH_PATTERNS: list[str] = [
    "allergic reaction", "allergy", "rash", "hives", "swelling",
    "breathing difficulty", "anaphylax", "hospital", "emergency room",
    "doctor said", "pediatrician",
]


def input_guardrails_node(state: dict) -> dict:
    """Validate & sanitise customer message before routing."""
    message: str = state["messages"][-1].content
    lower_msg = message.lower().strip()
    first_name = state.get("customer_first_name", "there")

    # ── 1. Empty / gibberish ─────────────────────────────────────────────
    if len(lower_msg) < 3 or not any(c.isalpha() for c in lower_msg):
        reply = (
            f"Hey {first_name}! 😊 It looks like your message might not have "
            f"come through properly. Could you let me know how I can help?\n\nCaz"
        )
        return {
            "input_blocked": True,
            "override_response": reply,
            "messages": [AIMessage(content=reply)],
            "agent_reasoning": ["INPUT GUARDRAIL: Empty or gibberish message"],
        }

    # ── 2. Prompt injection ──────────────────────────────────────────────
    for pattern in _INJECTION_PATTERNS:
        if pattern in lower_msg:
            reply = (
                f"Hey {first_name}! 😊 I'm here to help with your NatPat "
                f"orders, shipping, and products. What can I do for you today?\n\nCaz"
            )
            return {
                "input_blocked": True,
                "override_response": reply,
                "messages": [AIMessage(content=reply)],
                "agent_reasoning": [
                    "INPUT GUARDRAIL: Potential prompt injection detected"
                ],
            }

    # ── 3. PII redaction ─────────────────────────────────────────────────
    cleaned = message
    cleaned = re.sub(
        r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        "[CARD REDACTED]",
        cleaned,
    )
    cleaned = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN REDACTED]", cleaned)
    pii_detected = cleaned != message

    # ── 4. Length cap ────────────────────────────────────────────────────
    if len(cleaned) > 5000:
        cleaned = cleaned[:5000] + "... [truncated]"

    # Write sanitised content back into the message object
    if cleaned != message:
        try:
            state["messages"][-1].content = cleaned
        except Exception:  # noqa: BLE001
            pass

    # ── 5. Aggressive language ───────────────────────────────────────────
    aggressive = any(p in lower_msg for p in _AGGRESSIVE_PATTERNS)

    # ── 6. Health / safety ───────────────────────────────────────────────
    health = any(p in lower_msg for p in _HEALTH_PATTERNS)

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
        "agent_reasoning": [
            f"INPUT GUARDRAIL: {', '.join(reasons) if reasons else 'Clean input'}"
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# 2.  OUTPUT GUARDRAILS
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

_COMPETITORS: list[str] = [
    "zevo", "off!", "repel", "raid", "babyganics", "skin so soft",
]

_INTERNAL_PATTERNS: list[str] = [
    "gid://shopify", "tool_call", "system prompt", "state[", "state.get",
    "thought:", "observation:", "action:",
]


def output_guardrails_node(state: dict) -> dict:
    """Validate agent response before it reaches the customer."""
    response: str = state["messages"][-1].content
    lower = response.lower()
    issues: list[str] = []

    # ── Handoff / Escalation intercept ───────────────────────────────────
    stripped = response.strip()
    if stripped.startswith("HANDOFF:"):
        return {
            "output_guardrail_passed": True,
            "is_handoff": True,
            "agent_reasoning": [
                "OUTPUT GUARDRAIL: Handoff detected, bypassing checks"
            ],
        }
    if stripped.startswith("ESCALATE:"):
        # Parse escalation category
        parts = stripped.split("|")
        cat = parts[0].replace("ESCALATE:", "").strip().lower()
        reason = parts[1].replace("REASON:", "").strip() if len(parts) > 1 else ""
        return {
            "output_guardrail_passed": True,
            "is_escalation": True,
            "escalation_reason": cat,
            "escalation_detail": reason,
            "agent_reasoning": [
                f"OUTPUT GUARDRAIL: Escalation detected — {cat}: {reason}"
            ],
        }

    # ── Forbidden phrases ────────────────────────────────────────────────
    for phrase, reason in _FORBIDDEN_PHRASES:
        if phrase in lower:
            issues.append(f"FORBIDDEN PHRASE: '{phrase}' — {reason}")

    # ── Persona (Caz signature) ──────────────────────────────────────────
    if "caz" not in lower:
        issues.append("PERSONA: Response missing Caz signature")

    # ── Competitor mentions ──────────────────────────────────────────────
    for comp in _COMPETITORS:
        if comp in lower:
            issues.append(f"COMPETITOR: Mentioned '{comp}'")

    # ── Refund amount sanity ─────────────────────────────────────────────
    pending = state.get("pending_refund_amount")
    total = state.get("order_total")
    if pending and total:
        try:
            if float(pending) > float(total) * 1.1:
                issues.append("AMOUNT: Refund exceeds order total + 10% bonus")
        except (ValueError, TypeError):
            pass

    # ── Too short ────────────────────────────────────────────────────────
    if len(response.strip()) < 20:
        issues.append("LENGTH: Response too short for customer communication")

    # ── Internal info leak ───────────────────────────────────────────────
    for pat in _INTERNAL_PATTERNS:
        if pat in lower:
            issues.append(f"INTERNAL LEAK: Contains '{pat}'")

    if issues:
        return {
            "output_guardrail_passed": False,
            "output_guardrail_issues": issues,
            # Pre-populate reflection fields so revise_response can use them
            "reflection_rule_violated": "OUTPUT_GUARDRAILS",
            "reflection_feedback": "; ".join(issues),
            "reflection_suggested_fix": (
                "Remove forbidden/internal content, ensure Caz signature, "
                "fix any identified issues."
            ),
            "agent_reasoning": [
                f"OUTPUT GUARDRAIL: FAILED — {'; '.join(issues)}"
            ],
        }

    return {
        "output_guardrail_passed": True,
        "agent_reasoning": ["OUTPUT GUARDRAIL: Passed all checks"],
    }


# ═════════════════════════════════════════════════════════════════════════════
# 3.  TOOL CALL GUARDRAILS  (called from a wrapper around every tool)
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


def tool_call_guardrails(
    tool_name: str,
    params: dict,
    state: dict,
) -> tuple[bool, str, dict]:
    """
    Validate / correct tool parameters before execution.
    Returns (is_allowed, reason, corrected_params).
    """
    cp = params.copy()

    # ── 1. Order ID format auto-correction ───────────────────────────────
    if tool_name == "shopify_get_order_details" and "orderId" in cp:
        oid = str(cp["orderId"])
        if not oid.startswith("#"):
            cp["orderId"] = f"#{oid}"

    # ── 2. GID validation for action tools ───────────────────────────────
    if tool_name in _GID_REQUIRED_TOOLS:
        field = _GID_REQUIRED_TOOLS[tool_name]
        val = str(cp.get(field, ""))
        if val and not val.startswith("gid://"):
            return (
                False,
                f"Tool '{tool_name}' requires Shopify GID (gid://shopify/…), got '{val}'",
                cp,
            )

    # ── 3. Destructive action validation ─────────────────────────────────
    if tool_name in _DESTRUCTIVE_TOOLS:
        if tool_name == "shopify_cancel_order" and not cp.get("orderId"):
            return False, "Cannot cancel order without valid order ID", cp
        if tool_name == "shopify_refund_order" and not cp.get("orderId"):
            return False, "Cannot refund order without valid order ID", cp
        if tool_name == "skio_cancel_subscription" and not cp.get("subscriptionId"):
            return False, "Cannot cancel subscription without ID", cp

    # ── 4. Cancel order defaults (7 required params) ─────────────────────
    if tool_name == "shopify_cancel_order":
        cp.setdefault("reason", "CUSTOMER")
        cp.setdefault("notifyCustomer", True)
        cp.setdefault("restock", True)
        cp.setdefault("staffNote", "Customer requested cancellation via chat")
        cp.setdefault("refundMode", "ORIGINAL")
        cp.setdefault("storeCredit", {"expiresAt": None})

    # ── 5. Discount code limits ──────────────────────────────────────────
    if tool_name == "shopify_create_discount_code":
        if state.get("discount_code_created"):
            return (
                False,
                "Already created a discount code for this customer (max 1)",
                cp,
            )
        cp["type"] = "percentage"
        cp["value"] = 0.10
        cp["duration"] = 48
        cp.setdefault("productIds", [])

    # ── 6. Store credit 10% bonus enforcement ────────────────────────────
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

    # ── 7. Get customer orders defaults ──────────────────────────────────
    if tool_name == "shopify_get_customer_orders":
        cp.setdefault("after", "null")
        cp.setdefault("limit", 10)

    # ── 8. Duplicate call prevention (last 3) ────────────────────────────
    recent = (state.get("tool_calls_log") or [])[-3:]
    for call in recent:
        if call.get("tool_name") == tool_name and call.get("params") == cp:
            return False, f"Duplicate tool call detected: {tool_name}", cp

    return True, "OK", cp