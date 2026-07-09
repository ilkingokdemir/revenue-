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
