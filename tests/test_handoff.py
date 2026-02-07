"""
Tests for cross-agent handoff and escalation mechanisms.
"""

import pytest
from unittest.mock import MagicMock

from src.patterns.handoff import handoff_router_node
from src.agents.react_agents import _strip_internal_markers


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


class TestInternalMarkerStripping:
    def test_handoff_line_preserved(self):
        text = (
            "Thought: I should route this\n"
            "Action: handoff\n"
            "HANDOFF: issue_agent | REASON: Refund requested"
        )
        cleaned = _strip_internal_markers(text)
        assert cleaned == "HANDOFF: issue_agent | REASON: Refund requested"

    def test_escalate_line_preserved(self):
        text = (
            "Observation: potential risk\n"
            "ESCALATE: chargeback_risk | REASON: Customer threatened chargeback\n"
            "Caz"
        )
        cleaned = _strip_internal_markers(text)
        assert cleaned.startswith("ESCALATE: chargeback_risk")
