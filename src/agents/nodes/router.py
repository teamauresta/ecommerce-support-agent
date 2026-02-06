"""Router node - directs to specialist agents."""

from typing import Literal

import structlog

from src.agents.state import ConversationState

logger = structlog.get_logger()


# Map intents to agent names
INTENT_TO_AGENT = {
    "order_status": "wismo",
    "return_request": "returns",
    "refund_request": "refunds",
    "address_change": "general",
    "cancel_order": "general",
    "product_question": "general",
    "shipping_question": "general",
    "complaint": "escalation",
    "general_inquiry": "general",
    "other": "general",
}


def route_to_agent(
    state: ConversationState,
) -> Literal["wismo", "returns", "refunds", "general", "escalation"]:
    """
    Route to the appropriate specialist agent based on intent.

    This is a conditional edge function that returns the next node name.
    """
    intent = state.get("intent", "general_inquiry")
    sentiment = state.get("sentiment", "neutral")
    confidence = state.get("confidence", 0.5)

    # Force escalation for frustrated customers with complaints
    if intent == "complaint" or (
        sentiment == "frustrated" and state.get("sentiment_intensity", 0) >= 4
    ):
        logger.info(
            "routing_to_escalation",
            conversation_id=state["conversation_id"],
            reason="frustrated_customer_or_complaint",
        )
        return "escalation"

    # Low confidence → general agent will handle with fallback
    if confidence < 0.5:
        logger.info(
            "routing_to_general",
            conversation_id=state["conversation_id"],
            reason="low_confidence",
            confidence=confidence,
        )
        return "general"

    # Route based on intent
    agent = INTENT_TO_AGENT.get(intent, "general")

    logger.info(
        "routed_to_agent",
        conversation_id=state["conversation_id"],
        intent=intent,
        agent=agent,
    )

    return agent  # type: ignore[return-value]
