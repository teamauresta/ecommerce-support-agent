# System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CUSTOMER TOUCHPOINTS                           │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────┤
│   Website   │   Email     │   Gorgias   │   Zendesk   │   API Direct    │
│   Widget    │   Inbound   │   Plugin    │   Plugin    │                 │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴────────┬────────┘
       │             │             │             │               │
       └─────────────┴─────────────┼─────────────┴───────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            API GATEWAY                                   │
│  • Authentication  • Rate Limiting  • Request Routing  • Logging        │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENT ORCHESTRATOR                               │
│                          (LangGraph Core)                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  Classifier │  │  Sentiment  │  │   Router    │  │  Escalation │    │
│  │    Node     │→ │    Node     │→ │    Node     │→ │    Node     │    │
│  └─────────────┘  └─────────────┘  └──────┬──────┘  └─────────────┘    │
│                                           │                              │
│         ┌─────────────────────────────────┼─────────────────────────┐   │
│         ▼                   ▼             ▼            ▼            ▼   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │   WISMO    │  │  Returns   │  │  Refunds   │  │  Product   │  ...  │
│  │   Agent    │  │   Agent    │  │   Agent    │  │   Agent    │       │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘       │
│        └───────────────┴───────────────┴───────────────┘               │
│                                   │                                     │
│                          ┌────────┴────────┐                           │
│                          │ Response Builder │                           │
│                          └─────────────────┘                           │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │
       ┌──────────────────────────────┼──────────────────────────────┐
       ▼                              ▼                              ▼
┌─────────────┐              ┌─────────────┐              ┌─────────────┐
│    TOOLS    │              │  KNOWLEDGE  │              │    DATA     │
│             │              │    BASE     │              │    LAYER    │
│ • Shopify   │              │             │              │             │
│ • Stripe    │              │ • Policies  │              │ • PostgreSQL│
│ • Shipping  │              │ • FAQs      │              │ • Redis     │
│ • Email     │              │ • Products  │              │ • S3        │
└─────────────┘              └─────────────┘              └─────────────┘
```

---

## Component Details

### 1. API Gateway Layer

**Technology:** FastAPI with middleware stack

**Responsibilities:**
- Request authentication (API keys, JWT)
- Rate limiting (per-store, per-endpoint)
- Request validation and sanitization
- Response formatting
- Audit logging

```python
# Middleware stack
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(CORSMiddleware)
```

### 2. Agent Orchestrator (LangGraph)

The core intelligence layer, implemented as a state graph.

**State Schema:**
```python
class ConversationState(TypedDict):
    # Input
    conversation_id: str
    store_id: str
    customer_id: Optional[str]
    messages: List[Message]
    
    # Analysis
    intent: str
    sub_intents: List[str]
    sentiment: str
    priority: str
    
    # Context
    order_data: Optional[OrderData]
    customer_data: Optional[CustomerData]
    policy_context: List[str]
    
    # Processing
    current_agent: str
    agent_outputs: Dict[str, Any]
    actions_taken: List[ActionLog]
    
    # Output
    response: str
    requires_escalation: bool
    escalation_reason: Optional[str]
    confidence_score: float
    
    # Metadata
    started_at: datetime
    tokens_used: int
```

**Graph Structure:**
```python
graph = StateGraph(ConversationState)

# Entry nodes
graph.add_node("classify", classify_intent)
graph.add_node("analyze_sentiment", analyze_sentiment)
graph.add_node("fetch_context", fetch_context)

# Routing
graph.add_node("route", route_to_specialist)

# Specialist agents
graph.add_node("wismo_agent", handle_wismo)
graph.add_node("returns_agent", handle_returns)
graph.add_node("refunds_agent", handle_refunds)
graph.add_node("product_agent", handle_product_query)
graph.add_node("general_agent", handle_general)

# Output
graph.add_node("build_response", build_response)
graph.add_node("check_escalation", check_escalation)

# Edges
graph.set_entry_point("classify")
graph.add_edge("classify", "analyze_sentiment")
graph.add_edge("analyze_sentiment", "fetch_context")
graph.add_edge("fetch_context", "route")

# Conditional routing
graph.add_conditional_edges(
    "route",
    route_to_agent,
    {
        "wismo": "wismo_agent",
        "returns": "returns_agent",
        "refunds": "refunds_agent",
        "product": "product_agent",
        "general": "general_agent",
    }
)

# All agents lead to response building
for agent in ["wismo_agent", "returns_agent", "refunds_agent", 
              "product_agent", "general_agent"]:
    graph.add_edge(agent, "build_response")

graph.add_edge("build_response", "check_escalation")

# Final conditional
graph.add_conditional_edges(
    "check_escalation",
    lambda s: "escalate" if s["requires_escalation"] else "end",
    {"escalate": "human_handoff", "end": END}
)
```

### 3. Specialist Agents

Each specialist agent is a sub-graph with domain-specific logic.

**WISMO Agent:**
```
Input: Customer query about order status
│
├── Extract order identifier (order #, email, name)
├── Fetch order from Shopify
├── Determine status category:
│   ├── Processing → Explain timeline
│   ├── Shipped → Provide tracking + ETA
│   ├── Delivered → Confirm delivery
│   ├── Delayed → Apologize + new ETA
│   └── Not Found → Escalate or ask for details
└── Generate response with status details
```

**Returns Agent:**
```
Input: Customer wants to return item
│
├── Identify order and item(s)
├── Check return eligibility:
│   ├── Within window? (usually 30 days)
│   ├── Item condition requirements
│   └── Excluded categories
├── If eligible:
│   ├── Generate return label
│   ├── Create RMA record
│   └── Provide instructions
├── If not eligible:
│   ├── Explain why
│   └── Offer alternatives (exchange, store credit)
└── Generate response
```

**Refunds Agent:**
```
Input: Customer requests refund
│
├── Identify order and reason
├── Check refund eligibility:
│   ├── Within policy window?
│   ├── Item returned/in transit?
│   ├── Previous refunds on order?
│   └── Amount within auto-approve limit?
├── If auto-approvable:
│   ├── Process refund via Stripe/Shopify
│   ├── Log action
│   └── Confirm to customer
├── If needs review:
│   ├── Create pending refund record
│   └── Escalate to human with context
└── Generate response
```

### 4. Tools Layer

External integrations wrapped as LangChain tools.

```python
# Tool definitions
@tool
def get_order(order_id: str, store_id: str) -> OrderData:
    """Fetch order details from Shopify"""
    ...

@tool
def get_tracking(tracking_number: str) -> TrackingData:
    """Get shipment tracking information"""
    ...

@tool  
def create_return_label(order_id: str, items: List[str]) -> ReturnLabel:
    """Generate prepaid return shipping label"""
    ...

@tool
def process_refund(order_id: str, amount: float, reason: str) -> RefundResult:
    """Process refund through payment provider"""
    ...

@tool
def update_order(order_id: str, updates: Dict) -> OrderData:
    """Update order details (address, notes, etc.)"""
    ...

@tool
def search_knowledge_base(query: str) -> List[Document]:
    """Search policies, FAQs, and product info"""
    ...
```

### 5. Knowledge Base

Vector store for RAG-based policy and product retrieval.

**Structure:**
```
knowledge_base/
├── policies/
│   ├── returns_policy.md
│   ├── refunds_policy.md
│   ├── shipping_policy.md
│   └── warranty_policy.md
├── faqs/
│   ├── general_faqs.md
│   ├── shipping_faqs.md
│   └── product_faqs.md
└── products/
    └── [synced from Shopify]
```

**Implementation:**
- Embeddings: OpenAI text-embedding-3-small
- Vector store: PostgreSQL with pgvector
- Chunking: 500 tokens with 50 token overlap
- Retrieval: Top-5 with reranking

### 6. Data Layer

**PostgreSQL Tables:**
```sql
-- Conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    store_id UUID NOT NULL,
    customer_id VARCHAR(255),
    channel VARCHAR(50),
    status VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    metadata JSONB
);

-- Messages
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    role VARCHAR(20), -- user, assistant, system
    content TEXT,
    created_at TIMESTAMP,
    metadata JSONB
);

-- Actions
CREATE TABLE actions (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    action_type VARCHAR(50),
    action_data JSONB,
    status VARCHAR(20),
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Stores
CREATE TABLE stores (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    platform VARCHAR(50), -- shopify, woocommerce
    api_credentials JSONB, -- encrypted
    settings JSONB,
    created_at TIMESTAMP
);
```

**Redis Usage:**
- Session state (conversation context)
- Rate limiting counters
- Cache for frequently accessed orders
- Pub/sub for real-time updates

---

## Data Flow

### Typical Request Flow

```
1. Customer sends message via widget
   │
2. API Gateway receives request
   ├── Authenticate store API key
   ├── Rate limit check
   └── Validate payload
   │
3. Load/create conversation state
   ├── Fetch from PostgreSQL
   └── Load recent context from Redis
   │
4. Enter LangGraph workflow
   │
   ├── 4a. Classify intent
   │   └── LLM determines: "order_status"
   │
   ├── 4b. Analyze sentiment  
   │   └── LLM determines: "neutral"
   │
   ├── 4c. Fetch context
   │   ├── Extract order #12345
   │   ├── Call Shopify API
   │   └── Get customer history
   │
   ├── 4d. Route to WISMO agent
   │
   ├── 4e. WISMO agent processes
   │   ├── Order status: "shipped"
   │   ├── Tracking: "1Z999..."
   │   └── ETA: "Feb 8"
   │
   ├── 4f. Build response
   │   └── Generate natural language reply
   │
   └── 4g. Check escalation
       └── Confidence high, no escalation
   │
5. Persist state
   ├── Save message to PostgreSQL
   ├── Log action if any
   └── Update Redis session
   │
6. Return response to customer
```

---

## Security Architecture

### Authentication
- **Store API Keys:** Scoped, rotatable, rate-limited
- **Helpdesk Webhooks:** Signature verification
- **Internal Services:** JWT with short expiry

### Data Protection
- **At Rest:** AES-256 encryption for credentials
- **In Transit:** TLS 1.3 everywhere
- **PII Handling:** Never include in LLM prompts; use references

### Access Control
- **Store Isolation:** Strict tenant separation
- **Action Limits:** Refund caps, approval workflows
- **Audit Trail:** All actions logged with actor, timestamp, details

---

## Scalability Considerations

### Horizontal Scaling
- Stateless API servers behind load balancer
- Redis for shared session state
- PostgreSQL read replicas for heavy read loads

### Performance Targets
| Metric | Target |
|--------|--------|
| P50 Response Time | <2s |
| P99 Response Time | <10s |
| Concurrent Conversations | 1000+ |
| Messages/Second | 100+ |

### Bottleneck Mitigation
- **LLM Latency:** Streaming responses, model caching
- **Integration APIs:** Caching, connection pooling, async calls
- **Database:** Indexing, query optimization, read replicas
