"""Shipping integration for return labels."""

from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()


@dataclass
class Address:
    """Shipping address."""

    name: str
    street1: str
    city: str
    state: str
    zip_code: str
    country: str = "US"
    street2: str = ""
    phone: str = ""
    email: str = ""


@dataclass
class ReturnLabel:
    """Return shipping label."""

    tracking_number: str
    label_url: str
    carrier: str
    service: str
    cost: float
    estimated_days: int


class ShippingClient:
    """Client for shipping operations (EasyPost or similar)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.easypost.com/v2"
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                auth=(self.api_key, ""),
            )
        return self._client

    async def create_return_label(
        self,
        customer_address: Address,
        store_address: Address,
        weight_oz: float = 16,
        carrier: str = "USPS",
    ) -> ReturnLabel:
        """
        Create a prepaid return shipping label.

        Args:
            customer_address: Ship from (customer)
            store_address: Ship to (store warehouse)
            weight_oz: Package weight in ounces
            carrier: Preferred carrier

        Returns:
            ReturnLabel with tracking and label URL
        """
        try:
            # Create addresses
            from_address = await self._create_address(customer_address)
            to_address = await self._create_address(store_address)

            # Create parcel
            parcel = await self._create_parcel(weight_oz)

            # Create shipment
            shipment = await self._create_shipment(
                from_address["id"],
                to_address["id"],
                parcel["id"],
                is_return=True,
            )

            # Buy cheapest rate for carrier
            rate = self._select_rate(shipment["rates"], carrier)

            if not rate:
                raise ValueError(f"No rates available for {carrier}")

            # Buy the label
            purchased = await self._buy_label(shipment["id"], rate["id"])

            return ReturnLabel(
                tracking_number=purchased["tracking_code"],
                label_url=purchased["postage_label"]["label_url"],
                carrier=rate["carrier"],
                service=rate["service"],
                cost=float(rate["rate"]),
                estimated_days=rate.get("delivery_days", 5),
            )

        except Exception as e:
            logger.error("shipping_label_error", error=str(e))
            raise

    async def _create_address(self, address: Address) -> dict[str, Any]:
        """Create an address in EasyPost."""
        response = await self.client.post(
            f"{self.base_url}/addresses",
            json={
                "address": {
                    "name": address.name,
                    "street1": address.street1,
                    "street2": address.street2,
                    "city": address.city,
                    "state": address.state,
                    "zip": address.zip_code,
                    "country": address.country,
                    "phone": address.phone,
                    "email": address.email,
                }
            },
        )
        response.raise_for_status()
        return response.json()

    async def _create_parcel(self, weight_oz: float) -> dict[str, Any]:
        """Create a parcel."""
        response = await self.client.post(
            f"{self.base_url}/parcels",
            json={
                "parcel": {
                    "weight": weight_oz,
                    "predefined_package": "Parcel",
                }
            },
        )
        response.raise_for_status()
        return response.json()

    async def _create_shipment(
        self,
        from_address_id: str,
        to_address_id: str,
        parcel_id: str,
        is_return: bool = False,
    ) -> dict[str, Any]:
        """Create a shipment to get rates."""
        response = await self.client.post(
            f"{self.base_url}/shipments",
            json={
                "shipment": {
                    "from_address": {"id": from_address_id},
                    "to_address": {"id": to_address_id},
                    "parcel": {"id": parcel_id},
                    "is_return": is_return,
                }
            },
        )
        response.raise_for_status()
        return response.json()

    def _select_rate(
        self,
        rates: list[dict],
        preferred_carrier: str,
    ) -> dict | None:
        """Select the best rate."""
        # Filter by carrier
        carrier_rates = [r for r in rates if r["carrier"] == preferred_carrier]

        if not carrier_rates:
            # Fall back to any carrier
            carrier_rates = rates

        if not carrier_rates:
            return None

        # Select cheapest
        return min(carrier_rates, key=lambda r: float(r["rate"]))

    async def _buy_label(self, shipment_id: str, rate_id: str) -> dict[str, Any]:
        """Buy a shipping label."""
        response = await self.client.post(
            f"{self.base_url}/shipments/{shipment_id}/buy", json={"rate": {"id": rate_id}}
        )
        response.raise_for_status()
        return response.json()

    async def get_tracking(self, tracking_number: str, carrier: str) -> dict[str, Any]:
        """Get tracking information."""
        response = await self.client.post(
            f"{self.base_url}/trackers",
            json={
                "tracker": {
                    "tracking_code": tracking_number,
                    "carrier": carrier,
                }
            },
        )
        response.raise_for_status()
        data = response.json()

        return {
            "status": data.get("status"),
            "status_detail": data.get("status_detail"),
            "estimated_delivery": data.get("est_delivery_date"),
            "events": [
                {
                    "datetime": e.get("datetime"),
                    "message": e.get("message"),
                    "city": e.get("tracking_location", {}).get("city"),
                    "state": e.get("tracking_location", {}).get("state"),
                }
                for e in data.get("tracking_details", [])
            ],
        }


class MockShippingClient(ShippingClient):
    """Mock shipping client for development."""

    def __init__(self):
        self.api_key = "mock"

    async def create_return_label(
        self,
        customer_address: Address,
        store_address: Address,
        weight_oz: float = 16,
        carrier: str = "USPS",
    ) -> ReturnLabel:
        """Return mock label data."""
        import random
        import string

        tracking = "1Z" + "".join(random.choices(string.ascii_uppercase + string.digits, k=16))

        return ReturnLabel(
            tracking_number=tracking,
            label_url=f"https://example.com/labels/{tracking}.pdf",
            carrier=carrier,
            service="Priority Mail",
            cost=0.0,  # Prepaid by store
            estimated_days=3,
        )

    async def get_tracking(self, tracking_number: str, carrier: str) -> dict[str, Any]:
        """Return mock tracking data."""
        return {
            "status": "in_transit",
            "status_detail": "Package is in transit to destination",
            "estimated_delivery": "2026-02-10",
            "events": [
                {
                    "datetime": "2026-02-06T10:00:00Z",
                    "message": "Package picked up",
                    "city": "New York",
                    "state": "NY",
                },
            ],
        }


# Get client based on environment
def get_shipping_client() -> ShippingClient:
    """Get shipping client."""
    if settings.is_development:
        return MockShippingClient()

    # In production, would get API key from settings
    api_key = getattr(settings, "easypost_api_key", None)
    if not api_key:
        return MockShippingClient()

    return ShippingClient(api_key)
