# MyHotelBox (PMS) + ReveniQ (RMS) — PRD

## Orijinal Problem
Üst segment rakiplerle (Mews, Atomize, SiteMinder, Cloudbeds) %100 pariteli, tam fonksiyonel
full-stack otel platformu: React + FastAPI + MongoDB. Gelişmiş Revenue Management (ReveniQ),
Property Management (MyHotelBox), OTA senkronizasyonu, otomasyon, çoklu tesis.

- **Kullanıcı dili: TÜRKÇE** — tüm iletişim Türkçe yapılır.
- Branding: **MyHotelBox** (PMS) ve **ReveniQ** (RMS). Değiştirme.

## Mimari
- Backend: FastAPI, `/app/backend/server.py` + `routes/` altında domain klasörleri
  (pms, revenue_ext, finance_ext, guests, hotel_ops, integrations_pkg, distribution,
  marketing, platform_ext, staff_ops, ai). ~2200 route, 285 API prefix'i.
- Frontend: React (`App.js` router+sidebar, `lazyPanels.js` lazy kayıt,
  `components/dashboard/*Panel.js`). PWA aktif (public/sw.js).
- DB: MongoDB (MONGO_URL + DB_NAME env). ObjectId asla dışarı sızmaz (id: uuid4 string).
- Entegrasyonlar: Emergent LLM Key (GPT-4o-mini, Whisper, Nano Banana), Stripe test key,
  Resend (mock fallback), Slack/WhatsApp webhook mock.

## ⚠️ MÜKERRERLİK ÖNLEME KURALI (iter 377'de kullanıcı şikayetiyle eklendi)
Yeni özellik ÖNERMEDEN veya YAPMADAN önce MUTLAKA kontrol et:
1. `ROADMAP.md`'deki "MEVCUT MODÜLLER" envanterine bak.
2. `fd <isim> /app/backend/routes` + `grep -rn <prefix> /app/frontend/src` ile kod tara.
3. Route çakışması taraması: server.py app.routes dump + normalize path dedupe.
Geçmişte F&B POS (iter 280), MICE (iter 278), Demand Radar, A/B test, Carbon v2,
Marketplace zaten yapılmışken tekrar önerildi — bir daha ASLA.

## Dosyalar
- `ROADMAP.md` → tek kanonik backlog + mevcut modül envanteri (her iterasyonda güncelle)
- `CHANGELOG.md` → tüm iterasyon geçmişi (iter 262-377). Yeni iterasyonları buraya ekle.
- `test_credentials.md` → test hesapları

## Test Credentials
- Admin: `admin@hotelbox.com` / `HotelAdmin2026!` (login cevabında token alanı: `token`)
- Preview: frontend/.env REACT_APP_BACKEND_URL değerini kullan

## Son Durum (Iter 377, 2026-07-08) — Kod Denetimi & Konsolidasyon
- Tüm route'lar tarandı: 7 path çakışması bulundu, 0'a indirildi.
- Silinen ölü kod: `integrations_pkg/marketplace.py`, `IntegrationsMarketplace.js`,
  `SpaceBookingsPanel.js`, reviews.py'deki mükerrer `/`+`/status`, finance_pl.py'deki
  mükerrer expenses CRUD.
- Düzeltilen gerçek bug: Stripe webhook 2 kez tanımlıydı — eksik olan kazanıyordu;
  tek kanonik handler artık payments.py'de (booking confirm + tip + email log).
- Spaces çakışması: public endpoint `/api/spaces/public/{property_id}` olarak ayrıldı.
- Kupon deep-link: `/book/{property}?coupon=DIRECT-XXX` otomatik uygular; promo
  e-postasına "Şimdi Rezervasyon Yap" CTA butonu eklendi (PUBLIC_BASE_URL env).

## Son Durum (Iter 446, 2026-07-26) — Tur Operatörü Kontenjan (Allotment) Yönetimi
- `distribution/allotments.py` (/api/allotments): operatör kontratları, pickup, stop-sale,
  takvim grid, otomatik release (cron 05:45). AllotmentsPanel (System > Tur operatörü kontenjanları).
- E2E curl + UI ekran görüntüsü ile doğrulandı. Detay: CHANGELOG.md iter 446.

## Son Durum (Iter 380, 2026-07-08) — Nihai API Denetimi & Tahminsel Housekeeping
- 500 Hata Denetimi TAMAMLANDI: 2187 endpoint mutasyon taramasıyla test edildi.
  - `server.py`'ye global `bson.errors.InvalidId` + `BSONError` handler eklendi (400 döner).
  - `guests/profiles PUT` ve `maintenance/issues PUT` — olmayan ID'de None.get() crash → 404 düzeltildi.
  - Sonuç: SIFIR 500 hatası (mutasyon scripti: `/app/backend/tests/mutation_sweep.py`).
- YENİ MODÜL: Tahminsel Housekeeping (`routes/hotel_ops/predictive_hk.py` + `PredictiveHkPanel.js`)
  - `GET /api/housekeeping/predictive/{pid}?days=7` → günlük çıkış/varış/konaklama sayıları,
    iş yükü (dk/saat), gerekli personel tahmini, en yoğun gün.
  - `POST /api/housekeeping/predictive/{pid}/generate {date}` → otomatik görev üretimi
    (checkout_clean 45dk / stayover_refresh 20dk / arrival_inspection 10dk),
    kat görevlilerine round-robin atama, kopya engelleme (auto_generated + room + date + subtype).
  - UI: Housekeeping Hub → "Tahminsel Plan" sekmesi (7 günlük bar grafiği + gün detayı + tek tık görev üretimi).
- Not: AI Upsell Engine ve RFM Segmentasyon ZATEN MEVCUT (upsell_engine.py, guest_rfm.py) — kopya iş yapılmadı.

## Son Durum (Iter 381, 2026-07-08) — RMS Denetimi + Yield Guard (Hurdle/LRV)
- REVENUE DENETİMİ TAMAMLANDI: 27 revenue_ext modülünün tamamı server.py'de kayıtlı,
  tamamının UI bağlantısı var (yetim modül YOK). 12 kritik endpoint geçerli girdiyle
  spot-check edildi → hepsi 200.
- Rakip analizi (IDeaS/Duetto) sonucu GERÇEK eksik: Hurdle Rate / Last Room Value → EKLENDİ.
- YENİ MODÜL: Yield Guard (`revenue_ext/hurdle_lrv.py` + `HurdleLrvPanel.js`)
  - `GET /api/revenue/hurdle/{pid}?days=30` → günlük LRV (baz ADR × doluluk bandı × pickup boost),
    talep bandı (low→peak), DOW bazlı tarihsel no-show oranı, overbooking önerisi, aksiyon önerileri.
  - `POST /api/revenue/hurdle/{pid}/config` → min fiyat tabanı + overbooking limiti (422 validasyonlu).
  - UI: Revenue & rates → Tools → "Hurdle rate & LRV" (30 günlük tablo + aksiyon kutusu + config).
- Kalan RMS eksiği (bilinçli backlog): segment bazlı forecast kırılımı (Duetto tarzı) — P2.

## Son Durum (Iter 382, 2026-07-08) — 3 Eksik Tamamlandı (P2'ler kapatıldı)
1. AI PRICING LRV GUARDRAIL: `ai_pricing_engine.py` accept + run-auto-apply + cron helper,
   `hurdle_lrv.py compute_lrv_floor()` ile fiyatı LRV tabanına kelepçeler
   (test: £40 önerisi → £136.8'e yükseltildi, rationale'a not düşülür, `lrv_clamped` sayacı döner).
   Hurdle config'e `pricing_guardrail` toggle eklendi (UI: HurdleLrvPanel checkbox).
2. SEGMENT FORECAST (Duetto tarzı): `GET /api/forecast-v2/segments/{pid}?months=6`
   → 12 ay segment geçmişi (Direkt/OTA/Acente/Kurumsal/Diğer) + 6 ay tahmin
   (geçen yıl aynı ay × yoy trend, OTB tabanlı max). UI: ForecastV2Panel "Segmentler" sekmesi.
3. TAHMİNSEL HK → VARDİYA: `POST /api/housekeeping/predictive/{pid}/suggest-shifts {date}`
   → staff_needed kadar housekeeper'a "planned" shift_entries (dedupe'lu).
   UI: PredictiveHkPanel "Vardiya Önerisi (N)" butonu.

## Son Durum (Iter 383, 2026-07-08) — TAM SİSTEM DENETİMİ (kullanıcı talebi)
- Test ajanı FULL AUDIT: Backend 55/55 PASS, frontend tüm paneller PASS, SIFIR 5xx.
- Test suite: `/app/tests/test_iter383_full_audit.py` (pytest, ~9sn, 55 test).
- Bulunan tek eksik ve FIX: `/checkin/{slug}` rotası eşleşmiyordu (yalnızca `/checkin` exact match) →
  `startsWith("/checkin/")` eklendi; artık dostane "Geçersiz check-in bağlantısı" ekranı gösteriliyor
  (dikkat: `/checkin-kiosk/` rotasını yutmamak için `/checkin/` slash'lı prefix kullanıldı).

## Son Durum (Iter 384, 2026-07-08) — Sosyal Kanıt Widget'ı (Booking Widget dönüşüm artırıcı)
- YENİ PUBLIC ENDPOINT: `GET /api/booking-widget/social-proof/{pid}` (auth yok)
  → gerçek veriden: son 24s/7g rezervasyon sayısı, son rezervasyon kaç dk önce,
  son 30 dk görüntüleyen sayısı (widget_views koleksiyonu, 24s'ten eski kayıtlar otomatik silinir),
  en yeni 4+ puanlı yorum snippet'i (boş metinler filtrelenir).
- UI: `BookingWidgetPage.js` → `SocialProofBadge` bileşeni — sol altta 7 sn'de bir dönen
  animasyonlu rozet (🔥 rezervasyon / 🛎️ son rezervasyon / 👀 görüntüleyen / ⭐ yorum),
  kapatılabilir, embed modda ve onay sayfasında gizli. testid: be-social-proof-badge.

## Son Durum (Iter 385, 2026-07-08) — Sosyal Kanıt A/B Testi Entegrasyonu
- BookingWidgetPage → mevcut A/B motoruna bağlandı (`/api/ab/assign` + `/api/ab/track`):
  - Kalıcı session (localStorage `be_session_id`), deterministik varyant ataması.
  - `badge_on` (payload.show=true) / `badge_off` — rozet varyanta göre gösterilir/gizlenir.
  - Dönüşüm takibi: `check_availability` event + `booking_completed` (value=toplam fiyat);
    Stripe redirect dönüşünde de localStorage'daki varyantla track edilir.
- 5 tesiste "social_proof_badge" deneyi seed edildi (50/50, goal: booking_completed).
- Sonuçlar: A/B Testing panelinden (Wilson lower bound ile lider işaretleme mevcut motorda).
- E2E doğrulandı: assign deterministik ✓, track ✓, results ✓, frontend varyant-rozet tutarlılığı ✓.
- Not: Webhook retry + HMAC ROADMAP'te eksik görünüyordu ama kodda ZATEN VARDI (fire_webhooks) — ROADMAP düzeltildi.

## Son Durum (Iter 386, 2026-07-08) — App.js Refactor (Faz 1: Navigasyon)
- App.js 5230 → 4665 satır. Davranış DEĞİŞMEDİ (regresyon: 55/55 pytest + nav ekran testleri geçti).
- Yeni dosyalar: `src/navigation/menuSections.js` (buildMenuSections(t, user) — sidebar menü tanımı),
  `src/navigation/permMap.js` (SIDEBAR_PERM_MAP — testId → izin anahtarı).
- 64 kullanılmayan phosphor icon import'u App.js'ten temizlendi (110 → 46).
- Sonraki refactor fazları (backlog): görünüm render bloklarının alt dosyalara taşınması, public route dispatcher ayrımı.

## Son Durum (Iter 387, 2026-07-09) — PWA Offline Güçlendirme
- `sw.js` v2: GET /api/* network-first + başarılı yanıtlar API_CACHE'e kopyalanır (300 kayıt cap),
  bağlantı yokken son kopyayı `X-Served-From: sw-cache` header'ıyla sunar.
  Hassas yollar cache DIŞI: /api/auth/, /api/payments, /api/stripe, /api/ab/, social-proof.
- `offline.html`: markalı çevrimdışı fallback sayfası (navigasyon: cached index → offline.html).
- `OfflineBanner.js`: online/offline event dinleyicili üst banner ("Çevrimdışı mod" amber /
  "Bağlantı geri geldi" yeşil 4sn). App.js köküne eklendi. testid: offline-banner.
- Test: SW v2 kontrolde ✓, offline'da dashboard cached veriyle render ✓, banner iki yön ✓.

## Son Durum (Iter 388, 2026-07-09) — Offline Aksiyon Kuyruğu
- `src/lib/offlineQueue.js`: axios response interceptor — network hatasında whitelist'teki
  yazma istekleri (housekeeping tasks/rooms status/maintenance, maintenance issues) localStorage
  kuyruğuna alınır, sentetik 202 {queued:true} döner (UI kırılmaz).
- Online olunca otomatik flush: başarılı → toast "N işlem senkronize edildi"; 4xx → drop; ağ/5xx → kuyrukta kalır.
- OfflineBanner kuyruğu gösterir: "· N işlem kuyrukta" (offline-queue-changed event).
- Debug/test kancası: window.__offlineQueue {flushQueue, getQueueCount, axios}.
- E2E DOĞRULANDI: offline PUT → 202 queued + banner "1 işlem kuyrukta" → online flush → kuyruk 0
  → DB'de task status gerçekten 'in_progress' oldu ✓.
- Bilinen sınır: offline'dayken DAHA ÖNCE ZİYARET EDİLMEMİŞ lazy chunk yüklenemez (ErrorBoundary
  dostane hata gösterir; SW ziyaret edilen chunk'ları cache'ler — production'da normal davranış).

## Son Durum (Iter 389, 2026-07-09) — Legacy Modal Görünümleri → Inline Panel
- 7 modal görünüm inline sayfa paneline çevrildi: analytics, templates, integrations,
  alerts (NotificationSettings), reports, branding, approvals.
- Yöntem: App.js'e InlineContent/InlineHeader/InlineTitle shell'leri eklendi; App.js içi
  bileşenler (NotificationSettings, TemplatesManager, ApprovalQueuePanel) scoped replace ile
  çevrildi; 4 dashboard dosyasında (AnalyticsPanel, IntegrationsPanel, BrandingPanel,
  ReportsSettings) Dialog importları lokal inline shell'lerle değiştirildi (iç içerik değişmedi).
- Dialog sarmalayıcıları ve "Araç penceresi açık" backdrop placeholder'ı App.js'ten kaldırıldı.
- Test ajanı frontend regresyonu: 7/7 PASS, gerçek Dialog'lar hâlâ çalışıyor, scroll kilidi yok.
- Test ajanı notu (backlog): App.js içi bileşenleri kendi dosyalarına taşı (Refactor Faz 2 ile).

## Son Durum (Iter 390, 2026-07-09) — App.js Refactor Faz 2 TAMAMLANDI
- App.js 4645 → 2531 satır (Faz 1+2 toplam: 5230 → 2531, %52 küçülme).
- Yeni dosyalar:
  - `src/panels/InlineShell.js` (InlineContent/Header/Title shell'leri)
  - `src/panels/ReviewToolsPanels.js` (AIResponsePanel, NotificationSettings, TemplatesManager, ApprovalQueuePanel)
  - `src/panels/SystemToolsPanels.js` (UserManagementPanel, ApiConnectionPanel, WebhooksPanel, IntegrationGuidePanel)
  - StarRating/PlatformBadge/StatsCard/ReviewCard artık `components/dashboard/ReviewComponents.jsx`'ten import ediliyor (App.js'teki kopyalar silindi).
- DİKKAT (ders): İlk deneme regex tabanlı import pruner stale-offset yüzünden dosyaları bozdu →
  git checkout ile geri alınıp marker-tabanlı temiz extraction yapıldı. Import pruning YAPILMADI
  (panel dosyalarında kullanılmayan importlar var — zararsız, webpack temiz derliyor).
- Regresyon: babel parse 4/4 OK, webpack temiz, 6 görünüm canlı test edildi (analytics/templates/
  approvals/api-connection/webhooks/integrations) → hepsi hatasız render.

## Son Durum (Iter 391, 2026-07-09) — Refactor Sonrası TAM SİSTEM DENETİMİ
- Backend: 55/55 pytest audit GEÇTİ (7.5sn; ilk koşudaki tek fail geçici yüktü, izole geçti).
- Frontend (test ajanı, iteration_390.json): %100 — 9 sidebar bölümü, 14 refactor'lu görünüm,
  forecast Segmentler, predictive HK, hurdle LRV, komut paleti, public booking + sosyal kanıt.
  SIFIR error boundary, SIFIR boş içerik.
- Minör düzeltme: CommandPalette CommandItem key'i `${group}-${it.id}` yapıldı (duplicate key uyarısı).
- Bilinçli bırakılan: login öncesi 2× 401 console isteği (/me auth probe — beklenen davranış).
- Test ajanı gelecek önerisi (backlog): App.js kalan 2531 satırı domain bazlı bölme (opsiyonel Faz 3),
  sidebar bölüm başlığına tıklayınca otomatik görünüm açma davranışını chevron'dan ayırma (UX tercihi).

## Son Durum (Iter 392, 2026-07-09) — Rebook Kampanya Döngüsü TAMAMLANDI
- `routes/guests/rebook.py` yeniden yazıldı (iskelet → tam döngü):
  - Sweep artık GERÇEK tek kullanımlık kupon üretir (REBOOK-XXXXXX, direct_conversion_offers'a
    yazılır → widget /direct-conversion/validate ile doğrular, redeem edilir).
  - E-posta gönderimi: Resend (RESEND_API_KEY yoksa MOCK log) — markalı HTML şablon,
    deep-link: /book/{pid}?coupon=CODE&rebook=TOKEN.
  - Dispatches endpoint'i redeemed + conversion_rate döner.
  - `router.run_sweep_internal` + server.py JOB_HANDLERS["rebook_sweep"] → günlük otomatik tarama;
    5 tesiste scheduler config AKTİF edildi.
- Widget: ?rebook=token parametresi tıklama takibini tetikler (GET /rebook/token/{t}).
- RebookPanel: kupon kolonu + durum (gönderildi/mock) + Redeemed/Conversion kartları.
- E2E DOĞRULANDI: sweep 8 misafir → 8 kupon + 8 mock e-posta; kupon validate OK (%12);
  token resolve coupon_code döner; rerun dedupe 0; panel 8 satır + %12.5 tıklama gösterdi.
- NOT: E-posta MOCK modda (RESEND_API_KEY yok) — key gelince otomatik gerçek gönderime geçer.

## Son Durum (Iter 393, 2026-07-09) — Terk Edilmiş Rezervasyon Kurtarma
- `routes/pms/abandoned_recovery.py`: capture (public, e-posta+arama bağlamı upsert),
  convert (public, rezervasyon tamamlanınca; email_sent ise recovered=True),
  run-recovery (admin) + `JOB_HANDLERS["abandoned_recovery"]` (5 tesiste scheduler AKTİF).
  Kurtarma: 1-48 saat arası terk edilmiş sepetlere %5 COMEBACK-XXXXXX kuponu (direct_conversion_offers,
  7 gün geçerli) + devam linki `/book/{pid}?coupon=..&checkin=..&checkout=..` (Resend/mock e-posta).
- Widget: guest details adımında e-posta 1.5sn debounce ile otomatik yakalanır (blur güvenilmezdi);
  booking success her iki yolda (pay-at-property + Stripe dönüşü) convert çağrılır;
  ?checkin=&checkout= deep-link tarihleri uygular (default tarih effect'i URL paramına saygılı).
- DirectConversionPanel: yeni "Terk Edilmiş Kurtarma" sekmesi (4 stat kartı + tablo + "Şimdi Tara & Gönder").
- E2E DOĞRULANDI: capture → 2h yaşlandırma → recovery (1 e-posta mock + kupon) → kupon validate %5 →
  convert → recovered=True, panel %100 kurtarma oranı gösterdi. Rerun eligible=0 (dedupe).
- Not: Eski booking_engine_v2 /cart/track aynı koleksiyonu kullanıyordu (sadece listeleme, döngü yoktu) —
  stats endpoint'i legacy doc'lara .get() ile uyumlu.

## Son Durum (Iter 394, 2026-07-09) — Otomasyon ROI + Fırsat Radarı TAMAMLANDI
- ROI panosu bug'ı ÇÖZÜLDÜ: kod hatası yoktu — önceki test kapalı akordeon menüyü ("Revenue & rates")
  açmadan `automation-roi-btn`'e ulaşmaya çalışıyordu. Doğru akışla (bölüm başlığına tıkla → buton) UI doğrulandı.
- `GET /api/automation/roi/{property_id}?days=` — atfedilen gelir: rebook, comeback (sepet), OTA→direkt
  (komisyon tasarrufu dahil), upsell, AI fiyatlama (tahmini). E2E doğrulandı (£1,930 gerçek veri).
- YENİ: `GET /api/automation/opportunities/{property_id}` — Fırsat Radarı ("masada kalan para"):
  1) Rebook gönderilmemiş checked-out misafirler (son 90g, %6 dönüşüm varsayımı)
  2) E-postalanmamış terk sepetler (son 14g, %10 kurtarma) — şema uyumu: total_price/rate + email_sent_at
  3) Upsell teklifi almamış yaklaşan varışlar (14g, gecelik %12)
  4) Kuponlanmamış OTA misafirleri (%18 komisyon riski × %20 tekrar olasılığı)
- AutomationRoiPanel'e "Fırsat Radarı" bölümü eklendi: potansiyel gelir kartları + aksiyon butonları
  (onNavigate ile rebook / ai-predictions / direct-conversion panellerine derin bağlantı).
- E2E DOĞRULANDI: curl (388 rebook fırsatı, ~£12,534 toplam potansiyel) + screenshot (radar + aksiyon butonları görünür).

## Son Durum (Iter 395, 2026-07-09) — Fırsat Radarı "Hepsini Düzelt" (Auto-Fix) TAMAMLANDI
- `POST /api/automation/opportunities/{pid}/auto-fix`: tek tıkla rebook backfill taraması
  (7-90 gün önceki check-out'lar, run_sweep_internal döngüsü) + terk sepet kurtarma
  (run_recovery_internal). server.py runners dict ile enjekte edildi. Sonuç `automation_fix_runs`'a loglanıyor.
- Radar rebook sorgusu 7 gün eşiğine hizalandı (auto-fix kapsamıyla tutarlı).
- AutomationRoiPanel: "Hepsini Düzelt" butonu (auto-fix-btn) + sonuç toast'u + otomatik yenileme.
- E2E DOĞRULANDI: 388 fırsat → auto-fix (367 kupon + 1 sepet e-postası, <1sn) → rebook 0, sepet 0,
  direct_conversion 0; rerun dedupe queued=0. UI: buton tıklandı, radar yenilendi (~£668 sadece upsell kaldı).
- Düzeltilen bug: `fixing` state tanımı eksikti ("fixing is not defined" crash) → eklendi, doğrulandı.

## Son Durum (Iter 396, 2026-07-09) — Upsell Auto-Pilot TAMAMLANDI
- `routes/ai/upsell_autopilot.py`: yüksek skorlu (top_score>=60, _score_upsell_propensity) yaklaşan
  varışlara (14g) otomatik markalı upsell e-postası (TR şablon, kategori bazlı; Resend/mock).
  Teklifler `upsell_offers`'a source:"autopilot" ile yazılır (dedupe: booking_id bazlı).
- Endpoint'ler: POST /api/ai-predictions/upsell/autopilot/run, GET .../autopilot/stats/{pid}.
- `JOB_HANDLERS["upsell_autopilot"]` + 5 tesiste scheduler_config AKTİF (her gün 09:00).
- Auto-Fix artık 3 aksiyonu kapsıyor: rebook + comeback + upsell (toast güncellendi).
- Radar upsell sayımı autopilot ile hizalandı (sadece skor>=60 sayılıyor).
- E2E DOĞRULANDI: test rezervasyonu (honeymoon/standard/direct, skor 68) → radar 1 fırsat →
  autopilot 1 teklif (room_upgrade, mock e-posta) → rerun dedupe 0 → stats doğru. Test verisi temizlendi.
- 4 otomasyon döngüsünün tamamı artık tam otonom: rebook, sepet kurtarma, OTA→direkt, upsell.

## Son Durum (Iter 397, 2026-07-09) — Misafir Teklif Kabul Sayfası TAMAMLANDI
- Autopilot teklifleri artık fiyatlı (kategori bazlı: upgrade £40/gece, breakfast £15/gece, spa £20/gece,
  late_checkout £25, transfer £45) + `accept_token` + e-postada "Tek Tıkla Kabul Et" butonu (/offer/{token}).
- Public endpoint'ler (auth yok): GET /api/public/upsell-offer/{token},
  POST .../accept (idempotent; folio_items'a charge + upsell_log'a gerçek gelir), POST .../decline.
- Frontend: `UpsellOfferPage.js` (yeni public sayfa, /offer/{token} rotası App.js'e eklendi) —
  teklif kartı, Kabul Et / Hayır butonları, kabul/red durum ekranları.
- E2E DOĞRULANDI: autopilot teklif üretti (£80 room_upgrade) → public GET → accept → folio charge +
  upsell_log kaydı → ROI panosu upsell £80 GERÇEK gelir gösterdi → tekrar accept idempotent →
  UI screenshot: sayfa render + kabul akışı çalıştı. Test verisi temizlendi.

## Son Durum (Iter 398, 2026-07-09) — Teklif Sayfası Dönüşüm Artırıcıları TAMAMLANDI
- Erken kabul indirimi: teklif oluşturulduktan sonra 48 saat içinde kabulde %10 indirim
  (_early_bird helper, created_at bazlı — migration gerekmez). Accept endpoint'i indirimli tutarı
  folio + upsell_log'a yazar, folyo açıklamasına "erken kabul -%10" ekler, charged_amount saklanır.
- Sosyal kanıt: public GET aynı tesis+kategori için son 30 günde kabul edilen teklif sayısını döner.
- E-posta şablonu: buton indirimli fiyatı gösterir + "48 saat içinde %10 indirim" notu.
- UpsellOfferPage: üstü çizili orijinal fiyat + indirimli fiyat + "-%10 erken kabul" rozeti +
  son geçerlilik tarihi (offer-deadline) + "Son 30 günde X misafir kabul etti" (offer-social-proof).
- E2E DOĞRULANDI: £80 → £72 accept, folio £72 + doğru açıklama, social_count=3 (seed),
  UI screenshot tüm elementler render. Test verisi temizlendi.

## Son Durum (Iter 399, 2026-07-09) — ROI Haftalık Trend + Kabul Hunisi TAMAMLANDI
- `GET /api/automation/roi/{pid}/trend?weeks=8`: haftalık kova bazında kupon geliri
  (direct_conversion_offers.redeemed_at) + upsell geliri (upsell_log, property için bookings join).
- `GET /api/automation/funnel/{pid}?days=30`: Kupon hunisi (gönderilen→tıklanan→kullanılan, oranlarla)
  + Upsell hunisi (gönderilen→görüntülenen→kabul, viewed_at artık public GET'te bir kez loglanıyor).
- AutomationRoiPanel: recharts stacked BarChart (kupon yeşil / upsell amber) + 2 FunnelCard bileşeni.
- E2E DOĞRULANDI: curl trend (£1,400 son hafta) + funnel (655 kupon, %0.6 redeem) gerçek veri;
  UI screenshot: roi-trend-chart, roi-funnel, funnel-coupon, funnel-upsell hepsi render.

## Son Durum (Iter 400, 2026-07-09) — Akıllı Hatırlatma (Email Nudge) TAMAMLANDI
- `routes/marketing/nudge.py`: Açılmamış upsell tekliflerine 24s sonra (erken kabul indirimi
  dolmadan, kırmızı "son fırsat" şablonu) ve tıklanmamış rebook kuponlarına 72s sonra
  farklı konu satırıyla MAX 1 hatırlatma (nudged_at dedupe).
- Endpoint'ler: POST /api/automation/nudge/run, GET /api/automation/nudge/stats/{pid}
  (nudge sonrası geri kazanım: viewed/accepted/clicked > nudged_at → recovery_rate).
- `JOB_HANDLERS["email_nudge"]` + 5 tesiste scheduler AKTİF (günlük 10:00).
- AutomationRoiPanel: Nudge kartı (istatistikler + "Hatırlatmaları Gönder" butonu, nudge-run-btn).
- E2E DOĞRULANDI: 30s eski teklif + 96s eski kupon seed → nudge 1+1 gönderildi (mock) →
  rerun dedupe 0 → nudge sonrası görüntüleme → recovery %100 stats doğru → UI kart render.
  Test verisi temizlendi.

## Son Durum (Iter 401, 2026-07-09) — Günlük Nabız (Daily Pulse) TAMAMLANDI
- `routes/marketing/daily_pulse.py`: GM özet e-postası — bugünkü varış/çıkış/konaklayan/doluluk,
  dünkü yeni rezervasyon geliri, dünkü otomasyon kazancı (kupon+upsell), riskler (açık logbook,
  yanıtlanmamış yorum). TR HTML tablo şablonu. Alıcılar: admin/manager (test hesapları hariç).
- Günde 1 gönderim dedupe (`daily_pulse_log`), `force:true` ile manuel tekrar mümkün.
- Endpoint'ler: GET /api/automation/daily-pulse/preview/{pid}, POST /api/automation/daily-pulse/send.
- `JOB_HANDLERS["daily_pulse"]` + 5 tesiste scheduler AKTİF (08:00) — scheduler config sonrası
  otomatik ilk gönderimi kendisi yaptı (dedupe bunu doğruladı).
- ROI paneline "Günlük Nabız" kartı: 6 metrik önizleme + risk satırı + "Şimdi Gönder" (pulse-send-btn).
- E2E DOĞRULANDI: preview gerçek veri (%66.7 doluluk, £91,188 dün), scheduler otomatik gönderdi,
  force resend sent_to=1 (mock log doğrulandı), UI kart render.

## Son Durum (Iter 402, 2026-07-10) — Otomasyon Sağlık İzleyici (Watchdog) TAMAMLANDI
- `compute_automation_health(db, pid)` (automation_roi.py): scheduler_config (enabled) +
  scheduler_history üzerinden her job/tesis için durum: healthy / stale (>26s çalışmamış) /
  failing (son çalışma hatalı; error alanı veya result.ok=False) / pending (hiç çalışmamış).
  Ardışık hata sayısı (consecutive_failures) + son hata mesajı da dönülür.
- `GET /api/automation/health/{pid}` endpoint'i eklendi.
- Günlük Nabız risklerine `failing_automations` (job TR etiketleri) eklendi — GM e-postasında
  "Otomasyon HATALI: X" maddesi çıkar.
- ROI paneline "Otomasyon sağlığı" kartı: özet sayaçlar + job bazlı renkli durum chip'leri
  (tesisler arası en kötü durum gösterilir, tooltip'te son çalışma/hata).
- E2E DOĞRULANDI: 27 job-tesis sağlıklı; sahte hata kaydıyla failing=1 + pulse risks
  ['Rebook Taraması'] doğru tespit; seed temizlendi; UI kart + chip'ler render.
- NOT: İlk JSX düzenlemesi paralel edit çakışmasıyla dosyaya yazılmamıştı — insert_text ile eklendi.

## Son Durum (Iter 403, 2026-07-10) — Gelir Sızıntısı Denetçisi TAMAMLANDI
- `routes/revenue_ext/leakage.py`: GET /api/revenue/leakage/{pid}?days= — 4 sızıntı taraması:
  1) Ödenmemiş folyolar (checked_out; folio charges - payments > 0.5, aggregate pipeline)
  2) Folyoya işlenmemiş kabul edilmiş upsell'ler (upsell_offers accepted vs folio category upsell)
  3) Tahsil edilmemiş no-show'lar (status no_show, folio payment yok, total_price > 0)
  4) Sıfır fiyatlı aktif rezervasyonlar (veri hatası)
  Her satır: count, leaked (£), ilk 10 kayıt detayı; toplam sızıntı ve kayıt sayısı.
- Frontend: `LeakagePanel.js` (lazy) — 30/90/180 gün filtre, koyu özet bandı, genişleyebilir
  kategori kartları (kayıt detayları: ref, misafir, tutar). Menü: Revenue & rates → Tools
  → "Gelir sızıntısı denetçisi" (leakage-audit-btn).
- E2E DOĞRULANDI: 90 günde £15,531 gerçek sızıntı bulundu (54 no-show tahsil edilmemiş,
  2 açık folyo £498, 37 sıfır fiyatlı rezervasyon); UI 30 gün £1,175 + detay açılımı çalışıyor.

## Son Durum (Iter 404, 2026-07-10) — No-Show Toplu Tahsilat TAMAMLANDI
- `POST /api/revenue/leakage/{pid}/charge-noshows` body {policy: first_night|full, days}:
  tahsil edilmemiş no-show'lara folio charge (category: no_show) yazar, booking'e
  no_show_charged/no_show_fee/no_show_collected işaretler; kayıtlı vault kartı + STRIPE_API_KEY
  varsa off-session PaymentIntent dener (başarılıysa folio payment kaydı da düşer).
- Sızıntı taraması no_show_charged=True kayıtları artık hariç tutuyor (dedupe).
- LeakagePanel: no-show kartına aksiyon barı — İlk gece / Tam tutar politika seçici +
  "N No-Show'u Folyoya İşle & Tahsil Et" butonu (noshow-charge-btn), sonuç toast + otomatik yenile.
- E2E DOĞRULANDI: 30 günde 2 no-show → charge (first_night, £235 folyoya işlendi, kart yok) →
  tarama 0'a düştü → rerun dedupe posted=0 → folio kayıtları doğru → UI aksiyon barı 90 günde
  52 kayıtla render.
- NOT: Paralel search_replace aynı dosyada yine kayboldu (import + endpoint edit'leri) —
  sırayla tekrar uygulandı. AYNI DOSYAYA PARALEL EDİT YAPMA.

## Son Durum (Iter 405, 2026-07-11) — Otonom Sızıntı Taraması TAMAMLANDI
- leakage.py refactor: `_scan_core` / `_charge_core(actor)` core fonksiyonlara ayrıldı (endpoint'ler ince).
- `_sweep_core`: tara → no-show'ları otomatik işle (first_night, actor: leakage-sweep) → tekrar tara →
  `leakage_sweep_log`'a kaydet (found/closed/remaining). `router.run_leakage_sweep_internal` +
  `JOB_HANDLERS["leakage_sweep"]` + 5 tesiste HAFTALIK scheduler (Pazartesi 07:00, cron_dow=0).
- `GET /api/revenue/leakage/{pid}/sweep-log` endpoint'i.
- Günlük Nabız: `leakage_closed_7d` (son 7 gün kapatılan sızıntı) — hem JSON hem e-posta şablonu
  hem UI pulse kartında (koşullu stat) gösteriliyor.
- Watchdog: JOB_LABELS_TR'ye "Sızıntı Taraması" eklendi — sağlık panosunda chip görünür.
- E2E DOĞRULANDI: test no-show £200 → sweep found 200/closed 100 (ilk gece)/remaining 0,
  folio created_by=leakage-sweep; pulse leakage_closed_7d=100; sweep-log 1 kayıt;
  watchdog chip 'pending' (haftalık, henüz zamanı gelmedi); UI'da £100 stat görünür. Test verisi temizlendi.
- BUG FIX: daily_pulse'ta 'now' tanımsızdı (NameError) → datetime.now() ile düzeltildi.

## Son Durum (Iter 406, 2026-07-11) — Misafir Risk Radarı TAMAMLANDI
- `routes/guests/risk_score.py`: misafir e-postasından geçmiş analizi — no-show (×30, cap 60),
  iptal (×10, cap 30), chargeback (×30, cap 60), tahsil edilememiş no-show ücreti (×10, cap 20),
  sorunsuz konaklama (-5, cap -20). Skor 0-100; seviye low/medium(30+)/high(60+); önerilen aksiyon
  (standart / depozito iste / ön ödeme zorunlu).
- Endpoint'ler: GET /api/guests/risk/arrivals/{pid}?days_ahead= (yaklaşan varışlar risk sıralı,
  summary + value_at_risk), GET /api/guests/risk/{guest_email} (tekil, receptionist dahil).
- Frontend: `GuestRiskPanel.js` (lazy) — 7/14/30 gün filtre, koyu özet bandı (yüksek/orta sayısı +
  risk altındaki değer), risk kartları (rozet, skor barı, nedenler, aksiyon), "düşük riskleri göster" toggle.
  Menü: Guests → "Misafir risk radarı" (guest-risk-btn).
- E2E DOĞRULANDI: emily.williams 2 no-show → skor 40 medium "Depozito isteyin"; 30 günde 4 orta
  riskli varış £760 risk değeri; UI screenshot tüm elementler render.

## Son Durum (Iter 407, 2026-07-11) — Tek Tık Depozito Talebi (Stripe Checkout) TAMAMLANDI
- risk_score.py'ye eklendi (emergentintegrations StripeCheckout, playbook'a uygun):
  - POST /api/guests/risk/{booking_id}/request-deposit: ilk gece tutarı kadar GBP Checkout Session
    oluşturur (gerçek checkout.stripe.com URL), deposit_requests + payment_transactions (pending)
    kaydı, misafire ödeme linkli e-posta (mock), booking.deposit_requested=True (dedupe).
  - POST /api/guests/risk/{booking_id}/deposit-status: önce webhook-güncellemeli
    payment_transactions'a bakar, sonra best-effort get_checkout_status dener (proxy'de
    'No such session' verirse pending döner — ödeme onayı /api/webhook/stripe üzerinden gelir).
    Paid ise idempotent şekilde folio deposit payment + booking.deposit_paid=True.
- GuestRiskPanel: orta/yüksek risk satırlarında "Depozito İste" → "İstendi · Durumu kontrol et" →
  "Depozito alındı ✓" durum akışı (deposit-request-/deposit-check-/deposit-paid- testid'leri).
- E2E DOĞRULANDI: session oluştu (£104.98, gerçek Stripe test URL), dedupe already:true,
  status pending → webhook simülasyonu → paid + folio 1 kayıt (idempotent, 2. çağrıda çift kayıt yok),
  arrivals flag'leri döndü, UI toast + durum geçişi çalıştı. Simülasyon verisi temizlendi.
- NOT: emergentintegrations get_checkout_status bu ortamda 'No such checkout.session' veriyor —
  ödeme onayı webhook'a dayanıyor (payments.py'deki mevcut /api/webhook/stripe handler'ı
  payment_transactions'ı güncelliyor). Raw Stripe API sk_test_emergent ile ÇALIŞMAZ.

## Son Durum (Iter 408, 2026-07-11) — KAPSAMLI REGRESYON DENETİMİ GEÇTİ ✅
- Testing agent ile son 10 iterasyonun tamamı denetlendi: BACKEND 15/15 PASS,
  FRONTEND %100 (tüm testid'ler ve etkileşimler doğrulandı). Kritik/minör sorun YOK.
- Kapsam: ROI + fırsatlar + auto-fix (idempotent) + trend + funnel + health,
  upsell autopilot run/stats, nudge run/stats, daily-pulse preview/send (dedupe+force),
  leakage scan/sweep-log, guest risk arrivals/single/request-deposit (Stripe URL)/deposit-status.
  UI: AutomationRoiPanel 8 kart, LeakagePanel filtre+aksiyon barı, GuestRiskPanel butonları.
- 1 SKIP: public upsell-offer token akışı — DB'deki 2 eski teklif token özelliğinden önce
  oluşturulmuş (veri koşulu, kod hatası değil; akış iter 397-398'de gerçek e2e ile doğrulanmıştı).
- Rapor: /app/test_reports/iteration_408.json + /app/backend/tests/test_iteration408_automation_regression.py

## Son Durum (Iter 409, 2026-07-11) — İptal Kurtarma Autopilot (Cancel-Save) TAMAMLANDI
- `routes/ai/cancel_save_autopilot.py`: 3-45 gün içindeki confirmed/pending_payment rezervasyonları
  _score_cancel_risk ile tarar; skor ≥65 olanlara %10 tutundurma kuponu (STAY-XXXXXX) + TR e-posta
  (ücretsiz tarih değişikliği vurgusu). save_offers'a source:autopilot yazar; booking'e
  save_offer_sent_at (dedupe). Mevcut manuel save-offer altyapısıyla uyumlu.
- Endpoint'ler: POST /api/ai-predictions/cancel-save/run, GET /api/ai-predictions/cancel-save/stats/{pid}
  (offers_sent / saved+saved_revenue / pending / cancelled_anyway / save_rate — booking durumuna göre).
- `JOB_HANDLERS["cancel_save"]` + 5 tesiste scheduler AKTİF (günlük 11:00) + watchdog etiketi "İptal Kurtarma".
- ROI paneline teal "İptal Kurtarma" kartı: istatistikler + "Şimdi Tara" (cancel-save-run-btn).
- E2E DOĞRULANDI: 138 tarandı → 4 kupon gönderildi (mock e-posta), rerun dedupe 0, stats 4/4 pending,
  watchdog chip görünür, UI kart + istatistikler render.

## Son Durum (Iter 410, 2026-07-11) — Aylık Otomasyon Karnesi TAMAMLANDI
- `routes/marketing/report_card.py`: 6 bölümlü konsolide rapor — kupon (gönderilen/kullanılan/gelir),
  upsell autopilot, iptal kurtarma (kurtarılan gelir), no-show tahsilatı, sızıntı kapatma, nudge sayısı;
  grand_total ("platform size £X kazandırdı"). Koyu temalı TR e-posta şablonu.
- Endpoint'ler: GET /api/automation/report-card/preview/{pid}?days=, POST /api/automation/report-card/send
  (ayın 1'i değilse skip: not_first_of_month; ay bazlı dedupe report_card_log; force:true ile manuel).
- `JOB_HANDLERS["monthly_report_card"]` + 5 tesiste scheduler (günlük 09:30, kendi kendine ayın 1'ini bekler)
  + watchdog etiketi "Aylık Karne".
- ROI paneline koyu "Otomasyon Karnesi" kartı: grand total + 5 kalem döküm + "Karneyi Şimdi Gönder"
  (report-send-btn).
- E2E DOĞRULANDI: preview £1,635 (kupon £1,400 + no-show £235 + sızıntı £100), gün koruması skip,
  force send sent_to=1 (mock e-posta log), UI kart + döküm render.

## Son Durum (Iter 411, 2026-07-11) — Yorum Yanıt Autopilot TAMAMLANDI
- `routes/guests/review_autopilot.py`: bekleyen (response_status: pending) yorumları günlük tarar
  (max 10/çalıştırma, LLM maliyet kontrolü): 4-5★ → AI yanıtı DOĞRUDAN YAYINLAR
  (response_method: ai_autopilot, yorum dilinde, kişiselleştirilmiş, gpt-5.2 Emergent LLM key);
  ≤3★ → taslak üretip MEVCUT onay kuyruğuna düşürür (response_status: pending_approval —
  ReviewToolsPanels'daki Approval Queue UI'ı ve /api/reviews/{id}/approve endpoint'i zaten vardı).
- Endpoint'ler: POST /api/reviews/autopilot/run, GET /api/reviews/autopilot/stats.
- `JOB_HANDLERS["review_autopilot"]` + 5 tesiste scheduler (08:30) + watchdog "Yorum Yanıt Autopilot".
- Günlük Nabız risks güncellendi: unanswered_reviews artık sadece 'pending' sayar +
  yeni reviews_awaiting_approval alanı (e-posta + UI'da "X AI yanıt taslağı onay bekliyor").
- E2E DOĞRULANDI: scheduler kendisi çalıştırdı — 7 bekleyen yorum → 4 olumlu otomatik yayınlandı
  (gerçek kişiselleştirilmiş AI yanıtı doğrulandı), 3 olumsuz onay kuyruğunda; stats 4/3/0;
  pulse risks doğru; watchdog healthy; UI screenshot tüm elementler render.

## Son Durum (Iter 412, 2026-07-11) — E-postadan Tek Tık "Onayla & Yayınla" TAMAMLANDI
- review_autopilot.py: olumsuz yorum taslakları artık approve_token ile üretiliyor;
  mevcut 3 taslağa token backfill yapıldı.
- YENİ public endpoint: GET /api/public/review-approve/{token} — taslağı yayınlar
  (response_method: ai_autopilot_email_approved), şık TR HTML onay sayfası döner;
  idempotent ("Zaten yayınlandı"), geçersiz token güvenli hata sayfası.
- Günlük Nabız e-postasına "Onay bekleyen AI yanıt taslakları" bölümü eklendi: her taslak için
  misafir+yıldız, yorum özeti, AI taslak özeti ve turuncu "Onayla & Yayınla ⚡" butonu
  (_drafts_html). Preview JSON'a pending_drafts alanı eklendi (max 3).
- E2E DOĞRULANDI: preview 3 taslak+token; force pulse gönderimi; public link ile yayın →
  DB responded ✓; ikinci ziyaret idempotent; geçersiz token hata sayfası; kalan taslak 3→2.

## Son Durum (Iter 413, 2026-07-12) — Depozito Autopilot TAMAMLANDI
- risk_score.py: request-deposit endpoint'i `_request_deposit_core(booking_id, actor)` olarak
  ayrıldı; YENİ `_deposit_autopilot_core`: 14 gün içindeki varışlardan risk seviyesi HIGH (skor≥60)
  olanlara otomatik depozito talebi (Stripe Checkout + e-posta), medium'lar manuel bırakılır.
- POST /api/guests/risk/deposit-autopilot/run + `JOB_HANDLERS["deposit_autopilot"]` +
  5 tesiste scheduler (günlük 12:00) + watchdog "Depozito Autopilot" (healthy).
- GuestRiskPanel başlığına otomasyonu açıklayan alt satır eklendi.
- E2E DOĞRULANDI: yüksek riskli test varışı (2 no-show + 1 chargeback) → autopilot 1 talep
  (£120, created_by: deposit-autopilot) → rerun dedupe 0 → manuel endpoint regresyonu OK
  (Stripe URL üretiyor) → watchdog healthy. Test verisi temizlendi.
- OPERASYONEL NOT: risk_score.py hot-reload sırasında backend uzun süre kapalı kaldı
  (ağır startup görevleri) → `sudo supervisorctl restart backend` ile çözüldü.

## Son Durum (Iter 414, 2026-07-12) — Otomasyon Ayarları Paneli TAMAMLANDI
- YENİ backend: routes/platform_ext/automation_settings.py — JOB_REGISTRY (11 motor: upsell,
  nudge, daily_pulse, leakage, cancel_save, deposit, review, report_card, rebook, abandoned,
  ai_pricing[varsayılan kapalı]); GET /api/automation/settings (eksik config'leri auto-seed,
  son çalışma + params merge) ve PUT /api/automation/settings/{job} (enabled/cron/params,
  min-max validasyonlu). get_params() helper ile motorlar canlı parametre okuyor.
- Dinamik parametre bağlanan motorlar: cancel_save (risk_threshold, discount_pct),
  email_nudge (upsell/coupon nudge saatleri), review_autopilot (max_per_run),
  deposit_autopilot (days_ahead), upsell_autopilot (min_score, days_ahead).
- YENİ frontend: components/dashboard/AutomationSettingsPanel.js — kategori gruplu kart
  görünümü, aç/kapat anahtarı, genişletilebilir ayarlar (saat/dakika/gün + eşikler),
  son çalışma sonucu/hatası, "Şimdi çalıştır" (scheduler/trigger/all/{job}).
  Menü: Revenue & rates > Tools > "Otomasyon ayarları" (automation-settings-btn).
- E2E DOĞRULANDI: GET 11 motor listeledi; PUT param (threshold 70) → trigger sonucu
  threshold:70 döndü (canlı etki kanıtı); toggle on/off; 400 range validasyonu;
  404 bilinmeyen job; UI screenshot — panel, genişletilmiş kart, 10/11 aktif rozeti OK.

## Son Durum (Iter 415, 2026-07-12) — Otomasyon Etki Simülatörü TAMAMLANDI
- YENİ backend: routes/platform_ext/automation_simulator.py — POST /api/automation/simulate/{job}:
  parametrelerle dry-run "kaç misafir hedeflenirdi?" analizi, hiçbir şey göndermeden.
  Desteklenen: cancel_save (risk eşiği + kupon maliyet tahmini), upsell_autopilot (potansiyel
  gelir), deposit_autopilot (güvence tutarı), email_nudge (bekleyen hatırlatmalar),
  review_autopilot (işlenecek yorum). Skor histogramı (5 bucket) döner.
- risk_score.py: router.risk_for_internal expose edildi (simülatör için).
- Frontend: AutomationSettingsPanel kartlarına "Etkiyi simüle et" butonu + cyan sonuç kutusu
  (hedef/taranan, £ tahmin, detay metni, mini histogram barları). Kaydetmeden önce denenebilir.
- E2E DOĞRULANDI: 5 motor simülasyonu; eşik hassasiyeti kanıtı (40→70 hedef, 65→4, 80→1);
  404 desteklenmeyen job; UI'da eşik 40 girilip simüle edildi → 70/137 + histogram render OK.

## Son Durum (Iter 416, 2026-07-12) — Misafir Segment Motoru TAMAMLANDI
- YENİ backend: routes/guests/segments.py — 7 segment (vip, riskli, sadik, aile, is, yeni,
  standart); _classify: vip bayrağı/£3000+ harcama → VIP, risk high → Riskli, 3+ konaklama →
  Sadık, ort. 3+ kişi → Aile, hafta içi kısa konaklama ≥%60 → İş, ≤1 konaklama → Yeni.
  Endpoints: GET summary (aggregate gelir/sayı), GET list?segment=, GET/PUT strategy/{segment},
  POST refresh. guest_profiles.segment alanına yazar + guest_segments_summary.
- segment_allows(db, email, motor): motorlar göndermeden önce kontrol eder. Entegre motorlar:
  cancel_save, upsell_autopilot, deposit_autopilot, email_nudge (nudge iki döngüde de).
  Varsayılan strateji: VIP'e kupon+depozito YOK, Riskli'ye upsell+nudge YOK.
  ÖNEMLİ FIX: kısmi strateji kaydı defaults'u ezmesin diye merge mantığı (DEFAULT ∪ saved).
- Scheduler: JOB_HANDLERS["segment_refresh"] + JOB_REGISTRY (05:00, guest kategorisi) →
  Otomasyon Ayarları panelinde 12. motor olarak görünür.
- YENİ frontend: GuestSegmentsPanel.js — 7 segment kartı (sayı+gelir), Segment×Autopilot
  strateji matrisi (tık ile aç/kapat), segment misafir listesi, "Segmentleri yenile".
  Menü: Guests > "Segment motoru" (guest-segments-btn). menuSections'a UsersThree import fix.
- E2E DOĞRULANDI: 182 misafir sınıflandı (18 vip, 29 sadık, 29 iş, 101 yeni, 5 standart);
  segment_allows VIP: cancel_save=False, deposit=False, upsell=True ✓; strateji PUT+merge ✓;
  scheduler trigger ✓; cancel_save regresyonu ✓; UI screenshot (kartlar, matris, liste, toast) ✓.

## Son Durum (Iter 417, 2026-07-13) — Segment Bazlı Kişiselleştirilmiş Upsell TAMAMLANDI
- segments.py: SEGMENT_OFFER_PROFILES (vip/sadik/aile/is/yeni — selamlama, giriş, kapanış
  metinleri + category_boost) ve apply_segment_boost(scores, segment) helper eklendi.
  Boost örnekleri: VIP → room_upgrade+15/spa+10, İş → late_checkout+15/breakfast+10,
  Aile → breakfast+15/transport+10.
- upsell_autopilot.py: _email_html artık seg_profile alıyor (segment'e özel selamlama/giriş/
  kapanış); _autopilot_core segment lookup (guest_id yoksa email fallback) + boost'lu skor
  ile kategori seçiyor; offer doc'a segment alanı, sonuca by_segment sayacı eklendi.
- automation_simulator.py: _sim_upsell aynı boost mantığıyla tutarlı hale getirildi.
- E2E DOĞRULANDI: aynı ham skorlarla VIP→oda yükseltme, İş→geç çıkış, Aile→kahvaltı seçimi;
  VIP test misafiri → autopilot 1 teklif (skor 68, segment:vip, by_segment raporu, mock email);
  HTML'de "Değerli VIP misafirimiz"+"önceliğiniz garanti" / aile metinleri assert edildi;
  test verisi temizlendi; simulator + nudge regresyonu OK.

## Son Durum (Iter 418, 2026-07-13) — Segment Performans Raporu TAMAMLANDI
- segments.py: GET /guests/segments/performance?days=90 — upsell_offers'ı segmente göre
  toplar (gönderilen/görüntülenen/kabul/kabul oranı/gelir); segment alanı olmayan eski
  tekliflere otomatik backfill (booking→guest_email→profil segmenti, DB'ye kalıcı yazılır).
- GuestSegmentsPanel: strateji matrisi altına "Segment performansı" tablosu — kabul oranı
  progress bar, görüntülenme yüzdesi, kabul geliri; veri yoksa bilgilendirici boş durum.
- E2E DOĞRULANDI: 9 çeşitli test teklifi ile matematik (vip 2/3=%66.7 £81, yeni %16.7)
  + 2 gerçek teklifin backfill'i kanıtlandı; UI screenshot (tablo + barlar) OK; test verisi silindi.

## Son Durum (Iter 419, 2026-07-13) — Daily Pulse'a Segment Performans Özeti TAMAMLANDI
- daily_pulse.py: _pulse_data artık son 30 günün upsell tekliflerini segmente göre toplayıp
  segment_performance alanı döndürüyor (en çok gönderilen 5 segment: sent/accepted/oran/gelir).
- _segment_html: e-postaya "Segment performansı — upsell (30 gün)" tablosu — kabul oranı
  renk kodlu (≥%30 yeşil, ≥%10 turuncu, altı kırmızı). Veri yoksa bölüm tamamen gizlenir.
- E2E DOĞRULANDI: test teklifleriyle preview + force send → log'da segment_performance
  (VIP %50 £90); boş veri durumunda bölüm gizli; test verisi temizlendi; pulse regresyonu OK.

## Son Durum (Iter 420, 2026-07-13) — Kanal Sağlık Merkezi + OTA Senkron Watchdog TAMAMLANDI
- YENİ backend: routes/distribution/channel_health.py — kanal başına 24s senkron sağlığı
  (başarı oranı, bekleyen, dead-letter, son başarı, gecikme saati; status: healthy/warning/
  critical/no_data). Watchdog: dead-letter görevleri otomatik requeue (görev başına maks 2,
  çalışma başına max_requeue), stale/dead-letter için ota_sync_alerts (open/resolved yaşam
  döngüsü). Endpoints: GET /channel-health/{pid}, POST /channel-health/heal.
- Motor: JOB_HANDLERS["ota_sync_watchdog"] + registry (06:30, YENİ "distribution" kategorisi,
  params: stale_hours 24, max_requeue 10) → Otomasyon Ayarları'nda 13. motor.
- Daily Pulse: risks.ota_sync_alerts (açık uyarı sayısı) + e-posta risk satırı.
- YENİ frontend: ChannelHealthPanel.js — kanal kartları grid (durum rozetleri), açık uyarı
  banner'ı, dead-letter tablosu (tek tık yeniden dene), "Şimdi iyileştir". Menü: System >
  "Kanal sağlık merkezi" (channel-health-btn). AutomationSettingsPanel'e distribution kategorisi.
- E2E DOĞRULANDI: booking_com stale (2024s) → critical + otomatik alert; 2 test dead-letter →
  watchdog 2 requeue → run-tick işledi → expedia healthy %100; alert yaşam döngüsü; Daily Pulse
  preview ota_sync_alerts:1; 13 motor listesi; scheduler trigger; UI screenshot OK. Test verisi silindi.

## Son Durum (Iter 421, 2026-07-13) — Gerçek Zamanlı Kritik Kanal Uyarıları TAMAMLANDI
- channel_health.py: _notify_alert(msg) — yeni watchdog uyarısı açıldığında (upsert) anında:
  (1) uygulama içi bildirim (db.notifications, category: ota_sync, priority: high, zil sayacına
  düşer), (2) isteğe bağlı Slack uyumlu webhook POST {"text": "🚨 ..."} (httpx, 8s timeout,
  teslim durumu last_delivery_status'ta izlenir, hata durumunda graceful log).
- Endpoints: GET /channel-health/webhook-config/get, PUT /channel-health/webhook-config,
  POST /channel-health/webhook-test (in-app + webhook test uyarısı).
- ChannelHealthPanel: "Anlık uyarı ayarları" bölümü — webhook URL input, Kaydet, Test uyarısı
  gönder, son teslim durumu göstergesi.
- E2E DOĞRULANDI: lokal HTTP dinleyici ile gerçek webhook teslimi (Slack formatı, 200);
  watchdog yeni alert → bildirim + webhook zinciri; geçersiz URL graceful error izleme;
  boş config'de sadece in-app; test verisi/config temizlendi; UI screenshot OK.

## Son Durum (Iter 422, 2026-07-14) — Anahtar Göstergeler (eviivo Key Figures paritesi) TAMAMLANDI
- Kullanıcı eviivo "Key Figures" ekran görüntüsü paylaştı; birebir karşılık geliştirildi.
- YENİ backend: routes/revenue_ext/key_figures.py — GET /key-figures/{pid}?start&end&basis
  (staying: tarih aralığına kırpılmış gece/gelir payı; booked: created_at bazlı).
  12 metrik: satılan/satılmayan gece, doluluk, ADR, rezervasyon penceresi, ort. konaklama,
  toplam online %, kendi site %, misafir, toplam gelir, iptal/no-show %, komisyon maliyeti
  (ota_commission_rates + DEFAULT_RATES). Döküm: oda geliri, oda dışı (folio kategorileri),
  no-show ücretleri, turizm vergisi, komisyonlar, tahsil edilen depozitolar.
- YENİ frontend: KeyFiguresPanel.js — eviivo tarzı amber ikonlu 12 kutu + sağda gelir dökümü
  kartı; tarih aralığı seçici, hızlı aralıklar (Bu ay/Son 30 gün/Son 12 ay/Gelecek 12 ay),
  konaklama/rezervasyon bazı toggle. Menü: Overview > "Anahtar göstergeler" (key-figures-btn).
- E2E DOĞRULANDI: 12 aylık staying (2893 gece, %13.4, ADR £137, £397K, komisyon £20.2K);
  booked bazı; 400 tarih validasyonu; UI screenshot (tüm kutular + döküm) OK.
- NOT: Uluslararası misafir % metriği veri modelinde uyruk alanı olmadığı için yerine
  "İptal/no-show oranı" kutusu kondu. Kart ücretleri takip edilmiyor (0 varsayım, gösterilmiyor).
- ERTELENEN: Otomasyon sekmeleri konsolidasyon refactoring'i (kullanıcı eviivo paritesine yönlendirdi).

## Son Durum (Iter 423, 2026-07-14) — Anahtar Göstergeler Dönem Karşılaştırması TAMAMLANDI
- key_figures.py yeniden yapılandırıldı: _compute(pq, start, end, basis) tekrar kullanılabilir;
  compare=previous (aynı uzunlukta önceki dönem) | last_year (geçen yıl aynı tarih, gün 28'e
  kırpılır) parametresi → comparison.{start, end, tiles, deltas{prev, pct}}.
- KeyFiguresPanel: karşılaştırma seçici (yok/önceki dönem/geçen yıl), her kutuda ▲▼ renk
  kodlu değişim yüzdesi (invert mantığı: satılmayan gece/iptal/komisyon artışı kırmızı),
  karşılaştırma dönemi bilgi satırı.
- E2E DOĞRULANDI: previous (-45.7% gece, -17.3% gelir), last_year, compare=none regresyonu;
  UI screenshot — tüm deltalar doğru renk/yönde render.

## Son Durum (Iter 424, 2026-07-14) — Haftalık Yönetim Raporu (14. motor) + CSV Export TAMAMLANDI
- YENİ backend: routes/marketing/weekly_report.py — son 7 gün vs önceki 7 gün anahtar
  göstergeleri (key_figures compute_internal yeniden kullanılır), renk kodlu ▲▼ HTML e-posta
  (10 gösterge + gelir dökümü + net), admin/manager alıcıları, ISO hafta bazlı dedupe
  (weekly_report_log, force ile override). Endpoints: GET /reports/weekly-management/preview/{pid},
  POST /reports/weekly-management/send.
- Motor: JOB_HANDLERS["weekly_report"] + registry (Pazartesi 07:00, default_dow desteği
  registry seed'e eklendi) → 14. motor.
- key_figures.py: router.compute_internal expose + GET /key-figures/{pid}/export (CSV, BOM'lu,
  noktalı virgül ayraçlı — Excel uyumlu). KeyFiguresPanel'e "CSV" indirme butonu (blob download).
- E2E DOĞRULANDI: preview deltaları, send (1 alıcı, 2026-W29), dedupe skip, scheduler trigger,
  14 motor + dow=0, CSV çıktı, UI screenshot OK.

## Son Durum (Iter 425, 2026-07-14) — Otomasyon Merkezi Konsolidasyonu (Refactoring) TAMAMLANDI
- YENİ: components/dashboard/AutomationHubPanel.js — 4 sekmeli tek çatı: Ayarlar & Motorlar
  (AutomationSettingsPanel), ROI (AutomationRoiPanel), Analitik (AutomationAnalyticsPanel),
  Kurallar (AutomationRulesPanel). initialView prop'u ile eski view id'lerinden doğru sekme açılır.
- Menü sadeleştirme: "Otomasyon ayarları"+"Otomasyon analitiği"+"Otomasyon ROI" (Tools) ve
  "Otomasyon kuralları" (Quality Assurance) girişleri kaldırıldı → tek "Otomasyon merkezi"
  (automation-hub-btn, Revenue & rates > Tools).
- App.js: 4 ayrı render bloğu 2 hub bloğuna indirildi; eski activeView id'leri
  (automation-settings/analytics/roi/rules) geriye dönük uyumlu şekilde hub'a yönlenir
  (key={activeView} ile remount). Kullanılmayan importlar temizlendi.
- E2E DOĞRULANDI: eski menü girişleri kalktı (0 adet), hub 4 sekme de içerik render ediyor
  (Ayarlar 14 motor, ROI, Analitik 37 kural, Kurallar paneli), konsol hatasız.

## Son Durum (Iter 426, 2026-07-14) — KAPSAMLI REGRESYON TESTİ ✅ (%100 BAŞARI)
- Testing agent tam tur regresyon: BACKEND 30/30 PASS — 14 motorlu Otomasyon Ayarları
  (toggle/param/validasyon), Etki Simülatörü (5 job + eşik değişimi etkisi + 404), Segmentler
  (refresh/summary/list/strategy/performance), Kanal Sağlık (8 kanal/heal/webhook roundtrip),
  Anahtar Göstergeler (compare/booked/400/CSV), Haftalık Rapor (preview/dedupe/force),
  Scheduler trigger'ları. FRONTEND %100 — Otomasyon Merkezi tek giriş + eski 4 girişin
  kaldırıldığı teyitli, 4 sekme, motor kartı akışı, segment paneli, kanal sağlık paneli,
  anahtar göstergeler (23 kf-* elemanı, karşılaştırma, CSV).
- Rapor: /app/test_reports/iteration_409.json + kalıcı pytest suite:
  /app/backend/tests/test_iteration409_regression.py (state-restoring, tekrar çalıştırılabilir).
- Sıfır kritik/minör issue. Test verisi kalıntısı yok.

## Son Durum (Iter 427, 2026-07-21) — Kanal Push Geçmişi (P1) TAMAMLANDI
- YENİ backend: routes/distribution/push_history.py — GET /push-history/{pid}?channel&days&limit
  (zaman çizelgesi: kanal/tür/hedef tarih/değer/gecikme sn/durum + kanal bazlı istatistik:
  başarı/hata/ort-maks gecikme) ve GET /push-history/{pid}/freshness?days=14 (kanal × tarih
  tazelik matrisi: son push zamanı + yaş saati, sync_queue payload.date aggregate).
- ChannelHealthPanel'e sekme yapısı: "Sağlık & Uyarılar" + "Push Geçmişi" (yeni
  ChannelPushHistory.js bileşeni — renk kodlu tazelik matrisi ✓≤24s/sarı≤72s/kırmızı eski/
  gri hiç, istatistik kartları, kanal filtreli zaman çizelgesi).
- Veri gerçek akışla üretildi: /api/sync-queue/{pid}/enqueue ile 15 fiyat push'u (3 kanal ×
  5 tarih) → run-tick 15/15 başarılı işledi (kalıcı gerçek kayıtlar, fake seed değil).
- E2E DOĞRULANDI: timeline 15 kayıt, stats (5/5 başarı, ort 1.8sn), freshness matrisi
  booking_com 5 dolu hücre; UI screenshot — matris/istatistik/çizelge render OK.

## Son Durum (Iter 428, 2026-07-24) — Tek Tık "Şimdi Push'la" TAMAMLANDI
- push_history.py: POST /push-history/{pid}/push-now {channel, date} — fiyat çözümleme
  zinciri: son başarılı push → property_monthly_prices aylık ADR → son 90 gün booking ADR →
  £100 varsayılan (rate_source alanında raporlanır). Task enqueue + process_due_tasks ile
  anında işlenir; sonuç {ok, status, rate, rate_source, error} döner. Eksik alan 400.
  pid=all ise channel_connections'tan property çözülür.
- ChannelPushHistory: tazelik matrisinde eski (>24s) ve hiç push'lanmamış (↑) hücreler
  tıklanabilir buton oldu (push-cell-{ch}-{date} testid) → başarıda yeşil toast, mock OTA
  geçici hatasında (%10) mavi bilgi toast'ı "kuyruğa alındı, otomatik yeniden denenecek"
  (backoff retry sistemi devrede).
- E2E DOĞRULANDI: expedia push-now anında succeeded + freshness hücresi doldu; agoda mock
  503 → pending + backoff (doğru davranış); 400 validasyonu; UI'da hücre tıklama → toast →
  timeline pending kaydı → expedia ✓ hücresi görüldü.

## Son Durum (Iter 429, 2026-07-24) — Auto-Freshness (Watchdog Otomatik Push) TAMAMLANDI
- push_history.py: resolve_rate(db, pid, date) modül fonksiyonuna çıkarıldı (push-now da kullanır).
- channel_health.py watchdog 3. adım: kanal × tarih (freshness_days ufku) tarar; freshness_hours
  eşiğinden eski veya hiç push'lanmamış hücreler için resolve_rate ile fiyat çözüp sync_queue'ya
  otomatik push ekler (çalışma başına max_auto_push sınırı, pending/processing olanlar atlanır
  — idempotent), sonra process_due_tasks ile işler. Sonuçta freshness_pushed raporlanır.
- Registry ota_sync_watchdog yeni paramlar: freshness_hours (72), freshness_days (14),
  max_auto_push (30, 0=kapalı) — Otomasyon Ayarları'ndan yönetilir.
- DERS: search_replace sırasında channel_health.py'de dosya sonuna artık blok yapışması oldu
  (IndentationError) → sed ile 203+ temizlenip blok doğru yere kondu; AST + e2e ile onarım doğrulandı.
- E2E DOĞRULANDI: ardışık çalışmalar 30→30→30→19→0 (doygunlukta 0 = idempotens kanıtı);
  tazelik matrisi 97/112 taze hücreye ulaştı; kalan 15 backoff retry kuyruğunda (beklenen).

## Son Durum (Iter 430, 2026-07-24) — Rakip Fiyat Radarı (15. motor) TAMAMLANDI
- YENİ backend: routes/revenue_ext/comp_radar.py — compset rakiplerini deterministik MOCK
  scanner ile tarar (md5 seed → çalışmalar arası tutarlı; gerçek scraper kimlik bilgisi
  gelince swap edilir), comp_rate_snapshots'a saklar. Kendi fiyat (resolve_rate) vs rakip
  medyanı; threshold_pct dışında kalan tarihler için comp_radar_findings: underpriced
  (artış fırsatı + hedef fiyat) / overpriced (doluluk riski).
- Endpoints: GET /comp-radar/{pid} (findings + own-vs-median 14 gün serisi + özet),
  POST /comp-radar/scan. Motor: JOB_HANDLERS["comp_radar"] + registry (04:30, revenue,
  params: days_ahead 14, threshold_pct 10) → 15. motor.
- YENİ frontend: CompRadarPanel.js (recharts LineChart own vs medyan, 3 özet kart, bulgular
  tablosu Türkçe önerilerle, "Şimdi tara"). Menü: Revenue & rates > Tools > "Rakip fiyat
  radarı" (comp-radar-btn).
- FIX'ler: phosphor'da Radar ikonu yok → Crosshair; App.js render bloğu kaybolmuştu → yeniden eklendi.
- E2E DOĞRULANDI: scan 112 fiyat noktası + 4 bulgu (%10.7-12.2 pazar altı), scheduler trigger,
  15 motor listesi, UI (grafik + kartlar + 4 bulgu satırı) OK.
- NOT: Rakip fiyatları MOCK scanner (gerçek OTA scrape API'si yok).

## Son Durum (Iter 431, 2026-07-25) — Radar/Compset Mükerrerlik Giderme TAMAMLANDI
- KULLANICI GERİ BİLDİRİMİ: "Bu özellik zaten vardı, Revenue içinde — tekrar yapmışsın."
  Haklı: CompsetPanel (rakip CRUD + fiyat snapshot) zaten mevcuttu; yeni CompRadarPanel
  ayrı menü girişiyle mükerrerlik yaratıyordu.
- ÇÖZÜM (konsolidasyon): "Rakip fiyat radarı" menü girişi KALDIRILDI. CompsetPanel'e sekme
  yapısı eklendi: "Rakip Listesi" (mevcut CRUD, dokunulmadı) + "Fiyat Radarı" (CompRadarPanel
  lazy gömülü). comp-radar view id'si geriye dönük CompsetPanel(initialTab=radar)'a yönlenir.
  Backend comp_radar motoru (15.) ve endpoint'ler aynen duruyor — sadece UI birleşti.
- DERS: Yeni panel eklemeden önce mevcut menü/panel envanterinde işlevsel çakışma taraması yap.
- E2E DOĞRULANDI: mükerrer giriş 0, Compset > Fiyat Radarı sekmesi grafik + 4 bulgu ile çalışıyor.

## NOT: Iter 432+ kayıtları /app/memory/CHANGELOG.md dosyasına taşındı (700 satır limiti).

## Güncelleme (2026-08-14, iter 545)
- LOS Bazlı Fiyatlama, Grup Wash Projeksiyonu ve Modern Metrik Paketi (TRevPOR/RevPAG/GOPPAR) tamamlandı ve test edildi (iteration_537 %100).
- Sıradaki: Fonksiyon alanı booking motoru (RevPAM / Duetto OpenSpace paritesi), Expo mobil derleme (token bekleniyor), canlı kanal yöneticisi API'leri.

## Güncelleme (2026-08-15, iter 546)
- Fonksiyon Alanı Motoru (teklif→rezervasyon + RevPAM), LOS tek tık uygulama (booking widget fence), Wash Uyarı Robotu (14 gün cutoff bildirimi) ve TRevPOR/GOPPAR trend grafiği tamamlandı (iteration_538 %100).
- Sıradaki: Expo mobil derleme (token bekleniyor), canlı kanal yöneticisi API'leri (SiteMinder/HotelRunner).

## Güncelleme (2026-08-15, iter 547)
- HotelRunner canlı kanal bağlantısı (MOCK↔CANLI mod, kimlik bekliyor), TRevPOR/GOPPAR hedef ayarları, fonksiyon teklifi PDF + e-posta (Resend MOCK) ve haftalık salon takvimi (boş slot→teklif) tamamlandı (iteration_539 %100).
- Bekleyen kullanıcı girdileri: HotelRunner HR_ID+TOKEN, Resend API anahtarı, Expo Access Token.

## Güncelleme (2026-08-15, iter 548)
- Teklif takip hatırlatma robotu (3 gün yanıtsız → otomatik e-posta kuyruğu + bildirim) ve kanal fiyat sapma tablosu (kırmızı vurgulu, ±%5 eşik) tamamlandı (iteration_540 %100).

## Güncelleme (2026-08-15, RM Robot MVP Gap Analizi)
- Kullanıcının yüklediği rm_robot_mvp_roadmap.md (25 madde) kod tabanıyla karşılaştırıldı: 12 kalem ZATEN TAMAM (Net RevPAR, guardrail çekirdeği, açıklanabilirlik, onay akışı, kanal adaptörü, RGI ölçümü, hava/tatil sinyalleri...).
- 10 gerçek eksik ROADMAP.md'ye P0-P3 önceliğiyle eklendi (G1-G10). D1 uyum ilkeleri anayasası yazıldı: /app/memory/UYUM_ILKELERI_D1.md.
- P0 sıradaki işler: G1 guardrail sertleştirme (±%15 adım limiti + günlük push limiti), G2 öneri kabul oranı metriği + red nedeni etiketleme.

## Güncelleme (2026-08-15, iter 549 — Robot Güven Merkezi)
- RM MVP gap listesinden G1 (guardrail ±%15 + günlük limit + ihlal logu), G2 (kabul oranı raporu), G4 (Net OTB / p_cancel katmanı — motor artık net dolulukla fiyatlıyor) ve G6 (Shadow Mode) tamamlandı, iteration_542 %100.
- Kalan gap'ler: G3 compset source etiketi, G5 isotonic kalibrasyon, G7 talep simülatörü, G8 lisanslı rate shopping, G9 esneklik, G10 havuz veri.
