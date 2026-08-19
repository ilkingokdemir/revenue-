# DERİN GAP ANALİZİ — Mews & Cloudbeds Baz Alınarak (2026-08-19)

Referans: Mews Hospitality Cloud (Connector/POS/CM/BE API'leri, 1000+ marketplace, Mews Payments,
event-driven webhooks/WebSocket) ve Cloudbeds (tek veri modeli, 450+ OTA CM, Booking Engine,
Cloudbeds Payments PCI-L1, Guest Experience/Whistle, Signals AI, 50+ açık API çağrısı, 450+ marketplace).

## SONUÇ ÖZETİ
Modül GENİŞLİĞİMİZ (280+) Mews/Cloudbeds'i aşıyor; ancak onları "gerçek ürün" yapan şey
DERİNLİK: canlı para akışı, canlı kanal senkronu, dışa açık API ekosistemi ve platform işletim
(süper admin/faturalama) katmanı. Bizim en büyük riskimiz: birçok kritik akışın MOCK olması.

---
## P0 — MÜŞTERİYE SERVİS İÇİN OLMAZSA OLMAZ (bunlar olmadan yazılımın sahada karşılığı yok)

### P0-1. CANLI KANAL/PMS SENKRONU (en kritik — kullanıcının işaret ettiği nokta)
- Durum: Cloudbeds/Mews/Apaleo/SiteMinder push-pull altyapısı HAZIR ama TÜMÜ MOCK (API key yok).
- Mews/Cloudbeds farkı: iki yönlü GERÇEK senkron (fiyat+müsaitlik+rezervasyon) + overbooking koruması.
- Yapılacak: (a) müşteri kimlik bilgisi girme sihirbazı + canlı sertifikasyon zorunluluğu (var),
  (b) rezervasyon PULL'unu sürekli robota bağlama (delta sync + webhook dinleme),
  (c) çift yönlü çakışma çözümü (son yazan kazanır + audit).
- Bağımlılık: GERÇEK API anahtarları (Cloudbeds key, Mews AccessToken — demo token mümkün).

### P0-2. ÖDEME ALTYAPISI (Cloudbeds Payments / Mews Payments muadili)
- Durum: YOK (folio/kasa var ama gerçek tahsilat yok). Ortamda Stripe TEST key hazır.
- Yapılacak: Stripe entegrasyonu — booking engine'de kart tahsilatı, pay-by-link,
  depozito/no-show charge, iade; folio ile otomatik mutabakat.

### P0-3. DIŞA AÇIK API + WEBHOOK EKOSİSTEMİ (Mews Connector API muadili)
- Durum: Dev Portal (kayıt/login/API key) VAR, webhooks route VAR — ama dokümante edilmiş
  stabil bir "Public API v1" yüzeyi (rezervasyon/fiyat/misafir CRUD + OpenAPI spec) eksik.
- Yapılacak: /api/public/v1/* (API key auth, rate limit, OpenAPI dokümanı),
  giden webhook dispatcher (reservation.created, rate.updated, guest.updated) + retry.

### P0-4. SÜPER ADMİN / PLATFORM KONSOLU (biz = SaaS sağlayıcı)
- Durum: Provizyon (plan=full, apply-all) VAR; ama platform sahibi için tenant konsolu eksik.
- Yapılacak: super_admin rolü; tüm oteller listesi (kullanım, son giriş, sağlık skoru),
  impersonation (otel hesabına gir), plan/askıya alma, SaaS abonelik faturalama (Stripe subscription).

### P0-5. VERİ GÖÇÜ (MIGRATION) SİHİRBAZI
- Durum: YOK. Yeni müşteri mevcut PMS'inden (rezervasyon/misafir/fiyat) veriyle gelir.
- Yapılacak: CSV/Excel import (rezervasyon, misafir, oda tipleri) + Mews/Cloudbeds'ten API ile çekme.

---
## P1 — REKABET İÇİN GEREKLİ (Mews/Cloudbeds'te standart)

- P1-1. Gerçek mesajlaşma kanalları: unified inbox VAR ama WhatsApp/SMS MOCK → Twilio entegrasyonu.
- P1-2. Online check-in + dijital anahtar: kiosk view VAR; misafir tarafı self-service akışı gerçek değil.
- P1-3. E-posta altyapısı: Resend MOCK → gerçek key + rezervasyon onay/hatırlatma şablonları.
- P1-4. Overbooking koruması: kanal bazlı allotment/stop-sell kuralları (stop-sell temeli kuruldu).
- P1-5. Muhasebe dışa aktarımı: e-fatura/CSV export (Xero/QuickBooks formatı).
- P1-6. Güvenlik: 2FA, oturum yönetimi, IP kısıtı; granüler RBAC (roles.py var, genişletilmeli).
- P1-7. Housekeeping mobil PWA görünümü (saha personeli telefondan kullanır).
- P1-8. Rate limit + API kullanım ölçümü (dev portal'a usage metering).

## P2 — FARK YARATAN (bizde kısmen var, cilalanmalı)
- Marketplace (marketplace.py VAR — 3. parti uygulama listesi ve OAuth akışı eksik)
- WebSocket gerçek zamanlı panolar; POS API'sinin dışa açılması
- Çoklu para birimi/dil (TR/EN var); status page + SLA; Signals AI muadili (bizde DAHA GÜÇLÜ — RMS/AI pricing avantajımız)

## GÜÇLÜ OLDUĞUMUZ ALANLAR (Mews/Cloudbeds'e karşı avantaj)
- RMS/AI Pricing derinliği (rakip tetiği, ısı haritası, doluluk kuralları, shadow mode, simülatör)
- PMS-agnostik middleware (onlar tek platform, biz üstlerine bağlanıyoruz)
- Rapor merkezi (PDF üretimi), Sağlık Nöbetçisi, 280+ modül genişliği

## ÖNERİLEN SIRA
1) P0-2 Stripe ödemeleri (test key hazır — hemen yapılabilir)
2) P0-3 Public API v1 + giden webhooks
3) P0-4 Süper Admin konsolu + SaaS faturalama
4) P0-5 Veri göçü sihirbazı
5) P0-1 canlı senkron (müşteri API anahtarları geldikçe sertifikasyonlu açılır)
