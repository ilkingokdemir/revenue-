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

    @router.get("/function-space/{pid}/proposals/{prop_id}/pdf")
    async def proposal_pdf(pid: str, prop_id: str, _u: dict = Depends(require_roles(*ROLES))):
        prop = await db.function_proposals.find_one({"id": prop_id, "property_id": pid}, {"_id": 0})
        if not prop:
            raise HTTPException(404, "Teklif bulunamadı")
        prop_doc = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        hotel = prop_doc.get("name") or "Otel"
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as pdfcanvas
        from reportlab.lib.units import mm
        _t = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        buf = BytesIO()
        c = pdfcanvas.Canvas(buf, pagesize=A4)
        w, h = A4
        c.setFillColorRGB(0.28, 0.24, 0.55)
        c.rect(0, h - 40 * mm, w, 40 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(20 * mm, h - 22 * mm, hotel.translate(_t))
        c.setFont("Helvetica", 12)
        c.drawString(20 * mm, h - 32 * mm, "Fonksiyon Alani Teklifi".translate(_t))
        y = h - 55 * mm
        c.setFillColorRGB(0.15, 0.15, 0.15)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(20 * mm, y, f"Sayin {prop['client_name']}".translate(_t))
        y -= 10 * mm
        c.setFont("Helvetica", 10)
        rows = [
            ("Salon", prop["space_name"]),
            ("Tarih", f"{prop['date']}  {prop['start'][11:16]} - {prop['end'][11:16]} ({prop['hours']} saat)"),
            ("Katilimci", str(prop["attendees"])),
            ("Gecerlilik", prop.get("valid_until", "")),
        ]
        for label, val in rows:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(20 * mm, y, (label + ":").translate(_t))
            c.setFont("Helvetica", 10)
            c.drawString(55 * mm, y, str(val).translate(_t))
            y -= 7 * mm
        y -= 5 * mm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(20 * mm, y, "Kalem")
        c.drawRightString(w - 20 * mm, y, "Tutar")
        y -= 2 * mm
        c.line(20 * mm, y, w - 20 * mm, y)
        y -= 8 * mm
        items = [
            (f"Salon kirasi ({prop['hours']} saat x {prop['rate_per_hour']})", prop["rental"]),
            (f"F&B: {prop['fnb_label']} x {prop['attendees']} kisi", prop["fnb"]),
            ("AV ekipmani", prop["av"]),
        ]
        c.setFont("Helvetica", 10)
        for label, val in items:
            c.drawString(20 * mm, y, label.translate(_t))
            c.drawRightString(w - 20 * mm, y, f"{val:,.2f} {prop.get('currency', '')}")
            y -= 7 * mm
        y -= 2 * mm
        c.line(20 * mm, y, w - 20 * mm, y)
        y -= 9 * mm
        c.setFont("Helvetica-Bold", 13)
        c.drawString(20 * mm, y, "TOPLAM")
        c.drawRightString(w - 20 * mm, y, f"{prop['total']:,.2f} {prop.get('currency', '')}")
        y -= 15 * mm
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(20 * mm, y, f"Teklif no: {prop_id[:8]} - Bu teklif {prop.get('valid_until','')} tarihine kadar gecerlidir.".translate(_t))
        c.save()
        buf.seek(0)
        from fastapi.responses import StreamingResponse
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": f'inline; filename="teklif-{prop_id[:8]}.pdf"'})

    @router.post("/function-space/{pid}/proposals/{prop_id}/email")
    async def email_proposal(pid: str, prop_id: str, _u: dict = Depends(require_roles(*ROLES))):
        prop = await db.function_proposals.find_one({"id": prop_id, "property_id": pid}, {"_id": 0})
        if not prop:
            raise HTTPException(404, "Teklif bulunamadı")
        if not prop.get("client_email"):
            raise HTTPException(400, "Teklifte müşteri e-postası yok")
        now = datetime.now(timezone.utc).isoformat()
        body = (f"Sayın {prop['client_name']},\n\n"
                f"{prop['space_name']} için hazırladığımız teklif:\n"
                f"Tarih: {prop['date']} {prop['start'][11:16]}–{prop['end'][11:16]} ({prop['hours']} saat)\n"
                f"Katılımcı: {prop['attendees']} kişi\n"
                f"Salon kirası: {prop['rental']} · F&B ({prop['fnb_label']}): {prop['fnb']} · AV: {prop['av']}\n"
                f"TOPLAM: {prop['total']} {prop.get('currency', '')}\n\n"
                f"Teklif {prop.get('valid_until', '')} tarihine kadar geçerlidir.\nSaygılarımızla.")
        await db.outbound_email_queue.insert_one({
            "id": str(uuid.uuid4()), "to": prop["client_email"],
            "subject": f"Fonksiyon Alanı Teklifi — {prop['space_name']} ({prop['date']})",
            "body": body, "status": "queued", "kind": "function_proposal",
            "delivery_status": "mocked_email_queued", "created_at": now})
        await db.function_proposals.update_one({"id": prop_id}, {"$set": {"emailed_at": now}})
        return {"ok": True, "queued_to": prop["client_email"],
                "note": "E-posta kuyruğa alındı. Resend API anahtarı girilene kadar gönderim MOCK modda bekler."}

    @router.get("/function-space/{pid}/calendar")
    async def week_calendar(pid: str, week_start: str = "", _u: dict = Depends(require_roles(*ROLES))):
        today = datetime.now(timezone.utc).date()
        try:
            ws = datetime.strptime(week_start, "%Y-%m-%d").date() if week_start else today - timedelta(days=today.weekday())
        except ValueError:
            raise HTTPException(400, "week_start YYYY-MM-DD olmalı")
        days = [(ws + timedelta(days=i)).isoformat() for i in range(7)]
        spaces = await db.spaces.find(
            {"property_id": pid, "kind": "meeting_room", "active": {"$ne": False}},
            {"_id": 0}).to_list(50)
        start_iso, end_iso = f"{days[0]}T00:00:00", f"{days[-1]}T23:59:59"
        bks = await db.space_bookings.find(
            {"space_id": {"$in": [s["id"] for s in spaces]}, "status": {"$ne": "cancelled"},
             "start": {"$lt": end_iso}, "end": {"$gt": start_iso}},
            {"_id": 0, "space_id": 1, "start": 1, "end": 1, "guest_name": 1}).to_list(1000)
        out = []
        for sp in spaces:
            oh, ch = int(sp.get("open_hour", 8)), int(sp.get("close_hour", 22))
            day_rows = []
            for d in days:
                busy = []
                for b in bks:
                    if b["space_id"] != sp["id"] or b["start"][:10] > d or b["end"][:10] < d:
                        continue
                    sh = int(b["start"][11:13]) if b["start"][:10] == d else oh
                    eh = int(b["end"][11:13]) if b["end"][:10] == d else ch
                    busy.append({"start_hour": sh, "end_hour": max(eh, sh + 1), "guest": b.get("guest_name", "")})
                busy.sort(key=lambda x: x["start_hour"])
                free, cur = [], oh
                for bl in busy:
                    if bl["start_hour"] > cur:
                        free.append({"start_hour": cur, "end_hour": bl["start_hour"]})
                    cur = max(cur, bl["end_hour"])
                if cur < ch:
                    free.append({"start_hour": cur, "end_hour": ch})
                day_rows.append({"date": d, "busy": busy, "free": free,
                                 "busy_hours": sum(b["end_hour"] - b["start_hour"] for b in busy)})
            out.append({"space_id": sp["id"], "name": sp["name"],
                        "open_hour": oh, "close_hour": ch, "days": day_rows})
        return {"property_id": pid, "week_start": days[0], "days": days, "spaces": out}

    return router
