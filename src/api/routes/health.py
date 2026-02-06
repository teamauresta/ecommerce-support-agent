"""Health check endpoints."""

import json

from fastapi import APIRouter, Response

from src.database import check_db_connection

router = APIRouter()


@router.get("/health")
async def health():
    """Basic health check."""
    return {"status": "healthy"}


@router.get("/health/ready")
async def readiness():
    """Readiness check for load balancers."""
    checks = {
        "database": await check_db_connection(),
    }

    all_healthy = all(checks.values())

    return Response(
        content=json.dumps(
            {
                "status": "ready" if all_healthy else "not_ready",
                "checks": checks,
            }
        ),
        status_code=200 if all_healthy else 503,
        media_type="application/json",
    )


@router.get("/health/live")
async def liveness():
    """Liveness check for container orchestration."""
    return {"status": "alive"}
