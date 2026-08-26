"""
Gün Sonu Raporu (EOD) — gece denetimi (close-day) sonrası otomatik özet e-postası.
Kapanış anındaki değişmez (immutable) snapshot varsa onu kullanır; yoksa canlı hesaplar.
Resend anahtarı yoksa MOCK (email_outbox). Collection: eod_reports
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

from routes.platform_ext.mailer import send_email

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


async def build_eod(db, pid: str, business_date: str) -> Dict:
    close = await db.night_audit_closes.find_one(
        {"property_id": pid, "business_date": business_date}, {"_id": 0})
    active_q = {"property_id": pid, "status": {"$nin": ["cancelled"]}}
    if close:
        totals, counts = close["totals"], close["counts"]
        source = "night_audit_close"
    else:
        arrivals = await db.bookings.count_documents({**active_q, "check_in": business_date})
        departures = await db.bookings.count_documents({**active_q, "check_out": business_date})
        in_house = await db.bookings.count_documents({"property_id": pid, "status": "checked_in"})
        room_rev = 0.0
        async for b in db.bookings.find(
                {**active_q, "check_in": {"$lte": business_date}, "check_out": {"$gt": business_date},
                 "status": {"$nin": ["cancelled", "no_show"]}}, {"_id": 0, "rate": 1}):
            room_rev += float(b.get("rate", 0) or 0)
        totals = {"charges": round(room_rev, 2), "payments": 0.0, "adjustments": 0.0,
                  "net": round(room_rev, 2)}
        counts = {"arrivals": arrivals, "departures": departures,
                  "in_house": in_house, "folio_items": 0}
        source = "live_estimate"
    no_shows = await db.bookings.count_documents(
        {"property_id": pid, "check_in": business_date, "status": "no_show"})
    total_rooms = 0
    async for rt in db.room_types.find({"property_id": pid}, {"_id": 0, "total_rooms": 1}):
        total_rooms += int(rt.get("total_rooms", 0))
    sold = await db.bookings.count_documents(
        {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
         "check_in": {"$lte": business_date}, "check_out": {"$gt": business_date}})
    occ = round(sold / total_rooms * 100, 1) if total_rooms else 0.0
    tomorrow = (datetime.strptime(business_date, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
    tomorrow_arrivals = await db.bookings.count_documents({**active_q, "check_in": tomorrow})
    return {"business_date": business_date, "source": source, "occupancy": occ,
            "sold_rooms": sold, "total_rooms": total_rooms, "no_shows": no_shows,
            "totals": totals, "counts": counts, "tomorrow_arrivals": tomorrow_arrivals}


def _eod_html(prop_name: str, r: Dict) -> str:
    t, c = r["totals"], r["counts"]
    src = "gece kapanışı snapshot'ı" if r["source"] == "night_audit_close" else "canlı tahmin (kapanış yapılmadı)"
    return (f"<div style='font-family:sans-serif;max-width:560px'>"
            f"<h2>🌙 Gün Sonu Raporu — {prop_name} · {r['business_date']}</h2>"
            f"<table style='width:100%;border-collapse:collapse'>"
            + "".join(f"<tr><td style='padding:6px 10px;border-bottom:1px solid #eee'>{k}</td>"
                      f"<td style='padding:6px 10px;border-bottom:1px solid #eee;font-weight:600'>{v}</td></tr>"
                      for k, v in [
                          ("Doluluk", f"%{r['occupancy']} ({r['sold_rooms']}/{r['total_rooms']} oda)"),
                          ("Gelir (charges)", f"£{t['charges']}"),
                          ("Tahsilat (payments)", f"£{t['payments']}"),
                          ("Düzeltmeler", f"£{t['adjustments']}"),
                          ("Net", f"£{t['net']}"),
                          ("Giriş / Çıkış", f"{c['arrivals']} / {c['departures']}"),
                          ("Konaklayan (in-house)", c["in_house"]),
                          ("No-show", r["no_shows"]),
                          ("Yarın beklenen giriş", r["tomorrow_arrivals"]),
                      ])
            + f"</table><p style='color:#888;font-size:12px'>Kaynak: {src}. "
              f"Bu rapor gece denetimi sonrası otomatik gönderildi.</p></div>")


async def send_eod(db, pid: str, business_date: str, forced: bool = False) -> Dict:
    if not forced:
        existing = await db.eod_reports.find_one(
            {"property_id": pid, "business_date": business_date})
        if existing:
            return {"skipped": "already_sent"}
    report = await build_eod(db, pid, business_date)
    prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
    admins = await db.users.find({"role": {"$in": ["admin", "manager"]},
                                  "is_active": {"$ne": False}},
                                 {"_id": 0, "email": 1}).to_list(20)
    html = _eod_html(prop.get("name", pid), report)
    sent_to = []
    for a in admins:
        if a.get("email"):
            await send_email(db, a["email"],
                             f"🌙 Gün Sonu Raporu — {prop.get('name', pid)} · {business_date}",
                             html, kind="eod_report", meta={"property_id": pid})
            sent_to.append(a["email"])
    doc = {"id": str(uuid.uuid4()), "property_id": pid, "business_date": business_date,
           "report": report, "sent_to": sent_to, "forced": forced,
           "created_at": _now().isoformat()}
    await db.eod_reports.insert_one(dict(doc))
    doc.pop("_id", None)
    logger.info("EOD raporu gönderildi: %s %s → %s alıcı", pid, business_date, len(sent_to))
    return doc


def create_eod_report_router(db, require_roles):
    router = APIRouter(prefix="/eod-report", tags=["eod-report"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}/latest")
    async def latest(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        doc = await db.eod_reports.find_one({"property_id": pid}, {"_id": 0},
                                            sort=[("created_at", -1)])
        today = _now().date().isoformat()
        preview = await build_eod(db, pid, today)
        return {"latest": doc, "live_preview": preview}

    @router.get("/{pid}/history")
    async def history(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        docs = await db.eod_reports.find({"property_id": pid}, {"_id": 0}).sort(
            "created_at", -1).to_list(30)
        return {"history": docs}

    @router.post("/{pid}/send-now")
    async def send_now(pid: str, data: Dict = None, _u: dict = Depends(require_roles(*ROLES))):
        data = data or {}
        business_date = data.get("business_date") or _now().date().isoformat()
        return await send_eod(db, pid, business_date, forced=True)

    return router
