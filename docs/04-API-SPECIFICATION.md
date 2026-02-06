# API Specification

## Overview

The E-Commerce Support Agent exposes a RESTful API for managing conversations, handling webhooks, and administrative functions.

**Base URL:** `https://api.yourdomain.com/v1`

**Content Type:** `application/json`

**Authentication:** Bearer token in Authorization header

---

## Authentication

### API Keys

Each store receives a unique API key upon onboarding.

```http
Authorization: Bearer sk_live_abc123xyz...
```

**Key Format:**
- Live keys: `sk_live_<32 random chars>`
- Test keys: `sk_test_<32 random chars>`

**Key Permissions:**
| Permission | Description |
|------------|-------------|
| `conversations:read` | View conversations |
| `conversations:write` | Send messages, create conversations |
| `conversations:escalate` | Escalate to human |
| `orders:read` | Access order data |
| `analytics:read` | View analytics |
| `settings:write` | Modify store settings |

### Rate Limits

| Endpoint Type | Limit | Window |
|---------------|-------|--------|
| Conversation Create | 100 | per minute |
| Message Send | 300 | per minute |
| Read Operations | 1000 | per minute |
| Webhooks | 500 | per minute |

Rate limit headers included in all responses:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1707220800
```

---

## Endpoints

### Conversations

#### Create Conversation

Start a new support conversation.

```http
POST /conversations
```

**Request Body:**
```json
{
  "channel": "widget",
  "customer_email": "customer@example.com",
  "customer_name": "John Doe",
  "initial_message": "Where is my order #1234?",
  "context": {
    "page_url": "https://store.com/orders",
    "order_id": "1234"
  }
}
```

**Response (200 OK):**
```json
{
  "conversation_id": "conv_abc123",
  "message_id": "msg_xyz789",
  "response": {
    "content": "Hi John! I found your order #1234. It was shipped yesterday via USPS and is currently in transit. Based on the tracking, it should arrive by Friday, February 8th.\n\nHere's your tracking link: https://...\n\nIs there anything else I can help you with?",
    "type": "text"
  },
  "analysis": {
    "intent": "order_status",
    "sentiment": "neutral",
    "confidence": 0.95
  },
  "actions_taken": [],
  "created_at": "2026-02-06T10:30:00Z"
}
```

**Error Responses:**
| Code | Description |
|------|-------------|
| 400 | Invalid request body |
| 401 | Invalid API key |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

---

#### Send Message

Send a message in an existing conversation.

```http
POST /conversations/{conversation_id}/messages
```

**Request Body:**
```json
{
  "content": "It was supposed to arrive yesterday. This is frustrating!",
  "attachments": []
}
```

**Response (200 OK):**
```json
{
  "message_id": "msg_abc456",
  "response": {
    "content": "I completely understand your frustration, and I'm sorry for the delay. Let me look into this right away.\n\nI can see there was a weather delay at the regional hub. The package is now moving again and should arrive tomorrow.\n\nAs an apology for the inconvenience, I've applied a 10% discount code to your account: SORRY10\n\nWould you like me to set up a delivery notification so you know the moment it arrives?",
    "type": "text"
  },
  "analysis": {
    "intent": "order_status",
    "sentiment": "frustrated",
    "confidence": 0.92
  },
  "actions_taken": [
    {
      "type": "discount_applied",
      "details": {
        "code": "SORRY10",
        "value": "10%"
      }
    }
  ],
  "created_at": "2026-02-06T10:31:00Z"
}
```

---

#### Get Conversation

Retrieve conversation details and history.

```http
GET /conversations/{conversation_id}
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| include_messages | boolean | Include full message history (default: true) |
| message_limit | integer | Max messages to return (default: 50) |

**Response (200 OK):**
```json
{
  "id": "conv_abc123",
  "store_id": "store_xyz",
  "status": "active",
  "channel": "widget",
  "customer": {
    "email": "customer@example.com",
    "name": "John Doe"
  },
  "primary_intent": "order_status",
  "sentiment": "frustrated",
  "priority": "high",
  "order_id": "1234",
  "messages": [
    {
      "id": "msg_xyz789",
      "role": "user",
      "content": "Where is my order #1234?",
      "created_at": "2026-02-06T10:30:00Z"
    },
    {
      "id": "msg_def456",
      "role": "assistant",
      "content": "Hi John! I found your order...",
      "created_at": "2026-02-06T10:30:02Z"
    }
  ],
  "actions_taken": [
    {
      "type": "discount_applied",
      "message_id": "msg_abc456",
      "details": {"code": "SORRY10"},
      "created_at": "2026-02-06T10:31:00Z"
    }
  ],
  "created_at": "2026-02-06T10:30:00Z",
  "updated_at": "2026-02-06T10:31:00Z"
}
```

---

#### List Conversations

Get paginated list of conversations.

```http
GET /conversations
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| status | string | Filter by status (active, resolved, escalated) |
| intent | string | Filter by primary intent |
| sentiment | string | Filter by sentiment |
| customer_email | string | Filter by customer email |
| start_date | ISO8601 | Start of date range |
| end_date | ISO8601 | End of date range |
| page | integer | Page number (default: 1) |
| per_page | integer | Items per page (default: 20, max: 100) |

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "conv_abc123",
      "status": "active",
      "primary_intent": "order_status",
      "sentiment": "frustrated",
      "customer_email": "customer@example.com",
      "message_count": 4,
      "created_at": "2026-02-06T10:30:00Z",
      "updated_at": "2026-02-06T10:35:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_pages": 5,
    "total_count": 95
  }
}
```

---

#### Escalate Conversation

Manually escalate a conversation to human support.

```http
POST /conversations/{conversation_id}/escalate
```

**Request Body:**
```json
{
  "reason": "Customer specifically requested human agent",
  "priority": "high",
  "notes": "Customer is a VIP with multiple orders"
}
```

**Response (200 OK):**
```json
{
  "escalated": true,
  "ticket_id": "GORG-12345",
  "assigned_to": null,
  "customer_message": "I've connected you with our support team. A team member will be with you shortly. Your reference number is GORG-12345."
}
```

---

#### Resolve Conversation

Mark a conversation as resolved.

```http
POST /conversations/{conversation_id}/resolve
```

**Request Body:**
```json
{
  "resolution_summary": "Provided order tracking and delivery estimate",
  "resolution_type": "automated",
  "csat_score": 5
}
```

**Response (200 OK):**
```json
{
  "resolved": true,
  "resolved_at": "2026-02-06T10:40:00Z",
  "total_messages": 6,
  "resolution_time_seconds": 600
}
```

---

### Webhooks

#### Shopify Order Webhook

Receive order updates from Shopify.

```http
POST /webhooks/shopify/orders
```

**Headers:**
```http
X-Shopify-Topic: orders/updated
X-Shopify-Hmac-SHA256: <base64_hmac>
X-Shopify-Shop-Domain: store.myshopify.com
```

**Request Body:** Shopify order object

**Response (200 OK):**
```json
{
  "received": true,
  "order_id": "12345",
  "action": "cache_updated"
}
```

---

#### Gorgias Webhook

Receive ticket events from Gorgias.

```http
POST /webhooks/gorgias
```

**Headers:**
```http
X-Gorgias-Signature: <signature>
```

**Request Body:**
```json
{
  "event": "ticket.message.created",
  "ticket_id": 12345,
  "message": {
    "id": 67890,
    "sender": "customer",
    "body_text": "Thanks, that helps!",
    "created_at": "2026-02-06T10:45:00Z"
  }
}
```

**Response (200 OK):**
```json
{
  "received": true,
  "action": "message_synced"
}
```

---

### Analytics

#### Get Analytics

Retrieve analytics for a store.

```http
GET /analytics
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| start_date | ISO8601 | Start of period (required) |
| end_date | ISO8601 | End of period (required) |
| granularity | string | day, week, month (default: day) |

**Response (200 OK):**
```json
{
  "period": {
    "start": "2026-02-01T00:00:00Z",
    "end": "2026-02-06T23:59:59Z"
  },
  "summary": {
    "total_conversations": 523,
    "total_messages": 2104,
    "automation_rate": 0.82,
    "escalation_rate": 0.12,
    "avg_response_time_ms": 1850,
    "avg_resolution_time_seconds": 480,
    "csat_average": 4.3,
    "csat_count": 312
  },
  "by_intent": {
    "order_status": {
      "count": 245,
      "percentage": 0.47,
      "automation_rate": 0.94
    },
    "return_request": {
      "count": 89,
      "percentage": 0.17,
      "automation_rate": 0.78
    },
    "refund_request": {
      "count": 67,
      "percentage": 0.13,
      "automation_rate": 0.71
    }
  },
  "by_sentiment": {
    "positive": 156,
    "neutral": 298,
    "negative": 45,
    "frustrated": 24
  },
  "time_series": [
    {
      "date": "2026-02-01",
      "conversations": 78,
      "automation_rate": 0.81,
      "avg_response_time_ms": 1920
    }
  ],
  "actions_taken": {
    "refund_processed": 34,
    "return_label_generated": 56,
    "discount_applied": 23,
    "address_updated": 12
  }
}
```

---

### Admin

#### Get Store Settings

```http
GET /stores/{store_id}
```

**Response (200 OK):**
```json
{
  "id": "store_xyz",
  "name": "Acme Store",
  "domain": "acme.myshopify.com",
  "platform": "shopify",
  "settings": {
    "auto_refund_limit": 50.00,
    "auto_refund_enabled": true,
    "return_window_days": 30,
    "escalation_confidence_threshold": 0.6,
    "working_hours": {
      "timezone": "America/New_York",
      "start": "09:00",
      "end": "18:00"
    },
    "brand_voice": {
      "tone": "friendly_professional",
      "name_usage": "first_name"
    },
    "notifications": {
      "escalation_email": "support@acme.com",
      "daily_summary": true
    }
  },
  "integrations": {
    "shopify": {
      "connected": true,
      "scopes": ["read_orders", "write_orders"]
    },
    "gorgias": {
      "connected": true,
      "mode": "bidirectional"
    }
  },
  "created_at": "2026-01-15T00:00:00Z"
}
```

---

#### Update Store Settings

```http
PATCH /stores/{store_id}
```

**Request Body:**
```json
{
  "settings": {
    "auto_refund_limit": 75.00,
    "escalation_confidence_threshold": 0.7
  }
}
```

**Response (200 OK):**
```json
{
  "updated": true,
  "settings": {
    "auto_refund_limit": 75.00,
    "escalation_confidence_threshold": 0.7
  }
}
```

---

## WebSocket API

For real-time chat widget communication.

### Connection

```javascript
const ws = new WebSocket('wss://api.yourdomain.com/v1/ws');

// Authenticate after connection
ws.send(JSON.stringify({
  type: 'auth',
  api_key: 'sk_live_...',
  conversation_id: 'conv_abc123'  // optional, for existing
}));
```

### Message Types

**Client → Server:**
```json
// Send message
{
  "type": "message",
  "content": "Where is my order?"
}

// Typing indicator
{
  "type": "typing",
  "is_typing": true
}
```

**Server → Client:**
```json
// Response message
{
  "type": "message",
  "message_id": "msg_xyz",
  "content": "Let me look that up for you...",
  "timestamp": "2026-02-06T10:30:00Z"
}

// Typing indicator
{
  "type": "typing",
  "is_typing": true
}

// Escalation notification
{
  "type": "escalated",
  "message": "Connecting you with a team member...",
  "ticket_id": "GORG-12345"
}

// Error
{
  "type": "error",
  "code": "rate_limited",
  "message": "Too many messages. Please wait a moment."
}
```

---

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `invalid_request` | 400 | Malformed request body |
| `missing_field` | 400 | Required field missing |
| `invalid_api_key` | 401 | API key invalid or expired |
| `insufficient_permissions` | 403 | API key lacks required permission |
| `not_found` | 404 | Resource not found |
| `conversation_closed` | 409 | Cannot message closed conversation |
| `rate_limited` | 429 | Too many requests |
| `integration_error` | 502 | External service failure |
| `internal_error` | 500 | Unexpected server error |

**Error Response Format:**
```json
{
  "error": {
    "code": "invalid_request",
    "message": "The 'initial_message' field is required",
    "details": {
      "field": "initial_message",
      "reason": "required"
    }
  },
  "request_id": "req_abc123"
}
```

---

## SDKs & Examples

### Python SDK

```python
from ecommerce_agent import AgentClient

client = AgentClient(api_key="sk_live_...")

# Start conversation
conv = client.conversations.create(
    channel="api",
    customer_email="customer@example.com",
    initial_message="Where is order #1234?"
)

print(conv.response.content)

# Send follow-up
response = client.conversations.send_message(
    conversation_id=conv.id,
    content="When will it arrive?"
)
```

### JavaScript SDK

```javascript
import { AgentClient } from '@yourcompany/agent-sdk';

const client = new AgentClient({ apiKey: 'sk_live_...' });

// Start conversation
const conv = await client.conversations.create({
  channel: 'widget',
  customerEmail: 'customer@example.com',
  initialMessage: 'Where is order #1234?'
});

console.log(conv.response.content);
```

### cURL Example

```bash
curl -X POST https://api.yourdomain.com/v1/conversations \
  -H "Authorization: Bearer sk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "customer_email": "customer@example.com",
    "initial_message": "Where is my order #1234?"
  }'
```
