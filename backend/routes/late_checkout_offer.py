"""
Late-Checkout Offer Engine (P1)
-------------------------------
On checkout day, surface a paid late-checkout offer to the guest and the
front desk. Pricing is dynamic: % of nightly rate × hours requested, but
gated on whether the room is sold for the next night (if next-night booked,
no offer is generated for that room).

Endpoints
---------
POST /late-checkout/config              Upsert pricing config per property
GET  /late-checkout/{property_id}/config
POST /late-checkout/scan                Cron — generate offers for today's checkouts
GET  /late-checkout/{property_id}/offers
POST /late-checkout/offer/{offer_id}/accept   Guest accepts (folio post + booking checkout shift)
POST /late-checkout/offer/{offer_id}/decline
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> date:
    return datetime.now(timezone.utc).date()


def create_late_checkout_offer_router(db, require_roles):
    router = APIRouter()

    @router.post("/late-checkout/config")
    async def upsert_cfg(data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        if not property_id:
            raise HTTPException(400, "property_id required")
        record = {
            "property_id": property_id,
            "enabled": bool(data.get("enabled", True)),
            "pct_per_hour": float(data.get("pct_per_hour") or 8.0),     # 8% of nightly rate per extra hour
            "min_charge": float(data.get("min_charge") or 10.0),
            "max_hours": int(data.get("max_hours") or 5),
            "block_if_next_night_booked": bool(data.get("block_if_next_night_booked", True)),
            "auto_offer_pct_off_marketing": float(data.get("auto_offer_pct_off_marketing") or 0),  # for soft-sell email
            "updated_at": _now(),
            "updated_by": current_user.get("name", "Staff"),
        }
        await db.late_checkout_config.update_one({"property_id": property_id}, {"$set": record}, upsert=True)
        return {"ok": True, "config": record}

    @router.get("/late-checkout/{property_id}/config")
    async def get_cfg(property_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        return await db.late_checkout_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "property_id": property_id, "pct_per_hour": 8.0, "min_charge": 10.0,
            "max_hours": 5, "block_if_next_night_booked": True, "enabled": True,
        }

    @router.post("/late-checkout/scan")
    async def scan(data: Optional[Dict] = None,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        body = data or {}
        property_id = body.get("property_id", "")
        if not property_id:
            raise HTTPException(400, "property_id required")
        cfg = await db.late_checkout_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "pct_per_hour": 8.0, "min_charge": 10.0, "max_hours": 5,
            "block_if_next_night_booked": True, "enabled": True,
        }
        if not cfg.get("enabled", True):
            return {"ok": True, "skipped": "disabled"}

        today = _today().isoformat()
        # Bookings checking out today
        bookings = await db.bookings.find(
            {"property_id": property_id, "check_out": {"$regex": f"^{today}"}, "status": "checked_in"},
            {"_id": 0},
        ).to_list(500)
        generated = 0
        skipped = 0
        for b in bookings:
            existing = await db.late_checkout_offers.find_one(
                {"booking_id": b["id"], "for_date": today}, {"_id": 0}
            )
            if existing:
                continue
            # Block if next-night booking exists for same room number
            if cfg.get("block_if_next_night_booked", True):
                conflict = await db.bookings.find_one({
                    "property_id": property_id,
                    "room_number": b.get("room_number", ""),
                    "check_in": {"$regex": f"^{today}"},
                    "status": {"$nin": ["cancelled", "no_show"]},
                }, {"_id": 0})
                if conflict:
                    skipped += 1
                    continue
            nightly = float(b.get("total_price") or 0) / max(int(b.get("nights") or 1), 1)
            tiers: List[Dict] = []
            for hrs in [1, 2, 3, cfg.get("max_hours", 5)]:
                if hrs > cfg.get("max_hours", 5):
                    continue
                price = max(round(nightly * cfg.get("pct_per_hour", 8.0) / 100 * hrs, 2),
                              cfg.get("min_charge", 10.0))
                tiers.append({"hours": hrs, "price": price, "label": f"+{hrs}h until {12 + hrs}:00"})
            offer = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "booking_id": b["id"],
                "guest_name": b.get("guest_name", ""),
                "guest_email": b.get("guest_email", ""),
                "room_number": b.get("room_number", ""),
                "for_date": today,
                "currency": b.get("currency", "GBP"),
                "tiers": tiers,
                "status": "open",   # open | accepted | declined | expired
                "created_at": _now(),
            }
            await db.late_checkout_offers.insert_one(dict(offer))
            generated += 1
        return {"ok": True, "checkouts_today": len(bookings), "generated": generated, "skipped_blocked": skipped}

    @router.get("/late-checkout/{property_id}/offers")
    async def list_offers(property_id: str, days: int = 7, status: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: Dict = {"property_id": property_id, "created_at": {"$gte": since}}
        if status:
            q["status"] = status
        rows = await db.late_checkout_offers.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        accepted = sum(1 for r in rows if r["status"] == "accepted")
        revenue = round(sum(float(r.get("accepted_price") or 0) for r in rows if r["status"] == "accepted"), 2)
        return {"items": rows, "count": len(rows), "accepted": accepted, "revenue": revenue,
                 "conversion_pct": round(accepted * 100 / max(len(rows), 1), 1)}

    @router.post("/late-checkout/offer/{offer_id}/accept")
    async def accept(offer_id: str, data: Dict,
                      current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        offer = await db.late_checkout_offers.find_one({"id": offer_id}, {"_id": 0})
        if not offer:
            raise HTTPException(404, "Offer not found")
        if offer["status"] != "open":
            raise HTTPException(400, f"Offer is {offer['status']}")
        hours = int(data.get("hours") or 1)
        tier = next((t for t in offer["tiers"] if t["hours"] == hours), None)
        if not tier:
            raise HTTPException(400, f"Hours {hours} not in available tiers")
        # Post charge to folio
        await db.folio_charges.insert_one({
            "id": str(uuid.uuid4()),
            "booking_id": offer["booking_id"],
            "category": "late_checkout",
            "description": f"Late checkout {tier['label']}",
            "amount": tier["price"],
            "currency": offer.get("currency", "GBP"),
            "posted_at": _now(),
            "posted_by": current_user.get("name", "Staff"),
        })
        await db.late_checkout_offers.update_one(
            {"id": offer_id},
            {"$set": {"status": "accepted", "accepted_hours": hours,
                       "accepted_price": tier["price"], "accepted_at": _now(),
                       "accepted_by": current_user.get("name", "Staff")}},
        )
        return {"ok": True, "hours": hours, "charged": tier["price"]}

    @router.post("/late-checkout/offer/{offer_id}/decline")
    async def decline(offer_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        result = await db.late_checkout_offers.update_one(
            {"id": offer_id, "status": "open"},
            {"$set": {"status": "declined", "declined_at": _now()}},
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Open offer not found")
        return {"ok": True}

    return router
