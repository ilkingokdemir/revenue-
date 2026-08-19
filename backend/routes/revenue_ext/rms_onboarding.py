"""RMS-only müşteri hızlı kurulum (RoomPriceGenie paritesi) + Autopilot/Co-Pilot modu."""
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_rms_onboarding_router(db, require_roles):
    router = APIRouter(prefix="/rms", tags=["rms"])
    ROLES = ("admin", "manager")

    async def _setup(pid: str) -> dict:
        return await db.rms_setup.find_one({"property_id": pid}, {"_id": 0}) or {"property_id": pid}

    async def _room_types(pid: str) -> list:
        q = {"property_id": pid} if pid != "default" else {"$or": [{"property_id": pid}, {"property_id": None}]}
        return await db.room_types.find(q, {"_id": 0, "id": 1, "name": 1, "base_rate": 1, "base_price": 1, "total": 1}).to_list(50)

    async def _derive_rates(pid: str, setup: dict) -> list:
        """Baz oda fiyatından offset kuralıyla tüm oda tipi fiyatlarını türet (guardrail kırpmalı)."""
        base_id = setup.get("base_room_type_id")
        base_price = float(setup.get("base_price") or 0)
        if not base_id or base_price <= 0:
            return []
        lo = float(setup.get("min_rate") or 0)
        hi = float(setup.get("max_rate") or 0)
        offsets = {o.get("room_type_id"): o for o in (setup.get("offsets") or [])}
        derived = []
        for rt in await _room_types(pid):
            if rt["id"] == base_id:
                rate = base_price
            else:
                o = offsets.get(rt["id"]) or {}
                val = float(o.get("value") or 0)
                rate = base_price * (1 + val / 100.0) if o.get("mode") == "pct" else base_price + val
            if lo > 0:
                rate = max(rate, lo)
            if hi > lo > 0 or (hi > 0 and lo <= 0):
                rate = min(rate, hi) if hi > 0 else rate
            rate = round(rate, 2)
            await db.room_types.update_one({"id": rt["id"]}, {"$set": {"base_rate": rate, "updated_at": now_iso()}})
            derived.append({"room_type_id": rt["id"], "name": rt.get("name"), "rate": rate})
        return derived

    # ---------------- SETUP STATE ----------------
    @router.get("/setup/{pid}")
    async def get_setup(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        setup = await _setup(pid)
        comps = await db.compset.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1}).to_list(30)
        return {"setup": setup, "room_types": await _room_types(pid), "compset": comps}

    @router.post("/setup/{pid}/rooms")
    async def save_rooms(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        base_id = data.get("base_room_type_id")
        base_price = float(data.get("base_price") or 0)
        if not base_id or base_price <= 0:
            raise HTTPException(400, "base_room_type_id ve base_price zorunlu")
        upd = {"base_room_type_id": base_id, "base_price": base_price,
               "offsets": data.get("offsets") or [], "updated_at": now_iso()}
        await db.rms_setup.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        derived = await _derive_rates(pid, {**(await _setup(pid))})
        return {"ok": True, "derived": derived}

    @router.post("/setup/{pid}/guardrails")
    async def save_guardrails(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        lo, hi = float(data.get("min_rate") or 0), float(data.get("max_rate") or 0)
        if lo <= 0 or hi <= lo:
            raise HTTPException(400, "min_rate > 0 ve max_rate > min_rate olmalı")
        await db.rms_setup.update_one({"property_id": pid},
                                      {"$set": {"min_rate": lo, "max_rate": hi, "updated_at": now_iso()}}, upsert=True)
        return {"ok": True, "min_rate": lo, "max_rate": hi}

    @router.post("/setup/{pid}/compset")
    async def save_compset(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        names = list(dict.fromkeys(n.strip() for n in (data.get("names") or []) if n and n.strip()))
        existing = {c["name"] for c in await db.compset.find({"property_id": pid}, {"_id": 0, "name": 1}).to_list(100)}
        added = 0
        for n in names:
            if n in existing:
                continue
            await db.compset.insert_one({"id": str(uuid.uuid4()), "property_id": pid, "name": n,
                                         "source": "rms_wizard", "added_by": _u.get("name", ""), "added_at": now_iso()})
            added += 1
        total = await db.compset.count_documents({"property_id": pid})
        return {"ok": True, "added": added, "total": total}

    @router.post("/setup/{pid}/data-source")
    async def save_data_source(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        src = data.get("source")
        if src not in ("pms", "csv", "manual"):
            raise HTTPException(422, "source: pms|csv|manual")
        await db.rms_setup.update_one({"property_id": pid},
                                      {"$set": {"data_source": src, "updated_at": now_iso()}}, upsert=True)
        return {"ok": True, "source": src}

    @router.post("/setup/{pid}/mode")
    async def save_mode(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        mode = data.get("mode")
        if mode not in ("autopilot", "copilot", "manual"):
            raise HTTPException(422, "mode: autopilot|copilot|manual")
        ppd = max(1, min(24, int(data.get("pushes_per_day") or 1)))
        await db.rms_setup.update_one({"property_id": pid},
                                      {"$set": {"mode": mode, "pushes_per_day": ppd, "updated_at": now_iso()}}, upsert=True)
        await db.pricing_autopilot.update_one({"property_id": pid},
                                              {"$set": {"property_id": pid, "enabled": mode != "manual",
                                                        "auto_apply": mode == "autopilot",
                                                        "pushes_per_day": ppd, "updated_at": now_iso()}}, upsert=True)
        return {"ok": True, "mode": mode, "pushes_per_day": ppd}

    # ---------------- GO-LIVE SAĞLIK SKORU ----------------
    @router.get("/golive/{pid}")
    async def golive(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        setup = await _setup(pid)
        rts = await _room_types(pid)
        priced = bool(rts) and all(float(r.get("base_rate") or r.get("base_price") or 0) > 0 for r in rts)
        comp_n = await db.compset.count_documents({"property_id": pid})
        last_bk = await db.bookings.find_one({"property_id": pid}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
        fresh = setup.get("data_source") == "manual"
        if not fresh and last_bk and last_bk.get("created_at"):
            try:
                dt = datetime.fromisoformat(str(last_bk["created_at"]).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                fresh = (datetime.now(timezone.utc) - dt) < timedelta(hours=48)
            except Exception:
                fresh = False
        checks = [
            {"key": "rooms_priced", "label": "Tüm oda tipleri fiyatlandı", "ok": priced},
            {"key": "offsets", "label": "Baz fiyat + oda tipi farkları tanımlı", "ok": bool(setup.get("base_room_type_id"))},
            {"key": "guardrails", "label": "Min/Max fiyat koruması aktif", "ok": float(setup.get("min_rate") or 0) > 0},
            {"key": "compset", "label": "En az 2 rakip tanımlı", "ok": comp_n >= 2},
            {"key": "data_source", "label": "Veri kaynağı seçildi", "ok": bool(setup.get("data_source"))},
            {"key": "mode", "label": "Fiyatlama modu seçildi", "ok": bool(setup.get("mode"))},
            {"key": "data_fresh", "label": "Veri akışı taze (<48 saat)", "ok": bool(fresh)},
        ]
        score = round(sum(1 for c in checks if c["ok"]) / len(checks) * 100)
        return {"score": score, "ready": score >= 80, "checks": checks,
                "mode": setup.get("mode"), "compset_count": comp_n}

    # ---------------- CO-PILOT ÖNERİ KUYRUĞU ----------------
    @router.post("/copilot/generate/{pid}")
    async def generate_recs(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        setup = await _setup(pid)
        base = float(setup.get("base_price") or 0)
        if base <= 0:
            raise HTTPException(400, "Önce sihirbazda baz fiyat tanımlayın")
        lo = float(setup.get("min_rate") or 0) or base * 0.6
        hi = float(setup.get("max_rate") or 0) or base * 2.5
        total_rooms = await db.rooms.count_documents({"property_id": pid}) or \
            sum(int(r.get("total") or 0) for r in await _room_types(pid)) or 10
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=14)
        bks = await db.bookings.find(
            {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
             "check_out": {"$gt": today.isoformat()}, "check_in": {"$lt": end.isoformat()}},
            {"_id": 0, "check_in": 1, "check_out": 1}).to_list(3000)
        auto = setup.get("mode") == "autopilot"
        created = []
        for i in range(14):
            d = (today + timedelta(days=i)).isoformat()
            occ = sum(1 for b in bks if str(b.get("check_in")) <= d < str(b.get("check_out"))) / max(total_rooms, 1)
            suggested = round(min(max(base * (1 + (occ - 0.5) * 0.4), lo), hi), 2)
            if abs(suggested - base) / base < 0.01:
                continue
            status = "applied" if auto else "pending"
            rec = {"id": str(uuid.uuid4()), "property_id": pid, "date": d,
                   "occupancy_pct": round(occ * 100, 1), "current_rate": base, "suggested_rate": suggested,
                   "reason": f"Doluluk %{occ*100:.0f} — {'talep yüksek, artış' if suggested > base else 'talep düşük, indirim'}",
                   "status": status, "created_at": now_iso()}
            await db.copilot_queue.update_one({"property_id": pid, "date": d, "status": {"$in": ["pending", "applied"]}},
                                              {"$set": rec}, upsert=True)
            if auto:
                await db.rate_overrides.update_one(
                    {"property_id": pid, "date": d, "room_type_id": ""},
                    {"$set": {"property_id": pid, "room_type_id": "", "date": d,
                              "custom_rate": suggested, "set_by": "rms_autopilot",
                              "reason": rec["reason"], "updated_at": now_iso()}}, upsert=True)
            created.append(rec)
        return {"ok": True, "mode": setup.get("mode") or "manual", "auto_applied": auto,
                "count": len(created), "recommendations": created}

    @router.get("/copilot/queue/{pid}")
    async def get_queue(pid: str, status: str = "pending", _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.copilot_queue.find({"property_id": pid, "status": status},
                                           {"_id": 0}).sort("date", 1).to_list(60)
        return {"queue": rows, "count": len(rows)}

    @router.post("/copilot/queue/{pid}/decide")
    async def decide(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        ids = data.get("ids") or []
        action = data.get("action")
        if action not in ("approve", "reject") or not ids:
            raise HTTPException(422, "ids ve action (approve|reject) zorunlu")
        applied = 0
        for rid in ids:
            rec = await db.copilot_queue.find_one({"id": rid, "property_id": pid, "status": "pending"}, {"_id": 0})
            if not rec:
                continue
            new_status = "approved" if action == "approve" else "rejected"
            await db.copilot_queue.update_one({"id": rid}, {"$set": {
                "status": new_status, "decided_by": _u.get("name", ""), "decided_at": now_iso()}})
            if action == "approve":
                await db.rate_overrides.update_one(
                    {"property_id": pid, "date": rec["date"], "room_type_id": ""},
                    {"$set": {"property_id": pid, "room_type_id": "", "date": rec["date"],
                              "custom_rate": rec["suggested_rate"], "set_by": "rms_copilot",
                              "reason": rec.get("reason", ""), "updated_at": now_iso()}}, upsert=True)
                applied += 1
        return {"ok": True, "action": action, "applied": applied}

    return router
