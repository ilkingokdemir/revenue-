# MyHotelBox — Product Requirements Document

## Overview
Full-suite hotel PMS + POS. Competitive with Mews, Cloudbeds, M3, Chatlyn, Duve, Apicbase, Lightspeed, Prostay.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 | Stripe | Resend | reportlab | httpx

## Modules

### Dashboard — Financial KPIs (RevPAR, ADR, NPS, AR), Action Required, GSS
### Booking Engine — 10 templates, Stripe, 9 branches, 45 rooms, Multi-lang/currency, AI Concierge
### Guest Messaging (Chatlyn) — Unified Inbox, AI, Notes, Snooze, Translate, Analytics, Webchat, Contact Lists, Real outbound
### Guest Satisfaction Surveys — Public NPS survey page, 6 categories, analytics, auto-tag, alerts
### Review Hub — 14 platforms, AI responses, Real outbound sync (Google/Booking.com/TripAdvisor)

### Hotel POS (Prostay Competitor Level — iter 55-56)
- **6 Outlets**: Restaurant, Bar & Lounge, Room Service, Pool Bar, Spa, Gift Shop
- **37 Menu Items** across 10 categories with cost tracking
- **Order Management**: Dine In / Takeaway / Room Service + QR Self-Order
- **Payment**: Card, Cash, Room Charge, Contactless + tip calculator
- **Kitchen Display**: Real-time order queue (new → preparing → ready)
- **Table Management**: Visual grid with live status
- **Split Billing**: Equal or by-item
- **Room Charging**: Posts to guest folio
- **Shift Management**: Open/close till, cash reconciliation
- **QR Code Guest Ordering**: Public mobile page — guests scan, browse, order from phone
- **Digital Receipts**: Email receipts via Resend
- **Happy Hour / Dynamic Pricing**: Time-based discounts per outlet/category
- **Guest Preferences**: Dietary, allergens, favorites stored per guest
- **Loyalty Points**: Earn/redeem, 4 tiers (standard/silver/gold/platinum), auto-upgrade
- **POS Reports**: Revenue, margin, avg check, top items, by outlet/server, hourly
- **Linked to Accounting**: Payments auto-create income entries
- **Linked to Stock**: Orders auto-deduct inventory

### Hotel Accounting (19 tabs + Bank Recon)
### Operations — Stock Management (11 tabs, 128-item catalog) + POS
### Guest Experience — Profiles + Timeline, Guest App, Digital Keys, Campaigns, Surveys
### Automation, Channel Settings, Connections, Staff Performance

## Architecture: 23 route files in /backend/routes/
## Sidebar: Dashboard | Review Hub | Booking Engine | Guest Experience | Operations | Guest Messaging | Connections | Settings
## Testing: iter 49-56, 270+ total tests, all 95-100% pass
