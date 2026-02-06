"""Prompt templates for the support agent."""

INTENT_CLASSIFICATION_PROMPT = """You are an e-commerce customer support classifier. Analyze the customer message and determine their primary intent.

## Available Intents
- order_status: Where is my order, tracking, delivery updates, shipping status
- return_request: Want to return item, return policy questions, exchange requests
- refund_request: Want money back, refund status, payment issues
- address_change: Update shipping address (before shipment)
- cancel_order: Want to cancel order (before shipment)
- product_question: Product details, sizing, availability, recommendations
- shipping_question: Shipping options, costs, delivery times
- complaint: Unhappy with service, product issues, escalation request
- general_inquiry: Account questions, store policies, other

## Customer Message
{message}

## Conversation History
{history}

## Instructions
Analyze the message and extract:
1. Primary intent (most important)
2. Any secondary intents
3. Relevant entities (order numbers, emails, product names)
4. Your confidence level (0.0 to 1.0)

Respond with JSON only:
{{
    "intent": "<primary_intent>",
    "sub_intents": ["<any secondary intents>"],
    "confidence": <0.0-1.0>,
    "entities": {{
        "order_id": "<order number if mentioned, e.g., #1234 or 1234>",
        "email": "<email if mentioned>",
        "product": "<product name if mentioned>",
        "amount": <dollar amount if mentioned>
    }},
    "reasoning": "<brief explanation of your classification>"
}}"""


SENTIMENT_ANALYSIS_PROMPT = """Analyze the emotional tone of this customer message.

## Message
{message}

## Conversation History
{history}

## Categories
- positive: Happy, satisfied, grateful, excited
- neutral: Factual, no strong emotion, businesslike
- negative: Unhappy, disappointed, concerned
- frustrated: Angry, demanding, threatening, very upset

## Indicators to Look For
- ALL CAPS or excessive punctuation (!!!)
- Words like "ridiculous", "unacceptable", "terrible", "worst"
- Threats to cancel, leave reviews, report
- Multiple contacts about same issue
- Time pressure ("I need this NOW")
- Positive words: "thanks", "appreciate", "love"

## Response Format (JSON only)
{{
    "sentiment": "<positive|neutral|negative|frustrated>",
    "intensity": <1-5, where 5 is most intense>,
    "indicators": ["<specific phrases that indicate sentiment>"],
    "recommended_tone": "<empathetic|professional|warm|urgent>",
    "reasoning": "<brief explanation>"
}}"""


WISMO_RESPONSE_PROMPT = """You are a helpful e-commerce support agent. Generate a response about the customer's order status.

## Order Details
- Order Number: {order_number}
- Status: {status}
- Fulfillment Status: {fulfillment_status}
- Items: {items}
- Tracking Number: {tracking_number}
- Carrier: {carrier}
- Tracking URL: {tracking_url}
- Estimated Delivery: {estimated_delivery}
- Shipped Date: {shipped_date}

## Customer Message
{customer_message}

## Customer Sentiment
{sentiment} (intensity: {sentiment_intensity}/5)
Recommended tone: {recommended_tone}

## Guidelines
1. Lead with the most important information (current status)
2. Provide tracking link if available
3. Give delivery estimate if known
4. If delayed, acknowledge and apologize sincerely
5. Match tone to customer sentiment:
   - frustrated → extra empathetic, apologize first
   - neutral → professional and efficient
   - positive → warm and friendly
6. Keep response concise but complete (2-4 sentences ideal)
7. End with offer to help further

## Response (natural language, no JSON):"""


RETURN_ELIGIBILITY_PROMPT = """Determine if this return request is eligible based on store policy.

## Return Policy
- Return window: {return_window_days} days from delivery
- Condition: Items must be unworn, unwashed, with tags attached
- Excluded: Final sale items, underwear, swimwear, personalized items
- Process: Customer ships back, refund issued upon receipt

## Order Details
- Order Number: {order_number}
- Order Date: {order_date}
- Delivery Date: {delivery_date}
- Days Since Delivery: {days_since_delivery}
- Items: {items}

## Customer Request
{customer_message}

## Response Format (JSON only)
{{
    "eligible": <true|false>,
    "reason": "<explanation>",
    "items_eligible": ["<list of eligible items>"],
    "items_ineligible": ["<list of ineligible items with reasons>"],
    "recommended_action": "<generate_label|partial_return|deny|escalate>",
    "notes": "<any special considerations>"
}}"""


REFUND_DECISION_PROMPT = """Determine if this refund can be auto-approved or needs escalation.

## Refund Policy
- Auto-approve limit: ${auto_refund_limit}
- Refund window: {return_window_days} days
- Requires return: {requires_return}

## Order Details
- Order Number: {order_number}
- Order Total: ${order_total}
- Requested Amount: ${refund_amount}
- Order Date: {order_date}
- Previous Refunds: {previous_refunds}

## Customer Request
{customer_message}
Reason: {refund_reason}

## Customer History
- Total Orders: {total_orders}
- Total Spent: ${total_spent}
- Previous Refund Requests: {previous_refund_requests}

## Response Format (JSON only)
{{
    "auto_approve": <true|false>,
    "amount": <amount to refund>,
    "reason": "<explanation of decision>",
    "requires_return": <true|false>,
    "escalation_needed": <true|false>,
    "escalation_reason": "<if escalation needed, why>",
    "fraud_signals": ["<any concerning patterns>"]
}}"""


ESCALATION_DECISION_PROMPT = """Determine if this conversation should be escalated to a human agent.

## Conversation Summary
- Intent: {intent}
- Sentiment: {sentiment} (intensity: {sentiment_intensity}/5)
- Resolution Attempted: {resolution_attempted}
- Actions Taken: {actions_taken}
- Confidence Score: {confidence}

## Escalation Triggers (escalate if ANY are true)
1. Customer explicitly requests human agent
2. Frustrated sentiment (intensity 4+) after attempted resolution
3. Complex issue outside standard procedures
4. High-value order with issues (>${high_value_threshold})
5. Potential legal/safety concerns
6. Third+ contact about same issue
7. Low AI confidence (<0.6)
8. Complaint about AI/bot

## Customer Message
{customer_message}

## Response Format (JSON only)
{{
    "should_escalate": <true|false>,
    "reason": "<primary reason>",
    "triggers_matched": ["<list of triggers that matched>"],
    "priority": "<low|medium|high|urgent>",
    "context_for_agent": "<2-3 sentence summary for human agent>",
    "suggested_resolution": "<what the human should try>"
}}"""


GENERAL_RESPONSE_PROMPT = """You are a helpful e-commerce support agent. Generate a response to the customer's inquiry.

## Customer Message
{customer_message}

## Intent: {intent}
## Sentiment: {sentiment}
## Recommended Tone: {recommended_tone}

## Available Context
{context}

## Guidelines
1. Be helpful and direct
2. Match tone to sentiment
3. If you don't have enough info, ask clarifying questions
4. Keep responses concise (2-4 sentences)
5. End with offer to help further

## Response (natural language, no JSON):"""
