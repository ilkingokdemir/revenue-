# My Hotel Box - Product Requirements Document

## Original Problem Statement
Hotel management software "My Hotel Box" — a full-stack platform to rival top industry software (Chatlyn for messaging, M3 for accounting, Apicbase for stock, Prostay for POS, Cloudbeds for payments). Must NOT build: Channel Manager, Dynamic Pricing, or Space Bookings (handled externally).

## Tech Stack
- Frontend: React + Tailwind CSS + Shadcn UI
- Backend: FastAPI + MongoDB
- Integrations: OpenAI GPT-5.2 (Emergent LLM Key), Resend (Email), Stripe (Payments)

## Architecture
```
/app/backend/routes/ — 19 route files (bookings, payments, terminal, guest_payment, pos, accounting, messaging, etc.)
/app/frontend/src/ — Public pages (BookingEngine, GuestPaymentPage, KioskPage, QROrderPage, etc.)
/app/frontend/src/components/dashboard/ — Admin panel components
```

## What's Been Implemented (Complete)

### Core Platform
- Multi-property management (10 properties) with branch selector
- JWT auth (admin/manager/receptionist roles)
- Setup Wizard, Connections panel, Smart Locks, Digital Keys

### Booking Engine (Cloudbeds-level)
- Public booking page at /book?property={id}
- Room search, availability, multi-room booking
- Guest details, promo codes, add-ons, upsells
- AI Concierge chat, Cart abandonment recovery
- Self check-in, Guest portal, Group bookings
- Multi-currency, Multi-language (130+ via AI)

### Payment Gateway (Cloudbeds-level)
- Stripe Virtual Payments: Booking Engine → Pay Now with Card → Stripe Checkout
- Guest Payment Portal: Staff sends link → Guest views itemized folio → Pays via Stripe
- Automated Payment Reminders: Auto-email guests before checkout with unpaid balance
- POS Checkout via Stripe
- Physical Card Terminals: Stripe Terminal, iyzico (Turkey), PayTR (Turkey)
- Payment Dashboard, Transaction management, Payment settings

### Guest Payment Portal
- POST /api/guest-payment/send-link — Send payment link
- GET /api/guest-payment/folio/{token} — View itemized folio
- POST /api/guest-payment/pay/{token} — Pay via Stripe
- POST /api/guest-payment/add-charge/{link_id} — Add extra charges
- Frontend: /pay/{token} — Guest-facing folio page

### Automated Payment Reminders
- GET/PUT /api/guest-payment/reminder-settings/{property_id} — Configure timing
- POST /api/guest-payment/send-reminders/{property_id} — Send batch reminders
- GET /api/guest-payment/reminder-history/{property_id} — View history
- Settings: First/second reminder hours, max per booking, auto-send toggle
- Admin UI: Send Reminders button with detailed results

### Review Hub, Unified Messaging, Guest Surveys, Accounting, POS, Stock Management
All previously built and tested (see earlier PRD versions).

## Testing Status
- 62 test iterations completed (all passing)
- Iteration 60: Stripe Virtual Payments (16/16, 100%)
- Iteration 61: Guest Payment Portal (17/17, 100%)
- Iteration 62: Payment Reminders (14/14, 100%)

## Upcoming Tasks (P1)
- Real bi-directional outbound sync for review platforms (needs user API keys)
- Real outbound messaging for WhatsApp, Telegram, SMS (needs user credentials)

## Future/Backlog (P2)
- All requested features implemented
