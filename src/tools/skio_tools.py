"""
Skio (subscription platform) tool wrappers — 5 tools, spec-compliant.
"""

from __future__ import annotations

from langchain_core.tools import tool

from src.tools.api_client import api_call


@tool
def skio_get_subscription_status(email: str) -> dict:
    """Get subscription status by email."""
    return api_call("get-subscription-status", {"email": email})


@tool
def skio_cancel_subscription(
    subscriptionId: str,
    cancellationReasons: list[str],
) -> dict:
    """Cancel subscription. Requires subscriptionId and reasons list."""
    return api_call(
        "cancel-subscription",
        {
            "subscriptionId": subscriptionId,
            "cancellationReasons": cancellationReasons,
        },
    )


@tool
def skio_pause_subscription(subscriptionId: str, pausedUntil: str) -> dict:
    """Pause subscription until date. pausedUntil format: YYYY-MM-DD."""
    return api_call(
        "pause-subscription",
        {"subscriptionId": subscriptionId, "pausedUntil": pausedUntil},
    )


@tool
def skio_skip_next_order_subscription(subscriptionId: str) -> dict:
    """Skip next subscription order."""
    return api_call(
        "skip-next-order-subscription",
        {"subscriptionId": subscriptionId},
    )


@tool
def skio_unpause_subscription(subscriptionId: str) -> dict:
    """Unpause a paused subscription."""
    return api_call(
        "unpause-subscription",
        {"subscriptionId": subscriptionId},
    )