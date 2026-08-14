"""RGI Kanıt Paneli — pazara göre düzeltilmiş RevPAR endeksi (biz / pazar ort × 100).
Robot öncesi/sonrası karşılaştırma: ilk müşteriye satış kanıtı."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends


def create_rgi_proof_router(db, require_roles):
    router = APIRouter(prefix="/rgi-proof", tags=["rgi-proof"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def rgi(pid: str, weeks: int = 10, _u: dict = Depends(require_roles(*ROLES))):
        from routes.revenue_ext.ml_pickup import _stay_counts
        cap = await db.rooms.count_documents({"property_id": pid}) or 20
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        first_dec = await db.ai_pricing_decisions.find_one(
            {"property_id": pid}, {"_id": 0, "decided_at": 1}, sort=[("decided_at", 1)])
        robot_start = (first_dec or {}).get("decided_at", "")[:10] or None
        rows = []
        for w in range(min(weeks, 16) - 1, -1, -1):
            ws = monday - timedelta(weeks=w)
            days = [(ws + timedelta(days=i)).isoformat() for i in range(7)]
            room_nights = 0
            for ds in days:
                room_nights += (await _stay_counts(db, pid, ds))["otb"]
            occ = room_nights / (cap * 7)
            bs = await db.bookings.aggregate([
                {"$match": {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                            "check_in": {"$gte": days[0], "$lte": days[-1]}}},
                {"$group": {"_id": None, "rev": {"$sum": "$total_price"}, "n": {"$sum": 1}}}]).to_list(1)
            adr = 0.0
            if bs and bs[0]["n"]:
                adr = (bs[0]["rev"] or 0) / max(room_nights, bs[0]["n"])
            our_revpar = round(occ * (adr if adr > 0 else 0), 2)
            snaps = await db.market_supply.aggregate([
                {"$match": {"property_id": pid, "scan_type": "geo", "date": {"$in": days}}},
                {"$sort": {"scanned_at": -1}},
                {"$group": {"_id": "$date", "avg_price": {"$first": "$avg_price"},
                            "unavailable_pct": {"$first": "$unavailable_pct"}}}]).to_list(7)
            mk_revpar = None
            if snaps:
                vals = [float(s.get("avg_price") or 0) * float(s.get("unavailable_pct") or 0) / 100 for s in snaps]
                vals = [v for v in vals if v > 0]
                if vals:
                    mk_revpar = round(sum(vals) / len(vals), 2)
            rgi_v = round(our_revpar / mk_revpar * 100, 1) if (mk_revpar and our_revpar) else None
            rows.append({"week_start": days[0], "week": ws.strftime("%G-W%V"),
                         "our_revpar": our_revpar, "occ_pct": round(occ * 100, 1),
                         "market_revpar": mk_revpar, "rgi": rgi_v,
                         "phase": ("robot" if robot_start and days[0] >= robot_start else "önce")})
        before = [r["rgi"] for r in rows if r["phase"] == "önce" and r["rgi"]]
        after = [r["rgi"] for r in rows if r["phase"] == "robot" and r["rgi"]]
        avg_b = round(sum(before) / len(before), 1) if before else None
        avg_a = round(sum(after) / len(after), 1) if after else None
        if avg_b and avg_a:
            diff = round(avg_a - avg_b, 1)
            verdict = (f"Robot sonrası RGI ortalaması {avg_a} (öncesi {avg_b}, {diff:+} puan). "
                       + ("Pazardan bağımsız, robota atfedilebilir iyileşme kanıtı. ✓" if diff > 0
                          else "Fark negatif/nötr — daha fazla veri gerekli."))
        elif avg_a:
            verdict = f"Robot dönemi RGI ortalaması {avg_a} — 100 üzeri pazardan iyi performans demektir. Öncesi verisi biriktikçe kıyas netleşecek."
        else:
            verdict = "RGI hesaplamak için pazar verisi henüz yetersiz — pazar taramaları biriktikçe dolacak."
        return {"property_id": pid, "capacity": cap, "robot_start": robot_start,
                "weeks": rows, "avg_rgi_before": avg_b, "avg_rgi_after": avg_a, "verdict": verdict,
                "note": "RGI = bizim RevPAR / pazar RevPAR × 100. Pazar RevPAR'ı halka açık taramadan (ort. fiyat × doluluk vekili) türetilir. 100 üzeri = pazardan iyi."}

    return router
