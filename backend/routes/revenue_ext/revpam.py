"""
RevPAM — Toplantı Salonu Dinamik Fiyatlama (Total Revenue Management parçası).
db.spaces içindeki meeting_room türü alanlar için:
- RevPASH (Revenue per Available Seat-Hour) metriği (30g)
- Haftagünü talebi + tarih doluluğu bazlı 14 günlük dinamik fiyat önerisi
- Önerilen fiyatlar space_rate_overrides'a yazılır; spaces booking motoru
  o tarih için override fiyatı kullanır.

Endpoints (/api/revpam/*):
- GET  /{property_id}?days=14   → salon bazlı analiz + öneriler
- POST /{property_id}/apply     → {space_id, overrides:[{date, rate_per_unit}]}
"""
from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException


def _hours(b) -> float:
    try:
        sd = datetime.fromisoformat(b["start"])
        ed = datetime.fromisoformat(b["end"])
        return max(0.0, (ed - sd).total_seconds() / 3600)
    except (KeyError, ValueError, TypeError):
        return 0.0


def create_revpam_router(db, require_roles):
    router = APIRouter(prefix="/revpam", tags=["revpam"])

    @router.get("/{property_id}")
    async def analysis(property_id: str, days: int = 14,
                       _: dict = Depends(require_roles("admin", "manager"))):
        days = max(7, min(days, 30))
        spaces = await db.spaces.find(
            {"property_id": property_id, "kind": "meeting_room", "active": {"$ne": False}},
            {"_id": 0}).to_list(50)
        if not spaces:
            return {"spaces": [], "summary": None,
                    "hint": "meeting_room türünde space yok — Spaces panelinden ekleyin veya seed edin."}

        now = datetime.now(timezone.utc)
        cutoff60 = (now - timedelta(days=60)).isoformat()
        cutoff30 = (now - timedelta(days=30)).isoformat()
        sids = [s["id"] for s in spaces]
        bookings = await db.space_bookings.find(
            {"space_id": {"$in": sids}, "status": {"$ne": "cancelled"},
             "start": {"$gte": cutoff60}},
            {"_id": 0, "space_id": 1, "start": 1, "end": 1, "price": 1}).to_list(5000)
        overrides = {(o["space_id"], o["date"]): o["rate_per_unit"]
                     async for o in db.space_rate_overrides.find(
                         {"space_id": {"$in": sids}}, {"_id": 0})}

        out, tot_rev, tot_util = [], 0.0, []
        today = now.date()
        for sp in spaces:
            oh = max(1, int(sp.get("close_hour", 24)) - int(sp.get("open_hour", 0)))
            cap = max(1, int(sp.get("capacity", 1)))
            base = float(sp.get("rate_per_unit", 0) or 0)
            mine = [b for b in bookings if b["space_id"] == sp["id"]]
            rev30 = round(sum(float(b.get("price", 0) or 0)
                              for b in mine if (b.get("start") or "") >= cutoff30), 2)
            hours30 = sum(_hours(b) for b in mine if (b.get("start") or "") >= cutoff30)
            avail_sh = cap * oh * 30
            revpash = round(rev30 / avail_sh, 3) if avail_sh else 0
            util30 = round(min(hours30 / (oh * 30), 1.0) * 100, 1)

            dow_hours = [0.0] * 7
            for b in mine:
                try:
                    dow_hours[datetime.fromisoformat(b["start"]).weekday()] += _hours(b)
                except (KeyError, ValueError, TypeError):
                    continue
            max_dow = max(dow_hours) or 0

            day_rows = []
            for i in range(days):
                d = today + timedelta(days=i)
                iso = d.isoformat()
                booked = sum(_hours(b) for b in mine if (b.get("start") or "")[:10] == iso)
                date_util = min(booked / oh, 1.0)
                dow_score = (dow_hours[d.weekday()] / max_dow) if max_dow else 0.5
                mult = max(0.7, min(0.8 + 0.45 * dow_score + 0.35 * date_util, 1.5))
                suggested = round(base * mult, 2)
                day_rows.append({
                    "date": iso, "dow": d.strftime("%a"),
                    "booked_hours": round(booked, 1), "util_pct": round(date_util * 100, 1),
                    "multiplier": round(mult, 2), "suggested_rate": suggested,
                    "current_override": overrides.get((sp["id"], iso)),
                })
            out.append({
                "id": sp["id"], "name": sp["name"], "capacity": cap,
                "rate_per_unit": base, "open_hours": oh,
                "revenue_30d": rev30, "booked_hours_30d": round(hours30, 1),
                "utilization_pct": util30, "revpash": revpash, "days": day_rows,
            })
            tot_rev += rev30
            tot_util.append(util30)

        return {"spaces": out, "summary": {
            "total_revenue_30d": round(tot_rev, 2),
            "avg_utilization_pct": round(sum(tot_util) / len(tot_util), 1) if tot_util else 0,
            "meeting_rooms": len(out),
        }}

    @router.post("/{property_id}/apply")
    async def apply_overrides(property_id: str, body: Dict,
                              _: dict = Depends(require_roles("admin", "manager"))):
        space_id = (body.get("space_id") or "").strip()
        rows = body.get("overrides") or []
        if not space_id or not rows:
            raise HTTPException(400, "space_id ve overrides gerekli")
        space = await db.spaces.find_one({"id": space_id, "property_id": property_id}, {"_id": 0, "id": 1})
        if not space:
            raise HTTPException(404, "Space bulunamadı")
        now = datetime.now(timezone.utc).isoformat()
        applied = 0
        for r in rows[:60]:
            try:
                d = str(r["date"])[:10]
                rate = round(max(0.0, float(r["rate_per_unit"])), 2)
            except (KeyError, TypeError, ValueError):
                continue
            await db.space_rate_overrides.update_one(
                {"space_id": space_id, "date": d},
                {"$set": {"space_id": space_id, "property_id": property_id,
                          "date": d, "rate_per_unit": rate, "updated_at": now}},
                upsert=True)
            applied += 1
        return {"ok": True, "applied": applied}

    return router
