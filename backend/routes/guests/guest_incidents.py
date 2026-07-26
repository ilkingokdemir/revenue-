"""
Misafir Olay Kayıtları & Dönen Misafir Takibi (Mews Guest Notes paritesi)
- guest_incidents: misafire bağlı sorun/olay notları; handover=true ise vardiya
  devir defterine (shift_handover) otomatik düşer.
- Dönen misafir takibi: önümüzdeki 48 saatteki varışlarda kayıtlı tercihi
  (guest_prefs / profil) veya geçmiş olayı olan misafirler resepsiyona
  bildirilir + Arrivals Cockpit şeridinde gösterilir.
Motor: returning_guest_watch (06:30).
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

SEVERITIES = ("low", "medium", "high")


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _guest_context(db, email: str) -> Dict:
    """Tercih + olay özeti (dönen misafir kartı için)."""
    email = (email or "").lower().strip()
    if not email:
        return {"prefs": [], "incidents": [], "pref_count": 0, "incident_count": 0}
    profile = await db.guest_profiles.find_one({"email": email}, {"_id": 0, "id": 1, "preferences": 1, "vip": 1, "notes": 1}) or {}
    prefs_doc = await db.guest_preferences.find_one(
        {"guest_id": {"$in": [v for v in (profile.get("id"), email) if v]}}, {"_id": 0}) or {}
    pref_items = [f"{k}: {v}" for k, v in prefs_doc.items()
                  if k not in ("guest_id", "guest_email", "id", "updated_at", "created_at") and v]
    for p in (profile.get("preferences") or []):
        pref_items.append(str(p))
    incidents = await db.guest_incidents.find({"guest_email": email}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"prefs": pref_items[:10], "incidents": incidents,
            "pref_count": len(pref_items),
            "incident_count": len(incidents),
            "open_incidents": sum(1 for i in incidents if i.get("status") == "open"),
            "vip": bool(profile.get("vip"))}


async def returning_watch_internal(db, property_id: str = "all") -> Dict:
    today = date.today().isoformat()
    horizon = (date.today() + timedelta(days=2)).isoformat()
    pq: Dict = {} if property_id == "all" else {"property_id": property_id}
    arrivals = await db.bookings.find({
        **pq, "check_in": {"$gte": today, "$lte": horizon},
        "status": {"$in": ["confirmed", "pending", "pending_payment"]},
    }, {"_id": 0, "id": 1, "guest_email": 1, "guest_name": 1, "property_id": 1,
        "check_in": 1, "room_number": 1, "guest_watch_flagged": 1}).to_list(500)

    flagged, results = 0, []
    for b in arrivals:
        email = (b.get("guest_email") or "").lower().strip()
        if not email:
            continue
        ctx = await _guest_context(db, email)
        if ctx["pref_count"] == 0 and ctx["incident_count"] == 0:
            continue
        results.append({**b, **ctx})
        if b.get("guest_watch_flagged"):
            continue
        parts = []
        if ctx["pref_count"]:
            parts.append(f"{ctx['pref_count']} kayıtlı tercih")
        if ctx["incident_count"]:
            parts.append(f"{ctx['incident_count']} geçmiş olay" + (f" ({ctx['open_incidents']} açık)" if ctx["open_incidents"] else ""))
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "property_id": b.get("property_id", ""),
            "category": "returning_guest", "priority": "high" if ctx["open_incidents"] else "normal",
            "target_user": "", "target_role": "receptionist",
            "title": f"🔁 Dönen misafir: {b.get('guest_name', email)}",
            "message": f"{b.get('check_in')} varışı — {', '.join(parts)}. Profili kontrol edin.",
            "read": False, "created_at": _now()})
        await db.bookings.update_one({"id": b["id"]}, {"$set": {"guest_watch_flagged": True}})
        flagged += 1
    return {"arrivals_scanned": len(arrivals), "returning_with_context": len(results),
            "newly_flagged": flagged}


def create_guest_incidents_router(db, require_roles):
    router = APIRouter(prefix="/guest-incidents")
    router.run_watch_internal = lambda pid="all": returning_watch_internal(db, pid)

    STAFF = require_roles("admin", "manager", "receptionist", "housekeeper")

    @router.post("")
    async def create_incident(data: Dict, current_user: dict = Depends(STAFF)):
        email = (data.get("guest_email") or "").lower().strip()
        text = (data.get("text") or "").strip()
        if not email or "@" not in email or len(text) < 3:
            raise HTTPException(400, "guest_email ve text gerekli")
        severity = data.get("severity", "medium")
        if severity not in SEVERITIES:
            severity = "medium"
        doc = {
            "id": str(uuid.uuid4()), "guest_email": email,
            "guest_name": (data.get("guest_name") or "").strip(),
            "booking_id": data.get("booking_id", ""),
            "property_id": data.get("property_id", ""),
            "severity": severity, "text": text[:600],
            "handover": bool(data.get("handover")),
            "status": "open", "created_by": current_user.get("email", ""),
            "created_at": _now(),
        }
        await db.guest_incidents.insert_one(dict(doc))
        doc.pop("_id", None)
        if doc["handover"]:
            await db.shift_handover.insert_one({
                "id": str(uuid.uuid4()), "property_id": doc["property_id"] or "all",
                "note_type": "guest", "priority": severity, "status": "pending",
                "content": f"👤 Misafir olayı — {doc['guest_name'] or email}: {text[:400]}",
                "owner": "", "role_target": "receptionist",
                "due_date": date.today().isoformat(),
                "author": current_user.get("email", ""),
                "resolved_by": "", "resolved_at": "", "created_at": _now()})
        return doc

    @router.get("/by-guest/{email}")
    async def by_guest(email: str, current_user: dict = Depends(STAFF)):
        return await _guest_context(db, email)

    @router.put("/{incident_id}/resolve")
    async def resolve(incident_id: str, current_user: dict = Depends(STAFF)):
        r = await db.guest_incidents.update_one(
            {"id": incident_id, "status": "open"},
            {"$set": {"status": "resolved", "resolved_at": _now(),
                      "resolved_by": current_user.get("email", "")}})
        if not r.modified_count:
            raise HTTPException(404, "Açık olay bulunamadı")
        return {"ok": True}

    @router.delete("/{incident_id}")
    async def remove(incident_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.guest_incidents.delete_one({"id": incident_id})
        if not r.deleted_count:
            raise HTTPException(404, "Kayıt bulunamadı")
        return {"ok": True}

    @router.get("/returning/{property_id}")
    async def returning(property_id: str, current_user: dict = Depends(STAFF)):
        today = date.today().isoformat()
        horizon = (date.today() + timedelta(days=2)).isoformat()
        pq: Dict = {} if property_id == "all" else {"property_id": property_id}
        arrivals = await db.bookings.find({
            **pq, "check_in": {"$gte": today, "$lte": horizon},
            "status": {"$in": ["confirmed", "pending", "pending_payment", "checked_in"]},
        }, {"_id": 0, "id": 1, "guest_email": 1, "guest_name": 1,
            "check_in": 1, "room_number": 1, "property_id": 1}).to_list(300)
        out = []
        for b in arrivals:
            ctx = await _guest_context(db, b.get("guest_email", ""))
            if ctx["pref_count"] or ctx["incident_count"]:
                out.append({**b, "prefs": ctx["prefs"], "vip": ctx["vip"],
                            "incident_count": ctx["incident_count"],
                            "open_incidents": ctx["open_incidents"],
                            "incidents": [i for i in ctx["incidents"] if i.get("status") == "open"][:3]})
        return {"count": len(out), "guests": out}

    @router.post("/watch-run/{property_id}")
    async def watch_run(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        return await returning_watch_internal(db, property_id)

    return router
