"""
Guest Loyalty Program — Points, Tiers, Rewards, Auto-upgrade
Duty Manager Logbook — Shift handover, incidents, VIP tracking
Occupancy Forecasting — 30/60/90-day forecast, pickup pace
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import uuid
import logging

logger = logging.getLogger(__name__)

TIER_THRESHOLDS = {"standard": 0, "silver": 3, "gold": 7, "platinum": 15}
TIER_POINTS_MULTIPLIER = {"standard": 1.0, "silver": 1.25, "gold": 1.5, "platinum": 2.0}
TIER_BENEFITS = {
    "standard": ["Earn 10 points per £1 spent"],
    "silver": ["1.25x points", "Early check-in (subject to availability)", "Welcome drink"],
    "gold": ["1.5x points", "Room upgrade (subject to availability)", "Late checkout 2PM", "Welcome fruit basket"],
    "platinum": ["2x points", "Guaranteed upgrade", "Late checkout 4PM", "Airport transfer", "Spa credit £50"],
}


def create_loyalty_router(db, require_roles):
    router = APIRouter()

    # ==================== LOYALTY PROGRAM ====================

    @router.get("/loyalty/member/{guest_id}")
    async def get_loyalty_member(guest_id: str):
        """Get loyalty status for a guest"""
        member = await db.loyalty_members.find_one({"guest_id": guest_id}, {"_id": 0})
        if not member:
            guest = await db.guest_profiles.find_one({"id": guest_id}, {"_id": 0})
            if not guest:
                raise HTTPException(404, "Guest not found")
            member = {
                "id": str(uuid.uuid4()), "guest_id": guest_id,
                "guest_name": guest.get("name", ""), "guest_email": guest.get("email", ""),
                "tier": "standard", "points": 0, "lifetime_points": 0,
                "total_stays": guest.get("total_stays", 0), "total_spend": guest.get("total_spend", 0),
                "rewards_redeemed": [], "points_history": [],
                "member_since": datetime.now(timezone.utc).isoformat(),
            }
            await db.loyalty_members.insert_one(member)
            member.pop("_id", None)
        member["tier_benefits"] = TIER_BENEFITS.get(member.get("tier", "standard"), [])
        member["next_tier"] = _get_next_tier(member.get("tier", "standard"))
        member["stays_to_next_tier"] = _stays_to_next_tier(member)
        return member

    @router.post("/loyalty/earn-points")
    async def earn_points(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Award points to a guest"""
        guest_id = data.get("guest_id")
        amount = float(data.get("amount", 0))
        reason = data.get("reason", "stay")
        member = await db.loyalty_members.find_one({"guest_id": guest_id}, {"_id": 0})
        if not member:
            raise HTTPException(404, "Loyalty member not found")
        multiplier = TIER_POINTS_MULTIPLIER.get(member.get("tier", "standard"), 1.0)
        points = int(amount * 10 * multiplier)
        entry = {"points": points, "amount": amount, "reason": reason, "multiplier": multiplier, "date": datetime.now(timezone.utc).isoformat()}
        new_total = member.get("points", 0) + points
        new_lifetime = member.get("lifetime_points", 0) + points
        new_stays = member.get("total_stays", 0) + (1 if reason == "stay" else 0)
        new_spend = member.get("total_spend", 0) + amount
        new_tier = _calculate_tier(new_stays)
        tier_upgraded = new_tier != member.get("tier", "standard")
        await db.loyalty_members.update_one({"guest_id": guest_id}, {"$set": {
            "points": new_total, "lifetime_points": new_lifetime,
            "total_stays": new_stays, "total_spend": new_spend, "tier": new_tier,
        }, "$push": {"points_history": entry}})
        return {"points_earned": points, "new_balance": new_total, "tier": new_tier, "tier_upgraded": tier_upgraded}

    @router.post("/loyalty/redeem")
    async def redeem_points(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Redeem loyalty points for a reward"""
        guest_id = data.get("guest_id")
        reward_id = data.get("reward_id")
        member = await db.loyalty_members.find_one({"guest_id": guest_id}, {"_id": 0})
        if not member:
            raise HTTPException(404, "Member not found")
        rewards = _get_available_rewards()
        reward = next((r for r in rewards if r["id"] == reward_id), None)
        if not reward:
            raise HTTPException(404, "Reward not found")
        if member.get("points", 0) < reward["points_cost"]:
            raise HTTPException(400, f"Not enough points. Need {reward['points_cost']}, have {member['points']}")
        new_balance = member["points"] - reward["points_cost"]
        redemption = {"reward_id": reward_id, "reward_name": reward["name"], "points_cost": reward["points_cost"], "date": datetime.now(timezone.utc).isoformat()}
        await db.loyalty_members.update_one({"guest_id": guest_id}, {"$set": {"points": new_balance}, "$push": {"rewards_redeemed": redemption}})
        return {"status": "redeemed", "reward": reward["name"], "points_spent": reward["points_cost"], "new_balance": new_balance}

    @router.get("/loyalty/rewards")
    async def get_rewards():
        """List available rewards"""
        return _get_available_rewards()

    @router.get("/loyalty/leaderboard/{property_id}")
    async def loyalty_leaderboard(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Top loyalty members"""
        members = await db.loyalty_members.find({}, {"_id": 0}).sort("lifetime_points", -1).to_list(50)
        tiers = {"standard": 0, "silver": 0, "gold": 0, "platinum": 0}
        for m in members:
            t = m.get("tier", "standard")
            if t in tiers: tiers[t] += 1
        return {"members": members, "tier_counts": tiers, "total_members": len(members)}

    # ==================== DUTY MANAGER LOGBOOK ====================

    @router.post("/logbook/entries")
    async def create_logbook_entry(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Create a logbook entry"""
        entry = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "type": data.get("type", "note"),  # note, incident, vip, handover, complaint, request
            "title": data.get("title", ""),
            "content": data.get("content", ""),
            "priority": data.get("priority", "normal"),
            "room_number": data.get("room_number", ""),
            "guest_name": data.get("guest_name", ""),
            "shift": data.get("shift", _current_shift()),
            "status": "open",
            "created_by": current_user.get("name", current_user.get("email", "")),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "follow_up_required": data.get("follow_up_required", False),
            "resolved_at": "",
            "resolved_by": "",
        }
        await db.logbook_entries.insert_one(entry)
        entry.pop("_id", None)
        return entry

    @router.get("/logbook/entries/{property_id}")
    async def list_logbook_entries(property_id: str, shift: str = "", date: str = "", current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """List logbook entries"""
        query = {"property_id": property_id}
        if shift: query["shift"] = shift
        if date:
            query["created_at"] = {"$gte": f"{date}T00:00:00", "$lte": f"{date}T23:59:59"}
        docs = await db.logbook_entries.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.put("/logbook/entries/{entry_id}")
    async def update_logbook_entry(entry_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Update/resolve a logbook entry"""
        updates = {}
        if "status" in data:
            updates["status"] = data["status"]
            if data["status"] == "resolved":
                updates["resolved_at"] = datetime.now(timezone.utc).isoformat()
                updates["resolved_by"] = current_user.get("name", "")
        if "content" in data: updates["content"] = data["content"]
        if "priority" in data: updates["priority"] = data["priority"]
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.logbook_entries.update_one({"id": entry_id}, {"$set": updates})
        doc = await db.logbook_entries.find_one({"id": entry_id}, {"_id": 0})
        return doc

    @router.post("/logbook/shift-handover")
    async def create_shift_handover(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Create shift handover summary"""
        handover = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "from_shift": data.get("from_shift", _current_shift()),
            "to_shift": data.get("to_shift", ""),
            "summary": data.get("summary", ""),
            "key_items": data.get("key_items", []),
            "pending_issues": data.get("pending_issues", []),
            "vip_arrivals": data.get("vip_arrivals", []),
            "handover_by": current_user.get("name", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.shift_handovers.insert_one(handover)
        handover.pop("_id", None)
        return handover

    @router.get("/logbook/shift-handovers/{property_id}")
    async def list_handovers(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        docs = await db.shift_handovers.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(30)
        return docs

    # ==================== OCCUPANCY FORECASTING ====================

    @router.get("/forecast/occupancy/{property_id}")
    async def get_occupancy_forecast(property_id: str, days: int = 90, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate occupancy forecast for next N days"""
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        total_rooms = sum(int(r.get("total_rooms", 0)) for r in room_types)
        if total_rooms == 0:
            total_rooms = 20  # Default

        today = datetime.now(timezone.utc).date()
        forecast = []

        for i in range(days):
            target_date = (today + timedelta(days=i)).isoformat()
            bookings = await db.bookings.count_documents({
                "property_id": property_id,
                "check_in": {"$lte": target_date}, "check_out": {"$gt": target_date},
                "status": {"$nin": ["cancelled"]},
            })
            occupancy_pct = round(min(100, bookings / total_rooms * 100), 1)
            available = max(0, total_rooms - bookings)

            # Revenue estimate
            avg_rate = 0
            if bookings > 0:
                pipeline = [
                    {"$match": {"property_id": property_id, "check_in": {"$lte": target_date}, "check_out": {"$gt": target_date}, "status": {"$nin": ["cancelled"]}}},
                    {"$group": {"_id": None, "avg_rate": {"$avg": "$total_price"}, "total": {"$sum": "$total_price"}}},
                ]
                async for doc in db.bookings.aggregate(pipeline):
                    avg_rate = round(doc.get("avg_rate", 0), 2)

            forecast.append({
                "date": target_date,
                "day_of_week": (today + timedelta(days=i)).strftime("%a"),
                "bookings": bookings,
                "total_rooms": total_rooms,
                "available": available,
                "occupancy_pct": occupancy_pct,
                "estimated_revenue": round(bookings * avg_rate, 2) if avg_rate else 0,
                "avg_rate": avg_rate,
            })

        # Summaries
        next_7 = forecast[:7]
        next_30 = forecast[:30]
        next_90 = forecast[:90]

        return {
            "property_id": property_id,
            "total_rooms": total_rooms,
            "forecast": forecast,
            "summary": {
                "7_day": {"avg_occupancy": round(sum(d["occupancy_pct"] for d in next_7) / max(len(next_7), 1), 1), "total_revenue": round(sum(d["estimated_revenue"] for d in next_7), 2), "avg_rate": round(sum(d["avg_rate"] for d in next_7 if d["avg_rate"]) / max(sum(1 for d in next_7 if d["avg_rate"]), 1), 2)},
                "30_day": {"avg_occupancy": round(sum(d["occupancy_pct"] for d in next_30) / max(len(next_30), 1), 1), "total_revenue": round(sum(d["estimated_revenue"] for d in next_30), 2)},
                "90_day": {"avg_occupancy": round(sum(d["occupancy_pct"] for d in next_90) / max(len(next_90), 1), 1), "total_revenue": round(sum(d["estimated_revenue"] for d in next_90), 2)},
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    return router


def _calculate_tier(stays):
    if stays >= 15: return "platinum"
    if stays >= 7: return "gold"
    if stays >= 3: return "silver"
    return "standard"

def _get_next_tier(current):
    order = ["standard", "silver", "gold", "platinum"]
    idx = order.index(current) if current in order else 0
    return order[idx + 1] if idx < len(order) - 1 else None

def _stays_to_next_tier(member):
    current = member.get("tier", "standard")
    stays = member.get("total_stays", 0)
    nxt = _get_next_tier(current)
    if not nxt: return 0
    return max(0, TIER_THRESHOLDS[nxt] - stays)

def _current_shift():
    hour = datetime.now(timezone.utc).hour
    if 6 <= hour < 14: return "morning"
    if 14 <= hour < 22: return "afternoon"
    return "night"

def _get_available_rewards():
    return [
        {"id": "free_night", "name": "Free Night Stay", "points_cost": 5000, "category": "stay", "description": "Redeem for one free night"},
        {"id": "room_upgrade", "name": "Room Upgrade", "points_cost": 2000, "category": "upgrade", "description": "Upgrade to next room category"},
        {"id": "spa_voucher", "name": "Spa Voucher £50", "points_cost": 1500, "category": "spa", "description": "£50 credit at the hotel spa"},
        {"id": "restaurant_credit", "name": "Restaurant Credit £30", "points_cost": 1000, "category": "dining", "description": "£30 dining credit"},
        {"id": "late_checkout", "name": "Late Checkout 4PM", "points_cost": 500, "category": "service", "description": "Guaranteed late checkout until 4PM"},
        {"id": "welcome_amenity", "name": "Premium Welcome Amenity", "points_cost": 300, "category": "amenity", "description": "Champagne & chocolates on arrival"},
        {"id": "parking", "name": "Free Parking (1 night)", "points_cost": 200, "category": "service", "description": "Complimentary parking for one night"},
        {"id": "breakfast", "name": "Complimentary Breakfast", "points_cost": 400, "category": "dining", "description": "Full breakfast for two"},
    ]
