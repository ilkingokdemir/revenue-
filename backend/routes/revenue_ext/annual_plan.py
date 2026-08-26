"""
Yıllık Plan D90–365 (Annual Plan) — RevenueIQ gap P1.
Şekil × seviye ayrımı: mevsim/haftagünü ŞEKLİ 730 günlük rezervasyon geçmişindeki
oranlardan öğrenilir; SEVİYE yakın pencerenin (30 gün) medyan fiyatından gelir.
Fail-closed: şekil için yeterli örneklem yoksa ve operatör çapa (anchor) vermezse plan üretilmez.
Sürüm arşivi: her plan sürümlenir; yayın plandan AYRI ve açık bir operatör eylemidir.
Rakip sapma manşeti: plan pazara göre nerede — tek cümlelik dürüst özet.
Collections: annual_plans
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import statistics
import uuid

MIN_SHAPE_NIGHTS = 60
PLAN_START_DAY = 90
PLAN_END_DAY = 365


def _now():
    return datetime.now(timezone.utc)


async def _learn_shape(db, pid: str) -> Dict:
    """730 günlük geçmişten ay ve haftagünü endeksleri (büzülmeli/shrinkage)."""
    today = _now().date()
    start = (today - timedelta(days=730)).isoformat()
    bks = await db.bookings.find(
        {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
         "check_in": {"$gte": start, "$lte": today.isoformat()}},
        {"_id": 0, "check_in": 1, "check_out": 1}).to_list(10000)
    night_counts = {}
    for b in bks:
        try:
            ci = datetime.strptime(b["check_in"], "%Y-%m-%d").date()
            co = datetime.strptime(b["check_out"], "%Y-%m-%d").date()
        except Exception:
            continue
        d = ci
        while d < co and d <= today:
            night_counts[d] = night_counts.get(d, 0) + 1
            d += timedelta(days=1)
    sample_nights = len(night_counts)
    if sample_nights == 0:
        return {"sample_nights": 0, "month_idx": {}, "dow_idx": {}}
    overall = sum(night_counts.values()) / sample_nights
    m_sum, m_n, d_sum, d_n = {}, {}, {}, {}
    for d, c in night_counts.items():
        m_sum[d.month] = m_sum.get(d.month, 0) + c
        m_n[d.month] = m_n.get(d.month, 0) + 1
        wd = d.weekday()
        d_sum[wd] = d_sum.get(wd, 0) + c
        d_n[wd] = d_n.get(wd, 0) + 1
    month_idx, dow_idx = {}, {}
    for m in range(1, 13):
        n = m_n.get(m, 0)
        raw = (m_sum.get(m, 0) / n / overall) if n else 1.0
        w = n / (n + 10)  # küçük hücre nötre büzülür
        month_idx[str(m)] = round(1.0 + (raw - 1.0) * w, 3)
    for wd in range(7):
        n = d_n.get(wd, 0)
        raw = (d_sum.get(wd, 0) / n / overall) if n else 1.0
        w = n / (n + 10)
        dow_idx[str(wd)] = round(1.0 + (raw - 1.0) * w, 3)
    return {"sample_nights": sample_nights, "month_idx": month_idx, "dow_idx": dow_idx}


async def _near_level(db, pid: str) -> float:
    """Yakın 30 günün medyan efektif fiyatı (motorun sağlıklı yönettiği pencere)."""
    today = _now().date()
    rates = []
    base = 0.0
    rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0, "base_price": 1},
                                      sort=[("base_price", 1)])
    if rt:
        base = float(rt.get("base_price", 0))
    for i in range(30):
        day = (today + timedelta(days=i)).isoformat()
        ov = await db.rate_overrides.find_one(
            {"property_id": pid, "date": day, "custom_rate": {"$gt": 0}}, {"_id": 0})
        rates.append(float(ov["custom_rate"]) if ov else base)
    rates = [r for r in rates if r > 0]
    return round(statistics.median(rates), 2) if rates else 0.0


async def _comp_deviation(db, pid: str, days: list) -> Dict:
    """Rakip sapma manşeti — comp_rate_snapshots medyanına göre."""
    plan_by_date = {d["date"]: d["price"] for d in days}
    pipeline = [
        {"$match": {"property_id": pid, "date": {"$in": list(plan_by_date.keys())}}},
        {"$group": {"_id": "$date", "rates": {"$push": "$rate"}}},
    ]
    devs = []
    async for r in db.comp_rate_snapshots.aggregate(pipeline):
        med = statistics.median(r["rates"])
        if med > 0:
            devs.append((plan_by_date[r["_id"]] - med) / med * 100)
    if not devs:
        return {"headline": "Rakip verisi yok — kıyas fail-closed dışarıda bırakıldı.",
                "avg_dev_pct": None, "days_compared": 0}
    avg = round(sum(devs) / len(devs), 1)
    if avg > 3:
        word = f"pazarın %{abs(avg)} ÜZERİNDE"
    elif avg < -3:
        word = f"pazarın %{abs(avg)} ALTINDA"
    else:
        word = "pazarla uyumlu (±%3 bandında)"
    return {"headline": f"Plan {word} duruyor — {len(devs)} gün rakip medyanıyla kıyaslandı.",
            "avg_dev_pct": avg, "days_compared": len(devs)}


async def generate_plan(db, pid: str, anchor_level: float | None, notes: str, user_name: str) -> Dict:
    shape = await _learn_shape(db, pid)
    level_source = "near_window"
    level = await _near_level(db, pid)
    if anchor_level:
        level = float(anchor_level)
        level_source = "operator_anchor"
    # FAIL-CLOSED
    if shape["sample_nights"] < MIN_SHAPE_NIGHTS and not anchor_level:
        raise HTTPException(422, {
            "fail_closed": True,
            "reason": (f"Şekil için yeterli örneklem yok ({shape['sample_nights']}/{MIN_SHAPE_NIGHTS} gece). "
                       "Plan üretilmedi. Operatör başlangıç fiyat seviyesi (anchor_level) girerse "
                       "nötr şekille plan kurulur.")})
    if level <= 0:
        raise HTTPException(422, {"fail_closed": True,
                                  "reason": "Seviye bilinmiyor (yakın pencerede fiyat yok, çapa da verilmedi). Plan üretilmedi."})
    floors = await db.min_rate_floors.find_one(
        {"property_id": pid, "room_type_id": "all"}, {"_id": 0}) or {}
    fl = floors.get("standard_min_rate")
    cap = floors.get("standard_max_rate")
    today = _now().date()
    m_idx = shape["month_idx"] or {str(m): 1.0 for m in range(1, 13)}
    d_idx = shape["dow_idx"] or {str(w): 1.0 for w in range(7)}
    days = []
    for off in range(PLAN_START_DAY, PLAN_END_DAY + 1):
        d = today + timedelta(days=off)
        mi = float(m_idx.get(str(d.month), 1.0))
        di = float(d_idx.get(str(d.weekday()), 1.0))
        price = level * mi * di
        if fl is not None:
            price = max(price, float(fl))
        if cap is not None:
            price = min(price, float(cap))
        days.append({"date": d.isoformat(), "price": round(price, 2),
                     "month_idx": mi, "dow_idx": di})
    comp = await _comp_deviation(db, pid, days)
    version = await db.annual_plans.count_documents({"property_id": pid}) + 1
    plan = {"id": str(uuid.uuid4()), "property_id": pid, "version": version,
            "created_at": _now().isoformat(), "created_by": user_name,
            "level": level, "level_source": level_source,
            "shape_sample_nights": shape["sample_nights"],
            "month_idx": m_idx, "dow_idx": d_idx,
            "horizon": f"D{PLAN_START_DAY}–D{PLAN_END_DAY}",
            "days": days, "comp_deviation": comp,
            "notes": (notes or "")[:300], "published_at": None, "published_days": 0}
    await db.annual_plans.insert_one(dict(plan))
    plan.pop("_id", None)
    return plan


def create_annual_plan_router(db, require_roles):
    router = APIRouter(prefix="/annual-plan", tags=["annual-plan"])
    ROLES = ("admin", "manager")

    @router.post("/{pid}/generate")
    async def generate(pid: str, data: Dict = None, u: dict = Depends(require_roles(*ROLES))):
        data = data or {}
        return await generate_plan(db, pid, data.get("anchor_level"),
                                   data.get("notes", ""), u.get("name") or u.get("email", ""))

    @router.get("/{pid}/versions")
    async def versions(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        vs = await db.annual_plans.find(
            {"property_id": pid},
            {"_id": 0, "days": 0, "month_idx": 0, "dow_idx": 0}).sort("version", -1).to_list(50)
        return {"versions": vs}

    @router.get("/{pid}/versions/{plan_id}")
    async def get_version(pid: str, plan_id: str, _u: dict = Depends(require_roles(*ROLES))):
        p = await db.annual_plans.find_one({"id": plan_id, "property_id": pid}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Plan sürümü bulunamadı")
        return p

    @router.get("/{pid}/latest")
    async def latest(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        p = await db.annual_plans.find_one({"property_id": pid}, {"_id": 0}, sort=[("version", -1)])
        return {"latest": p}

    @router.post("/{pid}/versions/{plan_id}/publish")
    async def publish(pid: str, plan_id: str, u: dict = Depends(require_roles(*ROLES))):
        """Yayın plandan AYRI, açık operatör eylemidir — D90+ tarihlere override yazar."""
        p = await db.annual_plans.find_one({"id": plan_id, "property_id": pid}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Plan sürümü bulunamadı")
        actor = f"annual-plan-v{p['version']}"
        now = _now().isoformat()
        applied = 0
        # Operatör egemenliği: yayınlanan hücrelerdeki robot kiralarını iptal et
        await db.rate_cell_leases.delete_many(
            {"property_id": pid, "room_type_id": "",
             "date": {"$in": [d["date"] for d in p["days"]]}})
        for d in p["days"]:
            await db.rate_overrides.update_one(
                {"property_id": pid, "room_type_id": "", "date": d["date"]},
                {"$set": {"custom_rate": d["price"], "set_by": actor,
                          "reason": f"Yıllık plan v{p['version']} yayını",
                          "updated_at": now}}, upsert=True)
            applied += 1
        await db.annual_plans.update_one(
            {"id": plan_id},
            {"$set": {"published_at": now, "published_days": applied,
                      "published_by": u.get("name") or u.get("email", "")}})
        return {"ok": True, "applied_days": applied, "actor": actor}

    return router
