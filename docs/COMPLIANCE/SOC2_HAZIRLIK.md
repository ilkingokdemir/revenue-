# SOC 2 Hazırlık Dokümantasyonu — MyHotelBox

**Sürüm:** 1.0 · **Tarih:** 2026-08-13
**Hedef:** SOC 2 Type I (ardından 6-12 ay gözlem ile Type II)
**Kapsam Kriterleri:** Güvenlik (zorunlu) + Erişilebilirlik + Gizlilik

---

## 1. Sistem Tanımı

MyHotelBox; otel işletmeleri için PMS/RMS, kanal yönetimi, AI destekli misafir
iletişimi ve sosyal medya otomasyonu sunan çok kiracılı (multi-property) bir
SaaS platformudur.

- **Mimari:** React SPA + FastAPI + MongoDB (Kubernetes üzerinde)
- **Veri sınıfları:** Misafir PII (ad, e-posta, telefon), rezervasyon verisi,
  yorum/anket içerikleri, misafir fotoğrafları (açık izinli), operasyonel veri
- **Alt işleyiciler:** Stripe (ödeme), Resend (e-posta), OpenAI/Google
  (AI üretimi — Emergent LLM proxy), Meta (opsiyonel sosyal paylaşım)

## 2. Trust Services Criteria Karşılama Matrisi

### CC — Ortak Kriterler (Güvenlik)

| Kriter | Kontrol | Durum |
|---|---|---|
| CC6.1 Mantıksal erişim | JWT + bcrypt, RBAC (`require_roles`), rol matrisi | ✅ |
| CC6.6 Dış tehditler | Ingress TLS, public uçlarda token doğrulama, oy/istek sınırlama (IP bazlı) | ✅ |
| CC6.7 Veri aktarımı | Tüm API trafiği HTTPS; sırlar .env | ✅ |
| CC7.2 İzleme | Request-id'li yapısal loglama, supervisor süreç izleme | ✅ |
| CC7.3/7.4 Olay yönetimi | SLA takibi ve bildirim altyapısı mevcut; resmi IR planı yazılmalı | 🔶 |
| CC8.1 Değişiklik yönetimi | Git tabanlı sürümleme + her değişiklikte otomatik regresyon (testing suite) | ✅ |
| CC9.2 Tedarikçi riski | Alt işleyici listesi bu dokümanda; DPA'lar toplanmalı | 🔶 |

### A — Erişilebilirlik

| Kriter | Kontrol | Durum |
|---|---|---|
| A1.1 Kapasite | Kubernetes yatay ölçekleme; arka plan işleri async worker döngüleri | ✅ |
| A1.2 Yedekleme | MongoDB yönetilen yedekleme politikası belgelenmeli | 🔶 |
| A1.3 Kurtarma | DR runbook'u mevcut: YEDEKLEME_DR_RUNBOOK.md (RTO ≤4sa / RPO ≤24sa) | ✅ |

### P — Gizlilik (Misafir PII)

| Kriter | Kontrol | Durum |
|---|---|---|
| P1-P2 Bildirim/Onay | Anket fotoğrafı için **açık izin checkbox'ı**; izinsiz fotoğraf asla sosyal akışa girmez | ✅ |
| P4 Kullanım sınırı | Fotoğraflar yalnızca izinli galeride/paketlerde; galeri sayfasında izin beyanı görünür | ✅ |
| P5 Saklama | Veri saklama süreleri politikası yazılmalı (ör. anket PII 24 ay) | 🔶 |
| P6 Silme | Misafir verisi silme endpoint'i (POST /api/gdpr/erasure — PII anonimleştirme + fotoğraf dosyası silme) | ✅ |

## 3. Mevcut Teknik Kontrollerin Kanıt Haritası

| Kontrol | Kanıt (kod/dosya) |
|---|---|
| RBAC | `require_roles` bağımlılığı — tüm yönetim endpoint'leri |
| Parola güvenliği | bcrypt hash (auth modülü) |
| İstek sınırlama | `photo_votes` IP-hash dedupe + günlük 20 oy sınırı |
| Denetim izi | `hardening` middleware request loglama |
| Otomatik test | `/app/backend/tests/` + `/app/test_reports/` (iteration 503-505, %100) |
| İzinli içerik | `photo_consent` alanı; `guest-photos` yalnızca consent=true döner |
| Sır yönetimi | `.env` + ortam değişkeni okuma, kodda default fallback yok |

## 4. Denetim Öncesi Aksiyon Planı

| # | Aksiyon | Öncelik |
|---|---|---|
| 1 | Resmi Bilgi Güvenliği Politikası seti (erişim, şifre, cihaz, uzaktan çalışma) | P0 |
| 2 | Olay Müdahale Planı + yıllık tatbikat kaydı | P0 |
| 3 | Alt işleyici DPA/sözleşmelerinin dosyalanması (Stripe, Resend, Meta) | P0 |
| 4 | Yedekleme & felaket kurtarma runbook'u (RTO/RPO) | P1 |
| 5 | Veri saklama/silme politikası + misafir verisi silme endpoint'i | P1 |
| 6 | Çeyreklik erişim gözden geçirme kaydı | P1 |
| 7 | Type I denetim firması seçimi ve boşluk analizi (gap assessment) | P2 |

## 5. Yatırımcı Özeti

- Kart verisi platforma **hiç girmez** (Stripe tokenizasyon → SAQ-A).
- Misafir fotoğrafları **yalnızca açık izinle** kullanılır; izin beyanı hem
  ankette hem galeri sayfasında görünürdür.
- Tüm yönetim uçları rol bazlı korunur; public uçlar dar kapsamlı ve
  hız sınırlıdır.
- Sürekli otomatik regresyon testi kültürü mevcuttur (500+ iterasyon).
- Kalan işler ağırlıklı olarak **politika/dokümantasyon** niteliğindedir;
  mimari değişiklik gerektiren kritik boşluk tespit edilmemiştir.
