"""
2-Stage Intent Classification + Multi-Turn Intent Shift Detection.

Stage 1: Haiku classifies intent with confidence score.
Stage 2: Deterministic code routes to agent (or supervisor fallback).
Multi-turn: Haiku re-classifies to detect intent shifts.

Updates:
- Robust parsing: supports "INTENT|85" OR JSON {"intent": "...", "confidence": 85}
- Safe when haiku_llm is None (falls back to GENERAL with 50 unless strict=True)
- Confidence clamped to 0..100
- Removes duplicate imports/duplicate returns
"""

from __future__ import annotations

import json
import re
from typing import Any, Tuple

from src.config import (
    CONFIDENCE_THRESHOLD,
    INTENT_SHIFT_THRESHOLD,
    INTENT_TO_AGENT,
    VALID_INTENTS,
    haiku_llm,
)
from src.prompts.intent_classifier_prompt import INTENT_CLASSIFIER_PROMPT


# ─── Helpers ────────────────────────────────────────────────────────────────

def _clamp_confidence(x: Any, default: int = 50) -> int:
    try:
        val = int(x)
    except (TypeError, ValueError):
        val = default
    return max(0, min(val, 100))


def _parse_classifier_output(text: str) -> Tuple[str, int]:
    """
    Accepts:
      - "WISMO|85"
      - "WISMO | 85"
      - JSON: {"intent":"WISMO","confidence":85}
    Returns (intent, confidence).
    """
    raw = (text or "").strip()

    # Try JSON first (some LLM prompts drift into JSON)
    if raw.startswith("{") and raw.endswith("}"):
        try:
            obj = json.loads(raw)
            intent = str(obj.get("intent", "")).strip()
            conf = _clamp_confidence(obj.get("confidence", 50))
            return intent, conf
        except Exception:  # noqa: BLE001
            pass

    # Fallback to pipe-delimited
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    intent = parts[0] if parts else "GENERAL"
    confidence = _clamp_confidence(parts[1] if len(parts) > 1 else 50)
    return intent, confidence


_ACK_RE = re.compile(r"[^a-z0-9\s]")
_SHORT_ACKS: set[str] = {
    "yes",
    "yep",
    "yeah",
    "sure",
    "ok",
    "okay",
    "sounds good",
    "that works",
    "works",
    "please do",
    "go ahead",
    "do it",
    "thanks",
    "thank you",
    "got it",
    "alright",
}


def _is_short_acknowledgement(message: str) -> bool:
    """Detect brief confirmation messages that should keep current agent."""
    cleaned = _ACK_RE.sub(" ", (message or "").lower())
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return False
    if cleaned in _SHORT_ACKS:
        return True
    if len(cleaned.split()) <= 3 and any(token in cleaned for token in ("yes", "sure", "ok", "okay")):
        return True
    return False


# ─── Core Classifier ────────────────────────────────────────────────────────

async def classify_intent(message: str, *, strict: bool = False) -> tuple[str, int]:
    """
    Run Haiku to classify intent + confidence.
    If haiku_llm is unavailable:
      - strict=False -> returns ("GENERAL", 50)
      - strict=True  -> raises RuntimeError
    """
    if haiku_llm is None:
        if strict:
            raise RuntimeError(
                "Intent classifier model is unavailable. Install langchain-anthropic "
                "and configure ANTHROPIC_API_KEY."
            )
        return "GENERAL", 50

    prompt = INTENT_CLASSIFIER_PROMPT.format(message=message)
    result = await haiku_llm.ainvoke(prompt)
    text = getattr(result, "content", "").strip()

    intent, confidence = _parse_classifier_output(text)

    # Validate intent
    if intent not in VALID_INTENTS:
        return "GENERAL", 50

    return intent, confidence


# ─── Graph Nodes ─────────────────────────────────────────────────────────────

async def intent_classifier_node(state: dict) -> dict:
    """Intent classification for the FIRST human message."""
    customer_message = state["messages"][-1].content
    intent, confidence = await classify_intent(customer_message)

    return {
        "ticket_category": intent,
        "intent_confidence": confidence,
        "current_agent": INTENT_TO_AGENT.get(intent, "supervisor"),
        "agent_reasoning": [f"INTENT CLASSIFIER: {intent} (confidence: {confidence}%)"],
    }


async def intent_shift_check_node(state: dict) -> dict:
    """Check if customer intent changed mid-conversation (multi-turn)."""
    new_message = state["messages"][-1].content
    current_agent = state.get("current_agent", "supervisor")

    if _is_short_acknowledgement(new_message):
        return {
            "intent_shifted": False,
            "agent_reasoning": [
                f"MULTI-TURN: Short acknowledgement detected, continuing with {current_agent}"
            ],
        }

    new_intent, confidence = await classify_intent(new_message)
    expected_agent = INTENT_TO_AGENT.get(new_intent, "supervisor")

    if new_intent == "GENERAL" and current_agent != "supervisor":
        return {
            "intent_shifted": False,
            "agent_reasoning": [
                f"MULTI-TURN: Ignoring GENERAL drift, continuing with {current_agent} "
                f"(checked: {new_intent} @ {confidence}%)"
            ],
        }

    if expected_agent != current_agent and confidence >= INTENT_SHIFT_THRESHOLD:
        return {
            "ticket_category": new_intent,
            "intent_confidence": confidence,
            "current_agent": expected_agent,
            "intent_shifted": True,
            "agent_reasoning": [
                f"INTENT SHIFT: {current_agent} → {expected_agent} "
                f"(new intent: {new_intent}, confidence: {confidence}%)"
            ],
        }

    return {
        "intent_shifted": False,
        "agent_reasoning": [
            f"MULTI-TURN: Continuing with {current_agent} "
            f"(checked: {new_intent} @ {confidence}%)"
        ],
    }


# ─── Routing Functions ───────────────────────────────────────────────────────

def route_by_confidence(state: dict) -> str:
    """Route based on confidence threshold after first-message classification."""
    confidence = int(state.get("intent_confidence", 0) or 0)
    intent = state.get("ticket_category", "GENERAL")

    if confidence >= CONFIDENCE_THRESHOLD:
        return INTENT_TO_AGENT.get(intent, "supervisor")
    return "supervisor"


def route_after_shift_check(state: dict) -> str:
    """Route after intent shift detection (multi-turn)."""
    return state.get("current_agent", "supervisor")
