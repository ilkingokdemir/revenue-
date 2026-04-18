# My Hotel Box - Complete Hotel Management Platform

## 82+ Modules | Mobile Responsive | 142 Test Iterations (100%)

### Iter 143: Admin Reset Step — unlock onboarding documents
- Closes the loop on the iter-141 lockdown — admin can now reset any individual onboarding step when a staff member genuinely needs to correct a mistake
- **POST /api/staff-onboarding/{user_id}/reset/{passport|address|hmrc|contract}** (admin only)
  - passport/address: deletes the file on disk + unsets filename/path/url + flips `*_uploaded=false`
  - hmrc: unsets `hmrc_data` + flips `hmrc_submitted=false`
  - contract: unsets `contract_id` + flips `contract_signed=false` (doesn't touch staff_contracts)
- **Audit trail**: every reset pushes `{step, reset_by, reset_at}` to `staff_onboarding.reset_log`
- Admin UI: amber **RotateCcw** icon next to each document's download icon — shows window.confirm, then POST, toast + reload
- Rejects unknown step (400) and non-admin callers (403)
- After reset, staff can immediately re-upload / re-submit from their onboarding screen — locks release
- Tested iteration 142 (19/19 backend + frontend pass)

### Iter 142: Staff Onboarding Security Lockdown
User requirement: "When they fill when they on board staff they don't to be reach any document they upload and they fill they signed."
- **Server-side lockdown**:
  - `/staff-onboarding/me` **strips** filenames, URLs, paths, `hmrc_data` and `email_log` from staff-facing response
  - `upload/passport`, `upload/address`, `hmrc` POSTs return **400 "already submitted and locked"** on re-submission
  - New authenticated route `GET /api/uploads/onboarding/{filename}` requires `admin`|`manager` — registered **before** the public static mount so it takes precedence (401 unauth, 403 staff, 200 admin)
  - Path-traversal protection on the filename
- **Frontend lockdown**:
  - Upload buttons and "View uploaded document" links **removed** once a document is submitted
  - New simplified `UploadedChip` shows "{label} received · locked" — no filename, no link
  - Security disclaimer appears under each locked step
  - HMRC tab split: `tab-hmrc` (form, only when `!hmrc_submitted`) and `tab-hmrc-sealed` (big emerald success card, SUBMITTED & LOCKED badge) — the form is NEVER rendered again after first submit
- Admin detail drawer retains full access (all data, previews, downloads, email)
- Tested iteration 141 (23/23 backend + frontend pass)

### Iter 141: Download & Email Onboarding Documents
- Admin can now download **individual documents** or a **full ZIP bundle** of any staff member's onboarding pack
- Admin can **email the bundle** to any recipient(s) via Resend with selected attachments
- **New endpoints**:
  - `GET /api/staff-onboarding/{user_id}/download/{passport|address|hmrc}` — returns raw file (or generated PDF for HMRC)
  - `GET /api/staff-onboarding/{user_id}/download-bundle` — ZIP with up to 4 files (ID, address, HMRC PDF, contract reference)
  - `POST /api/staff-onboarding/{user_id}/email` — Resend-powered email with base64 attachments + audit log
- **HMRC PDF** generated on-the-fly with reportlab: HM Revenue & Customs header, sections mirroring 09/22 paper form (Personal / Statement / Loans / Declaration), coloured table rows, "Statement X applies" highlight
- **Admin UI enhancements**: indigo action bar atop the detail drawer with **ZIP bundle** + **Email documents** buttons; per-card download icons (eye-close-to-tick) only appear when that document exists
- **Email dialog**: Recipients (comma-sep), pre-filled subject, optional message, 3-way include checklist (each auto-disabled when staff hasn't uploaded that doc), Resend send with audit log
- **MOCKED**: Resend API key is a placeholder in preview env — real email returns 502 "API key is invalid" (expected; user sets valid key in production)
- Tested iteration 140 (19/19 backend + full frontend pass)

### Iter 140: HMRC Starter Checklist — Authentic HMRC 09/22 replica
- Rewrote the onboarding HMRC tab to mirror the official UK paper form the user uploaded
- **Section 1 · Personal details**: Last name, First names (with "Do not enter initials" helper), Sex radio (male/female as on birth certificate), DOB, Home address, Postcode, Country (new), NI number (now OPTIONAL per paper form), Employment start date
- **Section 2 · Employee statement decision tree**: Q8 another job? Q9 pension? Q10 recent payments? — **auto-computes Statement A/B/C** with blue banner showing which applies + plain-English explanation of the tax code implication
- **Section 3 · Student loans**: Q11/Q12/Q13 conditional flow with multi-tick Plan 1 / Plan 2 / Plan 4 / Postgraduate
- **Section 4 · Declaration**: Full name (auto-uppercase), Date (pre-filled today), script-font typed signature, confirmation checkbox
- Backend validates all new required fields + sex/statement enums + declaration_confirmed; stores backwards-compat aliases (first_name, gender, address) so existing admin view keeps working
- Admin detail drawer updated to display every new HMRC field
- Fixed a rules-of-hooks bug (computedStatement useEffect moved above early return)
- Tested iteration 139 (29/29 backend + full frontend pass)

### Iter 139: Admin Onboarding Review Panel
- Admin/manager-only sidebar entry 'Onboarding Review' with teal-emerald hero and 4 KPIs (Total / Pending / Docs Complete / Activated)
- Status filter tabs + search; table with per-user 4-step progress dots (ID → Address → HMRC → Contract), status badge (WAITING / READY / ACTIVATED) and context-aware Review + Activate buttons
- **Detail drawer** with 4 cards:
  - ID/Passport (image preview, clickable to open full-size)
  - Address proof (image preview with PDF fallback)
  - HMRC starter checklist (full structured data grid: name, DOB, NI, start date, postcode, statement, loans, address)
  - Employment contract (signed/awaiting state)
- One-click Activate (if docs complete) or Activate-anyway override, plus Deactivate for active users
- Reuses existing `GET /api/staff-onboarding/list` + `POST /admin-activate|admin-deactivate` endpoints
- Tested iteration 138 (15/15 backend + frontend pass)

### Iter 138: Staff Onboarding Gate — UK Right-to-Work Verification
- New non-admin staff start with `is_activated: false`; admin/manager are activated instantly
- Blocks the entire dashboard until the user completes **4 steps**:
  1. **ID/Passport** upload — file picker + native camera capture
  2. **Address proof** upload — utility bill / bank statement / council tax
  3. **HMRC Starter Checklist** — first/last name, DOB, NI number (9-char validation), address, postcode, start date, Statement A/B/C (official HMRC wording), student/postgrad loan flags
  4. **Employment Contract** — auto-ticks when the user's email matches a signed `staff_contracts` row
- Progress bar + per-task tick marks; Activate CTA only enabled at 4/4
- `POST /api/staff-onboarding/complete` → flips `users.is_activated=true`
- Admin endpoints: `GET /list` (filter by pending/activated/complete/incomplete), `POST /admin-activate/{user_id}`, `POST /admin-deactivate/{user_id}`
- Login + `/auth/me` now expose `is_activated` to the frontend
- Fixed flow ordering: `PendingLegalDocsGate` (legal policies) is suppressed while onboarding is incomplete — onboarding must finish first
- Mobile-friendly: tab icons collapse to numbered badges on small screens, camera capture uses `capture=environment` to go straight to rear camera
- **Tested**: iteration 137 — all backend + frontend flows pass end-to-end

### Iter 137: Login Gate for Pending Legal Documents
- Full-screen blocking modal (`z-[100]` + backdrop-blur) mounts right after login inside MainApp
- Auto-calls `/api/legal-documents/pending/me` — if non-empty, gate appears with "ACTION REQUIRED · 1 OF N" counter
- Renders each field type from the policy: heading (purple-bordered section), text, textarea, checkbox, select, date, signature (script-font)
- Client + server-side required validation; submits to `/accept` with `responses`; advances to next doc after each acceptance; dismisses when queue empty
- Footer shows "Signed as **{user.name}** · your IP will be recorded for audit"
- Tested iteration 136 — frontend + backend all pass

### Iter 136: Legal Documents & Consents — Policy Builder with E-Signature Audit
- Inspired by myhotelbox.com benchmark screenshots — built a superset
- **7 document types**: Privacy Policy, T&C, GDPR Consent, Code of Conduct, Health & Safety, NDA, Other
- **7 dynamic field types** (vs competitor's text-only): Heading, Text input, Long text, Checkbox, Dropdown, Date, Signature
- Full lifecycle: draft → active → scheduled → expired — with **version bump** (1.0 → 1.1 → 2.0) that auto-drafts the new version
- **Required-acceptance** tracking: `GET /api/legal-documents/pending/me` returns docs the user hasn't accepted or where version changed
- Audit trail per acceptance: user_id, user_role, version, IP, timestamp, field responses
- Edit lock: once a document has acceptances, only `active` and `expiry_date` can be edited — must create a new version to change anything substantive
- Delete lock: blocked if acceptances exist (forces deactivation)
- Admin UI: indigo hero, 4 KPIs (Active / Required & Live / Expiring ≤30d / Total Acceptances), type & status filters + search, table with acceptance progress bar, per-row view-acceptances dialog, edit, new-version, delete
- Dynamic field builder with inline editor, required toggle per field, move up/down, delete
- Tested end-to-end iteration 135 (29/29 backend + full frontend)

### Iter 135: Staff Contracts — Digital Employment with E-Signature
- Full lifecycle: **draft → sent → signed → active → expired/terminated** with admin-only gating
- Fields: contract_type (full_time/part_time/fixed_term/casual/zero_hours/freelance), start/end, probation_end, hours/week, hourly_rate, salary_annual, notice period, holiday entitlement, editable terms
- **Public signing flow**: `GET /api/contracts/sign/{token}` (no auth) returns contract + hotel; `POST /api/contracts/sign/{token}` records typed signature + full name + IP
- Admin UI: slate hero, 4 KPIs (active / expiring ≤30d / on probation / monthly cost with £/yr sub), status filter tabs + search, table with avatar + type + start-end + pay + status chip + context-aware actions (Edit / Send / Delete for drafts, Terminate for active)
- Public route `/contract/sign/{token}` — mobile-friendly signing page with key-terms grid, scrollable T&Cs, typed-script signature, accept-terms checkbox
- Monthly cost formula: `hours_per_week × hourly_rate × 4.333` or `salary_annual / 12`
- Signed contracts are lock-edited — must be terminated to supersede
- Tested end-to-end iteration 134 (24/24 backend + full frontend)

### Iter 134: Arrivals Cockpit — Contactless Guest Journey
- One-pane command centre for every incoming guest's progress across **Link Sent → Registered → ID Verified → Paid → Digital Key Issued**
- `GET /api/arrivals/{pid}?window=today|7d|30d|all&q=…` — aggregates bookings + guest_registrations + digital_keys into one payload with counters and per-booking `progress{}` + `stage` (0-5)
- `POST /api/arrivals/{bid}/mark-paid` (admin|manager), `POST /api/arrivals/{bid}/issue-key` (paid-gate, 8-char code + expiry), `POST /api/arrivals/{bid}/revoke-key`
- Frontend cockpit: emerald hero, 5 KPI cards with coverage bars, window tabs + search, table with avatar + source + 5-dot progress tracker + context-aware action buttons, per-row QR modal (QRCodeSVG of registration link) and amber digital-key-code modal
- Navigation entry `arrivals-btn` in Operations section
- Tested end-to-end iteration 133 (22/22 backend + full frontend)

### Iter 133: AI Picks — GPT-5.2 Marketplace Recommender
- Dark indigo "AI Picks · GPT-5.2" strip on top of the Marketplace
- `POST /api/marketplace/recommendations/{pid}/generate` — reads installed apps + booking source distribution + category coverage, sends structured signals to **GPT-5.2 via Emergent LLM Key**
- Returns `{headline, recommendations[3]}` with `id / title / reason / impact / priority / cat / domain` — server re-validates each pick against the catalog and filters out already-installed integrations
- Frontend: headline, analysis context line, 3 ranked cards (#1/#2/#3) with priority badges, impact chips (`+2-5% RevPAR`, `-8h/week`, etc.), per-card Connect button, Refresh Picks CTA
- Cached in MongoDB `marketplace_recommendations` so the strip persists across reloads
- Tested end-to-end iteration 132 (14/14 backend + full frontend)

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
- **Payroll Rate Matrix** (from myhotelbox screenshots) — cross-tab of user × branch × pay-type × rate with split-across-branches + active toggles
- **Clone Role** button + **Global Admin** flag on Roles & Permissions panel
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
