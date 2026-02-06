"""Billing and usage tracking models."""

from datetime import datetime, date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Date,
    Integer,
    Numeric,
    ForeignKey,
    Index,
    String,
    Boolean,
    DateTime,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin, TimestampMixin


class ConversationUsage(Base, UUIDMixin, TimestampMixin):
    """Tracks conversation usage per organization per month for billing."""

    __tablename__ = "conversation_usage"

    # Links
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    agent_instance_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("agent_instances.id"),
        nullable=True,
    )  # Optional: track per instance

    # Time period
    month: Mapped[date] = mapped_column(Date, nullable=False)  # First day of month

    # Usage
    conversation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Billing
    billed_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )  # Null until billed
    billed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    organization = relationship("Organization", back_populates="usage_records")

    __table_args__ = (
        Index("idx_usage_org_month", "organization_id", "month", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationUsage org={self.organization_id[:8]} "
            f"month={self.month} count={self.conversation_count}>"
        )


class OrganizationAPIKey(Base, UUIDMixin, TimestampMixin):
    """API keys for programmatic access to the platform."""

    __tablename__ = "organization_api_keys"

    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id"),
        nullable=False,
    )

    # Key
    key_prefix: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )  # sk_live_xxx or sk_test_xxx
    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )  # bcrypt hash

    # Metadata
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )  # "Production API Key"
    scopes: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: ["conversations:create"],
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    organization = relationship("Organization")

    def __repr__(self) -> str:
        return f"<OrganizationAPIKey {self.name} ({self.key_prefix})>"
