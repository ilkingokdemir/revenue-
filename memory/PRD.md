# MyHotelBox — Product Requirements Document

## Overview
Full-suite hotel PMS + POS + Accounting. Competitive with Mews, Cloudbeds, M3, Chatlyn, Duve, Apicbase, Lightspeed, Prostay, Toast.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 (Emergent) | Stripe | Resend | reportlab | httpx

## Complete Module List

### Dashboard — Financial KPIs (RevPAR, ADR, NPS, AR), Action Required, GSS, Activity Feed
### Booking Engine — 10 templates, Stripe, 9 branches, 45 rooms, Multi-lang/currency, AI Concierge
### Guest Messaging (Chatlyn level) — Unified Inbox, AI, Notes, Snooze, Translate, Analytics, Webchat Widget, Contact Lists, Real outbound delivery
### Guest Satisfaction Surveys (NPS) — Public survey page, 6 categories, analytics, auto-tag, alerts
### Review Hub — 14 platforms, AI responses, Real outbound sync (Google/Booking.com/TripAdvisor)

### Hotel POS (Prostay/Toast Competitor — iter 55-57)
- 6 Outlets, 37 Menu Items, 10 Categories
- Dine In / Takeaway / Room Service / QR Self-Order / Kiosk
- Card / Cash / Room Charge / Contactless + tip
- Kitchen Display, Table Management, Split Billing, Room Charging
- Shift Management (open/close till, cash reconciliation)
- **AI-Powered Upselling** — GPT-5.2 suggests add-ons based on cart + guest history + preferences
- **Self-Service Kiosk Mode** — Dark theme full-screen touch interface for tablets
- **QR Code Guest Ordering** — Mobile-optimized public page, no app needed
- **Happy Hour / Dynamic Pricing** — Time-based discounts per outlet/category
- **Digital Email Receipts** — Professional HTML receipts via Resend
- **Guest Preferences** — Dietary, allergens, favorites per guest
- **Loyalty Points** — 4 tiers, earn/redeem, auto tier upgrade
- POS Reports (revenue, margin, by outlet/server, top items, hourly)
- Auto-linked: Payments → Accounting income, Orders → Stock deduction

### Hotel Accounting (19 tabs + Bank Recon — M3 level)
### Stock Management (11 tabs, 128-item catalog — Apicbase level)
### Guest Experience — Profiles + Timeline, Guest App, Digital Keys, Campaigns, Surveys
### Automation, Channel Settings, Connections, Staff Performance

## Public Pages (No Auth)
- `/survey/{token}` — Guest satisfaction survey
- `/qr-order/{property}/{outlet}?table=5` — QR code ordering
- `/kiosk/{property}/{outlet}` — Self-service kiosk
- `/guest-portal` — Guest digital directory
- `/booking/{property}` — Booking engine
- `/widget` — Review widget

## Architecture: 24 route files in /backend/routes/
## Testing: iter 49-57, 285+ total tests, all 95-100% pass
