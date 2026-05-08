# PRD — Hotel PMS & Revenue Management

## Original Problem Statement
High-end full-stack hotel platform (React + FastAPI + MongoDB) — multi-tenant Mews-style hub with 140+ modules. Implement all "keyless" features before requesting external API keys. Turkish language UI.

## Implemented (latest first)

### 2026-05-08
- **Smart Insights — AI Auto-Learning from Patterns** (NEW)
  - `GET /api/rates/grid/insights/{prop}?lookback_days=N` — analyzes rate_override_history grouped by day-of-week
  - 3 pattern types:
    - `repeated_loss_pattern` (warning): same DOW ≥2× with owner >AI ≥10% + occupancy <30%
    - `consistent_win_pattern` (success): same DOW ≥3× with owner >AI + bookings + occupancy ≥30%
    - `min_rate_streak` (info): 5+ days at min_rate in last 14 days
  - `POST /api/rates/grid/insights/apply` — generates target rates for next N matching weekdays (dry-run, owner reviews+submits)
  - Frontend: amber/emerald/stone alert ribbon at top of My Rates panel; one-click "Sonraki 3 X için AI fiyatına çek" pre-fills pending overrides
  - 27/27 backend tests passed (test_reports/iteration_268.json)

- **AI vs Owner Win/Loss Scoreboard** — wins/losses/win-rate/revenue lift + biggest win/loss + per-date table (iter 267, 19/19)
- **Rate Override History + AI Explainer + Release-to-AI** — drawer with Sentinel rate + Why narrative + signals + history + Release (iter 266, 14/14)
- **PMS Link — Owner Rates Flow End-to-End** — submit-to-pms writes to owner_rate_overrides + rate_overrides + rate_sync_queue; booking engine uses per-night override (iter 265, 12/12)
- **Per-room-type Availability + Occupancy in date headers + My Rates panel** (iter 264, 28/28)
- **Shift Scheduler — unique colors + pay privacy + auto-finance-sync** (iter 263, 42/42)

### Earlier 2026-05
- Mobile & Apps consolidated sidebar
- WhatsApp Voice integration backend
- Voice Concierge (Whisper + TTS-1)
- Capacitor mobile wrapper
- Hardware Lock SDK
- F&B Recipe COGS
- Pre-arrival Auto Self Check-in
- Site Feasibility & Investor Analysis
- Wake Server button + Turkish i18n

## Backlog (P0 → P2)

### P0
- Real channel push from rate_sync_queue → Booking.com/Expedia (needs OTA credentials)
- Twilio API key flow (real WhatsApp/SMS)
- Resend API key flow (real email)
- FLOWCAST chart on My Rates panel (occupancy bars + pickup + PMS rate dots + AI line)

### P1
- Per-room-type override (Standard/Deluxe/Suite distinct rates)
- AI Status per-day toggle (SENTINEL/MANUAL/auto-revert schedule)
- Scheduled re-run of insights (daily background) → push notifications
- Backend folder restructure
- Mobile bottom-nav

### P2
- Demand Radar (event/holiday correlation)
- Compset Intel dedicated tab
- A/B testing methodology (replace naive winloss counterfactual)
- Carbon Reporting v2
- Marketplace v1
- OTA XML syncing
- PCI-DSS / SOC 2 cert prep
- Tip pool / Bordro CSV export

## Testing Status
- **174 cumulative backend tests passing** across iterations 262-268
- Voice Concierge / WhatsApp Voice tested earlier
- Frontend smoke-tested via Playwright
