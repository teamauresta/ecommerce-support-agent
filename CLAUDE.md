# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered customer support agent for e-commerce stores using LangGraph. Handles order status (WISMO), returns, refunds, and general inquiries with sentiment-aware routing and automatic escalation to human agents.

## Common Commands

```bash
make dev              # Install all dependencies (prod + dev) and set up pre-commit hooks
make run              # Start FastAPI server with hot reload on port 8000
make test             # Run all tests
make test-unit        # Run unit tests only
make test-component   # Run component tests only
make lint             # Run ruff, black --check, and mypy
make format           # Auto-format with ruff --fix and black
make docker-up        # Start Postgres (pgvector) and Redis via docker-compose
make migrate          # Run alembic migrations
make migrate-new      # Create new alembic migration (interactive prompt for name)
```

Run a single test file: `pytest tests/unit/test_classifier.py -v`
Run a single test: `pytest tests/unit/test_classifier.py::test_function_name -v`

## Architecture

**Request flow:** React chat widget → FastAPI API (`src/api/`) → LangGraph agent (`src/agents/graph.py`) → External integrations (Shopify, Gorgias, EasyPost)

**LangGraph agent pipeline** (defined in `src/agents/graph.py`):
1. `classify_intent` → determines customer intent (order_status, return_request, refund_request, complaint, etc.)
2. `analyze_sentiment` → detects emotional tone and recommends response tone
3. `fetch_context` → retrieves order/customer data from integrations
4. `route_to_agent` → conditional edge routing to specialist node based on intent (see `INTENT_TO_AGENT` map in `src/agents/nodes/router.py`)
5. Specialist node (`wismo`, `returns`, `refunds`, or `general`) → handles the specific request
6. `build_response` → finalizes the response text
7. `check_escalation` → conditional edge: either ends or routes to `handle_escalation`

The graph is compiled once at module load via `get_compiled_graph()` and invoked asynchronously with `graph.ainvoke(state)`.

**State:** `ConversationState` (TypedDict in `src/agents/state.py`) flows through all nodes. Uses `Annotated[list, add]` for `messages` and `actions_taken` fields to enable append-style updates across nodes.

**Routing logic:** Complaints and frustrated customers (sentiment intensity ≥ 4) are escalated directly. Low confidence (< 0.5) routes to the general agent. Otherwise, routes by intent.

## Key Design Patterns

- **Settings:** Pydantic `BaseSettings` in `src/config.py`, loaded from `.env`. Access via `from src.config import settings`.
- **Database:** Async SQLAlchemy with `asyncpg`. Session via `get_session()` (FastAPI dependency) or `get_session_context()` (context manager). Engine uses `NullPool` in dev/test, connection pooling in production.
- **Models:** All models inherit from `Base` + `UUIDMixin` (UUID primary key) + `TimestampMixin` (created_at/updated_at). Defined in `src/models/`.
- **Integrations:** Each external service has a client class in `src/integrations/`. `ShopifyClient` uses `httpx.AsyncClient`. In development, `MockShopifyClient` returns fixture data.
- **API auth:** API key in `Authorization` header (`Bearer sk_live_xxx` or `sk_test_xxx`). `sk_test_` keys create a dev store automatically.
- **LLM prompts:** All prompt templates live in `src/agents/prompts.py`. They expect JSON responses from the LLM for structured nodes and natural language for response-generation nodes.
- **Logging:** Uses `structlog` throughout. Log with key-value pairs: `logger.info("event_name", key=value)`.

## Tech Stack

- Python 3.11+, FastAPI, LangGraph/LangChain, OpenAI (gpt-4o-mini default, gpt-4o for reasoning)
- PostgreSQL 15 with pgvector, Redis, SQLAlchemy 2.0 async, Alembic
- Testing: pytest with pytest-asyncio (`asyncio_mode = "auto"`), httpx `AsyncClient` for API tests
- Linting: ruff + black (line-length 100) + mypy (mypy configured with `ignore_missing_imports = true`)

## Testing

Tests use `APP_ENV=testing` set in `conftest.py`. The test database is `test_support_agent` on localhost. Tests mock external services (Shopify, OpenAI) — never call real APIs in tests. The `client` fixture provides an async httpx test client against the FastAPI app.

## Database Sessions

Two session patterns are used consistently:
- **FastAPI routes:** Use `get_session()` as a dependency (`session: AsyncSession = Depends(get_session)`)
- **Standalone code:** Use `get_session_context()` as an async context manager:
  ```python
  from src.database import get_session_context

  async with get_session_context() as session:
      # Database operations here
      pass  # Auto-commits on exit, rolls back on exception
  ```

## API Structure

All API routes in `src/api/routes/` return FastAPI responses. Main endpoints:
- `/api/v1/conversations` - Create conversations and send messages
- `/api/v1/webhooks/shopify/*` - Shopify webhook handlers
- `/api/v1/analytics/*` - Usage tracking and metrics
- `/api/v1/knowledge-base/*` - KB management and search
- `/health` and `/health/ready` - Health checks

Auth is enforced via `AuthMiddleware.verify_api_key` dependency.
