"""API request/response schemas."""

from datetime import datetime
from typing import Any, Optional, List
from pydantic import BaseModel, Field


# === Conversation Schemas ===

class CreateConversationRequest(BaseModel):
    """Request to start a new conversation."""
    channel: str = Field(default="widget", description="Channel source")
    customer_email: Optional[str] = Field(None, description="Customer email")
    customer_name: Optional[str] = Field(None, description="Customer name")
    initial_message: str = Field(..., min_length=1, max_length=2000)
    context: Optional[dict[str, Any]] = Field(None, description="Additional context")


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str = Field(..., min_length=1, max_length=2000)
    attachments: Optional[List[str]] = None


class EscalateRequest(BaseModel):
    """Request to manually escalate a conversation."""
    reason: str = Field(..., min_length=1, max_length=500)
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    notes: Optional[str] = None


class ResolveRequest(BaseModel):
    """Request to mark a conversation as resolved."""
    resolution_summary: str = Field(..., min_length=1, max_length=1000)
    resolution_type: str = Field(default="automated", pattern="^(automated|human|customer)$")
    csat_score: Optional[int] = Field(None, ge=1, le=5)


# === Response Schemas ===

class MessageContent(BaseModel):
    """Message content."""
    content: str
    type: str = "text"


class AnalysisResult(BaseModel):
    """Analysis of a message."""
    intent: Optional[str]
    sentiment: Optional[str]
    confidence: Optional[float]


class ActionTaken(BaseModel):
    """Record of an action taken."""
    type: str
    data: dict[str, Any] = {}
    status: str = "completed"
    timestamp: Optional[str] = None


class ConversationResponse(BaseModel):
    """Response after creating a conversation."""
    conversation_id: str
    message_id: str
    response: MessageContent
    analysis: AnalysisResult
    actions_taken: List[ActionTaken] = []
    created_at: str


class MessageResponse(BaseModel):
    """Response after sending a message."""
    message_id: str
    response: MessageContent
    analysis: AnalysisResult
    actions_taken: List[ActionTaken] = []
    requires_escalation: bool = False
    created_at: str


class CustomerInfo(BaseModel):
    """Customer information."""
    email: Optional[str]
    name: Optional[str]


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
    primary_intent: Optional[str]
    sentiment: Optional[str]
    priority: str
    order_id: Optional[str]
    messages: List[MessageDetail]
    created_at: str
    updated_at: str


class ConversationSummary(BaseModel):
    """Conversation list item."""
    id: str
    status: str
    primary_intent: Optional[str]
    sentiment: Optional[str]
    customer_email: Optional[str]
    message_count: int
    created_at: str
    updated_at: str


class PaginatedResponse(BaseModel):
    """Paginated list response."""
    data: List[Any]
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
    csat_average: Optional[float]
    csat_count: int


class AnalyticsResponse(BaseModel):
    """Full analytics response."""
    period: dict[str, str]
    summary: AnalyticsSummary
    by_intent: dict[str, IntentStats]
    by_sentiment: dict[str, int]
    time_series: List[dict[str, Any]]
    actions_taken: dict[str, int]
