# My Hotel Box - Complete Hotel Management Platform

## 68+ Modules | Mobile Responsive | 127 Test Iterations (100%)

### NEW (Iter 127): P1 Operations — Shift Scheduler, Reception Report, Pass Over Duties

**Shift Scheduler (weekly Gantt)**
- Weekly grid with 7-day columns + staff rows (receptionist, housekeeper, maintenance)
- Role badges + daily rates (£50/£80/£100), role filter tabs
- Presets: morning 07-15, afternoon 12-20, evening 15-23, night 23-07, full 09-17
- Inline preset picker on empty cells; week navigation; Publish All, Approve All, Clear Week
- Backend: `GET/POST /api/operations/shifts/{pid}`, `/assign`, `/bulk-publish`, `/clear-week`

**Reception Report**
- 5 KPI cards (Bookings Created, Check-ins, Check-outs, Cancellations, Routine Runs)
- 4 detail tables with 7-day default range + date inputs
- Backend: `GET /api/operations/reception-report/{pid}?start=&end=`

**Pass Over Duties (shift handovers)**
- Priority (critical/high/normal/low) + category (general/maintenance/guest/housekeeping/reception/finance) + shift tags
- Mentions: pick staff from team roster; acknowledgement trail with user+timestamp
- Status filter tabs (open/acknowledged/archived/all), priority filter
- Admin/manager archive + delete; all staff can create + acknowledge
- Backend: `GET/POST /api/operations/pass-over/{pid}`, `/{id}/acknowledge`, `/{id}/archive`, `DELETE /{id}`

### Previously Shipped (Iter ≤126)
**Enhanced Dashboard (replaces old):**
- 5 color-coded KPI cards (In-House, Occupancy, Arrivals, Departures, Daily Income)
- Financial Overview table (Previous/This/Next Month + Same Month Last Year) — Gross, Room Rev, ADR, Commission, Net, Bookings
- 7-Day Revenue bar chart with total + daily avg
- Staff On Duty widget, Housekeeping completion % widget
- Recent Bookings (last 24h) + Stayovers + Pending Payment counts

**Reports Hub (4 reports):**
- Overview: 5 KPIs + Revenue by Source + Availability by Category
- Revenue Report: Daily timeline chart + breakdown by category/source
- Occupancy Report: Daily table (color-coded) + by-category bars + peak day
- Commission Report: Per-source commission table (gross, rate%, commission, paid, pending, net)

**Finance P&L Dashboard:**
- Operating Ledger (costs vs revenue side-by-side) with paid/accrued badges
- Operating Profit/Loss with margin %
- 6-Month Financial Trend (grouped bar chart: revenue, costs, profit)

### Premium Differentiators
- AI Weekly Revenue Digest (GPT-5.2), AI Upsell Engine, Competitor Rate Automation

### Complete Feature Set (68+ modules)
Core PMS | Revenue (38+ sub-modules) | Booking Engine | Guest Experience | Finance | Operations (shifts, handovers, reception) | AI | Mobile

## Upcoming (P1 Backlog)
- Compliance Register & Categories
- Laundry Management (Dispatch, Deliveries, Stock) + Contracts
- Maintenance Issues Kanban
- Payroll Runs, Adjustments, Cash Advances
- Expense Categories & Recurring Expenses
- User Contracts & granular Roles/Permissions
- System Feedback & internal Bug Tracker

## Future (P2)
- A/B Experiments & Pricing Playbooks
- Profit OS (ContributionPAR) & Distribution Cockpit
- Integrations Hub (PMS syncing UI)
- Rate Structure / OTA mapping configurations

## Refactor (low priority)
- Split `/app/frontend/src/components/dashboard/` (90+ files) into `/operations`, `/revenue`, `/finance`, `/guest`

## Architecture: React + Tailwind + Shadcn, FastAPI + MongoDB, GPT-5.2, Stripe, Resend
## Testing: 127 iterations, 100% pass rate
