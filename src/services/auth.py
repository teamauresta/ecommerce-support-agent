"""Authentication service for API keys and widget keys."""

import secrets
from datetime import datetime

import bcrypt
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import AgentInstance
from src.models.billing import OrganizationAPIKey
from src.models.store import Store

logger = structlog.get_logger()


class AuthService:
    """Handles API key generation and verification."""

    @staticmethod
    def generate_api_key(prefix: str = "sk_live") -> tuple[str, str]:
        """
        Generate a new API key for organization access.

        Args:
            prefix: Key prefix (sk_live or sk_test)

        Returns:
            Tuple of (full_key, key_hash)
        """
        random_part = secrets.token_urlsafe(32)
        full_key = f"{prefix}_{random_part}"
        key_hash = bcrypt.hashpw(full_key.encode(), bcrypt.gensalt()).decode()
        return full_key, key_hash

    @staticmethod
    def generate_widget_key() -> str:
        """
        Generate a public widget key for agent instances.

        Widget keys are safe to expose in frontend code.

        Returns:
            Widget key string (pk_widget_xxx)
        """
        return f"pk_widget_{secrets.token_urlsafe(24)}"

    async def verify_organization_key(
        self,
        session: AsyncSession,
        api_key: str,
    ) -> OrganizationAPIKey | None:
        """
        Verify an organization API key.

        Args:
            session: Database session
            api_key: API key to verify

        Returns:
            OrganizationAPIKey if valid, None otherwise
        """
        try:
            # Extract prefix (e.g., "sk_live" from "sk_live_xxx")
            parts = api_key.split("_")
            if len(parts) < 2:
                return None
            prefix = f"{parts[0]}_{parts[1]}"

            # Find all active keys with this prefix
            stmt = select(OrganizationAPIKey).where(
                OrganizationAPIKey.key_prefix == prefix,
                OrganizationAPIKey.is_active,
            )
            result = await session.execute(stmt)
            keys = result.scalars().all()

            # Check each key with constant-time comparison
            for key_record in keys:
                if bcrypt.checkpw(api_key.encode(), key_record.key_hash.encode()):
                    # Update last_used_at
                    key_record.last_used_at = datetime.now()
                    await session.commit()

                    logger.info(
                        "org_api_key_verified",
                        organization_id=key_record.organization_id,
                        key_name=key_record.name,
                    )
                    return key_record

            logger.warning("org_api_key_invalid", prefix=prefix)
            return None

        except Exception as e:
            logger.error("org_api_key_verification_error", error=str(e))
            return None

    async def verify_widget_key(
        self,
        session: AsyncSession,
        widget_key: str,
    ) -> AgentInstance | None:
        """
        Verify a widget public key.

        Args:
            session: Database session
            widget_key: Widget key to verify

        Returns:
            AgentInstance if valid, None otherwise
        """
        try:
            stmt = select(AgentInstance).where(
                AgentInstance.public_key == widget_key,
                AgentInstance.status == "active",
            )
            result = await session.execute(stmt)
            agent_instance = result.scalar_one_or_none()

            if agent_instance:
                logger.info(
                    "widget_key_verified",
                    agent_instance_id=agent_instance.id,
                    store_id=agent_instance.store_id,
                )
            else:
                logger.warning("widget_key_invalid", key_prefix=widget_key[:12])

            return agent_instance

        except Exception as e:
            logger.error("widget_key_verification_error", error=str(e))
            return None

    async def create_api_key(
        self,
        session: AsyncSession,
        organization_id: str,
        name: str,
        prefix: str = "sk_live",
        scopes: list[str] | None = None,
    ) -> tuple[str, OrganizationAPIKey]:
        """
        Create a new API key for an organization.

        Args:
            session: Database session
            organization_id: Organization UUID
            name: Descriptive name for the key
            prefix: Key prefix (sk_live or sk_test)
            scopes: Permission scopes

        Returns:
            Tuple of (api_key, OrganizationAPIKey record)
        """
        if scopes is None:
            scopes = ["conversations:create"]

        # Generate key
        api_key, key_hash = self.generate_api_key(prefix)

        # Create record
        api_key_record = OrganizationAPIKey(
            organization_id=organization_id,
            key_prefix=prefix,
            key_hash=key_hash,
            name=name,
            scopes=scopes,
            is_active=True,
        )
        session.add(api_key_record)
        await session.commit()
        await session.refresh(api_key_record)

        logger.info(
            "api_key_created",
            organization_id=organization_id,
            key_name=name,
            prefix=prefix,
        )

        return api_key, api_key_record

    async def revoke_api_key(
        self,
        session: AsyncSession,
        key_id: str,
    ) -> bool:
        """
        Revoke an API key.

        Args:
            session: Database session
            key_id: API key record UUID

        Returns:
            True if revoked, False if not found
        """
        stmt = select(OrganizationAPIKey).where(OrganizationAPIKey.id == key_id)
        result = await session.execute(stmt)
        api_key = result.scalar_one_or_none()

        if not api_key:
            return False

        api_key.is_active = False
        await session.commit()

        logger.info(
            "api_key_revoked",
            key_id=key_id,
            organization_id=api_key.organization_id,
        )
        return True

    async def get_organization_from_key(
        self,
        session: AsyncSession,
        api_key: str,
    ) -> str | None:
        """
        Extract organization ID from an API key (either org key or widget key).

        Args:
            session: Database session
            api_key: API key to check

        Returns:
            Organization UUID or None
        """
        # Try organization API key
        key_record = await self.verify_organization_key(session, api_key)
        if key_record:
            return key_record.organization_id

        # Try widget key
        agent_instance = await self.verify_widget_key(session, api_key)
        if agent_instance:
            # Load the store to get organization_id
            stmt = select(Store).where(Store.id == agent_instance.store_id)
            result = await session.execute(stmt)
            store = result.scalar_one()
            return store.organization_id

        return None
