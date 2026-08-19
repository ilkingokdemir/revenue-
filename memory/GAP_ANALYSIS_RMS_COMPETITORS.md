# DERİN RMS GAP ANALİZİ — FLYR · Duetto · IDeaS · RoomPriceGenie · PriceLabs (2026-06)

Amaç: "Sadece RMS almak isteyen otel" bizden hesap açtığı ANDA sorunsuz hizmet alabilmeli.
Referans mimariler aşağıda; her başlıkta bizdeki karşılık ve eksik işaretlendi.

---
## 1) RAKİP MİMARİLERİ (özet)

### FLYR Hospitality (eski Pace) — "AI-native karar motoru"
- Saatlik sürekli fiyatlama (tüm oda tipi × rate kodu × LOS), kural değil RL + Bayesian ML.
- Ensemble forecast + belirsizlik bandı, 2 yıl ileri; GEÇMİŞ VERİ GEREKTİRMEZ (day-1 pricing).
- "Management by exception": manuel override AI'ya sinyal olur, strateji adapte olur.
- OTB verisi 25–50 dk tazelik; optimizasyon ayrı near-real-time akış.
- 4 modül: Optimize / Insights / Planning / Groups. 2 haftada go-live.

### Duetto GameChanger (RP-OS)
- Open Pricing: segment × kanal × oda tipi × tarih bağımsız fiyat; min/max sınırlar.
- ScoreBoard: gün-seviyesi forecast (SmartSpread ML), portföy/tesis görünümü.
- BlockBuster: grup displacement + grup wash azaltma + AI grup fiyat önerisi.
- Veri: web shopping regrets/denials, sosyal yorumlar, rakip fiyat, loyalty verisi.
- AutoPilot: kılavuz sınırlar içinde kontrollü otomasyon. 100+ HTNG iki-yön entegrasyon.

### IDeaS G3 (SAS)
- 100+ forecast modeli (transient/grup/wholesale ayrı), dynamic-programming optimizasyon.
- Grup değerlendirme: gerçek-zaman displacement, Wish/Walk fiyatı, onay iş akışı.
- Function space RM (F&B + yan gelir dahil kârlılık), overbooking optimizasyonu
  (iptal/no-show/wash tahminli; kapalı rakip sayısına göre eşik ayarı).
- RevPlan (bütçe/plan tek kaynak), Spotlight (raporlama), 330 gün pace, 250+ entegrasyon.
- ADA/connector oda tiplerinin kapasite dağıtımı gibi ince inventory kuralları.

### RoomPriceGenie — "küçük otelin RMS'i; 30 dk kurulum"
- Baz fiyat (entry-level oda) → diğer oda tipleri % / tutar FARKI ile türetilir.
- Autopilot (otomatik push, günde 24'e kadar) vs Co-Pilot (önce onay).
- Min/max eşikler, doluluk hedefi, agresiflik ayarı, kişi-sayısı bazlı fiyat.
- Surge protection: beklenmedik talep sıçramasında alarm + koruma fiyatı.
- 90+ PMS entegrasyonu, 18 ay ileri fiyat, kurulum ~30 dk + 1 hafta içinde tam canlı.

### PriceLabs — "portföy + hiper-lokal nabız"
- Hyper Local Pulse algoritması: hiper-lokal talep + event fiyatlaması.
- Market Dashboards: compset benchmark, pacing, booking window, LOS desenleri.
- Portfolio Analytics: RevPAR/ADR/OCC hedef takibi + doğal dilde AI sorgu.
- 30+ özelleştirme: STLY tabanlı emniyet taban fiyatı, tarih override, ünite offset.
- Min-stay öneri motoru (gap night azaltma), POBA (portföy doluluğuna göre kalan
  üniteleri otomatik zamlama), Smart Presets (tesis tipine göre hazır strateji).

---
## 2) BİZDE OLANLAR (rakip paritesi — GÜÇLÜ YANLAR)
| Rakip özelliği | Bizdeki karşılık | Durum |
|---|---|---|
| Duetto Open Pricing | open_pricing.py (segment×kanal matrisi) | VAR |
| FLYR 18-24 ay forecast | forecast_v2.py (24 ay) + base_price_curve (18 ay) | VAR |
| Duetto BlockBuster | group_displacement + group_sales (RFP) + los_wash_metrics | VAR |
| IDeaS grup Wish/Walk | hurdle_lrv.py (hurdle & LRV) + displacement | VAR (kısmi) |
| IDeaS function space RM | function_space.py + revpam.py | VAR |
| Duetto regrets/denials | lost_demand.py | VAR |
| IDeaS overbooking | overbooking_control.py (wash tahminli) | VAR |
| FLYR backtest/deney | simulator.py (replay backtest) + rm_lab | VAR |
| Guardrail/onay/shadow | trust_center.py + decision_assurance.py | VAR |
| PriceLabs NL sorgu | bi_chat.py (Veriye Sor) | VAR |
| RPG intraday reprice | intraday_reprice.py (pickup spike) | VAR |
| Rakip fiyat & parite | compset, rate_scraper, parity heatmap, comp trigger | VAR |
| Min-stay/CTA önerisi | restriction_advisor.py (MLOS/CTA) | VAR |
| RevPlan bütçe | budget-actual paneli | VAR |
| STLY emniyet tabanı | min_rate_floors.py | VAR (STLY kuralı yok) |
| Autopilot | pricing_autopilot (scheduler tick) | VAR (mod kavramı eksik) |

---
## 3) EKSİKLER — "RMS-only müşteriye ANINDA hizmet" için

### P0 — hesap aç → hemen çalışsın (olmazsa olmaz)
1. **RMS planı yok.** Plan seti basic/pro/full; "sadece RMS" isteyen otel için `rms` plan
   tipi + RMS'e özel menü kapsamı gerekli (PMS modülleri gizli/kilitli).
2. **RMS Hızlı Kurulum Sihirbazı yok (RPG'nin 30 dk kurulumu).** Tek akışta:
   oda tipleri + baz fiyat → oda tipi FARKLARI (%/tutar) → min-max guardrail →
   compset seçimi → veri kaynağı (PMS bağla VEYA CSV VEYA manuel doluluk) →
   mod seçimi (Autopilot / Co-Pilot / Manuel) → GO-LIVE kontrol listesi.
3. **Pricing Mode kavramı eksik.** Tesis bazında `autopilot | copilot | manual` modu +
   push kadansı (1×/gün … 24×/gün). Co-Pilot = öneriler ONAY KUYRUĞUNA düşer,
   onaylanınca push edilir (RPG/Duetto AutoPilot paritesi).
4. **Oda tipi türetilmiş fiyat (base + offset) motoru eksik.** RPG'nin çekirdeği:
   entry oda fiyatı değişince tüm oda tipleri offset kuralıyla otomatik türesin.
5. **Go-Live sağlık kontrolü RMS'e özel değil.** "Fiyat var mı, compset var mı,
   guardrail var mı, veri akışı taze mi (FLYR 25-50dk), push hedefi bağlı mı" skoru.

### P1 — rekabette standart
6. **Surge Protection** (RPG): talep sıçramasında alarm + otomatik koruma tavanı.
   (price_alerts.py var → surge kuralı eklenmeli.)
7. **POBA** (PriceLabs): portföy doluluğu eşiği aşınca kalan envantere otomatik zam.
8. **Smart Presets** (PriceLabs): tesis tipine göre (şehir/resort/apart/B&B) hazır
   strateji şablonu — sihirbazda tek tık.
9. **STLY tabanlı emniyet taban fiyatı** (PriceLabs): min_rate_floors'a STLY kuralı.
10. **Veri tazeliği göstergesi** (FLYR): OTB son senkron yaşı UI'da rozet.

### P2 — cila
11. Forecast belirsizlik bandı (FLYR ensemble) — forecast_v2'ye ±band.
12. Loyalty fiyatlaması (Duetto) — segment matrisine loyalty tier bağlama.
13. Management-by-exception: manuel override'ların AI'ya öğrenme sinyali olması.
14. ADA/connector oda kapasite dağıtımı (IDeaS niş kuralı).

---
## 4) SONUÇ
Analitik ÇEKİRDEK (forecast, open pricing, grup, guardrail, backtest) rakip seviyesinde
veya üstünde. Eksik olan ÜRÜNLEŞTİRME katmanı: RMS-only plan, 30-dk kurulum sihirbazı,
Autopilot/Co-Pilot modu, oda tipi offset motoru ve go-live sağlık skoru.
Bunlar tamamlanınca "hesap aç → 30 dk'da fiyatlamaya başla" vaadi verilebilir.
