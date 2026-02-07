"""
Tests for escalation payload shaping and id extraction.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import src.agents.escalation as escalation_module


class _StubLLM:
    async def ainvoke(self, _prompt):
        return SimpleNamespace(content="Escalation summary")


def _msg(content: str):
    msg = MagicMock()
    msg.content = content
    return msg


def test_escalation_resolves_ids_and_uses_draft_order_id(monkeypatch):
    monkeypatch.setattr(escalation_module, "sonnet_llm", _StubLLM())

    state = {
        "customer_first_name": "Sarah",
        "customer_last_name": "Jones",
        "customer_email": "sarah@example.com",
        "escalation_reason": "chargeback_risk",
        "messages": [_msg("Customer said chargeback is next.")],
        "actions_taken": ["shopify_refund_order: failed"],
        "tool_calls_log": [
            {
                "tool_name": "shopify_get_order_details",
                "params": {"orderId": "#43189"},
                "result": {
                    "success": True,
                    "data": {"id": "gid://shopify/Order/5531567751245", "name": "#43189"},
                },
            },
            {
                "tool_name": "skio_get_subscription_status",
                "params": {"subscriptionId": "sub_123"},
                "result": {
                    "success": True,
                    "data": {
                        "status": "ACTIVE",
                        "subscriptionId": "sub_123",
                        "nextBillingDate": "2026-03-01",
                    },
                },
            },
            {
                "tool_name": "shopify_create_draft_order",
                "params": {},
                "result": {
                    "success": True,
                    "data": {"draftOrderId": "gid://shopify/DraftOrder/999"},
                },
            },
        ],
    }

    result = asyncio.run(escalation_module.escalation_handler_node(state))
    payload = result["escalation_payload"]

    assert payload["order_id"] == "gid://shopify/Order/5531567751245"
    assert payload["subscription_id"] == "sub_123"
    assert "gid://shopify/DraftOrder/999" in payload["summary"]
    assert result["current_order_id"] == "gid://shopify/Order/5531567751245"
    assert result["current_subscription_id"] == "sub_123"


def test_escalation_draft_order_id_falls_back_to_legacy_id(monkeypatch):
    monkeypatch.setattr(escalation_module, "sonnet_llm", _StubLLM())

    state = {
        "customer_first_name": "Ava",
        "customer_last_name": "Lee",
        "customer_email": "ava@example.com",
        "escalation_reason": "uncertain",
        "messages": [_msg("Need a human agent please.")],
        "tool_calls_log": [
            {
                "tool_name": "shopify_create_draft_order",
                "params": {},
                "result": {
                    "success": True,
                    "data": {"id": "legacy-draft-123"},
                },
            },
        ],
    }

    result = asyncio.run(escalation_module.escalation_handler_node(state))
    payload = result["escalation_payload"]

    assert "legacy-draft-123" in payload["summary"]


def test_escalation_backfills_intent_agent_fields(monkeypatch):
    monkeypatch.setattr(escalation_module, "sonnet_llm", _StubLLM())

    state = {
        "customer_first_name": "Sam",
        "customer_last_name": "Diaz",
        "customer_email": "sam@example.com",
        "escalation_reason": "chargeback_risk",
        "messages": [_msg("I will dispute the charge.")],
    }

    result = asyncio.run(escalation_module.escalation_handler_node(state))
    assert result["ticket_category"] == "REFUND"
    assert result["current_agent"] == "issue_agent"
    assert result["intent_confidence"] == 100


def test_health_escalation_message_includes_stop_using(monkeypatch):
    monkeypatch.setattr(escalation_module, "sonnet_llm", _StubLLM())

    state = {
        "customer_first_name": "Sarah",
        "customer_last_name": "Jones",
        "customer_email": "sarah@example.com",
        "escalation_reason": "health_concern",
        "messages": [_msg("My child has hives and trouble breathing.")],
    }

    result = asyncio.run(escalation_module.escalation_handler_node(state))
    msg = result["messages"][0].content.lower()
    assert "stop using" in msg
    assert "health" in msg
    assert "monica" in msg
