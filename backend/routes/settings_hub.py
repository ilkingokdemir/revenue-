"""
Settings Hub — Branches, Currencies, Room Categories, Rooms, Booking Sources,
Expense Categories, Laundry Providers, Booking Document Types
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_settings_hub_router(db, require_roles):
    router = APIRouter()

    # Generic CRUD factory
    def make_crud(collection_name, prefix, label):

        @router.get(f"/settings/{prefix}")
        async def list_items(current_user: dict = Depends(require_roles("admin", "manager"))):
            docs = await db[collection_name].find({}, {"_id": 0}).sort("order", 1).to_list(200)
            return docs

        @router.post(f"/settings/{prefix}")
        async def create_item(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
            now = datetime.now(timezone.utc).isoformat()
            item = {**data, "id": str(uuid.uuid4()), "created_at": now}
            item.pop("_id", None)
            count = await db[collection_name].count_documents({})
            item.setdefault("order", count + 1)
            await db[collection_name].insert_one(item)
            item.pop("_id", None)
            return item

        @router.put(f"/settings/{prefix}/{{item_id}}")
        async def update_item(item_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
            updates.pop("_id", None)
            updates.pop("id", None)
            await db[collection_name].update_one({"id": item_id}, {"$set": updates})
            return await db[collection_name].find_one({"id": item_id}, {"_id": 0})

        @router.delete(f"/settings/{prefix}/{{item_id}}")
        async def delete_item(item_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
            await db[collection_name].delete_one({"id": item_id})
            return {"status": "deleted"}

        list_items.__name__ = f"list_{prefix}"
        create_item.__name__ = f"create_{prefix}"
        update_item.__name__ = f"update_{prefix}"
        delete_item.__name__ = f"delete_{prefix}"

    make_crud("settings_currencies", "currencies", "Currency")
    make_crud("settings_room_categories", "room-categories", "Room Category")
    make_crud("settings_booking_sources", "booking-sources", "Booking Source")
    make_crud("settings_expense_categories", "expense-categories", "Expense Category")
    make_crud("settings_laundry_providers", "laundry-providers", "Laundry Provider")
    make_crud("settings_doc_types", "document-types", "Document Type")

    # Seed defaults
    @router.get("/settings/seed-defaults")
    async def seed_defaults(current_user: dict = Depends(require_roles("admin"))):
        now = datetime.now(timezone.utc).isoformat()
        seeded = []

        # Currencies
        if await db.settings_currencies.count_documents({}) == 0:
            currencies = [
                {"id": str(uuid.uuid4()), "code": "GBP", "name": "British Pound", "symbol": "£", "order": 1, "is_default": True, "created_at": now},
                {"id": str(uuid.uuid4()), "code": "EUR", "name": "Euro", "symbol": "€", "order": 2, "is_default": False, "created_at": now},
                {"id": str(uuid.uuid4()), "code": "USD", "name": "US Dollar", "symbol": "$", "order": 3, "is_default": False, "created_at": now},
                {"id": str(uuid.uuid4()), "code": "TRY", "name": "Turkish Lira", "symbol": "₺", "order": 4, "is_default": False, "created_at": now},
            ]
            await db.settings_currencies.insert_many(currencies)
            for c in currencies: c.pop("_id", None)
            seeded.append("currencies")

        # Room Categories
        if await db.settings_room_categories.count_documents({}) == 0:
            cats = [
                {"id": str(uuid.uuid4()), "name": "Standard", "code": "STD", "description": "Standard room", "order": 1, "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Deluxe", "code": "DLX", "description": "Deluxe room", "order": 2, "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Suite", "code": "STE", "description": "Suite", "order": 3, "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Family", "code": "FAM", "description": "Family room", "order": 4, "created_at": now},
            ]
            await db.settings_room_categories.insert_many(cats)
            for c in cats: c.pop("_id", None)
            seeded.append("room_categories")

        # Booking Sources
        if await db.settings_booking_sources.count_documents({}) == 0:
            sources = [
                {"id": str(uuid.uuid4()), "name": "Direct", "code": "direct", "commission_rate": 0, "order": 1, "status": "active", "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Booking.com", "code": "booking_com", "commission_rate": 15, "order": 2, "status": "active", "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Expedia", "code": "expedia", "commission_rate": 18, "order": 3, "status": "active", "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Airbnb", "code": "airbnb", "commission_rate": 3, "order": 4, "status": "active", "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Walk-in", "code": "walkin", "commission_rate": 0, "order": 5, "status": "active", "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Hotelbeds", "code": "hotelbeds", "commission_rate": 20, "order": 6, "status": "active", "created_at": now},
            ]
            await db.settings_booking_sources.insert_many(sources)
            for s in sources: s.pop("_id", None)
            seeded.append("booking_sources")

        # Expense Categories
        if await db.settings_expense_categories.count_documents({}) == 0:
            ecats = [
                {"id": str(uuid.uuid4()), "name": "Rent", "code": "rent", "order": 1, "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Commission", "code": "commission", "order": 2, "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Laundry", "code": "laundry", "order": 3, "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Cleaning Products", "code": "cleaning_products", "order": 4, "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Complementary", "code": "complementary", "order": 5, "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Insurance", "code": "insurance", "order": 6, "created_at": now},
                {"id": str(uuid.uuid4()), "name": "Utilities", "code": "utilities", "order": 7, "created_at": now},
            ]
            await db.settings_expense_categories.insert_many(ecats)
            for c in ecats: c.pop("_id", None)
            seeded.append("expense_categories")

        return {"seeded": seeded}

    return router
