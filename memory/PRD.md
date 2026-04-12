# MyHotelBox — Product Requirements Document

## Overview
Full-suite hotel management PMS. Competitive with Mews, Cloudbeds, M3, Chatlyn, Duve, Apicbase.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 | Stripe | Resend | reportlab | httpx

## Modules & Features

### Dashboard Home
- Today's Snapshot (check-ins/outs, guests, occupancy, messages, rating)
- **Financial KPIs**: RevPAR, ADR, Revenue MTD, Net Profit MTD, NPS Score, AR Outstanding
- Quick Actions, Action Required panel (7 alert types), Guest Satisfaction Score (GSS)

### Booking Engine — 10 templates, Stripe, 9 branches, 45 rooms, Multi-lang/currency, AI Concierge
### Guest Messaging Hub (Chatlyn level) — Unified Inbox, AI Replies, Notes, Snooze, Translate, Analytics, Webchat Widget, Contact Lists, Real outbound delivery (WhatsApp/Telegram/Email)
### Guest Satisfaction Surveys (NPS) — Public survey page, 6 categories, analytics, auto-tag, alerts
### Review Hub — 14 platforms, AI responses, approval workflow, Real outbound reply sync (Google/Booking.com/TripAdvisor)

### Hotel Accounting (19 tabs — M3 level)
- P&L, Income, Expenses, Invoicing with **PDF Download**, VAT, Budget, Trends, USALI CoA, Export
- AR/AP Aging (30/60/90/120+), Night Audit, Cash Flow, Payments (7 methods), Journal Entries (GL)
- Balance Sheet, Revenue Forecasting, Recurring Invoices, Audit Trail, **Bank Reconciliation**

### Operations — Stock Management (Apicbase-level, 11 tabs, 128-item catalog)
### Guest Experience — Profiles/CRM with **Timeline**, Guest App, Digital Keys, Campaigns, Surveys/NPS
### Automation Engine — 6 journey rules | Channel Settings | Connections | Staff Performance

## Architecture: 21 route files in /backend/routes/
## Sidebar: Dashboard | Review Hub | Booking Engine | Guest Experience | Operations | Guest Messaging | Connections | Settings
## Testing: iter 49-54 all 100% pass (51+39+30+46+32+23 = 221 total tests)
## Backlog: Dynamic Pricing/Channel Manager NOT building (legacy). Space Bookings/Housekeeping REMOVED.
