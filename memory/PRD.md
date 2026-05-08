# PRD — Hotel PMS & Revenue Management

## Original Problem Statement
High-end full-stack hotel platform (React + FastAPI + MongoDB) — multi-tenant Mews-style hub with 140+ modules. Implement all "keyless" features before requesting external API keys. Turkish language UI.

## Implemented (latest first)

### 2026-05-08
- **AI vs Owner Win/Loss Scoreboard** (NEW)
  - Captures `ai_rate_at_submit` in `rate_override_history` on every submit-to-pms
  - `GET /api/rates/winloss/{property_id}?lookback_days=N` — wins/losses/neutrals + revenue lift + biggest win/loss
  - Verdict logic: owner > AI + bookings → win | owner > AI + 0 bookings → loss | owner < AI + occ ≥50% → neutral
  - Naive revenue counterfactual: AI_revenue = bookings × ai_rate; Owner_revenue = bookings × owner_rate
  - Frontend: gradient violet/emerald tile on My Rates panel showing wins/losses/win-rate/revenue lift; click opens detailed modal with KPIs + biggest win/loss + per-date comparison table
  - 19/19 backend tests passed (test_reports/iteration_267.json)

- **Rate Override History + AI Explainer + Release-to-AI**
  - `rate_override_history` collection — every submit/release logged with previous→new, delta%, by-user, timestamp
  - 3 endpoints: GET /history, POST /release (kilidi kaldır → AI'a devret), GET /explain (Emergent LLM gpt-4o-mini Turkish narrative)
  - Click date column header → drawer with Sentinel rate + Why narrative + signals + history + Release button
  - 14/14 backend tests passed (test_reports/iteration_266.json)

- **PMS Link — Owner Rates Flow End-to-End**
  - submit-to-pms writes to owner_rate_overrides + rate_overrides (set_by=owner-override, locked=true) + rate_sync_queue
  - Booking engine /booking/reserve uses per-night override lookup → owner rates flow into actual sales
  - 12/12 backend tests passed (test_reports/iteration_265.json)

- **Per-room-type Availability + Occupancy in date headers** + **My Rates panel** (28/28, iter 264)
- **Shift Scheduler — unique colors + pay privacy + auto-finance-sync** (42/42, iter 263)

### Earlier 2026-05
- Mobile & Apps consolidated sidebar section
- WhatsApp Voice integration backend
- Voice Concierge (Whisper + TTS-1)
- Capacitor mobile wrapper
- Hardware Lock SDK
- F&B Recipe COGS
- Pre-arrival Auto Self Check-in trigger
- Site Feasibility & Investor Analysis
- Wake Server button + full Turkish i18n

## Backlog (P0 → P2)

### P0
- Real channel push from rate_sync_queue → Booking.com/Expedia (needs OTA credentials)
- Twilio API key flow (real WhatsApp/SMS)
- Resend API key flow (real email)
- FLOWCAST chart on My Rates panel

### P1
- Per-room-type override (different rates per Standard / Deluxe / Suite)
- AI Status per-day toggle (SENTINEL/MANUAL/auto-revert schedule)
- Advanced winloss A/B testing methodology (replace naive counterfactual)
- Backend folder restructure: `/routes/` → domain folders
- Mobile bottom-nav

### P2
- Demand Radar (event/holiday correlation)
- Compset Intel dedicated tab
- Carbon Reporting v2
- Marketplace v1
- OTA XML syncing
- PCI-DSS / SOC 2 cert prep
- Tip pool
- Bordro CSV export

## Testing Status
- 19+14+12+28+42+32 = 147 cumulative backend tests passing across iterations 262-267
- Voice Concierge / WhatsApp Voice tested earlier
- Frontend smoke-tested via Playwright
