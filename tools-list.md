# Hackathon Tooling Spec

# Uniform API Response Contract

All endpoints return **HTTP 200** (hackathon simplification).

## Success (always `200`)

- **Content-Type:** `application/json`
- **Body:**
    - `success: true`
    - Optional `data` only when there’s meaningful structured output

```json
{ "success": true }

```

or

```json
{ "success": true, "data": {} }

```

## Failure (always `200`)

- **Content-Type:** `application/json`
- **Body:**
    - `success: false`
    - `error: string` (human-readable explanation)

```json
{ "success": false, "error": "Shopify returned errors when cancelling order. Order ID is invalid." }

```

---

### Params Standard → https://json-schema.org/

---

# Tool List (sorted by handle)

1. `shopify_add_tags`
2. `shopify_cancel_order`
3. `shopify_create_discount_code`
4. `shopify_create_draft_order`
5. `shopify_create_return`
6. `shopify_create_store_credit`
7. `shopify_get_collection_recommendations`
8. `shopify_get_customer_orders`
9. `shopify_get_order_details`
10. `shopify_get_product_details`
11. `shopify_get_product_recommendations`
12. `shopify_get_related_knowledge_source`
13. `shopify_refund_order`
14. `shopify_update_order_shipping_address`
15. `skio_cancel_subscription`
16. `skio_get_subscription_status`
17. `skio_pause_subscription`
18. `skio_skip_next_order_subscription`
19. `skio_unpause_subscription`

---

# Tool Catalog

## 1) Shopify Add Tags (`shopify_add_tags`)

**Description:** Add tags to an order, a draft order, a customer, a product, or an online store article.

**API**

- **POST** `{API_URL}/hackhaton/add_tags`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["id", "tags"],
  "properties": {
    "id": { "type": "string", "description": "Shopify resource GID." },
    "tags": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string" },
      "description": "Tags to add."
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{ "success": true }

```

- Failure

```json
{ "success": false, "error": "Failed to add tags" }

```

---

## 2) Shopify Cancel Order (`shopify_cancel_order`)

**Description:** Cancel an order based on order ID and reason.

**API**

- **POST** `{API_URL}/hackhaton/cancel_order`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["orderId", "reason", "notifyCustomer", "restock", "staffNote", "refundMode", "storeCredit"],
  "properties": {
    "orderId": { "type": "string", "description": "Order GID." },
    "reason": {
      "type": "string",
      "enum": ["CUSTOMER", "DECLINED", "FRAUD", "INVENTORY", "OTHER", "STAFF"],
      "description": "Cancellation reason."
    },
    "notifyCustomer": { "type": "boolean", "default": true, "description": "Notify customer." },
    "restock": { "type": "boolean", "default": true, "description": "Restock inventory where applicable." },
    "staffNote": { "type": "string", "maxLength": 255, "description": "Internal note." },
    "refundMode": { "type": "string", "enum": ["ORIGINAL", "STORE_CREDIT"], "description": "Refund method." },
    "storeCredit": {
      "type": "object",
      "required": ["expiresAt"],
      "description": "Store credit options (only when refundMode=STORE_CREDIT).",
      "properties": {
        "expiresAt": { "type": "string", "nullable": true, "description": "ISO 8601 timestamp or null for no expiry." }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{ "success": true }

```

- Failure

```json
{ "success": false, "error": "Shopify returned errors when cancelling order" }

```

---

## 3) Shopify Create Discount Code (`shopify_create_discount_code`)

**Description:** Create a discount code for the customer.

**API**

- **POST** `{API_URL}/hackhaton/create_discount_code`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["type", "value", "duration", "productIds"],
  "properties": {
    "type": { "type": "string", "description": "'percentage' (0–1) or 'fixed' (absolute amount)." },
    "value": { "type": "number", "description": "If percentage, 0–1; if fixed, currency amount." },
    "duration": { "type": "number", "description": "Validity duration in hours (e.g. 48)." },
    "productIds": {
      "type": "array",
      "description": "Optional array of product/variant GIDs (empty for order-wide).",
      "items": { "type": "string" }
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{
  "success": true,
  "data": { "code": "DISCOUNT_LF_8F3K2J9QW1" }
}

```

- Failure

```json
{ "success": false, "error": "Failed to create discount code" }

```

---

## 4) Shopify Create Return (`shopify_create_return`)

**Description:** Create a Return using Shopify's returnCreate API.

**API**

- **POST** `{API_URL}/hackhaton/create_return`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["orderId"],
  "properties": {
    "orderId": {
      "type": "string",
      "description": "Order GID (e.g., 'gid://shopify/Order/5531567751245')."
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{ "success": true }

```

- Failure

```json
{ "success": false, "error": "Shopify returnCreate failed" }

```

---

## 5) Shopify Create Store Credit (`shopify_create_store_credit`)

**Description:** Credit store credit to a customer or StoreCreditAccount.

**API**

- **POST** `{API_URL}/hackhaton/create_store_credit`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["id", "creditAmount", "expiresAt"],
  "properties": {
    "id": {
      "type": "string",
      "description": "Customer GID or StoreCreditAccount GID (e.g. gid://shopify/Customer/7424155189325)."
    },
    "creditAmount": {
      "type": "object",
      "required": ["amount", "currencyCode"],
      "properties": {
        "amount": { "type": "string", "description": "Decimal amount, e.g. '49.99'." },
        "currencyCode": { "type": "string", "description": "ISO 4217 code, e.g. USD, EUR." }
      },
      "additionalProperties": false
    },
    "expiresAt": { "type": ["string", "null"], "description": "Optional ISO8601 expiry (or null)." }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{
  "success": true,
  "data": {
    "storeCreditAccountId": "gid://shopify/StoreCreditAccount/123",
    "credited": { "amount": "49.99", "currencyCode": "USD" },
    "newBalance": { "amount": "149.99", "currencyCode": "USD" }
  }
}

```

- Failure

```json
{ "success": false, "error": "Failed to credit store credit" }

```

---

## 6) Shopify Get Collection Recommendations (`shopify_get_collection_recommendations`)

**Description:** Generate collection recommendations based on text queries.

**API**

- **POST** `{API_URL}/hackhaton/get_collection_recommendations`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["queryKeys"],
  "properties": {
    "queryKeys": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Keywords describing what the customer wants."
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{
  "success": true,
  "data": [
    { "id": "gid://shopify/Collection/1", "title": "Acne Care", "handle": "acne-care" }
  ]
}

```

- Failure

```json
{ "success": false, "error": "Failed to fetch collection recommendations" }

```

---

## 7) Shopify Get Customer Orders (`shopify_get_customer_orders`)

**Description:** Get customer orders.

**API**

- **POST** `{API_URL}/hackhaton/get_customer_orders`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["email", "after", "limit"],
  "properties": {
    "email": { "type": "string", "description": "Customer email." },
    "after": { "type": "string", "description": "Cursor to start from, \"null\" if first page" },
    "limit": { "type": "number", "description": "Number of orders to return, max 250" }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{
  "success": true,
  "data": {
    "orders": [
      {
        "id": "gid://shopify/Order/1",
        "name": "#1001",
        "createdAt": "2026-02-06T01:06:46Z",
		    "status": "FULFILLED" | "UNFULFILLED" | "CANCELLED" | "DELIVERED",
        "trackingUrl": "https://tracking.example.com/abc123"
      }
    ],
    "hasNextPage": false,
    "endCursor": null
  }
}

```

- Failure

```json
{ "success": false, "error": "Failed to fetch customer orders" }

```

---

## 8) Shopify Get Order Details (`shopify_get_order_details`)

**Description:** Fetch detailed information for a single order by ID. If user provides only the order number, use `#{order_number}`.

**API**

- **POST** `{API_URL}/hackhaton/get_order_details`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["orderId"],
  "properties": {
    "orderId": {
      "type": "string",
      "description": "Order identifier. Must start with '#', e.g. '#1234'."
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{
  "success": true,
  "data": {
    "id": "gid://shopify/Order/1",
    "name": "#1001",
    "createdAt": "2026-02-06T01:06:46Z",
    "status": "FULFILLED" | "UNFULFILLED" | "CANCELLED" | "DELIVERED",
    "trackingUrl": "https://tracking.example.com/abc123"
  }
}

```

- Failure

```json
{ "success": false, "error": "Order not found" }

```

---

## 9) Shopify Get Product Details (`shopify_get_product_details`)

**Description:** Retrieve product information by product ID, name, or key feature.

**API**

- **POST** `{API_URL}/hackhaton/get_product_details`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["queryType", "queryKey"],
  "properties": {
    "queryKey": {
      "type": "string",
      "description": "Lookup key. If queryType is 'id', it must be a Shopify Product GID."
    },
    "queryType": {
      "type": "string",
      "enum": ["id", "name", "key feature"],
      "description": "How to interpret queryKey."
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success (always array)

```json
{
  "success": true,
  "data": [
    { "id": "gid://shopify/Product/9", "title": "Patch", "handle": "patch" }
  ]
}

```

- Failure

```json
{ "success": false, "error": "Product not found" }

```

---

## 10) Shopify Get Product Recommendations (`shopify_get_product_recommendations`)

**Description:** Generate product recommendations based on keyword intents.

**API**

- **POST** `{API_URL}/hackhaton/get_product_recommendations`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["queryKeys"],
  "properties": {
    "queryKeys": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Keywords describing the customer's intent and constraints."
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{
  "success": true,
  "data": [
    { "id": "gid://shopify/Product/9", "title": "Patch", "handle": "patch" }
  ]
}

```

- Failure

```json
{ "success": false, "error": "Failed to fetch product recommendations" }

```

---

## 11) Shopify Get Related Knowledge Source (`shopify_get_related_knowledge_source`)

**Description:** Retrieve related FAQs, PDFs, blog articles, and Shopify pages based on a question and optional product context.

**API**

- **POST** `{API_URL}/hackhaton/get_related_knowledge_source`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["question", "specificToProductId"],
  "properties": {
    "question": { "type": "string", "description": "Customer question/problem to answer." },
    "specificToProductId": {
      "type": "string",
      "description": "Related product ID (Shopify GID) or null if not product-specific."
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{
  "success": true,
  "data": {
    "faqs": [],
    "pdfs": [],
    "blogArticles": [],
    "pages": []
  }
}

```

- Failure

```json
{ "success": false, "error": "Failed to fetch related knowledge sources" }

```

---

## 12) Shopify Refund Order (`shopify_refund_order`)

**Description:** Refund an order.

**API**

- **POST** `{API_URL}/hackhaton/refund_order`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["orderId", "refundMethod"],
  "properties": {
    "orderId": {
      "type": "string",
      "description": "Order GID (e.g., 'gid://shopify/Order/5531567751245')."
    },
    "refundMethod": {
      "type": "string",
      "enum": ["ORIGINAL_PAYMENT_METHODS", "STORE_CREDIT"],
      "description": "Where the refund goes."
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{ "success": true }

```

- Failure

```json
{ "success": false, "error": "Shopify refundCreate failed" }

```

---

## 13) Shopify Update Order Shipping Address (`shopify_update_order_shipping_address`)

**Description:** Update an order's shipping address (Shopify orderUpdate).

**API**

- **POST** `{API_URL}/hackhaton/update_order_shipping_address`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["orderId", "shippingAddress"],
  "properties": {
    "orderId": { "type": "string", "description": "Order GID." },
    "shippingAddress": {
      "type": "object",
      "required": ["firstName", "lastName", "company", "address1", "address2", "city", "provinceCode", "country", "zip", "phone"],
      "properties": {
        "firstName": { "type": "string" },
        "lastName": { "type": "string" },
        "company": { "type": "string" },
        "address1": { "type": "string" },
        "address2": { "type": "string" },
        "city": { "type": "string" },
        "provinceCode": { "type": "string" },
        "country": { "type": "string" },
        "zip": { "type": "string" },
        "phone": { "type": "string" }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{ "success": true }

```

- Failure

```json
{ "success": false, "error": "Shopify returned errors when updating shipping address. Invalid zip" }

```

---

## 14) Skio Cancel Subscription (`skio_cancel_subscription`)

**Description:** Cancels the subscription if client encounter any technical errors.

**API**

- **POST** `{API_URL}/hackhaton/cancel-subscription`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["subscriptionId", "cancellationReasons"],
  "properties": {
    "subscriptionId": { "type": "string", "description": "ID of the subscription to be cancelled." },
    "cancellationReasons": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Reasons of cancellation."
    }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{ "success": true }

```

- Failure

```json
{ "success": false, "error": "Failed to cancel subscription" }

```

---

## 15) Skio Get Subscription Status (`skio_get_subscription_status`)

**Description:** Gets the subscription status of a customer.

**API**

- **POST** `{API_URL}/hackhaton/get-subscription-status`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["email"],
  "properties": {
    "email": { "type": "string", "description": "Email of the user whose subscription information is retrieved" }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{
  "success": true,
  "data": {
    "status": "ACTIVE",
    "subscriptionId": "sub_123",
    "nextBillingDate": "2026-03-01"
  }
}

```

- Failure

```json
{
  "success": false,
  "error": "Failed to get subscription status. This subscription has already been cancelled."
}

```

---

## 16) Skio Pause Subscription (`skio_pause_subscription`)

**Description:** Pauses the subscription.

**API**

- **POST** `{API_URL}/hackhaton/pause-subscription`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["subscriptionId", "pausedUntil"],
  "properties": {
    "subscriptionId": { "type": "string", "description": "ID of the subscription to be paused." },
    "pausedUntil": { "type": "string", "description": "Date to pause the subscription until. Format: YYYY-MM-DD" }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{ "success": true }

```

- Failure

```json
{ "success": false, "error": "Failed to pause subscription" }

```

---

## 17) Skio Skip Next Order Subscription (`skio_skip_next_order_subscription`)

**Description:** Skips the next order of an ongoing subscription.

**API**

- **POST** `{API_URL}/hackhaton/skip-next-order-subscription`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["subscriptionId"],
  "properties": {
    "subscriptionId": { "type": "string", "description": "ID of the subscription to be skipped." }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{ "success": true }

```

- Failure

```json
{ "success": false, "error": "Failed to skip next subscription order" }

```

---

## 18) Skio Unpause Subscription (`skio_unpause_subscription`)

**Description:** Unpauses the paused subscription.

**API**

- **POST** `{API_URL}/hackhaton/unpause-subscription`
- Headers: `Content-Type: application/json`

**Params (`paramsJsonSchema`)**

```json
{
  "type": "object",
  "required": ["subscriptionId"],
  "properties": {
    "subscriptionId": { "type": "string", "description": "ID of the subscription to be unpaused." }
  },
  "additionalProperties": false
}

```

**Output**

- Success

```json
{ "success": true }

```

- Failure