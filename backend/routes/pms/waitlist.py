"""
Bekleme Listesi (Waitlist) — dolu tarihlerde misafiri listeye alır; iptal ile
müsaitlik açılınca otomatik teklif e-postası (48s geçerli deep-link) gönderir.
Collections: waitlist_entries {id, token, property_id, guest_name, email,
check_in, check_out, guests, room_type_id?, status: waiting|offered|converted|expired}
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import os
import uuid
import secrets
import logging

logger = logging.getLogger(__name__)

try:
    import resend
except Exception:
    resend = None


def _now():
    return datetime.now(timezone.utc)


def _iso():
    return _now().isoformat()


async def _send_email(to_email: str, subject: str, html: str) -> str:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend or not api_key or api_key.startswith("re_1234"):
        logger.info(f"[MOCK EMAIL] Waitlist offer to {to_email}: {subject}")
        return "mock"
    try:
        resend.api_key = api_key
        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM", "MyHotelBox <onboarding@resend.dev>"),
            "to": [to_email], "subject": subject, "html": html,
        })
        return "sent"
    except Exception as e:
        logger.warning(f"Waitlist email failed: {e}")
        return "failed"


async def _availability(db, property_id: str, check_in: str, check_out: str, room_type_id: Optional[str]) -> int:
    """Returns count of available rooms for the date range (optionally one room type)."""
    q = {"property_id": property_id}
    if room_type_id:
        q["id"] = room_type_id
    rooms = await db.room_types.find(q, {"_id": 0}).to_list(50)
    total_avail = 0
    for room in rooms:
        booked = await db.bookings.count_documents({
            "property_id": property_id,
            "room_type": room.get("name", ""),
            "status": {"$in": ["confirmed", "checked_in"]},
            "check_in": {"$lt": check_out},
            "check_out": {"$gt": check_in},
        })
        total_avail += max(int(room.get("total_rooms", 0)) - booked, 0)
    return total_avail


def _offer_html(entry: Dict, prop_name: str, link: str, expires: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;background:#fafaf9;padding:24px;border-radius:12px">
      <h2 style="color:#1c1917">🎉 Müjde {entry['guest_name']}, yeriniz açıldı!</h2>
      <p style="color:#44403c">{prop_name} için beklediğiniz
        <strong>{entry['check_in']} → {entry['check_out']}</strong> tarihlerinde artık müsaitlik var.</p>
      <p style="color:#44403c">Bu teklif bekleme listesi sıranıza özeldir ve
        <strong>{expires}</strong> tarihine kadar geçerlidir — yer yeniden dolabilir.</p>
      <p style="text-align:center;margin:28px 0">
        <a href="{link}" style="background:#059669;color:#fff;padding:14px 28px;border-radius:8px;
          text-decoration:none;font-weight:bold">Şimdi Rezervasyon Yap →</a>
      </p>
      <p style="color:#a8a29e;font-size:12px">Bu e-postayı {prop_name} bekleme listesine katıldığınız için aldınız.</p>
    </div>"""


async def run_waitlist_match_internal(db, ttl_hours: int = 48) -> Dict:
    now = _now()
    # Expire stale offers
    expired = await db.waitlist_entries.update_many(
        {"status": "offered", "offer_expires_at": {"$lt": now.isoformat()}},
        {"$set": {"status": "expired"}})
    # Drop past-date waiting entries
    await db.waitlist_entries.update_many(
        {"status": "waiting", "check_in": {"$lt": now.strftime("%Y-%m-%d")}},
        {"$set": {"status": "expired"}})

    waiting = await db.waitlist_entries.find({"status": "waiting"}, {"_id": 0}).sort("created_at", 1).to_list(300)
    offered = 0
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    for e in waiting:
        try:
            avail = await _availability(db, e["property_id"], e["check_in"], e["check_out"], e.get("room_type_id"))
        except Exception as ex:
            logger.warning("Waitlist availability check failed: %s", ex)
            continue
        if avail <= 0:
            continue
        prop = await db.properties.find_one({"id": e["property_id"]}, {"_id": 0, "name": 1}) or {}
        prop_name = prop.get("name", e["property_id"])
        expires_at = (now + timedelta(hours=ttl_hours)).isoformat()
        link = f"{base}/book/{e['property_id']}?checkin={e['check_in']}&checkout={e['check_out']}&waitlist={e['token']}"
        status = await _send_email(e["email"], f"Yeriniz açıldı — {prop_name} ({e['check_in']})",
                                   _offer_html(e, prop_name, link, expires_at[:10]))
        await db.waitlist_entries.update_one({"id": e["id"]}, {"$set": {
            "status": "offered", "offered_at": now.isoformat(),
            "offer_expires_at": expires_at, "email_status": status, "offer_link": link}})
        offered += 1
    return {"waiting_scanned": len(waiting), "offers_sent": offered, "offers_expired": expired.modified_count}


def create_waitlist_router(db, require_roles):
    router = APIRouter(prefix="/waitlist")
    router.run_match_internal = lambda ttl_hours=48: run_waitlist_match_internal(db, ttl_hours)

    # ── PUBLIC ──
    @router.post("/{property_id}/join")
    async def join(property_id: str, data: Dict):
        email = (data.get("email") or "").strip().lower()
        name = (data.get("guest_name") or "").strip()
        check_in, check_out = data.get("check_in", ""), data.get("check_out", "")
        if not email or "@" not in email or not name:
            raise HTTPException(400, "guest_name ve geçerli email gerekli")
        if not check_in or not check_out or check_in >= check_out:
            raise HTTPException(400, "Geçerli check_in/check_out gerekli")
        existing = await db.waitlist_entries.find_one({
            "property_id": property_id, "email": email, "check_in": check_in,
            "check_out": check_out, "status": {"$in": ["waiting", "offered"]}}, {"_id": 0})
        if existing:
            return {"ok": True, "already": True, "id": existing["id"]}
        doc = {
            "id": str(uuid.uuid4()), "token": secrets.token_urlsafe(12),
            "property_id": property_id, "guest_name": name, "email": email,
            "check_in": check_in, "check_out": check_out,
            "guests": int(data.get("guests", 2) or 2),
            "room_type_id": data.get("room_type_id") or None,
            "note": (data.get("note") or "")[:300],
            "status": "waiting", "created_at": _iso(),
        }
        await db.waitlist_entries.insert_one(dict(doc))
        return {"ok": True, "id": doc["id"]}

    @router.get("/offer/{token}")
    async def resolve_offer(token: str):
        e = await db.waitlist_entries.find_one({"token": token}, {"_id": 0})
        if not e:
            raise HTTPException(404, "Geçersiz bekleme listesi bağlantısı")
        return {"id": e["id"], "status": e["status"], "property_id": e["property_id"],
                "check_in": e["check_in"], "check_out": e["check_out"], "guest_name": e["guest_name"]}

    @router.post("/convert/{token}")
    async def convert(token: str, data: Optional[Dict] = None):
        e = await db.waitlist_entries.find_one({"token": token}, {"_id": 0})
        if not e:
            raise HTTPException(404, "Geçersiz token")
        if e["status"] == "converted":
            return {"ok": True, "already": True}
        await db.waitlist_entries.update_one({"id": e["id"]}, {"$set": {
            "status": "converted", "converted_at": _iso(),
            "booking_id": (data or {}).get("booking_id", "")}})
        return {"ok": True}

    # ── STAFF ──
    @router.get("/{property_id}")
    async def list_entries(property_id: str, status: Optional[str] = None,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        if status:
            q["status"] = status
        rows = await db.waitlist_entries.find(q, {"_id": 0}).sort("created_at", -1).to_list(300)
        summary = {}
        for r in rows:
            summary[r["status"]] = summary.get(r["status"], 0) + 1
        conv = summary.get("converted", 0)
        offered_total = conv + summary.get("offered", 0) + summary.get("expired", 0)
        return {"entries": rows, "summary": summary,
                "conversion_rate": round(conv / offered_total * 100, 1) if offered_total else 0}

    @router.post("/{property_id}/match-run")
    async def match_run(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return await run_waitlist_match_internal(db)

    @router.delete("/{property_id}/{entry_id}")
    async def remove(property_id: str, entry_id: str,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        r = await db.waitlist_entries.delete_one({"id": entry_id})
        if not r.deleted_count:
            raise HTTPException(404, "Kayıt bulunamadı")
        return {"ok": True}

    return router
