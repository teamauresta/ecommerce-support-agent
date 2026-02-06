"""Database connection and session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool


# Lazy engine initialization
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _create_engine() -> AsyncEngine:
    """Create the async engine with appropriate pool settings."""
    from src.config import settings
    
    # Base options
    options: dict = {
        "echo": settings.app_debug,
    }
    
    # In development/testing, use NullPool (no connection pooling)
    # In production, use connection pooling
    if settings.is_testing or settings.is_development:
        options["poolclass"] = NullPool
    else:
        options["poolclass"] = AsyncAdaptedQueuePool
        options["pool_size"] = settings.database_pool_size
        options["max_overflow"] = settings.database_max_overflow
        options["pool_pre_ping"] = True
        options["pool_recycle"] = 3600  # Recycle connections after 1 hour
    
    return create_async_engine(settings.database_url, **options)


def get_engine() -> AsyncEngine:
    """Get or create the database engine (lazy initialization)."""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session (FastAPI dependency)."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session as context manager."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_connection() -> bool:
    """Check database connectivity."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


def reset_engine() -> None:
    """Reset the engine (useful for testing)."""
    global _engine, _session_factory
    if _engine is not None:
        # Note: In async context, you should await engine.dispose()
        pass
    _engine = None
    _session_factory = None
