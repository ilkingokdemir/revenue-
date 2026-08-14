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


async def expertise_context_for_llm(db, pid: str) -> str:
    """Copilot/Stratejist prompt'una eklenen uzmanlık özeti."""
    parts = ["\nRM UZMANLIK TABANI (robot bu alanda tam uzmandır — gerektiğinde atıf yap):"]
    for k in RM_KNOWLEDGE:
        if k["category"] in ("prensipler", "stratejiler"):
            parts.append(f"- {k['title']}: {k['body'][:160]}")
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


def create_rm_expertise_router(db, require_roles):
    router = APIRouter(prefix="/rm-expertise", tags=["rm-expertise"])
    ROLES = ("admin", "manager")

    @router.get("/knowledge")
    async def knowledge(category: str = "", _u: dict = Depends(require_roles(*ROLES))):
        items = [k for k in RM_KNOWLEDGE if not category or k["category"] == category]
        cats = sorted({k["category"] for k in RM_KNOWLEDGE})
        return {"count": len(items), "items": items, "categories": cats}

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
