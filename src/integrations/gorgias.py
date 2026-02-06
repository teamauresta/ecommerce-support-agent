"""Gorgias helpdesk integration."""

import base64
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class GorgiasClient:
    """Client for Gorgias API."""

    def __init__(self, domain: str, email: str, api_key: str):
        """
        Initialize Gorgias client.

        Args:
            domain: Gorgias subdomain (e.g., "mystore" for mystore.gorgias.com)
            email: Account email
            api_key: API key
        """
        self.base_url = f"https://{domain}.gorgias.com/api"

        # Basic auth
        credentials = base64.b64encode(f"{email}:{api_key}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }

        self._client: httpx.AsyncClient | None = None

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
                "gorgias_api_error",
                status_code=e.response.status_code,
                url=url,
                response=e.response.text[:500],
            )
            raise
        except httpx.RequestError as e:
            logger.error("gorgias_request_error", url=url, error=str(e))
            raise

    # === Customers ===

    async def get_or_create_customer(self, email: str, name: str = None) -> dict[str, Any]:
        """Get existing customer or create new one."""
        # Search for existing
        try:
            data = await self._request("GET", "customers", params={"email": email})
            customers = data.get("data", [])

            if customers:
                return customers[0]
        except Exception:
            pass

        # Create new
        customer_data = {"email": email}
        if name:
            parts = name.split(" ", 1)
            customer_data["firstname"] = parts[0]
            if len(parts) > 1:
                customer_data["lastname"] = parts[1]

        data = await self._request("POST", "customers", json=customer_data)
        return data

    async def get_customer(self, customer_id: int) -> dict[str, Any]:
        """Get customer by ID."""
        return await self._request("GET", f"customers/{customer_id}")

    # === Tickets ===

    async def create_ticket(
        self,
        customer_email: str,
        subject: str,
        message: str,
        channel: str = "chat",
        tags: list[str] = None,
        customer_name: str = None,
    ) -> dict[str, Any]:
        """
        Create a new support ticket.

        Args:
            customer_email: Customer's email
            subject: Ticket subject
            message: Initial message content
            channel: Channel type (chat, email, etc.)
            tags: Tags to apply
            customer_name: Customer's name

        Returns:
            Created ticket data
        """
        # Get or create customer
        customer = await self.get_or_create_customer(customer_email, customer_name)

        ticket_data = {
            "customer": {"id": customer["id"]},
            "channel": channel,
            "subject": subject,
            "messages": [
                {
                    "channel": channel,
                    "sender": {"id": customer["id"]},
                    "body_text": message,
                    "via": "api",
                    "source": {"type": "api"},
                }
            ],
        }

        if tags:
            ticket_data["tags"] = [{"name": tag} for tag in tags]

        data = await self._request("POST", "tickets", json=ticket_data)

        logger.info(
            "gorgias_ticket_created",
            ticket_id=data.get("id"),
            customer_email=customer_email,
        )

        return data

    async def get_ticket(self, ticket_id: int) -> dict[str, Any]:
        """Get ticket by ID."""
        return await self._request("GET", f"tickets/{ticket_id}")

    async def update_ticket(
        self,
        ticket_id: int,
        status: str = None,
        tags: list[str] = None,
        assignee_user_id: int = None,
        priority: str = None,
    ) -> dict[str, Any]:
        """
        Update ticket properties.

        Args:
            ticket_id: Ticket ID
            status: New status (open, closed)
            tags: Tags to set
            assignee_user_id: User ID to assign to
            priority: Priority level
        """
        update: dict[str, Any] = {}

        if status:
            update["status"] = status
        if tags is not None:
            update["tags"] = [{"name": tag} for tag in tags]
        if assignee_user_id:
            update["assignee_user"] = {"id": assignee_user_id}
        if priority:
            update["priority"] = priority

        data = await self._request("PUT", f"tickets/{ticket_id}", json=update)
        return data

    async def close_ticket(self, ticket_id: int) -> dict[str, Any]:
        """Close a ticket."""
        return await self.update_ticket(ticket_id, status="closed")

    # === Messages ===

    async def add_message(
        self,
        ticket_id: int,
        message: str,
        sender_type: str = "agent",  # agent or customer
        internal: bool = False,
    ) -> dict[str, Any]:
        """
        Add a message to a ticket.

        Args:
            ticket_id: Ticket ID
            message: Message content
            sender_type: Who sent it (agent or customer)
            internal: Whether it's an internal note
        """
        data = await self._request(
            "POST",
            f"tickets/{ticket_id}/messages",
            json={
                "channel": "chat",
                "body_text": message,
                "via": "api",
                "sender": {"type": sender_type},
                "internal": internal,
                "source": {"type": "api"},
            },
        )
        return data

    async def add_internal_note(
        self,
        ticket_id: int,
        note: str,
    ) -> dict[str, Any]:
        """Add an internal note to a ticket."""
        return await self.add_message(ticket_id, note, sender_type="agent", internal=True)

    # === Tags ===

    async def add_tags(self, ticket_id: int, tags: list[str]) -> dict[str, Any]:
        """Add tags to a ticket."""
        # Get current tags
        ticket = await self.get_ticket(ticket_id)
        current_tags = [t["name"] for t in ticket.get("tags", [])]

        # Merge tags
        all_tags = list(set(current_tags + tags))

        return await self.update_ticket(ticket_id, tags=all_tags)

    # === Macros ===

    async def list_macros(self) -> list[dict[str, Any]]:
        """List available macros."""
        data = await self._request("GET", "macros")
        return data.get("data", [])

    async def apply_macro(self, ticket_id: int, macro_id: int) -> dict[str, Any]:
        """Apply a macro to a ticket."""
        return await self._request(
            "POST", f"tickets/{ticket_id}/macros", json={"macro_id": macro_id}
        )


# Client cache
_gorgias_clients: dict[str, GorgiasClient] = {}


async def get_gorgias_client(store_id: str) -> GorgiasClient | None:
    """
    Get or create Gorgias client for a store.

    Returns None if Gorgias is not configured for the store.
    """
    if store_id in _gorgias_clients:
        return _gorgias_clients[store_id]

    # Fetch store configuration
    from sqlalchemy import select

    from src.database import get_session_context
    from src.models import Store

    try:
        async with get_session_context() as session:
            result = await session.execute(select(Store).where(Store.id == store_id))
            store = result.scalar_one_or_none()

            if store and store.api_credentials.get("gorgias_domain"):
                client = GorgiasClient(
                    domain=store.api_credentials["gorgias_domain"],
                    email=store.api_credentials["gorgias_email"],
                    api_key=store.api_credentials["gorgias_api_key"],
                )
                _gorgias_clients[store_id] = client
                return client
    except Exception as e:
        logger.warning("gorgias_client_error", store_id=store_id, error=str(e))

    return None


async def sync_conversation_to_gorgias(
    store_id: str,
    conversation_id: str,
    customer_email: str,
    customer_name: str,
    messages: list[dict],
    intent: str,
    external_ticket_id: str = None,
) -> int | None:
    """
    Sync a conversation to Gorgias as a ticket.

    Returns the Gorgias ticket ID.
    """
    gorgias = await get_gorgias_client(store_id)
    if not gorgias:
        logger.debug("gorgias_not_configured", store_id=store_id)
        return None

    try:
        if external_ticket_id:
            # Add messages to existing ticket
            ticket_id = int(external_ticket_id)

            for msg in messages:
                await gorgias.add_message(
                    ticket_id=ticket_id,
                    message=msg["content"],
                    sender_type="agent" if msg["role"] == "assistant" else "customer",
                )

            return ticket_id
        else:
            # Create new ticket
            if not messages:
                return None

            ticket = await gorgias.create_ticket(
                customer_email=customer_email,
                customer_name=customer_name,
                subject=f"Support: {intent}",
                message=messages[0]["content"],
                tags=["ai-handled", intent],
            )

            ticket_id = ticket["id"]

            # Add remaining messages
            for msg in messages[1:]:
                await gorgias.add_message(
                    ticket_id=ticket_id,
                    message=msg["content"],
                    sender_type="agent" if msg["role"] == "assistant" else "customer",
                )

            logger.info(
                "conversation_synced_to_gorgias",
                conversation_id=conversation_id,
                ticket_id=ticket_id,
            )

            return ticket_id

    except Exception as e:
        logger.error(
            "gorgias_sync_error",
            conversation_id=conversation_id,
            error=str(e),
        )
        return None


async def escalate_to_gorgias(
    store_id: str,
    conversation_id: str,
    customer_email: str,
    customer_name: str,
    summary: str,
    reason: str,
    priority: str = "normal",
) -> int | None:
    """
    Create an escalation ticket in Gorgias.

    Returns the Gorgias ticket ID.
    """
    gorgias = await get_gorgias_client(store_id)
    if not gorgias:
        return None

    try:
        ticket = await gorgias.create_ticket(
            customer_email=customer_email,
            customer_name=customer_name,
            subject=f"[Escalation] {reason}",
            message=summary,
            tags=["escalation", "ai-escalated", priority],
        )

        # Add internal note with context
        await gorgias.add_internal_note(
            ticket["id"],
            f"🤖 AI Escalation\n\n"
            f"Reason: {reason}\n"
            f"Priority: {priority}\n"
            f"Conversation ID: {conversation_id}\n\n"
            f"Summary:\n{summary}",
        )

        logger.info(
            "escalation_created_in_gorgias",
            conversation_id=conversation_id,
            ticket_id=ticket["id"],
            reason=reason,
        )

        return ticket["id"]

    except Exception as e:
        logger.error(
            "gorgias_escalation_error",
            conversation_id=conversation_id,
            error=str(e),
        )
        return None
