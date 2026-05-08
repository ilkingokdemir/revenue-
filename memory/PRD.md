# PRD — Hotel PMS & Revenue Management

## Original Problem Statement
High-end full-stack hotel platform (React + FastAPI + MongoDB) — multi-tenant Mews-style hub with 140+ modules. Implement all "keyless" features before requesting external API keys. Turkish language UI.

## Implemented (latest first)

### 2026-05-08 (iter 270)
- **Per-Room-Type Rate Override** (NEW)
  - Backend `rates_grid.py`: `GET /api/rates/grid/{prop}?room_type_id=` filter, override save/submit/delete/release all room-type scoped, response now returns `room_type_id`.
  - `bookings.py`: booking total now reads room-type-specific override first, falls back to property-wide, then base price.
  - `dynamic_pricing.py`: per-room-type override lookup with property-wide fallback.
  - Frontend `MyRatesPanel.js`: new "Oda Tipi" selector (`rates-room-type-select`), scope badge (`scope-badge` + `scope-clear-btn`), drawer scope indicator (`drawer-scope-badge`), release respects scope.
  - **20/20 backend tests passed + frontend UI verified** (iteration_270.json) — Standard £200 / Deluxe £350 / property-wide £90 verified non-colliding.

### 2026-05-08 (iter 269)
- **FLOWCAST chart + Bordro CSV export + Tip Pool** (NEW)
  - **FLOWCAST** (recharts): unified timeline on My Rates panel — occupancy bars + Live PMS line + Sentinel AI line + Compset avg + Min rate guardrail + Pickup line. Dual Y-axis (£ rate / occupancy %).
  - **Bordro CSV export** (`GET /api/payroll/export/{prop}?week_start=...&month=...`) — Turkish headers, completed/approved shifts only, TOPLAM row, downloadable from Operations Hub Shifts tab (admin/manager only)
  - **Tip Pool distribution** (`POST /api/tip-pool/distribute` with modes: equal / hours / role with weights). Persists to tip_distributions collection. `GET /api/tip-pool/history/{prop}` for audit.
  - 26/26 backend tests passed (test_reports/iteration_269.json)

- **Smart Insights — AI Auto-Learning** (iter 268, 27/27): DOW pattern detection, one-click apply
- **AI vs Owner Win/Loss Scoreboard** (iter 267, 19/19)
- **Rate Override History + AI Explainer + Release-to-AI** (iter 266, 14/14)
- **PMS Link — Owner Rates Flow End-to-End** (iter 265, 12/12)
- **Per-room-type Availability + Occupancy in date headers + My Rates panel** (iter 264, 28/28)
- **Shift Scheduler — unique colors + pay privacy + auto-finance-sync** (iter 263, 42/42)

### Earlier 2026-05
- Mobile & Apps consolidated sidebar, WhatsApp Voice, Voice Concierge, Capacitor mobile, Hardware Lock SDK, F&B Recipe COGS, Pre-arrival Auto Self Check-in, Site Feasibility & Investor Analysis, Wake Server, full Turkish i18n.

## Backlog (P0 → P2)

### P0
- Real channel push from rate_sync_queue → Booking.com/Expedia (needs OTA credentials)
- Twilio API key flow (real WhatsApp/SMS)
- Resend API key flow (real email)
- Native push notifications (Capacitor + FCM/APNs keys)

### P1
- AI Status per-day toggle (SENTINEL/MANUAL/auto-revert)
- Scheduled re-run of insights (nightly cron) + push notifications
- Offline mobile mode (service worker)
- Backend folder restructure (~220 routes → domain subfolders)
- Mobile bottom-nav
- Monthly PDF Bordro generation (TR Labor Law fields + signature areas)
- WhatsApp Voice inbound webhook completion (Twilio → Whisper → LLM → TTS)

### P2
- Demand Radar (event/holiday correlation)
- Compset Intel dedicated tab
- A/B testing methodology
- Carbon Reporting v2
- Marketplace v1
- OTA XML syncing
- PCI-DSS / SOC 2 cert prep

## Testing Status
- **220 cumulative backend tests passing** across iterations 262-270

## Test Credentials
Admin: admin@hotelbox.com / HotelAdmin2026!
