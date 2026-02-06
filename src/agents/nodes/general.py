"""General inquiry handler - fallback for non-specialized queries."""

from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.config import settings
from src.agents.state import ConversationState
from src.agents.prompts import GENERAL_RESPONSE_PROMPT
import structlog

logger = structlog.get_logger()


async def handle_general(state: ConversationState) -> dict[str, Any]:
    """
    Handle general inquiries that don't fit specialized agents.
    
    This is the fallback agent for:
    - Product questions
    - Shipping questions
    - Address changes
    - General inquiries
    - Low-confidence classifications
    """
    updates: dict[str, Any] = {
        "current_agent": "general",
    }
    
    intent = state.get("intent", "general_inquiry")
    message = state["current_message"]

    # Build conversation history
    conversation_history = ""
    if state.get("messages"):
        history_messages = state["messages"][-6:]  # Last 3 exchanges
        conversation_history = "\n".join([
            f"{m['role'].upper()}: {m['content']}"
            for m in history_messages
        ])

    # Build context from available data
    context_parts = []
    
    if state.get("order_data"):
        order = state["order_data"]
        context_parts.append(
            f"Order #{order.get('order_number')}: "
            f"Status: {order.get('status')}, "
            f"Total: ${order.get('total_price')}"
        )
    
    if state.get("customer_data"):
        customer = state["customer_data"]
        context_parts.append(
            f"Customer: {customer.get('name')}, "
            f"Orders: {customer.get('total_orders')}, "
            f"VIP: {'Yes' if customer.get('is_vip') else 'No'}"
        )

    if state.get("policy_context"):
        context_parts.append("--- Knowledge Base ---")
        context_parts.extend(state["policy_context"])

    context = "\n".join(context_parts) if context_parts else "No additional context available"
    
    # Generate response with LLM
    llm = ChatOpenAI(
        model=settings.default_model,
        temperature=0.7,
        api_key=settings.openai_api_key,
    )
    
    prompt = GENERAL_RESPONSE_PROMPT.format(
        conversation_history=conversation_history or "No previous messages in this conversation",
        customer_message=message,
        intent=intent,
        sentiment=state.get("sentiment", "neutral"),
        recommended_tone=state.get("recommended_tone", "professional"),
        context=context,
    )
    
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        updates["response_draft"] = response.content.strip()
        updates["agent_reasoning"] = f"General handler for intent: {intent}"
        
    except Exception as e:
        logger.error("general_response_error", error=str(e))
        # Fallback response
        updates["response_draft"] = (
            "Thank you for reaching out! I'd be happy to help with your question. "
            "Could you provide a bit more detail so I can assist you better?"
        )
        updates["agent_reasoning"] = f"LLM error, used fallback: {e}"
    
    return updates
