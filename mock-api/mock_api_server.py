# """
# NatPat Hackathon — Comprehensive Mock API Server
# =================================================
# Designed to be *forgiving* and *fully compatible* with a 95-scenario test suite +
# Tooling Spec expectations.

# ✅ Simulates ALL 19 Shopify + Skio tool endpoints
# ✅ Realistic, interconnected fake data (orders, products, customers, subscriptions)
# ✅ Order numbers explicitly present: #43189, #43200, #43215, #51234 (+ cancelled #43190)
# ✅ Stateful mutations: cancel, refund, tag, address update, store credit, subscription lifecycle
# ✅ Cursor-based pagination for get_customer_orders
# ✅ Accepts extra/unknown params without failing (spec-safe)
# ✅ Multiple PATH ALIASES supported (to avoid “hackhaton/hackathon” + naming mismatches)

# Run:
#   uvicorn mock_api_server:app --host 0.0.0.0 --port 8080 --reload
# """

# from __future__ import annotations

# import asyncio
# import copy
# import os
# import random
# import re
# import string
# import uuid
# from datetime import datetime, timedelta, timezone
# from typing import Any, Optional, Callable

# from fastapi import FastAPI, Request
# from fastapi.middleware.cors import CORSMiddleware


# # =============================================================================
# # App
# # =============================================================================

# app = FastAPI(title="NatPat Mock Tooling API", version="2.2")
# app.add_middleware(
#     CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
# )


# # =============================================================================
# # Deterministic "now" (important for test suites)
# # =============================================================================
# # If env MOCK_NOW is set, it must be ISO-8601 like:
# #   2026-02-06T12:00:00Z
# # Otherwise defaults to a stable date (matches typical hackathon test framing).

# def _parse_mock_now(s: str) -> datetime:
#     s = s.strip()
#     if s.endswith("Z"):
#         s = s[:-1] + "+00:00"
#     return datetime.fromisoformat(s).astimezone(timezone.utc)

# _DEFAULT_NOW = datetime(2026, 2, 6, 12, 0, 0, tzinfo=timezone.utc)
# _NOW = _parse_mock_now(os.environ["MOCK_NOW"]) if os.environ.get("MOCK_NOW") else _DEFAULT_NOW

# def _iso(dt: datetime) -> str:
#     return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

# _today_str = _iso(_NOW)
# _today_morning = _iso(_NOW.replace(hour=8, minute=0, second=0, microsecond=0))
# _yesterday = _iso(_NOW - timedelta(days=1))
# _yesterday_morning = _iso((_NOW - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0))
# _3_days_ago = _iso(_NOW - timedelta(days=3))
# _7_days_ago = _iso(_NOW - timedelta(days=7))
# _10_days_ago = _iso(_NOW - timedelta(days=10))
# _14_days_ago = _iso(_NOW - timedelta(days=14))
# _today_date = _NOW.strftime("%Y-%m-%d")


# # =============================================================================
# # Products
# # =============================================================================

# PRODUCTS: dict[str, dict] = {
#     "gid://shopify/Product/8001": {
#         "id": "gid://shopify/Product/8001",
#         "title": "SleepyPatch — Sleep Promoting Stickers for Kids",
#         "handle": "sleepypatch",
#         "description": (
#             "Natural sleep stickers infused with lavender and mandarin essential oils. "
#             "Apply 30 minutes before bedtime on pajamas or pillow."
#         ),
#         "price": "29.99",
#         "currency": "USD",
#         "tags": ["sleep", "kids", "essential oils", "lavender", "bedtime"],
#         "usage_guide": (
#             "Apply 1-2 patches on pajamas or pillow 30 minutes before bedtime. "
#             "For best results, use consistently for 5-7 nights. Keep patches away from "
#             "face and mouth. Each patch lasts 8-12 hours."
#         ),
#         "variants": [
#             {"id": "gid://shopify/ProductVariant/8001A", "title": "24-Pack", "price": "29.99"},
#             {"id": "gid://shopify/ProductVariant/8001B", "title": "60-Pack", "price": "59.99"},
#         ],
#     },
#     "gid://shopify/Product/8002": {
#         "id": "gid://shopify/Product/8002",
#         "title": "BuzzPatch — Mosquito Repellent Stickers",
#         "handle": "buzzpatch",
#         "description": "Citronella and eucalyptus stickers that keep mosquitoes away naturally. Safe for kids 2+.",
#         "price": "24.99",
#         "currency": "USD",
#         "tags": ["mosquito", "bug repellent", "outdoor", "kids", "citronella"],
#         "usage_guide": (
#             "Apply 1-2 patches on clothing (not skin) before going outdoors. "
#             "Reapply every 6-8 hours. For heavy mosquito areas, use 3-4 patches "
#             "spread across clothing."
#         ),
#         "variants": [
#             {"id": "gid://shopify/ProductVariant/8002A", "title": "24-Pack", "price": "24.99"},
#             {"id": "gid://shopify/ProductVariant/8002B", "title": "60-Pack", "price": "49.99"},
#         ],
#     },
#     "gid://shopify/Product/8003": {
#         "id": "gid://shopify/Product/8003",
#         "title": "FocusPatch — Concentration Stickers for Kids",
#         "handle": "focuspatch",
#         "description": "Essential oil stickers with peppermint and rosemary to help kids focus during school or homework.",
#         "price": "27.99",
#         "currency": "USD",
#         "tags": ["focus", "concentration", "school", "kids", "peppermint"],
#         "usage_guide": (
#             "Apply 1 patch on clothing near the collar area 15 minutes before focus is needed. "
#             "Each patch lasts 6-8 hours. Best used during homework, tests, or activities "
#             "requiring concentration. Use consistently for 5-7 days for best results."
#         ),
#         "variants": [
#             {"id": "gid://shopify/ProductVariant/8003A", "title": "24-Pack", "price": "27.99"},
#         ],
#     },
#     "gid://shopify/Product/8004": {
#         "id": "gid://shopify/Product/8004",
#         "title": "ZenPatch — Calm & Mood Stickers",
#         "handle": "zenpatch",
#         "description": "Calming essential oil stickers with chamomile and sweet orange. Great for anxious moments.",
#         "price": "29.99",
#         "currency": "USD",
#         "tags": ["calm", "mood", "anxiety", "kids", "chamomile", "zen"],
#         "usage_guide": (
#             "Apply 1-2 patches on clothing when feeling anxious or before stressful situations. "
#             "Can be used alongside SleepyPatch at bedtime for enhanced calm. Each patch lasts 6-8 hours."
#         ),
#         "variants": [
#             {"id": "gid://shopify/ProductVariant/8004A", "title": "24-Pack", "price": "29.99"},
#         ],
#     },
#     "gid://shopify/Product/8005": {
#         "id": "gid://shopify/Product/8005",
#         "title": "MagicPatch — Itch Relief Patches",
#         "handle": "magicpatch",
#         "description": "Chemical-free itch relief patches for bug bites. Uses grid-relief technology to drain the itch.",
#         "price": "14.99",
#         "currency": "USD",
#         "tags": ["itch relief", "bug bites", "kids", "chemical-free"],
#         "usage_guide": (
#             "Apply directly over the bug bite. The microlift technology helps drain the "
#             "biochemicals that cause itching. Leave on for 2-8 hours. Works best when "
#             "applied immediately after bite."
#         ),
#         "variants": [
#             {"id": "gid://shopify/ProductVariant/8005A", "title": "27-Pack", "price": "14.99"},
#             {"id": "gid://shopify/ProductVariant/8005B", "title": "60-Pack", "price": "24.99"},
#         ],
#     },
#     "gid://shopify/Product/8006": {
#         "id": "gid://shopify/Product/8006",
#         "title": "NatPat Family Bundle — Sleep + Buzz + Focus",
#         "handle": "family-bundle",
#         "description": "Our best-selling bundle with SleepyPatch, BuzzPatch, and FocusPatch. Save 20%!",
#         "price": "65.99",
#         "currency": "USD",
#         "tags": ["bundle", "sleep", "mosquito", "focus", "value"],
#         "usage_guide": "See individual product instructions for each patch type.",
#         "variants": [
#             {"id": "gid://shopify/ProductVariant/8006A", "title": "Bundle (24-Pack each)", "price": "65.99"},
#         ],
#     },
# }

# COLLECTIONS = [
#     {"id": "gid://shopify/Collection/1001", "title": "Sleep Solutions", "handle": "sleep-solutions"},
#     {"id": "gid://shopify/Collection/1002", "title": "Bug Protection", "handle": "bug-protection"},
#     {"id": "gid://shopify/Collection/1003", "title": "Focus & Learning", "handle": "focus-learning"},
#     {"id": "gid://shopify/Collection/1004", "title": "Calm & Wellness", "handle": "calm-wellness"},
#     {"id": "gid://shopify/Collection/1005", "title": "Best Sellers", "handle": "best-sellers"},
#     {"id": "gid://shopify/Collection/1006", "title": "Value Bundles", "handle": "value-bundles"},
# ]

# KNOWLEDGE_BASE = {
#     "sleep": {
#         "faqs": [
#             {"question": "How many SleepyPatch should I use?",
#              "answer": "We recommend 1-2 patches per night, placed on pajamas or pillow about 30 minutes before bedtime."},
#             {"question": "How long does it take to work?",
#              "answer": "Most kids notice a difference within the first 3-5 nights of consistent use. Give it at least a week for full effect."},
#             {"question": "Can I use SleepyPatch on skin?",
#              "answer": "SleepyPatch should be placed on clothing or pillow, not directly on skin."},
#         ],
#         "pdfs": [],
#         "blogArticles": [
#             {"title": "5 Tips for Better Kids' Sleep with SleepyPatch", "url": "https://natpat.com/blog/sleep-tips"},
#             {"title": "Essential Oils and Sleep: The Science", "url": "https://natpat.com/blog/essential-oils-sleep"},
#         ],
#         "pages": [{"title": "SleepyPatch Usage Guide", "url": "https://natpat.com/pages/sleepypatch-guide"}],
#     },
#     "focus": {
#         "faqs": [
#             {"question": "When should I apply FocusPatch?",
#              "answer": "Apply 15 minutes before focus is needed — before homework, tests, or activities."},
#             {"question": "How many patches at once?",
#              "answer": "One patch is usually enough. Place near the collar for best effect."},
#             {"question": "How long do FocusPatch last?",
#              "answer": "Each FocusPatch lasts 6-8 hours. Use consistently for 5-7 days for best results."},
#         ],
#         "pdfs": [],
#         "blogArticles": [{"title": "Helping Kids Focus Naturally", "url": "https://natpat.com/blog/kids-focus"}],
#         "pages": [],
#     },
#     "mosquito": {
#         "faqs": [
#             {"question": "How many BuzzPatch do I need?",
#              "answer": "Use 1-2 patches for mild exposure. For heavy mosquito areas, use 3-4 patches spread across clothing."},
#             {"question": "Does BuzzPatch work on ticks?",
#              "answer": "BuzzPatch is primarily designed for mosquitoes. For tick protection, consult your pediatrician about additional measures."},
#         ],
#         "pdfs": [],
#         "blogArticles": [{"title": "Natural Bug Protection for Summer", "url": "https://natpat.com/blog/summer-protection"}],
#         "pages": [],
#     },
#     "itch": {
#         "faqs": [
#             {"question": "How does MagicPatch work?",
#              "answer": "MagicPatch uses microlift technology to drain the biochemicals that cause itching from bug bites."},
#             {"question": "How soon should I apply MagicPatch?",
#              "answer": "Apply immediately after a bug bite for best results. The patch works for 2-8 hours."},
#         ],
#         "pdfs": [],
#         "blogArticles": [],
#         "pages": [],
#     },
#     "general": {
#         "faqs": [
#             {"question": "Are NatPat patches safe for kids?",
#              "answer": "Yes! Our patches are designed to be placed on clothing (not skin) and are safe for kids 2+."},
#             {"question": "What's your return policy?",
#              "answer": "We offer store credit with a 10% bonus, or a cash refund as a last resort (case-by-case)."},
#             {"question": "How long do patches last?",
#              "answer": "Most patches are effective for 6-12 hours depending on the product."},
#         ],
#         "pdfs": [],
#         "blogArticles": [],
#         "pages": [{"title": "FAQ", "url": "https://natpat.com/pages/faq"},
#                   {"title": "Shipping Policy", "url": "https://natpat.com/pages/shipping"}],
#     },
# }


# # =============================================================================
# # Customers
# # =============================================================================

# CUSTOMERS: dict[str, dict] = {
#     "gid://shopify/Customer/7424155189325": {
#         "id": "gid://shopify/Customer/7424155189325",
#         "email": "sarah@example.com",
#         "firstName": "Sarah",
#         "lastName": "Jones",
#         "storeCreditBalance": {"amount": "0.00", "currencyCode": "USD"},
#         "tags": [],
#     },
#     "gid://shopify/Customer/7424155189326": {
#         "id": "gid://shopify/Customer/7424155189326",
#         "email": "mike@example.com",
#         "firstName": "Mike",
#         "lastName": "Chen",
#         "storeCreditBalance": {"amount": "15.00", "currencyCode": "USD"},
#         "tags": [],
#     },
#     "gid://shopify/Customer/7424155189327": {
#         "id": "gid://shopify/Customer/7424155189327",
#         "email": "emma@example.com",
#         "firstName": "Emma",
#         "lastName": "Wilson",
#         "storeCreditBalance": {"amount": "0.00", "currencyCode": "USD"},
#         "tags": [],
#     },
#     "gid://shopify/Customer/7424155189328": {
#         "id": "gid://shopify/Customer/7424155189328",
#         "email": "test@example.com",
#         "firstName": "Test",
#         "lastName": "User",
#         "storeCreditBalance": {"amount": "0.00", "currencyCode": "USD"},
#         "tags": [],
#     },
# }

# EMAIL_TO_CUSTOMER: dict[str, str] = {c["email"].lower(): cid for cid, c in CUSTOMERS.items()}


# # =============================================================================
# # Orders (seed)
# # =============================================================================

# _SARAH_ADDRESS = {
#     "firstName": "Sarah", "lastName": "Jones", "company": "",
#     "address1": "123 Oak Street", "address2": "Apt 4B",
#     "city": "Austin", "provinceCode": "TX", "country": "US",
#     "zip": "78701", "phone": "+15125551234",
# }
# _MIKE_ADDRESS = {
#     "firstName": "Mike", "lastName": "Chen", "company": "",
#     "address1": "456 Pine Avenue", "address2": "",
#     "city": "San Francisco", "provinceCode": "CA", "country": "US",
#     "zip": "94102", "phone": "+14155559876",
# }
# _EMMA_ADDRESS = {
#     "firstName": "Emma", "lastName": "Wilson", "company": "",
#     "address1": "789 Elm Boulevard", "address2": "Suite 100",
#     "city": "Portland", "provinceCode": "OR", "country": "US",
#     "zip": "97201", "phone": "+15035557890",
# }

# _INITIAL_ORDERS: list[dict] = [
#     # Sarah main test orders (explicitly referenced by many scenarios)
#     {
#         "id": "gid://shopify/Order/5531567751245",
#         "name": "#43189",
#         "email": "sarah@example.com",
#         "customerId": "gid://shopify/Customer/7424155189325",
#         "createdAt": _10_days_ago,
#         "status": "FULFILLED",
#         "fulfillmentStatus": "FULFILLED",
#         "financialStatus": "PAID",
#         "trackingUrl": "https://tracking.example.com/NATPAT2026ABC",
#         "trackingNumber": "NATPAT2026ABC",
#         "totalPrice": "54.98",
#         "currency": "USD",
#         "tags": [],
#         "shippingAddress": copy.deepcopy(_SARAH_ADDRESS),
#         "lineItems": [
#             {"title": "SleepyPatch — 24-Pack", "quantity": 1, "price": "29.99",
#              "productId": "gid://shopify/Product/8001", "variantId": "gid://shopify/ProductVariant/8001A"},
#             {"title": "BuzzPatch — 24-Pack", "quantity": 1, "price": "24.99",
#              "productId": "gid://shopify/Product/8002", "variantId": "gid://shopify/ProductVariant/8002A"},
#         ],
#         "refunded": False,
#         "cancelledAt": None,
#         "refundedAt": None,
#     },
#     {
#         "id": "gid://shopify/Order/5531567751246",
#         "name": "#43200",
#         "email": "sarah@example.com",
#         "customerId": "gid://shopify/Customer/7424155189325",
#         "createdAt": _today_morning,
#         "status": "UNFULFILLED",
#         "fulfillmentStatus": "UNFULFILLED",
#         "financialStatus": "PAID",
#         "trackingUrl": None,
#         "trackingNumber": None,
#         "totalPrice": "24.99",
#         "currency": "USD",
#         "tags": [],
#         "shippingAddress": copy.deepcopy(_SARAH_ADDRESS),
#         "lineItems": [
#             {"title": "BuzzPatch — 24-Pack", "quantity": 1, "price": "24.99",
#              "productId": "gid://shopify/Product/8002", "variantId": "gid://shopify/ProductVariant/8002A"},
#         ],
#         "refunded": False,
#         "cancelledAt": None,
#         "refundedAt": None,
#     },
#     {
#         "id": "gid://shopify/Order/5531567751247",
#         "name": "#43215",
#         "email": "sarah@example.com",
#         "customerId": "gid://shopify/Customer/7424155189325",
#         "createdAt": _3_days_ago,
#         "status": "FULFILLED",
#         "fulfillmentStatus": "FULFILLED",
#         "financialStatus": "PAID",
#         "trackingUrl": "https://tracking.example.com/NATPAT2026DEF",
#         "trackingNumber": "NATPAT2026DEF",
#         "totalPrice": "27.99",
#         "currency": "USD",
#         "tags": [],
#         "shippingAddress": copy.deepcopy(_SARAH_ADDRESS),
#         "lineItems": [
#             {"title": "FocusPatch — 24-Pack", "quantity": 1, "price": "27.99",
#              "productId": "gid://shopify/Product/8003", "variantId": "gid://shopify/ProductVariant/8003A"},
#         ],
#         "refunded": False,
#         "cancelledAt": None,
#         "refundedAt": None,
#     },
#     {
#         "id": "gid://shopify/Order/5531567751248",
#         "name": "#51234",
#         "email": "sarah@example.com",
#         "customerId": "gid://shopify/Customer/7424155189325",
#         "createdAt": _14_days_ago,
#         "status": "DELIVERED",
#         "fulfillmentStatus": "FULFILLED",
#         "financialStatus": "PAID",
#         "trackingUrl": "https://tracking.example.com/NATPAT2026GHI",
#         "trackingNumber": "NATPAT2026GHI",
#         "totalPrice": "65.99",
#         "currency": "USD",
#         "tags": [],
#         "shippingAddress": copy.deepcopy(_SARAH_ADDRESS),
#         "lineItems": [
#             {"title": "NatPat Family Bundle — Sleep + Buzz + Focus", "quantity": 1, "price": "65.99",
#              "productId": "gid://shopify/Product/8006", "variantId": "gid://shopify/ProductVariant/8006A"},
#         ],
#         "refunded": False,
#         "cancelledAt": None,
#         "refundedAt": None,
#     },
#     # Sarah cancelled order (useful for "already cancelled" / "already refunded" edge cases)
#     {
#         "id": "gid://shopify/Order/5531567751249",
#         "name": "#43190",
#         "email": "sarah@example.com",
#         "customerId": "gid://shopify/Customer/7424155189325",
#         "createdAt": _14_days_ago,
#         "status": "CANCELLED",
#         "fulfillmentStatus": "UNFULFILLED",
#         "financialStatus": "REFUNDED",
#         "trackingUrl": None,
#         "trackingNumber": None,
#         "totalPrice": "14.99",
#         "currency": "USD",
#         "tags": ["Cancelled - Customer Request"],
#         "shippingAddress": copy.deepcopy(_SARAH_ADDRESS),
#         "lineItems": [
#             {"title": "MagicPatch — 27-Pack", "quantity": 1, "price": "14.99",
#              "productId": "gid://shopify/Product/8005", "variantId": "gid://shopify/ProductVariant/8005A"},
#         ],
#         "refunded": True,
#         "cancelledAt": _iso(_NOW - timedelta(days=13)),
#         "refundedAt": _iso(_NOW - timedelta(days=13)),
#     },

#     # Mike orders (includes partially fulfilled edge)
#     {
#         "id": "gid://shopify/Order/5531567752001",
#         "name": "#44001",
#         "email": "mike@example.com",
#         "customerId": "gid://shopify/Customer/7424155189326",
#         "createdAt": _7_days_ago,
#         "status": "FULFILLED",
#         "fulfillmentStatus": "FULFILLED",
#         "financialStatus": "PAID",
#         "trackingUrl": "https://tracking.example.com/NATPAT2026JKL",
#         "trackingNumber": "NATPAT2026JKL",
#         "totalPrice": "29.99",
#         "currency": "USD",
#         "tags": [],
#         "shippingAddress": copy.deepcopy(_MIKE_ADDRESS),
#         "lineItems": [
#             {"title": "SleepyPatch — 24-Pack", "quantity": 1, "price": "29.99",
#              "productId": "gid://shopify/Product/8001", "variantId": "gid://shopify/ProductVariant/8001A"},
#         ],
#         "refunded": False,
#         "cancelledAt": None,
#         "refundedAt": None,
#     },
#     {
#         "id": "gid://shopify/Order/5531567752002",
#         "name": "#44002",
#         "email": "mike@example.com",
#         "customerId": "gid://shopify/Customer/7424155189326",
#         "createdAt": _yesterday,
#         "status": "UNFULFILLED",
#         "fulfillmentStatus": "UNFULFILLED",
#         "financialStatus": "PAID",
#         "trackingUrl": None,
#         "trackingNumber": None,
#         "totalPrice": "27.99",
#         "currency": "USD",
#         "tags": [],
#         "shippingAddress": copy.deepcopy(_MIKE_ADDRESS),
#         "lineItems": [
#             {"title": "FocusPatch — 24-Pack", "quantity": 1, "price": "27.99",
#              "productId": "gid://shopify/Product/8003", "variantId": "gid://shopify/ProductVariant/8003A"},
#         ],
#         "refunded": False,
#         "cancelledAt": None,
#         "refundedAt": None,
#     },
#     {
#         "id": "gid://shopify/Order/5531567752003",
#         "name": "#44003",
#         "email": "mike@example.com",
#         "customerId": "gid://shopify/Customer/7424155189326",
#         "createdAt": _3_days_ago,
#         "status": "PARTIALLY_FULFILLED",
#         "fulfillmentStatus": "PARTIALLY_FULFILLED",
#         "financialStatus": "PAID",
#         "trackingUrl": "https://tracking.example.com/NATPAT2026MNO",
#         "trackingNumber": "NATPAT2026MNO",
#         "totalPrice": "84.98",
#         "currency": "USD",
#         "tags": [],
#         "shippingAddress": copy.deepcopy(_MIKE_ADDRESS),
#         "lineItems": [
#             {"title": "SleepyPatch — 24-Pack", "quantity": 1, "price": "29.99",
#              "productId": "gid://shopify/Product/8001", "variantId": "gid://shopify/ProductVariant/8001A",
#              "fulfillmentStatus": "FULFILLED"},
#             {"title": "BuzzPatch — 60-Pack", "quantity": 1, "price": "49.99",
#              "productId": "gid://shopify/Product/8002", "variantId": "gid://shopify/ProductVariant/8002B",
#              "fulfillmentStatus": "UNFULFILLED"},
#         ],
#         "refunded": False,
#         "cancelledAt": None,
#         "refundedAt": None,
#     },

#     # Emma orders
#     {
#         "id": "gid://shopify/Order/5531567753001",
#         "name": "#45001",
#         "email": "emma@example.com",
#         "customerId": "gid://shopify/Customer/7424155189327",
#         "createdAt": _7_days_ago,
#         "status": "DELIVERED",
#         "fulfillmentStatus": "FULFILLED",
#         "financialStatus": "PAID",
#         "trackingUrl": "https://tracking.example.com/NATPAT2026PQR",
#         "trackingNumber": "NATPAT2026PQR",
#         "totalPrice": "29.99",
#         "currency": "USD",
#         "tags": [],
#         "shippingAddress": copy.deepcopy(_EMMA_ADDRESS),
#         "lineItems": [
#             {"title": "ZenPatch — 24-Pack", "quantity": 1, "price": "29.99",
#              "productId": "gid://shopify/Product/8004", "variantId": "gid://shopify/ProductVariant/8004A"},
#         ],
#         "refunded": False,
#         "cancelledAt": None,
#         "refundedAt": None,
#     },
#     {
#         "id": "gid://shopify/Order/5531567753002",
#         "name": "#45002",
#         "email": "emma@example.com",
#         "customerId": "gid://shopify/Customer/7424155189327",
#         "createdAt": _3_days_ago,
#         "status": "FULFILLED",
#         "fulfillmentStatus": "FULFILLED",
#         "financialStatus": "PAID",
#         "trackingUrl": "https://tracking.example.com/NATPAT2026STU",
#         "trackingNumber": "NATPAT2026STU",
#         "totalPrice": "49.99",
#         "currency": "USD",
#         "tags": [],
#         "shippingAddress": copy.deepcopy(_EMMA_ADDRESS),
#         "lineItems": [
#             {"title": "BuzzPatch — 60-Pack", "quantity": 1, "price": "49.99",
#              "productId": "gid://shopify/Product/8002", "variantId": "gid://shopify/ProductVariant/8002B"},
#         ],
#         "refunded": False,
#         "cancelledAt": None,
#         "refundedAt": None,
#     },
# ]


# # =============================================================================
# # Subscriptions (seed)
# # =============================================================================

# _INITIAL_SUBSCRIPTIONS: dict[str, dict] = {
#     "sarah@example.com": {
#         "subscriptionId": "sub_SP_sarah_001",
#         "email": "sarah@example.com",
#         "status": "ACTIVE",
#         "productTitle": "SleepyPatch — 60-Pack",
#         "productId": "gid://shopify/Product/8001",
#         "frequency": "Every 30 days",
#         "nextBillingDate": (_NOW + timedelta(days=12)).strftime("%Y-%m-%d"),
#         "price": "53.99",
#         "currency": "USD",
#         "createdAt": (_NOW - timedelta(days=90)).strftime("%Y-%m-%d"),
#         "pausedUntil": None,
#         "cancelledAt": None,
#         "cancellationReasons": [],
#     },
#     "mike@example.com": {
#         "subscriptionId": "sub_FP_mike_002",
#         "email": "mike@example.com",
#         "status": "ACTIVE",
#         "productTitle": "FocusPatch — 24-Pack",
#         "productId": "gid://shopify/Product/8003",
#         "frequency": "Every 30 days",
#         "nextBillingDate": (_NOW + timedelta(days=5)).strftime("%Y-%m-%d"),
#         "price": "25.19",
#         "currency": "USD",
#         "createdAt": (_NOW - timedelta(days=60)).strftime("%Y-%m-%d"),
#         "pausedUntil": None,
#         "cancelledAt": None,
#         "cancellationReasons": [],
#     },
#     "emma@example.com": {
#         "subscriptionId": "sub_ZP_emma_003",
#         "email": "emma@example.com",
#         "status": "CANCELLED",
#         "productTitle": "ZenPatch — 24-Pack",
#         "productId": "gid://shopify/Product/8004",
#         "frequency": "Every 30 days",
#         "nextBillingDate": None,
#         "price": "26.99",
#         "currency": "USD",
#         "createdAt": (_NOW - timedelta(days=120)).strftime("%Y-%m-%d"),
#         "cancelledAt": (_NOW - timedelta(days=10)).strftime("%Y-%m-%d"),
#         "pausedUntil": None,
#         "cancellationReasons": ["No longer needed"],
#     },
# }

# _INITIAL_STORE_CREDITS: dict[str, dict] = {
#     "gid://shopify/Customer/7424155189325": {"amount": "0.00", "currencyCode": "USD"},
#     "gid://shopify/Customer/7424155189326": {"amount": "15.00", "currencyCode": "USD"},
#     "gid://shopify/Customer/7424155189327": {"amount": "0.00", "currencyCode": "USD"},
#     "gid://shopify/Customer/7424155189328": {"amount": "0.00", "currencyCode": "USD"},
# }
# _INITIAL_DISCOUNT_CODES: list[dict] = []


# # =============================================================================
# # Mutable State
# # =============================================================================

# class MockState:
#     def __init__(self) -> None:
#         self.reset()

#     def reset(self) -> None:
#         self.orders: list[dict] = copy.deepcopy(_INITIAL_ORDERS)
#         self.subscriptions: dict[str, dict] = copy.deepcopy(_INITIAL_SUBSCRIPTIONS)
#         self.store_credits: dict[str, dict] = copy.deepcopy(_INITIAL_STORE_CREDITS)
#         self.discount_codes: list[dict] = copy.deepcopy(_INITIAL_DISCOUNT_CODES)
#         self.returns: list[dict] = []
#         self.draft_orders: list[dict] = []
#         # Queue-based mock overrides: tool_name -> [response1, response2, ...]
#         self.mock_overrides: dict[str, list[dict]] = {}

#     def find_order_by_name(self, name: str) -> Optional[dict]:
#         """Find order by display name. Accepts '#43189', '43189', etc."""
#         clean = (name or "").strip().lstrip("#")
#         for o in self.orders:
#             if o.get("name", "").lstrip("#") == clean:
#                 return o
#         return None

#     def find_order_by_gid(self, gid: str) -> Optional[dict]:
#         gid = (gid or "").strip()
#         for o in self.orders:
#             if o.get("id") == gid:
#                 return o
#         return None

#     def find_orders_by_email(self, email: str) -> list[dict]:
#         email = (email or "").strip().lower()
#         return [o for o in self.orders if (o.get("email") or "").lower() == email]


# STATE = MockState()


# # =============================================================================
# # Helpers (responses, tags, parsing)
# # =============================================================================

# def _ok(data: Any = None) -> dict:
#     return {"success": True, **({"data": data} if data is not None else {})}

# def _fail(error: str) -> dict:
#     # Keep error short + consistent (many tests match substring)
#     return {"success": False, "error": error}

# def _gen_code(prefix: str = "DISCOUNT_LF_") -> str:
#     return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

# def _merge_tags(existing: list[str], new_tags: list[str]) -> list[str]:
#     """Order-preserving de-dupe (set() can reorder; tests sometimes assert contains)."""
#     out = list(existing or [])
#     seen = set(out)
#     for t in new_tags or []:
#         if t not in seen:
#             out.append(t)
#             seen.add(t)
#     return out

# def _order_summary(o: dict) -> dict:
#     return {
#         "id": o.get("id"),
#         "name": o.get("name"),
#         "createdAt": o.get("createdAt"),
#         "status": o.get("status"),
#         "trackingUrl": o.get("trackingUrl"),
#         "totalPrice": o.get("totalPrice"),
#         "currency": o.get("currency", "USD"),
#         "lineItems": [
#             {"title": li.get("title"), "quantity": li.get("quantity"), "price": li.get("price")}
#             for li in (o.get("lineItems") or [])
#         ],
#     }

# def _order_detail(o: dict) -> dict:
#     return {
#         "id": o.get("id"),
#         "name": o.get("name"),
#         "createdAt": o.get("createdAt"),
#         "status": o.get("status"),
#         "fulfillmentStatus": o.get("fulfillmentStatus", o.get("status")),
#         "financialStatus": o.get("financialStatus", "PAID"),
#         "trackingUrl": o.get("trackingUrl"),
#         "trackingNumber": o.get("trackingNumber"),
#         "totalPrice": o.get("totalPrice"),
#         "currency": o.get("currency", "USD"),
#         "tags": o.get("tags", []),
#         "shippingAddress": o.get("shippingAddress", {}),
#         "lineItems": o.get("lineItems", []),
#         "refunded": bool(o.get("refunded", False)),
#         "refundedAt": o.get("refundedAt"),
#         "cancelledAt": o.get("cancelledAt"),
#     }


# # =============================================================================
# # Route aliasing (VERY IMPORTANT)
# # =============================================================================
# # Many codebases differ on:
# #   - /hackhaton vs /hackathon
# #   - tool name vs simplified endpoint name
# #   - hyphen vs underscore
# #
# # To maximize compatibility, each tool is exposed under multiple aliases.

# _PREFIXES = ["/hackhaton", "/hackathon"]

# def _aliases(*names: str) -> list[str]:
#     paths: list[str] = []
#     for pfx in _PREFIXES:
#         for n in names:
#             n = n.strip("/")
#             paths.append(f"{pfx}/{n}")
#     # Also provide root aliases (some harnesses call directly)
#     for n in names:
#         n = n.strip("/")
#         paths.append(f"/{n}")
#     # De-dupe, preserve order
#     seen = set()
#     out = []
#     for x in paths:
#         if x not in seen:
#             out.append(x)
#             seen.add(x)
#     return out

# def register_post(*names: str) -> Callable:
#     """Decorator to register a POST handler across multiple alias paths."""
#     paths = _aliases(*names)

#     def deco(fn: Callable) -> Callable:
#         for path in paths:
#             app.add_api_route(path, fn, methods=["POST"])
#         return fn

#     return deco


# # =============================================================================
# # Health & Admin
# # =============================================================================

# @app.get("/health")
# async def health() -> dict:
#     return {"service": "NatPat Mock Tooling API", "version": "2.2", "status": "ok", "now": _today_str}

# @app.post("/admin/reset")
# async def admin_reset() -> dict:
#     STATE.reset()
#     return {"success": True, "message": "State reset to initial seed data"}

# @app.get("/admin/state")
# async def view_state() -> dict:
#     return {
#         "now": _today_str,
#         "orders_count": len(STATE.orders),
#         "orders": [
#             {"name": o["name"], "id": o["id"], "status": o["status"],
#              "email": o["email"], "tags": o.get("tags", []), "refunded": bool(o.get("refunded", False))}
#             for o in STATE.orders
#         ],
#         "subscriptions": {
#             k: {"subscriptionId": v["subscriptionId"], "status": v["status"],
#                 "pausedUntil": v.get("pausedUntil"), "cancelledAt": v.get("cancelledAt")}
#             for k, v in STATE.subscriptions.items()
#         },
#         "store_credits": STATE.store_credits,
#         "discount_codes_count": len(STATE.discount_codes),
#         "discount_codes": STATE.discount_codes,
#         "returns": STATE.returns,
#         "draft_orders_count": len(STATE.draft_orders),
#         "mock_overrides": {k: len(v) for k, v in STATE.mock_overrides.items()},
#     }


# # ═══════════════════════════════════════════════════════════════════════════════
# # Mock Override System (for test scenario injection)
# # ═══════════════════════════════════════════════════════════════════════════════

# async def _get_override_if_exists(tool_name: str) -> tuple[bool, dict | None]:
#     """
#     Check if override exists for this tool. Returns (has_override, response_or_none).
#     Consumes from queue (FIFO). Handles special simulation flags like timeout.
#     """
#     queue = STATE.mock_overrides.get(tool_name, [])
#     if not queue:
#         return False, None
    
#     response = queue.pop(0)  # FIFO — first response used first
    
#     # Handle special simulation flags
#     if isinstance(response, dict):
#         simulate = response.get("_simulate")
#         if simulate == "timeout":
#             await asyncio.sleep(61)  # Exceed typical timeout
#             return True, {"success": False, "error": "Request timed out"}
#         elif simulate == "error_504":
#             return True, {"success": False, "error": "Gateway Timeout", "_http_status": 504}
    
#     return True, response


# @app.post("/admin/set_mock_override")
# async def set_mock_override(request: Request) -> dict:
#     """
#     Queue a forced response for a specific tool.
#     Body: {"tool_name": "...", "response": {...}}
#     Or for multiple sequential responses:
#     Body: {"tool_name": "...", "responses": [{...}, {...}]}
#     Special simulation flags in response:
#       {"_simulate": "timeout"} → trigger 61s delay
#       {"_simulate": "error_504"} → return HTTP 504 error
#     """
#     body = await request.json()
#     tool_name = body.get("tool_name", "")
#     if not tool_name:
#         return {"success": False, "error": "tool_name required"}
    
#     # Support single or multiple responses
#     responses = body.get("responses", [])
#     if not responses and "response" in body:
#         responses = [body["response"]]
    
#     if not responses:
#         return {"success": False, "error": "response or responses required"}
    
#     if tool_name not in STATE.mock_overrides:
#         STATE.mock_overrides[tool_name] = []
#     STATE.mock_overrides[tool_name].extend(responses)
    
#     return {"success": True, "tool_name": tool_name, "queue_length": len(STATE.mock_overrides[tool_name])}


# @app.post("/admin/clear_mock_overrides")
# async def clear_mock_overrides() -> dict:
#     """Clear all queued mock overrides."""
#     STATE.mock_overrides.clear()
#     return {"success": True, "message": "All mock overrides cleared"}


# @app.post("/admin/set_time")
# async def set_mock_time(request: Request) -> dict:
#     """
#     Dynamically set MOCK_NOW and recalculate all date-dependent values.
#     Body: {"datetime": "2026-02-02T12:00:00Z"} or {"day": "Monday"}
#     """
#     global _NOW, _today_str, _today_morning, _yesterday, _yesterday_morning
#     global _3_days_ago, _7_days_ago, _10_days_ago, _14_days_ago, _today_date
    
#     body = await request.json()
    
#     # Parse target datetime
#     if "datetime" in body:
#         _NOW = datetime.fromisoformat(body["datetime"].replace("Z", "+00:00"))
#     elif "day" in body:
#         # 2026-02-06 is Friday. Calculate offset for target day.
#         day_offsets = {
#             "Monday": -4, "Tuesday": -3, "Wednesday": -2,
#             "Thursday": -1, "Friday": 0, "Saturday": 1, "Sunday": 2
#         }
#         offset = day_offsets.get(body["day"], 0)
#         base = datetime(2026, 2, 6, 12, 0, 0, tzinfo=timezone.utc)
#         _NOW = base + timedelta(days=offset)
#     else:
#         return {"success": False, "error": "datetime or day required"}
    
#     # Recalculate all derived date values
#     _today_str = _iso(_NOW)
#     _today_morning = _iso(_NOW.replace(hour=8, minute=0, second=0))
#     _yesterday = _iso(_NOW - timedelta(days=1))
#     _yesterday_morning = _iso((_NOW - timedelta(days=1)).replace(hour=8, minute=0, second=0))
#     _3_days_ago = _iso(_NOW - timedelta(days=3))
#     _7_days_ago = _iso(_NOW - timedelta(days=7))
#     _10_days_ago = _iso(_NOW - timedelta(days=10))
#     _14_days_ago = _iso(_NOW - timedelta(days=14))
#     _today_date = _NOW.strftime("%Y-%m-%d")
    
#     # Rebuild initial orders with new dates and reset state
#     _rebuild_initial_orders()
#     STATE.reset()
    
#     return {"success": True, "new_now": _today_str, "day": _NOW.strftime("%A")}


# def _rebuild_initial_orders():
#     """Rebuild _INITIAL_ORDERS with recalculated dates based on current _NOW."""
#     global _INITIAL_ORDERS
#     # Update createdAt timestamps relative to new _NOW
#     for order in _INITIAL_ORDERS:
#         name = order.get("name", "")
#         # Apply appropriate date based on order name for consistency
#         if name == "#43189":
#             order["createdAt"] = _10_days_ago
#         elif name == "#43200":
#             order["createdAt"] = _7_days_ago
#         elif name == "#43215":
#             order["createdAt"] = _3_days_ago
#         elif name == "#43190":
#             order["createdAt"] = _14_days_ago
#         elif name == "#51234":
#             order["createdAt"] = _yesterday

# @app.get("/admin/orders/{email}")
# async def view_orders(email: str) -> dict:
#     orders = STATE.find_orders_by_email(email)
#     return {"email": email, "orders": [_order_detail(o) for o in orders]}

# @app.post("/admin/add_customer")
# async def add_customer(request: Request) -> dict:
#     body = await request.json()
#     cid = body.get("id", f"gid://shopify/Customer/{random.randint(1000000, 9999999)}")
#     email = (body.get("email") or "").strip()
#     CUSTOMERS[cid] = {
#         "id": cid,
#         "email": email,
#         "firstName": body.get("firstName", ""),
#         "lastName": body.get("lastName", ""),
#         "storeCreditBalance": {"amount": "0.00", "currencyCode": "USD"},
#         "tags": [],
#     }
#     STATE.store_credits[cid] = {"amount": "0.00", "currencyCode": "USD"}
#     if email:
#         EMAIL_TO_CUSTOMER[email.lower()] = cid
#     return {"success": True, "customerId": cid}

# @app.post("/admin/add_order")
# async def add_order(request: Request) -> dict:
#     body = await request.json()
#     order = {
#         "id": body.get("id", f"gid://shopify/Order/{random.randint(5000000000000, 5999999999999)}"),
#         "name": body.get("name", f"#{random.randint(10000, 99999)}"),
#         "email": body.get("email", ""),
#         "customerId": body.get("customerId", ""),
#         "createdAt": body.get("createdAt", _today_str),
#         "status": body.get("status", "UNFULFILLED"),
#         "fulfillmentStatus": body.get("fulfillmentStatus", body.get("status", "UNFULFILLED")),
#         "financialStatus": body.get("financialStatus", "PAID"),
#         "trackingUrl": body.get("trackingUrl"),
#         "trackingNumber": body.get("trackingNumber"),
#         "totalPrice": body.get("totalPrice", "29.99"),
#         "currency": body.get("currency", "USD"),
#         "tags": body.get("tags", []),
#         "shippingAddress": body.get("shippingAddress", {}),
#         "lineItems": body.get("lineItems", []),
#         "refunded": bool(body.get("refunded", False)),
#         "cancelledAt": body.get("cancelledAt"),
#         "refundedAt": body.get("refundedAt"),
#     }
#     STATE.orders.append(order)
#     return {"success": True, "orderId": order["id"], "orderName": order["name"]}

# @app.post("/admin/add_subscription")
# async def add_subscription(request: Request) -> dict:
#     body = await request.json()
#     email = (body.get("email") or "").strip().lower()
#     if not email:
#         return {"success": False, "error": "email is required"}
#     STATE.subscriptions[email] = {
#         "subscriptionId": body.get("subscriptionId", f"sub_{uuid.uuid4().hex[:8]}"),
#         "email": email,
#         "status": body.get("status", "ACTIVE"),
#         "productTitle": body.get("productTitle", "SleepyPatch — 24-Pack"),
#         "productId": body.get("productId", "gid://shopify/Product/8001"),
#         "frequency": body.get("frequency", "Every 30 days"),
#         "nextBillingDate": body.get("nextBillingDate", (_NOW + timedelta(days=15)).strftime("%Y-%m-%d")),
#         "price": body.get("price", "29.99"),
#         "currency": body.get("currency", "USD"),
#         "createdAt": body.get("createdAt", _NOW.strftime("%Y-%m-%d")),
#         "pausedUntil": body.get("pausedUntil"),
#         "cancelledAt": body.get("cancelledAt"),
#         "cancellationReasons": body.get("cancellationReasons", []),
#     }
#     return {"success": True, "subscriptionId": STATE.subscriptions[email]["subscriptionId"]}


# # =============================================================================
# # Shopify Tools (14)
# # =============================================================================

# @register_post(
#     "get_order_details",
#     "shopify_get_order_details",
#     "shopify-get-order-details",
# )
# async def shopify_get_order_details(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_get_order_details")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     order_id = (body.get("orderId") or "").strip()
#     if not order_id:
#         return _fail("orderId is required")

#     # Allow #number, number, or GID
#     order = STATE.find_order_by_name(order_id) or STATE.find_order_by_gid(order_id)
#     if not order:
#         return _fail("Order not found")

#     return _ok(_order_detail(order))


# @register_post(
#     "get_customer_orders",
#     "shopify_get_customer_orders",
#     "shopify-get-customer-orders",
# )
# async def shopify_get_customer_orders(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_get_customer_orders")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     email = (body.get("email") or "").strip().lower()
#     if not email:
#         return _fail("email is required")

#     # Spec-safe: accept limit, after (cursor), plus any extra params
#     try:
#         limit = int(body.get("limit", 10))
#     except (ValueError, TypeError):
#         limit = 10
#     limit = max(1, min(limit, 250))

#     after_cursor = body.get("after")  # cursor is usually an order GID

#     orders = STATE.find_orders_by_email(email)
#     # Prefer NOT failing hard: many agent flows handle empty list better than tool error
#     if not orders:
#         return _ok({"orders": [], "hasNextPage": False, "endCursor": None})

#     orders.sort(key=lambda o: o.get("createdAt", ""), reverse=True)

#     start_idx = 0
#     if after_cursor and str(after_cursor).strip() not in ("null", "None", ""):
#         for i, o in enumerate(orders):
#             if o.get("id") == after_cursor:
#                 start_idx = i + 1
#                 break

#     page = orders[start_idx:start_idx + limit]
#     has_next = (start_idx + limit) < len(orders)

#     return _ok({
#         "orders": [_order_summary(o) for o in page],
#         "hasNextPage": has_next,
#         "endCursor": page[-1]["id"] if page else None,
#     })


# @register_post(
#     "get_product_details",
#     "shopify_get_product_details",
#     "shopify-get-product-details",
# )
# async def shopify_get_product_details(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_get_product_details")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     query_type = (body.get("queryType") or "").strip().lower()
#     query_key = (body.get("queryKey") or "").strip()
#     if not query_key:
#         return _fail("queryKey is required")

#     results: list[dict] = []

#     if query_type == "id":
#         p = PRODUCTS.get(query_key)
#         if p:
#             results.append(p)
#     elif query_type == "name":
#         kl = query_key.lower()
#         for p in PRODUCTS.values():
#             if kl in p["title"].lower() or kl in p["handle"].lower():
#                 results.append(p)
#     elif query_type in ("key feature", "key_feature", "feature"):
#         kl = query_key.lower()
#         for p in PRODUCTS.values():
#             if any(kl in tag.lower() for tag in p["tags"]) or kl in p["description"].lower():
#                 results.append(p)
#     else:
#         kl = query_key.lower()
#         for p in PRODUCTS.values():
#             if (
#                 kl in p["title"].lower()
#                 or kl in p["handle"].lower()
#                 or any(kl in tag.lower() for tag in p["tags"])
#                 or kl in p["description"].lower()
#             ):
#                 results.append(p)

#     if not results:
#         return _fail("Product not found")

#     # Return list (many implementations expect list even for single match)
#     return _ok([
#         {
#             "id": p["id"],
#             "title": p["title"],
#             "handle": p["handle"],
#             "description": p["description"],
#             "price": p["price"],
#             "currency": p.get("currency", "USD"),
#             "usage_guide": p.get("usage_guide", ""),
#             "variants": p.get("variants", []),
#             "tags": p.get("tags", []),
#         }
#         for p in results
#     ])


# @register_post(
#     "get_product_recommendations",
#     "shopify_get_product_recommendations",
#     "shopify-get-product-recommendations",
# )
# async def shopify_get_product_recommendations(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_get_product_recommendations")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     query_keys = body.get("queryKeys") or []
#     if not isinstance(query_keys, list) or not query_keys:
#         return _fail("queryKeys is required")

#     keywords = [str(k).lower() for k in query_keys]
#     scored: list[tuple[int, dict]] = []
#     seen: set[str] = set()

#     for p in PRODUCTS.values():
#         score = 0
#         for kw in keywords:
#             if kw in p["title"].lower():
#                 score += 3
#             if kw in p["handle"].lower():
#                 score += 2
#             if any(kw in tag.lower() for tag in p["tags"]):
#                 score += 2
#             if kw in p["description"].lower():
#                 score += 1
#         if score > 0 and p["id"] not in seen:
#             scored.append((score, p))
#             seen.add(p["id"])

#     scored.sort(key=lambda x: x[0], reverse=True)
#     picks = [p for _, p in scored[:5]] if scored else list(PRODUCTS.values())[:3]

#     return _ok([
#         {"id": p["id"], "title": p["title"], "handle": p["handle"],
#          "description": p["description"], "price": p["price"], "currency": p.get("currency", "USD")}
#         for p in picks
#     ])


# @register_post(
#     "get_related_knowledge_source",
#     "shopify_get_related_knowledge_source",
#     "shopify-get-related-knowledge-source",
# )
# async def shopify_get_related_knowledge_source(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_get_related_knowledge_source")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     question = (body.get("question") or "").lower()
#     product_id = body.get("specificToProductId")

#     category_keywords = {
#         "sleep": ["sleep", "sleepy", "bedtime", "night", "insomnia", "tired"],
#         "focus": ["focus", "concentration", "school", "homework", "attention", "adhd", "concentrate"],
#         "mosquito": ["mosquito", "bug", "bite", "buzz", "outdoor", "repel", "bitten"],
#         "itch": ["itch", "sting", "magic", "relief", "hive", "rash"],
#     }

#     best_category = "general"
#     best_score = 0
#     for cat, kws in category_keywords.items():
#         score = sum(1 for kw in kws if kw in question)
#         if score > best_score:
#             best_score = score
#             best_category = cat

#     # If specific product is provided, bias to its tags
#     if product_id and product_id in PRODUCTS:
#         tags = [t.lower() for t in PRODUCTS[product_id].get("tags", [])]
#         for cat, kws in category_keywords.items():
#             if any(t in kws or t == cat for t in tags):
#                 best_category = cat
#                 break

#     kb = KNOWLEDGE_BASE.get(best_category, KNOWLEDGE_BASE["general"])
#     return _ok({
#         "faqs": kb.get("faqs", []),
#         "pdfs": kb.get("pdfs", []),
#         "blogArticles": kb.get("blogArticles", []),
#         "pages": kb.get("pages", []),
#         "category": best_category,
#     })


# @register_post(
#     "get_collection_recommendations",
#     "shopify_get_collection_recommendations",
#     "shopify-get-collection-recommendations",
# )
# async def shopify_get_collection_recommendations(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_get_collection_recommendations")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     query_keys = body.get("queryKeys") or []
#     if not isinstance(query_keys, list):
#         query_keys = []

#     keywords = [str(k).lower() for k in query_keys]
#     results = [
#         c for c in COLLECTIONS
#         if any(kw in c["title"].lower() or kw in c["handle"].lower() for kw in keywords)
#     ]
#     if not results:
#         results = COLLECTIONS[:3]
#     return _ok(results)


# @register_post(
#     "cancel_order",
#     "shopify_cancel_order",
#     "shopify-cancel-order",
# )
# async def shopify_cancel_order(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_cancel_order")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     order_id = (body.get("orderId") or "").strip()

#     # Accept all spec-ish params without breaking
#     reason = body.get("reason", "CUSTOMER")
#     notify_customer = bool(body.get("notifyCustomer", True))
#     restock = bool(body.get("restock", True))
#     staff_note = body.get("staffNote", "")
#     refund_mode = body.get("refundMode", "ORIGINAL")
#     store_credit = body.get("storeCredit", {"expiresAt": None})
#     _ = (notify_customer, restock, refund_mode, store_credit)  # intentionally unused (but accepted)

#     if not order_id:
#         return _fail("orderId is required")

#     order = STATE.find_order_by_gid(order_id)
#     if not order:
#         # Helpful guidance if user passes #number
#         if STATE.find_order_by_name(order_id):
#             return _fail("Order ID must be a Shopify GID (gid://shopify/Order/...). Use get_order_details first.")
#         return _fail("Order not found")

#     if order["status"] == "CANCELLED":
#         return _fail("Order is already cancelled")

#     if order["status"] in ("FULFILLED", "DELIVERED"):
#         return _fail("Cannot cancel — order already shipped/fulfilled")

#     if order["status"] == "PARTIALLY_FULFILLED":
#         return _fail("Cannot cancel — order partially fulfilled (manual review required)")

#     if order.get("refunded"):
#         return _fail("Order has already been refunded")

#     order["status"] = "CANCELLED"
#     order["fulfillmentStatus"] = "UNFULFILLED"
#     order["financialStatus"] = "REFUNDED"
#     order["cancelledAt"] = _iso(datetime.now(timezone.utc))
#     order["refunded"] = True
#     order["refundedAt"] = order["cancelledAt"]

#     if staff_note:
#         order["tags"] = _merge_tags(order.get("tags", []), [f"Staff Note: {staff_note}"])
#     if reason:
#         order["tags"] = _merge_tags(order.get("tags", []), [f"Cancel Reason: {reason}"])

#     return _ok({"orderId": order["id"], "status": order["status"], "cancelledAt": order["cancelledAt"]})


# @register_post(
#     "refund_order",
#     "shopify_refund_order",
#     "shopify-refund-order",
# )
# async def shopify_refund_order(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_refund_order")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     order_id = (body.get("orderId") or "").strip()
#     refund_method = body.get("refundMethod", "ORIGINAL_PAYMENT_METHODS")

#     if not order_id:
#         return _fail("orderId is required")

#     order = STATE.find_order_by_gid(order_id)
#     if not order:
#         return _fail("Order not found")

#     if order.get("refunded"):
#         return _fail("Order has already been refunded")

#     # Even if cancelled, allow marking refunded (unless already refunded)
#     order["refunded"] = True
#     order["financialStatus"] = "REFUNDED"
#     order["refundedAt"] = _iso(datetime.now(timezone.utc))
#     order["tags"] = _merge_tags(order.get("tags", []), [f"Refunded via {refund_method}"])

#     return _ok({"orderId": order["id"], "refundedAt": order["refundedAt"]})


# @register_post(
#     "create_store_credit",
#     "shopify_create_store_credit",
#     "shopify-create-store-credit",
# )
# async def shopify_create_store_credit(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_create_store_credit")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     customer_id = (body.get("id") or "").strip()
#     credit_amount = body.get("creditAmount") or {}
#     expires_at = body.get("expiresAt")  # accepted (nullable)

#     if not customer_id:
#         return _fail("Customer ID is required")
#     if customer_id not in STATE.store_credits:
#         return _fail("Customer not found")

#     amount_raw = credit_amount.get("amount", "0")
#     currency = credit_amount.get("currencyCode", "USD")

#     try:
#         amount = float(amount_raw)
#     except (ValueError, TypeError):
#         return _fail("Invalid credit amount")

#     if amount <= 0:
#         return _fail("Credit amount must be positive")

#     current = float(STATE.store_credits[customer_id]["amount"])
#     new_balance = round(current + amount, 2)
#     STATE.store_credits[customer_id]["amount"] = f"{new_balance:.2f}"
#     STATE.store_credits[customer_id]["currencyCode"] = currency

#     # Mirror into customer object (if present)
#     if customer_id in CUSTOMERS:
#         CUSTOMERS[customer_id]["storeCreditBalance"] = {"amount": f"{new_balance:.2f}", "currencyCode": currency}

#     sc_account_id = f"gid://shopify/StoreCreditAccount/{abs(hash(customer_id)) % 100000}"
#     payload = {
#         "storeCreditAccountId": sc_account_id,
#         "credited": {"amount": f"{amount:.2f}", "currencyCode": currency},
#         "newBalance": {"amount": f"{new_balance:.2f}", "currencyCode": currency},
#         "expiresAt": expires_at,  # echo
#     }
#     return _ok(payload)


# @register_post(
#     "add_tags",
#     "shopify_add_tags",
#     "shopify-add-tags",
# )
# async def shopify_add_tags(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_add_tags")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     resource_id = (body.get("id") or "").strip()
#     tags = body.get("tags") or []

#     if not resource_id:
#         return _fail("Resource ID is required")
#     if not isinstance(tags, list) or not tags:
#         return _fail("Tags list is required and must not be empty")

#     order = STATE.find_order_by_gid(resource_id)
#     if order:
#         order["tags"] = _merge_tags(order.get("tags", []), tags)
#         return _ok()

#     if resource_id in CUSTOMERS:
#         CUSTOMERS[resource_id]["tags"] = _merge_tags(CUSTOMERS[resource_id].get("tags", []), tags)
#         return _ok()

#     if resource_id in PRODUCTS:
#         # products are static; still return ok for compatibility
#         return _ok()

#     for d in STATE.draft_orders:
#         if d.get("id") == resource_id:
#             d["tags"] = _merge_tags(d.get("tags", []), tags)
#             return _ok()

#     return _fail("Resource not found")


# @register_post(
#     "create_discount_code",
#     "shopify_create_discount_code",
#     "shopify-create-discount-code",
# )
# async def shopify_create_discount_code(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_create_discount_code")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     disc_type = body.get("type", "percentage")
#     value = body.get("value", 0.10)
#     duration = body.get("duration", 48)
#     product_ids = body.get("productIds", [])

#     # Be tolerant to types
#     try:
#         duration = int(duration)
#     except (ValueError, TypeError):
#         duration = 48

#     code = _gen_code(prefix="NATPAT_")
#     created_at = _iso(datetime.now(timezone.utc))
#     expires_at = _iso(datetime.now(timezone.utc) + timedelta(hours=max(1, duration)))

#     STATE.discount_codes.append({
#         "code": code,
#         "type": disc_type,
#         "value": value,
#         "duration": duration,
#         "productIds": product_ids if isinstance(product_ids, list) else [],
#         "createdAt": created_at,
#         "expiresAt": expires_at,
#     })

#     return _ok({"code": code, "expiresAt": expires_at})


# def _validate_address(addr: dict) -> Optional[str]:
#     required_fields = ["firstName", "lastName", "address1", "city", "provinceCode", "country", "zip", "phone"]
#     missing = [f for f in required_fields if not (addr.get(f) or "").strip()]
#     if missing:
#         return f"Missing required address fields: {', '.join(missing)}"

#     country = (addr.get("country") or "").strip().upper()
#     zip_code = (addr.get("zip") or "").strip()

#     if country in ("US", "USA"):
#         zip_clean = re.sub(r"[^0-9]", "", zip_code)
#         if len(zip_clean) not in (5, 9):
#             return f"Invalid US ZIP code: {zip_code}"

#     if country in ("CA", "CAN"):
#         pc = zip_code.replace(" ", "").upper()
#         if len(pc) != 6 or not re.match(r"^[A-Z]\d[A-Z]\d[A-Z]\d$", pc):
#             return f"Invalid Canadian postal code: {zip_code}"

#     return None


# @register_post(
#     "update_order_shipping_address",
#     "shopify_update_order_shipping_address",
#     "shopify-update-order-shipping-address",
# )
# async def shopify_update_order_shipping_address(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_update_order_shipping_address")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     order_id = (body.get("orderId") or "").strip()
#     new_address = body.get("shippingAddress") or {}

#     if not order_id:
#         return _fail("orderId is required")

#     order = STATE.find_order_by_gid(order_id)
#     if not order:
#         return _fail("Order not found")

#     if order["status"] in ("FULFILLED", "DELIVERED"):
#         return _fail("Cannot change address — order already shipped")

#     if order["status"] == "CANCELLED":
#         return _fail("Cannot update address for cancelled order")

#     err = _validate_address(new_address)
#     if err:
#         return _fail(err)

#     order["shippingAddress"] = new_address
#     return _ok({"orderId": order["id"], "updated": True})


# @register_post(
#     "create_return",
#     "shopify_create_return",
#     "shopify-create-return",
# )
# async def shopify_create_return(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_create_return")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     order_id = (body.get("orderId") or "").strip()
#     if not order_id:
#         return _fail("orderId is required")

#     order = STATE.find_order_by_gid(order_id)
#     if not order:
#         return _fail("Order not found")

#     if order["status"] == "CANCELLED":
#         return _fail("Cannot create return for cancelled order")

#     if order["status"] == "UNFULFILLED":
#         return _fail("Cannot create return for unfulfilled order")

#     return_id = f"gid://shopify/Return/{uuid.uuid4().hex[:12]}"
#     created_at = _iso(datetime.now(timezone.utc))
#     label_url = f"https://returns.example.com/label/{return_id.split('/')[-1]}"
#     portal_url = f"https://returns.example.com/portal/{order['name'].lstrip('#')}"

#     rec = {
#         "id": return_id,
#         "orderId": order_id,
#         "orderName": order["name"],
#         "status": "REQUESTED",
#         "createdAt": created_at,
#         "returnLabelUrl": label_url,
#         "returnPortalUrl": portal_url,
#         "requestBody": body,  # traceability
#     }
#     STATE.returns.append(rec)

#     return _ok({"returnId": return_id, "returnLabelUrl": label_url, "returnPortalUrl": portal_url})


# @register_post(
#     "create_draft_order",
#     "shopify_create_draft_order",
#     "shopify-create-draft-order",
# )
# async def shopify_create_draft_order(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("shopify_create_draft_order")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     draft_id = f"gid://shopify/DraftOrder/{uuid.uuid4().hex[:12]}"
#     token = uuid.uuid4().hex[:16]
#     created_at = _iso(datetime.now(timezone.utc))
#     checkout_url = f"https://checkout.example.com/draft/{draft_id.split('/')[-1]}?token={token}"
#     invoice_url = f"https://checkout.example.com/invoice/{draft_id.split('/')[-1]}?token={token}"

#     STATE.draft_orders.append({
#         "id": draft_id,
#         "status": "OPEN",
#         "createdAt": created_at,
#         "checkoutUrl": checkout_url,
#         "invoiceUrl": invoice_url,
#         "body": body,  # store entire request payload
#     })

#     return _ok({"draftOrderId": draft_id, "checkoutUrl": checkout_url, "invoiceUrl": invoice_url})


# # =============================================================================
# # Skio Tools (5)
# # =============================================================================

# @register_post(
#     "get-subscription-status",
#     "get_subscription_status",
#     "skio_get_subscription_status",
#     "skio-get-subscription-status",
# )
# async def skio_get_subscription_status(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("skio_get_subscription_status")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     email = (body.get("email") or "").strip().lower()
#     if not email:
#         return _fail("email is required")

#     sub = STATE.subscriptions.get(email)
#     if not sub:
#         return _fail("No subscription found for this email")

#     if sub.get("status") == "CANCELLED":
#         # Keep EXACTLY the common phrase many tests use
#         return _fail("Failed to get subscription status. This subscription has already been cancelled.")

#     return _ok({
#         "status": sub["status"],
#         "subscriptionId": sub["subscriptionId"],
#         "productTitle": sub["productTitle"],
#         "frequency": sub["frequency"],
#         "nextBillingDate": sub["nextBillingDate"],
#         "price": sub["price"],
#         "currency": sub["currency"],
#         "pausedUntil": sub.get("pausedUntil"),
#     })


# @register_post(
#     "cancel-subscription",
#     "cancel_subscription",
#     "skio_cancel_subscription",
#     "skio-cancel-subscription",
# )
# async def skio_cancel_subscription(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("skio_cancel_subscription")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     sub_id = (body.get("subscriptionId") or "").strip()
#     reasons = body.get("cancellationReasons", [])

#     if not sub_id:
#         return _fail("subscriptionId is required")

#     target = None
#     for sub in STATE.subscriptions.values():
#         if sub.get("subscriptionId") == sub_id:
#             target = sub
#             break

#     if not target:
#         return _fail("Subscription not found")

#     if target.get("status") == "CANCELLED":
#         return _fail("This subscription has already been cancelled.")

#     # Normalize reasons to list of strings
#     if isinstance(reasons, str):
#         reasons = [reasons]
#     if not isinstance(reasons, list):
#         reasons = []

#     target["status"] = "CANCELLED"
#     target["cancelledAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
#     target["nextBillingDate"] = None
#     target["cancellationReasons"] = reasons

#     return _ok({"subscriptionId": sub_id, "status": "CANCELLED"})


# @register_post(
#     "pause-subscription",
#     "pause_subscription",
#     "skio_pause_subscription",
#     "skio-pause-subscription",
# )
# async def skio_pause_subscription(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("skio_pause_subscription")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     sub_id = (body.get("subscriptionId") or "").strip()
#     paused_until = (body.get("pausedUntil") or "").strip()

#     if not sub_id:
#         return _fail("subscriptionId is required")
#     if not paused_until:
#         return _fail("pausedUntil is required (YYYY-MM-DD)")

#     # Basic format tolerance: accept YYYY-MM-DD; do not hard fail if not parseable,
#     # but many test suites provide a date string.
#     if not re.match(r"^\d{4}-\d{2}-\d{2}$", paused_until):
#         # still accept, but keep message stable if a harness wants strictness
#         # (if you prefer strict, swap to _fail(...))
#         pass

#     target = None
#     for sub in STATE.subscriptions.values():
#         if sub.get("subscriptionId") == sub_id:
#             target = sub
#             break

#     if not target:
#         return _fail("Subscription not found")
#     if target.get("status") == "CANCELLED":
#         return _fail("Cannot pause a cancelled subscription")
#     if target.get("status") == "PAUSED":
#         return _fail("Subscription is already paused")

#     target["status"] = "PAUSED"
#     target["pausedUntil"] = paused_until
#     return _ok({"subscriptionId": sub_id, "status": "PAUSED", "pausedUntil": paused_until})


# @register_post(
#     "skip-next-order-subscription",
#     "skip_next_order_subscription",
#     "skio_skip_next_order_subscription",
#     "skio-skip-next-order-subscription",
# )
# async def skio_skip_next_order_subscription(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("skio_skip_next_order_subscription")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     sub_id = (body.get("subscriptionId") or "").strip()

#     if not sub_id:
#         return _fail("subscriptionId is required")

#     target = None
#     for sub in STATE.subscriptions.values():
#         if sub.get("subscriptionId") == sub_id:
#             target = sub
#             break

#     if not target:
#         return _fail("Subscription not found")
#     if target.get("status") == "CANCELLED":
#         return _fail("Cannot skip order on a cancelled subscription")

#     # If nextBillingDate is missing, create a reasonable one
#     nbd = target.get("nextBillingDate")
#     try:
#         current_date = datetime.strptime(nbd, "%Y-%m-%d")
#         new_date = current_date + timedelta(days=30)
#     except Exception:
#         new_date = (_NOW + timedelta(days=60)).replace(tzinfo=None)

#     target["nextBillingDate"] = new_date.strftime("%Y-%m-%d")
#     return _ok({"subscriptionId": sub_id, "newNextBillingDate": target["nextBillingDate"]})


# @register_post(
#     "unpause-subscription",
#     "unpause_subscription",
#     "skio_unpause_subscription",
#     "skio-unpause-subscription",
# )
# async def skio_unpause_subscription(request: Request) -> dict:
#     # Check for queued override first
#     has_override, override_resp = await _get_override_if_exists("skio_unpause_subscription")
#     if has_override:
#         return override_resp
    
#     body = await request.json()
#     sub_id = (body.get("subscriptionId") or "").strip()

#     if not sub_id:
#         return _fail("subscriptionId is required")

#     target = None
#     for sub in STATE.subscriptions.values():
#         if sub.get("subscriptionId") == sub_id:
#             target = sub
#             break

#     if not target:
#         return _fail("Subscription not found")
#     if target.get("status") != "PAUSED":
#         return _fail(f"Subscription is not paused (current status: {target.get('status')})")

#     target["status"] = "ACTIVE"
#     target["pausedUntil"] = None
#     return _ok({"subscriptionId": sub_id, "status": "ACTIVE"})


# # =============================================================================
# # Main
# # =============================================================================

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8080)
