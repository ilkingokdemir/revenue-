# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) — Booking Engine + Review Hub + Guest Messaging modules. Competitive with Mews, Cloudbeds, eviivo, HiJiffy, Bookboost.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 (Emergent Key) | Stripe | Resend | Meta WhatsApp Cloud API (sandbox) | Telegram Bot API (sandbox)

## Completed Features

### Booking Engine — Core
- 10 website templates + live customizer, Full booking flow, Stripe + Pay-at-hotel
- Multi-property (9 branches, 45 room types), Resend email confirmations

### Competitive Features (All Tested 100%)
- Multi-Language (12 + RTL Arabic), Multi-Currency (18 currencies)
- Promo Codes, Add-ons, Policies, Facilities, Amenities, Room Editor
- Smart Upsells, Price Comparison, Social Proof, Google Structured Data
- Guest Reviews, Self-Check-in, Guest Portal, Cart Recovery, Group Bookings
- AI Concierge Chat (GPT-5.2), Hourly/Space Bookings (8 types)

### Guest Messaging Hub (iter 34-35)
- **Unified Inbox** — Multi-channel (WhatsApp/Telegram/Email/SMS/OTA), ticket workflow, priority, sentiment
- **AI-Suggested Replies** (GPT-5.2), Quick Reply Templates (10), Auto-Reply FAQ Bot (10 rules)
- **Guest Contact Directory** — From bookings, filters (All/In-House/Arriving/Departing/Upcoming/Past)
- **Bookings Calendar** — Monthly view with check-in/out events
- **New Conversation Modal** — Channel selector (WhatsApp/Telegram/Email/SMS/Internal)
- **Platform Sending** — WhatsApp (Meta Cloud API), Telegram (Bot API), Email (Resend) — all sandbox mode

### Automation Engine (iter 36)
- **6 Pre-built Journey Rules:**
  1. Pre-Arrival Welcome (email, 24h before)
  2. Day-of-Arrival Reminder (WhatsApp, same day)
  3. Mid-Stay Satisfaction Check (WhatsApp, 24h after check-in)
  4. Post-Checkout Thank You & Review (email, 2h after)
  5. Post-Checkout WhatsApp Follow-up (WhatsApp, 4h after)
  6. Cart Abandonment Recovery (email, 1h after)
- **Rule Editor** — Trigger selector, timing, channel, template with variables ({guest_name}, {hotel_name}, {booking_ref}, {checkin_link}, {review_link} etc.)
- **Template Preview** — Live preview with sample data
- **Run Now** — Manual execution matches bookings against rules
- **Execution Logs** — Full history with status (sent/failed/queued)
- **Stats Dashboard** — Active rules, total sent, today, failed, queued, by channel

### Admin Panels
- Space Bookings management, AI Concierge analytics

### Review Hub
- 14-platform integration, AI responses, approval workflow, analytics, competitor benchmarking

### Infrastructure
- JWT auth (admin/manager/receptionist), white-label branding, outbound webhooks

## Backlog
- P1: Channel Manager integration (sync availability across OTAs)
- P1: Real bi-directional outbound sync for review platforms
- P2: Extract server.py (~6,000 lines) into /routes/ modules
- P3: Real-time availability calendar integration
