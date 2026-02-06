"""Knowledge base integration — web scraping, chunking, embedding, and retrieval."""

from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.knowledge import KnowledgeChunk

logger = structlog.get_logger()


class WebScraper:
    """Scrapes a website and extracts text content, following internal links."""

    def __init__(
        self,
        base_url: str,
        max_pages: int = 200,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.domain = urlparse(base_url).netloc
        self.max_pages = max_pages
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "EcomSupportBot/1.0"},
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def scrape(self) -> list[dict[str, Any]]:
        """
        Crawl the website starting from base_url.

        Returns:
            List of dicts: [{"url": str, "title": str, "content": str}, ...]
        """
        visited: set[str] = set()
        to_visit: list[str] = [self.base_url]
        pages: list[dict[str, Any]] = []

        while to_visit and len(visited) < self.max_pages:
            url = to_visit.pop(0)
            normalized = self._normalize_url(url)

            if normalized in visited:
                continue
            visited.add(normalized)

            try:
                response = await self.client.get(url)
                response.raise_for_status()
            except (httpx.HTTPError, httpx.RequestError) as e:
                logger.warning("scrape_page_error", url=url, error=str(e))
                continue

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                continue

            soup = BeautifulSoup(response.text, "lxml")

            text_content = self._extract_text(soup)
            title = soup.title.string.strip() if soup.title and soup.title.string else ""

            if text_content.strip():
                pages.append(
                    {
                        "url": str(response.url),
                        "title": title,
                        "content": text_content,
                    }
                )
                logger.debug("page_scraped", url=url, content_length=len(text_content))

            for link in soup.find_all("a", href=True):
                href = link["href"]
                absolute_url = urljoin(url, href)
                if (
                    self._is_internal(absolute_url)
                    and self._normalize_url(absolute_url) not in visited
                ):
                    to_visit.append(absolute_url)

        logger.info("scrape_completed", pages_scraped=len(pages), pages_visited=len(visited))
        return pages

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract readable text, removing nav/footer/script elements."""
        for tag in soup.find_all(
            ["script", "style", "nav", "footer", "header", "aside", "noscript"]
        ):
            tag.decompose()

        main = soup.find("main") or soup.find("article") or soup.find("body")
        if not main:
            return ""

        return main.get_text(separator="\n", strip=True)

    def _is_internal(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc == self.domain and parsed.scheme in ("http", "https")

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """
    Split text into chunks of approximately chunk_size tokens.

    Uses ~4 chars per token approximation and splits on paragraph boundaries.
    """
    char_size = chunk_size * 4
    char_overlap = chunk_overlap * 4

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        para_len = len(paragraph)

        if current_length + para_len > char_size and current_chunk:
            chunks.append("\n".join(current_chunk))

            # Keep overlap from trailing paragraphs
            overlap_parts: list[str] = []
            overlap_len = 0
            for p in reversed(current_chunk):
                if overlap_len + len(p) > char_overlap:
                    break
                overlap_parts.insert(0, p)
                overlap_len += len(p)

            current_chunk = overlap_parts
            current_length = overlap_len

        current_chunk.append(paragraph)
        current_length += para_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


class KnowledgeBaseClient:
    """Manages knowledge base: embedding generation, storage, and retrieval."""

    def __init__(self) -> None:
        self._embeddings: OpenAIEmbeddings | None = None

    @property
    def embeddings(self) -> OpenAIEmbeddings:
        if self._embeddings is None:
            self._embeddings = OpenAIEmbeddings(
                model=settings.kb_embedding_model,
                openai_api_key=settings.openai_api_key,
            )
        return self._embeddings

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        return await self.embeddings.aembed_documents(texts)

    async def generate_query_embedding(self, query: str) -> list[float]:
        return await self.embeddings.aembed_query(query)

    async def ingest_pages(
        self,
        session: AsyncSession,
        store_id: str,
        pages: list[dict[str, Any]],
    ) -> int:
        """
        Chunk pages, generate embeddings, and store in database.

        Replaces all existing chunks for this store (full re-index).
        Returns number of chunks created.
        """
        await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.store_id == store_id))
        logger.info("existing_chunks_deleted", store_id=store_id)

        all_chunks: list[dict[str, Any]] = []
        for page in pages:
            text_chunks = chunk_text(
                page["content"],
                chunk_size=settings.kb_chunk_size,
                chunk_overlap=settings.kb_chunk_overlap,
            )
            for i, chunk_content in enumerate(text_chunks):
                all_chunks.append(
                    {
                        "source_url": page["url"],
                        "page_title": page.get("title", ""),
                        "content": chunk_content,
                        "chunk_index": i,
                    }
                )

        if not all_chunks:
            logger.warning("no_chunks_generated", store_id=store_id)
            return 0

        batch_size = 100
        total_created = 0

        for batch_start in range(0, len(all_chunks), batch_size):
            batch = all_chunks[batch_start : batch_start + batch_size]
            texts = [c["content"] for c in batch]

            embeddings = await self.generate_embeddings(texts)

            for chunk_data, embedding in zip(batch, embeddings, strict=False):
                chunk = KnowledgeChunk(
                    store_id=store_id,
                    source_url=chunk_data["source_url"],
                    page_title=chunk_data["page_title"],
                    content=chunk_data["content"],
                    chunk_index=chunk_data["chunk_index"],
                    embedding=embedding,
                    extra_data={},
                )
                session.add(chunk)
                total_created += 1

            logger.info(
                "embedding_batch_complete",
                batch_start=batch_start,
                batch_size=len(batch),
                total=len(all_chunks),
            )

        await session.flush()
        logger.info("ingestion_complete", store_id=store_id, chunks_created=total_created)
        return total_created

    async def search(
        self,
        session: AsyncSession,
        store_id: str,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> list[dict[str, Any]]:
        """
        Search for chunks relevant to the query using cosine similarity.

        Returns:
            List of dicts: [{"content", "source_url", "page_title", "score"}, ...]
        """
        query_embedding = await self.generate_query_embedding(query)
        max_distance = 1.0 - threshold

        # Format embedding as PostgreSQL array literal
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        result = await session.execute(
            text(f"""
                SELECT
                    content,
                    source_url,
                    page_title,
                    1 - (embedding <=> '{embedding_str}'::vector) AS similarity
                FROM knowledge_chunks
                WHERE store_id = :store_id
                  AND (embedding <=> '{embedding_str}'::vector) <= :max_distance
                ORDER BY embedding <=> '{embedding_str}'::vector
                LIMIT :top_k
            """),
            {
                "store_id": store_id,
                "max_distance": max_distance,
                "top_k": top_k,
            },
        )

        rows = result.fetchall()
        return [
            {
                "content": row.content,
                "source_url": row.source_url,
                "page_title": row.page_title,
                "score": float(row.similarity),
            }
            for row in rows
        ]


_kb_client: KnowledgeBaseClient | None = None


def get_kb_client() -> KnowledgeBaseClient:
    """Get or create the knowledge base client singleton."""
    global _kb_client
    if _kb_client is None:
        _kb_client = KnowledgeBaseClient()
    return _kb_client
