# Google Business Profile API — Erişim Onayı Başvuru Rehberi

Bu rehber, AI Yanıt Robotu'nun onaylanan yorum yanıtlarını Google'a otomatik
yayınlayabilmesi için gereken Google Business Profile (GBP) API erişiminin
nasıl alınacağını adım adım anlatır.

## Neden gerekli?
Google, işletme yorumlarına API üzerinden yanıt verilmesine yalnızca
onaylanmış Cloud projelerine izin verir. Sandbox/test ortamı yoktur.
Onay gelene kadar sistemimiz yanıtları güvenle **yayın kuyruğunda** bekletir.

## Ön Koşullar (başvurudan ÖNCE)
1. Google Business Profile'ınız (business.google.com) **en az 60 gündür
   doğrulanmış ve aktif** olmalı.
2. Otelinizi temsil eden yayında bir **web sitesi** olmalı.
3. Başvuruda kullanılacak e-posta, işletme profilinde **sahip (owner) veya
   yönetici (manager)** olmalı.

## Adım Adım Başvuru
### 1. Google Cloud Projesi
- https://console.cloud.google.com → "New Project" ile proje oluşturun.
- Dashboard'daki **Project Number**'ı not edin (başvuruda istenecek).

### 2. API Erişim Başvurusu
- https://developers.google.com/my-business/content/prereqs sayfasındaki
  **GBP API contact form** bağlantısını açın.
- Formu, profilde sahip/yönetici olan Google hesabıyla doldurun:
  - Proje numarası
  - İşletme web sitesi
  - Kullanım amacı: "Responding to customer reviews via our hotel
    management platform" yazabilirsiniz.

### 3. Onay Kontrolü (genelde ~2 hafta)
- Cloud Console → APIs & Services → **Quotas**
- Kota **0 QPM** = henüz onay yok. **300 QPM** = onaylandı.

### 4. API'leri Etkinleştirme (onay sonrası)
- APIs & Services → Library'den şunları etkinleştirin:
  - Google My Business API
  - My Business Account Management API
  - My Business Business Information API

### 5. OAuth Yapılandırması
- APIs & Services → OAuth consent screen:
  - Uygulama adı, logo, ana sayfa
  - Gizlilik politikası + kullanım şartları URL'leri
  - Scope: `https://www.googleapis.com/auth/business.manage`
- Credentials → Create Credentials → **OAuth Client ID (Web application)**
- Redirect URI olarak platformumuzun callback adresi eklenecek
  (canlıya geçişte tarafımızdan verilecek).

### 6. Bize İletin
Şunları paylaşın:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

Biz de:
- `.env` içinde `GBP_LIVE=true` yaparız,
- OAuth bağlantı akışını açarız (tek seferlik "Google'a Bağlan" onayı),
- Kuyrukta bekleyen tüm yanıtlar otomatik yayınlanır.

## Sık Karşılaşılan Sorunlar
| Sorun | Çözüm |
|---|---|
| 403 / kota 0 | Proje henüz onaylanmadı veya API'ler etkin değil |
| Belirli otelde 403 | OAuth kullanıcısı o lokasyonda sahip/yönetici değil |
| Yanıt "REJECTED" | Google içerik politikası ihlali — metni yumuşatıp tekrar deneyin |
| Refresh token gelmedi | "prompt=consent" ile yeniden bağlanın |

## Önemli Notlar
- Yanıt limiti: **4096 bayt (UTF-8)** — sistemimiz otomatik kısaltır.
- `updateReply` mevcut yanıtın üzerine yazar; geçmiş sistemde saklanır.
- Google OAuth doğrulaması (consent screen verification) ayrı bir süreçtir;
  geniş kullanım öncesi Google scope gerekçesi ve demo video isteyebilir.
