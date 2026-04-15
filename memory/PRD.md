# My Hotel Box - Complete Hotel Management Platform

## All Modules (18 total)

### Revenue & Analytics
- **Dashboard**: KPIs (RevPAR, ADR), Timeline, Occupancy gauge, Revenue chart, Housekeeping widget
- **Occupancy Forecast**: 30/60/90-day forecast, bar chart, daily breakdown table
- **Accounting**: 18 tabs, Bank Reconciliation, PDF Invoices

### Front Office
- **Bookings**: Room management, Calendar view, booking list, Pay Link
- **Night Audit**: 5-check wizard, revenue/occupancy report, Complete & Close Day
- **Guest Profiles**: Rich detail, history, spending, preferences, tags, notes, loyalty tiers

### Guest Experience
- **Guest Journey**: Pre-arrival registration (4-step form), ID upload, T&C acceptance, welcome pack emails, in-stay satisfaction checks, feedback collection, admin panel with stats/table/send-link dialog
- **Loyalty Program**: Points, 4 tiers (Standard→Platinum), 8 rewards, earn/redeem, auto-upgrade
- **Campaigns**: 6 email templates, 8 audience segments, scheduling, template variables
- **Surveys / NPS**: Customizable surveys, public guest page

### Operations
- **Housekeeping**: Room Board, Task Management, Maintenance Requests
- **Duty Logbook**: Shift notes, incidents, VIP tracking, shift handovers
- **Stock / F&B**: Inventory, POS deduction, auto purchase orders

### F&B / Revenue
- **Point of Sale**: Premium terminal, modifiers, split bill, kitchen, stock deduction
- **Payment Gateway**: Stripe, iyzico, PayTR, Guest Portal, Reminders

### Communications
- **Messaging**: WhatsApp, Telegram, SMS (real API), AI translate, auto-reply
- **Review Hub**: Multi-platform, AI responses, sentiment analysis

### Administration
- **Admin Panel**: Roles & Permissions (14×6), Module Settings, Auto Purchase Orders

## Architecture
- React + Tailwind + Shadcn UI (frontend)
- FastAPI + MongoDB (backend)
- 3rd party: OpenAI GPT-5.2, Resend, Twilio, Stripe, iyzico, PayTR, WhatsApp/Telegram webhooks

## Testing: 72 iterations, all passing

## Upcoming Tasks
- iPad/Kiosk-optimized UI for on-site registration (P1)
- Richer configurable city/hotel info in welcome emails (P1)
- WhatsApp/SMS delivery channel for satisfaction checks (P2)
