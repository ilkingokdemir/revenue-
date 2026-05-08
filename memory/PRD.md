# PRD — Hotel PMS & Revenue Management

## Original Problem Statement
High-end full-stack hotel platform (React + FastAPI + MongoDB) — multi-tenant Mews-style hub with 140+ modules. Implement all "keyless" features before requesting external API keys. Turkish language UI.

## Core Personas
- Admin / Manager / Hotel Owner — Full platform control, scheduling, finance, reports, **rate decisions**
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
- **My Rates — Market-Pulse style 365-day rate grid** (NEW, P0 done)
  - Aggregates per-day: ADR, Occupancy %, Pickup (24h), Min Rate, Floor (LMF), Live PMS Rate, Current Sell Rate (scraped), Compset Avg, Sentinel AI Rate (heuristic), Target Sell Rate, PMS Override
  - Owner inline-edits overrides; pending changes highlighted; batch "Submit X Change(s)" pushes to PMS+OTA queue with guardrails
  - Effective rate priority: pms_override > target_sell_rate > live_pms_rate, capped above min/floor
  - Sentinel AI rate anchored to compset_avg or default base, modulated by demand (occupancy + pickup), guardrail-clamped
  - 28/28 backend tests passed (test_reports/iteration_264.json)
  - New collections: `owner_rate_overrides`, `rate_sync_queue`
  - New endpoints: GET/POST `/api/rates/grid/{property_id}`, POST/DELETE `/api/rates/grid/override`, POST `/api/rates/grid/submit-to-pms`
  - Sidebar: "Revenue & rates → My Rates (Daily Grid)" first item

- **Shift Scheduler — Per-Staff Unique Color & Pay Privacy**
  - 24-color palette assigned deterministically per branch; avatars + cells matching
  - £ pay info hidden from non-admin/manager via `canSeePay`
  - Auto-sync shift status `completed`/`approved` → `finance_earned_salaries` (idempotent)
  - 42/42 backend tests passed (test_reports/iteration_263.json)

### 2026-05-07
- Shift Scheduler v2 backend (conflicts, AI auto-schedule, occupancy-needs, leaves, clock-in, open shifts)
- Mobile & Apps consolidated sidebar section
- WhatsApp Voice integration backend

### Earlier 2026-05
- Voice Concierge (Whisper + TTS-1)
- Capacitor mobile wrapper
- Hardware Lock SDK adapters
- F&B Recipe COGS
- Pre-arrival Auto Self Check-in trigger
- Site Feasibility & Investor Analysis
- Wake Server button + Turkish i18n full coverage

## Backlog (P0 → P2)

### P0
- Twilio API key flow (real WhatsApp/SMS dispatch)
- Resend API key flow (real email dispatch)
- FLOWCAST chart on My Rates panel (occupancy bars + pickup + PMS rate dots + AI line + min rate guardrail)

### P1
- Backend folder restructure: `/routes/` → domain folders
- Mobile bottom-nav with 5 most-used actions
- Native push notifications (Capacitor)
- Backend-side pay_rate/earned_amount filtering for non-admin GET requests (defense-in-depth)
- Override history (who, when, what change)
- Auto-revert (override expiry → back to AI)
- AI Status per-day toggle (some days SENTINEL, some MANUAL)
- Real OTA channel push from rate_sync_queue (currently queued only)

### P2
- Carbon Reporting v2 (Scope 1+2+3)
- Marketplace v1 (3rd-party app store architecture)
- OTA XML syncing (Booking.com, Expedia)
- PCI-DSS Level 1 / SOC 2 cert prep
- Tip pool (F&B auto-distribution)
- Bordro CSV/.xlsx export
- Demand Radar (event/holiday calendar correlation)
- Compset Intel dedicated tab

## Testing Status
- 28/28 + 42/42 + 32/32 backend tests pass across iterations 262-264
- Voice Concierge / WhatsApp Voice tested earlier
- Frontend smoke-tested via Playwright
