# Backend Routes — Domain Reorganization Plan

**Status as of Iter 290:** 247 route files. 14 recently-added modules moved into domain subpackages. The remaining ~230 legacy modules stay in `/app/backend/routes/` root for now — this document maps every file to its target domain so the next refactoring sprint can finish the work safely.

## ✅ Already Migrated (14 files — Iter 277-290 additions)

```
routes/
├── distribution/        — channel mgmt, OTAs, direct booking, agency
│   ├── agency_portal.py        (Iter 284 — TÜRSAB)
│   ├── booking_com.py          (Iter 290 — XML push)
│   ├── public_events.py        (Iter 285 — Tripleseat)
│   └── wholesaler.py           (Iter 287 — Hotel Trader)
├── ai/                  — autonomous & assist agents
│   ├── agents.py               (Iter 286 — Mews Agentic Loops)
│   ├── brand_voice.py          (Iter 289 — tone-of-voice service)
│   ├── review_agent.py         (Iter 284 — Lighthouse)
│   └── web_concierge.py        (Iter 284 — Eviivo)
├── marketing/           — outbound marketing, lead funnel, videos
│   ├── lead_funnel.py          (Iter 287)
│   └── marketing_videos.py     (Iter 288 — Sora 2)
├── revenue_ext/         — pricing extensions (legacy `revenue.py` keeps its name)
│   └── open_pricing.py         (Iter 285 — Duetto)
├── hotel_ops/           — operations extensions (legacy `operations.py` keeps its name)
│   ├── beach_pos.py            (Iter 285 — Elektra)
│   └── vacation_rental.py      (Iter 286 — Eviivo)
└── platform_ext/        — platform-level extensibility
    └── dev_portal.py           (Iter 287 — Mews Marketplace)
```

## 🔜 Future Migration Plan (~230 remaining files)

Move each file to the target domain folder. After moving, update its import in `server.py`. Always check for naming conflicts with existing legacy modules of the same name (e.g. `operations.py` vs `operations/`).

### Domain Mapping

#### `routes/pms/` — Property Management System core
```
arrivals.py, departures.py, bookings.py, booking_engine_v2.py, booking_widget.py,
booking_timeline.py, calendar_grid.py, room_assignments.py, room_assignments_v2.py,
room_types.py, rooms.py, group_blocks.py, holds.py, in_house_now.py,
late_checkouts.py, no_shows.py, no_show_predictor.py, overbooking_engine.py,
overbooking_v2.py, ota_inbox.py, ota_inbox_v2.py, ota_inbox_v3.py,
queue_room_returns.py, room_blocks_holds.py, room_moves.py, room_status_intelligence.py,
share_a_room.py, split_payment.py, stayover_routine.py, walk_in_intake.py,
walk_in_kiosk.py
```

#### `routes/revenue/` (renames to `revenue_ext/`) — Revenue management
```
revenue.py, revenue_management_v2.py, daily_revenue_report.py, daily_pickup.py,
forecast.py, forecast_v2.py, forecast_pace.py, forecast_pace_v2.py,
pace_optimizer.py, pickup_curve.py, pickup_curve_v2.py, pickup_velocity.py,
pricing.py, pricing_v2.py, pricing_intelligence.py, rate_engine.py, rate_shopper.py,
rate_shopper_v2.py, rate_card.py, rate_recommendation_engine.py, rate_recommender.py,
revpar_optimizer.py, revenue_displacement.py, sales_velocity.py, yield_optimizer.py,
yield_v2.py, market_pulse.py, market_pulse_v2.py, demand_pacing.py, demand_pace_v3.py,
compset.py, compset_v2.py
```

#### `routes/distribution/` — OTAs, channel manager, BE
```
channels.py, channels_v2.py, channel_manager.py, channel_pixel.py,
booking_engine.py, multi_property_widget.py, booking_intel.py,
distribution_alerts.py, distribution_health.py, distribution_overlay.py,
guest_pixel.py, partner_webhooks.py, partner_apis.py, rate_parity.py,
rate_parity_v2.py, parity_pulse.py, otaadm_inbox.py
```

#### `routes/finance/` (renames to `finance_ext/`) — Accounting, P&L, AR
```
finance.py, finance_pl.py, accounting.py, accounting_advanced.py, accounting_export.py,
ar_aging.py, ar_aging_v2.py, balance_sheet.py, bank_reconciliation.py,
budget_planner.py, budget_vs_actual.py, budget_vs_actual_v2.py, cashflow.py,
city_tax_summary.py, commissions.py, deferred_revenue.py, deposit_management.py,
e_invoice.py, e_invoice_v2.py, financial_close.py, financial_consolidation.py,
fx_revaluation.py, group_billing.py, gross_to_net.py, invoice_workflow.py,
invoice_workflow_v2.py, journal_entries.py, journal_entries_v2.py, payments.py,
posting_engine.py, settle.py, tax_engine.py, vat_summary.py, vat_summary_v2.py,
working_capital.py
```

#### `routes/guests/` — CRM, loyalty, communications
```
guests.py, guest_360.py, guest_engagement.py, guest_feedback.py,
guest_history.py, guest_segments.py, guest_segments_v2.py, vip_alerts.py,
loyalty.py, loyalty_v2.py, loyalty_tiers.py, crm.py, crm_pulse.py,
crm_pulse_v2.py, contact_center.py, surveys.py, surveys_v2.py, surveys_v3.py,
reviews.py, review_intel.py, review_intel_v2.py, sentiment.py, sentiment_v2.py,
mood_pulse.py, mood_pulse_v2.py, birthday.py, anniversary.py, win_back.py,
attribution.py
```

#### `routes/operations/` (renames to `hotel_ops/`) — HK, maintenance, FB
```
operations.py, ops_v2.py, ops_predictive.py, housekeeping.py, housekeeping_hub.py,
housekeeping_intel.py, maintenance.py, maintenance_intel.py, maintenance_v2.py,
sops.py, sops_v2.py, glitch_log.py, glitch_log_v2.py, mood_radar.py,
flexkeeping.py, fnb.py, fnb_pos_hub.py, fnb_pos_integration.py, fnb_pos_v2.py,
fnb_inventory.py, fnb_recipes.py, menu_engineering.py, banquet_orders.py,
meetings_sales.py, spa_activities.py, asset_register.py, room_attributes.py,
sustainability.py, esg.py, carbon_reporting.py, carbon_reporting_v2.py
```

#### `routes/marketing/` — Outbound campaigns, web
```
marketing.py, marketing_v2.py, marketing_pulse.py, marketing_pulse_v2.py,
campaign_intelligence.py, content_studio.py, social_media.py, email_dispatch.py,
sms_dispatch.py, whatsapp.py, voice_concierge.py, voice_pulse.py,
voice_pulse_v2.py, lead_scoring.py, conversion_funnel.py, conversion_funnel_v2.py
```

#### `routes/security/` — Audit, RBAC, compliance
```
audit_trail.py, audit_trail_v2.py, security.py, security_v2.py, security_dashboard.py,
security_owner.py, ai_predictions.py, ai_predictions_v2.py, anomaly_detection.py,
anomaly_detection_v2.py, fraud_detection.py, fraud_detection_v2.py, fraud_intel.py,
gdpr.py, gdpr_v2.py, dsar.py, dsar_v2.py, compliance.py, compliance_v2.py,
kyc_aml.py, kyc_aml_v2.py, hardening.py, hardening_v2.py, two_factor_auth.py
```

#### `routes/integrations/` — Third-party connectors
```
integrations.py, integrations_v2.py, integrations_marketplace.py,
integrations_marketplace_v2.py, integrations_marketplace_v3.py, webhooks.py,
webhooks_v2.py, webhooks_v3.py, bi_feed.py, bi_feed_v2.py, etl_export.py,
slack_notifier.py, slack_notifier_v2.py
```

#### `routes/ai/` — AI-powered automation
```
agents.py, agents_b2b.py, ai_predictions.py, brand_voice.py, review_agent.py,
web_concierge.py, ai_concierge.py, ai_pulse.py, predictive_maintenance.py,
predictive_no_show.py, recommendation_engine.py, recommendation_engine_v2.py
```

#### `routes/platform_ext/` — Platform extensibility
```
admin.py, auth_routes.py, branches.py, brand.py, multi_property.py,
multi_property_v2.py, property_groups.py, role_management.py, role_management_v2.py,
tenants.py, user_management.py, owner_self_service.py, dev_portal.py
```

## How to Migrate a File (template)

```bash
# 1. Move file to domain subfolder
git mv /app/backend/routes/X.py /app/backend/routes/DOMAIN/X.py

# 2. Update server.py import (single line change)
# OLD: from routes.X import create_X_router
# NEW: from routes.DOMAIN.X import create_X_router

# 3. Restart backend & smoke-test the endpoints owned by X.py

# 4. Watch out for naming conflicts: if a legacy `DOMAIN.py` flat file exists,
#    rename the new package to `DOMAIN_ext/` (e.g. revenue → revenue_ext)
```

## Why This Order

1. **Move newer modules first** (lower risk — they're fresh & well-tested).
2. **Domain folders with legacy flat files conflict** — use `_ext` suffix.
3. **Move legacy files in batches of 5-10**, restart + smoke test after each batch.
4. **Never modify legacy file contents during a move** — just relocate.

## Estimated Effort
- ~230 files × 2 minutes each (move + import update + verify) = ~8 hours focused work
- Recommended over 2-3 sprints (75-80 files per sprint, with full regression after each)
