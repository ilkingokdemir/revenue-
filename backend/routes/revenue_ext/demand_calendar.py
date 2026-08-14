"""Talep Takvimi (Demand Calendar) — Duetto Advance 2026 paritesi.
Isı haritası + tarihe tek tık sade Türkçe AI talep analizi. Ayrıca Orphan Gap tespiti (PriceLabs paritesi)."""
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from typing import Dict


def create_demand_calendar_router(db, require_roles):
    router = APIRouter(prefix="/demand-calendar", tags=["demand-calendar"])
    ROLES = ("admin", "manager", "receptionist")

    @router.get("/{pid}")
    async def calendar(pid: str, month: str = "", _u: dict = Depends(require_roles(*ROLES))):
        from routes.revenue_ext.ml_pickup import _stay_counts
        cap = await db.rooms.count_documents({"property_id": pid}) or 20
        today = datetime.now(timezone.utc).date()
        m = month or today.strftime("%Y-%m")
        start = datetime.strptime(m + "-01", "%Y-%m-%d").date()
        nxt = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        days, dow_occ = [], {}
        d = start
        while d < nxt:
            otb = (await _stay_counts(db, pid, d.isoformat()))["otb"]
            occ = round(otb / cap * 100, 1)
            dow_occ.setdefault(d.weekday(), []).append(occ)
            days.append({"date": d.isoformat(), "otb": otb, "occ": occ, "dow": d.weekday()})
            d += timedelta(days=1)
        dow_avg = {k: sum(v) / len(v) for k, v in dow_occ.items()}
        for x in days:
            dev = x["occ"] - dow_avg.get(x["dow"], 50)
            x["anomaly"] = round(dev, 1)
            x["heat"] = ("hot" if x["occ"] >= 75 else "warm" if x["occ"] >= 50
                         else "cool" if x["occ"] >= 30 else "cold")
            x["flag"] = "spike" if dev >= 20 else ("dip" if dev <= -20 else None)
        return {"property_id": pid, "month": m, "capacity": cap, "days": days,
                "legend": "hot ≥75% · warm 50-74 · cool 30-49 · cold <30 · bayrak: haftagünü ortalamasından ±20 puan sapma"}

    @router.get("/{pid}/analyze")
    async def analyze(pid: str, date: str, _u: dict = Depends(require_roles(*ROLES))):
        """Tarihe tek tık: talep sürücüleri + rakip bağlamı sade Türkçe."""
        from routes.revenue_ext.ml_pickup import _stay_counts
        from routes.distribution.push_history import resolve_rate
        cap = await db.rooms.count_documents({"property_id": pid}) or 20
        sc = await _stay_counts(db, pid, date)
        occ = round(sc["otb"] / cap * 100, 1)
        base, _src = await resolve_rate(db, pid, date)
        snap = await db.market_supply.find_one(
            {"property_id": pid, "scan_type": "geo", "date": date}, {"_id": 0},
            sort=[("scanned_at", -1)])
        camp = await db.promo_campaigns.find_one({"property_id": pid, "date": date}, {"_id": 0, "type": 1, "status": 1})
        dec = await db.ai_pricing_decisions.find_one(
            {"property_id": pid, "date": date}, {"_id": 0, "new_rate": 1, "status": 1, "decided_at": 1},
            sort=[("decided_at", -1)])
        facts = [f"Tarih: {date}", f"Doluluk: %{occ} ({sc['otb']}/{cap} oda)", f"Bizim fiyat: £{base or 0:.0f}"]
        if snap:
            facts.append(f"Pazar: ort £{snap.get('avg_price', 0):.0f}, pazar doluluk vekili %{snap.get('unavailable_pct', 0)}")
        if camp:
            facts.append(f"Aktif kampanya: {camp.get('type')} ({camp.get('status')})")
        if dec:
            facts.append(f"Son robot kararı: £{dec.get('new_rate')} ({dec.get('status')}, {str(dec.get('decided_at', ''))[:10]})")
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
                           session_id=f"dc-{uuid.uuid4().hex[:8]}",
                           system_message="Otel revenue analistisin. Verilen gerçek verilerle bu tarihin talep hikâyesini 3-4 cümlede sade Türkçe anlat: durum, olası sebep, önerilen aksiyon. Veri uydurma.").with_model("openai", "gpt-5.2")
            story = await chat.send_message(UserMessage(text="\n".join(facts)))
        except Exception:
            story = " · ".join(facts)
        return {"date": date, "occ": occ, "our_rate": base, "market": snap, "facts": facts, "story": story}

    @router.get("/{pid}/orphan-gaps")
    async def orphan_gaps(pid: str, days: int = 60, _u: dict = Depends(require_roles(*ROLES))):
        """Yetim geceler (PriceLabs paritesi): rezervasyonlar arasında kalan 1-2 gecelik boşluklar."""
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=min(days, 90))
        bks = await db.bookings.find(
            {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
             "room_id": {"$ne": None},
             "check_out": {"$gte": today.isoformat()}, "check_in": {"$lte": end.isoformat()}},
            {"_id": 0, "room_id": 1, "check_in": 1, "check_out": 1}).to_list(3000)
        by_room = {}
        for b in bks:
            by_room.setdefault(b["room_id"], []).append(b)
        gaps = {}
        for rid, lst in by_room.items():
            lst.sort(key=lambda x: x["check_in"])
            for a, b in zip(lst, lst[1:]):
                g = (datetime.strptime(b["check_in"], "%Y-%m-%d").date()
                     - datetime.strptime(a["check_out"], "%Y-%m-%d").date()).days
                if 1 <= g <= 2:
                    key = a["check_out"]
                    gaps.setdefault(key, {"start": a["check_out"], "nights": g, "rooms": 0})
                    gaps[key]["rooms"] += 1
        out = sorted(gaps.values(), key=lambda x: x["start"])
        return {"property_id": pid, "gaps": out, "total_orphan_room_nights": sum(g["nights"] * g["rooms"] for g in out),
                "suggestion": "Yetim gecelere %10 indirim + min-stay 1 uygulayın — tek tıkla kampanya açılabilir."}

    @router.post("/{pid}/orphan-gaps/fill")
    async def fill_gaps(pid: str, body: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        dates = body.get("dates") or []
        now = datetime.now(timezone.utc).isoformat()
        for ds in dates[:20]:
            await db.promo_campaigns.update_one(
                {"property_id": pid, "date": ds, "type": "orphan_fill"},
                {"$set": {"property_id": pid, "date": ds, "type": "orphan_fill",
                          "discount_pct": 10, "min_los": 1, "channel": "all",
                          "status": "aktif", "applied_at": now,
                          "applied_by": current_user.get("email", ""),
                          "aciklama": "Yetim gece doldurma — 1-2 gecelik boşluk kampanyası"}},
                upsert=True)
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "info",
            "title": "Yetim gece kampanyası açıldı",
            "message": f"{len(dates[:20])} boşluk gecesi için %10 indirim + min-stay 1 aktifleşti.",
            "category": "revenue", "target_user": "", "target_role": "manager",
            "link_to": "demand-calendar", "priority": "normal", "read": False,
            "created_by": "Yetim Gece Doldurucu", "created_at": now})
        return {"ok": True, "filled": len(dates[:20])}

    return router
