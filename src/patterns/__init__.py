# Patterns package - Guardrails, handoff, intent classification, reflection
"""
Agent patterns for the multi-agent system.
- Guardrails: Input/output validation, PII redaction, safety checks
- Handoff: Cross-agent routing
- Intent Classifier: 2-stage classification with confidence scoring
- Reflection: Quality validation and revision
"""

from src.patterns.guardrails import (
    input_guardrails_node,
    output_guardrails_node,
    tool_call_guardrails,
)
from src.patterns.handoff import handoff_router_node
from src.patterns.intent_classifier import (
    classify_intent,
    intent_classifier_node,
    intent_shift_check_node,
    route_by_confidence,
    route_after_shift_check,
)
from src.patterns.reflection import (
    reflection_validator_node,
    revise_response_node,
)

__all__ = [
    # Guardrails
    "input_guardrails_node",
    "output_guardrails_node",
    "tool_call_guardrails",
    # Handoff
    "handoff_router_node",
    # Intent Classification
    "classify_intent",
    "intent_classifier_node",
    "intent_shift_check_node",
    "route_by_confidence",
    "route_after_shift_check",
    # Reflection
    "reflection_validator_node",
    "revise_response_node",
]
