# My Hotel Box - Product Requirements Document

## Original Problem Statement
Hotel management software "My Hotel Box" — a full-stack platform to rival top industry software (Chatlyn for messaging, M3 for accounting, Apicbase for stock, Prostay for POS, Cloudbeds for payments). Must NOT build: Channel Manager, Dynamic Pricing, or Space Bookings (handled externally).

## Tech Stack
- Frontend: React + Tailwind CSS + Shadcn UI
- Backend: FastAPI + MongoDB
- Integrations: OpenAI GPT-5.2 (Emergent LLM Key), Resend (Email), Stripe (Payments), iyzico (Turkey), PayTR (Turkey)

## What's Been Implemented

### Payment Gateway (Cloudbeds-level)
- **Stripe Virtual Payments**: Booking Engine → Stripe Checkout at checkout.stripe.com
- **iyzico Virtual Checkout**: Turkish checkout with card form, installments (taksit), 3D Secure, all Turkish banks
- **PayTR Virtual Checkout**: Turkish Sanal POS with card form, installments, SMS payment support
- **Guest Payment Portal**: Staff sends link → Guest views itemized folio → Pays via Stripe/iyzico/PayTR
- **Automated Payment Reminders**: Auto-email before checkout with configurable timing
- **Physical Card Terminals**: Stripe Terminal, iyzico, PayTR hardware integration
- **Payment Dashboard**: Processed/Pending totals, success rate, daily trends, transaction filtering

### Booking Engine
- 4 payment options: Stripe, iyzico, PayTR, Pay at Hotel
- Public booking at /book?property={id}
- Room search, promo codes, add-ons, upsells, multi-currency, AI concierge

### Other Modules (All Complete)
- Review Hub, Unified Messaging, Guest Surveys (NPS), Accounting (18 tabs), POS, Stock Management, etc.

## Testing Status
- 63 iterations, all passing
- Iteration 63: Turkish Payments (14/14 backend, 100% frontend)

## Upcoming Tasks (P1)
- Real bi-directional outbound sync for review platforms (needs user API keys)
- Real outbound messaging for WhatsApp/Telegram/SMS (needs user credentials)
