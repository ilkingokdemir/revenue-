# TEKNİK SÖZLEŞME DOKÜMANLARI (K15) — D1 Anayasasının Teknik Ekleri
Tarih: 2026-08-15 · Üç sözleşme tek dosyada.

## 1. CONFIDENCE-SEMANTICS (Güven Semantiği Sözleşmesi)
- Her fiyat önerisi `confidence ∈ [0.05, 0.95]` taşır; asla 1.0 olamaz (model kibri yasak).
- Skor bileşenleri (toplamsal): baz 0.40 + iptal örneklemi ≥100 (+0.15) + OTB sinyali (+0.15)
  + tarih ≤30g (+0.15) + STR sinyali (+0.10) + öğrenilmiş çarpan (+0.05) − veri-güven düşük (−0.20).
- Anlamlar: ≥0.70 yeşil (oto-uygulamaya uygun) · 0.50-0.69 amber (insan onayı önerilir) ·
  <0.50 gri (UI soluk gösterir, oto-uygulama YASAK).
- Her skorun yanında `evidence[]` (dayanak listesi) zorunludur; kanıtsız skor geçersizdir.

## 2. PRICE-DOMAIN-CONTRACT (Fiyat Alanı Sözleşmesi)
- Fiyat her zaman: `min_rate_floor ≤ fiyat ≤ ceil_rate` ve LRV tabanının üstünde.
- Tek adım değişim: `−max_down_pct ≤ Δ% ≤ +max_up_pct` (vars. ±%15; cold-start: −0/+10).
- Cold-start: <100 rezervasyonlu tesiste indirim kilitli.
- Günlük push limiti (vars. 50) aşımı = BLOK. Kill switch aktifken push = BLOK.
- Her kırpma/blok `guardrail_violations`'a yazılır; sessiz düzeltme yasaktır.
- Fiyat şelalesi (`waterfall[]`) her öneri için üretilir: Baz→Lead→Doluluk(net)→Öğrenilmiş→Etkinlik/limit,
  ₺ delta + ara toplam; şelale toplamı nihai fiyata eşit olmak ZORUNDADIR.

## 3. RATE-PROVENANCE (Veri Kaynağı Sözleşmesi)
- Her rakip/pazar fiyat verisi kaynak etiketi taşır: `scraped_live` (kamuya açık canlı toplama) |
  `licensed` (lisanslı feed) | `mock` / `mock_fallback` (sentetik).
- Etiketsiz veri fiyat kararına GİREMEZ. mock_* etiketli veri canlı push kararında ağırlık taşıyamaz.
- Scraper yalnızca herkese açık arama sonuçlarını toplar; oturum arkası veri yasak; bot koruması
  algılanırsa otomatik mock_fallback + `fallback_reason` logu.
- İptal modeli tahminleri kalibrasyon damgası taşır (`cancel_calibration.calibrated_at`);
  90 günden eski kalibrasyon "bayat" sayılır ve veri-güven kapısında düşük güven üretir.
- Rezervasyonun kanal (`ota|direct`) ve iade (`ref|nonref`) sınıfları p_cancel'de izlenebilir olmalıdır.
