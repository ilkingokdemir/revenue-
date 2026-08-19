"""iCal Senkronu — API'siz kanallar (Airbnb, Vrbo...) için içe/dışa takvim aktarımı."""
import re
import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response

logger = logging.getLogger(__name__)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_ics(text: str) -> list:
    """VEVENT'lerden (DTSTART/DTEND, DATE veya DATE-TIME) busy aralıkları çıkarır."""
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        def _get(field):
            m = re.search(rf"{field}[^:]*:([\w]+)", block)
            return m.group(1) if m else None
        ds, de = _get("DTSTART"), _get("DTEND")
        if not ds:
            continue
        def _date(v):
            v = v[:8]
            try:
                return datetime.strptime(v, "%Y%m%d").date().isoformat()
            except Exception:
                return None
        start = _date(ds)
        end = _date(de) if de else start
        if not start:
            continue
        sm = re.search(r"SUMMARY:(.+)", block)
        um = re.search(r"UID:(.+)", block)
        events.append({"start": start, "end": end or start,
                       "summary": (sm.group(1).strip() if sm else "Busy")[:80],
                       "uid": (um.group(1).strip() if um else "")[:120]})
    return events


async def sync_ical_source(db, src: dict) -> dict:
    """Tek kaynağı çeker, oos_blocks'u kaynak bazında yeniler."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(src["url"])
            r.raise_for_status()
            events = parse_ics(r.text)
    except Exception as e:
        await db.ical_sources.update_one({"id": src["id"]}, {"$set": {
            "last_sync": now_iso(), "last_status": "error", "last_error": str(e)[:200]}})
        return {"source_id": src["id"], "status": "error", "error": str(e)[:200]}

    await db.oos_blocks.delete_many({"ical_source_id": src["id"]})
    count = 0
    for ev in events:
        if ev["end"] <= ev["start"]:
            ev["end"] = ev["start"]
        await db.oos_blocks.insert_one({
            "id": str(uuid.uuid4()), "property_id": src["property_id"], "room_id": src["room_id"],
            "start": ev["start"], "end": ev["end"],
            "reason": f"iCal: {src.get('channel_name') or 'Harici'} — {ev['summary']}",
            "ical_source_id": src["id"], "ical_uid": ev["uid"],
            "created_by": "ical_sync", "created_at": now_iso()})
        count += 1
    await db.ical_sources.update_one({"id": src["id"]}, {"$set": {
        "last_sync": now_iso(), "last_status": "ok", "last_error": None, "blocks_count": count}})

    # --- Çifte rezervasyon alarmı: iCal bloğu ↔ içerideki rezervasyon çakışması ---
    conflicts_found = 0
    try:
        bookings = await db.bookings.find(
            {"property_id": src["property_id"], "room_id": src["room_id"],
             "status": {"$nin": ["cancelled", "no_show"]}},
            {"_id": 0, "id": 1, "guest_name": 1, "check_in": 1, "check_out": 1}).to_list(2000)
        seen_keys = []
        new_conflicts = []
        for ev in events:
            for b in bookings:
                ci, co = str(b.get("check_in") or ""), str(b.get("check_out") or "")
                if not ci or not co:
                    continue
                if ci < ev["end"] and co > ev["start"]:
                    key = f"{src['id']}:{b['id']}:{ev['start']}:{ev['end']}"
                    seen_keys.append(key)
                    existing = await db.ical_conflicts.find_one({"key": key}, {"_id": 1})
                    await db.ical_conflicts.update_one({"key": key}, {"$set": {
                        "key": key, "property_id": src["property_id"], "room_id": src["room_id"],
                        "room_name": src.get("room_name", ""), "source_id": src["id"],
                        "channel_name": src.get("channel_name", "iCal"), "booking_id": b["id"],
                        "guest_name": b.get("guest_name", ""), "check_in": ci, "check_out": co,
                        "block_start": ev["start"], "block_end": ev["end"],
                        "status": "open", "last_seen": now_iso()},
                        "$setOnInsert": {"id": str(uuid.uuid4()), "first_seen": now_iso()}}, upsert=True)
                    conflicts_found += 1
                    if not existing:
                        new_conflicts.append((ev, b, ci, co))
        # Bildirim: ilk 3 yeni çakışma tekil, kalanı tek özet (bildirim patlamasını önle)
        for ev, b, ci, co in new_conflicts[:3]:
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "property_id": src["property_id"],
                "type": "ical_conflict",
                "title": f"⚠️ Çifte rezervasyon riski: {src.get('room_name', '')}",
                "message": f"{src.get('channel_name', 'iCal')} takvim bloğu ({ev['start']} → {ev['end']}) "
                           f"içerideki rezervasyonla çakışıyor: {b.get('guest_name', '')} ({ci} → {co}). "
                           f"Kanallardan birini kapatın!",
                "read": False, "created_at": now_iso()})
        if len(new_conflicts) > 3:
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "property_id": src["property_id"],
                "type": "ical_conflict",
                "title": f"⚠️ {len(new_conflicts)} çifte rezervasyon çakışması: {src.get('room_name', '')}",
                "message": f"{src.get('channel_name', 'iCal')} senkronunda {len(new_conflicts)} çakışma bulundu. "
                           f"Detaylar iCal Senkronu panelinde.",
                "read": False, "created_at": now_iso()})
        # Bu kaynağın artık görülmeyen çakışmalarını çözüldü işaretle
        await db.ical_conflicts.update_many(
            {"source_id": src["id"], "status": "open", "key": {"$nin": seen_keys}},
            {"$set": {"status": "resolved", "resolved_at": now_iso()}})
    except Exception as e:
        logger.warning(f"ical conflict check error: {e}")

    return {"source_id": src["id"], "status": "ok", "blocks": count, "conflicts": conflicts_found}


def create_ical_router(db, require_roles):
    router = APIRouter(prefix="/ical", tags=["ical"])
    ROLES = ("admin", "manager")

    def _check_scope(u: dict, pid: str):
        scoped = u.get("property_ids")
        if scoped and u.get("role") != "admin" and pid not in scoped:
            raise HTTPException(403, "Bu tesise erişim yetkiniz yok")

    async def _token(pid: str) -> str:
        s = await db.ical_settings.find_one({"property_id": pid}, {"_id": 0})
        if s and s.get("export_token"):
            return s["export_token"]
        tok = secrets.token_urlsafe(18)
        await db.ical_settings.update_one({"property_id": pid},
                                          {"$set": {"export_token": tok, "created_at": now_iso()}}, upsert=True)
        return tok

    # ---------------- PUBLIC EXPORT FEED ----------------
    @router.get("/export/{pid}.ics")
    async def export_feed(pid: str, token: str, room_type_id: str = None):
        s = await db.ical_settings.find_one({"property_id": pid}, {"_id": 0})
        if not s or s.get("export_token") != token:
            raise HTTPException(403, "Geçersiz token")
        q = {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]}}
        if room_type_id:
            q["room_type_id"] = room_type_id
        bks = await db.bookings.find(q, {"_id": 0, "id": 1, "check_in": 1, "check_out": 1}).to_list(3000)
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MyHotelBox//RMS//TR", "CALSCALE:GREGORIAN"]
        for b in bks:
            ci, co = str(b.get("check_in") or ""), str(b.get("check_out") or "")
            if len(ci) < 10 or len(co) < 10:
                continue
            lines += ["BEGIN:VEVENT", f"UID:{b['id']}@myhotelbox",
                      f"DTSTART;VALUE=DATE:{ci[:10].replace('-', '')}",
                      f"DTEND;VALUE=DATE:{co[:10].replace('-', '')}",
                      "SUMMARY:Reserved", "END:VEVENT"]
        lines.append("END:VCALENDAR")
        return Response(content="\r\n".join(lines), media_type="text/calendar",
                        headers={"Content-Disposition": f'attachment; filename="{pid}.ics"'})

    # ---------------- YÖNETİM ----------------
    @router.get("/{pid}")
    async def get_ical(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        sources = await db.ical_sources.find({"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(50)
        rooms = await db.rooms.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1}).to_list(200)
        rts = await db.room_types.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
        conflicts = await db.ical_conflicts.find({"property_id": pid, "status": "open"},
                                                 {"_id": 0}).sort("last_seen", -1).to_list(50)
        return {"sources": sources, "rooms": rooms, "room_types": rts,
                "conflicts": conflicts, "export_token": await _token(pid)}

    @router.post("/{pid}/sources")
    async def add_source(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        url = (data.get("url") or "").strip()
        room_id = data.get("room_id")
        if not url.startswith(("http://", "https://")):
            raise HTTPException(400, "Geçerli bir iCal URL girin (https://...)")
        if not room_id:
            raise HTTPException(400, "Oda seçimi zorunlu")
        room = await db.rooms.find_one({"id": room_id, "property_id": pid}, {"_id": 0, "name": 1})
        if not room:
            raise HTTPException(404, "Oda bulunamadı")
        doc = {"id": str(uuid.uuid4()), "property_id": pid, "room_id": room_id,
               "room_name": room.get("name", room_id), "channel_name": (data.get("channel_name") or "Airbnb").strip(),
               "url": url, "last_sync": None, "last_status": "pending", "blocks_count": 0,
               "created_by": _u.get("name", ""), "created_at": now_iso()}
        await db.ical_sources.insert_one({**doc})
        result = await sync_ical_source(db, doc)
        doc.pop("_id", None)
        return {"ok": True, "source": doc, "first_sync": result}

    @router.delete("/{pid}/sources/{sid}")
    async def delete_source(pid: str, sid: str, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        r = await db.ical_sources.delete_one({"id": sid, "property_id": pid})
        if r.deleted_count == 0:
            raise HTTPException(404, "Kaynak bulunamadı")
        blocks = await db.oos_blocks.delete_many({"ical_source_id": sid})
        await db.ical_conflicts.delete_many({"source_id": sid})
        return {"ok": True, "blocks_removed": blocks.deleted_count}

    @router.post("/{pid}/sync")
    async def sync_all(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        sources = await db.ical_sources.find({"property_id": pid}, {"_id": 0}).to_list(50)
        if not sources:
            raise HTTPException(400, "Önce bir iCal kaynağı ekleyin")
        results = [await sync_ical_source(db, s) for s in sources]
        return {"ok": True, "results": results}

    @router.post("/{pid}/rotate-token")
    async def rotate_token(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        tok = secrets.token_urlsafe(18)
        await db.ical_settings.update_one({"property_id": pid},
                                          {"$set": {"export_token": tok, "rotated_at": now_iso()}}, upsert=True)
        return {"ok": True, "export_token": tok}

    return router
