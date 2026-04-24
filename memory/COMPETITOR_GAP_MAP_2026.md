# MyHotelBox — Gap Map Update · Feb 2026 (Post Iter 172)

_Last review: Feb 2026_
_Competitors benchmarked: **Mews Enterprise**, **Cloudbeds**, **Eviivo**, **RoomRaccoon**, **Little Hotelier**, **SiteMinder**, **Oaky**, **Canary**, **Revinate**_

Codebase now: **131 backend routes** + **124 frontend panels** — up from 106+113 at Iter 157.

---

## ✅ Part 1 · Already SHIPPED Since Original Gap Map (Iter 157)

From the P0–P3 list in `COMPETITOR_GAP_MAP.md`, **14 of 15** are now DONE:

| # | Gap | Status |
|---|---|---|
| 1 | Night Audit Close-Day Lock | ✅ Iter 156 |
| 2 | Deposit Liability Ledger | ✅ Iter 156 |
| 3 | Commission Reconciliation | ✅ Iter 156 |
| 4 | Gift Cards / Vouchers | ✅ Iter 156 |
| 5 | Review Sentiment AI | ✅ Iter 156 |
| 6 | Guest RFM Segmentation | ✅ Iter 156 |
| 7 | Preventive Maintenance | ✅ Iter 156 |
| 8 | Asset Register | ✅ Iter 156 |
| 9 | Cash Drawer / Float | ✅ Iter 156 |
| 10 | 2FA TOTP | ✅ Iter 156 |
| 11 | Revenue Health Composite | ✅ Iter 157 |
| 12 | IP Allowlist | ✅ Iter 157 |
| 13 | PCI Card Vault | ✅ Iter 157 |
| 14 | Deposit Automation + Scheduler | ✅ Iter 158-159 |
| 15 | SSO/SAML | 🔴 Still deferred (needs IdP contract) |
| 15 | Google Hotel Ads | 🔴 Still deferred (needs Google partner) |

**Plus these NEW major features shipped Iter 160-172 that weren't on original map:**
- Channel Manager MVP (Restrictions, Inbound, Parity)
- OTA Health Dashboard (composite grade A+/F)
- Unified Inbox merging WhatsApp + SMS + Email + Booking.com + Airbnb
- Self-Service Kiosk (complete flow with QR room assignment)
- Split Folio (Sub-Folios) with per-sub-folio print/email/payer
- Rate Structure & OTA Mapping (BAR/NR/derived rates, promo codes)
- Group Bookings with Master Folio (3 billing modes)
- GDPR Art 17+20 (erasure + portability)
- Multi-Currency FX Consolidation (41 ISO currencies + multi-currency invoice lines)
- Laundry Management (full stack: items, contracts, dispatch, forecast)
- Market Robot AI (Smart Scanner, Neighborhood geo-scan, competitive pricing auto-apply)
- HR/RBAC (Clone Role dialog, Staff Contracts with Extend, Upcoming Renewals card)
- Mobile Responsiveness (Market Robot fully phone-compatible as of Iter 172)

---

## 🔴 Part 2 · Gaps STILL EKSIK — Feb 2026 Priority List

### P0 — AI Era Differentiators (Mews + Cloudbeds pushing hard 2026)

1. **AI Guest Concierge Chatbot (24/7)** ❌
   - Mews Advanced + Cloudbeds both ship this in 2026. Auto-answers WiFi password, breakfast time, late-checkout, local recommendations. Escalates to human on complex issues.
   - **Effort:** 1–2 days using Emergent LLM key + existing `unified_inbox`. Claude Sonnet 4.5 already wired.
   - **Impact:** Reduces reception load 30–50%; key sales demo feature for 2026.

2. **AI Reply Suggestions in Unified Inbox** ❌
   - Mews 2026 release: GPT-generated reply drafts in each inbox thread. Staff taps "Send" or "Edit".
   - **Effort:** 0.5 day. Already have the inbox, just add a suggested-reply endpoint per message.
   - **Impact:** Faster guest response time, better sales pitch.

3. **AI Arrival Brief (per-guest auto summary)** ❌
   - Mews Advanced 2026: one-liner at check-in time — "Repeat guest (4th stay), prefers high floor, birthday on 3rd night, owes £30 balance".
   - **Effort:** 0.5 day. Already have RFM, guest profiles, folio data.
   - **Impact:** Receptionist looks like a VIP concierge.

4. **SSO / SAML** ❌ (still deferred)
   - Required for 10+ property chain deals. Okta/Azure AD.
   - **Effort:** 2 days + external IdP setup.

5. **Google Hotel Ads / Meta-search** ❌ (still deferred)
   - Revenue driver. Free tier via Google Hotel Ads API.
   - **Effort:** 2 days + Google partner onboarding.

---

### 🟠 P1 — Modern 2026 Competitive Parity Gaps

6. **Banquet Event Orders (BEO) / Function Sheets** ❌
   - For hotels with F&B events (weddings, conferences). Mews has `events.py` exists but no BEO templates with setup diagram, dietary list, timeline.
   - **Effort:** 2 days.

7. **Kitchen Display System (KDS)** ❌
   - POS logs orders but no real-time kitchen-facing display with bump-bar workflow.
   - **Effort:** 1.5 days. Needed for F&B operations.

8. **Sustainability / Carbon Tracking** ❌
   - 2026 booking-engine trend — eco-certifications boost direct bookings 12-18% (Booking.com Travel Sustainable badge).
   - Track kWh, water, waste, stay-emissions per booking. Weeva, Hotelkit have it.
   - **Effort:** 2 days.

9. **Upsell Pre-Arrival Drip Campaigns** ⚠️
   - `upsell_engine.py` exists but no automated drip scheduler (T-7d / T-3d / T-1d emails with offers).
   - Oaky charges £200/room/month for this. We can ship in 1 day using existing Scheduler (Iter 159) + Campaigns.

10. **STR-style Comp Set Benchmarking** ⚠️
    - `compset_intel.py` exists. Missing: STR-grade metrics (MPI, ARI, RGI) + trailing-12-month comp trend line.
    - **Effort:** 1 day.

11. **Embedded BI / Shareable Dashboards** ⚠️
    - `reports_hub.py` exists. Missing: shareable public URL dashboards (owner / board view without login).
    - **Effort:** 1 day.

12. **Auto-Translation in Unified Inbox** ❌
    - Mews/Cloudbeds auto-translate inbound guest messages. Our inbox doesn't.
    - **Effort:** 0.5 day using Emergent LLM key (Claude/GPT both support translation).

---

### 🟡 P2 — Polish & Scale

13. **Voice of Guest (auto NPS/CSAT post-checkout)** ⚠️
    - `surveys.py` exists but no T+2h auto-trigger post check-out.
    - **Effort:** 0.5 day via Scheduler (Iter 159).

14. **Multi-property Pooled Inventory** ⚠️
    - "All Branches" view shows each separately. No pooled availability across sister hotels.
    - **Effort:** 1.5 days.

15. **Mobile Key Hand-off via Smart Lock API** ⚠️
    - `smart_locks.py` has digital_keys but no real integration with Assa Abloy/Salto/4Suites APIs. Currently issues QR payload for "future scanning".
    - **Effort:** 2-3 days per lock vendor.

16. **Multi-language Guest Email Templates** ⚠️
    - Templates exist but only English/Turkish. Modern hotels send in guest's detected language.
    - **Effort:** 1 day via GPT batch-translate existing templates.

17. **Google Review Auto-reply via AI** ❌
    - `reviews.py` + `review_sentiment.py` exist. Missing: auto-draft response based on sentiment/theme for human approval.
    - **Effort:** 0.5 day.

---

### 🟢 P3 — Nice-to-Have

18. **Rate Manager Heatmap Demand Overlay** — Event icons on rate calendar cells. ~0.5 day.
19. **Channel iCal Cron Config UI** — Backend polls work; no visible schedule editor. ~0.5 day.
20. **Booking Abandonment Recovery Emails** — Widget has tracking but no email drip to cart-abandoners. ~1 day.

---

## ⭐ Part 3 · What We BEAT Competitors On (marketing moat)

Unchanged from original map, plus new differentiators from Iter 158-172:

1. **Self-Service Kiosk** at SMB price (Mews charges $$$)
2. **Laundry Management** (RoomChecking is 3rd-party add-on)
3. **Market Robot AI** with multi-instance Smart Scanner + neighborhood geo-scan (no direct competitor at SMB tier)
4. **Onboarding Wizard × Market Robot fusion** — property setup in 3 min with auto-currency detection (Iter 169)
5. **Split Folio with per-sub-folio email/print** (Mews charges Advanced+, Cloudbeds doesn't have)
6. **Unified Inbox merging 6 channels** (Mews has it, Cloudbeds has partial — we have ALL 6)
7. **Multi-Currency FX Consolidation** with 41 ISO + multi-currency invoice lines (rare at SMB tier)
8. **Marketplace + White-label Branding** (Mews Enterprise only)
9. **Staff Contracts + Onboarding Review + Legal Documents + Clone Role Dialog + Upcoming Renewals** (Iter 170-171 — 3 separate vendors elsewhere)
10. **Competitor Rate Shopper + Neighborhood Geo-scan** (OTA Insight is £4000/yr)
11. **GDPR Art 17 + Art 20 dashboard** (deeper than Eviivo)
12. **Profit OS + Revenue Health + Gap Analyzer + Biz vs Pazar** (custom differentiators)
13. **Flashing balance pills + Quick Pay with 4 payment types** (slicker than Cloudbeds/Mews)
14. **Bug Tracker built-in** (unique)
15. **Scheduler + Nightly Auto-Deposit Capture** — fully automated deposit pipeline (Iter 158-159)

---

## 📊 Part 4 · Recommended Build Order (Next 2 Weeks)

**Week 1 — AI 2026 Era (4 features, ~3-4 days):**
- Day 1: AI Guest Concierge Chatbot (#1)
- Day 2: AI Reply Suggestions in Unified Inbox (#2)
- Day 3 AM: AI Arrival Brief per guest (#3)
- Day 3 PM: Auto-Translation in Inbox (#12)
- Day 4: Google Review Auto-reply Drafts (#17)

**Week 2 — Parity Close-out (4 features, ~5 days):**
- Upsell Drip Campaigns (#9) — 1d
- STR-style Comp Set (#10) — 1d
- Voice of Guest auto-NPS (#13) — 0.5d
- Sustainability tracking (#8) — 2d
- Embedded BI shareable dashboards (#11) — 1d

**After Week 2:** 100% parity with Mews **Advanced** (2026 AI tier) + 15 unique differentiators.

SSO/SAML, Google Hotel Ads, KDS, BEO deferred unless a specific customer requests them.

---

## 📋 Part 5 · Numbered Summary for Product Discussion

| # | Gap | Priority | Effort | Uses Emergent LLM Key |
|---|---|---|---|---|
| 1 | AI Guest Concierge Chatbot | 🔴 P0 | 1.5d | ✅ Claude |
| 2 | AI Reply Suggestions | 🔴 P0 | 0.5d | ✅ Claude |
| 3 | AI Arrival Brief | 🔴 P0 | 0.5d | ✅ Claude |
| 4 | SSO / SAML | 🔴 P0 | 2d | No (external IdP) |
| 5 | Google Hotel Ads | 🔴 P0 | 2d | No (Google partner) |
| 6 | BEO / Function Sheets | 🟠 P1 | 2d | No |
| 7 | KDS | 🟠 P1 | 1.5d | No |
| 8 | Sustainability/Carbon | 🟠 P1 | 2d | No |
| 9 | Upsell Drip Campaigns | 🟠 P1 | 1d | Optional |
| 10 | STR-style Benchmarking | 🟠 P1 | 1d | No |
| 11 | Embedded BI Dashboards | 🟠 P1 | 1d | No |
| 12 | Auto-Translation Inbox | 🟠 P1 | 0.5d | ✅ Claude |
| 13 | Auto NPS Post-Checkout | 🟡 P2 | 0.5d | No |
| 14 | Pooled Multi-Prop Inventory | 🟡 P2 | 1.5d | No |
| 15 | Real Smart Lock API Integration | 🟡 P2 | 2-3d/vendor | No |
| 16 | Multi-language Email Templates | 🟡 P2 | 1d | ✅ Claude |
| 17 | Google Review Auto-reply | 🟡 P2 | 0.5d | ✅ Claude |
| 18 | Rate Manager Demand Overlay | 🟢 P3 | 0.5d | No |
| 19 | iCal Cron Config UI | 🟢 P3 | 0.5d | No |
| 20 | Booking Abandonment Recovery | 🟢 P3 | 1d | Optional |
