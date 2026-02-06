"""WISMO (Where Is My Order) agent node."""

from typing import Any
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.config import settings
from src.agents.state import ConversationState
from src.agents.prompts import WISMO_RESPONSE_PROMPT
import structlog

logger = structlog.get_logger()


async def handle_wismo(state: ConversationState) -> dict[str, Any]:
    """
    Handle order status inquiries.
    
    This is the main WISMO agent that provides order tracking
    and delivery information.
    """
    updates: dict[str, Any] = {
        "current_agent": "wismo",
    }
    
    order_data = state.get("order_data")
    message = state["current_message"]
    
    # If no order data, we need to ask for order info
    if not order_data:
        order_id = state.get("order_id")
        if order_id:
            # We tried to find it but couldn't
            updates["response_draft"] = (
                f"I wasn't able to find order #{order_id} in our system. "
                "Could you please double-check the order number? "
                "You can find it in your order confirmation email. "
                "Alternatively, I can look it up using the email address you used for the order."
            )
        else:
            # No order ID provided
            updates["response_draft"] = (
                "I'd be happy to help you track your order! "
                "Could you please provide your order number? "
                "You can find it in your order confirmation email, and it usually looks like #1234."
            )
        
        updates["agent_reasoning"] = "No order data available, requesting order number"
        return updates
    
    # We have order data - generate response
    status = order_data.get("status", "unknown")
    tracking_numbers = order_data.get("tracking_numbers", [])
    tracking_urls = order_data.get("tracking_urls", [])
    carrier = order_data.get("carrier", "the carrier")
    
    # Format items list
    items = ", ".join([
        f"{item.get('title', 'Item')} (x{item.get('quantity', 1)})"
        for item in order_data.get("line_items", [])
    ]) or "your items"
    
    # Get estimated delivery (mock for now - would come from tracking API)
    estimated_delivery = _estimate_delivery(order_data)
    shipped_date = _get_shipped_date(order_data)
    
    # Use LLM to generate natural response
    llm = ChatOpenAI(
        model=settings.default_model,
        temperature=0.7,  # Slightly creative for natural responses
        api_key=settings.openai_api_key,
    )
    
    prompt = WISMO_RESPONSE_PROMPT.format(
        order_number=order_data.get("order_number", "N/A"),
        status=_status_to_friendly(status),
        fulfillment_status=order_data.get("fulfillment_status", "processing"),
        items=items,
        tracking_number=tracking_numbers[0] if tracking_numbers else "Not yet available",
        carrier=carrier or "the carrier",
        tracking_url=tracking_urls[0] if tracking_urls else "Not yet available",
        estimated_delivery=estimated_delivery,
        shipped_date=shipped_date,
        customer_message=message,
        sentiment=state.get("sentiment", "neutral"),
        sentiment_intensity=state.get("sentiment_intensity", 3),
        recommended_tone=state.get("recommended_tone", "professional"),
    )
    
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        updates["response_draft"] = response.content.strip()
        updates["agent_reasoning"] = f"Order status: {status}, provided tracking info"
        
        logger.info(
            "wismo_response_generated",
            conversation_id=state["conversation_id"],
            order_number=order_data.get("order_number"),
            status=status,
        )
        
    except Exception as e:
        logger.error("wismo_response_error", error=str(e))
        # Fallback to template response
        updates["response_draft"] = _generate_fallback_response(order_data, state)
        updates["agent_reasoning"] = f"LLM error, used fallback response: {e}"
    
    return updates


def _status_to_friendly(status: str) -> str:
    """Convert status code to friendly text."""
    mapping = {
        "processing": "being prepared for shipment",
        "shipped": "on its way to you",
        "delivered": "delivered",
        "partially_shipped": "partially shipped",
        "cancelled": "cancelled",
        "pending_payment": "awaiting payment confirmation",
    }
    return mapping.get(status, status)


def _estimate_delivery(order_data: dict) -> str:
    """Estimate delivery date based on order data."""
    # In production, this would call tracking API
    status = order_data.get("status")
    
    if status == "delivered":
        return "Already delivered"
    elif status == "shipped":
        # Mock: 2-5 days from now
        from datetime import timedelta
        est = datetime.now() + timedelta(days=3)
        return est.strftime("%A, %B %d")
    else:
        return "We'll send tracking info once shipped"


def _get_shipped_date(order_data: dict) -> str:
    """Get the date order was shipped."""
    # Would come from fulfillment data
    if order_data.get("status") in ["shipped", "delivered"]:
        return "recently"  # Would be actual date
    return "Not yet shipped"


def _generate_fallback_response(order_data: dict, state: ConversationState) -> str:
    """Generate a fallback response without LLM."""
    status = order_data.get("status", "processing")
    order_number = order_data.get("order_number", "your order")
    tracking = order_data.get("tracking_numbers", [])
    
    # Add empathy for frustrated customers
    prefix = ""
    if state.get("sentiment") == "frustrated":
        prefix = "I apologize for any inconvenience. "
    
    if status == "delivered":
        return f"{prefix}Great news! Order #{order_number} has been delivered. If you haven't received it, please check with neighbors or your building's package room. Let me know if you need any help!"
    
    elif status == "shipped":
        tracking_info = f" Your tracking number is {tracking[0]}." if tracking else ""
        return f"{prefix}Order #{order_number} is on its way!{tracking_info} It should arrive within the next few days. Is there anything else I can help you with?"
    
    elif status == "processing":
        return f"{prefix}Order #{order_number} is currently being prepared for shipment. You'll receive an email with tracking information once it ships. Is there anything else I can help with?"
    
    else:
        return f"{prefix}I found your order #{order_number}. It's currently {status}. Would you like me to provide more details?"
