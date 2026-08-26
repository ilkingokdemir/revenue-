"""
No-Show Riski Tahmini — yarınki girişler risk faktörleriyle puanlanır,
yüksek riskliler önceden işaretlenir ve günlük bildirim gönderilir.
Faktörler: iletişim eksikliği, ödeme durumu, OTA kanalı, 1 gece, misafirin
geçmiş no-show'u, çok eski rezervasyon. Collection: yok (canlı hesap) + notifications.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

OTA_CHANNELS = {"booking", "booking.com", "expedia", "airbnb", "ota", "agoda"}


def _now():
    return datetime.now(timezone.utc)


async def score_arrivals(db, pid: str, day: str) -> List[Dict]:
    arrivals = await db.bookings.find(
        {"property_id": pid, "check_in": day,
         "status": {"$nin": ["cancelled", "no_show", "checked_in"]}},
        {"_id": 0}).to_list(200)
    out = []
    for b in arrivals:
        score, reasons = 0, []
        if not (b.get("guest_email") or "").strip():
            score += 15
            reasons.append("E-posta yok")
        if not (b.get("guest_phone") or "").strip():
            score += 15
            reasons.append("Telefon yok")
        if (b.get("payment_status") or "pending") in ("pending", "unpaid", ""):
            score += 25
            reasons.append("Ödeme alınmamış")
        if (b.get("channel") or "").lower() in OTA_CHANNELS:
            score += 10
            reasons.append("OTA kanalı")
        if int(b.get("nights", 1) or 1) <= 1:
            score += 10
            reasons.append("Tek gece")
        # misafirin geçmiş no-show'u
        guest_q = []
        if (b.get("guest_email") or "").strip():
            guest_q.append({"guest_email": b["guest_email"]})
        if (b.get("guest_name") or "").strip():
            guest_q.append({"guest_name": b["guest_name"]})
        if guest_q:
            past_ns = await db.bookings.count_documents(
                {"property_id": pid, "status": "no_show", "$or": guest_q,
                 "id": {"$ne": b.get("id")}})
            if past_ns > 0:
                score += 30
                reasons.append(f"Geçmişte {past_ns} no-show")
        try:
            created = datetime.fromisoformat(b.get("created_at", "").replace("Z", "+00:00"))
            if (_now() - created).days > 30:
                score += 5
                reasons.append("30+ gün önce rezerve")
        except Exception:
            pass
        level = "high" if score >= 50 else ("medium" if score >= 30 else "low")
        out.append({"booking_id": b.get("id"), "booking_ref": b.get("booking_ref"),
                    "guest_name": b.get("guest_name"), "room_type": b.get("room_type"),
                    "channel": b.get("channel", "direct"), "nights": b.get("nights", 1),
                    "total_price": b.get("total_price", 0),
                    "payment_status": b.get("payment_status", "pending"),
                    "score": min(score, 100), "level": level, "reasons": reasons,
                    "suggestion": ("Bugün telefonla teyit alın + ön provizyon isteyin" if level == "high"
                                   else "Teyit SMS/e-postası gönderin" if level == "medium"
                                   else "İzleme yeterli")})
    out.sort(key=lambda x: -x["score"])
    return out


async def noshow_risk_loop(db, interval_seconds: int = 3600):
    await asyncio.sleep(330)
    while True:
        try:
            now = _now()
            if 14 <= now.hour <= 18:  # öğleden sonra tek sefer bildirim penceresi
                tomorrow = (now.date() + timedelta(days=1)).isoformat()
                for pid in await db.properties.distinct("id"):
                    already = await db.notifications.find_one(
                        {"property_id": pid, "category": "noshow_risk",
                         "meta_date": tomorrow})
                    if already:
                        continue
                    risks = await score_arrivals(db, pid, tomorrow)
                    high = [r for r in risks if r["level"] == "high"]
                    if not high:
                        continue
                    names = ", ".join(r["guest_name"] or r["booking_ref"] for r in high[:3])
                    await db.notifications.insert_one({
                        "id": str(uuid.uuid4()), "property_id": pid, "category": "noshow_risk",
                        "meta_date": tomorrow, "priority": "high",
                        "target_user": "", "target_role": "manager",
                        "title": f"⚠️ Yarın {len(high)} yüksek no-show riski",
                        "message": f"{names}… — bugün teyit araması + ön provizyon önerilir. Detay: No-Show Riski paneli.",
                        "read": False, "created_at": now.isoformat()})
        except Exception as ex:
            logger.warning("No-show risk loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_noshow_risk_router(db, require_roles):
    router = APIRouter(prefix="/noshow-risk", tags=["noshow-risk"])
    ROLES = ("admin", "manager", "receptionist")

    @router.get("/{pid}")
    async def risks(pid: str, day: str = "", _u: dict = Depends(require_roles(*ROLES))):
        target = day or (_now().date() + timedelta(days=1)).isoformat()
        items = await score_arrivals(db, pid, target)
        return {"date": target, "items": items,
                "summary": {"total": len(items),
                            "high": sum(1 for i in items if i["level"] == "high"),
                            "medium": sum(1 for i in items if i["level"] == "medium")}}

    return router
