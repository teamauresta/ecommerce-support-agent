"""Knowledge base models for RAG."""

from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDMixin, TimestampMixin


class KnowledgeChunk(Base, UUIDMixin, TimestampMixin):
    """A chunk of content from a scraped website, with embedding."""

    __tablename__ = "knowledge_chunks"

    store_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("stores.id"),
        nullable=False,
    )

    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    page_title: Mapped[Optional[str]] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    embedding: Mapped[Any] = mapped_column(
        Vector(1536),
        nullable=False,
    )

    extra_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        Index(
            "ix_knowledge_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_knowledge_chunks_store_id", "store_id"),
        Index("ix_knowledge_chunks_store_url", "store_id", "source_url"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeChunk {self.source_url} [{self.chunk_index}]>"
