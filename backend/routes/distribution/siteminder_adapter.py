"""
SiteMinder Middleware Translator Adapter (iter 375)
====================================================
SiteMinder, 450+ OTA'yı tek webhook'ta toplar. Bu adaptör SiteMinder'ın
reservation push formatını (JSON veya OTA_HotelResNotifRQ XML) alır,
kanal kodunu iç kanal anahtarına çevirir ve mevcut OTA inbound pipeline'ına
(auto room assign dahil) besler.

Endpoints
---------
  POST /api/siteminder/webhook          — reservation/modification/cancellation push
  GET  /api/siteminder/mappings         — kanal kodu → iç kanal eşlemesi
  PUT  /api/siteminder/mappings         — eşleme override
  GET  /api/siteminder/log              — son çeviri olayları
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
import logging
import uuid
from defusedxml import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routes.integrations_pkg.ota_inbound import (
    _auto_assign_room, _notify_auto_assign, ALLOWED_CHANNELS,
)

logger = logging.getLogger(__name__)

# SiteMinder channel codes → internal channel keys
DEFAULT_CHANNEL_MAP = {
    "BDC": "booking_com", "BOOKING.COM": "booking_com", "BOOKINGCOM": "booking_com",
    "EXP": "expedia", "EXPEDIA": "expedia",
    "ABB": "airbnb", "AIRBNB": "airbnb",
    "AGO": "agoda", "AGODA": "agoda",
    "CTP": "trip_com", "TRIP.COM": "trip_com", "CTRIP": "trip_com",
    "SM-DIRECT": "direct", "DIRECT": "direct",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _resolve_channel(db, code: str) -> Optional[str]:
    code_u = (code or "").strip().upper()
    row = await db.siteminder_channel_map.find_one({"code": code_u}, {"_id": 0, "channel": 1})
    if row:
        return row["channel"]
    ch = DEFAULT_CHANNEL_MAP.get(code_u)
    if not ch:
        logger.warning(f"SiteMinder: bilinmeyen kanal kodu '{code_u}' — webhook reddedildi")
    return ch


def _parse_ota_xml(raw: str) -> dict:
    """Minimal OTA_HotelResNotifRQ parse — reservation temel alanları."""
    ns_strip = lambda t: t.split("}")[-1]
    root = ET.fromstring(raw)
    out: dict = {"event": "reservation"}
    for el in root.iter():
        tag = ns_strip(el.tag)
        if tag == "HotelReservation":
            out["reservation_id"] = el.get("ResID_Value") or el.get("CreateDateTime", "")
        elif tag == "UniqueID" and not out.get("reservation_id"):
            out["reservation_id"] = el.get("ID", "")
        elif tag == "BasicPropertyInfo":
            out["property_id"] = el.get("HotelCode", "")
        elif tag == "TimeSpan":
            out["check_in"] = el.get("Start", "")
            out["check_out"] = el.get("End", "")
        elif tag == "Total":
            out["total_price"] = float(el.get("AmountAfterTax") or el.get("AmountBeforeTax") or 0)
            out["currency"] = el.get("CurrencyCode", "GBP")
        elif tag == "GivenName":
            out["_given"] = (el.text or "").strip()
        elif tag == "Surname":
            out["_surname"] = (el.text or "").strip()
        elif tag == "Email":
            out["guest_email"] = (el.text or "").strip()
        elif tag == "RoomType":
            out["room_type_id"] = el.get("RoomTypeCode") or out.get("room_type_id")
        elif tag == "Source":
            out["channel_code"] = el.get("BookingChannelCode") or out.get("channel_code")
        elif tag == "BookingChannel":
            out["channel_code"] = el.get("Type") or out.get("channel_code")
        elif tag == "GuestCount":
            try:
                out["guest_count"] = out.get("guest_count", 0) + int(el.get("Count") or 1)
            except Exception:
                pass
    out["guest_name"] = f"{out.pop('_given', '')} {out.pop('_surname', '')}".strip() or "SiteMinder Guest"
    return out


class SMReservation(BaseModel):
    event: str = "reservation"          # reservation | modification | cancellation
    reservation_id: str
    channel_code: str                    # SiteMinder channel code, örn. "BDC"
    property_id: Optional[str] = None
    guest_name: Optional[str] = None
    guest_email: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    room_type_id: Optional[str] = None
    total_price: float = 0
    currency: str = "GBP"
    guest_count: int = 1
    raw: Optional[dict] = None


class ChannelMapOverride(BaseModel):
    code: str
    channel: str


async def _ingest_reservation(db, data: dict) -> dict:
    """Çevrilmiş payload'ı bookings'e upsert et + auto-assign uygula."""
    channel = data["channel"]
    ref = data["reservation_id"]
    booking_key = f"{channel}:{ref}"
    existing = await db.bookings.find_one({"channel_key": booking_key},
                                          {"_id": 0, "id": 1, "room_id": 1, "room_number": 1})
    booking_id = existing["id"] if existing else str(uuid.uuid4())

    assignment_info: dict = {}
    notif_kind = None
    room_id, room_number = None, None
    already_assigned = bool(existing and (existing.get("room_id") or existing.get("room_number")))
    if not already_assigned and data.get("property_id"):
        picked = await _auto_assign_room(
            db, property_id=data["property_id"], room_type_id=data.get("room_type_id"),
            check_in=data.get("check_in", ""), check_out=data.get("check_out", ""),
            guest_email=data.get("guest_email"), exclude_booking_id=booking_id)
        if picked:
            room_id = picked.get("id")
            room_number = picked.get("name") or picked.get("id")
            assignment_info = {"auto_assigned": True, "assigned_room_id": room_id,
                               "assigned_score": picked.get("_score"),
                               "assigned_upgrade": picked.get("_upgrade", False),
                               "assigned_at": _now()}
            notif_kind = "upgrade" if picked.get("_upgrade") else "success"
        else:
            assignment_info = {"auto_assigned": False,
                               "room_assignment_status": "unassigned",
                               "unassigned_reason": "no_available_room",
                               "assigned_at": _now()}
            notif_kind = "unassigned"

    doc = {
        "id": booking_id, "channel_key": booking_key, "channel": channel,
        "channel_reference": ref, "property_id": data.get("property_id"),
        "guest_name": data.get("guest_name"), "guest_email": data.get("guest_email"),
        "check_in": data.get("check_in"), "check_out": data.get("check_out"),
        "room_number": room_number, "room_id": room_id,
        "room_type_id": data.get("room_type_id"),
        "total_price": data.get("total_price"), "currency": data.get("currency", "GBP"),
        "guest_count": data.get("guest_count", 1), "status": "confirmed",
        "source": f"ota:{channel}", "via_middleware": "siteminder",
        "created_at": _now() if not existing else None, "updated_at": _now(),
        **assignment_info,
    }
    doc = {k: v for k, v in doc.items() if v is not None}
    await db.bookings.update_one({"channel_key": booking_key}, {"$set": doc}, upsert=True)
    if notif_kind:
        await _notify_auto_assign(db, notif_kind, doc,
                                  extra={"via": "siteminder",
                                         "score": assignment_info.get("assigned_score")})
    return {"booking_id": booking_id, "action": "updated" if existing else "created",
            "auto_assigned": assignment_info.get("auto_assigned", False),
            "room_number": room_number}


def create_siteminder_router(db, require_roles):
    router = APIRouter(prefix="/siteminder", tags=["siteminder"])

    @router.post("/webhook")
    async def webhook(request: Request):
        """SiteMinder push — JSON (SMReservation) veya OTA XML kabul eder."""
        ctype = (request.headers.get("content-type") or "").lower()
        raw_body = await request.body()
        try:
            if "xml" in ctype:
                parsed = _parse_ota_xml(raw_body.decode("utf-8", errors="replace"))
                payload = SMReservation(
                    event=parsed.get("event", "reservation"),
                    reservation_id=parsed.get("reservation_id") or str(uuid.uuid4())[:8],
                    channel_code=parsed.get("channel_code", "BDC"),
                    property_id=parsed.get("property_id"),
                    guest_name=parsed.get("guest_name"),
                    guest_email=parsed.get("guest_email"),
                    check_in=parsed.get("check_in"), check_out=parsed.get("check_out"),
                    room_type_id=parsed.get("room_type_id"),
                    total_price=parsed.get("total_price", 0),
                    currency=parsed.get("currency", "GBP"),
                    guest_count=parsed.get("guest_count", 1) or 1,
                )
            else:
                import json as _json
                payload = SMReservation(**_json.loads(raw_body))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Payload çözümlenemedi: {e}")

        channel = await _resolve_channel(db, payload.channel_code)
        if not channel:
            raise HTTPException(400, f"Bilinmeyen kanal kodu: {payload.channel_code} — /api/siteminder/mappings ile eşleme ekleyin")
        event_id = str(uuid.uuid4())
        log_doc = {
            "id": event_id, "event": payload.event,
            "channel_code": payload.channel_code, "resolved_channel": channel,
            "reservation_id": payload.reservation_id,
            "format": "xml" if "xml" in ctype else "json",
            "received_at": _now(),
        }

        if payload.event == "cancellation":
            booking_key = f"{channel}:{payload.reservation_id}"
            r = await db.bookings.update_one(
                {"channel_key": booking_key},
                {"$set": {"status": "cancelled", "cancelled_at": _now(),
                          "cancellation_reason": "SiteMinder cancellation"}})
            log_doc["result"] = {"cancelled": r.modified_count > 0}
            await db.siteminder_log.insert_one(log_doc)
            return {"ok": True, "event_id": event_id, "channel": channel,
                    "cancelled": r.modified_count > 0}

        if channel not in ALLOWED_CHANNELS and channel != "direct":
            raise HTTPException(400, f"Çözümlenemeyen kanal kodu: {payload.channel_code}")

        result = await _ingest_reservation(db, {
            "channel": channel, "reservation_id": payload.reservation_id,
            "property_id": payload.property_id, "guest_name": payload.guest_name,
            "guest_email": payload.guest_email, "check_in": payload.check_in,
            "check_out": payload.check_out, "room_type_id": payload.room_type_id,
            "total_price": payload.total_price, "currency": payload.currency,
            "guest_count": payload.guest_count,
        })
        log_doc["result"] = result
        await db.siteminder_log.insert_one(log_doc)
        return {"ok": True, "event_id": event_id, "channel": channel, **result}

    @router.get("/mappings")
    async def get_mappings(_: dict = Depends(require_roles("admin", "manager"))):
        overrides = await db.siteminder_channel_map.find({}, {"_id": 0}).to_list(200)
        ov_codes = {o["code"] for o in overrides}
        items = list(overrides)
        for code, ch in DEFAULT_CHANNEL_MAP.items():
            if code not in ov_codes:
                items.append({"code": code, "channel": ch, "default": True})
        items.sort(key=lambda x: x["code"])
        return {"total": len(items), "items": items}

    @router.put("/mappings")
    async def set_mapping(body: ChannelMapOverride,
                          _: dict = Depends(require_roles("admin", "manager"))):
        if body.channel not in ALLOWED_CHANNELS and body.channel != "direct":
            raise HTTPException(400, f"Geçersiz iç kanal: {body.channel}")
        code = body.code.strip().upper()
        await db.siteminder_channel_map.update_one(
            {"code": code},
            {"$set": {"code": code, "channel": body.channel, "updated_at": _now()}},
            upsert=True)
        return {"ok": True, "code": code, "channel": body.channel}

    @router.get("/log")
    async def get_log(limit: int = 50,
                      _: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.siteminder_log.find({}, {"_id": 0}) \
            .sort("received_at", -1).to_list(min(limit, 200))
        return {"total": len(rows), "items": rows}

    return router
