# MyHotelBox — Product Requirements Document

## Overview
Full-suite hotel management PMS with POS. Competitive with Mews, Cloudbeds, M3, Chatlyn, Duve, Apicbase, Lightspeed.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 | Stripe | Resend | reportlab | httpx

## Modules

### Dashboard Home — Financial KPIs (RevPAR, ADR, NPS, AR), Action Required, GSS
### Booking Engine — 10 templates, Stripe, 9 branches, 45 rooms, Multi-lang/currency, AI Concierge
### Guest Messaging (Chatlyn) — Unified Inbox, AI, Notes, Snooze, Translate, Analytics, Webchat, Contact Lists, Real outbound
### Guest Satisfaction Surveys (NPS) — Public survey page, analytics, auto-tag, alerts
### Review Hub — 14 platforms, AI responses, Real outbound sync (Google/Booking.com/TripAdvisor)

### Hotel POS (NEW — iter 55)
- **6 Outlets**: Restaurant, Bar & Lounge, Room Service, Pool Bar, Spa, Gift Shop
- **37 Menu Items** across 10 categories (Starters, Mains, Desserts, Soft Drinks, Hot Drinks, Wine, Beer, Cocktails, Spa, Room Service)
- **Order Management**: Create orders with table/room/guest, quantity adjustments, notes
- **3 Order Types**: Dine In, Takeaway, Room Service
- **Payment Processing**: Card, Cash, Room Charge, Contactless + tip %
- **Kitchen Display System (KDS)**: Real-time order queue (new → preparing → ready)
- **Table Management**: Visual table grid showing available/occupied + active order details
- **Split Billing**: Equal split or by-item
- **Room Charging**: Charges posted to guest room folio
- **Shift Management**: Open/close till with cash counts, expected vs actual cash, sales by method
- **POS Reports**: Daily revenue, gross margin, avg check, top items, by outlet, by server, hourly breakdown
- **Linked to Accounting**: Payment creates income_entry automatically
- **Linked to Stock**: Order deducts stock for stock-linked items

### Hotel Accounting (19 tabs + Bank Recon — M3 level)
- P&L, Income, Expenses, Invoicing + PDF Download, VAT, Budget, Trends, USALI CoA, Export
- AR/AP Aging, Night Audit, Cash Flow, Payments, Journal Entries, Balance Sheet, Forecast
- Recurring Invoices, Audit Trail, Bank Reconciliation
### Operations — Stock Management (Apicbase-level, 11 tabs, 128-item catalog) + POS
### Guest Experience — Profiles/CRM + Timeline, Guest App, Digital Keys, Campaigns, Surveys/NPS
### Automation Engine, Channel Settings, Connections, Staff Performance

## Sidebar: Dashboard | Review Hub | Booking Engine | Guest Experience | Operations (Stock, Accounting, **POS**) | Guest Messaging | Connections | Settings
## Architecture: 22 route files in /backend/routes/ (added pos.py)
## Testing: iter 49-55, all 95-100% pass (250+ total tests)
## Backlog: Dynamic Pricing/Channel Manager NOT building (legacy). Space Bookings/Housekeeping REMOVED.
