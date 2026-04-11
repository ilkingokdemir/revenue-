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

### Admin Panels
- Space Bookings management, AI Concierge analytics

### Infrastructure
- JWT auth (admin/manager/receptionist), white-label branding, outbound webhooks

## Sidebar Structure
- Dashboard (home icon — default landing)
- Review Hub: Reviews, Analytics, Response Templates, Approvals, Alerts, Reports
- Booking Engine: Rooms & Bookings, Space Bookings, Website Templates, Customize, Promos, Add-ons, Policies
- Guest Messaging: Unified Inbox, Automation, Channel Settings, AI Concierge
- Connections: Integrations, API Connection, Webhooks

## Backlog
- P1: Real bi-directional outbound sync for review platforms
- P2: Extract server.py (~6,400 lines) into /routes/ modules
- P3: Real-time availability calendar integration
- Note: Channel Manager already exists on myhotelbox.com — NOT building
