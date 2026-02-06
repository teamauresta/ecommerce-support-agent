"""Conversation, Message, and Action models."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class ConversationStatus(StrEnum):
    """Conversation status values."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    ABANDONED = "abandoned"


class MessageRole(StrEnum):
    """Message sender role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Intent(StrEnum):
    """Customer intent categories."""

    ORDER_STATUS = "order_status"
    RETURN_REQUEST = "return_request"
    REFUND_REQUEST = "refund_request"
    ADDRESS_CHANGE = "address_change"
    CANCEL_ORDER = "cancel_order"
    PRODUCT_QUESTION = "product_question"
    SHIPPING_QUESTION = "shipping_question"
    COMPLAINT = "complaint"
    GENERAL_INQUIRY = "general_inquiry"
    OTHER = "other"


class Sentiment(StrEnum):
    """Customer sentiment."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"


class Priority(StrEnum):
    """Ticket priority."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Conversation(Base, UUIDMixin, TimestampMixin):
    """A customer support conversation."""

    __tablename__ = "conversations"

    # Store relationship
    store_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("stores.id"),
        nullable=False,
    )
    store = relationship("Store", back_populates="conversations")

    # Agent instance relationship
    agent_instance_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("agent_instances.id"),
        nullable=False,
        index=True,
    )
    agent_instance = relationship("AgentInstance", back_populates="conversations")

    # Customer info
    customer_email: Mapped[str | None] = mapped_column(String(255))
    customer_name: Mapped[str | None] = mapped_column(String(255))
    customer_id: Mapped[str | None] = mapped_column(String(255))

    # Channel
    channel: Mapped[str] = mapped_column(String(50), default="widget")

    # Status and analysis
    status: Mapped[str] = mapped_column(
        String(20),
        default=ConversationStatus.ACTIVE.value,
    )
    primary_intent: Mapped[str | None] = mapped_column(String(50))
    sentiment: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(20), default=Priority.MEDIUM.value)

    # Context
    order_id: Mapped[str | None] = mapped_column(String(100))
    external_ticket_id: Mapped[str | None] = mapped_column(String(100))

    # Resolution
    resolution_summary: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None]
    csat_score: Mapped[int | None] = mapped_column(Integer)

    # Extra data
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        order_by="Message.created_at",
    )
    actions: Mapped[list["Action"]] = relationship(
        "Action",
        back_populates="conversation",
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id[:8]} ({self.status})>"


class Message(Base, UUIDMixin, TimestampMixin):
    """A message in a conversation."""

    __tablename__ = "messages"

    # Conversation relationship
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("conversations.id"),
        nullable=False,
    )
    conversation = relationship("Conversation", back_populates="messages")

    # Content
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Analysis
    intent: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Float)

    # Metrics
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Extra data
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    def __repr__(self) -> str:
        return f"<Message {self.role}: {self.content[:30]}...>"


class Action(Base, UUIDMixin, TimestampMixin):
    """An action taken during a conversation."""

    __tablename__ = "actions"

    # Relationships
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("conversations.id"),
        nullable=False,
    )
    conversation = relationship("Conversation", back_populates="actions")

    message_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("messages.id"),
    )

    # Action details
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None]

    def __repr__(self) -> str:
        return f"<Action {self.action_type} ({self.status})>"
