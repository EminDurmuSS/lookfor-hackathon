"""
Tool groupings — each agent only sees the tools it needs.
"""

from src.tools.shopify_tools import (
    shopify_add_tags,
    shopify_cancel_order,
    shopify_create_discount_code,
    shopify_create_draft_order,
    shopify_create_return,
    shopify_create_store_credit,
    shopify_get_collection_recommendations,
    shopify_get_customer_orders,
    shopify_get_order_details,
    shopify_get_product_details,
    shopify_get_product_recommendations,
    shopify_get_related_knowledge_source,
    shopify_refund_order,
    shopify_update_order_shipping_address,
)
from src.tools.skio_tools import (
    skio_cancel_subscription,
    skio_get_subscription_status,
    skio_pause_subscription,
    skio_skip_next_order_subscription,
    skio_unpause_subscription,
)

wismo_tools = [
    shopify_get_customer_orders,
    shopify_get_order_details,
    shopify_add_tags,
    shopify_create_draft_order,  # reship escalation prep
]

issue_tools = [
    shopify_get_order_details,
    shopify_get_customer_orders,
    shopify_refund_order,
    shopify_create_store_credit,
    shopify_create_return,
    shopify_add_tags,
    shopify_get_product_recommendations,
    shopify_get_collection_recommendations,
    shopify_get_product_details,
    shopify_get_related_knowledge_source,
    shopify_create_draft_order,  # reship escalation prep
]

account_tools = [
    shopify_get_order_details,
    shopify_get_customer_orders,
    shopify_cancel_order,
    shopify_update_order_shipping_address,
    shopify_add_tags,
    shopify_create_discount_code,
    shopify_get_product_recommendations,
    skio_get_subscription_status,
    skio_cancel_subscription,
    skio_pause_subscription,
    skio_skip_next_order_subscription,
    skio_unpause_subscription,
]
