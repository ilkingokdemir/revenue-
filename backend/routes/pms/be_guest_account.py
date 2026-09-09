"""Misafir hesabı: e-posta magic-link girişi → otomatik doldurma, geçmiş rezervasyonlar, sadakat puanı; tek tık tekrar rezervasyon."""
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

now = lambda: datetime.now(timezone.utc)
now_iso = lambda: now().isoformat()


class MagicLinkReq(BaseModel):
    email: EmailStr
    property_id: str
    lang: str = "tr"
    return_path: str = "/book"


def create_guest_account_router(db, require_roles):
    router = APIRouter(tags=["guest-account"])

    async def _profile(email: str, pid: str) -> dict:
        email = email.lower()
        bookings = await db.bookings.find({"guest_email": email, "status": {"$nin": ["cancelled"]}}, {"_id": 0, "id": 1, "booking_ref": 1, "property_id": 1, "room_type_id": 1, "room_name": 1, "check_in": 1, "check_out": 1, "nights": 1, "adults": 1, "children": 1, "total_price": 1, "cart_total": 1, "currency": 1, "status": 1, "guest_name": 1, "guest_phone": 1, "special_requests": 1, "rate_plan_id": 1, "created_at": 1}).sort("check_in", -1).to_list(50)
        last = bookings[0] if bookings else {}
        prof = await db.guest_profiles.find_one({"email": email}, {"_id": 0, "name": 1, "phone": 1, "country": 1, "loyalty_tier": 1, "preferences": 1}) or {}
        mem = await db.loyalty_members.find_one({"email": email}, {"_id": 0, "tier": 1, "points": 1, "lifetime_points": 1, "name": 1}) or {}
        props = {p["id"]: p.get("name") for p in await db.properties.find({"id": {"$in": list({b["property_id"] for b in bookings})}}, {"_id": 0, "id": 1, "name": 1}).to_list(50)}
        today = now().date().isoformat()
        for b in bookings:
            b["property_name"] = props.get(b["property_id"], b["property_id"]); b["past"] = b["check_out"] < today
            b["rebook_url"] = f"/book?property={b['property_id']}&room={b.get('room_type_id', '')}&adults={b.get('adults', 2)}&rebook={b['booking_ref']}"
        return {"email": email, "name": prof.get("name") or mem.get("name") or last.get("guest_name", ""), "phone": prof.get("phone") or last.get("guest_phone", ""),
                "stays": sum(1 for b in bookings if b["past"]), "upcoming": [b for b in bookings if not b["past"]][:5], "past": [b for b in bookings if b["past"]][:5],
                "loyalty": {"tier": (mem.get("tier") or prof.get("loyalty_tier") or ("silver" if len(bookings) >= 3 else "bronze")).lower(), "points": int(mem.get("points") or 0), "lifetime_points": int(mem.get("lifetime_points") or 0), "member": bool(mem)},
                "returning": bool(bookings), "property_id": pid}

    @router.post("/booking/guest-account/magic-link")
    async def magic_link(req: MagicLinkReq):
        token = secrets.token_urlsafe(24)
        await db.guest_login_tokens.insert_one({"token": token, "email": req.email.lower(), "property_id": req.property_id, "created_at": now_iso(), "expires_at": (now() + timedelta(minutes=20)).isoformat(), "used": False})
        base = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("FRONTEND_URL") or ""
        link = f"{base}{req.return_path}?property={req.property_id}&glt={token}"
        from routes.platform_ext.mailer import send_email
        prop = await db.properties.find_one({"id": req.property_id}, {"_id": 0, "name": 1}) or {}
        status = await send_email(db, req.email, f"{prop.get('name', 'Otel')} — giriş bağlantınız", f"<p>Rezervasyon bilgilerinizin otomatik dolması ve geçmiş konaklamalarınızı görmek için <a href='{link}'>buraya tıklayın</a>. Bağlantı 20 dakika geçerlidir.</p>", kind="guest_magic_link", meta={"property_id": req.property_id})
        out = {"ok": True, "sent": status, "expires_in_min": 20}
        if status in ("mocked", "mock", "queued_mock") or not os.environ.get("RESEND_API_KEY"):
            out["dev_link"] = link; out["dev_token"] = token  # MOCK e-posta: test için bağlantı yanıtla döner
        return out

    @router.get("/booking/guest-account/session/{token}")
    async def verify(token: str):
        t = await db.guest_login_tokens.find_one({"token": token}, {"_id": 0})
        if not t or t.get("used") or t["expires_at"] < now_iso():
            raise HTTPException(401, "Bağlantı geçersiz veya süresi dolmuş")
        await db.guest_login_tokens.update_one({"token": token}, {"$set": {"used": True, "used_at": now_iso()}})
        sess = secrets.token_urlsafe(32)
        await db.guest_sessions.insert_one({"session": sess, "email": t["email"], "property_id": t["property_id"], "created_at": now_iso(), "expires_at": (now() + timedelta(days=30)).isoformat()})
        return {"session": sess, "profile": await _profile(t["email"], t["property_id"])}

    @router.get("/booking/guest-account/me")
    async def me(session: str, property_id: str = ""):
        s = await db.guest_sessions.find_one({"session": session}, {"_id": 0})
        if not s or s["expires_at"] < now_iso():
            raise HTTPException(401, "Oturum geçersiz")
        return {"profile": await _profile(s["email"], property_id or s["property_id"])}

    @router.post("/booking/guest-account/logout")
    async def logout(data: dict):
        await db.guest_sessions.delete_one({"session": str(data.get("session") or "")})
        return {"ok": True}

    @router.post("/booking/guest-account/dev-verify-latest")
    async def dev_latest(data: dict):
        """Test yardımcısı: MOCK e-posta ortamında son token'ı döner (RESEND_API_KEY varsa kapalı)."""
        if os.environ.get("RESEND_API_KEY"):
            raise HTTPException(403, "Canlı e-posta modunda kapalı")
        t = await db.guest_login_tokens.find_one({"email": str(data.get("email") or "").lower(), "used": False}, {"_id": 0, "token": 1}, sort=[("created_at", -1)])
        if not t:
            raise HTTPException(404, "Token yok")
        return {"token": t["token"]}

    return router
