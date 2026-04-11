# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) — Booking Engine + Review Hub + Guest Messaging modules. Competitive with Mews, Cloudbeds, eviivo, HiJiffy, Bookboost.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 (Emergent Key) | Stripe | Resend | Meta WhatsApp Cloud API (sandbox) | Telegram Bot API (sandbox)

## Completed Features

### Booking Engine — Core
- 10 website templates + live customizer
- Full booking flow: search > rooms > guest details > payment > confirmation
- Stripe Checkout + Pay-at-hotel, Resend email confirmations
- Multi-property (9 branches, 45 room types)

### Competitive Features (All Tested 100%)
- Multi-Language (12 languages + RTL Arabic), Multi-Currency (18 currencies)
- Promo Codes, Add-on Services, Hotel Policies, Property Facilities, Amenity Picker
- Room Editor, Smart Upsell Engine, Price Comparison Widget
- Social Proof Notifications, Google Hotel Structured Data
- Guest Review Collection, Mobile Self-Check-in, Guest Portal
- Cart Abandonment Recovery, Group Booking Engine
- AI Concierge Chat (GPT-5.2 floating widget)
- Hourly/Space Bookings (8 space types)

### Guest Messaging Hub (iter 34-35)

**Unified Inbox** — 3-column layout (list | chat | context sidebar)
- Multi-channel: WhatsApp, Telegram, Email, SMS, Booking.com, Airbnb, Website Chat
- Ticket workflow: New > In Progress > Waiting > Resolved
- Priority levels: Low/Medium/High/Urgent with color badges
- Sentiment detection (positive/negative/neutral)
- Assign/Resolve conversations, search & filters

**AI-Powered**
- AI-suggested replies via GPT-5.2 (one-click to fill)
- Quick Reply Templates (10 pre-built with /shortcuts)
- Auto-Reply FAQ Bot (10 keyword-triggered rules: check-in, WiFi, parking, restaurant, room service, late checkout, airport, spa, luggage, pet policy)

**Guest Contact Directory**
- Searchable guest list from all bookings (name, email, phone)
- Filters: All, In-House, Arriving Today, Departing Today, Upcoming, Past
- One-click WhatsApp/Email/Telegram buttons to start new conversations

**Bookings Calendar**
- Monthly calendar view with check-in (green) / check-out (amber) events
- Month navigation, daily event tooltips
- Stats: total bookings, today's check-ins/check-outs

**New Conversation Modal**
- Channel selector: WhatsApp, Telegram, Email, SMS, Internal
- Pre-fills from Guest Directory contacts
- Creates conversation + initial staff message

**Platform Sending (Sandbox Mode)**
- WhatsApp via Meta Cloud API (sandbox — add credentials in Settings for live)
- Telegram via Bot API (sandbox — add bot token in Settings for live)
- Email via Resend

**Admin Panels**
- Space Bookings Panel: stats, bookings table, complete/cancel actions
- AI Concierge Analytics: sessions, messages, recent conversations

### Review Hub
- 14-platform integration, AI responses (GPT-5.2), approval workflow
- Analytics, competitor benchmarking, embeddable widget

### Infrastructure
- JWT auth (admin/manager/receptionist), white-label branding
- Outbound webhooks (12 event types)

## DB Collections (Messaging)
- `conversations`, `messages`, `quick_replies`, `auto_replies`, `channel_settings`

## Public Routes
- `/book?property={id}`, `/widget?property={id}`, `/review?property={id}&ref={ref}`
- `/checkin?ref={ref}`, `/guest-portal`

## Backlog
- P1: Channel Manager integration (sync availability across OTAs)
- P1: Real bi-directional outbound sync for review platforms
- P1: Automated message sequences (pre-arrival, post-checkout)
- P2: Extract server.py (~5,800 lines) into /routes/ modules
- P3: Real-time availability calendar integration
