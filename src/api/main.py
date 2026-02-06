"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.api.routes import conversations, health, webhooks, analytics
import structlog

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("application_startup", env=settings.app_env)
    yield
    logger.info("application_shutdown")


# Create FastAPI app
app = FastAPI(
    title="E-Commerce Support Agent",
    description="AI-powered customer support for e-commerce",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(
    conversations.router,
    prefix="/api/v1",
    tags=["Conversations"],
)
app.include_router(
    webhooks.router,
    prefix="/api/v1",
    tags=["Webhooks"],
)
app.include_router(
    analytics.router,
    prefix="/api/v1",
    tags=["Analytics"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "E-Commerce Support Agent",
        "version": "0.1.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
    )
