"""Main LangGraph workflow for the support agent."""

from typing import Any

from langgraph.graph import StateGraph, END

from src.agents.state import ConversationState, create_initial_state
from src.agents.nodes.classifier import classify_intent
from src.agents.nodes.sentiment import analyze_sentiment
from src.agents.nodes.context import fetch_context
from src.agents.nodes.router import route_to_agent
from src.agents.nodes.wismo import handle_wismo
from src.agents.nodes.returns import handle_returns
from src.agents.nodes.refunds import handle_refunds
from src.agents.nodes.general import handle_general
from src.agents.nodes.response import build_response
from src.agents.nodes.escalation import check_escalation, handle_escalation_flow
import structlog

logger = structlog.get_logger()


def create_support_graph() -> StateGraph:
    """
    Create the main support agent workflow graph.
    
    Flow:
    1. classify_intent - Determine what the customer wants
    2. analyze_sentiment - Understand their emotional state
    3. fetch_context - Get relevant order/customer data
    4. route_to_agent - Select specialist agent
    5. [specialist agent] - Handle the specific request
    6. build_response - Finalize response
    7. check_escalation - Determine if human needed
    """
    
    # Initialize graph with state type
    graph = StateGraph(ConversationState)
    
    # === Add nodes ===
    
    # Entry nodes - analysis
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("analyze_sentiment", analyze_sentiment)
    graph.add_node("fetch_context", fetch_context)
    
    # Specialist agents
    graph.add_node("wismo", handle_wismo)
    graph.add_node("returns", handle_returns)
    graph.add_node("refunds", handle_refunds)
    graph.add_node("general", handle_general)
    
    # Output nodes
    graph.add_node("build_response", build_response)
    graph.add_node("check_escalation", check_escalation)
    graph.add_node("handle_escalation", handle_escalation_flow)
    
    # === Define edges ===
    
    # Entry point
    graph.set_entry_point("classify_intent")
    
    # Linear flow through analysis
    graph.add_edge("classify_intent", "analyze_sentiment")
    graph.add_edge("analyze_sentiment", "fetch_context")
    
    # Conditional routing to specialist agents
    graph.add_conditional_edges(
        "fetch_context",
        route_to_agent,
        {
            "wismo": "wismo",
            "returns": "returns",
            "refunds": "refunds",
            "general": "general",
            "escalation": "handle_escalation",  # Direct escalation for complaints
        }
    )
    
    # All specialist agents lead to response builder
    graph.add_edge("wismo", "build_response")
    graph.add_edge("returns", "build_response")
    graph.add_edge("refunds", "build_response")
    graph.add_edge("general", "build_response")
    
    # Response builder leads to escalation check
    graph.add_edge("build_response", "check_escalation")
    
    # Conditional ending based on escalation
    graph.add_conditional_edges(
        "check_escalation",
        lambda state: "escalate" if state.get("requires_escalation") else "end",
        {
            "escalate": "handle_escalation",
            "end": END,
        }
    )
    
    # Escalation handling ends the flow
    graph.add_edge("handle_escalation", END)
    
    return graph


# Compile the graph once at module load
_compiled_graph = None


def get_compiled_graph():
    """Get or create the compiled graph."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = create_support_graph().compile()
    return _compiled_graph


async def run_agent(
    conversation_id: str,
    store_id: str,
    message: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Run the support agent for a single message.
    
    Args:
        conversation_id: Unique conversation identifier
        store_id: Store this conversation belongs to
        message: The customer's message
        history: Previous messages in the conversation
        
    Returns:
        Dict containing:
        - response: The agent's response
        - intent: Classified intent
        - sentiment: Detected sentiment
        - requires_escalation: Whether to escalate
        - actions_taken: Any actions performed
    """
    logger.info(
        "agent_run_started",
        conversation_id=conversation_id,
        store_id=store_id,
        message_length=len(message),
    )
    
    # Create initial state
    state = create_initial_state(
        conversation_id=conversation_id,
        store_id=store_id,
        message=message,
    )
    
    # Add history if provided
    if history:
        state["messages"] = history
    
    # Get compiled graph
    graph = get_compiled_graph()
    
    # Run the graph
    try:
        result = await graph.ainvoke(state)
        
        logger.info(
            "agent_run_completed",
            conversation_id=conversation_id,
            intent=result.get("intent"),
            sentiment=result.get("sentiment"),
            requires_escalation=result.get("requires_escalation"),
        )
        
        return {
            "response": result.get("final_response", ""),
            "intent": result.get("intent"),
            "confidence": result.get("confidence"),
            "sentiment": result.get("sentiment"),
            "requires_escalation": result.get("requires_escalation", False),
            "escalation_reason": result.get("escalation_reason"),
            "actions_taken": result.get("actions_taken", []),
            "order_data": result.get("order_data"),
            "agent_reasoning": result.get("agent_reasoning"),
            "tokens_used": result.get("tokens_used", 0),
        }
        
    except Exception as e:
        logger.error(
            "agent_run_error",
            conversation_id=conversation_id,
            error=str(e),
        )
        
        # Return error response
        return {
            "response": (
                "I apologize, but I'm experiencing a technical issue. "
                "Please try again in a moment, or I can connect you with "
                "a team member who can help."
            ),
            "intent": "error",
            "requires_escalation": True,
            "escalation_reason": f"Agent error: {e}",
            "error": str(e),
        }
