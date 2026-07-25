"""
Spaces — Multi-Product Inventory
--------------------------------
Single bookable-resource engine for non-room sellable items: parking spots,
EV charge slots, meeting rooms, bicycles, lockers, kayaks, bicycles, cabanas.
Inspired by Mews "Spaces" but lighter — full hourly or daily resolution.

Endpoints:
  GET  /api/spaces/{property_id}                          — list
  POST /api/spaces/{property_id}                           — upsert
  DELETE /api/spaces/{property_id}/{space_id}
  GET  /api/spaces/{property_id}/{space_id}/availability?from&to
  POST /api/space-bookings                                 — book
  GET  /api/space-bookings/{property_id}                   — list bookings
  POST /api/space-bookings/{id}/cancel
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional, Any
import uuid
import logging

logger = logging.getLogger(__name__)


SPACE_KINDS = ["parking", "ev_charger", "meeting_room", "bicycle", "locker", "cabana", "kayak", "other"]


def create_spaces_router(db, require_roles):
    router = APIRouter()

    @router.get("/spaces/{property_id}")
    async def list_spaces(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        rows = await db.spaces.find(
            {"property_id": property_id, "active": {"$ne": False}}, {"_id": 0}
        ).sort("kind", 1).to_list(200)
        return rows

    @router.post("/spaces/{property_id}")
    async def upsert(property_id: str, data: Dict,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        sid = data.get("id") or str(uuid.uuid4())
        kind = data.get("kind", "other")
        if kind not in SPACE_KINDS:
            kind = "other"
        unit = data.get("unit_minutes")  # null = daily, int = hourly grain
        if unit is not None:
            try:
                unit = max(15, int(unit))
            except Exception:
                unit = None
        update = {
            "id": sid,
            "property_id": property_id,
            "kind": kind,
            "name": data.get("name", "Untitled space"),
            "code": data.get("code", ""),
            "capacity": int(data.get("capacity") or 1),
            "rate_per_unit": float(data.get("rate_per_unit") or 0),
            "currency": data.get("currency", "GBP"),
            "unit_minutes": unit,        # None = day-rate
            "open_hour":  int(data.get("open_hour", 0)),
            "close_hour": int(data.get("close_hour", 24)),
            "active": bool(data.get("active", True)),
            "description": data.get("description", ""),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.spaces.update_one(
            {"id": sid}, {"$set": update, "$setOnInsert": {"created_at": update["updated_at"]}}, upsert=True
        )
        doc = await db.spaces.find_one({"id": sid}, {"_id": 0})
        return {"ok": True, "space": doc}

    @router.delete("/spaces/{property_id}/{space_id}")
    async def deactivate(property_id: str, space_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.spaces.update_one({"id": space_id, "property_id": property_id}, {"$set": {"active": False}})
        return {"ok": True}

    @router.post("/spaces/{property_id}/seed")
    async def seed_starter_spaces(property_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """One-click starter kit: creates 6 curated spaces (parking, meeting rooms,
        coworking desk, EV charger, bike, locker) with sensible defaults so new
        operators can immediately experiment with the Spaces revenue channel.

        Writes to BOTH db.spaces (this router's list endpoint) AND db.property_spaces
        (the pms/bookings.py list endpoint that the SpacesPanel FE actually hits)
        so the seeded rows show up regardless of route resolution order."""
        existing = await db.spaces.count_documents({"property_id": property_id})
        existing_ps = await db.property_spaces.count_documents({"property_id": property_id})
        if existing > 0 or existing_ps > 0:
            raise HTTPException(400, f"Zaten {max(existing, existing_ps)} space var — silin veya devre dışı bırakın önce.")

        starter = [
            {"kind": "parking",      "name": "Otopark Yeri #1",           "code": "P-01",  "capacity": 5, "rate_per_unit": 3.0,  "unit_minutes": 60,  "open_hour": 0,  "close_hour": 24, "description": "Kapalı otopark, misafir aracı için saatlik."},
            {"kind": "ev_charger",   "name": "Elektrikli Şarj İstasyonu", "code": "EV-01", "capacity": 2, "rate_per_unit": 5.0,  "unit_minutes": 60,  "open_hour": 6,  "close_hour": 23, "description": "Type 2 hızlı şarj, 22 kW."},
            {"kind": "meeting_room", "name": "Executive Toplantı Odası",  "code": "MR-A",  "capacity": 8, "rate_per_unit": 50.0, "unit_minutes": 60,  "open_hour": 8,  "close_hour": 22, "description": "8 kişilik, projeksiyon + Wi-Fi, otel dışı misafir için de kiralık."},
            {"kind": "meeting_room", "name": "Board Room",                "code": "MR-B",  "capacity": 12,"rate_per_unit": 90.0, "unit_minutes": 60,  "open_hour": 8,  "close_hour": 22, "description": "12 kişilik yönetim toplantı odası, catering opsiyonlu."},
            {"kind": "cabana",       "name": "Co-working Desk",           "code": "CW-01", "capacity": 6, "rate_per_unit": 8.0,  "unit_minutes": 60,  "open_hour": 8,  "close_hour": 20, "description": "Ortak alanda yalıtılmış çalışma masası (day pass £45)."},
            {"kind": "locker",       "name": "Bagaj Dolabı",              "code": "LK-01", "capacity": 12,"rate_per_unit": 5.0,  "unit_minutes": None,"open_hour": 0,  "close_hour": 24, "description": "Check-out sonrası gündelik bagaj emaneti."},
        ]
        now = datetime.now(timezone.utc).isoformat()
        docs = []
        for s in starter:
            docs.append({
                "id": str(uuid.uuid4()), "property_id": property_id, "active": True,
                "is_active": True, "currency": "GBP", "created_at": now, "updated_at": now,
                # Both schemas expected by the two spaces backends
                "category": s["kind"], "icon": "boxes",
                "hourly_rate": s["rate_per_unit"], "half_day_rate": 0, "full_day_rate": 0,
                "amenities": [], "photos": [],
                **s,
            })
        # Write to both collections so both list endpoints (whichever route wins)
        # return the same seeded data.
        await db.spaces.insert_many([dict(d) for d in docs])
        await db.property_spaces.insert_many([dict(d) for d in docs])
        for d in docs:
            d.pop("_id", None)
        return {"ok": True, "seeded": len(docs), "spaces": docs}

    @router.get("/spaces/{property_id}/revenue")
    async def spaces_revenue(property_id: str, days: int = 30,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        """Simple KPI aggregation: total revenue, bookings, top space by revenue
        for the last `days` window. Used by the panel hero tiles."""
        f = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = db.space_bookings.find(
            {"property_id": property_id, "status": {"$ne": "cancelled"}, "start": {"$gte": f}},
            {"_id": 0, "space_id": 1, "space_name": 1, "kind": 1, "price": 1, "start": 1},
        )
        rows = await cursor.to_list(2000)
        total_rev = round(sum(r.get("price", 0) for r in rows), 2)
        by_kind: Dict[str, float] = {}
        by_space: Dict[str, Dict] = {}
        for r in rows:
            k = r.get("kind", "other")
            by_kind[k] = round(by_kind.get(k, 0) + r.get("price", 0), 2)
            sid = r.get("space_id", "")
            s = by_space.setdefault(sid, {"name": r.get("space_name", "—"), "revenue": 0, "bookings": 0})
            s["revenue"] = round(s["revenue"] + r.get("price", 0), 2)
            s["bookings"] += 1
        top_space = max(by_space.values(), key=lambda x: x["revenue"], default=None)
        return {
            "window_days": days,
            "total_revenue": total_rev,
            "total_bookings": len(rows),
            "avg_per_booking": round(total_rev / len(rows), 2) if rows else 0,
            "by_kind": [{"kind": k, "revenue": v} for k, v in sorted(by_kind.items(), key=lambda x: -x[1])],
            "top_space": top_space,
        }

    @router.get("/spaces/{property_id}/{space_id}/availability")
    async def availability(property_id: str, space_id: str,
                            from_dt: Optional[str] = None, to_dt: Optional[str] = None,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        space = await db.spaces.find_one({"id": space_id}, {"_id": 0})
        if not space:
            raise HTTPException(404, "Space not found")
        f = from_dt or datetime.now(timezone.utc).isoformat()
        t = to_dt or (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        bookings = await db.space_bookings.find({
            "space_id": space_id,
            "status": {"$ne": "cancelled"},
            "$or": [
                {"start": {"$lt": t}, "end": {"$gt": f}},
            ],
        }, {"_id": 0}).sort("start", 1).to_list(500)
        return {"space": space, "from": f, "to": t, "bookings": bookings, "capacity": space.get("capacity", 1)}

    async def _book_space(data: Dict, created_by: str, source: str = "admin"):
        space_id = data.get("space_id", "")
        start    = (data.get("start") or "").strip()
        end      = (data.get("end") or "").strip()
        guest    = (data.get("guest_name") or "").strip()
        if not space_id or not start or not end or not guest:
            raise HTTPException(400, "space_id, start, end, guest_name required")

        space = await db.spaces.find_one({"id": space_id}, {"_id": 0})
        if not space:
            raise HTTPException(404, "Space not found")

        # Concurrency check (overlap + capacity). Meeting rooms are exclusive:
        # capacity = seat count, not parallel bookings.
        limit = 1 if space.get("kind") == "meeting_room" else space.get("capacity", 1)
        overlap = await db.space_bookings.count_documents({
            "space_id": space_id, "status": {"$ne": "cancelled"},
            "start": {"$lt": end}, "end": {"$gt": start},
        })
        if overlap >= limit:
            raise HTTPException(409, "Space at capacity for this window")

        # Pricing
        try:
            sd = datetime.fromisoformat(start); ed = datetime.fromisoformat(end)
        except Exception:
            raise HTTPException(400, "invalid start/end ISO datetimes")
        unit_min = space.get("unit_minutes")
        if unit_min:  # hourly grain
            units = max(1, round((ed - sd).total_seconds() / 60 / unit_min))
        else:  # daily
            days = max(1, (ed.date() - sd.date()).days)
            units = days
        price = round(units * float(space.get("rate_per_unit") or 0), 2)
        if source == "admin" and "price_override" in data and data["price_override"] is not None:
            price = round(float(data["price_override"]), 2)

        record = {
            "id": str(uuid.uuid4()),
            "property_id": space["property_id"],
            "space_id": space_id,
            "space_name": space["name"],
            "kind": space["kind"],
            "guest_name": guest,
            "guest_email": data.get("guest_email", ""),
            "guest_phone": data.get("guest_phone", ""),
            "booking_id": data.get("booking_id", ""),
            "room_number": data.get("room_number", ""),
            "start": start, "end": end, "units": units,
            "price": price, "currency": space.get("currency", "GBP"),
            "charge_to": data.get("charge_to", "room") if source == "admin" else "direct",
            "notes": data.get("notes", ""),
            "status": "confirmed",
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": created_by,
        }
        await db.space_bookings.insert_one(dict(record))
        record.pop("_id", None)

        if record["charge_to"] == "room" and record["booking_id"] and price > 0:
            await db.folio_items.insert_one({
                "id": str(uuid.uuid4()),
                "booking_id": record["booking_id"],
                "property_id": record["property_id"],
                "type": "charge",
                "category": space["kind"],
                "description": f"{space['name']} · {start[:16]} → {end[:16]}",
                "amount": price,
                "currency": record["currency"],
                "posted_by": created_by,
                "created_at": record["created_at"],
            })
        return record

    @router.post("/space-bookings")
    async def book(data: Dict,
                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        record = await _book_space(data, created_by=current_user.get("name", "Staff"), source="admin")
        return {"ok": True, "booking": record}

    # ==================== PUBLIC HOURLY BOOKING ENGINE (no auth) ====================

    @router.get("/public/spaces/{property_id}")
    async def public_spaces(property_id: str, day: str = ""):
        if not property_id or property_id == "all":
            prop = await db.properties.find_one({}, {"_id": 0, "id": 1, "name": 1})
        else:
            prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "id": 1, "name": 1})
        pid = (prop or {}).get("id", property_id)
        day = day or datetime.now(timezone.utc).date().isoformat()
        spaces = await db.spaces.find(
            {"property_id": pid, "active": {"$ne": False}},
            {"_id": 0}).sort("name", 1).to_list(100)
        day_start, day_end = f"{day}T00:00:00", f"{day}T23:59:59"
        for s in spaces:
            busy = await db.space_bookings.find({
                "space_id": s["id"], "status": {"$ne": "cancelled"},
                "start": {"$lt": day_end}, "end": {"$gt": day_start},
            }, {"_id": 0, "start": 1, "end": 1}).sort("start", 1).to_list(100)
            s["busy"] = busy  # only time windows, no guest data
        return {"property_id": pid, "property_name": (prop or {}).get("name", ""),
                "date": day, "spaces": spaces}

    @router.post("/public/spaces/book")
    async def public_book(data: Dict):
        payload = {k: data.get(k) for k in
                   ("space_id", "start", "end", "guest_name", "guest_email", "guest_phone", "notes")}
        record = await _book_space(payload, created_by="Public Booking Engine", source="public")
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "info",
            "title": "Yeni Alan Rezervasyonu (Online)",
            "message": f"{record['guest_name']} — {record['space_name']} ({record['start'][:16]} → {record['end'][11:16]}, {record['currency']} {record['price']})",
            "category": "spaces", "target_user": "", "target_role": "",
            "link_to": "spaces", "priority": "normal",
            "read": False, "created_by": "Spaces Engine",
            "created_at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "booking": record}

    @router.get("/space-bookings/{property_id}")
    async def list_bookings(property_id: str, days: int = 14, kind: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        from_dt = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        to_dt   = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        q: Dict = {"property_id": property_id, "start": {"$gte": from_dt, "$lte": to_dt}}
        if kind:
            q["kind"] = kind
        rows = await db.space_bookings.find(q, {"_id": 0}).sort("start", 1).to_list(500)
        return rows

    @router.post("/space-bookings/{booking_id}/cancel")
    async def cancel(booking_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        await db.space_bookings.update_one({"id": booking_id}, {"$set": {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "cancelled_by": current_user.get("name", "Staff"),
        }})
        return {"ok": True}

    @router.get("/spaces/{property_id}/upsell-suggestions")
    async def upsell_suggestions(property_id: str,
                                   booking_id: Optional[str] = None,
                                   guest_count: int = 2,
                                   nights: int = 1,
                                   current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        """Smart per-booking upsell recommendations. Reads the booking's own
        signals (guest count, nights, special_requests, tags) + property
        space inventory, returns 2-4 ranked add-ons the operator should offer
        at check-in / pre-arrival email / mobile portal.

        Rationale surfaces in the response so the receptionist can pitch it
        confidently: e.g. 'Business traveler → 4h meeting room slot'.
        """
        signals: List[str] = []
        booking: Dict[str, Any] = {}
        if booking_id:
            booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0}) or {}
            if booking:
                guest_count = int(booking.get("adults", guest_count)) + int(booking.get("children", 0))
                try:
                    from datetime import datetime as _dt
                    ci = _dt.fromisoformat(booking["check_in"].split("T")[0])
                    co = _dt.fromisoformat(booking["check_out"].split("T")[0])
                    nights = max(1, (co - ci).days)
                except Exception:
                    pass
                sr = (booking.get("special_requests") or "").lower()
                if any(w in sr for w in ["car", "araç", "araba", "otopark", "parking"]):
                    signals.append("has_car")
                if any(w in sr for w in ["ev ", "elektrikli", "electric vehicle", "tesla"]):
                    signals.append("has_ev")
                if any(w in sr for w in ["business", "iş", "meeting", "toplantı", "conference"]):
                    signals.append("business_traveler")
                if any(w in sr for w in ["late", "geç", "après", "storage", "bagaj"]):
                    signals.append("late_departure")
                # Guest profile tags
                gid = booking.get("guest_id")
                if gid:
                    gp = await db.guest_profiles.find_one({"id": gid}, {"_id": 0, "tags": 1}) or {}
                    tags = [t.lower() for t in (gp.get("tags") or [])]
                    if "business" in tags or "corporate" in tags:
                        signals.append("business_traveler")
                    if "vip" in tags:
                        signals.append("vip")

        # Baseline signals from stay properties
        if nights >= 3:
            signals.append("long_stay")
        if guest_count >= 4:
            signals.append("group")

        # Fetch active spaces
        spaces_a = await db.spaces.find({"property_id": property_id, "active": {"$ne": False}}, {"_id": 0}).to_list(50)
        spaces_b = await db.property_spaces.find({"property_id": property_id, "is_active": {"$ne": False}}, {"_id": 0}).to_list(50)
        # Dedupe by id
        seen = set()
        spaces: List[Dict] = []
        for s in spaces_a + spaces_b:
            sid = s.get("id")
            if sid and sid not in seen:
                seen.add(sid)
                spaces.append(s)

        def _rate(s: Dict) -> float:
            return float(s.get("rate_per_unit") or s.get("hourly_rate") or 0)

        RULES = [
            # (predicate, kind_prefer, reason, cta_template)
            (lambda sig: "has_ev" in sig,             "ev_charger",   "🔌 Elektrikli aracınız için oda gecesi başına şarj slotu",     "1 gece EV şarj için £{rate} slot ekleyin"),
            (lambda sig: "has_car" in sig,             "parking",      "🚗 Rezervasyonunuzda araç bulunduğu belirtilmiş",              "Kapalı otopark rezerve et · £{rate}/saat"),
            (lambda sig: "business_traveler" in sig,   "meeting_room", "💼 İş seyahatinde toplantı odası — misafir odasında olmayan ortam", "Öğleden sonra 4 saat toplantı odası · £{total} (4h × £{rate})"),
            (lambda sig: "business_traveler" in sig,   "cabana",       "🧑‍💻 Ekstra çalışma masası — coworking alanı",                "Half-day coworking desk · £{half}"),
            (lambda sig: "group" in sig,                "meeting_room", "👥 4+ misafir — grup için toplantı/rezerve alan",             "Grup için toplantı odası · £{rate}/h"),
            (lambda sig: "long_stay" in sig,            "locker",       "🧳 Uzun konaklama — check-out sonrası bagaj emaneti",          "Check-out sonrası bagaj dolabı · günlük £{rate}"),
            (lambda sig: True,                          "parking",      "🅿️ Genel öneri — misafir aracı sıkça sorulur",                 "Otopark rezervasyonu · £{rate}/saat"),
        ]

        suggestions: List[Dict] = []
        used_ids = set()
        for pred, prefer_kind, reason, cta_tpl in RULES:
            if not pred(signals):
                continue
            # find first matching active space of that kind
            match = next((s for s in spaces if s.get("kind") == prefer_kind or s.get("category") == prefer_kind), None)
            if not match or match["id"] in used_ids:
                continue
            rate = _rate(match)
            half = round(rate * 4, 2) if rate else 0
            total4h = round(rate * 4, 2) if rate else 0
            suggestions.append({
                "space_id": match["id"],
                "space_name": match.get("name"),
                "kind": match.get("kind") or match.get("category"),
                "rate": rate,
                "reason": reason,
                "cta": cta_tpl.format(rate=rate, half=half, total=total4h),
                "matched_signal": next((s for s in signals if s in reason.lower() or s.replace("_", " ") in reason.lower()), signals[0] if signals else "generic"),
            })
            used_ids.add(match["id"])
            if len(suggestions) >= 4:
                break

        return {
            "booking_id": booking_id,
            "signals": signals,
            "guest_count": guest_count,
            "nights": nights,
            "suggestions": suggestions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @router.post("/public/spaces/pay/{sb_id}")
    async def public_space_pay(sb_id: str, request: Request):
        """Public: prepay a space booking via Stripe Checkout."""
        import os
        from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
        sb = await db.space_bookings.find_one({"id": sb_id}, {"_id": 0})
        if not sb:
            raise HTTPException(404, "Rezervasyon bulunamadı")
        if sb.get("payment_status") == "paid":
            raise HTTPException(409, "Zaten ödendi")
        if sb.get("status") == "cancelled":
            raise HTTPException(410, "Rezervasyon iptal edilmiş")
        amount = float(sb.get("price") or 0)
        if amount <= 0:
            raise HTTPException(400, "Ödenecek tutar yok")

        stripe_api_key = os.environ.get("STRIPE_API_KEY", "")
        host_url = str(request.base_url).rstrip("/")
        base_url = os.environ.get("BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", host_url))
        stripe_checkout = StripeCheckout(api_key=stripe_api_key,
                                         webhook_url=f"{host_url}/api/webhook/stripe")
        checkout_req = CheckoutSessionRequest(
            amount=amount,
            currency=(sb.get("currency") or "GBP").lower(),
            success_url=f"{base_url}/book-space?payment=success&sb={sb_id}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/book-space?payment=cancelled",
            metadata={"type": "space_booking", "space_booking_id": sb_id,
                      "space_name": sb.get("space_name", ""),
                      "guest_name": sb.get("guest_name", ""),
                      "property_id": sb.get("property_id", "")})
        session = await stripe_checkout.create_checkout_session(checkout_req)
        await db.payment_transactions.insert_one({
            "id": str(uuid.uuid4()), "session_id": session.session_id,
            "type": "space_booking", "reference_id": sb_id,
            "property_id": sb.get("property_id", ""),
            "amount": amount, "currency": sb.get("currency", "GBP"),
            "guest_name": sb.get("guest_name", ""),
            "payment_method": "stripe", "payment_status": "initiated",
            "created_at": datetime.now(timezone.utc).isoformat()})
        await db.space_bookings.update_one({"id": sb_id}, {"$set": {"payment_status": "initiated"}})
        return {"url": session.url, "session_id": session.session_id}

    @router.get("/public/spaces/pay-status/{sb_id}")
    async def public_space_pay_status(sb_id: str, session_id: str = "", request: Request = None):
        import os
        from emergentintegrations.payments.stripe.checkout import StripeCheckout
        sb = await db.space_bookings.find_one({"id": sb_id}, {"_id": 0})
        if not sb:
            raise HTTPException(404, "Rezervasyon bulunamadı")
        if sb.get("payment_status") == "paid":
            return {"status": "paid", "booking": sb}
        if session_id:
            try:
                host_url = str(request.base_url).rstrip("/") if request else ""
                sc = StripeCheckout(api_key=os.environ.get("STRIPE_API_KEY", ""),
                                    webhook_url=f"{host_url}/api/webhook/stripe")
                st = await sc.get_checkout_status(session_id)
                if st.payment_status == "paid":
                    now = datetime.now(timezone.utc).isoformat()
                    await db.space_bookings.update_one({"id": sb_id}, {"$set": {
                        "payment_status": "paid", "paid_at": now}})
                    await db.payment_transactions.update_one(
                        {"session_id": session_id},
                        {"$set": {"payment_status": "paid", "paid_at": now}})
                    sb["payment_status"] = "paid"
                    return {"status": "paid", "booking": sb}
            except Exception as e:
                logger.warning(f"space pay status check failed: {e}")
        return {"status": sb.get("payment_status", "unpaid"), "booking": sb}

    return router
