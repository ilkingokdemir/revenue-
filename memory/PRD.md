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
- **Guest Journey**: Complete module with:
  - Pre-arrival registration (4-step: details, ID upload w/ camera+gallery, T&C, complete)
  - Share modal (6 options: Copy Link, Email, SMS, WhatsApp, Print, Save QR)
  - iPad/Kiosk self check-in page (welcome screen, booking search, embedded registration, 60s auto-reset)
  - Configurable welcome email info (hotel policies, city info, custom message per property)
  - In-stay satisfaction checks via Email + SMS + WhatsApp
  - Admin panel with 4 tabs: Registrations, Satisfaction, Welcome Info, Kiosk Setup
- **Loyalty Program**: Points, 4 tiers, 8 rewards, earn/redeem, auto-upgrade
- **Campaigns**: 6 email templates, 8 audience segments, scheduling
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
- **Admin Panel**: Roles & Permissions (14x6), Module Settings, Auto Purchase Orders

## Architecture
- React + Tailwind + Shadcn UI (frontend)
- FastAPI + MongoDB (backend)
- 3rd party: OpenAI GPT-5.2, Resend, Twilio, Stripe, iyzico, PayTR, WhatsApp/Telegram webhooks
- QR code: qrcode.react@4.2.0

## Testing: 75 iterations, all passing
