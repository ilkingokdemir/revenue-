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
| Tahminsel Housekeeping | `hotel_ops/predictive_hk.py` + PredictiveHkPanel | iter 380 DONE |
| Hurdle Rate & LRV (Yield Guard) | `revenue_ext/hurdle_lrv.py` + HurdleLrvPanel | iter 381 DONE |
| AI Pricing LRV Guardrail | `ai_pricing_engine.py` + hurdle toggle | iter 382 DONE |
| Segment Forecast (Duetto tarzı) | `forecast_v2.py /segments` + Segmentler sekmesi | iter 382 DONE |
| Tahminsel HK → Vardiya önerisi | `predictive_hk.py /suggest-shifts` + buton | iter 382 DONE |
| Sosyal Kanıt Widget'ı (booking widget) | `booking_widget.py /social-proof` + SocialProofBadge | iter 384 DONE |
| Sosyal Kanıt A/B Testi (rozet açık/kapalı) | `ab_test.py` entegrasyonu + 5 tesiste deney seed | iter 385 DONE |
| Rebook Kampanya Döngüsü (kupon+e-posta+scheduler) | `guests/rebook.py` + RebookPanel | iter 392 DONE |
| Terk Edilmiş Rezervasyon Kurtarma | `pms/abandoned_recovery.py` + DCV "Terk Edilmiş" sekmesi | iter 393 DONE |
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
| NL Automation Builder (Mews Automations) | `platform_ext/nl_automation.py` + NlRuleBuilder | iter 432 DONE |
| Inbox AI Agent (Mews Guest Messaging) | `integrations_pkg/inbox_agent.py` + AgentBar | iter 432 DONE |
| AR Mutabakat Agent'ı (Mews AR) | `finance_ext/ar_recon_agent.py` + ArReconPanel | iter 432 DONE |
| Waitlist + otomatik teklif | `pms/waitlist.py` + WaitlistPanel + widget formu | iter 432 DONE |
| HK Auto-Dispatch (iş yükü dengeleme + öncelik) | `hotel_ops/hk_dispatch.py` + HkDispatchPanel | iter 433 DONE |
| Rezervasyon Kalite Kontrolü (RoboSize paritesi) | `pms/res_quality.py` + ResQualityPanel | iter 433 DONE |
| FTE/Kazanılan Saat metriği | automation_roi.py /time-saved + roi-time-saved kartı | iter 433 DONE |
| Loyalty Tiers + benefits + auto-upgrade + CRM kartı | loyalty_tiers/loyalty_tier/loyalty_v2/loyalty_auto | ÖNCEDEN MEVCUT — tekrar önerme |
| Tur Operatörü Kontenjan (Allotment) Yönetimi | `distribution/allotments.py` + AllotmentsPanel + cron allotment_release | iter 446 DONE |

## P0 — Kullanıcı API anahtarı gerektirir (BLOKE — anahtar gelince yap)
- Gerçek OTA rate push: rate_sync_queue → Booking.com/Expedia (OTA credentials gerekli)
- Twilio (gerçek WhatsApp/SMS + WhatsApp Voice inbound tamamlama)
- Resend production anahtarı (şu an mock fallback)
- Native push (FCM/APNs anahtarları; Capacitor)
- Gerçek compset rate scanner (OTA Insight / Lighthouse anahtarı; şu an mock pool)

## P1 — Anahtar gerektirmeden yapılabilir GERÇEK eksikler
- ~~Webhook dispatcher'a retry + HMAC-SHA256 imza + exponential backoff~~ YAPILDI (helpers.py fire_webhooks: 3 deneme + imza; iter 384'te doğrulandı)
- ~~sw.js offline stratejisini genişlet (route cache + offline fallback sayfası)~~ YAPILDI (iter 387: API cache + offline.html + OfflineBanner)
- ~~Offline aksiyon kuyruğu (HK görev/oda durumu yazmaları)~~ YAPILDI (iter 388: offlineQueue.js + banner sayacı)
- ~~App.js refactor (5200 satır → görünüm bazlı alt dosyalar; davranış değişmeden)~~ FAZ 1+2 YAPILDI (iter 386+390: navigasyon config + perm map + 8 büyük panel bileşeni ayrıldı, 5230→2531 satır). Kalan opsiyonel faz: Dashboard render bloklarının ayrıştırılması
- ~~server.py tick worker'larını ayrı worker modülüne taşı~~ YAPILDI (iter 466: backend/workers.py — scheduled_checkout_loop + reports_loop)
- ~~React linter uyarıları~~ YAPILDI (iter 379, sıfır uyarı)
- ~~Legacy modal görünümlerini (analytics/templates/integrations/alerts/reports/branding/approvals) inline panele çevir~~ YAPILDI (iter 389, test ajanı 7/7 PASS)

## P2
- PCI-DSS / SOC 2 hazırlık dokümantasyonu
- Native Mobile App (React Native) — kullanıcı talimatıyla backlog'da
- ~~Kupon dönüşüm A/B ölçümü (farklı indirim oranlarını test et)~~ YAPILDI (iter 466: rebook.py sweep-ab + discount-ab; RebookPanel A/B bölümü, Wilson LB + marj skoru ile kazanan)

## Süreç Kuralı
Her iterasyonda: yapılan işi CHANGELOG.md'ye ekle, bu dosyada ilgili maddeyi
"YAPILDI" tablosuna taşı. Yeni öneri yapmadan önce YAPILDI tablosunu kontrol et.

## FLYR Hospitality fark analizi (iter 449, detay: FLYR_GAP_REPORT.md)
| Forecast Planlama (sürüm+kilit+onay+yorum+karşılaştırma) | revenue_ext/forecast_plans.py + ForecastPlansPanel | iter 449 DONE |
Kalan FLYR boşlukları (P1 adayı): ~~gün-içi re-price~~ (iter 450 DONE), ~~AI MLOS/CTA kısıtlama önerileri~~ (iter 451 DONE),
~~forecast belirsizlik bandı~~ (iter 454 DONE), ~~grup blended-rate optimizasyonu~~ (iter 453 DONE), ~~bütçe-forecast-actual üçlü görünüm~~ (iter 452 DONE).

## Iter 478 sonrası (2026-07-27)
- DONE: Akıllı Oda / IoT Kontrol Merkezi (smart_rooms.py + SmartRoomsPanel) — sahneler, Eco Sweep, enerji tasarrufu KPI.
- DONE: F&B ↔ Sadakat köprüsü — tab kapatırken tier F&B indirimi otomatik uygulanıyor (apply_loyalty).
- P1 kalan: Native Mobile App (React Native), Eco Sweep'in workers.py'ye gece cron'u olarak bağlanması (şu an manuel buton).
- P2: IoT gerçek donanım sağlayıcı adaptörleri (şu an simülasyon).

## Iter 479 sonrası (2026-07-28) — RoomPriceGenie paritesi
- DONE: 18 ay fiyat ufku + baz fiyat eğrisi, Airbnb/STR compset sekmesi, ücretsiz Price Checker lead aracı.
- P1 kalan: Price Checker lead'lerini Demo Leads CRM pipeline'ına bağlama; price-check endpoint'ine rate-limit.
- P2: Gerçek Airbnb scraper adaptörü (şu an simülasyon), Native Mobile App.
