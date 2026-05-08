# PRD — Hotel PMS & Revenue Management

## Original Problem Statement
High-end full-stack hotel platform (React + FastAPI + MongoDB) — multi-tenant Mews-style hub with 140+ modules. Implement all "keyless" features before requesting external API keys. Turkish language UI.

## Core Personas
- Admin / Manager / Hotel Owner — Full platform control, scheduling, finance, reports, **rate decisions**
- Receptionist / Housekeeper / Maintenance — Operational view (no £ visibility)
- Chef / F&B — POS, KDS, recipe COGS, banquet, tip pool
- Guest — Guest app, voice concierge, WhatsApp, kiosk, self check-in

## Implemented (latest first)

### 2026-05-08
- **Rate Override History + AI Explainer + Release-to-AI** (NEW)
  - `rate_override_history` collection — every submit/release logged with previous→new, delta%, by-user, timestamp
  - `GET /api/rates/grid/history/{prop}/{date}` — last 20 changes
  - `POST /api/rates/grid/release/{prop}/{date}` — removes lock, AI takes over again
  - `GET /api/rates/grid/explain/{prop}/{date}` — AI-generated 3-bullet Turkish explanation via Emergent LLM (gpt-4o-mini)
  - Click any date column header → drawer with Sentinel rate + AI narrative + signal breakdown + history + Release button
  - 14/14 backend tests passed (test_reports/iteration_266.json)

- **PMS Link — Owner Rates Flow End-to-End**
  - `submit-to-pms` writes to `owner_rate_overrides` (grid) + `rate_overrides` (PMS source) + `rate_sync_queue` (channel push)
  - `set_by="owner-override"` + `locked=true` protect from auto-scanner overwrites
  - Booking engine `/booking/reserve` uses per-night override lookup → owner rates flow into actual sales
  - 12/12 backend tests passed (test_reports/iteration_265.json)

- **Per-room-type Availability + Occupancy in date headers**
  - Room types listed below the metric grid; per-day free count colored (red 0, amber low, green plenty)
  - Doluluk % shown in column header (under date number)

- **My Rates — Market-Pulse style 365-day rate grid**
  - Aggregates per-day: ADR, Occupancy %, Pickup, Min Rate, Floor, Live PMS Rate, Current Sell Rate, Compset Avg, Sentinel AI Rate, Target Sell Rate, PMS Override
  - Owner inline-edits; pending changes amber-ringed; batch Submit to PMS+OTA queue with guardrails
  - 28/28 backend tests passed (test_reports/iteration_264.json)

- **Shift Scheduler — Per-Staff Unique Color & Pay Privacy + Auto-sync to finance**
  - 24-color palette per branch; £ pay info hidden from non-admin/manager
  - Completed/approved shifts auto-sync to `finance_earned_salaries` (idempotent)
  - 42/42 backend tests passed (test_reports/iteration_263.json)

### Earlier 2026-05
- Mobile & Apps consolidated sidebar section (10 modules)
- WhatsApp Voice integration backend (Twilio webhook → Whisper → GPT → TTS)
- Voice Concierge (Whisper + TTS-1)
- Capacitor mobile wrapper
- Hardware Lock SDK adapters
- F&B Recipe COGS
- Pre-arrival Auto Self Check-in trigger
- Site Feasibility & Investor Analysis
- Wake Server button + Turkish i18n full coverage

## Backlog (P0 → P2)

### P0
- Real channel push from `rate_sync_queue` → Booking.com/Expedia (needs OTA credentials)
- Twilio API key flow (real WhatsApp/SMS dispatch)
- Resend API key flow (real email dispatch)
- FLOWCAST chart on My Rates panel

### P1
- Per-room-type override (different rates per Standard / Deluxe / Suite)
- AI Status per-day toggle (SENTINEL/MANUAL/auto-revert schedule)
- Backend folder restructure: `/routes/` → domain folders
- Mobile bottom-nav with 5 most-used actions
- Native push notifications (Capacitor)
- Backend-side pay_rate filter for non-admin (defense-in-depth)

### P2
- Demand Radar (event/holiday calendar correlation)
- Compset Intel dedicated tab
- Carbon Reporting v2 (Scope 1+2+3)
- Marketplace v1 (3rd-party app store)
- OTA XML syncing
- PCI-DSS Level 1 / SOC 2 cert prep
- Tip pool (F&B auto-distribution)
- Bordro CSV/.xlsx export

## Testing Status
- 14/14 + 12/12 + 28/28 + 42/42 + 32/32 backend tests across iterations 262-266, all green
- Voice Concierge / WhatsApp Voice tested earlier
- Frontend smoke-tested via Playwright
