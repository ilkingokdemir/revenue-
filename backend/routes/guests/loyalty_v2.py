"""
Loyalty v2 — Tier Benefits Engine + Referral Program + Dynamic Packaging.

Tier Benefits: Per-tier automatic perks applied at booking time
(early check-in, late checkout, room-type upgrade, F&B % off, free breakfast).
Marriott/IHG/Hilton reference model.

Referral: Guest A gets a unique code → shares with friend B → B books with code →
B gets configured discount, A gets configured points (on B's first stay completed).

Dynamic Packaging: Bundle of (room + spa + F&B + transport) sold at a single
package price that shows "you save £X vs a-la-carte". Mews-like.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel
import uuid
import logging

logger = logging.getLogger(__name__)


# ---------- Models ----------

class TierBenefit(BaseModel):
    property_id: str
    tier: str  # bronze | silver | gold | platinum
    early_check_in: bool = False
    late_check_out: bool = False
    room_upgrade: bool = False
    free_breakfast: bool = False
    fnb_discount_pct: float = 0
    spa_discount_pct: float = 0
    welcome_amenity: bool = False
    birthday_gift: bool = False


class ReferralCreate(BaseModel):
    property_id: str
    referrer_guest_id: str
    benefit_for_referee_pct: float = 10
    benefit_for_referrer_points: int = 500
    expires_days: int = 365


class ReferralClaim(BaseModel):
    code: str
    booking_id: str
    referee_guest_id: Optional[str] = None


class Package(BaseModel):
    id: Optional[str] = None
    property_id: str
    name: str
    description: Optional[str] = ""
    active: bool = True
    components: List[Dict]  # [{type: 'room'|'fnb'|'spa'|'transport', name, alacarte_price, qty}]
    package_price: float
    currency: str = "GBP"


DEFAULT_TIER_BENEFITS = {
    "bronze":   {"early_check_in": False, "late_check_out": False, "room_upgrade": False,
                 "free_breakfast": False, "fnb_discount_pct": 0,  "spa_discount_pct": 0,
                 "welcome_amenity": False, "birthday_gift": True},
    "silver":   {"early_check_in": True,  "late_check_out": True,  "room_upgrade": False,
                 "free_breakfast": False, "fnb_discount_pct": 5,  "spa_discount_pct": 5,
                 "welcome_amenity": True,  "birthday_gift": True},
    "gold":     {"early_check_in": True,  "late_check_out": True,  "room_upgrade": True,
                 "free_breakfast": True,  "fnb_discount_pct": 10, "spa_discount_pct": 10,
                 "welcome_amenity": True,  "birthday_gift": True},
    "platinum": {"early_check_in": True,  "late_check_out": True,  "room_upgrade": True,
                 "free_breakfast": True,  "fnb_discount_pct": 20, "spa_discount_pct": 20,
                 "welcome_amenity": True,  "birthday_gift": True},
}


def create_loyalty_v2_router(db, require_roles):
    router = APIRouter()

    # ==================== TIER BENEFITS ====================

    @router.get("/loyalty-v2/benefits/{property_id}")
    async def list_benefits(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.tier_benefits.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(10)
        existing = {r["tier"] for r in rows}
        # Seed defaults
        seed = []
        for tier, cfg in DEFAULT_TIER_BENEFITS.items():
            if tier not in existing:
                seed.append({
                    "id": str(uuid.uuid4()),
                    "property_id": property_id,
                    "tier": tier,
                    **cfg,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
        if seed:
            await db.tier_benefits.insert_many(seed)
            rows.extend([{k: v for k, v in r.items() if k != "_id"} for r in seed])
        # Order: bronze → platinum
        order = {"bronze": 0, "silver": 1, "gold": 2, "platinum": 3}
        rows.sort(key=lambda r: order.get(r["tier"], 99))
        return {"benefits": rows}

    @router.put("/loyalty-v2/benefits/{property_id}/{tier}")
    async def update_benefit(property_id: str, tier: str, b: TierBenefit,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        update = b.dict(exclude_unset=True, exclude={"property_id", "tier"})
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.tier_benefits.update_one(
            {"property_id": property_id, "tier": tier},
            {"$set": update, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": update["updated_at"]}},
            upsert=True,
        )
        return {"updated": True}

    @router.post("/loyalty-v2/benefits/apply/{booking_id}")
    async def apply_benefits_to_booking(booking_id: str,
                                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Auto-apply tier benefits to a booking (usually called on check-in)."""
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        g = await db.guest_profiles.find_one({"id": b.get("guest_id")}, {"_id": 0}) or {}
        tier = (g.get("loyalty_tier") or "bronze").lower()
        benefit = await db.tier_benefits.find_one(
            {"property_id": b.get("property_id"), "tier": tier}, {"_id": 0}
        ) or DEFAULT_TIER_BENEFITS.get(tier, {})

        applied = []
        now = datetime.now(timezone.utc).isoformat()

        # Early check-in: 13:00 instead of 15:00
        if benefit.get("early_check_in"):
            applied.append({"perk": "Early check-in 13:00"})
        # Late check-out: 14:00 instead of 11:00
        if benefit.get("late_check_out"):
            applied.append({"perk": "Late check-out 14:00"})
        # Room upgrade: find next-tier available room, swap
        if benefit.get("room_upgrade"):
            current_rt = b.get("room_type_id")
            all_rts = await db.room_types.find(
                {"property_id": b.get("property_id")}, {"_id": 0}
            ).sort("base_price", 1).to_list(50)
            upgrade = None
            for i, rt in enumerate(all_rts):
                if rt.get("id") == current_rt and i + 1 < len(all_rts):
                    upgrade = all_rts[i + 1]
                    break
            if upgrade:
                applied.append({"perk": f"Room upgrade → {upgrade.get('name')}", "to_room_type": upgrade.get("id")})
        # Free breakfast
        if benefit.get("free_breakfast"):
            applied.append({"perk": "Complimentary breakfast"})
        # Welcome amenity
        if benefit.get("welcome_amenity"):
            applied.append({"perk": "Welcome amenity in room"})
        # F&B discount
        if benefit.get("fnb_discount_pct", 0) > 0:
            applied.append({"perk": f"F&B -{benefit['fnb_discount_pct']}%", "fnb_discount_pct": benefit["fnb_discount_pct"]})
        # Spa discount
        if benefit.get("spa_discount_pct", 0) > 0:
            applied.append({"perk": f"Spa -{benefit['spa_discount_pct']}%", "spa_discount_pct": benefit["spa_discount_pct"]})

        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"tier_benefits_applied": applied, "tier_benefits_at": now, "tier": tier}}
        )
        return {"booking_id": booking_id, "tier": tier, "applied": applied}

    # ==================== REFERRAL PROGRAM ====================

    @router.post("/loyalty-v2/referrals")
    async def create_referral(req: ReferralCreate,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        guest = await db.guest_profiles.find_one({"id": req.referrer_guest_id}, {"_id": 0})
        if not guest:
            raise HTTPException(404, "Referrer guest not found")

        code = f"REF{req.referrer_guest_id[:4].upper()}{uuid.uuid4().hex[:4].upper()}"
        now = datetime.now(timezone.utc)
        doc = {
            "id": str(uuid.uuid4()),
            "code": code,
            "property_id": req.property_id,
            "referrer_guest_id": req.referrer_guest_id,
            "referrer_name": f"{guest.get('first_name','')} {guest.get('last_name','')}".strip(),
            "benefit_for_referee_pct": req.benefit_for_referee_pct,
            "benefit_for_referrer_points": req.benefit_for_referrer_points,
            "times_used": 0,
            "total_earned_points": 0,
            "total_bookings_generated": 0,
            "created_at": now.isoformat(),
            "created_by": current_user.get("email"),
            "expires_at": (now.replace(microsecond=0) + timedelta(days=req.expires_days)).isoformat(),
            "active": True,
        }
        await db.referrals.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}

    @router.get("/loyalty-v2/referrals/{property_id}")
    async def list_referrals(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.referrals.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("created_at", -1).limit(200).to_list(200)
        total_points = sum(r.get("total_earned_points", 0) for r in rows)
        total_bookings = sum(r.get("total_bookings_generated", 0) for r in rows)
        return {
            "rows": rows,
            "count": len(rows),
            "total_earned_points": total_points,
            "total_bookings_generated": total_bookings,
        }

    @router.post("/loyalty-v2/referrals/claim")
    async def claim_referral(req: ReferralClaim,
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        ref = await db.referrals.find_one({"code": req.code, "active": True}, {"_id": 0})
        if not ref:
            raise HTTPException(404, "Invalid or expired referral code")
        booking = await db.bookings.find_one({"id": req.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        now = datetime.now(timezone.utc).isoformat()
        discount_pct = ref.get("benefit_for_referee_pct", 10)

        # Apply discount to booking
        original_price = float(booking.get("total_price") or 0)
        discount_amount = round(original_price * discount_pct / 100, 2)
        new_price = round(original_price - discount_amount, 2)

        await db.bookings.update_one(
            {"id": req.booking_id},
            {"$set": {
                "referral_code": req.code,
                "referral_discount_pct": discount_pct,
                "referral_discount_amount": discount_amount,
                "referral_applied_at": now,
                "original_total_price": original_price,
                "total_price": new_price,
            }}
        )

        # Track on referral
        await db.referrals.update_one(
            {"code": req.code},
            {"$inc": {
                "times_used": 1,
                "total_bookings_generated": 1,
                "total_earned_points": ref.get("benefit_for_referrer_points", 500),
            }}
        )

        # Add points to referrer guest
        await db.guest_profiles.update_one(
            {"id": ref.get("referrer_guest_id")},
            {"$inc": {"loyalty_points": ref.get("benefit_for_referrer_points", 500)}}
        )

        return {
            "code": req.code,
            "referee_discount_pct": discount_pct,
            "referee_discount_amount": discount_amount,
            "new_booking_total": new_price,
            "referrer_points_awarded": ref.get("benefit_for_referrer_points", 500),
        }

    # ==================== DYNAMIC PACKAGING ====================

    @router.get("/loyalty-v2/packages/{property_id}")
    async def list_packages(property_id: str, active_only: bool = False,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q = {"property_id": property_id}
        if active_only:
            q["active"] = True
        rows = await db.packages.find(q, {"_id": 0}).to_list(200)
        # Enrich with savings
        for p in rows:
            alacarte = sum(float(c.get("alacarte_price", 0)) * int(c.get("qty", 1))
                           for c in (p.get("components") or []))
            savings = round(alacarte - float(p.get("package_price", 0)), 2)
            p["alacarte_total"] = round(alacarte, 2)
            p["savings"] = savings
            p["savings_pct"] = round((savings / alacarte * 100) if alacarte else 0, 1)
        return {"packages": rows, "count": len(rows)}

    @router.post("/loyalty-v2/packages")
    async def create_package(p: Package,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = p.dict()
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        doc["created_by"] = current_user.get("email")
        await db.packages.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}

    @router.put("/loyalty-v2/packages/{package_id}")
    async def update_package(package_id: str, p: Package,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        update = p.dict(exclude_unset=True, exclude={"id"})
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.packages.update_one({"id": package_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Package not found")
        return {"updated": True}

    @router.delete("/loyalty-v2/packages/{package_id}")
    async def delete_package(package_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.packages.delete_one({"id": package_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Package not found")
        return {"deleted": True}

    @router.post("/loyalty-v2/packages/{property_id}/seed-defaults")
    async def seed_default_packages(property_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        existing = await db.packages.count_documents({"property_id": property_id})
        if existing > 0:
            return {"seeded": 0, "note": f"{existing} packages already exist"}
        now = datetime.now(timezone.utc).isoformat()
        defaults = [
            {
                "id": str(uuid.uuid4()), "property_id": property_id,
                "name": "Romantik Kaçamak",
                "description": "Çift kişilik süit + spa + akşam yemeği + transfer",
                "active": True,
                "components": [
                    {"type": "room", "name": "Deluxe Double (2 gece)", "alacarte_price": 180, "qty": 2},
                    {"type": "spa", "name": "Couples Massage 60min", "alacarte_price": 120, "qty": 1},
                    {"type": "fnb", "name": "Candlelight Dinner (2p)", "alacarte_price": 90, "qty": 1},
                    {"type": "transport", "name": "Airport Transfer (RT)", "alacarte_price": 40, "qty": 1},
                ],
                "package_price": 499,
                "currency": "GBP",
                "created_at": now, "created_by": current_user.get("email"),
            },
            {
                "id": str(uuid.uuid4()), "property_id": property_id,
                "name": "İş Gezisi Kompakt",
                "description": "Tek gece + kahvaltı + akşam yemeği + airport transfer",
                "active": True,
                "components": [
                    {"type": "room", "name": "Standard Single (1 gece)", "alacarte_price": 120, "qty": 1},
                    {"type": "fnb", "name": "Full Breakfast", "alacarte_price": 18, "qty": 1},
                    {"type": "fnb", "name": "Business Dinner", "alacarte_price": 35, "qty": 1},
                    {"type": "transport", "name": "One-way Transfer", "alacarte_price": 20, "qty": 1},
                ],
                "package_price": 169,
                "currency": "GBP",
                "created_at": now, "created_by": current_user.get("email"),
            },
            {
                "id": str(uuid.uuid4()), "property_id": property_id,
                "name": "Aile Hafta Sonu",
                "description": "2 oda + aile yemekleri + aquapark",
                "active": True,
                "components": [
                    {"type": "room", "name": "Family Room (2 gece)", "alacarte_price": 200, "qty": 2},
                    {"type": "fnb", "name": "Family Breakfast (4p)", "alacarte_price": 50, "qty": 2},
                    {"type": "spa", "name": "Aquapark Day Pass (4p)", "alacarte_price": 80, "qty": 1},
                ],
                "package_price": 539,
                "currency": "GBP",
                "created_at": now, "created_by": current_user.get("email"),
            },
        ]
        await db.packages.insert_many(defaults)
        return {"seeded": len(defaults)}

    return router
