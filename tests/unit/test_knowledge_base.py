"""Unit tests for knowledge base integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bs4 import BeautifulSoup

from src.integrations.knowledge_base import WebScraper, KnowledgeBaseClient, chunk_text


class TestChunkText:
    """Tests for text chunking function."""

    def test_short_text_single_chunk(self):
        """Short text should produce a single chunk."""
        text = "Hello world.\nThis is a test."
        chunks = chunk_text(text, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1
        assert "Hello world." in chunks[0]

    def test_long_text_multiple_chunks(self):
        """Long text should be split into multiple chunks."""
        paragraphs = [f"Paragraph {i} " * 50 for i in range(20)]
        text = "\n".join(paragraphs)
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1

    def test_overlap_between_chunks(self):
        """Chunks should have overlapping content at boundaries."""
        # Create text where each paragraph is distinct and fits roughly in chunks
        paragraphs = [f"Para-{i}: " + "x" * 100 for i in range(10)]
        text = "\n".join(paragraphs)
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=50)

        if len(chunks) >= 2:
            # The last paragraph of chunk N should appear in chunk N+1
            # (if it fits within the overlap window)
            first_paras = chunks[0].split("\n")
            second_paras = chunks[1].split("\n")
            # At least one paragraph from the end of chunk 0
            # should be at the start of chunk 1
            overlap = set(first_paras) & set(second_paras)
            assert len(overlap) > 0

    def test_empty_text(self):
        """Empty text should return no chunks."""
        assert chunk_text("") == []
        assert chunk_text("   \n\n  ") == []

    def test_whitespace_only_paragraphs_skipped(self):
        """Paragraphs that are only whitespace should be skipped."""
        text = "Real content.\n   \n\nMore content."
        chunks = chunk_text(text, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1
        assert "Real content." in chunks[0]
        assert "More content." in chunks[0]


class TestWebScraper:
    """Tests for web scraper."""

    def test_is_internal_same_domain(self):
        scraper = WebScraper(base_url="https://example.com")
        assert scraper._is_internal("https://example.com/about") is True
        assert scraper._is_internal("https://example.com/products/item") is True

    def test_is_internal_different_domain(self):
        scraper = WebScraper(base_url="https://example.com")
        assert scraper._is_internal("https://other.com/page") is False
        assert scraper._is_internal("https://subdomain.example.com/page") is False

    def test_is_internal_rejects_non_http(self):
        scraper = WebScraper(base_url="https://example.com")
        assert scraper._is_internal("ftp://example.com/file") is False
        assert scraper._is_internal("javascript:void(0)") is False

    def test_normalize_url_strips_trailing_slash(self):
        scraper = WebScraper(base_url="https://example.com")
        assert scraper._normalize_url("https://example.com/page/") == "https://example.com/page"
        assert scraper._normalize_url("https://example.com/page") == "https://example.com/page"

    def test_normalize_url_strips_fragment(self):
        scraper = WebScraper(base_url="https://example.com")
        url = scraper._normalize_url("https://example.com/page#section")
        assert "#" not in url

    def test_extract_text_removes_nav_footer(self):
        scraper = WebScraper(base_url="https://example.com")
        html = """
        <html><body>
            <nav>Navigation links</nav>
            <main><p>Main content here</p></main>
            <footer>Footer info</footer>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        text = scraper._extract_text(soup)
        assert "Main content here" in text
        assert "Navigation links" not in text
        assert "Footer info" not in text

    def test_extract_text_removes_script_style(self):
        scraper = WebScraper(base_url="https://example.com")
        html = """
        <html><body>
            <script>var x = 1;</script>
            <style>.hidden { display: none; }</style>
            <article><p>Article content</p></article>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        text = scraper._extract_text(soup)
        assert "Article content" in text
        assert "var x" not in text
        assert ".hidden" not in text

    def test_extract_text_prefers_main_over_body(self):
        scraper = WebScraper(base_url="https://example.com")
        html = """
        <html><body>
            <div>Outside main</div>
            <main><p>Inside main</p></main>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        text = scraper._extract_text(soup)
        assert "Inside main" in text

    def test_base_url_trailing_slash_stripped(self):
        scraper = WebScraper(base_url="https://example.com/")
        assert scraper.base_url == "https://example.com"


class TestKnowledgeBaseClient:
    """Tests for knowledge base client."""

    @pytest.fixture
    def kb_client(self):
        return KnowledgeBaseClient()

    @pytest.mark.asyncio
    async def test_search_returns_results(self, kb_client):
        """Test search returns formatted results."""
        mock_row = MagicMock()
        mock_row.content = "Test content"
        mock_row.source_url = "https://example.com/page"
        mock_row.page_title = "Test Page"
        mock_row.similarity = 0.85

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch.object(kb_client, "generate_query_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            results = await kb_client.search(mock_session, "store-123", "test query")

        assert len(results) == 1
        assert results[0]["content"] == "Test content"
        assert results[0]["source_url"] == "https://example.com/page"
        assert results[0]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_search_empty_results(self, kb_client):
        """Test search with no matching results."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch.object(kb_client, "generate_query_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            results = await kb_client.search(mock_session, "store-123", "query")

        assert results == []

    @pytest.mark.asyncio
    async def test_ingest_pages_creates_chunks(self, kb_client):
        """Test ingesting pages creates embeddings and stores chunks."""
        pages = [
            {
                "url": "https://example.com/page1",
                "title": "Page 1",
                "content": "Some content about products.",
            }
        ]

        mock_session = AsyncMock()

        with patch.object(kb_client, "generate_embeddings", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [[0.1] * 1536]
            count = await kb_client.ingest_pages(mock_session, "store-123", pages)

        assert count > 0
        assert mock_session.add.called
        assert mock_session.flush.called

    @pytest.mark.asyncio
    async def test_ingest_empty_pages(self, kb_client):
        """Test ingesting empty page list returns 0."""
        mock_session = AsyncMock()
        count = await kb_client.ingest_pages(mock_session, "store-123", [])

        assert count == 0
        assert not mock_session.add.called
