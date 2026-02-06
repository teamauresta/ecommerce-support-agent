# Multi-Tenant Agent Platform - Architecture Design

**Date:** February 7, 2026
**Status:** Validated Design
**Target Launch:** Q3 2026 (6 months)

## Executive Summary

Transform the current single-purpose e-commerce customer service agent into a **multi-tenant agent platform** that serves 20-100 clients with multiple agent types (customer service, sales, marketing).

**Business Model:**
- Target: Mid-scale (20-100 clients) in first 12 months
- Pricing: Hybrid (base subscription + overage)
- Tiers: Basic, Pro, Enterprise
- Deployment: Shared for Basic/Pro, dedicated for Enterprise

## 1. System Architecture

### Overall Structure

Three-layer architecture:

1. **Control Plane** - Platform management dashboard
2. **Agent Runtime** - AI agents executing conversations
3. **Shared Services** - Auth, billing, analytics, knowledge base

### Multi-Tenancy Hierarchy

```
Organization (tenant)
  └─ Store (business unit)
      └─ Agent Instance (deployed agent)
          └─ Conversations
```

**Example:**
```
Organization: "ACME Corp" (Pro Tier)
  └─ Store: "ACME E-commerce"
      ├─ Agent Instance: Customer Service v2.1 (active)
      ├─ Agent Instance: Sales v1.0 (active)
      └─ Agent Instance: Customer Service v2.0 (archived)
  └─ Store: "ACME Wholesale"
      └─ Agent Instance: Customer Service v2.1 (active)
```

## 2. Data Model

### Core Tables

```python
# Organizations (top-level tenant)
class Organization(Base):
    id: UUID
    name: str
    tier: str  # "basic", "pro", "enterprise"
    billing_email: str
    subscription_status: str  # "active", "trial", "suspended"
    monthly_conversation_limit: int
    overage_rate: Decimal
    settings: JSONB
    created_at: DateTime
    updated_at: DateTime

# Stores (updated with org relationship)
class Store(Base):
    id: UUID
    organization_id: UUID  # NEW: Link to organization
    name: str
    domain: str
    platform: str
    is_active: bool
    api_credentials: JSONB
    settings: JSONB

# Agent Definitions (templates)
class AgentDefinition(Base):
    id: UUID
    type: str  # "customer_service", "sales", "marketing"
    version: str  # "2.1.0"
    graph_config: JSONB
    capabilities: JSONB
    tier_restrictions: JSONB
    created_at: DateTime

# Agent Instances (deployed agents)
class AgentInstance(Base):
    id: UUID
    store_id: UUID
    agent_definition_id: UUID
    status: str  # "active", "paused", "archived"
    config_overrides: JSONB
    deployed_at: DateTime

# Usage Tracking (for billing)
class ConversationUsage(Base):
    id: UUID
    organization_id: UUID
    agent_instance_id: UUID
    month: Date
    conversation_count: int
    billed_amount: Decimal
```

### Relationships

- Organization → Store (1:N)
- Store → Agent Instance (1:N)
- Agent Instance → Agent Definition (N:1)
- Organization → Conversation Usage (1:N)

## 3. Control Plane (Admin Dashboard)

### UI Structure

```
Platform Dashboard (platform.auresta.com)
├─ Organization Settings
│  ├─ Billing & Usage (all tiers)
│  ├─ Team Members (Pro+)
│  └─ White-label Branding (Enterprise)
│
├─ Stores Management
│  ├─ List/Create Stores
│  └─ Store Settings
│
├─ Agent Marketplace
│  ├─ Browse Agent Types
│  ├─ View Capabilities per Tier
│  └─ Deploy Agent Instance
│
├─ Agent Configuration
│  ├─ Knowledge Base Upload (all tiers)
│  ├─ Basic Prompts (all tiers)
│  ├─ Advanced Workflows (Pro+)
│  ├─ Custom Integrations (Pro+)
│  └─ Full Prompt Editing (Enterprise)
│
└─ Analytics & Monitoring
   ├─ Conversation Volume (all tiers)
   ├─ Sentiment Analysis (Pro+)
   ├─ Custom Reports (Enterprise)
   └─ LangSmith Integration (Enterprise)
```

### Tech Stack

- **Frontend**: React + TypeScript
- **UI Framework**: Tailwind CSS + shadcn/ui
- **State Management**: TanStack Query
- **Authentication**: Auth0 or Clerk
- **Hosting**: Vercel or similar

## 4. Agent Runtime Architecture

### Directory Structure

```
src/
├─ agent_runtime/
│  ├─ core/                    # Shared infrastructure
│  │  ├─ base_graph.py
│  │  ├─ memory.py
│  │  ├─ knowledge_base.py
│  │  └─ integrations/
│  │
│  ├─ agent_types/            # Separate graphs per type
│  │  ├─ customer_service/
│  │  │  ├─ graph.py
│  │  │  ├─ nodes/
│  │  │  ├─ prompts.py
│  │  │  └─ version.py
│  │  │
│  │  ├─ sales/
│  │  │  ├─ graph.py
│  │  │  ├─ nodes/
│  │  │  └─ prompts.py
│  │  │
│  │  └─ marketing/
│  │     ├─ graph.py
│  │     └─ nodes/
│  │
│  └─ registry.py             # Agent definition registry
```

### Agent Execution Flow

1. Request → Extract `agent_instance_id`
2. Look up Agent Instance → Get Agent Definition
3. Load graph: `agent_types/{type}/graph.py` at version
4. Apply config overrides
5. Execute with org/store context
6. Track usage for billing

## 5. Deployment Architecture

### Shared Platform (Basic/Pro Tiers)

```
┌─────────────────────────────────────────┐
│   platform.auresta.com                  │
│   Control Plane Dashboard               │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│   api.auresta.com                       │
│   Agent Runtime API                     │
│   • All Basic/Pro orgs                  │
│   • Isolated by organization_id         │
│   • Kubernetes deployment               │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│   PostgreSQL (Multi-tenant)             │
│   • Row-level security                  │
│   • Isolated by organization_id         │
└─────────────────────────────────────────┘
```

### Enterprise Dedicated

```
Enterprise: "BigCorp"
┌─────────────────────────────────────────┐
│   bigcorp-api.auresta.com               │
│   • Dedicated k8s namespace             │
│   • Custom subdomain                    │
│   • Optional VPC                        │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│   Dedicated PostgreSQL                  │
│   • Separate instance                   │
│   • Can be in client's cloud            │
└─────────────────────────────────────────┘
```

### Technology Choices

- **Container Orchestration**: Kubernetes (EKS/GKE/AKS)
- **Shared Platform**: Single cluster, namespaced
- **Enterprise**: Separate namespace or cluster
- **Auto-scaling**: HPA based on conversation volume
- **Database**: RDS PostgreSQL with read replicas
- **Caching**: Redis for usage counters
- **Message Queue**: Redis or RabbitMQ for async tasks

## 6. Billing & Usage Tracking

### Pricing Structure

```
Basic Tier:
  $99/month → 1,000 conversations included
  Overage: $0.10 per conversation

Pro Tier:
  $499/month → 5,000 conversations included
  Overage: $0.05 per conversation

Enterprise Tier:
  Custom pricing
  Dedicated deployment
  Volume discounts
```

### Usage Tracking

```python
class UsageTracker:
    def track_conversation(self, organization_id, agent_instance_id):
        # Increment Redis counter (fast)
        redis.incr(f"usage:{org_id}:{month}")

        # Async write to database (durable)
        queue.enqueue(save_usage_record, org_id, agent_id)

        # Check limits
        if usage > tier_limit:
            alert_approaching_limit(org_id)

class BillingEngine:
    def calculate_monthly_bill(self, org_id, month):
        tier = get_tier(org_id)
        conversations = get_count(org_id, month)
        included = TIER_LIMITS[tier]

        if conversations <= included:
            return TIER_PRICES[tier]
        else:
            overage = conversations - included
            return TIER_PRICES[tier] + (overage * OVERAGE_RATES[tier])
```

### Billing Integration

- **Payment Processor**: Stripe
- **Subscription Management**: Stripe Billing
- **Usage Metering**: Stripe metered billing
- **Invoicing**: Automated monthly
- **Failed Payment**: Webhook handling + grace period

## 7. Authentication & Security

### Authentication Layers

1. **Organization API Keys** (programmatic)
   - `sk_live_org_abc123...`
   - For integrations and API access
   - Scoped to organization + permissions

2. **User Authentication** (dashboard)
   - Email/password or SSO
   - Managed by Auth0/Clerk
   - MFA for Enterprise tier

3. **Agent Instance Keys** (widget)
   - `pk_widget_xyz...` (public, safe to expose)
   - Scoped to specific agent instance
   - Used in chat widgets

### Authorization (RBAC)

```python
Roles:
  - Owner: Full control, billing
  - Admin: Manage agents, analytics
  - Member: View only
  - Developer: API access (Pro+)

Permissions:
  - agents:deploy (Pro+)
  - agents:customize_prompts (Enterprise)
  - billing:view (All)
  - billing:manage (Owner)
  - team:invite (Admin+)
```

### Multi-Tenancy Security

```sql
-- Row-level security (PostgreSQL)
CREATE POLICY org_isolation ON conversations
  USING (organization_id = current_setting('app.current_org_id')::uuid);

-- Prevents data leakage between orgs
```

**Request Flow:**
```
Request → Auth Middleware
  ↓
Extract: org_id, user_id, permissions
  ↓
Set DB context: SET app.current_org_id = 'xxx'
  ↓
All queries automatically scoped
```

## 8. API Architecture

### Control Plane API

```
Base: https://api.auresta.com/v1
Auth: Bearer token or API key

/organizations
  GET    /{id}
  PATCH  /{id}
  GET    /{id}/usage

/stores
  GET    /organizations/{org_id}/stores
  POST   /organizations/{org_id}/stores
  PATCH  /stores/{id}

/agents
  GET    /agent-definitions (marketplace)
  POST   /stores/{store_id}/agent-instances
  GET    /agent-instances/{id}
  PATCH  /agent-instances/{id}/config
  DELETE /agent-instances/{id}

/knowledge-base
  POST   /agent-instances/{id}/knowledge/ingest
  GET    /agent-instances/{id}/knowledge/status

/billing
  GET    /organizations/{id}/subscription
  POST   /organizations/{id}/upgrade
  GET    /organizations/{id}/invoices
```

### Agent Runtime API

```
Base: https://agents.auresta.com/v1
Auth: Agent instance public key

/conversations
  POST   /conversations
  POST   /conversations/{id}/messages

/webhooks
  POST   /webhooks/events
```

**Design Principles:**
- RESTful
- Versioned (/v1, /v2)
- Rate limiting per tier
- Webhook support
- OpenAPI documentation

## 9. Monitoring & Observability

### Observability Stack

- **LangSmith**: LLM tracing per organization
- **Sentry**: Error tracking with org context
- **Datadog/Grafana**: Metrics and dashboards
- **Structured Logging**: JSON logs with org_id

### Key Metrics

**Per Organization:**
- Conversation volume
- Response latency (p50, p95, p99)
- Error rate by agent type
- Token usage and cost
- Knowledge base performance

**Platform-wide:**
- API response times
- Database performance
- Queue depth
- Infrastructure cost per org
- Deployment success rate

### Customer-Facing Analytics

```
Basic Tier:
  - Total conversations
  - Sentiment breakdown
  - Top 5 intents

Pro Tier:
  + Trend charts
  + Performance metrics
  + Custom date ranges
  + CSV export

Enterprise Tier:
  + LangSmith workspace
  + Custom dashboards
  + Real-time monitoring
  + Slack/email alerts
```

## 10. Implementation Roadmap

### Phase 1: Foundation (Months 1-2)

**Goal:** Multi-tenancy infrastructure

**Tasks:**
- ✓ Store model, knowledge base (done)
- Add Organization model
- Add AgentDefinition, AgentInstance models
- Implement row-level security
- Usage tracking system
- API key authentication
- Migrate existing data

**Deliverable:** Backend supports multiple orgs with isolation

### Phase 2: Control Plane MVP (Months 2-3)

**Goal:** Basic admin dashboard

**Tasks:**
- Build React admin dashboard
- Organization signup flow
- Deploy agent instance UI
- Knowledge base upload UI
- Usage dashboard
- Stripe integration

**Deliverable:** Self-service onboarding for CS agents

### Phase 3: Agent Type #2 - Sales (Month 4)

**Goal:** Prove multi-agent architecture

**Tasks:**
- Create sales/ agent graph
- Sales-specific nodes (qualification, objections)
- Sales prompts and capabilities
- Add to marketplace
- Test dual deployment

**Deliverable:** Two agent types working

### Phase 4: Tiered Features (Month 5)

**Goal:** Basic/Pro/Enterprise differentiation

**Tasks:**
- Tier-based feature flags
- Overage billing calculations
- Advanced config UI (Pro+)
- White-label (Enterprise)
- Custom prompts (Enterprise)

**Deliverable:** Three-tier offering live

### Phase 5: Scale & Polish (Month 6+)

**Goal:** Production-ready platform

**Tasks:**
- Kubernetes deployment automation
- Enterprise dedicated setup
- Enhanced analytics
- SSO/SAML support
- Advanced integrations
- Marketplace expansion

**Deliverable:** Platform ready for 20-100 clients

## Key Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Target Scale** | 20-100 clients in 12 months | Mid-scale allows automation with personalization |
| **Pricing Model** | Hybrid (base + overage) | Predictable baseline + upside capture |
| **Tier Strategy** | Basic/Pro/Enterprise | Serve different segments, upgrade path |
| **Deployment** | Hybrid (shared + dedicated) | Cost-efficient for most, premium isolation |
| **Agent Architecture** | Separate graphs per type | Independent versioning and iteration |
| **Control Plane** | Full platform UI | Competitive differentiator, reduce support |
| **Authentication** | Auth0/Clerk + API keys | Industry standard, MFA support |
| **Billing** | Stripe with metering | Proven, supports usage-based pricing |

## Success Metrics

**Year 1 Goals:**
- 50 active organizations
- 75% Basic/Pro (shared), 25% Enterprise
- $50K MRR
- < 2% churn rate
- 95% uptime SLA
- < 500ms p95 response time

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Multi-tenancy data leak | Critical | Row-level security + extensive testing |
| Shared platform limits Enterprise sales | High | Dedicated deployment option ready |
| LLM cost explosion | High | Usage limits + monitoring + alerts |
| Complex billing errors | Medium | Extensive testing + audit logs |
| Agent customization too limited | Medium | Tiered approach allows flexibility |

## Next Steps

1. Review and validate this design with stakeholders
2. Create detailed technical specifications per phase
3. Set up git worktree for Phase 1 development
4. Write implementation plan for Phase 1
5. Begin development

---

**Document Status:** ✅ Validated
**Next Review:** Start of each phase
**Owner:** Development Team
