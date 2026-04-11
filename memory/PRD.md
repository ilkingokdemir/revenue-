# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) — Booking Engine + Review Hub + Guest Messaging + Automation modules. Competitive with Mews, Cloudbeds, eviivo, HiJiffy, Bookboost, Duve, **Chatlyn**.

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

### Guest Messaging Hub (Chatlyn Parity — iter 50)
- **Unified Inbox**: Multi-channel (WhatsApp/Telegram/Email/SMS/OTA/Webchat), ticket workflow, priority, sentiment
- **AI-Suggested Replies** (GPT-5.2), Quick Reply Templates (10), Auto-Reply FAQ Bot (10 rules)
- **Guest Contact Directory**: From bookings, filters, one-click messaging
- **Bookings Calendar**: Monthly check-in/out events
- **New Conversation Modal**: Channel selector with pre-fill
- **Internal Notes / Private Comments** — Staff-only notes on conversations with @mention support (invisible to guests)
- **Conversation Snooze** — Snooze conversations with 5 duration options (30m, 1h, 2h, 4h, tomorrow 9AM), auto-wake when timer expires
- **1-Click Translate** — AI-powered translation for guest messages and staff replies across 20+ languages using GPT-5.2
- **Guest Booking Data Sidebar** — View guest profile, VIP status, loyalty tier, total stays, total spent, and full booking history right next to the conversation
- **Conversation Analytics Dashboard** — Activity heatmap (day × hour), First Response Time, Resolution Time, resolution rate, volume by channel/agent/tag, sentiment breakdown
- **Webchat Widget Configurator** — Full settings panel for embeddable live chat widget (color, position, welcome/offline messages, AI toggle, require name/email), live preview, embed code generator
- **Contact Lists** — Static and dynamic lists for targeted WhatsApp/Email campaigns. Dynamic lists auto-populate from guest profiles using filters (VIP, loyalty tier, min stays, tags, min spend)

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
- **Guest Profiles / CRM** — Unified guest history synced from bookings, VIP toggle, loyalty tiers, search/sort, detailed view with booking/review/conversation history
- **Campaign Manager** — Bulk messaging (Email/WhatsApp/SMS), guest segmentation filters (VIP, loyalty tier, stays, spend, tags), preview recipients, send tracking
- **Guest App / Digital Directory** — WiFi credentials, hotel services (6 default), local recommendations (4 default), public guest-facing URL, editable via admin panel

### Admin Panels
- Staff Performance Dashboard — Agent leaderboard, response times, resolution rates, channel breakdown, daily trends, performance scoring
- Guest Satisfaction Score (GSS) — Composite KPI (Reviews 50% + Sentiment 25% + Response Speed 25%), shown on Dashboard Home

### Infrastructure
- JWT auth (admin/manager/receptionist), white-label branding, outbound webhooks

## Sidebar Structure
- **Dashboard** (home icon — default landing)
- **Review Hub**: Reviews, Analytics, Response Templates, Approvals, Alerts, Reports
- **Booking Engine**: Rooms & Bookings, Website Templates, Customize, Promos, Add-ons, Policies
- **Guest Experience**: Guest Profiles, Guest App, Digital Keys, Campaigns
- **Operations**: Stock / F&B, Accounting
- **Guest Messaging**: Unified Inbox, Automation, Channel Settings, AI Concierge, Staff Performance
- **Connections**: Setup Wizard, Integrations, API Connection, Webhooks, Sync Log, Integration Guide
- **Settings**: Property Mapping, Branding, Team

### Operations
- **Stock Management (Best-in-class, Apicbase-level)** — Product catalog (13 categories, 9 units, allergens, yield %, expiry tracking, par levels), portion-based recipes with sub-recipes, automatic COGS per sale, Menu Engineering (Stars/Puzzles/Plowhorses/Dogs profitability matrix), Food Cost % Dashboard (target 28-35%, per-outlet breakdown), Par Level Auto-Ordering (auto-generate POs), Allergen & Nutrition tracking, Supplier Price History, Yield Management (raw vs usable cost), Perishable Forecasting (FIFO expiry alerts), Multi-Outlet Transfers, Inventory Turnover Rate (target 4-8x), theoretical vs actual consumption (theft-proof), wastage with reason codes, supplier management, purchase orders, stock count sheets, variance detection — **11 tabs in UI**
- **Hotel Accounting (M3/Xero-level)** — USALI Chart of Accounts (19 auto-seeded accounts), invoicing with automatic VAT calculation (20%), receivable & payable invoices, VAT reports (output vs input), 6-month financial trends, P&L statement with department cost centers, budget vs actual comparison, CSV export, auto-pull booking revenue from Booking Engine

## Code Architecture (Fully Refactored)
```
backend/
├── server.py              # App setup, Stripe webhook, seeds (446 lines)
├── routes/
│   ├── helpers.py         # Shared: serialize_review, log_sync, fire_webhooks
│   ├── auth_routes.py     # Auth, Users, Properties
│   ├── connections.py     # API Keys, Webhooks, Integration Guide
│   ├── reviews.py         # Reviews, Templates, Sentiment, Competitors, Widget
│   ├── integrations.py    # Reports, Branding, Platform Integrations, Sync
│   ├── bookings.py        # Booking Engine, Room Types, Stripe
│   ├── messaging.py       # Conversations, Messages, Quick Replies, Calendar
│   ├── messaging_advanced.py  # Internal Notes, Snooze, Translate, Booking Data, Analytics, Webchat Config, Contact Lists
│   ├── automation.py      # Automation Rules, Logs, Stats
│   ├── dashboard.py       # Dashboard Overview, Concierge, Space Bookings Admin
│   ├── staff_performance.py # Staff Performance Dashboard
│   ├── calendar_gss.py    # Guest Satisfaction Score
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
- Note: Dynamic Pricing, Drag-and-drop Calendar, Channel Manager — all exist on myhotelbox.com, NOT building
- Note: Space Bookings, Availability Calendar, Housekeeping — removed from sidebar per user request (backend routes still exist)
- Real bi-directional outbound sync for review platforms (P1)
- Real outbound messaging for WhatsApp, Telegram, SMS — currently Sandbox mode (P1)

## Testing
- Iteration 49: 100% pass (51 backend tests) — Full regression before chatlyn features
- Iteration 50: 100% pass (39 backend tests + frontend) — All 7 chatlyn competitor features verified
