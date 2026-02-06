"""LangGraph state definition for the support agent."""

from datetime import UTC
from operator import add
from typing import Annotated, Any, TypedDict


class OrderData(TypedDict, total=False):
    """Order information from Shopify."""

    id: str
    order_number: str
    email: str
    customer_name: str
    status: str
    fulfillment_status: str | None
    financial_status: str
    total_price: float
    currency: str
    line_items: list[dict[str, Any]]
    shipping_address: dict[str, Any]
    tracking_numbers: list[str]
    tracking_urls: list[str]
    carrier: str | None
    created_at: str
    updated_at: str


class CustomerData(TypedDict, total=False):
    """Customer information."""

    id: str
    email: str
    name: str
    total_orders: int
    total_spent: float
    tags: list[str]
    is_vip: bool


class ActionLog(TypedDict):
    """Record of an action taken."""

    type: str
    data: dict[str, Any]
    status: str
    timestamp: str


class ConversationState(TypedDict, total=False):
    """
    State passed through the LangGraph agent workflow.

    This state is updated by each node in the graph and carries
    all context needed for decision-making.
    """

    # === Identifiers ===
    conversation_id: str
    store_id: str

    # === Messages ===
    # Using Annotated with add to append messages
    messages: Annotated[list[dict[str, Any]], add]
    current_message: str

    # === Intent Classification ===
    intent: str
    sub_intents: list[str]
    confidence: float

    # === Sentiment Analysis ===
    sentiment: str
    sentiment_intensity: float  # 1-5 scale
    recommended_tone: str

    # === Priority ===
    priority: str

    # === Extracted Entities ===
    order_id: str | None
    order_number: str | None
    email: str | None
    tracking_number: str | None
    product_id: str | None
    refund_amount: float | None

    # === Retrieved Context ===
    order_data: OrderData | None
    customer_data: CustomerData | None
    policy_context: list[str]

    # === Agent Processing ===
    current_agent: str
    agent_reasoning: str

    # === Actions ===
    suggested_actions: list[dict[str, Any]]
    actions_taken: Annotated[list[ActionLog], add]

    # === Response ===
    response_draft: str
    final_response: str

    # === Escalation ===
    requires_escalation: bool
    escalation_reason: str | None
    escalation_priority: str

    # === Metadata ===
    started_at: str
    tokens_used: int
    model_used: str
    error: str | None


def create_initial_state(
    conversation_id: str,
    store_id: str,
    message: str,
) -> ConversationState:
    """Create initial state for a new conversation turn."""
    from datetime import datetime

    return ConversationState(
        conversation_id=conversation_id,
        store_id=store_id,
        messages=[],
        current_message=message,
        intent="",
        sub_intents=[],
        confidence=0.0,
        sentiment="neutral",
        sentiment_intensity=3.0,
        recommended_tone="professional",
        priority="medium",
        order_id=None,
        order_number=None,
        email=None,
        tracking_number=None,
        product_id=None,
        refund_amount=None,
        order_data=None,
        customer_data=None,
        policy_context=[],
        current_agent="",
        agent_reasoning="",
        suggested_actions=[],
        actions_taken=[],
        response_draft="",
        final_response="",
        requires_escalation=False,
        escalation_reason=None,
        escalation_priority="medium",
        started_at=datetime.now(UTC).isoformat(),
        tokens_used=0,
        model_used="",
        error=None,
    )
