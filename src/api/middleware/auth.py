"""Authentication middleware."""

from typing import Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_session
from src.models import Store
import structlog

logger = structlog.get_logger()

# API key header
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


class AuthMiddleware:
    """Authentication middleware for API requests."""
    
    @staticmethod
    async def verify_api_key(
        authorization: Optional[str] = Security(api_key_header),
        session: AsyncSession = Depends(get_session),
    ) -> Store:
        """
        Verify API key and return associated store.
        
        API keys are expected in format: Bearer sk_live_xxx or sk_test_xxx
        """
        if not authorization:
            raise HTTPException(
                status_code=401,
                detail="Missing API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Extract key from Bearer token
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]
        else:
            api_key = authorization
        
        # Validate key format
        if not api_key.startswith(("sk_live_", "sk_test_")):
            raise HTTPException(
                status_code=401,
                detail="Invalid API key format",
            )
        
        # Look up store by API key
        # In production, API keys would be hashed and stored separately
        result = await session.execute(
            select(Store).where(
                Store.api_credentials["api_key"].astext == api_key
            )
        )
        store = result.scalar_one_or_none()
        
        if not store:
            # For development, allow any key with dev store
            if api_key.startswith("sk_test_"):
                from src.api.routes.conversations import _get_or_create_dev_store
                store_id = await _get_or_create_dev_store(session)
                result = await session.execute(
                    select(Store).where(Store.id == store_id)
                )
                store = result.scalar_one_or_none()
        
        if not store:
            logger.warning("invalid_api_key", key_prefix=api_key[:15])
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
            )
        
        if not store.is_active:
            raise HTTPException(
                status_code=403,
                detail="Store is deactivated",
            )
        
        return store


async def get_api_key(
    authorization: Optional[str] = Security(api_key_header),
) -> Optional[str]:
    """Extract API key from header (for optional auth)."""
    if not authorization:
        return None
    
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return authorization
