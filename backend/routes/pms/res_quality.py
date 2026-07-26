"""
Rezervasyon Kalite Kontrolü (RobosizeME "Reservation Quality Check" paritesi) —
yaklaşan varışları hatalara karşı tarar; misafir gelmeden düzeltme şansı verir.
Kontroller: eksik e-posta/telefon, oda atanmamış, sıfır/eksik fiyat, tarih hatası,
aynı misafir çift rezervasyon. Autofix: guest_profiles'tan iletişim backfill.
Motor: res_quality (JOB_REGISTRY).
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import uuid
import logging

logger = logging.getLogger(__name__)

SEVERITY = {"missing_email": "high", "missing_phone": "medium", "no_room": "medium",
            "zero_rate": "high", "bad_dates": "high", "duplicate": "high"}
LABELS_TR = {
    "missing_email": "E-posta eksik", "missing_phone": "Telefon eksik",
    "no_room": "Oda atanmamış (varışa <48s)", "zero_rate": "Fiyat 0 / eksik",
    "bad_dates": "Tarih hatası", "duplicate": "Olası çift rezervasyon",
}


async def scan_internal(db, property_id: str = "", days: int = 14) -> Dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    horizon = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")
    pq = {} if not property_id or property_id == "all" else {"property_id": property_id}
    bookings = await db.bookings.find({
        **pq, "check_in": {"$gte": today, "$lte": horizon},
        "status": {"$in": ["confirmed", "pending", "pending_payment"]},
    }, {"_id": 0, "id": 1, "property_id": 1, "guest_name": 1, "guest_email": 1,
        "guest_phone": 1, "room_number": 1, "room_type": 1, "check_in": 1,
        "check_out": 1, "total_price": 1, "booking_ref": 1}).to_list(2000)

    soon = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
    seen = {}
    issues: List[Dict] = []
    for b in bookings:
        probs = []
        if not (b.get("guest_email") or "").strip():
            probs.append("missing_email")
        if not (b.get("guest_phone") or "").strip():
            probs.append("missing_phone")
        if not b.get("room_number") and (b.get("check_in") or "") <= soon:
            probs.append("no_room")
        if float(b.get("total_price") or 0) <= 0:
            probs.append("zero_rate")
        if b.get("check_out") and b.get("check_in") and b["check_out"] <= b["check_in"]:
            probs.append("bad_dates")
        dkey = ((b.get("guest_email") or b.get("guest_name") or "").lower().strip(),
                b.get("check_in"), b.get("property_id"))
        if dkey[0]:
            if dkey in seen:
                probs.append("duplicate")
            seen[dkey] = b["id"]
        if probs:
            issues.append({
                "booking_id": b["id"], "booking_ref": b.get("booking_ref", ""),
                "guest_name": b.get("guest_name", ""), "property_id": b.get("property_id", ""),
                "check_in": b.get("check_in", ""), "room": b.get("room_number") or "—",
                "problems": [{"code": p, "label": LABELS_TR[p], "severity": SEVERITY[p]} for p in probs],
            })
    by_code = {}
    for i in issues:
        for p in i["problems"]:
            by_code[p["code"]] = by_code.get(p["code"], 0) + 1
    return {"scanned": len(bookings), "days": days,
            "clean": len(bookings) - len(issues), "with_issues": len(issues),
            "quality_score": round((len(bookings) - len(issues)) / len(bookings) * 100, 1) if bookings else 100,
            "by_code": [{"code": c, "label": LABELS_TR[c], "count": n, "severity": SEVERITY[c]}
                        for c, n in sorted(by_code.items(), key=lambda x: -x[1])],
            "issues": issues[:100]}


async def autofix_internal(db, property_id: str = "") -> Dict:
    """Contact backfill: eksik email/telefonu guest_profiles'tan doldur."""
    scan = await scan_internal(db, property_id)
    fixed_email, fixed_phone = 0, 0
    for i in scan["issues"]:
        codes = {p["code"] for p in i["problems"]}
        if not ({"missing_email", "missing_phone"} & codes):
            continue
        bk = await db.bookings.find_one({"id": i["booking_id"]}, {"_id": 0, "guest_name": 1, "guest_email": 1, "guest_phone": 1})
        if not bk:
            continue
        prof = None
        if bk.get("guest_email"):
            prof = await db.guest_profiles.find_one({"email": bk["guest_email"].lower()}, {"_id": 0, "email": 1, "phone": 1})
        if not prof and bk.get("guest_name"):
            prof = await db.guest_profiles.find_one(
                {"name": {"$regex": f"^{bk['guest_name'].strip()}$", "$options": "i"}},
                {"_id": 0, "email": 1, "phone": 1})
        if not prof:
            continue
        upd = {}
        if "missing_email" in codes and prof.get("email"):
            upd["guest_email"] = prof["email"]
            fixed_email += 1
        if "missing_phone" in codes and prof.get("phone"):
            upd["guest_phone"] = prof["phone"]
            fixed_phone += 1
        if upd:
            upd["quality_fixed_at"] = datetime.now(timezone.utc).isoformat()
            await db.bookings.update_one({"id": i["booking_id"]}, {"$set": upd})
    result = {"fixed_email": fixed_email, "fixed_phone": fixed_phone,
              "scanned_issues": scan["with_issues"]}
    await db.res_quality_log.insert_one({"id": str(uuid.uuid4()), **result,
                                         "property_id": property_id or "all",
                                         "created_at": datetime.now(timezone.utc).isoformat()})
    return result


def create_res_quality_router(db, require_roles):
    router = APIRouter(prefix="/res-quality")
    router.run_autofix_internal = lambda pid="": autofix_internal(db, pid)

    @router.get("/{property_id}")
    async def scan(property_id: str, days: int = 14,
                   current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return await scan_internal(db, property_id, min(max(days, 1), 60))

    @router.post("/{property_id}/autofix")
    async def autofix(property_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        return await autofix_internal(db, property_id)

    return router
