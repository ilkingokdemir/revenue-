# PRD — Hotel PMS & Revenue Management

## Original Problem Statement
High-end full-stack hotel platform (React + FastAPI + MongoDB) — multi-tenant Mews-style hub with 140+ modules. Implement all "keyless" features before requesting external API keys. Turkish language UI.

## Core Personas
- Admin / Manager — Full platform control, scheduling, finance, reports (sees all £ amounts)
- Receptionist / Housekeeper / Maintenance — Operational view (no £ visibility)
- Chef / F&B — POS, KDS, recipe COGS, banquet, tip pool
- Guest — Guest app, voice concierge, WhatsApp, kiosk, self check-in

## Key Tech Decisions
- React + Tailwind + shadcn/ui · Capacitor for mobile
- FastAPI + Motor (async Mongo) · supervisor-managed
- Emergent LLM Key for OpenAI Whisper STT, TTS-1, GPT-4o-mini
- Stripe (test key) for payments · Twilio (pending) for SMS/WhatsApp

## Implemented (latest first)

### 2026-05-08
- **Shift Scheduler — Per-Staff Unique Color & Pay Privacy**
  - 24-color palette assigned deterministically per branch (id-sorted index)
  - Each staff = unique color: avatar + 4px left border + shift cell background all matching
  - Pay info (£ rate, earned amounts) HIDDEN from non-admin/manager users (frontend `canSeePay` check)
  - **Auto-sync to finance** — when shift status becomes `completed` or `approved` (single PUT or bulk endpoints), `finance_earned_salaries` entries are created automatically (idempotent via shift_id)
  - 42/42 backend tests passed (10 new + 32 regression, 0 failures)

### 2026-05-07
- **Shift Scheduler v2 — RotaPro v2** (backend)
  - Conflict detection: long_shift >12h, weekly_overtime >45h (TR), double_booking, consecutive_nights, leave_clash
  - AI Auto-Schedule via Emergent LLM
  - Occupancy-based staffing recommendation
  - Time-off / leave requests with TR annual leave balance
  - Mobile clock-in/out events
  - Open shifts (claimable)
- **Mobile & Apps consolidated sidebar section** (preserved across rollback)
- **WhatsApp Voice integration backend** — Twilio webhook → Whisper → GPT-4o-mini → TTS → auto-task

### Earlier 2026-05
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
- Backend folder restructure: `/routes/` → domain folders
- Mobile bottom-nav with 5 most-used actions
- Native push notifications (Capacitor)
- Backend-side pay_rate/earned_amount filtering for non-admin GET requests (defense-in-depth)

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
│   └── src/components/dashboard/
└── memory/
    ├── PRD.md
    └── test_credentials.md
```

## Testing Status
- 42/42 backend tests pass (Shift v2 + auto-sync regression)
- Voice Concierge / WhatsApp Voice tested earlier
- Frontend smoke-tested via Playwright screenshots
