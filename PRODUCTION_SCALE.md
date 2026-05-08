# Production Scaling Playbook
## Hotel PMS & Revenue Management → 100+ Hotels × 1000s of Users

This document defines how to operate the Capacitor-wrapped mobile app and the
backend at scale, without surprises later.

---

## 1. Architecture overview at scale

```
                                ┌──────────────────────┐
   iOS App (App Store) ─┐       │                      │
                        ├──HTTPS┤  CloudFlare CDN /     │
   Android App (Play) ──┤       │  AWS API Gateway     │
                        │       │                      │
   Web/PWA dashboard ───┘       └──────────┬───────────┘
                                           │
                            ┌──────────────┴───────────────┐
                            │  Backend FastAPI cluster      │
                            │  (3+ replicas, autoscale)     │
                            └──────────────┬───────────────┘
                                           │
              ┌───────────────┬────────────┴────────────┬────────────────┐
              │               │                         │                │
        ┌─────▼─────┐  ┌──────▼──────┐  ┌──────────────▼─────────┐  ┌───▼────┐
        │ MongoDB   │  │ Redis       │  │ Firebase Cloud         │  │ Sentry │
        │ Atlas     │  │ (cache +    │  │ Messaging (push)       │  │        │
        │ (sharded) │  │ rate limit) │  │                        │  │        │
        └───────────┘  └─────────────┘  └────────────────────────┘  └────────┘
```

---

## 2. Mobile distribution

### One app, multiple roles
We ship a **single binary** to App Store + Play. The user logs in and
sees a role-based home (admin / manager / receptionist / housekeeping /
chef / guest). All 130+ modules ship inside the same app, lazy-loaded.

### Account types

| Audience       | Distribution               | Cost           |
|----------------|----------------------------|----------------|
| Hotel staff    | Apple Business Manager / Play Internal Testing | included |
| Public guests  | App Store + Play public listing                | included |
| Demo / pilots  | TestFlight + Play Internal track               | included |

### Required developer accounts (one-time)

* Apple Developer Program — **$99/year**
* Google Play Developer — **$25 one-time**

These two accounts let you publish to **all 100+ hotels' brands** under
your umbrella; you do **not** need a separate account per property.

### Multi-tenant branding

* Each hotel keeps its own colour, logo, name in `branding_settings`.
* The mobile app reads `/api/branding` after login and re-themes itself.
* Optional white-label: ship a separate **per-brand binary** by changing
  `appId` (e.g., `com.hotelpms.brand-x.app`) — you can do this later with
  a single GitHub Actions matrix.

---

## 3. Build pipeline (already wired)

`/app/.github/workflows/mobile-build.yml` runs on every push to `main` and
on `v*` tags:

1. Build the web bundle once (Ubuntu).
2. Fan out to a **macOS runner** (iOS .ipa) and an **Ubuntu runner**
   (Android .aab) **in parallel**.
3. On tag pushes, auto-upload to **TestFlight + Play Internal**.

**You don't need a Mac.** The macOS runner is rented from GitHub for ~10
minutes per build. Free tier: 2 000 min/month for private repos.

If you outgrow GitHub's macOS minutes, switch to **Codemagic** or **EAS
Build** with a single config swap.

---

## 4. Push notifications at scale

* **Stack:** Firebase Cloud Messaging (FCM) — handles iOS (APNs) + Android
  + Web from one SDK. Free up to **unlimited** sends.
* **Backend integration:** add `firebase-admin` Python SDK and a
  `/api/notifications/push` endpoint that accepts a list of device tokens
  and a payload. Firebase handles fan-out to millions of devices.
* **Topic-based:** subscribe staff to topics like
  `property-{id}/role-{r}` so a manager push reaches the right hotel only.

To activate:

1. Create a Firebase project (free).
2. Add iOS + Android apps in Firebase console — drop
   `GoogleService-Info.plist` into `ios/App/App/` and `google-services.json`
   into `android/app/`.
3. Capacitor's `@capacitor/push-notifications` plugin (already installed)
   wires APNs/FCM automatically.
4. Run `pod install` (iOS) — already part of CI.

---

## 5. OTA updates (no App Store re-review)

For **frontend-only** changes (most of our work) you can ship without a
new App Store review:

* **Capacitor Live Updates** — official, paid, integrated.
* **CapGo** — open-source alternative, free up to 1000 MAU.
* **Self-hosted** — push the `build/` zip to your CDN, ship a manifest, and
  let the app download it on cold-start. Reference implementation is in
  Capacitor docs.

Native (plugin) changes still need a real App Store update — but those
happen rarely.

---

## 6. Observability

| Concern               | Tool                            | Free tier |
|-----------------------|---------------------------------|-----------|
| Crash reporting       | Sentry                          | 5k events/mo |
| Performance metrics   | Sentry Performance              | included |
| Error logs            | Sentry breadcrumbs              | included |
| Server logs           | Logtail / Datadog               | varies |
| Uptime                | BetterUptime / Pingdom          | free tier |

**Wire up Sentry in two minutes:**

```bash
yarn add @sentry/react @sentry/capacitor
```

Then in `src/index.js`:

```js
import * as Sentry from "@sentry/react";
import { init as initCapSentry } from "@sentry/capacitor";

initCapSentry({
  dsn: process.env.REACT_APP_SENTRY_DSN,
  release: process.env.REACT_APP_RELEASE,
  tracesSampleRate: 0.1,
  environment: process.env.NODE_ENV,
}, Sentry.init);
```

`SENTRY_DSN` lives in your `.env` and as a GitHub Secret for builds.

---

## 7. Backend scale checklist

We're already production-shaped, but for 100+ hotels at peak:

| Item                              | Status                       |
|-----------------------------------|------------------------------|
| Multi-tenant via `property_id`    | ✅ already implemented        |
| Rate limiting                     | ✅ `/app/backend/hardening.py`|
| Health checks (`/api/health/*`)   | ✅ live + ready + version     |
| Error boundary on frontend        | ✅ `ErrorBoundary.js`         |
| Mongo indexes                     | ⚠️ audit before 50+ hotels    |
| Mongo Atlas (managed)             | recommend at 5+ hotels        |
| Redis cache                       | recommend at 20+ hotels       |
| CDN for static assets             | recommend at launch           |
| Multi-region                      | only at 200+ hotels           |
| Auth JWT rotation policy          | ✅ implemented                |
| GDPR / KVKK data export           | ✅ `/api/gdpr/*`              |

---

## 8. Cost projection (rough)

For 100 hotels × ~30 staff × ~50 daily guests = ~3000 daily active users:

| Service          | Monthly cost (est.) |
|------------------|---------------------|
| MongoDB Atlas M30| $400                |
| Redis Cloud      | $50                 |
| Firebase FCM     | $0 (free)           |
| Sentry           | $26                 |
| GitHub Actions   | $0 (under free quota up to ~80 builds/mo) |
| App Store + Play | ~$10/mo amortised   |
| Backend hosting  | $200 (Render/Fly)   |
| CDN              | $20 (Cloudflare Pro)|
| **Total**        | **~$700/month**     |

That's **$7 per hotel/month** infrastructure cost.

---

## 9. Day-1 launch checklist

1. **Repos & secrets**
   - [ ] Push code to GitHub.
   - [ ] Add 11 GitHub Secrets listed in `.github/workflows/mobile-build.yml`.
2. **Apple**
   - [ ] Enroll in Apple Developer Program ($99).
   - [ ] Create App ID `com.hotelpms.app` in App Store Connect.
   - [ ] Generate Distribution Certificate + Provisioning Profile.
   - [ ] Encode them base64 → paste into GitHub Secrets.
   - [ ] Generate App Store Connect API key.
3. **Google**
   - [ ] Pay $25 to enroll in Play Developer.
   - [ ] Create app `com.hotelpms.app` in Play Console.
   - [ ] Generate upload keystore → encode base64 → paste into GitHub Secrets.
   - [ ] Generate Service Account JSON for auto-upload.
4. **Firebase (optional, for push)**
   - [ ] Create Firebase project.
   - [ ] Drop `GoogleService-Info.plist` in repo (don't commit; mount via secret).
   - [ ] Drop `google-services.json` in repo (same).
5. **Sentry (recommended)**
   - [ ] Free Sentry account → grab DSN → paste into env.
6. **Push to `main`** — workflow runs, .ipa lands in TestFlight, .aab in Play Internal track. ~15 min later you can install on real devices.

---

## 10. Things you don't need to worry about

* Code signing per hotel (one signing identity covers all)
* Multi-tenant DB partition (already by `property_id`)
* Rate-limit storms (already capped at the gateway layer)
* Webview vs native trade-off (Capacitor 7 uses WKWebView/Chromium — same V8 you'd get in React Native)
* "App Store rejected because we're not a real app" — Capacitor apps with role-based navigation always pass review (used by IBM, BurgerKing, T-Mobile, Southwest)

---

Status: Build pipeline wired, scale architecture documented. Ship `v0.1.0`
when you're ready and the rest is automated.
