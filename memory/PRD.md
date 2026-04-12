# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) — Full-suite PMS with Booking Engine, Review Hub, Guest Messaging, Automation, NPS Surveys, Stock Management, and Enterprise Accounting. Competitive with Mews, Cloudbeds, M3, Chatlyn, Duve, Apicbase.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 (Emergent Key) | Stripe | Resend | httpx (outbound APIs)

## Completed Modules

### Dashboard Home — Action Required panel, KPIs, Activity Feed, Quick Actions
### Booking Engine — 10 templates, Stripe, 9 branches, 45 room types, Multi-lang/currency, Promos, AI Concierge
### Guest Messaging Hub (Chatlyn Parity) — Unified Inbox, AI Replies, Notes, Snooze, Translate, Analytics, Webchat Widget, Contact Lists, **Real outbound delivery** (WhatsApp/Telegram/Email with delivery_status tracking)
### Guest Satisfaction Surveys (NPS) — Public survey page, 6 categories, analytics, auto-tag profiles, low-score alerts
### Review Hub — 14 platforms, AI responses, approval workflow, analytics, competitor benchmarking, **Real outbound reply sync** (Google/Booking.com/TripAdvisor API)
### Hotel Accounting (19 tabs — M3 level):
- P&L, Income, Expenses, Invoicing (AR/AP), VAT Report, Budget vs Actual, 6-Month Trends, USALI Chart of Accounts, CSV Export
- AR Aging (30/60/90/120+), AP Aging, Night Audit/Daily Revenue, Cash Flow Statement
- Payment Tracking (7 methods), Journal Entries (GL), Balance Sheet, Revenue Forecasting
- Recurring Invoices (weekly/monthly/quarterly), Audit Trail, **Bank Reconciliation** (import, auto-match, manual match, discrepancy tracking)
### Operations — Stock Management (Apicbase-level, 11 tabs, 128-item catalog)
### Guest Experience — Profiles/CRM, Guest App, Digital Keys, Campaigns, Surveys/NPS
### Automation Engine — 6 journey rules, template variables, logs
### Channel Settings — WhatsApp, Telegram, SMS, Email configuration
### Connections — Setup Wizard, Webhooks, Sync Logs, Integration Guide
### Staff Performance, Guest Satisfaction Score

## Code Architecture
```
backend/routes/ (20 files)
├── accounting.py + accounting_advanced.py + bank_reconciliation.py
├── messaging.py + messaging_advanced.py
├── surveys.py, reviews.py, bookings.py, automation.py
├── guest_profiles.py, campaigns.py, guest_app.py, smart_locks.py
├── dashboard.py, staff_performance.py, calendar_gss.py, setup_wizard.py
├── stock.py, connections.py, auth_routes.py, helpers.py
```

## Sidebar: Dashboard | Review Hub | Booking Engine | Guest Experience | Operations | Guest Messaging | Connections | Settings

## Backlog
- Dynamic Pricing, Channel Manager — NOT building (legacy)
- Space Bookings, Housekeeping — REMOVED per user request

## Testing: iter 49(51) | 50(39) | 51(30) | 52(46) | 53(32) — All 100% pass
