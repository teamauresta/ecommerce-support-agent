"""External service integrations."""

from src.integrations.gorgias import (
    GorgiasClient,
    escalate_to_gorgias,
    get_gorgias_client,
    sync_conversation_to_gorgias,
)
from src.integrations.knowledge_base import (
    KnowledgeBaseClient,
    WebScraper,
    get_kb_client,
)
from src.integrations.shopify import ShopifyClient, get_shopify_client

__all__ = [
    "ShopifyClient",
    "get_shopify_client",
    "GorgiasClient",
    "get_gorgias_client",
    "sync_conversation_to_gorgias",
    "escalate_to_gorgias",
    "KnowledgeBaseClient",
    "WebScraper",
    "get_kb_client",
]
