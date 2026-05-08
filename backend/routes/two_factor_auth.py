"""
Two-Factor Authentication (P2) — TOTP-based (Google Authenticator, Authy, 1Password).
Admin/manager accounts can enable 2FA for a security boost. User enrolls once,
scans QR, then future logins require a 6-digit code.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import uuid
import base64
import io
import logging

try:
    import pyotp
    PYOTP_OK = True
except ImportError:  # pragma: no cover
    PYOTP_OK = False

logger = logging.getLogger(__name__)


def create_2fa_router(db, require_roles, get_current_user):
    router = APIRouter()

    ISSUER = "MyHotelBox"

    @router.get("/2fa/status")
    async def status(current_user: dict = Depends(get_current_user)):
        user_id = current_user.get("id") or current_user.get("email")
        row = await db.user_2fa.find_one({"user_id": user_id}, {"_id": 0})
        return {
            "enabled": bool(row and row.get("enabled")),
            "enrolled": bool(row),
            "email": current_user.get("email", ""),
        }

    @router.post("/2fa/enroll")
    async def enroll(current_user: dict = Depends(get_current_user)):
        """Generate a TOTP secret + otpauth URL. User must verify before it's activated."""
        if not PYOTP_OK:
            raise HTTPException(status_code=503, detail="2FA library not installed")
        user_id = current_user.get("id") or current_user.get("email")
        email = current_user.get("email", "user@myhotelbox")
        secret = pyotp.random_base32()
        otpauth = pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)
        await db.user_2fa.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "email": email,
                "secret": secret,
                "enabled": False,
                "enrolled_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        return {
            "secret": secret,
            "otpauth_url": otpauth,
            "issuer": ISSUER,
            "account": email,
        }

    @router.post("/2fa/verify")
    async def verify(data: Dict, current_user: dict = Depends(get_current_user)):
        """Verify a 6-digit code against the pending secret.
        On first successful verification, sets enabled=True.
        Body: {code: '123456'}
        """
        if not PYOTP_OK:
            raise HTTPException(status_code=503, detail="2FA library not installed")
        code = str(data.get("code") or "").strip()
        if len(code) != 6 or not code.isdigit():
            raise HTTPException(status_code=400, detail="6-digit code required")
        user_id = current_user.get("id") or current_user.get("email")
        row = await db.user_2fa.find_one({"user_id": user_id}, {"_id": 0})
        if not row:
            raise HTTPException(status_code=404, detail="Not enrolled — call /2fa/enroll first")
        ok = pyotp.totp.TOTP(row["secret"]).verify(code, valid_window=1)
        if not ok:
            raise HTTPException(status_code=401, detail="Invalid code")
        if not row.get("enabled"):
            backup_codes = [base64.b32encode(uuid.uuid4().bytes)[:10].decode() for _ in range(8)]
            await db.user_2fa.update_one(
                {"user_id": user_id},
                {"$set": {"enabled": True, "activated_at": datetime.now(timezone.utc).isoformat(),
                          "backup_codes": backup_codes}}
            )
            return {"status": "enabled", "backup_codes": backup_codes}
        return {"status": "verified"}

    @router.post("/2fa/disable")
    async def disable(data: Dict, current_user: dict = Depends(get_current_user)):
        """Disable 2FA — requires the current TOTP code as proof of possession."""
        if not PYOTP_OK:
            raise HTTPException(status_code=503, detail="2FA library not installed")
        code = str(data.get("code") or "").strip()
        user_id = current_user.get("id") or current_user.get("email")
        row = await db.user_2fa.find_one({"user_id": user_id}, {"_id": 0})
        if not row or not row.get("enabled"):
            raise HTTPException(status_code=409, detail="2FA not enabled")
        if not pyotp.totp.TOTP(row["secret"]).verify(code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid code")
        await db.user_2fa.delete_one({"user_id": user_id})
        return {"status": "disabled"}

    return router
