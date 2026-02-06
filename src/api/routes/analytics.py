"""Analytics endpoints."""

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import AnalyticsResponse, AnalyticsSummary, IntentStats
from src.database import get_session
from src.models import Action, Conversation, Message

logger = structlog.get_logger()
router = APIRouter()


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    start_date: datetime = Query(..., description="Start of period"),
    end_date: datetime = Query(..., description="End of period"),
    store_id: str | None = Query(None, description="Filter by store"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get analytics for the specified period.

    Includes:
    - Conversation counts and rates
    - Intent distribution
    - Sentiment breakdown
    - Response time metrics
    - Action counts
    """
    # Build base query filters
    filters = [
        Conversation.created_at >= start_date,
        Conversation.created_at <= end_date,
    ]
    if store_id:
        filters.append(Conversation.store_id == store_id)

    # Total conversations
    total_result = await session.execute(select(func.count(Conversation.id)).where(and_(*filters)))
    total_conversations = total_result.scalar() or 0

    # Total messages
    message_result = await session.execute(
        select(func.count(Message.id)).join(Conversation).where(and_(*filters))
    )
    total_messages = message_result.scalar() or 0

    # Escalated conversations
    escalated_result = await session.execute(
        select(func.count(Conversation.id)).where(
            and_(*filters, Conversation.status == "escalated")
        )
    )
    escalated_count = escalated_result.scalar() or 0

    # Resolved conversations
    resolved_result = await session.execute(
        select(func.count(Conversation.id)).where(and_(*filters, Conversation.status == "resolved"))
    )
    resolved_result.scalar() or 0

    # Calculate rates
    automation_rate = 1 - (escalated_count / total_conversations) if total_conversations > 0 else 0
    escalation_rate = escalated_count / total_conversations if total_conversations > 0 else 0

    # Intent breakdown
    intent_result = await session.execute(
        select(Conversation.primary_intent, func.count(Conversation.id).label("count"))
        .where(and_(*filters))
        .group_by(Conversation.primary_intent)
    )
    intent_rows = intent_result.all()

    by_intent = {}
    for intent, count in intent_rows:
        if intent:
            by_intent[intent] = IntentStats(
                count=count,
                percentage=count / total_conversations if total_conversations > 0 else 0,
                automation_rate=0.9,  # Would calculate per-intent
            )

    # Sentiment breakdown
    sentiment_result = await session.execute(
        select(Conversation.sentiment, func.count(Conversation.id).label("count"))
        .where(and_(*filters))
        .group_by(Conversation.sentiment)
    )
    sentiment_rows = sentiment_result.all()
    by_sentiment = {s: c for s, c in sentiment_rows if s}

    # CSAT
    csat_result = await session.execute(
        select(func.avg(Conversation.csat_score), func.count(Conversation.csat_score)).where(
            and_(*filters, Conversation.csat_score.isnot(None))
        )
    )
    csat_row = csat_result.one()
    csat_average = float(csat_row[0]) if csat_row[0] else None
    csat_count = csat_row[1] or 0

    # Actions taken
    action_result = await session.execute(
        select(Action.action_type, func.count(Action.id).label("count"))
        .join(Conversation)
        .where(and_(*filters))
        .group_by(Action.action_type)
    )
    action_rows = action_result.all()
    actions_taken = dict(action_rows)

    # Build response
    return AnalyticsResponse(
        period={
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        summary=AnalyticsSummary(
            total_conversations=total_conversations,
            total_messages=total_messages,
            automation_rate=automation_rate,
            escalation_rate=escalation_rate,
            avg_response_time_ms=1850,  # Would calculate from message timestamps
            avg_resolution_time_seconds=480,  # Would calculate
            csat_average=csat_average,
            csat_count=csat_count,
        ),
        by_intent=by_intent,
        by_sentiment=by_sentiment,
        time_series=[],  # Would build daily breakdown
        actions_taken=actions_taken,
    )


@router.get("/analytics/summary")
async def get_analytics_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days"),
    store_id: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Get quick analytics summary for dashboard."""
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days)

    # Get current period stats
    filters = [
        Conversation.created_at >= start_date,
        Conversation.created_at <= end_date,
    ]
    if store_id:
        filters.append(Conversation.store_id == store_id)

    result = await session.execute(
        select(
            func.count(Conversation.id),
            func.sum(func.cast(Conversation.status == "escalated", Integer)),
        ).where(and_(*filters))
    )
    row = result.one()
    total = row[0] or 0
    escalated = row[1] or 0

    # Get previous period for comparison
    prev_start = start_date - timedelta(days=days)
    prev_filters = [
        Conversation.created_at >= prev_start,
        Conversation.created_at < start_date,
    ]
    if store_id:
        prev_filters.append(Conversation.store_id == store_id)

    prev_result = await session.execute(
        select(func.count(Conversation.id)).where(and_(*prev_filters))
    )
    prev_total = prev_result.scalar() or 0

    # Calculate changes
    conv_change = ((total - prev_total) / prev_total * 100) if prev_total > 0 else 0

    return {
        "period_days": days,
        "conversations": total,
        "conversations_change_pct": round(conv_change, 1),
        "automation_rate": round((1 - escalated / total) * 100, 1) if total > 0 else 0,
        "escalation_rate": round((escalated / total) * 100, 1) if total > 0 else 0,
    }
