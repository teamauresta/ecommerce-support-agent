"""Intent classification node."""

import json
import re
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.config import settings
from src.agents.state import ConversationState
from src.agents.prompts import INTENT_CLASSIFICATION_PROMPT
import structlog

logger = structlog.get_logger()


def extract_order_number(text: str) -> str | None:
    """Extract order number from text."""
    # Match patterns like #1234, order 1234, order #1234, order number 1234
    patterns = [
        r'#(\d{4,})',  # #1234
        r'order\s*#?\s*(\d{4,})',  # order 1234 or order #1234
        r'order\s+number\s*:?\s*#?(\d{4,})',  # order number: 1234
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1)
    
    return None


def extract_email(text: str) -> str | None:
    """Extract email from text."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(pattern, text)
    return match.group(0) if match else None


def extract_amount(text: str) -> float | None:
    """Extract dollar amount from text."""
    pattern = r'\$(\d+(?:\.\d{2})?)'
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


async def classify_intent(state: ConversationState) -> dict[str, Any]:
    """
    Classify the customer's intent from their message.
    
    This is the entry node that determines what the customer wants.
    """
    message = state["current_message"]
    
    # Build conversation history for context
    history = ""
    if state.get("messages"):
        history_messages = state["messages"][-6:]  # Last 3 exchanges
        history = "\n".join([
            f"{m['role'].upper()}: {m['content']}"
            for m in history_messages
        ])
    
    # Initialize LLM
    llm = ChatOpenAI(
        model=settings.default_model,
        temperature=0.1,
        api_key=settings.openai_api_key,
    )
    
    # Format prompt
    prompt = INTENT_CLASSIFICATION_PROMPT.format(
        message=message,
        history=history or "No previous messages",
    )
    
    try:
        # Get classification
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        # Parse JSON response
        content = response.content.strip()
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        result = json.loads(content)
        
        # Extract entities from both LLM and regex (regex as fallback)
        entities = result.get("entities", {})
        order_id = entities.get("order_id") or extract_order_number(message)
        email = entities.get("email") or extract_email(message)
        amount = entities.get("amount") or extract_amount(message)
        
        logger.info(
            "intent_classified",
            conversation_id=state["conversation_id"],
            intent=result["intent"],
            confidence=result["confidence"],
            order_id=order_id,
        )
        
        return {
            "intent": result["intent"],
            "sub_intents": result.get("sub_intents", []),
            "confidence": result["confidence"],
            "order_id": order_id,
            "order_number": order_id,  # Alias
            "email": email,
            "refund_amount": amount,
            "agent_reasoning": result.get("reasoning", ""),
            "tokens_used": response.usage_metadata.get("total_tokens", 0) if hasattr(response, "usage_metadata") else 0,
        }
        
    except json.JSONDecodeError as e:
        logger.error("classification_parse_error", error=str(e), response=content)
        # Fallback to basic classification
        return {
            "intent": "general_inquiry",
            "sub_intents": [],
            "confidence": 0.5,
            "order_id": extract_order_number(message),
            "email": extract_email(message),
            "error": f"Classification parse error: {e}",
        }
    except Exception as e:
        logger.error("classification_error", error=str(e))
        return {
            "intent": "general_inquiry",
            "confidence": 0.3,
            "error": str(e),
        }
