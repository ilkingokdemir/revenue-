# Production Readiness — Master Gap Map
**Updated:** Feb 2026 · Iter 247 · 126 modules · 23 batches green

This document is the single source of truth for everything between **today's preview build** and **production launch**.

Each gap has: **Track** (Code = main agent can fix / Biz = user must obtain key/cert/partnership), **Severity** (P0/P1/P2/P3), **Effort** (hours/days/weeks), **Status**.

---

## TRACK A — CODE (main agent can ship without user keys)

### A.1 Backend Hardening

| Gap | Severity | Effort | Status |
|---|---|---|---|
| Deep `/api/health` (DB ping + LLM ping + disk + version) | P0 | 1h | TODO |
| Structured JSON logging (request_id, user_id, latency) | P0 | 2h | TODO |
| Generic exception handler (no stack-trace leak) | P0 | 1h | TODO |
| Rate limit on `/api/auth/login` + `/api/auth/register` | P0 | 1h | TODO |
| Rate limit on AI endpoints (cost guardrail) | P1 | 2h | TODO |
| CORS lockdown (currently `*` in dev) | P0 | 30m | TODO |
| MongoDB index audit (slow queries) | P1 | 4h | TODO |
| Async background job queue (currently inline) | P2 | 1d | TODO |
| Idempotency keys on payment/booking POSTs | P1 | 4h | TODO |
| Soft-delete + retention policy | P2 | 1d | TODO |
| Request size limits (uploads bounded) | P0 | 1h | TODO |
| API versioning (`/api/v1/...`) | P2 | 1d | TODO |
| OpenAPI/Swagger docs polish | P1 | 2h | TODO |

### A.2 Frontend Hardening

| Gap | Severity | Effort | Status |
|---|---|---|---|
| React ErrorBoundary global | P0 | 1h | TODO |
| 404 / fallback route page | P0 | 30m | TODO |
| Sentry-ready instrumentation hook (env-gated) | P0 | 1h | TODO |
| Loading skeletons (vs spinners) on heavy panels | P1 | 4h | TODO |
| Empty-state illustrations | P2 | 4h | TODO |
| Offline detection banner | P2 | 2h | TODO |
| i18n coverage audit (missing TR keys) | P1 | 4h | TODO |
| Accessibility (WCAG AA) audit | P1 | 2d | TODO |
| Lighthouse score > 90 | P1 | 1d | TODO |
| Bundle analyzer + tree-shake unused | P2 | 4h | TODO |
| Lazy chunk pre-fetch (sidebar hover) | P2 | 2h | TODO |
| RTL support (Arabic market) | P3 | 1d | TODO |

### A.3 DevOps & Observability

| Gap | Severity | Effort | Status |
|---|---|---|---|
| MongoDB backup script (cron-ready) | P0 | 1h | TODO |
| Env var validation on boot | P0 | 1h | TODO |
| Healthcheck → restart policy | P0 | 1h | TODO |
| README + deployment guide | P0 | 2h | TODO |
| Docker Compose for self-host | P1 | 1d | TODO |
| CI/CD pipeline (GitHub Actions) | P1 | 1d | TODO |
| Sentry/PostHog/Plausible analytics | P1 | 4h | TODO |
| Uptime monitor stub (UptimeRobot/BetterStack) | P1 | 1h | TODO |
| Log aggregation (Loki/Datadog stub) | P2 | 1d | TODO |
| Database migration tool (Beanie/Motor) | P2 | 2d | TODO |

### A.4 Missing Feature Modules (no API key needed)

| Module | Severity | Effort | Notes |
|---|---|---|---|
| **Loyalty Tier engine v2** (auto-upgrade matrix) | P1 | 1d | Marriott Bonvoy seviye |
| **Banquet Event Order auto-PDF** | P1 | 1d | Conference S&C complement |
| **F&B Recipe-based COGS** | P1 | 2d | Modifier groups dahil |
| **F&B deep modifier trees** | P1 | 1d | |
| **Voice Concierge (whisper STT)** | P2 | 1d | Emergent LLM destekli |
| **Carbon Reporting v2** (Scope 1+2+3) | P2 | 1d | GHG protokol |
| **STR Global benchmark adapter** (data shape only) | P2 | 4h | Veri partner key gerekecek |
| **Lazy chunk pre-fetch** | P2 | 2h | UX latency |
| **Marketplace v1** (3rd party app store) | P3 | 1w | Kendi ekosistemimiz |
| **Spa & Golf module** | P2 | 2d | Book4Time tarzı |
| **AI Time-Saved Widget** (RM ROI tracker) | P2 | 2h | Dashboard kpi |
| **PMS-to-PBX adapter** (telefon → folio) | P3 | 3d | Hardware bağlantı |
| **TV casting** (Pro:Idiom, Enseo) | P3 | 1w | Hardware |
| **Notification Center v2** (in-app push) | P2 | 1d | |
| **Native mobil app (Capacitor wrap)** | P1 | 1w | App Store + Play Store |
| **Hardware lock adapter SDK** | P1 | 3d | Salto/Assa simulator |

### A.5 Test Coverage

| Gap | Severity | Effort | Status |
|---|---|---|---|
| Smoke test suite (<30s, 50 critical paths) | P0 | 1d | TODO |
| Backend unit test coverage > 60% | P1 | 1w | TODO |
| Playwright E2E suite (10 user journeys) | P1 | 1w | TODO |
| Load test (k6, 1000 concurrent users) | P1 | 2d | TODO |
| Chaos test (DB down, LLM timeout) | P2 | 2d | TODO |

---

## TRACK B — BUSINESS (user must obtain)

### B.1 API Keys (all blocked features)

| Service | Used For | Cost | Where to obtain |
|---|---|---|---|
| **Stripe LIVE key** | Pre-auth, tipping, deposits, gift cards production | 2.9% + $0.30 / txn | dashboard.stripe.com |
| **Booking.com Connectivity Partnership** | Real ARI push + reservation pull | Application | partner.booking.com/connectivity |
| **Expedia Partner Central** | Real ARI push | Application | partners.expediagroup.com |
| **Airbnb iCal/API** | Sync vacation rentals | Free | airbnb.com/host |
| **Google Hotel Ads** | Metasearch | CPC bidding | ads.google.com/hotel |
| **Resend API key** | Transactional email | $0/mo (free 3K) | resend.com |
| **Twilio account + phone numbers** | SMS + WhatsApp Business | $0.0075/SMS | twilio.com |
| **Onfido or Veriff API key** | Passport/ID OCR for self check-in | ~$1/check | onfido.com |
| **STR Global / Lighthouse data feed** | Comp set benchmark | Subscription | str.com / lighthouse.com |
| **TrustYou or Revinate API** (optional) | External review aggregation | Subscription | |
| **Salto / Assa Abloy SDK** | Hardware lock integration | Hardware purchase | salto.com / assaabloy.com |

### B.2 Certifications (sales blockers for chains)

| Cert | Required For | Effort | Cost |
|---|---|---|---|
| **PCI-DSS Level 1** | Pre-auth, card vault, recurring | 6-12 months | $50K-100K |
| **SOC 2 Type II** | Enterprise/chain sales | 6-12 months | $30K-60K |
| **ISO/IEC 27001** | EU enterprise sales | 9-12 months | $20K-40K |
| **GDPR DPA template** | EU sales | 1 week | Lawyer fee |
| **HIPAA** (if treating health data, e.g. spa) | US wellness brands | 6 months | $20K |
| **Cyber Essentials Plus** (UK) | UK gov/chain | 2 months | $5K |

### B.3 Partnerships

| Partner | Why |
|---|---|
| **Stripe Verified Partner** | Marketing co-promotion |
| **HiTec / HSMAI member** | Industry credibility |
| **Booking.com Premier Partner** | Featured connectivity |
| **Mews/Cloudbeds Migration Tool** | Switch from competitor |
| **Local accountant network (TR/EU)** | Compliance trust |

### B.4 Legal/Compliance Docs

| Doc | Status |
|---|---|
| Terms of Service | TODO |
| Privacy Policy (GDPR + CCPA + Turkish KVKK) | TODO |
| Data Processing Agreement (DPA) template | TODO |
| Cookie Policy | TODO |
| EULA | TODO |
| Reseller agreement template | TODO |

---

## PHASED ROADMAP TO PRODUCTION

### Phase 1 — Code Hardening (this week, agent-driven, no user input needed)
- Health endpoint deep check
- Structured logging + request_id
- Generic error handler
- Rate limit auth + AI endpoints
- React ErrorBoundary + 404
- Sentry-ready hook (env-gated)
- ENV validation script
- MongoDB backup script
- README + deploy guide

### Phase 2 — Missing Modules (next 2-3 weeks, agent-driven)
- Loyalty Tier engine v2
- Banquet Event Order auto-PDF
- F&B Recipe COGS + modifier trees
- Hardware lock SDK adapter (simulator)
- Native mobile via Capacitor
- AI Time-Saved widget
- Marketplace v1
- Voice Concierge
- Carbon v2

### Phase 3 — User Action (parallel, user-driven)
- Stripe live key → 1 day
- Resend + Twilio + Onfido → 1 day
- Booking.com Connectivity Partnership application → 3-6 months
- Legal docs (lawyer) → 2 weeks
- PCI-DSS SAQ-D process → 6-12 months
- SOC 2 audit prep → 6-12 months

### Phase 4 — Beta Launch (after Phase 1+2 done, with available keys)
- 3-5 pilot Turkish boutique hotels
- Free for 3 months in exchange for feedback
- Iterate on real-world bug reports

### Phase 5 — Public Launch
- Pricing page + sales site
- Marketplace open to 3rd-party devs
- Localization expansion

---

## OUR SCORE TODAY

| Dimension | Score | Target |
|---|---|---|
| Module coverage | 9/10 | 10/10 (Phase 2) |
| AI depth | 10/10 | 10/10 ✓ |
| UX modernity | 9/10 | 10/10 |
| Production hardening | 5/10 | **9/10 (Phase 1 closes this)** |
| Ecosystem partners | 3/10 | 7/10 (Phase 5) |
| Hardware integrations | 2/10 | 6/10 (Phase 2) |
| Certifications | 1/10 | 9/10 (Phase 3, user-blocked) |

**Overall production readiness: ~55%.** Phase 1 → 75%. Phase 2 → 85%. Phase 3 → 95%.
