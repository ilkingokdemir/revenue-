"""
RM Derin Bilgi Kütüphanesi — sektörün eğitim, akademik çalışma, gerçek vaka ve
RMS yazılımlarının çalışma prensiplerinin damıtılmış hali. Mongo'ya idempotent
seed edilir; chat robotu soruya göre en alakalı kayıtları bağlamına çeker (RAG-lite).
Kaynaklar: IDeaS/Duetto/Atomize/RoomPriceGenie resmi dokümanları, Cornell (Kimes),
HSMAI CRMA/CRME, CHIA/STR, hakemli akademik yayınlar (2026 taraması).
"""

DEEP_KNOWLEDGE = [
    # ═══ YAZILIM ÇALIŞMA PRENSİPLERİ ═══
    {"id": "ideas_g3_engine", "category": "yazilim_prensipleri",
     "title": "IDeaS G3 — Analitik Motorun Çalışma Prensibi",
     "tags": "ideas g3 sas forecasting tahmin model optimizasyon dinamik programlama unconstrained kisitsiz talep",
     "body": "SAS High-Performance Analytics üzerinde 100+ özel tahmin modeli çalıştırır; otelin iş tipine (grup, transient, "
             "wholesale) göre modeli OTOMATİK seçip kalibre eder. Çekirdek: (1) Kısıtsız talep tahmini — fiziksel kapasiteden "
             "bağımsız gerçek pazar talebini, veri seyrekliği/gürültü/sansürlemeyi yöneterek kestirir. (2) ENTEGRE optimizasyon — "
             "önce fiyat sonra kural yerine, dinamik programlama ile fiyat + LOS kısıtları + overbooking'i TÜM oda tipleri için "
             "AYNI ANDA optimize eder (sabit offset mantığının tuzağından kaçınır). (3) Sürekli öğrenme — yeni rezervasyon verisi "
             "geldikçe modeller yeniden kalibre olur, talep aralığı daralır. (4) Kâr optimizasyonu — RevPAR ötesinde yan gelir, "
             "değişken marj ve edinim maliyetini hesaba katarak en yüksek fiyatlı değil en yüksek DEĞERLİ segmenti önceliklendirir. "
             "(5) Şeffaflık — Investigator/Optix araçlarıyla her kararın gerekçesi denetlenebilir."},
    {"id": "duetto_algorithm", "category": "yazilim_prensipleri",
     "title": "Duetto — Open Pricing Algoritmasının Çalışma Prensibi",
     "tags": "duetto open pricing pickup pace bar segment kanal bagimsiz constrained forecast",
     "body": "Her segment × kanal × oda tipini tek BAR merdiveninden türetmek yerine BAĞIMSIZ fiyatlar. Algoritmanın kalbi "
             "pickup sapması: Kısıtlı Tahmin (Constrained Forecast) beklenen rezervasyon eğrisini kurar; son fiyat değişiminden "
             "bu yana gerçekleşen pickup modellenen eğriden SAPARSA fiyat tepki verir — transient pickup beklentiyi aşarsa fiyat "
             "yükselir, geride kalırsa düşer. Grup/kontratlı gibi 'open price edilemez' segmentler tetikleyici olarak hariç tutulur. "
             "Ders: statik tarihsel karşılaştırma değil, CANLI pace-vs-model sapması fiyatı yönetmelidir."},
    {"id": "atomize_engine", "category": "yazilim_prensipleri",
     "title": "Atomize (Mews) — Gerçek Zamanlı Optimizasyonun Çalışma Prensibi",
     "tags": "atomize mews gercek zamanli real time fiyat noktasi simulasyon oda tipi revpar trevpar",
     "body": "Talep tahminini FARKLI FİYAT NOKTALARINDA talebi simüle ederek kurar. İki mod: Standart (günde 3 güncelleme) ve "
             "Gerçek Zamanlı (pickup gibi veri değişimi algılanır algılanmaz anında). Her otelin kendi tarihsel verisiyle eğitilir "
             "(iptaller, grup tahsisleri, pace dahil). Oda tiplerini TEK TEK optimize eder ve toplam otel gelirini (RevPAR/TRevPAR) "
             "maksimize etmek için bazen belirli tiplere DÜŞÜK fiyat önerir — talebi daha kârlı konfigürasyona kaydırır. "
             "Ders: hücre bazlı optimizasyon + anlık tepki; oda tipi fiyatı tek başına değil portföy kârı için ayarlanır."},
    {"id": "rpg_hybrid", "category": "yazilim_prensipleri",
     "title": "RoomPriceGenie — Hibrit 3-Model Yaklaşımı",
     "tags": "roompricegenie hibrit bayesian pickup rakip airbnb model agirlik base price",
     "body": "Üç bağımsız talep modeli birleştirir: (1) yerel rakip otel fiyatları, (2) yerel Airbnb fiyat/doluluğu, "
             "(3) Bayesian Pickup modeli — mevcut fiyatta rezervasyon hacmi beklenenden DÜŞÜKSE 'adil fiyatı' aşağı çeker. "
             "Kullanıcı modellere ağırlık atayabilir (ör. pickup'a rakipten fazla ağırlık). Taban fiyat hesaplanır, sonra doluluk "
             "hedefi ve agresiflik ayarıyla düzeltilir; günde 4-12 kez tekrarlanır. Ders: tek sinyale güvenme — pickup + rakip + "
             "alternatif konaklama sinyallerini ağırlıklı birleştir."},
    {"id": "rms_common_arch", "category": "yazilim_prensipleri",
     "title": "Tüm RMS'lerin Ortak Mimarisi: Tahmin → Optimizasyon → Dağıtım → Ölçüm",
     "tags": "rms mimari pipeline tahmin optimizasyon dagitim olcum dongusu kapali",
     "body": "Piyasadaki her ciddi RMS aynı kapalı döngüyü işletir: (1) VERİ: PMS rezervasyonları, pace, rakip fiyatlar, etkinlik "
             "takvimi, web talep sinyalleri. (2) TAHMİN: segment/oda tipi bazında kısıtsız talep. (3) OPTİMİZASYON: fiyat + kısıt + "
             "overbooking kararları (kural bazlı → bilim bazlı spektrum). (4) DAĞITIM: kanal yöneticisi/CRS'e otomatik push. "
             "(5) ÖLÇÜM & ÖĞRENME: karar sonuçları ölçülür, modeller güncellenir. Bir RMS'i değerlendirirken sorulacak soru: "
             "döngünün hangi halkası insan eliyle kırılıyor?"},
    # ═══ AKADEMİK & GERÇEK VAKALAR ═══
    {"id": "case_ihg", "category": "vaka_calismalari",
     "title": "Vaka: IHG Fiyat Optimizasyonu — 145M$ Ek Gelir",
     "tags": "ihg intercontinental vaka case fiyat optimizasyon ek gelir kanit roi",
     "body": "InterContinental Hotels Group'un fiyat optimizasyon modülü 145 milyon $ ek gelir üretti; tam yaygınlaşmada yıllık "
             "400 milyon $ projeksiyonu (INFORMS Interfaces, hakemli). Ders: sistematik fiyat optimizasyonu zincir ölçeğinde "
             "kanıtlanmış, ölçülebilir getiri sağlar — sezgisel fiyatlama bırakılmalıdır."},
    {"id": "case_carlson", "category": "vaka_calismalari",
     "title": "Vaka: Carlson Rezidor SNAP — Uyumlu Otellerde %2-4 Gelir Artışı",
     "tags": "carlson rezidor snap vaka gece bazli fiyatlama otomasyon uyum",
     "body": "Carlson Rezidor'un Stay Night Automated Pricing (SNAP) sistemi: sisteme UYAN oteller uymayanlara göre %2-4 gelir "
             "artışı, yıllık 16M$+ kazanç (SSRN, hakemli). Kritik bulgu: aynı sistem kurulu olsa bile önerilere UYUM oranı "
             "sonucu belirler. Ders: robotun önerilerini bypass eden operasyon, sistemin getirisini yok eder."},
    {"id": "study_variability", "category": "vaka_calismalari",
     "title": "Bulgu: Dinamik Fiyat Değişkenliği RevPAR'ı Artırır (+%3.07)",
     "tags": "dinamik fiyat degiskenlik revpar arastirma 21687 gozlem adr doluluk",
     "body": "21.687 otel gözlemli araştırma: fiyatları DAHA SIK ayarlamak RevPAR'ı anlamlı artırır; fiyat varyasyonunda 1. "
             "çeyrekten 3. çeyreğe çıkmak ≈ %3.07 gelir artışı. Yüksek değişkenlik indirimler yüzünden ADR'yi düşürebilir ama "
             "doluluk kazancı net geliri artırır. Ders: fiyatı sabitleme korkusunu bırak; sık, küçük, veri temelli ayarlamalar kazandırır "
             "(guardrail ile istikrar korunarak)."},
    {"id": "study_unavailability", "category": "vaka_calismalari",
     "title": "Bulgu: Stratejik Kapatma Bid-Price'ı Yenebilir (+%34'e kadar)",
     "tags": "stratejik kapatma unavailability bid price simulasyon yuksek fiyat koruma",
     "body": "Simülasyon çalışması: gelecekteki yüksek fiyatlı talebi korumak için envanteri düşük fiyata STRATEJİK KAPATMAK, "
             "standart bid-price yöntemlerini geçebilir (+%34'e varan gelir artışı senaryosu). Ders: doluluk baskısıyla erken "
             "dönemde ucuza satmak, geç gelen yüksek değerli talebi 'yerinden eder' — LRV/hurdle disiplini şarttır."},
    {"id": "study_elasticity", "category": "vaka_calismalari",
     "title": "Bulgu: Düşük Sezonda Talep Çoğunlukla İNELASTİK",
     "tags": "esneklik elasticity log-log dusuk sezon inelastik veblen giffen fiyat artis",
     "body": "Log-log regresyon çalışmaları: oteller özellikle DÜŞÜK sezonda inelastik taleple karşılaşır — fiyat kırmak dolulukta "
             "beklenen sıçramayı yaratmaz, sadece ADR eritir. Ayrıca yüksek sezonda Veblen/Giffen etkisi görülebilir: fiyat "
             "artışı statü/beklenti sinyaliyle talebi ARTIRABİLİR. Ders: 'boş kaldı → indir' refleksi çoğu zaman yanlıştır; önce "
             "esnekliği ölç (bizim Fiyat Duyarlılığı motoru), elastik olmayan bağlamda fiyat koru/yükselt."},
    {"id": "study_rm_structure", "category": "vaka_calismalari",
     "title": "Bulgu: RM Organizasyon Yapısı RevPAR Endeksini Etkiler",
     "tags": "organizasyon yapi merkezi in-house ucuncu parti revpar index",
     "body": "Ampirik araştırma: revenue yönetiminin otel içinde mi, merkezi mi, üçüncü partide mi olduğu RevPAR endeksini ölçülebilir "
             "etkiler. Ders: teknoloji tek başına yetmez — karar sahipliği, hız ve hesap verebilirlik yapısı kurulmalıdır. "
             "Bizim modelde: robot 7/24 izler+önerir, insan chat üzerinden onaylar (hızlı döngü + insan-döngüde)."},
    # ═══ EĞİTİM MÜFREDATI (Cornell/HSMAI/CHIA damıtımı) ═══
    {"id": "edu_booking_curve", "category": "egitim",
     "title": "Cornell/Kimes: Rezervasyon Eğrisi ve Pickup Tahmini",
     "tags": "cornell kimes booking curve rezervasyon egrisi pickup tahmin lead time additive multiplicative",
     "body": "Talep, varış tarihine yaklaştıkça birikir: rezervasyon eğrisi bu birikimin desenidir. Pickup tahmini: geçmiş aynı "
             "gün-tipi eğrilerinden 'kalan pickup' kestirilir — additive (ortalama kalan oda sayısı eklenir) veya multiplicative "
             "(şu anki doluluk / o güne tipik tamamlanma oranı). Pace analizi: bugünkü OTB'yi (on-the-books) geçen yıl/ay aynı "
             "lead-time OTB'siyle kıyasla; sapma fiyat kararının ana tetiğidir."},
    {"id": "edu_forecast_error", "category": "egitim",
     "title": "Tahmin Doğruluğu: MAD ve MAPE ile Ölçüm",
     "tags": "mad mape tahmin hata dogruluk olcum forecast accuracy",
     "body": "Tahmin disiplini ölçülmeden gelişmez: MAD (ortalama mutlak sapma, oda sayısı) ve MAPE (ortalama mutlak yüzde hata). "
             "Sektör pratiği: 30+ gün ufukta MAPE %10-15 kabul edilebilir, son 7 günde %5 altı hedeflenir. Ders: robotun her "
             "tahmini sonradan gerçekleşenle kıyaslanmalı (bizim kapalı öğrenme döngümüz tam bunu yapar)."},
    {"id": "edu_overbooking_model", "category": "egitim",
     "title": "Overbooking Bilimi: Newsvendor / Kritik Oran Modeli",
     "tags": "overbooking newsvendor kritik oran walk maliyet bos oda no-show model",
     "body": "Optimum overbooking klasik newsvendor problemidir: kritik oran = Cu / (Cu + Co); Cu = boş oda maliyeti (kaçan marj), "
             "Co = walk maliyeti (başka otel + transfer + itibar). No-show dağılımının bu orana denk gelen yüzdelik değeri optimum "
             "limittir. Pratik: kaynak bazlı no-show oranları ayrışır (OTA > direkt), bu yüzden limit kaynak karmasına göre "
             "hesaplanmalı (bizim Overbooking modülü beklenen wash × güven katsayısı kullanır)."},
    {"id": "edu_displacement", "category": "egitim",
     "title": "Displacement Analizi: Grup Kabul Matematiği",
     "tags": "displacement grup analiz katki marj transient yer degistirme omuz gece",
     "body": "Grup teklifini değerlendirirken: kabul edilirse KAÇACAK transient gelir (yerinden edilen odalar × beklenen ADR) + "
             "kaybedilen esneklik vs grup oda geliri + F&B/toplantı katkısı + omuz gecesi dolgusu. Karar kuralı KATKI MARJI "
             "üzerinden verilir, ciro üzerinden değil. Doluluk düşük dönemde displacement maliyeti ~0'dır; yüksek dönemde grup "
             "fiyatı LRV'nin altındaysa reddet/karşı teklif ver."},
    {"id": "edu_los_controls", "category": "egitim",
     "title": "Envanter Kontrolleri: LOS Kuralları ve Rate Fence'ler",
     "tags": "los minlos cta ctd rate fence kural envanter kisit kapali varis",
     "body": "MinLOS/MaxLOS, CTA (varışa kapalı), CTD (çıkışa kapalı) yoğun geceyi tek gecelik düşük değerli rezervasyondan korur; "
             "omuz gecelerini çok geceli konaklamayla doldurur. Rate fence = düşük fiyata erişimi meşru koşula bağlama: iade "
             "edilmez ön ödeme, min konaklama, üye fiyatı, erken rezervasyon. İyi fence fiyat ayrımcılığını misafiri küstürmeden yapar."},
    {"id": "edu_hsmai_strategy", "category": "egitim",
     "title": "HSMAI CRME: Gelir Yönetiminden Gelir STRATEJİSİNE",
     "tags": "hsmai crme crma strateji total revenue toplam gelir egitim sertifika",
     "body": "HSMAI müfredatının ana tezi: RM oda fiyatlama taktiğinden TOPLAM otel gelir stratejisine evrildi — toplantı alanı, "
             "F&B, spa, otopark dahil tüm gelir akışları tek stratejiyle optimize edilir (Total Hotel Revenue Optimization). "
             "CRMA temeli: mikroekonomi, fiyatlama, envanter, dağıtım kanalları, tahmin. Ders: oda-RevPAR tüneline sıkışma; "
             "karar metriği TRevPAR/GOPPAR olmalı (bizim RevPAM modülü toplantı odalarına bunu uygular)."},
    {"id": "edu_chia_benchmark", "category": "egitim",
     "title": "CHIA/STR: Kıyaslama Matematiği — Penetrasyon, ARI, RGI",
     "tags": "chia str benchmark kiyas penetrasyon ari rgi mpi pazar payi star",
     "body": "STR STAR mantığı: performans ancak pazara GÖRE anlamlıdır. MPI (doluluk penetrasyonu) = otel doluluğu / compset "
             "doluluğu ×100; ARI = otel ADR / compset ADR; RGI (RevPAR endeksi) = otel RevPAR / compset RevPAR. 100 üstü pazardan "
             "pay aldığını gösterir. Teşhis matrisi: RGI<100 & ARI>100 → fiyat pazarın üstünde, hacim kaybı; RGI<100 & MPI>100 → "
             "hacim var ama fiyat bırakılıyor. Strateji bu matristen türetilir."},
    # ═══ TEKNİK MODELLER ═══
    {"id": "tech_unconstraining", "category": "teknik_modeller",
     "title": "Sansürlü Talep ve Unconstraining Yöntemleri",
     "tags": "sansur censoring unconstraining talep kisitsiz em booking limit kapali",
     "body": "Kapalı/dolu günlerde gözlenen talep GERÇEK talebin altıdır (sansürlü veri). Unconstraining yöntemleri: naif çarpan, "
             "Expectation-Maximization (EM), rezervasyon eğrisi ekstrapolasyonu. Bunu yapmayan sistem yoğun dönem talebini sistematik "
             "KÜÇÜMSER ve fiyatı düşük bırakır. IDeaS'ın çekirdek farkı budur."},
    {"id": "tech_bid_price", "category": "teknik_modeller",
     "title": "Bid-Price ve EMSR: Kapasite Tahsis Bilimi",
     "tags": "bid price emsr littlewood kapasite tahsis nested koruma seviyesi",
     "body": "Littlewood kuralı (2 sınıf): düşük fiyata satış, ancak yüksek fiyat talebinin o odayı doldurma olasılığı × yüksek fiyat "
             "< düşük fiyat ise yapılır. EMSR-b çok sınıfa genelleştirir: iç içe (nested) koruma seviyeleri. Bid-price: her kalan "
             "odanın gölge fiyatı — altındaki talep reddedilir. Pratik karşılığı bizim LRV/hurdle mantığımız ve Open Pricing hücre tabanlarıdır."},
    {"id": "tech_pace_signals", "category": "teknik_modeller",
     "title": "Pace/OTB Sinyal Okuma Rehberi",
     "tags": "pace otb on the books sinyal okuma lead time hizlanma yavaslama",
     "body": "OTB tek başına anlamsız; SİNYAL = OTB vs aynı lead-time'daki referans (STLY/ST2Y ort). Okuma: pace >+%15 → fiyat artış "
             "adayı (esneklik izinliyse); pace <-%15 → önce SEGMENT kırılımına bak (tek segment mi genel mi?), genelse hedefli aksiyon; "
             "pace normal + rakip fiyat düşmüş → panikleme, kendi eğrine güven. Kural: fiyat kararını tek günlük pickup'a değil "
             "3-7 günlük pace trendine bağla."},
    {"id": "tech_price_testing", "category": "teknik_modeller",
     "title": "Fiyat Testi: A/B Holdout ve Ölçülen Sonuç",
     "tags": "ab test holdout deney fiyat testi olcum kanit dogrulama",
     "body": "Fiyat kararının işe yarayıp yaramadığı ancak KONTROLLÜ kıyasla bilinir: holdout günleri/hücreleri değişimden muaf "
             "tutulur, sonuç farkı ölçülür. Büyük zincirler (IHG vakası) getiriyi böyle kanıtladı. Bizim platform: A/B holdout "
             "altyapısı + her kararın verdict'i (worked/neutral/hurt) + kalıcı hafızaya işleme."},
    # ═══ DERİN STRATEJİLER ═══
    {"id": "strat_max_profit_deep", "category": "derin_stratejiler",
     "title": "Maksimum Kârlılık — Uzman Reçetesi (7 Katman)",
     "tags": "maksimum karlilik kar recete strateji katman komisyon direkt upsell lrv",
     "body": "1) NET katkı fiyatlaması: kanal komisyonu + temizlik/edinim maliyeti düşülmüş marja göre optimize et. 2) Kanal miksi: "
             "direkt pay +10 puan ≈ ciroda %1.5-2 net kâr (OTA komisyon tasarrufu). 3) LRV disiplini: son odaları koru — stratejik "
             "kapatma bid-price'ı yenebilir (+%34 vaka). 4) İnelastik bağlamda cesur ADR (düşük sezon inelastik bulgusu). 5) ABS/upsell: "
             "oda başı ek gelir, sıfır ek kapasiteyle kâr. 6) Grup kararlarını displacement matematiğiyle ver. 7) Her kararı ölç, "
             "hafızaya işle, tekrarlama gücü kazan (SNAP vakası: uyum = getiri)."},
    {"id": "strat_max_occ_deep", "category": "derin_stratejiler",
     "title": "Maksimum Doluluk — Uzman Reçetesi (7 Katman)",
     "tags": "maksimum doluluk recete strateji bos gece pace kampanya los overbooking",
     "body": "1) Boş gece radarı: 14-30 gün ufukta pace'i geriden gelen günleri erken yakala (erken aksiyon = düşük maliyetli aksiyon). "
             "2) Elastik segmente hedefli teklif: fiyat kırmak yerine fence'li kampanya (üye fiyatı, min-2-gece paketi) — ADR tabanını korur. "
             "3) LOS mühendisliği: yoğun geceden omuz gecelere köprü kur (MinLOS). 4) Overbooking'i wash'a göre aç (newsvendor oranı). "
             "5) Kanal genişletme son çare, fiyat tabanıyla (min rate floor). 6) Sık küçük ayar > tek büyük indirim (+%3.07 değişkenlik bulgusu). "
             "7) Doluluk hedefini kâr hedefiyle sınırla: %100 doluluk ≠ maksimum kâr (Veblen dönemlerinde fiyat bırakma)."},
    {"id": "strat_compset_deep", "category": "derin_stratejiler",
     "title": "Rakip Fiyat Stratejisi — Takip Et, Taklit Etme",
     "tags": "rakip compset fiyat takip strateji pozisyon ari rgi",
     "body": "Rakip fiyatı SİNYAL'dir, PUSULA değil: (1) Rakip düşürdü + senin pace normal → takip etme (RPG modeli bile pickup'a "
             "rakipten çok ağırlık verdirir). (2) Rakip yükseltti + pazar pace güçlü → boşluğu değerlendir, kademeli çık. "
             "(3) Sürekli ARI>110 + MPI<90 → fiyat pozisyonun pazarın taşıyamayacağı yerde. (4) Etkinlik günlerinde compset "
             "median'ına değil kendi kısıtsız talebine fiyatla. Rakip verisi en çok TAHMİNE girdi olarak değerlidir, refleks olarak değil."},
    # ═══ İLERİ MİMARİ (üst düzey RMS iç mekanikleri) ═══
    {"id": "top20_rms_genis", "category": "yazilim_prensipleri",
     "title": "Geniş RMS Haritası: 20 Oyuncunun Uzmanlık Alanları",
     "tags": "top 20 rms beonx pricepoint happyhotel smartpricing blastness profitroom beyond wheelhouse cloudbeds otamiser",
     "body": "Liderler dışındaki niş uzmanlar: BEONx (bütünsel kârlılık analitiği, enterprise), Pricepoint (kur-ve-unut gün içi "
             "dinamik güncelleme), happyhotel (küçük tesislerde hızlı pace/rakip ayarı), Smartpricing (yalın ekipler için sezgisel "
             "günlük optimizasyon), Revolution Plus/Franco Grasso (AI + insan uzman hibrit modeli, Avrupa), Blastness (İtalyan/Avrupa "
             "lüks bağımsızlar), Profitroom (gelir kurallarını yüksek dönüşümlü direkt motorla hizalama), Beyond & Wheelhouse "
             "(alternatif konaklama/kısa dönem), Cloudbeds RI (PMS-native sıfır sürtünmeli tahmin), Intelligence Node (büyük veriyle "
             "rakip eşleştirme), Otamiser (dış kaynak RM operasyonu). Ders: her segmentin kazandıran formülü farklı — bizim platform "
             "PMS-native + otopilot + kârlılık analitiğini tek çatıda birleştirir."},
    {"id": "tech_metacognition", "category": "teknik_modeller",
     "title": "Metacognition: Modelin Modeli Seçmesi (IDeaS Çoklu-Model Dersi)",
     "tags": "metacognition model secici mape agirlik coklu model kendini duzeltme supervised",
     "body": "Üst düzey RMS tek algoritma çalıştırmaz: onlarca istatistik/ML modeli paralel koşar; sistem her modelin geçmiş MAPE "
             "hatasını ölçüp ağırlığını OTOMATİK ayarlar (tatilde farklı, iş gününde farklı model kazanabilir). Uygulanabilir kural: "
             "tahmin motorunun kendisi de ölçülmeli — hangi bağlamda hangi yaklaşım isabetliyse karar ağırlığı ona kaymalı. Bizim kapalı "
             "öğrenme döngüsü + kalıcı hafıza çarpanları bu üstbiliş katmanının pratiğidir."},
    {"id": "tech_denials_regrets", "category": "teknik_modeller",
     "title": "Denials & Regrets: Reddedilen ve Kaçan Talebi Say",
     "tags": "denials regrets red kacan talep tobit censored regression sinirsiz talep web trafik",
     "body": "Otel dolunca talep durmaz — sistem 'oda yok' diyerek reddeder (denial) veya misafir fiyatı yüksek bulup kaçar (regret). "
             "Bu görünmez talep Tobit/censored regression ve üstel düzeltme ile modele geri eklenmelidir. Satıcı raporları belirgin "
             "RevPAR avantajı iddia eder (doğrulanmamış pazarlama rakamı — katsayı olarak modele GÖMME). Uygulama: dolu günlerdeki "
             "web aramaları ve fiyat-red trafiği kaydedilmeli; ertesi yılın aynı dönemi bu gerçek talebe göre fiyatlanmalı."},
    {"id": "strat_price_war", "category": "derin_stratejiler",
     "title": "Fiyat Savaşı Savunması: Oyun Teorisi Kapısı",
     "tags": "fiyat savasi price war oyun teorisi nash rakip panik dusurme koru bekle",
     "body": "Rakip fiyat düşürünce körü körüne takip eden otel fiyat savaşında kârından ciddi pay kaybeder (yaygın sektör gözlemi; "
             "kesin yüzde iddialarına itibar etme). Karar kapısı: rakip düştü VE pazar "
             "talebi canlı (pace stabil/güçlü) → FİYATI KORU — rakibin ucuz odaları hızla tükenir, kalan yüksek talep sana yüksek "
             "fiyattan gelir. Rakip düştü VE pazar gerçekten ölü → hedefli, fence'li hafif indirim + LOS gevşetme. Nash mantığı: "
             "'fiyatı sabit tutarsam pazar payımın ne kadarını korurum?' simülasyonu, refleksten önce gelir."},
    {"id": "tech_anomaly_guard", "category": "teknik_modeller",
     "title": "Anomali Filtresi: Hatalı Rakip Verisine Karşı Sigorta",
     "tags": "anomali filtre isolation forest hatali veri rakip 1 dolar sigorta guard",
     "body": "Rakip sistem hatasıyla fiyatını saçma bir değere (ör. 1$) düşürürse, bunu pazar trendi sanan robot oteli zarara sokar. "
             "Sigorta: gelen dış veri tarihsel dağılımın makul bandı dışındaysa (aykırı değer tespiti — Isolation Forest sınıfı "
             "yöntemler) karar girdisinden DIŞLA ve logla. Aynı ilke içeride de geçerli: tek günlük uç pickup sıçraması tek başına "
             "fiyat kararı tetiklememeli, 3-7 günlük trend beklemeli."},
    {"id": "tech_external_signals", "category": "teknik_modeller",
     "title": "Dış Sinyal Katmanı: Uçuş, Hava Durumu, Etkinlik",
     "tags": "ucus flight hava durumu weather etkinlik event scraping erken uyari dis veri sinyal",
     "body": "İleri robotlar otel-içi veriye hapsolmaz: (1) Uçuş arama/fiyat trendleri şehre gelen talep dalgasını haftalar önce haber "
             "verebilir. (2) Hava durumu korelasyonu tatil/kaçamak otellerinde son dakika rezervasyon ve iptal tahminini iyileştirir "
             "(güneşli tahmin → son dakika fiyatı zirveye; yağmur → erken hedefli teklif). (3) Etkinlik/kongre "
             "takvimi kazıma: bilet satış hızı talep çarpanını otomatik yükseltmeli. Bu sinyaller tahmine GİRDİ olur, asla tek başına karar olmaz."},
    {"id": "tech_cancel_score", "category": "teknik_modeller",
     "title": "Rezervasyon Bazlı İptal Olasılık Skoru",
     "tags": "iptal olasilik skor logistic regression no-show overbooking rezervasyon bazli risk",
     "body": "Overbooking'in bir üst ligi: her GELEN rezervasyona iptal riski skoru atamak (lojistik regresyon sınıfı model; girdiler: "
             "kanal, lead-time, iade koşulu, konaklama günü, geçmiş davranış). Günlük beklenen wash = rezervasyonların skor toplamı — "
             "kaynak ortalamasından çok daha isabetli. Sonuç: sıfıra yakın boş oda riskiyle agresif ama güvenli satış limiti."},
    {"id": "edu_spillage_spoilage", "category": "egitim",
     "title": "Spillage vs Spoilage: İki Zarar Arasındaki Denge",
     "tags": "spillage spoilage erken ucuz satis bos kalma denge optimizasyon egri",
     "body": "İki simetrik zarar: SPILLAGE = odaları erken ve ucuza satıp geç gelen yüksek fiyatlı talebi kaçırmak (gün ERKEN doldu ise "
             "işaret). SPOILAGE = fiyatı yüksek tutup odayı boş bırakmak (yakın tarihte düşük doluluk işareti). Uzman denge kuralı: "
             "erken dolan günlerde fiyat tabanını yükselt; yaklaşan boş günlerde fence'li hedefli teklif aç. Fiyat eğrisi bu iki riski "
             "birlikte minimize edecek şekilde çizilir — tek yönlü optimizasyon her zaman öbür zarara kayar."},
    {"id": "strat_billboard", "category": "derin_stratejiler",
     "title": "Billboard Etkisi ve Kapalı Kullanıcı Grubu Fiyatı",
     "tags": "billboard etki direkt kapali kullanici grubu cug uye fiyat ota vitrin makas",
     "body": "OTA'lar vitrindir: misafir oteli Booking'de görür, akıllı otel satın almayı kendi sitesine çeker. Mekanizma: OTA fiyatını "
             "görece yüksek tut, kendi sitende üyelere özel (Closed User Group) fiyatla parite ihlali olmadan makas aç — üye fiyatı "
             "parite kurallarından muaftır. Kanıt: direkt payı +15 puan artıran otel net kâr marjını doğrudan +%3-4 taşır. "
             "Uygulama: üyelik/newsletter fence + web'e en iyi fiyat garantisi + OTA'da mobil indirimi sınırlı tut."},
    {"id": "tech_bellman", "category": "teknik_modeller",
     "title": "Bellman/MDP: Bozulabilir Varlık Olarak Oda ve Dinamik Esneklik",
     "tags": "bellman mdp markov dinamik programlama bozulabilir perishable golge fiyat dinamik esneklik lead time",
     "body": "Oda bozulabilir üründür: bugün satılmayan gece yarın çöptür. Optimal politika Markov Karar Süreci ile bulunur: her "
             "(kalan gün × kalan stok) durumunda 'şimdi bu fiyata sat' ile 'bekle, daha değerli talebe sakla' kıyaslanır (Bellman). "
             "Pratik çıkarım 1: gölge fiyat = son odanın fırsat maliyeti; altındaki teklif reddedilir. Pratik çıkarım 2: esneklik "
             "SABİT katsayı değildir — lead-time × haftanın günü × segmente göre saatlik değişir; girişe ≤3 gün + canlı pazar = "
             "inelastik (fiyat yukarı). Dinamik esneklik teoride sağlam bir yaklaşımdır; satıcıların ADR büyüme yüzdeleri ise "
             "doğrulanmamış pazarlama iddialarıdır."},
    # ═══ VERİ MÜHENDİSLİĞİ & KANIT DİSİPLİNİ (öz-eleştirel katman) ═══
    {"id": "meta_evidence", "category": "veri_muhendisligi",
     "title": "Kanıt Hijyeni: Uydurma Yüzde Tuzağı ve Patent Kaynağı",
     "tags": "kanit hijyen uydurma yuzde pazarlama brosur patent google patents dogrulama katsayi",
     "body": "'%X RevPAR artışı' iddialarının çoğu satıcı broşürüdür, izlenebilir çalışmaya dayanmaz — bunları hedef fonksiyonuna "
             "sabit katsayı olarak gömen model HAYALİ gerçekliği optimize eder. Gerçek algoritma bilgisinin kaynağı: Google Patents'ta "
             "assignee:'Duetto Research' / 'Integrated Decisions and Systems' (IDeaS) araması — patent metni hukuken açıklayıcı olmak "
             "zorundadır, algoritmanın iskeleti oradadır. Kural: her sayısal iddiayı 'ölçtüm / hakemli / satıcı iddiası' diye etiketle; "
             "yalnız kendi ölçtüğünü karar katsayısı yap."},
    {"id": "data_otb_matrix", "category": "veri_muhendisligi",
     "title": "OTB Matrisi: Robotun Gerçek Eğitim Seti",
     "tags": "otb matris rezervasyon egrisi tensor log booking_datetime lead time egitim seti",
     "body": "'Yılda 8.400 rezervasyon oldu' tablosu eğitim seti DEĞİLDİR. Asıl eğitim seti rezervasyon eğrisidir: 'X gecesi için "
             "T gün kala kaç oda satılmıştı?' Ham log alanları: booking_datetime, arrival/departure_date, cancel_datetime, room_type, "
             "rate_code, channel, adr, guest_country, pax. Bunlarla her (görüntüleme tarihi × konaklama tarihi) çifti için OTB matrisi "
             "geriye dönük inşa edilir — 3 yıllık logdan ~1.100×365 eğitim tensörü çıkar. Bizim platformda pace/pickup modülleri bu eğriyle çalışır."},
    {"id": "data_endogeneity", "category": "veri_muhendisligi",
     "title": "Endojenite: Esneklik Geçmiş Veriden Öğrenilemez",
     "tags": "endojenite esneklik regresyon tuzak thompson sampling epsilon greedy kesif rastgele deney expedia icdm",
     "body": "Geçmiş fiyatlar rastgele değildi — talep yüksekken yüksekti. Naif regresyon 'fiyat artınca talep artıyor' öğrenir "
             "(endojenite). Çözümler: (1) Rastgeleleştirilmiş veri — Expedia ICDM 2013 seti (399.344 arama, sıralaması rastgele "
             "alt küme = doğal deney) temiz esneklik/Multinomial Logit tahmini için en iyi halka açık kaynak. (2) Kendi otelinde "
             "kararların %5-10'unu bilinçli rastgeleleştir (ε-greedy/Thompson Sampling) — bu 'kayıp gelir' değil, esneklik eğrisinin "
             "bedelidir; keşif yapmayan robot körleşir. Bizim A/B holdout altyapısı tam bu keşif ilkesinin uygulamasıdır."},
    {"id": "data_calibration", "category": "veri_muhendisligi",
     "title": "Overbooking'de AUC Değil KALİBRASYON Hayat Kurtarır",
     "tags": "kalibrasyon auc isotonic regression iptal skor desil overbooking guven",
     "body": "İptal modeli AUC 0.86 olsa bile orta desillerde kayabilir (tahmin %22 → gerçek %30). Overbooking limiti OLASILIK "
             "toplamına dayandığından yanlış kalibrasyon doğrudan walk/boş oda zararıdır. Canlıya almadan önce isotonic regression "
             "ile kalibre et; desil bazında tahmin-vs-gerçek tablosunu her ay yeniden kontrol et. Sıralama gücü (AUC) fiyat sıralaması "
             "için, kalibrasyon kapasite riski için kritiktir."},
    {"id": "data_model_scale", "category": "veri_muhendisligi",
     "title": "Model Ölçeği: Tek Otelde LSTM Overfit Eder",
     "tags": "lstm overfit lightgbm xgboost hiyerarsik zaman serisi bayesian tek otel veri hacmi",
     "body": "Tek otel × 3 yıl ≈ 1.100 konaklama günü — derin öğrenme (LSTM) için çok az; kesin overfit. Bu ölçekte kazanan: "
             "LightGBM/XGBoost + hiyerarşik zaman serisi (hafta içi/sonu × segment × oda tipi seviyeleri) + basit Bayesyen güncelleme. "
             "LSTM'e ancak 50+ otelden havuzlanmış veriyle geç. Bizim mimari de bu ilkeyle uyumlu: bağlam kovaları (dow × lead-band) + "
             "küresel/bölgesel havuzlama = az veride sağlam öğrenme."},
    {"id": "data_free_signals", "category": "veri_muhendisligi",
     "title": "Ücretsiz Talep Sinyali Kaynakları ve Look-Ahead Tuzağı",
     "tags": "open-meteo era5 pytrends google trends ticketmaster predicthq opensky eurostat tuik look-ahead bias ucretsiz api",
     "body": "Hemen kullanılabilir ücretsiz katmanlar: Open-Meteo Historical API (1940'tan saatlik ERA5, key'siz, CC BY 4.0); "
             "Google Trends/pytrends ('otel [şehir]', '[şehir] uçak bileti' — 30-60 gün önden sinyal); Ticketmaster Discovery API "
             "(etkinlik), OpenSky/Eurocontrol (uçuş), Eurostat + TÜİK/Bakanlık il bazlı doluluk (benchmark). KRİTİK TUZAK: modeli "
             "eğitirken GERÇEKLEŞEN havayı değil o tarihte MEVCUT OLAN tahmini kullan (Open-Meteo Historical Forecast arşivi) — "
             "yoksa look-ahead bias ile sahte doğruluk üretirsin."},
    {"id": "data_academic_sets", "category": "veri_muhendisligi",
     "title": "Soğuk Başlangıç: Antonio 2019 ve Expedia ICDM Setleri",
     "tags": "antonio 2019 hotel booking demand dataset expedia icdm kaggle benchmark iptal modeli soguk baslangic",
     "body": "Antonio, de Almeida & Nunes (2019): iki gerçek Portekiz oteli (Algarve resort H1: 40.060, Lizbon şehir H2: 79.330 "
             "rezervasyon; 31 değişken; iptaller dahil; PMS'ten TSQL ile çekilmiş) — iptal olasılık modeli için sektör benchmark'ı; "
             "sonuçların literatürle kıyaslanabilir. Expedia ICDM 2013: rastgeleleştirilmiş sıralamalı arama verisi — esneklik/seçim "
             "modeli için en değerli halka açık set. Yeni modele başlarken önce bunlarla eğit, sonra otelin kendi verisiyle ince ayar yap."},
    {"id": "data_simulator", "category": "veri_muhendisligi",
     "title": "Talep Simülatörü Zorunluluğu: Fiyat Politikası Backtest Edilemez",
     "tags": "talep simulator backtest choice model iptal rakip tepki politika test sahte gecmis",
     "body": "'Fiyatı 120€ yapsaydım ne olurdu?' sorusunun cevabı geçmiş veride YOK — fiyatlama politikası ham geçmişte backtest "
             "edilemez. Zorunlu altyapı: talep simülatörü = seçim modeli (fiyata göre dönüşüm) + iptal modeli + rakip tepki modeli. "
             "Robotun yeni politikaları önce simülatörde eğitilir/test edilir, sonra küçük keşif payıyla canlıya alınır. "
             "Bizim ders etki simülatörü bu ilkenin ilk katmanıdır; tam simülatör doğal yol haritasıdır."},
    {"id": "data_ml_pickup_model", "category": "veri_muhendisligi",
     "title": "Yüklü Organ: Eğitilmiş LightGBM Pickup Modeli",
     "tags": "lightgbm pickup model 500 agac otb tahmin nihai doluluk yuklu organ ml motor",
     "body": "Robota gerçek eğitilmiş bir LightGBM tahmin organı (500 ağaç) yüklendi — Antonio 2019 gerçek otel verisiyle "
             "eğitildi. Girdi: otb_now, pickup_last7/14, T (gün kala), haftanın günü, ay, hafta, hafta sonu bayrağı. Çıktı: "
             "T gün kala nihai satılacak oda tahmini. Kullanım ilkeleri: (1) uzak ufukta (T>14) güven yüksek — fiyat penceresi "
             "kararları orada verilir; (2) yakın ufukta klasik pickup ile fark azalır — istikrar (guardrail) öncelikli; "
             "(3) tahmin ile gerçekleşen her ay kıyaslanmalı (MAPE), sapma büyürse model yeniden eğitilmeli.",},
    {"id": "data_horizon", "category": "veri_muhendisligi",
     "title": "Ufuk Bulgusu: Zekâ Uzak Ufukta Kazandırır",
     "tags": "ufuk horizon t60 t3 ml kazanc pickup baseline uzak erken karar agirlik",
     "body": "Gerçek veri deneyi (Antonio seti, 91 noktalı eğri): ML'in klasik pickup baseline'ına üstünlüğü T=60 gün kala ~%50 iken "
             "T=3'te ~%11'e düşer. Ders: robotun zeki olması gereken yer varıştan hemen önce değil, fiyatın hâlâ OYNANABİLDİĞİ uzak "
             "ufuktur. Karar ağırlığını erken döneme ver: uzak ufukta cesur optimizasyon + yakın ufukta istikrar (guardrail) doğru mimaridir."},
]


async def ensure_knowledge_seeded(db) -> int:
    """İdempotent seed — eksik/güncellenmiş kayıtları upsert eder."""
    n = 0
    for doc in DEEP_KNOWLEDGE:
        await db.rm_knowledge_library.update_one(
            {"id": doc["id"]}, {"$set": doc}, upsert=True)
        n += 1
    return n


def _tokenize(text: str) -> set:
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    return {w for w in text.lower().translate(tr_map).split() if len(w) > 2}


async def retrieve_knowledge(db, query: str, k: int = 4) -> list:
    """RAG-lite: soruya en alakalı derin bilgi kayıtlarını getirir."""
    await ensure_knowledge_seeded(db)
    q = _tokenize(query or "")
    if not q:
        return []
    scored = []
    async for d in db.rm_knowledge_library.find({}, {"_id": 0}):
        toks = _tokenize(f"{d.get('title','')} {d.get('tags','')} {d.get('body','')[:400]}")
        score = len(q & toks)
        if score > 0:
            scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    return [d for _s, d in scored[:k]]


async def knowledge_context_for_chat(db, user_message: str) -> str:
    """Chat robotuna soruya göre derin bilgi enjeksiyonu."""
    hits = await retrieve_knowledge(db, user_message, k=4)
    if not hits:
        return ""
    lines = ["\nDERİN UZMANLIK BİLGİN (içselleştirilmiş — bunlar SENİN kendi bilgindir; asla 'kaynağa/kütüphaneye göre' deme, "
             "kendi uzmanlığın olarak konuş ve MUTLAKA bu otelin rakamlarına uygulanabilir adımlara çevir):"]
    for h in hits:
        lines.append(f"- [{h['title']}] {h['body']}")
    return "\n".join(lines)
