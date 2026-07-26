"""
Kayıp Talep Takibi (Denials & Regrets) — Duetto/IDeaS paritesi. Reddedilen /
kaçan rezervasyon taleplerini kaydeder (fiyat yüksek, müsaitlik yok vb.) ve
kısıtsız talep (unconstrained demand) içgörüsü üretir. Widget'ta müsaitlik
bulunamayınca otomatik denial kaydı düşer.
Collection: lost_demand {id, property_id, check_in, check_out, rooms, nights,
  channel, reason, quoted_rate, est_lost_revenue, note, source, created_at}
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

STAFF = ("admin", "manager", "receptionist")
REASONS = ("price_too_high", "no_availability", "room_type_unavailable",
           "restrictions", "dates_changed", "other")
REASON_TR = {"price_too_high": "Fiyat yüksek bulundu", "no_availability": "Müsaitlik yok",
             "room_type_unavailable": "İstenen oda tipi yok", "restrictions": "Kısıtlama (min gece vb.)",
             "dates_changed": "Misafir tarih değiştirdi", "other": "Diğer"}
CHANNELS = ("phone", "walk_in", "email", "widget", "ota", "agency", "other")


def _iso():
    return datetime.now(timezone.utc).isoformat()


async def log_lost_demand(db, property_id: str, data: Dict, source: str = "manual") -> Dict:
    check_in, check_out = data.get("check_in", ""), data.get("check_out", "")
    try:
        ci, co = ddate.fromisoformat(check_in), ddate.fromisoformat(check_out)
        nights = max((co - ci).days, 1)
    except Exception:
        raise HTTPException(400, "Geçerli check_in/check_out gerekli (YYYY-MM-DD)")
    reason = data.get("reason", "other")
    if reason not in REASONS:
        raise HTTPException(400, f"reason şunlardan biri olmalı: {REASONS}")
    rooms = max(int(data.get("rooms", 1) or 1), 1)
    quoted = round(float(data.get("quoted_rate", 0) or 0), 2)
    doc = {"id": str(uuid.uuid4()), "property_id": property_id,
           "check_in": check_in, "check_out": check_out, "nights": nights,
           "rooms": rooms, "channel": data.get("channel", "other"),
           "reason": reason, "quoted_rate": quoted,
           "est_lost_revenue": round(rooms * nights * quoted, 2),
           "note": (data.get("note") or "")[:300], "source": source,
           "created_at": _iso()}
    await db.lost_demand.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


def create_lost_demand_router(db, require_roles):
    router = APIRouter(prefix="/lost-demand")

    @router.post("/{property_id}/log")
    async def log_entry(property_id: str, data: Dict,
                        current_user: dict = Depends(require_roles(*STAFF))):
        doc = await log_lost_demand(db, property_id, data, source="manual")
        return {"ok": True, "entry": doc}

    @router.get("/{property_id}")
    async def list_entries(property_id: str, days: int = 30,
                           current_user: dict = Depends(require_roles(*STAFF))):
        since = (datetime.now(timezone.utc) - timedelta(days=min(days, 365))).isoformat()
        q = {"created_at": {"$gte": since}}
        if property_id != "all":
            q["property_id"] = property_id
        rows = await db.lost_demand.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        by_reason: Dict[str, Dict] = {}
        lost_rn, lost_rev = 0, 0.0
        for r in rows:
            rn = r["rooms"] * r["nights"]
            lost_rn += rn
            lost_rev += r["est_lost_revenue"]
            b = by_reason.setdefault(r["reason"], {"count": 0, "room_nights": 0, "revenue": 0.0})
            b["count"] += 1
            b["room_nights"] += rn
            b["revenue"] = round(b["revenue"] + r["est_lost_revenue"], 2)
        top_reason = max(by_reason, key=lambda k: by_reason[k]["room_nights"]) if by_reason else None
        return {"entries": rows, "reason_labels": REASON_TR,
                "summary": {"entries": len(rows), "lost_room_nights": lost_rn,
                            "est_lost_revenue": round(lost_rev, 2),
                            "top_reason": top_reason,
                            "top_reason_label": REASON_TR.get(top_reason, "") if top_reason else "",
                            "by_reason": by_reason}}

    @router.delete("/{property_id}/{entry_id}")
    async def delete_entry(property_id: str, entry_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.lost_demand.delete_one({"id": entry_id, "property_id": property_id})
        if not r.deleted_count:
            raise HTTPException(404, "Kayıt bulunamadı")
        return {"ok": True}

    @router.get("/{property_id}/insights")
    async def insights(property_id: str, days_back: int = 60,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """Konaklama tarihi bazında kısıtsız talep: OTB + kayıp talep."""
        since = (datetime.now(timezone.utc) - timedelta(days=min(days_back, 365))).isoformat()
        q = {"created_at": {"$gte": since}}
        if property_id != "all":
            q["property_id"] = property_id
        rows = await db.lost_demand.find(q, {"_id": 0}).to_list(500)
        lost_by_date: Dict[str, Dict] = {}
        for r in rows:
            try:
                ci, co = ddate.fromisoformat(r["check_in"]), ddate.fromisoformat(r["check_out"])
            except Exception:
                continue
            d = ci
            while d < co:
                ds = d.isoformat()
                e = lost_by_date.setdefault(ds, {"lost_rooms": 0, "price": 0, "avail": 0})
                e["lost_rooms"] += r["rooms"]
                if r["reason"] == "price_too_high":
                    e["price"] += r["rooms"]
                elif r["reason"] in ("no_availability", "room_type_unavailable"):
                    e["avail"] += r["rooms"]
                d += timedelta(days=1)
        total_rooms = 0
        for rt in await db.room_types.find(
                {} if property_id == "all" else {"property_id": property_id},
                {"_id": 0, "total_rooms": 1}).to_list(100):
            total_rooms += int(rt.get("total_rooms", 0))
        today = ddate.today().isoformat()
        out = []
        for ds in sorted(k for k in lost_by_date if k >= today):
            e = lost_by_date[ds]
            booked = await db.bookings.count_documents({
                **({} if property_id == "all" else {"property_id": property_id}),
                "status": {"$in": ["confirmed", "checked_in"]},
                "check_in": {"$lte": ds}, "check_out": {"$gt": ds}})
            unconstrained = booked + e["lost_rooms"]
            if e["price"] > e["avail"]:
                rec = "Kayıplar fiyat kaynaklı — indirime koşmayın; değer iletişimi, kademeli fiyat veya paket teklifi deneyin."
            elif e["avail"] > 0 and total_rooms and unconstrained > total_rooms:
                rec = "Kısıtsız talep kapasiteyi aşıyor — fiyatı YÜKSELTİN ve waitlist/overbooking politikası değerlendirin."
            elif e["avail"] > 0:
                rec = "Müsaitlik kaynaklı kayıp — oda tipi dağılımını ve kısıtlamaları gözden geçirin, waitlist'e yönlendirin."
            else:
                rec = "Karma sebepler — kanal bazında talep kalitesini inceleyin."
            out.append({"date": ds, "otb_rooms": booked, "lost_rooms": e["lost_rooms"],
                        "unconstrained_demand": unconstrained, "capacity": total_rooms,
                        "price_driven": e["price"], "availability_driven": e["avail"],
                        "recommendation": rec})
        out.sort(key=lambda x: -x["lost_rooms"])
        return {"dates": out[:20], "capacity": total_rooms}

    return router
