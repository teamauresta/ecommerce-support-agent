# Deployment Guide

## Overview

This guide covers deploying the E-Commerce Support Agent to production environments.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────┐     ┌─────────────┐     ┌─────────────────────┐  │
│   │   CDN   │────▶│ Load Balancer│────▶│   API Servers (3+)  │  │
│   │Cloudflare│    │   (nginx)   │     │   (FastAPI/Uvicorn) │  │
│   └─────────┘     └─────────────┘     └──────────┬──────────┘  │
│                                                   │              │
│        ┌──────────────────────────────────────────┤              │
│        │                                          │              │
│   ┌────▼────┐   ┌────────────┐   ┌───────────────▼───────────┐  │
│   │  Redis  │   │ PostgreSQL │   │     External Services     │  │
│   │ Cluster │   │  Primary   │   │  (Shopify, Gorgias, etc.) │  │
│   └─────────┘   │  + Replica │   └───────────────────────────┘  │
│                 └────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Infrastructure Options

### Option 1: Railway (Recommended for Start)

Simple, fast deployment with managed services.

**Estimated Cost:** $50-150/month for initial scale

```yaml
# railway.yaml
version: "1"
services:
  api:
    image: python:3.11-slim
    build:
      dockerfile: Dockerfile
    deploy:
      numReplicas: 2
      healthcheck:
        path: /health
        interval: 30s
    envVars:
      - key: DATABASE_URL
        fromService: postgres
      - key: REDIS_URL
        fromService: redis

  postgres:
    plugin: postgresql
    
  redis:
    plugin: redis
```

### Option 2: AWS (Production Scale)

Full control, enterprise-grade infrastructure.

**Components:**
- ECS Fargate (containers)
- RDS PostgreSQL (database)
- ElastiCache Redis (caching)
- ALB (load balancer)
- CloudWatch (monitoring)
- Secrets Manager (credentials)

```hcl
# terraform/main.tf
module "ecs_cluster" {
  source = "terraform-aws-modules/ecs/aws"
  
  cluster_name = "support-agent-prod"
  
  fargate_capacity_providers = {
    FARGATE = {
      default_capacity_provider_strategy = {
        weight = 100
      }
    }
  }
}

module "rds" {
  source = "terraform-aws-modules/rds/aws"
  
  identifier = "support-agent-db"
  engine     = "postgres"
  engine_version = "15"
  instance_class = "db.t3.medium"
  
  allocated_storage = 50
  multi_az = true
  
  db_name  = "support_agent"
  username = "admin"
  port     = 5432
}
```

### Option 3: GCP (Alternative)

Similar to AWS with Cloud Run for serverless containers.

---

## Docker Configuration

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application
COPY src/ src/
COPY config/ config/

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

# Run
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose (Development)

```yaml
# docker-compose.yml
version: "3.8"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/support_agent
      - REDIS_URL=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - db
      - redis
    volumes:
      - ./src:/app/src  # Hot reload

  db:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: support_agent
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## Environment Configuration

### Environment Variables

```bash
# .env.production
# Application
APP_ENV=production
APP_DEBUG=false
APP_SECRET_KEY=<generated-secret>

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://host:6379/0
REDIS_PASSWORD=<password>

# LLM
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...
DEFAULT_MODEL=gpt-4o
FALLBACK_MODEL=gpt-4o-mini

# Integrations
SHOPIFY_API_KEY=<key>
SHOPIFY_API_SECRET=<secret>
GORGIAS_API_URL=https://domain.gorgias.com/api
EASYPOST_API_KEY=<key>
SENDGRID_API_KEY=<key>

# Observability
LANGSMITH_API_KEY=<key>
LANGSMITH_PROJECT=ecommerce-support-prod
SENTRY_DSN=https://...

# Security
CORS_ORIGINS=https://yourstore.com,https://app.yourcompany.com
RATE_LIMIT_ENABLED=true
```

### Secrets Management

```python
# src/config/secrets.py
import os
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

@lru_cache
def get_secrets():
    """Fetch secrets from AWS Secrets Manager"""
    if os.environ.get("APP_ENV") == "development":
        # Use local .env in development
        return {}
    
    client = boto3.client("secretsmanager")
    
    try:
        response = client.get_secret_value(
            SecretId="support-agent/production"
        )
        return json.loads(response["SecretString"])
    except ClientError as e:
        raise RuntimeError(f"Failed to fetch secrets: {e}")

def get_secret(key: str) -> str:
    """Get a specific secret"""
    secrets = get_secrets()
    return secrets.get(key) or os.environ.get(key)
```

---

## Database Migrations

### Using Alembic

```python
# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from src.models import Base

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

run_migrations()
```

### Migration Commands

```bash
# Create new migration
alembic revision --autogenerate -m "Add conversation metrics"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Show current version
alembic current
```

---

## CI/CD Pipeline

### GitHub Actions Deployment

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt -r requirements-test.txt
      - run: pytest tests/unit tests/component -v

  build:
    needs: test
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4
      
      - name: Log in to registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=
            type=raw,value=latest,enable={{is_default_branch}}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to staging
        run: |
          curl -X POST ${{ secrets.RAILWAY_WEBHOOK_STAGING }}
      
      - name: Run smoke tests
        run: |
          sleep 60  # Wait for deployment
          curl -f https://staging-api.yourcompany.com/health

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Deploy to production
        run: |
          curl -X POST ${{ secrets.RAILWAY_WEBHOOK_PRODUCTION }}
      
      - name: Verify deployment
        run: |
          sleep 60
          curl -f https://api.yourcompany.com/health
      
      - name: Notify Slack
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: Production deployment completed
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

---

## Scaling Configuration

### Horizontal Scaling

```yaml
# kubernetes/deployment.yaml (if using K8s)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: support-agent-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: support-agent-api
  template:
    metadata:
      labels:
        app: support-agent-api
    spec:
      containers:
        - name: api
          image: ghcr.io/yourcompany/support-agent:latest
          ports:
            - containerPort: 8000
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: support-agent-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: support-agent-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### Database Connection Pooling

```python
# src/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,          # Base connections
    max_overflow=10,       # Extra connections under load
    pool_timeout=30,       # Wait time for connection
    pool_recycle=1800,     # Recycle connections after 30 min
    pool_pre_ping=True,    # Verify connection before use
)

AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)
```

---

## Rollback Procedures

### Quick Rollback

```bash
# Railway
railway redeploy --previous

# Kubernetes
kubectl rollout undo deployment/support-agent-api

# Docker Compose
docker-compose pull  # Pull previous image
docker-compose up -d
```

### Database Rollback

```bash
# Rollback last migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade abc123

# Show migration history
alembic history
```

### Emergency Procedures

```markdown
## Emergency Runbook

### 1. High Error Rate
1. Check LangSmith traces for errors
2. Check external service status (Shopify, OpenAI)
3. If LLM issue: Switch to fallback model
4. If integration issue: Enable graceful degradation

### 2. High Latency
1. Check database connection pool usage
2. Check Redis connection
3. Check LLM response times
4. Scale up if CPU/memory constrained

### 3. Complete Outage
1. Check all health endpoints
2. Check database connectivity
3. Check Redis connectivity
4. Rollback to last known good deployment
5. Notify customers if prolonged

### Contacts
- On-call: [phone]
- Engineering lead: [phone]
- OpenAI support: [email]
- AWS support: [portal]
```

---

## Security Hardening

### Network Security

```hcl
# terraform/security.tf
resource "aws_security_group" "api" {
  name = "support-agent-api"
  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "database" {
  name = "support-agent-db"
  
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]
  }
  
  # No direct internet access
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

### SSL/TLS Configuration

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name api.yourcompany.com;
    
    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;
    ssl_protocols TLSv1.3 TLSv1.2;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    
    location / {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Monitoring Checklist

### Pre-Launch

- [ ] Health check endpoint working
- [ ] Database migrations applied
- [ ] Secrets configured
- [ ] SSL certificates valid
- [ ] Rate limiting configured
- [ ] Error tracking (Sentry) connected
- [ ] LangSmith project created
- [ ] Alerting rules configured
- [ ] Backup strategy in place
- [ ] Runbook documented

### Post-Launch

- [ ] Monitor error rates (< 1%)
- [ ] Monitor response times (P99 < 10s)
- [ ] Check database connections
- [ ] Verify webhook delivery
- [ ] Test escalation flow
- [ ] Verify billing/usage tracking
