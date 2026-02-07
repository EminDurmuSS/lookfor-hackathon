# Agents package - ReAct agents and routing
"""
ReAct agent nodes for the multi-agent system.
- wismo_agent_node: WISMO (Where Is My Order) specialist
- issue_agent_node: Wrong/missing items, product issues, refunds
- account_agent_node: Cancellations, address, subscriptions, discounts
- supervisor_node: Fallback router for low-confidence classification
- supervisor_route: Routing function for supervisor decisions
- escalation_handler_node: Human escalation handler
- post_escalation_node: Post-escalation session lock

Note: handoff_router_node is in src.patterns.handoff
"""

from src.agents.react_agents import (
    wismo_agent_node,
    issue_agent_node,
    account_agent_node,
)
from src.agents.supervisor import (
    supervisor_node,
    supervisor_route,
)
from src.agents.escalation import (
    escalation_handler_node,
    post_escalation_node,
    EscalationPayload,
)

__all__ = [
    "wismo_agent_node",
    "issue_agent_node",
    "account_agent_node",
    "supervisor_node",
    "supervisor_route",
    "escalation_handler_node",
    "post_escalation_node",
    "EscalationPayload",
]

