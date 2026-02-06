"""API request/response schemas."""

from typing import Any

from pydantic import BaseModel, Field

# === Conversation Schemas ===


class CreateConversationRequest(BaseModel):
    """Request to start a new conversation."""

    channel: str = Field(default="widget", description="Channel source")
    customer_email: str | None = Field(None, description="Customer email")
    customer_name: str | None = Field(None, description="Customer name")
    initial_message: str = Field(..., min_length=1, max_length=2000)
    context: dict[str, Any] | None = Field(None, description="Additional context")


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""

    content: str = Field(..., min_length=1, max_length=2000)
    attachments: list[str] | None = None


class EscalateRequest(BaseModel):
    """Request to manually escalate a conversation."""

    reason: str = Field(..., min_length=1, max_length=500)
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    notes: str | None = None


class ResolveRequest(BaseModel):
    """Request to mark a conversation as resolved."""

    resolution_summary: str = Field(..., min_length=1, max_length=1000)
    resolution_type: str = Field(default="automated", pattern="^(automated|human|customer)$")
    csat_score: int | None = Field(None, ge=1, le=5)


# === Response Schemas ===


class MessageContent(BaseModel):
    """Message content."""

    content: str
    type: str = "text"


class AnalysisResult(BaseModel):
    """Analysis of a message."""

    intent: str | None
    sentiment: str | None
    confidence: float | None


class ActionTaken(BaseModel):
    """Record of an action taken."""

    type: str
    data: dict[str, Any] = {}
    status: str = "completed"
    timestamp: str | None = None


class ConversationResponse(BaseModel):
    """Response after creating a conversation."""

    conversation_id: str
    message_id: str
    response: MessageContent
    analysis: AnalysisResult
    actions_taken: list[ActionTaken] = []
    created_at: str


class MessageResponse(BaseModel):
    """Response after sending a message."""

    message_id: str
    response: MessageContent
    analysis: AnalysisResult
    actions_taken: list[ActionTaken] = []
    requires_escalation: bool = False
    created_at: str


class CustomerInfo(BaseModel):
    """Customer information."""

    email: str | None
    name: str | None


class MessageDetail(BaseModel):
    """Message detail."""

    id: str
    role: str
    content: str
    created_at: str


class ConversationDetail(BaseModel):
    """Full conversation details."""

    id: str
    store_id: str
    status: str
    channel: str
    customer: CustomerInfo
    primary_intent: str | None
    sentiment: str | None
    priority: str
    order_id: str | None
    messages: list[MessageDetail]
    created_at: str
    updated_at: str


class ConversationSummary(BaseModel):
    """Conversation list item."""

    id: str
    status: str
    primary_intent: str | None
    sentiment: str | None
    customer_email: str | None
    message_count: int
    created_at: str
    updated_at: str


class PaginatedResponse(BaseModel):
    """Paginated list response."""

    data: list[Any]
    pagination: dict[str, int]


# === Analytics Schemas ===


class IntentStats(BaseModel):
    """Intent statistics."""

    count: int
    percentage: float
    automation_rate: float


class AnalyticsSummary(BaseModel):
    """Analytics summary."""

    total_conversations: int
    total_messages: int
    automation_rate: float
    escalation_rate: float
    avg_response_time_ms: int
    avg_resolution_time_seconds: int
    csat_average: float | None
    csat_count: int


class AnalyticsResponse(BaseModel):
    """Full analytics response."""

    period: dict[str, str]
    summary: AnalyticsSummary
    by_intent: dict[str, IntentStats]
    by_sentiment: dict[str, int]
    time_series: list[dict[str, Any]]
    actions_taken: dict[str, int]
