"""BE Paket 39-A: dönüşüm hunisi analitiği, onay .ics/PDF, oda bazlı doğrulanmış yorumlar."""
import io
import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

FUNNEL_STEPS = ["search", "rooms", "room_view", "rate_select", "details", "payment", "confirm"]
STEP_LABELS = {"search": "Arama", "rooms": "Oda listesi", "room_view": "Oda detayı", "rate_select": "Plan seçimi / sepet", "details": "Misafir bilgileri", "payment": "Ödeme", "confirm": "Onay"}
now_iso = lambda: datetime.now(timezone.utc).isoformat()


class FunnelEvent(BaseModel):
    property_id: str
    session_id: str = Field(min_length=6, max_length=80)
    step: str
    device: str = "desktop"
    source: str = ""
    medium: str = ""
    campaign: str = ""
    lang: str = ""
    meta: Dict = Field(default_factory=dict)


def _ics_escape(s: str) -> str:
    return re.sub(r"([,;\\])", r"\\\1", str(s or "")).replace("\n", "\\n")


def build_ics(b: dict, prop: dict) -> str:
    ci = b["check_in"].replace("-", ""); co = b["check_out"].replace("-", "")
    summary = f"{prop.get('name', 'Otel')} — {b.get('booking_ref')}"
    desc = f"Rezervasyon {b.get('booking_ref')}\\nOda: {b.get('room_name') or b.get('room_type', '')}\\nMisafir: {b.get('guest_name', '')}\\nGiriş: {b['check_in']} · Çıkış: {b['check_out']}"
    if prop.get("check_in_time"):
        desc += f"\\nCheck-in: {prop['check_in_time']}"
    loc = ", ".join(x for x in [prop.get("address"), prop.get("city"), prop.get("country")] if x)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MyHotelBox//Booking//TR", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
             f"UID:{b.get('booking_ref')}@myhotelbox", f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
             f"DTSTART;VALUE=DATE:{ci}", f"DTEND;VALUE=DATE:{co}", f"SUMMARY:{_ics_escape(summary)}", f"DESCRIPTION:{desc}",
             f"LOCATION:{_ics_escape(loc)}", "STATUS:CONFIRMED", "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY", f"DESCRIPTION:{_ics_escape('Yarın otel girişi: ' + prop.get('name', ''))}", "END:VALARM", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def build_pdf(b: dict, prop: dict, items: List[dict]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); w, h = A4
    c.setFillColor(colors.HexColor("#0f172a")); c.rect(0, h - 38 * mm, w, 38 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 20); c.drawString(20 * mm, h - 18 * mm, prop.get("name", "Hotel"))
    c.setFont("Helvetica", 10); c.drawString(20 * mm, h - 26 * mm, ", ".join(x for x in [prop.get("address"), prop.get("city"), prop.get("country")] if x)[:110])
    c.drawString(20 * mm, h - 32 * mm, " · ".join(x for x in [prop.get("phone"), prop.get("email")] if x)[:110])
    c.setFillColor(colors.HexColor("#0f172a")); c.setFont("Helvetica-Bold", 16); c.drawString(20 * mm, h - 52 * mm, "Booking Confirmation / Rezervasyon Onayı")
    c.setFont("Helvetica-Bold", 22); c.setFillColor(colors.HexColor("#0f766e")); c.drawString(20 * mm, h - 63 * mm, str(b.get("booking_ref", "")))
    c.setFillColor(colors.black); c.setFont("Helvetica", 11); y = h - 78 * mm
    rows = [("Guest / Misafir", b.get("guest_name", "")), ("Email", b.get("guest_email", "")), ("Check-in / Giriş", f"{b.get('check_in')}  {prop.get('check_in_time') or ''}"),
            ("Check-out / Çıkış", f"{b.get('check_out')}  {prop.get('check_out_time') or ''}"), ("Nights / Gece", str(b.get("nights") or "")),
            ("Guests / Kişi", f"{b.get('adults', 0)} adult(s)" + (f", {b.get('children')} child(ren)" if b.get("children") else "")),
            ("Status / Durum", f"{b.get('status', '')} · payment: {b.get('payment_status', '')}")]
    for k, v in rows:
        c.setFont("Helvetica-Bold", 10); c.drawString(20 * mm, y, k); c.setFont("Helvetica", 10); c.drawString(70 * mm, y, str(v)[:90]); y -= 7 * mm
    y -= 4 * mm; c.setFont("Helvetica-Bold", 11); c.drawString(20 * mm, y, "Rooms / Odalar"); y -= 7 * mm
    c.setFont("Helvetica", 10)
    for it in items or [{"qty": b.get("rooms", 1), "room_name": b.get("room_name") or b.get("room_type", ""), "rate_plan_name": "", "total": b.get("total_price", 0)}]:
        c.drawString(20 * mm, y, f"{it.get('qty', 1)} × {it.get('room_name', '')}" + (f" · {it['rate_plan_name']}" if it.get("rate_plan_name") else ""))
        c.drawRightString(w - 20 * mm, y, f"{b.get('currency', 'GBP')} {float(it.get('total') or 0):,.2f}"); y -= 6.5 * mm
    y -= 3 * mm; c.setStrokeColor(colors.HexColor("#cbd5e1")); c.line(20 * mm, y, w - 20 * mm, y); y -= 8 * mm
    c.setFont("Helvetica-Bold", 13); c.drawString(20 * mm, y, "Total / Toplam"); c.drawRightString(w - 20 * mm, y, f"{b.get('currency', 'GBP')} {float(b.get('cart_total') or b.get('total_price') or 0):,.2f}")
    if b.get("balance_due"):
        y -= 7 * mm; c.setFont("Helvetica", 10); c.drawString(20 * mm, y, "Balance due at hotel / Otelde ödenecek"); c.drawRightString(w - 20 * mm, y, f"{b.get('currency', 'GBP')} {float(b['balance_due']):,.2f}")
    if b.get("special_requests"):
        y -= 12 * mm; c.setFont("Helvetica-Bold", 10); c.drawString(20 * mm, y, "Requests / İstekler"); c.setFont("Helvetica", 10); c.drawString(70 * mm, y, str(b["special_requests"])[:100])
    c.setFont("Helvetica-Oblique", 8); c.setFillColor(colors.HexColor("#64748b")); c.drawString(20 * mm, 15 * mm, f"Generated {now_iso()[:16].replace('T', ' ')} UTC · Please present this confirmation at check-in.")
    c.showPage(); c.save()
    return buf.getvalue()


async def _step_drops(db, pid: str, since: str, until: str) -> tuple:
    rows = await db.be_funnel_events.find({"property_id": pid, "at": {"$gte": since, "$lt": until}}, {"_id": 0, "session_id": 1, "step": 1}).to_list(100000)
    sess: Dict[str, set] = defaultdict(set)
    for r in rows:
        sess[r["session_id"]].add(r["step"])
    counts = {st: sum(1 for v in sess.values() if st in v) for st in FUNNEL_STEPS}
    drops, prev = {}, None
    for st in FUNNEL_STEPS:
        n = counts[st]
        if prev:
            drops[st] = round((1 - n / prev) * 100, 1)
        prev = n if n else prev
    return len(sess), drops


async def check_funnel_alerts(db, pid: Optional[str] = None) -> dict:
    """Son 24 saatteki adım düşüşü, önceki 7 gün ortalamasını eşik puanı kadar aşarsa → bildirim + MOCK e-posta (gün/adım başına 1)."""
    from routes.platform_ext.mailer import send_email
    from routes.pms.be_gaps import get_be_settings
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(days=1)).isoformat(); week_ago = (now - timedelta(days=8)).isoformat()
    pids = [pid] if pid else await db.be_funnel_events.distinct("property_id", {"at": {"$gte": day_ago}})
    out = {"checked": 0, "alerts": []}
    for p in pids:
        st = await get_be_settings(db, p)
        if not st.get("funnel_alert_enabled", True):
            continue
        out["checked"] += 1
        n24, d24 = await _step_drops(db, p, day_ago, now.isoformat())
        if n24 < int(st.get("funnel_alert_min_sessions") or 20):
            continue
        _, d7 = await _step_drops(db, p, week_ago, day_ago)
        thr = float(st.get("funnel_alert_threshold_pts") or 15)
        prop = await db.properties.find_one({"id": p}, {"_id": 0, "name": 1}) or {}
        for step, drop in d24.items():
            base = d7.get(step)
            if base is None:  # 7g baz yok (yeni tesis) → sadece ciddi kayıpta uyar
                base = 0.0
                if drop < 60:
                    continue
            elif drop < base + thr or drop < 30:
                continue
            key = f"{p}:{step}:{now.date().isoformat()}"
            if await db.funnel_alerts.find_one({"key": key}, {"_id": 0, "id": 1}):
                continue
            title = f"⚠ Huni uyarısı — {STEP_LABELS[step]} adımında düşüş %{drop} (7g ort. %{base})"
            body = f"{prop.get('name', p)}: son 24 saatte {n24} oturum; '{STEP_LABELS[step]}' adımındaki kayıp 7 günlük ortalamanın {round(drop - base, 1)} puan üzerinde. Booking Engine → Huni Analitiği'nden inceleyin."
            emails = [u["email"] for u in await db.users.find({"role": {"$in": ["admin", "manager"]}}, {"_id": 0, "email": 1}).to_list(20)]
            statuses = [await send_email(db, e, title, f"<div style='font-family:system-ui'><h3>{title}</h3><p>{body}</p></div>", kind="funnel_alert", meta={"property_id": p, "step": step}) for e in emails[:10]]
            await db.notifications.insert_one({"id": str(uuid.uuid4()), "property_id": p, "type": "funnel_alert", "title": title, "body": body, "read": False, "created_at": now_iso()})
            doc = {"id": str(uuid.uuid4()), "key": key, "property_id": p, "step": step, "step_label": STEP_LABELS[step], "drop_24h": drop, "avg_7d": base, "sessions_24h": n24, "emails": emails[:10], "email_status": statuses, "created_at": now_iso()}
            await db.funnel_alerts.insert_one(dict(doc))
            out["alerts"].append(doc)
    return out


async def funnel_alert_loop(db, interval_seconds: int = 21600):
    import asyncio
    await asyncio.sleep(180)
    while True:
        try:
            await check_funnel_alerts(db)
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)


async def ai_tag_reviews(db, pid: str, limit: int = 40) -> dict:
    """LLM ile yorum → oda tipi eşleme (oda_type_id yoksa). Anahtar yoksa kelime eşleşmesi yedeği."""
    import json
    import os
    rooms = await db.room_types.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1, "description": 1}).to_list(50)
    reviews = await db.reviews.find({"property_id": pid, "room_type_id": {"$in": [None, ""]}, "room_tag_attempted": {"$ne": True}}, {"_id": 0, "id": 1, "comment": 1, "review_text": 1}).sort("created_at", -1).to_list(limit)
    reviews = [r for r in reviews if (r.get("comment") or r.get("review_text") or "").strip()]
    if not rooms or not reviews:
        return {"tagged": 0, "processed": 0, "source": "none"}
    mapping: Dict[str, dict] = {}
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    source = "heuristic"
    if api_key:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            room_list = "\n".join(f"- id={r['id']} | {r['name']}: {(r.get('description') or '')[:120]}" for r in rooms)
            rev_list = "\n".join(f"[{r['id']}] {(r.get('comment') or r.get('review_text') or '')[:400]}" for r in reviews)
            prompt = f"""Hotel room types:\n{room_list}\n\nGuest reviews (id in brackets):\n{rev_list}\n\nFor each review decide which room type the guest most likely stayed in based ONLY on explicit clues (room name, bed type, suite/family/king/twin, size, view, kitchen). If there is no clear clue return null. Respond with pure JSON: {{"<review_id>": {{"room_type_id": "<id or null>", "confidence": 0-1}}}}"""
            chat = LlmChat(api_key=api_key, session_id=f"room-tag-{uuid.uuid4()}", system_message="You map hotel reviews to room types. Output JSON only.").with_model("openai", "gpt-5.2")
            txt = (await chat.send_message(UserMessage(text=prompt))).strip()
            txt = txt[txt.find("{"): txt.rfind("}") + 1]
            mapping = json.loads(txt); source = "ai"
        except Exception:
            mapping = {}
    if not mapping:
        stop = {"room", "rooms", "oda", "suite", "the", "standard", "double", "with", "and"}
        toks = {r["id"]: [t for t in re.findall(r"[a-zçğıöşü]+", r["name"].lower()) if len(t) > 3 and t not in stop] for r in rooms}
        for rv in reviews:
            low = (rv.get("comment") or rv.get("review_text") or "").lower()
            hits = [rid for rid, tk in toks.items() if tk and all(t in low for t in tk)]
            mapping[rv["id"]] = {"room_type_id": hits[0] if len(hits) == 1 else None, "confidence": 0.6 if len(hits) == 1 else 0}
    valid = {r["id"] for r in rooms}
    tagged = 0
    for rv in reviews:
        m = mapping.get(rv["id"]) or {}
        rid = m.get("room_type_id") if m.get("room_type_id") in valid and float(m.get("confidence") or 0) >= 0.5 else None
        upd = {"room_tag_attempted": True, "room_tag_source": source, "room_tag_confidence": float(m.get("confidence") or 0), "room_tag_at": now_iso()}
        if rid:
            upd["room_type_id"] = rid; tagged += 1
        await db.reviews.update_one({"id": rv["id"]}, {"$set": upd})
    return {"tagged": tagged, "processed": len(reviews), "source": source}


def create_be_extras_router(db, require_roles):
    router = APIRouter(tags=["booking-engine-extras"])

    # ---------------- Huni analitiği ----------------
    @router.post("/booking/funnel/event")
    async def funnel_event(ev: FunnelEvent):
        if ev.step not in FUNNEL_STEPS:
            raise HTTPException(422, f"step: {FUNNEL_STEPS}")
        doc = {"id": str(uuid.uuid4()), **ev.model_dump(), "device": ev.device if ev.device in ("mobile", "tablet", "desktop") else "desktop", "at": now_iso()}
        doc["source"] = (doc["source"] or "direct")[:40]; doc["medium"] = doc["medium"][:40]; doc["campaign"] = doc["campaign"][:60]
        await db.be_funnel_events.insert_one(doc)
        return {"ok": True}

    @router.get("/booking/funnel/{pid}")
    async def funnel_report(pid: str, days: int = 30, _u: dict = Depends(require_roles("admin", "manager", "revenue_manager"))):
        days = max(1, min(180, days))
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.be_funnel_events.find({"property_id": pid, "at": {"$gte": since}}, {"_id": 0, "session_id": 1, "step": 1, "device": 1, "source": 1, "at": 1}).to_list(200000)
        sess: Dict[str, dict] = {}
        for r in rows:
            s = sess.setdefault(r["session_id"], {"steps": set(), "device": r.get("device") or "desktop", "source": r.get("source") or "direct", "day": r["at"][:10]})
            s["steps"].add(r["step"])
        total = len(sess)
        counts = {st: sum(1 for s in sess.values() if st in s["steps"]) for st in FUNNEL_STEPS}
        steps = []
        prev = None
        for st in FUNNEL_STEPS:
            n = counts[st]
            steps.append({"step": st, "label": STEP_LABELS[st], "sessions": n, "pct_of_start": round(n / total * 100, 1) if total else 0,
                          "drop_pct": round((1 - n / prev) * 100, 1) if prev else 0})
            prev = n if n else prev
        def _grp(key):
            g: Dict[str, dict] = defaultdict(lambda: {"sessions": 0, "confirm": 0})
            for s in sess.values():
                g[s[key]]["sessions"] += 1; g[s[key]]["confirm"] += 1 if "confirm" in s["steps"] else 0
            return [{key: k, **v, "cr": round(v["confirm"] / v["sessions"] * 100, 1) if v["sessions"] else 0} for k, v in sorted(g.items(), key=lambda x: -x[1]["sessions"])]
        daily: Dict[str, dict] = defaultdict(lambda: {"sessions": 0, "confirm": 0})
        for s in sess.values():
            daily[s["day"]]["sessions"] += 1; daily[s["day"]]["confirm"] += 1 if "confirm" in s["steps"] else 0
        biggest = max((x for x in steps[1:]), key=lambda x: x["drop_pct"], default=None)
        return {"property_id": pid, "days": days, "sessions": total, "conversions": counts["confirm"], "conversion_rate": round(counts["confirm"] / total * 100, 2) if total else 0,
                "steps": steps, "by_device": _grp("device"), "by_source": _grp("source"), "daily": [{"date": d, **v} for d, v in sorted(daily.items())],
                "biggest_drop": biggest, "events": len(rows)}

    # ---------------- Onay: .ics + PDF ----------------
    async def _booking_for(ref: str, email: str):
        b = await db.bookings.find_one({"$or": [{"booking_ref": ref}, {"id": ref}]}, {"_id": 0})
        if not b or (b.get("guest_email") or "").lower() != (email or "").lower():
            raise HTTPException(404, "Rezervasyon bulunamadı")
        prop = await db.properties.find_one({"id": b["property_id"]}, {"_id": 0, "name": 1, "address": 1, "city": 1, "country": 1, "phone": 1, "email": 1, "check_in_time": 1, "check_out_time": 1}) or {}
        b.setdefault("booking_ref", b.get("id"))
        return b, prop

    @router.get("/booking/{ref}/calendar.ics")
    async def booking_ics(ref: str, email: str):
        b, prop = await _booking_for(ref, email)
        return Response(build_ics(b, prop), media_type="text/calendar; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{b["booking_ref"]}.ics"'})

    @router.get("/booking/{ref}/confirmation.pdf")
    async def booking_pdf(ref: str, email: str):
        b, prop = await _booking_for(ref, email)
        items = b.get("cart_items") or []
        if not items and b.get("cart_id"):
            items = [{"qty": x.get("rooms", 1), "room_name": x.get("room_name") or x.get("room_type", ""), "rate_plan_name": x.get("rate_plan_name", ""), "total": x.get("total_price", 0)}
                     async for x in db.bookings.find({"cart_id": b["cart_id"]}, {"_id": 0})]
        return Response(build_pdf(b, prop, items), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{b["booking_ref"]}.pdf"'})

    # ---------------- Oda bazlı doğrulanmış yorumlar ----------------
    @router.get("/booking/room-reviews/{pid}")
    async def room_reviews(pid: str):
        rooms = await db.room_types.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1}).to_list(100)
        reviews = await db.reviews.find({"property_id": pid, "rating": {"$exists": True}}, {"_id": 0, "id": 1, "rating": 1, "comment": 1, "review_text": 1, "author": 1, "guest_name": 1, "created_at": 1, "room_type_id": 1, "booking_ref": 1, "guest_email": 1, "platform": 1, "source": 1}).sort("created_at", -1).to_list(2000)
        ref_map, email_map = {}, {}
        refs = [r["booking_ref"] for r in reviews if r.get("booking_ref")]
        emails = [r["guest_email"].lower() for r in reviews if r.get("guest_email")]
        if refs or emails:
            async for b in db.bookings.find({"property_id": pid, "$or": [{"booking_ref": {"$in": refs}}, {"guest_email": {"$in": emails}}]}, {"_id": 0, "booking_ref": 1, "guest_email": 1, "room_type_id": 1}):
                ref_map[b.get("booking_ref")] = b.get("room_type_id"); email_map[(b.get("guest_email") or "").lower()] = b.get("room_type_id")
        stop = {"room", "rooms", "oda", "suite", "the", "standard", "double", "with", "and"}
        tokens = {r["id"]: [t for t in re.findall(r"[a-zçğıöşü]+", r["name"].lower()) if len(t) > 3 and t not in stop] for r in rooms}
        per: Dict[str, dict] = {r["id"]: {"room_type_id": r["id"], "name": r["name"], "count": 0, "sum": 0.0, "quotes": [], "verified": 0} for r in rooms}
        prop_sum = prop_n = 0
        for rv in reviews:
            try:
                rating = float(rv.get("rating") or 0)
            except (TypeError, ValueError):
                continue
            if rating <= 0:
                continue
            prop_sum += rating; prop_n += 1
            text = (rv.get("comment") or rv.get("review_text") or "").strip()
            rid = rv.get("room_type_id") or ref_map.get(rv.get("booking_ref")) or email_map.get((rv.get("guest_email") or "").lower())
            verified = bool(rid)
            if not rid:
                low = text.lower()
                hits = [r for r, toks in tokens.items() if toks and all(t in low for t in toks)] or [r for r, toks in tokens.items() if any(t in low for t in toks)]
                rid = hits[0] if len(hits) == 1 else None
            if not rid or rid not in per:
                continue
            p = per[rid]; p["count"] += 1; p["sum"] += rating; p["verified"] += 1 if verified else 0
            if rating >= 4 and text and len(p["quotes"]) < 2:
                p["quotes"].append({"text": (text[:157] + "…") if len(text) > 160 else text, "author": rv.get("author") or rv.get("guest_name") or "Misafir", "rating": rating, "verified": verified, "platform": rv.get("platform") or "", "date": (rv.get("created_at") or "")[:10]})
        out = []
        for p in per.values():
            out.append({"room_type_id": p["room_type_id"], "name": p["name"], "count": p["count"], "avg": round(p["sum"] / p["count"], 1) if p["count"] else None, "verified": p["verified"], "quotes": p["quotes"]})
        return {"property_id": pid, "property_avg": round(prop_sum / prop_n, 1) if prop_n else None, "property_count": prop_n, "rooms": out}

    @router.get("/booking/funnel-alerts/{pid}")
    async def funnel_alerts_list(pid: str, _u: dict = Depends(require_roles("admin", "manager", "revenue_manager"))):
        rows = await db.funnel_alerts.find({"property_id": pid}, {"_id": 0, "emails": 0}).sort("created_at", -1).to_list(30)
        return {"alerts": rows}

    @router.post("/booking/funnel-alerts/{pid}/check")
    async def funnel_alerts_check(pid: str, _u: dict = Depends(require_roles("admin", "manager"))):
        return await check_funnel_alerts(db, pid)

    @router.post("/booking/room-reviews/{pid}/auto-tag")
    async def auto_tag(pid: str, limit: int = 40, _u: dict = Depends(require_roles("admin", "manager"))):
        return await ai_tag_reviews(db, pid, limit)

    @router.post("/booking/room-reviews/{pid}/reset-tags")
    async def reset_tags(pid: str, _u: dict = Depends(require_roles("admin"))):
        r = await db.reviews.update_many({"property_id": pid, "room_tag_source": {"$exists": True}}, {"$unset": {"room_type_id": "", "room_tag_attempted": "", "room_tag_source": "", "room_tag_confidence": ""}})
        return {"reset": r.modified_count}

    @router.put("/booking/room-reviews/{review_id}/tag")
    async def tag_review_room(review_id: str, data: dict, _u: dict = Depends(require_roles("admin", "manager"))):
        """Yorumu bir oda tipine bağla (doğrulanmış sayılır) — guest_collection yorumları booking_ref ile otomatik bağlanır."""
        rid = str(data.get("room_type_id") or "")
        rv = await db.reviews.find_one({"id": review_id}, {"_id": 0, "property_id": 1})
        if not rv:
            raise HTTPException(404, "Yorum yok")
        if rid and not await db.room_types.find_one({"id": rid, "property_id": rv["property_id"]}, {"_id": 0, "id": 1}):
            raise HTTPException(422, "room_type_id bu tesise ait değil")
        await db.reviews.update_one({"id": review_id}, {"$set": {"room_type_id": rid or None, "room_tagged_by": _u.get("email"), "room_tagged_at": now_iso()}})
        return {"ok": True, "review_id": review_id, "room_type_id": rid or None}

    return router
