"""
Mongo index yönetimi — startup'ta idempotent oluşturur (ölçek P0).
GET /system/indexes → mevcut index durumu. POST /system/indexes/ensure → tekrar çalıştır.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pymongo import ASCENDING, DESCENDING

logger = logging.getLogger(__name__)

# (collection, keys, options)
INDEX_SPECS = [
    ("reviews", [("property_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ("reviews", [("property_id", ASCENDING), ("response_status", ASCENDING)], {}),
    ("reviews", [("id", ASCENDING)], {"unique": True}),
    ("reviews", [("external_id", ASCENDING)], {"unique": True, "sparse": True}),
    ("reviews", [("sentiment_analysis.risk_level", ASCENDING)], {"sparse": True}),
    ("bookings", [("property_id", ASCENDING), ("check_in", ASCENDING)], {}),
    ("bookings", [("property_id", ASCENDING), ("check_out", ASCENDING)], {}),
    ("bookings", [("property_id", ASCENDING), ("status", ASCENDING)], {}),
    ("bookings", [("id", ASCENDING)], {"unique": True}),
    ("bookings", [("booking_ref", ASCENDING)], {"sparse": True}),
    ("bookings", [("guest_email", ASCENDING)], {"sparse": True}),
    ("users", [("email", ASCENDING)], {"unique": True, "sparse": True}),
    ("users", [("id", ASCENDING)], {"unique": True, "sparse": True}),
    ("properties", [("id", ASCENDING)], {"unique": True}),
    ("notifications", [("property_id", ASCENDING), ("read", ASCENDING), ("created_at", DESCENDING)], {}),
    ("staff_tasks", [("property_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)], {}),
    ("staff_tasks", [("source", ASCENDING), ("topic", ASCENDING)], {"sparse": True}),
    ("guest_complaints", [("property_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)], {}),
    ("promo_codes", [("code", ASCENDING)], {}),
    ("promo_codes", [("source", ASCENDING), ("valid_to", ASCENDING)], {}),
    ("scheduler_config", [("property_id", ASCENDING), ("job", ASCENDING)], {"unique": True}),
    ("scheduler_history", [("property_id", ASCENDING), ("ran_at", DESCENDING)], {}),
    ("scheduler_history", [("ran_at", ASCENDING)], {"expireAfterSeconds": 60 * 86400}),
    ("job_queue", [("status", ASCENDING), ("priority", DESCENDING), ("run_after", ASCENDING)], {}),
    ("job_queue", [("id", ASCENDING)], {"unique": True}),
    ("job_queue", [("finished_at", ASCENDING)], {"expireAfterSeconds": 14 * 86400, "sparse": True}),
    ("audit_logs", [("property_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ("gbp_publish_queue", [("property_id", ASCENDING), ("status", ASCENDING)], {}),
    ("google_tokens", [("property_id", ASCENDING)], {"unique": True}),
    ("oauth_states", [("created_at", ASCENDING)], {"expireAfterSeconds": 900}),
    ("staff_praise_log", [("property_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ("root_cause_impacts", [("property_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ("review_request_log", [("booking_id", ASCENDING)], {}),
    ("rate_limit_events", [("created_at", ASCENDING)], {"expireAfterSeconds": 7 * 86400}),
    ("messages", [("property_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ("payments", [("property_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ("folios", [("booking_id", ASCENDING)], {"sparse": True}),
    ("rates", [("property_id", ASCENDING), ("date", ASCENDING)], {}),
    ("housekeeping_tasks", [("property_id", ASCENDING), ("status", ASCENDING)], {}),
]


async def ensure_indexes(db) -> dict:
    created, skipped, errors = [], [], []
    for coll, keys, opts in INDEX_SPECS:
        name = coll + "__" + "_".join(f"{k}_{'1' if d == ASCENDING else '-1'}" for k, d in keys)
        try:
            await db[coll].create_index(keys, name=name, background=True, **opts)
            created.append(name)
        except Exception as e:
            msg = str(e)
            # conflicting existing index or duplicate data for unique → skip, don't crash startup
            (skipped if ("already exists" in msg or "IndexOptionsConflict" in msg or "IndexKeySpecsConflict" in msg) else errors).append({"index": name, "error": msg[:160]})
    res = {"ensured": len(created), "skipped": len(skipped), "errors": errors, "at": datetime.now(timezone.utc).isoformat()}
    await db.system_meta.update_one({"key": "indexes"}, {"$set": {"key": "indexes", **res}}, upsert=True)
    if errors:
        logger.warning(f"ensure_indexes errors: {errors}")
    logger.info(f"✅ Mongo indexes ensured: {len(created)} ok, {len(skipped)} skipped, {len(errors)} errors")
    return res


def create_db_indexes_router(db, require_roles):
    router = APIRouter()

    @router.get("/system/indexes")
    async def list_indexes(_: dict = Depends(require_roles("admin"))):
        out = {}
        for coll in sorted({c for c, _, _ in INDEX_SPECS}):
            try:
                info = await db[coll].index_information()
                out[coll] = sorted(k for k in info.keys() if k != "_id_")
            except Exception as e:
                out[coll] = [f"error: {e}"]
        meta = await db.system_meta.find_one({"key": "indexes"}, {"_id": 0})
        return {"specs": len(INDEX_SPECS), "collections": out, "last_run": meta}

    @router.post("/system/indexes/ensure")
    async def run_ensure(_: dict = Depends(require_roles("admin"))):
        return await ensure_indexes(db)

    return router
