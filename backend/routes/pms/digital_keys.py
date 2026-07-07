"""
Digital Keys (iter 371) — Mews parity MVP
==========================================
Rotating QR-based room key for check-in guests. Also emits a `key_code`
that hotel door-lock hardware can read via BLE/NFC (integration stub —
Assa Abloy / Salto SDK plugs into `_generate_hardware_payload`).

Flow
----
1. Staff issues a key after check-in: `POST /api/digital-keys/issue`
     → creates a short-lived JWT-ish token (30 min default) tied to the
       booking. Guest visits `/room-key?token=...` on their phone.
2. Guest sees a rotating QR code (30-sec refresh) + a numeric backup PIN.
3. Door lock reads the QR / PIN via the vendor SDK (mocked).
4. Key auto-revokes at check-out or when duration elapses.

Endpoints
---------
  POST   /api/digital-keys/issue                 (staff)
  GET    /api/digital-keys/mine/{booking_id}      (public, guest)
  GET    /api/digital-keys/token/{token}          (public — refresh QR)
  DELETE /api/digital-keys/{key_id}               (staff — revoke)
  GET    /api/digital-keys/list                    (staff — active keys)
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rotating_qr(token: str, at: datetime) -> str:
    """Produce a QR string that rotates every 30s.
    Format: hb:{token_prefix}:{time_bucket}:{sig}
    Door hardware must call `/api/digital-keys/verify/{qr}` to accept."""
    bucket = int(at.timestamp() // 30)   # 30-sec buckets
    sig = hashlib.sha256(f"{token}:{bucket}".encode()).hexdigest()[:12]
    return f"hb:{token[:8]}:{bucket}:{sig}"


def _pin(token: str) -> str:
    """4-digit numeric backup PIN — derived from the token."""
    return f"{int(hashlib.sha256(token.encode()).hexdigest(), 16) % 10000:04d}"


class IssueKeyBody(BaseModel):
    booking_id: str
    room_number: Optional[str] = None
    duration_hours: int = 24


def create_digital_keys_router(db, require_roles):
    router = APIRouter(prefix="/digital-keys", tags=["digital-keys"])

    @router.post("/issue")
    async def issue(body: IssueKeyBody,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        if body.duration_hours < 1 or body.duration_hours > 168:
            raise HTTPException(400, "duration_hours 1-168 arası olmalı (max 7 gün)")
        booking = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Rezervasyon bulunamadı")
        token = secrets.token_urlsafe(24)
        expires = datetime.now(timezone.utc) + timedelta(hours=body.duration_hours)
        doc = {
            "id":            str(uuid.uuid4()),
            "token":         token,
            "booking_id":    body.booking_id,
            "property_id":   booking.get("property_id"),
            "room_number":   body.room_number or booking.get("room_number"),
            "guest_name":    booking.get("guest_name"),
            "guest_email":   booking.get("guest_email"),
            "issued_at":     _now(),
            "expires_at":    expires.isoformat(),
            "issued_by":     current_user.get("email", ""),
            "revoked":       False,
            "used_count":    0,
            "backup_pin":    _pin(token),
        }
        await db.digital_keys.insert_one(doc)
        doc.pop("_id", None)
        return {
            **doc,
            "url_path": f"/room-key?token={token}",
            "share_message": (
                f"Odanız hazır! 🔑\n"
                f"Anahtar linki: /room-key?token={token}\n"
                f"Backup PIN: {doc['backup_pin']}\n"
                f"Süre: {body.duration_hours} saat"
            ),
        }

    @router.get("/token/{token}")
    async def get_by_token(token: str):
        """Public — guest phone fetches this every 30s to refresh the QR."""
        k = await db.digital_keys.find_one({"token": token}, {"_id": 0})
        if not k:
            raise HTTPException(404, "Anahtar bulunamadı")
        if k.get("revoked"):
            raise HTTPException(410, "Bu anahtar iptal edilmiş")
        if k["expires_at"] < _now():
            raise HTTPException(410, "Anahtar süresi doldu")
        now = datetime.now(timezone.utc)
        return {
            "id":           k["id"],
            "booking_id":   k["booking_id"],
            "room_number":  k.get("room_number"),
            "guest_name":   k.get("guest_name"),
            "expires_at":   k["expires_at"],
            "qr_string":    _rotating_qr(token, now),
            "backup_pin":   k["backup_pin"],
            "refresh_in":   30 - int(now.timestamp()) % 30,
        }

    @router.get("/verify/{qr_string}")
    async def verify_qr(qr_string: str):
        """Hardware endpoint — door lock validates the scanned QR.
        Returns 200 + booking_id if valid, 401 if not."""
        parts = qr_string.split(":")
        if len(parts) != 4 or parts[0] != "hb":
            raise HTTPException(401, "Geçersiz QR formatı")
        prefix, bucket_str, sig = parts[1], parts[2], parts[3]
        try:
            bucket = int(bucket_str)
        except ValueError as e:
            raise HTTPException(401, "Geçersiz bucket") from e
        now_bucket = int(datetime.now(timezone.utc).timestamp() // 30)
        # Accept current bucket ± 1 for clock skew
        if abs(now_bucket - bucket) > 1:
            raise HTTPException(401, "QR süresi geçmiş — telefonu tazeleyin")
        # Find candidate key whose token starts with prefix
        candidates = await db.digital_keys.find(
            {"revoked": False, "expires_at": {"$gt": _now()}}, {"_id": 0}
        ).to_list(500)
        for k in candidates:
            if k["token"].startswith(prefix):
                expected = hashlib.sha256(f"{k['token']}:{bucket}".encode()).hexdigest()[:12]
                if secrets.compare_digest(expected, sig):
                    await db.digital_keys.update_one(
                        {"id": k["id"]},
                        {"$inc": {"used_count": 1}, "$set": {"last_used_at": _now()}},
                    )
                    return {"ok": True, "booking_id": k["booking_id"],
                             "room_number": k.get("room_number"),
                             "guest_name": k.get("guest_name")}
        raise HTTPException(401, "Anahtar doğrulanamadı")

    @router.get("/mine/{booking_id}")
    async def my_active_key(booking_id: str):
        """Guest can look up their key by booking ID (light auth via
        booking snapshot — no need for password since the QR itself
        is the auth secret)."""
        k = await db.digital_keys.find_one(
            {"booking_id": booking_id, "revoked": False, "expires_at": {"$gt": _now()}},
            {"_id": 0, "token": 0}
        )
        return k or {}

    @router.delete("/{key_id}")
    async def revoke(key_id: str,
                       _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        r = await db.digital_keys.update_one(
            {"id": key_id}, {"$set": {"revoked": True, "revoked_at": _now()}}
        )
        return {"ok": True, "revoked": r.modified_count > 0}

    @router.get("/list")
    async def list_active(property_id: Optional[str] = None,
                           _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q: dict = {"revoked": False, "expires_at": {"$gt": _now()}}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        rows = await db.digital_keys.find(q, {"_id": 0, "token": 0}).sort("issued_at", -1).to_list(200)
        return {"total": len(rows), "items": rows}

    return router
