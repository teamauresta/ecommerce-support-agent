"""Conversation API endpoints."""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_session
from src.models import Conversation, Message, Store
from src.models.conversation import ConversationStatus, MessageRole
from src.agents import run_agent
import structlog

logger = structlog.get_logger()
router = APIRouter()


# === Request/Response Schemas ===

class CreateConversationRequest(BaseModel):
    """Request to start a new conversation."""
    channel: str = "widget"
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    initial_message: str = Field(..., min_length=1, max_length=2000)
    context: Optional[dict[str, Any]] = None


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    content: str = Field(..., min_length=1, max_length=2000)


class ConversationResponse(BaseModel):
    """Conversation response."""
    conversation_id: str
    message_id: str
    response: dict[str, Any]
    analysis: dict[str, Any]
    actions_taken: list[dict[str, Any]]
    created_at: str


class MessageResponse(BaseModel):
    """Message response."""
    message_id: str
    response: dict[str, Any]
    analysis: dict[str, Any]
    actions_taken: list[dict[str, Any]]
    requires_escalation: bool
    created_at: str


# === Endpoints ===

@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Start a new support conversation.
    
    Creates a conversation record and processes the initial message
    through the AI agent.
    """
    # For now, use a default store for development
    # In production, this would come from API key authentication
    store_id = await _get_or_create_dev_store(session)
    
    # Create conversation record
    conversation = Conversation(
        id=str(uuid4()),
        store_id=store_id,
        customer_email=request.customer_email,
        customer_name=request.customer_name,
        channel=request.channel,
        status=ConversationStatus.ACTIVE.value,
        metadata=request.context or {},
    )
    session.add(conversation)
    
    # Run the agent
    result = await run_agent(
        conversation_id=conversation.id,
        store_id=store_id,
        message=request.initial_message,
    )
    
    # Update conversation with analysis
    conversation.primary_intent = result.get("intent")
    conversation.sentiment = result.get("sentiment")
    if result.get("order_data"):
        conversation.order_id = result["order_data"].get("order_number")
    
    # Check for escalation
    if result.get("requires_escalation"):
        conversation.status = ConversationStatus.ESCALATED.value
    
    # Create message records
    user_message = Message(
        id=str(uuid4()),
        conversation_id=conversation.id,
        role=MessageRole.USER.value,
        content=request.initial_message,
        intent=result.get("intent"),
        confidence=result.get("confidence"),
    )
    session.add(user_message)
    
    assistant_message = Message(
        id=str(uuid4()),
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT.value,
        content=result.get("response", ""),
        tokens_used=result.get("tokens_used", 0),
    )
    session.add(assistant_message)
    
    await session.commit()
    
    logger.info(
        "conversation_created",
        conversation_id=conversation.id,
        intent=result.get("intent"),
    )
    
    return ConversationResponse(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        response={
            "content": result.get("response", ""),
            "type": "text",
        },
        analysis={
            "intent": result.get("intent"),
            "sentiment": result.get("sentiment"),
            "confidence": result.get("confidence"),
        },
        actions_taken=result.get("actions_taken", []),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Send a message in an existing conversation.
    
    Adds the message to the conversation history and processes it
    through the AI agent.
    """
    # Fetch conversation
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if conversation.status == ConversationStatus.RESOLVED.value:
        raise HTTPException(status_code=409, detail="Conversation is closed")
    
    # Fetch message history
    messages_result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .limit(10)
    )
    history_records = messages_result.scalars().all()
    
    history = [
        {"role": m.role, "content": m.content}
        for m in history_records
    ]
    
    # Run the agent
    agent_result = await run_agent(
        conversation_id=conversation.id,
        store_id=conversation.store_id,
        message=request.content,
        history=history,
    )
    
    # Update conversation
    if agent_result.get("intent"):
        conversation.primary_intent = agent_result["intent"]
    if agent_result.get("sentiment"):
        conversation.sentiment = agent_result["sentiment"]
    
    # Check for escalation
    if agent_result.get("requires_escalation"):
        conversation.status = ConversationStatus.ESCALATED.value
    
    # Create message records
    user_message = Message(
        id=str(uuid4()),
        conversation_id=conversation.id,
        role=MessageRole.USER.value,
        content=request.content,
        intent=agent_result.get("intent"),
        confidence=agent_result.get("confidence"),
    )
    session.add(user_message)
    
    assistant_message = Message(
        id=str(uuid4()),
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT.value,
        content=agent_result.get("response", ""),
        tokens_used=agent_result.get("tokens_used", 0),
    )
    session.add(assistant_message)
    
    await session.commit()
    
    return MessageResponse(
        message_id=assistant_message.id,
        response={
            "content": agent_result.get("response", ""),
            "type": "text",
        },
        analysis={
            "intent": agent_result.get("intent"),
            "sentiment": agent_result.get("sentiment"),
            "confidence": agent_result.get("confidence"),
        },
        actions_taken=agent_result.get("actions_taken", []),
        requires_escalation=agent_result.get("requires_escalation", False),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get conversation details and history."""
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Fetch messages
    messages_result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = messages_result.scalars().all()
    
    return {
        "id": conversation.id,
        "store_id": conversation.store_id,
        "status": conversation.status,
        "channel": conversation.channel,
        "customer": {
            "email": conversation.customer_email,
            "name": conversation.customer_name,
        },
        "primary_intent": conversation.primary_intent,
        "sentiment": conversation.sentiment,
        "priority": conversation.priority,
        "order_id": conversation.order_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


async def _get_or_create_dev_store(session: AsyncSession) -> str:
    """Get or create a development store."""
    DEV_STORE_ID = "00000000-0000-0000-0000-000000000001"
    
    result = await session.execute(
        select(Store).where(Store.id == DEV_STORE_ID)
    )
    store = result.scalar_one_or_none()
    
    if not store:
        store = Store(
            id=DEV_STORE_ID,
            name="Development Store",
            domain="dev.myshopify.com",
            platform="shopify",
            api_credentials={},
            settings={
                "auto_refund_limit": 50.0,
                "return_window_days": 30,
            },
        )
        session.add(store)
        await session.flush()
    
    return DEV_STORE_ID
