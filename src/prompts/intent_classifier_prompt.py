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

Response format (ONLY this, nothing else): CATEGORY|CONFIDENCE
Example: WISMO|92

Customer message: {message}"""