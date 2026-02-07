"""
Tests for intent classification and routing.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from src.config import CONFIDENCE_THRESHOLD, INTENT_TO_AGENT
from src.patterns.intent_classifier import (
    classify_intent,
    route_by_confidence,
    route_after_shift_check,
)
from src.graph.graph_builder import (
    _route_after_input_guardrails,
    output_guardrails_final_node,
)


class TestRouteByConfidence:
    def test_high_confidence_routes_to_agent(self):
        state = {"ticket_category": "WISMO", "intent_confidence": 95}
        assert route_by_confidence(state) == "wismo_agent"

    def test_low_confidence_routes_to_supervisor(self):
        state = {"ticket_category": "WISMO", "intent_confidence": 60}
        assert route_by_confidence(state) == "supervisor"

    def test_threshold_boundary(self):
        state = {"ticket_category": "REFUND", "intent_confidence": 80}
        assert route_by_confidence(state) == "issue_agent"

    def test_below_threshold(self):
        state = {"ticket_category": "REFUND", "intent_confidence": 79}
        assert route_by_confidence(state) == "supervisor"

    def test_all_intents_map_correctly(self):
        for intent, agent in INTENT_TO_AGENT.items():
            state = {"ticket_category": intent, "intent_confidence": 95}
            assert route_by_confidence(state) == agent


class TestRouteAfterShiftCheck:
    def test_returns_current_agent(self):
        state = {"current_agent": "issue_agent"}
        assert route_after_shift_check(state) == "issue_agent"

    def test_default_supervisor(self):
        state = {}
        assert route_after_shift_check(state) == "supervisor"


class _MockMessage:
    def __init__(self, content: str, msg_type: str = "ai"):
        self.content = content
        self.type = msg_type


class TestGraphRouting:
    def test_chargeback_routes_to_auto_escalate(self):
        state = {
            "input_blocked": False,
            "flag_health_concern": False,
            "flag_chargeback_threat": True,
            "messages": [_MockMessage("Chargeback incoming", "human")],
        }
        assert _route_after_input_guardrails(state) == "auto_escalate_chargeback"

    def test_health_priority_over_chargeback(self):
        state = {
            "input_blocked": False,
            "flag_health_concern": True,
            "flag_chargeback_threat": True,
            "messages": [_MockMessage("Health + chargeback", "human")],
        }
        assert _route_after_input_guardrails(state) == "auto_escalate_health"

    def test_output_guardrails_final_does_not_force_pass(self):
        state = {"messages": [_MockMessage("Your order is guaranteed by tomorrow!")]}
        result = asyncio.run(output_guardrails_final_node(state))
        assert result["output_guardrail_passed"] is False
