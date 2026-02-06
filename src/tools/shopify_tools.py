"""
Shopify tool wrappers — 14 tools, spec-compliant parameter schemas.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from src.tools.api_client import api_call


# ─── LOOKUP TOOLS ────────────────────────────────────────────────────────────

@tool
def shopify_get_order_details(orderId: str) -> dict:
    """Fetch detailed information for a single order.
    orderId must start with '#', e.g. '#1234'.
    Returns: order id (GID), name, status, tracking info, line items."""
    if not orderId.startswith("#"):
        orderId = f"#{orderId}"
    return api_call("get_order_details", {"orderId": orderId})


@tool
def shopify_get_customer_orders(
    email: str,
    after: str = "null",
    limit: int = 10,
) -> dict:
    """Get customer orders by email. Returns list of orders with GIDs.
    Use after='null' for first page. Max limit 250."""
    return api_call(
        "get_customer_orders",
        {"email": email, "after": after, "limit": limit},
    )


@tool
def shopify_get_product_details(queryType: str, queryKey: str) -> dict:
    """Get product info. queryType: 'id'|'name'|'key feature'.
    queryKey: product GID if id, or search term."""
    return api_call(
        "get_product_details",
        {"queryType": queryType, "queryKey": queryKey},
    )


@tool
def shopify_get_product_recommendations(queryKeys: list[str]) -> dict:
    """Get product recommendations. queryKeys: keywords like ['sleep', 'kids']."""
    return api_call("get_product_recommendations", {"queryKeys": queryKeys})


@tool
def shopify_get_related_knowledge_source(
    question: str,
    specificToProductId: Optional[str] = None,
) -> dict:
    """Get FAQs, articles, guides. question: customer's issue.
    specificToProductId: product GID or null if not product-specific."""
    return api_call(
        "get_related_knowledge_source",
        {
            "question": question,
            "specificToProductId": specificToProductId,
        },
    )


@tool
def shopify_get_collection_recommendations(queryKeys: list[str]) -> dict:
    """Get collection recommendations by keywords."""
    return api_call("get_collection_recommendations", {"queryKeys": queryKeys})


# ─── ACTION TOOLS (require GID) ─────────────────────────────────────────────

@tool
def shopify_cancel_order(
    orderId: str,
    reason: str,
    notifyCustomer: bool,
    restock: bool,
    staffNote: str,
    refundMode: str,
    storeCredit: dict,
) -> dict:
    """Cancel an order. orderId must be Shopify GID (gid://shopify/Order/...).
    reason: CUSTOMER|DECLINED|FRAUD|INVENTORY|OTHER|STAFF
    refundMode: ORIGINAL|STORE_CREDIT
    storeCredit: {"expiresAt": null} or {"expiresAt": "ISO8601"}"""
    return api_call(
        "cancel_order",
        {
            "orderId": orderId,
            "reason": reason,
            "notifyCustomer": notifyCustomer,
            "restock": restock,
            "staffNote": staffNote,
            "refundMode": refundMode,
            "storeCredit": storeCredit,
        },
    )


@tool
def shopify_refund_order(orderId: str, refundMethod: str) -> dict:
    """Refund an order. orderId must be Shopify GID.
    refundMethod: ORIGINAL_PAYMENT_METHODS or STORE_CREDIT"""
    return api_call(
        "refund_order",
        {"orderId": orderId, "refundMethod": refundMethod},
    )


@tool
def shopify_create_store_credit(
    id: str,
    creditAmount: dict,
    expiresAt: Optional[str] = None,
) -> dict:
    """Issue store credit to customer. id must be Customer GID.
    creditAmount: {"amount": "49.99", "currencyCode": "USD"}
    expiresAt: null for no expiry or ISO8601 string."""
    return api_call(
        "create_store_credit",
        {"id": id, "creditAmount": creditAmount, "expiresAt": expiresAt},
    )


@tool
def shopify_add_tags(id: str, tags: list[str]) -> dict:
    """Add tags to a Shopify resource. id must be Shopify GID."""
    return api_call("add_tags", {"id": id, "tags": tags})


@tool
def shopify_create_discount_code(
    type: str,
    value: float,
    duration: int,
    productIds: list[str] | None = None,
) -> dict:
    """Create discount code. type: 'percentage' (0-1) or 'fixed'.
    value: 0.10 for 10%. duration: hours (48). productIds: [] for order-wide."""
    return api_call(
        "create_discount_code",
        {
            "type": type,
            "value": value,
            "duration": duration,
            "productIds": productIds or [],
        },
    )


@tool
def shopify_update_order_shipping_address(
    orderId: str,
    shippingAddress: dict,
) -> dict:
    """Update shipping address. orderId must be Shopify GID.
    shippingAddress needs: firstName, lastName, company, address1, address2,
    city, provinceCode, country, zip, phone."""
    return api_call(
        "update_order_shipping_address",
        {"orderId": orderId, "shippingAddress": shippingAddress},
    )


@tool
def shopify_create_return(orderId: str) -> dict:
    """Create a return. orderId must be Shopify GID."""
    return api_call("create_return", {"orderId": orderId})


@tool
def shopify_create_draft_order() -> dict:
    """Create a draft order."""
    return api_call("create_draft_order", {})