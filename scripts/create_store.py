#!/usr/bin/env python3
"""Create a new store in the system."""

import argparse
import asyncio
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, ".")

from src.config import settings
from src.models.store import Store


async def create_store(
    name: str,
    domain: str,
    contact_email: str,
) -> dict:
    """Create a new store with API credentials."""
    
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession)
    
    async with async_session() as session:
        # Generate IDs and keys
        store_id = f"store_{uuid.uuid4().hex[:12]}"
        api_key = f"sk_live_{secrets.token_urlsafe(32)}"
        widget_id = f"wgt_{uuid.uuid4().hex[:12]}"
        
        # Create store
        store = Store(
            id=store_id,
            name=name,
            domain=domain,
            settings={
                "contact_email": contact_email,
                "api_key_hash": api_key,  # In prod, hash this
                "widget_id": widget_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            is_active=False,  # Activate after setup complete
        )
        
        session.add(store)
        await session.commit()
        
        return {
            "store_id": store_id,
            "api_key": api_key,
            "widget_id": widget_id,
        }


def main():
    parser = argparse.ArgumentParser(description="Create a new store")
    parser.add_argument("--name", required=True, help="Store name")
    parser.add_argument("--domain", required=True, help="Shopify domain")
    parser.add_argument("--contact-email", required=True, help="Contact email")
    
    args = parser.parse_args()
    
    result = asyncio.run(create_store(
        name=args.name,
        domain=args.domain,
        contact_email=args.contact_email,
    ))
    
    print(f"\n✅ Store created successfully!\n")
    print(f"Store ID:   {result['store_id']}")
    print(f"API Key:    {result['api_key']}")
    print(f"Widget ID:  {result['widget_id']}")
    print(f"\n⚠️  Save the API key - it won't be shown again!\n")


if __name__ == "__main__":
    main()
