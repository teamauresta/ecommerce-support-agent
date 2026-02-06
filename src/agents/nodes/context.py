"""Context fetching node - retrieves order and customer data."""

from typing import Any

from src.agents.state import ConversationState, OrderData
from src.config import settings
from src.database import get_session_context
from src.integrations.shopify import ShopifyClient, get_shopify_client
from src.integrations.knowledge_base import get_kb_client
import structlog

logger = structlog.get_logger()


async def fetch_context(state: ConversationState) -> dict[str, Any]:
    """
    Fetch relevant context based on extracted entities.
    
    This node retrieves order details, customer history, and any
    other context needed for the specialist agents.
    """
    updates: dict[str, Any] = {
        "current_agent": "context_fetcher",
    }
    
    store_id = state["store_id"]
    order_id = state.get("order_id") or state.get("order_number")
    email = state.get("email")
    
    # Try to get Shopify client
    try:
        shopify = await get_shopify_client(store_id)
    except Exception as e:
        logger.warning("shopify_client_unavailable", store_id=store_id, error=str(e))
        shopify = None
    
    # Fetch order if we have an order ID
    if order_id and shopify:
        try:
            order = await shopify.get_order_by_number(order_id)
            
            if order:
                # Transform to our OrderData format
                order_data: OrderData = {
                    "id": str(order.get("id", "")),
                    "order_number": str(order.get("order_number", order_id)),
                    "email": order.get("email", ""),
                    "customer_name": order.get("shipping_address", {}).get("name", "Customer"),
                    "status": _determine_order_status(order),
                    "fulfillment_status": order.get("fulfillment_status"),
                    "financial_status": order.get("financial_status", ""),
                    "total_price": float(order.get("total_price", 0)),
                    "currency": order.get("currency", "USD"),
                    "line_items": [
                        {
                            "title": item.get("title", ""),
                            "quantity": item.get("quantity", 1),
                            "price": item.get("price", "0"),
                        }
                        for item in order.get("line_items", [])
                    ],
                    "shipping_address": order.get("shipping_address", {}),
                    "tracking_numbers": _extract_tracking(order),
                    "tracking_urls": _extract_tracking_urls(order),
                    "carrier": _extract_carrier(order),
                    "created_at": order.get("created_at", ""),
                    "updated_at": order.get("updated_at", ""),
                }
                
                updates["order_data"] = order_data
                
                logger.info(
                    "order_fetched",
                    conversation_id=state["conversation_id"],
                    order_number=order_id,
                    status=order_data["status"],
                )
            else:
                logger.info(
                    "order_not_found",
                    conversation_id=state["conversation_id"],
                    order_number=order_id,
                )
                updates["agent_reasoning"] = f"Order #{order_id} not found in system"
                
        except Exception as e:
            logger.error(
                "order_fetch_error",
                order_id=order_id,
                error=str(e),
            )
            updates["error"] = f"Failed to fetch order: {e}"
    
    # Fetch customer data if we have email
    if email and shopify:
        try:
            customer = await shopify.get_customer_by_email(email)
            if customer:
                updates["customer_data"] = {
                    "id": str(customer.get("id", "")),
                    "email": customer.get("email", email),
                    "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
                    "total_orders": customer.get("orders_count", 0),
                    "total_spent": float(customer.get("total_spent", 0)),
                    "tags": customer.get("tags", "").split(", ") if customer.get("tags") else [],
                    "is_vip": "vip" in customer.get("tags", "").lower(),
                }
        except Exception as e:
            logger.warning("customer_fetch_error", email=email, error=str(e))

    # Search knowledge base for relevant content
    try:
        kb_client = get_kb_client()
        async with get_session_context() as session:
            kb_results = await kb_client.search(
                session=session,
                store_id=store_id,
                query=state["current_message"],
                top_k=settings.kb_retrieval_top_k,
                threshold=settings.kb_similarity_threshold,
            )
            if kb_results:
                updates["policy_context"] = [
                    f"[{r['page_title']}]({r['source_url']})\n{r['content']}"
                    for r in kb_results
                ]
                logger.info(
                    "kb_search_complete",
                    store_id=store_id,
                    results=len(kb_results),
                )
    except Exception as e:
        logger.warning("kb_search_error", store_id=store_id, error=str(e))

    return updates


def _determine_order_status(order: dict) -> str:
    """Determine human-readable order status."""
    if order.get("cancelled_at"):
        return "cancelled"
    
    fulfillment = order.get("fulfillment_status")
    financial = order.get("financial_status")
    
    if fulfillment == "fulfilled":
        return "delivered" if _is_delivered(order) else "shipped"
    elif fulfillment == "partial":
        return "partially_shipped"
    elif financial == "paid":
        return "processing"
    elif financial == "pending":
        return "pending_payment"
    else:
        return "unknown"


def _is_delivered(order: dict) -> bool:
    """Check if order has been delivered."""
    fulfillments = order.get("fulfillments", [])
    for f in fulfillments:
        if f.get("shipment_status") == "delivered":
            return True
    return False


def _extract_tracking(order: dict) -> list[str]:
    """Extract tracking numbers from order."""
    tracking = []
    for f in order.get("fulfillments", []):
        if f.get("tracking_number"):
            tracking.append(f["tracking_number"])
    return tracking


def _extract_tracking_urls(order: dict) -> list[str]:
    """Extract tracking URLs from order."""
    urls = []
    for f in order.get("fulfillments", []):
        if f.get("tracking_url"):
            urls.append(f["tracking_url"])
    return urls


def _extract_carrier(order: dict) -> str | None:
    """Extract shipping carrier from order."""
    fulfillments = order.get("fulfillments", [])
    if fulfillments:
        return fulfillments[0].get("tracking_company")
    return None
