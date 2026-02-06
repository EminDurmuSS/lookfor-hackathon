"""
Tests for cross-agent handoff and escalation mechanisms.
"""

import pytest
from unittest.mock import MagicMock

from src.patterns.handoff import handoff_router_node


class TestHandoffRouter:
    def test_valid_handoff(self):
        msg = MagicMock()
        msg.content = "HANDOFF: issue_agent | REASON: Customer wants refund"
        state = {"messages": [msg], "current_agent": "wismo_agent", "handoff_count_this_turn": 0}
        result = handoff_router_node(state)
        assert result["handoff_target"] == "issue_agent"
        assert result["handoff_count_this_turn"] == 1

    def test_loop_prevention(self):
        msg = MagicMock()
        msg.content = "HANDOFF: issue_agent | REASON: test"
        state = {"messages": [msg], "current_agent": "wismo_agent", "handoff_count_this_turn": 1}
        result = handoff_router_node(state)
        assert result["handoff_target"] == "supervisor"

    def test_invalid_target_falls_to_supervisor(self):
        msg = MagicMock()
        msg.content = "HANDOFF: unknown_agent | REASON: test"
        state = {"messages": [msg], "current_agent": "wismo_agent", "handoff_count_this_turn": 0}
        result = handoff_router_node(state)
        assert result["handoff_target"] == "supervisor"

    def test_not_handoff_message(self):
        msg = MagicMock()
        msg.content = "Hello, how can I help?"
        state = {"messages": [msg], "handoff_count_this_turn": 0}
        result = handoff_router_node(state)
        assert result["handoff_target"] == "supervisor"


class TestEscalationDetection:
    """Test that output guardrails correctly detect ESCALATE: format."""

    def test_escalation_detected_in_output(self):
        from src.patterns.guardrails import output_guardrails_node

        msg = MagicMock()
        msg.content = "ESCALATE: health_concern | REASON: Allergic reaction reported"
        state = {"messages": [msg]}
        result = output_guardrails_node(state)
        assert result.get("is_escalation") is True
        assert result["escalation_reason"] == "health_concern"