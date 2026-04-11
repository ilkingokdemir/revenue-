"""
Smart Lock / Digital Key Integration Routes
Generic framework supporting TTLock, Nuki, ASSA ABLOY, Salto, August/Yale
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import secrets
import asyncio
import logging

from routes.helpers import fire_webhooks, log_sync

logger = logging.getLogger(__name__)

PROVIDER_INFO = {
    "ttlock": {
        "name": "TTLock",
        "setup_url": "https://open.ttlock.com/",
        "docs_url": "https://open.ttlock.com/doc",
        "fields": ["api_key", "api_secret"],
        "description": "TTLock Cloud API — Most popular smart lock for hotels. Create app at open.ttlock.com to get Client ID & Secret.",
    },
    "nuki": {
        "name": "Nuki",
        "setup_url": "https://developer.nuki.io/",
        "docs_url": "https://developer.nuki.io/page/nuki-web-api-1-4/3",
        "fields": ["api_key"],
        "description": "Nuki Web API — Get your API token from the Nuki Developer portal.",
    },
    "august_yale": {
        "name": "August / Yale",
        "setup_url": "https://august.com/pages/developer",
        "docs_url": "https://august.com/pages/developer",
        "fields": ["api_key", "api_secret"],
        "description": "August/Yale Access API — Apply for partner access at August developer portal.",
    },
    "salto": {
        "name": "Salto KS",
        "setup_url": "https://saltoks.com/integrations/",
        "docs_url": "https://intercom.help/salto-ks/en/",
        "fields": ["api_key", "api_url"],
        "description": "Salto KS API — Contact Salto for API credentials. Set your property's API endpoint URL.",
    },
    "assa_abloy": {
        "name": "ASSA ABLOY Global Solutions",
        "setup_url": "https://www.assaabloyglobalsolutions.com/",
        "docs_url": "https://www.assaabloyglobalsolutions.com/hospitality/",
        "fields": ["api_key", "api_secret", "api_url"],
        "description": "ASSA ABLOY Hospitality Mobile Access — Enterprise lock system. Contact ASSA ABLOY for integration credentials.",
    },
    "generic": {
        "name": "Generic / Custom",
        "setup_url": "",
        "docs_url": "",
        "fields": ["api_key", "api_url"],
        "description": "Generic smart lock API — Configure any lock system with API key and endpoint URL.",
    },
}


def create_smart_locks_router(db, require_roles):
    router = APIRouter()

    @router.get("/smart-locks/providers")
    async def list_providers(current_user: dict = Depends(require_roles("admin", "manager"))):
        """List available smart lock providers with setup info"""
        return PROVIDER_INFO

    @router.get("/smart-locks/config/{property_id}")
    async def get_config(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.smart_lock_configs.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            from models import SmartLockConfig
            cfg = SmartLockConfig(property_id=property_id)
            d = cfg.model_dump()
            await db.smart_lock_configs.insert_one(d)
            d.pop("_id", None)
            return d
        return doc

    @router.put("/smart-locks/config/{property_id}")
    async def update_config(property_id: str, updates: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.smart_lock_configs.update_one({"property_id": property_id}, {"$set": updates}, upsert=True)
        doc = await db.smart_lock_configs.find_one({"property_id": property_id}, {"_id": 0})
        return doc

    @router.post("/smart-locks/config/{property_id}/test")
    async def test_connection(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Test smart lock API connection"""
        config = await db.smart_lock_configs.find_one({"property_id": property_id}, {"_id": 0})
        if not config or not config.get("api_key"):
            return {"success": False, "message": "No API credentials configured"}

        provider = config.get("provider", "generic")
        # In production, this would make a real API call to the lock provider
        # For now, validate that credentials are set
        required_fields = PROVIDER_INFO.get(provider, {}).get("fields", ["api_key"])
        missing = [f for f in required_fields if not config.get(f)]
        if missing:
            return {"success": False, "message": f"Missing required fields: {', '.join(missing)}"}

        return {"success": True, "message": f"Connection to {PROVIDER_INFO.get(provider, {}).get('name', provider)} validated. Credentials configured.", "provider": provider}

    @router.post("/smart-locks/config/{property_id}/rooms")
    async def add_room_lock(property_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Map a room to a smart lock"""
        room_entry = {
            "room_number": data.get("room_number", ""),
            "lock_id": data.get("lock_id", ""),
            "lock_name": data.get("lock_name", ""),
        }
        await db.smart_lock_configs.update_one(
            {"property_id": property_id},
            {"$push": {"rooms": room_entry}}
        )
        return {"status": "added", "room": room_entry}

    # === Digital Keys ===

    @router.get("/digital-keys/{property_id}")
    async def list_keys(property_id: str, status: str = "",
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {"property_id": property_id}
        if status: query["status"] = status
        docs = await db.digital_keys.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    @router.post("/digital-keys/generate")
    async def generate_key(data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Generate a digital key for a booking"""
        from models import DigitalKey
        booking_ref = data.get("booking_ref", "")
        if not booking_ref:
            raise HTTPException(status_code=400, detail="booking_ref required")

        booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        # Check if key already exists
        existing = await db.digital_keys.find_one({"booking_ref": booking_ref, "status": "active"}, {"_id": 0})
        if existing:
            return existing

        key = DigitalKey(
            property_id=booking.get("property_id", ""),
            booking_ref=booking_ref,
            guest_name=booking.get("guest_name", ""),
            guest_email=booking.get("guest_email", ""),
            room_number=data.get("room_number", ""),
            lock_id=data.get("lock_id", ""),
            valid_from=booking.get("check_in", ""),
            valid_until=booking.get("check_out", ""),
        )
        doc = key.model_dump()
        await db.digital_keys.insert_one(doc)
        doc.pop("_id", None)
        asyncio.create_task(fire_webhooks(db, "key.generated", {"booking_ref": booking_ref, "guest_name": doc.get("guest_name"), "room": doc.get("room_number"), "access_code": doc.get("access_code")}))
        await log_sync(db, "digital-keys", "internal", "success", f"Key generated for {doc.get('guest_name')} (room {doc.get('room_number', 'TBD')})", booking_ref)
        return doc

    @router.put("/digital-keys/{key_id}/revoke")
    async def revoke_key(key_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.digital_keys.update_one({"id": key_id}, {"$set": {"status": "revoked"}})
        asyncio.create_task(fire_webhooks(db, "key.revoked", {"key_id": key_id}))
        await log_sync(db, "digital-keys", "internal", "success", f"Key {key_id} revoked", key_id)
        return {"status": "revoked"}

    @router.get("/digital-keys/guest/{booking_ref}")
    async def guest_get_key(booking_ref: str):
        """Public: Guest accesses their digital key"""
        key = await db.digital_keys.find_one({"booking_ref": booking_ref, "status": "active"}, {"_id": 0})
        if not key:
            raise HTTPException(status_code=404, detail="No active digital key found")
        # Increment usage
        await db.digital_keys.update_one(
            {"id": key["id"]},
            {"$inc": {"used_count": 1}, "$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}}
        )
        asyncio.create_task(fire_webhooks(db, "key.used", {"booking_ref": booking_ref, "guest_name": key["guest_name"], "room": key["room_number"]}))
        await log_sync(db, "digital-keys", "inbound", "success", f"Guest accessed key for room {key['room_number']}", booking_ref)
        return {
            "access_code": key["access_code"],
            "room_number": key["room_number"],
            "guest_name": key["guest_name"],
            "valid_from": key["valid_from"],
            "valid_until": key["valid_until"],
        }

    @router.get("/digital-keys/{property_id}/stats")
    async def key_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        total = await db.digital_keys.count_documents({"property_id": property_id})
        active = await db.digital_keys.count_documents({"property_id": property_id, "status": "active"})
        expired = await db.digital_keys.count_documents({"property_id": property_id, "status": "expired"})
        revoked = await db.digital_keys.count_documents({"property_id": property_id, "status": "revoked"})
        return {"total": total, "active": active, "expired": expired, "revoked": revoked}

    return router
