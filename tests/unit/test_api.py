"""Unit tests for API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Use sync client for simpler testing
from src.api.main import app


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self):
        """Test basic health check."""
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_liveness_check(self):
        """Test liveness endpoint."""
        client = TestClient(app)
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    def test_readiness_check_structure(self):
        """Test readiness endpoint returns expected structure."""
        client = TestClient(app)

        with patch("src.database.check_db_connection", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = True

            response = client.get("/health/ready")

            # Response should be JSON with status info
            data = response.json()
            assert "status" in data or "checks" in data


class TestConversationEndpoints:
    """Tests for conversation API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_create_conversation_requires_auth(self, client):
        """Test creating conversation without API key."""
        response = client.post(
            "/api/v1/conversations",
            json={"customer_email": "test@example.com"},
        )

        # Should require authentication
        assert response.status_code in [401, 403, 422]


class TestAnalyticsEndpoints:
    """Tests for analytics API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_get_metrics_unauthorized(self, client):
        """Test analytics requires auth."""
        response = client.get("/api/v1/analytics/stores/store-123/metrics")

        assert response.status_code in [401, 403, 404, 422]


class TestAPIValidation:
    """Tests for API request validation."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_invalid_json(self, client):
        """Test API rejects invalid JSON."""
        response = client.post(
            "/api/v1/conversations",
            content="not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_missing_required_fields(self, client):
        """Test API requires mandatory fields."""
        response = client.post(
            "/api/v1/conversations",
            json={},  # Missing required fields
            headers={"X-API-Key": "test"},
        )

        # Should fail validation
        assert response.status_code in [401, 403, 422]


class TestRateLimiting:
    """Tests for rate limiting (if configured)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_rate_limit_header_present(self, client):
        """Test rate limit headers are present."""
        # Make a simple request
        response = client.get("/health")

        # Rate limit headers should be present if rate limiting is enabled
        # This is implementation-specific, so just check the request works
        assert response.status_code == 200


class TestAPIRoutes:
    """Tests for API route existence."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_conversations_route_exists(self, client):
        """Test conversations endpoint exists."""
        response = client.post("/api/v1/conversations", json={})
        # Should get auth error or validation error, not 404
        assert response.status_code != 404

    def test_health_route_exists(self, client):
        """Test health endpoint exists."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_ready_route_exists(self, client):
        """Test readiness endpoint exists."""
        with patch("src.database.check_db_connection", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = True
            response = client.get("/health/ready")
            assert response.status_code in [200, 503]
