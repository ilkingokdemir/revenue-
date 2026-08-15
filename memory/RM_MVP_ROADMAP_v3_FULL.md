# REVENUE MANAGEMENT — KAPSAMLI MVP + YOL HARİTASI (v3 FULL)
Tarih: 2026-08-15 · TÜM RM modülleri, robotlar, butonlar ve dağıtım katmanı dahil.
Envanter: 70 backend RM modülü (routes/revenue_ext + distribution) + 45+ panel butonu.

═══════════════════════════════════════════════════════
# BÖLÜM 1 — MVP: BUGÜN ÇALIŞAN TAM ENVANTER
═══════════════════════════════════════════════════════

## 1.1 🤖 ROBOTLAR ve OTOMASYON AJANLARI (tümü MVP'de)
| Robot | Modül | Ne yapar | Buton |
|---|---|---|---|
| Revenue Robotu (Beyin) | revenue_brain | Öğrenilmiş çarpanlar, kapalı döngü öğrenme, bölgesel+küresel hafıza, onboarding turu, katkı grafiği | revenue-brain |
| AI Fiyatlama Motoru | ai_pricing_engine | Net RevPAR hedefli 90g öneri + guardrail + oto-uygulama + rollback | ai-pricing-v2 |
| Pazar Robotu | market_robot | Halka açık pazar arz/fiyat taraması (geo scan), compset snapshot | (dashboard kartları + revenue) |
| Gece Denetim Robotu | night_audit (morning-report) | Gün sonu gelir/doluluk/ADR/anomali + sabah bildirimi | morning-report |
| Wash Uyarı Robotu | workers.run_group_wash_check | Cutoff −14g erime bildirimi | (bildirim) |
| Kanal Sapma Robotu | hotelrunner drift_autopush | Sapma bulunca otomatik düzeltme push'u | hotelrunner-live |
| Pazarlama Fırsat Radarı | marketing_radar | Düşük doluluk pencerelerine kampanya önerisi (arka plan) | marketing-radar |
| Anomaly Radar | (engine _detect_anomaly + panel) | Rakip verisi saçmalama / OTB sıçrama → fiyat dondurma | anomaly |
| Talep Radarı | demand_radar | Pickup ivmesi + talep sinyal birleştirme | demand-calendar içinde |
| Gün-içi Re-price | intraday_reprice | Pickup spike → gün içi yeniden fiyat | intraday-reprice |
| Data Quality Autopilot | data_quality | Veri kalite kontrolleri, eksik/sapan veri uyarısı | data-quality |
| Decision Assurance | decision_assurance | Kanıtlı autopilot — karar denetim zinciri | decision-assurance |
| Teklif Takip Robotu | workers.proposal_reminder | 3g yanıtsız fonksiyon teklifine hatırlatma | function-space |
| Shadow Mode Robotu | workers.shadow_mode_loop | Günlük öneri snapshot'ı (push YOK) | trust-center |
| BI Chat (Veriye Sor) | bi_chat | Doğal dille veri sorgulama (GPT) | bi-chat |
| Revenue Copilot / Stratejist | revenue_copilot, revenue_strategist | AI strateji önerileri + direktifler | copilot / strategy |
| RM Uzmanlık Kütüphanesi | rm_expertise, rm_knowledge_seed | RM bilgi tabanı (AI ajan bağlamı) | — |

## 1.2 💰 FİYATLAMA ÇEKİRDEĞİ
- ai_pricing_engine: Net RevPAR (komisyon+ödeme+iade+promo+CPOR), lead-time/occ/STR/öğrenilmiş çarpanlar, LOS enjeksiyonu
- open_pricing: Open Pricing matrisi (oda tipi × kanal × tarih bağımsız fiyat) — open-pricing
- dynamic_pricing + smart_rate_control: dinamik kurallar + akıllı fiyat kontrolü
- base_price_curve: 18 aylık baz fiyat eğrisi — base-curve
- profit_pricing: kâr-öncelikli fiyatlama (CPOR, kanal kesintileri) — profit-pricing
- discount_stack: indirim katmanları + net fiyat — discount-stack
- min_rate_floors + hurdle_lrv: minimum fiyat koruması + hurdle rate & LRV — min-rates / hurdle-lrv
- los_optimizer + los_wash_metrics: LOS optimizasyonu + 3+/7+ kademe + tek tık widget fence — los-wash-metrics
- rate_manager / rates_grid / rate_structure: fiyat yöneticisi, günlük grid (My Rates), rate planları
- historical_pricing: geçmiş fiyat/performans bağlamı
- price_alerts: fiyat uyarıları
- pricing_explain: AI fiyat açıklayıcı (faktör kırılımı) — pricing-explain
- restriction_advisor: AI MLOS/CTA/CTD kısıt önerileri — restriction-advisor
- parking_rms: Otopark RMS (oda dışı gelir) — parking-rms

## 1.3 📈 TAHMİN (FORECAST) PAKETİ
- forecast_v2: 24 aylık forecast (hava + tatil + hafta yapısı) — forecast-v2
- forecast_plans: forecast sürümleme + onay akışı — forecast-plans
- room_type_forecast: oda tipi bazlı forecast — room-type-forecast
- ml_pickup: pickup tahmini (ML) · forecast_accuracy: MAPE/MAE doğruluk takibi
- net_otb: beklenen NET OTB (p_cancel, lead-time kovalı) — trust-center
- lost_demand: kayıp talep (denials & regrets) + widget oto-log — lost-demand
- demand_calendar: talep ısı haritası + AI yorum + orphan gap doldurma — demand-calendar

## 1.4 🏢 GRUP + MICE + FONKSİYON GELİRİ
- group_sales: Group Sales OS (RFP pipeline) — group-sales
- group_displacement + displacement: grup displacement analizi — group-displacement
- los_wash_metrics (grup wash) + overbooking_control: wash & overbooking kontrol — overbooking-control
- function_space: teklif→rezervasyon motoru + RevPAM + takvim + PDF + kazanma analizi — function-space
- revpam: toplantı salonu RevPAM analizi — revpam
- abs_selling: özellik bazlı satış (ABS) — abs-selling
- Grup alternatif tarih önerisi (±30 gün)

## 1.5 🌐 DAĞITIM ve KANAL (distribution/)
- hotelrunner_live: CANLI ARI push + rezervasyon çekme + sapma tablosu + oto re-push — hotelrunner-live
- siteminder_adapter: inbound adaptör · channel_manager + channels_v2 + channel_hub: kanal yönetimi
- channel_parity + parity_analysis + competitor_parity: parity monitor + heatmap — channel-parity / parity-heatmap
- channel_revenue: kanal yield yönetimi — channel-revenue
- channel_health + ota_health: kanal/OTA sağlık merkezi
- ota_stop_sell_forecast: OTA stop-sell tahmini — ota-forecast
- allotments: tur operatörü kontenjanları · wholesaler: toptancı ağı · agency_portal: acente portalı
- booking_com + two_way_sync + push_history + channel_inbound/mappings/restrictions
- public_events: halka açık etkinlik sinyalleri (event robotu girdisi) — public-events

## 1.6 🔎 PAZAR İSTİHBARATI (compset)
- compset + compset_intel + comp_radar: compset yönetimi + istihbarat — compset
- str_market: canlı STR (Airbnb/tatil evi) baskı sinyali (<48s)
- rate_scraper: fiyat tarama altyapısı (MOCK — canlıda lisanslı kaynak, D4 scraping yasak)
- market_robot: geo pazar taraması

## 1.7 🛡 GUARDRAIL + GÜVEN (trust)
- trust_center: ±%15 adım limiti + günlük push limiti + ihlal logu + kabul oranı (%70 hedef) + shadow mode — trust-center
- Anomali dondurma + unfreeze + 1-tık rollback-run
- revenue_protection: gelir koruma kuralları — rev-protection
- leakage: gelir sızıntısı denetçisi — leakage-audit
- UYUM_ILKELERI_D1.md: rekabet hukuku + KVKK + EU AI Act anayasası

## 1.8 📊 ÖLÇÜM ve RAPORLAMA
- rgi_proof: RGI pazar endeksi kanıt paneli (pazara göre düzeltilmiş) — rgi kanıt
- key_figures: anahtar göstergeler — key-figures
- los_wash_metrics: TRevPOR / RevPAG / GOPPAR + hedefli trend — los-wash-metrics
- revenue / revenue_advanced / revenue_intelligence / revenue_phase2 / revenue_health: RM ana panelleri
- revenue_exports: rapor dışa aktarma · Exec Report PDF (haftalık) + arşiv
- night_audit (morning-report): gün sonu raporu
- owner_rates / owner_summary / owner_pulse: sahip fiyat panosu + aylık özet (yatırımcı tarafı)
- strategy_directives: strateji direktifleri · Competitor Comparison + Demo Mode + ROI hesaplayıcı (landing)

## MVP BAŞARI KRİTERLERİ (3 aylık pilot)
1. Öneri kabul oranı ≥%70 (trust-center canlı izleme)
2. 90 günde sıfır guardrail ihlalli push
3. RGI endeksi şehir kıyasında pozitif
4. Pickup MAE'de naive baseline'a karşı ≥%25 iyileşme
5. Kanal sapması: parity monitor ±%5 içinde

═══════════════════════════════════════════════════════
# BÖLÜM 2 — YOL HARİTASI (kalan işler)
═══════════════════════════════════════════════════════

## FAZ 0 — Ticari Kritik Yol (ŞİMDİ — kullanıcı aksiyonu)
- [ ] C2 Kanal yöneticisi partner başvurusu GÖNDER (şablon: PARTNER_BASVURU_KANAL_YONETICISI.md)
- [ ] HotelRunner HR_ID+TOKEN → hotelrunner_live anında CANLI
- [ ] C1 1-3 pilot otel · C3 niş kararı (TR 50-200 oda) · C4 birim ekonomi
- [ ] Resend API anahtarı (e-postalar MOCK) · Expo token (mobil derleme MOCK)

## FAZ 1 — MVP Cilası (1-2 hafta kod)
- [ ] G5 İptal modeli isotonic kalibrasyonu + aylık oto yeniden kalibrasyon
- [ ] G3 Compset girdilerine kaynak etiketi (public|licensed) zorunluluğu
- [ ] Pilot Otel Kiti (sözleşme + veri izni A5 + KVKK D2 + vaka çalışması)
- [ ] Event Robotu güçlendirme: public_events → talep takvimi + fiyat motoruna otomatik etkinlik çarpanı

## FAZ 2 — Simülatör + Backtest (3-6 hafta)
- [ ] G7 Talep simülatörü (MNL + iptal modeli + rakip kuralı)
- [ ] Politika backtesti: robot vs sabit fiyat vs "dün+%X"
- [ ] Shadow Mode 4 haftalık gerçek pilot verisi

## FAZ 3 — Pilot Canlı (8-12 hafta, Faz 0 onayına bağımlı)
- [ ] Kanal CANLI yazma → 4 hafta shadow → onaylı canlı mod
- [ ] RGI ölçümü + vaka çalışması

## FAZ 4 — Ürünleşme (3-6 ay)
- [ ] G8 Lisanslı rate shopping (rate_scraper mock → gerçek) + rakip-tepki guardrail'i
- [ ] G9 %5-10 kontrollü fiyat randomizasyonu (esneklik öğrenimi)
- [ ] G10 Havuz veri + transfer learning (soğuk başlangıç)
- [ ] Güven eşikli otonom mod · Overbooking önerisi (kalibre olasılıkla)
- [ ] Çok-otel RM dashboard'u (zincir görünümü)

## BİLİNÇLİ YAPILMAYACAKLAR
Derin öğrenme (şimdilik) · Kafka/mikroservis · rakibe otomatik fiyat tepkisi · scraping · çok segmentli genel ürün.
