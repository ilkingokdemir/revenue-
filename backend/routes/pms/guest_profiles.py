"""
Guest Profile / CRM Routes
Unified guest profiles, history, segmentation
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import asyncio
import logging

from routes.helpers import fire_webhooks, log_sync

logger = logging.getLogger(__name__)


def create_guest_profiles_router(db, require_roles):
    router = APIRouter()

    @router.get("/guests/profiles/{property_id}")
    async def list_profiles(property_id: str, search: str = "", vip: str = "", tag: str = "",
                             loyalty: str = "", sort_by: str = "last_stay",
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {}
        if property_id != "all":
            query["properties"] = property_id
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}},
            ]
        if vip == "true":
            query["vip"] = True
        if tag:
            query["tags"] = tag
        if loyalty:
            query["loyalty_tier"] = loyalty

        sort_field = {"last_stay": -1, "total_spend": -1, "total_stays": -1, "name": 1}.get(sort_by, -1)
        sort_key = sort_by if sort_by in ["name"] else sort_by
        docs = await db.guest_profiles.find(query, {"_id": 0}).sort(sort_key, sort_field).to_list(200)
        return docs

    @router.get("/guests/profiles/detail/{guest_id}")
    async def get_profile(guest_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        doc = await db.guest_profiles.find_one({"id": guest_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Guest not found")
        # Get booking history
        bookings = []
        if doc.get("email"):
            bookings = await db.bookings.find({"guest_email": doc["email"]}, {"_id": 0}).sort("check_in", -1).to_list(50)
        elif doc.get("phone"):
            bookings = await db.bookings.find({"guest_phone": doc["phone"]}, {"_id": 0}).sort("check_in", -1).to_list(50)
        # Get review history
        reviews = []
        if doc.get("name"):
            reviews = await db.reviews.find({"guest_name": doc["name"]}, {"_id": 0, "id": 1, "rating": 1, "platform": 1, "review_text": 1, "created_at": 1}).sort("created_at", -1).to_list(20)
        # Get conversation history
        conversations = []
        if doc.get("email") or doc.get("phone"):
            conv_q = {}
            if doc.get("email"):
                conv_q["guest_email"] = doc["email"]
            conversations = await db.conversations.find(conv_q, {"_id": 0, "id": 1, "channel": 1, "status": 1, "last_message_preview": 1, "created_at": 1}).sort("created_at", -1).to_list(20)
        doc["bookings"] = bookings
        doc["reviews"] = reviews
        doc["conversations"] = conversations
        return doc

    @router.post("/guests/profiles")
    async def create_profile(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import GuestProfile
        profile = GuestProfile(**data)
        doc = profile.model_dump()
        await db.guest_profiles.insert_one(doc)
        doc.pop("_id", None)
        asyncio.create_task(fire_webhooks(db, "guest.created", {"name": doc.get("name"), "email": doc.get("email"), "id": doc.get("id")}))
        await log_sync(db, "guest-profiles", "internal", "success", f"Guest profile created: {doc.get('name')}", doc.get("id", ""))
        return doc

    @router.put("/guests/profiles/{guest_id}")
    async def update_profile(guest_id: str, updates: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await db.guest_profiles.update_one({"id": guest_id}, {"$set": updates})
        doc = await db.guest_profiles.find_one({"id": guest_id}, {"_id": 0})
        if doc is None:
            raise HTTPException(status_code=404, detail="Misafir profili bulunamadı")
        if "vip" in updates:
            asyncio.create_task(fire_webhooks(db, "guest.vip_changed", {"guest_id": guest_id, "name": doc.get("name", ""), "vip": updates["vip"]}))
            await log_sync(db, "guest-profiles", "internal", "success", f"VIP {'set' if updates['vip'] else 'removed'}: {doc.get('name', '')}", guest_id)
        else:
            asyncio.create_task(fire_webhooks(db, "guest.updated", {"guest_id": guest_id, "name": doc.get("name", "")}))
        return doc

    @router.delete("/guests/profiles/{guest_id}")
    async def delete_profile(guest_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.guest_profiles.delete_one({"id": guest_id})
        return {"status": "deleted"}

    @router.post("/guests/profiles/{guest_id}/tags")
    async def add_tag(guest_id: str, tag: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.guest_profiles.update_one({"id": guest_id}, {"$addToSet": {"tags": tag}})
        return {"status": "added"}

    @router.get("/guests/profiles/{property_id}/stats")
    async def profile_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"properties": property_id}
        total = await db.guest_profiles.count_documents(query)
        vip = await db.guest_profiles.count_documents({**query, "vip": True})
        pipeline = [
            {"$match": query} if query else {"$match": {}},
            {"$group": {"_id": "$loyalty_tier", "count": {"$sum": 1}}}
        ]
        tiers = {}
        async for doc in db.guest_profiles.aggregate(pipeline):
            tiers[doc["_id"] or "standard"] = doc["count"]
        return {"total": total, "vip": vip, "tiers": tiers}

    @router.post("/guests/profiles/sync/{property_id}")
    async def sync_profiles_from_bookings(property_id: str,
                                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Build guest profiles from existing bookings"""
        bookings = await db.bookings.find(
            {"property_id": property_id} if property_id != "all" else {},
            {"_id": 0}
        ).to_list(2000)

        created = 0
        updated = 0
        for b in bookings:
            email = b.get("guest_email", "")
            phone = b.get("guest_phone", "")
            name = b.get("guest_name", "")
            if not name:
                continue
            key = email or phone or name

            existing = None
            if email:
                existing = await db.guest_profiles.find_one({"email": email}, {"_id": 0})
            if not existing and phone:
                existing = await db.guest_profiles.find_one({"phone": phone}, {"_id": 0})

            total_price = b.get("total_price", 0) or 0
            check_in = b.get("check_in", "")
            prop_id = b.get("property_id", "")

            if existing:
                update = {
                    "$inc": {"total_stays": 1, "total_spend": total_price},
                    "$set": {"last_stay": check_in, "updated_at": datetime.now(timezone.utc).isoformat()},
                    "$addToSet": {"properties": prop_id},
                }
                if not existing.get("first_stay") or check_in < existing.get("first_stay", "9999"):
                    update["$set"]["first_stay"] = check_in
                await db.guest_profiles.update_one({"id": existing["id"]}, update)
                updated += 1
            else:
                from models import GuestProfile
                profile = GuestProfile(
                    name=name, email=email, phone=phone,
                    total_stays=1, total_spend=total_price,
                    first_stay=check_in, last_stay=check_in,
                    source=b.get("source", "direct"),
                )
                doc = profile.model_dump()
                doc["properties"] = [prop_id]
                await db.guest_profiles.insert_one(doc)
                created += 1

        return {"message": f"Synced: {created} new, {updated} updated", "created": created, "updated": updated}

    # --- Cross-module: auto-link reviews to guest profiles ---
    @router.post("/guests/profiles/link-reviews/{property_id}")
    async def link_reviews_to_profiles(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Link existing reviews to guest profiles by matching guest_name"""
        reviews = await db.reviews.find({"property_id": property_id} if property_id != "all" else {}, {"_id": 0, "guest_name": 1, "rating": 1}).to_list(2000)
        linked = 0
        for r in reviews:
            name = r.get("guest_name", "")
            if not name:
                continue
            profile = await db.guest_profiles.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}}, {"_id": 0, "id": 1})
            if profile:
                await db.guest_profiles.update_one(
                    {"id": profile["id"]},
                    {"$set": {"avg_rating_given": r.get("rating", 0), "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                linked += 1
        await log_sync(db, "guest-profiles", "internal", "success", f"Linked {linked} reviews to profiles", f"property:{property_id}")
        return {"message": f"Linked {linked} reviews to guest profiles", "linked": linked}

    return router
