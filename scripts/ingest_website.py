#!/usr/bin/env python3
"""Scrape a website and ingest content into the knowledge base."""

import argparse
import asyncio

import sys
sys.path.insert(0, ".")

from src.config import settings
from src.database import get_session_context
from src.integrations.knowledge_base import WebScraper, get_kb_client


async def ingest(store_id: str, url: str, max_pages: int) -> None:
    """Scrape a website and ingest its content."""
    print(f"Scraping {url} (max {max_pages} pages)...")

    scraper = WebScraper(base_url=url, max_pages=max_pages)
    try:
        pages = await scraper.scrape()
    finally:
        await scraper.close()

    print(f"Scraped {len(pages)} pages.")

    if not pages:
        print("No content found. Nothing to ingest.")
        return

    kb = get_kb_client()
    async with get_session_context() as session:
        chunks_created = await kb.ingest_pages(session, store_id, pages)

    print(f"Ingested {chunks_created} chunks for store {store_id}.")


def main():
    parser = argparse.ArgumentParser(description="Scrape and ingest a website into the knowledge base")
    parser.add_argument("--store-id", required=True, help="Store UUID to associate content with")
    parser.add_argument("--url", required=True, help="Base URL to scrape")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=settings.kb_scrape_max_pages,
        help=f"Maximum pages to scrape (default: {settings.kb_scrape_max_pages})",
    )

    args = parser.parse_args()
    asyncio.run(ingest(store_id=args.store_id, url=args.url, max_pages=args.max_pages))


if __name__ == "__main__":
    main()
