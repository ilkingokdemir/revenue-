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
