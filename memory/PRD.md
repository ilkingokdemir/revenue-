# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) — Booking Engine module sold to hotels & serviced apartments. Competitive with Mews, Cloudbeds, eviivo, Hotelchamp.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 (Emergent Key) | Stripe | Resend

## Completed Features

### Booking Engine — Core
- 10 website templates + live customizer
- Full booking flow: search > rooms > guest details > payment > confirmation
- Stripe Checkout + Pay-at-hotel
- Resend email confirmations
- Multi-property (9 branches, 45 room types)

### Competitive Features (All Tested 100%)
- **Multi-Language** — 12 languages, RTL Arabic, URL/localStorage persistence (iter 30)
- **Promo Codes** — CRUD, validation, checkout integration (iter 29)
- **Add-on Services** — per_stay/night/person pricing, categories (iter 29)
- **Hotel Policies** — check-in/out, cancellation, house rules (iter 29)
- **Property Facilities** — 8 categories, 50+ options (iter 29)
- **Amenity Picker** — 160+ amenities, 10 categories (iter 29)
- **Room Editor** — unlimited photos, 4-tab layout (iter 29)
- **Smart Upsell Engine** — 10 templates, auto-suggest in checkout (iter 31)
- **Price Comparison Widget** — OTA vs direct pricing savings (iter 31)
- **Social Proof Notifications** — viewing count, recent bookings, low stock (iter 31)
- **Google Hotel Structured Data** — JSON-LD for Google Maps/Search (iter 31)
- **Guest Review Collection** — Post-stay review page, star rating, flows into Review Hub (iter 32)
- **Mobile Self-Check-in** — 4-step flow: welcome > ID > terms > complete (iter 32)
- **Guest Portal** — Magic link login, booking history, re-booking (iter 32)
- **Cart Abandonment Recovery** — Save/recover abandoned carts with tokens (iter 32)
- **Multi-Currency** — 18 currencies with conversion (iter 32)
- **Group Booking Engine** — Corporate/wedding/conference request form (iter 32)
- **AI Concierge Chat** — GPT-5.2 powered floating chat widget, property context, session tracking (iter 33)
- **Hourly/Space Bookings** — 8 space types, hourly/half-day/full-day rates, booking form (iter 33)

### Email Triggers (Resend)
- Booking confirmation, review collection, self-check-in link, cart abandonment recovery, guest portal magic link
- Note: RESEND_API_KEY is placeholder (re_123456789) — functional in production with real key

### Review Hub
- 14-platform integration, AI responses (GPT-5.2), approval workflow
- Analytics, competitor benchmarking, embeddable widget
- API keys, notifications, report settings

### Infrastructure
- JWT auth (admin/manager/receptionist), white-label branding
- Backend modular: server.py, models.py, auth.py, database.py
- Outbound webhooks (12 event types)

## Public Routes
- `/book?property={id}` — Booking engine
- `/widget?property={id}` — Embeddable review widget
- `/review?property={id}&ref={booking_ref}` — Review collection page
- `/checkin?ref={booking_ref}` — Self check-in page
- `/guest-portal` — Guest portal (magic link login)

## Backlog
- P1: Channel Manager integration (sync availability across OTAs)
- P1: Real bi-directional outbound sync for review platforms
- P2: Extract server.py (~5,000 lines) into /routes/ modules
- P3: Real-time availability calendar integration
