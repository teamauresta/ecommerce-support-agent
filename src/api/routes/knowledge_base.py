"""Knowledge base API routes — ingestion and status."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_session
from src.integrations.knowledge_base import WebScraper, get_kb_client
from src.models.knowledge import KnowledgeChunk
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/knowledge-base")


class IngestRequest(BaseModel):
    store_id: str
    url: HttpUrl
    max_pages: int = settings.kb_scrape_max_pages


class IngestResponse(BaseModel):
    pages_scraped: int
    chunks_created: int


class KBStatusResponse(BaseModel):
    store_id: str
    total_chunks: int
    unique_urls: int


@router.post("/ingest", response_model=IngestResponse)
async def ingest_website(
    request: IngestRequest,
    session: AsyncSession = Depends(get_session),
):
    """Scrape a website and ingest its content into the knowledge base."""
    scraper = WebScraper(
        base_url=str(request.url),
        max_pages=request.max_pages,
    )
    try:
        pages = await scraper.scrape()
    except Exception as e:
        logger.error("scrape_failed", url=str(request.url), error=str(e))
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e}")
    finally:
        await scraper.close()

    if not pages:
        return IngestResponse(pages_scraped=0, chunks_created=0)

    kb = get_kb_client()
    chunks_created = await kb.ingest_pages(session, request.store_id, pages)

    logger.info(
        "ingest_complete",
        store_id=request.store_id,
        pages=len(pages),
        chunks=chunks_created,
    )
    return IngestResponse(pages_scraped=len(pages), chunks_created=chunks_created)


@router.get("/{store_id}/status", response_model=KBStatusResponse)
async def knowledge_base_status(
    store_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get knowledge base status for a store."""
    total_chunks = await session.scalar(
        select(func.count()).where(KnowledgeChunk.store_id == store_id)
    )
    unique_urls = await session.scalar(
        select(func.count(func.distinct(KnowledgeChunk.source_url))).where(
            KnowledgeChunk.store_id == store_id
        )
    )

    return KBStatusResponse(
        store_id=store_id,
        total_chunks=total_chunks or 0,
        unique_urls=unique_urls or 0,
    )
