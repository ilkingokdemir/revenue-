# Backend Routes — Domain Reorganization

**Status (Iter 328): ✅ COMPLETE.** 243 of the original ~250 route modules now live in 11 domain subpackages. Only 5 cross-cutting / shared utility modules remain at the routes root by design.

## Final Layout

```
backend/routes/
├── __init__.py
├── helpers.py                 (shared: log_sync, fire_webhooks)
├── imports.py                 (shared imports manifest)
├── automation.py              (event automation core)
├── automation_rules.py        (fire_event hook — called by many modules)
├── automation_analytics.py    (automation analytics)
├── chatbot_automation.py      (live chat handoff + chatbot configs)
│
├── pms/                  39 files — bookings, group, walk-in, check-in, rooms, guest profiles, journeys
├── revenue_ext/          29 files — RM, forecast, rates, pricing, market_robot, ai_pricing_engine
├── finance_ext/          32 files — accounting, payments, payroll, currency, contracts, bi_feed
├── hotel_ops/            50 files — HK, maintenance, F&B, POS, night-audit, events, laundry, shifts
├── guests/               14 files — CRM, loyalty, reviews, surveys, messaging
├── marketing/            13 files — campaigns, upsell, concierge, whatsapp, voice, web push
├── distribution/         15 files — channel manager, OTAs, agency, wholesaler, booking_com
├── ai/                    8 files — agents, brand voice, AI predictions, image AI, copilot
├── security/             10 files — compliance, gdpr, audit, 2fa, ip allowlist
├── integrations_pkg/     16 files — marketplace, webhooks, smart locks, smart scanner, reports
└── platform_ext/         17 files — admin, auth, roles, dashboards, owner portal, setup wizard
```

## How New Modules Should Be Added

1. Drop the new `.py` file directly into the correct domain subfolder.
2. Add `from routes.<domain>.<file> import create_X_router` in `server.py`.
3. Mount it via `api_router.include_router(...)`.

If a new file does not fit any domain, create a new subpackage (with `__init__.py`) — never park it at root unless it is shared infrastructure used by ≥3 domains.

## Migration Tooling

`/app/scripts/migrate_routes.py` was used to mass-move files & rewrite `server.py` imports. It remains available for future re-organization.

```
python /app/scripts/migrate_routes.py <dest_subfolder> file1 file2 ...
```

## Cross-Folder Imports — Already Fixed

These intra-routes imports were rewritten during the migration:

| File | Old import | New import |
|------|-----------|-----------|
| `pms/rms_pro.py` | `routes.market_robot` | `routes.revenue_ext.market_robot` |
| `revenue_ext/market_robot.py` | `routes.smart_scanner` | `routes.integrations_pkg.smart_scanner` |
| `finance_ext/city_ledger.py` | `routes.currency_fx` | `routes.finance_ext.currency_fx` |
| `marketing/whatsapp_voice.py` | `routes.voice_concierge` | `routes.marketing.voice_concierge` |
| `distribution/channel_hub.py` | `routes.channel_hub` | `routes.distribution.channel_hub` |
| `platform_ext/roles.py` | `routes.permission_catalog` | `routes.platform_ext.permission_catalog` |
| `platform_ext/owner_self_service.py` | `routes.owner_portal` | `routes.platform_ext.owner_portal` |
| `auth.py` | `routes.permission_catalog` | `routes.platform_ext.permission_catalog` |

## Verification

- ✅ Backend boots cleanly (no `ModuleNotFoundError`).
- ✅ `/api/health` = 200.
- ✅ `/api/openapi.json` reports 1,791 endpoints.
- ✅ Sample auth flow + `/api/admin/users`, `/api/properties`, `/api/bookings`, `/api/chatbot/all/handoff/sessions` all return 200.
