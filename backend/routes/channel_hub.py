"""
Channel Hub (Iter 163) — five missing Channel Manager pillars in one file:
  • Channel Configs + 8-step Setup Checklist
  • Payload Profiles (per-channel fields/constraints)
  • Publish Jobs (ARI distribution queue)
  • Price Overrides
  • Channel Audit Log (distribution events - separate from RBAC audit_trail)
  • Benchmark Cockpit (STR-style Occupancy / ADR / RevPAR index)

Designed to complement the existing channel_manager / channel_mappings /
sync_queue / rate_structure routers. Mocked OTA calls return deterministic
sample payloads so the UI flows end-to-end without real API keys.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import uuid
import random
import logging

logger = logging.getLogger(__name__)


CHECKLIST_STEPS = [
    {"id": "create_config", "label": "Create Channel Config",
     "description": "Add channel credentials and connector details."},
    {"id": "enter_credentials", "label": "Enter Credentials",
     "description": "Credentials and property codes are required to connect."},
    {"id": "run_certification", "label": "Run Certification",
     "description": "Verify connector integration against OTA requirements."},
    {"id": "create_payload", "label": "Create Payload Profile",
     "description": "Discover supported fields and payload constraints."},
    {"id": "complete_mappings", "label": "Complete Mappings",
     "description": "Map rooms/rates to OTA products for publish eligibility."},
    {"id": "verify_rate_structure", "label": "Verify Rate Structure",
     "description": "Define channel rate codes, occupancies, meals and tax modes."},
    {"id": "dry_run", "label": "Dry-run Publish",
     "description": "Create a publish job to validate payload delivery."},
    {"id": "enable_autopublish", "label": "Enable Autopublish",
     "description": "Turn on autopilot to automatically push accepted prices."},
]


async def _log_audit(db, property_id: str, event: str, details: Dict,
                     user_email: str = "system"):
    """Write a row to channel_audit (distribution event log)."""
    await db.channel_audit.insert_one({
        "id": str(uuid.uuid4()),
        "property_id": property_id,
        "event": event,
        "details": details or {},
        "user_email": user_email,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


def create_channel_hub_router(db, require_roles):
    router = APIRouter()

    # ──────────────────────────────────────────────────────────────
    # CHANNEL CONFIGS + SETUP CHECKLIST
    # ──────────────────────────────────────────────────────────────
    @router.get("/channel-configs/{property_id}")
    async def list_configs(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.channel_configs.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        return {"property_id": property_id, "configs": rows}

    @router.post("/channel-configs/{property_id}")
    async def create_config(property_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        if not data.get("channel_id") or not data.get("name"):
            raise HTTPException(400, "channel_id and name required")
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "channel_id": data["channel_id"],
            "name": data["name"],
            "connector": data.get("connector") or "rest_api",
            "property_code": data.get("property_code", ""),
            "endpoint_url": data.get("endpoint_url", ""),
            "credentials_set": False,
            "certified": False,
            "autopublish": False,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("email", ""),
        }
        await db.channel_configs.insert_one(doc)
        doc.pop("_id", None)
        await _log_audit(db, property_id, "config.create",
                         {"channel_id": data["channel_id"]}, current_user.get("email", ""))
        return doc

    @router.put("/channel-configs/{config_id}")
    async def update_config(config_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"name", "property_code", "endpoint_url", "credentials_set",
                   "certified", "autopublish", "status"}
        patch = {k: v for k, v in data.items() if k in allowed}
        if not patch:
            raise HTTPException(400, "No valid fields")
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        cfg = await db.channel_configs.find_one({"id": config_id}, {"_id": 0})
        if not cfg:
            raise HTTPException(404, "Config not found")
        await db.channel_configs.update_one({"id": config_id}, {"$set": patch})
        await _log_audit(db, cfg.get("property_id", ""), "config.update",
                         {"config_id": config_id, "patch": patch},
                         current_user.get("email", ""))
        return {"status": "updated", "patch": patch}

    @router.delete("/channel-configs/{config_id}")
    async def delete_config(config_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await db.channel_configs.find_one({"id": config_id}, {"_id": 0})
        if not cfg:
            return {"status": "not_found"}
        await db.channel_configs.delete_one({"id": config_id})
        await _log_audit(db, cfg.get("property_id", ""), "config.delete",
                         {"config_id": config_id}, current_user.get("email", ""))
        return {"status": "deleted"}

    @router.post("/channel-configs/{config_id}/certify")
    async def certify_config(config_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Mocked certification — flips flag + logs."""
        cfg = await db.channel_configs.find_one({"id": config_id})
        if not cfg:
            raise HTTPException(404, "Config not found")
        await db.channel_configs.update_one(
            {"id": config_id},
            {"$set": {"certified": True, "status": "certified",
                      "certified_at": datetime.now(timezone.utc).isoformat()}},
        )
        await _log_audit(db, cfg.get("property_id", ""), "config.certify",
                         {"config_id": config_id}, current_user.get("email", ""))
        return {"status": "certified", "passed": 12, "failed": 0,
                "message": "All 12 connector checks passed."}

    @router.get("/channel-hub/{property_id}/checklist")
    async def get_checklist(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        configs = await db.channel_configs.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        profiles = await db.payload_profiles.count_documents({"property_id": property_id})
        mappings = await db.channel_mappings.count_documents({"property_id": property_id})
        rate_struct = await db.rate_structure_variants.count_documents({"property_id": property_id})
        publish_jobs = await db.publish_jobs.count_documents({"property_id": property_id})

        has_config = len(configs) > 0
        has_creds = any(c.get("credentials_set") for c in configs)
        has_cert = any(c.get("certified") for c in configs)
        has_autopub = any(c.get("autopublish") for c in configs)

        steps_state = {
            "create_config": has_config,
            "enter_credentials": has_creds,
            "run_certification": has_cert,
            "create_payload": profiles > 0,
            "complete_mappings": mappings > 0,
            "verify_rate_structure": rate_struct > 0,
            "dry_run": publish_jobs > 0,
            "enable_autopublish": has_autopub,
        }
        completed = sum(1 for v in steps_state.values() if v)
        total = len(CHECKLIST_STEPS)
        return {
            "property_id": property_id,
            "steps": [{**s, "completed": steps_state[s["id"]]} for s in CHECKLIST_STEPS],
            "completed_count": completed,
            "total": total,
            "percentage": round(completed / total * 100, 1),
            "channel_health": round(completed / total * 100),
        }

    # ──────────────────────────────────────────────────────────────
    # PAYLOAD PROFILES (per-channel discovered fields/constraints)
    # ──────────────────────────────────────────────────────────────
    DEFAULT_FIELDS = [
        {"key": "rate", "type": "number", "required": True, "min": 0, "max": 999999},
        {"key": "availability", "type": "integer", "required": True, "min": 0, "max": 99},
        {"key": "min_los", "type": "integer", "required": False, "min": 1, "max": 30},
        {"key": "max_los", "type": "integer", "required": False, "min": 1, "max": 90},
        {"key": "closed_to_arrival", "type": "boolean", "required": False},
        {"key": "closed_to_departure", "type": "boolean", "required": False},
        {"key": "stop_sell", "type": "boolean", "required": False},
        {"key": "currency", "type": "enum",
         "values": ["GBP", "USD", "EUR", "TRY"], "required": True},
        {"key": "meal_plan", "type": "enum",
         "values": ["RO", "BB", "HB", "FB", "AI"], "required": False},
    ]

    @router.get("/payload-profiles/{property_id}")
    async def list_profiles(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.payload_profiles.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        return {"profiles": rows}

    @router.post("/payload-profiles/{property_id}/discover")
    async def discover_profile(property_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        channel_id = data.get("channel_id")
        if not channel_id:
            raise HTTPException(400, "channel_id required")
        # Mocked discovery — seeds sensible defaults per channel
        fields = list(DEFAULT_FIELDS)
        if channel_id == "booking_com":
            fields.append({"key": "genius_eligible", "type": "boolean", "required": False})
        if channel_id == "airbnb":
            fields.append({"key": "house_rules", "type": "text", "required": False, "max_length": 500})
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "channel_id": channel_id,
            "fields": fields,
            "field_count": len(fields),
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "discovered_by": current_user.get("email", ""),
        }
        await db.payload_profiles.update_one(
            {"property_id": property_id, "channel_id": channel_id},
            {"$set": doc}, upsert=True,
        )
        await _log_audit(db, property_id, "profile.discover",
                         {"channel_id": channel_id, "field_count": len(fields)},
                         current_user.get("email", ""))
        doc.pop("_id", None)
        return doc

    # ──────────────────────────────────────────────────────────────
    # PUBLISH JOBS (ARI distribution queue)
    # ──────────────────────────────────────────────────────────────
    @router.get("/publish-jobs/{property_id}")
    async def list_jobs(property_id: str, status: str = "", limit: int = 100,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        q: Dict = {"property_id": property_id}
        if status:
            q["status"] = status
        rows = await db.publish_jobs.find(q, {"_id": 0}) \
            .sort("created_at", -1).limit(min(limit, 500)).to_list(500)
        return {"jobs": rows, "count": len(rows)}

    @router.post("/publish-jobs/{property_id}")
    async def create_job(property_id: str, data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        channel_id = data.get("channel_id")
        if not channel_id:
            raise HTTPException(400, "channel_id required")
        now = datetime.now(timezone.utc)
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "channel_id": channel_id,
            "type": data.get("type") or "ari_push",
            "from_date": data.get("from_date", now.date().isoformat()),
            "to_date": data.get("to_date",
                                (now + timedelta(days=30)).date().isoformat()),
            "dry_run": bool(data.get("dry_run", False)),
            "status": "queued",
            "progress": 0,
            "items_total": data.get("items_total", 30),
            "items_ok": 0,
            "items_error": 0,
            "created_at": now.isoformat(),
            "created_by": current_user.get("email", ""),
        }
        await db.publish_jobs.insert_one(doc)
        doc.pop("_id", None)
        await _log_audit(db, property_id, "publish.create",
                         {"job_id": doc["id"], "channel_id": channel_id,
                          "dry_run": doc["dry_run"]},
                         current_user.get("email", ""))
        return doc

    @router.post("/publish-jobs/{job_id}/run")
    async def run_job(job_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Mock runner — flips to 'completed' with fake stats."""
        job = await db.publish_jobs.find_one({"id": job_id})
        if not job:
            raise HTTPException(404, "Job not found")
        total = job.get("items_total", 30)
        errors = random.randint(0, max(1, total // 15))
        ok = total - errors
        now = datetime.now(timezone.utc).isoformat()
        status = "completed" if errors == 0 else "partial"
        await db.publish_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": status, "progress": 100, "items_ok": ok,
                      "items_error": errors, "completed_at": now}},
        )
        await _log_audit(db, job.get("property_id", ""), "publish.run",
                         {"job_id": job_id, "ok": ok, "errors": errors,
                          "channel_id": job.get("channel_id")},
                         current_user.get("email", ""))
        return {"status": status, "items_ok": ok, "items_error": errors}

    @router.delete("/publish-jobs/{job_id}")
    async def delete_job(job_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.publish_jobs.delete_one({"id": job_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    # ──────────────────────────────────────────────────────────────
    # PRICE OVERRIDES (per-channel price adjustments)
    # ──────────────────────────────────────────────────────────────
    @router.get("/price-overrides/{property_id}")
    async def list_overrides(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.price_overrides.find({"property_id": property_id}, {"_id": 0}) \
            .sort("created_at", -1).to_list(500)
        return {"overrides": rows}

    @router.post("/price-overrides/{property_id}")
    async def create_override(property_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        required = ["channel_id", "room_type_id", "from_date", "to_date", "adjustment_type"]
        for f in required:
            if not data.get(f):
                raise HTTPException(400, f"{f} required")
        if data["adjustment_type"] not in ("percent", "fixed", "absolute"):
            raise HTTPException(400, "adjustment_type must be percent|fixed|absolute")
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "channel_id": data["channel_id"],
            "room_type_id": data["room_type_id"],
            "from_date": data["from_date"],
            "to_date": data["to_date"],
            "adjustment_type": data["adjustment_type"],
            "value": float(data.get("value", 0)),
            "reason": data.get("reason", ""),
            "active": bool(data.get("active", True)),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("email", ""),
        }
        await db.price_overrides.insert_one(doc)
        doc.pop("_id", None)
        await _log_audit(db, property_id, "override.create",
                         {"override_id": doc["id"], "channel_id": doc["channel_id"],
                          "type": doc["adjustment_type"], "value": doc["value"]},
                         current_user.get("email", ""))
        return doc

    @router.delete("/price-overrides/{override_id}")
    async def delete_override(override_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        ov = await db.price_overrides.find_one({"id": override_id}, {"_id": 0})
        if not ov:
            return {"status": "not_found"}
        await db.price_overrides.delete_one({"id": override_id})
        await _log_audit(db, ov.get("property_id", ""), "override.delete",
                         {"override_id": override_id}, current_user.get("email", ""))
        return {"status": "deleted"}

    # ──────────────────────────────────────────────────────────────
    # CHANNEL AUDIT LOG (distribution event history)
    # ──────────────────────────────────────────────────────────────
    @router.get("/channel-audit/{property_id}")
    async def list_channel_audit(property_id: str, event: str = "",
                                 search: str = "", limit: int = 200,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        q: Dict = {"property_id": property_id}
        if event:
            q["event"] = event
        if search:
            q["$or"] = [
                {"user_email": {"$regex": search, "$options": "i"}},
                {"event": {"$regex": search, "$options": "i"}},
            ]
        rows = await db.channel_audit.find(q, {"_id": 0}) \
            .sort("ts", -1).limit(min(limit, 500)).to_list(500)
        # Available event types for filter dropdown
        pipeline = [
            {"$match": {"property_id": property_id}},
            {"$group": {"_id": "$event", "count": {"$sum": 1}}},
        ]
        agg = await db.channel_audit.aggregate(pipeline).to_list(200)
        events = sorted([{"event": a["_id"], "count": a["count"]} for a in agg],
                        key=lambda x: x["event"])
        return {"rows": rows, "count": len(rows), "events": events}

    # ──────────────────────────────────────────────────────────────
    # BENCHMARK COCKPIT (STR-style Occupancy / ADR / RevPAR index)
    # ──────────────────────────────────────────────────────────────
    @router.get("/benchmark/{property_id}")
    async def get_benchmark(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        latest = await db.benchmark_snapshots.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("snapshot_date", -1).limit(30).to_list(30)
        latest.reverse()  # oldest first for trend
        # Open alerts = snapshots below threshold on latest 3
        alerts: List[Dict] = []
        if latest:
            last = latest[-1]
            if last.get("occupancy_index", 100) < 90:
                alerts.append({"id": str(uuid.uuid4()), "severity": "warning",
                               "metric": "occupancy",
                               "message": f"Occupancy index {last['occupancy_index']} below competitive set.",
                               "ts": last.get("snapshot_date")})
            if last.get("adr_index", 100) < 90:
                alerts.append({"id": str(uuid.uuid4()), "severity": "warning",
                               "metric": "adr",
                               "message": f"ADR index {last['adr_index']} below competitive set.",
                               "ts": last.get("snapshot_date")})
        current = latest[-1] if latest else None
        return {
            "property_id": property_id,
            "current": current,
            "recent": latest,
            "alerts": alerts,
        }

    @router.post("/benchmark/{property_id}/calculate")
    async def calculate_snapshot(property_id: str,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Compute a snapshot from real bookings (ADR/Occupancy) and a mocked
        compset to produce index values. Stores in benchmark_snapshots."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)

        # Our ADR & Occupancy from bookings
        bookings = await db.bookings.find(
            {"property_id": property_id,
             "check_in": {"$gte": window_start.date().isoformat()}},
            {"_id": 0, "total_amount": 1, "nights": 1, "check_in": 1, "check_out": 1},
        ).to_list(5000)
        room_count = await db.room_types.count_documents({"property_id": property_id}) or 1
        inventory_nights = room_count * 30
        total_revenue = sum(float(b.get("total_amount") or 0) for b in bookings)
        total_nights = sum(int(b.get("nights") or 1) for b in bookings)
        our_occupancy = round(total_nights / inventory_nights * 100, 1) if inventory_nights else 0
        our_adr = round(total_revenue / total_nights, 2) if total_nights else 0
        our_revpar = round(our_adr * our_occupancy / 100, 2)

        # Mocked compset ADR/Occ (could be wired to rate_scraper later)
        compset_occupancy = round(max(50, min(95, our_occupancy + random.uniform(-8, 8))), 1) or 75
        compset_adr = round(max(50, our_adr + random.uniform(-20, 20)), 2) or 120
        compset_revpar = round(compset_adr * compset_occupancy / 100, 2)

        occ_idx = round((our_occupancy / compset_occupancy) * 100, 1) if compset_occupancy else 100
        adr_idx = round((our_adr / compset_adr) * 100, 1) if compset_adr else 100
        rev_idx = round((our_revpar / compset_revpar) * 100, 1) if compset_revpar else 100

        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "snapshot_date": now.date().isoformat(),
            "occupancy_index": occ_idx,
            "adr_index": adr_idx,
            "revpar_index": rev_idx,
            "our_occupancy": our_occupancy,
            "our_adr": our_adr,
            "our_revpar": our_revpar,
            "compset_occupancy": compset_occupancy,
            "compset_adr": compset_adr,
            "compset_revpar": compset_revpar,
            "created_at": now.isoformat(),
        }
        await db.benchmark_snapshots.insert_one(doc)
        doc.pop("_id", None)
        await _log_audit(db, property_id, "benchmark.snapshot",
                         {"occ_idx": occ_idx, "adr_idx": adr_idx, "rev_idx": rev_idx},
                         current_user.get("email", ""))
        return doc

    # ──────────────────────────────────────────────────────────────
    # RATE STRUCTURE VARIANTS (occupancy × meal × cancel → OTA code)
    # ──────────────────────────────────────────────────────────────
    @router.get("/rate-variants/{property_id}")
    async def list_variants(property_id: str, channel_id: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        q: Dict = {"property_id": property_id}
        if channel_id:
            q["channel_id"] = channel_id
        rows = await db.rate_structure_variants.find(q, {"_id": 0}).to_list(500)
        return {"rows": rows, "count": len(rows)}

    @router.post("/rate-variants/{property_id}")
    async def upsert_variant(property_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        required = ["channel_id", "internal_segment", "channel_room_code",
                    "channel_rate_code"]
        for f in required:
            if not data.get(f):
                raise HTTPException(400, f"{f} required")
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "channel_id": data["channel_id"],
            "internal_segment": data["internal_segment"],
            "occupancy": data.get("occupancy", 2),
            "meal_plan": data.get("meal_plan", "RO"),
            "cancellation": data.get("cancellation", "FLEX"),
            "channel_room_code": data["channel_room_code"],
            "channel_rate_code": data["channel_rate_code"],
            "status": data.get("status", "active"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.rate_structure_variants.insert_one(doc)
        doc.pop("_id", None)
        await _log_audit(db, property_id, "variant.create",
                         {"channel_id": doc["channel_id"],
                          "code": doc["channel_rate_code"]},
                         current_user.get("email", ""))
        return doc

    @router.post("/rate-variants/{property_id}/auto-generate")
    async def auto_generate_variants(property_id: str, data: Dict,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate variants from existing channel_mappings × common permutations."""
        channel_id = data.get("channel_id") or ""
        map_q = {"property_id": property_id, "kind": "room"}
        if channel_id:
            map_q["channel_id"] = channel_id
        mappings = await db.channel_mappings.find(map_q, {"_id": 0}).to_list(500)
        combos = [
            ("2 pax + BB + Flex", 2, "BB", "FLEX", "BB_FLEX"),
            ("2 pax + RO + Non-Ref", 2, "RO", "NR", "RO_NR"),
            ("4 pax + BB + Flex", 4, "BB", "FLEX", "BB_FLEX_4PAX"),
        ]
        created = 0
        for m in mappings:
            for label, occ, meal, cancel, suffix in combos:
                code = f"{m.get('external_id','STD')}_{suffix}"
                await db.rate_structure_variants.update_one(
                    {"property_id": property_id, "channel_id": m["channel_id"],
                     "internal_segment": label,
                     "channel_room_code": m.get("external_id", "")},
                    {"$set": {
                        "id": str(uuid.uuid4()),
                        "property_id": property_id,
                        "channel_id": m["channel_id"],
                        "internal_segment": label,
                        "occupancy": occ,
                        "meal_plan": meal,
                        "cancellation": cancel,
                        "channel_room_code": m.get("external_id", ""),
                        "channel_rate_code": code,
                        "status": "active",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
                created += 1
        await _log_audit(db, property_id, "variant.auto_generate",
                         {"count": created, "channel_id": channel_id or "all"},
                         current_user.get("email", ""))
        return {"generated": created, "from_mappings": len(mappings)}

    @router.delete("/rate-variants/{variant_id}")
    async def delete_variant(variant_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        v = await db.rate_structure_variants.find_one({"id": variant_id}, {"_id": 0})
        if not v:
            return {"status": "not_found"}
        await db.rate_structure_variants.delete_one({"id": variant_id})
        await _log_audit(db, v.get("property_id", ""), "variant.delete",
                         {"variant_id": variant_id}, current_user.get("email", ""))
        return {"status": "deleted"}

    # ──────────────────────────────────────────────────────────────
    # DEMO SEED (one-click populate Channel Hub for live demo)
    # ──────────────────────────────────────────────────────────────
    @router.post("/channel-hub/{property_id}/seed-demo")
    async def seed_demo(property_id: str,
                        current_user: dict = Depends(require_roles("admin"))):
        """Seeds configs + a payload profile + a completed publish job + audit rows
        for a convincing demo state. Safe to call repeatedly (idempotent upsert)."""
        email = current_user.get("email", "system")
        now = datetime.now(timezone.utc)
        demo_channels = [
            ("booking_com", "Booking.com", "rest_api"),
            ("expedia", "Expedia", "rest_api"),
            ("airbnb", "Airbnb", "oauth2"),
        ]
        for cid, name, conn in demo_channels:
            await db.channel_configs.update_one(
                {"property_id": property_id, "channel_id": cid},
                {"$set": {"property_id": property_id, "channel_id": cid,
                          "name": name, "connector": conn,
                          "property_code": f"PROP-{cid.upper()}-001",
                          "credentials_set": True, "certified": True,
                          "autopublish": cid == "booking_com",
                          "status": "live" if cid == "booking_com" else "certified",
                          "updated_at": now.isoformat()},
                 "$setOnInsert": {"id": str(uuid.uuid4()),
                                  "created_at": now.isoformat(),
                                  "created_by": email}},
                upsert=True,
            )
            await db.payload_profiles.update_one(
                {"property_id": property_id, "channel_id": cid},
                {"$set": {"property_id": property_id, "channel_id": cid,
                          "fields": DEFAULT_FIELDS,
                          "field_count": len(DEFAULT_FIELDS),
                          "discovered_at": now.isoformat(),
                          "discovered_by": email},
                 "$setOnInsert": {"id": str(uuid.uuid4())}},
                upsert=True,
            )
        # One completed publish job for dashboard KPIs
        for i, (cid, _, _) in enumerate(demo_channels):
            job_doc = {
                "id": str(uuid.uuid4()),
                "property_id": property_id, "channel_id": cid,
                "type": "ari_push", "from_date": now.date().isoformat(),
                "to_date": (now + timedelta(days=30)).date().isoformat(),
                "dry_run": False, "status": "completed", "progress": 100,
                "items_total": 30, "items_ok": 30 - i, "items_error": i,
                "created_at": (now - timedelta(hours=i * 3)).isoformat(),
                "completed_at": (now - timedelta(hours=i * 3 - 1)).isoformat(),
                "created_by": email,
            }
            await db.publish_jobs.insert_one(job_doc)
        # Benchmark snapshots for a trend
        for days_ago in range(5, -1, -1):
            snap_doc = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "snapshot_date": (now - timedelta(days=days_ago)).date().isoformat(),
                "occupancy_index": round(95 + random.uniform(-5, 8), 1),
                "adr_index": round(105 + random.uniform(-8, 8), 1),
                "revpar_index": round(100 + random.uniform(-10, 10), 1),
                "our_occupancy": round(78 + random.uniform(-5, 5), 1),
                "our_adr": round(145 + random.uniform(-15, 15), 2),
                "our_revpar": round(110 + random.uniform(-10, 10), 2),
                "compset_occupancy": round(76 + random.uniform(-3, 3), 1),
                "compset_adr": round(140 + random.uniform(-10, 10), 2),
                "compset_revpar": round(106 + random.uniform(-5, 5), 2),
                "created_at": (now - timedelta(days=days_ago)).isoformat(),
            }
            await db.benchmark_snapshots.insert_one(snap_doc)
        await _log_audit(db, property_id, "demo.seed",
                         {"channels": [c[0] for c in demo_channels]}, email)
        return {"status": "seeded", "channels": len(demo_channels)}

    # ──────────────────────────────────────────────────────────────
    # NIGHTLY DRIFT — surface results of the scheduled dry-run publish
    # ──────────────────────────────────────────────────────────────
    @router.get("/nightly-drift/{property_id}")
    async def latest_drift(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.nightly_drift_snapshots.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("ran_at", -1).limit(14).to_list(14)
        return {"latest": rows[0] if rows else None, "history": rows}

    @router.post("/nightly-drift/{property_id}/run-now")
    async def run_drift_now(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        # Import inside to avoid circular init ordering surprises
        from routes.channel_hub import nightly_dry_publish as _run
        result = await _run(db, property_id)
        return {"status": "ok", **result}

    # ──────────────────────────────────────────────────────────────
    # HUB DASHBOARD — single endpoint for Channel Manager Dashboard tiles
    # ──────────────────────────────────────────────────────────────
    @router.get("/channel-hub/{property_id}/dashboard")
    async def hub_dashboard(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        configs = await db.channel_configs.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        active_channels = sum(1 for c in configs if c.get("status") in ("certified", "live"))
        # Recent jobs
        jobs = await db.publish_jobs.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("created_at", -1).limit(5).to_list(5)
        ok = sum(j.get("items_ok", 0) for j in jobs)
        err = sum(j.get("items_error", 0) for j in jobs)
        sync_pct = round(ok / (ok + err) * 100, 1) if (ok + err) else 99.9
        sync_label = "Good" if sync_pct >= 99 else "Warn" if sync_pct >= 95 else "Fail"
        # Recent audit
        recent = await db.channel_audit.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("ts", -1).limit(10).to_list(10)
        # Channel bookings last 7 days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        chan_bookings = await db.bookings.count_documents({
            "property_id": property_id,
            "created_at": {"$gte": cutoff},
        })
        mappings = await db.channel_mappings.count_documents({"property_id": property_id})
        total_mappings_expected = max(1, len(configs) * 6)
        mapping_coverage = round(min(100, mappings / total_mappings_expected * 100), 1)
        return {
            "active_channels": active_channels,
            "sync_health_pct": sync_pct,
            "sync_health_label": sync_label,
            "channel_bookings_7d": chan_bookings,
            "mapping_coverage_pct": mapping_coverage,
            "recent_activity": recent,
            "recent_jobs": jobs,
            "configs_count": len(configs),
        }

    return router


# ──────────────────────────────────────────────────────────────
# SCHEDULER JOB — nightly dry-run publish for all live channels
# (imported by server.py and wired into JOB_HANDLERS via scheduler)
# ──────────────────────────────────────────────────────────────
async def nightly_dry_publish(db, property_id: str) -> dict:
    """For each live/certified channel config under this property, create a
    dry-run publish job, run it, and record drift. Designed to run nightly.

    Returns: {channels_checked, total_items, total_errors, drift_alerts}
    Drift alert = any channel returning >=5% items_error in the dry-run.
    """
    import random  # local import — scheduler runs in background loop
    configs_q = {"property_id": property_id,
                 "status": {"$in": ["live", "certified"]}}
    configs = await db.channel_configs.find(configs_q, {"_id": 0}).to_list(50)
    now = datetime.now(timezone.utc)
    results = []
    drift_alerts = []
    total_items = 0
    total_errors = 0

    for cfg in configs:
        job = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "channel_id": cfg["channel_id"],
            "type": "ari_push",
            "from_date": now.date().isoformat(),
            "to_date": (now + timedelta(days=30)).date().isoformat(),
            "dry_run": True,
            "status": "running",
            "progress": 0,
            "items_total": 30,
            "items_ok": 0,
            "items_error": 0,
            "triggered_by": "scheduler:nightly_dry_publish",
            "created_at": now.isoformat(),
        }
        await db.publish_jobs.insert_one(job)

        # Simulated run (same model as run_job endpoint)
        errors = random.randint(0, 4)
        ok = job["items_total"] - errors
        status = "completed" if errors == 0 else "partial"
        err_pct = round(errors / job["items_total"] * 100, 1)
        await db.publish_jobs.update_one(
            {"id": job["id"]},
            {"$set": {"status": status, "progress": 100,
                      "items_ok": ok, "items_error": errors,
                      "completed_at": datetime.now(timezone.utc).isoformat()}}
        )
        total_items += job["items_total"]
        total_errors += errors
        results.append({"channel_id": cfg["channel_id"], "ok": ok,
                        "errors": errors, "err_pct": err_pct,
                        "status": status})
        if err_pct >= 5:
            drift_alerts.append({"channel_id": cfg["channel_id"],
                                 "err_pct": err_pct, "errors": errors})

    # Audit row (one per scheduler run)
    await db.channel_audit.insert_one({
        "id": str(uuid.uuid4()),
        "property_id": property_id,
        "event": "publish.nightly_dry_run",
        "details": {"channels": len(configs), "total_items": total_items,
                    "total_errors": total_errors,
                    "drift_alerts": len(drift_alerts),
                    "results": results},
        "user_email": "scheduler",
        "ts": now.isoformat(),
    })
    # Store a concise snapshot for the Benchmark Cockpit to surface
    await db.nightly_drift_snapshots.insert_one({
        "id": str(uuid.uuid4()),
        "property_id": property_id,
        "ran_at": now.isoformat(),
        "channels_checked": len(configs),
        "total_items": total_items,
        "total_errors": total_errors,
        "drift_alerts": drift_alerts,
        "results": results,
    })
    return {"channels_checked": len(configs), "total_items": total_items,
            "total_errors": total_errors, "drift_alerts": len(drift_alerts)}
