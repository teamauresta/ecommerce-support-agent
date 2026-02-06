"""Tests for Returns agent."""

import pytest
from unittest.mock import AsyncMock, patch

from src.agents.nodes.returns import handle_returns
from src.agents.state import create_initial_state


@pytest.mark.asyncio
class TestHandleReturns:
    """Tests for returns handler."""
    
    async def test_no_order_data_no_order_id(self):
        """When no order info available, ask for it."""
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="I want to return something",
        )
        state["order_data"] = None
        state["order_id"] = None
        
        result = await handle_returns(state)
        
        assert "order number" in result["response_draft"].lower()
        assert result["current_agent"] == "returns"
    
    async def test_no_order_data_with_order_id(self):
        """When order ID given but not found."""
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="I want to return from order #1234",
        )
        state["order_data"] = None
        state["order_id"] = "1234"
        
        result = await handle_returns(state)
        
        assert "#1234" in result["response_draft"]
        assert "verify" in result["response_draft"].lower() or "couldn't find" in result["response_draft"].lower()
    
    @patch("src.agents.nodes.returns.ChatOpenAI")
    async def test_eligible_return(self, mock_llm_class):
        """When return is eligible, generate label."""
        # Mock LLM for eligibility check
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content='{"eligible": true, "reason": "Within window", "items_eligible": ["Blue T-Shirt"], "items_ineligible": [], "recommended_action": "generate_label"}'
        )
        mock_llm_class.return_value = mock_llm
        
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="I want to return the blue t-shirt",
        )
        state["order_data"] = {
            "order_number": "1234",
            "created_at": "2026-02-01T10:00:00Z",
            "line_items": [{"title": "Blue T-Shirt", "price": "29.99"}],
        }
        state["sentiment"] = "neutral"
        
        result = await handle_returns(state)
        
        assert result["current_agent"] == "returns"
        assert "approved" in result["response_draft"].lower() or "return" in result["response_draft"].lower()
    
    @patch("src.agents.nodes.returns.ChatOpenAI")
    async def test_ineligible_return(self, mock_llm_class):
        """When return is not eligible."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content='{"eligible": false, "reason": "Return window has passed", "items_eligible": [], "items_ineligible": ["Blue T-Shirt"], "recommended_action": "deny"}'
        )
        mock_llm_class.return_value = mock_llm
        
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="I want to return from old order",
        )
        state["order_data"] = {
            "order_number": "1234",
            "created_at": "2025-12-01T10:00:00Z",  # Old order
            "line_items": [{"title": "Blue T-Shirt", "price": "29.99"}],
        }
        state["sentiment"] = "neutral"
        
        result = await handle_returns(state)
        
        assert "not able" in result["response_draft"].lower() or "unfortunately" in result["response_draft"].lower()
