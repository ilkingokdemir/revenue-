# MyHotelBox — Product Requirements Document

## Overview
Full-suite hotel PMS + POS + Payments + Card Terminals + Accounting. Competitive with Mews, Cloudbeds, M3, Chatlyn, Prostay, Toast, Lightspeed.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 (Emergent) | Stripe (Checkout + Terminal) | Resend | reportlab | httpx

## Complete Module List

### Dashboard — Financial KPIs, Action Required, GSS, Activity Feed
### Booking Engine — 10 templates, Stripe checkout, 9 branches, 45 rooms, Multi-lang/currency, AI Concierge
### Guest Messaging (Chatlyn level) — Unified Inbox, AI, Notes, Snooze, Translate, Analytics, Webchat, Contact Lists, Real outbound
### Guest Satisfaction Surveys — Public NPS page, analytics, auto-tag, alerts
### Review Hub — 14 platforms, AI responses, Real outbound sync

### Hotel POS — 6 Outlets, 37 Menu Items, AI Upselling, Kitchen Display, Table Management, Split Billing, Room Charging, Shift Management, QR Ordering, Kiosk, Happy Hour, Receipts, Loyalty, Guest Preferences

### Payment Gateway (Cloudbeds level)
- Stripe Checkout (Bookings + POS), Webhook handler, Transaction dashboard
- Payment Settings (Stripe/Cash/Room Charge/Contactless/Tipping)

### Card Terminal Integration (NEW — iter 59)
- **Stripe Terminal** — Global: Creates PaymentIntent → sends to physical reader → guest taps card → auto-confirmed
- **iyzico** — Turkey #1: All Turkish banks, installments, virtual POS
- **PayTR** — Turkey: Virtual POS, SMS payment links
- **Device Management** — Register/manage card readers, status tracking
- **Quick-Pay** — One-click: POS order → terminal (amount auto-sent, no manual entry)
- **Quick-Pay Booking** — Same for hotel room checkout
- **Terminal Settings** — Switch providers, API credentials, tipping on terminal
- **Payment History** — All terminal transactions with status tracking
- **Auto-Accounting** — Successful terminal payments create income entries

### Hotel Accounting (19 tabs + Bank Recon)
### Stock Management (11 tabs, 128-item catalog)
### Guest Experience — Profiles + Timeline, Guest App, Digital Keys, Campaigns, Surveys
### Automation, Channel Settings, Connections, Staff Performance

## Public Pages: /survey, /qr-order, /kiosk, /guest-portal, /booking, /widget
## Sidebar: Dashboard | Review Hub | Booking Engine | Guest Experience | Operations (Stock, Accounting, POS, Payment Gateway) | Guest Messaging | Connections | Settings
## Architecture: 26 route files in /backend/routes/
## Testing: iter 49-59, 320+ total tests, all 100% pass
