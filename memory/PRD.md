# Hotel Review Management Module + Booking Engine - PRD

## Original Problem Statement
Hotel management review module + booking engine for MyHotelBox.com PMS. Receive reviews from online platforms, respond with AI-generated unique replies. Booking engine like Mews/Cloudbeds/eviivo with Booking.com-style design for trust. Stripe payment processing for direct bookings.

## What's Been Implemented

### Booking Engine with Stripe Payments (April 2026)
- **Public Booking Engine** at `/book?property={property_id}`:
  - Booking.com-style blue UI with trust signals (SSL, security badges)
  - Step-by-step flow: Search → Select Room → Guest Details → Payment → Confirmation
  - Room cards with photos, amenities, pricing, "Free cancellation" and "Breakfast included" badges
  - "Only X left on our site!" urgency cues
  - **Payment Method Selection**: Pay Now with Card (Stripe) or Pay at Hotel
  - Stripe Checkout integration with real Stripe redirect
  - Payment status polling on return from Stripe
  - Booking confirmation with MHB-XXXXXXXX reference number
  - Mobile-responsive with sticky "Book Now" bar

- **Stripe Payment Integration**:
  - `POST /api/payments/create-checkout` — creates Stripe checkout session (amount from server-side only)
  - `GET /api/payments/status/{session_id}` — polls payment status
  - `POST /api/webhook/stripe` — handles Stripe webhook events
  - `payment_transactions` collection for audit trail
  - Prevents double-processing of payments

- **Admin Dashboard - Booking Engine Panel**:
  - Room Types tab: Create, edit, delete room types
  - Bookings tab with status management (Check In, Cancel, No Show, Check Out)
  - Payment status badges (Paid/Unpaid/Processing)
  - Copy Booking URL and Preview buttons

- **Sample Data**: 5 room types seeded for "aldgate-flats" (£89-£349)

### Review Hub Module (Earlier)
- Webhook inbound sync for 14 platforms
- GPT-5.2 AI response generation in 16 languages
- Role-based approval workflow
- Real-time widget with notifications
- Integration panel with connection testing
- Multi-branch selector (9 branches)
- Sync logging, property mapping, branding

## Architecture
```
frontend/src/
├── App.js (~2770 lines)
├── BookingEngine.js (Stripe + booking flow)
├── ReviewWidget.js
├── components/dashboard/
│   ├── BookingEnginePanel.js (admin room/booking management)
│   ├── IntegrationsPanel.js, AnalyticsPanel.js, etc.
│   └── index.js

backend/server.py (~4100 lines)
 - Auth, Reviews, AI, Webhooks, Integrations
 - Booking Engine: rooms, availability, reservations
 - Stripe: checkout sessions, status polling, webhooks
```

## DB Collections
reviews, users, properties, webhooks, webhook_deliveries, api_keys, 
platform_integrations, sync_logs, branding_settings,
room_types, bookings, payment_transactions

## Remaining Work
- Hotel website landing page template with embeddable booking widget
- Email confirmation for bookings (Resend integration)
- Real outbound sync to review platforms (vendor credentials needed)
- Google OAuth configuration (user needs to obtain credentials)
- More website templates for different hotel styles
