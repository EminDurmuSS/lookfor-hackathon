"""
NatPat Hackathon — Comprehensive Mock API Server
=================================================
100% compatible with the 95-scenario test suite AND the Tooling Spec.

Simulates ALL 19 Shopify + Skio tool endpoints with:
  - Realistic, interconnected fake data matching test scenario expectations
  - Order numbers: #43189, #43200, #43215, #51234 (as referenced in tests)
  - Stateful mutations (cancel, refund, tag, address update persist)
  - Edge cases (already cancelled, already refunded, fulfilled vs unfulfilled, etc.)
  - Knowledge base & product recommendations
  - Discount code generation
  - Subscription lifecycle (active/paused/cancelled)
  - Cursor-based pagination for get_customer_orders
  - Full param acceptance per Tooling Spec schemas

Run:  uvicorn mock_api_server:app --port 8080 --reload
"""

from __future__ import annotations

import copy
import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="NatPat Mock Tooling API", version="2.1")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ── Health & Admin Endpoints ──────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"service": "NatPat Mock Tooling API", "version": "2.1", "status": "ok"}

@app.post("/admin/reset")
async def admin_reset():
    STATE.reset()
    return {"success": True, "message": "State reset to initial values"}

# ═══════════════════════════════════════════════════════════════════════════════
# TIMESTAMPS — relative to "now"
# ═══════════════════════════════════════════════════════════════════════════════

_now = datetime.utcnow()
_today_str = _now.strftime("%Y-%m-%dT%H:%M:%SZ")
_today_morning = _now.replace(hour=8, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%SZ")
_yesterday = (_now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
_yesterday_morning = (_now - timedelta(days=1)).replace(hour=8, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%SZ")
_3_days_ago = (_now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
_7_days_ago = (_now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
_10_days_ago = (_now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
_14_days_ago = (_now - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
_today_date = _now.strftime("%Y-%m-%d")

# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════════

PRODUCTS: dict[str, dict] = {
    "gid://shopify/Product/8001": {
        "id": "gid://shopify/Product/8001",
        "title": "SleepyPatch — Sleep Promoting Stickers for Kids",
        "handle": "sleepypatch",
        "description": "Natural sleep stickers infused with lavender and mandarin essential oils. Apply 30 minutes before bedtime on pajamas or pillow.",
        "price": "29.99",
        "currency": "USD",
        "tags": ["sleep", "kids", "essential oils", "lavender", "bedtime"],
        "usage_guide": (
            "Apply 1-2 patches on pajamas or pillow 30 minutes before bedtime. "
            "For best results, use consistently for 5-7 nights. Keep patches away from "
            "face and mouth. Each patch lasts 8-12 hours."
        ),
        "variants": [
            {"id": "gid://shopify/ProductVariant/8001A", "title": "24-Pack", "price": "29.99"},
            {"id": "gid://shopify/ProductVariant/8001B", "title": "60-Pack", "price": "59.99"},
        ],
    },
    "gid://shopify/Product/8002": {
        "id": "gid://shopify/Product/8002",
        "title": "BuzzPatch — Mosquito Repellent Stickers",
        "handle": "buzzpatch",
        "description": "Citronella and eucalyptus stickers that keep mosquitoes away naturally. Safe for kids 2+.",
        "price": "24.99",
        "currency": "USD",
        "tags": ["mosquito", "bug repellent", "outdoor", "kids", "citronella"],
        "usage_guide": (
            "Apply 1-2 patches on clothing (not skin) before going outdoors. "
            "Reapply every 6-8 hours. For heavy mosquito areas, use 3-4 patches "
            "spread across clothing."
        ),
        "variants": [
            {"id": "gid://shopify/ProductVariant/8002A", "title": "24-Pack", "price": "24.99"},
            {"id": "gid://shopify/ProductVariant/8002B", "title": "60-Pack", "price": "49.99"},
        ],
    },
    "gid://shopify/Product/8003": {
        "id": "gid://shopify/Product/8003",
        "title": "FocusPatch — Concentration Stickers for Kids",
        "handle": "focuspatch",
        "description": "Essential oil stickers with peppermint and rosemary to help kids focus during school or homework.",
        "price": "27.99",
        "currency": "USD",
        "tags": ["focus", "concentration", "school", "kids", "peppermint"],
        "usage_guide": (
            "Apply 1 patch on clothing near the collar area 15 minutes before focus is needed. "
            "Each patch lasts 6-8 hours. Best used during homework, tests, or activities "
            "requiring concentration. Use consistently for 5-7 days for best results."
        ),
        "variants": [
            {"id": "gid://shopify/ProductVariant/8003A", "title": "24-Pack", "price": "27.99"},
        ],
    },
    "gid://shopify/Product/8004": {
        "id": "gid://shopify/Product/8004",
        "title": "ZenPatch — Calm & Mood Stickers",
        "handle": "zenpatch",
        "description": "Calming essential oil stickers with chamomile and sweet orange. Great for anxious moments.",
        "price": "29.99",
        "currency": "USD",
        "tags": ["calm", "mood", "anxiety", "kids", "chamomile", "zen"],
        "usage_guide": (
            "Apply 1-2 patches on clothing when feeling anxious or before stressful situations. "
            "Can be used alongside SleepyPatch at bedtime for enhanced calm. Each patch lasts 6-8 hours."
        ),
        "variants": [
            {"id": "gid://shopify/ProductVariant/8004A", "title": "24-Pack", "price": "29.99"},
        ],
    },
    "gid://shopify/Product/8005": {
        "id": "gid://shopify/Product/8005",
        "title": "MagicPatch — Itch Relief Patches",
        "handle": "magicpatch",
        "description": "Chemical-free itch relief patches for bug bites. Uses grid-relief technology to drain the itch.",
        "price": "14.99",
        "currency": "USD",
        "tags": ["itch relief", "bug bites", "kids", "chemical-free"],
        "usage_guide": (
            "Apply directly over the bug bite. The microlift technology helps drain the "
            "biochemicals that cause itching. Leave on for 2-8 hours. Works best when "
            "applied immediately after bite."
        ),
        "variants": [
            {"id": "gid://shopify/ProductVariant/8005A", "title": "27-Pack", "price": "14.99"},
            {"id": "gid://shopify/ProductVariant/8005B", "title": "60-Pack", "price": "24.99"},
        ],
    },
    "gid://shopify/Product/8006": {
        "id": "gid://shopify/Product/8006",
        "title": "NatPat Family Bundle — Sleep + Buzz + Focus",
        "handle": "family-bundle",
        "description": "Our best-selling bundle with SleepyPatch, BuzzPatch, and FocusPatch. Save 20%!",
        "price": "65.99",
        "currency": "USD",
        "tags": ["bundle", "sleep", "mosquito", "focus", "value"],
        "usage_guide": "See individual product instructions for each patch type.",
        "variants": [
            {"id": "gid://shopify/ProductVariant/8006A", "title": "Bundle (24-Pack each)", "price": "65.99"},
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# COLLECTIONS
# ═══════════════════════════════════════════════════════════════════════════════

COLLECTIONS = [
    {"id": "gid://shopify/Collection/1001", "title": "Sleep Solutions", "handle": "sleep-solutions"},
    {"id": "gid://shopify/Collection/1002", "title": "Bug Protection", "handle": "bug-protection"},
    {"id": "gid://shopify/Collection/1003", "title": "Focus & Learning", "handle": "focus-learning"},
    {"id": "gid://shopify/Collection/1004", "title": "Calm & Wellness", "handle": "calm-wellness"},
    {"id": "gid://shopify/Collection/1005", "title": "Best Sellers", "handle": "best-sellers"},
    {"id": "gid://shopify/Collection/1006", "title": "Value Bundles", "handle": "value-bundles"},
]

# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE
# ═══════════════════════════════════════════════════════════════════════════════

KNOWLEDGE_BASE = {
    "sleep": {
        "faqs": [
            {"question": "How many SleepyPatch should I use?", "answer": "We recommend 1-2 patches per night, placed on pajamas or pillow about 30 minutes before bedtime."},
            {"question": "How long does it take to work?", "answer": "Most kids notice a difference within the first 3-5 nights of consistent use. Give it at least a week for full effect."},
            {"question": "Can I use SleepyPatch on skin?", "answer": "SleepyPatch should be placed on clothing or pillow, not directly on skin."},
        ],
        "pdfs": [],
        "blogArticles": [
            {"title": "5 Tips for Better Kids' Sleep with SleepyPatch", "url": "https://natpat.com/blog/sleep-tips"},
            {"title": "Essential Oils and Sleep: The Science", "url": "https://natpat.com/blog/essential-oils-sleep"},
        ],
        "pages": [
            {"title": "SleepyPatch Usage Guide", "url": "https://natpat.com/pages/sleepypatch-guide"},
        ],
    },
    "focus": {
        "faqs": [
            {"question": "When should I apply FocusPatch?", "answer": "Apply 15 minutes before focus is needed — before homework, tests, or activities."},
            {"question": "How many patches at once?", "answer": "One patch is usually enough. Place near the collar for best effect."},
            {"question": "How long do FocusPatch last?", "answer": "Each FocusPatch lasts 6-8 hours. Use consistently for 5-7 days for best results."},
        ],
        "pdfs": [],
        "blogArticles": [
            {"title": "Helping Kids Focus Naturally", "url": "https://natpat.com/blog/kids-focus"},
        ],
        "pages": [],
    },
    "mosquito": {
        "faqs": [
            {"question": "How many BuzzPatch do I need?", "answer": "Use 1-2 patches for mild exposure. For heavy mosquito areas (camping, hiking), use 3-4 patches spread across clothing."},
            {"question": "Does BuzzPatch work on ticks?", "answer": "BuzzPatch is primarily designed for mosquitoes. For tick protection, consult your pediatrician about additional measures."},
        ],
        "pdfs": [],
        "blogArticles": [
            {"title": "Natural Bug Protection for Summer", "url": "https://natpat.com/blog/summer-protection"},
        ],
        "pages": [],
    },
    "itch": {
        "faqs": [
            {"question": "How does MagicPatch work?", "answer": "MagicPatch uses microlift technology to drain the biochemicals that cause itching from bug bites."},
            {"question": "How soon should I apply MagicPatch?", "answer": "Apply immediately after a bug bite for best results. The patch works for 2-8 hours."},
        ],
        "pdfs": [],
        "blogArticles": [],
        "pages": [],
    },
    "general": {
        "faqs": [
            {"question": "Are NatPat patches safe for kids?", "answer": "Yes! All our patches use natural essential oils and are designed to be placed on clothing, not skin. They're safe for kids 2 and up."},
            {"question": "What's your return policy?", "answer": "We offer store credit with a 10% bonus, or a cash refund as a last resort. We always try to make things right!"},
            {"question": "How long do patches last?", "answer": "Most patches are effective for 6-12 hours depending on the product."},
        ],
        "pdfs": [],
        "blogArticles": [],
        "pages": [
            {"title": "FAQ", "url": "https://natpat.com/pages/faq"},
            {"title": "Shipping Policy", "url": "https://natpat.com/pages/shipping"},
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════════

CUSTOMERS: dict[str, dict] = {
    "gid://shopify/Customer/7424155189325": {
        "id": "gid://shopify/Customer/7424155189325",
        "email": "sarah@example.com",
        "firstName": "Sarah",
        "lastName": "Jones",
        "storeCreditBalance": {"amount": "0.00", "currencyCode": "USD"},
    },
    "gid://shopify/Customer/7424155189326": {
        "id": "gid://shopify/Customer/7424155189326",
        "email": "mike@example.com",
        "firstName": "Mike",
        "lastName": "Chen",
        "storeCreditBalance": {"amount": "15.00", "currencyCode": "USD"},
    },
    "gid://shopify/Customer/7424155189327": {
        "id": "gid://shopify/Customer/7424155189327",
        "email": "emma@example.com",
        "firstName": "Emma",
        "lastName": "Wilson",
        "storeCreditBalance": {"amount": "0.00", "currencyCode": "USD"},
    },
    "gid://shopify/Customer/7424155189328": {
        "id": "gid://shopify/Customer/7424155189328",
        "email": "test@example.com",
        "firstName": "Test",
        "lastName": "User",
        "storeCreditBalance": {"amount": "0.00", "currencyCode": "USD"},
    },
}

EMAIL_TO_CUSTOMER: dict[str, str] = {
    c["email"]: cid for cid, c in CUSTOMERS.items()
}

# ═══════════════════════════════════════════════════════════════════════════════
# ORDERS — Seed data aligned 1:1 with test scenarios
# ═══════════════════════════════════════════════════════════════════════════════
#
# Test scenario order mapping:
#   #43189 → gid://shopify/Order/5531567751245  Sarah, FULFILLED, main test order
#   #43200 → gid://shopify/Order/5531567751246  Sarah, UNFULFILLED, today
#   #43215 → gid://shopify/Order/5531567751247  Sarah, FULFILLED, recent
#   #51234 → gid://shopify/Order/5531567751248  Sarah, DELIVERED, 14d ago
#   #43190 → gid://shopify/Order/5531567751249  Sarah, CANCELLED
#
# NOTE: Many test scenarios override responses via mock_tool_responses.
# This seed data serves as the DEFAULT when no override is provided.
# ═══════════════════════════════════════════════════════════════════════════════

_SARAH_ADDRESS = {
    "firstName": "Sarah", "lastName": "Jones", "company": "",
    "address1": "123 Oak Street", "address2": "Apt 4B",
    "city": "Austin", "provinceCode": "TX", "country": "US",
    "zip": "78701", "phone": "+15125551234",
}

_MIKE_ADDRESS = {
    "firstName": "Mike", "lastName": "Chen", "company": "",
    "address1": "456 Pine Avenue", "address2": "",
    "city": "San Francisco", "provinceCode": "CA", "country": "US",
    "zip": "94102", "phone": "+14155559876",
}

_EMMA_ADDRESS = {
    "firstName": "Emma", "lastName": "Wilson", "company": "",
    "address1": "789 Elm Boulevard", "address2": "Suite 100",
    "city": "Portland", "provinceCode": "OR", "country": "US",
    "zip": "97201", "phone": "+15035557890",
}

_INITIAL_ORDERS: list[dict] = [
    # ── #43189 — Sarah's main order (FULFILLED, 10 days ago) ─────────────
    {
        "id": "gid://shopify/Order/5531567751245",
        "name": "#43189",
        "email": "sarah@example.com",
        "customerId": "gid://shopify/Customer/7424155189325",
        "createdAt": _10_days_ago,
        "status": "FULFILLED",
        "fulfillmentStatus": "FULFILLED",
        "financialStatus": "PAID",
        "trackingUrl": "https://tracking.example.com/NATPAT2026ABC",
        "trackingNumber": "NATPAT2026ABC",
        "totalPrice": "54.98",
        "currency": "USD",
        "tags": [],
        "shippingAddress": copy.deepcopy(_SARAH_ADDRESS),
        "lineItems": [
            {
                "title": "SleepyPatch — 24-Pack", "quantity": 1, "price": "29.99",
                "productId": "gid://shopify/Product/8001",
                "variantId": "gid://shopify/ProductVariant/8001A",
            },
            {
                "title": "BuzzPatch — 24-Pack", "quantity": 1, "price": "24.99",
                "productId": "gid://shopify/Product/8002",
                "variantId": "gid://shopify/ProductVariant/8002A",
            },
        ],
        "refunded": False,
        "cancelledAt": None,
    },
    # ── #43200 — Sarah's today order (UNFULFILLED) ───────────────────────
    {
        "id": "gid://shopify/Order/5531567751246",
        "name": "#43200",
        "email": "sarah@example.com",
        "customerId": "gid://shopify/Customer/7424155189325",
        "createdAt": _today_morning,
        "status": "UNFULFILLED",
        "fulfillmentStatus": "UNFULFILLED",
        "financialStatus": "PAID",
        "trackingUrl": None,
        "trackingNumber": None,
        "totalPrice": "24.99",
        "currency": "USD",
        "tags": [],
        "shippingAddress": copy.deepcopy(_SARAH_ADDRESS),
        "lineItems": [
            {
                "title": "BuzzPatch — 24-Pack", "quantity": 1, "price": "24.99",
                "productId": "gid://shopify/Product/8002",
                "variantId": "gid://shopify/ProductVariant/8002A",
            },
        ],
        "refunded": False,
        "cancelledAt": None,
    },
    # ── #43215 — Sarah's recent order (FULFILLED, 3 days ago) ────────────
    {
        "id": "gid://shopify/Order/5531567751247",
        "name": "#43215",
        "email": "sarah@example.com",
        "customerId": "gid://shopify/Customer/7424155189325",
        "createdAt": _3_days_ago,
        "status": "FULFILLED",
        "fulfillmentStatus": "FULFILLED",
        "financialStatus": "PAID",
        "trackingUrl": "https://tracking.example.com/NATPAT2026DEF",
        "trackingNumber": "NATPAT2026DEF",
        "totalPrice": "27.99",
        "currency": "USD",
        "tags": [],
        "shippingAddress": copy.deepcopy(_SARAH_ADDRESS),
        "lineItems": [
            {
                "title": "FocusPatch — 24-Pack", "quantity": 1, "price": "27.99",
                "productId": "gid://shopify/Product/8003",
                "variantId": "gid://shopify/ProductVariant/8003A",
            },
        ],
        "refunded": False,
        "cancelledAt": None,
    },
    # ── #51234 — Sarah's delivered order (14 days ago) ───────────────────
    {
        "id": "gid://shopify/Order/5531567751248",
        "name": "#51234",
        "email": "sarah@example.com",
        "customerId": "gid://shopify/Customer/7424155189325",
        "createdAt": _14_days_ago,
        "status": "DELIVERED",
        "fulfillmentStatus": "FULFILLED",
        "financialStatus": "PAID",
        "trackingUrl": "https://tracking.example.com/NATPAT2026GHI",
        "trackingNumber": "NATPAT2026GHI",
        "totalPrice": "65.99",
        "currency": "USD",
        "tags": [],
        "shippingAddress": copy.deepcopy(_SARAH_ADDRESS),
        "lineItems": [
            {
                "title": "NatPat Family Bundle — Sleep + Buzz + Focus", "quantity": 1, "price": "65.99",
                "productId": "gid://shopify/Product/8006",
                "variantId": "gid://shopify/ProductVariant/8006A",
            },
        ],
        "refunded": False,
        "cancelledAt": None,
    },
    # ── #43190 — Sarah's CANCELLED order ─────────────────────────────────
    {
        "id": "gid://shopify/Order/5531567751249",
        "name": "#43190",
        "email": "sarah@example.com",
        "customerId": "gid://shopify/Customer/7424155189325",
        "createdAt": _14_days_ago,
        "status": "CANCELLED",
        "fulfillmentStatus": "UNFULFILLED",
        "financialStatus": "REFUNDED",
        "trackingUrl": None,
        "trackingNumber": None,
        "totalPrice": "14.99",
        "currency": "USD",
        "tags": ["Cancelled - Customer Request"],
        "shippingAddress": copy.deepcopy(_SARAH_ADDRESS),
        "lineItems": [
            {
                "title": "MagicPatch — 27-Pack", "quantity": 1, "price": "14.99",
                "productId": "gid://shopify/Product/8005",
                "variantId": "gid://shopify/ProductVariant/8005A",
            },
        ],
        "refunded": True,
        "cancelledAt": (_now - timedelta(days=13)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    # ── Mike's orders ────────────────────────────────────────────────────
    {
        "id": "gid://shopify/Order/5531567752001",
        "name": "#44001",
        "email": "mike@example.com",
        "customerId": "gid://shopify/Customer/7424155189326",
        "createdAt": _7_days_ago,
        "status": "FULFILLED",
        "fulfillmentStatus": "FULFILLED",
        "financialStatus": "PAID",
        "trackingUrl": "https://tracking.example.com/NATPAT2026JKL",
        "trackingNumber": "NATPAT2026JKL",
        "totalPrice": "29.99",
        "currency": "USD",
        "tags": [],
        "shippingAddress": copy.deepcopy(_MIKE_ADDRESS),
        "lineItems": [
            {
                "title": "SleepyPatch — 24-Pack", "quantity": 1, "price": "29.99",
                "productId": "gid://shopify/Product/8001",
                "variantId": "gid://shopify/ProductVariant/8001A",
            },
        ],
        "refunded": False,
        "cancelledAt": None,
    },
    {
        "id": "gid://shopify/Order/5531567752002",
        "name": "#44002",
        "email": "mike@example.com",
        "customerId": "gid://shopify/Customer/7424155189326",
        "createdAt": _yesterday,
        "status": "UNFULFILLED",
        "fulfillmentStatus": "UNFULFILLED",
        "financialStatus": "PAID",
        "trackingUrl": None,
        "trackingNumber": None,
        "totalPrice": "27.99",
        "currency": "USD",
        "tags": [],
        "shippingAddress": copy.deepcopy(_MIKE_ADDRESS),
        "lineItems": [
            {
                "title": "FocusPatch — 24-Pack", "quantity": 1, "price": "27.99",
                "productId": "gid://shopify/Product/8003",
                "variantId": "gid://shopify/ProductVariant/8003A",
            },
        ],
        "refunded": False,
        "cancelledAt": None,
    },
    # Mike's partially fulfilled order
    {
        "id": "gid://shopify/Order/5531567752003",
        "name": "#44003",
        "email": "mike@example.com",
        "customerId": "gid://shopify/Customer/7424155189326",
        "createdAt": _3_days_ago,
        "status": "PARTIALLY_FULFILLED",
        "fulfillmentStatus": "PARTIALLY_FULFILLED",
        "financialStatus": "PAID",
        "trackingUrl": "https://tracking.example.com/NATPAT2026MNO",
        "trackingNumber": "NATPAT2026MNO",
        "totalPrice": "84.98",
        "currency": "USD",
        "tags": [],
        "shippingAddress": copy.deepcopy(_MIKE_ADDRESS),
        "lineItems": [
            {
                "title": "SleepyPatch — 24-Pack", "quantity": 1, "price": "29.99",
                "productId": "gid://shopify/Product/8001",
                "variantId": "gid://shopify/ProductVariant/8001A",
                "fulfillmentStatus": "FULFILLED",
            },
            {
                "title": "BuzzPatch — 60-Pack", "quantity": 1, "price": "49.99",
                "productId": "gid://shopify/Product/8002",
                "variantId": "gid://shopify/ProductVariant/8002B",
                "fulfillmentStatus": "UNFULFILLED",
            },
        ],
        "refunded": False,
        "cancelledAt": None,
    },
    # ── Emma's orders ────────────────────────────────────────────────────
    {
        "id": "gid://shopify/Order/5531567753001",
        "name": "#45001",
        "email": "emma@example.com",
        "customerId": "gid://shopify/Customer/7424155189327",
        "createdAt": _7_days_ago,
        "status": "DELIVERED",
        "fulfillmentStatus": "FULFILLED",
        "financialStatus": "PAID",
        "trackingUrl": "https://tracking.example.com/NATPAT2026PQR",
        "trackingNumber": "NATPAT2026PQR",
        "totalPrice": "29.99",
        "currency": "USD",
        "tags": [],
        "shippingAddress": copy.deepcopy(_EMMA_ADDRESS),
        "lineItems": [
            {
                "title": "ZenPatch — 24-Pack", "quantity": 1, "price": "29.99",
                "productId": "gid://shopify/Product/8004",
                "variantId": "gid://shopify/ProductVariant/8004A",
            },
        ],
        "refunded": False,
        "cancelledAt": None,
    },
    {
        "id": "gid://shopify/Order/5531567753002",
        "name": "#45002",
        "email": "emma@example.com",
        "customerId": "gid://shopify/Customer/7424155189327",
        "createdAt": _3_days_ago,
        "status": "FULFILLED",
        "fulfillmentStatus": "FULFILLED",
        "financialStatus": "PAID",
        "trackingUrl": "https://tracking.example.com/NATPAT2026STU",
        "trackingNumber": "NATPAT2026STU",
        "totalPrice": "49.99",
        "currency": "USD",
        "tags": [],
        "shippingAddress": copy.deepcopy(_EMMA_ADDRESS),
        "lineItems": [
            {
                "title": "BuzzPatch — 60-Pack", "quantity": 1, "price": "49.99",
                "productId": "gid://shopify/Product/8002",
                "variantId": "gid://shopify/ProductVariant/8002B",
            },
        ],
        "refunded": False,
        "cancelledAt": None,
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

_INITIAL_SUBSCRIPTIONS: dict[str, dict] = {
    "sarah@example.com": {
        "subscriptionId": "sub_SP_sarah_001",
        "email": "sarah@example.com",
        "status": "ACTIVE",
        "productTitle": "SleepyPatch — 60-Pack",
        "productId": "gid://shopify/Product/8001",
        "frequency": "Every 30 days",
        "nextBillingDate": (_now + timedelta(days=12)).strftime("%Y-%m-%d"),
        "price": "53.99",
        "currency": "USD",
        "createdAt": (_now - timedelta(days=90)).strftime("%Y-%m-%d"),
        "pausedUntil": None,
        "cancelledAt": None,
        "cancellationReasons": [],
    },
    "mike@example.com": {
        "subscriptionId": "sub_FP_mike_002",
        "email": "mike@example.com",
        "status": "ACTIVE",
        "productTitle": "FocusPatch — 24-Pack",
        "productId": "gid://shopify/Product/8003",
        "frequency": "Every 30 days",
        "nextBillingDate": (_now + timedelta(days=5)).strftime("%Y-%m-%d"),
        "price": "25.19",
        "currency": "USD",
        "createdAt": (_now - timedelta(days=60)).strftime("%Y-%m-%d"),
        "pausedUntil": None,
        "cancelledAt": None,
        "cancellationReasons": [],
    },
    "emma@example.com": {
        "subscriptionId": "sub_ZP_emma_003",
        "email": "emma@example.com",
        "status": "CANCELLED",
        "productTitle": "ZenPatch — 24-Pack",
        "productId": "gid://shopify/Product/8004",
        "frequency": "Every 30 days",
        "nextBillingDate": None,
        "price": "26.99",
        "currency": "USD",
        "createdAt": (_now - timedelta(days=120)).strftime("%Y-%m-%d"),
        "cancelledAt": (_now - timedelta(days=10)).strftime("%Y-%m-%d"),
        "pausedUntil": None,
        "cancellationReasons": ["No longer needed"],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# STORE CREDITS & DISCOUNT CODES
# ═══════════════════════════════════════════════════════════════════════════════

_INITIAL_STORE_CREDITS: dict[str, dict] = {
    "gid://shopify/Customer/7424155189325": {"amount": "0.00", "currencyCode": "USD"},
    "gid://shopify/Customer/7424155189326": {"amount": "15.00", "currencyCode": "USD"},
    "gid://shopify/Customer/7424155189327": {"amount": "0.00", "currencyCode": "USD"},
    "gid://shopify/Customer/7424155189328": {"amount": "0.00", "currencyCode": "USD"},
}

_INITIAL_DISCOUNT_CODES: list[dict] = []


# ═══════════════════════════════════════════════════════════════════════════════
# MUTABLE STATE
# ═══════════════════════════════════════════════════════════════════════════════

class MockState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.orders: list[dict] = copy.deepcopy(_INITIAL_ORDERS)
        self.subscriptions: dict[str, dict] = copy.deepcopy(_INITIAL_SUBSCRIPTIONS)
        self.store_credits: dict[str, dict] = copy.deepcopy(_INITIAL_STORE_CREDITS)
        self.discount_codes: list[dict] = copy.deepcopy(_INITIAL_DISCOUNT_CODES)
        self.returns: list[dict] = []
        self.draft_orders: list[dict] = []

    def find_order_by_name(self, name: str) -> Optional[dict]:
        """Find order by name. Accepts #43189, 43189, etc."""
        clean = name.strip().lstrip("#")
        for o in self.orders:
            if o["name"].lstrip("#") == clean:
                return o
        return None

    def find_order_by_gid(self, gid: str) -> Optional[dict]:
        for o in self.orders:
            if o["id"] == gid:
                return o
        return None

    def find_orders_by_email(self, email: str) -> list[dict]:
        return [o for o in self.orders if o["email"].lower() == email.lower()]


STATE = MockState()


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY
# ═══════════════════════════════════════════════════════════════════════════════

def _ok(data: Any = None) -> dict:
    if data is not None:
        return {"success": True, "data": data}
    return {"success": True}

def _fail(error: str) -> dict:
    return {"success": False, "error": error}

def _gen_code(prefix: str = "DISCOUNT_LF_") -> str:
    return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

def _order_summary(o: dict) -> dict:
    """Summary for list views — includes totalPrice and lineItems for agent decisions."""
    return {
        "id": o["id"],
        "name": o["name"],
        "createdAt": o["createdAt"],
        "status": o["status"],
        "trackingUrl": o.get("trackingUrl"),
        "totalPrice": o["totalPrice"],
        "currency": o.get("currency", "USD"),
        "lineItems": [
            {"title": li["title"], "quantity": li["quantity"], "price": li["price"]}
            for li in o.get("lineItems", [])
        ],
    }

def _order_detail(o: dict) -> dict:
    """Full detail for single-order views."""
    return {
        "id": o["id"],
        "name": o["name"],
        "createdAt": o["createdAt"],
        "status": o["status"],
        "fulfillmentStatus": o.get("fulfillmentStatus", o["status"]),
        "financialStatus": o.get("financialStatus", "PAID"),
        "trackingUrl": o.get("trackingUrl"),
        "trackingNumber": o.get("trackingNumber"),
        "totalPrice": o["totalPrice"],
        "currency": o.get("currency", "USD"),
        "tags": o.get("tags", []),
        "shippingAddress": o.get("shippingAddress", {}),
        "lineItems": o.get("lineItems", []),
        "refunded": o.get("refunded", False),
        "cancelledAt": o.get("cancelledAt"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS — POST /hackhaton/{tool_name}
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1) shopify_get_order_details ─────────────────────────────────────────────
@app.post("/hackhaton/get_order_details")
async def get_order_details(request: Request):
    body = await request.json()
    order_id = body.get("orderId", "")
    if not order_id:
        return _fail("orderId is required")

    # Try name lookup first (#43189, 43189), then GID lookup
    order = STATE.find_order_by_name(order_id)
    if not order:
        order = STATE.find_order_by_gid(order_id)
    if not order:
        return _fail(f"Order not found: {order_id}")

    return _ok(_order_detail(order))


# ── 2) shopify_get_customer_orders ───────────────────────────────────────────
@app.post("/hackhaton/get_customer_orders")
async def get_customer_orders(request: Request):
    body = await request.json()
    email = body.get("email", "")
    limit = min(int(body.get("limit", 10)), 250)
    after_cursor = body.get("after")  # cursor-based pagination support

    if not email:
        return _fail("email is required")

    orders = STATE.find_orders_by_email(email)
    if not orders:
        return _fail(f"No orders found for email: {email}")

    # Sort newest first
    orders.sort(key=lambda o: o["createdAt"], reverse=True)

    # Cursor-based pagination: 'after' is an order GID
    start_idx = 0
    if after_cursor and after_cursor not in ("null", "None", ""):
        for i, o in enumerate(orders):
            if o["id"] == after_cursor:
                start_idx = i + 1
                break

    page = orders[start_idx:start_idx + limit]
    has_next = (start_idx + limit) < len(orders)

    return _ok({
        "orders": [_order_summary(o) for o in page],
        "hasNextPage": has_next,
        "endCursor": page[-1]["id"] if page else None,
    })


# ── 3) shopify_get_product_details ───────────────────────────────────────────
@app.post("/hackhaton/get_product_details")
async def get_product_details(request: Request):
    body = await request.json()
    query_type = body.get("queryType", "")
    query_key = body.get("queryKey", "")

    if not query_key:
        return _fail("queryKey is required")

    results = []
    if query_type == "id":
        p = PRODUCTS.get(query_key)
        if p:
            results.append(p)
    elif query_type == "name":
        kl = query_key.lower()
        for p in PRODUCTS.values():
            if kl in p["title"].lower() or kl in p["handle"].lower():
                results.append(p)
    elif query_type == "key feature":
        kl = query_key.lower()
        for p in PRODUCTS.values():
            if any(kl in tag for tag in p["tags"]) or kl in p["description"].lower():
                results.append(p)
    else:
        # Fallback: search across all fields
        kl = query_key.lower()
        for p in PRODUCTS.values():
            if (kl in p["title"].lower() or kl in p["handle"].lower()
                    or any(kl in tag for tag in p["tags"])
                    or kl in p["description"].lower()):
                results.append(p)

    if not results:
        return _fail(f"Product not found for {query_type}='{query_key}'")

    return _ok([
        {"id": p["id"], "title": p["title"], "handle": p["handle"],
         "description": p["description"], "price": p["price"],
         "usage_guide": p.get("usage_guide", ""), "variants": p.get("variants", [])}
        for p in results
    ])


# ── 4) shopify_get_product_recommendations ───────────────────────────────────
@app.post("/hackhaton/get_product_recommendations")
async def get_product_recommendations(request: Request):
    body = await request.json()
    query_keys = body.get("queryKeys", [])
    if not query_keys:
        return _fail("queryKeys is required")

    results = []
    seen = set()
    keywords = [k.lower() for k in query_keys]

    for p in PRODUCTS.values():
        score = 0
        for kw in keywords:
            if kw in p["title"].lower(): score += 3
            if any(kw in tag for tag in p["tags"]): score += 2
            if kw in p["description"].lower(): score += 1
        if score > 0 and p["id"] not in seen:
            results.append((score, p))
            seen.add(p["id"])

    results.sort(key=lambda x: x[0], reverse=True)

    if not results:
        fallback = list(PRODUCTS.values())[:3]
        return _ok([{"id": p["id"], "title": p["title"], "handle": p["handle"]} for p in fallback])

    return _ok([
        {"id": p["id"], "title": p["title"], "handle": p["handle"],
         "description": p["description"], "price": p["price"]}
        for _, p in results[:5]
    ])


# ── 5) shopify_get_related_knowledge_source ──────────────────────────────────
@app.post("/hackhaton/get_related_knowledge_source")
async def get_related_knowledge_source(request: Request):
    body = await request.json()
    question = body.get("question", "").lower()
    product_id = body.get("specificToProductId")

    best_category = "general"
    best_score = 0
    category_keywords = {
        "sleep": ["sleep", "sleepy", "bedtime", "night", "insomnia", "tired"],
        "focus": ["focus", "concentration", "school", "homework", "attention", "adhd", "concentrate"],
        "mosquito": ["mosquito", "bug", "bite", "buzz", "outdoor", "repel", "bitten"],
        "itch": ["itch", "sting", "magic", "relief"],
    }

    for cat, kws in category_keywords.items():
        score = sum(1 for kw in kws if kw in question)
        if score > best_score:
            best_score = score
            best_category = cat

    if product_id:
        product = PRODUCTS.get(product_id)
        if product:
            for tag in product["tags"]:
                for cat, kws in category_keywords.items():
                    if tag in kws:
                        best_category = cat
                        break

    kb = KNOWLEDGE_BASE.get(best_category, KNOWLEDGE_BASE["general"])
    return _ok({
        "faqs": kb.get("faqs", []),
        "pdfs": kb.get("pdfs", []),
        "blogArticles": kb.get("blogArticles", []),
        "pages": kb.get("pages", []),
    })


# ── 6) shopify_get_collection_recommendations ───────────────────────────────
@app.post("/hackhaton/get_collection_recommendations")
async def get_collection_recommendations(request: Request):
    body = await request.json()
    query_keys = body.get("queryKeys", [])
    keywords = [k.lower() for k in query_keys]

    results = [c for c in COLLECTIONS
               if any(kw in c["title"].lower() or kw in c["handle"].lower() for kw in keywords)]
    if not results:
        results = COLLECTIONS[:3]

    return _ok(results)


# ── 7) shopify_cancel_order ──────────────────────────────────────────────────
@app.post("/hackhaton/cancel_order")
async def cancel_order(request: Request):
    body = await request.json()
    order_id = body.get("orderId", "")

    # Accept all spec params gracefully (7 required by spec)
    reason = body.get("reason", "CUSTOMER")
    notify_customer = body.get("notifyCustomer", True)
    restock = body.get("restock", True)
    staff_note = body.get("staffNote", "")
    refund_mode = body.get("refundMode", "ORIGINAL")
    store_credit = body.get("storeCredit", {"expiresAt": None})

    if not order_id:
        return _fail("orderId is required. Please provide a valid order ID.")

    order = STATE.find_order_by_gid(order_id)
    if not order:
        # If they passed order name instead of GID, give helpful error
        order = STATE.find_order_by_name(order_id)
        if order:
            return _fail(
                f"Order ID must be a Shopify GID (e.g. gid://shopify/Order/...), "
                f"not an order number. Use get_order_details first to retrieve the GID."
            )
        return _fail(f"Order not found: {order_id}")

    if order["status"] == "CANCELLED":
        return _fail(f"Order {order['name']} is already cancelled (cancelled at {order.get('cancelledAt', 'unknown')})")

    if order["status"] in ("FULFILLED", "DELIVERED"):
        return _fail(f"Cannot cancel order {order['name']} — it has already been fulfilled/shipped. Consider a return or store credit instead.")

    if order["status"] == "PARTIALLY_FULFILLED":
        return _fail(f"Cannot cancel order {order['name']} — it is partially fulfilled. Manual review required.")

    if order.get("refunded"):
        return _fail(f"Order {order['name']} has already been refunded.")

    # Perform cancellation
    order["status"] = "CANCELLED"
    order["fulfillmentStatus"] = "UNFULFILLED"
    order["financialStatus"] = "REFUNDED"
    order["cancelledAt"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    order["refunded"] = True

    if staff_note:
        order["tags"].append(f"Staff Note: {staff_note}")
    if reason:
        order["tags"].append(f"Cancel Reason: {reason}")

    return _ok()


# ── 8) shopify_refund_order ──────────────────────────────────────────────────
@app.post("/hackhaton/refund_order")
async def refund_order(request: Request):
    body = await request.json()
    order_id = body.get("orderId", "")
    refund_method = body.get("refundMethod", "ORIGINAL_PAYMENT_METHODS")

    if not order_id:
        return _fail("orderId is required")

    order = STATE.find_order_by_gid(order_id)
    if not order:
        return _fail(f"Order not found: {order_id}")

    if order.get("refunded"):
        return _fail(f"Order {order['name']} has already been refunded.")

    if order["status"] == "CANCELLED" and order.get("financialStatus") == "REFUNDED":
        return _fail(f"Order {order['name']} is cancelled and already refunded.")

    order["refunded"] = True
    order["financialStatus"] = "REFUNDED"
    order["tags"].append(f"Refunded via {refund_method}")

    return _ok()


# ── 9) shopify_create_store_credit ───────────────────────────────────────────
@app.post("/hackhaton/create_store_credit")
async def create_store_credit(request: Request):
    body = await request.json()
    customer_id = body.get("id", "")
    credit_amount = body.get("creditAmount", {})
    expires_at = body.get("expiresAt")  # Accept per spec (nullable)

    if not customer_id:
        return _fail("Customer ID is required")
    if customer_id not in STATE.store_credits:
        return _fail(f"Customer not found: {customer_id}")

    amount_str = credit_amount.get("amount", "0")
    currency = credit_amount.get("currencyCode", "USD")

    try:
        amount = float(amount_str)
    except (ValueError, TypeError):
        return _fail(f"Invalid credit amount: {amount_str}")

    if amount <= 0:
        return _fail("Credit amount must be positive")

    current = float(STATE.store_credits[customer_id]["amount"])
    new_balance = round(current + amount, 2)
    STATE.store_credits[customer_id]["amount"] = f"{new_balance:.2f}"

    sc_account_id = f"gid://shopify/StoreCreditAccount/{abs(hash(customer_id)) % 100000}"

    return _ok({
        "storeCreditAccountId": sc_account_id,
        "credited": {"amount": f"{amount:.2f}", "currencyCode": currency},
        "newBalance": {"amount": f"{new_balance:.2f}", "currencyCode": currency},
    })


# ── 10) shopify_add_tags ────────────────────────────────────────────────────
@app.post("/hackhaton/add_tags")
async def add_tags(request: Request):
    body = await request.json()
    resource_id = body.get("id", "")
    tags = body.get("tags", [])

    if not resource_id:
        return _fail("Resource ID is required")
    if not tags:
        return _fail("Tags list is required and must not be empty")

    # Try to find the resource: order, customer, or product
    order = STATE.find_order_by_gid(resource_id)
    if order:
        order["tags"] = list(set(order.get("tags", []) + tags))
        return _ok()

    if resource_id in CUSTOMERS:
        return _ok()
    if resource_id in PRODUCTS:
        return _ok()

    # Also check draft orders
    for d in STATE.draft_orders:
        if d["id"] == resource_id:
            return _ok()

    return _fail(f"Resource not found: {resource_id}")


# ── 11) shopify_create_discount_code ─────────────────────────────────────────
@app.post("/hackhaton/create_discount_code")
async def create_discount_code(request: Request):
    body = await request.json()
    disc_type = body.get("type", "percentage")
    value = body.get("value", 0.10)
    duration = body.get("duration", 48)
    product_ids = body.get("productIds", [])

    code = _gen_code()

    STATE.discount_codes.append({
        "code": code,
        "type": disc_type,
        "value": value,
        "duration": duration,
        "productIds": product_ids,
        "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expiresAt": (datetime.utcnow() + timedelta(hours=duration)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })

    return _ok({"code": code})


# ── 12) shopify_update_order_shipping_address ────────────────────────────────
@app.post("/hackhaton/update_order_shipping_address")
async def update_order_shipping_address(request: Request):
    body = await request.json()
    order_id = body.get("orderId", "")
    new_address = body.get("shippingAddress", {})

    if not order_id:
        return _fail("orderId is required")

    order = STATE.find_order_by_gid(order_id)
    if not order:
        return _fail(f"Order not found: {order_id}")

    if order["status"] in ("FULFILLED", "DELIVERED"):
        return _fail(f"Cannot change address — order {order['name']} has already been shipped.")

    if order["status"] == "CANCELLED":
        return _fail(f"Cannot update address for cancelled order {order['name']}")

    # Validate required fields per spec
    required_fields = ["firstName", "lastName", "address1", "city", "provinceCode", "country", "zip", "phone"]
    missing = [f for f in required_fields if not new_address.get(f)]
    if missing:
        return _fail(f"Missing required address fields: {', '.join(missing)}")

    # Zip code validation
    zip_code = new_address.get("zip", "")
    country = new_address.get("country", "").upper()
    if country in ("US", "USA"):
        zip_clean = zip_code.replace("-", "").replace(" ", "")
        if len(zip_clean) not in (5, 9):
            return _fail(f"Invalid US ZIP code: {zip_code}")

    if country in ("CA", "CAN"):
        if len(zip_code.replace(" ", "")) != 6:
            return _fail(f"Invalid Canadian postal code: {zip_code}")

    order["shippingAddress"] = new_address
    return _ok()


# ── 13) shopify_create_return ────────────────────────────────────────────────
@app.post("/hackhaton/create_return")
async def create_return(request: Request):
    body = await request.json()
    order_id = body.get("orderId", "")
    if not order_id:
        return _fail("orderId is required")

    order = STATE.find_order_by_gid(order_id)
    if not order:
        return _fail(f"Order not found: {order_id}")

    if order["status"] == "CANCELLED":
        return _fail(f"Cannot create return for cancelled order {order['name']}")

    if order["status"] == "UNFULFILLED":
        return _fail(f"Cannot create return for unfulfilled order {order['name']}. Order hasn't shipped yet — consider cancellation instead.")

    return_id = f"gid://shopify/Return/{uuid.uuid4().hex[:12]}"
    STATE.returns.append({
        "id": return_id, "orderId": order_id, "orderName": order["name"],
        "status": "REQUESTED", "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    return _ok({"returnId": return_id})


# ── 14) shopify_create_draft_order ───────────────────────────────────────────
@app.post("/hackhaton/create_draft_order")
async def create_draft_order(request: Request):
    body = await request.json()
    draft_id = f"gid://shopify/DraftOrder/{uuid.uuid4().hex[:12]}"
    STATE.draft_orders.append({
        "id": draft_id,
        "status": "OPEN",
        "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "body": body,  # Store full request body for traceability
    })
    return _ok({"draftOrderId": draft_id})


# ═══════════════════════════════════════════════════════════════════════════════
# SKIO ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── 15) skio_get_subscription_status ─────────────────────────────────────────
@app.post("/hackhaton/get-subscription-status")
async def get_subscription_status(request: Request):
    body = await request.json()
    email = body.get("email", "").lower()
    if not email:
        return _fail("email is required")

    sub = STATE.subscriptions.get(email)
    if not sub:
        return _fail("No subscription found for this email")

    if sub["status"] == "CANCELLED":
        return _fail(
            f"Failed to get subscription status. This subscription has already been cancelled"
            f" (cancelled on {sub.get('cancelledAt', 'unknown')})."
        )

    return _ok({
        "status": sub["status"],
        "subscriptionId": sub["subscriptionId"],
        "productTitle": sub["productTitle"],
        "frequency": sub["frequency"],
        "nextBillingDate": sub["nextBillingDate"],
        "price": sub["price"],
        "currency": sub["currency"],
        "pausedUntil": sub.get("pausedUntil"),
    })


# ── 16) skio_cancel_subscription ────────────────────────────────────────────
@app.post("/hackhaton/cancel-subscription")
async def cancel_subscription(request: Request):
    body = await request.json()
    sub_id = body.get("subscriptionId", "")
    reasons = body.get("cancellationReasons", [])

    if not sub_id:
        return _fail("subscriptionId is required")

    target = None
    for sub in STATE.subscriptions.values():
        if sub["subscriptionId"] == sub_id:
            target = sub
            break

    if not target:
        return _fail(f"Subscription not found: {sub_id}")

    if target["status"] == "CANCELLED":
        return _fail("This subscription has already been cancelled.")

    target["status"] = "CANCELLED"
    target["cancelledAt"] = datetime.utcnow().strftime("%Y-%m-%d")
    target["nextBillingDate"] = None
    target["cancellationReasons"] = reasons

    return _ok()


# ── 17) skio_pause_subscription ──────────────────────────────────────────────
@app.post("/hackhaton/pause-subscription")
async def pause_subscription(request: Request):
    body = await request.json()
    sub_id = body.get("subscriptionId", "")
    paused_until = body.get("pausedUntil", "")

    if not sub_id:
        return _fail("subscriptionId is required")
    if not paused_until:
        return _fail("pausedUntil date is required (YYYY-MM-DD)")

    target = None
    for sub in STATE.subscriptions.values():
        if sub["subscriptionId"] == sub_id:
            target = sub
            break

    if not target:
        return _fail(f"Subscription not found: {sub_id}")
    if target["status"] == "CANCELLED":
        return _fail("Cannot pause a cancelled subscription")
    if target["status"] == "PAUSED":
        return _fail("Subscription is already paused")

    target["status"] = "PAUSED"
    target["pausedUntil"] = paused_until
    return _ok()


# ── 18) skio_skip_next_order_subscription ────────────────────────────────────
@app.post("/hackhaton/skip-next-order-subscription")
async def skip_next_order(request: Request):
    body = await request.json()
    sub_id = body.get("subscriptionId", "")

    if not sub_id:
        return _fail("subscriptionId is required")

    target = None
    for sub in STATE.subscriptions.values():
        if sub["subscriptionId"] == sub_id:
            target = sub
            break

    if not target:
        return _fail(f"Subscription not found: {sub_id}")
    if target["status"] == "CANCELLED":
        return _fail("Cannot skip order on a cancelled subscription")

    try:
        current_date = datetime.strptime(target["nextBillingDate"], "%Y-%m-%d")
        new_date = current_date + timedelta(days=30)
        target["nextBillingDate"] = new_date.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        target["nextBillingDate"] = (_now + timedelta(days=60)).strftime("%Y-%m-%d")

    return _ok({"newNextBillingDate": target["nextBillingDate"]})


# ── 19) skio_unpause_subscription ────────────────────────────────────────────
@app.post("/hackhaton/unpause-subscription")
async def unpause_subscription(request: Request):
    body = await request.json()
    sub_id = body.get("subscriptionId", "")

    if not sub_id:
        return _fail("subscriptionId is required")

    target = None
    for sub in STATE.subscriptions.values():
        if sub["subscriptionId"] == sub_id:
            target = sub
            break

    if not target:
        return _fail(f"Subscription not found: {sub_id}")
    if target["status"] != "PAUSED":
        return _fail(f"Subscription is not paused (current status: {target['status']})")

    target["status"] = "ACTIVE"
    target["pausedUntil"] = None
    return _ok()


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok", "service": "NatPat Mock API", "version": "2.1"}

@app.post("/admin/reset")
async def reset_state():
    STATE.reset()
    return {"success": True, "message": "State reset to initial seed data"}

@app.get("/admin/state")
async def view_state():
    return {
        "orders_count": len(STATE.orders),
        "orders": [
            {"name": o["name"], "id": o["id"], "status": o["status"],
             "email": o["email"], "tags": o.get("tags", []), "refunded": o.get("refunded", False)}
            for o in STATE.orders
        ],
        "subscriptions": {
            k: {"subscriptionId": v["subscriptionId"], "status": v["status"],
                "pausedUntil": v.get("pausedUntil"), "cancelledAt": v.get("cancelledAt")}
            for k, v in STATE.subscriptions.items()
        },
        "store_credits": STATE.store_credits,
        "discount_codes_count": len(STATE.discount_codes),
        "discount_codes": STATE.discount_codes,
        "returns": STATE.returns,
    }

@app.get("/admin/orders/{email}")
async def view_orders(email: str):
    orders = STATE.find_orders_by_email(email)
    return {"email": email, "orders": [_order_detail(o) for o in orders]}

@app.post("/admin/add_customer")
async def add_customer(request: Request):
    body = await request.json()
    cid = body.get("id", f"gid://shopify/Customer/{random.randint(1000000, 9999999)}")
    email = body.get("email", "")
    CUSTOMERS[cid] = {
        "id": cid, "email": email,
        "firstName": body.get("firstName", ""), "lastName": body.get("lastName", ""),
        "storeCreditBalance": {"amount": "0.00", "currencyCode": "USD"},
    }
    STATE.store_credits[cid] = {"amount": "0.00", "currencyCode": "USD"}
    if email:
        EMAIL_TO_CUSTOMER[email] = cid
    return {"success": True, "customerId": cid}

@app.post("/admin/add_order")
async def add_order(request: Request):
    body = await request.json()
    order = {
        "id": body.get("id", f"gid://shopify/Order/{random.randint(5000000000000, 5999999999999)}"),
        "name": body.get("name", f"#{random.randint(10000, 99999)}"),
        "email": body.get("email", ""),
        "customerId": body.get("customerId", ""),
        "createdAt": body.get("createdAt", _today_str),
        "status": body.get("status", "UNFULFILLED"),
        "fulfillmentStatus": body.get("fulfillmentStatus", body.get("status", "UNFULFILLED")),
        "financialStatus": body.get("financialStatus", "PAID"),
        "trackingUrl": body.get("trackingUrl"),
        "trackingNumber": body.get("trackingNumber"),
        "totalPrice": body.get("totalPrice", "29.99"),
        "currency": body.get("currency", "USD"),
        "tags": body.get("tags", []),
        "shippingAddress": body.get("shippingAddress", {}),
        "lineItems": body.get("lineItems", []),
        "refunded": body.get("refunded", False),
        "cancelledAt": body.get("cancelledAt"),
    }
    STATE.orders.append(order)
    return {"success": True, "orderId": order["id"], "orderName": order["name"]}

@app.post("/admin/add_subscription")
async def add_subscription(request: Request):
    body = await request.json()
    email = body.get("email", "")
    STATE.subscriptions[email] = {
        "subscriptionId": body.get("subscriptionId", f"sub_{uuid.uuid4().hex[:8]}"),
        "email": email,
        "status": body.get("status", "ACTIVE"),
        "productTitle": body.get("productTitle", "SleepyPatch — 24-Pack"),
        "productId": body.get("productId", "gid://shopify/Product/8001"),
        "frequency": body.get("frequency", "Every 30 days"),
        "nextBillingDate": body.get("nextBillingDate", (_now + timedelta(days=15)).strftime("%Y-%m-%d")),
        "price": body.get("price", "29.99"),
        "currency": body.get("currency", "USD"),
        "createdAt": body.get("createdAt", _now.strftime("%Y-%m-%d")),
        "pausedUntil": None, "cancelledAt": None, "cancellationReasons": [],
    }
    return {"success": True, "subscriptionId": STATE.subscriptions[email]["subscriptionId"]}


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)