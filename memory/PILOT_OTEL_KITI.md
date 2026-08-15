# PİLOT OTEL KİTİ — Sözleşme Paketi Taslağı
Tarih: 2026-08-15 · RM Robot pilot programı için hazır şablon (hukuk incelemesinden geçirilmeli).

## 1. PİLOT PROGRAM ÖZETİ
- Süre: 3 ay (4 hafta Shadow Mode + 8 hafta onaylı canlı mod)
- Ücret: [ücretsiz / %50 indirimli — karşılığı aşağıdaki 4-5-6. maddeler]
- Kapsam: AI fiyat önerisi (insan onaylı), guardrail koruması, kanal push (HotelRunner), haftalık rapor
- Başarı ölçümü: RGI pazar-düzeltmeli endeks + öneri kabul oranı ≥%70 + sıfır guardrail ihlali

## 2. TARAFLARIN YÜKÜMLÜLÜKLERİ
- SAĞLAYICI: kurulum (≤5 iş günü), eğitim (2 saat), 7/24 kill-switch erişimi, haftalık exec raporu
- OTEL: PMS/kanal erişim yetkisi, haftalık 15 dk geri bildirim görüşmesi, red nedenlerini işaretleme

## 3. GÜVENLİK ve KONTROL TAAHHÜTLERİ
- İlk 4 hafta SHADOW MODE: hiçbir fiyat otele sorulmadan değişmez
- Canlı modda: her öneri insan onaylı; adım limiti ±%15 (otel isterse daraltır); günlük push limiti;
  anomali dondurma; tek tuş KILL SWITCH oteldedir; 1-tık toplu geri alma
- Her fiyat kararının "neden" açıklaması ve denetim izi otele açıktır (EU AI Act uyumu)

## 4. VERİ İZNİ (A5 — havuz veri maddesi)
"OTEL, SAĞLAYICI'nın işbu sözleşme kapsamında işlenen rezervasyon ve fiyat verilerini
KİMLİKSİZLEŞTİRİLMİŞ ve TOPLULAŞTIRILMIŞ biçimde, tahmin modellerinin geliştirilmesi amacıyla
kullanmasına izin verir. Bu veri hiçbir koşulda (a) otel adıyla ilişkilendirilerek üçüncü taraflara
açıklanamaz, (b) başka otellerin fiyat kararlarına otel-özdeş girdi olarak beslenemez."

## 5. KVKK VERİ İŞLEME EK PROTOKOLÜ (D2 — DPA özeti)
- Roller: OTEL = veri sorumlusu, SAĞLAYICI = veri işleyen
- İşlenen veri: rezervasyon metrikleri (tarih, gece, tutar, kanal). MİSAFİR KİŞİSEL VERİSİ
  (ad, e-posta, telefon) fiyatlama hattına GİRMEZ.
- Saklama: sözleşme bitiminde 30 gün içinde silme/iade; silme talebi ≤72 saat
- Güvenlik: şifreli aktarım, erişim logu, alt-işleyen listesi yazılı onaya tabi
- İhlal bildirimi: farkına varmadan itibaren 72 saat içinde otele yazılı bildirim

## 6. VAKA ÇALIŞMASI ve REFERANS HAKKI (C1)
"OTEL, pilot sonunda elde edilen pazara-göre-düzeltilmiş sonuçların (RGI, doluluk, ADR trendi)
otel adı [belirtilerek / anonim 'X şehri Y odalı otel' olarak] pazarlama vaka çalışmasında
kullanılmasını kabul eder. Yayın öncesi metin onayı oteldedir (≤10 iş günü)."

## 7. ÖLÇÜM PROTOKOLÜ (itiraz edilemez kanıt için)
- Kıyas: otelin RGI endeksi (kendi RevPAR'ı / şehir ortalaması) pilot öncesi 3 ay vs pilot dönemi
- İkincil metrikler: kabul oranı, tahmin MAE, guardrail ihlali sayısı, parity sapması
- "RevPAR arttı" tek başına başarı sayılmaz; pazar-düzeltmeli fark esastır

## 8. FESİH ve SORUMLULUK
- OTEL 7 gün önceden bildirimle sebepsiz fesih hakkına sahiptir (pilot süresince)
- SAĞLAYICI sorumluluğu pilot dönem ücretiyle sınırlıdır; dolaylı zarar hariçtir
- Fiyat kararlarının nihai onayı OTEL'dedir (insan onaylı mod)

## EKLER
- EK-A: Kurulum kontrol listesi (PMS erişimi, HotelRunner HR_ID/TOKEN, oda envanteri, CPOR)
- EK-B: UYUM_ILKELERI_D1.md (uyum anayasası)
- EK-C: Haftalık rapor örneği (Exec Report PDF)
