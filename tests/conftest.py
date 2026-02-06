"""Pytest configuration and fixtures."""

import os
import pytest
import asyncio
from typing import AsyncGenerator

# Set testing environment BEFORE any other imports
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test_support_agent")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")

import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    from src.api.main import app
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def sample_order():
    """Sample order data for testing."""
    return {
        "id": 12345,
        "order_number": 1234,
        "name": "#1234",
        "email": "customer@example.com",
        "financial_status": "paid",
        "fulfillment_status": "fulfilled",
        "total_price": "49.99",
        "currency": "USD",
        "created_at": "2026-02-01T10:00:00Z",
        "line_items": [
            {"title": "Blue T-Shirt", "quantity": 1, "price": "29.99"},
        ],
        "fulfillments": [{
            "tracking_number": "1Z999AA10123456784",
            "tracking_company": "UPS",
            "tracking_url": "https://www.ups.com/track?tracknum=1Z999AA10123456784",
        }],
        "shipping_address": {
            "name": "John Doe",
            "address1": "123 Main St",
            "city": "New York",
            "province": "NY",
            "zip": "10001",
        },
    }


@pytest.fixture
def sample_customer():
    """Sample customer data for testing."""
    return {
        "id": 67890,
        "email": "customer@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "orders_count": 5,
        "total_spent": "249.95",
        "tags": "",
    }
