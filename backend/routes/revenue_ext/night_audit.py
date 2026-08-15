"""Gece Denetim Robotu — her gece gün sonu raporu (gelir, doluluk, ADR, anomaliler)."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends


def _nights(b) -> int:
    try:
        return max((datetime.strptime(b["check_out"], "%Y-%m-%d")
                    - datetime.strptime(b["check_in"], "%Y-%m-%d")).days, 1)
    except Exception:
        return 1


async def _day_metrics(db, pid: str, d: str) -> dict:
    bks = await db.bookings.find(
        {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
         "check_in": {"$lte": d}, "check_out": {"$gt": d}},
        {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1}).to_list(3000)
    occupied = len(bks)
    revenue = round(sum((b.get("total_price") or 0) / _nights(b) for b in bks), 2)
    total_rooms = await db.rooms.count_documents({"property_id": pid}) or 20
    arrivals = await db.bookings.count_documents(
        {"property_id": pid, "check_in": d, "status": {"$nin": ["cancelled", "no_show"]}})
    departures = await db.bookings.count_documents(
        {"property_id": pid, "check_out": d, "status": {"$nin": ["cancelled", "no_show"]}})
    return {"date": d, "occupied": occupied, "total_rooms": total_rooms,
            "occupancy_pct": round(occupied / total_rooms * 100, 1),
            "room_revenue": revenue,
            "adr": round(revenue / occupied, 2) if occupied else 0,
            "arrivals": arrivals, "departures": departures}


async def run_night_audit(db, pid: str, audit_date: str = "") -> dict:
    d = audit_date or (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    m = await _day_metrics(db, pid, d)
    base = datetime.strptime(d, "%Y-%m-%d").date()
    hist = [await _day_metrics(db, pid, (base - timedelta(days=i)).isoformat()) for i in range(1, 8)]
    avg_occ = sum(h["occupancy_pct"] for h in hist) / 7
    avg_rev = sum(h["room_revenue"] for h in hist) / 7
    avg_adr = sum(h["adr"] for h in hist) / max(sum(1 for h in hist if h["adr"]), 1)
    anomalies = []
    if avg_occ and m["occupancy_pct"] < avg_occ * 0.7:
        anomalies.append(f"Doluluk %{m['occupancy_pct']:g} — 7 günlük ortalamanın (%{avg_occ:.0f}) belirgin altında")
    if avg_rev and m["room_revenue"] < avg_rev * 0.8:
        anomalies.append(f"Oda geliri ₺{m['room_revenue']:g} — 7 günlük ortalamadan (₺{avg_rev:.0f}) %20+ düşük")
    if avg_adr and m["adr"] and m["adr"] < avg_adr * 0.85:
        anomalies.append(f"ADR ₺{m['adr']:g} — ortalamadan (₺{avg_adr:.0f}) %15+ düşük")
    if m["arrivals"] == 0 and avg_occ > 10:
        anomalies.append("Dün hiç giriş olmadı — kanal bağlantılarını kontrol edin")
    audit = {**m, "property_id": pid,
             "avg7_occupancy_pct": round(avg_occ, 1), "avg7_revenue": round(avg_rev, 2),
             "avg7_adr": round(avg_adr, 2), "anomalies": anomalies,
             "created_at": datetime.now(timezone.utc).isoformat()}
    await db.morning_reports.update_one({"property_id": pid, "date": d},
                                     {"$set": audit}, upsert=True)
    return audit


def create_night_audit_router(db, require_roles):
    router = APIRouter(prefix="/morning-report", tags=["morning-report"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def history(pid: str, limit: int = 7, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.morning_reports.find(
            {"property_id": pid}, {"_id": 0}).sort("date", -1).to_list(min(limit, 30))
        return {"audits": rows,
                "note": "Robot her sabah (04:00-09:00 UTC arası ilk kontrolde) önceki gecenin raporunu üretir ve anomali varsa bildirim gönderir."}

    @router.post("/{pid}/run")
    async def run_now(pid: str, data: dict = None, _u: dict = Depends(require_roles(*ROLES))):
        audit = await run_night_audit(db, pid, (data or {}).get("date", ""))
        return {"ok": True, "audit": audit}

    return router
