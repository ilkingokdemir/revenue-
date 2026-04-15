# My Hotel Box - Complete Hotel Management Platform

## 22+ Modules + Multi-Language (7 languages)

### Multi-Language: English, Turkish, Spanish, Russian, Arabic (RTL), French, German

### Revenue & Analytics
- Dashboard (KPIs, widgets, timeline)
- Occupancy Forecast (30/60/90-day)
- Accounting (18 tabs, bank reconciliation)
- **Rate Manager**: Dynamic pricing — day-of-week multipliers, occupancy rules, seasons, 30-day calendar
- **Reports Centre**: Consolidated data across all modules, period filters, CSV export

### Front Office
- Bookings + **Online Booking Widget**: Public booking page, availability check, 4-step flow
- Night Audit (5-step wizard)
- Guest Profiles

### Guest Experience
- Guest Journey (registration, ID upload, T&C, welcome emails, satisfaction, kiosk, share 6 options)
- Loyalty Program, Campaigns, Surveys/NPS

### Operations
- Housekeeping + **Maintenance Integration**: One-tap creates maintenance issue with room, photos
- Maintenance: Kanban+Table, Priority/SLA, Before/After Photos, Job Timeline, Cost tracking, Recurring/Preventive
- **Operations Hub** (NEW - 7 modules):
  1. **Reception Report**: KPI cards (Bookings Created, Check-ins, Check-outs, Cancellations, Routine Runs), date filters, detail tables
  2. **Routine Templates**: Create/edit/delete templates with steps, branch/role/shift targeting, start routines
  3. **Routine History**: Stats cards, filterable/sortable table with progress bars, view/complete tasks
  4. **Pass Over Duties**: Shift handover notes with type/priority/status badges, search, create/resolve/delete
  5. **Laundry Management**: Action cards (Dispatch/Deliveries/Daily Usage/Stock), CRUD, status tracking (sent→in_progress→returned)
  6. **Compliance Checks**: Schedule safety/fire/health/electrical/hygiene inspections with checklists, evidence uploads
  7. **Shift Scheduler**: Weekly calendar, staff management, role filters, add/delete shifts, bulk actions (Publish All, Mark Completed, Approve, Clear Week, Copy Week), payroll summary
- Duty Logbook, Stock/F&B

### F&B / Revenue
- Point of Sale, Payment Gateway (Stripe, iyzico, PayTR)

### Communications
- Messaging (WhatsApp, Telegram, SMS), Review Hub

### Administration
- Admin Panel (Roles & Permissions 14x6)

## Testing: 82 iterations, all passing (100%)

## Architecture
- Backend: FastAPI + MongoDB
- Frontend: React + Tailwind CSS + Shadcn UI
- Routes: /app/backend/routes/operations.py (Reception, Routines, Handover, Laundry, Compliance)
- Routes: /app/backend/routes/shifts.py (Staff, Entries, Bulk Actions, Payroll)
- Panel: /app/frontend/src/components/dashboard/OperationsHubPanel.js (7 tabbed modules)

## Upcoming Tasks
- Staff Mobile Optimization (P1)
- Notification Centre (P1)

## Future/Backlog
- Lost & Found Module (P2)
- Event/Meeting Room Management (P2)
