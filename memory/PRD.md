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
- **Action Required Panel**: Tracks 7 types of system alerts

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
- **Internal Notes / Private Comments** — Staff-only notes with @mention support
- **Conversation Snooze** — 5 duration options, auto-wake timer
- **1-Click Translate** — AI GPT-5.2 translation across 20+ languages
- **Guest Booking Data Sidebar** — VIP status, loyalty tier, total stays/spent, booking history
- **Conversation Analytics Dashboard** — Heatmap, FRT, Resolution Time, by channel/agent/tag
- **Webchat Widget Configurator** — Color, position, messages, AI toggle, preview, embed code
- **Contact Lists** — Static & dynamic lists for targeted campaigns

### Guest Satisfaction Surveys (NPS) — iter 51
- **NPS Score Collection** — 0-10 scale with emoji feedback, categorizes promoter/passive/detractor
- **Category Ratings** — 6 configurable categories (Cleanliness, Service, Location, Value, Comfort, Facilities) rated 1-5
- **Multi-Channel Delivery** — Email + WhatsApp (configurable), customizable email templates
- **Auto-Send** — Automatically sends surveys to guests after checkout (configurable delay: 2h default)
- **Manual Send** — Send survey to specific guest by name/email
- **Public Survey Page** — Beautiful guest-facing survey form at /survey/{token} (no auth needed)
- **Analytics Dashboard** — Net NPS, avg NPS, response rate, NPS distribution bar, category averages, daily trend, recent comments
- **Low Score Alerts** — Configurable threshold triggers sync log alerts
- **Guest Profile Integration** — Auto-tags guest profiles as nps:promoter/passive/detractor
- **Configurable Settings** — Survey type (NPS only vs detailed), delay hours, channels, email template, reminder, alert threshold

### Automation Engine
- 6 Pre-built Journey Rules (Pre-Arrival, Arrival Day, Mid-Stay, Post-Checkout x2, Cart Recovery)
- Rule editor with template variables, Run Now, logs & stats

### Channel Settings
- WhatsApp (Meta Cloud API), Telegram (Bot API), SMS, Email (Resend), Auto-Reply

### Review Hub
- 14-platform integration, AI responses, approval workflow, analytics, competitor benchmarking

### Webhooks & Sync Logs (Production-Ready Audit Trail)
- Guest Profiles, Campaigns, Messaging Hub, Automation Engine, Digital Keys, Guest App webhooks + sync logs
- Cross-Module Connections: Booking→Guest Profile, Campaign→Guest Profile, Review→Guest Profile

### Connections & Integrations
- Platform Setup Wizard (Google Business, Booking.com, TripAdvisor, WhatsApp, Telegram)
- Digital Keys / Smart Locks (6 providers)
- 130+ Language AI Chat

### Guest Experience
- Guest Profiles / CRM with VIP, loyalty tiers, NPS tags
- Campaign Manager (Email/WhatsApp/SMS bulk messaging)
- Guest App / Digital Directory
- Guest Satisfaction Surveys / NPS

### Admin Panels
- Staff Performance Dashboard
- Guest Satisfaction Score (GSS)

### Operations
- **Stock Management (Apicbase-level)** — 13 categories, recipes, sub-recipes, COGS, Menu Engineering, Par Level Auto-Ordering, Allergen tracking, Yield Management, 11 tabs
- **Hotel Accounting (M3/Xero-level)** — USALI accounts, invoicing, VAT, P&L, budgets, CSV export

### Infrastructure
- JWT auth (admin/manager/receptionist), white-label branding, outbound webhooks

## Sidebar Structure
- **Dashboard** (home icon)
- **Review Hub**: Reviews, Analytics, Response Templates, Approvals, Alerts, Reports
- **Booking Engine**: Rooms & Bookings, Website Templates, Customize, Promos, Add-ons, Policies
- **Guest Experience**: Guest Profiles, Guest App, Digital Keys, Campaigns, **Surveys / NPS**
- **Operations**: Stock / F&B, Accounting
- **Guest Messaging**: Unified Inbox, Automation, Channel Settings, AI Concierge, Staff Performance
- **Connections**: Setup Wizard, Integrations, API Connection, Webhooks, Sync Log, Integration Guide
- **Settings**: Property Mapping, Branding, Team

## Code Architecture
```
backend/
├── server.py
├── routes/
│   ├── helpers.py, auth_routes.py, connections.py, reviews.py, integrations.py
│   ├── bookings.py, messaging.py, messaging_advanced.py, automation.py
│   ├── dashboard.py, staff_performance.py, calendar_gss.py
│   ├── guest_profiles.py, campaigns.py, guest_app.py, smart_locks.py
│   ├── setup_wizard.py, stock.py, accounting.py
│   └── surveys.py          # NEW: Guest Satisfaction Surveys
├── auth.py, database.py, models.py
```

## Backlog
- Dynamic Pricing, Drag-and-drop Calendar, Channel Manager — NOT building (exists on legacy site)
- Space Bookings, Availability Calendar, Housekeeping — REMOVED per user request
- Real bi-directional outbound sync for review platforms (P1)
- Real outbound messaging for WhatsApp, Telegram, SMS — currently Sandbox mode (P1)

## Testing
- Iteration 49: 100% pass (51 tests) — Full regression
- Iteration 50: 100% pass (39 tests) — Chatlyn competitor features
- Iteration 51: 100% pass (30 tests) — Guest Satisfaction Surveys
