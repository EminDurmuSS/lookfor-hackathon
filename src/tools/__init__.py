# Tools package - Shopify and Skio API tools
"""
Tool implementations for agent actions.
- Shopify tools: Order lookup, cancellation, refunds, returns, store credit
- Skio tools: Subscription management
- Tool groups: Pre-configured tool sets for each agent
- API client: HTTP client with retry logic
"""

from src.tools.api_client import api_call

# Shopify lookup tools
from src.tools.shopify_tools import (
    shopify_get_order_details,
    shopify_get_customer_orders,
    shopify_get_product_details,
    shopify_get_product_recommendations,
    shopify_get_related_knowledge_source,
    shopify_get_collection_recommendations,
)

# Shopify action tools
from src.tools.shopify_tools import (
    shopify_cancel_order,
    shopify_refund_order,
    shopify_create_store_credit,
    shopify_add_tags,
    shopify_create_discount_code,
    shopify_update_order_shipping_address,
    shopify_create_return,
)

# Skio subscription tools
from src.tools.skio_tools import (
    skio_get_subscriptions,
    skio_cancel_subscription,
    skio_pause_subscription,
    skio_skip_next_order_subscription,
    skio_unpause_subscription,
)

# Pre-configured tool groups
from src.tools.tool_groups import (
    wismo_tools,
    issue_tools,
    account_tools,
)

__all__ = [
    # API
    "api_call",
    # Shopify lookup
    "shopify_get_order_details",
    "shopify_get_customer_orders",
    "shopify_get_product_details",
    "shopify_get_product_recommendations",
    "shopify_get_related_knowledge_source",
    "shopify_get_collection_recommendations",
    # Shopify actions
    "shopify_cancel_order",
    "shopify_refund_order",
    "shopify_create_store_credit",
    "shopify_add_tags",
    "shopify_create_discount_code",
    "shopify_update_order_shipping_address",
    "shopify_create_return",
    # Skio
    "skio_get_subscriptions",
    "skio_cancel_subscription",
    "skio_pause_subscription",
    "skio_skip_next_order_subscription",
    "skio_unpause_subscription",
    # Tool groups
    "wismo_tools",
    "issue_tools",
    "account_tools",
]
