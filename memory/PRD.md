# My Hotel Box - Complete Hotel Management Platform

## 72+ Modules | Mobile Responsive | 129 Test Iterations (100%)

### NEW (Iter 129): Payroll Management + Expense Management

**Payroll Management (4-tab UI)**
- **Earned Salaries** — auto-computed from `shifts` collection × ROLE_RATES (receptionist £50, housekeeper £80, maintenance £100, manager £120, admin £150 per day)
- **Payroll Runs** — monthly snapshot with lifecycle draft → approved → paid; auto-marks linked cash advances as repaid on "mark paid"
- **Adjustments** — bonus/overtime/commission/benefit (+) or deduction/tax (−); aggregated into Net
- **Cash Advances** — request → approve/reject → mark repaid; outstanding total deducted from next earnings
- KPIs: Staff, Gross, Adjustments, Advances, Net Payable
- Backend: `/api/payroll/earnings`, `/runs[/{id}/approve|mark-paid]`, `/adjustments`, `/advances[/{id}/approve|reject|mark-repaid]`

**Expense Management (3-tab UI)**
- **Expenses** — 9 default categories (utilities, supplies, maintenance, marketing, salaries, rent, food, tech, other), vendor/method/receipt URL, category-color pills with monthly spend
- **Recurring** — templates with weekly/biweekly/monthly/quarterly/annual frequency, auto-advance `next_due`, "Post Now" on due items, "Run All Due" batch, due count badge in header
- **Categories & Budgets** — monthly budget per category, usage bar (green <80% / amber 80-100% / red >100%)
- KPIs: Total Spent, Transactions, Avg/Expense, Recurring count
- Backend: `/api/expenses[/{id}]`, `/expenses/categories/{pid}[/{cat}/budget]`, `/expenses/recurring[/{id}/post]`, `/run-due`

### Iter 128: Compliance Register + Laundry Management
### Iter 127: Shift Scheduler + Reception Report + Pass Over Duties
### Previously (≤Iter 126): Enhanced Dashboard, Reports Hub, Finance P&L, AI Weekly Digest, AI Upsell Engine, Competitor Rate Automation, Demand Radar, Compset, Price Alerts, Gantt Booking Calendar, AI Auto-Respond, OTA Sync, SEO Meta Tags, Digital Check-in/Folio, Displacement Analysis, LOS Optimizer, Mobile Companion + 65 more.

## Complete Feature Set (72+ modules)
Core PMS | Revenue (38+ sub-modules) | Booking Engine | Guest Experience | **Finance (Payroll, Expenses, P&L, Accounting, POS)** | **Operations (shifts, handovers, reception, compliance, laundry, maintenance)** | AI | Mobile

## Upcoming (P1 Backlog)
- User Contracts & granular Roles/Permissions
- System Feedback & internal Bug Tracker

## Future (P2)
- A/B Experiments & Pricing Playbooks
- Profit OS (ContributionPAR) & Distribution Cockpit
- Integrations Hub (PMS syncing UI)
- Rate Structure / OTA mapping configurations

## Refactor (low priority)
- Split `/app/frontend/src/components/dashboard/` (94+ files) into `/operations`, `/revenue`, `/finance`, `/guest`

## Architecture: React + Tailwind + Shadcn, FastAPI + MongoDB, GPT-5.2, Stripe, Resend
## Testing: 129 iterations, 100% pass rate
