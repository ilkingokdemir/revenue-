# My Hotel Box - Complete Hotel Management Platform

## 74+ Modules | Mobile Responsive | 131 Test Iterations (100%)

### Iter 132: Integrations Marketplace — "Connect everything. Run anything."
- **124 integrations** across **17 categories** (OTAs, Payments, Channel Managers, Revenue, Messaging/CRM, AI, Reviews, Smart Locks, Accounting, POS/F&B, Analytics, Ops, Marketing, Productivity, Storage/CDN, Identity/SSO, Compliance)
- Real brand logos via Google Favicon service — no emojis, no letter initials
- Hero with live **Available / Connected / Coverage %** counters
- Search, category chips with per-category install counts, tabs (All / Connected / Featured)
- **Install / Toggle / Sync / Uninstall** with MongoDB `marketplace_installs` persistence
- Detail drawer with status, connected timestamp, last-sync timestamp, role-gated connect
- Endpoints: `GET /api/marketplace/catalog/{pid}`, `POST /install|toggle|sync`, `DELETE /uninstall` — all admin/manager gated
- Sidebar entry `marketplace-btn` in Connections section — coexists with existing Integrations panel

### Iter 131: Cash Flow AI Recommendations — **REMOVED per user request**
### Iter 130: Cash Flow Forecast — The CFO Dashboard

**Cash Flow Forecast**
- Period selector 30/60/90 days forward from today
- Configurable opening balance (debounced input)
- **Inflows**: confirmed future bookings (on check_in date) + recurring invoices
- **Outflows**: recurring expenses (on next_due) + manually-dated future expenses + payroll estimate (avg of last 3 approved/paid runs, posted on last day of each calendar month)
- **KPIs**: Opening, Total Inflows, Total Outflows, Ending Balance, Lowest Balance (with at-risk flag when negative)
- **Charts** (Recharts): Area chart of projected running balance with zero reference line; stacked bar of daily in/out
- **Events table**: Top 8 days by cash magnitude, expandable to see individual line items (booking name, recurring template, payroll estimate, expense)
- Endpoint: `GET /api/finance/cash-flow-forecast/{pid}?days=30|60|90&opening_balance=N` — single aggregator call, zero N+1

### Iter 129: Payroll + Expense Management
### Iter 128: Compliance Register + Laundry Management
### Iter 127: Shift Scheduler + Reception Report + Pass Over Duties
### Previously (≤Iter 126): Enhanced Dashboard, Reports Hub, Finance P&L, AI Weekly Digest (GPT-5.2), AI Upsell Engine, Competitor Rate Automation, Demand Radar, Compset, Price Alerts, Gantt Booking Calendar, AI Auto-Respond, OTA Sync, SEO Meta Tags, Digital Check-in/Folio, Displacement Analysis, LOS Optimizer, Mobile Companion + 65 more.

## Complete Feature Set (73+ modules)
Core PMS | Revenue (38+ sub-modules) | Booking Engine | Guest Experience | **Finance (Payroll, Expenses, P&L, Cash Flow Forecast, Accounting, POS)** | **Operations (shifts, handovers, reception, compliance, laundry, maintenance)** | AI | Mobile

## Upcoming (P1 Backlog)
- Contactless Guest Journey / Self-Service Kiosks (from Mews benchmark)
- Maintenance Issues (Kanban/Table tracking)
- User Contracts & granular Roles/Permissions
- System Feedback & internal Bug Tracker

## Future (P2)
- A/B Experiments & Pricing Playbooks
- Profit OS (ContributionPAR) & Distribution Cockpit
- Rate Structure / OTA mapping configurations
- Deprecate legacy IntegrationsPanel in favor of new Marketplace

## Refactor (low priority)
- Split `/app/frontend/src/components/dashboard/` (95+ files) into `/operations`, `/revenue`, `/finance`, `/guest`

## Architecture: React + Tailwind + Shadcn, FastAPI + MongoDB, GPT-5.2, Stripe, Resend
## Testing: 130 iterations, 100% pass rate
