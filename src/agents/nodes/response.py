"""Response builder node - finalizes the response."""

from typing import Any
from datetime import datetime, timezone

from src.agents.state import ConversationState, ActionLog
import structlog

logger = structlog.get_logger()


async def build_response(state: ConversationState) -> dict[str, Any]:
    """
    Finalize the response and prepare for delivery.
    
    This node:
    1. Takes the draft response from specialist agents
    2. Applies any final formatting or adjustments
    3. Logs the message for persistence
    """
    response_draft = state.get("response_draft", "")
    
    if not response_draft:
        # No response was generated - this shouldn't happen
        logger.warning(
            "no_response_draft",
            conversation_id=state["conversation_id"],
            current_agent=state.get("current_agent"),
        )
        response_draft = (
            "I apologize, but I'm having trouble processing your request. "
            "Could you please rephrase your question, or I can connect you "
            "with a team member who can help."
        )
    
    # Apply any tone adjustments
    final_response = _apply_tone_adjustments(response_draft, state)
    
    # Create message record for history
    assistant_message = {
        "role": "assistant",
        "content": final_response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "intent": state.get("intent"),
        "agent": state.get("current_agent"),
    }
    
    # Also add the user message to history
    user_message = {
        "role": "user",
        "content": state["current_message"],
        "timestamp": state.get("started_at"),
    }
    
    logger.info(
        "response_built",
        conversation_id=state["conversation_id"],
        response_length=len(final_response),
        agent=state.get("current_agent"),
    )
    
    return {
        "final_response": final_response,
        "messages": [user_message, assistant_message],
    }


def _apply_tone_adjustments(response: str, state: ConversationState) -> str:
    """Apply final tone adjustments based on sentiment."""
    sentiment = state.get("sentiment", "neutral")
    tone = state.get("recommended_tone", "professional")
    
    # For frustrated customers, ensure we start with empathy
    if sentiment == "frustrated" and not _starts_with_empathy(response):
        empathy_starters = [
            "I completely understand your frustration. ",
            "I'm truly sorry for this experience. ",
            "I apologize for the inconvenience. ",
        ]
        # Only add if response doesn't already have empathy
        import random
        response = random.choice(empathy_starters) + response
    
    return response


def _starts_with_empathy(response: str) -> bool:
    """Check if response already starts with empathetic language."""
    empathy_words = [
        "sorry", "apologize", "understand", "frustrat",
        "inconvenien", "appreciate your patience",
    ]
    lower = response.lower()[:100]
    return any(word in lower for word in empathy_words)
