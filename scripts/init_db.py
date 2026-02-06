#!/usr/bin/env python3
"""Initialize the database with tables."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from src.database import engine
from src.models import Base


async def init_db():
    """Create all tables."""
    print("Creating database tables...")
    
    async with engine.begin() as conn:
        # Enable pgvector extension
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            print("✓ pgvector extension enabled")
        except Exception as e:
            print(f"⚠ Could not enable pgvector: {e}")
        
        # Create tables
        await conn.run_sync(Base.metadata.create_all)
        print("✓ Tables created")
    
    print("Database initialization complete!")


if __name__ == "__main__":
    asyncio.run(init_db())
