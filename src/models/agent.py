"""Agent definition and instance models."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class AgentDefinition(Base, UUIDMixin, TimestampMixin):
    """Template/blueprint for agent types (customer_service, sales, marketing, etc.)."""

    __tablename__ = "agent_definitions"

    # Identity
    type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )  # customer_service, sales, marketing
    version: Mapped[str] = mapped_column(String(50), nullable=False)  # 2.1.0
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Configuration
    graph_module: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )  # e.g., "src.agents.customer_service.graph"
    capabilities: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    default_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Tier restrictions
    tier_restrictions: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )  # {"min_tier": "pro"}

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deprecated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Relationships
    instances = relationship("AgentInstance", back_populates="definition")

    __table_args__ = (Index("idx_agent_type_version", "type", "version"),)

    def __repr__(self) -> str:
        return f"<AgentDefinition {self.type} v{self.version}>"


class AgentInstance(Base, UUIDMixin, TimestampMixin):
    """Deployed agent tied to a specific store."""

    __tablename__ = "agent_instances"

    # Relationships
    store_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("stores.id"),
        nullable=False,
        index=True,
    )
    agent_definition_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("agent_definitions.id"),
        nullable=False,
    )

    # Identity
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )  # e.g., "Auresta CS Agent"
    public_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )  # pk_widget_xxx

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
    )  # active, paused, archived

    # Configuration
    config_overrides: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Metadata
    deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    deployed_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )  # user email or "system"

    # Relationships
    store = relationship("Store", back_populates="agent_instances")
    definition = relationship("AgentDefinition", back_populates="instances")
    conversations = relationship("Conversation", back_populates="agent_instance")

    def __repr__(self) -> str:
        return f"<AgentInstance {self.name} ({self.status})>"
