"""Fiyat Karışımı Analizi (Rate Mix) — rezervasyonları taban/orta/yüksek katmanlara
ayırır, LMF + lead-time çıkarır, sweet-spot fiyat önerir ve tek tıkla uygular."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict, List, Optional
import uuid

ACTOR = "rate-mix"
ACTIVE = {"$nin": ["cancelled", "no_show", "pending", "pending_payment"]}


def _now():
    return datetime.now(timezone.utc)


def _rate_of(b: Dict) -> float:
    r = b.get("rate_per_night") or b.get("rate")
    if not r:
        tp, n = b.get("total_price"), b.get("nights") or 1
        r = (float(tp) / max(int(n), 1)) if tp else 0
    return float(r or 0)


def _lead_days(b: Dict) -> Optional[int]:
    try:
        ld = (ddate.fromisoformat(b["check_in"][:10])
              - ddate.fromisoformat(b["created_at"][:10])).days
        return ld if ld >= 0 else None
    except Exception:
        return None


async def analyze_property(db, pid: str, days: int = 365) -> Optional[Dict]:
    since = (ddate.today() - timedelta(days=days)).isoformat()
    rows = await db.bookings.find(
        {"property_id": pid, "status": ACTIVE, "check_in": {"$gte": since}},
        {"_id": 0, "rate_per_night": 1, "rate": 1, "total_price": 1, "nights": 1,
         "rooms": 1, "created_at": 1, "check_in": 1, "check_out": 1}).to_list(15000)
    pts = []
    for b in rows:
        r = _rate_of(b)
        if r <= 0:
            continue
        rn = max(int(b.get("rooms", 1) or 1), 1) * max(int(b.get("nights", 1) or 1), 1)
        pts.append({"rate": r, "rn": rn, "lead": _lead_days(b)})
    if len(pts) < 10:
        return None
    pts.sort(key=lambda x: x["rate"])
    total_rn = sum(p["rn"] for p in pts)
    # fiyat bandı sınırları: p05-p95 aralığı 3 eşit banda bölünür (gerçek karışım görünür)
    n = len(pts)
    lo, hi = pts[max(0, n // 20)]["rate"], pts[min(n - 1, n * 19 // 20)]["rate"]
    if hi <= lo:
        hi = pts[-1]["rate"]
    step = (hi - lo) / 3 or 1
    bounds = [round(lo + step, 2), round(lo + 2 * step, 2)]
    tiers = []
    for name, lo, hi in (("floor", 0, bounds[0]), ("mid", bounds[0], bounds[1]),
                         ("high", bounds[1], float("inf"))):
        grp = [p for p in pts if lo < p["rate"] <= hi] if name != "floor" else \
              [p for p in pts if p["rate"] <= hi]
        rn = sum(p["rn"] for p in grp)
        leads = sorted(p["lead"] for p in grp if p["lead"] is not None)
        tiers.append({"tier": name, "room_nights": rn,
                      "share_pct": round(rn / total_rn * 100, 1),
                      "avg_rate": round(sum(p["rate"] * p["rn"] for p in grp) / rn, 0) if rn else 0,
                      "median_lead": leads[len(leads) // 2] if leads else None,
                      "bookings": len(grp)})
    adr = round(sum(p["rate"] * p["rn"] for p in pts) / total_rn, 0)
    # LMF: 0-3 gün kala satılanların ortalaması
    lm = [p for p in pts if p["lead"] is not None and p["lead"] <= 3]
    lm_rn = sum(p["rn"] for p in lm)
    lmf = round(sum(p["rate"] * p["rn"] for p in lm) / lm_rn, 0) if lm_rn else tiers[0]["avg_rate"]
    floor_leads = sorted(p["lead"] for p in pts if p["lead"] is not None
                         and p["rate"] <= bounds[0])
    lmf_lead = floor_leads[len(floor_leads) // 2] if floor_leads else None
    # doluluk (son 90 gün)
    total_rooms = 0
    for rt in await db.room_types.find({"property_id": pid},
                                       {"_id": 0, "total_rooms": 1}).to_list(50):
        total_rooms += int(rt.get("total_rooms", 0))
    occ = None
    if total_rooms:
        occ_since = (ddate.today() - timedelta(days=90)).isoformat()
        today = ddate.today().isoformat()
        sold = 0
        async for b in db.bookings.find(
                {"property_id": pid, "status": ACTIVE,
                 "check_in": {"$lt": today}, "check_out": {"$gt": occ_since}},
                {"_id": 0, "check_in": 1, "check_out": 1, "rooms": 1}):
            try:
                ci = max(ddate.fromisoformat(b["check_in"][:10]), ddate.fromisoformat(occ_since))
                co = min(ddate.fromisoformat(b["check_out"][:10]), ddate.today())
                sold += max((co - ci).days, 0) * max(int(b.get("rooms", 1) or 1), 1)
            except Exception:
                pass
        occ = round(sold / (total_rooms * 90) * 100, 1)
    rec = _recommend(tiers, adr, _wpct(pts, total_rn, 0.9))
    prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1})
    return {"property_id": pid, "name": (prop or {}).get("name", pid),
            "rooms": total_rooms, "occ_pct": occ, "adr": adr,
            "lmf": lmf, "lmf_lead": lmf_lead, "tiers": tiers,
            "sample": {"bookings": len(pts), "room_nights": total_rn, "days": days},
            "recommendation": rec}


def _wpct(pts: List[Dict], total_rn: int, q: float) -> float:
    acc, cut = 0, total_rn * q
    for p in pts:
        acc += p["rn"]
        if acc >= cut:
            return p["rate"]
    return pts[-1]["rate"]


def _recommend(tiers: List[Dict], adr: float, p90: float) -> Optional[Dict]:
    floor, mid, high = tiers
    if floor["share_pct"] < 45:
        return None
    attempted = min(high["avg_rate"] or p90, p90) or mid["avg_rate"]
    if attempted <= floor["avg_rate"]:
        return None
    # sweet-spot: taban ile denenen fiyat arasında, tabana yakın (%35 konum)
    sweet = round(floor["avg_rate"] + 0.35 * (attempted - floor["avg_rate"]), 0)
    # taban hacminin yarısı sweet-spot'tan erken satılırsa gelir artışı
    uplift = round(floor["share_pct"] / 100 * 0.5 * (sweet - floor["avg_rate"]) / adr * 100, 1)
    if uplift <= 0:
        return None
    msg = (f"Odaların %{floor['share_pct']}'i £{floor['avg_rate']:.0f} taban fiyattan gidiyor; "
           f"uzak tarihlerde £{attempted:.0f} denenip satılamıyor. Uzak tarihleri "
           f"£{sweet:.0f} bandından açın → tahmini +%{uplift} gelir.")
    return {"sweet_spot": sweet, "uplift_pct": uplift, "floor_rate": floor["avg_rate"],
            "high_rate": round(attempted, 0), "message": msg}


def create_rate_mix_router(db, require_roles):
    router = APIRouter(prefix="/rate-mix", tags=["rate-mix"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def get_mix(pid: str, days: int = 365,
                      _u: dict = Depends(require_roles(*ROLES))):
        days = max(30, min(days, 730))
        if pid == "all":
            props = await db.properties.find({}, {"_id": 0, "id": 1}).to_list(50)
            out = []
            for p in props:
                a = await analyze_property(db, p["id"], days)
                if a:
                    out.append(a)
            out.sort(key=lambda x: -x["tiers"][0]["share_pct"])
            return {"properties": out, "days": days}
        a = await analyze_property(db, pid, days)
        if not a:
            raise HTTPException(404, "Analiz için yeterli rezervasyon yok (min 10)")
        return {"properties": [a], "days": days}

    @router.post("/{pid}/apply")
    async def apply(pid: str, data: Dict, u: dict = Depends(require_roles(*ROLES))):
        rate = round(float(data.get("rate", 0) or 0), 2)
        if rate <= 0:
            raise HTTPException(422, "Geçerli bir fiyat gerekli")
        start = max(1, min(int(data.get("start_offset", 14) or 14), 365))
        end = max(start, min(int(data.get("end_offset", 90) or 90), 365))
        from routes.revenue_ext.write_lease import acquire_lease
        rts = await db.room_types.find(
            {"property_id": pid}, {"_id": 0, "id": 1, "base_price": 1}).to_list(50)
        if not rts:
            rts = [{"id": "", "base_price": rate}]
        min_base = min(float(r.get("base_price") or rate) or rate for r in rts) or rate
        today = ddate.today()
        written, skipped = 0, 0
        for i in range(start, end + 1):
            day = (today + timedelta(days=i)).isoformat()
            for rt in rts:
                rt_id = rt.get("id", "")
                rt_rate = round(rate * (float(rt.get("base_price") or min_base) / min_base), 0)
                ex = await db.rate_overrides.find_one(
                    {"property_id": pid, "room_type_id": rt_id, "date": day},
                    {"_id": 0, "set_by": 1})
                sb = (ex or {}).get("set_by") or ""
                # insan/etkinlik yazımları korunur; robot yazımları operatör onayıyla ezilir
                if ex and (sb in ("event-intelligence", "owner-override")
                           or "@" in sb or " " in sb):
                    skipped += 1
                    continue
                if await acquire_lease(db, pid, rt_id, day, ACTOR) is None:
                    skipped += 1
                    continue
                await db.rate_overrides.update_one(
                    {"property_id": pid, "room_type_id": rt_id, "date": day},
                    {"$set": {"custom_rate": rt_rate, "set_by": ACTOR,
                              "reason": "Rate-mix sweet-spot uygulaması",
                              "updated_at": _now().isoformat()}}, upsert=True)
                written += 1
        log = {"id": str(uuid.uuid4()), "property_id": pid, "rate": rate,
               "start_offset": start, "end_offset": end, "written": written,
               "skipped": skipped, "by": u.get("name") or u.get("email", ""),
               "created_at": _now().isoformat()}
        await db.rate_mix_applies.insert_one(dict(log))
        try:
            from routes.revenue_ext.reprice_bridge import fire_reprice
            fire_reprice(db, pid, "rate_mix_apply", log["id"])
        except Exception:
            pass
        log.pop("_id", None)
        return {"ok": True, **log}

    @router.get("/{pid}/applies")
    async def list_applies(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.rate_mix_applies.find(
            {} if pid == "all" else {"property_id": pid},
            {"_id": 0}).sort("created_at", -1).to_list(20)
        return {"applies": rows}

    return router
