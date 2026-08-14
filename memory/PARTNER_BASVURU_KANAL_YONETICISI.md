# Kanal Yöneticisi API Partner Başvurusu — SiteMinder & HotelRunner

Hazırlayan: MyHotelBox & ReveniQ ekibi · Tarih: Ağustos 2026
Amaç: Robotun fiyat kararlarını kanal yöneticisine YAZABİLMEK (ARI push). Sertifikasyon süreci aylar
sürebildiği için model mükemmelleşmeden başvuru şimdi yapılmalı.

---

## BÖLÜM 1 — SiteMinder Partner Başvurusu (İngilizce, forma yapıştırılmaya hazır)

Başvuru adresi: https://www.siteminder.com/partner-with-us/ → "Become an app partner"
(SiteMinder Exchange / SMX program — Rate & Availability push API gerekir)

**Company name:** MyHotelBox & ReveniQ
**Category:** Revenue Management System (RMS)
**Integration type requested:** Two-way — Rates & Availability WRITE (push), Reservations READ (pull/webhook)

**Product description (200 kelime):**
ReveniQ is an AI-first revenue management system for independent hotels and small groups (10–200 rooms).
Our pricing robot combines machine-learning pickup forecasting (LightGBM), competitor-market scanning of
public prices, and a closed learning loop that measures the real outcome of every price decision. Rates are
optimised against Net RevPAR (net of channel commission, payment fees and variable room cost), protected by
hard guardrails (min/max bounds, ±15% step limit, anomaly freeze with human-in-the-loop approval). We need
SiteMinder connectivity to deliver approved rate updates to all connected OTAs in real time and to receive
reservations for our forecast and pickup models. Pilot portfolio: 13 properties (UK/EU). Expected volume at
launch: ≤50 properties, ~12 rate updates/property/day.

**Technical readiness:**
- REST/JSON stack (FastAPI), OAuth2 & API-key auth supported, HMAC webhook verification ready
- Idempotent rate-push adapter layer already live in production against our internal channel simulator
- Full audit trail per price decision (who/why/when + AI rationale), rollback support
- Sandbox-first: we request test credentials for certification before any production traffic
- Rate limits respected; exponential backoff + circuit breaker implemented

**Contact:** [ad-soyad], [e-posta], [telefon]  ← DOLDURUN

---

## BÖLÜM 2 — HotelRunner Partner Başvurusu (Türkçe)

Başvuru adresi: https://hotelrunner.com/tr/partner/ (Teknoloji Partneri / API entegrasyonu)

**Şirket:** MyHotelBox & ReveniQ
**Kategori:** Gelir Yönetim Sistemi (RMS)
**Talep edilen entegrasyon:** Çift yönlü — Fiyat & Müsaitlik YAZMA (push), Rezervasyon OKUMA (webhook)

**Ürün özeti:**
ReveniQ; bağımsız oteller için yapay zekâ destekli gelir yönetim sistemidir. Fiyat robotumuz makine
öğrenmesi pickup tahmini, halka açık rakip fiyat taraması ve her kararın gerçek sonucunu ölçen kapalı
öğrenme döngüsünü birleştirir. Fiyatlar Net RevPAR (komisyon + değişken maliyet düşülmüş) hedefiyle,
sert korumalar (min/max sınır, ±%15 adım limiti, anomali dondurma + insan onayı) altında üretilir.
HotelRunner bağlantısıyla onaylanan fiyatları tüm kanallara anlık iletmek ve rezervasyon verisini tahmin
modellerimize beslemek istiyoruz. Pilot: 13 tesis. Açılış hacmi: ≤50 tesis, tesis başına ~12 güncelleme/gün.

**Teknik hazırlık:** REST/JSON (FastAPI), OAuth2/API-key, HMAC webhook doğrulama, idempotent push
adaptörü, karar bazlı tam denetim izi, önce sandbox sertifikasyonu talebi, rate-limit uyumu.

**İletişim:** [ad-soyad], [e-posta], [telefon]  ← DOLDURUN

---

## BÖLÜM 3 — Teknik Ek (her iki başvuruya eklenecek)

### 3.1 Mimari Özet
- Backend: FastAPI (Python 3.11) + MongoDB; frontend: React. Bulut: Kubernetes.
- Kanal Adaptör Katmanı: kanal-bağımsız tek arayüz (`push_rate(property, room_type, date, rate, restrictions)`).
  Yeni kanal = tek adaptör sınıfı; sertifikasyon sonrası prodüksiyona bağlanır.
- Fiyat akışı: Robot önerisi → guardrail zinciri (min/max → ±%15 → LRV tabanı → anomali kontrolü)
  → insan onayı VEYA eşik-altı oto-uygulama → adaptör push → onay/başarısızlık logu → sonuç ölçümü.

### 3.2 Veri İhtiyaçları
| Yön | Veri | Frekans |
|---|---|---|
| YAZMA | Oda tipi bazlı fiyat (BAR), min-stay/CTA kısıtları | Olay bazlı, ~12/gün/tesis |
| OKUMA | Rezervasyon (yeni/değişiklik/iptal) | Webhook (tercih) veya 15 dk poll |
| OKUMA | Envanter/müsaitlik anlık görüntüsü | Günlük |

### 3.3 Güvenlik & Uyum
- Kimlik doğrulama: OAuth2 client-credentials veya API key + IP allowlist
- Webhook: HMAC-SHA256 imza doğrulaması
- Veri: AB verisi AB bölgesinde işlenir; PII minimizasyonu (misafir verisi yalnız rezervasyon eşleme için)
- Fiyat kararları otel başına bağımsız üretilir; yalnız halka açık pazar fiyatları girdi alınır

### 3.4 Sertifikasyon Planı
1. Sandbox erişimi (hafta 1-2): adaptör eşleme + birim testleri
2. Uçtan uca test (hafta 3-4): 1 test oteli, 7 gün fiyat push + rezervasyon webhook doğrulaması
3. Pilot (hafta 5-8): 2-3 gerçek tesis, günlük mutabakat raporu
4. Genel kullanım: kademeli açılış, hacim limitleriyle

### 3.5 SSS'ye Hazır Cevaplar
- "Hata durumunda?" → Push başarısızsa 3 deneme (exponential backoff), sonra fiyat değişikliği geri alınır
  ve yöneticiye bildirim düşer; kanalda asla 'yarım' durum bırakılmaz.
- "Rate parity?" → Parite monitörümüz mevcut; kanal başına fence'li kampanyalar parite kurallarına uygun etiketlenir.
- "Ölçek?" → Şu an 13 tesis; adaptör katmanı tesis başına bağımsız kuyruk kullanır, yatay ölçeklenir.
