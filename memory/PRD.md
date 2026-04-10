# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module for MyHotelBox.com integration. Receive reviews from online platforms, respond with AI-generated unique replies. Role-based team access, approval workflow, multi-property support.

## What's Been Implemented

### Real-time Notification Popups with Sound (April 2026)
- Red gradient popup slides in from top-right when new review arrives
- Shows: bell icon, "NEW REVIEW" label, guest name, platform badge, star rating, review preview
- Sound notification via Web Audio API (3-tone chime: 880Hz, 1100Hz, 1320Hz)
- Polling every 20 seconds via GET /api/widget/reviews/new
- Click X to dismiss individual, "Dismiss all" for multiple
- Auto-dismiss after 8 seconds
- Review list and stats auto-refresh on new review detection

### Red Notification Badge (April 2026)
- Pulsing red badge showing unread count, red dots on unread cards
- Click review to mark read, click badge to mark all read
- Persisted in MongoDB (is_read field)

### Embeddable Reviews Widget (April 2026)
- Standalone at /widget?api_key=rhk_xxx&property_id=xxx
- No login, API key auth, iframe embeddable, dark mode support

### Webhook Delivery Log + Test Ping (April 2026)
- Last 20 deliveries, test ping with HTTP status + timing

### MyHotelBox Integration Guide (April 2026)
- 5-step walkthrough, API docs, code snippets, iframe embed code

### Left Sidebar Navigation (April 2026)
- 12 items across 4 sections

### API Connection + Webhooks (April 2026)
- CRUD for API keys (rhk_) and webhooks (8 event types)

### Core Features
- JWT auth, 3 roles, 7 departments, approval workflow
- GPT-5.2 AI responses, 16 languages
- 14 platform integrations (UI, sync MOCKED)
- Multi-property, white-label branding

## Next Tasks
1. **P0** - Real bi-directional platform sync (currently MOCKED)
2. **P1** - Property mapping (MyHotelBox branches <-> Review Hub)
3. **P2** - Break down App.js into components
