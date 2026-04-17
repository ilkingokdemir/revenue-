# My Hotel Box - Complete Hotel Management Platform

## 70+ Modules | Mobile Responsive | 128 Test Iterations (100%)

### NEW (Iter 128): Compliance Register + Laundry Management

**Compliance Register**
- 7 default categories: Fire Safety, Food Hygiene, H&S, Licensing, Insurance, Data Protection, Staff Training
- Status auto-computed: compliant / expiring_soon (≤30d) / overdue / action_needed / N/A
- Category pills with badge counts for items needing attention
- KPI row (Total, Compliant, Expiring ≤30d, Overdue, Action Needed)
- Full CRUD, "Mark as Checked" one-click action, evidence URL links, frequency (weekly/monthly/quarterly/annual/once)
- Backend: `/api/compliance/categories/{pid}`, `/api/compliance/items/{pid}[?category=&status=]`, `{id}/check`, PUT/DELETE

**Laundry Management**
- 3 tabs: Dispatches / Stock / Contracts
- 11-item default catalog (sheets, pillow cases, towels, napkins, etc.)
- Dispatch flow auto-adjusts stock (clean→in_transit on send; in_transit→clean on receive)
- Stock ledger with on_hand_clean / dirty / in_transit / damaged columns (inline edit)
- Contracts with rate cards, pickup schedules, vendor contact info
- KPIs: Items Sent YTD, Sent, Received, Active Contracts, Total Spend
- Backend: `/api/laundry/dispatches/{pid}` (list/create/receive), `/api/laundry/stock/{pid}[/{item_id}]`, `/api/laundry/contracts/{pid}[/{id}]`, `/api/laundry/catalog`

### Iter 127: Shift Scheduler + Reception Report + Pass Over Duties
- Weekly Gantt grid with role filters, presets, bulk publish/approve/clear-week
- Reception KPI dashboard with 4 detail tables
- Shift handovers with priority/category/mentions/acknowledgements

### Previously Shipped (≤Iter 126)
**Enhanced Dashboard, Reports Hub, Finance P&L**, AI Weekly Digest (GPT-5.2), AI Upsell Engine, Competitor Rate Automation, Demand Radar, Compset, Price Alerts, Gantt Booking Calendar, AI Auto-Respond, OTA Availability Sync, SEO Meta Tags, Digital Check-in/Folio, Displacement Analysis, LOS Optimizer, Mobile Companion, and 65+ additional modules.

### Complete Feature Set (70+ modules)
Core PMS | Revenue (38+ sub-modules) | Booking Engine | Guest Experience | Finance | Operations (shifts, handovers, reception, compliance, laundry) | AI | Mobile

## Upcoming (P1 Backlog)
- Payroll Runs, Adjustments, Cash Advances, Earned Salaries
- Expense Categories & Recurring Expenses
- User Contracts & granular Roles/Permissions
- System Feedback & internal Bug Tracker

## Future (P2)
- A/B Experiments & Pricing Playbooks
- Profit OS (ContributionPAR) & Distribution Cockpit
- Integrations Hub (PMS syncing UI)
- Rate Structure / OTA mapping configurations

## Refactor (low priority)
- Split `/app/frontend/src/components/dashboard/` (92+ files) into `/operations`, `/revenue`, `/finance`, `/guest`

## Architecture: React + Tailwind + Shadcn, FastAPI + MongoDB, GPT-5.2, Stripe, Resend
## Testing: 128 iterations, 100% pass rate
