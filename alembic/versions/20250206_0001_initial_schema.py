"""Initial schema with stores, conversations, messages.

Revision ID: 0001
Revises: 
Create Date: 2025-02-06 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # Stores table
    op.create_table(
        "stores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("shopify_shop_id", sa.String(255), nullable=True, unique=True),
        sa.Column("shopify_access_token", sa.Text, nullable=True),
        sa.Column("gorgias_domain", sa.String(255), nullable=True),
        sa.Column("gorgias_api_key", sa.Text, nullable=True),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("brand_voice", sa.Text, nullable=True),
        sa.Column("policies", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_stores_domain", "stores", ["domain"])
    op.create_index("ix_stores_shopify_shop_id", "stores", ["shopify_shop_id"])
    
    # Conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("store_id", sa.String(36), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("channel", sa.String(50), nullable=False, server_default="chat"),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("primary_intent", sa.String(100), nullable=True),
        sa.Column("sentiment", sa.String(50), nullable=True),
        sa.Column("is_escalated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("escalation_reason", sa.Text, nullable=True),
        sa.Column("gorgias_ticket_id", sa.String(255), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_conversations_store_id", "conversations", ["store_id"])
    op.create_index("ix_conversations_customer_email", "conversations", ["customer_email"])
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_index("ix_conversations_created_at", "conversations", ["created_at"])
    
    # Messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),  # user, assistant, system
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("intent", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("sentiment", sa.String(50), nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("actions_taken", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    
    # Knowledge base documents table
    op.create_table(
        "kb_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("store_id", sa.String(36), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_kb_documents_store_id", "kb_documents", ["store_id"])
    op.create_index("ix_kb_documents_category", "kb_documents", ["category"])
    
    # Knowledge base chunks table (for RAG)
    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float), nullable=True),  # Or use pgvector
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_kb_chunks_document_id", "kb_chunks", ["document_id"])
    
    # Escalation tickets table
    op.create_table(
        "escalations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", sa.String(36), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("priority", sa.String(50), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("context_summary", sa.Text, nullable=True),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("external_ticket_id", sa.String(255), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_escalations_conversation_id", "escalations", ["conversation_id"])
    op.create_index("ix_escalations_store_id", "escalations", ["store_id"])
    op.create_index("ix_escalations_status", "escalations", ["status"])
    
    # Metrics/analytics table
    op.create_table(
        "metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("store_id", sa.String(36), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("conversations_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("conversations_automated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("conversations_escalated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_response_time_ms", sa.Integer, nullable=True),
        sa.Column("avg_resolution_time_ms", sa.Integer, nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("intents", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("sentiments", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_metrics_store_id_date", "metrics", ["store_id", "date"], unique=True)


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("metrics")
    op.drop_table("escalations")
    op.drop_table("kb_chunks")
    op.drop_table("kb_documents")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("stores")
    op.execute("DROP EXTENSION IF EXISTS vector")
