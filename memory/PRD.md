# Hotel Review Management Module - PRD

## Original Problem Statement
Hotel management review module for MyHotelBox.com integration. Receive reviews from online platforms, respond with AI-generated unique replies. Role-based team access, approval workflow, multi-property support.

## What's Been Implemented

### Low-Rating Alerts (April 2026)
- When review rating <= 2 stars: extra-prominent popup with:
  - Darker red gradient (#991B1B), 2px red border, urgentPulse animation
  - Warning triangle icon (replaces bell), "LOW RATING ALERT" badge + "NEEDS ATTENTION"
  - Larger size (420px max-width, 40px icon), 3-line review preview
  - "Respond quickly to protect your reputation" action prompt
  - Alarm sound (descending square wave: 880→660→440Hz)
  - Stays on screen 15 seconds (vs 8s for normal)
- Email notification logged to DB (Resend integration ready, needs API key)
- Normal reviews (3+ stars): standard bell icon, ascending chime, 8s dismiss

### Real-time Notification Popups with Sound (April 2026)
- Red popup slides from top-right, polls every 20s
- Bell icon + sound for normal, alarm for low-rating
- Dismiss individual or all, auto-dismiss

### Red Notification Badge (April 2026)
- Pulsing red unread count, red dots, mark read/all

### Embeddable Reviews Widget (April 2026)
- /widget?api_key=rhk_xxx&property_id=xxx, no login, iframe embeddable

### Webhook System (April 2026)
- CRUD, 8 event types, delivery log (last 20), test ping

### Integration Guide (April 2026)
- 5-step MyHotelBox walkthrough, code snippets, iframe embed code

### Left Sidebar + API Keys (April 2026)
- 12 nav items, API key CRUD (rhk_ prefix)

### Core Features
- JWT auth, 3 roles, 7 departments, approval workflow
- GPT-5.2 AI responses, 16 languages
- 14 platform integrations (UI, sync MOCKED)
- Multi-property, white-label branding

## Next Tasks
1. **P0** - Real bi-directional platform sync (currently MOCKED)
2. **P1** - Property mapping (MyHotelBox branches <-> Review Hub)
3. **P2** - Break down App.js into components
