# Customer Onboarding Guide

## Overview

This guide walks through onboarding a new e-commerce store to the AI Support Agent.

---

## Prerequisites

Before onboarding, the customer needs:

- [ ] Shopify store (required)
- [ ] Admin access to Shopify
- [ ] Gorgias account (optional, for helpdesk integration)
- [ ] Technical contact for widget installation

---

## Onboarding Steps

### Step 1: Create Store Account (5 min)

```bash
# Via admin CLI
python scripts/create_store.py \
  --name "Acme Store" \
  --domain "acme-store.myshopify.com" \
  --contact-email "owner@acme.com"

# Output:
# Store created: store_abc123
# API Key: sk_live_xxx (save this!)
# Widget ID: wgt_abc123
```

Or via Admin UI:
1. Go to Admin Dashboard → Stores → Add Store
2. Enter store name and domain
3. Copy the generated API key

### Step 2: Connect Shopify (10 min)

#### Option A: OAuth Flow (Recommended)

1. Share OAuth URL with customer:
   ```
   https://app.example.com/shopify/install?store=store_abc123
   ```
2. Customer clicks and authorizes in Shopify
3. Access token is automatically saved

#### Option B: Manual API Key

1. Customer creates private app in Shopify Admin:
   - Settings → Apps → Develop apps → Create app
   - Name: "Support Agent"
   - Scopes: `read_orders`, `read_customers`, `read_products`, `write_orders` (for refunds)
2. Customer provides API credentials
3. Enter in Admin UI or CLI:
   ```bash
   python scripts/update_store.py \
     --store-id store_abc123 \
     --shopify-access-token shpat_xxx
   ```

### Step 3: Configure Policies (15 min)

Work with customer to configure:

```json
{
  "returns": {
    "window_days": 30,
    "excluded_categories": ["final_sale", "underwear"],
    "free_return_threshold": 50.00,
    "restocking_fee_percent": 0
  },
  "refunds": {
    "auto_approve_limit": 50.00,
    "require_return_first": true,
    "allow_store_credit": true
  },
  "shipping": {
    "processing_days": 2,
    "carriers": ["usps", "ups", "fedex"]
  },
  "escalation": {
    "order_value_threshold": 500.00,
    "vip_customers": true
  }
}
```

Save via Admin UI or:
```bash
python scripts/update_store.py \
  --store-id store_abc123 \
  --policies policies.json
```

### Step 4: Set Brand Voice (10 min)

Configure the agent's tone and style:

```markdown
# Brand Voice for Acme Store

## Tone
- Friendly and warm, like a helpful neighbor
- Professional but not corporate
- Use customer's first name when available

## Language
- Simple, clear explanations
- No jargon or complex terms
- Casual punctuation (exclamation points OK!)

## Phrases to Use
- "Happy to help!"
- "Let me check on that for you"
- "Thanks for your patience"

## Phrases to Avoid
- "Per our policy..."
- "Unfortunately..."
- Technical terms
```

### Step 5: Import Knowledge Base (20 min)

Upload store-specific content:

```bash
# Upload FAQ document
python scripts/upload_kb.py \
  --store-id store_abc123 \
  --file faq.md \
  --category faq

# Upload product info
python scripts/upload_kb.py \
  --store-id store_abc123 \
  --file products.csv \
  --category products

# Sync from Shopify (products + collections)
python scripts/sync_shopify_kb.py \
  --store-id store_abc123
```

### Step 6: Install Chat Widget (10 min)

Provide embed code to customer:

```html
<!-- Acme Store Support Widget -->
<script>
  window.SupportAgentConfig = {
    storeId: 'store_abc123',
    widgetId: 'wgt_abc123',
    position: 'bottom-right',
    primaryColor: '#2563eb',
    greeting: 'Hi there! How can I help you today?'
  };
</script>
<script src="https://widget.example.com/v1/embed.js" async></script>
```

Installation locations:
- **Shopify**: Settings → Custom Code → Add to `<head>` or use app
- **Other**: Add before `</body>` tag

### Step 7: Connect Gorgias (Optional, 15 min)

If customer uses Gorgias:

1. Get API credentials from Gorgias:
   - Settings → REST API → Create API Key
2. Configure in Admin UI or:
   ```bash
   python scripts/update_store.py \
     --store-id store_abc123 \
     --gorgias-domain "acme.gorgias.com" \
     --gorgias-api-key "xxx"
   ```
3. Set up webhook in Gorgias:
   - Settings → Webhooks → Create
   - URL: `https://api.example.com/api/v1/webhooks/gorgias`
   - Events: `ticket.created`, `message.created`

### Step 8: Test Integration (15 min)

Run through test scenarios:

```bash
# Run automated tests
python scripts/test_store.py --store-id store_abc123

# Manual test checklist:
# [ ] Widget appears on storefront
# [ ] "Where is my order?" returns real data
# [ ] Returns flow works correctly
# [ ] Escalation triggers correctly
# [ ] Gorgias tickets sync (if enabled)
```

### Step 9: Go Live (5 min)

Enable production traffic:

```bash
# Enable store (starts routing traffic)
python scripts/update_store.py \
  --store-id store_abc123 \
  --active true

# Or via Admin UI: Stores → store_abc123 → Status → Active
```

Recommended rollout:
1. Start with 10% traffic (via widget config)
2. Monitor for 24-48 hours
3. Increase to 50%
4. Full rollout after 1 week

---

## Post-Onboarding

### Training Call (30 min)

Schedule call to cover:
- Admin dashboard walkthrough
- Viewing conversation transcripts
- Adjusting policies
- Reading analytics
- Escalation workflow

### First Week Check-in

- Review first-week metrics
- Identify common issues
- Adjust policies/responses as needed
- Gather feedback

### Ongoing Support

- Weekly metrics email
- Monthly optimization review
- Dedicated Slack channel (for higher tiers)

---

## Troubleshooting Common Issues

### Widget Not Appearing

1. Check embed code is correct
2. Verify store is active
3. Check browser console for errors
4. Ensure widget domain is whitelisted

### Orders Not Found

1. Verify Shopify connection is valid
2. Check API permissions include `read_orders`
3. Test with recent order (within 60 days)
4. Check order number format matches Shopify

### Wrong Responses

1. Review knowledge base content
2. Check policy configuration
3. Review conversation in LangSmith
4. Adjust prompts if needed

---

## Onboarding Checklist

```markdown
## Store: _____________  Date: _____________

### Setup
- [ ] Store account created
- [ ] API key generated and shared
- [ ] Shopify connected and tested
- [ ] Policies configured
- [ ] Brand voice set
- [ ] Knowledge base imported

### Integration
- [ ] Widget installed
- [ ] Widget appearing correctly
- [ ] Gorgias connected (if applicable)

### Testing
- [ ] WISMO test passed
- [ ] Returns test passed
- [ ] Refunds test passed
- [ ] Escalation test passed
- [ ] End-to-end flow verified

### Go Live
- [ ] Store activated
- [ ] Initial traffic % set
- [ ] Monitoring configured
- [ ] Training call scheduled

### Sign-off
Store Owner: _____________ Date: _____________
Onboarding Lead: _____________ Date: _____________
```
