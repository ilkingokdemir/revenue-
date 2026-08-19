# RAKİP KARŞILAŞTIRMA RAPORU — Cloudbeds & Mews (Site Menüleri) vs Bizim Platform (2026-06)

Kaynak: Kullanıcının paylaştığı cloudbeds.com ve mews.com ekran görüntüleri (Platform/Solutions menüleri).
Yöntem: Menüdeki her ürün/hizmet, kod tabanındaki modüllerle tek tek eşleştirildi.

## 1) CLOUDBEDS PLATFORM MENÜSÜ
| Cloudbeds | Bizde | Durum |
|---|---|---|
| PMS | 280+ modüllü PMS (rezervasyon, takvim, ön büro, night audit) | ✅ VAR |
| Payments | Stripe checkout + pay-by-link + preauth + card_vault + chargeback | ✅ VAR (fiziksel terminal hariç) |
| Insights & Reporting | Analytics, custom dashboards, scheduled reports, BI chat | ✅ VAR |
| Channel Manager | channel_hub, mappings, two_way_sync, CM Hızlı Kurulum, iCal | ✅ VAR |
| Booking Engine | Direct Booking (widget, promo, gift cards) | ✅ VAR |
| Distribution Partners | Connector Catalog (Cloudbeds/Mews/Apaleo) + 8 kanal kataloğu | 🟡 KISMİ (canlı push API anahtarı bekliyor; partner ağı ölçeği küçük) |
| Guest Communication & Digital Check-in | messaging, unified inbox, WhatsApp, guest-checkin link | ✅ VAR |
| Revenue Intelligence | RMS paketi (AI pricing, forecast, compset) — rakipten derin | ✅ VAR (üstün) |
| Guest Marketing CRM | crm_360, segments, campaigns, loyalty v2 | ✅ VAR |
| Digital Marketing | campaigns, ab_test, attribution, web_push, nudge | 🟡 KISMİ (Google/Meta reklam API entegrasyonu YOK) |
| **Websites (site oluşturucu)** | og_images + booking widget var; tam web sitesi oluşturucu YOK | ❌ EKSİK (P1) |
| Reputation Management | reviews, review_autopilot, AI yanıt robotu | ✅ VAR |
| App Marketplace | marketplace.py + Connector Catalog | 🟡 KISMİ (ekosistem genişliği: onlarca vs 450+/1000+) |
| API Docs / Become a Partner | Public API + Dev Portal + webhooks + partner başvurusu | ✅ VAR |
| Onboarding / University / Help Center | property_onboarding, mews_university, help-guide, setup wizard | ✅ VAR |
| **Signals AI (foundation AI modeli)** | AI pricing, BI chat, ai_predictions, pos_ai — dağınık, tek marka değil | 🟡 KISMİ (işlev var; tek "AI markası" çatısı yok) |

## 2) MEWS PLATFORM MENÜSÜ
| Mews | Bizde | Durum |
|---|---|---|
| Reservation Management | BookingTimeline + rezervasyon modülleri | ✅ VAR |
| Upsells | upsell_engine, extras v1/v2 | ✅ VAR |
| Housekeeping | housekeeping, hk_dispatch, hk_turnover, route optimizer | ✅ VAR |
| Guest Intelligence | crm_360, risk_score, segments, guest incidents | ✅ VAR |
| Accounting & Billing | accounting, folio_split, city_ledger, tax v2, P&L | ✅ VAR |
| Booking Engine + Guest Check-In | Direct Booking + guest-checkin | ✅ VAR |
| ePOS | fnb_pos_hub, fnb_tabs, beach_pos, menu_engineering, pos_ai | ✅ VAR |
| Embedded Payments | Stripe embedded (checkout, pay-by-link, rezervasyon içi ödeme) | ✅ VAR |
| Tokenization | card_vault | ✅ VAR |
| Automated Reconciliation | bank_reconciliation, ar_recon_agent, commission_recon | ✅ VAR |
| Multicurrency | currency_fx | ✅ VAR |
| **Terminals (fiziksel POS terminali)** | YOK — Stripe Terminal entegre değil | ❌ EKSİK (P1) |
| **Flexible Financing (YouLend)** | YOK — işletme finansmanı ortaklığı | ❌ EKSİK (P2, niş) |
| Dynamic Pricing / Forecasting / Portfolio & Group Pricing | RMS paketi + Grup Satış OS + POBA — rakipten derin | ✅ VAR (üstün) |
| Open API / Developer Docs / Security / Data | Public API, dev portal, webhooks, RBAC v2, 2FA | ✅ VAR |
| Marketplace (1000+ entegrasyon) | marketplace + katalog | 🟡 KISMİ (ölçek farkı) |
| Solutions by Property Type (hostel/motel/extended stay...) | property_type alanı var; tipe özel hazır şablon/preset yok | 🟡 KISMİ (P2: Smart Presets) |
| Solutions by Role (GM/Revenue/Finance/IT/F&B/MICE) | custom_dashboards + department_shortcuts | 🟡 KISMİ (role hazır dashboard preset'i yok) |

## 3) SONUÇ — EKSİK LİSTESİ (öncelikli)
❌ P1-1. **Otel Web Sitesi Oluşturucu** (Cloudbeds "Websites", TBF paritesi): şablon seçimi + içerik + booking widget gömme + yayınlama.
❌ P1-2. **Fiziksel Ödeme Terminali** (Mews "Terminals"): Stripe Terminal entegrasyonu (resepsiyon kartlı cihaz).
🟡 P2-1. **Reklam Entegrasyonu** (Digital Marketing): Google Ads / Meta kampanya bağlantısı (şimdilik UTM + attribution ile kısmi).
🟡 P2-2. **AI Marka Çatısı** (Signals AI paritesi): dağınık AI modüllerini tek "AI Copilot" markası + tek panel altında toplamak.
🟡 P2-3. **Tesis Tipi & Role Hazır Preset'ler**: hostel/apart/extended-stay şablonları + role-based dashboard preset'leri.
🟡 P2-4. **Esnek Finansman** (YouLend): 3. parti finansman ortaklığı — niş, ertelenebilir.
🟡 P2-5. **Ekosistem Genişliği**: marketplace konnektör sayısını büyütme (iCal ile API'siz kanallar kapandı; canlı OTA/PMS anahtarları gelince genişler).

## 4) BİZİM ÜSTÜN OLDUĞUMUZ ALANLAR (menü karşılaştırmasında rakipte görünmeyen)
- RMS derinliği: comp trigger, heatmap, simulator/backtest, trust center, hurdle/LRV, Fiyat Bekçileri (POBA+Surge), Co-Pilot onay kuyruğu
- Grup Satış OS + displacement + wash metrikleri (Duetto/IDeaS seviyesi; Cloudbeds/Mews menüsünde yok)
- iCal çifte rezervasyon alarmı + tek tık çözüm sihirbazı
- Self-signup + 14 gün deneme + plan kilitleri (rms/cm/pro/full) — Cloudbeds/Mews'te demo talebi zorunlu
- Health Sentinel, Data Quality Nöbetçisi, Süper Admin sağlık skorları
- Kâr-öncelikli fiyatlama (profit_os), ABS (attribute-based selling)
