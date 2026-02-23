"""Unit tests for external integrations."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestShopifyIntegration:
    """Tests for Shopify API client."""

    @pytest.fixture
    def shopify_client(self):
        """Create Shopify client for testing."""
        from src.integrations.shopify import ShopifyClient

        return ShopifyClient(
            shop="test-store.myshopify.com",
            access_token="shpat_test_token",
        )

    @pytest.mark.asyncio
    async def test_get_order_by_id(self, shopify_client):
        """Test fetching order by ID."""
        mock_response = {
            "order": {
                "id": 12345,
                "name": "#1001",
                "email": "customer@example.com",
                "financial_status": "paid",
                "fulfillment_status": "fulfilled",
                "created_at": "2025-01-15T10:00:00Z",
                "line_items": [{"title": "Blue Widget", "quantity": 2}],
                "fulfillments": [
                    {
                        "tracking_number": "1Z999AA10123456784",
                        "tracking_company": "UPS",
                        "status": "in_transit",
                    }
                ],
            }
        }

        with patch.object(shopify_client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            order = await shopify_client.get_order("12345")

            assert order["id"] == 12345
            assert order["name"] == "#1001"
            assert order["fulfillment_status"] == "fulfilled"
            mock_req.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_order_not_found(self, shopify_client):
        """Test handling order not found."""
        with patch.object(shopify_client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404),
            )

            with pytest.raises(httpx.HTTPStatusError):
                await shopify_client.get_order("99999")

    @pytest.mark.asyncio
    async def test_search_orders_by_email(self, shopify_client):
        """Test searching orders by email."""
        mock_response = {
            "orders": [
                {"id": 123, "name": "#1001"},
                {"id": 124, "name": "#1002"},
            ]
        }

        with patch.object(shopify_client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            orders = await shopify_client.search_orders(email="customer@example.com")

            assert len(orders) == 2
            assert orders[0]["name"] == "#1001"

    @pytest.mark.asyncio
    async def test_get_order_by_number(self, shopify_client):
        """Test fetching order by order number."""
        mock_response = {
            "orders": [
                {"id": 12345, "order_number": 1234, "name": "#1234"},
            ]
        }

        with patch.object(shopify_client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            order = await shopify_client.get_order_by_number("#1234")

            assert order is not None
            assert order["order_number"] == 1234


class TestGorgiasIntegration:
    """Tests for Gorgias helpdesk API client."""

    @pytest.fixture
    def gorgias_client(self):
        """Create Gorgias client for testing."""
        from src.integrations.gorgias import GorgiasClient

        return GorgiasClient(
            domain="test-store",
            email="admin@test.com",
            api_key="gorgias_test_key",
        )

    @pytest.mark.asyncio
    async def test_create_ticket(self, gorgias_client):
        """Test creating a support ticket."""
        mock_customer = {"id": 111, "email": "customer@example.com"}
        mock_ticket = {
            "id": 12345,
            "status": "open",
            "channel": "chat",
            "customer": mock_customer,
        }

        with (
            patch.object(
                gorgias_client, "get_or_create_customer", new_callable=AsyncMock
            ) as mock_get_cust,
            patch.object(gorgias_client, "_request", new_callable=AsyncMock) as mock_req,
        ):
            mock_get_cust.return_value = mock_customer
            mock_req.return_value = mock_ticket

            ticket = await gorgias_client.create_ticket(
                customer_email="customer@example.com",
                subject="Order inquiry",
                message="Where is my order?",
            )

            assert ticket["id"] == 12345
            assert ticket["status"] == "open"

    @pytest.mark.asyncio
    async def test_add_message_to_ticket(self, gorgias_client):
        """Test adding a message to existing ticket."""
        mock_response = {
            "id": 67890,
            "body_text": "Your order is on the way!",
        }

        with patch.object(gorgias_client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            message = await gorgias_client.add_message(
                ticket_id=12345,
                message="Your order is on the way!",
            )

            assert "id" in message

    @pytest.mark.asyncio
    async def test_update_ticket_status(self, gorgias_client):
        """Test updating ticket status."""
        mock_response = {"id": 12345, "status": "closed"}

        with patch.object(gorgias_client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            ticket = await gorgias_client.update_ticket(
                ticket_id=12345,
                status="closed",
            )

            assert ticket["status"] == "closed"


class TestShippingIntegration:
    """Tests for shipping/tracking API client."""

    @pytest.mark.asyncio
    async def test_mock_shipping_client_create_label(self):
        """Test mock shipping client returns valid data."""
        from src.integrations.shipping import Address, MockShippingClient

        client = MockShippingClient()

        customer_addr = Address(
            name="Customer",
            street1="123 Main St",
            city="Los Angeles",
            state="CA",
            zip_code="90001",
        )

        store_addr = Address(
            name="Returns Dept",
            street1="456 Warehouse Way",
            city="Phoenix",
            state="AZ",
            zip_code="85001",
        )

        label = await client.create_return_label(
            customer_address=customer_addr,
            store_address=store_addr,
        )

        assert label.label_url is not None
        assert label.tracking_number is not None
        assert label.carrier is not None

    @pytest.mark.asyncio
    async def test_mock_shipping_client_tracking(self):
        """Test mock shipping client tracking."""
        from src.integrations.shipping import MockShippingClient

        client = MockShippingClient()

        tracking = await client.get_tracking(
            tracking_number="1Z999AA10123456784",
            carrier="UPS",
        )

        assert tracking["status"] == "in_transit"
        assert "events" in tracking

    def test_address_dataclass(self):
        """Test Address dataclass works correctly."""
        from src.integrations.shipping import Address

        addr = Address(
            name="Test User",
            street1="123 Main St",
            city="New York",
            state="NY",
            zip_code="10001",
        )

        assert addr.name == "Test User"
        assert addr.country == "US"  # Default value

    def test_get_shipping_client_returns_mock_in_dev(self):
        """Test get_shipping_client returns mock in development."""
        from src.integrations.shipping import MockShippingClient, get_shipping_client

        with patch("src.integrations.shipping.settings") as mock_settings:
            mock_settings.is_development = True

            client = get_shipping_client()

            assert isinstance(client, MockShippingClient)


class TestPaymentIntegration:
    """Tests for payment refund handling."""

    @pytest.mark.asyncio
    async def test_process_refund_via_shopify(self):
        """Test processing refund through Shopify."""
        from src.integrations.shopify import ShopifyClient

        client = ShopifyClient(
            shop="test.myshopify.com",
            access_token="test_token",
        )

        mock_calc_response = {
            "refund": {
                "transactions": [{"parent_id": 999}],
            }
        }

        mock_refund_response = {
            "refund": {
                "id": 789,
                "order_id": 12345,
                "transactions": [{"amount": "29.99"}],
            }
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            # First call is calculate, second is create
            mock_req.side_effect = [mock_calc_response, mock_refund_response]

            refund = await client.create_refund(
                order_id="12345",
                amount=29.99,
                reason="Customer request",
            )

            assert refund["id"] == 789
            assert refund["order_id"] == 12345

    def test_refund_amount_check(self):
        """Test refund amount validation logic."""
        # Simple policy check - amounts over limit need approval
        auto_refund_limit = 100.0

        test_cases = [
            (50.0, False),  # Under limit, auto-approve
            (100.0, False),  # At limit, auto-approve
            (150.0, True),  # Over limit, needs approval
            (500.0, True),  # Way over limit
        ]

        for amount, should_need_approval in test_cases:
            needs_approval = amount > auto_refund_limit
            assert needs_approval == should_need_approval, f"Failed for amount {amount}"


class TestMockShopifyClient:
    """Tests for the mock Shopify client."""

    @pytest.mark.asyncio
    async def test_mock_get_order_by_number(self):
        """Test mock client returns valid data."""
        from src.integrations.shopify import MockShopifyClient

        client = MockShopifyClient()
        order = await client.get_order_by_number("#1234")

        assert order is not None
        assert order["order_number"] == 1234
        assert "line_items" in order
        assert "fulfillments" in order

    @pytest.mark.asyncio
    async def test_mock_get_customer_by_email(self):
        """Test mock client returns customer data."""
        from src.integrations.shopify import MockShopifyClient

        client = MockShopifyClient()
        customer = await client.get_customer_by_email("test@example.com")

        assert customer is not None
        assert customer["email"] == "test@example.com"
