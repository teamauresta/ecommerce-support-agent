"""Rate limiting middleware."""

import time

import redis.asyncio as redis
import structlog
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings

logger = structlog.get_logger()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis."""

    def __init__(self, app, redis_url: str = None):
        super().__init__(app)
        self.redis_url = redis_url or settings.redis_url
        self._redis: redis.Redis | None = None

    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url)
        return self._redis

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)

        # Get identifier (API key or IP)
        identifier = self._get_identifier(request)

        # Check rate limit
        try:
            allowed, remaining, reset_at = await self._check_rate_limit(
                identifier,
                request.url.path,
            )
        except Exception as e:
            # If Redis fails, allow request but log
            logger.warning("rate_limit_check_failed", error=str(e))
            return await call_next(request)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(self._get_limit(request.url.path)),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                    "Retry-After": str(reset_at - int(time.time())),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self._get_limit(request.url.path))
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)

        return response

    def _get_identifier(self, request: Request) -> str:
        """Get unique identifier for rate limiting."""
        # Prefer API key, fall back to IP
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return f"key:{auth[7:20]}"  # Use prefix of key

        # Use client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        return f"ip:{request.client.host if request.client else 'unknown'}"

    def _get_limit(self, path: str) -> int:
        """Get rate limit for endpoint."""
        # Different limits for different endpoints
        if "/conversations" in path and "messages" in path:
            return 300  # 300 messages per minute
        elif "/conversations" in path:
            return 100  # 100 new conversations per minute
        else:
            return 1000  # 1000 for other endpoints

    async def _check_rate_limit(
        self,
        identifier: str,
        path: str,
    ) -> tuple[bool, int, int]:
        """
        Check if request is within rate limit.

        Returns: (allowed, remaining, reset_timestamp)
        """
        r = await self.get_redis()
        limit = self._get_limit(path)
        window = 60  # 1 minute window

        now = int(time.time())
        window_start = now - (now % window)
        key = f"ratelimit:{identifier}:{path}:{window_start}"

        # Increment counter
        current = await r.incr(key)

        # Set expiry on first request
        if current == 1:
            await r.expire(key, window + 1)

        remaining = max(0, limit - current)
        reset_at = window_start + window

        return current <= limit, remaining, reset_at
