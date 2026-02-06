# Quick Start Card

## 🎯 What We're Building

An AI agent that handles 80%+ of e-commerce customer support automatically.

**Core Capabilities:**
- Order status inquiries (WISMO)
- Returns & refunds processing
- Address changes
- Product questions
- Smart escalation to humans

---

## 📅 8-Week Timeline

```
Week 1-2: MVP           → WISMO agent + Shopify + basic chat
Week 3-4: Expand        → Returns, refunds, escalation, sentiment
Week 5-6: Polish        → Helpdesk integration, monitoring, admin UI
Week 7-8: Launch        → Beta customers, iteration, documentation
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| Agent Framework | LangGraph 0.5+ |
| LLM | GPT-4o / GPT-4o-mini |
| API | FastAPI |
| Database | PostgreSQL + pgvector |
| Cache | Redis |
| Observability | LangSmith |

---

## 📊 Success Metrics

| Metric | Target |
|--------|--------|
| Automation Rate | >80% |
| First Response | <30s |
| Resolution Rate | >75% |
| CSAT | >4.2/5 |
| Escalation Rate | <15% |

---

## 🏃 Quick Start Commands

```bash
# Setup
git clone <repo>
cd ecommerce-support-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add your keys

# Run locally
docker-compose up -d  # Start Postgres + Redis
python -m src.api.main

# Test
pytest tests/unit
pytest tests/component  # Needs OPENAI_API_KEY
```

---

## 📁 Project Structure

```
ecommerce-support-agent/
├── docs/               # This documentation
├── src/
│   ├── agents/         # LangGraph agents (WISMO, returns, etc.)
│   ├── tools/          # Shopify, shipping, payment tools
│   ├── integrations/   # External service clients
│   ├── api/            # FastAPI routes
│   └── models/         # Database models
├── tests/
├── config/
└── scripts/
```

---

## 🔑 Key Files to Understand

1. `src/agents/orchestrator.py` — Main LangGraph workflow
2. `src/agents/wismo.py` — Order status agent
3. `src/integrations/shopify.py` — Shopify API client
4. `src/api/routes/conversations.py` — API endpoints
5. `src/prompts/` — LLM prompt templates

---

## 📚 Documentation Map

| Need to... | Read... |
|------------|---------|
| Understand the project | `docs/00-PROJECT-OVERVIEW.md` |
| See the architecture | `docs/01-ARCHITECTURE.md` |
| Know what to build when | `docs/02-WEEK-BY-WEEK-PLAN.md` |
| Implement agents | `docs/03-TECHNICAL-SPEC.md` |
| Build the API | `docs/04-API-SPECIFICATION.md` |
| Integrate Shopify/Gorgias | `docs/05-INTEGRATIONS.md` |
| Write tests | `docs/06-TESTING-STRATEGY.md` |
| Deploy to production | `docs/07-DEPLOYMENT-GUIDE.md` |
| Set up monitoring | `docs/08-METRICS-AND-MONITORING.md` |

---

## 🎯 Week 1 Checklist

- [ ] Set up repository and dev environment
- [ ] Configure database schemas
- [ ] Build basic LangGraph structure
- [ ] Implement intent classification
- [ ] Create Shopify order lookup
- [ ] Build WISMO agent
- [ ] Write first integration test

---

## 💡 Key Decisions Made

1. **Multi-agent over monolithic** — Separate agents for each domain
2. **LangGraph for orchestration** — State graphs for complex flows
3. **Shopify-first** — Most common platform for target market
4. **Gorgias for helpdesk** — E-commerce focused, good API
5. **GPT-4o-mini for speed** — GPT-4o for complex reasoning

---

## ⚠️ Watch Out For

- **Hallucinated policies** — Always RAG from verified knowledge base
- **Over-refunding** — Set limits, require approval for high amounts
- **Integration failures** — Graceful degradation, not hard failures
- **Prompt leakage** — Don't expose system prompts to customers

---

## 🆘 Need Help?

1. Check the relevant doc in `/docs`
2. Search LangGraph docs: https://langchain-ai.github.io/langgraph/
3. LangSmith for debugging: https://smith.langchain.com/
