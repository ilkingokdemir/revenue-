# GAP ANALİZ RAPORU — RevenueIQ vs. Bizim Platform (MyHotelBox RMS)
Tarih: Haziran 2026 | Kaynak: RevenueIQ-Motor-Ozellikleri.pptx (16 slayt)

## ÖZET
Sunumdaki 40+ özelliğin ~%70'i bizde zaten mevcut (çoğu daha derin). Gerçek eksik: 9 kalem.
Ayrıca bizde olup RevenueIQ'da OLMAYAN 10+ büyük modül var (Grup OS, ABS, Stripe, PMS-agnostik connector...).

## A) BİZDE OLMAYAN — GERÇEK EKSİKLER

### P0 (Kritik — doğrudan gelir/güven etkisi)
1. **Son-Gün Merdiveni (D0–D1 Last-Minute Ladder)**: Varışa 0-1 gün kala satılmamış oda 4 saatte bir ~%8 kademeli iner, oda satılınca yön DÖNER, operatör tabanının altına inmez, pin'e dokunmaz. Bizde intraday_reprice sadece talep sıçraması ALARMI üretiyor — otomatik kademeli merdiven yok.
2. **Vitrin Doğrulaması (Own Storefront Scan)**: Otelin KENDİ Booking ilanını misafir gözüyle tarayıp panele yazılan ↔ vitrinde görünen fiyatı kuruşuna kıyaslama + hangi indirim katmanından sapma geldiğini raporlama. Bizde rakip taraması (comp_radar) var, kendi vitrin taraması yok.
3. **İkinci-Yazıcı Tespiti**: Kanala bizden başka bir sistem/elle müdahale fiyat yazarsa saatler içinde alarm. (HotelRunner drift auto-repush kısmi karşılık; genel aktör-imzalı tespit yok.)

### P1 (Yüksek değer)
4. **Misafir-Onaylı Zam Merdiveni**: İlk zam talep kanıtıyla; İKİNCİ basamak için YENİ REZERVASYON şartı — kimsenin ödemediği fiyata tırmanış matematiksel kapalı. Bizde adım limitleri var ama "yeni rezervasyon = yeni basamak" kilidi yok.
5. **Yıllık Plan Modülü (D90–365)**: Şekil × seviye ayrımı (mevsim şekli oranlardan, seviye yakın pencereden), plan SÜRÜM ARŞİVİ, rakip sapma manşeti (tek cümlelik özet), uzak fırsat kulvarı (+%3..+%20 mesafe merdiveni). Bizde senaryo fiyatlama 90 güne kadar; sahipli 365 günlük plan + sürümleme yok.
6. **Kira & Çit (Lease/Fencing) Yazım Kilidi**: Aynı fiyat hücresine iki yazıcı aynı anda giremez; her yazım sahiplik kirası + aktör imzası taşır. Bizde yapısal write-lock yok.

### P2 (Nice-to-have / kısmi karşılığı var)
7. **Kısmi Yayın Telafisi**: Çok hücreli yazımın bir kısmı reddedilirse yalnız etkilenen hücreler geri alınır.
8. **Günlük Sabah Karnesi E-postası**: Sistem her sabah kendi bekçi-zinciri karnesini e-postayla verir. (Bizde haftalık sağlık özeti + aylık report card var; günlük yok.)
9. **Cold-Start Kardeş Otel Şekil Ödünçü**: Sıfır geçmişli otelde mevsim şekli hesaptaki kardeş otellerden alınır + tek "başlangıç seviyesi" çapası, öğrenince otomatik devre dışı. (Bizde cold_start_mode var; sibling-borrowing yok.)
+ **Asimetrik Zaman Kuralı** (zam için zaman geçmesi bilgi değil, indirim için bilgidir) — motorda açık kural olarak yok.
+ **2 Yıl Geçmiş Otomatik İçe Aktarım** PMS bağlantı anında — kısmi.

## B) BİZDE ZATEN VAR (RevenueIQ ile eşdeğer/daha derin)
- Kanıt zarfı + güven semantiği (decision_assurance) ✓ (bizim "unique" listemizde)
- Randomize fiyat deneyleri + güç analizi (G9) ✓
- Golden replay / point-in-time backtest (G7) ✓
- Adım limitleri + 72s kümülatif tavan + günlük push tavanı (G1) ✓
- İptal/no-show modeli + aylık kalibrasyon + Brier (G4, G5) ✓
- Booking curve, pickup, pace (demand_radar, forecast_v2) ✓
- Rakip seti + harita + p25/medyan/p75 (comp_radar, compset) ✓
- Promo zinciri çözümü / indirim katmanları (discount_stack: Genius, last-minute, phone) ✓
- Türetilmiş oda fiyatları (rate_structure derived rates) ✓
- Onay kuyruğu + kabul oranı + red taksonomisi (G2) ✓
- Elastikiyet ölçümü + agresiflik faktörü (elasticity.py) ✓
- Etkinlik/hava/tatil sinyalleri ✓
- Rate parity + kanal izleme ✓
- Shadow mode + çıkış kriterleri (G6) ✓
- KVKK/GDPR, kill switch, publisher sertifikasyonu ✓
- Çok kiracılı izolasyon ✓
- Kurulum sihirbazı + demo seeder + tur ✓

## C) BİZDE OLUP RevenueIQ'DA OLMAYAN (rekabet avantajlarımız)
- PMS-agnostik Connector Hub (RevenueIQ sadece Cloudbeds)
- Grup Satış OS + displacement analizi
- Attribute-Based Selling (ABS)
- Kâr-öncelikli fiyatlama + kanal ekonomisi (komisyon/VAT/net katkı)
- Stripe ödemeleri + faturalama + MRR/churn/winback SaaS motoru
- Süper Admin konsolu, sistem sağlığı, otonom robot filosu
- Bid-price displacement ağı (MinLOS/CTA/CTD)
- RGI/MPI/ARI endeksleri, yönetici PDF raporları
- Public API

## ÖNERİLEN SPRINT SIRASI
1. Son-Gün Merdiveni (P0)
2. Vitrin Doğrulaması + İkinci-Yazıcı Tespiti (P0)
3. Misafir-Onaylı Zam Merdiveni (P1)
4. Yıllık Plan D90–365 + Sürüm Arşivi (P1)
5. Lease/Fencing (P1) → Kısmi telafi + Günlük karne + Cold-start sibling (P2)
