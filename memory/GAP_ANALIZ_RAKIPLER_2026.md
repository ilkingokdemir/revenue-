# RAKİP ANALİZİ — Duetto · IDeaS G3 · Atomize · RoomPriceGenie · FLYR (2026)
Onlarda olup BİZDE OLMAYAN özellikler. Kaynak: güncel web araştırması (Haziran 2026).

## ❌ GERÇEK EKSİKLER (öncelikli)

### P0 — Stratejik
1. **Toplantı/Etkinlik Alanı Fiyat Optimizasyonu (Duetto OpenSpace / IDeaS FSRM)**: Toplantı salonu, balo salonu, bahçe gibi alanlar için algoritmik dinamik fiyat + F&B/AV dahil toplam etkinlik kârlılığı + etkinlik planlayıcıları için teklif/booking motoru. Bizde Grup OS oda tarafını çözüyor; ALAN fiyatlaması yok.
2. **Regret & Denial Takibi (Duetto)**: Booking engine'de fiyata bakıp ALMAYAN (regret) ve müsaitlik bulamayan (denial) misafir sinyallerinin toplanıp fiyat motoruna girdi yapılması. Bizde talep radarı rezervasyon bazlı; kayıp talep sinyali yok.
3. **Olay-Tetiklemeli Anlık Re-Price (Atomize)**: Rezervasyon/iptal ANINDA fiyat motorunu tetikleme (bizde 30dk–4sa döngüler + gün-içi spike alarmı var; event-driven yazım yok).

### P1 — Yüksek Değer
4. **Segment & Kanal Bazlı Open Pricing (Duetto GameChanger)**: Aynı gece için segment (kurumsal, loyalty, OTA) ve kanal başına BAĞIMSIZ fiyat offsetleri. Bizde oda tipi+tarih var; segment/kanal katmanı yok (kanal ekonomisi net-kâr analizi var ama fiyat setleme değil).
5. **Grup Wish & Walk Price + Onay İş Akışı (IDeaS Group Pricing)**: Grup teklifinde "istenen fiyat / vazgeçme fiyatı" metrikleri + departmanlar arası onay akışı. Bizde displacement var; wish/walk ve onay zinciri yok.
6. **Grup Wash Tahmini (Duetto BlockBuster)**: Grup bloklarının eriyeceği (wash) oranın otomatik projeksiyonu ve kapasiteye yansıtılması.
7. **RMS Etki Ölçer (RoomPriceGenie "system benefit measurement")**: RMS'in kazandırdığı geliri before/after metodolojisiyle kanıtlayan genel uplift raporu. Bizde merdiven haftalık özeti var; motorun TÜM etkisini ölçen atıf raporu yok.

### P2 — Orta/Uzun Vade
8. **730 Gün Tahmin Ufku (Atomize)**: Bizde plan D365'e kadar; 2 yıl ileriye talep tahmini yok.
9. **Sosyal Duyarlılık Girdisi (Duetto)**: Social sentiment verisinin fiyat sinyali olarak kullanımı.
10. **Rakip Veri Anomali Düzeltme (IDeaS)**: Geriye dönük 180 güne kadar rakip fiyat verisini "yok say" işaretleme.
11. **Kârlılık Benchmarking (Duetto+HotStats)**: P&L bazlı pazar kıyası (bizde RGI/MPI/ARI var; kâr benchmark yok).
12. **İşbirlikçi Tahmin (FLYR)**: Tahmin üzerinde takım yorum/not/onay akışı.
13. **Mobil Uygulama (RoomPriceGenie)**: Native/PWA mobil fiyat onay deneyimi.

## ✅ ONLARDA OLUP BİZDE DE OLANLAR (kanıtlı)
Continuous pricing (kademesiz custom_rate), What-if senaryo simülasyonu (IDeaS What-if ≈ bizim Senaryo Karşılaştırma), takvimde OTB doluluk, grup displacement (BlockBuster çekirdeği), open-pricing'in oda tipi+tarih boyutu, ML tahmin (forecast v2), rakip radar + harita, AutoPilot benzeri otonom modlar (autopilot + shadow), Information Manager benzeri bildirim/uyarı merkezi, BI/executive raporlar, çoklu tesis.

## 🏆 BİZDE OLUP ONLARDA OLMAYAN/ZAYIF OLANLAR
Kanıt zarfı + fail-closed güven mimarisi, misafir-onaylı zam merdiveni, son-gün merdiveni (satışta yön dönüşü), ikinci-yazıcı tespiti + kira-çit kilidi, vitrin doğrulaması, no-show risk motoru + otomatik Stripe depozito + RSVP, PMS-agnostik connector, ABS, SaaS faturalama/MRR motoru, sabah karnesi/EOD/haftalık bülten otomasyonu.

## ÖNERİLEN SPRINT SIRASI
1. Regret & Denial Takibi (P0 — booking engine'e hızlı eklenir, motoru besler)
2. Olay-Tetiklemeli Anlık Re-Price (P0)
3. Segment/Kanal Open Pricing Offsetleri (P1)
4. Grup Wish & Walk + Onay Akışı + Wash Tahmini (P1)
5. RMS Etki Ölçer (P1) → Toplantı Alanı Fiyatlaması (P0 ama en büyük iş — ayrı faz)
