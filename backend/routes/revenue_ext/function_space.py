"""Fonksiyon Alanı Motoru — toplantı/balo salonu teklif & rezervasyon + RevPAM (Duetto OpenSpace paritesi)."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

FNB_PACKAGES = {
    "none": {"label": "Yok", "per_person": 0},
    "coffee": {"label": "Kahve Molası", "per_person": 8},
    "lunch": {"label": "Öğle Yemeği", "per_person": 25},
    "banquet": {"label": "Banket / Gala", "per_person": 55},
}
AV_FLAT = 75.0


def create_function_space_router(db, require_roles):
    router = APIRouter(tags=["function-space"])
    ROLES = ("admin", "manager")

    async def _quote(pid: str, data: dict) -> dict:
        space = await db.spaces.find_one({"id": data.get("space_id"), "property_id": pid}, {"_id": 0})
        if not space:
            raise HTTPException(404, "Salon bulunamadı")
        date = data.get("date") or datetime.now(timezone.utc).date().isoformat()
        sh, eh = int(data.get("start_hour", 9)), int(data.get("end_hour", 17))
        if eh <= sh:
            raise HTTPException(400, "end_hour, start_hour'dan büyük olmalı")
        attendees = max(1, int(data.get("attendees", 10)))
        pkg = FNB_PACKAGES.get(data.get("fnb_package", "none"), FNB_PACKAGES["none"])
        hours = eh - sh
        rate = float(space.get("rate_per_unit") or 0)
        dyn = await db.space_rate_overrides.find_one({"space_id": space["id"], "date": date}, {"_id": 0})
        if dyn and dyn.get("rate_per_unit"):
            rate = float(dyn["rate_per_unit"])
        rental = round(hours * rate, 2)
        fnb = round(attendees * pkg["per_person"], 2)
        av = AV_FLAT if data.get("av_needed") else 0.0
        start, end = f"{date}T{sh:02d}:00:00", f"{date}T{eh:02d}:00:00"
        overlap = await db.space_bookings.count_documents({
            "space_id": space["id"], "status": {"$ne": "cancelled"},
            "start": {"$lt": end}, "end": {"$gt": start}})
        sqm = float(space.get("sqm") or space.get("capacity", 1) * 1.5)
        total = round(rental + fnb + av, 2)
        return {
            "space_id": space["id"], "space_name": space["name"], "date": date,
            "start": start, "end": end, "hours": hours, "attendees": attendees,
            "rate_per_hour": rate, "rental": rental,
            "fnb_package": data.get("fnb_package", "none"), "fnb_label": pkg["label"], "fnb": fnb,
            "av": av, "total": total, "currency": space.get("currency", "GBP"),
            "available": overlap == 0,
            "revpam_contribution": round(total / sqm, 2),
            "capacity_ok": attendees <= int(space.get("capacity") or 999),
        }

    @router.post("/function-space/{pid}/quote")
    async def quote(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        return await _quote(pid, data)

    @router.post("/function-space/{pid}/proposals")
    async def create_proposal(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        if not (data.get("client_name") or "").strip():
            raise HTTPException(400, "client_name gerekli")
        q = await _quote(pid, data)
        if not q["available"]:
            raise HTTPException(409, "Salon o saat aralığında dolu")
        now = datetime.now(timezone.utc)
        prop = {"id": str(uuid.uuid4()), "property_id": pid, **q,
                "client_name": data["client_name"].strip(),
                "client_email": data.get("client_email", ""),
                "notes": data.get("notes", ""), "status": "sent",
                "valid_until": (now + timedelta(days=14)).date().isoformat(),
                "created_at": now.isoformat(), "created_by": _u.get("name", "")}
        await db.function_proposals.insert_one(dict(prop))
        prop.pop("_id", None)
        return {"ok": True, "proposal": prop}

    @router.get("/function-space/{pid}/proposals")
    async def list_proposals(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.function_proposals.find(
            {"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return {"proposals": rows}

    @router.post("/function-space/{pid}/proposals/{prop_id}/accept")
    async def accept(pid: str, prop_id: str, _u: dict = Depends(require_roles(*ROLES))):
        prop = await db.function_proposals.find_one({"id": prop_id, "property_id": pid}, {"_id": 0})
        if not prop:
            raise HTTPException(404, "Teklif bulunamadı")
        if prop["status"] == "accepted":
            raise HTTPException(400, "Teklif zaten kabul edilmiş")
        overlap = await db.space_bookings.count_documents({
            "space_id": prop["space_id"], "status": {"$ne": "cancelled"},
            "start": {"$lt": prop["end"]}, "end": {"$gt": prop["start"]}})
        if overlap:
            raise HTTPException(409, "Salon artık dolu — teklif tarihi çakışıyor")
        now = datetime.now(timezone.utc).isoformat()
        booking = {"id": str(uuid.uuid4()), "property_id": pid,
                   "space_id": prop["space_id"], "space_name": prop["space_name"],
                   "kind": "meeting_room", "guest_name": prop["client_name"],
                   "guest_email": prop.get("client_email", ""), "guest_phone": "",
                   "booking_id": "", "room_number": "",
                   "start": prop["start"], "end": prop["end"], "units": prop["hours"],
                   "price": prop["total"], "currency": prop.get("currency", "GBP"),
                   "charge_to": "direct",
                   "notes": f"Fonksiyon teklifi {prop_id[:8]} — {prop['fnb_label']}, {prop['attendees']} kişi",
                   "status": "confirmed", "source": "proposal",
                   "created_at": now, "created_by": _u.get("name", "")}
        await db.space_bookings.insert_one(dict(booking))
        await db.function_proposals.update_one(
            {"id": prop_id},
            {"$set": {"status": "accepted", "accepted_at": now, "space_booking_id": booking["id"]}})
        booking.pop("_id", None)
        return {"ok": True, "booking": booking}

    @router.post("/function-space/{pid}/proposals/{prop_id}/reject")
    async def reject(pid: str, prop_id: str, _u: dict = Depends(require_roles(*ROLES))):
        r = await db.function_proposals.update_one(
            {"id": prop_id, "property_id": pid}, {"$set": {"status": "rejected"}})
        if not r.matched_count:
            raise HTTPException(404, "Teklif bulunamadı")
        return {"ok": True}

    @router.get("/function-space/{pid}/revpam")
    async def revpam(pid: str, days: int = 30, _u: dict = Depends(require_roles(*ROLES))):
        days = max(7, min(90, days))
        spaces = await db.spaces.find(
            {"property_id": pid, "kind": "meeting_room", "active": {"$ne": False}},
            {"_id": 0}).to_list(50)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        out, tot_rev, tot_sqm = [], 0.0, 0.0
        for sp in spaces:
            sqm = float(sp.get("sqm") or sp.get("capacity", 1) * 1.5)
            agg = await db.space_bookings.aggregate([
                {"$match": {"space_id": sp["id"], "status": {"$ne": "cancelled"},
                            "start": {"$gte": since}}},
                {"$group": {"_id": None, "rev": {"$sum": "$price"}, "n": {"$sum": 1}}}]).to_list(1)
            rev = (agg[0]["rev"] or 0) if agg else 0
            n = agg[0]["n"] if agg else 0
            tot_rev += rev
            tot_sqm += sqm
            out.append({"space_id": sp["id"], "name": sp["name"], "sqm": round(sqm, 1),
                        "capacity": sp.get("capacity"), "bookings": n,
                        "revenue": round(rev, 2), "revpam": round(rev / sqm / days, 2)})
        out.sort(key=lambda x: -x["revpam"])
        return {"property_id": pid, "window_days": days, "spaces": out,
                "total_revpam": round(tot_rev / tot_sqm / days, 2) if tot_sqm else 0,
                "note": "RevPAM = gelir / m² / gün. m² tanımlı değilse kapasite × 1.5 m² varsayılır."}

    return router
