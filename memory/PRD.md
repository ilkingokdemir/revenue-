# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) — Booking Engine + Review Hub + Guest Messaging modules. Competitive with Mews, Cloudbeds, eviivo, HiJiffy, Bookboost, Duve.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 (Emergent Key) | Stripe | Resend | Meta WhatsApp Cloud API | Telegram Bot API

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
- **Guest Contact Directory** — From bookings, filters, one-click messaging
- **Bookings Calendar** — Monthly check-in/out events
- **New Conversation Modal** — Channel selector with pre-fill from contacts

### Automation Engine (iter 36)
- 6 Pre-built Journey Rules (Pre-Arrival, Arrival Day, Mid-Stay, Post-Checkout x2, Cart Recovery)
- Rule editor with template variables, trigger/timing/channel config
- Run Now execution, execution logs, stats dashboard

### Channel Settings (iter 37)
- **WhatsApp Business** — Meta Cloud API config (Phone Number ID, Access Token, Business ID)
- **Telegram Bot** — Bot Token + Username config
- **SMS** — Provider, API Key, Sender Number
- **Email** — Resend (active by default)
- **Auto-Reply** — Welcome message + auto-reply when staff unavailable
- Setup guides with step-by-step instructions
- Test Connection buttons for each channel
- All channels in sandbox mode until credentials added

### Review Hub
- 14-platform integration, AI responses, approval workflow, analytics, competitor benchmarking

### Admin Panels
- Space Bookings management, AI Concierge analytics

### Infrastructure
- JWT auth (admin/manager/receptionist), white-label branding, outbound webhooks

## Sidebar Structure
- Review Hub: Reviews, Analytics, Response Templates, Approvals, Alerts, Reports
- Booking Engine: Rooms & Bookings, Space Bookings, Website Templates, Customize Template, Promo Codes, Add-on Services, Policies & Facilities
- Guest Messaging: Unified Inbox, Automation, Channel Settings, AI Concierge
- Connections: Integrations, API Connection, Webhooks

## Backlog
- P1: Channel Manager integration (sync availability across OTAs)
- P1: Real bi-directional outbound sync for review platforms
- P2: Extract server.py (~6,200 lines) into /routes/ modules
- P3: Real-time availability calendar integration
