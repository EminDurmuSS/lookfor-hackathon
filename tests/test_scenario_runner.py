#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
NatPat Multi-Agent System — Comprehensive Scenario Test Runner  (v2.2)
═══════════════════════════════════════════════════════════════════════════════

Tests the live multi-agent system against the REAL API using scenarios
from the anonymized_ticket_test.json file.

Produces a detailed .log file with:
  - Full conversation turns (input → output)
  - Tool calls with params & results
  - Agent routing decisions & reasoning trace
  - Guardrail checks (input/output)
  - Escalation payloads
  - Reflection / Revision details
  - Intent classification & shifts
  - Per-scenario PASS/FAIL with reason
  - Summary statistics

Additionally produces a FAIL-ONLY log file with:
  - Only failed/errored scenarios + failure reasons
  - Last response snippet for quick debugging
  - Summary footer

Usage:
  # 1. Ensure Real API is running at APP_URL
  # 2. Run tests:         python test_scenario_runner.py

  Options via environment variables:
    APP_URL        — Main app URL (default: http://localhost:8000)
    MOCK_API_URL   — Mock API URL (default: http://localhost:8080)
    LOG_FILE       — Output log file (default: test_results_{timestamp}.log)
    FAIL_LOG_FILE  — Fail-only log file (default: test_failures_{timestamp}.log)
    SCENARIOS      — Comma-separated scenario IDs or 'all' (default: all)
    CATEGORIES     — Comma-separated categories to run (default: all)
    RESET_BETWEEN  — Reset mock API state between scenarios (default: true)
    VERBOSE        — Show full JSON payloads in log (default: true)
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Optional

import httpx

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

APP_URL = os.getenv("APP_URL", "http://localhost:8000")
MOCK_API_URL = os.getenv("MOCK_API_URL", "http://localhost:8080")
RESET_BETWEEN = False # os.getenv("RESET_BETWEEN", "true").lower() == "true" # Disabled for real API
SCENARIO_FILTER = os.getenv("SCENARIOS", "all")
CATEGORY_FILTER = os.getenv("CATEGORIES", "all")
VERBOSE = os.getenv("VERBOSE", "true").lower() == "true"

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.getenv("LOG_FILE", f"test_results_{timestamp}.log")
FAIL_LOG_FILE = os.getenv("FAIL_LOG_FILE", f"test_failures_{timestamp}.log")

TIMEOUT = 120.0  # seconds per LLM call — generous for ReAct loops


# ═══════════════════════════════════════════════════════════════════════════════
# Logger — writes to both console and log file
# ═══════════════════════════════════════════════════════════════════════════════

class DualLogger:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.file = open(filepath, "w", encoding="utf-8")

    def log(self, msg: str = "", end: str = "\n"):
        line = msg + end
        sys.stdout.write(line)
        sys.stdout.flush()
        self.file.write(line)
        self.file.flush()

    def section(self, title: str, char: str = "═", width: int = 90):
        self.log(char * width)
        self.log(f"  {title}")
        self.log(char * width)

    def subsection(self, title: str, char: str = "─", width: int = 70):
        self.log(f"\n  {char * 3} {title} {char * max(1, width - len(title) - 5)}")

    def kv(self, key: str, value: Any, indent: int = 4):
        prefix = " " * indent
        val_str = str(value)
        if not VERBOSE and len(val_str) > 200:
            val_str = val_str[:200] + "…"
        self.log(f"{prefix}{key}: {val_str}")

    def json_block(self, data: Any, indent_level: int = 6, max_lines: int = 80):
        prefix = " " * indent_level
        try:
            formatted = json.dumps(data, indent=2, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            formatted = str(data)
        lines = formatted.split("\n")
        if not VERBOSE and len(lines) > max_lines:
            for line in lines[: max_lines // 2]:
                self.log(f"{prefix}{line}")
            self.log(f"{prefix}  ... ({len(lines) - max_lines} lines omitted) ...")
            for line in lines[-(max_lines // 2) :]:
                self.log(f"{prefix}{line}")
        else:
            for line in lines:
                self.log(f"{prefix}{line}")

    def close(self):
        self.file.close()


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP Client Helpers
# ═══════════════════════════════════════════════════════════════════════════════

client = httpx.Client(timeout=TIMEOUT)


def reset_mock_api() -> bool:
    try:
        r = client.post(f"{MOCK_API_URL}/admin/reset")
        return r.status_code == 200
    except Exception:
        return False


def configure_mock_responses(mock_responses: dict) -> bool:
    """Queue mock_tool_responses into the mock API for scenario isolation."""
    if not mock_responses:
        return True
    try:
        for tool_name, response in mock_responses.items():
            r = client.post(
                f"{MOCK_API_URL}/admin/set_mock_override",
                json={"tool_name": tool_name, "response": response}
            )
            if r.status_code != 200:
                return False
        return True
    except Exception:
        return False


def clear_mock_overrides() -> bool:
    """Clear all queued mock overrides after scenario completes."""
    try:
        r = client.post(f"{MOCK_API_URL}/admin/clear_mock_overrides")
        return r.status_code == 200
    except Exception:
        return False


def set_mock_time_for_day(day_name: str) -> tuple[bool, Optional[dict]]:
    """Set mock API time for test_day scenarios and return payload."""
    try:
        r = client.post(f"{MOCK_API_URL}/admin/set_time", json={"day": day_name})
        if r.status_code != 200:
            return False, None
        payload = r.json()
        return bool(payload.get("success", True)), payload
    except Exception:
        return False, None


def _wait_promise_for_day(day_name: str) -> str:
    """Mirror src.config wait-promise logic for deterministic scenario runs."""
    if day_name in {"Monday", "Tuesday", "Wednesday"}:
        return "this Friday"
    return "early next week"


def set_app_time_override(date_str: str, day_name: str) -> bool:
    """Sync app-side date context with mock API date context."""
    try:
        body = {
            "date": date_str,
            "day_of_week": day_name,
            "wait_promise": _wait_promise_for_day(day_name),
        }
        r = client.post(f"{APP_URL}/debug/set-time", json=body)
        return r.status_code == 200
    except Exception:
        return False


def clear_app_time_override() -> bool:
    """Clear app-side date override to avoid cross-scenario leakage."""
    try:
        r = client.post(f"{APP_URL}/debug/clear-time")
        return r.status_code == 200
    except Exception:
        return False


def check_health(url: str) -> bool:
    """Check if API is accessible."""
    try:
        r = client.get(f"{url}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def start_session(customer: dict) -> dict:
    r = client.post(f"{APP_URL}/session/start", json=customer)
    r.raise_for_status()
    return r.json()


def send_message(session_id: str, message: str) -> dict:
    r = client.post(
        f"{APP_URL}/session/message",
        json={"session_id": session_id, "message": message},
    )
    r.raise_for_status()
    return r.json()


def get_trace(session_id: str) -> Optional[dict]:
    try:
        r = client.get(f"{APP_URL}/session/{session_id}/trace")
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions for Assertions
# ═══════════════════════════════════════════════════════════════════════════════

def _has_any(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(kw.lower() in low for kw in keywords)


def _no_forbidden(text: str) -> bool:
    forbidden = [
        "guaranteed delivery", "i promise", "100% money back",
        "thought:", "action:", "observation:",
        "gid://shopify", "tool_call",
    ]
    low = text.lower()
    return not any(f in low for f in forbidden)


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario Loading from JSON
# ═══════════════════════════════════════════════════════════════════════════════

SCENARIOS_JSON_PATH = os.path.join(os.path.dirname(__file__), "anonymized_ticket_test.json")

DEFAULT_CUSTOMER = {
    "email": "sarah@example.com",
    "first_name": "Sarah",
    "last_name": "Jones",
    "customer_shopify_id": "gid://shopify/Customer/7424155189325",
}

SCENARIOS: list[dict] = []


def _build_checks_from_expected(expected: dict) -> list[tuple[str, callable]]:
    """
    Convert JSON 'expected' block into list of (description, check_fn) tuples.
    Each check is a lambda that receives (response_dict, trace_dict).
    """
    checks = []

    # ── Intent / Agent checks ─────────────────────────────────────────────
    if "intent" in expected:
        intent = expected["intent"]
        checks.append((
            f"Intent = {intent}",
            lambda r, t, i=intent: r.get("intent", r.get("ticket_category", "")) == i
        ))

    if "agent" in expected:
        agent = expected["agent"]
        checks.append((
            f"Agent = {agent}",
            lambda r, t, a=agent: r.get("agent", r.get("current_agent", "")) == a
        ))

    # ── Escalation checks ─────────────────────────────────────────────────
    if "escalation" in expected:
        esc = expected["escalation"]
        if esc is True:
            checks.append((
                "Is escalated",
                lambda r, t: r.get("is_escalated", False) is True
            ))
        elif esc is False:
            checks.append((
                "Not escalated",
                lambda r, t: r.get("is_escalated", False) is False
            ))

    # ── Handoff checks ────────────────────────────────────────────────────
    if "handoff_to" in expected:
        target = expected["handoff_to"]
        checks.append((
            f"Handoff to {target}",
            lambda r, t, tgt=target: r.get("agent", r.get("current_agent", "")) == tgt
            or t.get("handoff_target") == tgt
        ))

    # ── Response content checks ───────────────────────────────────────────
    if "response_must_contain" in expected:
        keywords = expected["response_must_contain"]
        checks.append((
            f"Response contains: {keywords}",
            lambda r, t, kw=keywords: _has_any(r.get("response", ""), kw)
        ))

    if "response_must_not_contain" in expected:
        forbidden = expected["response_must_not_contain"]
        checks.append((
            f"Response must NOT contain: {forbidden}",
            lambda r, t, f=forbidden: not _has_any(r.get("response", ""), f)
        ))

    if "response_must_end_with_signature" in expected:
        sig = expected["response_must_end_with_signature"]
        checks.append((
            f"Signed as {sig}",
            lambda r, t, s=sig: s.lower() in r.get("response", "").lower()
        ))

    if "wait_promise_must_contain" in expected:
        keywords = expected["wait_promise_must_contain"]
        checks.append((
            f"Wait promise mentions: {keywords}",
            lambda r, t, kw=keywords: _has_any(r.get("response", ""), kw)
        ))

    if "response_should_ask" in expected:
        keywords = expected["response_should_ask"]
        checks.append((
            f"Response asks about: {keywords}",
            lambda r, t, kw=keywords: _has_any(r.get("response", ""), kw)
        ))

    # ── Tool call checks ──────────────────────────────────────────────────
    if "tools_called" in expected:
        tools = expected["tools_called"]
        checks.append((
            f"Tools called: {tools}",
            lambda r, t, tl=tools: _check_tools_called(t, tl)
        ))

    # ── Boolean flags ─────────────────────────────────────────────────────
    bool_checks = [
        ("must_ask_reason", ["why", "reason", "happened"], True),
        ("must_ask_usage_details", ["how", "usage", "using", "how many", "how long"], True),
        ("must_ask_for_details", ["which", "describe", "photo", "details", "tell me"], True),
        ("must_ask_which_items", ["which", "missing", "items"], True),
        ("must_ask_which_product", ["which", "product", "item"], True),
        ("must_offer_reship_first", ["reship", "replacement", "send", "correct"], True),
        ("must_offer_store_credit_first", ["store credit", "credit"], True),
        ("must_offer_store_credit_before_refund", ["store credit", "credit"], True),
        ("must_apply_wait_promise", ["friday", "next week", "wait", "few more days"], True),
        ("must_not_offer_refund_first_turn", ["refund"], False),
        ("must_not_offer_refund_yet", ["refund"], False),
        ("must_not_jump_to_refund", ["refund"], False),
        ("must_not_jump_to_cash_refund", ["cash refund", "refund to"], False),
        ("must_not_process_refund_immediately", ["processed", "refunded", "initiated"], False),
        ("must_not_cancel_immediately", ["cancelled", "canceled"], False),
        ("must_not_give_another_wait_promise", ["friday", "next week", "wait"], False),
        ("must_share_usage_tips", ["tips", "try", "recommend", "suggest"], True),
        ("must_suggest_try_longer", ["try", "longer", "more", "days", "nights"], True),
    ]

    for flag, keywords, should_contain in bool_checks:
        if expected.get(flag):
            if should_contain:
                checks.append((
                    f"{flag.replace('_', ' ').title()}",
                    lambda r, t, kw=keywords: _has_any(r.get("response", ""), kw)
                ))
            else:
                checks.append((
                    f"{flag.replace('_', ' ').title()}",
                    lambda r, t, kw=keywords: not _has_any(r.get("response", ""), kw)
                ))

    # ── Default guardrail checks ──────────────────────────────────────────
    checks.append((
        "No internal markers (THOUGHT/ACTION/gid://)",
        lambda r, t: _no_forbidden(r.get("response", ""))
    ))

    return checks


def _check_tools_called(trace: dict, expected_tools: list[str]) -> bool:
    """Check if expected tools were called in the trace."""
    traces = trace.get("traces", [])
    called = set()
    for entry in traces:
        if entry.get("action_type") in ("tool_call", "tool_execution"):
            tool_name = entry.get("tool_name", "")
            if tool_name:
                called.add(tool_name)

    tool_calls_log = trace.get("tool_calls_log", [])
    for tc in tool_calls_log:
        if isinstance(tc, dict) and tc.get("tool_name"):
            called.add(tc["tool_name"])

    return all(t in called for t in expected_tools)


def load_scenarios_from_json() -> list[dict]:
    """Load and parse scenarios from anonymized_ticket_test.json."""
    global SCENARIOS

    if not os.path.exists(SCENARIOS_JSON_PATH):
        print(f"⚠️ WARNING: {SCENARIOS_JSON_PATH} not found. Using empty scenario list.")
        return []

    with open(SCENARIOS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_scenarios = data.get("scenarios", [])
    loaded = []

    for sc in raw_scenarios:
        # Extract customer messages only
        messages = []
        for msg in sc.get("messages", []):
            if msg.get("role") == "customer":
                messages.append(msg.get("content", ""))

        customer = sc.get("customer", DEFAULT_CUSTOMER)
        
        # Get the old agent response for comparison (from agent_response field)
        old_agent_response = sc.get("agent_response", "")

        scenario_obj = {
            "id": sc.get("id", "UNKNOWN"),
            "title": sc.get("title", "Untitled"),
            "category": sc.get("category", "UNKNOWN"),
            "description": sc.get("description", ""),
            "messages": messages,
            "customer": customer,
            "old_agent_response": old_agent_response,  # Old agent's response for comparison
        }
        loaded.append(scenario_obj)

    SCENARIOS = loaded
    print(f"✅ Loaded {len(SCENARIOS)} scenarios from {SCENARIOS_JSON_PATH}")
    return SCENARIOS


load_scenarios_from_json()


# ═══════════════════════════════════════════════════════════════════════════════
# Detailed Trace Logger
# ═══════════════════════════════════════════════════════════════════════════════

ACTION_ICONS = {
    "guardrail_check": "🛡️", "input_guardrail": "🛡️", "output_guardrail": "🛡️",
    "classification": "🏷️", "intent_classification": "🏷️",
    "routing": "🔀", "agent_routing": "🔀",
    "react_thought": "💭", "thought": "💭",
    "tool_call": "🔧", "tool_execution": "🔧",
    "response": "💬", "agent_response": "💬",
    "reflection": "🔎", "revision": "✏️",
    "escalation": "🚨", "handoff": "🔄",
    "intent_shift": "↩️", "session_lock": "🔒", "pii_redaction": "🔐",
}


def log_detailed_trace(logger: DualLogger, trace_data: dict):
    """Log the full session trace with maximum detail."""
    trace = trace_data.get("trace", trace_data)

    logger.log("      ┌─────────────────────────────────────────────────────────┐")
    logger.log("      │                  📋 STATE SNAPSHOT                      │")
    logger.log("      └─────────────────────────────────────────────────────────┘")

    state_fields = [
        ("session_id", "Session"),
        ("customer_email", "Customer Email"),
        ("customer_first_name", "First Name"),
        ("ticket_category", "Intent Category"),
        ("intent_confidence", "Intent Confidence"),
        ("intent_shifted", "Intent Shifted"),
        ("current_agent", "Active Agent"),
        ("is_escalated", "Escalated"),
        ("escalation_reason", "Escalation Reason"),
        ("reflection_passed", "Reflection Passed"),
        ("was_revised", "Was Revised"),
        ("reflection_rule_violated", "Reflection Rule Violated"),
        ("reflection_feedback", "Reflection Feedback"),
        ("reflection_suggested_fix", "Suggested Fix"),
        ("output_guardrail_passed", "Output Guardrail OK"),
        ("input_blocked", "Input Blocked"),
        ("pii_redacted", "PII Redacted"),
        ("discount_code_created", "Discount Created"),
        ("is_handoff", "Handoff Occurred"),
        ("handoff_target", "Handoff Target"),
        ("handoff_count_this_turn", "Handoff Count"),
        ("flag_escalation_risk", "Escalation Risk Flag"),
        ("flag_health_concern", "Health Concern Flag"),
    ]

    for field, label in state_fields:
        val = trace.get(field)
        if val is not None and val != "" and val != [] and val is not False:
            logger.log(f"         {label:25s}: {val}")
    logger.log()

    reasoning = trace.get("agent_reasoning", [])
    if reasoning:
        logger.log("      ┌─────────────────────────────────────────────────────────┐")
        logger.log("      │              🧠 AGENT REASONING CHAIN                   │")
        logger.log("      └─────────────────────────────────────────────────────────┘")
        for i, step in enumerate(reasoning, 1):
            if step.startswith("HANDOFF:"):
                logger.log(f"         🔄 [{i:2d}] {step}")
            elif step.startswith("ESCALATED"):
                logger.log(f"         🚨 [{i:2d}] {step}")
            elif step.startswith("SESSION LOCKED"):
                logger.log(f"         🔒 [{i:2d}] {step}")
            else:
                logger.log(f"         💭 [{i:2d}] {step}")
        logger.log()

    traces = trace.get("traces", [])
    if traces:
        logger.log("      ┌─────────────────────────────────────────────────────────┐")
        logger.log(f"      │          🔍 STEP-BY-STEP TRACE ({len(traces):2d} steps)                │")
        logger.log("      └─────────────────────────────────────────────────────────┘")

        for i, entry in enumerate(traces, 1):
            action_type = entry.get("action_type", entry.get("type", "unknown"))
            agent = entry.get("agent", "")
            detail = entry.get("detail", entry.get("message", ""))
            passed = entry.get("passed")
            icon = ACTION_ICONS.get(action_type, "▪️")

            if passed is True:
                status = " ✓"
            elif passed is False:
                status = " ✗"
            else:
                status = ""

            logger.log(f"         ┄┄┄ Step {i} ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
            logger.log(f"         {icon} [{action_type}]{status}")
            if agent:
                logger.log(f"            Agent:   {agent}")
            if detail:
                for j, chunk in enumerate(_wrap_text(detail, 110)):
                    if j == 0:
                        logger.log(f"            Detail:  {chunk}")
                    else:
                        logger.log(f"                     {chunk}")

            tool_name = entry.get("tool_name")
            if tool_name:
                tool_input = entry.get("tool_input", entry.get("input", {}))
                tool_output = entry.get("tool_output", entry.get("output", {}))

                logger.log(f"            ╔═ Tool: {tool_name}")
                input_str = json.dumps(tool_input, default=str, ensure_ascii=False)
                logger.log(f"            ║  Input:  {input_str[:300]}")
                out_str = json.dumps(tool_output, default=str, ensure_ascii=False)
                if len(out_str) > 500 and not VERBOSE:
                    logger.log(f"            ║  Output: {out_str[:500]}…")
                else:
                    for j, chunk in enumerate(_wrap_text(out_str, 100)):
                        if j == 0:
                            logger.log(f"            ║  Output: {chunk}")
                        else:
                            logger.log(f"            ║          {chunk}")

                if isinstance(tool_output, dict):
                    success = tool_output.get("success")
                    if success is not None:
                        logger.log(f"            ╚═ Success: {'✅ true' if success else '❌ false'}")
                    else:
                        logger.log("            ╚═══════════")
                else:
                    logger.log("            ╚═══════════")

            issues = entry.get("issues", entry.get("guardrail_issues", []))
            if issues:
                logger.log(f"            ⚠️ Issues: {issues}")

            if action_type in ("reflection", "revision"):
                rule = entry.get("rule_violated", entry.get("rule"))
                fix = entry.get("suggested_fix", entry.get("fix"))
                if rule:
                    logger.log(f"            Rule Violated:  {rule}")
                if fix:
                    logger.log(f"            Suggested Fix:  {fix}")

        logger.log()

    tool_calls = [t for t in traces if t.get("action_type") in ("tool_call", "tool_execution")]
    if not tool_calls:
        tool_calls_log = trace.get("tool_calls_log", [])
        if tool_calls_log:
            logger.log(f"      🔧 TOOL CALLS LOG ({len(tool_calls_log)} calls):")
            for tc in tool_calls_log:
                logger.json_block(tc, indent_level=10)
            logger.log()
    else:
        logger.log(f"      🔧 TOOL CALLS SUMMARY ({len(tool_calls)} calls):")
        for tc in tool_calls:
            tn = tc.get("tool_name", "?")
            ti = tc.get("tool_input", tc.get("input", {}))
            to = tc.get("tool_output", tc.get("output", {}))
            success = to.get("success", "?") if isinstance(to, dict) else "?"
            s_icon = "✅" if success is True else ("❌" if success is False else "❓")
            logger.log(f"         {s_icon} {tn}({json.dumps(ti, default=str, ensure_ascii=False)[:150]})")
        logger.log()

    actions = trace.get("actions_taken", [])
    if actions:
        logger.log("      ⚡ ACTIONS TAKEN:")
        for a in actions:
            logger.log(f"         • {a}")
        logger.log()

    og_issues = trace.get("output_guardrail_issues", [])
    if og_issues:
        logger.log("      🛡️ OUTPUT GUARDRAIL ISSUES:")
        for issue in og_issues:
            logger.log(f"         ⚠️ {issue}")
        logger.log()

    esc_payload = trace.get("escalation_payload")
    if esc_payload:
        logger.log("      🚨 ESCALATION PAYLOAD:")
        logger.json_block(esc_payload, indent_level=10)
        logger.log()

    if VERBOSE:
        shown = {f[0] for f in state_fields} | {
            "traces", "agent_reasoning", "tool_calls_log",
            "actions_taken", "output_guardrail_issues",
            "escalation_payload", "messages", "trace",
        }
        extra = {k: v for k, v in trace.items() if k not in shown and v}
        if extra:
            logger.log("      📦 ADDITIONAL TRACE DATA:")
            logger.json_block(extra, indent_level=10, max_lines=40)
            logger.log()


def _wrap_text(text: str, width: int) -> list[str]:
    """Split long text into chunks for display."""
    if len(text) <= width:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:width])
        text = text[width:]
    return chunks


# ═══════════════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_scenario(logger: DualLogger, sc: dict, index: int, total: int) -> dict:
    """Run a single scenario and return result dict with old vs new agent comparison."""
    sid = sc["id"]
    old_agent_response = sc.get("old_agent_response", "")

    logger.log()
    logger.section(f"SCENARIO {index}/{total}: {sid} — {sc['title']}", "═")
    logger.kv("Category", sc["category"])
    logger.kv("Customer", f"{sc['customer']['first_name']} {sc['customer']['last_name']} <{sc['customer']['email']}>")
    logger.kv("Turns", len(sc["messages"]))
    logger.kv("Has Old Response", "Yes" if old_agent_response else "No")

    result = {
        "id": sid, "title": sc["title"], "category": sc["category"],
        "passed": True, "error": None, "turns": [], "duration_s": 0,
        "old_agent_response": old_agent_response,
        "new_agent_response": "",
    }
    start_time = time.time()

    try:
        # Configure test_day FIRST (this triggers a reset with recalculated dates)
        if sc.get("test_day") and False: # Disabled for real API
            day_ok, payload = set_mock_time_for_day(sc["test_day"])
            logger.log(f"    [Mock time → {sc['test_day']}: {'OK' if day_ok else 'FAILED'}]")
            if day_ok and isinstance(payload, dict):
                mock_day = str(payload.get("day") or sc["test_day"])
                new_now = str(payload.get("new_now") or "")
                date_str = new_now.split("T")[0] if "T" in new_now else new_now
                if date_str:
                    app_sync_ok = set_app_time_override(date_str, mock_day)
                    logger.log(
                        f"    [App time sync -> {mock_day} {date_str}: {'OK' if app_sync_ok else 'FAILED'}]"
                    )
        elif RESET_BETWEEN and False: # Disabled for real API
            ok = reset_mock_api()
            logger.log(f"    [Mock API state reset: {'OK' if ok else 'FAILED'}]")
            app_clear_ok = clear_app_time_override()
            logger.log(f"    [App time clear: {'OK' if app_clear_ok else 'FAILED'}]")

        # Inject mock_tool_responses if specified
        if sc.get("mock_tool_responses") and False: # Disabled for real API
            mock_ok = configure_mock_responses(sc["mock_tool_responses"])
            logger.log(f"    [Mock overrides: {'OK' if mock_ok else 'FAILED'} — {list(sc['mock_tool_responses'].keys())}]")

        logger.subsection("SESSION START")
        session_data = start_session(sc["customer"])
        session_id = session_data.get("session_id", "")
        logger.kv("Session ID", session_id, indent=6)

        if not session_id:
            raise RuntimeError(f"Failed to start session: {session_data}")

        if VERBOSE:
            logger.log("      Full session start response:")
            logger.json_block(session_data, indent_level=8)

        last_response = None

        for turn_idx, msg in enumerate(sc["messages"], 1):
            logger.subsection(f"TURN {turn_idx}/{len(sc['messages'])}")
            logger.log("      📨 CUSTOMER INPUT:")
            logger.log(f"         \"{msg}\"")
            logger.log()

            turn_start = time.time()
            resp = send_message(session_id, msg)
            turn_duration = round(time.time() - turn_start, 2)
            last_response = resp

            turn_data = {
                "turn": turn_idx,
                "input": msg,
                "response": resp.get("response", ""),
                "agent": resp.get("agent", resp.get("current_agent", "")),
                "intent": resp.get("intent", resp.get("ticket_category", "")),
                "confidence": resp.get("intent_confidence", 0),
                "is_escalated": resp.get("is_escalated", False),
                "was_revised": resp.get("was_revised", False),
                "intent_shifted": resp.get("intent_shifted", False),
                "actions_taken": resp.get("actions_taken", []),
                "duration_s": turn_duration,
            }
            result["turns"].append(turn_data)

            logger.log(f"      🤖 AGENT RESPONSE (took {turn_duration}s):")
            logger.log(f"         Agent:          {turn_data['agent'] or 'N/A'}")
            logger.log(f"         Intent:         {turn_data['intent'] or 'N/A'} ({turn_data['confidence']}%)")
            logger.log(f"         Escalated:      {turn_data['is_escalated']}")
            logger.log(f"         Revised:        {turn_data['was_revised']}")
            logger.log(f"         Intent Shifted: {turn_data['intent_shifted']}")
            if turn_data["actions_taken"]:
                logger.log("         Actions:")
                for a in turn_data["actions_taken"]:
                    logger.log(f"            • {a}")
            logger.log()

            logger.log("      📝 RESPONSE TEXT:")
            logger.log(f"      ┌{'─' * 66}┐")
            for line in resp.get("response", "(empty)").split("\n"):
                if len(line) <= 64:
                    logger.log(f"      │ {line:64s} │")
                else:
                    logger.log(f"      │ {line}")
            logger.log(f"      └{'─' * 66}┘")
            logger.log()

            if VERBOSE:
                extra_resp = {k: v for k, v in resp.items()
                              if k not in ("response", "session_id") and v}
                if extra_resp:
                    logger.log("      📦 ALL RESPONSE FIELDS:")
                    logger.json_block(extra_resp, indent_level=10, max_lines=50)
                    logger.log()

        logger.subsection("SESSION TRACE (Post-Conversation)")
        trace_data = get_trace(session_id)

        if trace_data:
            log_detailed_trace(logger, trace_data)
        else:
            logger.log("      ⚠️  Trace endpoint returned no data.")
            logger.log("         (Check /session/{id}/trace endpoint)")

        # Store new agent response
        new_response = last_response.get("response", "") if last_response else ""
        result["new_agent_response"] = new_response

        # ── OLD vs NEW Agent Response Comparison ──────────────────────────
        logger.subsection("OLD vs NEW AGENT RESPONSE COMPARISON")
        
        if old_agent_response:
            logger.log("      📜 OLD AGENT RESPONSE:")
            logger.log(f"      ┌{'─' * 66}┐")
            for line in old_agent_response.split("\n"):
                if len(line) <= 64:
                    logger.log(f"      │ {line:64s} │")
                else:
                    logger.log(f"      │ {line}")
            logger.log(f"      └{'─' * 66}┘")
            logger.log()
        else:
            logger.log("      ⚠️ No old agent response available for this scenario")
            logger.log()

        logger.log("      🤖 NEW AGENT RESPONSE:")
        logger.log(f"      ┌{'─' * 66}┐")
        for line in new_response.split("\n") if new_response else ["(empty)"]:
            if len(line) <= 64:
                logger.log(f"      │ {line:64s} │")
            else:
                logger.log(f"      │ {line}")
        logger.log(f"      └{'─' * 66}┘")
        logger.log()

    except Exception as exc:
        result["passed"] = False
        result["error"] = str(exc)
        logger.log(f"\n      💥 SCENARIO ERROR: {exc}")
        logger.log(traceback.format_exc())

    finally:
        pass  # No mock cleanup needed for real API

    result["duration_s"] = round(time.time() - start_time, 2)
    status = "✅ COMPLETED" if result["passed"] else "❌ ERROR"
    logger.log(f"\n    {status} [{result['duration_s']}s]")
    logger.log()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    logger = DualLogger(LOG_FILE)
    fail_f = None

    try:
        # Open fail-only log file
        fail_f = open(FAIL_LOG_FILE, "w", encoding="utf-8")
        fail_f.write("NatPat Multi-Agent System — FAILED SCENARIOS ONLY (Real API)\n")
        fail_f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        fail_f.write(f"App URL: {APP_URL}\n")
        fail_f.write(f"Main Log: {LOG_FILE}\n")
        fail_f.write("=" * 90 + "\n\n")
        fail_f.flush()

        logger.section("NatPat Multi-Agent System — Scenario Test Report (v2.2 - Real API)")
        logger.log(f"  Timestamp:       {datetime.now().isoformat()}")
        logger.log(f"  App URL:         {APP_URL}")
        logger.log(f"  Log File:        {LOG_FILE}")
        logger.log(f"  Fail Log File:   {FAIL_LOG_FILE}")
        logger.log(f"  Total Scenarios: {len(SCENARIOS)}")
        logger.log()

        # ── Health checks ────────────────────────────────────────────────
        logger.subsection("HEALTH CHECKS")
        app_ok = check_health(APP_URL)
        logger.log(f"    Main App ({APP_URL}):   {'🟢 OK' if app_ok else '🔴 DOWN'}")
        logger.log(f"    Mock API:  DISABLED (using real API)")

        if not app_ok:
            logger.log("\n    ❌ Cannot proceed — main app not running.")
            logger.log(f"    Ensure API is available at: {APP_URL}")

            fail_f.write("❌ Cannot proceed — main app not running.\n")
            fail_f.write(f"Main App OK: {app_ok}\n\n")
            fail_f.write("=" * 90 + "\n")
            fail_f.flush()

            logger.close()
            sys.exit(1)

        # ── Filter scenarios ─────────────────────────────────────────────
        scenarios_to_run = SCENARIOS

        if SCENARIO_FILTER != "all":
            ids = {s.strip() for s in SCENARIO_FILTER.split(",")}
            scenarios_to_run = [s for s in scenarios_to_run if s["id"] in ids]

        if CATEGORY_FILTER != "all":
            cats = {c.strip().upper() for c in CATEGORY_FILTER.split(",")}
            scenarios_to_run = [s for s in scenarios_to_run if s["category"] in cats]

        if not scenarios_to_run:
            logger.log("\n    ⚠️ No scenarios matched filters.")
            logger.log(f"    Available IDs: {[s['id'] for s in SCENARIOS]}")
            logger.log(f"    Available categories: {sorted(set(s['category'] for s in SCENARIOS))}")

            fail_f.write("⚠️ No scenarios matched filters.\n")
            fail_f.write(f"SCENARIOS filter: {SCENARIO_FILTER}\n")
            fail_f.write(f"CATEGORIES filter: {CATEGORY_FILTER}\n")
            fail_f.flush()

            logger.close()
            sys.exit(1)

        logger.log(f"\n    Running {len(scenarios_to_run)} scenarios...")
        logger.log(f"    IDs: {[s['id'] for s in scenarios_to_run]}")
        logger.log()

        # ── Run ──────────────────────────────────────────────────────────
        results = []
        total_start = time.time()

        for idx, sc in enumerate(scenarios_to_run, 1):
            res = run_scenario(logger, sc, idx, len(scenarios_to_run))
            results.append(res)

            # Write fail-only entry
            if not res["passed"]:
                fail_f.write(f"❌ {res['id']}: {res['title']}  (Category: {res['category']})\n")
                fail_f.write(
                    f"   Duration: {res.get('duration_s', '?')}s | Checks: {res.get('checks_passed', 0)}/{res.get('checks_total', 0)}\n"
                )

                if res.get("error"):
                    fail_f.write(f"   💥 Error: {res['error']}\n")

                failures = res.get("failures", [])
                if failures:
                    fail_f.write("   Failures:\n")
                    for f in failures:
                        fail_f.write(f"     - {f}\n")

                last_resp = ""
                if res.get("turns"):
                    last_resp = (res["turns"][-1].get("response", "") or "").strip()

                if last_resp:
                    snippet = last_resp.replace("\n", " ")[:300]
                    fail_f.write(f"   Last response: \"{snippet}{'…' if len(last_resp) > 300 else ''}\"\n")

                fail_f.write("\n" + ("-" * 90) + "\n\n")
                fail_f.flush()

        total_duration = round(time.time() - total_start, 2)

        # ═══════════════════════════════════════════════════════════════════
        # Summary Report
        # ═══════════════════════════════════════════════════════════════════

        logger.section("TEST SUMMARY", "═")

        completed = sum(1 for r in results if r["passed"])
        errored = sum(1 for r in results if r.get("error"))
        with_old_response = sum(1 for r in results if r.get("old_agent_response"))

        logger.log(f"  Scenarios:           {len(results)} total")
        logger.log(f"  Completed:           {completed} ✅")
        logger.log(f"  Errors:              {errored} 💥")
        logger.log(f"  With Old Response:   {with_old_response} (for comparison)")
        logger.log(f"  Total Duration:      {total_duration}s")
        logger.log(f"  Avg per scenario:    {round(total_duration/max(len(results),1),1)}s")
        logger.log()

        # ── Category breakdown ───────────────────────────────────────────
        categories: dict[str, dict] = {}
        for r in results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"passed": 0, "failed": 0, "total_time": 0}
            if r["passed"]:
                categories[cat]["passed"] += 1
            else:
                categories[cat]["failed"] += 1
            categories[cat]["total_time"] += r["duration_s"]

        logger.log("  By Category:")
        logger.log(f"    {'Category':20s} {'Done':>5s} {'Err':>5s} {'Total':>6s} {'Time':>8s}")
        logger.log(f"    {'─'*20} {'─'*5} {'─'*5} {'─'*6} {'─'*8}")
        for cat in sorted(categories.keys()):
            c = categories[cat]
            total_cat = c["passed"] + c["failed"]
            logger.log(f"    {cat:20s} {c['passed']:5d} {c['failed']:5d} {total_cat:6d} {c['total_time']:7.1f}s")
        logger.log()


        # ── Completion rate bar ──────────────────────────────────────────
        if results:
            bar_len = 40
            fill = round(completed / len(results) * bar_len)
            bar = "█" * fill + "░" * (bar_len - fill)
            pct = round(completed / len(results) * 100)
            logger.log(f"  Completion Rate: [{bar}] {pct}% ({completed}/{len(results)})")
            logger.log()

        # ── Error scenarios ──────────────────────────────────────────────
        if errored > 0:
            logger.subsection("ERROR SCENARIOS")
            for r in results:
                if r.get("error"):
                    logger.log(f"    💥 {r['id']}: {r['title']}")
                    logger.log(f"       Error: {r['error']}")
            logger.log()

        # ── Timing ───────────────────────────────────────────────────────
        logger.subsection("TIMING (slowest first)")
        for r in sorted(results, key=lambda x: -x["duration_s"]):
            status = "✅" if r["passed"] else "💥"
            has_old = "📜" if r.get("old_agent_response") else "  "
            logger.log(f"    {status} {has_old} {r['id']:20s} {r['duration_s']:6.1f}s")
        logger.log()

        # ── Multi-turn analysis ──────────────────────────────────────────
        multi_turn = [r for r in results if len(r.get("turns", [])) > 1]
        if multi_turn:
            logger.subsection("MULTI-TURN ANALYSIS")
            for r in multi_turn:
                logger.log(f"    {r['id']:20s}: {len(r['turns'])} turns {'✅' if r['passed'] else '❌'}")
                for t in r["turns"]:
                    intent = t.get("intent", "?")
                    agent = t.get("agent", "?")
                    shifted = " ↩️SHIFT" if t.get("intent_shifted") else ""
                    escalated = " 🚨ESC" if t.get("is_escalated") else ""
                    logger.log(
                        f"      Turn {t['turn']}: intent={intent} agent={agent}{shifted}{escalated} [{t.get('duration_s', '?')}s]"
                    )
            logger.log()

        # ── Write log footer summary ─────────────────────────────────────
        fail_f.write("\n" + "=" * 90 + "\n")
        fail_f.write("EXECUTION SUMMARY\n")
        fail_f.write(f"Total scenarios: {len(results)}\n")
        fail_f.write(f"Completed: {completed}\n")
        fail_f.write(f"Errors: {errored}\n")
        fail_f.write(f"With Old Response: {with_old_response}\n")
        fail_f.write(f"Main log: {LOG_FILE}\n")
        fail_f.write("=" * 90 + "\n")
        fail_f.flush()

        logger.section("END OF REPORT")
        logger.log(f"  Log saved to:      {LOG_FILE}")
        logger.log(f"  Fail log saved to: {FAIL_LOG_FILE}")
        logger.close()

        print(f"\n{'═' * 70}")
        print(f"  Results:  {completed}/{len(results)} scenarios completed ({round(completed/max(len(results),1)*100)}%)")
        print(f"  Errors:   {errored}")
        print(f"  Log:      {LOG_FILE}")
        print(f"{'═' * 70}")

        sys.exit(0 if errored == 0 else 1)

    finally:
        # Ensure files/client are closed even if sys.exit or exception occurs
        try:
            if fail_f and not fail_f.closed:
                fail_f.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
