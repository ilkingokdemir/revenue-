# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) — Booking Engine + Review Hub + Guest Messaging modules. Competitive with Mews, Cloudbeds, eviivo, HiJiffy, Bookboost.

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
- **AI Concierge Chat** — GPT-5.2 floating chat widget, property context, sessions (iter 33)
- **Hourly/Space Bookings** — 8 space types, hourly/half-day/full-day rates (iter 33)

### Guest Messaging Hub — Phase 1 (iter 34)
- **Unified Inbox** — All guest conversations in one 3-column view (list | chat | profile)
- **Multi-Channel** — WhatsApp, Email, SMS, Booking.com, Airbnb, Website Chat
- **Ticket Workflow** — New > In Progress > Waiting > Resolved
- **AI-Suggested Replies** — GPT-5.2 one-click contextual reply suggestions
- **Quick Reply Templates** — 10 pre-built templates with shortcuts (/welcome, /checkin, /wifi etc.)
- **Guest Profile Sidebar** — Contact info, channel, status, priority, tags, assigned staff
- **Conversation Actions** — Assign to me, Resolve, Mark Urgent, Lower Priority
- **Search & Filters** — Search by guest name/email, filter by status and channel
- **Sentiment Detection** — Positive/negative/neutral with emoji indicators
- **Space Bookings Admin Panel** — Stats cards, bookings table, complete/cancel actions
- **AI Concierge Analytics** — Session counts, message stats, recent chat sessions list

### Email Triggers (Resend)
- Booking confirmation, review collection, self-check-in link, cart abandonment recovery, guest portal magic link
- Note: RESEND_API_KEY is placeholder — functional in production with real key

### Review Hub
- 14-platform integration, AI responses (GPT-5.2), approval workflow
- Analytics, competitor benchmarking, embeddable widget
- API keys, notifications, report settings

### Infrastructure
- JWT auth (admin/manager/receptionist), white-label branding
- Backend modular: server.py, models.py, auth.py, database.py
- Outbound webhooks (12 event types)

## DB Collections (Messaging)
- `conversations`: guest_name, guest_email, channel, status, priority, sentiment, tags, assigned_to, unread_count
- `messages`: conversation_id, sender_type (guest/staff/ai), content, channel
- `quick_replies`: name, content, category, shortcut, usage_count
- `channel_settings`: property_id, whatsapp/sms/email enabled, twilio config

## Public Routes
- `/book?property={id}` — Booking engine
- `/widget?property={id}` — Embeddable review widget
- `/review?property={id}&ref={booking_ref}` — Review collection page
- `/checkin?ref={booking_ref}` — Self check-in page
- `/guest-portal` — Guest portal (magic link login)

## In Progress
- Phase 2: AI auto-categorization & smart priority scoring for conversations
- Phase 3: WhatsApp/SMS via Twilio (sandbox mode), automation engine

## Backlog
- P1: Channel Manager integration (sync availability across OTAs)
- P1: Real bi-directional outbound sync for review platforms
- P1: Automated message sequences (pre-arrival, post-checkout)
- P2: Extract server.py (~5,500 lines) into /routes/ modules
- P3: Real-time availability calendar integration
