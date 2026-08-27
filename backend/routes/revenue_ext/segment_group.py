"""Segment Fiyat Katmanı (Open Pricing offsetleri) + Grup Wish/Walk Onay Akışı."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import uuid

DEFAULT_SEGMENTS = [
    {"code": "direct", "name": "Direkt (web)", "offset_pct": 0.0, "active": True},
    {"code": "corporate", "name": "Kurumsal", "offset_pct": -10.0, "active": True},
    {"code": "loyalty", "name": "Sadakat üyesi", "offset_pct": -5.0, "active": True},
    {"code": "ota", "name": "OTA", "offset_pct": 3.0, "active": True},
]


def _now():
    return datetime.now(timezone.utc)


def create_segment_pricing_router(db, require_roles):
    router = APIRouter(prefix="/segment-pricing", tags=["segment-pricing"])
    ROLES = ("admin", "manager")

    async def _segments(pid):
        doc = await db.segment_offsets.find_one({"property_id": pid}, {"_id": 0})
        return (doc or {}).get("segments") or [dict(s) for s in DEFAULT_SEGMENTS]

    @router.get("/{pid}")
    async def get_segments(pid: str, date: str = "", _u: dict = Depends(require_roles(*ROLES))):
        segs = await _segments(pid)
        base = 0.0
        if date:
            ov = await db.rate_overrides.find_one(
                {"property_id": pid, "date": date, "custom_rate": {"$gt": 0}}, {"_id": 0})
            if ov:
                base = float(ov["custom_rate"])
            else:
                rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0, "base_price": 1},
                                                  sort=[("base_price", 1)])
                base = float((rt or {}).get("base_price", 0))
        rates = [{**s, "rate": round(base * (1 + s["offset_pct"] / 100), 2) if base else None}
                 for s in segs]
        return {"segments": rates, "base_rate": base, "date": date}

    @router.put("/{pid}")
    async def save_segments(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        segs = data.get("segments")
        if not isinstance(segs, list) or not segs:
            raise HTTPException(422, "segments listesi gerekli")
        clean = [{"code": s.get("code", "")[:20], "name": s.get("name", "")[:40],
                  "offset_pct": max(-50.0, min(float(s.get("offset_pct", 0)), 50.0)),
                  "active": bool(s.get("active", True))} for s in segs[:10]]
        await db.segment_offsets.update_one(
            {"property_id": pid}, {"$set": {"segments": clean, "updated_at": _now().isoformat()}},
            upsert=True)
        return {"ok": True, "segments": clean}

    return router


def create_group_approval_router(db, require_roles):
    router = APIRouter(prefix="/group-approval", tags=["group-approval"])
    ROLES = ("admin", "manager")
    CHAIN = ["revenue", "sales"]
    DEFAULT_STEP_DEPTS = {"revenue": ["revenue", "management"],
                          "sales": ["sales", "management"]}

    async def _step_depts(pid: str) -> Dict:
        cfg = await db.group_approval_config.find_one({"property_id": pid}, {"_id": 0})
        return (cfg or {}).get("steps") or DEFAULT_STEP_DEPTS

    @router.get("/{pid}/config")
    async def get_config(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return {"steps": await _step_depts(pid), "chain": CHAIN,
                "note": "Her onay adımını sadece listedeki departmanlar (veya admin) onaylayabilir."}

    @router.put("/{pid}/config")
    async def put_config(pid: str, data: Dict, u: dict = Depends(require_roles("admin"))):
        steps = data.get("steps") or {}
        clean = {}
        for step in CHAIN:
            depts = steps.get(step)
            if not isinstance(depts, list) or not depts:
                depts = DEFAULT_STEP_DEPTS[step]
            clean[step] = [str(d).strip().lower()[:30] for d in depts[:8] if str(d).strip()]
        await db.group_approval_config.update_one(
            {"property_id": pid},
            {"$set": {"steps": clean, "updated_by": u.get("name") or u.get("email", ""),
                      "updated_at": _now().isoformat()}}, upsert=True)
        return {"ok": True, "steps": clean}

    @router.get("/{pid}")
    async def list_quotes(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        qs = await db.group_quotes.find({"property_id": pid}, {"_id": 0}).sort(
            "created_at", -1).to_list(50)
        return {"quotes": qs, "chain": CHAIN}

    @router.post("/{pid}/quotes")
    async def create_quote(pid: str, data: Dict, u: dict = Depends(require_roles(*ROLES))):
        wish = float(data.get("wish_price", 0) or 0)
        walk = float(data.get("walk_price", 0) or 0)
        if wish <= 0 or walk <= 0 or walk >= wish:
            raise HTTPException(422, "Wish fiyatı > Walk fiyatı > 0 olmalı")
        q = {"id": str(uuid.uuid4()), "property_id": pid,
             "group_name": (data.get("group_name") or "")[:80],
             "rooms": max(1, int(data.get("rooms", 1) or 1)),
             "nights": max(1, int(data.get("nights", 1) or 1)),
             "check_in": data.get("check_in", ""),
             "wish_price": wish, "walk_price": walk,
             "wish_total": round(wish * int(data.get("rooms", 1)) * int(data.get("nights", 1)), 2),
             "walk_total": round(walk * int(data.get("rooms", 1)) * int(data.get("nights", 1)), 2),
             "notes": (data.get("notes") or "")[:300],
             "status": "pending_revenue", "approvals": [],
             "created_by": u.get("name") or u.get("email", ""),
             "created_at": _now().isoformat()}
        await db.group_quotes.insert_one(dict(q))
        q.pop("_id", None)
        return q

    @router.post("/{pid}/quotes/{qid}/approve")
    async def approve(pid: str, qid: str, data: Dict, u: dict = Depends(require_roles(*ROLES))):
        role = data.get("role", "revenue")
        q = await db.group_quotes.find_one({"id": qid, "property_id": pid}, {"_id": 0})
        if not q:
            raise HTTPException(404, "Teklif bulunamadı")
        expected = f"pending_{role}"
        if q["status"] != expected:
            raise HTTPException(422, f"Sıra bu adımda değil (durum: {q['status']})")
        if u.get("role") != "admin":
            allowed = (await _step_depts(pid)).get(role, [])
            if (u.get("department") or "").lower() not in allowed:
                raise HTTPException(
                    403, f"Bu adımı sadece {' / '.join(allowed)} departmanı onaylayabilir "
                         f"(sizin departmanınız: {u.get('department') or 'tanımsız'})")
        approvals = q["approvals"] + [{"role": role, "by": u.get("name") or u.get("email", ""),
                                       "at": _now().isoformat()}]
        idx = CHAIN.index(role)
        new_status = f"pending_{CHAIN[idx + 1]}" if idx + 1 < len(CHAIN) else "approved"
        await db.group_quotes.update_one(
            {"id": qid}, {"$set": {"status": new_status, "approvals": approvals}})
        return {"ok": True, "status": new_status}

    @router.post("/{pid}/quotes/{qid}/reject")
    async def reject(pid: str, qid: str, data: Dict = None, u: dict = Depends(require_roles(*ROLES))):
        r = await db.group_quotes.update_one(
            {"id": qid, "property_id": pid, "status": {"$regex": "^pending"}},
            {"$set": {"status": "rejected",
                      "rejected_by": u.get("name") or u.get("email", ""),
                      "reject_reason": ((data or {}).get("reason") or "")[:200],
                      "rejected_at": _now().isoformat()}})
        if r.matched_count == 0:
            raise HTTPException(404, "Bekleyen teklif bulunamadı")
        return {"ok": True}

    return router
