# PRD — Hotel PMS & Revenue Management

## Original Problem Statement
High-end full-stack hotel platform (React + FastAPI + MongoDB) — multi-tenant Mews-style hub with 140+ modules. Implement all "keyless" features before requesting external API keys. Turkish language UI.

## Core Personas
- Admin / Manager — Full platform control, scheduling, finance, reports
- Receptionist — Check-in/out, walk-in, folio, time clock
- Housekeeping — Turnover board, route, checklists, time clock
- Chef / F&B — POS, KDS, recipe COGS, banquet, tip pool
- Maintenance — Lock SDK, tickets, asset register
- Guest — Guest app, voice concierge, WhatsApp, kiosk, self check-in

## Key Tech Decisions
- React + Tailwind + shadcn/ui · Capacitor for mobile (iOS/Android)
- FastAPI + Motor (async Mongo) · supervisor-managed
- Emergent LLM Key for OpenAI Whisper STT, TTS-1, GPT-4o-mini
- Stripe (test key) for payments · Twilio (pending) for SMS/WhatsApp
- TR İş Kanunu compliance for labour rules

## Implemented (latest first)

### 2026-05-07
- **Shift Scheduler v2 — RotaPro v2** (NEW)
  - Drag & drop weekly grid, click-to-add modal with templates (Sabah/Öğle/Akşam/Gece)
  - Copy previous week, Bulk publish, Clear week
  - Live cost summary (haftalık £, kişi başı), occupancy panel
  - Conflict detection: long_shift >12h, weekly_overtime >45h (TR İş Kanunu), double_booking, consecutive_nights, leave_clash
  - **AI Auto-Schedule** via Emergent LLM (gpt-4o-mini) with deterministic fallback
  - Occupancy-based staffing recommendation (housekeeper per 12 rooms, +1 receptionist if occ>70%)
  - Time-off / leave requests with TR annual leave balance (14/20/26 days)
  - Mobile clock-in/out events with GPS-ready
  - Open shifts (claimable by staff)
  - 32/32 backend tests passed
- **Mobile & Apps consolidated sidebar section**
  - 10 modules consolidated: Mobile view, Guest app, Self-service kiosk, Pre-arrival check-in, Auto pre-arrival trigger, Voice concierge, WhatsApp voice, Concierge inbox AI, Hardware lock SDK, Marketplace
  - Removed from scattered sections (Reservations / Guests / Operations / System)
  - New `MOBİL & UYGULAMALAR` quick-access grid on Mobile Home (4-col icon grid)
  - WhatsApp Voice admin panel created with setup tab, dev test simulator, sessions log

### Earlier 2026-05
- WhatsApp Voice backend (Twilio webhook → Whisper → GPT-4o-mini → TTS → auto-task)
- Voice Concierge (Whisper STT + TTS-1 + intent classifier)
- Capacitor mobile wrapper (iOS/Android)
- Hardware Lock SDK adapters
- F&B Recipe COGS
- Pre-arrival Auto Self Check-in trigger
- Site Feasibility & Investor Analysis
- Wake Server button + Turkish i18n full coverage

## Backlog (P0 → P2)

### P0
- Twilio API key flow once user provides credentials (real WhatsApp/SMS dispatch)
- Resend API key flow for real email dispatch

### P1
- Backend folder restructure: `/routes/` → `/routes/revenue/`, `/routes/fnb/`, etc.
- Mobile bottom-nav with 5 most-used actions
- Native push notifications (Capacitor)

### P2
- Carbon Reporting v2 (Scope 1+2+3)
- Marketplace v1 (3rd-party app store architecture)
- OTA XML syncing (Booking.com, Expedia)
- PCI-DSS Level 1 / SOC 2 cert prep
- Tip pool (F&B auto-distribution)
- Bordro CSV/.xlsx export

## Architecture
```
/app/
├── backend/
│   ├── routes/ (~220 domain routers)
│   ├── server.py
│   └── hardening.py
├── frontend/
│   ├── src/App.js (slim root + sidebar)
│   ├── src/lazyPanels.js
│   └── src/components/
│       ├── MobileHome.js
│       └── dashboard/ (panels)
└── memory/
    ├── PRD.md
    └── test_credentials.md
```

## Testing Status
- 32/32 backend tests pass for Shift v2 endpoints
- Voice Concierge / WhatsApp Voice already tested earlier
- Frontend smoke-tested via Playwright screenshots
