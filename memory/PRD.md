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

## Güncelleme (2026-09-01, iter 600) — UK Uyumlu İK & Bordro Modülü
- /api/uk-payroll/* + UKPayrollPanel (Operations > Staff > "İK & Bordro (UK)", PRO mod).
- NMW yaş bantları + top-up, PAYE, NI Class 1, öğrenci kredisi, offboarding final pay,
  aylık bordro run + payslip PDF (Türkçe font fix) + mock e-posta. iteration_600 %100.
- Detay: CHANGELOG.md iter 600. Bekleyen: Resend/Twilio anahtarları (kullanıcı).

## Güncelleme (2026-09-01, iter 601) — Bordro Robotu + P45 + Portal + Emeklilik
- Bordro Robotu (16. motor, ayın son günü otomatik run + yönetici özeti), P45 Part 1A PDF,
  Personel Portalı ("Portalım" sekmesi, staff rolleri sadece bunu görür), Emeklilik AE
  (%5 EE + %3 ER, £520-£4,189 band). iteration_601 %100. Detay: CHANGELOG.md iter 601.

## Güncelleme (2026-09-01, iter 602) — P60 + İzin Portalı + BACS + Vardiya Hatırlatması
- P60 vergi yılı özet PDF, self-servis izin talebi + yönetici onayı, BACS Standard 18
  banka dosyası, Vardiya Hatırlatması (17. motor, "İK & Vardiya" kategorisi, opsiyonel).
  iteration_602: backend 28/28. Detay: CHANGELOG.md iter 602.

## Güncelleme (2026-09-01, iter 603) — İzin Bakiyesi + Karşılaştırma + WhatsApp + Belgeler
- İzin bakiyesi (portal rozeti + çifte kontrol), bordro dönem karşılaştırma (renkli farklar),
  WhatsApp'lı vardiya hatırlatma (Twilio mock), personel İK belgeleri (Object Storage CRUD).
  iteration_603: backend 35/35 kümülatif. Detay: CHANGELOG.md iter 603.
- UI otomasyon notu: sidebar bölüm testid'i `nav-section-{label}` (örn. nav-section-Operations).

## Güncelleme (2026-09-01, iter 604) — SSP + İzin Takvimi + Belge Hatırlatıcısı
- SSP 2026/27 otomatik bordro entegrasyonu (SSP-only satır dahil), renkli izin takvimi
  (çakışma vurgulu, 5. sekme), belge süresi hatırlatıcısı (18. motor, 60 gün eşiği).
  iteration_604: 44/44 kümülatif pytest. Detay: CHANGELOG.md iter 604.
- Resend/Twilio anahtarları 5. kez istendi, sağlanmadı — MOCK devam (bkz CHANGELOG geçiş adımları).

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

## Güncelleme (2026-08-15, rakip karşı-analizi)
- Rakip raporu incelendi: 15 yeni gap (K1-K15) ROADMAP'e eklendi. P0 hızlı işler: K1 asimetrik adım tavanı, K2 karar sonuç takibi, K3 kill switch. Bizim 9 satış kozumuz netleşti (HotelRunner, hava sinyali, KVKK, grup wash, parity, RGI, PDF, günlük limit, uyum anayasası).

## Güncelleme (2026-08-15, iter 550 — Rakip gap P0)
- K1 asimetrik adım tavanı + cold-start, K2 karar sonuç zinciri (outcome ledger + günlük worker), K3 kill switch (acil fren), K7 shadow çıkış kriterleri tamamlandı. Kullanıcı kararıyla CANLI SCRAPER opsiyonu eklendi (D1 ilkesi rev.2: yasal kamuya açık toplama; bot koruması→mock_fallback). iteration_543 %100.
- Kalan rakip gap'leri: K4 iptal modeli v2 (Brier+temporal), K5 güven zarfı, K6 veri-güven kapısı, K8 event v2, K9-K12 (P2), K13-K15 (P3).

## Güncelleme (2026-08-15, iter 551 — Rakip gap P1)
- K4 iptal modeli v2 (kanal+iade+Brier+temporal+isotonic, aylık oto kalibrasyon), K5 güven zarfı (skor+kanıt+gri satır), K6 veri-güven kapısı (bayat veri→auto-apply gated), K8 event sinyali v2 (kapasite ağırlıklı boost) tamamlandı. iteration_544 %100. G5 de kapandı.
- Kalan: K9 replay backtest, K10 faktör şelalesi, K11 bid-price ağı, K12 güç analizi, K13-K15, G7 simülatör, pilot kiti.

## Güncelleme (2026-08-15, iter 552)
- K10 faktör şelalesi (₺ etkili çipler), K9 replay backtest (point-in-time), G7 talep simülatörü (robot optimizör +%13.2 uplift ile kazanıyor) ve Pilot Otel Kiti (PILOT_OTEL_KITI.md) tamamlandı. iteration_545 %100.
- Kalan: K11 bid-price ağı, K12 esneklik güç analizi, K13 publisher sertifikasyonu, K14 Cloudbeds, K15 teknik sözleşme dokümanları.

## Güncelleme (2026-08-15, iter 553 — K11/K13/K15 + Simülatör PDF)
- K11 Bid-Price Ağı: displacement + MinLOS/CTA/CTD tek çerçevede. AI pricing önerilerine bid_price/bid_floor_applied/restrictions alanları eklendi (öneri bid tabanının altına inemez, şelaleye "Bid-price tabanı" adımı düşer). Simülatör panelinde "Ağı Hesapla" tablosu (GET /api/simulator/{pid}/bid-price).
- K13 Publisher Sertifikasyonu: POST /api/hotelrunner/certify/{pid} — test push + geri okuma doğrulaması. CANLI modda sertifikasyon geçilmeden push_daily HTTP 428 ile BLOKLANIR (MOCK etkilenmez). HotelRunnerPanel'e sertifikasyon bölümü (rozet + kontrol listesi) eklendi.
- K15 Teknik Sözleşme Dokümanları: TEKNIK_SOZLESMELER_K15.md (confidence-semantics, price-domain-contract, rate-provenance) tamamlandı.
- Simülatör PDF: GET /api/simulator/{pid}/report-pdf (reportlab) + panelde "PDF Rapor" butonu.
- iteration_546 %100 (backend 7/7, frontend 3/3). MOCK modda kimlik kontrolü ⚠️ olarak gösteriliyor (UX düzeltmesi).
- Kalan: K12 esneklik güç analizi, K14 Cloudbeds adaptörü, Event Signal v2 mekan-mesafe ağırlığı, lisanslı rate-shopping feed (P2), Expo EAS build (P3, kullanıcı anahtarı bekleniyor).

## Güncelleme (2026-08-15, iter 554 — K12/K14 + Event v2 + Pilot Sunum)
- K12 Esneklik Güç Analizi: GET /api/elasticity/{pid} — log-log OLS ile tesis esnekliği (e, r², örneklem) + agresiflik faktörü (×0.75–×1.2). AI pricing motoru 7 gün taze faktörü delta ölçeklemesine uygular (evidence: "Esneklik ayarı", alan: elasticity_aggressiveness). Simülatör panelinde "Esneklik Güç Analizi" kartı.
- K14 Cloudbeds PMS Adaptörü: /api/cloudbeds/* (status, config, test-connection, push-from-rms → putRate ≤30 aralık, pull-reservations → getReservations, log). API key yoksa MOCK. Yeni CloudbedsPanel ("cloudbeds-live" görünümü, Market & Compset menüsünde).
- Event Signal v2: public_events artık venue_name + distance_km alır; motor ağırlığı = kapasite × mesafe sönümü (max(0.25, 1−km/10)).
- Pilot Sunum Modu: POST/GET /api/simulator/{pid}/branding (logo_url) + GET /api/simulator/{pid}/pitch-pdf — logo + robot-vs-sabit özeti + 7 günlük rakip fiyat kıyası (fiyat endeksi) + esneklik bulgusu tek PDF. Panelde "Pilot Sunum PDF" butonu + logo girişi.
- iteration_547: backend 16/16 %100; frontend'de SimulatorPanel state/handler eksiği (testing agent revert'i) bulunup düzeltildi, UI ekran görüntüsüyle doğrulandı. Ayrıca ai_pricing_engine.py sonundaki başıboş "router" satırı (import'u kıran NameError) temizlendi.
- Kalan: lisanslı rate-shopping feed (P2), Expo EAS build (P3, kullanıcı anahtarı bekleniyor), Cloudbeds/HotelRunner CANLI mod (kullanıcı kimlikleri bekleniyor).

## Güncelleme (2026-08-15, iter 555 — PMS Bağlantı Merkezi + Cloudbeds Sertifikasyonu)
- PMS Bağlantı Merkezi (agnostic middleware): /api/pms-connect/* — 5 adaptör: Mews (açık, Connector API rates/updatePrice), Apaleo (açık, OAuth2 + rate-plans PUT), SiteMinder (partner, OTA_HotelRateAmountNotifRQ XML), eviivo (kapalı, bulk JSON iskelet), Elektraweb (yarı açık, fiyat matrisi JSON). Standart RMS satırları [{date,rate,availability}] _translate() ile sağlayıcı diline çevrilir. Kimlik yoksa MOCK; sertifikasyon (test push + geri okuma + format çevirisi) geçilmeden CANLI push 428 ile bloklanır. Yeni PmsConnectHub paneli ("pms-connect", Market & Compset menüsü): sağlayıcı kartları (API türü rozetleri), dinamik kimlik formu, push + çevrilmiş payload önizleme, sertifikasyon, log.
- Cloudbeds Sertifikasyonu: POST /api/cloudbeds/certify/{pid} (test push + geri okuma + canlı API erişim kontrolü), canlı push gate (CERT-TEST bypass riski kapatıldı), CloudbedsPanel'e sertifikasyon bölümü.
- Kayıtlar: db.pms_connect_config, db.pms_push_log, db.pms_inbound.
- iteration_548: backend 19/19, frontend %100 geçti.
- Yeni sağlayıcı ekleme: pms_connect.py PROVIDERS sözlüğüne kayıt + _translate'e çeviri şablonu eklemek yeterli (UI otomatik).

## Güncelleme (2026-08-15, iter 556 — 7 özellik: Partner Kiti, Mews CANLI, Gece Push, Sağlık Panosu, Esneklik Trendi, Mesafe Otomasyonu, Sunum Kütüphanesi)
- Partner Başvuru Kiti: GET /api/pms-connect/{provider}/partner-kit/{pid} — hazır İngilizce başvuru e-postası (2-Way ARI, guardrail'ler, sertifikasyon sonuçları) + teknik özet JSON. UI'da kopyala butonu.
- Mews Demo CANLI: POST /api/pms-connect/mews/demo-connect/{pid} — herkese açık demo token'larıyla api.mews-demo.com'a bağlanır, root rate + enterprise saat dilimini otomatik bulur. _mews_utc() tarihleri enterprise TZ gece yarısına çevirir (ilk denemede 'FirstTimeUnitStartUtc is not start of TimeUnit' hatası alındı, TZ dönüşümüyle çözüldü). CANLI sertifikasyon 4/4 GEÇTİ, CANLI push (mocked:false) doğrulandı — İLK GERÇEK UÇTAN UCA FİYAT PUSH'U.
- Otomatik Gece Push: pms_connect.run_auto_night_push() — sertifikalı kanallara RMS senkronu; night_audit.run_night_audit'e bağlandı (pms_connect_settings.auto_night_push açıksa). Toggle + 'Şimdi Çalıştır' UI.
- Kanal Sağlık Panosu: GET /api/pms-connect/health/{pid} — 7 kanal (5 PMS + Cloudbeds + HotelRunner): mod, sertifika, son push, hata oranı. PmsConnectHub üstünde tablo.
- Esneklik Trendi: db.elasticity_history (aylık) + GET /api/elasticity/{pid}/history + SimulatorPanel'de bar grafik.
- Etkinlik Mesafe Otomasyonu: POST /api/public-events/estimate-distance — Nominatim (OpenStreetMap) geocode + haversine (Hallenstadion→4.2km doğrulandı). PublicEventsPanel'de 'Mesafeyi Tahmin Et' butonu.
- Sunum Kütüphanesi: pitch PDF'ler db.pitch_archive'a base64 arşivlenir; liste + indirme endpoint'leri + SimulatorPanel'de kütüphane listesi.
- iteration_549: backend 14/14, frontend %100 geçti. pms_connect.py helper'ları modül seviyesine refactor edildi (night_audit import edebilsin diye).

## Güncelleme (2026-08-15, iter 557 — Push Fark Kontrolü, OTB İçe Aktarım, Haftalık Rapor, Apaleo Rehberi)
- Push Fark Kontrolü: POST /api/pms-connect/{provider}/verify-push/{pid} — _verify_channel(): Mews'te GERÇEK geri okuma (rates/getPricing, TZ eşleştirmeli), diğerlerinde mock; sapma >%0.5 → db.pms_alerts uyarısı. Gece push'a entegre (results: verify_ok + max_drift_pct). Canlı doğrulama: %0 sapma, birebir eşleşme.
- Rezervasyon İçe Aktarımı: POST /api/pms-connect/mews/import-to-otb/{pid} — Mews demo'dan CollidingUtc (60 gün) ile 200 GERÇEK rezervasyon bookings'e upsert (source pms:mews, idempotent, fiyatlar RMS rate'lerinden tahmini). OTB/tahmin/AI fiyatlama artık canlı veri görüyor. NOT: ilk denemede eski TimeFilter/StartUtc parametreleri tarihi veri döndürdü — 2023-06-06 sürümünde interval filtresi CollidingUtc objesi olmalı.
- Haftalık Partner Raporu: GET /api/pms-connect/weekly-report/{pid} — 7 günlük kanal performansı + Türkçe e-posta taslağı + kopyala butonu (sağlık panosunda).
- Apaleo Sandbox Rehberi: PmsConnectHub'da apaleo seçilince 4 adımlı kurulum kutusu (apaleo.dev hesabını KULLANICI açmalı — ajan harici hesap açamaz; kimlik girilince Mews akışıyla aynı canlı sertifikasyon+push hazır).
- iteration_550: backend 11/11, frontend %100 geçti.
- BEKLEYEN: Apaleo canlı testi kullanıcının client_id/client_secret girmesini bekliyor.

## Güncelleme (2026-08-15, iter 558 — Sapma Uyarısı, Forecast Kıyası, Rate Plan Eşleştirme)
- Sapma Uyarı Bildirimi: GET /api/pms-connect/alerts/{pid} + resolve endpoint'i; sağlık panosunda kırmızı uyarı zili (pms-alert-bell, animate-pulse) + liste + "Çözüldü" butonu; morning report anomalilerine son 24h çözülmemiş sapma uyarıları "Dağıtım:" satırı olarak düşüyor. health response'una active_alerts eklendi.
- Canlı Veri Forecast Kıyası: night_audit her çalıştığında db.forecast_snapshots'a 14 günlük OTB/doluluk fotoğrafı; GET /api/pms-connect/forecast-accuracy/{pid} — olgun snapshot'lardan MAE + Mews gerçek rezervasyon katkısı (dahil/hariç, 14 günde +8 oda-gece). UI: "🎯 Forecast Doğruluk" butonu + tablo.
- Rate Plan Eşleştirme: db.pms_rate_mapping — oda tipi ↔ kanal rate kodu + çarpan; GET/POST rate-mapping endpoint'leri; push_from_rms eşleştirme varsa oda tipi bazında ayrı basar (cfg_override rate_id/rate_plan_id/inv_code). CANLI test: Mews'e 2 oda tipi (×1.0 Standard, ×1.4 Deluxe) mocked:false basıldı.
- Verify mapping-aware yapıldı: push loglarına rate_code eklendi; son push batch'i kod bazında gruplanıp her kodun kendi getPricing'i ile karşılaştırılıyor — mapped push sonrası %0 sapma doğrulandı (161.0 = 115×1.4 birebir). Gece push'ta canlı verify öncesi 6sn bekleme (Mews asenkron işleme yanlış pozitifini önler).
- iteration_551: backend 13/14 (tek fark verify tasarım konusuydu, düzeltildi), frontend %100. React duplicate-key uyarısı giderildi.
- ÖĞRENİM: Mews updatePrice asenkron — push'tan hemen sonra getPricing eski değeri dönebilir; verify'ı geciktir.

## Güncelleme (2026-08-15, iter 559 — Mews Oda/Rate Keşfi + Kanal Gelir Katkısı)
- Mews Oda/Rate Keşfi: GET /api/pms-connect/mews/discover-rates/{pid} — CANLI: services/getAll + rates/getAll (200 gerçek rate) + resourceCategories/getAll (100 gerçek oda kategorisi). UI: "🔎 Mews Oda/Rate Keşfi" butonu boş eşleştirme kodlarını root rate'lerle otomatik doldurur; input altında ✓ rate adı doğrulaması + datalist önerileri.
- Kanal Gelir Katkısı: GET /api/pms-connect/revenue-by-channel/{pid}?months=6 — rezervasyon kaynağına göre aylık gelir aggregate (pct, bookings, totals). UI: recharts PieChart (donut) + ay seçici + legend; varsayılan ay = içinde bulunulan ay. 6 aylık toplam ₺131K, en güçlü kanal gösterimi.
- BUG FIX: loadRev/discoverRates handler tanımları ilk edit'te dosyaya işlenmemişti → "loadRev is not defined" çökme; yeniden eklendi, ekran görüntüsüyle doğrulandı.
- Ekran doğrulaması: sağlık panosu 7 kanal (Mews CANLI+SERTİFİKALİ·CANLI, tümü sertifikalı), gelir pastası, eşleştirme tablosu keşif sonrası ✓ etiketli.
- BEKLEYEN: Apaleo kimliği hâlâ girilmedi (panelde rehber hazır — kullanıcı girince canlı sertifikasyon+push).

## Güncelleme (2026-08-15, iter 560 — OTA Kırılımı, Genel Keşif, Aylık Trend)
- OTA Kırılımı: revenue-by-channel artık kaynakları gruplar (OTA/PMS/Doğrudan/Grup Satış/Demo/Diğer) + komisyon sonrası net gelir (Booking %15, Expedia/Hotels.com %18, Agoda %17, diğer OTA %15). Response: groups[], commission_pct/net_revenue per source, total_net_revenue. UI: GRUP/KAYNAK görünüm anahtarı, legend'da net gelir.
- Keşif Tüm Kanallara: /api/pms-connect/{provider}/discover-rates/{pid} generic oldu — mews (canlı, 200 rate + 100 kategori) + apaleo (OAuth → rate-plans + unit-groups, kimlik girilince çalışır) + diğerleri 501. UI butonu mews/apaleo canlı modda görünür.
- Aylık Trend Çizgisi: UI'da ilk 5 kaynağın aylık pay yüzdesi LineChart + son iki ay farkına göre ▲/▼ vurguları.
- BUG: bir search_replace edit'i bozuk dosya kopyasına uygulandı → dosya sonunda syntax hatası; artık blok temizlendi, generic discover yeniden uygulandı. Test sırasında girilen sahte eviivo kimlikleri temizlendi (tümü tekrar mocked, mews live).
- Doğrulama: curl (gruplar: OTA %9.4 komisyon ₺2051, net ₺129K; mews keşif 200/100; apaleo 400; eviivo 501) + 2 ekran görüntüsü (pasta+net gelir, GRUP görünümü, trend çizgisi ▼ oklarıyla).
- BEKLEYEN: Apaleo kimliği hâlâ girilmedi.

## Güncelleme (2026-08-15, iter 561 — Komisyon Ayarları, Yönetici PDF, Doğrudan Teşvik)
- Komisyon Ayarları: GET/POST /api/pms-connect/commission-settings/{pid} — OTA kaynak bazında özel oran (0-50%), boş = varsayılan; revenue-by-channel net hesabı override'ı kullanıyor (Booking %12 testi: net=brüt×0.88 doğrulandı, sonra temizlendi). UI: ⚙ panel + Kaydet.
- Aylık Yönetici Özeti PDF: GET /api/pms-connect/executive-pdf/{pid} — reportlab tek sayfa: gelir kırılımı (grup+net+komisyon), kanal sağlığı (7 kanal, sertifika, son push, uyarı), forecast isabeti + Mews katkısı. UI: 📄 buton (health board).
- Doğrudan Rezervasyon Teşviki: GET /api/pms-connect/direct-booking-tips/{pid} — 6 aylık OTA komisyon kaybı (₺2.052, yıllık ~₺4.103), doğrudan pay (%8.9 vs %30 hedef), 5 akıllı öneri. UI: 💡 yeşil ipucu kartı.
- Doğrulama: curl (override matematiği, tips, PDF %PDF) + ekran görüntüsü (komisyon paneli tüm OTA kaynaklarıyla, teşvik kartı, PDF butonu).
- BEKLEYEN: Apaleo kimliği hâlâ girilmedi (4. istek — kullanıcıya tekrar hatırlatıldı).

## Güncelleme (2026-08-15, iter 562 — TAM REGRESYON GEÇTİ)
- iteration_552: PMS Bağlantı Merkezi'nin son 3 oturumdaki TÜM özellikleri toplu uçtan uca doğrulandı — backend 30/30 pytest, frontend %100, sıfır hata/regresyon.
- Kapsam: providers, push+cert+404, Mews CANLI zinciri (push→verify drift 0→import ~200 idempotent), keşif (Mews canlı / Apaleo 400), rate mapping, gece push toggle+run, health (7 kanal + active_alerts), uyarı akışı (insert→resolve→morning report 'Dağıtım' anomalisi), gelir kırılımı (grup/net/komisyon override), haftalık rapor, teşvik, yönetici PDF, forecast isabet, partner kiti + platform regresyonları (ai-pricing, elasticity, simulator, hotelrunner, cloudbeds).
- Kanonik regresyon paketi: /app/backend/tests/test_iteration552_full_regression.py (Mews canlı çağrılar 3x retry + 8s bekleme ile).
- BEKLEYEN: Apaleo kimliği (5. hatırlatma) — kullanıcı Client ID/Secret girince canlı doğrulama yapılacak.

## Güncelleme (2026-08-15, iter 563 — Pilot Davet + Teşvik Takibi)
- Pilot Otel Daveti: GET /api/pms-connect/pilot-invite/{pid} — Türkçe davet e-postası, GERÇEK kanıtlarla dolu (CANLI sertifikasyon tarihi, 24+ canlı push, %0 sapma doğrulaması, ~200 rezervasyon aktarımı) + son pilot sunum PDF arşiv referansı. UI: "✉ Pilot Davet" butonu + kanıt rozetleri + kopyala.
- Teşvik Takibi: tips artık {index, text, done} objeleri; POST /direct-booking-tips/{pid}/toggle ile yapıldı/yapılmadı işaretleme (db.tip_status); direct_trend ile doğrudan payın aylık değişimi (%22→...). UI: checkbox'lar (optimistic update, üstü çizili tamamlanan), done_count sayacı, aylık pay satırı.
- BUG FIX: eski tips render'ı obje listesini string basınca React çöktü ("Objects are not valid as a React child") — checkbox'lı render ile değiştirildi, ekran doğrulandı.
- SiteMinder partner formu: harici site, ajan dolduramaz — başvuru kiti (kopyala butonlu) kullanıcı için hazır.
- BEKLEYEN: Apaleo kimliği (6. hatırlatma).
- BEKLEYEN: Apaleo canlı testi kullanıcının client_id/client_secret girmesini bekliyor (rehber panelde).
- Kalan: lisanslı rate-shopping feed (P2), Expo EAS build (P3), tüm PMS'lerde CANLI mod (partner kimlikleri bekleniyor: Mews demo token, Cloudbeds API key, SiteMinder pmsXchange, eviivo NDA, Elektraweb entegrasyon ekibi).

## Güncelleme (2026-08-15, iter 564 — Pilot Takip Listesi CRM + Kill Switch Tatbikatı TAMAMLANDI)
- Pilot Takip Listesi (mini CRM): GET/POST /api/pms-connect/pilot-leads/{pid}, POST /pilot-leads/{lead_id}/status (davet→görüşme→demo→pilot→kaybedildi), YENİ: POST /pilot-leads/{lead_id}/note (not güncelleme). UI: "📋 Pilot Takip" butonu → otel adı+iletişim+not ekleme formu, satır bazında durum select'i ve onBlur ile kaydedilen not input'u.
- Kill Switch Tatbikatı: POST /api/pms-connect/killswitch-drill/{pid} — 4 adımlı tatbikat (aç→blok doğrula→denetim kaydı→kapat, drill=true etiketiyle gerçek olaylardan ayrı). YENİ: GET /killswitch-drill/{pid}/report-pdf — yönetime sunulabilir reportlab güvence PDF'i (adımlar, son 30 gün gerçek blok/guardrail sayıları, tatbikat geçmişi). UI: "🛑 Kill Switch Tatbikatı" butonu + rapor + "📄 Güvence PDF" + kopyala.
- Test: curl E2E (lead CRUD+not, drill 4/4 geçti, PDF 200 %PDF) + testing_agent iteration_553 frontend %100 (persistence, drill sonrası kill switch pasif regresyonu, pilot davet regresyonu dahil). Test leadleri temizlendi.
- BEKLEYEN: Apaleo Client ID/Secret (7. hatırlatma), SiteMinder/eviivo/Elektraweb kimlikleri, Expo EAS build.

## Güncelleme (2026-08-16, MVP Kapanış Paketi — 7/7 TAMAMLANDI, iterasyon 555)
- Rakip gap analizi belgesi incelendi; 13 iddianın çoğu zaten bizde vardı (tablo kullanıcıya sunuldu). Gerçek 7 eksik kapatıldı:
  1) Red nedeni taksonomisi: reject endpoint'i reason_tag enum kabul ediyor (too_aggressive/too_low/event_unknown/segment_mismatch/data_wrong/strategy_conflict/other); AIPricingEnginePanel reject modalında chip'ler; Trust Center kabul raporu reason_tags agregasyonu (REJECT_TAG_LABELS trust_center.py'de).
  2) MPI/ARI: rgi_proof.py hafta satırlarına our_adr/market_adr/market_occ_pct/mpi/ari + avg_mpi/avg_ari; RgiProofCard rozetleri.
  3) D1 anayasası: GET /api/compliance-principles (memory/UYUM_ILKELERI_D1.md okur); TrustCenterPanel'de tc-principles-section.
  4) Haftalık PDF: GET /api/pms-connect/weekly-report-pdf/{pid} (reportlab); PmsConnectHub'da 📄 Haftalık PDF.
  5+6) weather_calendar.py (YENİ): open-meteo (geocode + günlük tahmin) + Nager.Date resmi tatiller, anahtarsız. Koleksiyonlar: property_geo, holiday_cache, demand_calendar_signals. Çarpanlar: tatil +%5, arife +%3, güneşli hafta sonu (≥22°C, yağışsız) +%3, şiddetli hava (WMO kodu/≥15mm) −%3. GET/POST /api/demand-signals/{pid}. Motor entegrasyonu: ai_pricing_engine BUILD_SUGGESTIONS ext_map → suggested_rate çarpımı + ext_mult/ext_reasons alanları + kanıt satırı. UI: AIPricingEnginePanel 14 günlük sinyal şeridi.
  7) Havuz izni: /api/chain/benchmark/consent GET/PUT (pool_consent koleksiyonu); share_data=false tesis benchmark'tan hariç; ChainBenchmarkPanel'de toggle'lı Havuz Veri İzinleri bölümü.
- Test: tüm backend curl E2E (motor ×1.03 canlı Londra verisiyle doğrulandı) + testing_agent iteration_555 frontend %95+ (blokaj yok, opsiyonel palet derin-link P2'ye yazıldı).
- BEKLEYEN: Apaleo Client ID/Secret hâlâ kullanıcıdan gelmedi (canlı sertifikasyon bloke).

## Güncelleme (2026-08-16, 3 özellik — iter. 556, %100 geçti)
- Sinyal Ağırlık Ayarı: GET/PUT /api/demand-signals/{pid}/config (holiday_pct/eve_pct/sunny_weekend_pct/bad_weather_pct 0-15 clamp + enabled; demand_signal_config koleksiyonu); PUT sonrası otomatik takvim yenileme. UI: AIPricingEnginePanel sinyal şeridinde ⚙ Ağırlıklar dişlisi.
- Rakip Karşılaştırma PDF: GET /api/competitive-gap-pdf (trust_center.py; 17 kalem G1-G10+ekstralar, 16 VAR/1 KISMI + benzersiz farklar bölümü). UI: RmsComparisonPanel'de 📄 Gap Analizi PDF butonu (rmsc-gap-pdf-btn).
- Kör Nokta Radarı: rms-acceptance raporuna blind_spot (en yaygın red etiketi + % pay + öneri, BLIND_SPOT_RECS) ve monthly_tags eklendi; TrustCenterPanel'de amber tc-blind-spot kartı; aylık yönetici PDF'ine '4. Kor Nokta Radari' bölümü (son 90 gün).
- BEKLEYEN: Apaleo Client ID/Secret hâlâ gelmedi (kullanıcı 2 kez 'Evet' dedi ama anahtar yapıştırmadı; DB'de credentials boş — canlı sertifikasyon bloke).

## Güncelleme (2026-08-16, 3 özellik — iter. 557, %100 geçti)
- Sinyal Etki Raporu: GET /api/demand-signals/{pid}/impact-report?weeks=4 (oda-gece × ADR × (çarpan−1)/çarpan tahmini); AIPricingEnginePanel'de 📊 Etki Raporu toggle'ı, haftalık hücreler + toplam (+18.3 CHF doğrulandı).
- Radar Bildirimi: workers.check_blind_spot_alert (min 3 etiketli red, pay ≥%50, 7 gün dedupe, notifications'a high priority uyarı) + günlük blind_spot_alert_loop; manuel tetik POST /api/rms-acceptance/{pid}/blind-spot-alert/run.
- Gap PDF Markalama: /api/competitive-gap-pdf?pid=&customer= — template_settings logo_url (varsa çizilir) + 'X icin hazirlanmistir' altın satır; RmsComparisonPanel'de müşteri adı inputu (rmsc-gap-customer-input).
- BEKLEYEN: Apaleo Client ID/Secret (4. kez istendi, hâlâ gelmedi — DB'de credentials boş).

## Güncelleme (2026-08-16, 3 özellik — iter. 558, %100 geçti)
- Etki Arşivi: compute_impact_report module-level yapıldı (weather_calendar.py); aylık yönetici PDF'ine '5. Sinyal Etkisi' bölümü (toplam katkı + haftalık satırlar).
- Logo Yükleme: YENİ routes/platform_ext/branding.py — POST/GET/DELETE /api/branding/logo/{pid} (b64, max 700KB, PNG/JPEG/WebP; template_settings.logo_b64); get_logo_reader+draw_logo helper'ları exec/haftalık/tatbikat/gap PDF'lerinin tümünde sağ üst logo çizer. UI: SettingsHubPanel 'Hotel Logo (PDF)' bölümü (yükle/önizle/kaldır).
- Tatil Önizleme: GET /api/demand-signals/{pid}/holidays?days=90; RateCalendarEditable gün hücrelerinde teal 🎌 tatil bandı + lejant (CH tesiste Jeûne genevois/Bettagsmontag doğrulandı).
- BEKLEYEN: Apaleo Client ID/Secret (kullanıcı bu turda Apaleo'yu seçmedi; hâlâ boş).

## Güncelleme (2026-08-16, 2 özellik — iter. 559, %100 geçti)
- Tatil Fiyat Önerisi: RateCalendarEditable'da tatil bandına tıklayınca modal (rev-cal-holiday-modal) — base × (1+holiday_pct/100) önerisi, 'Zammı Uygula' mevcut rate-override PUT'unu kullanır. holiday_pct sinyal config'inden gelir. Testing agent düzeltmeleri: Room Type dedupe (duplicate key uyarısı) + base Math.round (off-by-one algısı).
- PDF Rapor Merkezi: GET /api/pms-connect/pdf-center/{pid} (4 on-demand rapor + tatbikat arşivi + logo notu); ReportsHub'a 5. sekme 'PDF Arşivi' (report-tab-pdf, pdf-report-center) indirme linkleriyle.
- BEKLEYEN: Apaleo Client ID/Secret (hâlâ boş), Resend anahtarı (haftalık e-posta otomasyonu için).

## Güncelleme (2026-08-16, 3 özellik — iter. 560, %100 geçti)
- Toplu Tatil Zammı: POST /api/demand-signals/{pid}/apply-holiday-markup (90 gün tatilleri, base=occ-katmanlı recommended × (1+holiday_pct/100); manuel/diğer robot override'ları korunur, holiday_markup=True idempotent). UI: rev-cal-bulk-holiday-btn + onay modalı.
- Rapor Zamanlayıcı: pms_connect PDF_BUILDERS kaydı + archive_pdf_reports (db.pdf_archive, dönem dedupe) + pdf_archive_loop (Pzt haftalık, ayın 1'i aylık); POST run-now + GET download; ReportsHub 'Zamanlanmış Arşiv' bloğu + ⚡ Şimdi Üret.
- Takvim Etkinlik Bandı: GET /api/demand-signals/{pid}/events?days=90 (public_events, kapasite×mesafe decay boost); RateCalendarEditable mor 🎪 bant + lejant (tatil bandıyla dikey istif).
- P2 notları ROADMAP'e eklendi (duplicate room_types verisi, tur modalı persistence).

## Güncelleme (2026-08-16, 3 özellik — iter. 561, %100 geçti)
- Etkinlik Zam Önerisi: mor 🎪 banda tıklayınca violet modal (rev-cal-event-modal) — base × (1+boost_pct/100), Zammı Uygula/Vazgeç.
- Arşiv Temizliği: db.pdf_archive_config.retention_months (3-36, default 12); PUT /api/pms-connect/pdf-archive/{pid}/retention (anında purge) + archive_pdf_reports her çalışmada purge; ReportsHub'da Saklama select'i (6/12/24/36 ay).
- Takvim Tur Hatırlama: YENİ routes/platform_ext/ui_prefs.py (GET/PUT /api/ui-prefs, kullanıcı bazlı); RevenuePanel tur bayraklarını sunucuyla senkronlar (tarayıcı değişse de bir kez gösterim). Test: yeni browser context'te tur açılmadı ✓.
- Console uyarı düzeltmeleri: retention option template literal + arşiv listelerinde index'li key.

## Güncelleme (2026-08-16, 3 özellik — iter. 562, %100 geçti)
- Zam Geri Alma: POST /api/demand-signals/{pid}/apply-markup (prev_custom_rate saklar, markup_kind/markup_name) + POST /{pid}/undo-markups (manuel fiyat varsa restore, yoksa override silinir); takvim modalları artık apply-markup kullanır; header'da ↩ Zamları Geri Al (rev-cal-undo-markups-btn).
- Sinyal Özeti Bildirimi: send_weekly_signal_digest (hafta dedupe, refresh + 7 gün tatil/hava/etkinlik satırları) + weekly_signal_digest_loop (Pzt 03-09 UTC) + manuel POST /{pid}/weekly-digest/run. W33 özeti bildirimlerde.
- Mükerrer Veri Temizliği: YENİ routes/hotel_ops/data_cleanup.py — GET dry-run + POST merge (en çok rezervasyonlu kayıt korunur; bookings/rooms/rate_overrides/pms_rate_mapping remap; data_cleanup_log denetim). Settings → 'Veri Temizliği' (DB temiz: 78 kayıt, 0 grup → yeşil rozet).

## Güncelleme (2026-08-17, 3 özellik — iter. 563, %100 geçti)
- Sezon Şablonları: db.season_templates (tesis başına seed: Yaz +15 / Kış -10 / Bayram +20 — bayram tarihi tesisin ülkesine göre otomatik); CRUD + apply (max 190 gün, occ-katmanlı base, manuel override korunur, markup_kind=season); RateCalendarEditable 🗂 Sezonlar modalı (listele/uygula/sil/oluştur).
- Zam Geçmişi: db.markup_history (_log_markup — apply/undo, kind, detay, kullanıcı e-postası); GET /{pid}/markup-history; 🕓 Geçmiş modalı.
- Digest E-postası: send_weekly_signal_digest artık owner_pulse._send_email ile admin/manager kullanıcılara HTML e-posta gönderiyor — RESEND_API_KEY placeholder olduğundan MOCK modda; gerçek anahtar girilince canlı.
- Tüm zamlar (tatil/etkinlik/sezon) tek '↩ Zamları Geri Al' ile geri alınabilir.

## Güncelleme (2026-08-17, 2 özellik — iter. 564, %100 geçti)
- Sezon Önizleme: apply_season dry_run parametresi (yazmadan gün gün eski→yeni fiyat listesi, max 60 satır); Sezonlar modalında Önizle → önizleme paneli + 'Onayla ve Uygula'/Kapat.
- Doluluk Kuralları: db.occupancy_rules (threshold_pct 50-100 def 90, extra_pct 1-50 def 10, enabled def false); GET/PUT /occupancy-rule + POST /run; apply_occupancy_rule (30 gün tarama, occ≥eşik → base×mult×(1+ek%), markup_kind=occupancy, manuel korunur, idempotent) + occupancy_rule_loop (6 saatte bir enabled kuralları çalıştırır). UI: ⚡ Doluluk Kuralı modalı (Kaydet+Şimdi Çalıştır / Sadece Kaydet). Zam Geçmişi ve ↩ Geri Al occupancy'yi de kapsar.

## Güncelleme (2026-08-17, 2 özellik — iter. 565, %100 geçti)
- Düşük Doluluk Kuralı: occupancy_rules'a low_enabled/low_threshold_pct(def 40)/low_discount_pct(def 10); apply_occupancy_rule düşük doluluk günlerine indirim uygular (markup_kind=occupancy, ↩ Geri Al kapsar). UI: modalda checkbox + sky-blue inputlar.
- Kural PMS Push'u: occupancy_rules.push_to_pms; kural uygulandığında run_auto_night_push tetiklenir (70 gün-fiyat, 1 canlı Mews kanalı doğrulandı); toast'ta push özeti.
- BEKLEYEN: RESEND_API_KEY hâlâ placeholder (re_XXX...) — kullanıcı gerçek anahtarı .env'e/mesaja iletmedi; digest e-postası MOCK. Apaleo Client ID/Secret hâlâ yok.

## Güncelleme (2026-08-17, 2 özellik — iter. 566, %100 geçti)
- Kural Etki Paneli: db.occupancy_rule_impact (her kural koşusunda ay bazlı zam/indirim gün + delta kaydı); GET /{pid}/occupancy-rule/impact (son 6 ay aggregate, net katkı). UI: Doluluk Kuralı modalında yeşil etki paneli (rev-cal-occ-impact-panel) — ay satırları ↑zam/↓indirim/net; boşsa bilgi metni.
- Rakip Fiyat Tetiği: db.comp_trigger (threshold_pct 3-50 def 10, enabled); GET/PUT + POST /comp-trigger/run — market_supply geo ortalaması vs bizim fiyat (14 gün), sapma ≥ eşik ise günlük dedupe'lu bildirim (🔔 'Rakip Fiyat Tetiği', öneri fiyatlarıyla) + comp_trigger_loop (6 saatte bir). UI: AI Pricing panelinde kart (ai-pricing-comp-trigger) — eşik input, otomatik switch, 'Şimdi Kontrol Et' + sapma tablosu (biz/pazar/%/öneri).
- BEKLEYEN: RESEND_API_KEY placeholder (digest e-postası MOCK); Apaleo Client ID/Secret yok.

## Güncelleme (2026-08-17, 3 özellik — iter. 567, %100 geçti)
- Tetik Fiyat Uygula: POST /{pid}/comp-trigger/apply — sapan günlerin öneri fiyatlarını (max 10) rate_overrides'a yazar (markup_kind=comp_trigger, prev saklanır, ↩ Geri Al kapsar, markup_history logu). UI: sonuç panelinde yeşil '⚡ Önerileri Takvime Uygula' (ai-pricing-comptrig-apply).
- Etki Grafiği: Doluluk Kuralı modalında 2+ ay veri varsa aylık net katkı çubuk grafiği (rev-cal-occ-impact-chart, yeşil/kırmızı barlar); tek ayda gizli.
- Sapma Isı Haritası: GET /{pid}/comp-deviations?year&month (eşiksiz tüm sapmalar); takvimde '🌡 Sapma' toggle (rev-cal-heat-toggle) — kırmızı=pahalıyız/mavi=ucuzuz arka plan tonu (koyuluk=|sapma|), ▲/▼ % rozetleri + lejant (Ağustos 2026'da 31 hücre doğrulandı).

## Güncelleme (2026-08-17, 3 özellik — iter. 568, backend %100 + UI self-test doğrulandı)
- Seçmeli Uygula: comp-trigger/apply {dates:[...]} filtresi; UI'da sapma satırlarında checkbox (ai-pricing-comptrig-sel-{date}, hepsi seçili başlar), '⚡ Seçili Önerileri Uygula (N gün)' sayaçlı buton (0 seçimde disabled).
- Türe Göre Geri Al: undo-markups {kind} filtresi (holiday/event/season/occupancy/comp_trigger, kind'sız=tümü); UI'da '↩ Zamları Geri Al ▾' dropdown (rev-cal-undo-menu, 6 seçenek, dış-tık kapanır); markup_history undo loguna tür yazılır.
- Isı Haritası PDF: GET /{pid}/heatmap-pdf?year&month — reportlab takvim ızgarası (kırmızı/mavi renk tonu, gün başına biz/pazar/%), özet (ort. sapma, en pahalı/ucuz günler), lejant, logo desteği; PDF Merkezi on_demand'e 'heatmap' kartı eklendi (pdf-center-card-heatmap).
- Ek: branch-selector-btn data-testid'i (SelectTrigger) otomasyon stabilitesi için eklendi.

## Güncelleme (2026-08-17, 2 özellik — iter. 568b, curl + UI self-test doğrulandı)
- Oda Tipi Bazlı Tetik: apply_comp_trigger artık TÜM oda tiplerine yazar — her oda tipinin fiyatı taban fiyat oranıyla ölçeklenir (ör. öneri 221.24 → Deluxe 327.44); dönüş {applied, room_types, writes}; log '{N} gün × {M} oda tipi'; toast güncellendi.
- Tetik Geçmiş Grafiği: GET /{pid}/comp-trigger/trend?weeks=8 — konaklama tarihine göre haftalık ort/min/max sapma (ISO hafta bucket'ları, geçmiş 2 hafta + gelecek N hafta); UI'da '📈 Trend' butonu (ai-pricing-comptrig-trend-btn) → SVG çizgi grafik (sıfır çizgisi, kırmızı=pahalı/mavi=ucuz noktalar, hafta etiketleri). Not: SVG text'te çoklu JSX child render sorunu template literal ile çözüldü.

## Güncelleme (2026-08-17, 2 özellik — curl + UI self-test doğrulandı)
- Trend Uyarısı: check_trend_alert(db,pid) — haftalık |ort. sapma| 2 hafta üst üste ≥1pp artarsa 'Trend Uyarısı' bildirimi (haftada 1 dedupe, week alanı); run_competitor_price_trigger her koşuda çağırır (robot 6 saatte bir + manuel), dönüşe trend_alert alanı eklendi; UI'da 'Şimdi Kontrol Et' toast'ı uyarıyı gösterir. Doğrulandı: 2026-W34 bildirimi oluştu, ikinci koşuda dedupe.
- Oda Tipi Sapma Görünümü: _month_deviations(room_type_id) — seçili oda tipinin fiyatı, taban fiyat oranıyla ölçeklenmiş pazar referansına kıyaslanır (Deluxe 185 vs 327 ölçekli pazar); comp-deviations + heatmap-pdf room_type_id parametresi aldı (PDF başlığına oda adı eklenir); takvimdeki mevcut Room Type seçicisi ısı haritasını yeniden yükler (useEffect roomType dep), lejantta oda adı görünür.

## Güncelleme (2026-08-17, 2 özellik — curl + UI self-test doğrulandı)
- Uyarı Eşiği Ayarı: comp_trigger doc'a trend_weeks (2-6, def 2) + trend_step_pp (0.5-10, def 1.0) eklendi; GET/PUT comp-trigger destekler (clamp'li), check_trend_alert cfg'yi okur (N ardışık hafta, her adım ≥ step puan); UI'da 'Uyarı: hafta' + 'puan artış ≥' inputları (ai-pricing-comptrig-trend-weeks / -trend-step), bildirim başlığı N haftayı gösterir.
- Sapma Özeti Kartı: GET /{pid}/comp-trigger/summary — bu hafta/gelecek hafta avg_dev, direction (açılıyor/kapanıyor/stabil, ±0.5pp), alert_active, 6 haftalık bucket'lar; yeni GapSummaryCard.js (gap-summary-card) TodayHub'da Pickup24Card altında — büyük % değeri, sparkline SVG, yön rozeti, 'trend uyarısı aktif' etiketi, tıklayınca revenue'ya gider.

## Güncelleme (2026-08-17, 2 özellik — curl + UI self-test doğrulandı)
- Karttan Hızlı Aksiyon: GapSummaryCard'a '⚡ Önerileri Uygula' butonu (gap-summary-apply, stopPropagation) — dashboard'dan comp-trigger/apply çağırır, toast + kart yenilenir. Doğrulandı: 10 gün × 2 oda tipi uygulandı, makas −%29.5 → +%3.8'e kapandı.
- Haftalık Makas Raporu: send_weekly_signal_digest'e '📡 Pazarla Makas Durumu' bölümü — bu hafta ort. sapma, yön (açılıyor/kapanıyor/stabil), 4-6 haftalık W-bazlı seri; bildirim + e-postaya (MOCK) girer, dönüşte gap_included alanı.
- BUG FIX: _weekly_trend ve _month_deviations override sorgusu artık referans oda tipi id'siyle filtreli (önceden Deluxe override'ı Standard referansına karışıp makası +%45 şişiriyordu).

## Güncelleme (2026-08-17, TAM MODÜL DENETİMİ — iter. 569)
- Kullanıcı '%30 modül çalışmıyor' iddiasıyla tam denetim istedi. testing_agent 280/280 sidebar modülünü (menuSections.js) tek tek tıklayıp doğruladı: HEPSİ RENDER EDİYOR ve çalışıyor (%98.6 tamamen temiz). İddia doğrulanmadı.
- KÖK NEDEN (muhtemel): BASIT mod varsayılan — sidebar'da sadece ~30 core modül görünür, 250'si gizli; kullanıcı göremediklerini 'kırık' sanmış olabilir. PRO moda geçince hepsi erişilebilir.
- DÜZELTİLEN: RateStructurePanel.js /admin/room-types (404) → /room-types (200). Error Sentinel'deki 5 eski hata kaydı (loadRev, measureElasticity, showTgt, toLocaleString, React child obj — hepsi 15 Ağustos, kodda çoktan düzeltilmiş, taramada tekrarlanmadı) resolved işaretlendi.

## Güncelleme (2026-08-18, DERİN TEST 4 GRUP — iter. 570-573 TAMAMLANDI)
- Kullanıcının '%30 çalışmıyor' iddiası 4 gruplu derin testle (tüm butonlar/modallar/formlar) ÇÜRÜTÜLDÜ: iter 570 Ön Büro 35/35 OK; iter 571 CRM+Ops 0 broken; iter 572 Gelir+Kanal+Finans 71/77 OK 0 broken; iter 573 Rapor+POS+Etkinlik+Ayarlar+Admin+Portal 74/74 %100 OK. Tahmini gerçek sorun oranı <%3 (kozmetik).
- YAPILAN DÜZELTMELER: (1) 15+ dosyada <option> içi çoklu/karışık JSX expression'lar template literal'e çevrildi (platform instrumentation'ın span-in-option hydration hatası kökten çözüldü — KDS, BeachPos, TaxReportsV2, PmsConnectHub vb. doğrulandı HOLDS). (2) RateStructurePanel /admin/room-types 404 → /room-types. (3) MyTasks'a kişisel görev ekleme (POST/PUT /api/my-tasks/personal, my-tasks-new-input/add-btn, personal_tasks response alanı). (4) Branch seçimi localStorage 'active-property-id' persist (reload doğrulandı). (5) CampaignsPanel modal grid düzeni. (6) Error Sentinel'deki 5 eski kayıt resolved.
- YANLIŞ ALARMLAR (kendim doğruladım): rev-tab geçişleri çalışıyor (içerik boyutları farklı), branch persistence çalışıyor, GuestProfiles key uyarısı ve global duplicate-key uyarısı tekrarlanamadı (0 uyarı, tam yük + PRO + tüm section'lar açık). PRO toggle testid'leri zaten mevcut (nav-mode-pro/simple).
- BİLİNEN DÜŞÜK ÖNCELİK: testing agent'ın tek seferlik gördüğü duplicate-key uyarısı reprodüise edilemedi — kaynak panel belirsiz, UI kırılması yok.

## Güncelleme (2026-08-18, Sağlık Nöbetçisi + Basit Mod Rozeti — curl + UI doğrulandı)
- Sağlık Nöbetçisi: /app/backend/routes/platform_ext/health_sentinel.py — 29 temsili modül GET endpoint'i (HEALTH_ENDPOINTS, gerçek route'larla eşleştirildi); run_health_sentinel: 2xx/401/403/422=sağlıklı, 404/5xx/timeout=sorun; sonuç db.health_checks'e; sorun varsa günde 1 dedupe'lu 'error' bildirimi (link error-sentinel). health_sentinel_loop 24 saatte bir (server.py startup). Routes: GET /api/health-sentinel/status, POST /run. UI: ErrorSentinelPanel'e yeşil kart (health-sentinel-card, Şimdi Tara butonu, son koşu özeti, fail listesi). Doğrulandı: 29/29 OK, 1.4sn.
- Basit Mod Rozeti: App.js simple-mode-hint görsel rozete çevrildi — '🔓 250+ modül için PRO'ya geçin' (indigo gradient kart), tıklayınca PRO moda geçiyor (doğrulandı).
- Kullanıcı sorusu yanıtlandı: Revenue tarafında kırık modül YOK (iter 572: 71/77 OK, 0 broken).

## Güncelleme (2026-08-19, Cloudbeds Fiyat Basma API — Whitechapel Grand)
- do_push_rates(db,pid,days,rate_id,source): oda tipi bazlı Cloudbeds putRate — her RMS oda tipi cfg.rate_map ile CB rateID'ye eşlenir (eşlenmeyen atlanır; hiç map yoksa ilk oda → varsayılan rateID); fiyat: oda-özel override → property override → base_rate fallback. Canlıda sertifikasyon şartı korunur; cb_push_log'a source (manual/auto) yazılır.
- Yeni routes: GET/POST /api/cloudbeds/rate-map/{pid} (oda listesi + eşleme kaydet), POST /api/cloudbeds/auto-push/{pid} (enabled+days). cloudbeds_autopush_loop 24 saatte bir auto_push=true property'leri basar, sonucu bildirime yazar (Cloudbeds Robotu, günde 1 dedupe).
- UI (CloudbedsPanel): '🗺 Oda Tipi → Cloudbeds rateID Eşleme' kartı (cb-ratemap-section, satır inputları, Eşlemeyi Kaydet), '🌙 Otomatik gece push' toggle + gün (cb-autopush-toggle/days), push sonucunda oda bazlı özet (cb-push-room-*). Panel: Revenue & rates → Cloudbeds Bağlantısı (cloudbeds-live-btn).
- Whitechapel Grand test: 5 oda tipi listelendi, 2 eşleme kaydedildi (CB-DBL-01/CB-KING-01), MOCK push 2 oda × 14 gün £125, auto_push AÇIK. CANLI push için kullanıcının Cloudbeds API key girmesi gerekiyor (Account → Apps & Marketplace → API Credentials).

## Güncelleme (2026-08-19, Bağlantı Kataloğu + Push Önizleme + Müsaitlik Push — curl + UI e2e doğrulandı)
- Bağlantı Kataloğu: /app/backend/routes/distribution/connector_catalog.py — 28 konnektör (PMS: Cloudbeds/Mews/Apaleo/eviivo/Elektraweb/Booking Factory/Opera/protel/Guestline/Little Hotelier/Sirvoy/Beds24/Clock/Hotelogix/RMS Cloud; CM: SiteMinder/HotelRunner/D-EDGE/RateGain/Cubilis/WuBook/Octorate/Hotel-Spider; OTA Direct yakında: Booking.com/Expedia/Airbnb/Agoda; Direkt: Kendi Otel Sitesi→booking-engine-v2). GET /api/connector-catalog/{pid} (durumlar: connected/ready/available/requested/coming_soon, cloudbeds dinamik), POST /{pid}/request (db.connector_requests). UI: ConnectorCatalogPanel.js (connector-catalog view, Revenue&rates menüsü, kategori filtreleri, API tipi rozetleri, Bağlan→panel nav, Talep Et). lazyPanels+DashboardViews kayıtlı.
- Push Önizleme: GET /api/cloudbeds/push-preview/{pid}?days → tarih×oda tipi fiyat+müsaitlik tablosu (göndermez, build_push_preview). UI: '👁 Önizle & Gönder' (cb-preview-btn) → modal (cb-preview-modal, tablo, Vazgeç/Onayla ve Gönder). Doğrulandı: 14 satır, £/oda gösterimi, onay→push.
- Müsaitlik Push: _availability(total_rooms − aktif bookings); do_push_rates(include_availability) → canlıda putRoomBlocks'a ikinci payload, MOCK'ta cb_push_log kind=availability_push. push-from-rms body {include_availability}, auto-push cfg push_availability. UI: '🛏 Müsaitliği de gönder' toggle (cb-avail-toggle). Doğrulandı: 10 gün fiyat + 10 gün müsaitlik MOCK. _build_rate_blocks base_price fallback eklendi.
- NOT: Cloudbeds canlı müsaitlik endpoint'i putRoomBlocks (Nexla doc referansı); kesin doğrulama kullanıcı API key'i gelince yapılacak.

## Güncelleme (2026-08-19, Talep Sıralaması + Stop-Sell + Mews Önizlemeli Push — curl + UI doğrulandı)
- Talep Sıralaması: GET /api/connector-catalog/requests/summary/all (aggregate oy sayısı, sıralı); ConnectorCatalogPanel'de '🗳 Talep Sıralaması' kartı (catalog-request-ranking, #sıra + oy). Doğrulandı: Booking Factory 1 oy.
- Stop-Sell: cloudbeds availability payload'ında roomsAvailable<=0 olan günlere stopSell:true; response'ta stop_sell_days. Doğrulandı: suite total_rooms=0 senaryosunda 3 gün stopSell:true (test sonrası total_rooms=2 restore edildi, geçici rate_map eşlemesi kaldırıldı).
- Mews Önizlemeli Push: GET /api/pms-connect/{provider}/push-preview/{pid}?days (eşleme çarpanlı tarih×oda tablosu, TÜM sağlayıcılar için çalışır: mews/apaleo/siteminder/eviivo/elektraweb); PmsConnectHub'da '👁 Önizle & Gönder' butonu + modal (pms-preview-btn/modal/confirm). Doğrulandı: Mews 14 satır tablo → Onayla → push.
- Cloudbeds API key HÂLÂ kullanıcıdan gelmedi — canlı push/müsaitlik/stop-sell testi bekliyor.

## Güncelleme (2026-08-19, Tesis Provizyonu — TÜM otellere uygulandı + yeni hesap otomasyonu)
- /app/backend/routes/platform_ext/provisioning.py: provision_property(db,pid,name) idempotent seed — plan=full/modules_enabled=all, örnek oda tipi (yoksa), comp_trigger + occupancy_rules + cloudbeds_config + template_settings varsayılanları, hoş geldin bildirimi. Routes: GET /api/provisioning/status, POST /api/provisioning/apply-all (admin).
- UYGULANDI: 13/13 aktif otel plan=full oldu (apply-all koştu). auth_routes.py POST /properties artık her YENİ oteli otomatik provizyonlar (doğrulandı: test oteli 7 öğeyle açıldı, sonra temizlendi).
- Gelecek müşteri otelleri: hesap açıldığında 280+ modülün tamamı + varsayılan konfigürasyonlarla hazır başlar.

## Güncelleme (2026-08-19, P0 PAKETİ — Mews/Cloudbeds gap kapama, iter 574: 30/30 geçti)
- GAP ANALİZİ: /app/memory/GAP_ANALYSIS_MEWS_CLOUDBEDS.md (P0/P1/P2 + güçlü yönler). Kullanıcı TÜM P0'ları onayladı.
- STRIPE ÖDEMELERİ: sandbox provizyonlandı (acct_1TxnuLE62dFDeRxE, keyler backend/.env'de STRIPE_SECRET_KEY vb.). POST /api/payments/checkout (dinamik tutar, pay-by-link, price_data), payment_transactions koleksiyonu, /api/stripe/webhook (imza doğrulamalı), GET /api/payments/tx-log/{pid}. Eski finance_ext/payments.py status handler'ı raw stripe SDK'ya çevrildi (StripeObject metadata .to_dict() fix). NOT: /api/payments/status + /transactions eski finance_ext handler'larında (p0_pack duplicate'leri kaldırıldı).
- PUBLIC API v1: POST/GET /api/public-keys/{pid} (hbx_ key, maskeli liste, kullanım sayacı); X-API-Key auth ile GET /api/public/v1/{bookings,rates,guests} + POST /public/v1/bookings (booking.created webhook emit). Bilinen sınırlar: pagination/rate-limit yok (P1 backlog).
- GİDEN WEBHOOKS: db.webhook_subscriptions + emit_webhook() (teslimat logu webhook_deliveries); events: booking.created, payment.completed, rate.updated, *.
- SÜPER ADMİN: GET /api/super-admin/tenants (kullanım sayaçlarıyla), POST /{pid}/suspend.
- VERİ GÖÇÜ: GET /api/migration/template/{kind}, POST /api/migration/import/{pid}/{kind} (bookings/guests/room_types, CSV, tarih validasyonu fromisoformat + co>ci, hata satır raporu, migration_log).
- Test: iter 574 30/30 pytest + route çakışması/tarih validasyonu düzeltmeleri sonrası curl doğrulaması. UI henüz YOK (backend-first) — panel entegrasyonu sonraki adım.

## Güncelleme (2026-08-19, Platform Yönetimi + Onboarding + Plan + Sağlık Skoru — UI e2e doğrulandı)
- Backend (p0_pack.py ek): GET /api/onboarding/{pid} (5 adım: oda/fiyat/kanal/ödeme/API, score%), GET /api/super-admin/health-scores (tenant başına % + eksik listesi, skora göre sıralı), POST /api/super-admin/tenants/{pid}/plan (basic|pro|full, modules_enabled günceller).
- UI: PlatformAdminPanel.js — 'super-admin' view (Settings & Admin menüsü, admin-only, testId super-admin-btn). Kartlar: müşteri otelleri (sağlık skoru barı %40'lar doğrulandı, plan select, askıya al), 💳 Ödeme Linki Üret (gerçek Stripe checkout URL üretti, tx listesi), 🔑 API anahtarı üret/listele (hbx_ tam key bir kez gösterilir), 📦 CSV import (kind seçici), 📖 API Dokümantasyonu (7 endpoint + auth açıklaması).
- Onboarding: mevcut OnboardingBanner TodayHub'a bağlandı (kurulum eksikse görünür, onResume→onboarding view); mevcut OnboardingWizard view'ı zaten vardı. Yeni /api/onboarding/{pid} endpoint'i skoru veriyor.
- Rezervasyona ödeme linki: panel üzerinden booking_id ile link üretimi çalışıyor (rezervasyon detayına gömme sonraki adım). Cloudbeds API key HÂLÂ gelmedi.

## Güncelleme (2026-08-19, RMS RAKIP GAP + RMS-ONLY PAKET + Plan Kilitleri + Rezervasyon İçi Ödeme — iter 575: backend 23/23, frontend %95)
- GAP ANALİZİ: /app/memory/GAP_ANALYSIS_RMS_COMPETITORS.md — FLYR, Duetto, IDeaS, RoomPriceGenie, PriceLabs mimarileri + parite tablosu. Sonuç: analitik çekirdek tam; eksik ürünleştirme katmanı kapatıldı.
- RMS PLANI: plan seti artık basic|rms|pro|full (p0_pack.py PLAN_MODULES, süper admin plan selector'da rms var). GET /api/super-admin/tenants artık "plans" haritasını da döner (route fix).
- PLAN KİLİTLERİ (sidebar): /app/frontend/src/navigation/planGate.js (isModuleAllowed/requiredPlanFor; FULL_ONLY: public-api/dev-portal/webhooks/ai-agents/marketplace/lock-sdk; rms planı: Overview+Revenue&rates+Reports+Settings; basic: core items). App.js: kilitli öğe soluk + amber kilit ikonu (testid locked-*), tıklayınca toast + PlanUpsellModal.js (plan karşılaştırma, MEVCUT rozeti, admin için "Planı Yükselt"→super-admin). all-properties görünümü ve full plan kilitsiz.
- RMS HIZLI KURULUM SİHİRBAZI: /app/frontend/src/components/dashboard/RmsSetupWizard.js — menü: Revenue & rates > "RMS Hızlı Kurulum (30 dk)" (rms-setup-btn, core). 6 adım: baz oda+fiyat+oda tipi offsetleri (%/£, canlı önizleme) → min/max guardrail → compset → veri kaynağı (pms/csv/manual) → mod (autopilot/copilot/manual + günde 1-24× push slider) → Go-Live checklist (7 kontrol, %skor, %80+ hazır) + öneri üretme + Co-Pilot onay kuyruğu (tekli/toplu onay-red).
- BACKEND: /app/backend/routes/revenue_ext/rms_onboarding.py — /api/rms/setup/{pid} (GET + rooms/guardrails/compset/data-source/mode POST'ları), /api/rms/golive/{pid}, /api/rms/copilot/generate/{pid} (14 gün doluluk-bazlı öneri; autopilot=rate_overrides'a otomatik, copilot=pending kuyruk), /api/rms/copilot/queue/{pid} + /decide (approve→rate_overrides upsert). db.rms_setup, db.copilot_queue koleksiyonları. mode kaydı pricing_autopilot'u senkronlar.
- REZERVASYON İÇİ ÖDEME: BookingTimeline.js folio sekmesi, balance_due>0 iken "Stripe Ödeme Linki" kutusu (stripe-paylink-box): tek tık link üret (/api/payments/checkout, gerçek checkout.stripe.com URL) + panoya kopyala (clipboard hatası yakalanıyor) + E-posta Gönder (/api/payments/email-link → MOCK, db.email_outbox; Resend anahtarı gelince canlı) + Yeni Link.
- Test: iter_575 — backend 23/23 pytest, frontend akışlar doğrulandı (kilitler, modal, sihirbaz, paylink). Düzeltmeler: clipboard try/catch, tenants "plans" alanı, compset payload dedup. Tüm oteller full planda bırakıldı (plan değişimi Süper Admin'den).
- BEKLEYEN: Resend API anahtarı (e-posta canlı gönderim), Cloudbeds/Mews canlı API anahtarları, haftalık skor e-postası (P1), self-signup landing (RMS-only müşteri kendi hesabını açsın — backlog).

## Güncelleme (2026-08-19, CM RAKIP GAP + CM-ONLY PAKET + FİYAT BEKÇİLERİ + SELF-SIGNUP — iter 576: backend 22/22, frontend %100)
- GAP ANALİZİ: /app/memory/GAP_ANALYSIS_CM_COMPETITORS.md — Cloudbeds, Mews, eviivo, The Booking Factory mimarileri + parite tablosu. Dağıtım çekirdeği paritede; ürünleştirme katmanı bu pakette kapatıldı.
- CM PLANI: plan seti basic|rms|cm|pro|full. planGate.js CM_SECTIONS (Overview, Reservations, Direct Booking, Channels & Distribution, Settings). PlatformAdminPanel + upsell modal + p0_pack PLAN_MODULES "cm" içerir.
- CM HIZLI KURULUM: /app/frontend/src/components/dashboard/CmSetupWizard.js (menü: Channels & Distribution > "CM Hızlı Kurulum", cm-setup). 5 adım: kanal seçimi (8 kanallık katalog: Booking/Expedia/Airbnb/Agoda/GHA/Tripadvisor/Vrbo/HRS) → oda eşleme matrisi (external ID) → ARI kapsamı Full/Custom + push frekansı + stop-sell toggle → test push (MOCK, push_history + last_sync) → Go-Live (6 kontrol + eşleme kapsamı %). Backend: /app/backend/routes/distribution/cm_onboarding.py (/api/cm/*), db.cm_setup.
- FİYAT BEKÇİLERİ: /app/backend/routes/revenue_ext/price_guards.py (/api/price-guards/{pid} GET, /poba, /surge, /run) + workers.py price_guard_loop (saatlik). POBA: doluluk eşiği aşan tarihlere kalan envantere zam (guardrail clamp, set_by=poba_guard). Surge: 24s pickup eşiği → notification alarm + koruma fiyatı (alert_only|alert_and_cap, set_by=surge_guard). UI: PriceGuardsPanel.js (Revenue & rates > "Fiyat Bekçileri", price-guards) — toggle'lar, eşik inputları, Şimdi Çalıştır, bekçi günlüğü. db.price_guards, db.price_guard_log.
- SELF-SIGNUP: POST /api/auth/signup (public; validasyon, IP başına 10dk/3 kayıt limiti, duplicate email 400) → otel provizyonu (seçilen planla) + manager kullanıcı (property_ids=[pid]) + cookie auto-login. TENANT İZOLASYONU: GET /api/properties non-admin + property_ids → sadece kendi oteli. Frontend: /signup rotası (SignupPage.js: 3 plan kartı RMS/CM/PRO, form), landing header "RMS ile Başla" butonu (landing-signup-btn). Kayıt sonrası localStorage mhb_post_signup_view → App.js effect ilgili sihirbaza (rms-setup|cm-setup) düşürür. Yeni kullanıcı legal onay kapısından (PendingLegalDocsGate, 6 doküman) geçer — beklenen davranış.
- Test: iter_576 — backend 22/22, frontend %100 (signup e2e, CM wizard, bekçiler, tenant izolasyonu UI'da doğrulandı). Test tenantları silindi, default plan=full ve overrides temiz. Bilinen minör: bir sayfada "div inside p" hydration console uyarısı (LOW, önceden var olabilir).
- BEKLEYEN: Resend anahtarı, canlı OTA/PMS anahtarları, iCal import/export (P1), Express Connect benzeri listing açma (P1), haftalık skor e-postası.

## Güncelleme (2026-08-19, LISTING AÇMA + KARŞILAMA E-POSTASI + DENEME SAYACI — iter 577: backend 12/12, frontend %100)
- KANAL LISTING AÇMA (Express Connect): cm_onboarding.py sonuna /api/cm/listings/{pid} (GET otomatik mock ilerleme: in_review→live 60sn), POST (taslak, description zorunlu 400/kanal 422), /{lid}/submit (draft→in_review, tekrar 400). UI: ChannelListingPanel.js (Channels & Distribution > "Kanal Listing Açma", channel-listings) — form + durum stepper'lı kartlar (Taslak→Gönderildi→İncelemede→Canlı) + MOCK rozeti. db.channel_listings.
- KARŞILAMA E-POSTASI: /app/backend/routes/platform_ext/mailer.py — send_email (RESEND_API_KEY yoksa/placeholder re_123456789 ise MOCK, email_outbox denetim izi her durumda) + welcome_email_html (plana göre RMS/CM kurulum adımları, TR HTML). Signup'ta otomatik gönderilir (hata yutulur, kayıt asla bozulmaz). resend==2.27.0 kuruldu. Anahtar gelince .env RESEND_API_KEY güncelle → canlı.
- DENEME SAYACI: signup'ta trial_started_at + trial_ends_at (14 gün) property'ye yazılır. App.js sidebar (şube seçicinin altı): trial-badge — "Deneme: X gün kaldı" (cyan), ≤3 gün amber, süresi dolunca kırmızı "Süre doldu — Yükseltin"; tıklayınca PlanUpsellModal. Tek otelli kullanıcıda şube otomatik seçilir (fetchProperties).
- TENANT İZOLASYONU SIKILAŞTIRMA: /api/data-quality/summary/all artık property_ids scoping yapar (sağlık şeridi sızıntısı kapandı); tüm /api/cm/* endpoint'lerine _check_scope (403) eklendi ve doğrulandı. PendingLegalDocsGate hydration uyarısı (p>div) düzeltildi.
- Test: iter_577 backend 12/12 + frontend %100; ek self-test: scoped kullanıcı → cm/setup/default 403 OK. Test tenantları temizlendi, default plan=full.
- BEKLEYEN: Resend gerçek anahtarı, canlı OTA/PMS anahtarları, iCal import/export (P1), haftalık skor e-postası (P1).

## Güncelleme (2026-08-19, iCal SENKRONU — self-test: backend curl e2e + UI screenshot PASS)
- iCal SENKRONU: /app/backend/routes/distribution/ical_sync.py (/api/ical/*). DIŞA: GET /api/ical/export/{pid}.ics?token=...&room_type_id= (public, token'lı; rezervasyonlardan VEVENT feed; yanlış token 403; rotate-token var). İÇE: kaynak ekle (oda + kanal adı + URL, gerçek HTTP fetch + regex VEVENT parser DATE/DATE-TIME) → dolu tarihler oos_blocks olarak yazılır (reason "iCal: Airbnb — ...", ical_source_id ile; re-sync'te kaynak blokları yenilenir; kaynak silinince blokları da silinir). GERÇEK entegrasyon — mock değil. workers.py ical_sync_loop 4 saatte bir. Tenant scope 403 korumalı.
- UI: IcalSyncPanel.js (Channels & Distribution > "iCal Senkronu (Airbnb)", ical-sync) — export URL + oda tipi feed kopyalama çipleri, içe aktarma formu, kaynak listesi (durum/blok sayısı/son senkron/sil), "Şimdi Senkronla".
- Test: kendi export feed'imizle gerçek e2e (324 blok içe aktarıldı, hata/validasyon durumları OK), test kaynakları + blokları temizlendi. UI screenshot doğrulandı.

## Güncelleme (2026-08-19, TAKVİMDE iCAL ROZETİ — screenshot PASS)
- BookingTimeline.js oos blok render'ı: ical_source_id/created_by=ical_sync bloklar Airbnb kırmızısı (#FF385C) çizgili, Airbnb bélo SVG logosu (kanal adı airbnb içeriyorsa; değilse CalendarDays ikonu) + kanal etiketi (testid ical-block-{id}). Elle silinemez — tıklayınca "iCal Senkronu panelinden yönetilir" toast'ı. Normal OOS blokları gri çizgili kalır.

## Güncelleme (2026-08-19, ÇİFTE REZERVASYON ALARMI — e2e curl + UI screenshot PASS)
- ical_sync.py sync_ical_source: her senkron sonrası içe aktarılan blokları odanın aktif rezervasyonlarıyla çakışma taraması. Çakışmalar db.ical_conflicts'e key (source:booking:aralık) ile dedupe upsert; kaybolanlar "resolved". Bildirim patlaması koruması: senkron başına ilk 3 yeni çakışma tekil bildirim + kalanı tek özet bildirimi (db.notifications, type ical_conflict). Kaynak silinince çakışmaları da silinir. Sync sonucu conflicts sayısı döner.
- UI: IcalSyncPanel — kırmızı "Çifte Rezervasyon Alarmı — N çakışma" kartı (ical-conflicts-card; oda, kanal blok aralığı × rezervasyon misafir/tarih satırları) + senkron/kaynak ekleme toast'larında çakışma uyarısı.
- Test: kendi feed'imizle 526 unique çakışma üretildi → bildirim 4'te sınırlandı (3+özet), GET 50 döndü, UI kartı doğrulandı, tüm test verisi temizlendi.

## Güncelleme (2026-08-19, ÇAKIŞMA ÇÖZÜM SİHİRBAZI — e2e curl + UI screenshot PASS)
- ical_sync.py: GET /api/ical/{pid}/conflicts/{cid}/options (tarih aralığında boş odalar: rezervasyon + oos blok kontrolü, aynı tip önce) ve POST /resolve — action move_booking (hedef oda müsaitlik yeniden kontrolü 409, booking.room_id taşınır + move_reason, o rezervasyonun tüm açık çakışmaları resolved) | action close_channel (ilgili oos bloğu silinir, çakışma channel_closed, db.ical_ignored_events'e eklenir → sonraki senkron o bloğu yeniden İTHAL ETMEZ; kullanıcıya "kanal tarafında da iptal edin" mesajı).
- UI: IcalSyncPanel çakışma satırlarında "Odaya Taşı" (boş oda dropdown + Taşımayı Onayla; boş oda yoksa uyarı) ve "Kanalı Kapat" butonları (conflict-move-btn-{id}, conflict-close-btn-{id}, conflict-room-select-{id}).
- Test: iki yol da curl ile e2e doğrulandı (taşıma: booking taşındı+resolved; kapama: blok silindi+ignored kaydı), UI resolver ekran görüntüsüyle onaylandı, tüm test verisi temizlendi/geri alındı.

## Güncelleme (2026-08-19, CLOUDBEDS/MEWS MENÜ KARŞILAŞTIRMA RAPORU)
- Kullanıcının paylaştığı cloudbeds.com + mews.com menü ekran görüntüleri madde madde kod tabanıyla denetlendi → /app/memory/GAP_ANALYSIS_CLOUDBEDS_MEWS_MENUS_2026.md
- SONUÇ: ~30 menü kaleminin %80'i tam VAR, %13 kısmi, gerçek eksikler: P1 Web Sitesi Oluşturucu (Cloudbeds Websites), P1 Stripe Terminal (Mews Terminals), P2 reklam entegrasyonu, P2 AI marka çatısı, P2 tesis tipi/role preset'leri, P2 esnek finansman, P2 marketplace ölçeği.
- Üstün alanlar: RMS derinliği, Grup Satış OS, iCal çakışma çözümü, self-signup+deneme, Health Sentinel, profit-first pricing, ABS.

## MVP BACKLOG KAYDI (2026-08-19, Cloudbeds/Mews karşılaştırmasından)
- P1-1 Web Sitesi Oluşturucu (Cloudbeds Websites paritesi) → UYGULANIYOR
- P1-2 Stripe Terminal fiziksel ödeme (Mews Terminals paritesi) → UYGULANIYOR (test modunda simüle cihaz)
- P2-1 AI Copilot çatısı (Signals AI paritesi) → UYGULANIYOR
- P2-2 Tesis Tipi Preset'leri (hostel/apart/extended-stay/şehir/resort) → UYGULANIYOR
- P2 (bekleyen): Google/Meta reklam API, YouLend tarzı finansman, marketplace ölçeği

## Güncelleme (2026-08-19, P1/P2 GAP PAKETİ TAMAMLANDI — iter 578: backend 13/13, frontend %95→bulgu fixlendi)
- WEB SİTESİ OLUŞTURUCU: routes/pms/site_builder.py (/api/site-builder/{pid} GET/POST + /public/site/{pid} public; şablon classic|modern|boutique, 422 validasyon, amenities tip toleransı) + SiteBuilderPanel.js (Direct Booking > "Web Sitesi Oluşturucu": şablon kartları, içerik formu, Taslak/Yayınla/Yayından Kaldır) + HotelSitePage.js public /site/{pid} rotası (3 tema, hero + odalar + olanaklar + iletişim + /book/{pid} CTA). db.hotel_sites. default oteli 'modern' temayla YAYINDA bırakıldı.
- STRIPE TERMINAL: routes/finance_ext/terminal.py (/api/terminal/{pid}: readers list/register [simulated-wpe test cihazı GERÇEK Stripe test-mode], charge [PI card_present + process_payment_intent + TestHelpers.present → succeeded], payments log; Location otomatik) + TerminalPanel.js (Finance > "Ödeme Terminali"). Gerçek cihaz için ekrandaki kayıt kodu girilir. db.terminal_settings, db.terminal_payments.
- AI COPILOT ÇATISI: routes/ai/ai_copilot.py (/api/ai-copilot/summary/{pid}: 6 metrik) + AiCopilotPanel.js (Overview > "AI Copilot", dashboard'ın hemen altı: ReveniQ AI Copilot markalı gradient başlık + canlı istatistik + 8 AI modül kartı, tıklayınca navigate). 
- TESİS TİPİ PRESET'LERİ: routes/platform_ext/presets.py (/api/property-presets GET katalog + /apply/{pid}: 5 preset [city_hotel/resort/hostel/apart/extended_stay], oda tipleri sadece boşsa oluşturulur, rms_setup varsayılanları + property_type set) + PresetsPanel.js (Settings & Admin > "Tesis Tipi Şablonları").
- Fix: menuSections duplicate import (Globe/CreditCard) derleme hatası; HotelSitePage amenities array/string toleransı + backend coercion (iter578 bulgusu).
- Test: iter_578 backend 13/13, frontend regression dahil geçti; amenities fix'i curl ile doğrulandı.
- BEKLEYEN P2: Google/Meta reklam API, YouLend finansman, marketplace ölçeği, deneme bitiş e-postası, skor e-postası (Resend anahtarı).

## Güncelleme (2026-08-19, SİTE FOTOĞRAFLARI + TERMİNAL→FOLYO + COPILOT GÖREV AKIŞI — self-test e2e PASS)
- SİTE FOTOĞRAFLARI (Emergent Object Storage): site_builder.py — POST /api/site-builder/{pid}/photos?kind=cover|gallery (8MB, jpg/png/webp/gif, storage init/put/get + 404'te force re-init), GET /api/site-builder/photo/{id} (public servis, cache 1h), DELETE soft-delete (db.site_photos is_deleted). Kapak yüklenince eski kapak otomatik pasif. Public site payload'una photos eklendi. UI: SiteBuilderPanel kapak+galeri yükleme/silme; HotelSitePage hero'da kapak bg (karartma degrade) + Galeri bölümü. Demo: AI üretimi otel kapak fotoğrafı /site/default'ta yayında.
- TERMİNAL→FOLYO: terminal.py charge — booking_id verilip PI succeeded olursa db.folio_items'a payment (method card, reference=PI id) otomatik yazılır + booking.payment_status guest_services ile aynı mantıkla güncellenir (paid/partial/pending). Response'ta folio_posted; UI'da "Folyoya otomatik işlendi" toast'ı. Test edildi ve test kaydı geri alındı.
- COPILOT GÖREV AKIŞI: ai_copilot.py GET /api/ai-copilot/today/{pid} — önceliklendirilmiş görevler: bekleyen co-pilot önerileri (high), açık iCal çakışmaları (high), bugün gelen ödemesi eksik rezervasyonlar (medium), okunmamış surge/trend uyarıları (medium), guardrail tanımsız / site yayında değil / bekçiler kapalı (low), hiçbiri yoksa yeşil "acil aksiyon yok". UI: AiCopilotPanel "📋 Bugün ne yapmalıyım?" kartı — severity noktalı, tıklayınca ilgili modüle navigate (copilot-task-{i}).
- Test: 3 akış da curl+screenshot ile e2e doğrulandı (foto upload/serve 200, folio item + partial status, today list + UI). Test verileri temizlendi.

## Güncelleme (2026-08-19, SİTE ALAN ADI — e2e curl + UI screenshot PASS)
- site_builder.py: POST /api/site-builder/{pid}/domain (format regex 400, başka tesise bağlıysa 409, expected_target=uygulama host'u, status pending + CNAME talimatı), POST /domain/verify (Google DNS-over-HTTPS ile GERÇEK CNAME/A sorgusu → hedef eşleşirse verified), DELETE /domain, GET /public/resolve-domain?host= (sadece verified+published → property_id, yoksa 404).
- Frontend: SiteBuilderPanel "Özel Alan Adı" kartı (input + Kaydet + DNS Doğrula + Kaldır + durum rozeti + CNAME talimatı). App.js: uygulama host'u dışındaki hostlarda (localhost/emergentagent.com hariç) CustomDomainSite gate — resolve-domain eşleşirse otelin sitesi render edilir, yoksa landing.
- Test: kayıt/validasyon/409/verify(pending—gerçek DNS yok)/resolve 404→verified simülasyonuyla 200 curl e2e; UI kartı + gerçek DoH doğrulama toast'ı screenshot ile onaylandı. Test alan adı temizlendi. NOT: gerçek özel alan adının çalışması için kullanıcının DNS CNAME kaydı + (deploy ortamında) alan adının ingress'e yönlendirilmesi gerekir.

## Güncelleme (2026-08-19, SİTE SEO AYARLARI — e2e PASS)
- Builder: SiteBuilderPanel "SEO Ayarları" kartı — seo_title (60 kr sayaç), seo_description (160 kr sayaç) + gerçekçi Google Önizlemesi (yeşil URL, mavi başlık, gri açıklama; doğrulanmış özel alan adı da gösterilir). Backend content coercion listesine seo_* alanları eklendi.
- Public site (HotelSitePage): runtime SEO enjeksiyonu — document.title, meta description/keywords, OG title/desc/type/image (kapak fotoğrafı), JSON-LD schema.org Hotel (ad, açıklama, adres, telefon, görsel). Screenshot + evaluate ile doğrulandı (title/meta/jsonld hepsi sayfada).
- NOT: SPA olduğu için SSR yok; Google JS render'lı sayfaları indeksler, ancak tam SEO için ileride prerender/SSR düşünülebilir (backlog P2).

## Güncelleme (2026-08-19, SİTE ZİYARET İSTATİSTİĞİ — e2e PASS)
- Backend (site_builder.py): POST /api/site-builder/public/track (public; event view|cta_click 422 validasyonlu, visitor_id, db.site_visits) + GET /api/site-builder/{pid}/stats?days=30 (görüntülenme, distinct tekil ziyaretçi, cta tıkları, source=website_widget rezervasyonlar, tık oranı + dönüşüm % [100 cap], son 14 gün günlük seri).
- Frontend: HotelSitePage mount'ta view track (localStorage mhb_visitor_id) + tüm rezervasyon CTA'larında cta_click track. SiteBuilderPanel "Ziyaret İstatistikleri" kartı: 5 metrik karosu + günlük mini bar grafik (site-stats-card, site-stat-*).
- Test: curl (track/validasyon/stats) + gerçek tarayıcı akışı (view+CTA→/book yönlendirme→sayaç artışı) screenshot ile doğrulandı.

## Güncelleme (2026-08-19, PRO ŞABLON BAĞLANTISI + KAYNAK KIRILIMI — e2e PASS)
- PRO ŞABLONLAR LİNKLENDİ: Site Builder'a mod toggle eklendi — "Basit Tema (3)" vs "Profesyonel Şablonlar (10)" (templates/templateConfig.js: 4× Booking.com, 2× Airbnb, 2× Expedia, 2× Hotels.com tarzı; BookingEngine /book?property=X&template=Y). Panelde 10 kart (renk şeridi + platform etiketi + Önizle↗). mode=pro + engine_template kaydedilir; public /site/{pid} pro modda view'i TRACK edip seçili profesyonel şablona redirect eder. Doğrulandı: /site/default → /book?property=default&template=booking-classic. Demo simple moda geri alındı (kapak/SEO sayfası görünür kalsın diye) — kullanıcı toggle ile geçebilir.
- KAYNAK KIRILIMI: track endpoint'i referrer sınıflandırır (google/social[fb,ig,x,tiktok,yt,linkedin]/direct/other, db.site_visits.source). Stats response'una "sources" eklendi; panelde renkli çipler (Google mavi, Sosyal pembe, Direkt yeşil + adet ve %). Curl + UI doğrulandı (Direkt 3 %60, Google 1, Sosyal 1).

## Güncelleme (2026-08-19, OTOMATİK YÜKSELTME E-POSTASI — e2e curl + UI screenshot PASS)
- routes/platform_ext/trial_emails.py: run_trial_email_check(db) — self-signup + trial_ends_at olan tesisler; 2 aşama: t3 (bitişe ≤3 gün, "X gün kaldı ⏳" hatırlatması) ve expired (bitişte "yükseltme linkiniz hazır 🚀"). İdempotent: properties.trial_emails_sent ($addToSet). Sahip e-postası: signup_source=self_signup kullanıcı, yoksa manager fallback. Her gönderimde admin'e bildirim (Deneme Takip Robotu). E-posta CTA linki: {BASE_URL}/?upgrade=1&property={pid}.
- trial_email_loop(db, 3600) server.py startup'ta kayıtlı (saatlik). Manuel tetik: POST /api/trial-emails/run (admin/manager) + GET /api/trial-emails/outbox (son 50, html'siz).
- Frontend (App.js): ?upgrade=1 URL paramı girişten sonra PlanUpsellModal'i otomatik açar, paramlar history.replaceState ile temizlenir.
- NOT: require_roles varargs alır (liste DEĞİL) — require_roles("admin","manager").
- Test: seed edilen t3+expired sahte tesislerle loop gönderdi (outbox mocked ×2, doğru konu/link), ikinci run skipped=idempotent, modal screenshot PASS. Test verisi temizlendi. Resend anahtarı mock (re_123456789 placeholder) — gerçek gönderim için kullanıcı anahtarı bekleniyor.

## Güncelleme (2026-08-19, DENEME DÖNÜŞÜM PANELİ + RESEND ANAHTAR UI + PMS CANLI DOĞRULAMA — e2e curl + UI screenshot PASS)
- trial_emails.py genişletildi: GET /api/trial-conversion/summary (metrikler: toplam/aktif/süresi dolan/dönüşen/dönüşüm %, satır bazında kalan gün + gönderilen e-posta rozetleri + sahip e-postası) | POST /trial-conversion/{pid}/convert {plan} (plan+modules_enabled+converted_at/converted_plan) | POST /trial-conversion/{pid}/send-upgrade-email (manuel anında yükseltme maili).
- RESEND UI'DAN ANAHTAR: GET/POST/DELETE /api/email-settings (re_ format 422, Resend /domains ile CANLI doğrulama — 400/401/403 → "anahtar geçersiz" 400; ulaşılamazsa unverified kaydeder) + POST /email-settings/test (test maili). Anahtar db.platform_settings{id:email}'e yazılır ve os.environ'a uygulanır (RESEND_API_KEY/SENDER_EMAIL/RESEND_FROM/FROM_EMAIL) → tüm e-posta modülleri restartsız canlıya geçer. Startup'ta trial_email_loop load_email_settings(db) ile db anahtarını env'e yükler.
- UI: TrialConversionPanel.js — PlatformAdminPanel (super-admin) en üstünde: Resend kartı (CANLI/MOCK rozeti, maskeli anahtar, test maili) + deneme panosu (5 metrik karosu, satır aksiyonları: Yükseltme Maili / plan seç / Dönüştü ✓). testids: email-settings-card, trial-conversion-card, trial-row-{pid}, resend-save-btn...
- PMS CANLI BAĞLANTI: anahtar giriş UI'ları zaten mevcuttu (PmsConnectHub: Mews client/access token formu + Bağlantıyı Test Et + "Mews Demo'ya Bağlan"; CloudbedsPanel: API key formu). Mews demo-connect curl ile CANLI doğrulandı (gerçek Mews demo API: enterprise + rate_id döndü). Kullanıcı kendi anahtarlarını bu ekranlardan girebilir.
- Test: seed edilen deneme oteliyle summary→send-upgrade(mocked)→convert(pro, oran %16.7) akışı; email-settings 422/geçersiz anahtar 400/delete; super-admin screenshot (iki kart görünür). Test verisi temizlendi. Resend hâlâ MOCK — kullanıcı gerçek anahtarını UI'daki karttan girecek.

## Güncelleme (2026-08-19, DÖNÜŞÜM HUNİSİ + DENEME SALT-OKUNUR KİLİDİ — e2e curl + UI screenshot PASS)
- HUNİ: /api/trial-conversion/summary'ye funnel (Kayıt → Kuruluma Başladı [rms_setup|room_types var] → Hatırlatma E-postası Aldı → Süre Doldu → Dönüştü, adım arası "−N kayıp") + weekly (son 8 hafta kohortu: kayıt haftasına göre signups/conversions) eklendi. UI: TrialConversionPanel'de yatay huni barları (trial-funnel, funnel-step-{i}) + haftalık çift çubuk grafik (trial-weekly).
- SALT-OKUNUR KİLİT: server.py http middleware trial_readonly_guard — POST/PUT/PATCH/DELETE + /api yolunda, path segmentleri veya query param değerleri süresi dolmuş+dönüşmemiş self-signup pid'iyle eşleşirse 403 {"code":"trial_expired"}. Whitelist: /api/auth, /api/platform/auth, /api/trial-*, /api/email-settings, /api/payments, /api/public, /api/webhook, /api/site-builder/public. Pid seti trial_emails.get_expired_trial_pids (30 sn cache); convert endpoint'i invalidate_trial_cache() ile kilidi ANINDA açar. Frontend: App.js axios response interceptor — 403 trial_expired → PlanUpsellModal otomatik açılır.
- Test: süresi dolmuş sahte tesiste yazma 403, okuma 200, whitelist 200, normal tesise yazma 200, convert sonrası aynı yazma 200 (anında açıldı); huni/kohort curl + super-admin screenshot PASS. Test verisi temizlendi.
- ATLANDI: Cloudbeds canlı sertifikasyon — kullanıcı API anahtarını henüz paylaşmadı (UI'daki CloudbedsPanel'den girilebilir).

## Güncelleme (2026-08-19, SALT-OKUNUR BANNER + CLOUDBEDS MOCK SERTİFİKASYON — e2e PASS)
- BANNER: App.js <main> başında sticky kırmızı şerit (trial-readonly-banner) — properties içinde signup_source=self_signup + trial_ends_at geçmiş + converted_at yok olan (aktif şube veya All Branches) tesis varsa görünür; "Planı Yükselt →" (trial-readonly-upgrade-btn) PlanUpsellModal'i açar. Screenshot ile doğrulandı (banner + modal), test tesisi temizlendi.
- CLOUDBEDS SERTİFİKASYON (MOCK e2e): POST /api/cloudbeds/certify/default → passed:true mode:mocked (test push MOCK + geri okuma doğrulaması eşleşti), push-preview ve push-from-rms mock akışları çalışıyor. Kullanıcı API anahtarını CloudbedsPanel'den girince aynı akış CANLI modda tekrarlanacak (anahtar hâlâ bekleniyor).

## Güncelleme (2026-08-19, DENEME UZATMA BUTONU — e2e PASS)
- POST /api/trial-conversion/{pid}/extend (admin): trial_ends_at = max(şimdi, mevcut bitiş) + 7 gün; trial_emails_sent'ten t3/expired $pull edilir (hatırlatmalar yeni döneme göre yeniden kurulur); invalidate_trial_cache() ile salt-okunur kilit ANINDA açılır.
- UI: TrialConversionPanel satırlarında "+7 gün" butonu (trial-extend-{pid}), toast'ta yeni bitiş tarihi.
- Test: süresi dolmuş tesiste yazma 403 → extend → yazma 200 + status active + days_left 7 + emails_sent [] (curl); UI buton + toast screenshot PASS. Test verisi temizlendi.
- BACKLOG'DAN KALDIRILDI: Cloudbeds Canlı Sertifikasyon — kullanıcının Cloudbeds hesabı/anahtarı yok (mock akış hazır ve test edildi, anahtar gelirse CloudbedsPanel'den girilir).

## Güncelleme (2026-08-19, MİMARİ TEMİZLİK + WORKER SHUTDOWN STABİLİZASYONU — e2e PASS)
- TEST ARTIK TEMİZLİĞİ: 8 test tesisi silindi (3× TEST_ITER486 uuid, trial-test-otel-263ce8, mock-mail-otel-d23868, 3× iter577*) — 667 koleksiyonun tamamında property_id eşleşmeli 1.191 doküman + 11 rastgele-sufiksli test kullanıcısı (test_receptionist/housekeeper/manager/perm/del_[hex8]) temizlendi. Kalan: 10 gerçek tesis, 5 kullanıcı (admin, ali@hotel.com, sarah@hotel.test, testrecep/testhk@hotelbox.com). UI şube çubuğu doğrulandı (Veri Nöbetçisi 90.8'e çıktı).
- WORKER SHUTDOWN FIX: server.py'de 49 `asyncio.create_task(...)` çağrısı `_spawn(...)` kayıt fonksiyonuna çevrildi (_bg_tasks listesi); shutdown handler'ı tüm arka plan görevlerini cancel + gather ile kapatıyor. Hot reload artık takılmıyor (touch ile test edildi: WatchFiles → clean shutdown → startup complete, login 200 ~20 sn). NOT: loop'lardaki `except Exception` CancelledError'ı yutmaz (py3.11 BaseException).
- Regresyon: 6 kritik endpoint 200, frontend screenshot temiz.
- KALAN TEKNİK BORÇ (P1/P2): market_robot.py 9.024 satır bölünmeli; NeighborhoodScanPanel/BookingTimeline 2.6k+ satır; SPA prerender (SEO) backlog'da.

## Güncelleme (2026-08-19, MARKET ROBOT PAKET BÖLME + DEMO VERİ MODU + MORNING-BRIEF KPI FİXİ — e2e PASS)
- MARKET ROBOT BÖLME (faz 1): routes/revenue_ext/market_robot.py (9.025 satır) → market_robot/ paketi: __init__.py (dış API aynı: create_market_robot_router + 3 fleet worker + _internal_close_gap re-export), state.py (SCRAPE_LOCKS vb. paylaşılan kilitler), gap_logic.py (_internal_close_gap), geo_utils.py (OSM/Google Places/kart sayacı/fiyat istatistiği), fleet_workers.py (fleet_geo_validate/vision_enrich/competitor_price_scan), core.py (router factory 8.374 satır + başa BÖLÜM HARİTASI yorumu). GLOBAL_SCAN_SEM core'da kaldı (global mutasyon). Eksik importlar AST analiziyle bulundu (re, Tuple). rms_pro.py'nin _internal_close_gap importu __init__ üzerinden çalışıyor. Regresyon: 13 market-robot endpoint'i 200 (config/supply/competitors/performance/demand-dashboard/market-pulse/ranking/action-feed/weekly-summary/geo-supply/logs/occupancy-pickup/competitive-config). DOĞRU PATH: /api/revenue/market-robot/{pid}/... (market-robot/{pid} DEĞİL). FAZ 2 (backlog): core.py'nin bölüm bazlı register_* fonksiyonlarına ayrılması.
- DEMO VERİ MODU: TodayHub'a kart eklendi — panel boşsa (occ+gelir+inhouse 0) gradient "Demo Verisi Doldur →" kartı (POST /api/demo-seeder/seed/{pid}?count=25), doluysa yeşil "Demo Veri Modu aktif — N rezervasyon" şeridi + "Demo Verisini Temizle" (POST /clear). refreshKey ile brief/tier1 sayfa yenilenmeden tazelenir. testids: demo-mode-card, demo-seed-btn, demo-mode-active-strip, demo-clear-btn. Eski 153 bayat demo kaydı temizlendi; default'ta 25 taze demo rezervasyon YAYINDA (kullanıcı tek tıkla silebilir).
- KÖK NEDEN FİXİ: /api/morning-brief hiç occupancy_pct/revenue/adr/revpar döndürmüyordu → dashboard KPI'ları hep 0 görünüyordu. competitor_parity.py morning_brief'e eklendi: total_rooms (rooms yoksa room_types.total_rooms toplamı), in-house rezervasyonların gecelik gelir payı, no_shows, currency (tesisten). Doğrulandı: occ %83.3, gelir CHF489, ADR 97.77, RevPAR 81.48 + UI screenshot (tüm KPI kutuları dolu).

## Güncelleme (2026-08-19, MARKET ROBOT FAZ-2 + DEMO TANITIM TURU — e2e PASS)
- FAZ-2 BÖLME TAMAMLANDI: core.py'deki 8.336 satırlık fabrika, AST+tokenize tabanlı üreteçle 10 bölüm modülüne ayrıldı (sec_scan_engine 795, sec_geo_competitive 708, sec_supply_dashboards 948, sec_performance 629, sec_competitors 1005, sec_fleet_ai 871, sec_vision_gap 1287, sec_auto_helpers 472, sec_scanner_metrics 913, sec_pulse_loop 703). Her modül register(router, db, require_roles, resend, S) sunar; bölümler arası çağrılar S (SimpleNamespace) üzerinden (ör. S._do_scan, S.scanner, S._build_weekly_summary — tokenize NAME-token rewrite ile, string/f-string'lere dokunulmadan). core.py artık 38 satırlık ince fabrika (kayıt sırası korunur). GLOBAL_SCAN_SEM sec_pulse_loop modül globali (global bildirimi orada). router.auto_scan_loop attr'ı korunmuş (server startup getattr'ı çalışıyor).
- Regresyon: import OK, 89 route aynen, 25 GET endpoint 200 + close-gap POST (sec_vision_gap→gap_logic çapraz çağrı) 200 + scanner/status + auto-heal/config + room-count 200. DOĞRU PATH'LER: auto-heal config = /competitors/auto-heal/config, oda sayısı = /room-count.
- DEMO TANITIM TURU: DemoTour.js — 5 adımlı spotlight tur (demo şeridi → KPI satırı → Takvim → AI Copilot → Şube seçici), karartma + ring vurgusu + İleri/Geri/Geç/Bitir + nokta ilerleme. Demo verisi doldurulunca otomatik açılır (localStorage mhb_demo_tour_done ile tek sefer), şeritteki "🧭 Tanıtım Turu" butonuyla tekrar izlenir. TodayHub'a today-kpi-row testid eklendi. Tur uçtan uca tarayıcıda doğrulandı (5 adım + bitir + kapanış).
- NOT: Market robot POST/scan uçları (gerçek scraping tetikleyenler) canlı çalıştırılmadı; GET yüzeyi ve çapraz-bölüm çağrıları doğrulandı.

## Güncelleme (2026-08-19, DEMO SENARYO ÇEŞİTLERİ + TAM REGRESYON TURU — iter_579 PASS)
- DEMO SENARYOLARI: demo_seeder.py SCENARIOS dict — balanced(25, ±%12 fiyat), high_season(45, x1.15-1.45 fiyat, yakın tarihler, %3 iptal), low_occupancy(8, x0.75-0.95, geniş dağılım, %15 iptal), group_heavy(30, %60'ı 4 grup adına [TechSummit/düğün/acente/takım], rooms 2-4, channel='group', is_group:true). POST /api/demo-seeder/seed/{pid}?scenario=X (geçersiz→422, count override edilebilir). UI: TodayHub demo kartında senaryo dropdown'ı (demo-scenario-select, 4 seçenek emoji'li).
- TAM REGRESYON (iter_579): backend 24/24 PASS — login, bookings CRUD, market-robot refactor 8 uç + close-gap, cloudbeds status+certify, pms-connect, Stripe checkout + tx-log + terminal, trial-conversion (funnel/weekly dahil), email-settings, morning-brief KPI'ları, 3 senaryo sayıları birebir. Frontend: login, demo şeridi + 5 adımlı tur (next/finish), KPI'lar dolu (%50 doluluk CHF311), süper admin kartları — hepsi PASS. Tek not: boş-şube demo kartı city-rooms'ta render olmadı çünkü şube boş değil (beklenen davranış; aynı akış bu oturumda default'ta e2e doğrulanmıştı). Test dosyası: /app/backend/tests/test_regression_579.py (kendi verisini temizliyor).

## Güncelleme (2026-08-20, SENARYO KARŞILAŞTIRMA + DEPLOY HAZIRLIK KONTROLÜ — e2e PASS)
- SENARYO KARŞILAŞTIRMA: POST /api/demo-seeder/compare/{pid}?a=X&b=Y — DB'ye yazmadan bellek-içi simülasyon (deterministik seed: property+scenario), 30 günlük daily_occ_pct + daily_rev serileri + total_rev/avg_occ_pct/adr; oda kapasitesi rooms count veya room_types.total_rooms toplamı; 422 validasyon. UI: ScenarioComparePanel.js modalı (demo şeridindeki "⚖️ Senaryo Karşılaştır" butonu) — a/b dropdown, 3 metrik karosu + ▲/▼ fark rozetleri, günlük gelir eşli bar grafiği (fix: gün sarmalayıcıya h-full şart) + doluluk çizgi SVG. testids: scenario-compare-btn/-modal/-run/-result, scenario-a/b-select. Curl + UI screenshot doğrulandı (Yoğun Sezon CHF28.434 vs Düşük Doluluk CHF1.613).
- DEPLOY HAZIRLIK: deployment_agent statik analizi → STATUS: PASS. Hardcoded secret/URL yok, env kullanımı doğru, seed'ler idempotent, destructive startup yok, supervisor/CORS/package.json geçerli. Uygulama Emergent deploy'una HAZIR.

## Güncelleme (2026-08-20, SENARYO UYGULA (RMS'E AKTAR) + YAYINA ALMA REHBERİ — e2e PASS)
- SENARYO UYGULA: POST /api/demo-seeder/apply-scenario/{pid} {scenario} → 30 gün × oda tipi başına fiyat ÖNERİSİ üretir (suggested = base × mult_mid × (0.95 + occ%/100 × 0.25), aynı deterministik simülasyon), db.scenario_rate_suggestions'a pending batch yazar (fiyatlara dokunmaz), avg_change_pct + preview döner. POST .../confirm {batch_id} → rate_overrides'a yazar (set_by: scenario-simulator, reason: '🏆 X senaryosu simülasyonundan onaylandı'), batch applied olur, ikinci onay 404.
- UI: ScenarioComparePanel'de '🏆 Kazanan' bandı (yüksek total_rev) → 'Kazananı RMS'e Aktar →' → öneri özeti (N öneri · gün · oda · ort değişim %) → 'Onayla ve Fiyatlara Uygula ✓' / Vazgeç. testids: scenario-apply-btn/-preview, scenario-confirm-btn/-cancel. Curl (60 öneri → 60 override → çift onay 404) + UI e2e doğrulandı; test override'ları geri alındı (default fiyatları orijinal).
- YAYINA ALMA: deploy hazırlığı PASS (önceki oturum); support_agent'tan Türkçe deploy + custom domain rehberi kullanıcıya iletildi (Deploy Now, 50 kredi ilk + 50/ay, redeploy/rollback ücretsiz; domain: Link domain → CNAME/Entri, 5-15 dk yayılım). Deploy işlemi KULLANICI tarafından Deploy butonuyla yapılacak.

## Güncelleme (2026-08-20, ÖNERİ GEÇMİŞİ + GERİ ALMA + TAKVİM 🏆 ROZETİ — e2e PASS)
- ÖNERİ GEÇMİŞİ: confirm artık her fiyatın öncekini kaydediyor (batch.prev_rates: prev_rate/prev_set_by/prev_reason; yoksa null) + applied_by. GET /api/demo-seeder/apply-scenario/{pid}/history (aggregate $size ile item_count, son 20 batch). POST .../revert {batch_id}: prev null ise scenario-simulator override'ını siler, doluysa eski değere/set_by'a döndürür; status=reverted + reverted_by/at; çift revert 404. Doğrulama: 1086 override → apply 60 → revert → 1086 (birebir geri).
- UI: ScenarioComparePanel altında '📜 Öneri Geçmişi' — senaryo, N fiyat, kim onayladı/geri aldı + tarih, durum rozeti (UYGULANDI/GERİ ALINDI/BEKLİYOR), uygulananlar için '↩ Geri Al' butonu (UI'dan test edildi, toast '60 fiyat geri alındı'). testids: scenario-history, scenario-history-row-{id}, scenario-revert-{id}.
- TAKVİM ROZETİ: rate-calendar endpoint'ine override_source (set_by) eklendi (revenue.py); RateCalendarEditable'da override_source==='scenario-simulator' olan günlerde fiyat önünde 🏆 (scenario-badge-{date}). UI doğrulandı: Revenue management → Rate Calendar'da 12 günde 🏆 £210/£226/£234 görünüyor. NOT: RevenuePanel iç sekmesine gitmek için sidebar 'Revenue management' (revenue-btn) → 'Rate Calendar' butonu (sidebar'daki 'Calendar' Booking Calendar'dır, karıştırma).
- Test batch'leri geri alındı; default fiyatları orijinal (scenario override 0).
- NOT: WatchFiles hot-reload bu dev uygulamada bazen yeni worker'ı başlatamıyor — çözüm: sudo supervisorctl restart backend (güvenilir).

## Güncelleme (2026-08-20, ROZET DETAY BALONU + FİNAL DEPLOY KONTROLÜ — e2e PASS)
- ROZET BALONU: confirm artık rate_overrides'a scenario + approved_by yazıyor; rate-calendar day'e override_scenario/override_by/override_at eklendi (revenue.py). RateCalendarEditable'da 🏆 hover balonu (group-hover, stone-900 balon): senaryo adı emoji'li + '✓ X onayladı' + tarih. testid: scenario-tooltip-{date}. UI hover doğrulandı ('🔥 Yoğun Sezon senaryosundan / ✓ admin@hotelbox.com onayladı / 20.08.2026 09:14'). Test batch geri alındı (senaryo override 0).
- FİNAL DEPLOY KONTROLÜ: deployment_agent tekrar PASS (tüm yeni dosyalar dahil). Deploy işlemi kullanıcının Deploy butonuna kalmış durumda — kod tarafı hazır.

## Güncelleme (2026-08-20, SİSTEM SAĞLIĞI SAYFASI — e2e PASS)
- BACKEND: routes/platform_ext/system_health.py — bellek-içi metrik deposu (REQS deque 5000, ERRORS deque 50, path normalize: uuid/24hex/sayı → {id}); server.py'de health_metrics_mw middleware'i tüm /api isteklerini kaydeder (kendisi hariç). GET /api/system-health/status (admin/manager): status healthy/degraded/unhealthy (5xx oranı ≥5 veya DB ping yok → unhealthy; ≥1 veya ping>250ms veya p95>3s → degraded), uptime, son 1 saat istek/avg/p95, 4xx/5xx, DB ping, en yavaş 8 uç (count/avg/max/errors), son 15 hata.
- FRONTEND: SystemHealthPanel.js — 30 sn auto-refresh; durum banner'ı, 6 metrik karosu, 🐢 En Yavaş Uçlar, ⚠️ Son Hatalar. Menü: system-health (admin-only, core:true — ÖNEMLİ: BASIT modda core:true olmayan öğeler App.js:578'de filtrelenir, ilk denemede bu yüzden görünmedi). lazyPanels + DashboardViews'a bağlandı. testids: system-health-btn/-page, health-status-banner, health-slowest, health-recent-errors.
- Test: curl (404 üretip son hatalarda görüldü, metrikler doğru) + UI screenshot (146 istek, p95 417.9ms, yavaş uçlar gerçek, 401 hataları listede). Deploy sonrası izleme hazır.
- RESEND: kullanıcı anahtarı Süper Admin'deki karttan KENDİSİ girecek (tekrar sorma; kart + canlı doğrulama zaten hazır).

## Güncelleme (2026-08-24, KAYIP NEDENİ ANKETİ — e2e PASS)
- ANKET AKIŞI: trial_emails.py yeni 'survey' aşaması — bitişten 3+ gün sonra, dönüşmemiş otele tek soruluk e-posta (5 tık-butonu: price/features/setup/competitor/no_time = CHURN_REASONS). Idempotent (trial_emails_sent 'survey'), converted olanlara artık hiçbir aşama gitmez. db.churn_surveys {id=token, property_id, email, sent_at, reason, answered_at}.
- PUBLIC YANIT: GET /api/public/churn-survey/{token}?reason=X — auth'suz, HTML teşekkür sayfası; ilk yanıt kilitlenir (ikinci tık üzerine YAZMAZ), geçersiz token 404, yanıtta admin'e bildirim.
- PANEL: trial-conversion summary'ye churn{sent,answered,reasons[]} + satırlara churn_reason eklendi. TrialConversionPanel: huni yanında 3. kart '💔 Kayıp Nedenleri' (yanıt oranı + neden barları, testid trial-churn, churn-reason-{key}) + satırda ✉ ANKET rozeti ve 💔 neden chip'i (trial-churn-chip-{pid}).
- Test: seed (4 gün önce bitmiş) → run ile anket mock gönderildi → public tık reason=price → ikinci tık yazamadı → summary 1/1 + satır chip → panel screenshot PASS. Test verisi temizlendi.
- NOT: dış URL curl'leri ara sıra proxy hıçkırığı yapıyor — doğrulamada localhost:8001 güvenilir alternatif.

## Güncelleme (2026-08-24, GERİ KAZANMA TEKLİFİ + SAĞLIK UYARI BİLDİRİMİ — e2e PASS)
- WINBACK: churn-survey public endpoint'inde reason=price ise otomatik %20 indirim e-postası (winback_email_html, kod WINBACK20, link ?upgrade=1&promo=WINBACK20, kind=winback_offer) + admin bildirimi; churn_surveys.winback_sent ile idempotent. Summary satırlarına winback_sent, panelde 🎁 %20 TEKLİF chip'i (trial-winback-chip-{pid}). E2e doğrulandı (mock e-posta içinde kod+link, chip UI'da görünür).
- SAĞLIK UYARISI: system_health.py — compute_health(db) endpoint'ten ayrıldı; check_and_alert(db): unhealthy'ye GEÇİŞTE admin'lere bildirim (Sağlık Nöbetçisi, priority high, link system-health) + tüm admin'lere e-posta (kind=health_alert), 30 dk cooldown; healthy'ye dönüşte '🟢 normale döndü' bildirimi. health_alert_loop(db, 300) server startup'ta _spawn'lı. Test: %10 5xx enjeksiyonu → unhealthy + bildirim + e-posta; cooldown ikinci çağrıda bildirim üretmedi; temiz REQS → iyileşme bildirimi. Test verileri temizlendi.
- Yayına Al: kullanıcı aksiyonu (Deploy butonu) — kod hazır.

## Güncelleme (2026-08-24, WINBACK20 OTOMATİK İNDİRİM + HAFTALIK SAĞLIK ÖZETİ — e2e PASS)
- WINBACK20 CLAIM: POST /api/public/winback-claim {property_id, code} — yalnızca winback_sent=True teklifi olan self-signup tesis; properties'e promo_code/promo_pct:20/promo_until(+180g)/promo_claimed_at yazar, admin bildirimi; idempotent (already_claimed), yanlış kod 422, teklifsiz tesis 404. Frontend: App.js ?upgrade=1&promo=WINBACK20&property=X linkinde otomatik claim + toast ('İlk 6 ay %20 indiriminiz tanımlandı 🎁'). Summary satırlarına promo_active/promo_until; panelde 🎉 %20 İNDİRİM AKTİF chip'i (teklif chip'i pasife düşer).
- HAFTALIK ÖZET: system_health.py record_request artık DAY_AGG günlük toplayıcıyı da besler (uç başına count/sum/max/err, 300 uç limiti); health_alert_loop her 5 dk flush_daily ile db.health_daily'ye yazar (top 20 uç). send_weekly_digest: son 7 gün toplamları + en yavaş 5 uç tablosu, adminlere kind=health_digest e-posta, db.health_digest_log ile hafta bazında idempotent. weekly_digest_loop (saatlik, Pazartesi ≥06 UTC) startup'ta _spawn'lı. Manuel tetik: POST /api/system-health/send-weekly-digest (force). E2e: claim akışı + özet e-postası (konu, tablo, endpoint satırları) doğrulandı, test verisi temizlendi.
- NOT: E-postalar Resend anahtarı girilene dek MOCKED. Deploy kullanıcı aksiyonu.

## Güncelleme (2026-08-24, İNDİRİMLİ FATURALAMA GÖRÜNÜMÜ — e2e PASS)
- BACKEND (p0_pack.py): PLAN_PRICES {basic:49, rms:99, cm:99, pro:149, full:199} £/ay; /super-admin/health-scores artık her tesise list_price, billed_price (WINBACK20 aktifse %20 düşülmüş), promo_active/promo_pct/promo_until döner + mrr (askıya alınanlar hariç, indirimler düşülmüş toplam).
- FRONTEND (PlatformAdminPanel): yeni '💳 Faturalama' kartı — MRR banner'ı (pa-mrr), tesis satırlarında plan + fiyat; promo'lu otelde üstü çizili liste fiyatı → yeşil indirimli tutar + '🎉 %20 İNDİRİM · bitiş {tarih}' rozeti (pa-promo-{id}); askıdakilere '⛔ ASKIDA — faturalanmaz'. testids: pa-billing, pa-billed-{id}.
- Test: promo'lu sahte tesis PRO £149→£119.2, MRR £2.109,2 (curl + UI screenshot PASS). Test verisi temizlendi.

## Güncelleme (2026-08-24, MRR TREND GRAFİĞİ — e2e PASS)
- /super-admin/health-scores'a mrr_trend eklendi: son 6 ayın MRR'ı — tesis katılım tarihine (provisioned_at/trial_started_at/created_at) göre geriye dönük hesap, WINBACK20 indirimi claim ayından itibaren ve promo_until'e kadar düşülür, askıdakiler hariç.
- Faturalama kartında MRR yanında mini SVG çizgi grafik (6 nokta, ay etiketleri) + '▲/▼ £X son ay' delta rozeti. testids: pa-mrr-trend, pa-mrr-delta. Curl + UI screenshot PASS (tüm tesisler Ağustos 2026'da katıldığı için önceki aylar 0 — veri dürüst).
- Resend anahtarı girme + Deploy: KULLANICI aksiyonları (kart ve deploy hazır durumda).

## Güncelleme (2026-08-24, PLAN DEĞİŞİKLİK GEÇMİŞİ + GELİR HEDEFİ ÇUBUĞU — e2e PASS)
- PLAN GEÇMİŞİ: db.plan_changes {property_id, from_plan, to_plan, changed_by, changed_at, source}. Loglama: super-admin set_plan (source=super-admin) + trial-conversion convert (source=trial-conversion, from=önceki plan|trial). GET /api/super-admin/plan-history?property_id= (son 50). UI: Faturalama satırında '🕒 Geçmiş' toggle → indigo zaman çizelgesi (FROM → TO · kim · tarih · 'deneme dönüşümü' rozeti). testids: pa-history-btn-{id}, pa-history-{id}.
- GELİR HEDEFİ: POST /api/super-admin/mrr-target {target} (422 doğrulama) → db.platform_settings{id:billing}.mrr_target; health-scores yanıtına mrr_target eklendi. UI: MRR banner'ında 🎯 hedef çubuğu (yeşil ≥%100 🎉 / amber ≥%60 / kırmızı altı) + % rozeti + hedef girişi/Kaydet. testids: pa-mrr-target, pa-target-pct/-bar/-input/-save.
- Test: hedef 2500 kaydet → %80 amber çubuk UI'da; plan pro→full→pro değişimleri loglandı ve zaman çizelgesinde göründü; geçersiz hedef 422. aldgate-flats planı FULL olarak bırakıldı (orijinal değeri).

## Güncelleme (2026-06, fork sonrası — RevenueIQ Gap Analizi TAMAMLANDI)
- Kullanıcının yüklediği RevenueIQ-Motor-Ozellikleri.pptx (16 slayt) analiz edildi; tam rapor: /app/memory/GAP_ANALIZ_RevenueIQ.md
- Sonuç: ~17 kalem bizde zaten var, 9 gerçek eksik tespit edildi.
- YENİ BACKLOG (RevenueIQ gap):
  - P0: Son-Gün Merdiveni (D0-D1, 4 saatte ~%8 kademeli otomatik indirim, satışta yön dönüşü)
  - P0: Vitrin Doğrulaması (kendi Booking ilanını misafir gözüyle tarama, panele yazılan vs görünen kıyası)
  - P0: İkinci-Yazıcı Tespiti (kanala yabancı yazım alarmı)
  - P1: Misafir-Onaylı Zam Merdiveni (2. basamak = yeni rezervasyon şartı)
  - P1: Yıllık Plan D90-365 (şekil×seviye, plan sürüm arşivi, rakip sapma manşeti)
  - P1: Lease/Fencing yazım kilidi
  - P2: Kısmi yayın telafisi, günlük sabah karnesi e-postası, cold-start kardeş otel şekil ödünçü, asimetrik zaman kuralı, 2 yıl geçmiş otomatik import
- Önceki backlog devam: Canlı duman testi (URL bekleniyor), Gün Sonu Rapor E-postası (P1), Hedef Aşım Kutlaması (P2), Resend/Cloudbeds/Mews anahtarları (BLOCKED).

## Güncelleme (2026-06, iter 580 — RevenueIQ Gap P0+P1 MVP'leri TAMAMLANDI, 11/11 PASS)
- SON-GÜN MERDİVENİ: /api/lastday-ladder/{pid} (config/scan). D0-D1 boş odalar 4 saatte ~%8 kademeli iner, satışta yön döner, min_rate_floors tabanına saygılı (fail-closed: taban yoksa dokunmaz), pin saygısı. 30dk loop. Panel: lastday-ladder.
- VİTRİN DOĞRULAMASI: /api/storefront-verify/{pid} (scan/inject-drift/config). Yazılan + discount_layers → beklenen misafir fiyatı vs gözlenen; sapma bildirimli. MOCK mod (canlı scraper anahtarı bekleniyor). 6 saat loop. Panel: storefront-verify.
- İKİNCİ YAZICI ALARMI: /api/second-writer/{pid} (push/scan/simulate-foreign-write/repush/ack). Aktör imzalı channel_price_ledger + mock_channel_rates kıyası; yabancı yazım → high alarm + onarım (repush). Saatlik loop. Panel: second-writer.
- YILLIK PLAN D90-365: /api/annual-plan/{pid} (generate/versions/publish/latest). Şekil(730g, shrinkage)×seviye(30g medyan veya operatör çapası), fail-closed (<60 gece örneklem), sürüm arşivi, rakip sapma manşeti, yayın ayrı operatör eylemi (set_by annual-plan-vN). Panel: annual-plan.
- Test: iteration_580.json PASS (backend 11/11 pytest + frontend Playwright %100). Regresyon dosyası: /app/backend/tests/test_iter580_revenue_iq_gaps.py
- Kalan RevenueIQ gap backlog (P1/P2): Misafir-onaylı zam merdiveni, lease/fencing yazım kilidi, kısmi yayın telafisi, günlük sabah karnesi, cold-start kardeş otel şekil ödünçü, asimetrik zaman kuralı, 2 yıl geçmiş otomatik import.

## Güncelleme (2026-06, iter 581 — 4 yeni RevenueIQ gap özelliği TAMAMLANDI, 22/22 PASS)
- ZAM MERDİVENİ (misafir-onaylı): /api/ramp-ladder/{pid}. Kademe 1 talep kanıtı (doluluk eşiği); kademe 2+ YENİ REZERVASYON şartı (awaiting_guest_approval kilidi). Tavan korumalı, D2-D21, kira-çit ile yazar, set_by 'ramp-ladder'. Panel: ramp-ladder. NOT: test için occ_threshold=30 bırakıldı (varsayılan 70).
- YAZIM KİLİDİ (kira-çit): /api/write-lease/{pid} (list/test-acquire/force-release). rate_cell_leases; lastday+ramp merdivenleri yazmadan önce kira alır; manuel override ve yıllık plan yayını robot kiralarını iptal eder (operatör egemenliği). Panel: write-lease.
- SABAH KARNESİ: /api/morning-karne/{pid} (latest/send-now/history/config). 8 kontrollü A/B/C notu, her sabah 06:00 UTC sonrası admin+manager'lara e-posta (Resend MOCK → email_outbox). Panel: morning-karne.
- TAKVİM ROZETİ: RateCalendarEditable'da override_source lastday-ladder → 🪜, ramp-ladder → 📈 rozet + tooltip (ladder-badge-{date}). Room Type select'e data-testid + görünür değer eklendi.
- Test: iteration_581.json PASS (22/22 pytest: 11 regresyon + 11 yeni; frontend %95→UX düzeltmesi yapıldı). Regresyon dosyaları: tests/test_iter580_*.py + tests/test_iter581_*.py
- Kalan RevenueIQ gap backlog (P2): kısmi yayın telafisi, cold-start kardeş otel şekil ödünçü, asimetrik zaman kuralı, 2 yıl geçmiş otomatik import, ramp 'demand_faded' yön dönüşü (kademe geri alma).

## Güncelleme (2026-06, iter 582 — RevenueIQ gap turu 3 TAMAMLANDI, 23/23 PASS)
- EŞİK SIFIRLAMA: Zam merdiveni occ_threshold kalıcı olarak 70'e çekildi. Kök neden bulundu: iter581 pytest süiti eşiği 30'a düşürüp geri almıyordu → teste test_zz_restore_production_threshold eklendi (artık her koşuda 70'e döner).
- ZAM YÖN DÖNÜŞÜ: ramp_ladder.py — talep eşik altına inince kademe geri alınır (direction:'down', reason:'demand_faded_reversal', cadence+lease korumalı). Panelde ramp-stat-reversals kartı + ▼ satırlar. Doğrulandı: 4 gece 126→120 geri indi.
- KISMİ YAYIN TELAFİSİ: annual_plan publish — hücre bazlı doğrulama (floor_violation) + yazım hatasında yalnız o hücre eski haline döner; publish_report {applied, rejected[]} plana kaydedilir, panelde annual-publish-report bloğu (koşullu: red varsa görünür). Doğrulandı: 102 uygulandı / 174 tekil red.
- KARDEŞ OTEL ÖDÜNÇÜ: annual_plan generate — kendi örneklemi <60 gece ise mevsim şekli kardeş otellerin toplamından öğrenilir (shape_source:'sibling', siblings_used); o da yetmezse çapa + nötr şekil, hiçbiri yoksa fail-closed. Doğrulandı: sentetik kardeş otelle shape_source='sibling' (sonra temizlendi). Panelde şekil kaynağı etiketi.
- Test: iteration_582.json (frontend render PASS) + pytest 23/23. Bilinen not: backend hot-reload arka plan tarayıcı görevleri yüzünden bazen takılıyor → supervisorctl restart backend çözüyor.
- Kalan RevenueIQ gap backlog (P2): asimetrik zaman kuralı, 2 yıl geçmiş otomatik import.

## Güncelleme (2026-06, iter 583 — RevenueIQ gap listesi TAMAMEN KAPANDI + Canlı Duman Testi hazır)
- ASİMETRİK ZAMAN KURALI: Motor kuralı açıkça işlendi ve panellerde görünür (ladder/ramp GET → rules.asymmetric_time; skip detayına eklendi). "Zam için zaman kanıt değildir, indirim için kanıttır."
- 2 YIL GEÇMİŞ İÇE AKTARIMI: /api/history-import/{pid} (status/start/DELETE undo). D-731→D-31 (son 30 gün raporları kirletmemek için hariç), gerçekçi mevsimsel MOCK, deterministik. Auto-trigger: pms_connections status connected/live olunca 10dk döngü. default'a 8896 kayıt/701 gece aktarıldı → şekil örneklemi 47→725+, plan v16 shape_source:'own' çapasız üretildi. UI: AnnualPlanPanel'de history-import-card (geri al butonu var).
- CANLI DUMAN TESTİ: /api/live-smoke/run {base_url,email,password} → sağlık→login→rezervasyon→Stripe checkout→iptal (5 adım). Preview'a karşı PASS 5/5. Panel: live-smoke (menü: Canlı Duman Testi). Kullanıcı canlı URL verdiğinde panelden koşulacak.
- MERDİVEN HAFTALIK ÖZETİ: /api/morning-karne/{pid}/ladder-weekly + karneye 9. kalem 'Merdiven geliri (7g, tahmini)' + MorningKarnePanel'de ladder-weekly-card (kurtarılan/ek gelir/toplam).
- Test: iteration_583.json frontend %100 PASS, backend curl ile tam doğrulandı.
- RevenueIQ gap backlog: TAMAMI KAPANDI (9/9).

## Güncelleme (2026-06, iter 584 — 3 özellik TAMAMLANDI, frontend %100 + backend curl PASS)
- MRR HEDEF KUTLAMASI: /api/mrr-celebration (status/check/reset). Hedef (platform_settings billing.mrr_target) aşılınca ayda 1 kez admin bildirim + e-posta (MOCK). 6 saatlik loop. UI: PlatformAdminPanel hedef çubuğu altında pa-celebration-status + 'Şimdi kontrol et'. Test: tetiklendi+dedupe doğrulandı, sonra ay kaydı resetlendi (hedef £2500, MRR £1990 — gerçek aşımda otomatik gidecek).
- MERDİVEN TREND GRAFİĞİ: /api/morning-karne/{pid}/ladder-trend?days=14 → günlük kurtarılan/ek gelir/toplam. UI: MorningKarnePanel'de recharts 3 çizgili grafik (ladder-trend-chart).
- GÜN SONU RAPORU (EOD): /api/eod-report/{pid} (latest/history/send-now). night-audit close-day sonrası OTOMATİK e-posta kancası (immutable snapshot); kapanış yoksa canlı tahmin. UI: MorningKarnePanel'de eod-report-card + 'Bugünü Şimdi Gönder'. Kanca test edildi (2026-08-25 kapanışı → otomatik EOD, sonra gün geri açıldı).
- React key uyarısı düzeltildi (PlatformAdminPanel txs/keys map).
- CANLI DUMAN TESTİ: kullanıcı henüz canlı URL vermedi ('Devam et' dedi) — panel ve endpoint hazır, URL gelince koşulacak.
- Test: iteration_584.json frontend %100 PASS.

## Güncelleme (2026-06, iter 585 — 3 özellik TAMAMLANDI, frontend %100 + backend curl PASS)
- RESEND ANAHTARI UI: Mevcut /api/email-settings (trial_emails.py — key doğrulamalı) endpointlerine bağlı yeni kart MorningKarnePanel'e eklendi (email-settings-card: anahtar kaydet + test e-postası + MOCK/GERÇEK rozeti). mailer.send_email artık DB anahtarını (platform_settings 'email') env'e tercih ediyor. NOT: Kullanıcı henüz gerçek anahtar girmedi — MOCK devam.
- NO-SHOW TAHMİNİ: /api/noshow-risk/{pid}?day= — risk skoru (iletişim eksik +15/+15, ödeme yok +25, OTA +10, tek gece +10, geçmiş no-show +30, eski rezervasyon +5), high>=50. Günlük 14-18 UTC bildirimi (yarın için, dedupe'lu). Panel: noshow-risk (menü: No-Show Riski). Doğrulama: Sven Lee 55 HIGH.
- HAFTALIK YÖNETİCİ BÜLTENİ: /api/weekly-digest/{pid} (latest/history/send-now). Pazartesi >=07 UTC otomatik; gelir/doluluk/ADR/giriş/iptal/merdiven katkısı şık HTML e-posta. rate=0 fallback: total_price/nights (düzeltildi — gelir £3715). Kart: MorningKarnePanel weekly-digest-card.
- CANLI DUMAN TESTİ: Kullanıcı URL'yi hâlâ paylaşmadı — hazır bekliyor.
- Test: iteration_585.json frontend %100 PASS.
- Not (düşük öncelik, bakım): MorningKarnePanel 324 satır (5 kart) — ileride alt bileşenlere bölünebilir.

## Güncelleme (2026-06, iter 586 — 3 özellik TAMAMLANDI, frontend %100 + backend curl PASS)
- DEPOZİTO KURALI: /api/deposit-rule/{pid} (status/config/run). Skor >= min_score (50) + ödemesiz → otomatik %30 Stripe checkout depozito linki + misafire e-posta (MOCK) + dedupe. 6 saatlik loop (origin_url config'den). UI: NoShowRiskPanel'de deposit-rule-card (toggle AÇIK bırakıldı) + risk satırında 💳 rozeti. Test: Sven Lee GBP 51.08 gerçek Stripe URL.
- NO-SHOW TEYİT MESAJI: POST /api/noshow-risk/{pid}/confirm/{booking_id} {channel: email|sms}. E-posta mailer'dan (MOCK), SMS sms_outbox'a MOCK. noshow_confirmations ile satırda '✓ Teyit gönderildi' durumu. UI: Aksiyon sütunu butonları.
- BÜLTEN KARŞILAŞTIRMASI: weekly_digest build_digest artık önceki haftayı da hesaplar; deltas {revenue_pct, occupancy_pts, adr_pct, arrivals_diff} + HTML'de ▲/▼ okları + panel önizlemede renkli oklar (digest-delta-*).
- CANLI DUMAN TESTİ: Kullanıcı URL'yi hâlâ paylaşmadı — hazır bekliyor.
- Test: iteration_586.json frontend %100 PASS.

## Güncelleme (2026-06, iter 586+ — Depozito Ödendi Takibi + Risk Trendi TAMAMLANDI)
- DEPOZİTO ÖDENDİ TAKİBİ: mark_deposit_paid(db, session_id) — deposit_requests→paid, booking→{payment_status:deposit_paid, noshow_secured:true} + bildirim. İki tetik: (1) Stripe webhook /api/webhook/stripe içine kanca (payments.py), (2) fallback POST /api/deposit-rule/{pid}/check-payments (Stripe session sorgusu) + panelde 'Ödemeleri Kontrol Et' butonu. Simülasyonla doğrulandı (sonra geri alındı — gerçek ödeme yapılmadı).
- RİSK TRENDİ: noshow_risk_snapshots (günlük avg_score/high/medium) — loop'ta ve GET'te kaydedilir, trend endpoint bugün+yarını self-heal eder. GET /api/noshow-risk/{pid}/trend → 14 gün + weekly_avg. UI: risk-trend-card (recharts, 2 çizgi) + haftalık ortalama rozeti. Screenshot ile doğrulandı.
- Testler: backend curl + mark_deposit_paid simülasyonu + UI screenshot (panel/trend/buton hepsi render).
- CANLI DUMAN TESTİ: URL hâlâ bekleniyor.

## Güncelleme (2026-06, iter 586++ — Risk Modeli + Güvenceli Rozet + RSVP Takibi TAMAMLANDI)
- RİSK MODEL AYARI: risk_model_config {weights(7 faktör), thresholds(high/medium)}. GET/PUT/POST-reset /api/noshow-risk/{pid}/model. score_arrivals config'den okur. UI: risk-model-card (7 input + eşikler + kaydet/sıfırla). Test: unpaid 40 → Sven Lee 70 high, reset OK.
- GÜVENCELİ ROZETİ: arrivals endpoint'ine noshow_secured alanı eklendi (routes/pms/arrivals.py); ArrivalsCockpit misafir adının yanında 🛡️ (secured-badge-*). Depozito ödenince otomatik görünür.
- TEYİT YANIT TAKİBİ (RSVP): confirm e-postasında ✅ Geliyorum / ❌ Gelemiyorum butonları → PUBLIC GET /api/noshow-risk/rsvp/{token}?answer= (auth'suz HTML yanıt sayfası). 'Gelemiyorum' → high bildirim ('odayı satışa açın'). Panel satırında yanıt rozetleri (rsvp-*). Test: not_coming akışı uçtan uca doğrulandı (Sven Lee kaydı demo olarak not_coming durumunda bırakıldı).
- Testler: backend curl uçtan uca + UI screenshot (model kartı, rsvp rozeti, trend, depozito kartı render).
- CANLI DUMAN TESTİ: URL hâlâ bekleniyor.

## Güncelleme (2026-06 — Rakip Analizi 2: Duetto/IDeaS/Atomize/RoomPriceGenie/FLYR)
- Web araştırmasıyla 5 rakip tarandı; rapor: /app/memory/GAP_ANALIZ_RAKIPLER_2026.md
- YENİ BACKLOG (rakip gap): P0: Regret&Denial takibi, Olay-tetiklemeli anlık re-price, Toplantı alanı fiyatlaması (büyük faz). P1: Segment/kanal Open Pricing offsetleri, Grup Wish&Walk+onay akışı, Grup wash tahmini, RMS etki ölçer. P2: 730g tahmin, sosyal sentiment, rakip veri anomali düzeltme, kâr benchmark, işbirlikçi tahmin, mobil PWA.
- Bekleyen: Canlı duman testi URL'si + Resend anahtarı (kullanıcı girecek).

## Güncelleme (2026-06 — Duetto/IDeaS Gap Fazı 1: 4 özellik TAMAMLANDI)
- KAYIP TALEP → FİYAT MOTORU: lost_demand POST /{pid}/log artık fire_reprice tetikliyor (lost_demand_{reason} olayı). Duetto/IDeaS regret&denial paritesi.
- ANLIK RE-PRICE KÖPRÜSÜ: routes/revenue_ext/reprice_bridge.py — fire_reprice() ateşle-unut; booking create (POST /api/bookings) + status change (PUT /api/bookings/{id}/status: cancelled/no_show/confirmed) hook'ları. Merdiven taramaları (lastday+ramp) saniyeler içinde koşuyor (~70-160ms). GET /api/reprice-bridge/{pid}/events, POST .../trigger. Collection: reprice_events.
- SEGMENT FİYAT KATMANI: routes/revenue_ext/segment_group.py create_segment_pricing_router — GET/PUT /api/segment-pricing/{pid}. 4 varsayılan segment (direct 0, corporate -10, loyalty -5, ota +3), offset clamp ±50, baz fiyat rate_overrides/room_types'tan. Collection: segment_offsets.
- GRUP ONAY AKIŞI: create_group_approval_router — POST /api/group-approval/{pid}/quotes (wish>walk>0 validasyonu), approve zinciri revenue→sales→approved (sıra dışı 422), reject. Collection: group_quotes.
- UI: SegmentGroupPanel.js (view id: segment-group, menü: 'Segment fiyat & Grup onayı', Pro modda RMS bölümünde). Segment offset kartları + canlı fiyat, grup teklif formu + onay/red butonları, re-price olay çipleri.
- TEST: iteration_587.json — backend 13/13 pytest, frontend %100 (offset kaydet, tam onay zinciri, reprice çipleri, regresyon lost-demand/noshow-risk OK).
- KALAN BACKLOG (rakip gap): P0: Toplantı/etkinlik alanı fiyatlaması (Duetto OpenSpace). P1: Grup wash tahmini (BlockBuster), RMS etki ölçer (uplift raporu). P2: 730g tahmin, sosyal sentiment, rakip anomali düzeltme, kâr benchmark.

## Güncelleme (2026-06 — Fiyat Karışımı Analizi / Rate Mix TAMAMLANDI)
- Kullanıcı içgörüsü: oteller uzak tarihte yüksek fiyat deneyip satamıyor, ~%60 oda son-dakika taban fiyattan gidiyor → uzak tarihleri sweet-spot'tan (£90-100 bandı) açmak %30'a varan uplift sağlar.
- BACKEND: routes/revenue_ext/rate_mix.py — GET /api/rate-mix/{pid|all}?days=30..730: rezervasyonlar (iptal/no-show hariç) p05-p95 aralığında 3 eşit fiyat bandına ayrılır (floor/mid/high, room-night ağırlıklı), tier share/avg/lead, ADR, LMF (lead<=3g ort.), doluluk (90g), öneri motoru (_recommend: floor share>=45 → sweet=floor+0.35*(min(high_avg,p90)-floor), uplift=share*0.5*Δ/ADR). POST /{pid}/apply: oda tipi bazlı ölçekli yazım (en ucuz oda=verilen fiyat, base_price oranıyla ölçek), robot override'ları ezer (operatör egemen), insan('@'/boşluk)/event-intelligence/owner-override korunur, write-lease alır, fire_reprice tetikler. GET /{pid}/applies geçmiş. Collections: rate_mix_applies.
- FRONTEND: RateMixPanel.js (view: rate-mix, menü: 'Fiyat Karışımı (Rate Mix)', koyu tema — referans görsele uygun): otel satırları + stacked bar (kırmızı taban/bej orta/yeşil yüksek, % + £), ADR/LMF/doluluk başlıkta, öneri kartı + '£X Uygula' butonu (confirm + toast), gün seçici (90/180/365/730).
- TEST: iteration_588.json — backend 11/11, frontend %100. Regresyon dosyası: /app/backend/tests/test_rate_mix.py

## Güncelleme (2026-06 — Duetto/IDeaS Gap Fazı 2: 4 özellik TAMAMLANDI)
- TOPLANTI ALANI DİNAMİK FİYATLAMA (OpenSpace paritesi): routes/revenue_ext/space_rms.py — GET/POST /api/function-space/{pid}/dynamic-pricing[/apply]. Talep çarpanları: gün tipi (Sal-Per ×1.15), salon doluluğu ≥%50 ×1.2, otel doluluğu ≥%80 ×1.1, son 7 gün boş salon ×0.85, banket F&B marj kredisi ×0.92; clamp 0.7-1.5, ±%5 altı önerilmez. Apply: space_rate_overrides set_by='space-rms', insan yazımı ('@'/boşluk) korunur. UI: FunctionSpacePanel fs-dynamic-pricing-section (tablo + Tümünü Uygula).
- GRUP WASH TAHMİNİ (BlockBuster paritesi): los_wash_metrics.py compute_group_wash pace+hist harman modeli — pace=geçen süre/cutoff penceresi, projected_final=pace*kendi temposu+(1-pace)*tarihsel beklenti, wash_forecast_pct, confidence (yüksek/orta/düşük). BUG FIX: allocations 'quantity' anahtarı da sayılıyor (önceden sadece 'rooms'). UI: LosWashMetricsPanel'e Pace/Tahmini Final/Wash Tahmini kolonları. Demo blok: DEMO-KONGRE (default).
- RMS ETKİ ÖLÇER (RoomPriceGenie paritesi): routes/revenue_ext/rms_uplift.py — GET /api/rms-uplift/{pid}?months=4..24. Aylık RevPAR (check_in bazlı), robot_start (ai_pricing_decisions→robot rate_overrides fallback), baz=robot öncesi aylar ort. (yoksa ilk çeyrek 'baz*'), uplift_gbp=(revpar-baz)×oda×gün, kapasite=room_types toplamı. UI: RmsUpliftPanel (view: rms-uplift, menü: 'RMS Etki Ölçer (uplift)') — başlık metrikleri + aylık bar listesi + baz çizgisi.
- RATE MIX HAFTALIK TAKİP: rate_mix.py — rate_mix_snapshots (property×hafta upsert, 90g pencere), rate_mix_weekly_loop (6 saatte bir, hafta başına idempotent) server startup'ta spawn. GET /api/rate-mix/{pid}/weekly (12 hafta + son apply karşılaştırma verdict'i: taban payı düştü mü), POST /{pid}/weekly/snapshot manuel. UI: RateMixPanel 'Haftalık Takip' kartı (hafta çipleri + verdict).
- TEST: iteration_589.json — backend 13/13, RMS Uplift + Function Space UI görsel doğrulandı; weekly kart + wash kolonları ana ajan screenshot ile doğrulandı. Regresyon dosyası: /app/backend/tests/test_iter589_new_features.py
- KALAN BACKLOG: P2: 730g tahmin, sosyal sentiment, rakip veri anomali düzeltme, kâr benchmark, Segment onay yetkisi (departman RBAC).

## Güncelleme (2026-06 — Duetto/IDeaS Gap Fazı 3: son 4 P2 özellik TAMAMLANDI)
- SEGMENT ONAY YETKİSİ: segment_group.py — group_approval_config {property_id, steps:{revenue:[dept], sales:[dept]}}, GET/PUT /api/group-approval/{pid}/config (PUT admin-only). approve() departman kontrolü: admin bypass, aksi halde user.department allowed listede olmalı (403 Türkçe mesaj). Varsayılan: revenue→[revenue,management], sales→[sales,management]. UI: SegmentGroupPanel approval-config-card. Test kullanıcıları: revenue@hotelbox.com & sales@hotelbox.com / Test2026! (test_credentials.md'de).
- 730 GÜN TAHMİN (Atomize paritesi): forecast_730.py — GET /api/forecast-730/{pid}: son 730g tarihsel oda-geceden ay-of-year mevsimsellik endeksi, 24 ay ileri projeksiyon + OTB overlay + Türkçe strateji önerisi. UI: Forecast730Panel (view: forecast-730) 24 ay kartı (yeşil güçlü/kırmızı zayıf).
- RAKİP VERİ ANOMALİ DÜZELTME (IDeaS paritesi): comp_anomaly.py — kaynaklar: comp_rate_snapshots + market_competitors.prices. Robust z-skor (median/MAD×1.4826) + yüzde bandı (low_pct/high_pct). GET /api/comp-anomaly/{pid}, PUT /config (clamp z 1.5-6, lo 10-90, hi 120-500), POST /ignore, /ignore-all, GET /clean-median (diğer modüller için ayıklanmış medyan). Collections: comp_anomaly_config, comp_anomaly_ignores. UI: CompAnomalyPanel (view: comp-anomaly).
- KÂR BENCHMARK (HotStats tarzı): profit_benchmark.py — GET /api/profit-benchmark?months=1..12: tüm oteller GOPPAR ligi (GOP = gelir+POS − rn×CPOR − %22 sabit), rank/madalya, vs_portfolio_pct, badge, insight (lider farkı £). UI: ProfitBenchmarkPanel (view: profit-benchmark).
- TEST: iteration_590.json — backend 17/17, frontend 4/4 panel. Regresyon dosyası: /app/backend/tests/test_iter590_new_features.py
- RAKİP GAP BACKLOG'U TAMAMEN KAPANDI (13/13 özellik). Kalan genel backlog: sosyal sentiment fiyat girdisi (P2, opsiyonel), canlı PMS/Resend anahtarları (kullanıcı bekleniyor).

## Güncelleme (2026-06 — Faz 4: Sentiment + Anomali Entegrasyonu + Yönetici Özeti + Mobil PWA TAMAMLANDI)
- SOSYAL SENTİMENT FİYATI (Duetto paritesi): sentiment_pricing.py — GET /api/sentiment-pricing/{pid}: endeks 0-100 (rating ort %80 + 30g trend×20 + hacim bonusu), sinyal (≥80→+%4, ≥70→+%2, <45→−%2), risk yorumları. POST /apply: 30 güne oda tipi bazlı % ayar (insan/etkinlik korunur, lease, adj clamp ±5, fire_reprice 'sentiment_apply'). UI: SentimentPricingPanel (view: sentiment-pricing). Apply butonu sinyal nötr olunca gizlenir (doğru davranış).
- ANOMALİ MOTOR BAĞLANTISI: comp_anomaly.py helpers — robust_band_filter (saf) + clean_comp_entries (yoksayılan+bant). comp_radar.py medyanı artık ayıklanmış listeyle hesaplıyor (findings'e anomalies_excluded alanı), market_robot/sec_pulse_loop.py medyanı robust_band_filter'dan geçiyor.
- YÖNETİCİ HAFTALIK ÖZETİ: owner_weekly.py — build_owner_summary (compute_league + compute_uplift), HTML e-posta (GOPPAR ligi tablosu + uplift listesi), send_owner_summary (hafta bazlı idempotent, admin+manager alıcılar, mailer MOCK), owner_weekly_loop (Pazartesi ≥07:00) startup'ta spawn. Endpoints: GET /api/owner-weekly/preview, POST /send-now (admin), GET /history. REFACTOR: profit_benchmark.compute_league ve rms_uplift.compute_uplift modül-seviyesine çıkarıldı (router'lar sarmalıyor).
- MOBİL PWA TAMAMLAMASI: manifest+sw.js+PWAInstall zaten vardı. YENİ: MobileApprovalsPanel (view: mobile-approvals, 'Mobil Onay Merkezi') — bekleyen grup teklifleri + salon teklifleri tek dokunuş onay/red (büyük butonlar), bildirim izni butonu, haftalık özet 'Şimdi Gönder' + geçmiş. NotificationBridge.js (App.js'e mount): 60sn'de bir unread bildirimleri poll eder, high/revenue öncelikli olanları tarayıcı Notification olarak gösterir.
- TEST: iteration_591.json — backend 18/18, frontend 2/2 panel. Regresyon: profit-benchmark, rms-uplift, rate-mix yapıları korunmuş. Test dosyası: /app/backend/tests/test_iter591_new_features.py
- NOT (testing agent kod incelemesi, düşük öncelik backlog): sentiment set_by koruması '@'/boşluk sezgiseli yerine explicit allowlist; comp_radar delete_many yerine scan_id versiyonlama; mad=0 durumunda tespiti atla.
- DURUM: Rakip gap listesi + tüm ask edilen özellikler tamam. Bekleyen: Resend/Mews/Cloudbeds API anahtarları (kullanıcı), canlı URL duman testi (kullanıcı URL verecek).

## Güncelleme (2026-06 — Faz 5: Kalıcı Depolama + Sentiment AI + Sesli Onay TAMAMLANDI)
- KALICI DOSYA DEPOLAMA (Emergent Object Storage): /app/backend/object_storage.py (init/put/get, APP_NAME='hotelbox', EMERGENT_LLM_KEY + INTEGRATION_PROXY_URL). 10 upload noktası (booking_widget×2, guest_journey×2, housekeeping, maintenance×2, operations, staff_onboarding×2) artık yerel disk yerine save_upload ile buluta yazıyor (hata durumunda raise → 500). server.py StaticFiles mount kaldırıldı → GET /api/uploads/{path:path}: önce yerel disk, yoksa buluttan fetch_upload; path traversal korumalı ('..' reddi). 78 eski dosya buluta migrate edildi. Dosyalar canlı deploy'da kaybolmaz.
- SENTİMENT AI DERİNLİĞİ: sentiment_pricing.py POST /{pid}/analyze-themes — son 90g yorum metinleri LlmChat (gpt-5.2, Emergent key) ile 6 tema (temizlik/personel/konum/konfor/fiyat/kahvaltı) skorlanır + pricing_note; günlük cache (db.sentiment_themes); <3 metinli yorum → 422. UI: SentimentPricingPanel 'AI ile Analiz Et' butonu + tema çipleri + fiyat gücü notu.
- ONAY SESLİ BİLDİRİMİ: MobileApprovalsPanel — 45sn poll; bekleyen sayısı artınca WebAudio çift ton + navigator.vibrate + toast. Ses toggle (sound-toggle-btn) localStorage'da kalıcı.
- TEST: iteration_592.json — backend 13/13, frontend %100. Kod inceleme düzeltmeleri uygulandı: save_upload artık hata yükseltiyor (sahte 'uploaded' dönmüyor), upload_path '..' reddi.
- NOT: /api/uploads auth'suz servis (booking widget görselleri kamuya açık olmalı); hassas alt yollar (ids/) için auth kapısı backlog'a eklendi (P2).

## Güncelleme (2026-06 — Faz 6: Hassas Dosya Kilidi + Tema Trend Takibi TAMAMLANDI)
- HASSAS DOSYA KİLİDİ: server.py serve_upload — ids/, onboarding/, compliance/ önekleri JWT zorunlu (cookie access_token otomatik <img> ile gider; Bearer header ve ?auth=token da destekli). Token yok → 401, geçersiz → 401. rooms/ vb. kamuya açık kalır (booking widget). Doğrulandı: ids dosyası token'sız 401, token'la 200.
- TEMA TREND TAKİBİ: sentiment_pricing.py — run_theme_analysis modül fonksiyonu (delta hesabı: önceki analize göre; ≥10 puan düşüş → alerts + db.notifications high priority → NotificationBridge tarayıcı bildirimi). sentiment_theme_loop: haftalık otomatik analiz (ISO hafta idempotent, 12 saatte bir kontrol) startup'ta spawn. GET /{pid}/theme-trends: son 12 analiz, tema başına seri + delta + alert. UI: SentimentPricingPanel 'Tema Trend Takibi' kartı (bar grafik + ▼delta + ⚠️ ERKEN UYARI rozeti — temizlik 85→70 senaryosu görsel doğrulandı).
- BEKLEYEN (kullanıcı girdisi): Resend API anahtarı (e-postalar MOCK), canlı yayın URL (duman testi için).

## Güncelleme (2026-06 — Faz 7: Tema-Fiyat Otomasyonu + Misafir Kimlik Arşivi TAMAMLANDI)
- TEMA-FİYAT OTOMASYONU: sentiment_pricing.py run_theme_analysis — erken uyarı (≥10 puan düşüş) tetiklenince analyze_sentiment otomatik koşar, db.sentiment_recos'a öneri düşer (index, adj, signal, trigger_alerts, status:new), fire_reprice('sentiment_theme_alert'). GET /{pid} yanıtına recos eklendi; POST /{pid}/recos/{rid}/dismiss. UI: SentimentPricingPanel '🤖 Otomatik Öneriler' kartı (Uygula + Kapat). Doğrulandı: temizlik 85→70 → uyarı → öneri → reprice olayı.
- MİSAFİR KİMLİK ARŞİVİ (KVKK): routes/hotel_ops/id_archive.py — GET /api/id-archive (guest_registrations ⋈ bookings; expires=check_out+retention; durum: saklamada/imha bekliyor/imha edildi), PUT /config (retention_days 30-3650, varsayılan 365, admin), POST /purge-expired (admin: yerel dosya silinir + upload_blocklist + id_purged işaretlenir). server.py serve_upload: blocklist'teki hassas dosya → 410 'KVKK gereği imha edildi'. UI: IdArchivePanel (view: id-archive, menü 'Misafir Kimlik Arşivi (KVKK)') — tablo, rozetler, saklama süresi formu, imha butonu (confirm), güvenli blob önizleme modalı (Authorization header ile buluttan). Doğrulandı: 6 kayıt imha + 410 + demo kimlik önizleme.
- NOT: menuSections'a IdentificationCard import eklendi (eksikti, beyaz ekran verdi — düzeltildi). Demo: John Smith / demo_id.jpg saklamada, diğerleri imha edildi durumda.
- BEKLEYEN: Resend anahtarı, canlı URL (duman testi).

## Güncelleme (2026-06 — Faz 8: Kimlik OCR + AI Rezervasyon Doğrulama TAMAMLANDI)
- KİMLİK OCR + AI DOĞRULAMA: routes/guests/id_verification.py refactor — run_id_verification(db, booking, img_b64, by) modül fonksiyonu (gpt-5.4 vision, alan çıkarma: full_name/document_number/nationality/dob, _name_match Türkçe karakter normalizasyonlu token eşleşmesi, ≥0.5 → verified). id_archive.py POST /api/id-archive/{registration_id}/ocr-verify: belgeyi yerel/buluttan okur, AI'ya gönderir, rezervasyon guest_name ile karşılaştırır, verdict_tr döner (EŞLEŞTİ/UYUŞMUYOR/OKUNAMADI). İmha edilmiş belge → 410. GET /api/id-archive artık verification alanı içeriyor (id_verifications join).
- UI: IdArchivePanel 'AI Doğrulama' kolonu — '🤖 AI Doğrula' butonu (id-ocr-btn-{rid}), sonuç rozetleri (✅ EŞLEŞTİ %xx / ❌ UYUŞMUYOR / ⚠️ OKUNAMADI) + kimlikten okunan ad ve belge no.
- TEST: Demo kimlik (JOHN SMITH / 12345678901) AI ile okundu, rezervasyon 'John Smith' ile %100 eşleşti (verified). UI rozetleri ekran görüntüsüyle doğrulandı.
- BEKLEYEN: Canlı URL (duman testi — kullanıcı 2 kez istedi ama URL vermedi), Resend anahtarı.

## Güncelleme (2026-06 — Faz 9: Ön Check-in Davet Kiti + Otomatik OCR + KVKK Oto-İmha TAMAMLANDI)
- ÖN CHECK-İN DAVET KİTİ (kullanıcının referans ekranları birebir): guest_journey.py GET /api/guest-journey/invite-kit/{booking_id} — kayıt yoksa token üretir, PUBLIC_BASE_URL/register/{token} linki, TR+EN hazır mesaj, wa.me linki (misafir telefonuyla), mailto linki döner. UI: GuestJourneyPanel 'Send Registration Link' dialogunda her rezervasyona '📲 Davet Kiti' butonu → modal (link+Kopyala, TR/EN sekme, mesaj kopyala, WhatsApp ile Gönder, E-posta ile Gönder, QR kod). BASE_URL fix: PUBLIC_BASE_URL env önceliği (cluster iç URL sorunu çözüldü).
- OTOMATİK OCR DOĞRULAMA (Check-in OCR kısayolu): guest_journey.py _auto_ocr_verify — misafir linkten (upload-id/{token}) veya resepsiyondan (reception-upload-id) kimlik yükleyince asyncio.create_task ile AI doğrulama otomatik koşar; UYUŞMAZLIK/OKUNAMADI → yüksek öncelikli bildirim ('Chen Thomas: kimlikte JOHN SMITH okundu — kontrol edin' senaryosu uçtan uca doğrulandı).
- KVKK OTO-İMHA (opsiyonlu): id_archive.py purge_expired_ids modül fonksiyonu + id_auto_purge_loop (12 saatte bir, sadece auto_purge=true iken; imha sonrası bildirim). PUT /config artık auto_purge kabul ediyor; GET auto_purge döner. UI: IdArchivePanel 'Otomatik imha (her gece)' checkbox. Manuel imha + süre ayarı korundu.
- BEKLEYEN: Canlı URL (3 kez istendi, verilmedi), Resend anahtarı.

## Güncelleme (2026-06 — Faz 10: Takvim Davet Kiti + Varış Öncesi Hatırlatma Robotu TAMAMLANDI)
- TAKVİM HIZLI AKSİYON MENÜSÜ: BookingTimeline quick-actions popover'ında zaten Check In/Out, No-Show, Add Note, Duplicate, Lock, Details, Cancel, Send Link vardı (referans ekranla uyumlu). YENİ: 'Davet Kiti' aksiyonu — tıklayınca invite-kit çekilir, TR mesaj panoya kopyalanır, wa.me WhatsApp sekmesi açılır.
- VARIŞ ÖNCESİ HATIRLATMA ROBOTU: guest_journey.py run_precheckin_reminders + precheckin_reminder_loop (saatte bir; enabled iken). Config: db.precheckin_reminder_config {enabled, lead_hours 1-168}. Check-in'i tamamlamamış (kayıt yok/id yüklenmemiş), e-postası olan, lead penceresindeki misafirlere kayıt linkli e-posta (mailer, MOCK); booking.precheckin_reminder_sent idempotent. Endpoints: GET/PUT /api/guest-journey/reminder-config, POST /reminder-run-now. UI: GuestJourneyPanel '⏰ Varış Öncesi Hatırlatma Robotu' kartı (Aktif checkbox + 24/48/72 saat seçici + Şimdi Çalıştır). Test: 6 misafire gönderildi, e-posta loglandı, UI doğrulandı.
- BEKLEYEN: Twilio WhatsApp/SMS otomatik gönderim (kullanıcıdan Account SID + Auth Token + WhatsApp numarası gerekli), Canlı URL (4. kez istendi), Resend anahtarı.

## Güncelleme (2026-06 — Faz 11: Hatırlatma Etki Raporu + Takvim Menü Gap Analizi)
- HATIRLATMA ETKİ RAPORU: GET /api/guest-journey/reminder-impact — hatırlatılan/tamamlayan/bekleyen + dönüşüm %. UI: GuestJourneyPanel hatırlatma kartında istatistik satırı + dönüşüm barı (reminder-impact-stats). Test: 6 hatırlatıldı / 0 tamamladı / %0 (dürüst veri).
- TAKVİM MENÜ GAP ANALİZİ: /app/memory/TAKVIM_MENU_GAP_ANALIZI.md — 7 eksik tespit (oda taşı, split, onay yeniden gönder, mesaj kısayolu, ödeme linki kısayolu, tarih düzenle, kayıt kartı popover). P0: Oda Değiştir + Ödeme Linki kısayolu.
- BEKLEYEN: Twilio anahtarları, Canlı URL, Resend anahtarı (kullanıcı hiçbirini henüz paylaşmadı).

## Güncelleme (2026-06 — Faz 12: Takvim Hızlı İşlemleri — Oda Değiştir / Ödeme Linki / Onayı Gönder TAMAMLANDI)
- ODA DEĞİŞTİR: BookingTimeline popover'a 'Oda Değiştir' aksiyonu (qa-changeroom) → change-room-modal: müsait odalar (aynı tip önce, OOS bloklu odalar hariç), tıklayınca PUT /bookings/timeline/{pid}/reassign/{bid}. Backend reassign conflict check artık no_show/checked_out'u hariç tutuyor (yanlış blok düzeltildi).
- ÖDEME LİNKİ KISAYOLU: popover 'Ödeme Linki' (qa-paylink) → POST /payments/checkout (balance_due ?? total_price), Stripe checkout_url panoya kopyalanır; bakiye 0 → 'Ödenmemiş bakiye yok'.
- ONAY YENİDEN GÖNDER: popover 'Onayı Gönder' (qa-resend, guest_email yoksa disabled) → POST /bookings/{id}/resend-confirmation (MOCK mailer). 60sn cooldown eklendi (429 'Lütfen 1 dakika bekleyin'), confirmation_resent_at booking'e yazılır.
- TEST: iteration_593.json — backend 7/7, frontend %100 (popover + 3 buton + modal + regresyon). Cooldown curl ile doğrulandı (200 → 429).
- KÖK LINT FIX: /app/eslint.config.js oluşturuldu (platform linter /app kökünden koşuyordu, config yoktu → engine error). react-hooks plugin frontend/node_modules'ten yükleniyor, reportUnusedDisableDirectives kapalı.
- BEKLEYEN: Twilio anahtarları (kullanıcı 'birazdan paylaşacağım' dedi — gelince integration_expert çağır), Resend anahtarı, Canlı URL.

## Güncelleme (2026-06 — Faz 13: Tarih Düzenle + Böl + Ödeme Linki Takibi + Modül Yöneticisi + Rebase Etki Analizi TAMAMLANDI)
- TARİH DÜZENLE: PUT /bookings/{id}/dates (çakışma 409, nights/total_price yeniden hesap). UI: popover 'Tarih Düzenle' (qa-editdates) → edit-dates-modal.
- REZERVASYON BÖL: POST /bookings/{id}/split {split_date, new_room_id} — oransal fiyat bölme, 2. kayıt split_from + '-B' ref + payment_status='pending'. UI: popover 'Böl' (qa-split) → split-modal (tarih + müsait oda seçimi).
- ÖDEME LİNKİ TAKİBİ: /payments/checkout artık izleme linki döner (/api/pay/r/{tx_id} → 302 Stripe + status 'opened'); GET /payments/booking-links/{bid} (lazy Stripe poll). Timeline bar serializer'a pay_link/guest_email/room_id eklendi (KRİTİK FIX: bar'lar bu alanları hiç taşımıyordu). UI: barda paylink-dot rozeti (gri=gönderildi, amber=açıldı, yeşil=ödendi) + popover'da qa-paylink-status chip.
- MODÜL YÖNETİCİSİ: routes/platform_ext/menu_manager.py — GET/PUT/DELETE /menu-overrides + /reset (admin). PUT boş override → sil (hidden:false desteklenir). UI: ModuleManagerPanel (module-manager view, admin-only menü öğesi) 312 modül, bölüm taşıma dropdown + gizle + arama + Varsayılana Dön. App.js applyMenuOverrides + 'menu-overrides-changed' eventi ile anında menü güncellenir. Taşınan modüller hedef bölümde 'Taşınan Modüller' böleni altında.
- REBASE ETKİ ANALİZİ (kullanıcının Camden raporu birebir): routes/revenue_ext/rebase_impact.py — GET defaults (oda tipi × 0-30/31-60/61-90 net bugün + son-dakika-gerçekleşen hedef önerisi, misafir-öder çarpanı medyan+band+güvenilirlik, 90g doluluk, rezervasyon penceresi, rate_plan kalitesi), POST analyze (18 satırlık tablo, oda-ağırlıklı otel geneli, katkı analizi komisyon+değişken maliyet, 90 günde katkı kaybı, başabaş oda-gece/doluluk + İMKÂNSIZ uyarısı, 'söylemediği 3 şey', deterministik Türkçe narrative, db.rebase_reports), POST ai-comment (Emergent LLM gpt-5.2 Türkçe danışman yorumu), GET history. UI: RebaseImpactPanel ('rebase-impact' view, Revenue & rates > AI & Insights) — düzenlenebilir hedef tablosu, Analiz Et, sonuç tabloları, başabaş kartı, AI Yorum, Yazdır/PDF (print CSS).
- KÖK LINT: /app/eslint.config.js stub react-hooks plugin ile (platform linter /app kökünden koşuyor).
- TEST: iteration_594.json (16/16 backend + %100 frontend), iteration_595.json (10/10 backend + %100 frontend).
- BEKLEYEN: Twilio anahtarları (kullanıcı paylaşacak — gelince integration_expert çağır), Resend anahtarı, Canlı URL.

## Güncelleme (2026-06 — Faz 14: Rebase Deney Takibi + ABS Çekirdek TAMAMLANDI)
- REBASE DENEY TAKİBİ: rebase_impact.py — POST /experiment/start {report_id} (çalışan varsa 409), GET /experiments (progress: elapsed_days, pickup_before/after simetrik pencere, pickup_change_pct, adr_change_pct, katkı before/after, verdict_tr: ✅/⚠️/❌/⏳ ilk 24 saat), POST /experiment/{id}/stop. db.rebase_experiments. UI: RebaseImpactPanel 'Deneyi Başlat' butonu + 'Deney Takibi — Tahmin vs Gerçek' kartları (pickup/ADR/katkı/başabaş + verdict + Durdur).
- ABS ÇEKİRDEK: abs_selling.py — GET /{pid}/room-matrix, PUT /{pid}/room-attrs/{room_id}, POST /room-attrs/auto-seed (demo dağıtım), POST /public/{pid}/availability (auth yok; per_attribute + combined_free_rooms). booking_widget.py: ABS seçiminde TÜM özelliklere sahip müsait oda otomatik atanır (room_id + abs_room_guaranteed:true); uygun oda yoksa 409; eşleme hiç yoksa legacy (ek ücret, atamasız). UI: AbsPanel 'Oda–Özellik Matrisi' (checkbox grid + otomatik dağıt), BookingWidgetPage canlı müsaitlik ('Son N oda' / 'Müsait oda yok' rozetleri + kombine garanti satırı abs-combined-availability).
- TEST: iteration_596.json — backend 11/11 + %100 frontend. Deneyler durduruldu.
- BEKLEYEN: Twilio anahtarları, Resend anahtarı, Canlı URL.

## Güncelleme (2026-06 — Faz 15: ABS Fiyat Önerisi + Deney Bildirimi TAMAMLANDI)
- ABS FİYAT ÖNERİSİ: abs_selling.py GET /{pid}/price-suggestions — son 90g satış verisi: özellik başına attach_rate; ≥%30 → %15 zam (tavan ADR'nin %15'i), ≤%5 → %15 indirim (taban £2), <20 rezervasyon → 'yetersiz veri'. reason_tr açıklamalı. UI: AbsPanel '🤖 Robot Fiyat Önerileri' kartı + Uygula butonu (mevcut upsert ile fiyat güncellenir) — ekran görüntüsü + canlı uygulama doğrulandı.
- DENEY BİLDİRİMİ: rebase_impact.py modül seviyesine refactor (compute_experiment_progress, check_experiment_alerts, rebase_experiment_loop — server.py startup'ta spawn, saatlik). Sonuç: success/partial/failing → db.notifications (high, revenue) BİR KEZ (notified_* idempotent flag; failing için min 3 gün bekler, <24 saat değerlendirmez). POST /experiments/check-now elle tetikleme. Simülasyonla doğrulandı: 5 günlük deney → '❌ Rebase deneyi başabaşı tutturamıyor' bildirimi + ikinci koşuda 0 (idempotent).
- TWILIO: Kullanıcı WhatsApp numarası verdi (+447878867510, /app/memory/twilio_pending.md'ye not edildi) ama Account SID + Auth Token HÂLÂ EKSİK — gelince integration_expert çağır.

## Güncelleme (2026-06 — Faz 16: Rapor E-postası + ABS Otomatik Fiyat + Bildirim Sesi TAMAMLANDI)
- RAPOR E-POSTASI: rebase_impact.py POST /email-report {report_id, to} — şık HTML e-posta (kategori tablosu, katkı/başabaş, narrative, son deney ilerlemesi, AI yorumu html.escape'li) mailer üzerinden (MOCK → email_outbox). UI: RebaseImpactPanel '✉ E-posta' → inline satır (rebase-email-input/send).
- ABS OTOMATİK FİYAT: abs_selling.py modül seviyesi compute_price_suggestions + abs_auto_pricing_run (korkuluk: ADR %15 tavan, £2 taban, <20 rezervasyon dokunmaz; abs_price_log + notification) + abs_auto_pricing_loop (saatlik kontrol, 24 saatte bir uygular; server.py spawn). Endpointler: PUT /auto-pricing, POST /auto-pricing/run, GET /price-log. UI: AbsPanel 'Otomatik mod AÇIK/KAPALI' anahtarı + 'Şimdi çalıştır' + son koşu zamanı. Şu an KAPALI bırakıldı.
- BİLDİRİM SESİ: NotificationBell.js — yeni HIGH öncelikli bildirimde WebAudio iki tonlu uyarı (soundOnRef kontrolü VAR), panelde 🔊/🔇 anahtarı (localStorage notifSound).
- TEST: iteration_597.json — backend 10/10 + %100 frontend. AI yorum HTML escape düzeltmesi test sonrası eklendi.
- TWILIO: Hâlâ SID + Auth Token bekleniyor (numara alındı: +447878867510).

## Güncelleme (2026-06 — Faz 17: ABS Gelir Panosu + Haftalık Rapor Robotu Genişletmesi TAMAMLANDI)
- ABS GELİR PANOSU: abs_selling.py GET /{pid}/revenue-dashboard — son 6 ay (created_at/satış ayına göre, start_month..cur_month clamp), monthly abs_revenue + by_attribute (price×nights) + total + attach_rate. UI: AbsPanel '📊 ABS Gelir Panosu' — recharts bar chart + özellik bazında yatay barlar.
- HAFTALIK RAPOR ROBOTU: weekly_digest.py build_digest'e 'rebase' bloğu (son 30g rapor: değişim %, katkı kaybı, başabaş, son deney verdict'i — compute_experiment_progress ile) ve abs_price_changes_7d eklendi; _rebase_section_html HTML bölümü (loss None guard'lı). Pazartesi 07:00 UTC loop zaten mevcuttu — otomatik gidiyor.
- TEST: iteration_598.json — backend %100 (7/7) + frontend %100.
- BEKLEYEN: Resend anahtarı + Twilio SID/Token (kullanıcı 2 kez action item seçti ama değerleri hiç yapıştırmadı).

## Güncelleme (2026-06 — Faz 18: ABS Hedef Takibi + Bülten Arşivi TAMAMLANDI)
- ABS HEDEF TAKİBİ: abs_selling.py PUT /{pid}/revenue-target {monthly_target} (abs_settings.abs_monthly_target); revenue-dashboard yanıtına monthly_target/current_month_revenue/target_progress_pct eklendi. UI: AbsPanel Gelir Panosu'nda '🎯 Aylık ABS Hedefi' — hedef inputu + renkli ilerleme çubuğu (yeşil ≥%100, sarı ≥%60, kırmızı altı). Curl + screenshot doğrulandı (hedef £500, %28 kırmızı).
- BÜLTEN ARŞİVİ: weekly_digest.py GET /{pid}/render/{digest_id} — arşivdeki bülteni e-postadaki HTML haliyle döndürür. UI: WeeklyDigest.js '📬 Bülten Arşivi' bölümü (Revenue management > Weekly Digest sekmesi) — geçmiş bültenler listesi (week_key, tarih, alıcı sayısı, elle/otomatik), tıklayınca inline HTML önizleme, 'Şimdi Gönder' butonu. Screenshot ile doğrulandı (4 arşiv kaydı, önizlemede Rebase/Deney/ABS bölümleri görünüyor).
- TEST: Self-test (curl + 2 screenshot) — testing agent kullanılmadı (küçük eklemeler, mevcut test edilmiş modüller üzerine).
- BEKLEYEN: Resend anahtarı + Twilio SID/Token (kullanıcı 3. kez action item seçti, değer yapıştırmadı).

## Güncelleme (2026-06 — Faz 19: Hedef Bildirimi + Bülten PDF İndirme TAMAMLANDI)
- HEDEF BİLDİRİMİ: abs_selling.py check_abs_target_alerts(db, force_pid) — ay sonuna ≤5 gün kala hedefi olan mülklerde bu ay ABS geliri + lineer ay sonu projeksiyonu hedefin altındaysa HIGH bildirim (ayda 1 kez, abs_target_warned=YYYY-MM flag). abs_auto_pricing_loop içinde saatlik koşuyor. POST /{pid}/target-alert/check elle tetikleme (force). Doğrulandı: bildirim + flag + doğru matematik (£140/£500 %28, projeksiyon £155).
- BÜLTEN PDF: WeeklyDigest.js arşiv satırlarına 'PDF' butonu — render endpoint'ten HTML alıp yeni pencerede yazdırma diyaloğu (tarayıcı Save as PDF). Popup başlığı bulten-{week_key}. Screenshot ile doğrulandı. 'Invalid Date' koruması eklendi.
- BEKLEYEN: Resend anahtarı + Twilio SID/Token.

## Güncelleme (2026-06 — Faz 20: Hedef Panoları + Aylık Yönetim Raporu TAMAMLANDI)
- HEDEF PANOLARI: routes/revenue_ext/monthly_report.py — GET/PUT /revenue/targets/{pid} (db.revenue_targets: revenue_target, occupancy_target 0-100 validasyonlu) + bu ay gerçekleşme (check_in ayı bazlı gelir/doluluk) ve progress %. UI: MonthlyTargetsCard.js — Revenue management > Dashboard sekmesi en üstünde renkli çubuklar (yeşil/sarı/kırmızı) + 'Hedefleri Düzenle' inline form. Doğrulandı: £43,539/£50,000 %87.1 + %58.4/%80 %73.
- AYLIK YÖNETİM RAPORU: build_monthly_report (ay metrikleri + önceki ay karşılaştırma + hedef performansı + ABS + rebase özeti), _monthly_html, send_monthly_report (admin/manager'lara MOCK e-posta + db.monthly_reports + bildirim), monthly_report_loop (ayın 1'i ≥07:00 UTC önceki ayı otomatik hazırlar, idempotent). Endpointler: /monthly-report/{pid}/history, /render/{id}, POST /send-now {month}. UI: WeeklyDigest.js '🗓 Aylık Yönetim Raporu' arşiv bölümü (önizleme + PDF + Bu Ayı Şimdi Hazırla). Screenshot + curl doğrulandı.
- NOT: server.py'de hot-reload sonrası backend geç kalktı — supervisorctl restart gerekti (bilinen yavaş startup).
- BEKLEYEN: Resend anahtarı + Twilio SID/Token (4. kez istendi, hâlâ yok).

## Güncelleme (2026-06 — Faz 21: Fiyat Güvenlik Sınırları + DEMAND_STRONG TAMAMLANDI)
- KULLANICI ANALİZ TALEBİ: RevenueIQ benzeri belge vs bizim sistem karşılaştırıldı — ~%70 mevcuttu (satış kanıtlı merdiven, fire_reprice anında tepki, yön dönüşü, taban/tavan, comp medyan, gerekçe logu). 4 eksik bulundu, 2'si kullanıcı onayıyla kapatıldı:
- FİYAT GÜVENLİK SINIRLARI: routes/revenue_ext/price_guard.py — guard_rate_change(db,...): tek hamle max %10 (kırpar), 72h kümülatif max %25 (price_guard_log ilk old_rate bazlı tavan; tavan dolunca bloklar), owner-override kilitli geceye otomatik aktör dokunamaz. GET/PUT /price-guard/{pid} (1-50 / 5-100 bounds, enabled toggle). Zam Merdiveni yazımdan önce guard'dan geçer ('güvenlik sınırı uygulandı' reason eki). UI: PriceGuardCard (Revenue > Dashboard, MonthlyTargets altında).
- DEMAND_STRONG: ramp_ladder.py _market_signal — comp_rate_snapshots taze(48h) vs eski(5-10 gün) medyan ≥%3 artış VEYA sold-out payı ≥0.5 → kendi satışı olmadan SÖNÜMLÜ kademe (yarım adım; unavail ≥0.6 → tam adım/fren gevşer), tarih başına 24h'de 1 piyasa kademesi (ramp_state.market_step_at), ramp_steps reason=DEMAND_STRONG + market_signal, rate_overrides reason 'DEMAND_STRONG (piyasa)...'.
- TEST: iteration_599.json — 10/10 backend + %100 frontend (guard API/mantık, DEMAND_STRONG e2e scan, 24h kilidi, awaiting_guest_approval regresyonu, UI kart). Import hot-path'e taşındı (review notu).
- BEKLEYEN: Resend + Twilio anahtarları.

## Güncelleme (2026-06 — Faz 22: Guard İhlal Uyarısı + Fiyat Karar Zaman Çizelgesi + Tarama Kadansı TAMAMLANDI)
- GUARD İHLAL UYARISI: price_guard.py _maybe_alert_repeated_clamps — aynı aktör 24 saatte ≥3 kez kırpılırsa HIGH bildirim ('ayarları gözden geçirin'), 24 saatte 1 kez (price_guard_alerts.last_alert_at). Birim test: 3 kırpma → 1 bildirim, 4. kırpma → tekrar yok.
- FİYAT KARAR ZAMAN ÇİZELGESİ: price_guard.py GET /price-timeline/{pid}?date= — ramp_steps + clamped price_guard_log + rate_overrides birleşik kronolojik event listesi + 48s rakip medyanı. UI: PriceTimelineCard (Revenue > Dashboard, PriceGuard altında) — tarih seçici, ikonlu dikey timeline (merdiven yeşil / korkuluk amber / yazım mavi), gerekçeler görünür. Screenshot: 18 event, DEMAND_STRONG gerekçeleri dahil.
- TARAMA KADANSI: sec_pulse_loop.py _boosted_interval — market_robot_config.near_term_boost (vars. açık): önümüzdeki 7 gün doluluk ≥%60 ise city-scan aralığı 1/3'e iner (min 15 dk).
- TEST: Guard uyarısı python birim + timeline curl (18 event) + UI screenshot. Kadans kod düzeyinde (deterministik yardımcı), e2e loop beklenmedi.
- BEKLEYEN: Resend + Twilio anahtarları.

## Güncelleme (2026-06 — Faz 23: İK Bordro Genişletme + Revenue Boşlukları TAMAMLANDI)
- SMP/SPP (Doğum Yardımı): uk_payroll.py — sabitler 2026/27 (£194.32/hafta, LEL £129, SMP 39 hafta: ilk 6 hafta %90 AWE, sonra min(£194.32, %90 AWE); SPP 1-2 hafta). compute_parental_pay (hafta başı ay içinde ise sayılır). db.staff_parental_leaves. Endpointler: GET /uk-payroll/parental-leave/{pid}, POST /uk-payroll/employees/{sid}/parental-leave {type,start_date,awe?,weeks}, DELETE /uk-payroll/parental-leave/{id}. Bordro satırı smp/smp_weeks/smp_type + totals.smp + smp_recovery (%92 HMRC). Payslip PDF'e SMP/SPP satırı. UI: ParentalLeaveCard (Personel & İK sekmesi), Aylık Bordro 'SMP/SPP' sütunu.
- İZİN İPTALİ: POST /uk-payroll/me/leaves/{id}/cancel (pending→cancelled; approved→cancel_requested + bildirim), POST /uk-payroll/leaves/{id}/cancel-decision {approve} (manager). LEAVE_ACTIVE_STATUSES = approved+cancel_requested (bakiye/SSP/takvim). UI: portalda 'İptal Et' / 'İptal Talep Et', yöneticide 'İzin İptal Talepleri' bloğu.
- BORDRO KİLİDİ: _persist_run → locked:true, revision; kilitliyse force dahil 423. db.uk_payroll_corrections. POST /uk-payroll/runs/{id}/correction-request {reason}, GET /uk-payroll/corrections/{pid}, POST /uk-payroll/corrections/{id}/decide {decision} (admin → kilit açılır), POST /uk-payroll/runs/{id}/unlock {reason} (admin doğrudan, direct:true log), POST /uk-payroll/runs/{id}/lock. Yeniden çalıştırınca approved→applied. Robot kilitli ayı atlar. UI: PayrollCorrectionsCard + run kartında Kilitli/Açık rozeti + Düzeltme Talebi / Kilidi Aç / Kilitle butonları.
- WIDGET DİNAMİK FİYAT (kritik boşluk kapatıldı): routes/pms/widget_pricing.py — nightly_rates (rate_overrides oda-tipi → mülk-geneli → base_rate), explain_price, check_los_restrictions. check-availability: nightly[], price_explanation, LOS ihlalinde restriction{}. /book: sunucu tarafı yeniden fiyatlama (istemci rate yok sayılır, loyalty % uygulanır), LOS ihlali 409, nightly_rates kayda yazılır.
- LOS KISITI: los_restrictions (min_stay/max_stay, days/applies_to weekends, date_from/to) artık widget + /book'ta UYGULANIYOR.
- FİYAT ŞEFFAFLIĞI ROZETİ: BookingWidgetPage 'Why this price? ±%' rozeti → gece gece fiyat grid + sürücü etiketleri (High demand / Local event / Guest review score...). Gerçek standart fiyat üstü çizili (sahte ×1.15 sadece açıklama yoksa).
- FORECAST → FİYAT: ramp_ladder.py _forecast_map (ml_pickup LightGBM) + _forecast_signal: T>14 gün ve tahmin ≥%90 → FORECAST_HOT sönümlü yarım kademe (48 saatte 1, ramp_state.forecast_step_at); tahmin <%50 → forecast_cold_brake (yukarı kademe yok). cfg.forecast_boost (vars. açık) — PUT config + RampLadderPanel 'ML tahmin anahtarı' checkbox; günlükte 🤖 etiketi.
- TEST: iteration_605.json — backend 23/23 + frontend %100. Python simülasyonla FORECAST_HOT (100→107.62) / 48h kilidi / cold brake doğrulandı.
- BEKLEYEN: Resend + Twilio anahtarları (kullanıcı 'anahtarları paylaşıyorum' dedi ama değer yapıştırmadı → MOCK).

## Güncelleme (Faz 24 — Widget Etkinlik Bandı + OTA Kanal Şeridi + Bordro Bildirimi) — iteration_606 %100
- ETKİNLİK FİYAT BANDI: widget_pricing.stay_signals → market_events (pid/all, hotel_demand_score≥30, kategori→misafir dili: 🎵 konser/festival, 🏟️ spor, 🏢 kongre/fuar, 🎉 şehir kutlaması; tür başına 1) + demand_calendar_signals.holiday (🎄) + public_events (✨ oteldeki etkinlik). check-availability → price_explanation.signals; widget panelinde be-price-signals-*.
- KANAL YÖNLENDİRME: booking_widget_config.direct_advantage_pct (vars. 5) + ota_banner_enabled (info.theme'e eklendi; BookingEngineAdmin ThemeConfig'te theme-direct-pct / theme-ota-banner-toggle). Widget ?src=booking|expedia|... veya OTA referrer → be-ota-banner ("Coming from X? Book direct and save %Y") + oda kartında be-ota-compare-* (OTA ~fiyat üstü çizili / Direct / save). check-availability → ota_compare{}.
- BORDRO ONAY BİLDİRİMİ: uk_payroll._notify(push=True) → admin/manager users'a e-posta (_send_email, Resend MOCK) + WhatsApp (phone varsa, Twilio MOCK) + db.hr_notification_log; correction-request/decide/unlock yanıtında delivery{emails,whatsapp,mode}. GET /uk-payroll/notification-log. UI toast: "yöneticilere 3 e-posta (MOCK) kuyruklandı". Gerçek anahtar gelince mode=live otomatik.
- MOCK: Resend, Twilio (anahtar hâlâ yok).

## Güncelleme (Faz 25 — Widget TR/EN/DE + OTA Dönüşüm Ölçümü + Etkinlik Primi) — iteration_607 %100
- MİSAFİR DİLİ: frontend/src/widgetI18n.js (sözlük en/tr/de, useWidgetLang: ?lang → localStorage be_lang → navigator.language). Widget ana metinleri t() ile; backend label_de/headline_de/message_de eklendi (widget_pricing.py). Header'da be-lang-switch (be-lang-en/tr/de). pick(obj,"label") dil seçimi. Otel özel subtitle varsa çevrilmez (owner içeriği), varsayılan çevrilir.
- OTA DÖNÜŞÜM: POST /booking-widget/ota-banner-view (public, db.ota_banner_views) — şerit gösteriminde otomatik; /book payload channel_source "ota_banner:<OTA>" + lang → booking.channel_source/guest_lang. GET /booking-widget/ota-conversion/{pid}?days → views, bookings, conversion_pct, revenue, commission_saved (~%15 OTA komisyonu), by_ota. UI: OTACommissionPanel Summary sekmesinde ota-conversion-card.
- ETKİNLİK PRİMİ: ramp_ladder.py _event_map (market_events pid/all, hotel_demand_score ≥ cfg.event_min_score vars. 60). step 0 + doluluk eşik altı + etkinlik → EVENT_PREMIUM sönümlü yarım kademe (1 kez, ramp_state.event_step_at/event_name), etkinlik sürdükçe yön dönüşü yapılmaz. cfg.event_premium (vars. açık) + event_min_score; RampLadderPanel ramp-event-toggle / ramp-event-score; günlükte 🎪 etiketi. Simülasyon: 121→127.1 (yarım adım) doğrulandı.
- MOCK: Resend, Twilio (anahtar hâlâ paylaşılmadı).

## Güncelleme (Faz 26 — Misafir E-posta Dili + Etkinlik Takvimi Şeridi + OTA A/B Testi) — iteration_608 %100
- MİSAFİR E-POSTASI: routes/pms/guest_email_i18n.py — build_confirmation(booking, hotel, lang) TR/EN/DE şablon (konu+gövde, tarih ay adları çevrili), send_guest_confirmation → mailer.send_email (Resend MOCK → email_outbox{lang}) + booking_email_log. Widget pay-at-property /book yanıtında email{status,lang,subject}; Stripe webhook (payments.py) ödeme sonrası aynı fonksiyonu kullanır.
- ETKİNLİK ŞERİDİ: GET /booking-widget/upcoming-events/{pid}?days&limit (public; market_events skor≥60, tür+tarih çakışması dedupe, suggest_check_in/out min 2 gece). Widget ana sayfa be-events-strip (TrustBar altı) 4 kart, be-event-book-{date} → search({ci,co}) tarihleri doldurup arar + scrollTop. i18n events_* anahtarları.
- OTA A/B: booking_widget_config.ota_ab_enabled / ota_ab_variant_b_pct (vars. 8) → info.theme; BookingEngineAdmin Theme'de ota-ab-config (theme-ab-toggle, theme-ab-b-pct). Widget: localStorage be_ab_variant (A/B sabit), B'de şerit+karşılaştırma yüzdesi B (fiyat aynı); ota-banner-view {variant,pct}; /book ab_variant. ota-conversion → ab{enabled, variant_b_pct, variants[A,B], winner (≥20 gösterim/varyant), min_views_for_winner}; 'all' görünümünde A/B açık olan ilk mülk config'i yansıtılır. OTACommissionPanel ota-ab-card.
- MOCK: Resend, Twilio.

## Güncelleme (Faz 27 — Ön Varış E-postası + Etkinlik Paketleri + A/B Otomatik Kazanan) — iteration_609 %100
- ÖN VARIŞ E-POSTASI: routes/pms/arrival_reminder.py (prefix /arrival-reminder) — build_arrival_email TR/EN/DE (check-in/out saati, adres, Google Maps linki, upsell: upsell_items ilk 3 veya varsayılan 3 teklif). run_arrival_reminders_internal: check_in ∈ {T+2, T+1} & arrival_reminder_sent_at yok → mailer.send_email (MOCK) + booking.arrival_reminder_sent_at + db.arrival_reminder_log. Endpoints: POST /run/{pid}, GET /log/{pid}, GET /preview/{pid}?lang. JOB_REGISTRY 'arrival_reminder' (10:00, kategori guest) + server.py JOB_HANDLERS. NOT: eski pre_arrival.py drip (T-7/T-3/T-1 şablon, sadece kuyruk) hâlâ var, göndermez.
- ETKİNLİK PAKETLERİ: db.event_packages {name_en/tr/de, price_per_night, includes[], enabled}; GET (public)/POST(use_default→£25 kahvaltı+geç çıkış)/PUT/DELETE /arrival-reminder/event-packages/{pid}. Widget: etkinlik kartında be-event-package-{date} → selectedPackage + arama; sonuçlarda be-selected-package çipi, oda kartında be-room-package-*, toplam += price×nights×rooms; /book package_id → sunucu doğrular, booking.package{total} ve total'e ekler (geçersiz → 400).
- A/B OTOMATİK KAZANAN: booking_widget.run_ab_auto_winner_internal — ota_ab_enabled config'ler için 90 gün varyant istatistiği; her varyant ≥20 gösterim ve fark ≥2 puan → direct_advantage_pct=kazanan %, ota_ab_enabled=false, ota_ab_auto_locked{variant,pct,at,stats}, notifications + admin e-posta (MOCK). POST /booking-widget/ab-auto-winner/run/{pid}; JOB 'ota_ab_auto_winner' (06:30). ota-conversion.ab.auto_locked → OTACommissionPanel 'otomatik sabitlendi' etiketi.
- ADMIN UI: BookingEngineAdmin yeni sekme "Misafir Yolculuğu" (bea-tab-journey) → ArrivalReminderCard (şimdi çalıştır, TR/EN/DE önizleme iframe, log) + EventPackagesCard (varsayılan/özel ekle, aktif/pasif, sil). 'all' şube seçiliyken pid ilk mülke düşer.
- MOCK: Resend, Twilio.

## ⚠️ KULLANICI KURALI (2026-09 — zorunlu, her fork okusun)
- Kullanıcı: "Olan özellikleri tekrar yazıyorsun, ekstra maliyet ve zaman kaybı — istemiyorum."
- HER yeni istek öncesi ZORUNLU: `grep -rn` ile backend/routes ve frontend/src'de mevcut modül/endpoint/panel ara (ör. ab_test.py, pre_arrival.py, guest_journey.py, upsell_autopilot.py, event_intelligence, forecast_v2, los_optimizer, parity_analysis…). Varsa ASLA yeniden yazma → mevcut modülü genişlet ve kullanıcıya "zaten var, şunu ekliyorum" de.
- Bilinen duplikasyonlar (kullanıcı isterse birleştir, kendi başına yeni iş açma): OTA A/B sayaçları (booking_widget.py) ↔ ab_test.py motoru; arrival_reminder.py ↔ pre_arrival.py drip (eski göndermiyor).
- Kullanıcı onayı olmadan yeni modül/koleksiyon açma; öneri listesinde mevcut özellikleri "yeni" gibi sunma.

## Güncelleme (Faz 28 — SADECE mevcut modüller genişletildi, yeni modül YOK) — iteration_610 %100
- (a) Upsell tek tık: upsell_engine.py → _apply_upsell paylaşımlı helper (staff accept aynı helper'ı kullanır) + PUBLIC GET /revenue/upsell/claim/{token} (TR/EN/DE HTML sayfası; kullanılmış→"Zaten eklenmiş", geçersiz→"Link not valid"). arrival_reminder.py _with_claim_links → db.upsell_claim_tokens (14 gün) ve e-postada "+ Rezervasyonuma ekle" butonları (PUBLIC_BASE_URL). Kabul → folio_items upsell + upsell_log source=pre_arrival_email.
- (b) Çıkış sonrası yorum: bookings.py mevcut _send_review_collection_email TR/EN/DE (REVIEW_T) + mailer (MOCK) + booking.review_request_sent_at/lang; run_review_requests_internal (checkout 1-7 gün önce, sorulmamış, guest_reviews varsa atla). Mevcut POST /review-collection/send/{pid} bunu kullanır; JOB 'review_request' (11:00, guest) server.py JOB_HANDLERS.
- (c) Paket satış raporu: ota-conversion yanıtına packages{bookings, revenue, attach_rate_pct, widget_bookings, by_package}; OTACommissionPanel package-sales-card.
- MOCK: Resend, Twilio.

## Güncelleme (Faz 29 — küçük genişletmeler, yeni modül YOK; curl+screenshot ile doğrulandı)
- /review sayfası (ReviewCollectionPage.js) ?lang=tr|en|de (yoksa navigator.language) → tüm metinler + tarih locale çevrildi (R sözlüğü, data-testid review-title).
- Upsell kabul bildirimi: upsell_engine.claim_upsell → db.notifications (category upsell, priority high, booking_id) "Misafir ekstra ekledi: …".
- Sabah Karnesi (morning_karne.build_karne) yeni satır "Misafir robotları (24s)": ön varış e-postası sayısı · yorum isteği sayısı · (varsa) A/B kazanan sabitlendi.

## Güncelleme (Faz 30 — Yorum Teşekkür Kuponu; mevcut promo_codes + mailer altyapısı, yeni modül YOK)
- bookings.py submit_review → _issue_review_thanks_coupon: db.promo_codes'a {kind percent, amount 10, max_uses 1, valid_to +365g, source review_thanks, booking_ref} (aynı rezervasyona 1 kez); TR/EN/DE e-posta (kind review_thanks_coupon, MOCK) + /book/{pid}?coupon=CODE&lang= linki (widget ?coupon= zaten okuyor, direct-conversion/validate ile kullanılır). Submit yanıtı coupon{code,pct,valid_to,email_status}; ReviewCollectionPage teşekkür ekranında review-coupon kutusu.

## Güncelleme (Faz 31 — mevcut dosyalara 3 küçük ekleme; curl ile doğrulandı)
- Düşük puan uyarısı: bookings.submit_review rating ≤2 → kupon YOK, db.notifications {category guest_recovery, priority high, booking_ref, guest_email, rating} "⚠️ Misafir kurtarma: 1★ yorum — …"; ≥3 → THANKS kuponu.
- Karne WhatsApp: morning_karne.send_karne admin/manager phone varsa _send_whatsapp_reply (Twilio MOCK→queued) ile not + en fazla 3 sorunlu kontrol; doc.whatsapp[] loglanır.
- Kupon kullanım raporu: direct-conversion/stats → review_coupons{issued, used, expired, usage_pct, revenue (bookings.coupon_code eşleşmesi)}; DirectConversionPanel dcv-review-coupons kartı.

## Güncelleme (Faz 32 — Review Operations Agent: MEVCUT review modülü genişletildi, yeni modül YOK) — iteration_611 backend 13/13, frontend Approval Center %100 + ReviewAgentPanel nav düzeltildi
- KULLANICI POLİTİKASI (kalıcı): 5★ isteme, puan/yorum değiştirme talebi, silme baskısı, para/hediye karşılığı yorum, sahte yorum, uydurma yönetici adı → ASLA. quality_score.policy_safety bu ifadeleri cezalandırır; sign_off yalnızca işletmenin tanımladığı gerçek takım/yetkili.
- reviews.py modül fonksiyonları: heuristic_flags, compute_risk (0-100 → low/medium/high/critical + escalation_level), similarity_score (imza satırları hariç; son 100 yanıt), quality_score (7 boyut), decide_action (do_not_reply | escalate | auto_approve | human_approval; publishing_mode manual/smart_auto/full_auto + auto_rules), privacy_check/privacy_check_db (email, phone, card/IBAN, payment, booking_ref [rakam zorunlu], room_number, internal_notes, staff_private [rol kelimeleri hariç]), log_review_event (reviews.events[] son 60), get_review_agent_cfg (review_agent_config koleksiyonu ortak).
- analyze_sentiment genişledi: emotion, severity, subtopics, staff_mentioned, refund/compensation/safety/legal/discrimination/harassment/fraud/medical, spam/fake_probability, customer_intent, risk_*, spam_suspected, recommended_action.
- generate-ai-response: candidates:true → 3 varyant (warm/professional/concise) paralel; benzerlik ≥85 → 1 kez regenerate; en iyi seçilir; response_quality/similarity/ai_decision/response_privacy/ai_candidates/ai_draft kaydedilir, regeneration_count++. submit-for-approval ai_draft'a düşer.
- approve: izin (has_permission reviews.approve/publish — admin.py REVIEW_ACTIONS), gizlilik engeli 400, high/critical/escalated/spam → notes zorunlu → approval_override{}; action 'escalate' → escalated, escalation_level, db.notifications review_escalation. pending-approval risk sıralı + canlı response_privacy. approve-bulk: 4-5★ & low risk & kalite ≥ eşik & spam değil & gizlilik ok. stats/summary.approval_center{risk_counts, escalated, spam_suspected, high_risk_open, ai_performance}.
- review_autopilot: analiz → spam ise do_not_reply → üret → kalite/benzerlik → karar → publish / draft / escalate (+bildirim); gizlilik ihlali otomatik yayını engeller. review_agent.py: config publishing_mode/auto_rules/full_auto_authorised_by (full_auto için zorunlu), batch-draft karar motoru + gizlilik, publish gizlilik 400.
- review_sources.py: Trustpilot (TRUSTPILOT_API_KEY + trustpilot_business_unit_id → gerçek; yoksa SIMULATED); rating/text değişimi → rating_history + events review_updated + bildirim. integrations.py platform listesi + requirements 'trustpilot'.
- bookings.py review isteği: e-postaya ek WhatsApp (Twilio MOCK, nötr metin, herkese, puan istenmez) → booking.review_request_whatsapp + db.review_request_log.
- UI: ReviewOpsBits.jsx (RiskBadge, FlagChips, SpamNotice, PrivacyAlert, QualityPanel); AIResponsePanel risk/flag/spam + '3 variants' + kalite paneli + aday çipleri; ApprovalQueuePanel → Approval Center (risk sayaçları filtre, Escalate, Override & Publish + zorunlu gerekçe, toplu güvenli onay, spam/gizlilik kilidi); ReviewAgentPanel yayın modu + kural alanları; nav: Reviews & Sentiment → 'Yayın Modu & Onay Kuralları' (review-agent-btn).
- BEKLEYEN (kullanıcı onaylı, yapılmadı): Yönetici Telefonları UI (AdminPanel phone + karne_whatsapp alanı), Kupon Hatırlatma UI (DirectConversionPanel), Kurtarma Takibi 'Arandı/Çözüldü' butonları — backend'leri hazır.
- Review Ops P1/P2 backlog: Staff Intelligence (mention → personel bazlı), Root Cause (konu frekans + trend + öneri), konu bazlı rakip kıyası, dashboard AI Performance bloğu (Reviews ana sayfa), GBP v1 + Pub/Sub (Google OAuth/kota gerekir).
- MOCK: Resend, Twilio, Trustpilot/Booking/Google sync (anahtar yok).
