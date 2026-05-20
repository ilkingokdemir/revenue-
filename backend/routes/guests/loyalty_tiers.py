"""
Loyalty Tiers — Silver / Gold / Platinum tiers with auto-upgrade based on stays/spend.

Endpoints:
  GET   /api/loyalty-tiers/config              — get tier config (admin)
  PUT   /api/loyalty-tiers/config              — update tier thresholds & benefits
  GET   /api/loyalty-tiers/member/{email}      — get member tier + benefits
  GET   /api/loyalty-tiers/members             — list all members with tiers
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends


DEFAULT_TIERS = [
    {"name": "Silver",   "min_stays": 1,  "min_spend": 0,    "benefits": ["Late checkout (12 PM)"]},
    {"name": "Gold",     "min_stays": 5,  "min_spend": 2500, "benefits": ["Late checkout (2 PM)", "Welcome amenity", "10% F&B discount"]},
    {"name": "Platinum", "min_stays": 15, "min_spend": 7500, "benefits": ["Late checkout (4 PM)", "Welcome amenity", "20% F&B discount", "Room upgrade subject to availability", "Suite upgrade certificate yearly"]},
]


async def _compute_member_tier(db, guest_email: str, tier_cfg: list) -> dict:
    bookings = await db.bookings.find(
        {"guest_email": guest_email,
         "status": {"$in": ["confirmed", "checked_in", "checked_out", "completed"]}},
        {"_id": 0, "total_price": 1}
    ).to_list(500)
    total_stays = len(bookings)
    total_spend = round(sum(float(b.get("total_price", 0)) for b in bookings), 2)
    # Find highest tier qualifying
    qualified = None
    for t in sorted(tier_cfg, key=lambda x: x.get("min_stays", 0)):
        if total_stays >= t.get("min_stays", 0) and total_spend >= t.get("min_spend", 0):
            qualified = t
    return {
        "guest_email": guest_email,
        "tier": qualified["name"] if qualified else None,
        "benefits": qualified["benefits"] if qualified else [],
        "total_stays": total_stays,
        "total_spend": total_spend,
    }


def create_loyalty_tiers_router(db, require_roles):
    router = APIRouter(prefix="/loyalty-tiers")

    @router.get("/config")
    async def get_config(_: dict = Depends(require_roles("admin", "manager"))):
        cfg = await db.loyalty_tier_config.find_one({"id": "global"}, {"_id": 0})
        if not cfg:
            cfg = {"id": "global", "tiers": DEFAULT_TIERS,
                   "updated_at": datetime.now(timezone.utc).isoformat()}
            await db.loyalty_tier_config.insert_one(dict(cfg))
        return cfg

    @router.put("/config")
    async def update_config(body: dict,
                            current_user: dict = Depends(require_roles("admin"))):
        body["id"] = "global"
        body["updated_at"] = datetime.now(timezone.utc).isoformat()
        body["updated_by"] = current_user.get("name", "")
        await db.loyalty_tier_config.update_one({"id": "global"}, {"$set": body}, upsert=True)
        return {"updated": True}

    @router.get("/member/{guest_email}")
    async def get_member(guest_email: str,
                         _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        cfg = await db.loyalty_tier_config.find_one({"id": "global"}, {"_id": 0})
        tiers = (cfg or {}).get("tiers", DEFAULT_TIERS)
        return await _compute_member_tier(db, guest_email, tiers)

    @router.get("/members")
    async def list_members(_: dict = Depends(require_roles("admin", "manager"))):
        cfg = await db.loyalty_tier_config.find_one({"id": "global"}, {"_id": 0})
        tiers = (cfg or {}).get("tiers", DEFAULT_TIERS)
        emails = await db.bookings.distinct(
            "guest_email",
            {"status": {"$in": ["confirmed", "checked_in", "checked_out", "completed"]}}
        )
        members: list = []
        by_tier: dict = {"Silver": 0, "Gold": 0, "Platinum": 0, "None": 0}
        for em in [e for e in emails if e][:500]:
            m = await _compute_member_tier(db, em, tiers)
            members.append(m)
            t = m["tier"] or "None"
            by_tier[t] = by_tier.get(t, 0) + 1
        # Sort by spend desc
        members.sort(key=lambda x: x["total_spend"], reverse=True)
        return {"count": len(members), "by_tier": by_tier, "members": members[:200]}

    return router
