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