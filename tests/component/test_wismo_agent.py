"""Tests for WISMO agent."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.nodes.wismo import _status_to_friendly, handle_wismo
from src.agents.state import create_initial_state


class TestStatusToFriendly:
    """Tests for status conversion."""

    def test_processing(self):
        assert _status_to_friendly("processing") == "being prepared for shipment"

    def test_shipped(self):
        assert _status_to_friendly("shipped") == "on its way to you"

    def test_delivered(self):
        assert _status_to_friendly("delivered") == "delivered"

    def test_unknown(self):
        assert _status_to_friendly("custom_status") == "custom_status"


@pytest.mark.asyncio
class TestHandleWismo:
    """Tests for WISMO handler."""

    async def test_no_order_data_no_order_id(self):
        """When no order info is available, ask for it."""
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="Where is my order?",
        )
        state["order_data"] = None
        state["order_id"] = None

        result = await handle_wismo(state)

        assert "order number" in result["response_draft"].lower()
        assert result["current_agent"] == "wismo"

    async def test_no_order_data_with_order_id(self):
        """When order ID given but not found."""
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="Where is order #1234?",
        )
        state["order_data"] = None
        state["order_id"] = "1234"

        result = await handle_wismo(state)

        assert "#1234" in result["response_draft"]
        assert (
            "not found" in result["response_draft"].lower()
            or "double-check" in result["response_draft"].lower()
        )

    @patch("src.agents.nodes.wismo.ChatOpenAI")
    async def test_with_order_data(self, mock_llm_class, sample_order):
        """When order data is available, generate response."""
        # Mock LLM response
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content="Your order #1234 is on its way! Tracking: 1Z999AA10123456784"
        )
        mock_llm_class.return_value = mock_llm

        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="Where is order #1234?",
        )
        state["order_data"] = {
            "order_number": "1234",
            "status": "shipped",
            "fulfillment_status": "fulfilled",
            "line_items": [{"title": "Blue T-Shirt", "quantity": 1}],
            "tracking_numbers": ["1Z999AA10123456784"],
            "tracking_urls": ["https://ups.com/track"],
            "carrier": "UPS",
        }
        state["sentiment"] = "neutral"
        state["sentiment_intensity"] = 3
        state["recommended_tone"] = "professional"

        result = await handle_wismo(state)

        assert result["current_agent"] == "wismo"
        assert "response_draft" in result
        assert result["agent_reasoning"]
