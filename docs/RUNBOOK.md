# Operations Runbook

## Quick Reference

| Issue | First Action | Escalation |
|-------|--------------|------------|
| High error rate | Check LangSmith traces | Rollback if >5% |
| High latency | Check DB connections | Scale up replicas |
| LLM errors | Switch to fallback model | Contact OpenAI |
| Database down | Check RDS status | Failover to replica |
| Complete outage | Check all health endpoints | Emergency rollback |

---

## Health Checks

### Check Service Status

```bash
# API health
curl https://api.example.com/health

# Full readiness (includes DB + Redis)
curl https://api.example.com/health/ready

# Check response times
curl -w "@curl-format.txt" -o /dev/null -s https://api.example.com/health
```

### Check Database

```bash
# Connection count
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"

# Slow queries
psql $DATABASE_URL -c "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Table sizes
psql $DATABASE_URL -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;"
```

### Check Redis

```bash
# Connection
redis-cli -u $REDIS_URL ping

# Memory usage
redis-cli -u $REDIS_URL info memory

# Keys count
redis-cli -u $REDIS_URL dbsize
```

---

## Incident Response

### 1. High Error Rate (>1%)

**Symptoms:**
- Sentry alerts firing
- LangSmith showing failed traces
- Customer complaints

**Diagnosis:**
```bash
# Check recent errors in LangSmith
# https://smith.langchain.com/project/ecommerce-support-prod

# Check API logs
railway logs --service api --limit 100

# Check error distribution
psql $DATABASE_URL -c "SELECT intent, COUNT(*) FROM messages WHERE created_at > NOW() - INTERVAL '1 hour' AND role = 'assistant' AND metadata->>'error' IS NOT NULL GROUP BY intent;"
```

**Resolution:**
1. If LLM errors: Switch to fallback model
   ```python
   # Temporary: set in environment
   DEFAULT_MODEL=gpt-4o-mini
   ```
2. If integration errors: Check Shopify/Gorgias status pages
3. If database errors: Check connection pool
4. If persistent: Rollback to last known good deployment

### 2. High Latency (P99 > 10s)

**Symptoms:**
- Slow response alerts
- Customer timeout complaints
- High queue depth

**Diagnosis:**
```bash
# Check LangSmith trace durations
# Filter by: duration > 5s

# Check database connection pool
psql $DATABASE_URL -c "SELECT state, count(*) FROM pg_stat_activity GROUP BY state;"

# Check Redis latency
redis-cli -u $REDIS_URL --latency
```

**Resolution:**
1. Scale up API replicas:
   ```bash
   railway scale api --replicas 5
   ```
2. Check for slow database queries
3. Verify Redis connection
4. Consider model downgrade for speed

### 3. LLM Provider Issues

**Symptoms:**
- OpenAI API errors
- Rate limit errors (429)
- Timeout errors

**Resolution:**
1. Check OpenAI status: https://status.openai.com/
2. Switch to fallback model:
   ```bash
   railway vars set DEFAULT_MODEL=gpt-4o-mini
   ```
3. If persistent, enable request queuing
4. Contact OpenAI support if widespread

### 4. Database Connection Issues

**Symptoms:**
- "Connection refused" errors
- Connection pool exhausted
- Slow queries

**Resolution:**
1. Check database status:
   ```bash
   # Railway
   railway status --service postgres
   
   # AWS RDS
   aws rds describe-db-instances --db-instance-identifier support-agent-db
   ```
2. Increase connection pool:
   ```bash
   railway vars set DATABASE_POOL_SIZE=30
   ```
3. Restart API to reset connections:
   ```bash
   railway redeploy --service api
   ```

### 5. Complete Outage

**Symptoms:**
- All health checks failing
- No API responses
- Customer-facing widget broken

**Resolution:**
1. Check all infrastructure:
   ```bash
   railway status
   ```
2. Check DNS:
   ```bash
   dig api.example.com
   ```
3. Emergency rollback:
   ```bash
   railway redeploy --service api --previous
   ```
4. If infrastructure issue, contact Railway support
5. Post status update to customers

---

## Deployment Procedures

### Standard Deployment

```bash
# Merge to main triggers automatic deployment
git push origin main

# Monitor deployment
railway logs --service api -f
```

### Manual Deployment

```bash
# Deploy specific commit
railway deploy --service api --commit abc123

# Deploy with environment override
railway deploy --service api --environment staging
```

### Rollback

```bash
# Immediate rollback
railway redeploy --service api --previous

# Rollback to specific deployment
railway redeploy --service api --deployment dep_abc123

# Database rollback (if needed)
alembic downgrade -1
```

### Database Migrations

```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply migration (staging first!)
DATABASE_URL=$STAGING_DB alembic upgrade head

# Apply to production
DATABASE_URL=$PROD_DB alembic upgrade head
```

---

## Scaling Procedures

### Horizontal Scaling (Replicas)

```bash
# Scale up API
railway scale api --replicas 5

# Scale down
railway scale api --replicas 2
```

### Vertical Scaling (Resources)

```bash
# Increase memory/CPU
railway vars set --service api RAILWAY_MEMORY=2048
railway vars set --service api RAILWAY_CPU=2
```

### Database Scaling

```bash
# AWS RDS - modify instance class
aws rds modify-db-instance \
  --db-instance-identifier support-agent-db \
  --db-instance-class db.t3.large \
  --apply-immediately
```

---

## Monitoring & Alerts

### Key Metrics to Watch

| Metric | Warning | Critical |
|--------|---------|----------|
| Error rate | >0.5% | >2% |
| P99 latency | >5s | >10s |
| Automation rate | <75% | <60% |
| Escalation rate | >20% | >30% |
| DB connections | >80% pool | >95% pool |

### Alert Channels

- **Slack**: #support-agent-alerts
- **PagerDuty**: On-call rotation
- **Email**: ops@example.com

### Dashboard Links

- **LangSmith**: https://smith.langchain.com/project/ecommerce-support-prod
- **Grafana**: https://grafana.example.com/d/support-agent
- **Sentry**: https://sentry.io/organizations/example/issues/?project=support-agent

---

## Security Procedures

### Rotate API Keys

```bash
# Generate new store API key
python scripts/rotate_api_key.py --store-id store-123

# Rotate OpenAI key
# 1. Generate new key in OpenAI dashboard
# 2. Update secret
railway vars set OPENAI_API_KEY=sk-new-key
# 3. Verify functionality
# 4. Revoke old key in OpenAI dashboard
```

### Security Incident Response

1. **Assess scope**: Which stores/customers affected?
2. **Contain**: Disable affected API keys
3. **Investigate**: Check access logs
4. **Remediate**: Patch vulnerability
5. **Notify**: Inform affected customers per policy

---

## Maintenance Windows

### Scheduled Maintenance

- **When**: Sundays 2-4 AM UTC
- **Notice**: 48 hours advance
- **Process**:
  1. Post maintenance notice
  2. Enable maintenance mode
  3. Perform updates
  4. Verify health
  5. Disable maintenance mode

### Emergency Maintenance

- Notify customers immediately
- Keep maintenance window minimal
- Post incident report after

---

## Contacts

| Role | Contact | When to Reach |
|------|---------|---------------|
| On-call Engineer | PagerDuty | P1/P2 incidents |
| Engineering Lead | [email/phone] | Escalation |
| OpenAI Support | support@openai.com | LLM issues |
| Railway Support | Railway Discord | Infrastructure |
| Security | security@example.com | Security incidents |
