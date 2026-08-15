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

## Iter 505-507 sonrası (2026-08-02)
- DONE: Pay-by-Link tam paketi (QR + A5 yazdırma, AI dönüşüm ipuçları + etki takibi, analitik,
  toplu gönderim, EN/TR/DE e-posta/sayfa, oto-hatırlatma cron, haftalık pickup raporu cron).
- DONE: Pickup suite (24s kart, hedef+tahmin+geçmiş, kanal trendi, kanal düşüş uyarısı, güçlü gün bildirimi).
- DONE (düzeltme): Price Checker→CRM ve rate-limit ZATEN VARDI — tekrar önerme.
- DONE: Eco Sweep nightly cron (03:30 UTC, tüm tesisler).
- P0 (anahtar bekliyor): Resend, Twilio, OTA push, FCM, Lighthouse compset.
- P2: Native Mobile App (React Native), PCI/SOC2 dokümantasyonu, gerçek IoT/Airbnb adaptörleri.

## MVP Eklentisi — "Üç Bağımsız Rapor" Yol Haritası (Iter 511, 2026-06)
- [x] P0: Decision Assurance / Kanıtlı Autopilot (P10/P50/P90 + readback + gözlemsel etki) — TAMAM
- [x] P0: Data Quality Autopilot (mapping drift, orphan override auto-fix, birim anomalisi, bayat fiyat, mükerrer rez.) — TAMAM
- [x] P1: Net Contribution v2 (ödeme ücreti + iade/chargeback riski + OTA promo fonlama + direct edinim maliyeti) — TAMAM
- [x] P1: Group Sales OS lite (RFP yaşam döngüsü, wash/attrition, comp oda, teklif versiyonlama + PDF) — TAMAM
- [ ] P2: Alternatif tarih önerisi (grup teklifi için düşük displacement'lı tarih arama)
- [ ] P2: Oda tipi / rate-code seviyesinde bağımsız forecast
- [ ] P2: Kontrollü deney (A/B) altyapısı ile NEDENSEL etki ölçümü (şimdiki etiket: gözlemsel)
- [ ] P3: Search/flight/conference demand intelligence, portföyler arası substitution, LTV

## MVP Eklentisi 2 — Kalan Rapor Eksikleri (Iter 517, kullanıcı onayı: "mvp kayıt et ve yap sırayla")
- [x] a) P0: Open Pricing Optimizer (TAMAM iter 517) — segment×kanal×oda tipi hücre bazlı BAĞIMSIZ fiyat üreten motor
- [x] b) P0: Gelişmiş Overbooking (TAMAM iter 517) & Wash Control — kaynak/lead-time bazlı no-show modeli + günlük limit + walk riski
- [x] c) P1: A/B Nedensel Etki (TAMAM iter 517) — holdout deney altyapısı (uygulanmış vs tutulmuş kararların gerçek uplift'i)
- [x] d) P1: Oda tipi bazlı bağımsız forecast (TAMAM iter 517)
- [x] e) P2: Group Sales kalanları (TAMAM iter 518)

## MVP Eklentisi 3 — RMS Rakip Denetimi (Iter 532, 2026-08-14, kullanıcı talebi: "eksikleri tespit et, MVP'ye kaydet, sırayla tamamla")
DENETİM SONUCU: Kullanıcının paylaştığı 2026 RMS karşılaştırmasında "❌ YOK" denilen 4 özellik
ZATEN MEVCUT ve derin (bir sonraki agent tekrar önermesin):
- [x] Kâr-Öncelikli Fiyatlama (BEONx paritesi) → profit_pricing.py (CPOR + komisyon + ödeme ücreti + iade riski + gece yarısı Kâr Otopilotu)
- [x] Shoulder-Night Grup Displacement (FLYR/IDeaS paritesi) → group_displacement.py (shoulder_loss + breakeven_rate_net)
- [x] Attribute-Based Selling → abs_selling.py (widget + 90g gelir istatistiği)
- [x] RevPAM Toplantı Salonu Dinamik Fiyat → revpam.py (RevPASH + 14g öneri + apply)
GERÇEK EKSİKLER (bu iterasyonda tamamlandı):
- [x] a) Grup Alternatif Tarih Önerisi (FLYR "⚠️ Kısmen" kapandı) — POST /api/group-displacement/alternative-dates
      (±30 gün, 56 pencere taraması, komisyon-sonrası net katkı sıralaması, gain_vs_requested, Türkçe özet).
      UI: GroupDisplacementPanel "Alternatif Tarih Öner" butonu + karşılaştırma tablosu (gd-alt-*)
- [x] b) Tur Genişletme — RevenueRobotTour generic steps prop'u aldı; PANEL_TOURS ile Rate Calendar (4 adım)
      ve AI Dynamic Pricing (4 adım) turları; otomatik ilk açılış + breadcrumb'da manuel buton (rev-tour-btn-{tab})
- [x] c) Katkı Grafiği — impact-summary'ye daily_series (günlük delta + kümülatif) eklendi;
      RobotImpactCard'da SVG sparkline (robot-impact-sparkline)
KALAN (P2/P3): Oda tipi/rate-code bağımsız forecast zaten var (iter 517); söz konusu denetimde yeni eksik çıkmadı.

## MVP Eklentisi 4 — IDeaS.com + FLYR Site Denetimi (Iter 535, 2026-08-14)
Tamamlanan iterasyon içi işler: Arşiv Trend Grafiği (recharts, exec-archive-chart) + Demo Sunum Modu
(RmsComparisonPanel: 9 slaytlık tam ekran deck, ok tuşları+ESC, rmsc-present-btn / rmsc-slide-*).
SİTE DENETİMİ BULGULARI (ideas.com + flyrhospitality.com canlı tarandı):
Paritede olanlar (tekrar önerme): saatlik fiyatlama (intraday), explainable AI (pricing-explain),
forecast versiyonlama+onay+doğruluk karnesi (iter 449 + MAPE), grup displacement+blended rate,
Meeting&Event RM (RevPAM), bütçe-forecast-actual (iter 452), rate hurdles (hurdle_lrv).
GERÇEK EKSİKLER (önem sırasıyla):
- [ ] A) P1: Pazarlama Fırsat Radarı (IDeaS "Marketing Optimization" paritesi) — düşük talepli tarih
      pencerelerini bulup kampanya önerisi + beklenen ROI üretir, pazarlama görevine dönüştürür.
- [ ] B) P1: Doğal Dil BI Chat (FLYR "Insights — ask your data anything") — tüm PMS verisi üzerinde
      NL soru-cevap ("geçen hafta RevPAR'ı ne sürükledi?") + rol bazlı hazır dashboard görünümleri.
      Not: revenue_copilot var ama yalnız revenue bağlamı; genel BI chat yok.
- [ ] C) P2: Strateji Direktifleri (FLYR "influence the AI with strategic directions") — serbest metin
      direktif ("Eylül'de doluluk önceliği") fiyat motoru parametrelerine çevrilir, kural yazmadan.
- [ ] D) P2: ROI Hesaplayıcı (satış/landing lead aracı — FLYR ana sayfa paritesi; Price Checker'ın yanına).
- [ ] E) P3: Otopark RMS (IDeaS Car Park RMS) — otopark alanı için doluluk bazlı dinamik fiyat (niş).

## MVP Eklentisi 5 — Rakip Kıyası v2 (Iter 543, 2026-08-14, canlı web: Duetto/Mews/Lighthouse/trendler)
PARİTEDE (tekrar önerme): Open Pricing, 5dk-gün içi otomatik fiyat, grup displacement+min fiyat+alternatif
tarih (Mews'ten üstün), 24 ay forecast, dinamik kısıtlar, agentic yönetişim merdiveni (öneri/onaylı/sınırlı
otonomi+anomali dondurma), kaynak izlenebilirliği, RGI, kâr-öncelikli fiyat, MAPE.
EKSİKLER (öncelik sırasıyla):
- [x] 1) P1 Talep Takvimi (TAMAM iter 544) ısı haritası + tarihe tek tık AI analizi (Duetto Advance 2026 paritesi)
- [x] 2) P1 Tek Tık Toplu Geri Alma (TAMAM iter 544) — son auto-apply koşusunu tüm tarihlerde geri yükleme (agentic rollback standardı)
- [x] 3) P2 Grup Wash Projeksiyonu (TAMAM iter 545) — grup bloğu erime tahmini (Duetto BlockBuster)
- [x] 4) P2 TRevPOR / RevPAG / GOPPAR metrik paketi (TAMAM iter 545)
- [ ] 5) P3 Fonksiyon alanı online teklif/booking motoru (Duetto OpenSpace paritesi; RevPAM'e satış aracı)
- [~] E-posta uyarıları: teknik hazır, Resend API anahtarı bekliyor (BLOKLU)

## MVP Eklentisi 5b — Top-20 Rakip Listesi Kıyası (Iter 543 devam)
13/20 rakiple parite (IDeaS, Duetto, Atomize, RPG, Cloudbeds, Lighthouse*, FLYR, BEONx, Pricepoint,
happyhotel, Smartpricing, Profitroom, roomMaster). Revolution Plus/Otamiser = hizmet modeli.
YENİ eksikler (PriceLabs/Beyond/Wheelhouse'dan): 
- [x] 3) P1 Orphan Gap Doldurma (TAMAM iter 544) (yetim 1-2 gece boşluklarına oto indirim + min-stay gevşetme)
- [x] 4) P2 LOS Bazlı Fiyatlama (TAMAM iter 545) (3+/7+ gece kademeli fiyat önerisi)
Nihai sıra: 1-TalepTakvimi, 2-TopluGeriAlma, 3-OrphanGap, 4-LOS, 5-GrupWash, 6-TRevPOR/GOPPAR, 7-FonksiyonBooking (TAMAM iter 546).
*Lighthouse rate-shop gerçek verisi API anahtarı bekliyor (BLOKLU).

- [x] Canlı Kanal: HotelRunner ARI push altyapısı (iter 547) — GERÇEK moda geçiş için kullanıcıdan HR_ID+TOKEN bekleniyor

# ============================================================
# RM ROBOT MVP GAP ANALİZİ (2026-08-15, kullanıcı dokümanı: rm_robot_mvp_roadmap.md)
# 25 maddelik eksik listesi bizim kod tabanıyla karşılaştırıldı.
# ============================================================

## ZATEN BİZDE VAR (doküman istiyor, biz tamamlamışız) ✅
- B4 Net RevPAR hedef fonksiyonu → ai_pricing_engine (net contribution + CPOR + komisyon) ✅
- B5 Guardrail (kısmi) → min_rate_floors + LRV clamp + anomaly freeze + 1-click rollback ✅
- B7 Açıklanabilirlik → her öneri "neden" dökümü + AI context + freeze_reason ✅
- C6 İnsan onay akışı → öneri + onay/red UI + applied logu ✅
- B8 Model izleme → MAPE takibi + Error Sentinel + haftalık Exec Report PDF ✅
- B9 Servis mimarisi → FastAPI + supervisor + background loops ✅
- B3 Fiyat karar motoru → kural tablosu + occupancy/lead-time çarpanları ✅
- C2 Kanal yazma adaptörü → HotelRunner ARI push (canlı-hazır, kimlik bekliyor) + SiteMinder inbound + partner başvuru şablonu ✅
- C5/A6 Ölçüm protokolü → RGI Market Index Proof Panel (pazar-düzeltmeli kıyas) ✅
- A4 Dış talep sinyalleri → hava durumu + tatil takvimi (forecast_v2, historical_pricing) ✅
- Grup wash + LOS + parity monitor + orphan gap ✅
- D2 KVKK/GDPR modülleri → gdpr, eu_compliance, audit_trail ✅

## GERÇEK EKSİKLER — MVP'YE EKLENDİ (öncelik sırasıyla)
- [x] P0-G1 (TAMAM iter 549) (B5 tamamlama) GUARDRAIL SERTLEŞTİRME: tek adımda ±%15 üstü fiyat değişim bloğu +
      günlük push limiti (N/gün) + guardrail ihlal logu. (Mevcut min/max + freeze'in üstüne.)
- [x] P0-G2 (TAMAM iter 549) (C6 tamamlama) ÖNERİ KABUL ORANI METRİĞİ: kabul/red oranı raporu + red nedenleri
      etiketli veri olarak loglanır (modelin kör nokta haritası). Hedef: kabul ≥%70.
- [ ] P0-G3 (D1) UYUM İLKELERİ ANAYASASI: /app/memory/UYUM_ILKELERI_D1.md YAZILDI ✅ (2026-08-15).
      Kod tarafı: compset girdilerine source etiketi zorunluluğu eklenecek.
- [x] P1-G4 (TAMAM iter 549) (B1) BEKLENEN NET OTB: transient p_cancel skoru (rezervasyon başına iptal olasılığı,
      lead time + kanal + fiyat + LOS özellikleriyle) → brüt OTB'den düşülür. Grup wash'ın
      transient karşılığı. Fiyatlama motoru net OTB ile çalışır.
- [ ] P1-G5 (B6) İPTAL MODELİ KALİBRASYONU: isotonic regression + aylık yeniden kalibrasyon +
      kalibrasyon testi (AUC değil olasılık doğruluğu).
- [x] P1-G6 (TAMAM iter 549) SHADOW MODE: 4 hafta robot önerir ama push edilmez; robot önerisi vs otelin gerçek
      fiyat kararı karşılaştırma raporu (pilot güven inşası).
- [ ] P2-G7 (B2) TALEP SİMÜLATÖRÜ / BACKTEST: MNL seçim modeli + iptal modeli + basit rakip
      kuralı = sentetik pazar; politika backtesti (sabit fiyat vs dün+%X vs robot).
- [ ] P2-G8 (A2/D4) LİSANSLI RATE SHOPPING: mock compset verisi canlıda lisanslı kaynak/resmi
      API ile değiştirilecek. Scraping yasak (D4).
- [ ] P3-G9 (A3) ESNEKLİK ÖĞRENİMİ: canlıda %5-10 kontrollü fiyat randomizasyonu (yeterli hacim
      + otel onayı şartıyla) — bilinçli erteleme.
- [ ] P3-G10 (A5) HAVUZ VERİ HENDEĞİ: pilot sözleşmesine anonim veri kullanım izni + 3. otelden
      itibaren transfer learning ile soğuk başlangıç çözümü.

## TİCARİ KRİTİK YOL (kod değil — kullanıcı aksiyonu)
- C2 kanal yöneticisi partner BAŞVURUSUNU ŞİMDİ gönder (şablon hazır: PARTNER_BASVURU_KANAL_YONETICISI.md).
  En uzun süreç bu; HotelRunner adaptörümüz kimlik gelir gelmez canlıya geçer.
- C1 pilot otel: 1-3 otel görüşmesi; ücretsiz/indirimli pilot ↔ veri izni + vaka çalışması hakkı.
- C3 niş kararı: Türkiye 50-200 oda butik/orta segment + yerel kanal yöneticileri (mevcut analiz dosyalarıyla uyumlu).
- C4 birim ekonomi: oda başına aylık fiyat + rate shopper maliyeti hesabı.

# ============================================================
# RAKİP KARŞI-ANALİZ GAP'LERİ (2026-08-15) — rakipte VAR, bizde YOK/EKSİK
# Kaynak: rakibin bizim MVP dokümanımıza verdiği madde-madde cevap
# ============================================================

## P0 — Guardrail ve karar hijyeni (küçük, hızlı işler)
- [ ] K1 ASİMETRİK ADIM TAVANI: tek ±%15 yerine max_up / max_down ayrı limitler +
      cold-start modu (yeni otel: down=%0, up=%10) + güven skoruyla ölçekli tavan
      (guardrail_config'e alanlar + _apply_one genişletme, ~yarım gün)
- [ ] K2 KARAR SONUÇ TAKİBİ (outcome ledger): her uygulanan fiyat kararının GERÇEKLEŞEN
      sonucu (pickup, gelir farkı) append-only olay zincirine yazılır; kabul oranı paneline
      "karar → sonuç" kolonu (rakipteki decision_evaluation karşılığı)
- [ ] K3 KILL SWITCH: tüm robot push'larını tek tuşla durduran global acil durdurma
      (anomali dondurmanın üstünde, tesis+global seviye)

## P1 — Model olgunluğu
- [ ] K4 İPTAL MODELİ v2: p_cancel'e kanal + iade edilebilirlik (refundable/non-ref) +
      no-show özellikleri; Brier skoru + temporal validation + data-trust kapısı
      (G5 isotonic ile birleşik iş)
- [ ] K5 GÜVEN SEMANTİĞİ + KANIT ZARFI: her öneriye confidence skoru + dayanak kanıt
      listesi (veri tazeliği, örneklem, sinyal uyumu); düşük güven → öneri "gri" gösterilir
- [ ] K6 VERİ-GÜVEN KAPISI: girdi verisi bayat/eksik/sapan ise model o tarihi fiyatlamaz
      (data_quality modülüyle motor arasına kapı)
- [ ] K7 SHADOW ÇIKIŞ KRİTERLERİ: yazılı exit-criteria (ör. 4 hafta + uyum ≥%X + MAE ≤Y)
      dokümanı + panelde "canlıya geçmeye hazır" rozeti
- [ ] K8 EVENT SİNYALİ v2: etkinlik sinyaline mekan kapasitesi ağırlığı + otele uzaklık
      (rakipte Ticketmaster/PredictHQ venue-weighted; bizde public_events zayıf)

## P2 — Simülasyon ve fiyat bilimi
- [ ] K9 POINT-IN-TIME REPLAY BACKTEST: geçmiş bir günün verisiyle "o gün robot ne derdi"
      tekrarı + politika taraması + sold-out nedensel kazanç analizi (G7 kapsam genişletme)
- [ ] K10 FİYAT FAKTÖR ŞELALESİ: öneri açıklamasını yapılandırılmış waterfall görseline çevir
      (baz → lead → occ → STR → öğrenilmiş → guardrail kırpma, ₺ katkılarıyla)
- [ ] K11 BID-PRICE DISPLACEMENT AĞI: displacement + MinLOS/CTA/CTD kısıtlarını tek
      bid-price çerçevesinde birleştir (mevcut hurdle_lrv + restriction_advisor üstüne)
- [ ] K12 ESNEKLİK SHRINKAGE + GÜÇ ANALİZİ: G9 randomizasyonuna güç analizi + doğal
      deney tespiti + shrinkage kalibrasyonu ekle

## P3 — Ürünleşme
- [ ] K13 PUBLISHER SERTİFİKASYONU: kanala yazma öncesi otomatik sertifikasyon testi
      (test push + doğrulama + geri okuma) — HotelRunner canlıya geçişte zorunlu adım
- [ ] K14 ÇOKLU PMS/KANAL ADAPTÖRÜ: HotelRunner'a ek Cloudbeds/SiteMinder yazma adaptörleri
- [ ] K15 TEKNİK SÖZLEŞME DOKÜMANLARI: CONFIDENCE-SEMANTICS.md, PRICE-DOMAIN-CONTRACT.md,
      RATE-PROVENANCE.md (D1 anayasasının teknik ekleri)

## BİZDE VAR, RAKİPTE YOK (satış kozları — koru ve vitrine çıkar)
HotelRunner yazma adaptörü (TR pazarı) · hava durumu sinyali · KVKK/GDPR modülü ·
grup wash projeksiyonu · rate parity monitor + heatmap · RGI/MPI endeks raporu ·
haftalık Exec PDF · günlük push limiti (bizde VAR, rakipte YOK) · yazılı uyum anayasası (D1).

## STRATEJİK NOT — scraping çelişkisi
Rakip kendi scraping'ini canlı kullanıyor (Booking GraphQL) ve bunu hukuki açık olarak kabul
ediyor. Bizim D1 anayasamız scraping'i yasaklıyor — bu bizim SATIŞ AVANTAJIMIZ (EU AI Act +
OTA ToS uyumu). Karar: ilkeyi KORU, G8 lisanslı rate shopping bütçesini pilot sözleşmesine yaz.
