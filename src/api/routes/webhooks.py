"""Webhook endpoints for external integrations."""

import base64
import hashlib
import hmac
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from src.config import settings

logger = structlog.get_logger()
router = APIRouter()


# === Shopify Webhooks ===


class ShopifyOrderWebhook(BaseModel):
    """Shopify order webhook payload (simplified)."""

    id: int
    order_number: int
    email: str
    financial_status: str
    fulfillment_status: str | None = None


def verify_shopify_webhook(
    data: bytes,
    hmac_header: str,
    secret: str,
) -> bool:
    """Verify Shopify webhook signature."""
    computed = base64.b64encode(hmac.new(secret.encode(), data, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(computed, hmac_header)


@router.post("/webhooks/shopify/orders/create")
async def shopify_order_created(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None),
    x_shopify_topic: str = Header(None),
):
    """Handle Shopify order created webhook."""
    body = await request.body()

    # Verify signature in production
    if settings.is_production and settings.shopify_api_secret:
        if not verify_shopify_webhook(body, x_shopify_hmac_sha256, settings.shopify_api_secret):
            raise HTTPException(401, "Invalid webhook signature")

    # Parse payload
    import json

    order = json.loads(body)

    logger.info(
        "shopify_order_created",
        order_id=order.get("id"),
        order_number=order.get("order_number"),
    )

    # TODO: Cache order data, trigger notifications

    return {"received": True, "order_id": order.get("id")}


@router.post("/webhooks/shopify/orders/updated")
async def shopify_order_updated(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None),
):
    """Handle Shopify order updated webhook."""
    body = await request.body()

    if settings.is_production and settings.shopify_api_secret:
        if not verify_shopify_webhook(body, x_shopify_hmac_sha256, settings.shopify_api_secret):
            raise HTTPException(401, "Invalid webhook signature")

    import json

    order = json.loads(body)

    logger.info(
        "shopify_order_updated",
        order_id=order.get("id"),
        status=order.get("fulfillment_status"),
    )

    # TODO: Update cached order, notify active conversations

    return {"received": True, "action": "cache_updated"}


@router.post("/webhooks/shopify/orders/fulfilled")
async def shopify_order_fulfilled(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None),
):
    """Handle Shopify order fulfilled webhook."""
    body = await request.body()

    if settings.is_production and settings.shopify_api_secret:
        if not verify_shopify_webhook(body, x_shopify_hmac_sha256, settings.shopify_api_secret):
            raise HTTPException(401, "Invalid webhook signature")

    import json

    order = json.loads(body)

    logger.info(
        "shopify_order_fulfilled",
        order_id=order.get("id"),
        tracking=order.get("fulfillments", [{}])[0].get("tracking_number"),
    )

    # TODO: Proactive notification to customer

    return {"received": True, "action": "notification_queued"}


# === Gorgias Webhooks ===


class GorgiasWebhookEvent(BaseModel):
    """Gorgias webhook event."""

    event: str
    ticket_id: int
    message: dict[str, Any] | None = None


@router.post("/webhooks/gorgias")
async def gorgias_webhook(
    request: Request,
    x_gorgias_signature: str = Header(None),
):
    """Handle Gorgias webhook events."""
    body = await request.body()

    # TODO: Verify signature in production

    import json

    event = json.loads(body)

    event_type = event.get("event")
    ticket_id = event.get("ticket_id")

    logger.info(
        "gorgias_webhook_received",
        event=event_type,
        ticket_id=ticket_id,
    )

    if event_type == "ticket.message.created":
        message = event.get("message", {})
        sender_type = message.get("sender", {}).get("type")

        if sender_type == "agent":
            # Human agent responded - pause AI on this conversation
            logger.info(
                "human_agent_response",
                ticket_id=ticket_id,
            )
            # TODO: Update conversation status to "human_handling"

        elif sender_type == "customer":
            # Customer replied in Gorgias
            logger.info(
                "customer_response_in_gorgias",
                ticket_id=ticket_id,
            )
            # TODO: Route to AI if configured for auto-response

    return {"received": True, "event": event_type}
