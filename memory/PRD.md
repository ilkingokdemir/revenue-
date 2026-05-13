# PRD — Hotel PMS & Revenue Management

## Original Problem Statement
High-end full-stack hotel platform (React + FastAPI + MongoDB) — multi-tenant Mews-style hub with 140+ modules. Implement all "keyless" features before requesting external API keys. Turkish language UI.

## Implemented (latest first)

### 2026-05-13 (iter 275 — Flexkeeping Automation Suite)
- **Otomasyon Kuralları** (NEW — Flexkeeping Automation Suite parity)
  - Backend `automation_rules.py`: event-driven rule engine, TRIGGER_CATALOG (8), ACTION_CATALOG (6), OPERATORS (8). Endpoints under `/api/automation/v2/*` (separate from legacy automation).
  - Exposed `fire_event(db, event, payload)` for other modules to call. Wired into:
    - `bookings.py` → fires `booking_created` after every successful booking
    - `glitch_log.py` → fires `glitch_critical` when severity=critical
  - Action execution: `create_task` / `create_glitch` / `amenity_request` / `notify_role` / `set_room_status` / `tag_booking`. Template substitution (`{guest_name}` → payload).
  - Frontend `AutomationRulesPanel.js`: rule cards with last-run status, enable/disable toggle, create modal (trigger + AND-conditions builder + actions builder), runs history modal.
  - **36/36 backend testi geçti + frontend %100 doğrulandı** (iteration_273.json).

### 2026-05-13 (iter 274 — Flexkeeping parity)
- **Glitch Log & Vardiya Devri** (NEW — Flexkeeping-style)
  - Backend `glitch_log.py`: CRUD + acknowledge + handover endpoints. Severity/department/shift enum validation, idempotent ack via `$addToSet`.
  - Frontend `GlitchLogPanel.js`: filtered list (status/severity/shift/dept/days), create modal, handover packet modal grouped by severity.
- **Digital SOPs Library** (NEW — Flexkeeping-style QA Suite)
  - Backend `sops.py`: CRUD + publish + acknowledge + versioning (steps değişince version+1 ve acks reset).
  - 9 kategori, role bazlı targeting, draft/published/archived statüleri.
  - Frontend `SopsPanel.js`: arama, kategori/status filtre, step builder, detail modal (publish/archive/ack).
- Sidebar: Operations altında yeni "**Quality Assurance**" alt-bölüm.
- **52/52 backend + frontend %100** (iteration_272.json — note: iteration number reset by testing agent)

### 2026-05-09 (iter 272 — bugfix)
- **Online Check-in Kiosk `/checkin-kiosk/all` Düzeltildi**
  - Bug: `kiosk-lookup/all` literal `"property_id":"all"` filtreliyordu; gerçek hiçbir rezervasyon eşleşmiyordu (1581 gerçek rezervasyondan 0).
  - Fix `guest_journey.py`: `kiosk_info` ve `kiosk_lookup` artık `property_id="all"` parametresinde tüm property'lere bakıyor; `kiosk_register` rezervasyonu booking'in **gerçek** property_id'sine kaydediyor (URL placeholder'ı yerine).
  - Fix `CheckInKioskPage.js`: `all` modunda her booking sonucunda 🏨 property_id label'ı görünüyor.
  - Manuel doğrulama: "Smith" arandığında 20 gerçek rezervasyon listeleniyor (önceki davranış: sadece 1 test kaydı).

### 2026-05-09 (iter 271)
- **Aylık TR Bordro PDF** (NEW)
  - Backend `workforce_extras.py`: `_aggregate_for_payroll()` ve `_tr_payroll_breakdown()` yardımcıları, `GET /api/payroll/preview/{property_id}` (JSON) + `GET /api/payroll/export-pdf/{property_id}` (PDF) endpoint'leri.
  - 4857/5510 sayılı kanunlara uygun kesintiler: SGK %14, İşsizlik %1, Gelir V. %15, Damga %0.759. Custom oranlar query ile override edilebilir.
  - PDF (reportlab Platypus): Property başlığı, dönem, kesinti politikası dipnotu, personel başına Brüt/SGK/İşsizlik/GV/Damga/Net tablosu, TOPLAM satırı, İşveren+Personel imza alanları, 4857-32/37 yasal not.
  - Frontend `OperationsHubPanel.js`: Shifts tab'ında yeni `📄 Bordro PDF (Aylık)` butonu (admin/manager only).
  - **24/24 backend testi geçti + frontend UI %100 doğrulandı** (iteration_271.json).

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
- **244 cumulative backend tests passing** across iterations 262-271

## Test Credentials
Admin: admin@hotelbox.com / HotelAdmin2026!
