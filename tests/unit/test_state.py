"""Tests for agent state management."""

from datetime import datetime

from src.agents.state import create_initial_state


class TestCreateInitialState:
    """Tests for initial state creation."""

    def test_creates_valid_state(self):
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="Where is my order?",
        )

        assert state["conversation_id"] == "conv_123"
        assert state["store_id"] == "store_456"
        assert state["current_message"] == "Where is my order?"

    def test_default_values(self):
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="Hello",
        )

        assert state["intent"] == ""
        assert state["confidence"] == 0.0
        assert state["sentiment"] == "neutral"
        assert state["priority"] == "medium"
        assert state["requires_escalation"] is False
        assert state["messages"] == []
        assert state["actions_taken"] == []

    def test_has_timestamp(self):
        state = create_initial_state(
            conversation_id="conv_123",
            store_id="store_456",
            message="Hello",
        )

        assert "started_at" in state
        # Should be valid ISO format
        datetime.fromisoformat(state["started_at"])
