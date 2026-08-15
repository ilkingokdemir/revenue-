# UYUM İLKELERİ ANAYASASI (D1 — Rekabet Hukuku + KVKK/GDPR + EU AI Act)
Tarih: 2026-08-15 · Bu doküman mimari kararların anayasasıdır. Her yeni fiyatlama özelliği bu 6 ilkeye uymak zorundadır.

## 1. Yalnızca HALKA AÇIK fiyat girdisi
- Robot rakip fiyatı olarak SADECE halka açık kaynakları (resmi API, lisanslı rate shopper) kullanır.
- Oteller arası özel/paylaşılan veri (doluluk, gelecek fiyat niyeti, kontrat oranları) ASLA girdi olamaz.
- Kod kuralı: `market_robot` ve compset modülleri yalnızca `source: public|licensed` etiketli veriyi kabul eder.

## 2. Otel başına BAĞIMSIZ karar
- Her tesisin fiyat kararı yalnızca kendi verisi + halka açık pazar verisiyle üretilir.
- Havuzlanmış çok-otel verisi yalnızca ANONİM model eğitiminde kullanılır; asla "X oteli şu fiyatı verdi, sen de ver" koordinasyonuna dönüşemez.
- RealPage davası emsali: fiyat önerisi motoru hiçbir zaman oteller arası fiyat hizalama aracı olamaz.

## 3. Scraping — REVİZE (kullanıcı kararı 2026-08-15, rev.2)
- Kamuya açık OTA fiyatlarının YASAL TOPLANMASI (scraping) artık CANLI bir opsiyondur (rakip paritesi).
- İki kaynak modu: `scraper` (kendi canlı toplama, yalnızca halka açık fiyatlar) | `licensed` (lisanslı rate shopper — üretim hedefi).
- Kurallar: yalnızca herkese açık arama sonuçları; oturum/hesap arkası veri ASLA; hız sınırı ve robots duyarlılığı; kaynak etiketi (`scraped_live` / `licensed` / `mock`) zorunlu.
- Bot koruması engellerse otomatik mock_fallback + neden logu.

## 4. Açıklanabilirlik (EU AI Act)
- Her fiyat önerisi "neden" dökümüyle üretilir (OTB sapması, pickup hızı, LOS, tarih olayı, guardrail durumu).
- Tüm kararlar loglanır: `ai_pricing_decisions` (öneri + neden + freeze_reason + applied + kim onayladı).
- Kara kutu yok: onaylanmamış otonom fiyat değişimi ilk yıl kapalı (öneri modu varsayılan).

## 5. KVKK / GDPR
- PMS'ten çekilen misafir kişisel alanları fiyatlama pipeline'ına GİRMEZ (yalnızca anonim rezervasyon metrikleri).
- Mevcut gdpr/eu_compliance modülleri veri silme/anonimleştirme taleplerini karşılar.
- Pilot otel sözleşmesine veri işleme ek protokolü (DPA) eklenir.

## 6. Guardrail'ler modelden önce gelir
- Mutlak kurallar: min/max fiyat bandı (mevcut: min_rate_floors + LRV), tek adımda ±%15 üstü değişim yasak (YAPILACAK), günlük push limiti (YAPILACAK), anomali durumunda fiyat dondurma + insana sorma (mevcut: anomaly freeze).
- Guardrail ihlali = push iptal + bildirim. İstisna yok.

## Sözleşme maddeleri (pilot otel şablonuna eklenecek)
- A5: "Anonimleştirilmiş veriler model geliştirmede kullanılabilir" izni (soğuk başlangıç hendeği).
- C1: Vaka çalışması yayın hakkı + ölçüm protokolü (RGI pazar-düzeltmeli kıyas) kabulü.
- D2: KVKK veri işleme ek protokolü.
