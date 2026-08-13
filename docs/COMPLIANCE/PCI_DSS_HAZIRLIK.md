# PCI-DSS Hazırlık Dokümantasyonu — MyHotelBox

**Sürüm:** 1.0 · **Tarih:** 2026-08-13 · **Kapsam Sahibi:** Platform Yönetimi
**Hedef Standart:** PCI DSS v4.0

---

## 1. Kapsam Tespiti (Scoping)

MyHotelBox, kart verisini **hiçbir zaman kendi sistemlerinde saklamaz, işlemez
veya iletmez**. Tüm ödeme akışları PCI DSS Level 1 sertifikalı sağlayıcı
**Stripe** üzerinden tokenizasyon ile yürütülür.

| Akış | Kart Verisi Nerede? | Platform Teması |
|---|---|---|
| Booking widget ödemesi | Stripe Checkout (hosted) | Yalnızca session_id / payment_intent id |
| Pay-by-Link | Stripe hosted link | Yalnızca link URL ve durum webhook'u |
| Depozito / no-show tahsilatı | Stripe saved payment method (token) | Yalnızca pm_ token referansı |
| İade | Stripe API (token ile) | Kart numarası hiç görülmez |

**Sonuç:** Platform, kartla temas etmeyen "tamamen dış kaynaklı" model olduğu
için **SAQ-A** (Self-Assessment Questionnaire A) kapsamına girer.

## 2. SAQ-A Gereksinim Karşılama Matrisi

| PCI Gereksinimi | Durum | Uygulama |
|---|---|---|
| 2. Güvenli yapılandırma | ✅ | Tüm sırlar .env'de; kodda hardcoded kimlik bilgisi yok |
| 6. Güvenli yazılım | ✅ | Bağımlılıklar requirements.txt/yarn.lock ile sabit; düzenli güncelleme |
| 8. Kimlik doğrulama | ✅ | JWT + bcrypt hash; rol bazlı erişim (admin/manager/staff) |
| 9. Fiziksel erişim | ➖ | Bulut sağlayıcı sorumluluğu (Kubernetes, yönetilen altyapı) |
| 11. Güvenlik testleri | 🔶 | Otomatik regresyon test suite mevcut; yıllık pentest planlanmalı |
| 12. Politika | 🔶 | Bu doküman temel; resmi InfoSec politikası yazılmalı |

✅ karşılanıyor · 🔶 kısmi / aksiyon gerekli · ➖ sağlayıcı sorumluluğu

## 3. Teknik Kontroller (Mevcut Durum)

- **Şifreleme (aktarımda):** Tüm trafik TLS ile sonlandırılır (ingress).
- **Sır yönetimi:** `MONGO_URL`, `STRIPE_API_KEY`, `EMERGENT_LLM_KEY`,
  `RESEND_API_KEY` yalnızca ortam değişkenlerinde; repoya yazılmaz.
- **Erişim kontrolü:** `require_roles()` dekoratörü ile endpoint bazlı RBAC;
  misafir (public) uçları yalnızca token/QR doğrulamalı anket, şikayet takip,
  galeri ve oylama ile sınırlıdır.
- **Oturum:** JWT süreli token; parolalar bcrypt ile saklanır.
- **Loglama:** `hardening` middleware her isteğe request_id, path, status,
  latency yazar (denetim izi).
- **Webhook doğrulama:** Stripe webhook imza kontrolü ile işlenir.

## 4. Aksiyon Planı (Denetime Kadar)

| # | Aksiyon | Öncelik | Sorumlu |
|---|---|---|---|
| 1 | SAQ-A formunun resmi olarak doldurulup imzalanması | P0 | Yönetim |
| 2 | Stripe hesabında ASV taraması onayı (Stripe sağlar) | P0 | Teknik |
| 3 | Yıllık sızma testi (3. taraf) sözleşmesi | P1 | Yönetim |
| 4 | Resmi Bilgi Güvenliği Politikası + çalışan eğitimi kaydı | P1 | İK/Yönetim |
| 5 | Olay müdahale (incident response) runbook'u | P1 | Teknik |
| 6 | Erişim gözden geçirme takvimi (çeyreklik kullanıcı/rol denetimi) | P2 | Teknik |

## 5. Kart Verisi Akış Şeması (Özet)

```
Misafir tarayıcısı ──kart verisi──▶ Stripe (hosted checkout / link)
        │                                 │
        └──── session_id ────▶ MyHotelBox ◀── webhook (imzalı, kartsız) ──┘
```

Platform veritabanında (MongoDB) saklanan ödemeyle ilgili tek veri:
işlem kimliği, tutar, durum, tarih. **PAN, CVV, son kullanma tarihi asla.**
