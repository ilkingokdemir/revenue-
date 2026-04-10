# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module for MyHotelBox.com integration. Receive reviews from online platforms, respond with AI-generated unique replies. Role-based team access, approval workflow, multi-property support.

## What's Been Implemented

### Red Notification Badge (April 2026)
- Pulsing red (#DC2626) badge on widget showing unread review count
- Red dots on each unread review card (top-right corner)
- Click individual review to mark as read (dot disappears, count decrements)
- Click badge to mark ALL as read (badge disappears, all dots gone)
- Persisted in DB (is_read field on reviews)
- API: GET /api/widget/unread-count, PUT /api/widget/reviews/{id}/read, PUT /api/widget/reviews/mark-all-read

### Embeddable Reviews Widget (April 2026)
- Standalone at `/widget?api_key=rhk_xxx&property_id=xxx`
- No login, API key auth, iframe embeddable
- Stats bar, review list, detail panel, AI generation, filters
- Dark mode (?theme=dark)

### Webhook Delivery Log + Test Ping (April 2026)
- Last 20 deliveries per webhook, test ping with result display

### MyHotelBox Integration Guide (April 2026)
- 5-step walkthrough, API docs, code snippets, iframe embed code

### Left Sidebar Navigation (April 2026)
- 12 items: Reviews, Analytics, Templates, Approvals, Integrations, API Connection, Webhooks, Integration Guide, Alerts, Reports, Branding, Team

### API Connection + Webhooks (April 2026)
- CRUD for API keys (rhk_ prefix) and webhooks (8 event types)

### Core Features
- JWT auth, 3 roles, 7 departments, approval workflow
- GPT-5.2 AI responses, 16 languages
- 14 platform integrations (UI, sync MOCKED)
- Multi-property support, white-label branding

## Next Tasks
1. **P0** - Real bi-directional platform sync (currently MOCKED)
2. **P1** - Property mapping (MyHotelBox branches <-> Review Hub)
3. **P2** - Break down App.js into components
