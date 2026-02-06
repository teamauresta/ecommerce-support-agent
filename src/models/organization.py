"""Organization model for multi-tenancy."""

from decimal import Decimal
from typing import Any

from sqlalchemy import String, Integer, Numeric, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin, TimestampMixin


class Organization(Base, UUIDMixin, TimestampMixin):
    """Top-level tenant - represents a business/company using the platform."""

    __tablename__ = "organizations"

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    # Billing
    tier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="basic",
    )  # basic, pro, enterprise
    billing_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subscription_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="trial",
    )  # trial, active, suspended, cancelled

    # Usage limits
    monthly_conversation_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1000,
    )
    overage_rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("0.10"),
    )

    # Settings
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    stores = relationship(
        "Store",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    usage_records = relationship(
        "ConversationUsage",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name} ({self.tier})>"
