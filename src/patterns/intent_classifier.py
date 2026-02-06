"""
2-Stage Intent Classification + Multi-Turn Intent Shift Detection.

Stage 1: Haiku classifies intent with confidence score.
Stage 2: Deterministic code routes to agent (or supervisor fallback).
Multi-turn: Haiku re-classifies to detect intent shifts.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage

from src.config import (
    CONFIDENCE_THRESHOLD,
    INTENT_SHIFT_THRESHOLD,
    INTENT_TO_AGENT,
    VALID_INTENTS,
    haiku_llm,
)
from src.prompts.intent_classifier_prompt import INTENT_CLASSIFIER_PROMPT


# ─── Core Classifier ────────────────────────────────────────────────────────

async def classify_intent(message: str) -> tuple[str, int]:
    """Run Haiku to classify intent + confidence."""
    prompt = INTENT_CLASSIFIER_PROMPT.format(message=message)
    result = await haiku_llm.ainvoke(prompt)
    text = result.content.strip()

    parts = text.split("|")
    intent = parts[0].strip()
    try:
        confidence = int(parts[1].strip()) if len(parts) > 1 else 50
    except (ValueError, IndexError):
        confidence = 50

    if intent not in VALID_INTENTS:
        intent = "GENERAL"
        confidence = 50

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
        "agent_reasoning": [
            f"INTENT CLASSIFIER: {intent} (confidence: {confidence}%)"
        ],
    }


async def intent_shift_check_node(state: dict) -> dict:
    """Check if customer intent changed mid-conversation (multi-turn)."""
    new_message = state["messages"][-1].content
    current_agent = state.get("current_agent", "supervisor")

    new_intent, confidence = await classify_intent(new_message)
    expected_agent = INTENT_TO_AGENT.get(new_intent, "supervisor")

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
    confidence = state.get("intent_confidence", 0)
    intent = state.get("ticket_category", "GENERAL")

    if confidence >= CONFIDENCE_THRESHOLD:
        return INTENT_TO_AGENT.get(intent, "supervisor")
    return "supervisor"


def route_after_shift_check(state: dict) -> str:
    """Route after intent shift detection (multi-turn)."""
    return state.get("current_agent", "supervisor")