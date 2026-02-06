"""Store model."""

from typing import Any, Optional

from sqlalchemy import String, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin, TimestampMixin


class Store(Base, UUIDMixin, TimestampMixin):
    """E-commerce store configuration."""

    __tablename__ = "stores"

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # shopify, woocommerce

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # API credentials (encrypted in production)
    api_credentials: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Store-specific settings
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "auto_refund_limit": 50.0,
            "return_window_days": 30,
            "escalation_threshold": 0.6,
            "brand_voice": "friendly_professional",
        },
    )

    # Relationships
    conversations = relationship("Conversation", back_populates="store")

    def __repr__(self) -> str:
        return f"<Store {self.name} ({self.platform})>"
