# Metrics and Monitoring

## Overview

Comprehensive monitoring is critical for AI agent systems to ensure quality, catch issues early, and demonstrate value to customers.

```
┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY STACK                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐          │
│   │  LangSmith  │   │   Sentry    │   │  DataDog/   │          │
│   │   (LLM)     │   │  (Errors)   │   │  Prometheus │          │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘          │
│          │                 │                 │                  │
│          └─────────────────┼─────────────────┘                  │
│                            │                                     │
│                    ┌───────▼───────┐                            │
│                    │   Grafana     │                            │
│                    │  Dashboards   │                            │
│                    └───────────────┘                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Metrics

### Business Metrics

| Metric | Description | Target | Alert Threshold |
|--------|-------------|--------|-----------------|
| **Automation Rate** | % of conversations resolved without escalation | >80% | <70% |
| **Resolution Rate** | % of conversations successfully resolved | >75% | <60% |
| **CSAT Score** | Customer satisfaction (1-5) | >4.2 | <3.5 |
| **First Response Time** | Time to first AI response | <30s | >60s |
| **Resolution Time** | Time to full resolution | <5 min | >15 min |
| **Escalation Rate** | % escalated to human | <15% | >25% |

### Operational Metrics

| Metric | Description | Target | Alert Threshold |
|--------|-------------|--------|-----------------|
| **API Latency P50** | Median response time | <2s | >5s |
| **API Latency P99** | 99th percentile latency | <10s | >30s |
| **Error Rate** | % of requests with errors | <1% | >5% |
| **LLM Token Usage** | Tokens per conversation | <4000 | >8000 |
| **LLM Cost/Conversation** | Cost per conversation | <$0.10 | >$0.25 |
| **Uptime** | Service availability | 99.5% | <99% |

### Quality Metrics

| Metric | Description | Target | Alert Threshold |
|--------|-------------|--------|-----------------|
| **Intent Accuracy** | Correct intent classification | >95% | <90% |
| **Action Success Rate** | Successful tool executions | >98% | <95% |
| **Hallucination Rate** | Factually incorrect responses | <1% | >3% |
| **Sentiment Misread** | Wrong sentiment classification | <5% | >10% |

---

## LangSmith Integration

### Setup

```python
# src/observability/langsmith.py
import os
from langsmith import Client
from langsmith.run_trees import RunTree

# Auto-tracing with environment variables
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "<your-key>"
os.environ["LANGCHAIN_PROJECT"] = "ecommerce-support-prod"

# Manual run tracking
client = Client()

def create_run(
    name: str,
    run_type: str,
    inputs: dict,
    metadata: dict = None
) -> RunTree:
    """Create a new traced run"""
    return RunTree(
        name=name,
        run_type=run_type,
        inputs=inputs,
        extra={"metadata": metadata or {}}
    )
```

### Custom Metrics

```python
# src/observability/metrics.py
from langsmith import Client

client = Client()

async def log_conversation_metrics(
    conversation_id: str,
    intent: str,
    sentiment: str,
    response_time_ms: int,
    tokens_used: int,
    resolved: bool,
    escalated: bool,
    csat: int = None
):
    """Log conversation-level metrics to LangSmith"""
    client.create_feedback(
        run_id=conversation_id,
        key="intent",
        value=intent
    )
    
    client.create_feedback(
        run_id=conversation_id,
        key="sentiment",
        value=sentiment
    )
    
    client.create_feedback(
        run_id=conversation_id,
        key="response_time_ms",
        score=response_time_ms
    )
    
    client.create_feedback(
        run_id=conversation_id,
        key="tokens_used",
        score=tokens_used
    )
    
    client.create_feedback(
        run_id=conversation_id,
        key="resolved",
        score=1 if resolved else 0
    )
    
    if csat is not None:
        client.create_feedback(
            run_id=conversation_id,
            key="csat",
            score=csat
        )
```

### Evaluation Datasets

```python
# Create evaluation dataset for regression testing
def create_eval_dataset():
    dataset = client.create_dataset(
        "support-agent-eval-v1",
        description="Core scenarios for support agent evaluation"
    )
    
    # Add examples
    examples = [
        {
            "input": "Where is my order #1234?",
            "expected_intent": "order_status",
            "expected_elements": ["tracking", "delivery estimate"]
        },
        {
            "input": "I want to return this item",
            "expected_intent": "return_request",
            "expected_elements": ["return policy", "return label"]
        },
        # ... more examples
    ]
    
    for example in examples:
        client.create_example(
            inputs={"message": example["input"]},
            outputs={"intent": example["expected_intent"]},
            dataset_id=dataset.id
        )
```

---

## Prometheus Metrics

### Metrics Definition

```python
# src/observability/prometheus.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Conversation metrics
CONVERSATIONS_TOTAL = Counter(
    'conversations_total',
    'Total conversations',
    ['store_id', 'channel', 'intent']
)

CONVERSATIONS_RESOLVED = Counter(
    'conversations_resolved_total',
    'Resolved conversations',
    ['store_id', 'resolution_type']
)

CONVERSATIONS_ESCALATED = Counter(
    'conversations_escalated_total',
    'Escalated conversations',
    ['store_id', 'reason']
)

# Latency metrics
RESPONSE_LATENCY = Histogram(
    'response_latency_seconds',
    'Response time distribution',
    ['store_id', 'intent'],
    buckets=[0.5, 1, 2, 5, 10, 30, 60]
)

LLM_LATENCY = Histogram(
    'llm_latency_seconds',
    'LLM API latency',
    ['model', 'operation'],
    buckets=[0.1, 0.5, 1, 2, 5, 10]
)

# Resource metrics
LLM_TOKENS_USED = Counter(
    'llm_tokens_total',
    'Total LLM tokens used',
    ['store_id', 'model', 'type']  # type: input/output
)

ACTIVE_CONVERSATIONS = Gauge(
    'active_conversations',
    'Currently active conversations',
    ['store_id']
)

# Error metrics
ERRORS_TOTAL = Counter(
    'errors_total',
    'Total errors',
    ['store_id', 'error_type', 'component']
)

# Integration metrics
INTEGRATION_REQUESTS = Counter(
    'integration_requests_total',
    'External API requests',
    ['service', 'endpoint', 'status']
)

INTEGRATION_LATENCY = Histogram(
    'integration_latency_seconds',
    'External API latency',
    ['service', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 1, 2, 5]
)
```

### Metrics Endpoint

```python
# src/api/routes/metrics.py
from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter()

@router.get("/metrics")
async def metrics():
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

---

## Alerting Rules

### Prometheus Alerting

```yaml
# prometheus/alerts.yml
groups:
  - name: support-agent
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          sum(rate(errors_total[5m])) / sum(rate(conversations_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High error rate detected
          description: "Error rate is {{ $value | humanizePercentage }}"
      
      # Slow responses
      - alert: SlowResponses
        expr: |
          histogram_quantile(0.95, rate(response_latency_seconds_bucket[5m])) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: Slow response times
          description: "P95 latency is {{ $value }}s"
      
      # High escalation rate
      - alert: HighEscalationRate
        expr: |
          sum(rate(conversations_escalated_total[1h])) / 
          sum(rate(conversations_total[1h])) > 0.25
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: High escalation rate
          description: "Escalation rate is {{ $value | humanizePercentage }}"
      
      # LLM latency spike
      - alert: LLMLatencySpike
        expr: |
          histogram_quantile(0.99, rate(llm_latency_seconds_bucket[5m])) > 15
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: LLM latency spike
          description: "P99 LLM latency is {{ $value }}s"
      
      # Database connection issues
      - alert: DatabaseConnectionPoolExhausted
        expr: |
          pg_stat_activity_count > pg_settings_max_connections * 0.9
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: Database connection pool nearly exhausted
```

### PagerDuty/Slack Integration

```python
# src/observability/alerting.py
import httpx

async def send_alert(
    severity: str,
    title: str,
    description: str,
    context: dict = None
):
    """Send alert to configured channels"""
    
    if severity == "critical":
        # PagerDuty for critical
        await httpx.post(
            PAGERDUTY_URL,
            json={
                "routing_key": PAGERDUTY_KEY,
                "event_action": "trigger",
                "payload": {
                    "summary": title,
                    "severity": "critical",
                    "source": "support-agent",
                    "custom_details": context
                }
            }
        )
    
    # Always Slack
    await httpx.post(
        SLACK_WEBHOOK_URL,
        json={
            "text": f"*[{severity.upper()}]* {title}",
            "attachments": [{
                "color": "danger" if severity == "critical" else "warning",
                "text": description,
                "fields": [
                    {"title": k, "value": str(v), "short": True}
                    for k, v in (context or {}).items()
                ]
            }]
        }
    )
```

---

## Dashboards

### Grafana Dashboard Configuration

```json
{
  "dashboard": {
    "title": "E-Commerce Support Agent",
    "panels": [
      {
        "title": "Automation Rate",
        "type": "stat",
        "targets": [{
          "expr": "1 - (sum(rate(conversations_escalated_total[24h])) / sum(rate(conversations_total[24h])))",
          "legendFormat": "Automation Rate"
        }],
        "fieldConfig": {
          "defaults": {
            "unit": "percentunit",
            "thresholds": {
              "steps": [
                {"value": 0, "color": "red"},
                {"value": 0.7, "color": "yellow"},
                {"value": 0.8, "color": "green"}
              ]
            }
          }
        }
      },
      {
        "title": "Response Time Distribution",
        "type": "heatmap",
        "targets": [{
          "expr": "sum(rate(response_latency_seconds_bucket[5m])) by (le)",
          "format": "heatmap"
        }]
      },
      {
        "title": "Conversations by Intent",
        "type": "piechart",
        "targets": [{
          "expr": "sum(increase(conversations_total[24h])) by (intent)",
          "legendFormat": "{{intent}}"
        }]
      },
      {
        "title": "Error Rate",
        "type": "timeseries",
        "targets": [{
          "expr": "sum(rate(errors_total[5m])) / sum(rate(conversations_total[5m]))",
          "legendFormat": "Error Rate"
        }],
        "fieldConfig": {
          "defaults": {
            "unit": "percentunit"
          }
        }
      },
      {
        "title": "LLM Token Usage",
        "type": "timeseries",
        "targets": [{
          "expr": "sum(rate(llm_tokens_total[1h])) by (model)",
          "legendFormat": "{{model}}"
        }]
      },
      {
        "title": "Active Conversations",
        "type": "timeseries",
        "targets": [{
          "expr": "sum(active_conversations) by (store_id)",
          "legendFormat": "{{store_id}}"
        }]
      }
    ]
  }
}
```

### Key Dashboard Views

1. **Executive Overview**
   - Automation rate (daily/weekly/monthly)
   - Total conversations
   - Cost savings
   - CSAT trends

2. **Operations**
   - Response time percentiles
   - Error rates
   - Escalation breakdown
   - Active conversations

3. **Quality**
   - Intent accuracy
   - Sentiment distribution
   - Hallucination incidents
   - Customer feedback

4. **Costs**
   - Token usage by model
   - Cost per conversation
   - Cost by store
   - Trend projections

---

## Logging

### Structured Logging

```python
# src/observability/logging.py
import structlog
from datetime import datetime

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

# Usage
logger.info(
    "conversation_started",
    conversation_id="conv_123",
    store_id="store_456",
    channel="widget",
    customer_email="customer@example.com"
)

logger.info(
    "message_processed",
    conversation_id="conv_123",
    intent="order_status",
    confidence=0.95,
    response_time_ms=1850,
    tokens_used=320
)

logger.error(
    "integration_failed",
    conversation_id="conv_123",
    service="shopify",
    error_type="timeout",
    error_message="Request timed out after 30s"
)
```

### Log Aggregation

```yaml
# fluentd/fluent.conf
<source>
  @type forward
  port 24224
</source>

<filter support-agent.**>
  @type parser
  key_name log
  <parse>
    @type json
  </parse>
</filter>

<match support-agent.**>
  @type elasticsearch
  host elasticsearch
  port 9200
  index_name support-agent
  type_name log
</match>
```

---

## Health Checks

### Endpoints

```python
# src/api/routes/health.py
from fastapi import APIRouter, Response
from src.database import check_db_connection
from src.cache import check_redis_connection

router = APIRouter()

@router.get("/health")
async def health():
    """Basic health check"""
    return {"status": "healthy"}

@router.get("/health/ready")
async def readiness():
    """Readiness check for load balancer"""
    checks = {
        "database": await check_db_connection(),
        "redis": await check_redis_connection(),
        "llm": await check_llm_connection()
    }
    
    all_healthy = all(checks.values())
    
    return Response(
        content=json.dumps({
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks
        }),
        status_code=200 if all_healthy else 503,
        media_type="application/json"
    )

@router.get("/health/live")
async def liveness():
    """Liveness check for container orchestration"""
    return {"status": "alive"}
```

---

## Cost Tracking

### Token Usage Tracking

```python
# src/observability/costs.py
from dataclasses import dataclass
from typing import Dict

@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    model: str

# Cost per 1K tokens (approximate, update as needed)
MODEL_COSTS = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "text-embedding-3-small": {"input": 0.00002, "output": 0}
}

def calculate_cost(usage: TokenUsage) -> float:
    """Calculate cost for token usage"""
    costs = MODEL_COSTS.get(usage.model, {"input": 0.01, "output": 0.03})
    
    input_cost = (usage.input_tokens / 1000) * costs["input"]
    output_cost = (usage.output_tokens / 1000) * costs["output"]
    
    return input_cost + output_cost

async def track_conversation_cost(
    conversation_id: str,
    store_id: str,
    usages: list[TokenUsage]
):
    """Track and persist conversation costs"""
    total_cost = sum(calculate_cost(u) for u in usages)
    
    # Log to metrics
    for usage in usages:
        LLM_TOKENS_USED.labels(
            store_id=store_id,
            model=usage.model,
            type="input"
        ).inc(usage.input_tokens)
        
        LLM_TOKENS_USED.labels(
            store_id=store_id,
            model=usage.model,
            type="output"
        ).inc(usage.output_tokens)
    
    # Persist to database
    await db.save_conversation_cost(
        conversation_id=conversation_id,
        store_id=store_id,
        total_cost=total_cost,
        breakdown=[
            {
                "model": u.model,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "cost": calculate_cost(u)
            }
            for u in usages
        ]
    )
```

### Monthly Cost Report

```python
async def generate_cost_report(store_id: str, month: str) -> dict:
    """Generate monthly cost report for a store"""
    
    data = await db.get_monthly_costs(store_id, month)
    
    return {
        "store_id": store_id,
        "month": month,
        "summary": {
            "total_conversations": data["conversation_count"],
            "total_cost": data["total_cost"],
            "avg_cost_per_conversation": data["total_cost"] / data["conversation_count"],
            "total_tokens": data["total_tokens"]
        },
        "by_model": data["by_model"],
        "by_intent": data["by_intent"],
        "daily_breakdown": data["daily"],
        "comparison": {
            "vs_last_month": data["total_cost"] / data["last_month_cost"] - 1,
            "trend": "increasing" if data["total_cost"] > data["last_month_cost"] else "decreasing"
        }
    }
```

---

## Weekly Report Template

```markdown
# Weekly Support Agent Report
**Week of:** {{week_start}} - {{week_end}}
**Store:** {{store_name}}

## Key Metrics
| Metric | This Week | Last Week | Change |
|--------|-----------|-----------|--------|
| Conversations | {{conversations}} | {{last_conversations}} | {{change}}% |
| Automation Rate | {{automation_rate}}% | {{last_automation}}% | {{change}}pp |
| Avg Response Time | {{response_time}}s | {{last_response}}s | {{change}}% |
| CSAT | {{csat}}/5 | {{last_csat}}/5 | {{change}} |
| Escalation Rate | {{escalation}}% | {{last_escalation}}% | {{change}}pp |

## Intent Breakdown
{{#intents}}
- {{name}}: {{count}} ({{percentage}}%)
{{/intents}}

## Top Issues This Week
{{#issues}}
1. {{description}} - {{count}} occurrences
{{/issues}}

## Recommendations
{{#recommendations}}
- {{text}}
{{/recommendations}}

## Cost Summary
- Total LLM Cost: ${{total_cost}}
- Cost per Conversation: ${{cost_per_conv}}
- Estimated Monthly: ${{monthly_projection}}
```
