"""Shopify API integration."""

from typing import Any, Optional
from functools import lru_cache

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()


class ShopifyClient:
    """Client for Shopify Admin API."""
    
    def __init__(self, shop: str, access_token: str):
        """
        Initialize Shopify client.
        
        Args:
            shop: Shop domain (e.g., "mystore.myshopify.com")
            access_token: Shopify Admin API access token
        """
        self.shop = shop
        self.base_url = f"https://{shop}/admin/api/2024-01"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=self.headers,
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Make an API request."""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "shopify_api_error",
                status_code=e.response.status_code,
                url=url,
                response=e.response.text[:500],
            )
            raise
        except httpx.RequestError as e:
            logger.error("shopify_request_error", url=url, error=str(e))
            raise
    
    # === Orders ===
    
    async def get_order(self, order_id: str) -> dict[str, Any]:
        """
        Fetch order by Shopify order ID.
        
        Args:
            order_id: Shopify order ID (numeric)
            
        Returns:
            Order data dict
        """
        data = await self._request("GET", f"orders/{order_id}.json")
        return data.get("order", {})
    
    async def get_order_by_number(self, order_number: str) -> Optional[dict[str, Any]]:
        """
        Fetch order by order number (e.g., #1234).
        
        Args:
            order_number: Order number (with or without #)
            
        Returns:
            Order data dict or None if not found
        """
        # Remove # if present
        number = order_number.lstrip("#")
        
        data = await self._request(
            "GET",
            "orders.json",
            params={"name": number, "status": "any"}
        )
        
        orders = data.get("orders", [])
        
        # Match exact order number
        for order in orders:
            if str(order.get("order_number")) == number:
                return order
        
        # Try with # prefix
        for order in orders:
            if order.get("name", "").lstrip("#") == number:
                return order
        
        return None
    
    async def search_orders(
        self,
        email: Optional[str] = None,
        customer_id: Optional[str] = None,
        status: str = "any",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search orders by customer email or ID.
        
        Args:
            email: Customer email
            customer_id: Shopify customer ID
            status: Order status filter
            limit: Max orders to return
            
        Returns:
            List of order dicts
        """
        params: dict[str, Any] = {"status": status, "limit": limit}
        
        if email:
            params["email"] = email
        if customer_id:
            params["customer_id"] = customer_id
        
        data = await self._request("GET", "orders.json", params=params)
        return data.get("orders", [])
    
    async def add_order_note(self, order_id: str, note: str) -> dict[str, Any]:
        """Add or update order note."""
        data = await self._request(
            "PUT",
            f"orders/{order_id}.json",
            json={"order": {"note": note}}
        )
        return data.get("order", {})
    
    # === Customers ===
    
    async def get_customer(self, customer_id: str) -> dict[str, Any]:
        """Fetch customer by ID."""
        data = await self._request("GET", f"customers/{customer_id}.json")
        return data.get("customer", {})
    
    async def get_customer_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """Search for customer by email."""
        data = await self._request(
            "GET",
            "customers/search.json",
            params={"query": f"email:{email}"}
        )
        customers = data.get("customers", [])
        return customers[0] if customers else None
    
    # === Refunds ===
    
    async def create_refund(
        self,
        order_id: str,
        amount: float,
        reason: str,
        notify_customer: bool = True,
    ) -> dict[str, Any]:
        """
        Create a refund for an order.
        
        Args:
            order_id: Shopify order ID
            amount: Refund amount
            reason: Reason for refund
            notify_customer: Whether to email customer
            
        Returns:
            Refund data dict
        """
        # First calculate available refund
        calc_data = await self._request(
            "POST",
            f"orders/{order_id}/refunds/calculate.json",
            json={"refund": {"shipping": {"amount": 0}}}
        )
        
        # Create the refund
        data = await self._request(
            "POST",
            f"orders/{order_id}/refunds.json",
            json={
                "refund": {
                    "notify": notify_customer,
                    "note": reason,
                    "shipping": {"amount": 0},
                    "transactions": [{
                        "parent_id": calc_data["refund"]["transactions"][0]["parent_id"],
                        "amount": amount,
                        "kind": "refund",
                    }]
                }
            }
        )
        
        return data.get("refund", {})
    
    # === Products ===
    
    async def get_product(self, product_id: str) -> dict[str, Any]:
        """Fetch product by ID."""
        data = await self._request("GET", f"products/{product_id}.json")
        return data.get("product", {})
    
    async def search_products(
        self,
        title: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search products."""
        params: dict[str, Any] = {"limit": limit}
        if title:
            params["title"] = title
        
        data = await self._request("GET", "products.json", params=params)
        return data.get("products", [])


# Store client cache
_client_cache: dict[str, ShopifyClient] = {}


async def get_shopify_client(store_id: str) -> ShopifyClient:
    """
    Get or create Shopify client for a store.
    
    In production, this would fetch credentials from database.
    For now, uses environment variables for development.
    """
    if store_id in _client_cache:
        return _client_cache[store_id]
    
    # TODO: Fetch from database in production
    # For development, use env vars
    from src.database import get_session_context
    from src.models import Store
    from sqlalchemy import select
    
    try:
        async with get_session_context() as session:
            result = await session.execute(
                select(Store).where(Store.id == store_id)
            )
            store = result.scalar_one_or_none()
            
            if store and store.api_credentials:
                client = ShopifyClient(
                    shop=store.domain,
                    access_token=store.api_credentials.get("access_token", ""),
                )
                _client_cache[store_id] = client
                return client
    except Exception as e:
        logger.warning("store_fetch_error", store_id=store_id, error=str(e))
    
    # Fallback to env vars for development
    if settings.is_development:
        # Create mock client for development
        return MockShopifyClient()
    
    raise ValueError(f"Store {store_id} not found or not configured")


class MockShopifyClient(ShopifyClient):
    """Mock Shopify client for development/testing."""
    
    def __init__(self):
        self.shop = "test.myshopify.com"
        self._client = None
    
    async def get_order_by_number(self, order_number: str) -> Optional[dict[str, Any]]:
        """Return mock order data."""
        number = order_number.lstrip("#")
        
        # Return mock data
        return {
            "id": 12345,
            "order_number": int(number),
            "name": f"#{number}",
            "email": "customer@example.com",
            "financial_status": "paid",
            "fulfillment_status": "fulfilled",
            "total_price": "49.99",
            "currency": "USD",
            "created_at": "2026-02-01T10:00:00Z",
            "updated_at": "2026-02-03T14:00:00Z",
            "line_items": [
                {"title": "Blue T-Shirt", "quantity": 1, "price": "29.99"},
                {"title": "Black Socks", "quantity": 2, "price": "9.99"},
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
                "country": "US",
            },
        }
    
    async def get_customer_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """Return mock customer data."""
        return {
            "id": 67890,
            "email": email,
            "first_name": "John",
            "last_name": "Doe",
            "orders_count": 5,
            "total_spent": "249.95",
            "tags": "",
        }
