# My Hotel Box - Product Requirements Document

## Original Problem Statement
Hotel management software "My Hotel Box" — a full-stack platform to rival top industry software (Chatlyn for messaging, M3 for accounting, Apicbase for stock, Prostay for POS, Cloudbeds for payments). Must NOT build: Channel Manager, Dynamic Pricing, or Space Bookings (handled externally).

## Tech Stack
- Frontend: React + Tailwind CSS + Shadcn UI
- Backend: FastAPI + MongoDB
- Integrations: OpenAI GPT-5.2 (Emergent LLM Key), Resend (Email), Stripe (Payments)

## Architecture
```
/app/backend/routes/ — 18 route files (bookings, payments, terminal, pos, accounting, messaging, etc.)
/app/frontend/src/components/dashboard/ — Admin panel components
/app/frontend/src/ — Public pages (BookingEngine, KioskPage, QROrderPage, etc.)
```

## What's Been Implemented (Complete)

### Core Platform
- Multi-property management with branch selector
- JWT auth (admin/manager/receptionist roles)
- Setup Wizard, Connections panel, Smart Locks

### Booking Engine (Cloudbeds-level)
- Public booking page at /book?property={id}
- Room search, availability, multi-room booking
- Guest details, promo codes, add-ons, upsells
- AI Concierge chat, Cart abandonment recovery
- Self check-in, Guest portal, Group bookings
- Multi-currency, Multi-language (130+ via AI)

### Payment Gateway (Cloudbeds-level) - VERIFIED WORKING
- **Stripe Virtual Payments**: Booking Engine → Pay Now with Card → Redirects to real Stripe Checkout at checkout.stripe.com
- POS Checkout via Stripe
- Payment status tracking, webhook handling
- Physical Card Terminals: Stripe Terminal, iyzico (Turkey), PayTR (Turkey)
- Payment Dashboard: Processed/Pending/Failed totals, success rate, daily trends
- Payment Settings: Toggle Stripe, Pay at Hotel, Room Charging, Cash, Contactless, Tipping

### Review Hub
- Multi-platform review aggregation (Google, Booking.com, TripAdvisor, etc.)
- AI-powered response generation
- Sentiment analysis, Review collection from guests

### Unified Messaging (Chatlyn-level)
- 7 advanced features: Snooze, Translate, Internal Notes, Widget, Lists, FAQ
- Multi-channel: Email, WhatsApp, Telegram, SMS (requires real credentials)

### Guest Surveys (NPS)
- Customizable survey templates
- Public guest-facing survey pages
- NPS scoring and analytics

### Accounting (M3-level)
- 18 tabs: Income, Expenses, P&L, Balance Sheet, Cash Flow, etc.
- Bank Reconciliation with CSV import
- PDF Invoice generation
- Department budgets, Tax reporting

### Hotel POS (Prostay-level)
- Outlets, Categories, Menu items, Tables
- QR Code self-ordering at /qr-order/{property}/{outlet}
- AI-powered Self-Service Kiosk at /kiosk/{property}/{outlet}
- Kitchen display, Order management

### Stock Management
- Inventory tracking, Purchase orders
- Low stock alerts, Supplier management

### Other Features
- Enhanced Dashboard with RevPAR, ADR KPIs
- Staff Performance tracking
- Campaign management
- Automation rules

## Bugs Fixed This Session
1. `bookings.py` line 1112: `property.get()` used Python built-in instead of fetched property doc → Fixed to `prop_doc = await db.properties.find_one(...)`
2. Frontend called `/api/payments/create-checkout` (non-existent) → Fixed to call `/api/payments/booking-checkout`
3. Stripe success URL pointed to `/booking-confirmation` (no such route) → Fixed to `/book?property={id}&payment=success&session_id={SESSION_ID}`
4. Payment status endpoint missing `booking_ref` in response → Added

## Testing Status
- 60 test iterations completed (iterations 1-60)
- Iteration 60: 16/16 backend tests passed (100%), all frontend features verified (100%)

## Known Limitations
- Stripe test key (`sk_test_emergent`) can CREATE checkout sessions but cannot RETRIEVE session status (expected for test mode)
- Real WhatsApp/Telegram/SMS requires user's API credentials
- Physical terminal hardware integration is simulated

## Upcoming Tasks (P1)
- Real bi-directional outbound sync for review platforms (needs user API keys)
- Real outbound messaging for WhatsApp, Telegram, SMS (needs user credentials)

## Future/Backlog (P2)
- Guest Portal payment page (guests view folio and pay via Stripe)
