# Testing Strategy

## Overview

Testing an AI agent system requires multiple layers of validation, from unit tests to production monitoring.

```
┌─────────────────────────────────────────────────────────────────┐
│                      TESTING PYRAMID                             │
├─────────────────────────────────────────────────────────────────┤
│                    Production Monitoring                         │
│                  ┌─────────────────────┐                        │
│                  │   A/B Testing       │                        │
│                  │   Shadow Mode       │                        │
│               ┌──┴─────────────────────┴──┐                     │
│               │   End-to-End Tests        │                     │
│               │   Conversation Scenarios   │                     │
│            ┌──┴───────────────────────────┴──┐                  │
│            │   Integration Tests              │                  │
│            │   API, Shopify, Gorgias          │                  │
│         ┌──┴─────────────────────────────────┴──┐               │
│         │   Component Tests                      │               │
│         │   Agents, Tools, Prompts               │               │
│      ┌──┴───────────────────────────────────────┴──┐            │
│      │   Unit Tests                                 │            │
│      │   Functions, Utils, Models                   │            │
└──────┴─────────────────────────────────────────────┴────────────┘
```

---

## Test Categories

### 1. Unit Tests

Test individual functions and utilities in isolation.

```python
# tests/unit/test_utils.py
import pytest
from src.utils.order_parser import extract_order_number

class TestOrderParser:
    def test_extract_order_number_with_hash(self):
        assert extract_order_number("Where is order #1234?") == "1234"
    
    def test_extract_order_number_without_hash(self):
        assert extract_order_number("Order 1234 status") == "1234"
    
    def test_extract_order_number_in_sentence(self):
        assert extract_order_number("I placed order #5678 last week") == "5678"
    
    def test_extract_order_number_none(self):
        assert extract_order_number("Where is my package?") is None
    
    def test_extract_order_number_multiple(self):
        # Returns first match
        assert extract_order_number("Orders #1234 and #5678") == "1234"


# tests/unit/test_sentiment.py
from src.utils.sentiment import calculate_frustration_score

class TestSentiment:
    def test_high_frustration_caps(self):
        text = "THIS IS RIDICULOUS! I WANT MY MONEY BACK!"
        score = calculate_frustration_score(text)
        assert score > 0.7
    
    def test_low_frustration_polite(self):
        text = "Hi, could you please help me track my order?"
        score = calculate_frustration_score(text)
        assert score < 0.3
    
    def test_medium_frustration(self):
        text = "I've been waiting for a week. Not happy."
        score = calculate_frustration_score(text)
        assert 0.3 <= score <= 0.7
```

### 2. Component Tests

Test individual agents and tools with mocked dependencies.

```python
# tests/component/test_wismo_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.wismo import WISMOAgent
from src.state import ConversationState

class TestWISMOAgent:
    @pytest.fixture
    def mock_shopify(self):
        mock = AsyncMock()
        mock.get_order_by_number.return_value = {
            "id": 12345,
            "order_number": 1234,
            "email": "customer@example.com",
            "fulfillment_status": "fulfilled",
            "financial_status": "paid",
            "fulfillments": [{
                "tracking_number": "1Z999AA10123456784",
                "tracking_company": "UPS",
                "tracking_url": "https://ups.com/track/1Z999AA10123456784"
            }],
            "line_items": [{"title": "Blue T-Shirt", "quantity": 1}]
        }
        return mock
    
    @pytest.fixture
    def mock_tracking(self):
        mock = AsyncMock()
        mock.get_tracking.return_value = {
            "status": "in_transit",
            "estimated_delivery": "2026-02-08",
            "last_update": "Package departed facility"
        }
        return mock
    
    @pytest.fixture
    def agent(self, mock_shopify, mock_tracking):
        return WISMOAgent(
            shopify=mock_shopify,
            tracking=mock_tracking,
            llm=MagicMock()
        )
    
    @pytest.fixture
    def base_state(self):
        return ConversationState(
            conversation_id="conv_123",
            store_id="store_456",
            messages=[],
            current_intent="order_status",
            sentiment="neutral",
            priority="medium",
            confidence_score=0.9
        )
    
    async def test_handle_shipped_order(self, agent, base_state):
        state = {**base_state, "order_id": "1234"}
        
        result = await agent.handle(state)
        
        assert result["order_data"] is not None
        assert "1Z999AA10123456784" in str(result["agent_reasoning"])
        agent.shopify.get_order_by_number.assert_called_once_with("1234")
    
    async def test_handle_order_not_found(self, agent, base_state, mock_shopify):
        mock_shopify.get_order_by_number.return_value = None
        state = {**base_state, "order_id": "9999"}
        
        result = await agent.handle(state)
        
        assert result["order_data"] is None
        assert "not found" in result["agent_reasoning"].lower()
    
    async def test_handle_unfulfilled_order(self, agent, base_state, mock_shopify):
        mock_shopify.get_order_by_number.return_value = {
            "id": 12345,
            "order_number": 1234,
            "fulfillment_status": None,
            "financial_status": "paid",
            "fulfillments": [],
            "line_items": [{"title": "Blue T-Shirt"}]
        }
        state = {**base_state, "order_id": "1234"}
        
        result = await agent.handle(state)
        
        assert "processing" in result["agent_reasoning"].lower()


# tests/component/test_refund_agent.py
class TestRefundAgent:
    @pytest.fixture
    def mock_policy(self):
        return {
            "auto_refund_limit": 50.00,
            "refund_window_days": 30,
            "require_return_for_refund": True
        }
    
    async def test_auto_approve_under_limit(self, agent, base_state, mock_policy):
        state = {
            **base_state,
            "order_data": {"total_price": 35.00, "created_at": "2026-02-01"},
            "policy_context": mock_policy
        }
        
        result = await agent.handle(state)
        
        assert result["suggested_actions"][0]["type"] == "refund"
        assert result["suggested_actions"][0]["auto_approve"] is True
    
    async def test_escalate_over_limit(self, agent, base_state, mock_policy):
        state = {
            **base_state,
            "order_data": {"total_price": 150.00, "created_at": "2026-02-01"},
            "policy_context": mock_policy
        }
        
        result = await agent.handle(state)
        
        assert result["requires_escalation"] is True
        assert "amount exceeds limit" in result["escalation_reason"]
```

### 3. Prompt Tests

Test LLM prompts with deterministic evaluation.

```python
# tests/component/test_prompts.py
import pytest
from langsmith import unit
from src.prompts import INTENT_CLASSIFICATION_PROMPT
from src.agents.classifier import classify_intent

class TestIntentClassification:
    @pytest.mark.parametrize("message,expected_intent", [
        ("Where is my order #1234?", "order_status"),
        ("I want to return the blue shirt", "return_request"),
        ("Can I get a refund?", "refund_request"),
        ("Change my shipping address", "address_change"),
        ("Cancel my order please", "cancel_order"),
        ("What size should I get?", "product_question"),
        ("How long does shipping take?", "shipping_question"),
        ("This is terrible service!", "complaint"),
        ("What are your store hours?", "general_inquiry"),
    ])
    async def test_intent_classification(self, message, expected_intent):
        result = await classify_intent(message)
        assert result["intent"] == expected_intent
    
    async def test_classification_confidence(self):
        # Clear intent should have high confidence
        result = await classify_intent("Where is order #1234?")
        assert result["confidence"] > 0.9
        
        # Ambiguous should have lower confidence
        result = await classify_intent("Help")
        assert result["confidence"] < 0.7
    
    async def test_entity_extraction(self):
        result = await classify_intent("Where is order #1234 for john@example.com?")
        assert result["extracted_entities"]["order_id"] == "1234"
        assert result["extracted_entities"]["email"] == "john@example.com"


# Using LangSmith for prompt testing
@unit
def test_wismo_response_quality():
    """Test WISMO response contains required elements"""
    from src.agents.wismo import generate_wismo_response
    
    context = {
        "order_number": "1234",
        "status": "shipped",
        "tracking_number": "1Z999AA10123456784",
        "carrier": "UPS",
        "estimated_delivery": "February 8, 2026",
        "sentiment": "neutral"
    }
    
    response = generate_wismo_response(context)
    
    # Assert required elements
    assert "1234" in response  # Order number
    assert "1Z999AA10123456784" in response  # Tracking
    assert "February 8" in response  # Delivery estimate
    assert len(response) < 500  # Not too long
```

### 4. Integration Tests

Test real integrations with sandbox/test accounts.

```python
# tests/integration/test_shopify.py
import pytest
import os

@pytest.mark.integration
class TestShopifyIntegration:
    @pytest.fixture
    def shopify(self):
        from src.integrations.shopify import ShopifyClient
        return ShopifyClient(
            shop=os.environ["TEST_SHOPIFY_SHOP"],
            access_token=os.environ["TEST_SHOPIFY_TOKEN"]
        )
    
    async def test_get_order(self, shopify):
        # Use a known test order
        order = await shopify.get_order(os.environ["TEST_ORDER_ID"])
        
        assert order is not None
        assert "id" in order
        assert "line_items" in order
    
    async def test_search_orders(self, shopify):
        orders = await shopify.search_orders(
            email=os.environ["TEST_CUSTOMER_EMAIL"]
        )
        
        assert isinstance(orders, list)
    
    async def test_add_order_note(self, shopify):
        note = f"Test note from integration test - {datetime.now()}"
        order = await shopify.add_order_note(
            os.environ["TEST_ORDER_ID"],
            note
        )
        
        assert note in order.get("note", "")


# tests/integration/test_api.py
@pytest.mark.integration
class TestAPIIntegration:
    @pytest.fixture
    def client(self):
        from httpx import AsyncClient
        return AsyncClient(
            base_url=os.environ["TEST_API_URL"],
            headers={"Authorization": f"Bearer {os.environ['TEST_API_KEY']}"}
        )
    
    async def test_create_conversation(self, client):
        response = await client.post("/v1/conversations", json={
            "channel": "api",
            "initial_message": "Where is order #1234?"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        assert "response" in data
    
    async def test_send_message(self, client):
        # Create conversation
        conv = await client.post("/v1/conversations", json={
            "channel": "api",
            "initial_message": "Hi"
        })
        conv_id = conv.json()["conversation_id"]
        
        # Send follow-up
        response = await client.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"content": "Where is order #1234?"}
        )
        
        assert response.status_code == 200
```

### 5. End-to-End Scenario Tests

Test complete conversation flows.

```python
# tests/e2e/test_scenarios.py
import pytest
from src.agent import SupportAgent

class TestConversationScenarios:
    @pytest.fixture
    def agent(self):
        return SupportAgent(config=TEST_CONFIG)
    
    async def test_wismo_happy_path(self, agent):
        """Customer asks about shipped order, gets tracking"""
        # Setup: Order exists and is shipped
        conv = await agent.start_conversation(
            store_id="test_store",
            customer_email="customer@example.com"
        )
        
        # Customer asks
        response1 = await agent.send_message(
            conv.id, 
            "Where is my order #1234?"
        )
        
        assert response1.intent == "order_status"
        assert "tracking" in response1.content.lower()
        assert "1Z999" in response1.content  # Tracking number
        
        # Customer satisfied
        response2 = await agent.send_message(conv.id, "Thanks!")
        
        assert response2.requires_escalation is False
    
    async def test_frustrated_customer_escalation(self, agent):
        """Frustrated customer about delayed order gets escalated"""
        conv = await agent.start_conversation(
            store_id="test_store",
            customer_email="customer@example.com"
        )
        
        # Initial complaint
        response1 = await agent.send_message(
            conv.id,
            "WHERE IS MY ORDER #1234?! This is RIDICULOUS!"
        )
        
        assert response1.sentiment == "frustrated"
        assert "sorry" in response1.content.lower()  # Empathetic
        
        # Continued frustration
        response2 = await agent.send_message(
            conv.id,
            "I want to speak to a human! This is the third time!"
        )
        
        assert response2.requires_escalation is True
        assert "team member" in response2.content.lower()
    
    async def test_return_flow(self, agent):
        """Customer initiates return, gets label"""
        conv = await agent.start_conversation(
            store_id="test_store",
            customer_email="customer@example.com"
        )
        
        # Return request
        response1 = await agent.send_message(
            conv.id,
            "I want to return the blue shirt from order #1234"
        )
        
        assert response1.intent == "return_request"
        
        # Confirm return
        response2 = await agent.send_message(conv.id, "Yes, please send the label")
        
        assert "label" in response2.content.lower()
        assert any(a["type"] == "return_label_generated" for a in response2.actions)
    
    async def test_refund_within_limit(self, agent):
        """Small refund processed automatically"""
        conv = await agent.start_conversation(
            store_id="test_store",
            customer_email="customer@example.com"
        )
        
        response = await agent.send_message(
            conv.id,
            "I received a damaged item in order #1234. Can I get a refund? It was $25."
        )
        
        assert response.intent == "refund_request"
        assert any(a["type"] == "refund_processed" for a in response.actions)
        assert "refund" in response.content.lower()
        assert response.requires_escalation is False
    
    async def test_multi_intent_conversation(self, agent):
        """Handle conversation with multiple topics"""
        conv = await agent.start_conversation(
            store_id="test_store",
            customer_email="customer@example.com"
        )
        
        # Start with order status
        r1 = await agent.send_message(conv.id, "Where is order #1234?")
        assert r1.intent == "order_status"
        
        # Switch to return
        r2 = await agent.send_message(conv.id, "Actually, I want to return it")
        assert r2.intent == "return_request"
        
        # Ask product question
        r3 = await agent.send_message(conv.id, "What's the return window?")
        assert "30 days" in r3.content or "policy" in r3.content.lower()
```

---

## Test Data Management

### Fixtures

```python
# tests/fixtures/orders.py
SHIPPED_ORDER = {
    "id": 12345,
    "order_number": 1234,
    "email": "customer@example.com",
    "financial_status": "paid",
    "fulfillment_status": "fulfilled",
    "total_price": "49.99",
    "created_at": "2026-02-01T10:00:00Z",
    "line_items": [
        {"title": "Blue T-Shirt", "quantity": 1, "price": "29.99"},
        {"title": "Black Socks", "quantity": 2, "price": "9.99"}
    ],
    "fulfillments": [{
        "tracking_number": "1Z999AA10123456784",
        "tracking_company": "UPS",
        "tracking_url": "https://ups.com/track/1Z999AA10123456784"
    }],
    "shipping_address": {
        "name": "John Doe",
        "address1": "123 Main St",
        "city": "New York",
        "province": "NY",
        "zip": "10001",
        "country": "US"
    }
}

UNFULFILLED_ORDER = {
    **SHIPPED_ORDER,
    "fulfillment_status": None,
    "fulfillments": []
}

CANCELLED_ORDER = {
    **SHIPPED_ORDER,
    "cancelled_at": "2026-02-02T10:00:00Z",
    "cancel_reason": "customer"
}
```

### Test Database

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def test_db():
    """Create test database with fixtures"""
    engine = create_engine("postgresql://localhost/test_support_agent")
    Session = sessionmaker(bind=engine)
    
    # Create tables
    Base.metadata.create_all(engine)
    
    # Load fixtures
    session = Session()
    session.add_all([
        Store(id="test_store", name="Test Store", ...),
        # ... more fixtures
    ])
    session.commit()
    
    yield session
    
    # Cleanup
    session.close()
    Base.metadata.drop_all(engine)
```

---

## Evaluation Metrics

### Accuracy Metrics

```python
# tests/evaluation/test_accuracy.py
from src.evaluation import EvaluationDataset, Evaluator

class TestAccuracy:
    @pytest.fixture
    def eval_dataset(self):
        return EvaluationDataset.from_file("tests/data/eval_set.json")
    
    async def test_intent_accuracy(self, eval_dataset, agent):
        evaluator = Evaluator(agent)
        results = await evaluator.evaluate_intent_accuracy(eval_dataset)
        
        assert results.accuracy >= 0.90  # 90% accuracy target
        assert results.precision["order_status"] >= 0.95
    
    async def test_action_accuracy(self, eval_dataset, agent):
        """Test that correct actions are taken"""
        evaluator = Evaluator(agent)
        results = await evaluator.evaluate_actions(eval_dataset)
        
        assert results.true_positive_rate >= 0.85
        assert results.false_positive_rate <= 0.05  # Few wrong actions
```

### Response Quality

```python
# Using LangSmith evaluators
from langsmith.evaluation import evaluate

def test_response_quality():
    results = evaluate(
        lambda x: agent.generate_response(x["input"]),
        data="ecommerce-support-eval",
        evaluators=[
            "relevance",      # Is response relevant to query?
            "helpfulness",    # Does it help solve the problem?
            "coherence",      # Is it well-written?
            "custom:brand_voice"  # Matches brand tone?
        ]
    )
    
    assert results.average_score("relevance") >= 0.85
    assert results.average_score("helpfulness") >= 0.80
```

---

## CI/CD Pipeline

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Run unit tests
        run: pytest tests/unit -v --cov=src
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  component-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-test.txt
      
      - name: Run component tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: pytest tests/component -v

  integration-tests:
    runs-on: ubuntu-latest
    needs: component-tests
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-test.txt
      
      - name: Run integration tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          TEST_SHOPIFY_SHOP: ${{ secrets.TEST_SHOPIFY_SHOP }}
          TEST_SHOPIFY_TOKEN: ${{ secrets.TEST_SHOPIFY_TOKEN }}
        run: pytest tests/integration -v -m integration
```

---

## Test Coverage Requirements

| Category | Minimum Coverage |
|----------|------------------|
| Unit Tests | 80% |
| Component Tests | 70% |
| Integration Tests | Key paths covered |
| E2E Scenarios | 20+ scenarios |

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit

# With coverage
pytest --cov=src --cov-report=html

# Integration tests (requires credentials)
pytest tests/integration -m integration

# E2E scenarios
pytest tests/e2e -v

# Specific test file
pytest tests/component/test_wismo_agent.py -v
```
