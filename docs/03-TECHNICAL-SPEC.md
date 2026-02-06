# Technical Specification

## Technology Stack

### Core Technologies

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Language | Python | 3.11+ | Primary development |
| Agent Framework | LangGraph | 0.5+ | Agent orchestration |
| LLM Framework | LangChain | 0.3+ | LLM integration |
| API Framework | FastAPI | 0.110+ | REST API |
| Database | PostgreSQL | 15+ | Primary data store |
| Cache | Redis | 7+ | Sessions, rate limiting |
| Vector Store | pgvector | 0.6+ | Embeddings storage |
| Observability | LangSmith | Latest | Tracing, debugging |

### LLM Models

| Use Case | Model | Fallback | Notes |
|----------|-------|----------|-------|
| Classification | gpt-4o-mini | gpt-3.5-turbo | Fast, cheap |
| Sentiment | gpt-4o-mini | - | Simple task |
| Response Generation | gpt-4o | gpt-4o-mini | Quality matters |
| Embeddings | text-embedding-3-small | - | Cost effective |

### Infrastructure

| Component | Service | Notes |
|-----------|---------|-------|
| Compute | Railway / AWS ECS | Container-based |
| Database | Railway Postgres / RDS | Managed |
| Cache | Railway Redis / ElastiCache | Managed |
| CDN | Cloudflare | Widget delivery |
| Secrets | AWS Secrets Manager | Encrypted storage |
| Logging | DataDog / CloudWatch | Centralized |

---

## Data Models

### Core Entities

```python
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID

# Enums
class ConversationStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    ABANDONED = "abandoned"

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Intent(str, Enum):
    ORDER_STATUS = "order_status"
    RETURN_REQUEST = "return_request"
    REFUND_REQUEST = "refund_request"
    ADDRESS_CHANGE = "address_change"
    CANCEL_ORDER = "cancel_order"
    PRODUCT_QUESTION = "product_question"
    SHIPPING_QUESTION = "shipping_question"
    GENERAL_INQUIRY = "general_inquiry"
    COMPLAINT = "complaint"
    OTHER = "other"

class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

# Models
class Store(BaseModel):
    id: UUID
    name: str
    platform: str  # shopify, woocommerce
    domain: str
    api_credentials: Dict[str, Any]  # encrypted
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class Customer(BaseModel):
    id: str  # External ID from platform
    store_id: UUID
    email: Optional[str]
    name: Optional[str]
    phone: Optional[str]
    total_orders: int = 0
    total_spent: float = 0.0
    tags: List[str] = []
    metadata: Dict[str, Any] = {}

class Conversation(BaseModel):
    id: UUID
    store_id: UUID
    customer_id: Optional[str]
    channel: str  # widget, email, gorgias, zendesk
    status: ConversationStatus
    primary_intent: Optional[Intent]
    sentiment: Optional[Sentiment]
    priority: Priority = Priority.MEDIUM
    order_id: Optional[str]
    assigned_agent: Optional[str]  # For escalated
    resolution_summary: Optional[str]
    csat_score: Optional[int]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    metadata: Dict[str, Any] = {}

class Message(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    intent: Optional[Intent]
    confidence: Optional[float]
    tokens_used: int = 0
    latency_ms: int = 0
    created_at: datetime
    metadata: Dict[str, Any] = {}

class Action(BaseModel):
    id: UUID
    conversation_id: UUID
    message_id: UUID
    action_type: str  # refund, return_label, address_update, etc.
    action_data: Dict[str, Any]
    status: str  # pending, completed, failed
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

class Order(BaseModel):
    """Cached order data from Shopify"""
    id: str
    store_id: UUID
    order_number: str
    email: str
    customer_name: str
    status: str
    fulfillment_status: Optional[str]
    financial_status: str
    total_price: float
    currency: str
    line_items: List[Dict[str, Any]]
    shipping_address: Dict[str, Any]
    tracking_numbers: List[str]
    created_at: datetime
    updated_at: datetime
    cached_at: datetime
```

### LangGraph State

```python
from typing import TypedDict, Optional, List, Dict, Any, Annotated
from langgraph.graph import add_messages

class ConversationState(TypedDict):
    """State passed through the agent graph"""
    
    # Identifiers
    conversation_id: str
    store_id: str
    
    # Messages (with history)
    messages: Annotated[List[dict], add_messages]
    
    # Current message analysis
    current_intent: Optional[str]
    sub_intents: List[str]
    sentiment: Optional[str]
    priority: str
    confidence_score: float
    
    # Extracted entities
    order_id: Optional[str]
    email: Optional[str]
    tracking_number: Optional[str]
    product_id: Optional[str]
    
    # Retrieved context
    order_data: Optional[Dict[str, Any]]
    customer_data: Optional[Dict[str, Any]]
    policy_context: List[str]
    
    # Agent processing
    current_agent: str
    agent_reasoning: str
    suggested_actions: List[Dict[str, Any]]
    actions_taken: List[Dict[str, Any]]
    
    # Output
    response_draft: str
    final_response: str
    requires_escalation: bool
    escalation_reason: Optional[str]
    
    # Metadata
    started_at: str
    tokens_used: int
    tools_called: List[str]
```

---

## API Specification

### Authentication

All API requests require authentication via API key in header:

```
Authorization: Bearer <api_key>
```

API keys are scoped to stores and have configurable permissions.

### Endpoints

#### Conversations

```yaml
POST /api/v1/conversations
Description: Start a new conversation
Request:
  {
    "channel": "widget",
    "customer_email": "customer@example.com",  # optional
    "initial_message": "Where is my order #1234?"
  }
Response:
  {
    "conversation_id": "uuid",
    "message_id": "uuid",
    "response": "I'll look up order #1234 for you...",
    "intent": "order_status",
    "requires_action": false
  }

POST /api/v1/conversations/{id}/messages
Description: Send a message in existing conversation
Request:
  {
    "content": "It was supposed to arrive yesterday"
  }
Response:
  {
    "message_id": "uuid",
    "response": "I apologize for the delay...",
    "intent": "order_status",
    "actions_taken": []
  }

GET /api/v1/conversations/{id}
Description: Get conversation details
Response:
  {
    "id": "uuid",
    "status": "active",
    "messages": [...],
    "primary_intent": "order_status",
    "sentiment": "frustrated",
    "created_at": "2026-02-06T10:00:00Z"
  }

POST /api/v1/conversations/{id}/escalate
Description: Manually escalate to human
Request:
  {
    "reason": "Customer requested human agent"
  }
Response:
  {
    "escalated": true,
    "ticket_id": "GORG-12345"
  }

POST /api/v1/conversations/{id}/resolve
Description: Mark conversation as resolved
Request:
  {
    "resolution_summary": "Order tracking provided",
    "csat_score": 5
  }
Response:
  {
    "resolved": true
  }
```

#### Webhooks

```yaml
POST /api/v1/webhooks/shopify/orders
Description: Receive Shopify order webhooks
Headers:
  X-Shopify-Hmac-SHA256: <signature>
Payload: Shopify order object

POST /api/v1/webhooks/gorgias
Description: Receive Gorgias ticket webhooks
Headers:
  X-Gorgias-Signature: <signature>
Payload: Gorgias ticket event
```

#### Admin

```yaml
GET /api/v1/stores/{id}
Description: Get store configuration

PATCH /api/v1/stores/{id}
Description: Update store settings
Request:
  {
    "settings": {
      "auto_refund_limit": 50.00,
      "escalation_threshold": 0.7
    }
  }

GET /api/v1/stores/{id}/analytics
Description: Get store analytics
Query: ?start_date=2026-01-01&end_date=2026-02-01
Response:
  {
    "total_conversations": 1250,
    "automation_rate": 0.82,
    "avg_response_time_ms": 1850,
    "escalation_rate": 0.12,
    "csat_average": 4.3,
    "intents": {
      "order_status": 520,
      "return_request": 180,
      ...
    }
  }
```

---

## Agent Prompts

### Intent Classification

```python
INTENT_CLASSIFICATION_PROMPT = """
You are an e-commerce customer support classifier. Analyze the customer message and determine their primary intent.

## Available Intents
- order_status: Where is my order, tracking, delivery updates
- return_request: Want to return item, return policy questions
- refund_request: Want money back, refund status
- address_change: Update shipping address (before shipment)
- cancel_order: Want to cancel order (before shipment)
- product_question: Product details, sizing, availability
- shipping_question: Shipping options, costs, times
- complaint: Unhappy with service, escalation request
- general_inquiry: Other questions, account, etc.

## Customer Message
{message}

## Previous Context (if any)
{context}

## Response Format
Respond with JSON:
{{
  "intent": "<primary_intent>",
  "sub_intents": ["<additional_intents>"],
  "confidence": <0.0-1.0>,
  "extracted_entities": {{
    "order_id": "<if mentioned>",
    "email": "<if mentioned>",
    "product": "<if mentioned>"
  }},
  "reasoning": "<brief explanation>"
}}
"""
```

### Sentiment Analysis

```python
SENTIMENT_ANALYSIS_PROMPT = """
Analyze the emotional tone of this customer message.

## Message
{message}

## Categories
- positive: Happy, satisfied, grateful
- neutral: Factual, no strong emotion
- negative: Unhappy, disappointed
- frustrated: Angry, demanding, threatening to leave

## Indicators to Look For
- Capitalization, exclamation marks
- Words like "ridiculous", "unacceptable", "terrible"
- Threats to cancel, leave bad reviews
- Expressions of disappointment or confusion
- Repeat contact mentions ("this is the third time")

## Response Format
{{
  "sentiment": "<category>",
  "intensity": <1-5>,
  "indicators": ["<specific phrases>"],
  "recommended_tone": "<empathetic|professional|warm>"
}}
"""
```

### WISMO Response

```python
WISMO_RESPONSE_PROMPT = """
You are a helpful e-commerce support agent. Generate a response about the customer's order status.

## Order Details
- Order Number: {order_number}
- Status: {status}
- Items: {items}
- Tracking: {tracking_number}
- Carrier: {carrier}
- Estimated Delivery: {estimated_delivery}
- Shipped Date: {shipped_date}

## Customer Sentiment
{sentiment}

## Guidelines
1. Lead with the most important information (status/tracking)
2. If delayed, acknowledge and apologize
3. Provide tracking link if available
4. Match tone to customer sentiment (more empathetic if frustrated)
5. Keep response concise but complete
6. End with offer to help further

## Response
"""
```

### Escalation Decision

```python
ESCALATION_DECISION_PROMPT = """
Determine if this conversation should be escalated to a human agent.

## Conversation Summary
Customer Intent: {intent}
Sentiment: {sentiment}
Resolution Attempted: {resolution_attempted}
Actions Taken: {actions_taken}
Customer Satisfaction: {satisfaction_signals}

## Escalation Triggers
- Customer explicitly requests human agent
- Frustrated sentiment after attempted resolution
- Complex issue outside standard procedures
- High-value order with issues (>${threshold})
- Potential legal/safety concerns
- Third+ contact about same issue
- Low confidence in AI resolution (<0.6)

## Response Format
{{
  "should_escalate": <true/false>,
  "reason": "<explanation>",
  "priority": "<low|medium|high|urgent>",
  "context_for_agent": "<summary for human>"
}}
"""
```

---

## Error Handling

### Error Categories

```python
class AgentError(Exception):
    """Base class for agent errors"""
    pass

class IntegrationError(AgentError):
    """External service failure"""
    def __init__(self, service: str, message: str):
        self.service = service
        super().__init__(f"{service}: {message}")

class PolicyViolationError(AgentError):
    """Action violates business rules"""
    pass

class EscalationRequired(AgentError):
    """Issue requires human intervention"""
    def __init__(self, reason: str, context: dict):
        self.reason = reason
        self.context = context
        super().__init__(reason)
```

### Graceful Degradation

```python
# Example: Order lookup with fallbacks
async def get_order_with_fallback(order_id: str, store_id: str) -> Optional[Order]:
    try:
        # Try cache first
        cached = await redis.get(f"order:{store_id}:{order_id}")
        if cached:
            return Order.parse_raw(cached)
        
        # Fetch from Shopify
        order = await shopify.get_order(order_id)
        await redis.setex(f"order:{store_id}:{order_id}", 300, order.json())
        return order
        
    except ShopifyAPIError as e:
        logger.error(f"Shopify API error: {e}")
        # Try database cache
        db_order = await db.get_cached_order(order_id, store_id)
        if db_order:
            return db_order
        # Graceful response
        return None
        
    except Exception as e:
        logger.exception(f"Unexpected error fetching order: {e}")
        return None
```

### User-Facing Error Responses

```python
ERROR_RESPONSES = {
    "order_not_found": (
        "I couldn't find an order with that number. Could you please "
        "double-check the order number or provide the email address "
        "used for the order?"
    ),
    "integration_error": (
        "I'm having trouble accessing your order details right now. "
        "Let me connect you with a team member who can help. "
        "One moment please..."
    ),
    "action_failed": (
        "I wasn't able to complete that action automatically. "
        "I've flagged this for our team and someone will follow up "
        "within 24 hours. Is there anything else I can help with?"
    ),
}
```

---

## Performance Requirements

| Metric | Requirement | Measurement |
|--------|-------------|-------------|
| Response Time (P50) | <2 seconds | End-to-end API |
| Response Time (P95) | <5 seconds | End-to-end API |
| Response Time (P99) | <10 seconds | End-to-end API |
| Availability | 99.5% | Monthly uptime |
| Concurrent Conversations | 500+ | Simultaneous |
| Throughput | 50 msg/sec | Peak sustained |

### Optimization Strategies

1. **Parallel Execution**
   - Fetch order + customer data concurrently
   - Non-blocking integration calls

2. **Caching**
   - Order data: 5 min TTL
   - Policy documents: 1 hour TTL
   - Embeddings: Persistent

3. **Model Selection**
   - Simple tasks → gpt-4o-mini
   - Complex reasoning → gpt-4o
   - Streaming for long responses

4. **Connection Pooling**
   - Database: 20 connections per worker
   - Redis: 10 connections per worker
   - HTTP: Persistent connections with retry
