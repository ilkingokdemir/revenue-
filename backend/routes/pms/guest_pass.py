"""Misafir cüzdanı: web geçiş kartı (/pass/{ref}), QR, .ics takvim; Apple/Google Wallet anahtar gelince aktif."""
import io
import os
import uuid
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Response


def create_guest_pass_router(db, require_roles):
    router = APIRouter()

    async def _booking(ref: str, email: str) -> dict:
        b = await db.bookings.find_one({"booking_ref": ref.strip(), "guest_email": (email or "").strip()}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Rezervasyon bulunamadı")
        return b

    async def _wallet_settings(pid: str) -> dict:
        doc = await db.wallet_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
        return {"apple_pass_type_id": "", "apple_team_id": "", "apple_cert_present": False, "google_issuer_id": "", "google_sa_present": False, **doc}

    @router.get("/guest-pass/{ref}")
    async def pass_data(ref: str, email: str):
        b = await _booking(ref, email)
        prop = await db.properties.find_one({"id": b.get("property_id")}, {"_id": 0, "name": 1, "address": 1, "city": 1, "country": 1, "phone": 1, "check_in_time": 1, "check_out_time": 1}) or {}
        ws = await _wallet_settings(b.get("property_id") or "")
        return {"booking_ref": b["booking_ref"], "guest_name": b.get("guest_name"), "check_in": b.get("check_in"), "check_out": b.get("check_out"),
                "nights": b.get("nights"), "adults": b.get("adults"), "children": b.get("children"), "room_name": b.get("room_name") or b.get("room_type"),
                "room_number": b.get("room_number"), "rate_plan_name": b.get("rate_plan_name"), "status": b.get("status"), "payment_status": b.get("payment_status"),
                "total_price": b.get("cart_total") or b.get("total_price"), "currency": b.get("currency"), "balance_due": b.get("balance_due", 0),
                "extras": [{"name": u.get("name"), "price": u.get("price"), "paid": bool(u.get("paid"))} for u in (b.get("post_upsells") or [])],
                "hotel": {"name": prop.get("name"), "address": ", ".join(x for x in [prop.get("address"), prop.get("city"), prop.get("country")] if x),
                          "phone": prop.get("phone"), "check_in_time": prop.get("check_in_time") or "15:00", "check_out_time": prop.get("check_out_time") or "11:00"},
                "wallet": {"apple_ready": bool(ws.get("apple_cert_present") and ws.get("apple_pass_type_id")), "google_ready": bool(ws.get("google_sa_present") and ws.get("google_issuer_id"))}}

    @router.get("/guest-pass/{ref}/qr.png")
    async def pass_qr(ref: str, email: str):
        b = await _booking(ref, email)
        import qrcode
        img = qrcode.make(f"MHB|{b['booking_ref']}|{b.get('guest_email', '')}|{b.get('check_in', '')}", box_size=8, border=2)
        buf = io.BytesIO(); img.save(buf, format="PNG")
        return Response(buf.getvalue(), media_type="image/png")

    @router.get("/guest-pass/{ref}/calendar.ics")
    async def pass_ics(ref: str, email: str):
        b = await _booking(ref, email)
        prop = await db.properties.find_one({"id": b.get("property_id")}, {"_id": 0, "name": 1, "address": 1, "city": 1}) or {}
        ci = (b.get("check_in") or "").replace("-", ""); co = (b.get("check_out") or "").replace("-", "")
        extras = ", ".join(u.get("name", "") for u in (b.get("post_upsells") or []))
        base = (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
        ics = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MyHotelBox//Guest Pass//EN", "BEGIN:VEVENT",
                           f"UID:{b['booking_ref']}@myhotelbox", f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                           f"DTSTART;VALUE=DATE:{ci}", f"DTEND;VALUE=DATE:{co}", f"SUMMARY:{prop.get('name', 'Hotel')} — {b['booking_ref']}",
                           f"LOCATION:{prop.get('address', '')} {prop.get('city', '')}".strip(),
                           f"DESCRIPTION:{b.get('room_name') or b.get('room_type') or ''}" + (f" · Ekstralar: {extras}" if extras else "") + (f" · {base}/pass/{b['booking_ref']}?email={b.get('guest_email', '')}" if base else ""),
                           "END:VEVENT", "END:VCALENDAR"])
        return Response(ics, media_type="text/calendar; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{b["booking_ref"]}.ics"'})

    @router.get("/guest-pass/{ref}/apple.pkpass")
    async def apple_pass(ref: str, email: str):
        b = await _booking(ref, email)
        ws = await _wallet_settings(b.get("property_id") or "")
        if not (ws.get("apple_cert_present") and ws.get("apple_pass_type_id")):
            raise HTTPException(503, "Apple Wallet sertifikası tanımlı değil — Ayarlar › Cüzdan")
        raise HTTPException(501, "PassKit imzalama sertifika yüklendiğinde etkinleşir")

    @router.get("/guest-pass/{ref}/google")
    async def google_pass(ref: str, email: str):
        b = await _booking(ref, email)
        ws = await _wallet_settings(b.get("property_id") or "")
        if not (ws.get("google_sa_present") and ws.get("google_issuer_id")):
            raise HTTPException(503, "Google Wallet servis hesabı tanımlı değil — Ayarlar › Cüzdan")
        raise HTTPException(501, "Google Wallet JWT servis hesabı yüklendiğinde etkinleşir")

    @router.get("/wallet-settings/{pid}")
    async def wallet_settings_get(pid: str, _u: dict = Depends(require_roles("admin", "manager"))):
        return await _wallet_settings(pid)

    @router.put("/wallet-settings/{pid}")
    async def wallet_settings_put(pid: str, data: Dict, _u: dict = Depends(require_roles("admin", "manager"))):
        upd = {"property_id": pid, "apple_pass_type_id": str(data.get("apple_pass_type_id") or "")[:80], "apple_team_id": str(data.get("apple_team_id") or "")[:20],
               "google_issuer_id": str(data.get("google_issuer_id") or "")[:40], "updated_at": datetime.now(timezone.utc).isoformat()}
        if data.get("apple_cert_pem"):
            upd["apple_cert_pem"] = str(data["apple_cert_pem"])[:20000]; upd["apple_cert_present"] = True
        if data.get("google_sa_json"):
            upd["google_sa_json"] = str(data["google_sa_json"])[:20000]; upd["google_sa_present"] = True
        await db.wallet_settings.update_one({"property_id": pid}, {"$set": upd, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
        return await _wallet_settings(pid)

    return router
