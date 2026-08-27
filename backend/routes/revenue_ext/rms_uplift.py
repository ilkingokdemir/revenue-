"""RMS Etki Ölçer — robot öncesi baz senaryoya göre aylık RevPAR uplift kanıtı (RoomPriceGenie paritesi)."""
import calendar
from datetime import datetime, timezone
from fastapi import APIRouter, Depends

ROBOT_ACTORS = ("market-robot", "auto-scanner", "ai-dynamic-pricing", "autopilot",
                "lastday-ladder", "ramp-ladder", "rate-mix", "base-curve", "ai-v2")


def create_rms_uplift_router(db, require_roles):
    router = APIRouter(prefix="/rms-uplift", tags=["rms-uplift"])
    ROLES = ("admin", "manager")

    async def _robot_start(pid: str):
        d = await db.ai_pricing_decisions.find_one(
            {"property_id": pid, "decided_at": {"$exists": True}},
            {"_id": 0, "decided_at": 1}, sort=[("decided_at", 1)])
        if d and d.get("decided_at"):
            return d["decided_at"][:10]
        ov = await db.rate_overrides.find_one(
            {"property_id": pid, "set_by": {"$in": list(ROBOT_ACTORS)},
             "updated_at": {"$exists": True}},
            {"_id": 0, "updated_at": 1}, sort=[("updated_at", 1)])
        return (ov or {}).get("updated_at", "")[:10] or None

    async def _capacity(pid: str) -> int:
        total = 0
        for rt in await db.room_types.find({"property_id": pid},
                                           {"_id": 0, "total_rooms": 1}).to_list(100):
            total += int(rt.get("total_rooms", 0))
        return total or await db.rooms.count_documents({"property_id": pid}) or 20

    @router.get("/{pid}")
    async def uplift(pid: str, months: int = 12, _u: dict = Depends(require_roles(*ROLES))):
        return await compute_uplift(db, pid, months)

    return router


async def compute_uplift(db, pid: str, months: int = 12):
        async def _robot_start2(p):
            d = await db.ai_pricing_decisions.find_one(
                {"property_id": p, "decided_at": {"$exists": True}},
                {"_id": 0, "decided_at": 1}, sort=[("decided_at", 1)])
            if d and d.get("decided_at"):
                return d["decided_at"][:10]
            ov = await db.rate_overrides.find_one(
                {"property_id": p, "set_by": {"$in": list(ROBOT_ACTORS)},
                 "updated_at": {"$exists": True}},
                {"_id": 0, "updated_at": 1}, sort=[("updated_at", 1)])
            return (ov or {}).get("updated_at", "")[:10] or None

        months = max(4, min(months, 24))
        total = 0
        for rt in await db.room_types.find({"property_id": pid},
                                           {"_id": 0, "total_rooms": 1}).to_list(100):
            total += int(rt.get("total_rooms", 0))
        cap = total or await db.rooms.count_documents({"property_id": pid}) or 20
        robot_start = await _robot_start2(pid)
        now = datetime.now(timezone.utc)
        rows = []
        for i in range(months - 1, -1, -1):
            y, m = now.year, now.month - i
            while m <= 0:
                m += 12
                y -= 1
            m0 = f"{y:04d}-{m:02d}-01"
            dim = calendar.monthrange(y, m)[1]
            nm, ny = (m + 1, y) if m < 12 else (1, y + 1)
            m1 = f"{ny:04d}-{nm:02d}-01"
            agg = await db.bookings.aggregate([
                {"$match": {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                            "check_in": {"$gte": m0, "$lt": m1}}},
                {"$group": {"_id": None, "rev": {"$sum": "$total_price"},
                            "rn": {"$sum": {"$multiply": [
                                {"$ifNull": ["$nights", 1]},
                                {"$ifNull": ["$rooms", 1]}]}}}}]).to_list(1)
            rev = float((agg[0]["rev"] or 0) if agg else 0)
            rn = int((agg[0]["rn"] or 0) if agg else 0)
            avail = cap * dim
            rows.append({"month": f"{y:04d}-{m:02d}", "revenue": round(rev, 0),
                         "room_nights": rn, "occ_pct": min(round(rn / avail * 100, 1), 100.0),
                         "adr": round(rev / rn, 0) if rn else 0,
                         "revpar": round(rev / avail, 2), "days": dim,
                         "phase": ("robot" if robot_start and f"{y:04d}-{m:02d}" >= robot_start[:7]
                                   else "baz")})
        base_rows = [r for r in rows if r["phase"] == "baz" and r["revpar"] > 0]
        if not base_rows:
            k = max(2, len(rows) // 4)
            base_rows = [r for r in rows[:k] if r["revpar"] > 0]
            for r in rows[:k]:
                r["phase"] = "baz*"
        baseline = round(sum(r["revpar"] for r in base_rows) / len(base_rows), 2) if base_rows else 0
        total_uplift, robot_months = 0.0, 0
        for r in rows:
            if r["phase"].startswith("baz") or not baseline:
                r["uplift_gbp"] = None
                continue
            r["uplift_gbp"] = round((r["revpar"] - baseline) * cap * r["days"], 0)
            total_uplift += r["uplift_gbp"]
            robot_months += 1
        pct = round((sum(r["revpar"] for r in rows if r["phase"] == "robot")
                     / max(robot_months, 1) / baseline - 1) * 100, 1) if baseline and robot_months else None
        if pct is not None and robot_months:
            verdict = (f"RMS motoru {robot_months} ayda baz RevPAR £{baseline}'a göre "
                       f"{'%+.1f' % pct}% etki yarattı — tahmini {'+' if total_uplift >= 0 else ''}£{total_uplift:,.0f} ek gelir."
                       + (" ✓ Motor kendini fazlasıyla amorti ediyor." if total_uplift > 0
                          else " Daha fazla veri gerekli."))
        else:
            verdict = "Uplift hesabı için baz dönem verisi yetersiz — rezervasyon geçmişi biriktikçe netleşecek."
        return {"property_id": pid, "capacity": cap, "robot_start": robot_start,
                "baseline_revpar": baseline, "months": rows,
                "total_uplift_gbp": round(total_uplift, 0), "uplift_pct": pct,
                "robot_months": robot_months, "verdict": verdict,
                "note": "Uplift = (aylık RevPAR − baz RevPAR) × oda × gün. Baz = robot öncesi ayların ortalaması (yoksa serinin ilk çeyreği, 'baz*' olarak işaretlenir)."}
