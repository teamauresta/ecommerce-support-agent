# Integration Guide

## Overview

The E-Commerce Support Agent integrates with multiple external services to provide comprehensive support capabilities.

```
┌─────────────────────────────────────────────────────────────────┐
│                     INTEGRATION LAYER                            │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   E-Commerce    │    Helpdesk     │         Utilities           │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ • Shopify       │ • Gorgias       │ • Shipping (EasyPost)       │
│ • WooCommerce   │ • Zendesk       │ • Payments (Stripe)         │
│ • BigCommerce   │ • Front         │ • Email (SendGrid)          │
│                 │ • Intercom      │ • SMS (Twilio)              │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

---

## Shopify Integration

### Authentication

Shopify uses OAuth 2.0 for authentication. We support both:
1. **Custom App** (single store) - Admin API access token
2. **Public App** (multi-store) - OAuth flow

#### OAuth Flow (Public App)

```python
# Step 1: Redirect to Shopify
def get_auth_url(shop: str, redirect_uri: str, scopes: list) -> str:
    return (
        f"https://{shop}/admin/oauth/authorize"
        f"?client_id={SHOPIFY_API_KEY}"
        f"&scope={','.join(scopes)}"
        f"&redirect_uri={redirect_uri}"
        f"&state={generate_nonce()}"
    )

# Step 2: Exchange code for token
async def exchange_code(shop: str, code: str) -> str:
    response = await httpx.post(
        f"https://{shop}/admin/oauth/access_token",
        json={
            "client_id": SHOPIFY_API_KEY,
            "client_secret": SHOPIFY_API_SECRET,
            "code": code
        }
    )
    return response.json()["access_token"]
```

#### Required Scopes

| Scope | Purpose |
|-------|---------|
| `read_orders` | View order details |
| `write_orders` | Update orders, add notes |
| `read_customers` | View customer info |
| `read_products` | Product information |
| `read_fulfillments` | Shipment tracking |
| `write_fulfillments` | Create return labels |

### API Wrapper

```python
from typing import Optional, List
import httpx

class ShopifyClient:
    def __init__(self, shop: str, access_token: str):
        self.base_url = f"https://{shop}/admin/api/2024-01"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient()
    
    async def get_order(self, order_id: str) -> dict:
        """Fetch order by ID"""
        response = await self.client.get(
            f"{self.base_url}/orders/{order_id}.json",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()["order"]
    
    async def search_orders(
        self, 
        email: Optional[str] = None,
        name: Optional[str] = None,
        status: str = "any"
    ) -> List[dict]:
        """Search orders by customer email or name"""
        params = {"status": status}
        if email:
            params["email"] = email
        if name:
            params["name"] = name
            
        response = await self.client.get(
            f"{self.base_url}/orders.json",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()["orders"]
    
    async def get_order_by_number(self, order_number: str) -> Optional[dict]:
        """Fetch order by order number (e.g., #1234)"""
        # Remove # if present
        number = order_number.lstrip("#")
        
        response = await self.client.get(
            f"{self.base_url}/orders.json",
            headers=self.headers,
            params={"name": number, "status": "any"}
        )
        response.raise_for_status()
        orders = response.json()["orders"]
        
        # Match exact number
        for order in orders:
            if str(order["order_number"]) == number:
                return order
        return None
    
    async def add_order_note(self, order_id: str, note: str) -> dict:
        """Add a note to an order"""
        response = await self.client.put(
            f"{self.base_url}/orders/{order_id}.json",
            headers=self.headers,
            json={"order": {"note": note}}
        )
        response.raise_for_status()
        return response.json()["order"]
    
    async def create_refund(
        self, 
        order_id: str, 
        amount: float,
        reason: str,
        notify_customer: bool = True
    ) -> dict:
        """Create a refund for an order"""
        # First, calculate refund
        calc_response = await self.client.post(
            f"{self.base_url}/orders/{order_id}/refunds/calculate.json",
            headers=self.headers,
            json={"refund": {"shipping": {"amount": 0}}}
        )
        calc_response.raise_for_status()
        
        # Create refund
        response = await self.client.post(
            f"{self.base_url}/orders/{order_id}/refunds.json",
            headers=self.headers,
            json={
                "refund": {
                    "notify": notify_customer,
                    "note": reason,
                    "transactions": [{
                        "parent_id": calc_response.json()["refund"]["transactions"][0]["parent_id"],
                        "amount": amount,
                        "kind": "refund",
                        "gateway": "manual"
                    }]
                }
            }
        )
        response.raise_for_status()
        return response.json()["refund"]
    
    async def get_customer(self, customer_id: str) -> dict:
        """Fetch customer details"""
        response = await self.client.get(
            f"{self.base_url}/customers/{customer_id}.json",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()["customer"]
```

### Webhooks

Configure Shopify webhooks to keep order data in sync.

```python
SHOPIFY_WEBHOOK_TOPICS = [
    "orders/create",
    "orders/updated",
    "orders/fulfilled",
    "orders/cancelled",
    "refunds/create"
]

async def register_webhooks(shop: str, access_token: str, callback_url: str):
    client = ShopifyClient(shop, access_token)
    
    for topic in SHOPIFY_WEBHOOK_TOPICS:
        await client.client.post(
            f"{client.base_url}/webhooks.json",
            headers=client.headers,
            json={
                "webhook": {
                    "topic": topic,
                    "address": f"{callback_url}/webhooks/shopify/{topic.replace('/', '_')}",
                    "format": "json"
                }
            }
        )

def verify_shopify_webhook(data: bytes, hmac_header: str, secret: str) -> bool:
    """Verify webhook signature"""
    import hmac
    import hashlib
    import base64
    
    computed = base64.b64encode(
        hmac.new(secret.encode(), data, hashlib.sha256).digest()
    ).decode()
    
    return hmac.compare_digest(computed, hmac_header)
```

---

## Gorgias Integration

### Authentication

Gorgias uses HTTP Basic Auth with email and API key.

```python
import base64

def get_gorgias_headers(email: str, api_key: str) -> dict:
    credentials = base64.b64encode(f"{email}:{api_key}".encode()).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json"
    }
```

### API Wrapper

```python
class GorgiasClient:
    def __init__(self, domain: str, email: str, api_key: str):
        self.base_url = f"https://{domain}.gorgias.com/api"
        self.headers = get_gorgias_headers(email, api_key)
        self.client = httpx.AsyncClient()
    
    async def create_ticket(
        self,
        customer_email: str,
        subject: str,
        message: str,
        channel: str = "chat",
        tags: List[str] = None
    ) -> dict:
        """Create a new support ticket"""
        # First, get or create customer
        customer = await self.get_or_create_customer(customer_email)
        
        response = await self.client.post(
            f"{self.base_url}/tickets",
            headers=self.headers,
            json={
                "customer": {"id": customer["id"]},
                "channel": channel,
                "subject": subject,
                "messages": [{
                    "channel": channel,
                    "sender": {"id": customer["id"]},
                    "body_text": message,
                    "via": "api"
                }],
                "tags": [{"name": tag} for tag in (tags or [])]
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def add_message(
        self,
        ticket_id: int,
        message: str,
        sender_type: str = "agent",  # agent or customer
        internal: bool = False
    ) -> dict:
        """Add a message to an existing ticket"""
        response = await self.client.post(
            f"{self.base_url}/tickets/{ticket_id}/messages",
            headers=self.headers,
            json={
                "channel": "chat",
                "body_text": message,
                "via": "api",
                "sender": {"type": sender_type},
                "internal": internal
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def update_ticket(
        self,
        ticket_id: int,
        status: str = None,
        tags: List[str] = None,
        assignee_user_id: int = None
    ) -> dict:
        """Update ticket status, tags, or assignee"""
        update = {}
        if status:
            update["status"] = status
        if tags:
            update["tags"] = [{"name": tag} for tag in tags]
        if assignee_user_id:
            update["assignee_user"] = {"id": assignee_user_id}
            
        response = await self.client.put(
            f"{self.base_url}/tickets/{ticket_id}",
            headers=self.headers,
            json=update
        )
        response.raise_for_status()
        return response.json()
    
    async def get_or_create_customer(self, email: str) -> dict:
        """Get existing customer or create new one"""
        # Search for existing
        response = await self.client.get(
            f"{self.base_url}/customers",
            headers=self.headers,
            params={"email": email}
        )
        response.raise_for_status()
        customers = response.json()["data"]
        
        if customers:
            return customers[0]
        
        # Create new
        response = await self.client.post(
            f"{self.base_url}/customers",
            headers=self.headers,
            json={"email": email}
        )
        response.raise_for_status()
        return response.json()
```

### Bidirectional Sync

```python
# Sync AI conversation to Gorgias
async def sync_to_gorgias(
    gorgias: GorgiasClient,
    conversation: Conversation,
    messages: List[Message]
):
    # Create or find ticket
    if not conversation.external_ticket_id:
        ticket = await gorgias.create_ticket(
            customer_email=conversation.customer_email,
            subject=f"Support: {conversation.primary_intent}",
            message=messages[0].content,
            tags=["ai-handled", conversation.primary_intent]
        )
        conversation.external_ticket_id = ticket["id"]
    
    # Sync subsequent messages
    for message in messages[1:]:
        await gorgias.add_message(
            ticket_id=conversation.external_ticket_id,
            message=message.content,
            sender_type="agent" if message.role == "assistant" else "customer"
        )

# Handle Gorgias webhook (human reply)
async def handle_gorgias_webhook(event: dict):
    if event["event"] == "ticket.message.created":
        message = event["message"]
        
        # Find our conversation
        conversation = await db.get_conversation_by_ticket(
            event["ticket_id"]
        )
        
        if conversation and message["sender"]["type"] == "agent":
            # Human took over - pause AI
            conversation.status = "human_handling"
            await db.save(conversation)
```

---

## Shipping Integration (EasyPost)

For generating return labels and tracking shipments.

### API Wrapper

```python
import easypost

class ShippingClient:
    def __init__(self, api_key: str):
        easypost.api_key = api_key
    
    def create_return_label(
        self,
        from_address: dict,
        to_address: dict,  # Store's return address
        parcel: dict,
        carrier: str = "USPS"
    ) -> dict:
        """Create a prepaid return shipping label"""
        shipment = easypost.Shipment.create(
            is_return=True,
            from_address=from_address,
            to_address=to_address,
            parcel=parcel
        )
        
        # Buy cheapest rate for carrier
        rates = [r for r in shipment.rates if r.carrier == carrier]
        if not rates:
            rates = shipment.rates
        
        cheapest = min(rates, key=lambda r: float(r.rate))
        shipment.buy(rate=cheapest)
        
        return {
            "tracking_number": shipment.tracking_code,
            "label_url": shipment.postage_label.label_url,
            "carrier": cheapest.carrier,
            "service": cheapest.service,
            "cost": float(cheapest.rate)
        }
    
    def get_tracking(self, tracking_number: str, carrier: str) -> dict:
        """Get tracking details for a shipment"""
        tracker = easypost.Tracker.create(
            tracking_code=tracking_number,
            carrier=carrier
        )
        
        return {
            "status": tracker.status,
            "status_detail": tracker.status_detail,
            "estimated_delivery": tracker.est_delivery_date,
            "tracking_details": [
                {
                    "datetime": event.datetime,
                    "message": event.message,
                    "city": event.tracking_location.city,
                    "state": event.tracking_location.state
                }
                for event in tracker.tracking_details
            ]
        }
```

---

## Payment Integration (Stripe)

For direct refunds when not going through Shopify.

```python
import stripe

class PaymentClient:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
    
    async def process_refund(
        self,
        payment_intent_id: str,
        amount_cents: int,
        reason: str
    ) -> dict:
        """Process a refund through Stripe"""
        refund = stripe.Refund.create(
            payment_intent=payment_intent_id,
            amount=amount_cents,
            reason="requested_by_customer",
            metadata={"internal_reason": reason}
        )
        
        return {
            "refund_id": refund.id,
            "status": refund.status,
            "amount": refund.amount / 100,
            "currency": refund.currency
        }
    
    async def get_payment_intent(self, payment_intent_id: str) -> dict:
        """Get payment details"""
        pi = stripe.PaymentIntent.retrieve(payment_intent_id)
        return {
            "id": pi.id,
            "amount": pi.amount / 100,
            "status": pi.status,
            "customer_email": pi.receipt_email
        }
```

---

## Email Integration (SendGrid)

For sending transactional emails (escalation notifications, etc.).

```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

class EmailClient:
    def __init__(self, api_key: str, from_email: str):
        self.client = SendGridAPIClient(api_key)
        self.from_email = from_email
    
    async def send_escalation_notification(
        self,
        to_email: str,
        ticket_id: str,
        customer_email: str,
        summary: str
    ):
        """Notify support team of escalation"""
        message = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject=f"[Escalation] New ticket requires attention: {ticket_id}",
            html_content=f"""
            <h2>Escalated Support Ticket</h2>
            <p><strong>Ticket ID:</strong> {ticket_id}</p>
            <p><strong>Customer:</strong> {customer_email}</p>
            <h3>Summary</h3>
            <p>{summary}</p>
            <p><a href="https://app.gorgias.com/tickets/{ticket_id}">View in Gorgias</a></p>
            """
        )
        
        await self.client.send(message)
    
    async def send_return_label(
        self,
        to_email: str,
        customer_name: str,
        order_number: str,
        label_url: str,
        instructions: str
    ):
        """Send return label to customer"""
        message = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject=f"Your Return Label for Order #{order_number}",
            html_content=f"""
            <h2>Hi {customer_name},</h2>
            <p>Your return label is ready!</p>
            <p><a href="{label_url}" style="...">Download Return Label</a></p>
            <h3>Instructions</h3>
            <p>{instructions}</p>
            """
        )
        
        await self.client.send(message)
```

---

## Integration Testing

### Mock Services

```python
# tests/mocks/shopify.py
from unittest.mock import AsyncMock

def create_mock_shopify():
    mock = AsyncMock()
    
    mock.get_order.return_value = {
        "id": 12345,
        "order_number": 1234,
        "email": "customer@example.com",
        "fulfillment_status": "fulfilled",
        "fulfillments": [{
            "tracking_number": "1Z999AA10123456784",
            "tracking_company": "UPS"
        }]
    }
    
    mock.get_order_by_number.return_value = mock.get_order.return_value
    
    return mock

# Usage in tests
@pytest.fixture
def mock_shopify():
    return create_mock_shopify()

async def test_wismo_agent(mock_shopify):
    agent = WISMOAgent(shopify=mock_shopify)
    response = await agent.handle("Where is order #1234?")
    
    assert "1Z999AA10123456784" in response
    mock_shopify.get_order_by_number.assert_called_with("1234")
```

### Integration Test Suite

```python
# tests/integration/test_shopify_integration.py
import pytest
from src.integrations.shopify import ShopifyClient

@pytest.mark.integration
class TestShopifyIntegration:
    @pytest.fixture
    def client(self):
        return ShopifyClient(
            shop=os.environ["TEST_SHOPIFY_SHOP"],
            access_token=os.environ["TEST_SHOPIFY_TOKEN"]
        )
    
    async def test_get_order(self, client):
        order = await client.get_order("test_order_id")
        assert order["id"] is not None
        assert "line_items" in order
    
    async def test_search_orders_by_email(self, client):
        orders = await client.search_orders(email="test@example.com")
        assert isinstance(orders, list)
```

---

## Security Considerations

### Credential Storage

```python
# Use environment variables or secrets manager
import os
from cryptography.fernet import Fernet

class CredentialStore:
    def __init__(self, encryption_key: str):
        self.fernet = Fernet(encryption_key.encode())
    
    def encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        return self.fernet.decrypt(encrypted.encode()).decode()

# Store credentials encrypted in database
store.api_credentials = {
    "shopify_token": credential_store.encrypt(token),
    "gorgias_key": credential_store.encrypt(key)
}
```

### Webhook Verification

Always verify webhook signatures before processing:

```python
async def webhook_handler(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Shopify-Hmac-SHA256")
    
    if not verify_shopify_webhook(body, signature, WEBHOOK_SECRET):
        raise HTTPException(401, "Invalid signature")
    
    # Process webhook...
```

### Rate Limit Handling

```python
from tenacity import retry, wait_exponential, retry_if_exception_type

class RateLimitError(Exception):
    pass

@retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=1, min=4, max=60)
)
async def api_call_with_retry(client, method, *args, **kwargs):
    try:
        return await getattr(client, method)(*args, **kwargs)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise RateLimitError()
        raise
```
