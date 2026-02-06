# Phase 1: Multi-Tenancy Foundation - Implementation Plan

**Phase:** 1 of 5
**Duration:** 2 months
**Goal:** Build multi-tenancy infrastructure to support organization-level isolation
**Status:** Ready to implement

## Prerequisites (Completed ✅)

- ✅ Store model implemented (`src/models/store.py`)
- ✅ Knowledge base with store-level isolation (`src/models/knowledge.py`, `src/integrations/knowledge_base.py`)
- ✅ PostgreSQL with pgvector extension
- ✅ Basic conversation and message models
- ✅ LangGraph agent working for single store

## Phase 1 Tasks Breakdown

### Task 1: Database Schema - Organization Model

**Priority:** Critical
**Estimated Time:** 2-3 days
**Dependencies:** None

#### 1.1 Create Organization Model

**File:** `src/models/organization.py`

```python
from sqlalchemy import String, Integer, Numeric, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from src.models.base import Base, UUIDMixin, TimestampMixin

class Organization(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organizations"

    # Basic info
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)

    # Billing
    tier = Column(String(50), nullable=False, default="basic")  # basic, pro, enterprise
    billing_email = Column(String(255), nullable=False)
    subscription_status = Column(String(50), nullable=False, default="trial")  # trial, active, suspended, cancelled

    # Usage limits
    monthly_conversation_limit = Column(Integer, nullable=False, default=1000)
    overage_rate = Column(Numeric(10, 4), nullable=False, default=0.10)

    # Settings
    settings = Column(JSONB, nullable=False, default={})
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    stores = relationship("Store", back_populates="organization", cascade="all, delete-orphan")
    usage_records = relationship("ConversationUsage", back_populates="organization", cascade="all, delete-orphan")
```

#### 1.2 Update Store Model

**File:** `src/models/store.py`

Add organization relationship:
```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

class Store(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stores"

    # NEW: Link to organization
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)

    # Existing fields...
    name = Column(String(255), nullable=False)
    domain = Column(String(255))
    platform = Column(String(50))
    is_active = Column(Boolean, default=True)
    api_credentials = Column(JSONB)
    settings = Column(JSONB)

    # Relationships
    organization = relationship("Organization", back_populates="stores")
    agent_instances = relationship("AgentInstance", back_populates="store", cascade="all, delete-orphan")
```

#### 1.3 Create Migration

**Command:**
```bash
make migrate-new  # Enter: "add_organizations"
```

**File:** `alembic/versions/YYYYMMDD_HHMM_add_organizations.py`

Migration must:
1. Create `organizations` table
2. Add `organization_id` column to `stores` (nullable initially)
3. Create a default organization and assign all existing stores to it
4. Make `organization_id` NOT NULL
5. Add foreign key constraint

---

### Task 2: Agent Definition & Instance Models

**Priority:** Critical
**Estimated Time:** 3-4 days
**Dependencies:** Task 1 complete

#### 2.1 Create AgentDefinition Model

**File:** `src/models/agent.py`

```python
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from src.models.base import Base, UUIDMixin, TimestampMixin

class AgentDefinition(Base, UUIDMixin, TimestampMixin):
    """Template/blueprint for agent types"""
    __tablename__ = "agent_definitions"

    # Identity
    type = Column(String(100), nullable=False, index=True)  # customer_service, sales, marketing
    version = Column(String(50), nullable=False)  # 2.1.0
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Configuration
    graph_module = Column(String(255), nullable=False)  # e.g., "src.agents.customer_service.graph"
    capabilities = Column(JSONB, nullable=False, default=[])
    default_config = Column(JSONB, nullable=False, default={})

    # Tier restrictions
    tier_restrictions = Column(JSONB, nullable=False, default={})  # {"min_tier": "pro"}

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_deprecated = Column(Boolean, nullable=False, default=False)

    # Relationships
    instances = relationship("AgentInstance", back_populates="definition")

    __table_args__ = (
        Index("idx_agent_type_version", "type", "version"),
    )
```

#### 2.2 Create AgentInstance Model

**File:** `src/models/agent.py` (same file)

```python
class AgentInstance(Base, UUIDMixin, TimestampMixin):
    """Deployed agent tied to a specific store"""
    __tablename__ = "agent_instances"

    # Relationships
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False, index=True)
    agent_definition_id = Column(UUID(as_uuid=True), ForeignKey("agent_definitions.id"), nullable=False)

    # Identity
    name = Column(String(255), nullable=False)  # e.g., "Auresta CS Agent"
    public_key = Column(String(255), unique=True, nullable=False, index=True)  # pk_widget_xxx

    # Status
    status = Column(String(50), nullable=False, default="active")  # active, paused, archived

    # Configuration
    config_overrides = Column(JSONB, nullable=False, default={})

    # Metadata
    deployed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deployed_by = Column(String(255))  # user email or "system"

    # Relationships
    store = relationship("Store", back_populates="agent_instances")
    definition = relationship("AgentDefinition", back_populates="instances")
    conversations = relationship("Conversation", back_populates="agent_instance")
```

#### 2.3 Update Conversation Model

**File:** `src/models/conversation.py`

Add agent_instance relationship:
```python
class Conversation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversations"

    # NEW: Link to agent instance
    agent_instance_id = Column(UUID(as_uuid=True), ForeignKey("agent_instances.id"), nullable=False, index=True)

    # Existing fields...
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    customer_email = Column(String(255))
    status = Column(String(50), default="active")
    sentiment = Column(String(50))
    escalated = Column(Boolean, default=False)
    metadata = Column(JSONB)

    # Relationships
    agent_instance = relationship("AgentInstance", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
```

#### 2.4 Create Migration

```bash
make migrate-new  # Enter: "add_agent_definitions_and_instances"
```

---

### Task 3: Usage Tracking for Billing

**Priority:** High
**Estimated Time:** 2-3 days
**Dependencies:** Task 1 complete

#### 3.1 Create ConversationUsage Model

**File:** `src/models/billing.py`

```python
from sqlalchemy import Date, Integer, Numeric, ForeignKey, Index
from sqlalchemy.orm import relationship
from src.models.base import Base, UUIDMixin, TimestampMixin

class ConversationUsage(Base, UUIDMixin, TimestampMixin):
    """Tracks conversation usage per organization per month for billing"""
    __tablename__ = "conversation_usage"

    # Links
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    agent_instance_id = Column(UUID(as_uuid=True), ForeignKey("agent_instances.id"), nullable=True)  # Optional: track per instance

    # Time period
    month = Column(Date, nullable=False)  # First day of month

    # Usage
    conversation_count = Column(Integer, nullable=False, default=0)

    # Billing
    billed_amount = Column(Numeric(10, 2), nullable=True)  # Null until billed
    billed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="usage_records")

    __table_args__ = (
        Index("idx_usage_org_month", "organization_id", "month", unique=True),
    )
```

#### 3.2 Create Usage Tracker Service

**File:** `src/services/usage_tracker.py`

```python
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.models.billing import ConversationUsage
from src.models.organization import Organization
import structlog

logger = structlog.get_logger()

class UsageTracker:
    """Tracks conversation usage for billing"""

    async def track_conversation(
        self,
        session: AsyncSession,
        organization_id: str,
        agent_instance_id: str,
    ) -> None:
        """Increment conversation count for the current month"""
        current_month = date.today().replace(day=1)

        # Upsert usage record
        stmt = select(ConversationUsage).where(
            ConversationUsage.organization_id == organization_id,
            ConversationUsage.month == current_month,
        )
        result = await session.execute(stmt)
        usage_record = result.scalar_one_or_none()

        if usage_record:
            usage_record.conversation_count += 1
        else:
            usage_record = ConversationUsage(
                organization_id=organization_id,
                agent_instance_id=agent_instance_id,
                month=current_month,
                conversation_count=1,
            )
            session.add(usage_record)

        await session.commit()

        logger.info(
            "conversation_tracked",
            organization_id=organization_id,
            month=str(current_month),
            count=usage_record.conversation_count,
        )

        # Check if approaching limit
        await self._check_limit_alert(session, organization_id, current_month)

    async def _check_limit_alert(
        self,
        session: AsyncSession,
        organization_id: str,
        month: date,
    ) -> None:
        """Alert if approaching monthly limit"""
        stmt = select(Organization).where(Organization.id == organization_id)
        result = await session.execute(stmt)
        org = result.scalar_one()

        stmt = select(ConversationUsage).where(
            ConversationUsage.organization_id == organization_id,
            ConversationUsage.month == month,
        )
        result = await session.execute(stmt)
        usage = result.scalar_one()

        limit = org.monthly_conversation_limit
        current = usage.conversation_count

        if current >= limit * 0.9:  # 90% threshold
            logger.warning(
                "usage_limit_approaching",
                organization_id=organization_id,
                current=current,
                limit=limit,
                tier=org.tier,
            )
            # TODO: Send email/webhook notification
```

#### 3.3 Create Migration

```bash
make migrate-new  # Enter: "add_conversation_usage"
```

---

### Task 4: Row-Level Security (RLS)

**Priority:** Critical (Security)
**Estimated Time:** 2-3 days
**Dependencies:** Task 1 complete

#### 4.1 Create RLS Policies

**File:** `alembic/versions/YYYYMMDD_HHMM_add_row_level_security.py`

```python
def upgrade() -> None:
    # Enable RLS on critical tables
    op.execute("ALTER TABLE stores ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conversations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE knowledge_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agent_instances ENABLE ROW LEVEL SECURITY")

    # Create policy for stores
    op.execute("""
        CREATE POLICY org_isolation_stores ON stores
        USING (
            organization_id::text = current_setting('app.current_org_id', TRUE)
            OR current_setting('app.current_org_id', TRUE) IS NULL
        )
    """)

    # Create policy for conversations
    op.execute("""
        CREATE POLICY org_isolation_conversations ON conversations
        USING (
            EXISTS (
                SELECT 1 FROM stores
                WHERE stores.id = conversations.store_id
                AND stores.organization_id::text = current_setting('app.current_org_id', TRUE)
            )
            OR current_setting('app.current_org_id', TRUE) IS NULL
        )
    """)

    # Similar policies for other tables...
```

#### 4.2 Create Security Middleware

**File:** `src/api/middleware/security.py`

```python
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies import get_session
import structlog

logger = structlog.get_logger()

async def set_organization_context(
    request: Request,
    session: AsyncSession,
    organization_id: str,
) -> None:
    """Set PostgreSQL session variable for RLS"""
    await session.execute(
        f"SET LOCAL app.current_org_id = '{organization_id}'"
    )
    logger.debug("rls_context_set", organization_id=organization_id)
```

---

### Task 5: API Key Authentication

**Priority:** High
**Estimated Time:** 3-4 days
**Dependencies:** Task 2 complete

#### 5.1 Add API Keys to Models

**File:** `src/models/organization.py`

```python
class OrganizationAPIKey(Base, UUIDMixin, TimestampMixin):
    """API keys for programmatic access"""
    __tablename__ = "organization_api_keys"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    # Key
    key_prefix = Column(String(20), nullable=False, index=True)  # sk_live_xxx or sk_test_xxx
    key_hash = Column(String(255), nullable=False, unique=True)  # bcrypt hash

    # Metadata
    name = Column(String(255), nullable=False)  # "Production API Key"
    scopes = Column(JSONB, nullable=False, default=["conversations:create"])

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    last_used_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))

    # Relationships
    organization = relationship("Organization")
```

Update `AgentInstance` model to include public key (already done in Task 2.2).

#### 5.2 Create Auth Service

**File:** `src/services/auth.py`

```python
import secrets
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.organization import OrganizationAPIKey
from src.models.agent import AgentInstance
import structlog

logger = structlog.get_logger()

class AuthService:
    """Handles API key authentication"""

    @staticmethod
    def generate_api_key(prefix: str = "sk_live") -> tuple[str, str]:
        """Generate API key and return (full_key, hash)"""
        random_part = secrets.token_urlsafe(32)
        full_key = f"{prefix}_{random_part}"
        key_hash = bcrypt.hashpw(full_key.encode(), bcrypt.gensalt()).decode()
        return full_key, key_hash

    @staticmethod
    def generate_widget_key() -> str:
        """Generate public widget key (not hashed, safe to expose)"""
        return f"pk_widget_{secrets.token_urlsafe(24)}"

    async def verify_organization_key(
        self,
        session: AsyncSession,
        api_key: str,
    ) -> OrganizationAPIKey | None:
        """Verify organization API key"""
        prefix = api_key.split("_")[0] + "_" + api_key.split("_")[1]

        stmt = select(OrganizationAPIKey).where(
            OrganizationAPIKey.key_prefix == prefix,
            OrganizationAPIKey.is_active == True,
        )
        result = await session.execute(stmt)
        keys = result.scalars().all()

        for key_record in keys:
            if bcrypt.checkpw(api_key.encode(), key_record.key_hash.encode()):
                # Update last_used_at
                key_record.last_used_at = func.now()
                await session.commit()
                return key_record

        return None

    async def verify_widget_key(
        self,
        session: AsyncSession,
        widget_key: str,
    ) -> AgentInstance | None:
        """Verify widget public key"""
        stmt = select(AgentInstance).where(
            AgentInstance.public_key == widget_key,
            AgentInstance.status == "active",
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
```

#### 5.3 Create Auth Middleware

**File:** `src/api/middleware/auth.py`

```python
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.auth import AuthService
from src.api.dependencies import get_session
import structlog

logger = structlog.get_logger()
security = HTTPBearer()

async def get_current_organization(
    request: Request,
    credentials: HTTPAuthorizationCredentials,
    session: AsyncSession,
) -> str:
    """Extract organization_id from API key"""
    api_key = credentials.credentials

    auth_service = AuthService()

    # Try organization API key
    key_record = await auth_service.verify_organization_key(session, api_key)
    if key_record:
        logger.info("org_authenticated", organization_id=key_record.organization_id)
        return str(key_record.organization_id)

    # Try widget key
    agent_instance = await auth_service.verify_widget_key(session, api_key)
    if agent_instance:
        # Load organization via store
        org_id = agent_instance.store.organization_id
        logger.info("widget_authenticated", organization_id=org_id)
        return str(org_id)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )
```

---

### Task 6: Data Migration

**Priority:** High
**Estimated Time:** 1-2 days
**Dependencies:** Tasks 1-4 complete

#### 6.1 Create Default Organization

**File:** `scripts/migrate_to_multi_tenant.py`

```python
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_session_context
from src.models.organization import Organization
from src.models.store import Store
from src.services.auth import AuthService
import structlog

logger = structlog.get_logger()

async def migrate_existing_data():
    """Migrate existing single-tenant data to multi-tenant structure"""

    async with get_session_context() as session:
        # 1. Create default organization
        default_org = Organization(
            name="Auresta",
            slug="auresta",
            tier="enterprise",
            billing_email="billing@auresta.com.au",
            subscription_status="active",
            monthly_conversation_limit=10000,
            overage_rate=0.05,
        )
        session.add(default_org)
        await session.flush()

        logger.info("created_default_org", org_id=default_org.id)

        # 2. Assign all existing stores to default org
        stores = await session.execute(select(Store))
        for store in stores.scalars():
            store.organization_id = default_org.id

        await session.commit()
        logger.info("migrated_stores", count=len(stores.scalars().all()))

        # 3. Create default agent definition
        from src.models.agent import AgentDefinition

        cs_agent_def = AgentDefinition(
            type="customer_service",
            version="1.0.0",
            name="E-commerce Customer Service Agent",
            description="Handles WISMO, returns, refunds, and general inquiries",
            graph_module="src.agents.graph",
            capabilities=["order_status", "returns", "refunds", "general_inquiry"],
            tier_restrictions={},
        )
        session.add(cs_agent_def)
        await session.flush()

        logger.info("created_agent_definition", definition_id=cs_agent_def.id)

        # 4. Create agent instances for existing stores
        auth_service = AuthService()

        for store in stores.scalars():
            widget_key = auth_service.generate_widget_key()

            instance = AgentInstance(
                store_id=store.id,
                agent_definition_id=cs_agent_def.id,
                name=f"{store.name} CS Agent",
                public_key=widget_key,
                status="active",
                deployed_by="migration_script",
            )
            session.add(instance)

        await session.commit()
        logger.info("created_agent_instances")

        # 5. Update existing conversations to link to agent instances
        # This requires a database-level update
        await session.execute("""
            UPDATE conversations
            SET agent_instance_id = (
                SELECT id FROM agent_instances
                WHERE agent_instances.store_id = conversations.store_id
                LIMIT 1
            )
        """)
        await session.commit()

        logger.info("migration_complete")

if __name__ == "__main__":
    asyncio.run(migrate_existing_data())
```

---

## Testing Plan

### Unit Tests

**File:** `tests/unit/test_organization.py`
- Test Organization model creation
- Test tier limits and overage calculations
- Test organization-store relationships

**File:** `tests/unit/test_agent_models.py`
- Test AgentDefinition creation
- Test AgentInstance deployment
- Test configuration overrides

**File:** `tests/unit/test_usage_tracker.py`
- Test conversation tracking
- Test monthly rollover
- Test limit alerts

**File:** `tests/unit/test_auth_service.py`
- Test API key generation
- Test key verification
- Test widget key validation

### Integration Tests

**File:** `tests/integration/test_multi_tenant_isolation.py`
- Test RLS policies work correctly
- Test organization A cannot access organization B data
- Test cross-store isolation within same org

**File:** `tests/integration/test_auth_flow.py`
- Test end-to-end API key authentication
- Test widget key authentication
- Test organization context setting

---

## Deployment Checklist

- [ ] All migrations run successfully on dev database
- [ ] Migration script tested with production-like data
- [ ] RLS policies verified with test queries
- [ ] API key authentication tested via Postman/curl
- [ ] Usage tracking verified by creating test conversations
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Documentation updated in MULTI_TENANCY.md
- [ ] Environment variables documented (.env.example)
- [ ] Docker Compose updated if needed
- [ ] Rollback plan documented

---

## Rollback Plan

If issues occur during deployment:

1. **Immediate rollback:**
   ```bash
   # Rollback last migration
   alembic downgrade -1
   ```

2. **Full rollback to pre-Phase 1:**
   ```bash
   # Rollback all Phase 1 migrations
   alembic downgrade <revision_before_phase_1>
   ```

3. **Data corruption:**
   - Restore from backup taken before migration
   - Re-run migration with fixes

---

## Success Criteria

- [ ] Organizations table exists and can be queried
- [ ] Stores are linked to organizations
- [ ] AgentDefinition and AgentInstance tables exist
- [ ] Conversations track usage per organization
- [ ] RLS policies prevent cross-organization data access
- [ ] API keys authenticate successfully
- [ ] Widget keys authenticate successfully
- [ ] Migration script completes without errors
- [ ] All existing conversations still accessible
- [ ] No performance regression in API response times

---

## Next Steps After Phase 1

Once Phase 1 is complete:
- **Phase 2:** Build React admin dashboard (control plane UI)
- **Phase 3:** Implement second agent type (sales agent)
- **Phase 4:** Add tiered feature restrictions
- **Phase 5:** Production deployment automation

---

**Document Owner:** Development Team
**Created:** 2026-02-07
**Status:** Ready for Implementation
