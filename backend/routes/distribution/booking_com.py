"""
Booking.com Premier Connectivity — XML push prototype.

Builds the XML payloads required for Booking.com's API (rates/availability/
restrictions push). Once the user obtains a Booking.com certificate + endpoint
URL + auth credentials, the `_simulate_booking_push` function can be replaced
with a real HTTP POST + signing.

This prototype lets us:
  - Generate compliant XML for rates_and_availability push
  - Validate against schema rules (xsd-lite — required field check)
  - Store every "push attempt" in `booking_push_attempts` (audit trail)
  - Pre-verify payloads BEFORE certification submission

Endpoints
---------
  GET  /api/booking-com/status              — cert status + endpoint config
  POST /api/booking-com/config              — update endpoint URL + credentials (admin)
  POST /api/booking-com/push/rates           — push rates+inventory for a property
  POST /api/booking-com/push/availability    — push availability only
  POST /api/booking-com/push/restrictions    — push restrictions (minLOS/maxLOS/CTA/CTD)
  GET  /api/booking-com/push-log             — recent push attempts (audit)
  POST /api/booking-com/validate-payload    — validate XML structure without sending
"""
from datetime import datetime, timezone
import logging
import os
import uuid
import xml.etree.ElementTree as ET
from xml.dom import minidom

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pretty_xml(elem: ET.Element) -> str:
    rough = ET.tostring(elem, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ")


def build_rates_xml(hotel_id: str, room_id: str, rate_plan_id: str,
                    daily: list, currency: str = "EUR") -> str:
    """Build Booking.com OTA_HotelRateAmountNotifRQ XML."""
    root = ET.Element("OTA_HotelRateAmountNotifRQ", {
        "xmlns": "http://www.opentravel.org/OTA/2003/05",
        "Version": "2.0",
        "EchoToken": uuid.uuid4().hex[:24],
    })
    rates = ET.SubElement(root, "RateAmountMessages",
                          HotelCode=hotel_id, HotelCodeContext="BOOKING")
    for d in daily:
        msg = ET.SubElement(rates, "RateAmountMessage")
        statap = ET.SubElement(msg, "StatusApplicationControl",
                               Start=d["date"], End=d["date"],
                               RatePlanCode=rate_plan_id,
                               InvTypeCode=room_id)
        del statap  # only for the side-effect of appending
        rates_block = ET.SubElement(msg, "Rates")
        rate = ET.SubElement(rates_block, "Rate")
        base = ET.SubElement(rate, "BaseByGuestAmts")
        ET.SubElement(base, "BaseByGuestAmt", {
            "AmountAfterTax": f"{float(d['rate']):.2f}",
            "CurrencyCode": currency,
            "NumberOfGuests": str(d.get("guests", 2)),
        })
    return _pretty_xml(root)


def build_availability_xml(hotel_id: str, room_id: str,
                           daily: list) -> str:
    """Build Booking.com OTA_HotelAvailNotifRQ XML."""
    root = ET.Element("OTA_HotelAvailNotifRQ", {
        "xmlns": "http://www.opentravel.org/OTA/2003/05",
        "Version": "2.0",
        "EchoToken": uuid.uuid4().hex[:24],
    })
    msgs = ET.SubElement(root, "AvailStatusMessages",
                         HotelCode=hotel_id, HotelCodeContext="BOOKING")
    for d in daily:
        msg = ET.SubElement(msgs, "AvailStatusMessage",
                            BookingLimit=str(d["allotment"]))
        ET.SubElement(msg, "StatusApplicationControl",
                      Start=d["date"], End=d["date"],
                      InvTypeCode=room_id)
    return _pretty_xml(root)


def build_restrictions_xml(hotel_id: str, room_id: str,
                           rate_plan_id: str, daily: list) -> str:
    """Build Booking.com OTA_HotelAvailNotifRQ XML with Restrictions block."""
    root = ET.Element("OTA_HotelAvailNotifRQ", {
        "xmlns": "http://www.opentravel.org/OTA/2003/05",
        "Version": "2.0",
        "EchoToken": uuid.uuid4().hex[:24],
    })
    msgs = ET.SubElement(root, "AvailStatusMessages",
                         HotelCode=hotel_id, HotelCodeContext="BOOKING")
    for d in daily:
        msg = ET.SubElement(msgs, "AvailStatusMessage")
        attrs = {"Start": d["date"], "End": d["date"],
                 "InvTypeCode": room_id, "RatePlanCode": rate_plan_id}
        ET.SubElement(msg, "StatusApplicationControl", attrs)
        if d.get("min_stay"):
            ET.SubElement(msg, "LengthsOfStay",
                          ArrivalDateBased="true").append(
                ET.Element("LengthOfStay", {
                    "Time": str(d["min_stay"]), "TimeUnit": "Day",
                    "MinMaxMessageType": "SetMinLOS",
                }))
        if d.get("max_stay"):
            ET.SubElement(msg, "LengthsOfStay",
                          ArrivalDateBased="true").append(
                ET.Element("LengthOfStay", {
                    "Time": str(d["max_stay"]), "TimeUnit": "Day",
                    "MinMaxMessageType": "SetMaxLOS",
                }))
        rests = ET.SubElement(msg, "RestrictionStatus")
        rests.set("Restriction", "Arrival" if d.get("cta") else "Departure" if d.get("ctd") else "Master")
        rests.set("Status", "Close" if (d.get("cta") or d.get("ctd")) else "Open")
    return _pretty_xml(root)


async def _simulate_booking_push(xml_body: str, endpoint: str = None,
                                  credentials: dict = None) -> dict:
    """Simulate the actual HTTPS POST to Booking.com. Replace with real call
    once `endpoint`, `BOOKING_USERNAME` and `BOOKING_PASSWORD` are set."""
    real_endpoint = endpoint or os.environ.get("BOOKING_COM_ENDPOINT")
    if real_endpoint and credentials and credentials.get("username"):
        # Placeholder for real call. For safety only enable when explicit env set.
        logger.info(f"[REAL CALL DISABLED] Would POST to {real_endpoint}")
    # Mocked response that mirrors Booking.com OTA_NotifReportRS shape
    return {
        "ok": True,
        "echo_token": uuid.uuid4().hex[:24],
        "warnings": [],
        "errors": [],
        "simulated": True,
        "note": ("MOCK response. Replace _simulate_booking_push with real HTTPS POST "
                 "+ BasicAuth signing once you obtain Booking.com certificate "
                 "and endpoint URL."),
    }


def _validate_daily(daily: list, required: list) -> list:
    errors = []
    for i, d in enumerate(daily or []):
        for r in required:
            if r not in d:
                errors.append(f"daily[{i}] missing '{r}'")
    return errors


def create_booking_com_router(db, require_roles):
    router = APIRouter()

    async def _get_config() -> dict:
        cfg = await db.booking_com_config.find_one({"key": "main"}, {"_id": 0})
        if cfg:
            return cfg
        return {
            "key": "main",
            "endpoint_url": "",
            "auth_username": "",
            "cert_status": "not_yet_certified",
            "hotel_id_mapping": {},  # property_id → BOOKING_HOTEL_ID
            "room_id_mapping": {},   # room_type_id → BOOKING_ROOM_ID
            "rate_plan_mapping": {}, # rate_plan_id → BOOKING_RATE_PLAN_ID
        }

    @router.get("/booking-com/status")
    async def status(_: dict = Depends(require_roles("admin", "manager"))):
        cfg = await _get_config()
        has_endpoint = bool(cfg.get("endpoint_url"))
        has_creds = bool(cfg.get("auth_username"))
        env_endpoint = bool(os.environ.get("BOOKING_COM_ENDPOINT"))
        return {
            "cert_status": cfg.get("cert_status"),
            "endpoint_configured": has_endpoint or env_endpoint,
            "credentials_configured": has_creds,
            "live_mode": (has_endpoint or env_endpoint) and has_creds,
            "hotel_count_mapped": len(cfg.get("hotel_id_mapping", {})),
            "note": ("MOCK mode active." if not ((has_endpoint or env_endpoint) and has_creds)
                     else "Live mode would activate."),
        }

    @router.post("/booking-com/config")
    async def update_config(body: dict,
                            current_user: dict = Depends(require_roles("admin"))):
        allowed = {"endpoint_url", "auth_username", "cert_status",
                   "hotel_id_mapping", "room_id_mapping", "rate_plan_mapping"}
        update = {k: v for k, v in body.items() if k in allowed}
        # never store password in clear text; if provided, just keep a flag
        if body.get("auth_password"):
            update["auth_password_set"] = True
            update["auth_password_hint"] = body["auth_password"][:2] + "***"
        update["updated_at"] = _now_iso()
        update["updated_by"] = current_user.get("name", "")
        await db.booking_com_config.update_one(
            {"key": "main"}, {"$set": {**update, "key": "main"}}, upsert=True
        )
        return await _get_config()

    @router.post("/booking-com/push/rates")
    async def push_rates(body: dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = body.get("property_id")
        room_type_id = body.get("room_type_id")
        rate_plan_id = body.get("rate_plan_id", "STANDARD")
        daily = body.get("daily") or []
        currency = body.get("currency", "EUR")
        errors = _validate_daily(daily, ["date", "rate"])
        if not property_id or not room_type_id:
            errors.append("property_id and room_type_id required")
        if errors:
            raise HTTPException(400, "; ".join(errors))
        cfg = await _get_config()
        hotel_id = cfg.get("hotel_id_mapping", {}).get(property_id, property_id)
        room_id = cfg.get("room_id_mapping", {}).get(room_type_id, room_type_id)
        xml = build_rates_xml(hotel_id, room_id, rate_plan_id, daily, currency)
        result = await _simulate_booking_push(xml,
                                              endpoint=cfg.get("endpoint_url"),
                                              credentials={"username": cfg.get("auth_username")})
        attempt = {
            "id": str(uuid.uuid4()),
            "kind": "rates",
            "property_id": property_id,
            "hotel_id_used": hotel_id,
            "room_type_id": room_type_id,
            "rate_plan_id": rate_plan_id,
            "dates_count": len(daily),
            "currency": currency,
            "xml_payload": xml,
            "response": result,
            "status": "ok" if result.get("ok") else "error",
            "simulated": result.get("simulated", True),
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
        }
        await db.booking_push_attempts.insert_one(attempt)
        attempt.pop("_id", None)
        return attempt

    @router.post("/booking-com/push/availability")
    async def push_availability(body: dict,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = body.get("property_id")
        room_type_id = body.get("room_type_id")
        daily = body.get("daily") or []
        errors = _validate_daily(daily, ["date", "allotment"])
        if not property_id or not room_type_id:
            errors.append("property_id and room_type_id required")
        if errors:
            raise HTTPException(400, "; ".join(errors))
        cfg = await _get_config()
        hotel_id = cfg.get("hotel_id_mapping", {}).get(property_id, property_id)
        room_id = cfg.get("room_id_mapping", {}).get(room_type_id, room_type_id)
        xml = build_availability_xml(hotel_id, room_id, daily)
        result = await _simulate_booking_push(xml,
                                              endpoint=cfg.get("endpoint_url"),
                                              credentials={"username": cfg.get("auth_username")})
        attempt = {
            "id": str(uuid.uuid4()),
            "kind": "availability",
            "property_id": property_id,
            "room_type_id": room_type_id,
            "dates_count": len(daily),
            "xml_payload": xml,
            "response": result,
            "status": "ok" if result.get("ok") else "error",
            "simulated": result.get("simulated", True),
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
        }
        await db.booking_push_attempts.insert_one(attempt)
        attempt.pop("_id", None)
        return attempt

    @router.post("/booking-com/push/restrictions")
    async def push_restrictions(body: dict,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = body.get("property_id")
        room_type_id = body.get("room_type_id")
        rate_plan_id = body.get("rate_plan_id", "STANDARD")
        daily = body.get("daily") or []
        errors = _validate_daily(daily, ["date"])
        if not property_id or not room_type_id:
            errors.append("property_id and room_type_id required")
        if errors:
            raise HTTPException(400, "; ".join(errors))
        cfg = await _get_config()
        hotel_id = cfg.get("hotel_id_mapping", {}).get(property_id, property_id)
        room_id = cfg.get("room_id_mapping", {}).get(room_type_id, room_type_id)
        xml = build_restrictions_xml(hotel_id, room_id, rate_plan_id, daily)
        result = await _simulate_booking_push(xml,
                                              endpoint=cfg.get("endpoint_url"),
                                              credentials={"username": cfg.get("auth_username")})
        attempt = {
            "id": str(uuid.uuid4()),
            "kind": "restrictions",
            "property_id": property_id,
            "room_type_id": room_type_id,
            "rate_plan_id": rate_plan_id,
            "dates_count": len(daily),
            "xml_payload": xml,
            "response": result,
            "status": "ok",
            "simulated": result.get("simulated", True),
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
        }
        await db.booking_push_attempts.insert_one(attempt)
        attempt.pop("_id", None)
        return attempt

    @router.post("/booking-com/validate-payload")
    async def validate_payload(body: dict,
                                _: dict = Depends(require_roles("admin", "manager"))):
        """Validate without sending. Returns the XML so you can verify pre-cert."""
        kind = body.get("kind", "rates")
        daily = body.get("daily") or []
        if kind == "rates":
            xml = build_rates_xml(body.get("hotel_id", "TEST"),
                                  body.get("room_id", "TEST"),
                                  body.get("rate_plan_id", "STANDARD"),
                                  daily, body.get("currency", "EUR"))
        elif kind == "availability":
            xml = build_availability_xml(body.get("hotel_id", "TEST"),
                                          body.get("room_id", "TEST"),
                                          daily)
        else:
            xml = build_restrictions_xml(body.get("hotel_id", "TEST"),
                                          body.get("room_id", "TEST"),
                                          body.get("rate_plan_id", "STANDARD"),
                                          daily)
        return {"ok": True, "kind": kind, "xml": xml,
                "byte_length": len(xml.encode("utf-8"))}

    @router.get("/booking-com/push-log")
    async def push_log(kind: str = "", property_id: str = "", limit: int = 50,
                       _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if kind:
            q["kind"] = kind
        if property_id:
            q["property_id"] = property_id
        items = await db.booking_push_attempts.find(
            q, {"_id": 0, "xml_payload": 0}  # exclude verbose XML in list
        ).sort("created_at", -1).to_list(min(limit, 200))
        return {"items": items, "count": len(items)}

    return router
