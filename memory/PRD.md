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
