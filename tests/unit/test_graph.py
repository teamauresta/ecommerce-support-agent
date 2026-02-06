"""Unit tests for the LangGraph agent workflow."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.state import ConversationState, create_initial_state
from src.agents.graph import create_support_graph, run_agent


class TestConversationState:
    """Tests for conversation state management."""

    def test_create_initial_state(self):
        """Test creating initial state with required fields."""
        state = create_initial_state(
            conversation_id="conv-123",
            store_id="store-456",
            message="Where is my order?",
        )
        
        assert state["conversation_id"] == "conv-123"
        assert state["store_id"] == "store-456"
        assert state["current_message"] == "Where is my order?"
        assert state["intent"] == ""
        assert state["sentiment"] == "neutral"
        assert state["requires_escalation"] is False

    def test_initial_state_has_all_required_fields(self):
        """Test state has all required fields initialized."""
        state = create_initial_state(
            conversation_id="conv-123",
            store_id="store-456",
            message="Help me",
        )
        
        # Check key fields are present
        assert "messages" in state
        assert "priority" in state
        assert "confidence" in state
        assert "started_at" in state


class TestSupportGraph:
    """Tests for the LangGraph structure."""

    def test_graph_has_required_nodes(self):
        """Test that graph has all required nodes."""
        graph = create_support_graph()
        
        # Check core nodes exist
        assert "classify_intent" in graph.nodes
        assert "analyze_sentiment" in graph.nodes
        assert "fetch_context" in graph.nodes
        assert "build_response" in graph.nodes
        assert "check_escalation" in graph.nodes
        
        # Check specialist nodes
        assert "wismo" in graph.nodes
        assert "returns" in graph.nodes
        assert "refunds" in graph.nodes
        assert "general" in graph.nodes

    def test_graph_compiles(self):
        """Test that graph compiles without errors."""
        graph = create_support_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_can_set_entry_point(self):
        """Test that graph has entry point set."""
        graph = create_support_graph()
        # Entry point is set via set_entry_point
        # The graph should compile successfully with the entry point
        compiled = graph.compile()
        assert compiled is not None


class TestRunAgent:
    """Tests for the run_agent function."""

    @pytest.mark.asyncio
    async def test_run_agent_returns_response(self):
        """Test that run_agent returns expected structure."""
        with patch("src.agents.graph.get_compiled_graph") as mock_graph:
            # Mock the graph invoke
            mock_graph.return_value.ainvoke = AsyncMock(return_value={
                "final_response": "Your order is on the way!",
                "intent": "wismo",
                "confidence": 0.95,
                "sentiment": "neutral",
                "requires_escalation": False,
                "actions_taken": [],
            })
            
            result = await run_agent(
                conversation_id="conv-123",
                store_id="store-456",
                message="Where is my order?",
            )
            
            assert result["response"] == "Your order is on the way!"
            assert result["intent"] == "wismo"
            assert result["requires_escalation"] is False

    @pytest.mark.asyncio
    async def test_run_agent_handles_error(self):
        """Test that run_agent handles errors gracefully."""
        with patch("src.agents.graph.get_compiled_graph") as mock_graph:
            mock_graph.return_value.ainvoke = AsyncMock(
                side_effect=Exception("LLM API error")
            )
            
            result = await run_agent(
                conversation_id="conv-123",
                store_id="store-456",
                message="Help",
            )
            
            assert "technical issue" in result["response"].lower()
            assert result["requires_escalation"] is True
            assert "error" in result

    @pytest.mark.asyncio
    async def test_run_agent_with_history(self):
        """Test run_agent with conversation history."""
        with patch("src.agents.graph.get_compiled_graph") as mock_graph:
            mock_graph.return_value.ainvoke = AsyncMock(return_value={
                "final_response": "Here's your tracking info.",
                "intent": "wismo",
                "sentiment": "neutral",
            })
            
            history = [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello! How can I help?"},
            ]
            
            result = await run_agent(
                conversation_id="conv-123",
                store_id="store-456",
                message="Where is order #12345?",
                history=history,
            )
            
            assert result["response"] is not None


class TestRouterNode:
    """Tests for agent routing."""

    def test_router_handles_wismo(self):
        """Test WISMO intent routes correctly."""
        from src.agents.nodes.router import route_to_agent
        
        # Use full initial state
        state = create_initial_state(
            conversation_id="test",
            store_id="test",
            message="Where is my order?",
        )
        state["intent"] = "order_status"
        state["confidence"] = 0.9
        
        result = route_to_agent(state)
        assert result == "wismo"

    def test_router_handles_returns(self):
        """Test returns intent routes correctly."""
        from src.agents.nodes.router import route_to_agent
        
        state = create_initial_state(
            conversation_id="test",
            store_id="test",
            message="I want to return this item",
        )
        state["intent"] = "return_request"
        state["confidence"] = 0.85
        
        result = route_to_agent(state)
        assert result == "returns"

    def test_router_handles_low_confidence(self):
        """Test low confidence handling."""
        from src.agents.nodes.router import route_to_agent
        
        state = create_initial_state(
            conversation_id="test",
            store_id="test",
            message="Something unclear",
        )
        state["intent"] = "order_status"
        state["confidence"] = 0.3
        
        result = route_to_agent(state)
        # Low confidence routes to general
        assert result == "general"

    def test_router_handles_complaint(self):
        """Test complaint routing."""
        from src.agents.nodes.router import route_to_agent
        
        state = create_initial_state(
            conversation_id="test",
            store_id="test",
            message="This is terrible service!",
        )
        state["intent"] = "complaint"
        state["confidence"] = 0.9
        
        result = route_to_agent(state)
        # Complaints route to escalation
        assert result == "escalation"

    def test_router_handles_frustrated_customer(self):
        """Test frustrated customer triggers escalation."""
        from src.agents.nodes.router import route_to_agent
        
        state = create_initial_state(
            conversation_id="test",
            store_id="test",
            message="I've been waiting forever!",
        )
        state["intent"] = "order_status"
        state["confidence"] = 0.9
        state["sentiment"] = "frustrated"
        state["sentiment_intensity"] = 4.5
        
        result = route_to_agent(state)
        # Frustrated customers route to escalation
        assert result == "escalation"


class TestEscalationCheck:
    """Tests for escalation logic."""

    @pytest.mark.asyncio
    async def test_check_escalation_returns_dict(self):
        """Test check_escalation returns proper structure."""
        from src.agents.nodes.escalation import check_escalation
        
        state = create_initial_state(
            conversation_id="test",
            store_id="test",
            message="This is terrible!",
        )
        state["sentiment"] = "frustrated"
        state["sentiment_intensity"] = 5.0
        state["final_response"] = "I understand your frustration."
        
        result = await check_escalation(state)
        
        # Result should include escalation-related fields
        assert "requires_escalation" in result

    @pytest.mark.asyncio
    async def test_check_escalation_happy_path(self):
        """Test normal conversation handling."""
        from src.agents.nodes.escalation import check_escalation
        
        state = create_initial_state(
            conversation_id="test",
            store_id="test",
            message="Where is my order?",
        )
        state["sentiment"] = "neutral"
        state["sentiment_intensity"] = 3.0
        state["final_response"] = "Your order is on the way!"
        state["confidence"] = 0.95
        
        result = await check_escalation(state)
        
        # Should return a dict with requires_escalation
        assert "requires_escalation" in result


class TestIntentMapping:
    """Tests for intent to agent mapping."""

    def test_intent_mapping_exists(self):
        """Test that intent mapping is defined."""
        from src.agents.nodes.router import INTENT_TO_AGENT
        
        assert "order_status" in INTENT_TO_AGENT
        assert "return_request" in INTENT_TO_AGENT
        assert "refund_request" in INTENT_TO_AGENT
        
    def test_all_intents_have_valid_agents(self):
        """Test all defined intents have valid agent mappings."""
        from src.agents.nodes.router import INTENT_TO_AGENT
        
        valid_agents = ["wismo", "returns", "refunds", "general", "escalation"]
        
        # Check that all mapped intents route to valid agents
        for intent, agent in INTENT_TO_AGENT.items():
            assert agent in valid_agents, f"Intent '{intent}' maps to invalid agent '{agent}'"
