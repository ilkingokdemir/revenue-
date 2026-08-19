# DERİN CHANNEL MANAGER GAP ANALİZİ — Cloudbeds · Mews · eviivo · The Booking Factory (2026-06)

Amaç: "Sadece Channel Manager (veya paket) almak isteyen otel" hesap açtığı ANDA sorunsuz hizmet alabilmeli.

---
## 1) RAKİP MİMARİLERİ (özet)

### Cloudbeds Distribution
- Havuzlanmış envanter (pooled inventory): tek kaynak → 450+ OTA/metasearch/booking engine.
- İki yönlü API senkron (gerçek zamanlı ARI: Availability/Rates/Restrictions); API'siz kanallar için iCal.
- Bağlantı tipleri: Full / Custom (hangi ARI kapsamını Cloudbeds'in yöneteceği seçilir).
- Oda eşleme 1:1 zorunlu; Advanced Channel Rates ile çoklu rate plan eşleme.
- Express Connect (kanal listinglerini içeriden aç/bağla), Allotment (kanala kota),
  Closeouts (kanal bazlı tarih kapama), Channel Revenue Allocation (folyo bazlı komisyon dağılımı).
- Distribution sayfasında bağlantı durumu + hata göstergeleri (kimlik/eşleme/rate türetme hataları).

### Mews Distribution
- Mews = source of truth; Availability Block push (space kategori tahsisi, pickup tipi, messageId + async responseUrl).
- Rate group & space kategori eşleme; senkronize/senkronize-olmayan rate ayrımı (senkronsuz da rezervasyon alabilir).
- Operasyonlar: /updateAvailability, /inventory (fiyat), /updateRestrictions; Process Group (100 rezervasyon/grup).
- Distributor API (booking engine), metasearch (Google Hotel Ads) merkezi eşlemeden beslenir. Marketplace ile bağlanır.

### eviivo Suite
- Derin iki yönlü API: rate+müsaitlik+zengin içerik (foto, olanak, politika, vergi) senkronu.
- Tek tık onboarding, çoklu listing toplu yönetim. Booking.com/Expedia/Airbnb/Vrbo/Agoda/Tripadvisor/GHA.
- Promo Manager: web-özel indirim, LOS/early-bird, promo kod, billboard etkisi stratejisi.
- Unified inbox (OTA mesajları+SMS+WhatsApp), AI concierge, Payment Manager (tahsilat otomasyonu).

### The Booking Factory
- Küçük oteller; kanal bağlantısı destek ekibi tarafından kurulur (Channex/SiteMinder/RoomCloud altyapısı üstünden).
- Website builder + direct booking engine + gift cards + Travia (acente sözleşme portalı).
- Pricepoint entegrasyonu ile dinamik fiyat; seasonality/derived rates/occupancy kısıtları manuel.

---
## 2) BİZDE OLANLAR (parite)
| Rakip özelliği | Bizdeki karşılık | Durum |
|---|---|---|
| Pooled inventory + ARI push | two_way_sync.py + channel_hub.py + push_history | VAR |
| Oda/rate plan eşleme matrisi | channel_mappings.py (kind: room/rate_plan, external_id) | VAR |
| Bağlantı durumu + hata izleme | channel_health.py + ota_health.py + Health Sentinel | VAR |
| Kanal bazlı closeout/stop-sell | channel_restrictions.py + ota_stop_sell_forecast + 0-avail stop-sell | VAR |
| Allotment (kanal kotası) | allotments.py | VAR |
| Kanal komisyon/gelir dağılımı | channel_revenue.py (markup, komisyon %) | VAR |
| Parite takibi | channel_parity.py + parity heatmap | VAR |
| PMS konnektörleri | connector_catalog.py (Cloudbeds/Mews/Apaleo push-preview) | VAR |
| Booking engine (direct) | Direct Booking bölümü (engine + promo + gift cards) | VAR |
| Unified inbox | Marketing & Messaging unified-inbox | VAR |
| Acente portalı (Travia) | agency_portal.py | VAR |
| Rate markup/derived rates | channel_connections.rate_rule/rate_markup_pct | VAR |

---
## 3) EKSİKLER — "CM-only müşteriye ANINDA hizmet"
### P0
1. **CM planı yok** → `cm` plan tipi: Overview + Reservations + Direct Booking + Channels & Distribution + Settings açık, gerisi kilitli/upsell.
2. **CM Hızlı Kurulum Sihirbazı yok** (eviivo tek-tık onboarding paritesi): kanal seç → oda/rate eşle → senkron ayarları (ARI kapsamı Full/Custom, stop-sell, frekans) → test push → Go-Live sağlık skoru.
3. **Self-signup yok**: landing'den hesap aç → plan seç (RMS/CM/PRO) → otel otomatik provizyon → ilgili sihirbaza düş.
4. **Tenant izolasyonu**: self-signup kullanıcısı sadece kendi otelini görmeli (property_ids scoping).
### P1
5. Express Connect benzeri "içeriden listing açma" (mock, gerçek OTA API anahtarları gelince canlı).
6. iCal import/export (API'siz kanallar).
### P2
7. Zengin içerik senkronu (foto/olanak push), messageId+async response teyit akışı (Mews paritesi).

---
## 4) SONUÇ
Dağıtım çekirdeği (ARI push, eşleme, sağlık, parite, kota, kısıt) rakip seviyesinde.
Eksik olan yine ÜRÜNLEŞTİRME: cm planı + kurulum sihirbazı + self-signup + tenant scoping.
