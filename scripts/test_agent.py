#!/usr/bin/env python3
"""Quick test script for the agent."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents import run_agent


async def test_wismo():
    """Test WISMO query."""
    print("\n" + "="*60)
    print("🔍 Testing WISMO Agent")
    print("="*60)
    
    result = await run_agent(
        conversation_id="test_conv_1",
        store_id="test_store",
        message="Where is my order #1234?",
    )
    
    print(f"\n📝 Intent: {result.get('intent')}")
    print(f"🎭 Sentiment: {result.get('sentiment')}")
    print(f"📊 Confidence: {result.get('confidence')}")
    print(f"🚨 Escalation: {result.get('requires_escalation')}")
    print(f"\n💬 Response:\n{result.get('response')}")
    
    return result


async def test_return_request():
    """Test return request."""
    print("\n" + "="*60)
    print("↩️ Testing Returns Agent")
    print("="*60)
    
    result = await run_agent(
        conversation_id="test_conv_2",
        store_id="test_store",
        message="I want to return the blue t-shirt from order #1234",
    )
    
    print(f"\n📝 Intent: {result.get('intent')}")
    print(f"🎭 Sentiment: {result.get('sentiment')}")
    print(f"📊 Confidence: {result.get('confidence')}")
    print(f"🎬 Actions: {result.get('actions_taken')}")
    print(f"\n💬 Response:\n{result.get('response')}")
    
    return result


async def test_refund_request():
    """Test refund request."""
    print("\n" + "="*60)
    print("💰 Testing Refunds Agent")
    print("="*60)
    
    result = await run_agent(
        conversation_id="test_conv_3",
        store_id="test_store",
        message="I received a damaged item. Can I get a refund for $25?",
    )
    
    print(f"\n📝 Intent: {result.get('intent')}")
    print(f"🎭 Sentiment: {result.get('sentiment')}")
    print(f"📊 Confidence: {result.get('confidence')}")
    print(f"🎬 Actions: {result.get('actions_taken')}")
    print(f"🚨 Escalation: {result.get('requires_escalation')}")
    print(f"\n💬 Response:\n{result.get('response')}")
    
    return result


async def test_frustrated_customer():
    """Test frustrated customer handling."""
    print("\n" + "="*60)
    print("😤 Testing Frustrated Customer")
    print("="*60)
    
    result = await run_agent(
        conversation_id="test_conv_4",
        store_id="test_store",
        message="WHERE IS MY ORDER?! This is RIDICULOUS! I've been waiting for weeks!",
    )
    
    print(f"\n📝 Intent: {result.get('intent')}")
    print(f"🎭 Sentiment: {result.get('sentiment')}")
    print(f"🚨 Escalation: {result.get('requires_escalation')}")
    print(f"📋 Escalation Reason: {result.get('escalation_reason')}")
    print(f"\n💬 Response:\n{result.get('response')}")
    
    return result


async def test_human_request():
    """Test request for human agent."""
    print("\n" + "="*60)
    print("👤 Testing Human Agent Request")
    print("="*60)
    
    result = await run_agent(
        conversation_id="test_conv_5",
        store_id="test_store",
        message="I want to speak to a real person, not a bot",
    )
    
    print(f"\n📝 Intent: {result.get('intent')}")
    print(f"🚨 Escalation: {result.get('requires_escalation')}")
    print(f"📋 Escalation Reason: {result.get('escalation_reason')}")
    print(f"\n💬 Response:\n{result.get('response')}")
    
    return result


async def test_general_query():
    """Test general query."""
    print("\n" + "="*60)
    print("❓ Testing General Query")
    print("="*60)
    
    result = await run_agent(
        conversation_id="test_conv_6",
        store_id="test_store",
        message="What is your return policy?",
    )
    
    print(f"\n📝 Intent: {result.get('intent')}")
    print(f"🎭 Sentiment: {result.get('sentiment')}")
    print(f"\n💬 Response:\n{result.get('response')}")
    
    return result


async def test_conversation_flow():
    """Test multi-turn conversation."""
    print("\n" + "="*60)
    print("💬 Testing Multi-Turn Conversation")
    print("="*60)
    
    history = []
    
    # First message
    result1 = await run_agent(
        conversation_id="test_conv_7",
        store_id="test_store",
        message="Hi, I have a question about my order",
        history=history,
    )
    print(f"\n👤 User: Hi, I have a question about my order")
    print(f"🤖 Agent: {result1.get('response')}")
    
    history.append({"role": "user", "content": "Hi, I have a question about my order"})
    history.append({"role": "assistant", "content": result1.get("response", "")})
    
    # Second message
    result2 = await run_agent(
        conversation_id="test_conv_7",
        store_id="test_store",
        message="It's order #1234. When will it arrive?",
        history=history,
    )
    print(f"\n👤 User: It's order #1234. When will it arrive?")
    print(f"🤖 Agent: {result2.get('response')}")
    
    return result2


async def main():
    """Run all tests."""
    print("\n" + "🤖 E-Commerce Support Agent Test Suite".center(60))
    print("="*60)
    
    tests = [
        ("WISMO", test_wismo),
        ("Returns", test_return_request),
        ("Refunds", test_refund_request),
        ("Frustrated Customer", test_frustrated_customer),
        ("Human Request", test_human_request),
        ("General Query", test_general_query),
        ("Multi-Turn", test_conversation_flow),
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            result = await test_func()
            results[name] = "✅ Passed"
        except Exception as e:
            results[name] = f"❌ Failed: {e}"
            print(f"\n❌ Error in {name}: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    for name, status in results.items():
        print(f"  {name}: {status}")
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
