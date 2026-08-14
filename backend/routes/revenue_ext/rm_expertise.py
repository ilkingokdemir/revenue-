"""
RM Uzmanlık Beyni — robotun revenue management alanında TAM UZMAN olması.
1. Bilgi Tabanı: RM prensipleri, rakip RMS ürünleri (2026 pazarı), pazar trendleri, strateji playbook'ları.
2. Fiyat Duyarlılık (elasticity) Motoru: kendi verisinden bağlam bazlı talep esnekliği ölçer.
3. Uzman Brifingi: LLM ile pazar+rakip+duyarlılık+hafıza birleşik strateji raporu üretir.
Bilgi tabanı ve duyarlılık sonuçları Copilot chat'ine de beslenir.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import os
import uuid
import logging

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


RM_KNOWLEDGE = [
    # ── PRENSİPLER ──
    {"id": "elasticity", "category": "prensipler", "title": "Fiyat Duyarlılığı (Price Elasticity)",
     "body": "Talebin fiyat değişimine tepkisi. |e|>1 elastik (fiyat düşüşü doluluğu güçlü artırır), |e|<0.3 inelastik "
             "(fiyat artışı doluluğu bozmadan karı artırır). Altın kural: inelastik dönemlerde (yüksek talep, etkinlik, "
             "son dakika iş seyahati) fiyatı yükselt; elastik dönemlerde (düşük sezon, tatil segmenti) hedefli indirim yap."},
    {"id": "displacement", "category": "prensipler", "title": "Displacement (Yer Değiştirme) Analizi",
     "body": "Bir grup/uzun konaklama teklifini kabul etmenin, kaçırılacak bireysel (transient) geliri karşılayıp "
             "karşılamadığını ölçer. Kural: Grup geliri + yan gelir (F&B, toplantı) > kaçan transient gelir + omuz gecesi fırsatları."},
    {"id": "hurdle", "category": "prensipler", "title": "Hurdle Rate & Last Room Value (LRV)",
     "body": "Kalan her odanın minimum kabul fiyatı. Doluluk arttıkça LRV yükselir; LRV altındaki rezervasyon talepleri "
             "(ör. düşük fiyatlı OTA segmenti) kapatılır. Enterprise RMS'lerin (IDeaS G3) çekirdek mekanizmasıdır."},
    {"id": "open_pricing", "category": "prensipler", "title": "Open Pricing",
     "body": "Her segment × kanal × oda tipi × tarih hücresinin BAĞIMSIZ fiyatlanması (Duetto'nun farklılaştırıcısı). "
             "Sabit yüzde indirimler yerine her hücre kendi talebine göre optimize edilir; kapatmak yerine fiyatla yönetilir."},
    {"id": "forecasting", "category": "prensipler", "title": "Talep Tahmini (Unconstrained Demand)",
     "body": "Kısıtsız talep = gerçekleşen + reddedilen + kaçan talep. Pickup eğrisi, rezervasyon hızı (pace), "
             "aynı gün tipi geçmişi ve etkinlik takvimiyle tahmin edilir. Tahmin doğruluğu her RMS'in temelidir — "
             "kötü tahmin üstüne kurulan optimizasyon zarar verir."},
    {"id": "overbooking", "category": "prensipler", "title": "Overbooking & Wash Teorisi",
     "body": "Beklenen no-show/iptal (wash) kadar fazla satış yaparak boş oda kaybını önleme. Optimum limit: "
             "beklenen wash × güven katsayısı; walk maliyeti (başka otel + itibar) beklenen kazançla dengelenir."},
    {"id": "trevpar", "category": "prensipler", "title": "TRevPAR, GOPPAR ve Kâr-Öncelikli Fiyatlama",
     "body": "RevPAR sadece oda geliri; TRevPAR tüm gelir; GOPPAR brüt işletme kârı. Modern RM doluluk değil KÂR optimize eder: "
             "kanal komisyonu, temizlik maliyeti, F&B katkısı düşülerek net katkıya göre fiyatlanır (bu platformdaki Kâr-Öncelikli Fiyatlama)."},
    {"id": "los", "category": "prensipler", "title": "LOS (Konaklama Süresi) Optimizasyonu",
     "body": "MinLOS/MaxLOS kısıtları ve süreye göre fiyat farklılaştırma; yoğun geceyi tek gecelik rezervasyona kapatıp "
             "omuz gecelerini dolduran çok geceli konaklamalara açmak toplam geliri artırır."},
    {"id": "mix", "category": "prensipler", "title": "Segment & Kanal Mix Yönetimi",
     "body": "Doğru misafiri doğru fiyata almak: direkt kanal payını artırmak (0 komisyon vs OTA %15-18), kurumsal/grup "
             "tabanını düşük sezona, yüksek ADR'li transient'i yoğun döneme yerleştirmek. Mix, ADR'den daha fazla kâr belirler."},
    # ── RAKİPLER (2026) ──
    {"id": "rpg", "category": "rakipler", "title": "RoomPriceGenie — Bağımsız Otel Lideri",
     "body": "2026 HotelTechAwards #1. Revenue yöneticisi olmayan küçük/bağımsız oteller için otopilot basitliği ve hızlı kurulum. "
             "Zayıf yanı: enterprise derinliği ve segment bazlı optimizasyon sınırlı. Bizim farkımız: aynı basitlik + öğrenen kalıcı hafıza + kâr-öncelikli motor."},
    {"id": "ideas", "category": "rakipler", "title": "IDeaS G3 — Enterprise Standardı",
     "body": "30.000+ tesis; lüks zincirlerin varsayılanı. Güçlü: kurumsal analitik, otomatik LOS ve overbooking kontrolleri. "
             "Zayıf: kurulum karmaşası ve maliyet. Bizim farkımız: aynı LRV/hurdle mantığı, çok daha hızlı devreye alma."},
    {"id": "duetto", "category": "rakipler", "title": "Duetto GameChanger — Open Pricing Öncüsü",
     "body": "Butik gruplar için; segment/kanal bazlı bağımsız fiyatlama (Open Pricing) farklılaştırıcısı. "
             "Bizim platformda aynı Open Pricing matrisi + gece optimizer + guardrail mevcut."},
    {"id": "atomize", "category": "rakipler", "title": "Atomize (Mews) — Gerçek Zamanlı Optimizasyon",
     "body": "2024 sonunda Mews tarafından satın alındı; PMS-native entegrasyonla gerçek zamanlı fiyat optimizasyonu lideri. "
             "Trend: RMS'in PMS içinde erimesi. Bizim farkımız: PMS+RMS zaten tek platform."},
    {"id": "flyr", "category": "rakipler", "title": "FLYR Hospitality (eski Pace) — İşbirlikçi Tahmin",
     "body": "Havacılıktan gelen derin öğrenme; ekiplerin birlikte tahmin/strateji yaptığı 'collaborative forecasting'. "
             "Bizim karşılığımız: Robot Chat ile birlikte karar alma + 'Robota Uygulat'."},
    {"id": "pricelabs", "category": "rakipler", "title": "PriceLabs — Çoklu Mülk / Kısa Dönem Kiralama",
     "body": "500.000+ ünite; tatil kiralaması ve çoklu mülk portföyleri için şeffaf kural motoru. "
             "Bizim karşılığımız: STR pazar taraması + portföy (küresel/bölgesel) hafıza."},
    {"id": "lighthouse", "category": "rakipler", "title": "Lighthouse (eski OTA Insight) — Pazar Zekâsı",
     "body": "Pazar istihbaratından AI fiyat önerisine genişledi: rate shopping, parite, talep verisi. "
             "Bizim karşılığımız: Compset Radar + parite analizi + talep radarı modülleri."},
    {"id": "revevolve", "category": "rakipler", "title": "RevEvolve — Agentic Otonom Fiyatlama",
     "body": "Günlük insan onayı olmadan fiyat değişikliği uygulayan 'agentic' otonom yaklaşımın öncüsü. "
             "Bizim karşılığımız: gece optimizer + guardrail (±%10-20) + insan onaylı chat aksiyonları — EU AI Act'in insan-döngüde şartıyla uyumlu."},
    # ── PAZAR ──
    {"id": "market_size", "category": "pazar", "title": "Pazar Büyüklüğü ve Büyüme",
     "body": "Otel RMS pazarı ~4,7 milyar $ (2026) → 12,83 milyar $ (2035 projeksiyonu). RMS kullanan oteller manuel yönetime "
             "kıyasla ortalama %15-20 RevPAR artışı raporluyor."},
    {"id": "trend_realtime", "category": "pazar", "title": "Trend: Gerçek Zamanlı AI Otopilot",
     "body": "Sektör zamanlanmış fiyat güncellemesinden gerçek zamanlı AI otomasyonuna geçti; otopilot artık pazar standardı. "
             "Fark yaratan: otomasyonun ölçülen sonuçlardan ÖĞRENMESİ (bizim kapalı öğrenme döngümüz)."},
    {"id": "trend_euai", "category": "pazar", "title": "Trend: EU AI Act Uyumu",
     "body": "Algoritmik şeffaflık, insan-döngüde müdahale (human-in-the-loop) ve AB'de promosyon fiyatlarında 30 günlük "
             "taban fiyat beyanı zorunluluğu mimari belirleyici oldu. Fiyat kararlarının açıklanabilirliği (bizim Decision Assurance) kritik."},
    {"id": "trend_pms", "category": "pazar", "title": "Trend: PMS Entegrasyon Derinliği Kazandırıyor",
     "body": "CRM, F&B ve spa verisini de içen platformlar yalnız dolulukla çalışanlardan belirgin daha iyi performans veriyor. "
             "Toplam-gelir (TRevPAR) verisiyle beslenen fiyatlama ana rekabet alanı."},
    # ── STRATEJİLER ──
    {"id": "strat_profit", "category": "stratejiler", "title": "Maksimum Kârlılık Playbook'u",
     "body": "1) Net katkıya göre fiyatla (komisyon+maliyet düş). 2) Direkt kanal payını artır (web'e en iyi fiyat + üyelik). "
             "3) LRV altı talebi kapat, yukarısını yakala. 4) Upsell/ABS ile oda başı ek gelir. 5) İnelastik günlerde cesur ADR."},
    {"id": "strat_occupancy", "category": "stratejiler", "title": "Maksimum Doluluk Playbook'u",
     "body": "1) Boş gece radarı: 14 gün içi düşük doluluk günlerini erken tespit. 2) Elastik segmentlere hedefli kampanya "
             "(paket, uzun konaklama). 3) LOS kısıtlarıyla omuz gecelerini doldur. 4) Overbooking limitini wash'a göre aç. "
             "5) Son dakika kanal genişletme — ama ADR tabanını (min rate floor) koru."},
    {"id": "strat_sensitivity", "category": "stratejiler", "title": "Duyarlılık-Bazlı Fiyatlama Playbook'u",
     "body": "1) Her bağlamın (gün tipi × lead-time) esnekliğini ölç. 2) İnelastik bağlamda +%5-10 test artışları; "
             "elastikte fiyatı koru, değeri artır. 3) Sonucu ölç, kalıcı hafızaya işle. 4) A/B holdout ile doğrula. "
             "5) Guardrail ile gecelik değişimi sınırla — istikrar müşteri güveni demektir."},
]


def _classify_elasticity(e: float) -> dict:
    a = abs(e)
    if a >= 1.0:
        return {"label": "elastik (duyarlı)", "advice": "Fiyat artışlarında temkinli ol; indirim/kampanya doluluk kazandırır."}
    if a >= 0.3:
        return {"label": "orta duyarlı", "advice": "Kademeli fiyat testleri uygula; guardrail bandında kal."}
    return {"label": "inelastik (duyarsız)", "advice": "Fiyat artışı doluluğu bozmadan kârı artırır — cesur ADR fırsatı."}


async def compute_sensitivity(db, pid: str) -> dict:
    """Kendi ölçülmüş sonuçlarından bağlam bazlı fiyat esnekliği tahmini."""
    buckets: Dict[str, list] = {}
    async for o in db.ai_pricing_outcomes.find(
            {"property_id": pid, "delta_pct": {"$ne": 0}},
            {"_id": 0, "band": 1, "dow_type": 1, "delta_pct": 1, "final_occ": 1, "baseline_occ": 1}):
        base = float(o.get("baseline_occ") or 0)
        delta = float(o.get("delta_pct") or 0)
        if delta == 0:
            continue
        if base > 0:
            occ_change_pct = (float(o.get("final_occ") or 0) - base) / base * 100
        else:
            # baseline 0 ise yüzde-puan değişimi kullan (düşük veri modu)
            occ_change_pct = float(o.get("final_occ") or 0) - base
        e = occ_change_pct / delta
        buckets.setdefault(f"{o.get('dow_type','?')}|{o.get('band','?')}", []).append(e)
    rows = []
    for key, vals in buckets.items():
        e_avg = round(sum(vals) / len(vals), 2)
        cls = _classify_elasticity(e_avg)
        dow, band = key.split("|")
        rows.append({"bucket": key, "dow_type": dow, "band": band,
                     "elasticity": e_avg, "samples": len(vals), **cls})
    rows.sort(key=lambda r: -r["samples"])
    doc = {"property_id": pid, "buckets": rows, "sample_total": sum(r["samples"] for r in rows),
           "computed_at": _now(),
           "note": "Esneklik = doluluk değişim %'si / fiyat değişim %'si (kendi ölçülmüş sonuçlarından)."}
    await db.revenue_sensitivity.update_one(
        {"property_id": pid}, {"$set": doc}, upsert=True)
    return doc


async def internalize_expertise(db, pid: str) -> dict:
    """İçselleştirme: kütüphane bilgisini BU OTELİN verisiyle birleştirip
    uygulanabilir uzman kurallarına dönüştürür. Robot bunları kendi uzmanlığı olarak kullanır."""
    from datetime import timedelta
    now = _now()
    today = datetime.now(timezone.utc).date()
    rules = []

    # Otel temel verileri
    total_rooms = await db.rooms.count_documents({"property_id": pid}) or 20
    adr_rows = [float(b.get("rate") or 0) async for b in db.bookings.find(
        {"property_id": pid, "rate": {"$gt": 0}}, {"_id": 0, "rate": 1}).limit(500)]
    adr = round(sum(adr_rows) / len(adr_rows), 2) if adr_rows else 100.0

    # 1) Newsvendor: bu otele özel optimum overbooking kritik oranı
    cu = adr * 0.7
    co = adr * 1.5 + 50
    critical = round(cu / (cu + co) * 100, 1)
    rules.append({"source_id": "edu_overbooking_model", "baslik": "Optimum Overbooking Oranın",
                  "kural": f"Bu otelin newsvendor kritik oranı %{critical} (boş oda maliyeti ~{round(cu,0)} vs walk ~{round(co,0)}). "
                           f"No-show dağılımının %{critical}'lik dilimine denk gelen değeri günlük limit olarak uygula — "
                           f"Overbooking panelindeki öneriler bu disiplinle çalışır.",
                  "rakamlar": {"kritik_oran_pct": critical, "adr": adr, "walk_maliyeti": round(co, 2)}})

    # 2) Kanal miksi: direkt pay ve kâr fırsatı
    src_counts = {}
    async for b in db.bookings.find({"property_id": pid, "status": {"$nin": ["cancelled"]}},
                                    {"_id": 0, "source": 1}).limit(1000):
        s = (b.get("source") or "direct").lower()
        src_counts[s] = src_counts.get(s, 0) + 1
    total_b = sum(src_counts.values()) or 1
    direct_pct = round(src_counts.get("direct", 0) / total_b * 100, 1)
    rules.append({"source_id": "strat_max_profit_deep", "baslik": "Direkt Kanal Payın ve Kâr Kaldıracın",
                  "kural": f"Direkt pay şu an %{direct_pct}. Her +10 puan direkt pay ≈ ciroda %1.5-2 net kâr (OTA komisyon tasarrufu). "
                           f"Hedef: %{min(direct_pct + 10, 65):.0f} — web'e en iyi fiyat garantisi + üye fiyatı fence'i uygula.",
                  "rakamlar": {"direkt_pay_pct": direct_pct, "hedef_pct": round(min(direct_pct + 10, 65), 1)}})

    # 3) Fiyat değişkenliği: kendi ayar sıklığın vs +%3.07 bulgusu
    d60 = (today - timedelta(days=60)).isoformat()
    changes = await db.ai_pricing_decisions.count_documents({"property_id": pid, "run_at": {"$gte": d60}})
    per_week = round(changes / 8.6, 1)
    yeterli = per_week >= 7
    rules.append({"source_id": "study_variability", "baslik": "Fiyat Ayar Sıklığın",
                  "kural": (f"Son 60 günde {changes} fiyat kararı (haftada ~{per_week}). " +
                            ("Sıklık iyi — sık küçük ayarlar RevPAR'a ~+%3 katkı sağlar; guardrail bandında sürdür."
                             if yeterli else
                             "Bu az — fiyat değişkenliğini artıran oteller ~+%3.07 gelir kazanıyor. Gece optimizer'ını "
                             "günlük çalıştır, elle fiyat sabitleme.")),
                  "rakamlar": {"karar_60g": changes, "haftalik": per_week, "hedef_haftalik": 7}})

    # 4) Duyarlılık → ADR taktiği (kendi ölçümünden)
    sens = await db.revenue_sensitivity.find_one({"property_id": pid}, {"_id": 0})
    inel = [b for b in (sens or {}).get("buckets", []) if "inelastik" in b.get("label", "")]
    if inel:
        ctxs = ", ".join(f"{'hafta sonu' if b['dow_type']=='weekend' else 'hafta içi'} {b['band']} gün kala" for b in inel[:3])
        rules.append({"source_id": "study_elasticity", "baslik": "İnelastik Bağlamlarında Cesur ADR",
                      "kural": f"Kendi ölçümlerine göre şu bağlamlarda talep İNELASTİK: {ctxs}. Buralarda fiyat kırma — "
                               f"+%5-10 ADR testleri uygula; doluluk bozulmaz, kâr artar. Sonuçlar otomatik ölçülüp hafızana işlenir.",
                      "rakamlar": {"inelastik_baglam": len(inel)}})

    # 5) LRV disiplini: önümüzdeki 14 günde yüksek doluluk günleri
    high_days = []
    for i in range(14):
        ds = (today + timedelta(days=i)).isoformat()
        sold = await db.bookings.count_documents({
            "property_id": pid, "status": {"$nin": ["cancelled"]},
            "check_in": {"$lte": ds}, "check_out": {"$gt": ds}})
        if sold / total_rooms >= 0.9:
            high_days.append(ds)
    if high_days:
        rules.append({"source_id": "study_unavailability", "baslik": "Son Oda Değeri (LRV) Koruması",
                      "kural": f"Önümüzdeki 14 günde {len(high_days)} gün %90+ doluluk ({', '.join(high_days[:4])}…). "
                               f"Bu günlerde düşük fiyatlı segment/kanalları stratejik kapat — son odaları geç gelen yüksek "
                               f"değerli talebe sakla (bu disiplin +%34'e kadar gelir farkı yaratır).",
                      "rakamlar": {"yuksek_doluluk_gun": len(high_days), "gunler": high_days[:5]}})

    # 6) Pace okuma: son 7 gün vs önceki 7 gün rezervasyon hızı
    d7 = (today - timedelta(days=7)).isoformat()
    d14 = (today - timedelta(days=14)).isoformat()
    p1 = await db.bookings.count_documents({"property_id": pid, "created_at": {"$gte": d7}})
    p0 = await db.bookings.count_documents({"property_id": pid, "created_at": {"$gte": d14, "$lt": d7}})
    trend = round((p1 - p0) / p0 * 100, 1) if p0 else 0.0
    if abs(trend) >= 15 and p0:
        aksiyon = ("pickup hızlanıyor → fiyat artış penceresi açık; inelastik bağlamlardan başla."
                   if trend > 0 else
                   "pickup yavaşlıyor → önce segment kırılımına bak; genel yavaşlamaysa fence'li hedefli teklif aç, fiyat kırma.")
    else:
        aksiyon = "pace normal bantta → rakip fiyat hareketlerine refleks verme, kendi eğrine güven."
    rules.append({"source_id": "tech_pace_signals", "baslik": "Güncel Pace Okuman",
                  "kural": f"Son 7 gün {p1} rezervasyon vs önceki 7 gün {p0} (%{trend:+}). Uzman okuma: {aksiyon}",
                  "rakamlar": {"son7": p1, "onceki7": p0, "trend_pct": trend}})

    # 7) Spillage / Spoilage radarı (yeni içselleştirilen denge dersi)
    spill_days, spoil_days = [], []
    for i in range(30):
        ds = (today + timedelta(days=i)).isoformat()
        sold = await db.bookings.count_documents({
            "property_id": pid, "status": {"$nin": ["cancelled"]},
            "check_in": {"$lte": ds}, "check_out": {"$gt": ds}})
        occ_r = sold / total_rooms
        if occ_r >= 0.95 and i > 7:
            spill_days.append(ds)
        elif occ_r < 0.5 and i <= 7:
            spoil_days.append(ds)
    if spill_days or spoil_days:
        parca = []
        if spill_days:
            parca.append(f"{len(spill_days)} gün 7+ gün kala %95+ doldu ({spill_days[0]}…) → SPILLAGE işareti: bu günler "
                         f"muhtemelen ucuza satıldı, benzer günlerde fiyat tabanını yükselt")
        if spoil_days:
            parca.append(f"{len(spoil_days)} gün 7 gün içinde <%50 doluluk ({spoil_days[0]}…) → SPOILAGE riski: fence'li "
                         f"hedefli teklif aç (üye fiyatı/min-2-gece), fiyatı çıplak kırma")
        rules.append({"source_id": "edu_spillage_spoilage", "baslik": "Spillage/Spoilage Dengesi",
                      "kural": "İki zarar radarın: " + "; ".join(parca) + ".",
                      "rakamlar": {"spillage_gun": len(spill_days), "spoilage_gun": len(spoil_days)}})

    # Kaydet (property başına güncel set)
    await db.rm_expert_rules.delete_many({"property_id": pid})
    for i, r in enumerate(rules):
        r.update({"id": str(uuid.uuid4())[:8], "property_id": pid, "sira": i + 1,
                  "status": "aktif", "computed_at": now})
        await db.rm_expert_rules.insert_one(r)
        r.pop("_id", None)
    return {"property_id": pid, "rules_count": len(rules), "rules": rules, "computed_at": now}


async def expertise_context_for_llm(db, pid: str) -> str:
    """Copilot/Stratejist prompt'una eklenen uzmanlık özeti."""
    parts = ["\nRM UZMANLIK TABANI (bunlar SENİN içselleştirilmiş bilgindir — kaynak anmadan kendi uzmanlığın olarak uygula):"]
    for k in RM_KNOWLEDGE:
        if k["category"] in ("prensipler", "stratejiler"):
            parts.append(f"- {k['title']}: {k['body'][:160]}")
    er = await db.rm_expert_rules.find({"property_id": pid}, {"_id": 0}).sort("sira", 1).to_list(10)
    if er:
        parts.append("\nBU OTELE ÖZEL İÇSELLEŞTİRDİĞİN UZMAN KURALLARIN (rakamlar canlı veriden — tavsiyelerini bunlara dayandır):")
        for r in er:
            parts.append(f"- {r['baslik']}: {r['kural']}")
    sens = await db.revenue_sensitivity.find_one({"property_id": pid}, {"_id": 0})
    if sens and sens.get("buckets"):
        parts.append("\nFİYAT DUYARLILIK ÖLÇÜMLERİ (bu otelin kendi verisi):")
        for b in sens["buckets"][:6]:
            parts.append(f"- {b['dow_type']} / {b['band']} gün kala: esneklik {b['elasticity']} → {b['label']} ({b['samples']} örnek). {b['advice']}")
    parts.append("\nRAKİP RMS PAZARI 2026 (kısa): RoomPriceGenie bağımsız otel lideri; IDeaS G3 enterprise standardı; "
                 "Duetto open pricing; Atomize (Mews) gerçek zamanlı; FLYR işbirlikçi tahmin; PriceLabs çoklu mülk; "
                 "Lighthouse pazar zekâsı; RevEvolve agentic otonom. Pazar ~4,7 mlr $ → 12,8 mlr $ (2035); "
                 "trendler: gerçek zamanlı AI otopilot, EU AI Act şeffaflık, PMS-derin entegrasyon; RMS kullanan oteller %15-20 RevPAR artışı görüyor.")
    return "\n".join(parts)


async def generate_expert_brief(db, pid: str, user_email: str = "robot") -> dict:
    """LLM ile tam uzman strateji brifingi: pazar + rakip + duyarlılık + hafıza + KPI."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    await compute_sensitivity(db, pid)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_rooms = await db.rooms.count_documents({"property_id": pid}) or 20
    booked = await db.bookings.count_documents({
        "property_id": pid, "status": {"$nin": ["cancelled"]},
        "check_in": {"$lte": today}, "check_out": {"$gt": today}})
    occ = round(booked / total_rooms * 100, 1)
    mem = await db.revenue_brain_memory.find({"property_id": pid}, {"_id": 0, "detail": 1}).to_list(6)
    expertise = await expertise_context_for_llm(db, pid)
    try:
        from routes.revenue_ext.rm_knowledge_seed import retrieve_knowledge
        deep = await retrieve_knowledge(db, "maksimum karlilik doluluk strateji fiyat esneklik pace", k=5)
        expertise += "\n\nDERİN BİLGİ (vakalar/modeller — brifingde kullan):\n" + "\n".join(
            f"- [{d['title']}] {d['body'][:220]}" for d in deep)
    except Exception:
        pass
    prompt = (f"Otel: {pid} · Bugün doluluk %{occ} ({booked}/{total_rooms}).\n"
              f"KALICI HAFIZA DERSLERİ:\n" + "\n".join(f"- {m['detail']}" for m in mem) + "\n" + expertise +
              "\n\nGÖREV: Bu otelin yöneticisi için TÜRKÇE, uzman seviyesinde bir revenue strateji brifingi yaz. Bölümler: "
              "1) Pazar Konumu ve Rakip RMS'lere Karşı Farklılaşma, 2) Maksimum Kârlılık Stratejisi (somut adımlar), "
              "3) Maksimum Doluluk Stratejisi, 4) Fiyat Duyarlılığı Taktikleri (ölçümlere dayan), "
              "5) Bu Hafta Yapılacak 5 Somut Aksiyon. Rakamlarla, kısa ve keskin yaz.")
    chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
                   session_id=f"rm-brief-{pid}-{uuid.uuid4().hex[:8]}",
                   system_message="Sen 20 yıllık deneyimli, IDeaS/Duetto/Atomize düzeyinde uzman bir otel revenue management danışmanısın. Türkçe, veri odaklı ve keskin yazarsın.").with_model("openai", "gpt-5.2")
    content = await chat.send_message(UserMessage(text=prompt))
    doc = {"id": str(uuid.uuid4())[:8], "property_id": pid, "content": content,
           "created_by": user_email, "created_at": _now()}
    await db.rm_expert_briefs.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def measure_campaign_impact(db, pid: str) -> dict:
    """Kampanya Etki Takibi: fence'li gecelerin doluluk değişimini ölç, robota öğret."""
    from routes.revenue_ext.ml_pickup import _stay_counts
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cap = await db.rooms.count_documents({"property_id": pid}) or 20
    async for c in db.promo_campaigns.find(
            {"property_id": pid, "type": "uye_fence", "date": {"$lt": today},
             "measured": {"$ne": True}}, {"_id": 0, "date": 1, "otb_at_apply": 1}):
        final = (await _stay_counts(db, pid, c["date"]))["otb"]
        base = int(c.get("otb_at_apply") or 0)
        gain = final - base
        occ = round(final / cap * 100, 1)
        verdict = "worked" if (gain >= 1 or occ >= 50) else "neutral"
        await db.promo_campaigns.update_one(
            {"property_id": pid, "date": c["date"], "type": "uye_fence"},
            {"$set": {"measured": True, "final_rooms": final, "pickup_gain": gain,
                      "final_occ_pct": occ, "verdict": verdict, "measured_at": _now()}})
    measured = await db.promo_campaigns.find(
        {"property_id": pid, "type": "uye_fence", "measured": True}, {"_id": 0}).to_list(100)
    n = len(measured)
    stats = {"measured": n, "avg_pickup_gain": round(sum(m["pickup_gain"] for m in measured) / n, 2) if n else None,
             "success_rate": round(sum(1 for m in measured if m["verdict"] == "worked") / n * 100, 1) if n else None}
    if n >= 3:
        detail = (f"Fence'li boş-gece kampanyaları: {n} ölçülmüş gecede ortalama +{stats['avg_pickup_gain']} oda pickup, "
                  f"başarı %{stats['success_rate']}. Bu ders ölçülmeye devam ediyor; başarı düşerse strateji gözden geçirilir.")
        await db.revenue_brain_memory.update_one(
            {"property_id": pid, "bucket_key": "fence_kampanya"},
            {"$set": {"property_id": pid, "bucket_key": "fence_kampanya", "kind": "kampanya_dersi",
                      "importance": "firsat" if (stats["success_rate"] or 0) >= 50 else "kritik",
                      "title": "Fence'li Boş Gece Kampanyası", "detail": detail,
                      "factor": 1.0, "samples": n,
                      "worked_rate": round((stats["success_rate"] or 0) / 100, 2),
                      "status": "aktif", "last_confirmed": _now()},
             "$setOnInsert": {"id": str(uuid.uuid4()), "first_learned": _now()},
             "$inc": {"times_confirmed": 1}}, upsert=True)
    return {"property_id": pid, "stats": stats, "campaigns": measured[-20:]}


async def exploration_report(db, pid: str) -> dict:
    """Keşif Sonuç Raporu: explorer denemelerinin ölçülmüş sonuçları ve temiz esneklik tahmini."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = await db.ai_pricing_decisions.count_documents({"property_id": pid, "set_by": "explorer"})
    pending = await db.ai_pricing_decisions.count_documents(
        {"property_id": pid, "set_by": "explorer", "date": {"$gte": today}})
    rows, elast = [], []
    stats = {"worked": 0, "neutral": 0, "hurt": 0}
    async for dec in db.ai_pricing_decisions.find(
            {"property_id": pid, "set_by": "explorer", "date": {"$lt": today}},
            {"_id": 0, "date": 1, "delta_pct": 1, "days_out": 1}).sort("date", -1).limit(60):
        out = await db.ai_pricing_outcomes.find_one(
            {"property_id": pid, "stay_date": dec["date"]},
            {"_id": 0, "verdict": 1, "final_occ": 1, "baseline_occ": 1})
        if not out:
            continue
        v = out.get("verdict", "neutral")
        stats[v] = stats.get(v, 0) + 1
        base, delta = float(out.get("baseline_occ") or 0), float(dec.get("delta_pct") or 0)
        if delta:
            ch = ((float(out.get("final_occ") or 0) - base) / base * 100) if base > 0 else (float(out.get("final_occ") or 0) - base)
            elast.append(ch / delta)
        rows.append({"date": dec["date"], "delta_pct": dec["delta_pct"], "days_out": dec.get("days_out"),
                     "verdict": v, "final_occ": out.get("final_occ"), "baseline_occ": out.get("baseline_occ")})
    measured_n = len(rows)
    clean_e = round(sum(elast) / len(elast), 2) if elast else None
    return {"property_id": pid, "total_experiments": total, "pending": pending, "measured": measured_n,
            "verdicts": stats, "clean_elasticity": clean_e,
            "rows": rows[:30],
            "note": "Keşif denemeleri rastgele olduğu için buradaki esneklik tahmini endojeniteden arınmış TEMİZ ölçümdür. "
                    "Denemeler biriktikçe güven artar; kayıp değil, esneklik eğrisinin bedelidir."}


def create_rm_expertise_router(db, require_roles):
    router = APIRouter(prefix="/rm-expertise", tags=["rm-expertise"])
    ROLES = ("admin", "manager")

    @router.get("/knowledge")
    async def knowledge(category: str = "", _u: dict = Depends(require_roles(*ROLES))):
        items = [k for k in RM_KNOWLEDGE if not category or k["category"] == category]
        cats = sorted({k["category"] for k in RM_KNOWLEDGE})
        return {"count": len(items), "items": items, "categories": cats}

    @router.get("/library")
    async def library(q: str = "", category: str = "", _u: dict = Depends(require_roles(*ROLES))):
        """Derin bilgi kütüphanesi — RMS çalışma prensipleri, akademik vakalar, eğitim, teknik modeller."""
        from routes.revenue_ext.rm_knowledge_seed import ensure_knowledge_seeded, retrieve_knowledge
        total = await ensure_knowledge_seeded(db)
        if q:
            items = await retrieve_knowledge(db, q, k=10)
            if category:
                items = [i for i in items if i["category"] == category]
        else:
            flt = {"category": category} if category else {}
            items = await db.rm_knowledge_library.find(flt, {"_id": 0}).to_list(100)
        cats = await db.rm_knowledge_library.distinct("category")
        return {"count": len(items), "total": total, "items": items, "categories": sorted(cats)}

    @router.get("/{pid}/ml-pickup")
    async def ml_pickup(pid: str, days: int = 30, _u: dict = Depends(require_roles(*ROLES))):
        """Kullanıcının yüklediği eğitilmiş LightGBM modeliyle nihai doluluk tahmini."""
        from routes.revenue_ext.ml_pickup import ml_pickup_forecast
        return await ml_pickup_forecast(db, pid, days)

    @router.get("/{pid}/campaign-impact")
    async def campaign_impact(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await measure_campaign_impact(db, pid)

    @router.get("/{pid}/exploration-report")
    async def exploration_rep(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await exploration_report(db, pid)

    @router.get("/{pid}/forecast-scorecard")
    async def forecast_scorecard(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Tahmin karnesi: ML tahminleri vs gerçekleşen — ufuk bazlı MAPE."""
        from routes.revenue_ext.ml_pickup import log_ml_forecasts, score_forecasts
        await log_ml_forecasts(db, pid)
        return await score_forecasts(db, pid)

    @router.post("/{pid}/empty-night-campaigns")
    async def empty_night_campaigns(pid: str, current_user: dict = Depends(require_roles(*ROLES))):
        """Boş gece otomasyonu: ML'in işaretlediği riskli gecelere fence'li kampanya (1 tık)."""
        from routes.revenue_ext.ml_pickup import ml_pickup_forecast
        f = await ml_pickup_forecast(db, pid, days=30)
        now, created = _now(), []
        for ds in f["empty_risk_dates"]:
            await db.promo_campaigns.update_one(
                {"property_id": pid, "date": ds, "type": "uye_fence"},
                {"$set": {"property_id": pid, "date": ds, "type": "uye_fence",
                          "discount_pct": 8, "min_los": 2, "channel": "direct",
                          "status": "aktif", "applied_at": now,
                          "applied_by": current_user.get("email", ""),
                          "aciklama": "ML boş gece riski — üye fiyatı (CUG) %8 + min 2 gece; ADR tabanı korunur"},
                 "$setOnInsert": {"id": str(uuid.uuid4())[:8]}}, upsert=True)
            created.append(ds)
        return {"ok": True, "campaign_dates": created,
                "detail": f"{len(created)} riskli geceye fence'li kampanya uygulandı (üye fiyatı %8, min 2 gece — açık fiyat kırılmadı)"}

    @router.get("/{pid}/empty-night-campaigns")
    async def list_campaigns(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        items = await db.promo_campaigns.find(
            {"property_id": pid, "type": "uye_fence", "status": "aktif"},
            {"_id": 0}).sort("date", 1).to_list(60)
        return {"count": len(items), "items": items}

    @router.post("/{pid}/weekly-brief-now")
    async def weekly_brief_now(pid: str, current_user: dict = Depends(require_roles(*ROLES))):
        """Haftalık uzman brifingini şimdi üret ve sohbete bırak."""
        doc = await generate_expert_brief(db, pid, current_user.get("email", ""))
        await db.revenue_copilot_messages.insert_one({
            "id": str(uuid.uuid4())[:8], "property_id": pid, "user_id": "robot-brifing",
            "role": "assistant",
            "content": "📋 **HAFTALIK UZMAN BRİFİNGİ** (robot tarafından otomatik hazırlandı)\n\n" + doc["content"],
            "created_at": _now()})
        return {"ok": True, "detail": "Brifing üretildi ve sohbete bırakıldı", "brief_id": doc["id"]}

    @router.post("/{pid}/internalize")
    async def internalize(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Kütüphane bilgisini bu otelin verisiyle uygulanabilir uzman kurallarına dönüştür."""
        return await internalize_expertise(db, pid)

    @router.get("/{pid}/expert-rules")
    async def expert_rules(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rules = await db.rm_expert_rules.find({"property_id": pid}, {"_id": 0}).sort("sira", 1).to_list(20)
        return {"property_id": pid, "count": len(rules), "rules": rules}

    @router.post("/{pid}/analyze-sensitivity")
    async def analyze_sensitivity(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await compute_sensitivity(db, pid)

    @router.get("/{pid}/sensitivity")
    async def get_sensitivity(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        doc = await db.revenue_sensitivity.find_one({"property_id": pid}, {"_id": 0})
        return doc or {"property_id": pid, "buckets": [], "sample_total": 0,
                       "note": "Henüz analiz yok — 'Analiz Et' ile başlatın."}

    @router.post("/{pid}/expert-brief")
    async def expert_brief(pid: str, current_user: dict = Depends(require_roles(*ROLES))):
        return await generate_expert_brief(db, pid, current_user.get("email", ""))

    @router.get("/{pid}/expert-brief/latest")
    async def latest_brief(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        doc = await db.rm_expert_briefs.find_one(
            {"property_id": pid}, {"_id": 0}, sort=[("created_at", -1)])
        return doc or {"property_id": pid, "content": None}

    return router
