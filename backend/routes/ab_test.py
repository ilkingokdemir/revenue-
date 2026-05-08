"""
A/B Test Engine (P1)
--------------------
Lightweight experimentation framework for the booking widget and direct
website. Operator defines an experiment with named variants and a weight
distribution (e.g. control 50% / hero_v2 50%).

Visitor SDK calls `/ab/assign` once per session — server returns deterministic
assignment (hash of session_id + experiment_key + salt to keep splits stable
across page loads). Conversion events post via `/ab/track`.

Endpoints
---------
POST   /ab/experiments                    Create experiment
GET    /ab/experiments                    List experiments for property
POST   /ab/experiments/{id}/toggle        Enable / disable
DELETE /ab/experiments/{id}               Delete (cascade results)
POST   /ab/assign                         Public — pick variant for a session
POST   /ab/track                          Public — record event (impression / convert)
GET    /ab/experiments/{id}/results       Conversion-rate per variant + p-value flag
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import hashlib
import math
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wilson_lower(p: float, n: int) -> float:
    """Wilson score 95% CI lower bound — handy for ranking variants."""
    if n == 0:
        return 0.0
    z = 1.96
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


def create_ab_test_router(db, require_roles):
    router = APIRouter()

    @router.post("/ab/experiments")
    async def create_experiment(data: Dict,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        key = (data.get("key") or "").strip().lower().replace(" ", "_")
        name = (data.get("name") or key).strip()
        variants = data.get("variants") or []
        if not property_id or not key or len(variants) < 2:
            raise HTTPException(400, "property_id, key and >=2 variants required")
        # Validate variants — list of {"name": str, "weight": int, "payload": dict}
        normalised: List[Dict] = []
        total = 0
        for v in variants:
            n = (v.get("name") or "").strip()
            w = int(v.get("weight") or 1)
            if not n or w <= 0:
                raise HTTPException(400, "each variant needs name + positive weight")
            normalised.append({"name": n, "weight": w, "payload": v.get("payload") or {}})
            total += w

        existing = await db.ab_experiments.find_one({"property_id": property_id, "key": key}, {"_id": 0})
        if existing:
            raise HTTPException(409, f"Experiment '{key}' already exists for this property")
        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "key": key,
            "name": name,
            "description": data.get("description", ""),
            "goal_event": data.get("goal_event", "booking_completed"),
            "variants": normalised,
            "weight_total": total,
            "active": True,
            "salt": uuid.uuid4().hex[:8],
            "created_at": _now(),
            "created_by": current_user.get("name", "Staff"),
        }
        await db.ab_experiments.insert_one(dict(record))
        record.pop("_id", None)
        return {"ok": True, "experiment": record}

    @router.get("/ab/experiments")
    async def list_experiments(property_id: str,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.ab_experiments.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.post("/ab/experiments/{exp_id}/toggle")
    async def toggle(exp_id: str, data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        active = bool(data.get("active", True))
        result = await db.ab_experiments.update_one({"id": exp_id}, {"$set": {"active": active, "toggled_at": _now()}})
        if result.matched_count == 0:
            raise HTTPException(404, "Experiment not found")
        return {"ok": True, "active": active}

    @router.delete("/ab/experiments/{exp_id}")
    async def delete_experiment(exp_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.ab_experiments.delete_one({"id": exp_id})
        await db.ab_events.delete_many({"experiment_id": exp_id})
        return {"ok": True}

    @router.post("/ab/assign")
    async def assign(data: Dict):
        property_id = (data.get("property_id") or "").strip()
        key = (data.get("key") or "").strip().lower()
        session_id = (data.get("session_id") or "").strip()
        if not property_id or not key or not session_id:
            raise HTTPException(400, "property_id, key, session_id required")
        exp = await db.ab_experiments.find_one({"property_id": property_id, "key": key, "active": True}, {"_id": 0})
        if not exp:
            return {"assigned": False, "variant": None}
        h = int(hashlib.md5(f"{exp['salt']}|{key}|{session_id}".encode()).hexdigest()[:8], 16)
        bucket = h % max(exp["weight_total"], 1)
        running = 0
        chosen = exp["variants"][0]
        for v in exp["variants"]:
            running += v["weight"]
            if bucket < running:
                chosen = v
                break
        # Optional: log impression
        if data.get("track_impression", True):
            await db.ab_events.insert_one({
                "id": str(uuid.uuid4()),
                "experiment_id": exp["id"],
                "key": key,
                "variant": chosen["name"],
                "session_id": session_id,
                "event": "impression",
                "at": _now(),
            })
        return {"assigned": True, "variant": chosen["name"], "payload": chosen.get("payload", {}),
                 "experiment_id": exp["id"]}

    @router.post("/ab/track")
    async def track(data: Dict):
        experiment_id = (data.get("experiment_id") or "").strip()
        key = (data.get("key") or "").strip().lower()
        session_id = (data.get("session_id") or "").strip()
        variant = (data.get("variant") or "").strip()
        event = (data.get("event") or "convert").strip()
        if not experiment_id and not key:
            raise HTTPException(400, "experiment_id or key required")
        if not session_id or not variant:
            raise HTTPException(400, "session_id, variant required")
        exp = await db.ab_experiments.find_one({"$or": [{"id": experiment_id}, {"key": key}]}, {"_id": 0})
        if not exp:
            raise HTTPException(404, "Experiment not found")
        await db.ab_events.insert_one({
            "id": str(uuid.uuid4()),
            "experiment_id": exp["id"],
            "key": exp["key"],
            "variant": variant,
            "session_id": session_id,
            "event": event,
            "value": float(data.get("value") or 0),
            "at": _now(),
        })
        return {"ok": True}

    @router.get("/ab/experiments/{exp_id}/results")
    async def results(exp_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        exp = await db.ab_experiments.find_one({"id": exp_id}, {"_id": 0})
        if not exp:
            raise HTTPException(404, "Experiment not found")
        events = await db.ab_events.find({"experiment_id": exp_id}, {"_id": 0}).to_list(200000)
        per: Dict[str, Dict[str, float]] = {v["name"]: {"impressions": 0, "conversions": 0, "value": 0.0} for v in exp["variants"]}
        for e in events:
            cell = per.setdefault(e["variant"], {"impressions": 0, "conversions": 0, "value": 0.0})
            if e["event"] == "impression":
                cell["impressions"] += 1
            elif e["event"] in ("convert", "booking_completed"):
                cell["conversions"] += 1
                cell["value"] += float(e.get("value") or 0)
        out = []
        for name, c in per.items():
            imp = max(int(c["impressions"]), 0)
            conv = int(c["conversions"])
            cr = round(conv * 100 / max(imp, 1), 2) if imp else 0
            out.append({
                "variant": name,
                "impressions": imp,
                "conversions": conv,
                "conversion_rate_pct": cr,
                "wilson_lower_pct": round(_wilson_lower(conv / imp, imp) * 100, 2) if imp else 0,
                "total_value": round(c["value"], 2),
                "value_per_visitor": round(c["value"] / imp, 2) if imp else 0,
            })
        # Mark leader (highest wilson_lower)
        if out:
            best = max(out, key=lambda r: r["wilson_lower_pct"])
            for r in out:
                r["leader"] = (r["variant"] == best["variant"] and best["impressions"] >= 30)
        return {"experiment": exp, "results": out, "total_events": len(events)}

    return router
