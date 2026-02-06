"""
Reflection Validator (8-rule check) + Revision Node.
Uses Haiku for cheap/fast QA, Sonnet for revision when needed.
"""

from __future__ import annotations

import json
from datetime import datetime

from langchain_core.messages import AIMessage

from src.config import get_current_context, haiku_llm, sonnet_llm
from src.prompts.reflection_prompt import REFLECTION_PROMPT, REVISION_PROMPT


# ─── Reflection Validator ────────────────────────────────────────────────────

async def reflection_validator_node(state: dict) -> dict:
    """Lightweight 8-rule check on the draft response. Max 1 cycle."""
    draft = state["messages"][-1].content

    # Gather context
    tool_results = json.dumps(
        (state.get("tool_calls_log") or [])[-5:], default=str
    )
    customer_msg = ""
    for m in reversed(state["messages"]):
        if hasattr(m, "type") and m.type == "human":
            customer_msg = m.content
            break

    turn_count = sum(
        1 for m in state["messages"] if hasattr(m, "type") and m.type == "human"
    )

    ctx = get_current_context()

    prompt = REFLECTION_PROMPT.format(
        draft_response=draft,
        tool_results=tool_results,
        customer_message=customer_msg,
        turn_count=turn_count,
        day_of_week=ctx["day_of_week"],
    )

    result = await haiku_llm.ainvoke(prompt)
    text = result.content.strip()

    # ── Parse JSON (with fallbacks) ──────────────────────────────────────
    validation: dict | None = None

    # Strip markdown fences
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        validation = json.loads(text)
    except json.JSONDecodeError:
        # Try extracting the first JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                validation = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

    # If still can't parse → retry once asking for JSON only
    if validation is None:
        retry_result = await haiku_llm.ainvoke(
            "Your previous response was not valid JSON. "
            "Please respond with ONLY valid JSON, no markdown:\n"
            '{"pass": true} OR {"pass": false, "rule_violated": "...", '
            '"reason": "...", "suggested_fix": "..."}'
        )
        retry_text = retry_result.content.strip().replace("```json", "").replace("```", "").strip()
        try:
            validation = json.loads(retry_text)
        except json.JSONDecodeError:
            return {
                "reflection_passed": True,
                "agent_reasoning": [
                    "REFLECTION: Parse error after retry, defaulting to pass"
                ],
            }

    if validation.get("pass"):
        return {
            "reflection_passed": True,
            "agent_reasoning": ["REFLECTION: All 8 rules passed ✅"],
        }

    return {
        "reflection_passed": False,
        "reflection_feedback": validation.get("reason", ""),
        "reflection_rule_violated": validation.get("rule_violated", ""),
        "reflection_suggested_fix": validation.get("suggested_fix", ""),
        "agent_reasoning": [
            f"REFLECTION: FAILED — Rule: {validation.get('rule_violated')}, "
            f"Reason: {validation.get('reason')}"
        ],
    }


# ─── Revision Node ───────────────────────────────────────────────────────────

async def revise_response_node(state: dict) -> dict:
    """Rewrite draft fixing the identified quality issue. Max 1 cycle."""
    draft = state["messages"][-1].content
    ctx = get_current_context()
    tool_results = json.dumps(
        (state.get("tool_calls_log") or [])[-5:], default=str
    )

    prompt = REVISION_PROMPT.format(
        draft_response=draft,
        rule_violated=state.get("reflection_rule_violated", "OUTPUT_GUARDRAILS"),
        reason=state.get("reflection_feedback", ""),
        suggested_fix=state.get("reflection_suggested_fix", ""),
        tool_results=tool_results,
        first_name=state.get("customer_first_name", "there"),
        current_date=ctx["current_date"],
        day_of_week=ctx["day_of_week"],
    )

    revised = await sonnet_llm.ainvoke(prompt)

    return {
        "messages": [AIMessage(content=revised.content)],
        "was_revised": True,
        "agent_reasoning": [
            f"REVISION: Response corrected for "
            f"{state.get('reflection_rule_violated', 'quality issue')}"
        ],
    }