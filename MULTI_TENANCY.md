# Multi-Tenancy Guide

## 🎯 Summary
Your system **already supports multi-tenancy** out of the box! Each store can have its own knowledge base while sharing the same infrastructure.

## 📊 Current Setup

| Store | Store ID | Knowledge | Chunks |
|-------|----------|-----------|--------|
| Development Store (Auresta) | `00000000-0000-0000-0000-000000000001` | www.auresta.com.au | 25 chunks |
| Tech Store (Example) | `aaaaaaaa-bbbb-cccc-dddd-111111111111` | www.anthropic.com | 11 chunks |

## 🔧 How to Deploy a New Agent

### Option 1: Add New Store to Existing Deployment (Recommended)

**Step 1: Create the Store**
```sql
INSERT INTO stores (id, name, domain, platform, is_active, api_credentials, settings)
VALUES (
    'new-store-uuid-here',
    'Client Company Name',
    'client-domain.com',
    'shopify',
    true,
    '{}',
    '{}'
);
```

**Step 2: Ingest Knowledge**
```bash
# Via API (easiest)
curl -X POST http://localhost:8001/api/v1/knowledge-base/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "store_id": "new-store-uuid-here",
    "url": "https://client-website.com",
    "max_pages": 100
  }'

# Via CLI (if you have Python env)
python scripts/ingest_website.py \
  --store-id new-store-uuid-here \
  --url https://client-website.com \
  --max-pages 100
```

**Step 3: Route Traffic**
Modify `src/api/routes/conversations.py`:
```python
async def create_conversation(request, session):
    # Determine store from API key or domain
    store_id = get_store_from_api_key(request.headers['Authorization'])
    # Or from subdomain/domain
    # store_id = get_store_from_domain(request.headers['Host'])

    conversation = Conversation(store_id=store_id, ...)
```

### Option 2: Separate Deployment

Deploy a completely independent instance:
```bash
# Clone the repo
git clone <repo-url> client-agent
cd client-agent

# Configure new environment
cp .env.example .env
# Edit .env with new DATABASE_URL, OPENAI_API_KEY, etc.

# Deploy
docker-compose up -d

# Ingest knowledge
python scripts/ingest_website.py \
  --store-id <uuid> \
  --url https://client-website.com
```

## 🌐 Deployment Strategies

### Strategy A: Single Deployment, Multiple Stores (SaaS Model)
```
┌─────────────────────────────────────┐
│     Single FastAPI Instance         │
│                                     │
│  ┌─────────┐  ┌─────────┐         │
│  │ Store 1 │  │ Store 2 │  ...    │
│  │ KB: 25  │  │ KB: 11  │         │
│  └─────────┘  └─────────┘         │
│                                     │
│     Shared PostgreSQL Database      │
│  (store_id filters all queries)    │
└─────────────────────────────────────┘

Pros: Cost-efficient, easy to manage
Cons: Shared resources
Best for: SaaS platform with many clients
```

### Strategy B: Dedicated Deployments
```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Client A   │  │   Client B   │  │   Client C   │
│              │  │              │  │              │
│  API + DB    │  │  API + DB    │  │  API + DB    │
│  KB: 100     │  │  KB: 200     │  │  KB: 50      │
└──────────────┘  └──────────────┘  └──────────────┘

Pros: Complete isolation, custom config per client
Cons: Higher costs, more management overhead
Best for: Enterprise clients, compliance requirements
```

### Strategy C: Hybrid (Recommended for Growth)
```
┌─────────────────────────────────────┐
│         Shared Platform             │
│  Small/Medium Clients (Stores 1-50) │
└─────────────────────────────────────┘
              +
┌──────────────┐  ┌──────────────┐
│ Enterprise A │  │ Enterprise B │
│ (Dedicated)  │  │ (Dedicated)  │
└──────────────┘  └──────────────┘

Pros: Balanced cost/isolation
Best for: Growing platform
```

## 🔐 API Key Based Routing (Production Pattern)

**In your `.env` or database:**
```
API_KEY_1=sk_live_auresta_xxx → store_id: 00000000-0000-0000-0000-000000000001
API_KEY_2=sk_live_techco_yyy → store_id: aaaaaaaa-bbbb-cccc-dddd-111111111111
```

**Update middleware:**
```python
# src/api/middleware/auth.py
def get_store_from_api_key(api_key: str) -> str:
    # Query stores table where api_key matches
    # Return store_id
    pass
```

## 📝 Quick Commands

```bash
# Check all stores
docker compose exec db psql -U postgres -d support_agent -c \
  "SELECT id, name, (SELECT COUNT(*) FROM knowledge_chunks WHERE store_id = stores.id) FROM stores;"

# Check knowledge status for a store
curl http://localhost:8001/api/v1/knowledge-base/{store_id}/status

# Ingest new knowledge
curl -X POST http://localhost:8001/api/v1/knowledge-base/ingest \
  -H 'Content-Type: application/json' \
  -d '{"store_id":"xxx","url":"https://example.com","max_pages":50}'

# Clear knowledge for a store (re-index)
docker compose exec db psql -U postgres -d support_agent -c \
  "DELETE FROM knowledge_chunks WHERE store_id = 'xxx';"
```

## 🎯 Next Steps

1. **For each new client:**
   - Create a store in the database
   - Ingest their website/docs
   - Configure API key routing

2. **For production:**
   - Add authentication middleware
   - Implement API key → store_id mapping
   - Set up monitoring per store
   - Configure rate limits per store

3. **Scaling:**
   - Start with Option 1 (shared deployment)
   - Move enterprise clients to dedicated deployments
   - Use LangSmith to track usage per store

## 🔍 How Isolation Works

### Database Level
Every query filters by `store_id`:
```sql
SELECT * FROM knowledge_chunks WHERE store_id = 'xxx';
SELECT * FROM conversations WHERE store_id = 'xxx';
```

### Agent Level
```python
# When agent searches knowledge base
kb_results = await kb_client.search(
    session=session,
    store_id=state["store_id"],  # Only searches this store
    query=query
)
```

### API Level
```python
# Conversation creation
conversation = Conversation(
    store_id=request.store_id,  # Tied to specific store
    ...
)
```

## ✅ Verification

Test isolation:
```bash
# Store 1 only sees its own knowledge
curl http://localhost:8001/api/v1/knowledge-base/00000000-0000-0000-0000-000000000001/status

# Store 2 only sees its own knowledge
curl http://localhost:8001/api/v1/knowledge-base/aaaaaaaa-bbbb-cccc-dddd-111111111111/status
```
