"""
Intent Classifier prompt — used by Haiku for fast, cheap classification.
"""

INTENT_CLASSIFIER_PROMPT = """Classify the customer message into exactly ONE category
and rate your confidence (0-100).

CATEGORIES:
- WISMO: shipping delay, order tracking, delivery status, "where is my order",
  package not arrived, shipment update, estimated delivery
- WRONG_MISSING: wrong item received, missing item in package, damaged item,
  incorrect product, incomplete order
- NO_EFFECT: product not working, no results, ineffective, "doesn't work",
  "not helping", "no difference", allergic reaction, rash
- REFUND: refund request, money back, return request, "want my money back",
  chargeback mention
- ORDER_MODIFY: cancel order, change address, modify order, update shipping,
  "accidentally ordered"
- SUBSCRIPTION: cancel subscription, pause subscription, billing issue,
  double charge, subscription management, "too many", "skip next",
  "update payment"
- DISCOUNT: promo code not working, discount issue, coupon, "code doesn't work",
  "code invalid"
- POSITIVE: compliment, praise, happy feedback, "love your product",
  "thank you so much", "amazing results", "works great"
- GENERAL: greeting, general question, not fitting other categories,
  off-topic, multi-topic unclear

MULTI-INTENT RULE: If the message contains multiple intents, classify by the
PRIMARY intent (the main complaint/request, not secondary mentions).
Example: "My order hasn't arrived and I want a refund" → REFUND (primary action request)
Example: "Where is order #123?" → WISMO (status inquiry)

## FEW-SHOT EXAMPLES — WRONG_MISSING vs WISMO:

### WRONG_MISSING (NOT WISMO):
- "I only received 2 of 5 items" → WRONG_MISSING|95 (partial delivery)
- "My order #NP1234 arrived but 3 stickers are missing" → WRONG_MISSING|90
- "The box only had half my order" → WRONG_MISSING|92
- "Received wrong items, not what I ordered" → WRONG_MISSING|95

### WISMO (entire order status):
- "Has my order shipped yet?" → WISMO|95
- "Where is my order #NP1234?" → WISMO|92 (status inquiry)
- "It's been 2 weeks and I haven't received anything" → WISMO|88 (entire order not arrived)
- "What's my tracking number?" → WISMO|90

KEY DISTINCTION:
- "Items missing FROM arrived order" → WRONG_MISSING
- "Entire order hasn't arrived" → WISMO
- Order number does NOT automatically mean WISMO

Response format (ONLY this, nothing else): CATEGORY|CONFIDENCE
Example: WISMO|92

Customer message: {message}"""