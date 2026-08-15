"""Beklenen Net OTB katmanı — rezervasyon başına iptal olasılığı (p_cancel) ve net doluluk.
Grup wash'ın münferit (transient) karşılığı. Fiyat motoru net doluluğu kullanır."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

LEAD_BUCKETS = [(0, 3, "0-3"), (4, 7, "4-7"), (8, 14, "8-14"), (15, 30, "15-30"), (31, 9999, "31+")]


def _lead_bucket(days: int) -> str:
    for lo, hi, name in LEAD_BUCKETS:
        if lo <= days <= hi:
            return name
    return "31+"


def _lead_days(b: dict) -> int:
    try:
        ci = datetime.strptime(b["check_in"], "%Y-%m-%d").date()
        cr = datetime.fromisoformat(str(b.get("created_at", "")).replace("Z", "")).date()
        return max((ci - cr).days, 0)
    except Exception:
        return 15


async def get_cancel_stats(db, pid: str) -> dict:
    """Son 365 günün rezervasyonlarından lead-time kovası bazlı iptal oranları (Laplace düzeltmeli)."""
    since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    bks = await db.bookings.find(
        {"property_id": pid, "check_in": {"$gte": since}},
        {"_id": 0, "check_in": 1, "created_at": 1, "status": 1}).to_list(10000)
    total = len(bks)
    cancelled = sum(1 for b in bks if b.get("status") in ("cancelled", "no_show"))
    global_rate = (cancelled + 1) / (total + 4) if total else 0.12
    buckets = {}
    for b in bks:
        k = _lead_bucket(_lead_days(b))
        st = buckets.setdefault(k, {"n": 0, "c": 0})
        st["n"] += 1
        st["c"] += 1 if b.get("status") in ("cancelled", "no_show") else 0
    rates = {}
    for k, st in buckets.items():
        rates[k] = round((st["c"] + global_rate * 10) / (st["n"] + 10), 4)
    return {"global_rate": round(global_rate, 4), "bucket_rates": rates,
            "sample": total, "cancelled": cancelled}


def p_cancel_for(stats: dict, days_to_checkin: int) -> float:
    """Kalan lead time'a göre iptal olasılığı — check-in yaklaştıkça olasılık azalır."""
    base = stats["bucket_rates"].get(_lead_bucket(max(days_to_checkin, 0)), stats["global_rate"])
    if days_to_checkin <= 1:
        return round(base * 0.35, 4)
    if days_to_checkin <= 3:
        return round(base * 0.6, 4)
    return base


async def expected_net_for_date(db, pid: str, date: str, stats: dict, total_rooms: int) -> dict:
    """Bir tarih için brüt OTB, beklenen iptal ve net doluluk."""
    bks = await db.bookings.find(
        {"property_id": pid, "check_in": {"$lte": date}, "check_out": {"$gt": date},
         "status": {"$nin": ["cancelled", "no_show"]}},
        {"_id": 0, "check_in": 1}).to_list(3000)
    today = datetime.now(timezone.utc).date()
    exp_cancel = 0.0
    for b in bks:
        try:
            dtc = (datetime.strptime(b["check_in"], "%Y-%m-%d").date() - today).days
        except Exception:
            dtc = 15
        exp_cancel += p_cancel_for(stats, dtc)
    gross = len(bks)
    net = max(gross - exp_cancel, 0)
    return {"date": date, "gross_otb": gross, "expected_cancels": round(exp_cancel, 2),
            "net_otb": round(net, 2), "total_rooms": total_rooms,
            "gross_occupancy_pct": round(min(100, gross / total_rooms * 100), 1) if total_rooms else 0,
            "net_occupancy_pct": round(min(100, net / total_rooms * 100), 1) if total_rooms else 0}


def create_net_otb_router(db, require_roles):
    router = APIRouter(prefix="/net-otb", tags=["net-otb"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def net_otb(pid: str, days: int = 30, _u: dict = Depends(require_roles(*ROLES))):
        days = max(1, min(90, days))
        stats = await get_cancel_stats(db, pid)
        total_rooms = await db.rooms.count_documents({"property_id": pid}) or 20
        today = datetime.now(timezone.utc).date()
        rows = []
        for i in range(days):
            d = (today + timedelta(days=i)).isoformat()
            rows.append(await expected_net_for_date(db, pid, d, stats, total_rooms))
        return {"property_id": pid, "cancel_stats": stats, "rows": rows,
                "note": ("p_cancel: son 365 günün lead-time kovalı iptal oranları (Laplace düzeltmeli). "
                         "Check-in yaklaştıkça iptal olasılığı düşürülür. Fiyat motoru NET doluluğu kullanır — "
                         "brüt OTB yanıltıcıdır, beklenen iptal düşülür.")}

    return router
