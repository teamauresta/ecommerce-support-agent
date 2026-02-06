"""Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_debug: bool = False
    app_secret_key: str = "change-me"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/support_agent"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str = ""
    default_model: str = "gpt-4o-mini"
    reasoning_model: str = "gpt-4o"

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str | None = None
    langchain_project: str = "ecommerce-support"

    # Shopify
    shopify_api_key: str | None = None
    shopify_api_secret: str | None = None

    # Gorgias
    gorgias_domain: str | None = None
    gorgias_email: str | None = None
    gorgias_api_key: str | None = None

    # Agent Settings
    auto_refund_limit: float = 50.0
    return_window_days: int = 30
    escalation_confidence_threshold: float = 0.6
    max_tokens_per_response: int = 500

    # Knowledge Base / RAG
    kb_embedding_model: str = "text-embedding-3-small"
    kb_embedding_dimensions: int = 1536
    kb_chunk_size: int = 500
    kb_chunk_overlap: int = 50
    kb_retrieval_top_k: int = 5
    kb_similarity_threshold: float = 0.3
    kb_scrape_max_pages: int = 200
    kb_scrape_timeout: float = 10.0

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_testing(self) -> bool:
        return self.app_env == "testing"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
