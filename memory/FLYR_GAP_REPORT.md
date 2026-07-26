# FLYR Hospitality (flyrhospitality.com) — İnceleme Raporu & Fark Analizi
Tarih: 2026-07-26 (iter 449) · Kaynak: flyrhospitality.com ana sayfa + /optimize + /planning

## FLYR Nedir?
AI-first "revenue strategy" platformu (eski adıyla Pace Revenue). 2.300+ tesis, Best Western,
Premier Inn, Ennismore gibi zincirler kullanıyor. 4 ürün sütunu:
1. **Optimize** — saatlik AI fiyatlama + kısıtlama (MLOS/CTA) önerileri, %98 kabul oranı,
   "strategic influences" (kural yazmadan AI'ı yönlendirme), açıklanabilir AI (karar soy kütüğü).
2. **Insights** — doğal dilde BI sohbeti ("RevPAR'ı geçen hafta ne sürükledi?"), rol bazlı
   panolar, planlı rapor dağıtımı, PMS+rate shopper+market data tek katmanda.
3. **Planning** — gün & segment seviyesinde AI forecast (2 yıl ileri, birkaç saatte bir güncel),
   ensemble model + belirsizlik ölçümü, senaryo stres testi, forecast doğruluk takibi,
   **rolling + kilitli sürümler**, yorum/görev, onay iş akışı, bütçe vs forecast vs actual dağıtımı.
4. **Groups** — gerçek zamanlı grup displacement analizi, karma (blended) fiyat optimizasyonu,
   taahhüt öncesi forecast etkisi, enquiry-to-conversion hızlandırma.

## Bizde ZATEN OLANLAR (FLYR eşleniği)
| FLYR özelliği | Bizdeki karşılık |
|---|---|
| AI fiyat önerileri + kabul/ret | ai_pricing_engine.py + rates_grid (öneri akışı) |
| Açıklanabilir AI ("neden bu fiyat?") | pricing_explain.py (anlatı + sürücü dökümü) |
| NL BI sohbeti | revenue_copilot.py (GPT tabanlı) |
| 2 yıl forecast + segment dökümü | forecast_v2.py (horizon, segments, demand-calendar) |
| Forecast doğruluk takibi | forecast_accuracy.py (snapshot + trust score) |
| Grup displacement analizi | displacement.py |
| Bütçe vs actual | budget_actual.py |
| Planlı rapor dağıtımı | scheduled_reports + weekly_report |
| Rol bazlı panolar | custom dashboards + RBAC perm map |
| Agresiflik ayarı (strategic influence, kısmî) | dynamic_pricing.py aggressiveness |
| Kısıtlama yönetimi | channel_restrictions (manuel; AI önerisi yok) |

## Bizde OLMAYAN ve FAYDA SAĞLAYACAK özellikler (öncelik sıralı)
1. ✅ **Forecast Planlama Çalışma Alanı** (Planning paritesi) — sürümleme, taslak/kilitli ayrımı,
   ekip düzeltmesi (AI'ı "challenge" etme), yorum, onay akışı, sürüm karşılaştırma.
   → **iter 449'da YAPILDI**: revenue_ext/forecast_plans.py + ForecastPlansPanel.
2. **Saatlik / gün-içi yeniden fiyatlama tetikleyicisi** — bizim motor günlük cron; FLYR saatlik.
   Gün içi pickup sıçramasında anında re-price (örn. 2 saatte bir hafif tarama) eklenebilir.
3. **AI kısıtlama önerileri (MLOS/CTA)** — restrictions manuel; talep sinyaline göre MLOS
   önerisi üretip onayla-push akışı eklenebilir.
4. **Forecast belirsizlik bandı (ensemble)** — forecast'a alt/üst güven aralığı eklenebilir.
5. **Grup blended-rate optimizasyonu** — displacement var; segment karışımına göre önerilen
   grup fiyatı + taahhüt öncesi forecast etkisi simülasyonu eklenebilir.
6. **Bütçe vs Forecast vs Actual üçlü görünüm + planlı dağıtım** — budget_actual + forecast_plans
   birleştirilebilir (tek tablo + haftalık e-posta).

## Sonuç
Platformumuz FLYR'ın Insights ve Optimize sütunlarının büyük kısmını zaten karşılıyor.
En büyük gerçek boşluk Planning sütunuydu — iter 449 ile kapatıldı. Kalan 2-6 maddeleri
ROADMAP'e eklendi.
