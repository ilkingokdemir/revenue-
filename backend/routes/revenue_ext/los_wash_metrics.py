"""LOS Bazlı Fiyatlama + Grup Wash Projeksiyonu + Modern Metrikler (TRevPOR/RevPAG/GOPPAR)."""
import calendar
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends


def _n(b):
    try:
        return max((datetime.strptime(b["check_out"], "%Y-%m-%d")
                    - datetime.strptime(b["check_in"], "%Y-%m-%d")).days, 1)
    except Exception:
        return 1


async def compute_los_tiers(db, pid: str) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")
    bks = await db.bookings.find(
        {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
         "check_in": {"$gte": since}},
        {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1}).to_list(5000)
    buckets = {"1-2": [], "3-6": [], "7+": []}
    for b in bks:
        n = _n(b)
        k = "1-2" if n <= 2 else "3-6" if n <= 6 else "7+"
        buckets[k].append((b.get("total_price") or 0) / n)
    rows = []
    for k, v in buckets.items():
        rows.append({"bucket": k, "bookings": len(v),
                     "adr": round(sum(v) / len(v), 2) if v else 0})
    share7 = len(buckets["7+"]) / max(len(bks), 1)
    tiers = [
        {"min_nights": 3, "discount_pct": 5,
         "why": "3-6 gece talebini büyütür; temizlik/CPOR maliyeti geceye yayıldığı için net kâr korunur"},
        {"min_nights": 7, "discount_pct": 12 if share7 < 0.1 else 8,
         "why": f"7+ gece payınız %{share7*100:.0f} — {'düşük, agresif teşvik önerilir' if share7 < 0.1 else 'sağlıklı, ölçülü teşvik yeter'}"},
    ]
    return {"sample_bookings": len(bks), "buckets": rows, "suggested_tiers": tiers}


async def compute_group_wash(db, pid: str) -> dict:
    blocks = await db.group_blocks.find(
        {"property_id": pid}, {"_id": 0}).sort("from_date", -1).to_list(100)
    today = datetime.now(timezone.utc).date().isoformat()
    past = [b for b in blocks if (b.get("to_date") or "") < today]
    washes = []
    for b in past:
        alloc = sum(int(a.get("rooms") or 0) for a in (b.get("allocations") or []))
        picked = sum(int(a.get("picked_up") or 0) for a in (b.get("allocations") or []))
        if alloc > 0:
            washes.append(1 - picked / alloc)
    hist_wash = round(sum(washes) / len(washes) * 100, 1) if washes else 25.0
    out = []
    for b in blocks:
        if (b.get("to_date") or "") < today or b.get("status") in ("cancelled",):
            continue
        alloc = sum(int(a.get("rooms") or 0) for a in (b.get("allocations") or []))
        picked = sum(int(a.get("picked_up") or 0) for a in (b.get("allocations") or []))
        expected = round(alloc * (1 - hist_wash / 100), 1)
        releasable = max(round(alloc - expected - picked, 1), 0)
        out.append({"name": b.get("name"), "code": b.get("code"),
                    "from_date": b.get("from_date"), "to_date": b.get("to_date"),
                    "cutoff_date": b.get("cutoff_date"), "allocated": alloc,
                    "picked_up": picked, "expected_pickup": expected,
                    "projected_wash_pct": hist_wash, "releasable_now": releasable,
                    "advice": (f"{releasable:.0f} oda erimeye gidecek görünüyor — cutoff beklemeden transient satışa açın"
                               if releasable >= 1 else "Blok sağlıklı ilerliyor")})
    return {"historical_wash_pct": hist_wash, "measured_blocks": len(washes),
            "active_blocks": out}


def create_los_wash_metrics_router(db, require_roles):
    router = APIRouter(tags=["los-wash-metrics"])
    ROLES = ("admin", "manager")

    @router.get("/los-pricing/{pid}")
    async def los(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        data = await compute_los_tiers(db, pid)
        return {"property_id": pid, **data,
                "note": "Kademeli LOS fiyatı: min_nights ve üzeri konaklamalara otomatik % indirim. Booking widget ve kanallara fence olarak yansıtılabilir."}

    @router.post("/los-pricing/{pid}/apply")
    async def apply_los(pid: str, data: dict = None, _u: dict = Depends(require_roles(*ROLES))):
        tiers = (data or {}).get("tiers") or (await compute_los_tiers(db, pid))["suggested_tiers"]
        tiers = [{"min_nights": int(t["min_nights"]), "discount_pct": float(t["discount_pct"])} for t in tiers]
        now = datetime.now(timezone.utc).isoformat()
        await db.los_fences.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "tiers": tiers, "active": True,
                      "applied_at": now, "applied_by": _u.get("name", "")}},
            upsert=True)
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "success",
            "title": "LOS indirimleri aktif",
            "message": " · ".join(f"{t['min_nights']}+ gece → −%{t['discount_pct']:g}" for t in tiers)
                       + " — booking widget'ta otomatik uygulanacak.",
            "category": "revenue", "target_user": "", "target_role": "manager",
            "link_to": "los-wash-metrics", "priority": "normal", "read": False,
            "created_by": "LOS Motoru", "created_at": now})
        return {"ok": True, "tiers": tiers, "active": True}

    @router.get("/los-pricing/{pid}/fences")
    async def get_fences(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        f = await db.los_fences.find_one({"property_id": pid}, {"_id": 0})
        return f or {"property_id": pid, "active": False, "tiers": []}

    @router.post("/los-pricing/{pid}/deactivate")
    async def deactivate_los(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        await db.los_fences.update_one({"property_id": pid}, {"$set": {"active": False}})
        return {"ok": True, "active": False}

    @router.get("/group-wash/{pid}")
    async def wash(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        data = await compute_group_wash(db, pid)
        return {"property_id": pid, **data,
                "note": "Wash = tahsis edilen ama kullanılmayan blok oranı. Tarihsel ortalama yoksa sektör varsayılanı %25 kullanılır."}

    @router.get("/modern-metrics/{pid}")
    async def metrics(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cap = await db.rooms.count_documents({"property_id": pid}) or 20
        now = datetime.now(timezone.utc)
        m_start = now.replace(day=1).strftime("%Y-%m-%d")
        days_elapsed = now.day
        bks = await db.bookings.find(
            {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
             "check_in": {"$gte": m_start}},
            {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1, "adults": 1}).to_list(5000)
        room_rev = sum(b.get("total_price") or 0 for b in bks)
        room_nights = sum(_n(b) for b in bks)
        guests = sum(int(b.get("adults") or 1) for b in bks)
        pos = await db.pos_orders.aggregate([
            {"$match": {"property_id": pid, "created_at": {"$gte": m_start}}},
            {"$group": {"_id": None, "rev": {"$sum": "$total"}}}]).to_list(1)
        pos_rev = (pos[0]["rev"] or 0) if pos else 0
        total_rev = room_rev + pos_rev
        avail = cap * days_elapsed
        try:
            from routes.revenue_ext.profit_pricing import _get_settings as _ps
            cpor = float((await _ps(db, pid))["cpor"])
        except Exception:
            cpor = 18.0
        gop = total_rev - room_nights * cpor - total_rev * 0.22
        return {"property_id": pid, "month": now.strftime("%Y-%m"),
                "trevpor": round(total_rev / room_nights, 2) if room_nights else 0,
                "revpag": round(total_rev / guests, 2) if guests else 0,
                "goppar": round(gop / avail, 2) if avail else 0,
                "total_revenue": round(total_rev, 2), "room_revenue": round(room_rev, 2),
                "ancillary_revenue": round(pos_rev, 2), "room_nights": room_nights, "guests": guests,
                "note": "TRevPOR = toplam gelir/dolu oda-gece · RevPAG = toplam gelir/misafir · GOPPAR = brüt işletme kârı/müsait oda (CPOR + %22 sabit gider varsayımıyla)."}

    @router.get("/modern-metrics/{pid}/trend")
    async def metrics_trend(pid: str, months: int = 6, _u: dict = Depends(require_roles(*ROLES))):
        months = max(3, min(12, months))
        cap = await db.rooms.count_documents({"property_id": pid}) or 20
        try:
            from routes.revenue_ext.profit_pricing import _get_settings as _ps
            cpor = float((await _ps(db, pid))["cpor"])
        except Exception:
            cpor = 18.0
        now = datetime.now(timezone.utc)
        out = []
        for i in range(months - 1, -1, -1):
            y, m = now.year, now.month - i
            while m <= 0:
                m += 12
                y -= 1
            m_start = f"{y:04d}-{m:02d}-01"
            nm, ny = (m + 1, y) if m < 12 else (1, y + 1)
            m_end = f"{ny:04d}-{nm:02d}-01"
            bks = await db.bookings.find(
                {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                 "check_in": {"$gte": m_start, "$lt": m_end}},
                {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1, "adults": 1}).to_list(5000)
            rev = sum(b.get("total_price") or 0 for b in bks)
            rn = sum(_n(b) for b in bks)
            guests = sum(int(b.get("adults") or 1) for b in bks)
            dim = calendar.monthrange(y, m)[1]
            gop = rev - rn * cpor - rev * 0.22
            out.append({"month": f"{y:04d}-{m:02d}",
                        "trevpor": round(rev / rn, 2) if rn else 0,
                        "revpag": round(rev / guests, 2) if guests else 0,
                        "goppar": round(gop / (cap * dim), 2)})
        vals_t = [r["trevpor"] for r in out if r["trevpor"]]
        vals_g = [r["goppar"] for r in out if r["goppar"]]
        tgt = await db.metric_targets.find_one({"property_id": pid}, {"_id": 0}) or {}
        target_trevpor = float(tgt.get("target_trevpor") or (round(sum(vals_t) / len(vals_t) * 1.1, 2) if vals_t else 0))
        target_goppar = float(tgt.get("target_goppar") or (round(sum(vals_g) / len(vals_g) * 1.1, 2) if vals_g else 0))
        return {"property_id": pid, "months": out,
                "target_trevpor": target_trevpor, "target_goppar": target_goppar,
                "note": "Hedefler ayarlanmadıysa son dönem ortalamasının %110'u hedef alınır."}

    return router
