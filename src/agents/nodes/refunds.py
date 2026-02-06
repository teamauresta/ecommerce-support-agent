"""Refunds agent node - handles refund requests."""

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from src.agents.prompts import REFUND_DECISION_PROMPT
from src.agents.state import ConversationState
from src.config import settings

logger = structlog.get_logger()


async def handle_refunds(state: ConversationState) -> dict[str, Any]:
    """
    Handle refund requests.

    This agent:
    1. Validates refund eligibility
    2. Checks against auto-approve limits
    3. Processes refund or escalates
    """
    updates: dict[str, Any] = {
        "current_agent": "refunds",
    }

    order_data = state.get("order_data")
    message = state["current_message"]

    # Need order info to process refund
    if not order_data:
        order_id = state.get("order_id")
        if order_id:
            updates["response_draft"] = (
                f"I'd like to help you with a refund for order #{order_id}, "
                "but I couldn't locate that order. "
                "Could you please double-check the order number?"
            )
        else:
            updates["response_draft"] = (
                "I'd be happy to help with your refund request! "
                "Could you please provide your order number so I can look into this?"
            )
        updates["agent_reasoning"] = "No order data, requesting order number"
        return updates

    # Determine refund amount
    refund_amount = state.get("refund_amount")
    if not refund_amount:
        refund_amount = float(order_data.get("total_price", 0))

    # Check refund eligibility and auto-approve limits
    decision = await _make_refund_decision(order_data, refund_amount, message, state)

    if decision.get("auto_approve"):
        # Process the refund
        refund_result = await _process_refund(
            order_data, decision["amount"], decision.get("reason", "Customer request")
        )

        if refund_result["success"]:
            updates["response_draft"] = _generate_refund_approved_response(
                order_data, decision, refund_result, state
            )
            updates["actions_taken"] = [
                {
                    "type": "refund_processed",
                    "data": {
                        "order_id": order_data.get("order_number"),
                        "amount": decision["amount"],
                        "refund_id": refund_result.get("refund_id"),
                    },
                    "status": "completed",
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ]
            updates["agent_reasoning"] = (
                f"Refund of ${decision['amount']} auto-approved and processed"
            )
        else:
            updates["response_draft"] = (
                "I've approved your refund request, but there was a technical issue "
                "processing it right now. I've flagged this for immediate attention, "
                "and our team will process the refund within the next few hours. "
                "You'll receive an email confirmation once it's complete. "
                "Is there anything else I can help with?"
            )
            updates["agent_reasoning"] = (
                f"Refund approved but processing failed: {refund_result.get('error')}"
            )

    elif decision.get("escalation_needed"):
        # Needs human review
        updates["response_draft"] = _generate_refund_escalation_response(
            order_data, decision, state
        )
        updates["requires_escalation"] = True
        updates["escalation_reason"] = decision.get("escalation_reason", "Refund requires review")
        updates["agent_reasoning"] = f"Refund escalated: {decision.get('escalation_reason')}"

    else:
        # Not eligible
        updates["response_draft"] = _generate_refund_denied_response(order_data, decision, state)
        updates["agent_reasoning"] = f"Refund not eligible: {decision.get('reason')}"

    return updates


async def _make_refund_decision(
    order_data: dict,
    refund_amount: float,
    message: str,
    state: ConversationState,
) -> dict[str, Any]:
    """Determine if refund can be auto-approved."""

    # Get policy settings
    auto_refund_limit = settings.auto_refund_limit  # Default $50
    return_window_days = settings.return_window_days  # Default 30

    order_total = float(order_data.get("total_price", 0))

    # Use LLM for nuanced decision
    llm = ChatOpenAI(
        model=settings.default_model,
        temperature=0.1,
        api_key=settings.openai_api_key,
    )

    # Get customer history if available
    customer_data = state.get("customer_data") or {}

    prompt = REFUND_DECISION_PROMPT.format(
        auto_refund_limit=auto_refund_limit,
        return_window_days=return_window_days,
        requires_return="Yes for items over $20",
        order_number=order_data.get("order_number"),
        order_total=order_total,
        refund_amount=refund_amount,
        order_date=order_data.get("created_at", "Unknown")[:10],
        previous_refunds="None on this order",
        customer_message=message,
        refund_reason="Customer request",
        total_orders=customer_data.get("total_orders", 1),
        total_spent=customer_data.get("total_spent", order_total),
        previous_refund_requests=0,
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])

        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        result = json.loads(content)

        logger.info(
            "refund_decision_made",
            conversation_id=state["conversation_id"],
            auto_approve=result.get("auto_approve"),
            amount=result.get("amount"),
            escalation_needed=result.get("escalation_needed"),
        )

        return result

    except Exception as e:
        logger.error("refund_decision_error", error=str(e))

        # Conservative fallback: auto-approve if under limit
        if refund_amount <= auto_refund_limit:
            return {
                "auto_approve": True,
                "amount": refund_amount,
                "reason": "Under auto-approve limit",
                "requires_return": refund_amount > 20,
            }
        else:
            return {
                "auto_approve": False,
                "escalation_needed": True,
                "escalation_reason": f"Refund amount ${refund_amount} exceeds auto-approve limit",
                "amount": refund_amount,
            }


async def _process_refund(
    order_data: dict,
    amount: float,
    reason: str,
) -> dict[str, Any]:
    """Process the refund through payment provider."""

    # In production, this would call Shopify/Stripe refund API
    # For now, return mock success
    logger.info(
        "refund_processed",
        order_number=order_data.get("order_number"),
        amount=amount,
    )

    return {
        "success": True,
        "refund_id": "ref_mock_12345",
        "amount": amount,
        "status": "processed",
    }


def _generate_refund_approved_response(
    order_data: dict,
    decision: dict,
    refund_result: dict,
    state: ConversationState,
) -> str:
    """Generate response for approved refund."""

    order_number = order_data.get("order_number", "your order")
    amount = decision.get("amount", 0)

    # Empathetic opener for frustrated customers
    opener = ""
    if state.get("sentiment") == "frustrated":
        opener = "I completely understand your frustration, and I want to make this right. "
    elif state.get("sentiment") == "negative":
        opener = "I'm sorry you had a less than perfect experience. "

    response = (
        f"{opener}Great news! I've processed a refund of ${amount:.2f} for order #{order_number}.\n\n"
        f"Here's what happens next:\n"
        f"• Your refund will appear on your original payment method\n"
        f"• Processing time: 3-5 business days (depending on your bank)\n"
        f"• Confirmation email is on its way\n\n"
    )

    if decision.get("requires_return"):
        response += "Since this is a product issue, no return is needed — please keep or donate the item.\n\n"

    response += "Is there anything else I can help you with?"

    return response


def _generate_refund_escalation_response(
    order_data: dict,
    decision: dict,
    state: ConversationState,
) -> str:
    """Generate response when refund needs human review."""

    order_number = order_data.get("order_number", "your order")

    opener = ""
    if state.get("sentiment") == "frustrated":
        opener = "I hear you, and I want to make sure this gets resolved properly. "

    return (
        f"{opener}I've reviewed your refund request for order #{order_number}, "
        "and I want to make sure we handle this correctly.\n\n"
        "I'm connecting you with a member of our team who can review this personally "
        "and ensure you get the best possible resolution. They'll be with you shortly.\n\n"
        "Your request has been prioritized, and you should hear back within the hour."
    )


def _generate_refund_denied_response(
    order_data: dict,
    decision: dict,
    state: ConversationState,
) -> str:
    """Generate response for denied refund."""

    order_number = order_data.get("order_number", "your order")
    reason = decision.get("reason", "our refund policy")

    opener = "I understand this isn't the answer you were hoping for. "
    if state.get("sentiment") == "frustrated":
        opener = "I'm really sorry about this situation. "

    response = (
        f"{opener}Unfortunately, I'm not able to process a refund for order #{order_number} at this time.\n\n"
        f"The reason is: {reason}\n\n"
        "I want to help find a solution though. Here are some options:\n"
        "• Exchange for a different item\n"
        "• Store credit for future use\n"
        "• Speak with our support team about exceptions\n\n"
        "Would any of these work for you?"
    )

    return response
