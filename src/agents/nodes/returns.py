"""Returns agent node - handles return requests."""

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from src.agents.prompts import RETURN_ELIGIBILITY_PROMPT
from src.agents.state import ConversationState
from src.config import settings

logger = structlog.get_logger()


async def handle_returns(state: ConversationState) -> dict[str, Any]:
    """
    Handle return requests.

    This agent:
    1. Checks return eligibility based on policy
    2. Generates return label if eligible
    3. Provides return instructions
    """
    updates: dict[str, Any] = {
        "current_agent": "returns",
    }

    order_data = state.get("order_data")
    message = state["current_message"]

    # Need order info to process return
    if not order_data:
        order_id = state.get("order_id")
        if order_id:
            updates["response_draft"] = (
                f"I'd like to help you with your return for order #{order_id}, "
                "but I couldn't find that order in our system. "
                "Could you please verify the order number from your confirmation email?"
            )
        else:
            updates["response_draft"] = (
                "I'd be happy to help you with a return! "
                "Could you please provide your order number? "
                "You can find it in your order confirmation email."
            )
        updates["agent_reasoning"] = "No order data, requesting order number"
        return updates

    # Check eligibility
    eligibility = await _check_return_eligibility(order_data, message, state)

    if eligibility["eligible"]:
        # Generate return label
        label_result = await _generate_return_label(order_data, eligibility)

        if label_result["success"]:
            updates["response_draft"] = _generate_return_response(
                order_data, eligibility, label_result, state
            )
            updates["actions_taken"] = [
                {
                    "type": "return_label_generated",
                    "data": {
                        "order_id": order_data.get("order_number"),
                        "tracking_number": label_result.get("tracking_number"),
                        "items": eligibility.get("items_eligible", []),
                    },
                    "status": "completed",
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ]
            updates["agent_reasoning"] = "Return approved, label generated"
        else:
            updates["response_draft"] = (
                "Your return request has been approved! However, I'm having trouble "
                "generating your shipping label right now. I've flagged this for our team, "
                "and we'll email you the return label within the next hour. "
                "Is there anything else I can help you with?"
            )
            updates["agent_reasoning"] = (
                f"Return approved but label failed: {label_result.get('error')}"
            )
    else:
        # Not eligible - explain why and offer alternatives
        updates["response_draft"] = _generate_ineligible_response(order_data, eligibility, state)
        updates["agent_reasoning"] = f"Return not eligible: {eligibility.get('reason')}"

        # May need escalation for edge cases
        if eligibility.get("recommend_escalation"):
            updates["requires_escalation"] = True
            updates["escalation_reason"] = eligibility.get("reason")

    return updates


async def _check_return_eligibility(
    order_data: dict,
    message: str,
    state: ConversationState,
) -> dict[str, Any]:
    """Check if the return request is eligible per store policy."""

    # Get policy settings (would come from store settings in production)
    return_window_days = 30

    # Calculate days since delivery
    # In production, would use actual delivery date from tracking
    created_at = order_data.get("created_at", "")
    if created_at:
        try:
            order_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            days_since = (datetime.now(order_date.tzinfo) - order_date).days
        except (ValueError, AttributeError):
            days_since = 0
    else:
        days_since = 0

    # Estimated delivery is typically order date + 5 days
    days_since_delivery = max(0, days_since - 5)

    # Use LLM to analyze the specific return request
    llm = ChatOpenAI(
        model=settings.default_model,
        temperature=0.1,
        api_key=settings.openai_api_key,
    )

    items_str = ", ".join(
        [
            f"{item.get('title', 'Item')} (${item.get('price', '0')})"
            for item in order_data.get("line_items", [])
        ]
    )

    prompt = RETURN_ELIGIBILITY_PROMPT.format(
        return_window_days=return_window_days,
        order_number=order_data.get("order_number"),
        order_date=created_at[:10] if created_at else "Unknown",
        delivery_date="Estimated",
        days_since_delivery=days_since_delivery,
        items=items_str,
        customer_message=message,
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
            "return_eligibility_checked",
            conversation_id=state["conversation_id"],
            eligible=result.get("eligible"),
            reason=result.get("reason"),
        )

        return result

    except Exception as e:
        logger.error("return_eligibility_error", error=str(e))

        # Default to eligible if within window (conservative approach)
        if days_since_delivery <= return_window_days:
            return {
                "eligible": True,
                "reason": "Within return window",
                "items_eligible": [item.get("title") for item in order_data.get("line_items", [])],
                "items_ineligible": [],
                "recommended_action": "generate_label",
            }
        else:
            return {
                "eligible": False,
                "reason": f"Return window of {return_window_days} days has passed",
                "recommend_escalation": True,
            }


async def _generate_return_label(
    order_data: dict,
    eligibility: dict,
) -> dict[str, Any]:
    """Generate a return shipping label."""

    # In production, this would call EasyPost or similar
    # For now, return mock data
    return {
        "success": True,
        "tracking_number": "1Z999AA10123456785",
        "label_url": "https://example.com/labels/return-12345.pdf",
        "carrier": "USPS",
        "estimated_cost": 0,  # Prepaid by store
    }


def _generate_return_response(
    order_data: dict,
    eligibility: dict,
    label_result: dict,
    state: ConversationState,
) -> str:
    """Generate response for approved return."""

    order_number = order_data.get("order_number", "your order")
    items = eligibility.get("items_eligible", ["your items"])

    # Empathetic opener for frustrated customers
    opener = ""
    if state.get("sentiment") == "frustrated":
        opener = "I completely understand, and I'm sorry for any inconvenience. "

    items_str = ", ".join(items[:3])
    if len(items) > 3:
        items_str += f", and {len(items) - 3} more item(s)"

    return (
        f"{opener}Great news! Your return for order #{order_number} has been approved.\n\n"
        f"Here's what to do next:\n"
        f"1. Pack {items_str} securely in the original packaging if possible\n"
        f"2. Print the prepaid return label (we've emailed it to you)\n"
        f"3. Drop off the package at any USPS location\n\n"
        f"Your tracking number is: {label_result.get('tracking_number')}\n\n"
        f"Once we receive the return, your refund will be processed within 3-5 business days. "
        f"Is there anything else I can help you with?"
    )


def _generate_ineligible_response(
    order_data: dict,
    eligibility: dict,
    state: ConversationState,
) -> str:
    """Generate response for ineligible return."""

    reason = eligibility.get("reason", "policy restrictions")
    order_number = order_data.get("order_number", "your order")

    # Empathetic opener
    opener = "I understand you'd like to return your order, and I wish I could help more. "
    if state.get("sentiment") == "frustrated":
        opener = "I'm really sorry about this situation. "

    response = (
        f"{opener}Unfortunately, I'm not able to process a return for order #{order_number}. "
    )
    response += f"The reason is: {reason}\n\n"

    # Offer alternatives
    response += "However, I have a few options that might help:\n"
    response += "• If the item is defective, we can arrange an exchange\n"
    response += "• Store credit is available as an alternative\n"
    response += "• I can connect you with our support team to discuss exceptions\n\n"
    response += "Would any of these options work for you?"

    return response
