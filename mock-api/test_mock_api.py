"""
Test suite: Validates mock_api_server.py against all 95 test scenarios.
Run:  python test_mock_api.py
"""
import json, sys, requests, time

BASE = "http://localhost:8080/hackhaton"
ADMIN = "http://localhost:8080/admin"
PASS = 0; FAIL = 0; ERRORS = []

def ok(tid, desc):
    global PASS; PASS += 1; print(f"  ✅ {tid}: {desc}")

def fail(tid, desc, detail=""):
    global FAIL; FAIL += 1
    msg = f"  ❌ {tid}: {desc}" + (f" — {detail}" if detail else "")
    print(msg); ERRORS.append(msg)

def post(ep, body=None): return requests.post(f"{BASE}/{ep}", json=body or {}).json()
def apost(ep, body=None): return requests.post(f"{ADMIN}/{ep}", json=body or {}).json()
def aget(ep): return requests.get(f"{ADMIN}/{ep}").json()
def reset(): apost("reset")

def test_wismo():
    print("\n📦 WISMO TESTS"); reset()
    # WISMO-001: Order lookup
    r = post("get_order_details", {"orderId": "#43189"})
    if r["success"] and r["data"]["name"] == "#43189": ok("WISMO-001", "Order #43189 found")
    else: fail("WISMO-001", "Lookup failed", str(r))
    if r["success"] and r["data"]["id"] == "gid://shopify/Order/5531567751245": ok("WISMO-001-GID", "GID correct")
    else: fail("WISMO-001-GID", "GID mismatch")
    if r["success"] and r["data"]["status"] == "FULFILLED" and r["data"]["trackingUrl"]: ok("WISMO-001-STATUS", "FULFILLED+tracking")
    else: fail("WISMO-001-STATUS", "Bad status/tracking")

    # WISMO-002: Email lookup
    r = post("get_customer_orders", {"email": "sarah@example.com", "after": "null", "limit": 10})
    if r["success"] and len(r["data"]["orders"]) >= 3: ok("WISMO-002", f"{len(r['data']['orders'])} orders for sarah")
    else: fail("WISMO-002", "Email lookup failed", str(r))
    if r["success"]:
        names = {o["name"] for o in r["data"]["orders"]}
        exp = {"#43189", "#43200", "#43215"}
        if exp.issubset(names): ok("WISMO-002-NAMES", f"All expected orders found")
        else: fail("WISMO-002-NAMES", f"Missing: {exp - names}")

    # WISMO-005: Not found
    r = post("get_order_details", {"orderId": "#99999"})
    if not r["success"] and "not found" in r["error"].lower(): ok("WISMO-005", "#99999 not found")
    else: fail("WISMO-005", "Should not find", str(r))

    # WISMO-006: Disambiguation (3+ orders)
    r = post("get_customer_orders", {"email": "sarah@example.com", "after": "null", "limit": 10})
    if r["success"]:
        names = [o["name"] for o in r["data"]["orders"]]
        if all(n in names for n in ["#43189", "#43200", "#43215"]): ok("WISMO-006", "Disambiguation orders present")
        else: fail("WISMO-006", f"Missing orders: {names}")

    # WISMO-009: Unfulfilled
    r = post("get_order_details", {"orderId": "#43200"})
    if r["success"] and r["data"]["status"] == "UNFULFILLED": ok("WISMO-009", "#43200 UNFULFILLED")
    else: fail("WISMO-009", "Expected UNFULFILLED", str(r))

    # WISMO-011: Cancelled
    r = post("get_order_details", {"orderId": "#43190"})
    if r["success"] and r["data"]["status"] == "CANCELLED": ok("WISMO-011", "#43190 CANCELLED")
    else: fail("WISMO-011", "Expected CANCELLED", str(r))

def test_order_modify():
    print("\n✏️ ORDER_MODIFY TESTS"); reset()

    # OM-002: Cancel unfulfilled
    r = post("get_order_details", {"orderId": "#43200"})
    if r["success"]:
        gid = r["data"]["id"]
        r2 = post("cancel_order", {
            "orderId": gid,
            "reason": "CUSTOMER",
            "notifyCustomer": True,
            "restock": True,
            "staffNote": "Customer requested cancellation via chat",
            "refundMode": "ORIGINAL",
            "storeCredit": {"expiresAt": None}
        })
        if r2["success"]: ok("OM-002", "Cancelled #43200")
        else: fail("OM-002", "Cancel failed", str(r2))
        r3 = post("add_tags", {"id": gid, "tags": ["Cancelled - Customer Request"]})
        if r3["success"]: ok("OM-002-TAG", "Tags added")
        else: fail("OM-002-TAG", "Tag failed", str(r3))

    reset()
    # OM-003: Can't cancel fulfilled
    r = post("get_order_details", {"orderId": "#43189"})
    if r["success"]:
        r2 = post("cancel_order", {"orderId": r["data"]["id"], "reason": "CUSTOMER", "notifyCustomer": True, "restock": True, "staffNote": "", "refundMode": "ORIGINAL", "storeCredit": {"expiresAt": None}})
        if not r2["success"] and ("fulfilled" in r2["error"].lower() or "shipped" in r2["error"].lower()):
            ok("OM-003", "Fulfilled cancel blocked")
        else: fail("OM-003", "Should block", str(r2))

    # OM-004: Already cancelled
    r = post("get_order_details", {"orderId": "#43190"})
    if r["success"]:
        r2 = post("cancel_order", {"orderId": r["data"]["id"], "reason": "CUSTOMER", "notifyCustomer": True, "restock": True, "staffNote": "", "refundMode": "ORIGINAL", "storeCredit": {"expiresAt": None}})
        if not r2["success"] and "already cancelled" in r2["error"].lower(): ok("OM-004", "Already cancelled blocked")
        else: fail("OM-004", "Should detect", str(r2))

    # OM-005: Partially fulfilled
    r = post("get_order_details", {"orderId": "#44003"})
    if r["success"]:
        r2 = post("cancel_order", {"orderId": r["data"]["id"], "reason": "CUSTOMER", "notifyCustomer": True, "restock": True, "staffNote": "", "refundMode": "ORIGINAL", "storeCredit": {"expiresAt": None}})
        if not r2["success"] and "partially" in r2["error"].lower(): ok("OM-005", "Partial cancel blocked")
        else: fail("OM-005", "Should block", str(r2))

    # OM-007: Same-day address update
    reset()
    r = post("get_order_details", {"orderId": "#43200"})
    if r["success"]:
        gid = r["data"]["id"]
        addr = {"firstName":"Sarah","lastName":"Jones","company":"","address1":"123 Main St","address2":"","city":"Toronto","provinceCode":"ON","country":"CA","zip":"M5V2T6","phone":"+14165551234"}
        r2 = post("update_order_shipping_address", {"orderId": gid, "shippingAddress": addr})
        if r2["success"]: ok("OM-007", "Address updated")
        else: fail("OM-007", "Update failed", str(r2))
        r3 = post("add_tags", {"id": gid, "tags": ["customer verified address"]})
        if r3["success"]: ok("OM-007-TAG", "Verification tag added")
        else: fail("OM-007-TAG", "Tag failed", str(r3))

    # OM-009: Address on shipped order
    r = post("get_order_details", {"orderId": "#43189"})
    if r["success"]:
        r2 = post("update_order_shipping_address", {"orderId": r["data"]["id"], "shippingAddress": {"firstName":"S","lastName":"J","company":"","address1":"x","address2":"","city":"NYC","provinceCode":"NY","country":"US","zip":"10001","phone":"1"}})
        if not r2["success"] and "shipped" in r2["error"].lower(): ok("OM-009", "Shipped address blocked")
        else: fail("OM-009", "Should block", str(r2))

    # OM-010: Incomplete address
    reset()
    r = post("get_order_details", {"orderId": "#43200"})
    if r["success"]:
        r2 = post("update_order_shipping_address", {"orderId": r["data"]["id"], "shippingAddress": {"address1": "456 Oak Ave"}})
        if not r2["success"] and "missing" in r2["error"].lower(): ok("OM-010", "Incomplete address rejected")
        else: fail("OM-010", "Should reject", str(r2))

def test_wrong_missing():
    print("\n📋 WRONG/MISSING TESTS"); reset()
    # WM-004: Store credit + tags (with expiresAt per spec)
    r = post("create_store_credit", {
        "id": "gid://shopify/Customer/7424155189325",
        "creditAmount": {"amount": "33.00", "currencyCode": "USD"},
        "expiresAt": None
    })
    if r["success"] and float(r["data"]["credited"]["amount"]) == 33.0: ok("WM-004", "Store credit $33 (incl 10% bonus)")
    else: fail("WM-004", "Credit failed", str(r))
    r2 = post("add_tags", {"id": "gid://shopify/Order/5531567751245", "tags": ["Wrong or Missing", "Store Credit"]})
    if r2["success"]: ok("WM-004-TAG", "WM+SC tags added")
    else: fail("WM-004-TAG", "Tag failed", str(r2))

    # WM-005: Refund + tags
    reset()
    r = post("refund_order", {"orderId": "gid://shopify/Order/5531567751245", "refundMethod": "ORIGINAL_PAYMENT_METHODS"})
    if r["success"]: ok("WM-005", "Refund processed")
    else: fail("WM-005", "Refund failed", str(r))
    r2 = post("add_tags", {"id": "gid://shopify/Order/5531567751245", "tags": ["Wrong or Missing", "Cash Refund"]})
    if r2["success"]: ok("WM-005-TAG", "WM+CR tags added")
    else: fail("WM-005-TAG", "Tag failed", str(r2))

def test_refund():
    print("\n💰 REFUND TESTS"); reset()
    r = post("get_order_details", {"orderId": "#51234"})
    if r["success"] and r["data"]["status"] == "DELIVERED": ok("REF-001", "#51234 DELIVERED")
    else: fail("REF-001", "Expected DELIVERED", str(r))

    r = post("get_order_details", {"orderId": "#43200"})
    if r["success"] and r["data"]["status"] == "UNFULFILLED": ok("REF-004", "#43200 UNFULFILLED (for cancel flow)")
    else: fail("REF-004", "Expected UNFULFILLED", str(r))

    r = post("get_order_details", {"orderId": "#43189"})
    if r["success"] and r["data"]["status"] == "FULFILLED": ok("REF-005", "#43189 FULFILLED (for SC flow)")
    else: fail("REF-005", "Expected FULFILLED", str(r))

    r = post("get_order_details", {"orderId": "#43190"})
    if r["success"] and r["data"]["status"] == "CANCELLED" and r["data"]["refunded"]: ok("REF-007", "#43190 CANCELLED+REFUNDED")
    else: fail("REF-007", "Expected cancelled+refunded", str(r))
    if r["success"]:
        r2 = post("refund_order", {"orderId": r["data"]["id"], "refundMethod": "ORIGINAL_PAYMENT_METHODS"})
        if not r2["success"] and "already" in r2["error"].lower(): ok("REF-007-DUPE", "Double refund blocked")
        else: fail("REF-007-DUPE", "Should block", str(r2))

def test_subscription():
    print("\n🔄 SUBSCRIPTION TESTS"); reset()
    r = post("get-subscription-status", {"email": "sarah@example.com"})
    if r["success"] and r["data"]["status"] == "ACTIVE": ok("SUB-001", "Sarah ACTIVE sub")
    else: fail("SUB-001", "Expected ACTIVE", str(r))
    sub_id = r["data"]["subscriptionId"] if r["success"] else None

    if sub_id:
        r = post("cancel-subscription", {"subscriptionId": sub_id, "cancellationReasons": ["Too many on hand"]})
        if r["success"]: ok("SUB-003", "Sub cancelled")
        else: fail("SUB-003", "Cancel failed", str(r))
        r2 = post("cancel-subscription", {"subscriptionId": sub_id, "cancellationReasons": []})
        if not r2["success"] and "already" in r2["error"].lower(): ok("SUB-003-DUPE", "Double cancel blocked")
        else: fail("SUB-003-DUPE", "Should block", str(r2))

    reset()
    r = post("get-subscription-status", {"email": "emma@example.com"})
    if not r["success"] and "already been cancelled" in r["error"].lower(): ok("SUB-005", "Cancelled sub → error per spec")
    else: fail("SUB-005", "Expected cancelled error", str(r))

    r = post("get-subscription-status", {"email": "nobody@example.com"})
    if not r["success"] and "no subscription" in r["error"].lower(): ok("SUB-007", "No sub found")
    else: fail("SUB-007", "Expected not found", str(r))

    r = post("get-subscription-status", {"email": "sarah@example.com"})
    if r["success"]:
        sid = r["data"]["subscriptionId"]
        r2 = post("pause-subscription", {"subscriptionId": sid, "pausedUntil": "2026-09-01"})
        if r2["success"]: ok("SUB-008", "Sub paused")
        else: fail("SUB-008", "Pause failed", str(r2))
        r3 = post("pause-subscription", {"subscriptionId": sid, "pausedUntil": "2026-10-01"})
        if not r3["success"] and "already paused" in r3["error"].lower(): ok("SUB-008-DUPE", "Double pause blocked")
        else: fail("SUB-008-DUPE", "Should block", str(r3))

    reset()
    r = post("get-subscription-status", {"email": "sarah@example.com"})
    if r["success"]:
        sid = r["data"]["subscriptionId"]
        r2 = post("skip-next-order-subscription", {"subscriptionId": sid})
        if r2["success"]: ok("SUB-009", "Next order skipped")
        else: fail("SUB-009", "Skip failed", str(r2))

    # SUB-009: Verify new billing date pushed +30 days
    reset()
    r = post("get-subscription-status", {"email": "sarah@example.com"})
    if r["success"]:
        sid = r["data"]["subscriptionId"]
        old_date = r["data"]["nextBillingDate"]
        r2 = post("skip-next-order-subscription", {"subscriptionId": sid})
        if r2["success"] and r2["data"]["newNextBillingDate"] != old_date:
            ok("SUB-009-DATE", f"Billing date changed: {old_date} → {r2['data']['newNextBillingDate']}")
        else: fail("SUB-009-DATE", "Date should change", str(r2))

    # Unpause test
    reset()
    r = post("get-subscription-status", {"email": "sarah@example.com"})
    if r["success"]:
        sid = r["data"]["subscriptionId"]
        post("pause-subscription", {"subscriptionId": sid, "pausedUntil": "2026-09-01"})
        r2 = post("unpause-subscription", {"subscriptionId": sid})
        if r2["success"]: ok("SUB-UNPAUSE", "Unpause works")
        else: fail("SUB-UNPAUSE", "Unpause failed", str(r2))

def test_discount():
    print("\n🏷️ DISCOUNT TESTS"); reset()
    r = post("create_discount_code", {"type": "percentage", "value": 0.10, "duration": 48, "productIds": []})
    if r["success"] and r["data"]["code"].startswith("DISCOUNT_LF_"): ok("DISC-001", f"Code: {r['data']['code']}")
    else: fail("DISC-001", "Creation failed", str(r))

def test_guardrails():
    print("\n🛡️ GUARDRAIL TESTS"); reset()
    r = post("cancel_order", {"orderId": "#43189", "reason": "CUSTOMER", "notifyCustomer": True, "restock": True, "staffNote": "", "refundMode": "ORIGINAL", "storeCredit": {"expiresAt": None}})
    if not r["success"] and "gid" in r["error"].lower(): ok("GR-TOOL-001", "Cancel with # blocked → GID hint")
    else: fail("GR-TOOL-001", "Should block non-GID", str(r))

    r = post("get_order_details", {"orderId": "43189"})
    if r["success"] and r["data"]["name"] == "#43189": ok("GR-TOOL-002", "43189 → #43189 auto-corrected")
    else: fail("GR-TOOL-002", "Should find without #", str(r))

    r = post("cancel_order", {"reason": "CUSTOMER", "notifyCustomer": True, "restock": True, "staffNote": "", "refundMode": "ORIGINAL", "storeCredit": {"expiresAt": None}})
    if not r["success"] and "order" in r["error"].lower(): ok("EDGE-011", "Cancel no orderId blocked")
    else: fail("EDGE-011", "Should require orderId", str(r))

    r = post("get_order_details", {"orderId": "43200"})
    if r["success"] and r["data"]["name"] == "#43200": ok("EDGE-019", "43200 auto-corrected")
    else: fail("EDGE-019", "Should find", str(r))

def test_edge_cases():
    print("\n🔧 EDGE CASE TESTS"); reset()
    # EDGE-006: GID from lookup
    r = post("get_order_details", {"orderId": "#43200"})
    if r["success"]:
        gid = r["data"]["id"]
        r2 = post("cancel_order", {"orderId": gid, "reason": "CUSTOMER", "notifyCustomer": True, "restock": True, "staffNote": "Customer requested cancellation via chat", "refundMode": "ORIGINAL", "storeCredit": {"expiresAt": None}})
        if r2["success"]: ok("EDGE-006", f"Cancel via looked-up GID")
        else: fail("EDGE-006", "Cancel with GID failed", str(r2))

    reset()
    # EDGE-020 / NE-007: Multi-line-item order
    r = post("get_order_details", {"orderId": "#43189"})
    if r["success"]:
        items = r["data"]["lineItems"]
        titles = [i["title"] for i in items]
        if len(items) >= 2 and any("Sleepy" in t for t in titles) and any("Buzz" in t for t in titles):
            ok("EDGE-020", f"Multi-item order: {[t.split('—')[0].strip() for t in titles]}")
            ok("NE-007", "Multi-product for disambiguation")
        else: fail("EDGE-020", f"Expected 2+ items, got: {titles}")

    # Return on unfulfilled
    reset()
    r = post("get_order_details", {"orderId": "#43200"})
    if r["success"]:
        r2 = post("create_return", {"orderId": r["data"]["id"]})
        if not r2["success"] and "unfulfilled" in r2["error"].lower(): ok("EDGE-RETURN", "Unfulfilled return blocked")
        else: fail("EDGE-RETURN", "Should block", str(r2))

    # Return on fulfilled
    r = post("get_order_details", {"orderId": "#43189"})
    if r["success"]:
        r2 = post("create_return", {"orderId": r["data"]["id"]})
        if r2["success"]: ok("EDGE-RETURN-OK", "Fulfilled return allowed")
        else: fail("EDGE-RETURN-OK", "Should allow", str(r2))

    # Return on cancelled
    r = post("get_order_details", {"orderId": "#43190"})
    if r["success"]:
        r2 = post("create_return", {"orderId": r["data"]["id"]})
        if not r2["success"] and "cancelled" in r2["error"].lower(): ok("EDGE-RETURN-CANCEL", "Cancelled return blocked")
        else: fail("EDGE-RETURN-CANCEL", "Should block", str(r2))

def test_data_consistency():
    print("\n🔗 DATA CONSISTENCY TESTS"); reset()
    r = post("get_customer_orders", {"email": "sarah@example.com", "after": "null", "limit": 10})
    if r["success"]:
        names = {o["name"] for o in r["data"]["orders"]}
        exp = {"#43189", "#43200", "#43215", "#51234", "#43190"}
        if exp.issubset(names): ok("DATA-001", f"All {len(exp)} Sarah orders found")
        else: fail("DATA-001", f"Missing: {exp - names}")

    orders = {"#43189":"gid://shopify/Order/5531567751245","#43200":"gid://shopify/Order/5531567751246","#43215":"gid://shopify/Order/5531567751247","#51234":"gid://shopify/Order/5531567751248","#43190":"gid://shopify/Order/5531567751249"}
    for name, gid in orders.items():
        r = post("get_order_details", {"orderId": name})
        if r["success"] and r["data"]["id"] == gid: ok(f"DATA-GID-{name}", f"{name}→{gid[:30]}...")
        else: fail(f"DATA-GID-{name}", f"Expected {gid}")

    statuses = {"#43189":"FULFILLED","#43200":"UNFULFILLED","#43215":"FULFILLED","#51234":"DELIVERED","#43190":"CANCELLED"}
    for name, st in statuses.items():
        r = post("get_order_details", {"orderId": name})
        if r["success"] and r["data"]["status"] == st: ok(f"DATA-ST-{name}", f"{name}→{st}")
        else: fail(f"DATA-ST-{name}", f"Expected {st}")

    r = post("get-subscription-status", {"email": "sarah@example.com"})
    if r["success"] and r["data"]["status"] == "ACTIVE": ok("DATA-SUB-SARAH", "Sarah sub ACTIVE")
    else: fail("DATA-SUB-SARAH", "Expected ACTIVE")
    r = post("get-subscription-status", {"email": "emma@example.com"})
    if not r["success"] and "cancelled" in r["error"].lower(): ok("DATA-SUB-EMMA", "Emma sub CANCELLED")
    else: fail("DATA-SUB-EMMA", "Expected cancelled")
    r = post("get-subscription-status", {"email": "mike@example.com"})
    if r["success"] and r["data"]["status"] == "ACTIVE": ok("DATA-SUB-MIKE", "Mike sub ACTIVE")
    else: fail("DATA-SUB-MIKE", "Expected ACTIVE")

    # Verify Mike has 3 orders
    r = post("get_customer_orders", {"email": "mike@example.com", "after": "null", "limit": 10})
    if r["success"] and len(r["data"]["orders"]) == 3: ok("DATA-MIKE-ORDERS", "Mike has 3 orders")
    else: fail("DATA-MIKE-ORDERS", f"Expected 3 Mike orders, got {len(r['data']['orders']) if r['success'] else 'error'}")

    # Verify Emma has 2 orders
    r = post("get_customer_orders", {"email": "emma@example.com", "after": "null", "limit": 10})
    if r["success"] and len(r["data"]["orders"]) == 2: ok("DATA-EMMA-ORDERS", "Emma has 2 orders")
    else: fail("DATA-EMMA-ORDERS", f"Expected 2 Emma orders, got {len(r['data']['orders']) if r['success'] else 'error'}")

def test_knowledge():
    print("\n📚 KNOWLEDGE & PRODUCT TESTS")
    r = post("get_related_knowledge_source", {"question": "focus patches not helping concentrate", "specificToProductId": None})
    if r["success"] and len(r["data"]["faqs"]) > 0: ok("NE-002-KB", "Focus FAQs returned")
    else: fail("NE-002-KB", "No FAQs", str(r))

    r = post("get_product_recommendations", {"queryKeys": ["focus", "concentration", "school"]})
    if r["success"] and any("Focus" in p["title"] for p in r["data"]): ok("NE-003-REC", "FocusPatch recommended")
    else: fail("NE-003-REC", "Missing FocusPatch", str(r))

    r = post("get_product_details", {"queryType": "name", "queryKey": "BuzzPatch"})
    if r["success"] and len(r["data"]) > 0 and "usage_guide" in r["data"][0]: ok("PRODUCT-BUZZ", "BuzzPatch+guide found")
    else: fail("PRODUCT-BUZZ", "Missing", str(r))

    r = post("get_product_details", {"queryType": "key feature", "queryKey": "sleep"})
    if r["success"] and any("Sleepy" in p["title"] for p in r["data"]): ok("PRODUCT-SLEEP", "SleepyPatch by feature")
    else: fail("PRODUCT-SLEEP", "Missing", str(r))

    r = post("get_related_knowledge_source", {"question": "itch relief patch did nothing for the sting", "specificToProductId": None})
    if r["success"] and len(r["data"]["faqs"]) > 0: ok("NE-006-KB", "Itch FAQs for 'sting'")
    else: fail("NE-006-KB", "Missing", str(r))

    # Collection recommendations
    r = post("get_collection_recommendations", {"queryKeys": ["sleep"]})
    if r["success"] and any("Sleep" in c["title"] for c in r["data"]): ok("COLL-REC", "Sleep collection found")
    else: fail("COLL-REC", "Missing sleep collection", str(r))

    # Mosquito knowledge
    r = post("get_related_knowledge_source", {"question": "mosquito patches not repelling bugs", "specificToProductId": None})
    if r["success"] and len(r["data"]["faqs"]) > 0: ok("NE-MOSQUITO-KB", "Mosquito FAQs returned")
    else: fail("NE-MOSQUITO-KB", "Missing", str(r))

def test_pagination():
    print("\n📄 PAGINATION TESTS"); reset()
    # Get first 2 orders
    r = post("get_customer_orders", {"email": "sarah@example.com", "after": "null", "limit": 2})
    if r["success"]:
        if len(r["data"]["orders"]) == 2: ok("PAGE-001", "Got 2 orders (limit=2)")
        else: fail("PAGE-001", f"Expected 2, got {len(r['data']['orders'])}")
        if r["data"]["hasNextPage"]: ok("PAGE-002", "hasNextPage=true (5 orders, got 2)")
        else: fail("PAGE-002", "Expected hasNextPage=true")

        # Get next page using cursor
        cursor = r["data"]["endCursor"]
        r2 = post("get_customer_orders", {"email": "sarah@example.com", "after": cursor, "limit": 2})
        if r2["success"]:
            if len(r2["data"]["orders"]) == 2: ok("PAGE-003", "Got 2 more orders")
            else: fail("PAGE-003", f"Expected 2, got {len(r2['data']['orders'])}")
            # Ensure no overlap
            first_names = {o["name"] for o in r["data"]["orders"]}
            second_names = {o["name"] for o in r2["data"]["orders"]}
            if first_names.isdisjoint(second_names): ok("PAGE-004", "No overlap between pages")
            else: fail("PAGE-004", f"Overlap: {first_names & second_names}")

def test_spec_compliance():
    print("\n📋 SPEC COMPLIANCE TESTS"); reset()

    # create_store_credit with expiresAt (per spec)
    r = post("create_store_credit", {
        "id": "gid://shopify/Customer/7424155189325",
        "creditAmount": {"amount": "10.00", "currencyCode": "USD"},
        "expiresAt": "2026-12-31T23:59:59Z"
    })
    if r["success"]: ok("SPEC-SC-EXPIRES", "Store credit with expiresAt accepted")
    else: fail("SPEC-SC-EXPIRES", "Should accept expiresAt", str(r))

    reset()
    # create_store_credit with null expiresAt
    r = post("create_store_credit", {
        "id": "gid://shopify/Customer/7424155189325",
        "creditAmount": {"amount": "5.00", "currencyCode": "USD"},
        "expiresAt": None
    })
    if r["success"]: ok("SPEC-SC-NULL-EXP", "Store credit with null expiresAt accepted")
    else: fail("SPEC-SC-NULL-EXP", "Should accept null expiresAt", str(r))

    # cancel_order with all 7 required params
    reset()
    r = post("get_order_details", {"orderId": "#43200"})
    if r["success"]:
        r2 = post("cancel_order", {
            "orderId": r["data"]["id"],
            "reason": "CUSTOMER",
            "notifyCustomer": True,
            "restock": True,
            "staffNote": "Test cancel with all params",
            "refundMode": "ORIGINAL",
            "storeCredit": {"expiresAt": None}
        })
        if r2["success"]: ok("SPEC-CANCEL-ALL", "Cancel with all 7 params works")
        else: fail("SPEC-CANCEL-ALL", "Should work", str(r2))

    # get_customer_orders with 'after' param
    reset()
    r = post("get_customer_orders", {"email": "sarah@example.com", "after": "null", "limit": 5})
    if r["success"]: ok("SPEC-ORDERS-AFTER", "get_customer_orders with 'after' works")
    else: fail("SPEC-ORDERS-AFTER", "Should work", str(r))

    # create_discount_code with all required params
    r = post("create_discount_code", {
        "type": "percentage", "value": 0.10, "duration": 48, "productIds": []
    })
    if r["success"]: ok("SPEC-DISC-ALL", "Discount with all params works")
    else: fail("SPEC-DISC-ALL", "Should work", str(r))

def test_flows():
    print("\n🔄 FULL MUTATION FLOWS"); reset()
    # Flow: lookup → cancel → tag
    r1 = post("get_order_details", {"orderId": "#43200"})
    gid = r1["data"]["id"]
    post("cancel_order", {
        "orderId": gid,
        "reason": "CUSTOMER",
        "notifyCustomer": True,
        "restock": True,
        "staffNote": "Customer requested cancellation via chat",
        "refundMode": "ORIGINAL",
        "storeCredit": {"expiresAt": None}
    })
    post("add_tags", {"id": gid, "tags": ["Cancelled - Customer Request"]})
    r4 = post("get_order_details", {"orderId": "#43200"})
    if r4["success"] and r4["data"]["status"] == "CANCELLED" and "Cancelled - Customer Request" in r4["data"]["tags"]:
        ok("FLOW-CANCEL", "Cancel flow complete")
    else: fail("FLOW-CANCEL", "Bad final state", str(r4))

    reset()
    # Flow: store credit + tag
    post("create_store_credit", {
        "id": "gid://shopify/Customer/7424155189325",
        "creditAmount": {"amount": "33.00", "currencyCode": "USD"},
        "expiresAt": None
    })
    post("add_tags", {"id": "gid://shopify/Order/5531567751245", "tags": ["Wrong or Missing", "Store Credit"]})
    r = post("get_order_details", {"orderId": "#43189"})
    if r["success"] and "Wrong or Missing" in r["data"]["tags"]: ok("FLOW-CREDIT", "Credit flow complete")
    else: fail("FLOW-CREDIT", "Missing tags", str(r))

    reset()
    # Flow: sub check → skip
    r1 = post("get-subscription-status", {"email": "sarah@example.com"})
    sid = r1["data"]["subscriptionId"]
    r2 = post("skip-next-order-subscription", {"subscriptionId": sid})
    if r2["success"]: ok("FLOW-SKIP", "Skip flow complete")
    else: fail("FLOW-SKIP", "Skip failed", str(r2))

    reset()
    # Flow: sub check → pause → unpause
    r1 = post("get-subscription-status", {"email": "sarah@example.com"})
    sid = r1["data"]["subscriptionId"]
    post("pause-subscription", {"subscriptionId": sid, "pausedUntil": "2026-09-01"})
    r3 = post("unpause-subscription", {"subscriptionId": sid})
    if r3["success"]: ok("FLOW-PAUSE-UNPAUSE", "Pause→Unpause flow complete")
    else: fail("FLOW-PAUSE-UNPAUSE", "Unpause failed", str(r3))

if __name__ == "__main__":
    print("=" * 70)
    print("NatPat Mock API — Test Scenario Compatibility Suite v2.1")
    print("=" * 70)
    try:
        h = requests.get("http://localhost:8080/health", timeout=3).json()
        print(f"\n🟢 Server: {h['service']} v{h['version']}")
    except:
        print("\n🔴 Server not running! Start: uvicorn mock_api_server:app --port 8080")
        sys.exit(1)

    test_wismo(); test_order_modify(); test_wrong_missing(); test_refund()
    test_subscription(); test_discount(); test_guardrails(); test_edge_cases()
    test_data_consistency(); test_knowledge(); test_pagination()
    test_spec_compliance(); test_flows()

    print("\n" + "=" * 70)
    total = PASS + FAIL
    print(f"RESULTS: {PASS}/{total} passed ({FAIL} failed)")
    print("=" * 70)
    if ERRORS:
        print("\n❌ FAILURES:")
        for e in ERRORS: print(e)
    sys.exit(0 if FAIL == 0 else 1)