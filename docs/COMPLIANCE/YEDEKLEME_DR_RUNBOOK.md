# Yedekleme & Felaket Kurtarma Runbook'u — MyHotelBox

**Sürüm:** 1.0 · **Tarih:** 2026-08-13 · **Sorumlu:** Teknik Operasyon

## 1. Hedefler

| Metrik | Hedef | Açıklama |
|---|---|---|
| **RPO** (Recovery Point Objective) | ≤ 24 saat | Kabul edilebilir maksimum veri kaybı |
| **RTO** (Recovery Time Objective) | ≤ 4 saat | Kesinti sonrası tam hizmete dönüş |
| Kritik akış RTO (rezervasyon alma) | ≤ 1 saat | Booking widget + ödeme öncelikli |

## 2. Veri Envanteri ve Yedekleme Stratejisi

| Veri | Yer | Yöntem | Sıklık | Saklama |
|---|---|---|---|---|
| Operasyonel DB (rezervasyon, misafir, anket, sosyal) | MongoDB | `mongodump` → şifreli obje depolama | Günlük 03:00 UTC | 30 gün |
| Yüklenen dosyalar (misafir fotoğrafları, sosyal görseller, PDF raporlar) | `/app/backend/uploads/` | rsync/objeye senkron | Günlük | 30 gün |
| Kod ve konfigürasyon | Git deposu | Her commit | Süresiz |
| Sırlar (.env) | Ortam değişkeni kasası | Manuel, değişimde | Son 3 sürüm |
| Ödeme kayıtları | Stripe (dış) | Stripe sorumluluğu | — |

Yedekleme komut örneği:
```bash
mongodump --uri "$MONGO_URL" --db "$DB_NAME" --archive=/backups/$(date +%F).gz --gzip
tar czf /backups/uploads-$(date +%F).tgz /app/backend/uploads
```

## 3. Kurtarma Prosedürleri

### 3.1 Veritabanı kaybı / bozulması
1. Trafiği bakım moduna al (ingress maintenance sayfası).
2. Son sağlıklı yedeği doğrula: `mongorestore --dryRun`.
3. Geri yükle: `mongorestore --uri "$MONGO_URL" --archive=<dosya> --gzip --drop`.
4. Smoke test: login → rezervasyon listesi → anket gönderimi → sosyal arşiv.
5. `sudo supervisorctl restart backend frontend` ve worker loglarını izle.

### 3.2 Uygulama pod'u / servis çökmesi
1. `sudo supervisorctl status` → başarısız servisi restart et.
2. Log incele: `tail -n 100 /var/log/supervisor/backend.err.log`.
3. Kubernetes seviyesinde pod yeniden planlama otomatiktir.

### 3.3 Dosya deposu (uploads) kaybı
1. Son uploads arşivini `/app/backend/uploads/`'a aç.
2. Eksik sosyal görseller yeniden üretilebilir (AI); misafir fotoğrafları
   yedekten döner, dönemezse ilgili taslaklar görselsiz işaretlenir.

### 3.4 Üçüncü taraf kesintileri
| Servis | Etki | Davranış |
|---|---|---|
| Stripe | Ödeme alınamaz | Pay-later rezervasyon devam eder; ödeme linki sonra gönderilir |
| Resend | E-posta gitmez | Kuyruk `queued` bekler, servis dönünce dispatcher otomatik gönderir |
| LLM (Emergent) | AI taslak/görsel üretimi durur | Şablon fallback'ler devrede; manuel taslak yazılabilir |

## 4. Tatbikat ve Doğrulama

- **Çeyreklik:** Yedekten test ortamına tam geri yükleme tatbikatı (sonuç kaydı bu dosyanın altına işlenir).
- **Aylık:** Yedek bütünlük kontrolü (`mongorestore --dryRun` + arşiv checksum).
- **Her dağıtımda:** Otomatik regresyon suite (`/app/backend/tests/`).

## 5. İletişim Zinciri

1. Teknik sorumlu → kesinti tespiti + bakım modu (0-15 dk)
2. Yönetim bilgilendirme + müşteri durum mesajı (15-30 dk)
3. Kurtarma uygulaması (30 dk - 4 sa) → çözüm sonrası RCA raporu (48 sa içinde)

## Tatbikat Kayıtları

| Tarih | Tür | Sonuç | Not |
|---|---|---|---|
| _(ilk tatbikat planlanacak)_ | | | |
