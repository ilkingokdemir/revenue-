# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) — Booking Engine + Review Hub + Guest Messaging + Automation modules. Competitive with Mews, Cloudbeds, eviivo, HiJiffy, Bookboost, Duve.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 (Emergent Key) | Stripe | Resend | Meta WhatsApp Cloud API | Telegram Bot API

## Completed Features

### Dashboard Home (Default Landing) — iter 38
- **Today's Snapshot**: Check-ins, check-outs, in-house guests, occupancy rate
- **Revenue Widgets**: Week/month totals with booking counts
- **Messaging Stats**: Unread messages, open conversations (clickable → inbox)
- **Review Stats**: Avg rating, total reviews (clickable → reviews)
- **3-Column Activity Feed**: Recent bookings, unread messages (with channel icons), recent reviews (with star ratings)
- **Automation Status**: Today's sends, failed, tomorrow's pre-arrival count
- **Quick Actions**: Jump to Inbox, Automation, Reviews, Bookings

### Booking Engine — Core
- 10 website templates + live customizer, Full booking flow, Stripe + Pay-at-hotel
- Multi-property (9 branches, 45 room types), Resend email confirmations

### Competitive Features (All Tested 100%)
- Multi-Language (12 + RTL Arabic), Multi-Currency (18 currencies)
- Promo Codes, Add-ons, Policies, Facilities, Amenities, Room Editor
- Smart Upsells, Price Comparison, Social Proof, Google Structured Data
- Guest Reviews, Self-Check-in, Guest Portal, Cart Recovery, Group Bookings
- AI Concierge Chat (GPT-5.2), Hourly/Space Bookings (8 types)

### Guest Messaging Hub
- **Unified Inbox**: Multi-channel (WhatsApp/Telegram/Email/SMS/OTA), ticket workflow, priority, sentiment
- **AI-Suggested Replies** (GPT-5.2), Quick Reply Templates (10), Auto-Reply FAQ Bot (10 rules)
- **Guest Contact Directory**: From bookings, filters, one-click messaging
- **Bookings Calendar**: Monthly check-in/out events
- **New Conversation Modal**: Channel selector with pre-fill

### Automation Engine
- 6 Pre-built Journey Rules (Pre-Arrival, Arrival Day, Mid-Stay, Post-Checkout x2, Cart Recovery)
- Rule editor with template variables, Run Now, logs & stats

### Channel Settings
- WhatsApp (Meta Cloud API), Telegram (Bot API), SMS, Email (Resend), Auto-Reply
- Setup guides, credential inputs, Test Connection buttons

### Review Hub
- 14-platform integration, AI responses, approval workflow, analytics, competitor benchmarking

### Webhooks & Sync Logs (Production-Ready Audit Trail)
- **Guest Profiles**: `guest.created`, `guest.updated`, `guest.vip_changed` webhooks + sync logs
- **Campaigns**: `campaign.created`, `campaign.sent` webhooks + sync logs + auto-tags guest profiles
- **Messaging Hub**: `conversation.created`, `conversation.resolved`, `message.sent` webhooks + sync logs
- **Automation Engine**: `automation.triggered`, `automation.failed` webhooks + sync logs
- **Digital Keys**: `key.generated`, `key.revoked`, `key.used` webhooks + sync logs
- **Guest App**: `directory.updated` webhook + sync log
- **Cross-Module Connections**: Booking→Guest Profile auto-update, Campaign→Guest Profile tagging, Review→Guest Profile linking

### Connections & Integrations
- **Platform Setup Wizard** — Self-service step-by-step guides for Google Business, Booking.com, TripAdvisor, WhatsApp, Telegram with credential management, test connection, auto-sync to channel settings
- **Digital Keys / Smart Locks** — 6 lock providers (TTLock, Nuki, August/Yale, Salto KS, ASSA ABLOY, Generic), digital key generation per booking with 6-digit access codes, public guest key endpoint, revoke support
- **130+ Language AI Chat** — AI Concierge auto-detects guest language and responds in same language, AI messaging replies also multilingual

### Guest Experience (Competitive with Mews, Cloudbeds, Duve, HiJiffy)
- **Housekeeping Management** — Room status board (Clean/Dirty/Inspected/In Progress/Out of Order), task assignment, maintenance requests, seeding
- **Guest Profiles / CRM** — Unified guest history synced from bookings, VIP toggle, loyalty tiers, search/sort, detailed view with booking/review/conversation history
- **Campaign Manager** — Bulk messaging (Email/WhatsApp/SMS), guest segmentation filters (VIP, loyalty tier, stays, spend, tags), preview recipients, send tracking
- **Guest App / Digital Directory** — WiFi credentials, hotel services (6 default), local recommendations (4 default), public guest-facing URL, editable via admin panel

### Admin Panels
- Space Bookings management, AI Concierge analytics
- Staff Performance Dashboard — Agent leaderboard, response times, resolution rates, channel breakdown, daily trends, performance scoring
- Real-time Availability Calendar — Month grid, color-coded occupancy, day detail panel, room type breakdown
- Guest Satisfaction Score (GSS) — Composite KPI (Reviews 50% + Sentiment 25% + Response Speed 25%), shown on Dashboard Home

### Infrastructure
- JWT auth (admin/manager/receptionist), white-label branding, outbound webhooks

## Sidebar Structure
- Dashboard (home icon — default landing)
- Review Hub: Reviews, Analytics, Response Templates, Approvals, Alerts, Reports
- Booking Engine: Rooms & Bookings, Space Bookings, Website Templates, Customize, Promos, Add-ons, Policies
- Guest Messaging: Unified Inbox, Automation, Channel Settings, AI Concierge
- Connections: Integrations, API Connection, Webhooks

### Operations
- **Stock Management (Apicbase-level)** — Product catalog, portion-based recipes, sub-recipes (recipe-in-recipe), automatic COGS per sale, theoretical vs actual consumption tracking (theft-proof), wastage with reason codes (expired/spoiled/theft_suspected/etc), supplier management, purchase orders with auto-receive→stock, stock count sheets with variance calculation, all-inclusive cost per guest per night, low stock alerts, variance/theft detection
- **Hotel Accounting (M3/Xero-level)** — USALI Chart of Accounts (19 auto-seeded accounts), invoicing with automatic VAT calculation (20%), receivable & payable invoices, VAT reports (output vs input), 6-month financial trends, P&L statement with department cost centers, budget vs actual comparison, CSV export, auto-pull booking revenue from Booking Engine

## Code Architecture (Fully Refactored)
```
backend/
├── server.py              # App setup, Stripe webhook, seeds (406 lines — was 6,400)
├── routes/
│   ├── helpers.py         # Shared: serialize_review, log_sync, fire_webhooks (55 lines)
│   ├── auth_routes.py     # Auth, Users, Properties (243 lines)
│   ├── connections.py     # API Keys, Webhooks, Integration Guide (337 lines)
│   ├── reviews.py         # Reviews, Templates, Sentiment, Competitors, Widget (1,399 lines)
│   ├── integrations.py    # Reports, Branding, Platform Integrations, Sync (1,417 lines)
│   ├── bookings.py        # Booking Engine, Room Types, Stripe (1,451 lines)
│   ├── messaging.py       # Conversations, Messages, Quick Replies (517 lines)
│   ├── automation.py      # Automation Rules, Logs, Stats (222 lines)
│   ├── dashboard.py       # Dashboard Overview, Concierge, Space Bookings Admin (179 lines)
│   ├── staff_performance.py # Staff Performance Dashboard (220 lines)
│   ├── calendar_gss.py    # Availability Calendar + Guest Satisfaction Score
│   ├── housekeeping.py    # Room Status Board, Tasks, Maintenance
│   ├── guest_profiles.py  # Guest CRM, Profile Sync, VIP Management
│   ├── campaigns.py       # Campaign Manager, Segmentation, Bulk Send
│   ├── guest_app.py       # Guest App / Digital Directory (public + admin)
│   ├── smart_locks.py     # Smart Lock Providers + Digital Keys
│   ├── setup_wizard.py    # Platform Setup Wizard (5 platforms)
│   ├── stock.py           # Stock Management (F&B inventory, recipes, variance)
│   └── accounting.py      # Hotel Accounting (P&L, income, expenses, budgets)
├── auth.py                # JWT auth, require_roles
├── database.py            # MongoDB connection
└── models.py              # Pydantic models
```

## Backlog
- P1: Dynamic Pricing / Revenue Management (AI-driven rate optimization)
- P2: Drag-and-drop reservation calendar (visual booking management)
- Note: Channel Manager already exists on myhotelbox.com — NOT building
