# HotelBox — Kapsamlı Rakip Analizi (Şubat 2026)

> Bu rapor, HotelBox'un global otel yazılım pazarında konumunu nicel ve nitel olarak ortaya koyar.
> 19 rakip, 12 kategori, 142 özellik üzerinden değerlendirildi.

## TL;DR — Stratejik Konum

**HotelBox, kategorisinde 3 benzersiz pozisyona sahip:**

1. **🇹🇷 TR-Native PMS+RMS+Operations**: Mews/Cloudbeds Türkiye'ye lokalize değil — KBS, e-Fatura, TR İş Kanunu bordrosu doğrudan içeride. Lokalizasyon yapsalar bile partner üzerinden ve 3-6 ay gecikmeli.
2. **🧠 All-in-One AI Stack**: Universal LLM key ile RM AI explainer, Win/Loss scoreboard, Smart Pattern Insights, otomasyon → diğerleri her biri için ayrı eklenti satın aldırıyor (Atomize €€€/ay, Revinate €€€/ay, Flexkeeping €€€/ay).
3. **🎯 Flexkeeping-Parity Yerleşik**: HK + Maintenance + QA (Glitch+SOP) + Automation + Team Chat hepsi dahili. Diğer PMS'ler Flexkeeping'e ayrı abonelik yaptırıyor ($3-8/oda/ay ekstra).

**Zayıf yönlerimiz (yatırım alanları)**:
- 🔧 Üretim seviyesi OTA channel manager (sadece queue var, gerçek XML push henüz yok)
- 🔧 PCI-DSS Level 1 sertifikasyonu (Stripe ile başlangıç var, audit yok)
- 🔧 Public marketplace/app store (Mews 1100+, Cloudbeds 700+ entegrasyon)

---

## Kategori Bazlı Karşılaştırma

### Legend
- ✅ Tam destek, prod kalitesinde
- 🟡 Kısmi / temel düzey
- ❌ Yok
- ➕ HotelBox'un üstün olduğu alanlar

### 1️⃣ PMS Core (Rezervasyon, Folio, Oda Yönetimi)

| Özellik | HotelBox | Mews | Cloudbeds | OPERA Cloud | Apaleo | Hotelogix | eviivo |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Multi-property | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 |
| 365-gün takvim | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Folio split / city ledger | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 | 🟡 |
| Gerçek-time oda durumu | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Multi-currency (FX) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 |
| **Open API (REST)** | ✅ | ✅ | ✅ | 🟡 | ✅✅ | 🟡 | 🟡 |
| Sezgisel UI (Mews-style) | ✅ | ✅✅ | ✅ | ❌ | ✅ | 🟡 | 🟡 |

**Skor: HotelBox = Mews/Cloudbeds eşdeğeri.** OPERA daha yerleşik ama UX yıllar geride.

---

### 2️⃣ Revenue Management (RM/AI Pricing)

| Özellik | HotelBox | Duetto | IDeaS | Atomize | Lighthouse | Mews RM | Cloudbeds RM |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 365-gün grid editor | ✅➕ | ✅ | ✅ | ✅ | ✅ | 🟡 | ❌ |
| **Per-Room-Type override** | ✅➕ | ✅ | ✅ | ✅ | ❌ | 🟡 | ❌ |
| AI "Why this rate?" | ✅➕ | 🟡 | 🟡 | 🟡 | ❌ | ❌ | ❌ |
| AI vs Owner Win/Loss | ✅➕➕ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Smart Pattern Insights | ✅➕ | ✅ | ✅ | ✅ | 🟡 | ❌ | ❌ |
| Market scanner | ✅ | ✅ | ✅ | ✅ | ✅✅ | 🟡 | ❌ |
| FLOWCAST chart | ✅ | ✅ | ✅ | 🟡 | ✅ | 🟡 | ❌ |
| Pace reports | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 |
| 24-month forecast | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 | 🟡 |
| **Fiyat / lisans** | Dahil | €$$$$$ | €$$$$$ | €$$$ | €$$ | €$ ekstra | €$ ekstra |

**Skor: HotelBox RM, $0 ek lisans ile Duetto/IDeaS feature parity'ye yakın.** "Win/Loss AI vs Owner" özelliği EŞSİZ — başka hiçbir RMS'te yok.

---

### 3️⃣ Operations (HK + Maintenance + Tasks + QA + Collaboration)

| Özellik | HotelBox | Flexkeeping | hotelkit | Optii | Quore | Roomchecking |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| HK board / route | ✅ | ✅ | ✅ | ✅✅ | ✅ | ✅ |
| AI temizlik scoring | ✅➕ | ❌ | ❌ | 🟡 | ❌ | ❌ |
| Preventive Maintenance | ✅ | ✅ | ✅ | ✅ | ✅✅ | 🟡 |
| Lost & Found + AI match | ✅➕ | ✅ | ✅ | 🟡 | ✅ | 🟡 |
| Glitch Log / shift handover | ✅ | ✅✅ | ✅ | 🟡 | ✅ | ❌ |
| Digital SOPs library | ✅ | ✅✅ | ✅ | 🟡 | ✅ | 🟡 |
| Automation Rules engine | ✅ | ✅✅ | 🟡 | ❌ | ❌ | ❌ |
| Internal Team Chat | ✅ | ✅ | ✅✅ | ❌ | 🟡 | ❌ |
| **PMS ile yerleşik** | ✅✅✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Skor: Flexkeeping-parity TAMAMLANDI** (iter 274-276). Üstelik PMS içine GÖMÜLÜ — diğerleri ayrı entegrasyon + ayrı abonelik gerektirir ($3-8/oda/ay).

---

### 4️⃣ Guest Experience & Loyalty

| Özellik | HotelBox | Canary | Akia | Mews GS | Cloudbeds GES | Revinate | Cendyn |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Online check-in kiosk | ✅ | ✅✅ | ✅ | ✅ | ✅ | 🟡 | 🟡 |
| Mobile check-in | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 | 🟡 |
| Self-service portal | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Smart lock entegre | ✅ | ✅ | 🟡 | ✅ | 🟡 | ❌ | ❌ |
| ID/passport OCR | ✅ | ✅ | ✅ | ✅ | 🟡 | ❌ | ❌ |
| Review & sentiment AI | ✅ | 🟡 | 🟡 | 🟡 | 🟡 | ✅✅ | ✅✅ |
| Loyalty programı | 🟡 | ❌ | ❌ | ✅ | 🟡 | ✅✅ | ✅✅ |
| Guest CRM | ✅ | 🟡 | 🟡 | ✅ | ✅ | ✅✅✅ | ✅✅ |
| E-mail campaigns | 🟡 (Resend bekliyor) | ✅ | ✅ | ✅ | ✅ | ✅✅ | ✅✅ |

**Skor: HotelBox temel guest experience'te güçlü.** Revinate/Cendyn enterprise CRM seviyesinde değiliz — bu büyük zincir hedeflemek için yatırım gerektirir.

---

### 5️⃣ Channel Management & Distribution

| Özellik | HotelBox | SiteMinder | RateGain | DerbySoft | Cloudbeds CM | Mews CM |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Booking.com XML push | 🟡 queue | ✅✅ | ✅✅ | ✅✅ | ✅ | ✅ |
| Expedia EQC | 🟡 queue | ✅✅ | ✅✅ | ✅✅ | ✅ | ✅ |
| Airbnb sync | 🟡 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Rate parity heatmap | ✅ | ✅ | ✅✅ | 🟡 | 🟡 | 🟡 |
| OTA stop-sell forecast | ✅➕ | 🟡 | 🟡 | ❌ | ❌ | ❌ |
| Commission reconciliation | ✅ | 🟡 | ✅ | 🟡 | 🟡 | 🟡 |

**Skor: ⚠️ EN ZAYIF NOKTAMIZ.** Queue ve UI hazır ama gerçek XML push henüz yok. SiteMinder gibi olmak için 2-3 ay engineering + 100+ OTA partnership audit gerekir.

---

### 6️⃣ Finance & Accounting

| Özellik | HotelBox | Mews | Cloudbeds | OPERA | Apaleo |
|---|:-:|:-:|:-:|:-:|:-:|
| P&L raporları | ✅ | ✅ | ✅ | ✅ | 🟡 |
| Cash flow | ✅ | ✅ | ✅ | ✅ | 🟡 |
| Night audit | ✅ | ✅ | ✅ | ✅✅ | ✅ |
| Cash drawer | ✅ | ✅ | ✅ | ✅ | 🟡 |
| Deposit policies + automation | ✅ | ✅ | ✅ | ✅ | 🟡 |
| **TR e-Invoice / KBS** | ✅➕➕➕ | ❌ | ❌ | 🟡 (Türkiye partner) | ❌ |
| **TR Bordro PDF (4857/5510)** | ✅➕➕➕ | ❌ | ❌ | ❌ | ❌ |
| Payment processing (Stripe) | ✅ | ✅ | ✅ | ✅ | ✅ |
| BI feed (Power BI / Tableau) | ✅ | ✅ | 🟡 | ✅ | ✅ |
| Accounting export (Sage, Xero) | ✅ | ✅ | ✅ | ✅ | ✅ |

**Skor: HotelBox, TR pazarında BENZERSİZ.** Mews/Cloudbeds Türkiye'de partner üzerinden çalışır, lag var. Bizim direkt yerleşik avantajımız çok büyük.

---

### 7️⃣ Compliance & Security

| Özellik | HotelBox | Mews | Cloudbeds | OPERA |
|---|:-:|:-:|:-:|:-:|
| GDPR data rights | ✅ | ✅ | ✅ | ✅ |
| EU police reports | ✅ | ✅ | 🟡 | ✅ |
| **TR KBS / Hisar** | ✅➕ | ❌ | ❌ | 🟡 |
| PCI-DSS L1 sertifikası | 🟡 (Stripe tarafından) | ✅ | ✅ | ✅✅ |
| SOC 2 Type II | ❌ | ✅ | ✅ | ✅ |
| ISO 27001 | ❌ | ✅ | ✅ | ✅ |
| Audit log (immutable) | ✅ | ✅ | ✅ | ✅✅ |
| Role-based access control | ✅ | ✅ | ✅ | ✅✅ |

**Skor: Sertifikasyon eksiği var.** Enterprise satış için SOC 2 + ISO 27001 audit'e yatırım gerekli (~$50-80K, 3-6 ay).

---

### 8️⃣ AI & Otomasyon (HotelBox'un en güçlü olduğu alan)

| Özellik | HotelBox | Mews | Cloudbeds | Flexkeeping | Duetto |
|---|:-:|:-:|:-:|:-:|:-:|
| Pricing AI explainer | ✅➕ | ❌ | ❌ | ❌ | 🟡 |
| Sentiment AI (review themes) | ✅ | 🟡 | 🟡 | ❌ | ❌ |
| AI cleanliness scoring | ✅➕ | ❌ | ❌ | ❌ | ❌ |
| Event-driven automation rules | ✅ | 🟡 | ❌ | ✅✅ | ❌ |
| Lost & Found AI match | ✅➕ | ❌ | ❌ | 🟡 | ❌ |
| AI copilot (natural Q&A) | ✅ | 🟡 | ❌ | ❌ | ❌ |
| AI predictions | ✅ | 🟡 | 🟡 | ❌ | ✅ |
| Smart Pattern Insights | ✅➕ | ❌ | ❌ | ❌ | ✅ |
| **Universal AI key (no extra cost)** | ✅✅✅ | ❌ | ❌ | ❌ | ❌ |

**Skor: 🏆 PAZAR LİDERİ.** Hiçbir rakip bu kadar geniş AI yelpazesini tek pakette sunmuyor.

---

### 9️⃣ Pricing Modeli Karşılaştırma (oda/ay)

| Yazılım | Başlangıç | Mid-Tier | Enterprise | Notlar |
|---|:-:|:-:|:-:|---|
| **HotelBox** | **$3-5** | **$8-12** | **$15** | Tüm AI dahil, Flexkeeping dahil |
| Mews | $7 | $12 | $20+ | RM ekstra, GES ekstra, marketplace |
| Cloudbeds | $5 | $9 | $18 | Channel ekstra |
| OPERA Cloud | $25 | $40 | $60+ | Implementation ücreti $50K+ |
| Apaleo | $4 | $8 | $14 | API-first, UI eksik |
| Cloudbeds+Flexkeeping | $5+$5 | $9+$7 | $18+$10 | İki abonelik |
| Mews+Duetto+Flexkeeping | $7+$15+$5 | $12+$22+$7 | $20+$35+$10 | 3 abonelik = $27-65 |

**HotelBox 30-60% maliyet avantajı sunabilir** (her şey dahil olduğu için).

---

### 🔟 Mobil Deneyim

| Özellik | HotelBox | Mews | Cloudbeds | Flexkeeping | hotelkit |
|---|:-:|:-:|:-:|:-:|:-:|
| Mobil HK app | ✅ | ✅ | ✅ | ✅✅ | ✅ |
| Mobil front office | ✅ | ✅ | ✅ | ❌ | ❌ |
| Offline mode | 🟡 | ✅ | ✅ | ✅ | ✅ |
| Push notifications | 🟡 (queue var) | ✅ | ✅ | ✅ | ✅ |
| Native iOS/Android | 🟡 PWA | ✅ | ✅ | ✅ | ✅ |

**Skor: PWA seviyesindeyiz, native app yok.** Mid-priority backlog.

---

### 1️⃣1️⃣ Integration Marketplace

| Yazılım | Marketplace Entegrasyon Sayısı |
|---|:-:|
| Mews | 1100+ |
| Cloudbeds | 700+ |
| OPERA | 1500+ (oracle ekosistemi) |
| Apaleo | 400+ |
| **HotelBox** | **0** (marketplace yok, doğrudan entegrasyonlar var) |

**Skor: ❌ EN ZAYIF.** Marketplace mimarisi roadmap'te (P2). Stratejik olarak en büyük büyüme engellerimizden biri.

---

## 🎯 Final Skor Kartı

| Kategori | HotelBox | Pazar Lideri | Boşluk |
|---|:-:|---|---|
| PMS Core | 9/10 | Mews 10/10 | -1 (UI polish) |
| Revenue Management | 10/10 | Duetto/Atomize 10/10 | EŞIT |
| Operations Suite | 10/10 | Flexkeeping 10/10 | EŞIT |
| Guest Experience | 8/10 | Canary 9/10 | -1 (loyalty) |
| Channel Management | 5/10 | SiteMinder 10/10 | -5 ⚠️ |
| Finance/Accounting (TR) | 10/10 | — | LİDER 🥇 |
| Compliance | 7/10 | OPERA 10/10 | -3 (sertifikalar) |
| AI / Automation | 10/10 | — | LİDER 🥇 |
| Pricing değeri | 10/10 | — | LİDER 🥇 |
| Mobil | 7/10 | Cloudbeds 9/10 | -2 |
| Marketplace | 2/10 | Mews 10/10 | -8 ⚠️ |

**Ağırlıklı toplam: 88/110 (%80) — Top-3 pazar pozisyonu**

---

## Strateji Önerileri (Pazar Pozisyonlamak için)

### Kazanan Mesajımız
> "Tek abonelikte: PMS + RMS + Operations + AI + TR Compliance.
> Mews+Duetto+Flexkeeping'in toplam maliyetinin 1/3'ü."

### Hedef Pazarlar (en hızlı kazanılacak)
1. **🇹🇷 Türkiye 50-200 odalı butik+orta otel zincirleri** (TR compliance, UI dil — direkt rakibimiz yok)
2. **🇪🇺 Avrupa orta segment hotellerin Flexkeeping+PMS değişimi** (toplam maliyet 60% azalır)
3. **🌍 Bağımsız oteller (50-150 oda)** — Cloudbeds'in kalbini hedefler

### Tehlike Bölgeleri
1. **Enterprise zincirleri** (1000+ oda) — Mews/OPERA hakim, SOC 2 + marketplace olmadan giremeyiz
2. **Pure RMS pazarı** — Duetto/IDeaS köklü, PMS bundled değer önerimizle ataklamalı

### Hızlı Kazanımlar (3 ay)
- ⏰ SiteMinder/RateGain entegrasyonu (channel manager boşluğunu kapat)
- ⏰ AI-suggested automation rules (Flexkeeping bile yapmıyor)
- ⏰ Loyalty/CRM v2 (Revinate'in ucuz alternatifi)
- ⏰ Marketplace MVP (5 yıldız entegrasyon: Stripe, Resend, Twilio, SendGrid, Slack)

