"""
Booking Source Attribution
--------------------------
Multi-touch attribution model for booking sources. Captures UTM parameters
and referrer on the booking widget, then runs first-click / last-click /
linear / weighted reports.

Endpoints:
  POST /api/attribution/log                     — public: log a touchpoint
  GET  /api/attribution/{property_id}/report    — admin: model breakdown
  GET  /api/attribution/{property_id}/funnel    — touch → booking funnel
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid


def create_attribution_router(db, require_roles):
    router = APIRouter()

    @router.post("/attribution/log")
    async def log_touch(data: Dict):
        """PUBLIC. Called by the booking widget on every visit / step."""
        property_id = data.get("property_id", "")
        if not property_id:
            raise HTTPException(400, "property_id required")
        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "session_id": (data.get("session_id") or "").strip(),
            "fingerprint": (data.get("fingerprint") or "").strip(),
            "event": data.get("event", "visit"),
            "utm_source":   data.get("utm_source", ""),
            "utm_medium":   data.get("utm_medium", ""),
            "utm_campaign": data.get("utm_campaign", ""),
            "utm_term":     data.get("utm_term", ""),
            "utm_content":  data.get("utm_content", ""),
            "referrer":     data.get("referrer", ""),
            "landing_page": data.get("landing_page", ""),
            "booking_id":   data.get("booking_id", ""),
            "created_at":   datetime.now(timezone.utc).isoformat(),
        }
        await db.attribution_touches.insert_one(dict(record))
        return {"ok": True, "id": record["id"]}

    def _source_key(t: dict) -> str:
        s = t.get("utm_source") or ""
        if s:
            return f"{s}/{t.get('utm_medium', '') or 'unknown'}"
        ref = t.get("referrer", "")
        if ref:
            try:
                from urllib.parse import urlparse
                host = urlparse(ref).netloc.replace("www.", "")
                return host or "direct"
            except Exception:
                return "direct"
        return "direct"

    @router.get("/attribution/{property_id}/report")
    async def report(property_id: str, days: int = 30,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        # Pull bookings in window
        bookings = await db.bookings.find(
            {"property_id": property_id, "created_at": {"$gte": since},
             "status": {"$in": ["confirmed", "checked_in", "checked_out"]}},
            {"_id": 0, "id": 1, "total_price": 1, "currency": 1, "guest_email": 1, "channel": 1}
        ).to_list(2000)
        booking_ids = {b["id"] for b in bookings}
        rev_by_id = {b["id"]: float(b.get("total_price") or 0) for b in bookings}

        # Pull all touches that ended in a booking
        touches = await db.attribution_touches.find(
            {"property_id": property_id, "created_at": {"$gte": since}},
            {"_id": 0}
        ).sort("created_at", 1).to_list(20000)

        # Group touches by session_id
        sessions: Dict[str, List[dict]] = {}
        for t in touches:
            sid = t.get("session_id") or t.get("fingerprint") or t["id"]
            sessions.setdefault(sid, []).append(t)

        models: Dict[str, Dict[str, dict]] = {
            "first_click": {}, "last_click": {}, "linear": {}, "channel_native": {},
        }
        booking_rev_attributed = 0.0

        for sid, ts in sessions.items():
            booked = next((t for t in ts if t.get("booking_id") and t["booking_id"] in booking_ids), None)
            if not booked:
                continue
            bid = booked["booking_id"]
            rev = rev_by_id.get(bid, 0)
            booking_rev_attributed += rev
            sources = [_source_key(t) for t in ts]
            sources = [s for s in sources if s]
            if not sources:
                continue
            # First-click
            fc = sources[0]
            models["first_click"].setdefault(fc, {"source": fc, "bookings": 0, "revenue": 0})
            models["first_click"][fc]["bookings"] += 1
            models["first_click"][fc]["revenue"] += rev
            # Last-click (the touch tied to the booking)
            lc = _source_key(booked)
            models["last_click"].setdefault(lc, {"source": lc, "bookings": 0, "revenue": 0})
            models["last_click"][lc]["bookings"] += 1
            models["last_click"][lc]["revenue"] += rev
            # Linear (1/N each)
            share_b = 1 / len(sources)
            share_r = rev  / len(sources)
            for s in sources:
                models["linear"].setdefault(s, {"source": s, "bookings": 0, "revenue": 0})
                models["linear"][s]["bookings"] += share_b
                models["linear"][s]["revenue"] += share_r

        # Channel-native fallback (booking.channel) for whole booking set
        for b in bookings:
            ch = b.get("channel") or "direct"
            models["channel_native"].setdefault(ch, {"source": ch, "bookings": 0, "revenue": 0})
            models["channel_native"][ch]["bookings"] += 1
            models["channel_native"][ch]["revenue"] += rev_by_id[b["id"]]

        def _to_list(d: Dict[str, dict]):
            arr = list(d.values())
            arr.sort(key=lambda x: x["revenue"], reverse=True)
            for x in arr:
                x["bookings"] = round(x["bookings"], 2)
                x["revenue"]  = round(x["revenue"], 2)
            return arr

        return {
            "window_days": days,
            "total_bookings": len(bookings),
            "total_sessions": len(sessions),
            "attributed_sessions": sum(1 for ts in sessions.values()
                                         if any(t.get("booking_id") in booking_ids for t in ts)),
            "attributed_revenue": round(booking_rev_attributed, 2),
            "first_click":     _to_list(models["first_click"]),
            "last_click":      _to_list(models["last_click"]),
            "linear":          _to_list(models["linear"]),
            "channel_native":  _to_list(models["channel_native"]),
        }

    @router.get("/attribution/{property_id}/funnel")
    async def funnel(property_id: str, days: int = 30,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        events = await db.attribution_touches.aggregate([
            {"$match": {"property_id": property_id, "created_at": {"$gte": since}}},
            {"$group": {"_id": "$event", "n": {"$sum": 1}}},
        ]).to_list(50)
        return {
            "window_days": days,
            "events": [{"event": e["_id"] or "(none)", "count": e["n"]}
                        for e in sorted(events, key=lambda x: x["n"], reverse=True)],
        }

    return router
