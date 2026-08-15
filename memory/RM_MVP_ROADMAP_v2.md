# REVENUE MANAGEMENT — MVP TANIMI ve YOL HARİTASI (v2)
Tarih: 2026-08-15 · Kaynak: platform kod tabanı + rm_robot_mvp_roadmap.md gap analizi (iter 549 sonrası durum)

---

# 1. MVP TEZİ (tek cümle)
> "Robot her sabah 90 günlük fiyat önerir, her önerinin NEDENİNİ açıklar, guardrail'lerden geçirir,
> revenue manager tek tıkla onaylar, fiyat kanal yöneticisine yazılır — ve sonuç pazara göre
> düzeltilmiş RGI endeksiyle ölçülür."

---

# 2. MVP KAPSAMI — NE VAR? (✅ = kodda çalışıyor ve test edildi)

## 2.1 Veri Çekirdeği
- ✅ OTB (on-the-books) doluluk matrisi — tarih bazlı rezervasyon fan-out
- ✅ **Beklenen NET OTB**: rezervasyon başına p_cancel skoru (365g lead-time kovalı, Laplace düzeltmeli);
  motor brüt değil net dolulukla fiyatlar (`/api/net-otb/{pid}`)
- ✅ Dış talep sinyalleri: hava durumu + resmi tatil takvimi + hafta yapısı (forecast_v2)
- ✅ Canlı STR baskı sinyali (Airbnb/tatil evi müsaitlik + medyan fiyat, <48s taze)
- ✅ Pazar arzı taraması (geo scan, market_supply) — halka açık veri
- ✅ Kayıp talep logu (widget'ta müsaitlik yoksa otomatik kayıt)

## 2.2 Karar Motoru (ai_pricing_engine)
- ✅ **Net RevPAR hedef fonksiyonu**: kanal karması komisyon + ödeme + iade + promo kesintisi + CPOR
- ✅ Kural tablolu öneri: referans fiyat × lead-time × (net) doluluk × STR × öğrenilmiş çarpanlar
- ✅ Öğrenilmiş çarpanlar: yerel → bölgesel (×0.7) → küresel (×0.5) hafıza önseli (kapalı döngü)
- ✅ LOS kademeleri (3+/7+ gece) öneriye enjekte + tek tık widget fence uygulaması
- ✅ Grup wash projeksiyonu + erime uyarı robotu (cutoff −14 gün bildirimi)

## 2.3 Guardrail Katmanı (modelden önce, MUTLAK)
- ✅ Min/max fiyat bandı (min_rate_floors) + LRV (last room value) tabanı
- ✅ **±%15 tek adım limiti** (aşımı kırpılır + loglanır) — panelden ayarlanır
- ✅ **Günlük push limiti** (aşımı bloklanır + loglanır)
- ✅ Anomali dondurma: rakip verisi saçmalarsa / OTB ani sıçrarsa fiyat DONAR, insana sorar
- ✅ 1-tık toplu geri alma (rollback-run)
- ✅ İhlal logu (`guardrail_violations`) — Güven Merkezi'nde görünür

## 2.4 İnsan-Onay Döngüsü (human-in-the-loop)
- ✅ Öneri + "neden" dökümü (faktör kırılımı: ref × lead × occ × STR × öğrenilmiş) — EU AI Act uyumlu
- ✅ Tek tık kabul / red (red NEDENİ etiketli veri olarak saklanır)
- ✅ **Kabul oranı raporu**: haftalık kabul/oto/red grafiği, hedef ≥%70
- ✅ **Shadow Mode**: robot önerir, HİÇBİR ŞEY push edilmez; robot vs insan uyum raporu (4 haftalık pilot güveni)
- ✅ Oto-uygulama modu: eşik içi öneriler otomatik (opsiyonel, varsayılan KAPALI)

## 2.5 Kanal Yazma (dağıtım)
- ✅ HotelRunner ARI push adaptörü (fiyat+müsaitlik, canlı-hazır; kimlik girilince MOCK→CANLI)
- ✅ Fiyat sapma tablosu (kanal vs RMS, ±%5 eşik) + tek tık / otomatik yeniden push
- ✅ SiteMinder inbound adaptörü + parity monitor
- ✅ Partner başvuru şablonu hazır (PARTNER_BASVURU_KANAL_YONETICISI.md)

## 2.6 Ölçüm ve Raporlama
- ✅ RGI pazar endeksi kanıt paneli (pazara göre düzeltilmiş kıyas — "RevPAR arttı" değil, endeks)
- ✅ MAPE tahmin doğruluğu takibi + Error Sentinel
- ✅ Haftalık Exec Report PDF + arşiv
- ✅ Modern metrikler: TRevPOR / RevPAG / GOPPAR + hedefli trend grafiği
- ✅ Gece Denetim Robotu: gün sonu gelir/doluluk/ADR/anomali + sabah bildirimi
- ✅ Talep takvimi ısı haritası + AI yorum + orphan gap doldurma

## 2.7 Uyum (compliance)
- ✅ Uyum İlkeleri Anayasası (UYUM_ILKELERI_D1.md): halka açık veri, otel başına bağımsız karar,
  scraping yasağı, açıklanabilirlik, KVKK, guardrail önceliği
- ✅ GDPR/KVKK modülleri + audit trail

## MVP'de BİLİNÇLİ OLARAK YOK (erteleme)
- ❌ Varsayılan otonom fiyat (insan onayı zorunlu; oto-uygulama opsiyonel eşikli)
- ❌ Gerçek rakip fiyat verisi (mock compset; canlıda lisanslı rate shopper — G8)
- ❌ Derin öğrenme / LSTM (kural + hafif öğrenilmiş çarpan yeterli)
- ❌ Overbooking otomasyonu (skor raporlanır, limit kararı insanda)

## MVP BAŞARI KRİTERLERİ (3 aylık pilot)
1. Öneri kabul oranı ≥ %70 (panelde canlı izleniyor)
2. 90 günde SIFIR guardrail ihlalli push (ihlal logu boş kalmalı)
3. RGI endeksi şehir kıyasında pozitif fark
4. Tahmin MAE'sinde naive baseline'a karşı ≥%25 iyileşme

---

# 3. YOL HARİTASI

## FAZ 0 — Ticari Zemin (ŞİMDİ, kod değil — kullanıcı aksiyonu, kritik yol!)
- [ ] C2: Kanal yöneticisi partner başvurusunu GÖNDER (şablon hazır). Onay AYLAR sürebilir → en uzun iş.
- [ ] C1: 1-3 pilot otel görüşmesi (ücretsiz/indirimli pilot ↔ veri izni + vaka çalışması hakkı)
- [ ] C3: Niş kararını netleştir (öneri: TR 50-200 oda butik/orta + yerel kanal yöneticileri)
- [ ] C4: Birim ekonomi (oda/ay fiyat + rate shopper maliyeti)
- [ ] HotelRunner HR_ID + TOKEN → adaptör anında CANLI moda geçer

## FAZ 1 — MVP Cilası (1-2 hafta, kod)
- [ ] G5: İptal modeli isotonic kalibrasyonu + aylık otomatik yeniden kalibrasyon
- [ ] G3: Compset girdilerine kaynak etiketi zorunluluğu (public|licensed) — uyum anayasası gereği
- [ ] Pilot Otel Kiti: sözleşme taslağı (veri izni A5 + KVKK D2 + vaka çalışması maddeleri)

## FAZ 2 — Simülatör ve Backtest (3-6 hafta)
- [ ] G7: Talep simülatörü — MNL seçim modeli + iptal modeli + basit rakip kuralı
- [ ] Politika backtesti: robot vs sabit fiyat vs "dün+%X" (satış argümanı üretir)
- [ ] Shadow Mode 4 haftalık gerçek veri toplama (pilot otelde)

## FAZ 3 — Pilot Canlı (8-12 hafta, Faz 0 onayına bağımlı)
- [ ] Kanal yöneticisi CANLI yazma (kimlikler gelince)
- [ ] İlk 4 hafta shadow → sonra onaylı canlı mod
- [ ] RGI ölçümü + pilot sonu vaka çalışması

## FAZ 4 — Ürünleşme (3-6 ay)
- [ ] G8: Lisanslı rate shopping (mock compset değişir) + rakip-tepki guardrail'i
- [ ] G9: %5-10 kontrollü fiyat randomizasyonu ile esneklik öğrenimi (hacim + otel onayı şartıyla)
- [ ] G10: Havuz veri hendeği — 3. otelden itibaren transfer learning (soğuk başlangıç)
- [ ] Güven eşikli otonom mod (eşik üstü otomatik, altı insana)
- [ ] Overbooking önerisi (kalibre olasılıkla, insan onaylı)

## BİLİNÇLİ YAPILMAYACAKLAR
Derin öğrenme (veri hacmi gerekene dek) · Kafka/mikroservis (cron yeter) · Rakip fiyatına otomatik
tepki (fiyat savaşı riski) · Scraping (hukuki risk) · Çok segmentli genel ürün (konumlanma ölür).
