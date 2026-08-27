"""Toplantı Alanı Dinamik Fiyatlama — talep + F&B/AV marjına göre salon fiyatı (Duetto OpenSpace paritesi)."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict
import uuid

ACTOR = "space-rms"
DOW_W = {0: 1.0, 1: 1.15, 2: 1.15, 3: 1.15, 4: 1.0, 5: 1.1, 6: 0.85}
DOW_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def create_space_rms_router(db, require_roles):
    router = APIRouter(tags=["space-rms"])
    ROLES = ("admin", "manager")

    async def _suggestions(pid: str, days: int):
        spaces = await db.spaces.find(
            {"property_id": pid, "kind": "meeting_room", "active": {"$ne": False}},
            {"_id": 0, "id": 1, "name": 1, "rate_per_unit": 1}).to_list(30)
        if not spaces:
            return {"spaces": 0, "suggestions": []}
        n_spaces = len(spaces)
        cap = await db.rooms.count_documents({"property_id": pid}) or 20
        today = ddate.today()
        d0, d1 = today.isoformat(), (today + timedelta(days=days)).isoformat()
        # salon doluluğu: gün → rezerve salon sayısı
        sb = {}
        async for b in db.space_bookings.find(
                {"space_id": {"$in": [s["id"] for s in spaces]},
                 "status": {"$ne": "cancelled"}, "start": {"$gte": d0, "$lt": d1 + "T24"}},
                {"_id": 0, "space_id": 1, "start": 1, "notes": 1}):
            day = b["start"][:10]
            sb.setdefault(day, set()).add(b["space_id"])
        # otel doluluğu: gün → konaklayan oda
        occ = {}
        async for b in db.bookings.find(
                {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                 "check_in": {"$lte": d1}, "check_out": {"$gt": d0}},
                {"_id": 0, "check_in": 1, "check_out": 1, "rooms": 1}):
            try:
                ci = max(ddate.fromisoformat(b["check_in"][:10]), today)
                co = min(ddate.fromisoformat(b["check_out"][:10]), today + timedelta(days=days))
                d = ci
                while d < co:
                    occ[d.isoformat()] = occ.get(d.isoformat(), 0) + max(int(b.get("rooms", 1) or 1), 1)
                    d += timedelta(days=1)
            except Exception:
                pass
        # aktif banket teklifleri (F&B marj kredisi)
        banquet = set()
        async for p in db.function_proposals.find(
                {"property_id": pid, "status": "sent",
                 "fnb_package": {"$in": ["banquet", "lunch"]}, "date": {"$gte": d0, "$lte": d1}},
                {"_id": 0, "date": 1, "space_id": 1}):
            banquet.add((p["space_id"], p["date"]))
        out = []
        for i in range(days):
            d = today + timedelta(days=i)
            ds = d.isoformat()
            util = len(sb.get(ds, set())) / n_spaces
            hotel_occ = min(occ.get(ds, 0) / cap, 1.2)
            for sp in spaces:
                base = float(sp.get("rate_per_unit") or 0)
                if base <= 0:
                    continue
                mult, why = DOW_W[d.weekday()], []
                if DOW_W[d.weekday()] > 1:
                    why.append(f"{DOW_TR[d.weekday()]} güçlü toplantı günü")
                elif DOW_W[d.weekday()] < 1:
                    why.append(f"{DOW_TR[d.weekday()]} zayıf gün")
                if util >= 0.5:
                    mult *= 1.2
                    why.append(f"salonların %{util*100:.0f}'i dolu — sıkışan arz")
                if hotel_occ >= 0.8:
                    mult *= 1.1
                    why.append(f"otel doluluğu %{hotel_occ*100:.0f} — şehirde talep var")
                if i <= 7 and sp["id"] not in sb.get(ds, set()) and util < 0.3:
                    mult *= 0.85
                    why.append("son 7 gün, salon boş — doldurma indirimi")
                fnb_credit = (sp["id"], ds) in banquet
                if fnb_credit:
                    mult *= 0.92
                    why.append("banket/yemekli teklif var — F&B marjı kira esnekliği sağlıyor")
                mult = max(0.7, min(mult, 1.5))
                cur = base
                ov = await db.space_rate_overrides.find_one(
                    {"space_id": sp["id"], "date": ds}, {"_id": 0, "rate_per_unit": 1})
                if ov and ov.get("rate_per_unit"):
                    cur = float(ov["rate_per_unit"])
                suggested = round(base * mult, 0)
                if cur and abs(suggested - cur) / cur < 0.05:
                    continue
                out.append({"space_id": sp["id"], "space_name": sp["name"], "date": ds,
                            "dow": DOW_TR[d.weekday()], "current_rate": cur,
                            "suggested_rate": suggested,
                            "change_pct": round((suggested - cur) / cur * 100, 1) if cur else None,
                            "fnb_credit": fnb_credit,
                            "why": " · ".join(why) or "standart gün ayarı"})
        out.sort(key=lambda x: (x["date"], x["space_name"]))
        return {"spaces": n_spaces, "suggestions": out[:120]}

    @router.get("/function-space/{pid}/dynamic-pricing")
    async def dynamic(pid: str, days: int = 30, _u: dict = Depends(require_roles(*ROLES))):
        days = max(7, min(days, 60))
        data = await _suggestions(pid, days)
        return {"property_id": pid, "days": days, **data,
                "note": "Öneri = saatlik baz fiyat × talep çarpanı (gün tipi, salon doluluğu, otel doluluğu, son-dakika boşluk, F&B marj kredisi). ±%5 altı farklar gösterilmez."}

    @router.post("/function-space/{pid}/dynamic-pricing/apply")
    async def apply(pid: str, data: Dict = None, u: dict = Depends(require_roles(*ROLES))):
        items = (data or {}).get("items")
        if not items:
            items = (await _suggestions(pid, int((data or {}).get("days", 30) or 30)))["suggestions"]
        now = datetime.now(timezone.utc).isoformat()
        written = 0
        for it in items[:200]:
            rate = round(float(it.get("suggested_rate") or it.get("rate") or 0), 2)
            if rate <= 0 or not it.get("space_id") or not it.get("date"):
                continue
            ex = await db.space_rate_overrides.find_one(
                {"space_id": it["space_id"], "date": it["date"]}, {"_id": 0, "set_by": 1})
            sb = (ex or {}).get("set_by") or ""
            if ex and ("@" in sb or " " in sb):
                continue
            await db.space_rate_overrides.update_one(
                {"space_id": it["space_id"], "date": it["date"]},
                {"$set": {"rate_per_unit": rate, "set_by": ACTOR,
                          "reason": it.get("why", "dinamik fiyat"), "updated_at": now}},
                upsert=True)
            written += 1
        await db.space_pricing_applies.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "written": written,
            "by": u.get("name") or u.get("email", ""), "created_at": now})
        return {"ok": True, "written": written}

    return router
