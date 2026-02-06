#!/usr/bin/env python3
"""Test a store's integration end-to-end."""

import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from src.agents.graph import run_agent
from src.integrations.shopify import ShopifyClient


async def test_store(store_id: str, verbose: bool = False) -> bool:
    """Run integration tests for a store."""
    
    print(f"\n🧪 Testing store: {store_id}\n")
    
    all_passed = True
    
    # Test 1: WISMO Query
    print("1️⃣  Testing WISMO (Order Status)...")
    try:
        result = await run_agent(
            conversation_id="test-wismo",
            store_id=store_id,
            message="Where is my order #1001?",
        )
        
        if result.get("intent") == "wismo":
            print("   ✅ WISMO intent detected correctly")
        else:
            print(f"   ❌ Expected 'wismo' intent, got: {result.get('intent')}")
            all_passed = False
            
        if result.get("response"):
            print("   ✅ Response generated")
            if verbose:
                print(f"      Response: {result['response'][:100]}...")
        else:
            print("   ❌ No response generated")
            all_passed = False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        all_passed = False
    
    # Test 2: Returns Query
    print("\n2️⃣  Testing Returns...")
    try:
        result = await run_agent(
            conversation_id="test-returns",
            store_id=store_id,
            message="I want to return the shoes I bought last week",
        )
        
        if result.get("intent") == "returns":
            print("   ✅ Returns intent detected correctly")
        else:
            print(f"   ❌ Expected 'returns' intent, got: {result.get('intent')}")
            all_passed = False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        all_passed = False
    
    # Test 3: Refunds Query
    print("\n3️⃣  Testing Refunds...")
    try:
        result = await run_agent(
            conversation_id="test-refunds",
            store_id=store_id,
            message="I need a refund for order #1002",
        )
        
        if result.get("intent") == "refunds":
            print("   ✅ Refunds intent detected correctly")
        else:
            print(f"   ❌ Expected 'refunds' intent, got: {result.get('intent')}")
            all_passed = False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        all_passed = False
    
    # Test 4: Sentiment Detection
    print("\n4️⃣  Testing Sentiment Detection...")
    try:
        result = await run_agent(
            conversation_id="test-sentiment",
            store_id=store_id,
            message="This is absolutely ridiculous! I've been waiting for 3 weeks!",
        )
        
        if result.get("sentiment") in ["frustrated", "angry", "negative"]:
            print("   ✅ Negative sentiment detected correctly")
        else:
            print(f"   ⚠️  Expected negative sentiment, got: {result.get('sentiment')}")
            # Not a hard failure
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        all_passed = False
    
    # Test 5: Escalation Trigger
    print("\n5️⃣  Testing Escalation...")
    try:
        result = await run_agent(
            conversation_id="test-escalation",
            store_id=store_id,
            message="I want to speak to a manager immediately!",
        )
        
        if result.get("requires_escalation"):
            print("   ✅ Escalation triggered correctly")
        else:
            print("   ⚠️  Escalation not triggered (may be acceptable)")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        all_passed = False
    
    # Summary
    print("\n" + "="*50)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed - review above")
    print("="*50 + "\n")
    
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Test store integration")
    parser.add_argument("--store-id", required=True, help="Store ID to test")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    success = asyncio.run(test_store(args.store_id, args.verbose))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
