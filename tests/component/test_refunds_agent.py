"""Tests for Refunds agent."""

import pytest
from unittest.mock import AsyncMock, patch

from src.agents.nodes.refunds import handle_refunds
from src.agents.state import create_initial_state


@pytest.mark.asyncio
class TestHandleRefunds:
    """Tests for refunds handler."""
    
    async def test_no_order_data_no_order_id(self):
        """When no order info available, ask for it."""
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="I want a refund",
        )
        state["order_data"] = None
        state["order_id"] = None
        
        result = await handle_refunds(state)
        
        assert "order number" in result["response_draft"].lower()
        assert result["current_agent"] == "refunds"
    
    @patch("src.agents.nodes.refunds.ChatOpenAI")
    async def test_auto_approve_under_limit(self, mock_llm_class):
        """Small refund gets auto-approved."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content='{"auto_approve": true, "amount": 25.00, "reason": "Under limit", "requires_return": false, "escalation_needed": false}'
        )
        mock_llm_class.return_value = mock_llm
        
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="I need a refund for $25",
        )
        state["order_data"] = {
            "order_number": "1234",
            "total_price": "49.99",
            "created_at": "2026-02-01T10:00:00Z",
        }
        state["refund_amount"] = 25.0
        state["sentiment"] = "neutral"
        
        result = await handle_refunds(state)
        
        assert result["current_agent"] == "refunds"
        assert any(a["type"] == "refund_processed" for a in result.get("actions_taken", []))
        assert "refund" in result["response_draft"].lower()
    
    @patch("src.agents.nodes.refunds.ChatOpenAI")
    async def test_escalate_over_limit(self, mock_llm_class):
        """Large refund needs escalation."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content='{"auto_approve": false, "amount": 150.00, "escalation_needed": true, "escalation_reason": "Amount exceeds auto-approve limit"}'
        )
        mock_llm_class.return_value = mock_llm
        
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="I need a full refund for my $150 order",
        )
        state["order_data"] = {
            "order_number": "1234",
            "total_price": "150.00",
            "created_at": "2026-02-01T10:00:00Z",
        }
        state["refund_amount"] = 150.0
        state["sentiment"] = "neutral"
        
        result = await handle_refunds(state)
        
        assert result["requires_escalation"] is True
        assert "team" in result["response_draft"].lower() or "review" in result["response_draft"].lower()
    
    @patch("src.agents.nodes.refunds.ChatOpenAI")
    async def test_frustrated_customer_tone(self, mock_llm_class):
        """Response adapts to frustrated customer."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content='{"auto_approve": true, "amount": 25.00, "reason": "Customer complaint", "requires_return": false, "escalation_needed": false}'
        )
        mock_llm_class.return_value = mock_llm
        
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="This is ridiculous! I want my money back!",
        )
        state["order_data"] = {
            "order_number": "1234",
            "total_price": "25.00",
            "created_at": "2026-02-01T10:00:00Z",
        }
        state["sentiment"] = "frustrated"
        
        result = await handle_refunds(state)
        
        # Should have empathetic language
        response = result["response_draft"].lower()
        assert any(word in response for word in ["understand", "sorry", "frustration", "apologize"])
