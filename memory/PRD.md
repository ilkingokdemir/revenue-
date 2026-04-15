# My Hotel Box - Complete Hotel Management Platform

## 22+ Modules + Multi-Language (7 languages) + Mobile Responsive

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
- **Operations Hub** (7 modules):
  1. **Reception Report**: KPI cards, date filters, detail tables
  2. **Routine Templates**: Create/edit/delete with steps, branch/role/shift targeting
  3. **Routine History**: Stats cards, filterable table with progress bars
  4. **Pass Over Duties**: Shift handover notes with type/priority/status
  5. **Laundry Management**: Action cards, CRUD, status tracking pipeline
  6. **Compliance Checks**: Schedule inspections with checklists
  7. **Shift Scheduler**: Weekly calendar, staff management, bulk actions, payroll
- Duty Logbook, Stock/F&B

### Notification Centre (NEW)
- **In-app notifications** with bell icon + unread badge
- **Auto-generated alerts**: SLA breaches, pending handovers, compliance due, incomplete routines
- **Filter tabs**: All, Unread, SLA, Handover, Compliance
- **Mark as read / Mark all read**
- Backend: `/api/notifications` CRUD + `/api/notifications/generate-check`

### Mobile Responsive (NEW)
- **Mobile top bar** with hamburger menu + app name + notification bell
- **Slide-in sidebar** with overlay + close button
- **All navigation** accessible on phone/tablet
- **Auto-close** sidebar on navigation item tap

### F&B / Revenue
- Point of Sale, Payment Gateway (Stripe, iyzico, PayTR)

### Communications
- Messaging (WhatsApp, Telegram, SMS), Review Hub

### Administration
- Admin Panel (Roles & Permissions 14x6)

## Testing: 83 iterations, all passing (100%)

## Architecture
- Backend: FastAPI + MongoDB
- Frontend: React + Tailwind CSS + Shadcn UI
- Routes: operations.py, shifts.py, notifications.py + 20 other route files
- Key components: OperationsHubPanel.js, NotificationBell.js

## Upcoming Tasks
- My Tasks Dashboard (P2) - personalized daily to-do list
- Lost & Found Module (P2)
- Event/Meeting Room Management (P2)
