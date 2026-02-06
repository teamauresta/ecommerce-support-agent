#!/usr/bin/env python3
"""
Data migration script to convert existing single-tenant data to multi-tenant structure.

This script:
1. Creates a default organization for existing data
2. Assigns all existing stores to this organization
3. Creates a default agent definition for customer service
4. Creates agent instances for all stores
5. Links existing conversations to agent instances
6. Creates API keys for the organization

Run this AFTER running the alembic migration to add the new tables.
"""

import asyncio
import sys
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_context
from src.models.organization import Organization
from src.models.store import Store
from src.models.agent import AgentDefinition, AgentInstance
from src.models.conversation import Conversation
from src.services.auth import AuthService
import structlog

logger = structlog.get_logger()


async def migrate_existing_data():
    """Migrate existing single-tenant data to multi-tenant structure."""

    logger.info("migration_started", script="migrate_to_multi_tenant")

    async with get_session_context() as session:
        try:
            # Step 1: Create default organization
            logger.info("step_1", action="creating_default_organization")

            default_org = Organization(
                name="Auresta",
                slug="auresta",
                tier="enterprise",
                billing_email="billing@auresta.com.au",
                subscription_status="active",
                monthly_conversation_limit=10000,
                overage_rate=0.05,
                settings={
                    "is_initial_organization": True,
                    "migrated_from_single_tenant": True,
                },
            )
            session.add(default_org)
            await session.flush()

            logger.info(
                "organization_created",
                org_id=default_org.id,
                name=default_org.name,
            )

            # Step 2: Assign all existing stores to default org
            logger.info("step_2", action="assigning_stores_to_organization")

            stmt = select(Store)
            result = await session.execute(stmt)
            stores = result.scalars().all()

            store_count = 0
            for store in stores:
                store.organization_id = default_org.id
                store_count += 1

            await session.flush()
            logger.info("stores_assigned", count=store_count)

            # Step 3: Create default agent definition
            logger.info("step_3", action="creating_agent_definition")

            cs_agent_def = AgentDefinition(
                type="customer_service",
                version="1.0.0",
                name="E-commerce Customer Service Agent",
                description="Handles WISMO, returns, refunds, and general inquiries",
                graph_module="src.agents.graph",
                capabilities=[
                    "order_status",
                    "return_request",
                    "refund_request",
                    "address_change",
                    "cancel_order",
                    "product_question",
                    "shipping_question",
                    "complaint",
                    "general_inquiry",
                ],
                default_config={
                    "model": "gpt-4o-mini",
                    "temperature": 0.1,
                },
                tier_restrictions={},
            )
            session.add(cs_agent_def)
            await session.flush()

            logger.info(
                "agent_definition_created",
                definition_id=cs_agent_def.id,
                type=cs_agent_def.type,
            )

            # Step 4: Create agent instances for existing stores
            logger.info("step_4", action="creating_agent_instances")

            auth_service = AuthService()
            instance_count = 0

            for store in stores:
                widget_key = auth_service.generate_widget_key()

                instance = AgentInstance(
                    store_id=store.id,
                    agent_definition_id=cs_agent_def.id,
                    name=f"{store.name} CS Agent",
                    public_key=widget_key,
                    status="active",
                    deployed_by="migration_script",
                    config_overrides={},
                )
                session.add(instance)
                instance_count += 1

                logger.info(
                    "agent_instance_created",
                    store_id=store.id,
                    store_name=store.name,
                    widget_key=widget_key[:20] + "...",
                )

            await session.flush()
            logger.info("agent_instances_created", count=instance_count)

            # Step 5: Update existing conversations to link to agent instances
            logger.info("step_5", action="linking_conversations_to_agents")

            # Get all agent instances
            stmt = select(AgentInstance)
            result = await session.execute(stmt)
            agent_instances = result.scalars().all()

            # Create mapping of store_id -> agent_instance_id
            store_to_agent = {ai.store_id: ai.id for ai in agent_instances}

            # Update conversations
            stmt = select(Conversation)
            result = await session.execute(stmt)
            conversations = result.scalars().all()

            conversation_count = 0
            for conversation in conversations:
                agent_instance_id = store_to_agent.get(conversation.store_id)
                if agent_instance_id:
                    conversation.agent_instance_id = agent_instance_id
                    conversation_count += 1
                else:
                    logger.warning(
                        "no_agent_instance_for_conversation",
                        conversation_id=conversation.id,
                        store_id=conversation.store_id,
                    )

            await session.flush()
            logger.info("conversations_linked", count=conversation_count)

            # Step 6: Create API keys for the organization
            logger.info("step_6", action="creating_api_keys")

            # Create production API key
            api_key_live, _ = await auth_service.create_api_key(
                session=session,
                organization_id=default_org.id,
                name="Production API Key",
                prefix="sk_live",
                scopes=["conversations:create", "conversations:read", "knowledge:manage"],
            )

            # Create test API key
            api_key_test, _ = await auth_service.create_api_key(
                session=session,
                organization_id=default_org.id,
                name="Test API Key",
                prefix="sk_test",
                scopes=["conversations:create", "conversations:read"],
            )

            logger.info("api_keys_created", count=2)

            # Commit all changes
            await session.commit()

            # Step 7: Print summary
            logger.info("migration_completed", status="success")

            print("\n" + "=" * 70)
            print(" MIGRATION COMPLETED SUCCESSFULLY")
            print("=" * 70)
            print(f"\n✅ Organization Created:")
            print(f"   ID: {default_org.id}")
            print(f"   Name: {default_org.name}")
            print(f"   Tier: {default_org.tier}")
            print(f"\n✅ Stores Migrated: {store_count}")
            print(f"\n✅ Agent Definition Created:")
            print(f"   Type: {cs_agent_def.type}")
            print(f"   Version: {cs_agent_def.version}")
            print(f"\n✅ Agent Instances Created: {instance_count}")
            print(f"\n✅ Conversations Linked: {conversation_count}")
            print(f"\n✅ API Keys Created:")
            print(f"   Production: {api_key_live}")
            print(f"   Test: {api_key_test}")
            print("\n" + "=" * 70)
            print("\n⚠️  IMPORTANT: Save these API keys securely!")
            print("   They will not be shown again.")
            print("\n" + "=" * 70 + "\n")

        except Exception as e:
            await session.rollback()
            logger.error("migration_failed", error=str(e), exc_info=True)
            print(f"\n❌ Migration failed: {e}")
            print("   Database changes have been rolled back.")
            sys.exit(1)


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(" DATA MIGRATION: Single-Tenant → Multi-Tenant")
    print("=" * 70)
    print("\nThis script will:")
    print("  1. Create a default organization")
    print("  2. Assign all stores to the organization")
    print("  3. Create agent definitions and instances")
    print("  4. Link existing conversations to agents")
    print("  5. Create API keys")
    print("\n⚠️  Make sure you have:")
    print("  - Run the alembic migration first (make migrate)")
    print("  - Backed up your database")
    print("\n" + "=" * 70 + "\n")

    confirm = input("Continue with migration? (yes/no): ")
    if confirm.lower() != "yes":
        print("Migration cancelled.")
        sys.exit(0)

    asyncio.run(migrate_existing_data())
