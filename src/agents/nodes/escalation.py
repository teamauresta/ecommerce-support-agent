"""Escalation decision node."""

import json
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.config import settings
from src.agents.state import ConversationState
from src.agents.prompts import ESCALATION_DECISION_PROMPT
import structlog

logger = structlog.get_logger()


async def check_escalation(state: ConversationState) -> dict[str, Any]:
    """
    Determine if the conversation should be escalated to a human.
    
    This node runs after response generation to catch cases where
    the AI response might not be sufficient.
    """
    # Quick checks that don't need LLM
    quick_escalate, reason = _quick_escalation_check(state)
    
    if quick_escalate:
        logger.info(
            "quick_escalation_triggered",
            conversation_id=state["conversation_id"],
            reason=reason,
        )
        return _create_escalation_response(state, reason, "high")
    
    # Use LLM for more nuanced check
    llm = ChatOpenAI(
        model=settings.default_model,
        temperature=0.1,
        api_key=settings.openai_api_key,
    )
    
    prompt = ESCALATION_DECISION_PROMPT.format(
        intent=state.get("intent", "unknown"),
        sentiment=state.get("sentiment", "neutral"),
        sentiment_intensity=state.get("sentiment_intensity", 3),
        resolution_attempted=bool(state.get("response_draft")),
        actions_taken=state.get("actions_taken", []),
        confidence=state.get("confidence", 0.5),
        high_value_threshold=200,  # Would come from store settings
        customer_message=state["current_message"],
    )
    
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        result = json.loads(content)
        
        if result.get("should_escalate"):
            logger.info(
                "llm_escalation_recommended",
                conversation_id=state["conversation_id"],
                reason=result.get("reason"),
                priority=result.get("priority"),
            )
            return _create_escalation_response(
                state,
                result.get("reason", "AI recommended escalation"),
                result.get("priority", "medium"),
                context_for_agent=result.get("context_for_agent"),
            )
        
        return {
            "requires_escalation": False,
        }
        
    except Exception as e:
        logger.warning("escalation_check_error", error=str(e))
        # On error, don't escalate but log
        return {
            "requires_escalation": False,
        }


def _quick_escalation_check(state: ConversationState) -> tuple[bool, str]:
    """
    Fast heuristic checks for obvious escalation cases.
    
    Returns (should_escalate, reason)
    """
    message = state["current_message"].lower()
    
    # Explicit request for human
    human_keywords = [
        "speak to human", "talk to human", "human agent",
        "real person", "speak to someone", "talk to someone",
        "manager", "supervisor", "representative",
        "not a bot", "stop bot", "no bot",
    ]
    if any(kw in message for kw in human_keywords):
        return True, "Customer explicitly requested human agent"
    
    # Very frustrated + high intensity
    if (state.get("sentiment") == "frustrated" and 
        state.get("sentiment_intensity", 0) >= 5):
        return True, "Extremely frustrated customer"
    
    # Complaint intent
    if state.get("intent") == "complaint":
        return True, "Customer complaint requires human attention"
    
    # Very low confidence
    if state.get("confidence", 1.0) < 0.4:
        return True, "Low confidence in intent classification"
    
    # Legal/safety keywords
    safety_keywords = ["lawyer", "sue", "legal", "attorney", "police", "fraud"]
    if any(kw in message for kw in safety_keywords):
        return True, "Potential legal/safety concern"
    
    return False, ""


def _create_escalation_response(
    state: ConversationState,
    reason: str,
    priority: str,
    context_for_agent: str | None = None,
) -> dict[str, Any]:
    """Create escalation response updates."""
    
    # Generate context if not provided
    if not context_for_agent:
        context_for_agent = (
            f"Customer inquiry about {state.get('intent', 'unknown')}. "
            f"Sentiment: {state.get('sentiment', 'neutral')}. "
            f"Order: {state.get('order_id', 'not specified')}. "
            f"Reason for escalation: {reason}"
        )
    
    # Update response to indicate escalation
    escalation_message = (
        "I understand you'd like to speak with a member of our team. "
        "I'm connecting you with someone who can help right away. "
        "Please hold for just a moment."
    )
    
    return {
        "requires_escalation": True,
        "escalation_reason": reason,
        "escalation_priority": priority,
        "final_response": escalation_message,
        "agent_reasoning": f"Escalation triggered: {reason}. Context: {context_for_agent}",
    }


async def handle_escalation_flow(state: ConversationState) -> dict[str, Any]:
    """
    Handle the escalation by creating ticket in helpdesk.
    
    This would be called as a separate node after escalation is confirmed.
    """
    # This will integrate with Gorgias/Zendesk in Week 5
    logger.info(
        "escalation_initiated",
        conversation_id=state["conversation_id"],
        reason=state.get("escalation_reason"),
        priority=state.get("escalation_priority"),
    )
    
    # For now, just log - Week 5 adds helpdesk integration
    return {
        "actions_taken": [{
            "type": "escalation_created",
            "data": {
                "reason": state.get("escalation_reason"),
                "priority": state.get("escalation_priority"),
            },
            "status": "pending",
            "timestamp": state.get("started_at"),
        }],
    }
