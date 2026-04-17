# My Hotel Box - Complete Hotel Management Platform

## 30+ Modules | Mobile Responsive | 119 Test Iterations (100%)

### NEW: Price Intelligence Alerts
- **Configurable Alert Rules** — Thresholds for: competitor price drop/rise (% and £), demand spike/drop (pp), supply compression (%), rate parity breach (%), high/low occupancy thresholds, scan window (days)
- **8-Check Market Scanner** — Detects: competitor price drops, competitor price rises, demand spikes, demand drops, supply compression, rate parity breaches, high demand dates, low demand dates
- **Alert Dashboard** — Real-time feed with severity badges (high/medium), meta data (old vs new prices, demand %, your rate), filter by type
- **Quick Actions** — View (navigates to Demand Radar/Compset Intel), Adjust Rate, Acknowledge, Dismiss per alert
- **NotificationBell Integration** — Price Intel filter tab, unread count badge

### Demand Radar & Compset Intelligence
1. **Demand Radar** — 90-day forward market intelligence: demand chart, WAP tracking, 7-day pickup change, pricing opportunity scatter map, lead time/LOS analysis, DOW patterns. Day selectors: 30/60/90/180/365.
2. **Compset Intelligence** — Your hotel vs competitive set: occupancy/ADR/RevPAR ranking cards (out of 12), ADR/Occ/RevPAR comparison charts, daily drill-down table, market context, tier distribution, neighbourhoods. Day selectors: 7/14/30/60/90.

### Revenue Intelligence Suite
1. **Booking Pace & Pickup Velocity** — This year vs last year comparison, 24h pickup rate
2. **Revenue Forecast Engine** — AI-projected Revenue, ADR, Occupancy, RevPAR
3. **Rate Recommendation Actions** — Daily AI to-do list with one-click Accept
4. **What-If Simulator** — Test rate changes before committing

### Revenue Sidebar (30+ modules)
INTELLIGENCE: Market Robot (11 sub-tabs), Demand Radar, Compset Intelligence, Price Alerts, Booking Pace, Revenue Forecast, Rate Actions, What-If Simulator, Historical Analysis, Forecasting, Analytics, Competitors
PRICING: AI Dynamic Pricing (365-day, 10-factor), Rate Calendar, Pricing Strategy, Smart Pricing, Approvals  
DISTRIBUTION: Channel Manager (9 OTAs), Segments, Parity, Overbooking
FINANCE: Profit OS, Reports & Export, Rate Resolver

## Architecture
- React + Tailwind + Shadcn UI (frontend)
- FastAPI + MongoDB (backend)
- OpenAI GPT-5.2 via Emergent LLM Key (AI features)
- Stripe (payments), Resend (emails)

## Testing: 119 iterations, 100% pass rate

## Upcoming Tasks
- SEO meta tags for public booking engine (P2)
- Automate reviews generation/response via LLM (P2)

## Future/Backlog
- Weather Intelligence
- Displacement Analysis
- Length of Stay Optimizer
- Scheduled report email delivery
- Mobile companion app
