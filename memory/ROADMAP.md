# ROADMAP — Tek Kanonik Backlog (iter 377'de kod taramasıyla doğrulandı)

## ⛔ YAPILDI — BİR DAHA ÖNERME (kodda mevcut, tarih: doğrulama iterasyonu)
| Modül | Kod | Durum |
|---|---|---|
| F&B POS Integration Hub | `hotel_ops/fnb_pos_hub.py` + FnbPosHubPanel | iter 280 DONE |
| Meeting & Events (MICE) | `hotel_ops/meetings_sales.py` + MeetingsSalesPanel | iter 278 DONE |
| Demand Radar | `revenue_ext/demand_radar.py` | DONE |
| A/B Testing | `marketing/ab_test.py` + ABTestPanel | DONE |
| Carbon Reporting v2 | `hotel_ops/sustainability.py` + CarbonReportingV2Panel | DONE |
| Marketplace v1 | `platform_ext/marketplace.py` + MarketplacePanel | DONE (iter 377: tek modüle indirildi) |
| AI Status günlük toggle + auto-revert | `revenue_ext/rates_grid.py` | iter 376 DONE |
| Nightly insights cron + bildirim | `rates_grid.py` nightly_insights_loop | iter 376 DONE |
| Backend klasör yapılandırması | routes/ domain alt klasörleri | DONE |
| Service worker / PWA offline | `frontend/public/sw.js` + PWAInstall | DONE (geliştirilebilir) |
| Webhook dispatcher (gerçek HTTP) | `routes/helpers.py fire_webhooks` (httpx+secret) | DONE (retry/HMAC-imza eklenebilir) |
| SiteMinder middleware adapter | `distribution/siteminder_adapter.py` | iter 375 DONE |
| Direct Booking Conversion Engine | `integrations_pkg/direct_conversion.py` | iter 375-377 DONE |
| OTA Commission Dashboard | `integrations_pkg/ota_commission.py` | iter 374 DONE |
| 2-Year Forecast | `revenue_ext/forecast_v2.py` | DONE |
| External Loyalty (Marriott/Hilton) | `integrations_pkg/external_loyalty.py` | DONE |
| Mobile home | `components/MobileHome.js` | DONE |
| Booking Engine v2 + abandoned cart | `booking-engine/*` | iter 277 DONE |
| Owner Portal + PDF + self-service | `/api/owners`, `/api/owner-auth`, /owner route | iter 277-282 DONE |
| Spa & Activities | `/api/spa/*` | iter 277 DONE |
| Loyalty Tiers | `/api/loyalty-tiers/*` | iter 277 DONE |
| Budget vs Actual | `/api/budget/*` | iter 277 DONE |
| Compset Auto-Discovery (mock pool) | `/api/compset/*` | iter 277 DONE |
| Partner Webhooks & API Keys | `/api/partner/*` | iter 277 DONE |

## P0 — Kullanıcı API anahtarı gerektirir (BLOKE — anahtar gelince yap)
- Gerçek OTA rate push: rate_sync_queue → Booking.com/Expedia (OTA credentials gerekli)
- Twilio (gerçek WhatsApp/SMS + WhatsApp Voice inbound tamamlama)
- Resend production anahtarı (şu an mock fallback)
- Native push (FCM/APNs anahtarları; Capacitor)
- Gerçek compset rate scanner (OTA Insight / Lighthouse anahtarı; şu an mock pool)

## P1 — Anahtar gerektirmeden yapılabilir GERÇEK eksikler
- Webhook dispatcher'a retry + HMAC-SHA256 imza + exponential backoff
- sw.js offline stratejisini genişlet (route cache + offline fallback sayfası)
- App.js refactor (5200 satır → görünüm bazlı alt dosyalar; davranış değişmeden)
- server.py tick worker'larını ayrı worker modülüne taşı
- ~~React linter uyarıları~~ YAPILDI (iter 379, sıfır uyarı)
- Legacy modal görünümlerini (analytics/templates/integrations/alerts) inline panele çevirme (UX iyileştirme, şu an modal olarak çalışıyorlar)

## P2
- PCI-DSS / SOC 2 hazırlık dokümantasyonu
- Native Mobile App (React Native) — kullanıcı talimatıyla backlog'da
- Kupon dönüşüm A/B ölçümü (farklı indirim oranlarını test et)

## Süreç Kuralı
Her iterasyonda: yapılan işi CHANGELOG.md'ye ekle, bu dosyada ilgili maddeyi
"YAPILDI" tablosuna taşı. Yeni öneri yapmadan önce YAPILDI tablosunu kontrol et.
