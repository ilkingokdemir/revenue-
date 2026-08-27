"""Kâr Benchmark — oteller arası GOPPAR ligi (HotStats tarzı kârlılık kıyası)."""
import calendar
from datetime import datetime, timezone
from fastapi import APIRouter, Depends

ACTIVE = {"$nin": ["cancelled", "no_show", "pending", "pending_payment"]}


def create_profit_benchmark_router(db, require_roles):
    router = APIRouter(prefix="/profit-benchmark", tags=["profit-benchmark"])
    ROLES = ("admin", "manager")

    @router.get("")
    async def league(months: int = 3, _u: dict = Depends(require_roles(*ROLES))):
        months = max(1, min(months, 12))
        now = datetime.now(timezone.utc)
        # pencere: son N tam ay + içinde bulunulan ay
        y, m = now.year, now.month - (months - 1)
        while m <= 0:
            m += 12
            y -= 1
        start = f"{y:04d}-{m:02d}-01"
        end = now.date().isoformat()
        window_days = (now.date() - datetime.strptime(start, "%Y-%m-%d").date()).days or 1
        rows = []
        for p in await db.properties.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(50):
            pid = p["id"]
            cap = 0
            for rt in await db.room_types.find({"property_id": pid},
                                               {"_id": 0, "total_rooms": 1}).to_list(100):
                cap += int(rt.get("total_rooms", 0))
            cap = cap or await db.rooms.count_documents({"property_id": pid}) or 0
            if not cap:
                continue
            agg = await db.bookings.aggregate([
                {"$match": {"property_id": pid, "status": ACTIVE,
                            "check_in": {"$gte": start, "$lte": end}}},
                {"$group": {"_id": None, "rev": {"$sum": "$total_price"},
                            "rn": {"$sum": {"$multiply": [
                                {"$ifNull": ["$nights", 1]},
                                {"$ifNull": ["$rooms", 1]}]}}}}]).to_list(1)
            rev = float((agg[0]["rev"] or 0) if agg else 0)
            rn = int((agg[0]["rn"] or 0) if agg else 0)
            pos = await db.pos_orders.aggregate([
                {"$match": {"property_id": pid, "created_at": {"$gte": start}}},
                {"$group": {"_id": None, "rev": {"$sum": "$total"}}}]).to_list(1)
            anc = float((pos[0]["rev"] or 0) if pos else 0)
            total_rev = rev + anc
            try:
                from routes.revenue_ext.profit_pricing import _get_settings as _ps
                cpor = float((await _ps(db, pid))["cpor"])
            except Exception:
                cpor = 18.0
            gop = total_rev - rn * cpor - total_rev * 0.22
            avail = cap * window_days
            rows.append({"property_id": pid, "name": p.get("name", pid), "rooms": cap,
                         "occ_pct": min(round(rn / avail * 100, 1), 100.0),
                         "adr": round(rev / rn, 0) if rn else 0,
                         "revpar": round(rev / avail, 2),
                         "trevpar": round(total_rev / avail, 2),
                         "goppar": round(gop / avail, 2),
                         "gop": round(gop, 0), "cpor": cpor,
                         "ancillary": round(anc, 0)})
        rows = [r for r in rows if r["revpar"] > 0 or r["goppar"] != 0]
        rows.sort(key=lambda x: -x["goppar"])
        port_goppar = round(sum(r["goppar"] for r in rows) / len(rows), 2) if rows else 0
        for i, r in enumerate(rows):
            r["rank"] = i + 1
            r["vs_portfolio_pct"] = round((r["goppar"] / port_goppar - 1) * 100, 1) if port_goppar else None
            r["badge"] = ("lider" if i == 0 else
                          "ortalama üstü" if port_goppar and r["goppar"] >= port_goppar else
                          "ortalama altı")
            if r["badge"] == "ortalama altı" and rows[0]["goppar"] > 0:
                gap = round((rows[0]["goppar"] - r["goppar"]) * r["rooms"] * window_days, 0)
                r["insight"] = f"Lider GOPPAR'ı yakalasa {window_days} günde +£{gap:,.0f} brüt kâr eklerdi"
            else:
                r["insight"] = "Portföy ortalamasının üzerinde kârlılık"
        return {"window_start": start, "window_days": window_days,
                "portfolio_goppar": port_goppar, "properties": rows,
                "note": "GOPPAR = (toplam gelir − oda-gece×CPOR − %22 sabit gider) / müsait oda-gece. TRevPAR yan gelirleri (POS) içerir. Kaynak: HotStats metodolojisi."}

    return router
