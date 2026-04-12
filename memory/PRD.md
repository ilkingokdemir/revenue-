# MyHotelBox — Product Requirements Document

## Overview
Hotel management software (www.myhotelbox.com) — Booking Engine + Review Hub + Guest Messaging + Automation + Full Accounting. Competitive with Mews, Cloudbeds, eviivo, HiJiffy, Bookboost, Duve, Chatlyn, **M3 Accounting**.

## Tech Stack
React + Tailwind + Shadcn UI | FastAPI + MongoDB | GPT-5.2 (Emergent Key) | Stripe | Resend

## Completed Features

### Dashboard Home — iter 38
- Today's Snapshot, Revenue Widgets, Messaging/Review Stats, Activity Feed, Automation Status, Quick Actions, Action Required Panel

### Booking Engine — Core
- 10 templates, Stripe + Pay-at-hotel, 9 branches, 45 room types, Resend emails
- Multi-Language (12+RTL), Multi-Currency (18), Promo Codes, Add-ons, Smart Upsells, AI Concierge

### Guest Messaging Hub (Chatlyn Parity — iter 50)
- Unified Inbox (WhatsApp/Telegram/Email/SMS/OTA/Webchat), AI Replies, Quick Templates, FAQ Bot
- Internal Notes, Conversation Snooze, 1-Click Translate, Guest Booking Sidebar
- Conversation Analytics (heatmap, FRT, resolution), Webchat Widget Configurator, Contact Lists

### Guest Satisfaction Surveys (NPS — iter 51)
- NPS + 6 category ratings, Email/WhatsApp delivery, auto-send after checkout
- Public survey page, analytics dashboard, low-score alerts, guest profile auto-tagging

### Hotel Accounting (M3 Competitor Level — iter 52)
**Original features:**
- P&L Statement (by category, department), Income & Expense CRUD, USALI Chart of Accounts
- Invoicing (AR/AP) with VAT, Budget vs Actual, 6-Month Trends, Booking Revenue Sync, CSV Export

**10 New Features (iter 52):**
- **AR Aging Report** — 30/60/90/120+ day overdue receivable tracking with colored distribution bars
- **AP Aging Report** — Same for supplier payables
- **Daily Revenue Report (Night Audit)** — Daily room revenue + F&B + expenses + payments + 7-day bar chart
- **Cash Flow Statement** — Operating (revenue/expenses/AR/AP) + Investing (capex) + Financing
- **Payment Tracking** — Record received/made payments with 7 methods (bank, card, cash, cheque, online), links to invoices, auto-updates invoice status & amount_paid
- **Journal Entries (General Ledger)** — Double-entry bookkeeping with debit/credit balance validation, void support
- **Balance Sheet** — Assets (cash + AR), Liabilities (AP + VAT), Equity with balanced check
- **Revenue Forecasting** — 3-month projections based on confirmed bookings + historical average + trend, confidence levels
- **Recurring Invoices** — Weekly/monthly/quarterly auto-generation with start/end dates, enable/disable
- **Audit Trail** — Timestamped log of all accounting actions with user, entity, before/after values

**Total: 18 tabs** — P&L, Night Audit, Income, Expenses, Invoices, Payments, Journal, AR Aging, AP Aging, Cash Flow, Balance Sheet, Forecast, VAT, Recurring, Trends, Budget, CoA, Audit Trail

### Operations
- **Stock Management (Apicbase-level)** — 13 categories, recipes, COGS, Menu Engineering, Par Levels, Allergens, 11 tabs
- **Hotel Accounting (M3-level)** — 18 tabs (see above)

### Other Modules
- Review Hub (14 platforms, AI responses, analytics, competitor benchmarking)
- Automation Engine (6 journey rules)
- Channel Settings (WhatsApp, Telegram, SMS, Email)
- Guest Experience (Profiles/CRM, Guest App, Digital Keys, Campaigns, Surveys/NPS)
- Connections (Setup Wizard, Webhooks, Sync Logs, Integration Guide)
- Staff Performance Dashboard, Guest Satisfaction Score

### Infrastructure
- JWT auth (admin/manager/receptionist), white-label branding, webhooks

## Code Architecture
```
backend/routes/
├── accounting.py           # P&L, Income, Expenses, Invoices, VAT, Trends, Budget, CoA, Export
├── accounting_advanced.py  # AR/AP Aging, Night Audit, Cash Flow, Payments, Journal, Balance Sheet, Forecast, Recurring, Audit Trail
├── messaging.py + messaging_advanced.py
├── surveys.py              # Guest Satisfaction Surveys
├── (14 other route files)
```

## Sidebar Structure
- Dashboard | Review Hub | Booking Engine | Guest Experience (+ Surveys/NPS) | Operations (Stock, Accounting) | Guest Messaging | Connections | Settings

## Backlog
- Dynamic Pricing, Channel Manager, Drag-and-drop Calendar — NOT building (legacy)
- Space Bookings, Availability Calendar, Housekeeping — REMOVED per user request
- Real bi-directional outbound sync for review platforms (P1)
- Real outbound messaging for WhatsApp/Telegram/SMS — Sandbox mode (P1)

## Testing
- iter 49: 100% (51 tests) | iter 50: 100% (39 tests) | iter 51: 100% (30 tests) | iter 52: 100% (46 tests)
