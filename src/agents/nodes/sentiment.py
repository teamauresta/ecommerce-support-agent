"""Sentiment analysis node."""

import json
from typing import Any

import structlog
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from src.agents.prompts import SENTIMENT_ANALYSIS_PROMPT
from src.agents.state import ConversationState
from src.config import settings

logger = structlog.get_logger()


async def analyze_sentiment(state: ConversationState) -> dict[str, Any]:
    """
    Analyze the customer's emotional state.

    This affects response tone and escalation decisions.
    """
    message = state["current_message"]

    # Quick heuristic checks for obvious cases
    message_upper_ratio = sum(1 for c in message if c.isupper()) / max(len(message), 1)
    has_multiple_exclamation = "!!" in message or message.count("!") > 2

    # Build history
    history = ""
    if state.get("messages"):
        history_messages = state["messages"][-4:]
        history = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history_messages])

    llm = ChatOpenAI(
        model=settings.default_model,
        temperature=0.1,
        api_key=settings.openai_api_key,
    )

    prompt = SENTIMENT_ANALYSIS_PROMPT.format(
        message=message,
        history=history or "No previous messages",
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])

        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        result = json.loads(content)

        # Boost intensity if heuristics suggest frustration
        intensity = result.get("intensity", 3)
        if message_upper_ratio > 0.5 or has_multiple_exclamation:
            intensity = min(5, intensity + 1)

        logger.info(
            "sentiment_analyzed",
            conversation_id=state["conversation_id"],
            sentiment=result["sentiment"],
            intensity=intensity,
        )

        return {
            "sentiment": result["sentiment"],
            "sentiment_intensity": intensity,
            "recommended_tone": result.get("recommended_tone", "professional"),
        }

    except json.JSONDecodeError as e:
        logger.error("sentiment_parse_error", error=str(e))
        # Fallback based on heuristics
        if message_upper_ratio > 0.5 or has_multiple_exclamation:
            return {
                "sentiment": "frustrated",
                "sentiment_intensity": 4,
                "recommended_tone": "empathetic",
            }
        return {
            "sentiment": "neutral",
            "sentiment_intensity": 3,
            "recommended_tone": "professional",
        }
    except Exception as e:
        logger.error("sentiment_error", error=str(e))
        return {
            "sentiment": "neutral",
            "sentiment_intensity": 3,
            "recommended_tone": "professional",
        }
