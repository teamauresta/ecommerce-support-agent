# Week-by-Week Development Plan

## Overview

| Phase | Weeks | Focus | Deliverables |
|-------|-------|-------|--------------|
| **MVP** | 1-2 | Core agent + Shopify | Working WISMO agent |
| **Expand** | 3-4 | Returns, refunds, escalation | Full support coverage |
| **Polish** | 5-6 | Helpdesk + monitoring | Production-ready |
| **Launch** | 7-8 | Beta + iteration | Live customers |

---

## Phase 1: MVP (Weeks 1-2)

### Week 1: Foundation + WISMO Agent

#### Day 1-2: Project Setup
- [ ] Initialize repository structure
- [ ] Set up development environment
  - Python 3.11+ virtual environment
  - Pre-commit hooks (black, ruff, mypy)
  - Docker Compose for local services
- [ ] Configure dependencies
  ```
  langgraph>=0.5.0
  langchain>=0.3.0
  langchain-openai>=0.3.0
  fastapi>=0.110.0
  uvicorn>=0.27.0
  sqlalchemy>=2.0.0
  redis>=5.0.0
  httpx>=0.27.0
  pydantic>=2.6.0
  python-dotenv>=1.0.0
  ```
- [ ] Set up PostgreSQL + Redis (Docker)
- [ ] Create database schemas
- [ ] Configure LangSmith project

#### Day 3-4: Core Agent Framework
- [ ] Define state schema (`ConversationState`)
- [ ] Build base LangGraph structure
  - Entry node
  - Classification node
  - Routing logic
  - Response builder
- [ ] Create prompt templates
  - Intent classification prompt
  - Response generation prompt
- [ ] Implement basic conversation flow
- [ ] Write unit tests for state management

#### Day 5-7: WISMO Agent
- [ ] Build Shopify integration
  - Authentication (API key + access token)
  - Order lookup by order ID
  - Order lookup by email + name
  - Order status mapping
- [ ] Create WISMO specialist agent
  - Parse order identifier from query
  - Fetch order details
  - Determine status category
  - Generate status-appropriate response
- [ ] Build tracking integration
  - AfterShip or direct carrier APIs
  - Parse tracking events
  - Estimate delivery date
- [ ] Handle edge cases
  - Order not found
  - Multiple orders
  - Partial shipments
- [ ] Integration tests with Shopify sandbox

**Week 1 Deliverable:** WISMO agent that can answer "Where is my order?" queries with real Shopify data.

---

### Week 2: API Layer + Basic UI

#### Day 8-9: API Development
- [ ] FastAPI application structure
  ```
  src/api/
  ├── main.py
  ├── routes/
  │   ├── conversations.py
  │   ├── webhooks.py
  │   └── health.py
  ├── middleware/
  │   ├── auth.py
  │   ├── rate_limit.py
  │   └── logging.py
  └── schemas/
      ├── requests.py
      └── responses.py
  ```
- [ ] Implement endpoints
  - `POST /api/v1/conversations` - Start conversation
  - `POST /api/v1/conversations/{id}/messages` - Send message
  - `GET /api/v1/conversations/{id}` - Get conversation
  - `POST /api/v1/webhooks/shopify` - Shopify webhooks
- [ ] Add authentication middleware
- [ ] Add rate limiting
- [ ] API documentation (OpenAPI/Swagger)

#### Day 10-11: Chat Widget
- [ ] Simple React chat component
  - Message list
  - Input field
  - Send button
  - Typing indicator
- [ ] WebSocket support for real-time
- [ ] Embed script for stores
  ```html
  <script src="https://agent.example.com/widget.js" 
          data-store-id="xxx"></script>
  ```
- [ ] Basic styling (customizable)

#### Day 12-14: Integration Testing + Polish
- [ ] End-to-end test scenarios
  - New conversation flow
  - WISMO happy path
  - WISMO edge cases
  - Error handling
- [ ] Load testing (basic)
- [ ] Bug fixes and refinements
- [ ] Documentation updates

**Week 2 Deliverable:** Functional API + chat widget that handles WISMO queries.

---

## Phase 2: Expand (Weeks 3-4)

### Week 3: Returns + Refunds

#### Day 15-16: Returns Agent
- [ ] Return eligibility checker
  - Policy rules engine
  - Time window validation
  - Item category exclusions
- [ ] Return label generation
  - Shopify Shipping API or
  - EasyPost/Shippo integration
- [ ] RMA tracking
  - Create RMA record
  - Status updates
- [ ] Returns agent workflow
  ```
  Input → Check eligibility → Generate label → Instructions → Response
  ```

#### Day 17-18: Refunds Agent
- [ ] Refund eligibility checker
  - Policy validation
  - Amount limits (auto-approve thresholds)
  - Fraud signals check
- [ ] Payment integration
  - Shopify Payments refund
  - Stripe direct refund (if applicable)
- [ ] Refund workflow
  ```
  Input → Validate → Check limits → Process/Escalate → Confirm
  ```
- [ ] Partial refund support
- [ ] Store credit alternative

#### Day 19-21: Sentiment Analysis + Priority
- [ ] Sentiment analysis node
  - Frustration detection
  - Urgency signals
  - Positive/neutral/negative
- [ ] Priority scoring
  - VIP customer detection
  - Order value consideration
  - Repeat contact flag
- [ ] Tone adaptation
  - Match response tone to sentiment
  - Extra empathy for frustrated customers
- [ ] Update all response templates

**Week 3 Deliverable:** Full returns and refunds handling with sentiment-aware responses.

---

### Week 4: Escalation + Knowledge Base

#### Day 22-23: Escalation System
- [ ] Escalation triggers
  - Low confidence score
  - Negative sentiment + unresolved
  - Policy exceptions
  - Customer request
  - High-value orders
- [ ] Escalation workflow
  - Collect context summary
  - Create support ticket
  - Notify human agent
  - Handoff response to customer
- [ ] Human takeover flow
  - Pause AI responses
  - Resume after resolution

#### Day 24-25: Knowledge Base (RAG)
- [ ] Set up vector store (pgvector)
- [ ] Document ingestion pipeline
  - Markdown parser
  - Chunking strategy
  - Embedding generation
- [ ] Policy documents
  - Returns policy
  - Refund policy
  - Shipping policy
  - FAQ content
- [ ] Retrieval integration
  - Query embedding
  - Semantic search
  - Context injection
- [ ] Product information sync
  - Shopify product feed
  - Periodic refresh

#### Day 26-28: General Query Handling
- [ ] Product questions agent
  - Size/fit guidance
  - Availability check
  - Feature comparisons
- [ ] General FAQ agent
  - Policy questions
  - Account questions
  - Contact information
- [ ] Fallback handling
  - Unknown intent
  - Out of scope
  - Graceful "I don't know"

**Week 4 Deliverable:** Complete support coverage with escalation and knowledge base.

---

## Phase 3: Polish (Weeks 5-6)

### Week 5: Helpdesk Integration

#### Day 29-31: Gorgias Integration
- [ ] Gorgias API setup
  - Authentication
  - Ticket creation
  - Ticket updates
  - Message sync
- [ ] Bidirectional sync
  - AI responses → Gorgias tickets
  - Human responses → Conversation history
- [ ] Tagging and categorization
  - Auto-tag by intent
  - Priority mapping
- [ ] Macros integration
  - Trigger existing macros
  - Suggest macros to agents

#### Day 32-33: Zendesk Integration (Alternative)
- [ ] Zendesk API setup
- [ ] Ticket creation/updates
- [ ] Bidirectional sync
- [ ] Custom fields mapping

#### Day 34-35: Multi-Store Support
- [ ] Store configuration model
  - API credentials (encrypted)
  - Custom policies
  - Brand voice settings
  - Feature toggles
- [ ] Store isolation
  - Data separation
  - Rate limits per store
- [ ] Onboarding flow
  - Store registration
  - Shopify OAuth
  - Initial configuration

**Week 5 Deliverable:** Working helpdesk integration (Gorgias or Zendesk).

---

### Week 6: Monitoring + Admin

#### Day 36-38: Observability
- [ ] LangSmith integration
  - Trace all conversations
  - Token usage tracking
  - Error logging
- [ ] Custom metrics
  - Response time histograms
  - Intent distribution
  - Escalation rates
  - Sentiment trends
- [ ] Alerting
  - High error rate
  - Slow response times
  - Escalation spike
- [ ] Dashboard (Grafana or similar)
  - Real-time metrics
  - Historical trends
  - Store comparison

#### Day 39-40: Admin UI
- [ ] Store management
  - View all stores
  - Edit configuration
  - API key management
- [ ] Conversation browser
  - Search/filter conversations
  - View full transcripts
  - Manual escalation
- [ ] Analytics dashboard
  - Automation rate
  - CSAT scores
  - Top intents
  - Resolution times
- [ ] Knowledge base editor
  - Add/edit policies
  - FAQ management
  - Trigger re-indexing

#### Day 41-42: Performance Optimization
- [ ] Response time optimization
  - Parallel API calls
  - Caching strategies
  - Model selection tuning
- [ ] Cost optimization
  - Prompt efficiency
  - Model tiering (simple → complex)
  - Caching embeddings
- [ ] Load testing
  - 100 concurrent conversations
  - Identify bottlenecks
  - Fix performance issues

**Week 6 Deliverable:** Production-ready monitoring and admin tools.

---

## Phase 4: Launch (Weeks 7-8)

### Week 7: Beta Deployment

#### Day 43-44: Production Infrastructure
- [ ] Cloud setup (AWS/GCP/Railway)
  - Production database
  - Redis cluster
  - Container orchestration
- [ ] CI/CD pipeline
  - Automated tests
  - Staging deployment
  - Production deployment
- [ ] SSL/TLS configuration
- [ ] Backup strategy

#### Day 45-46: Security Hardening
- [ ] Penetration testing
- [ ] Dependency audit
- [ ] Secrets management
- [ ] Access controls review
- [ ] GDPR/privacy compliance check

#### Day 47-49: Beta Customer Onboarding
- [ ] Select 2-3 beta stores
  - Relationship with founders
  - Good ticket volume (50-200/week)
  - Willing to provide feedback
- [ ] Onboarding calls
  - Platform walkthrough
  - Configuration assistance
  - Expectations setting
- [ ] Go live (limited traffic)
  - Start with 10% of tickets
  - Monitor closely
  - Rapid response to issues

**Week 7 Deliverable:** Beta customers live with limited traffic.

---

### Week 8: Iteration + Handoff

#### Day 50-52: Feedback Integration
- [ ] Collect beta feedback
  - Weekly calls with customers
  - In-app feedback mechanism
  - Ticket review sessions
- [ ] Bug fixes
  - Priority based on impact
  - Same-day fixes for blockers
- [ ] Feature adjustments
  - Tweak prompts
  - Adjust thresholds
  - Add missing intents

#### Day 53-54: Traffic Ramp
- [ ] Increase to 50% traffic
- [ ] Monitor metrics
  - Automation rate
  - Customer satisfaction
  - Escalation patterns
- [ ] Fine-tune based on data

#### Day 55-56: Documentation + Handoff
- [ ] Complete API documentation
- [ ] User guides
  - Admin guide
  - Configuration guide
  - Troubleshooting guide
- [ ] Runbook
  - Common issues
  - Escalation procedures
  - Deployment process
- [ ] Knowledge transfer
  - Architecture overview
  - Codebase walkthrough
  - Future roadmap

**Week 8 Deliverable:** Stable beta with documentation, ready for wider rollout.

---

## Daily Standup Template

```markdown
## Date: YYYY-MM-DD

### Yesterday
- [Completed tasks]

### Today
- [Planned tasks]

### Blockers
- [Any blockers or questions]

### Notes
- [Learnings, decisions, or observations]
```

---

## Risk Checkpoints

| Week | Checkpoint | Action if Behind |
|------|------------|------------------|
| 1 | WISMO agent works | Simplify scope; mock Shopify |
| 2 | API + widget functional | Skip widget; API-only MVP |
| 3 | Returns/refunds work | Defer refunds to week 5 |
| 4 | Escalation + KB work | Simplify KB; manual fallback |
| 5 | Helpdesk integrated | Single helpdesk only |
| 6 | Monitoring in place | Basic logs; defer dashboard |
| 7 | Beta customers live | Single customer; longer beta |
| 8 | Stable + documented | Extend timeline 1-2 weeks |
