"""Usage tracking service for billing."""

from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.billing import ConversationUsage
from src.models.organization import Organization
import structlog

logger = structlog.get_logger()


class UsageTracker:
    """Tracks conversation usage for billing purposes."""

    async def track_conversation(
        self,
        session: AsyncSession,
        organization_id: str,
        agent_instance_id: str,
    ) -> None:
        """
        Increment conversation count for the current month.

        Args:
            session: Database session
            organization_id: Organization UUID
            agent_instance_id: Agent instance UUID
        """
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
        """
        Alert if approaching monthly conversation limit.

        Args:
            session: Database session
            organization_id: Organization UUID
            month: Month date
        """
        # Get organization
        stmt = select(Organization).where(Organization.id == organization_id)
        result = await session.execute(stmt)
        org = result.scalar_one()

        # Get usage
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
                percent=int((current / limit) * 100),
            )
            # TODO: Send email/webhook notification to organization

    async def get_current_usage(
        self,
        session: AsyncSession,
        organization_id: str,
    ) -> dict:
        """
        Get current month's usage statistics.

        Args:
            session: Database session
            organization_id: Organization UUID

        Returns:
            Usage statistics dictionary
        """
        current_month = date.today().replace(day=1)

        # Get organization
        stmt = select(Organization).where(Organization.id == organization_id)
        result = await session.execute(stmt)
        org = result.scalar_one()

        # Get usage
        stmt = select(ConversationUsage).where(
            ConversationUsage.organization_id == organization_id,
            ConversationUsage.month == current_month,
        )
        result = await session.execute(stmt)
        usage = result.scalar_one_or_none()

        conversations_used = usage.conversation_count if usage else 0
        limit = org.monthly_conversation_limit
        overage = max(0, conversations_used - limit)

        return {
            "month": str(current_month),
            "tier": org.tier,
            "conversations_used": conversations_used,
            "conversations_limit": limit,
            "conversations_remaining": max(0, limit - conversations_used),
            "overage": overage,
            "overage_cost": float(overage * org.overage_rate),
            "percent_used": int((conversations_used / limit) * 100) if limit > 0 else 0,
        }


class BillingEngine:
    """Calculate billing amounts for organizations."""

    # Tier pricing configuration
    TIER_PRICES = {
        "basic": 99.00,
        "pro": 499.00,
        "enterprise": None,  # Custom pricing
    }

    TIER_LIMITS = {
        "basic": 1000,
        "pro": 5000,
        "enterprise": 10000,  # Default for enterprise
    }

    OVERAGE_RATES = {
        "basic": 0.10,
        "pro": 0.05,
        "enterprise": 0.03,
    }

    async def calculate_monthly_bill(
        self,
        session: AsyncSession,
        organization_id: str,
        month: date,
    ) -> dict:
        """
        Calculate billing amount for a specific month.

        Args:
            session: Database session
            organization_id: Organization UUID
            month: Month to calculate for

        Returns:
            Billing details dictionary
        """
        # Get organization
        stmt = select(Organization).where(Organization.id == organization_id)
        result = await session.execute(stmt)
        org = result.scalar_one()

        # Get usage
        stmt = select(ConversationUsage).where(
            ConversationUsage.organization_id == organization_id,
            ConversationUsage.month == month,
        )
        result = await session.execute(stmt)
        usage = result.scalar_one_or_none()

        conversations = usage.conversation_count if usage else 0
        tier = org.tier
        base_price = self.TIER_PRICES.get(tier, 0)
        included = org.monthly_conversation_limit

        if conversations <= included:
            total = base_price
            overage_count = 0
            overage_cost = 0.0
        else:
            overage_count = conversations - included
            overage_cost = float(overage_count * org.overage_rate)
            total = base_price + overage_cost if base_price else overage_cost

        return {
            "organization_id": organization_id,
            "month": str(month),
            "tier": tier,
            "base_price": base_price,
            "conversations_included": included,
            "conversations_used": conversations,
            "overage_conversations": overage_count,
            "overage_rate": float(org.overage_rate),
            "overage_cost": overage_cost,
            "total_amount": total,
        }
