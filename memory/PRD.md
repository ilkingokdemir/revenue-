# MyHotelBox — Product Requirements Document

## Overview
Full-suite hotel PMS + POS + Payments + Accounting. Competitive with Mews, Cloudbeds, M3, Chatlyn, Prostay, Toast, Lightspeed.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 (Emergent) | Stripe | Resend | reportlab | httpx

## Complete Module List

### Dashboard — Financial KPIs (RevPAR, ADR, NPS, AR), Action Required, GSS, Activity Feed
### Booking Engine — 10 templates, Stripe checkout, 9 branches, 45 rooms, Multi-lang/currency, AI Concierge
### Guest Messaging (Chatlyn level) — Unified Inbox, AI, Notes, Snooze, Translate, Analytics, Webchat, Contact Lists, Real outbound
### Guest Satisfaction Surveys — Public NPS page, 6 categories, analytics, auto-tag, alerts
### Review Hub — 14 platforms, AI responses, Real outbound sync

### Hotel POS (Prostay/Toast level)
- 6 Outlets, 37 Menu Items, 10 Categories
- Dine In / Takeaway / Room Service / QR Self-Order / Kiosk
- AI-Powered Upselling (GPT-5.2), Self-Service Kiosk Mode (dark theme)
- Kitchen Display, Table Management, Split Billing, Room Charging
- Shift Management, Happy Hour Pricing, Digital Receipts, Guest Preferences, Loyalty Points
- POS Reports, Auto-linked to Accounting + Stock

### Payment Gateway (Cloudbeds level — iter 58)
- **Stripe Checkout** for Bookings and POS orders
- **Payment Status Tracking** — Real-time status check from Stripe
- **Stripe Webhook Handler** — Auto-processes successful payments
- **Payment Transactions** — Full history with filters (status, type)
- **Payment Dashboard** — Processed/Pending/Failed totals, success rate, daily trend, by type/method
- **Payment Settings** — Toggle Stripe/Cash/Room Charge/Contactless, tipping config, accepted cards, default currency
- **Auto-Accounting** — Successful payments auto-create income entries
- **Auto-Booking Update** — Paid bookings marked as confirmed

### Hotel Accounting (19 tabs + Bank Recon)
### Stock Management (11 tabs, 128-item catalog)
### Guest Experience — Profiles + Timeline, Guest App, Digital Keys, Campaigns, Surveys
### Automation, Channel Settings, Connections, Staff Performance

## Public Pages (No Auth): /survey, /qr-order, /kiosk, /guest-portal, /booking, /widget
## Sidebar: Dashboard | Review Hub | Booking Engine | Guest Experience | Operations (Stock, Accounting, POS, Payment Gateway) | Guest Messaging | Connections | Settings
## Architecture: 25 route files in /backend/routes/
## Testing: iter 49-58, 300+ total tests, all 100% pass
