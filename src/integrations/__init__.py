"""External service integrations."""

from src.integrations.shopify import ShopifyClient, get_shopify_client
from src.integrations.gorgias import (
    GorgiasClient, 
    get_gorgias_client,
    sync_conversation_to_gorgias,
    escalate_to_gorgias,
)

__all__ = [
    "ShopifyClient", 
    "get_shopify_client",
    "GorgiasClient",
    "get_gorgias_client",
    "sync_conversation_to_gorgias",
    "escalate_to_gorgias",
]
