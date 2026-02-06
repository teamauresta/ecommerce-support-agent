# E-Commerce Support Agent

AI-powered customer support agent for e-commerce stores. Automates 80%+ of common support inquiries using LangGraph.

## Features

- 🛒 **Order Status (WISMO)** - Real-time order tracking with Shopify integration
- 📦 **Returns Processing** - Automated return eligibility checks and label generation
- 💰 **Refunds** - Policy-based auto-approval with escalation for edge cases
- 😊 **Sentiment Analysis** - Tone adaptation based on customer mood
- 🔄 **Smart Escalation** - Seamless handoff to human agents when needed
- 📊 **Analytics** - Track automation rates, response times, and more

## Quick Start

```bash
# Clone and setup
git clone https://github.com/yourcompany/ecommerce-support-agent.git
cd ecommerce-support-agent
python -m venv venv && source venv/bin/activate
make dev

# Configure
cp .env.example .env
# Edit .env with your API keys

# Start services
make docker-up
make migrate
make run
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Chat Widget │────▶│   FastAPI    │────▶│   LangGraph     │
│  (React)    │     │   API        │     │   Agent         │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
         ┌─────────────────────────────────────────┼─────────────┐
         │                                         │             │
    ┌────▼─────┐   ┌────────────┐   ┌─────────────▼─────────────┐
    │ Postgres │   │   Redis    │   │     Integrations          │
    │ + Vector │   │   Cache    │   │ Shopify · Gorgias · EasyPost│
    └──────────┘   └────────────┘   └───────────────────────────┘
```

### Agent Flow

```
Message → Classify Intent → Analyze Sentiment → Fetch Context
                                                      │
                    ┌─────────────────────────────────┼─────────────────┐
                    │              │                  │                 │
               ┌────▼────┐   ┌────▼────┐        ┌────▼────┐       ┌────▼────┐
               │  WISMO  │   │ Returns │        │ Refunds │       │ General │
               └────┬────┘   └────┬────┘        └────┬────┘       └────┬────┘
                    │              │                  │                 │
                    └─────────────────────────────────┼─────────────────┘
                                                      │
                                            Build Response → Check Escalation → End
```

## Project Structure

```
ecommerce-support-agent/
├── src/
│   ├── agents/           # LangGraph agents
│   │   ├── graph.py      # Main workflow
│   │   ├── state.py      # State definitions
│   │   ├── prompts.py    # LLM prompts
│   │   └── nodes/        # Individual agent nodes
│   ├── integrations/     # External service clients
│   │   ├── shopify.py    # Shopify API
│   │   ├── gorgias.py    # Gorgias helpdesk
│   │   └── shipping.py   # EasyPost/carriers
│   ├── api/              # FastAPI application
│   │   ├── main.py       # App entry point
│   │   ├── routes/       # API endpoints
│   │   └── middleware/   # Auth, rate limiting
│   ├── models/           # SQLAlchemy models
│   └── config.py         # Settings
├── widget/               # React chat widget
├── tests/                # Test suite
├── docs/                 # Documentation
├── alembic/              # Database migrations
└── scripts/              # Utility scripts
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `LANGCHAIN_API_KEY` | LangSmith API key | No |
| `SENTRY_DSN` | Sentry error tracking | No |

See `.env.example` for full list.

### Store Configuration

Stores are configured with:
- **Shopify credentials** - API access for orders
- **Policies** - Returns window, refund limits, etc.
- **Brand voice** - Customized agent personality
- **Knowledge base** - FAQ and product info

## API Endpoints

### Conversations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/conversations` | Start new conversation |
| `POST` | `/api/v1/conversations/{id}/messages` | Send message |
| `GET` | `/api/v1/conversations/{id}` | Get conversation |

### Webhooks

| Endpoint | Source | Purpose |
|----------|--------|---------|
| `/api/v1/webhooks/shopify/orders` | Shopify | Order updates |
| `/api/v1/webhooks/gorgias` | Gorgias | Ticket sync |

### Health

| Endpoint | Purpose |
|----------|---------|
| `/health` | Basic liveness |
| `/health/ready` | Full readiness |

## Development

```bash
# Run tests
make test

# Run with coverage
make test-cov

# Lint code
make lint

# Format code
make format

# Create migration
make migrate-new
```

## Deployment

### Railway (Recommended)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway up
```

### Docker

```bash
# Build image
make build

# Run
docker run -p 8000:8000 --env-file .env ecommerce-support-agent
```

## Monitoring

- **LangSmith** - Trace all agent runs
- **Sentry** - Error tracking
- **Grafana** - Metrics dashboard

See `docs/08-METRICS-AND-MONITORING.md` for details.

## Documentation

| Doc | Purpose |
|-----|---------|
| [Architecture](docs/01-ARCHITECTURE.md) | System design |
| [Week-by-Week](docs/02-WEEK-BY-WEEK-PLAN.md) | Development plan |
| [Technical Spec](docs/03-TECHNICAL-SPEC.md) | Implementation details |
| [API Spec](docs/04-API-SPECIFICATION.md) | API documentation |
| [Integrations](docs/05-INTEGRATIONS.md) | External services |
| [Testing](docs/06-TESTING-STRATEGY.md) | Test approach |
| [Deployment](docs/07-DEPLOYMENT-GUIDE.md) | Production setup |
| [Monitoring](docs/08-METRICS-AND-MONITORING.md) | Observability |
| [Runbook](docs/RUNBOOK.md) | Operations guide |
| [Onboarding](docs/ONBOARDING.md) | Customer setup |

## License

Private - All rights reserved.
