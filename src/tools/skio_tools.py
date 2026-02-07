"""
Skio (subscription platform) tool wrappers — 5 tools, spec-compliant.
"""

from __future__ import annotations

from langchain_core.tools import tool

from src.tools.api_client import api_call_async


@tool
async def skio_get_subscriptions(email: str) -> dict:
    """Gets the subscription status of a customer by email.
    Returns array of subscriptions with status (ACTIVE|PAUSED|CANCELLED), 
    subscriptionId, and nextBillingDate."""
    return await api_call_async("get-subscriptions", {"email": email})


@tool
async def skio_cancel_subscription(
    subscriptionId: str,
    cancellationReasons: list[str],
) -> dict:
    """Cancel subscription. Requires subscriptionId and reasons list."""
    return await api_call_async(
        "cancel-subscription",
        {
            "subscriptionId": subscriptionId,
            "cancellationReasons": cancellationReasons,
        },
    )


@tool
async def skio_pause_subscription(subscriptionId: str, pausedUntil: str) -> dict:
    """Pause subscription until date. pausedUntil format: YYYY-MM-DD."""
    return await api_call_async(
        "pause-subscription",
        {"subscriptionId": subscriptionId, "pausedUntil": pausedUntil},
    )


@tool
async def skio_skip_next_order_subscription(subscriptionId: str) -> dict:
    """Skip next subscription order."""
    return await api_call_async(
        "skip-next-order-subscription",
        {"subscriptionId": subscriptionId},
    )


@tool
async def skio_unpause_subscription(subscriptionId: str) -> dict:
    """Unpause a paused subscription."""
    return await api_call_async(
        "unpause-subscription",
        {"subscriptionId": subscriptionId},
    )