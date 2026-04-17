# My Hotel Box - Complete Hotel Management Platform

## 30+ Modules | Mobile Responsive | 104 Test Iterations (100%)

### Revenue Management System — Industry-Leading (23 Sidebar Modules)

OVERVIEW: Dashboard, AI Copilot (GPT-5.2 + Voice), Setup Wizard
PRICING: AI Dynamic Pricing (90-day 9-factor incl. Event Intelligence), Rate Calendar (Editable), Pricing Strategy (7 sub-tabs), Smart Pricing, Approvals
INTELLIGENCE: Market Robot (Smart Tiered Scanner + 30 cities), Event Intelligence (GPT-5.2 event detection, wired into Dynamic Pricing), Forecasting, Analytics (3 sub-tabs), Competitors
AUTOMATION: Playbooks, Experiments, Action Center
DISTRIBUTION: Segments, Parity, Overbooking, Distribution
FINANCE: Profit OS, Reports & Export, Rate Resolver

### AI Dynamic Pricing Engine (9 Factors)
1. Day-of-Week adjustments
2. Monthly seasonality
3. Lead time to check-in
4. Our occupancy levels
5. Market supply (Booking.com via Market Robot)
6. Competitor hotel positioning
7. Event Intelligence (GPT-5.2 powered) — NEW: wired as 9th factor
8. Aggressiveness multiplier
9. Min/Max guardrails

### Event Intelligence (GPT-5.2 Powered)
- Scrapes web for upcoming concerts, matches, exhibitions, marathons, festivals
- GPT-5.2 analyzes and classifies events by attendance & hotel demand impact
- Auto-pricing: Mega (50k+) → +40%, Large (20k+) → +25%, Medium (5k+) → +12%, Small (1k+) → +5%
- Applies price boosts to event date + 1 day before/after
- Manual event addition with auto-pricing
- Grouped by month with color-coded impact badges
- Integrated into Dynamic Pricing data_sources (events_loaded) and summary (event_days)

### Smart Tiered Scanner
5-tier schedule: 30m/1h/3h/6h/12h based on date proximity

## Upcoming Tasks
- Channel Manager integration (P1)
- SEO meta tags for public booking engine (P2)
- Automate reviews generation/response via LLM (P2)

## Future/Backlog
- Scheduled report email delivery (P2)
- Mobile companion app (P2)

## Refactoring
- Backend revenue routes spread across ~9 files — could be organized into /app/backend/routes/revenue/ module

## Testing: 104 iterations, 100% pass rate
