"""Arrival reminder robot — T-2 pre-arrival e-mail in guest language (TR/EN/DE) + event packages."""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict
from urllib.parse import quote_plus

from fastapi import APIRouter, HTTPException, Depends

from routes.platform_ext.mailer import send_email

logger = logging.getLogger(__name__)

DAYS_BEFORE = 2
T = {
    "en": {"subject": "See you in {days} days — your stay at {hotel} ({ref})", "title": "We're getting your room ready",
           "hi": "Dear {name}, your arrival is in {days} days. Here's everything you need for a smooth check-in.",
           "checkin": "Check-in from", "checkout": "Check-out until", "address": "Address", "directions": "Open directions in Google Maps",
           "ref": "Booking reference", "room": "Room", "upsell": "Make your stay even better", "upsell_hint": "Reply to this e-mail and we'll add it to your booking.",
           "footer": "Questions? Just reply — we're happy to help. See you soon!", "per_stay": "per stay", "per_night": "per night", "add": "Add to my booking"},
    "tr": {"subject": "{days} gün sonra görüşürüz — {hotel} konaklamanız ({ref})", "title": "Odanızı hazırlıyoruz",
           "hi": "Sayın {name}, girişinize {days} gün kaldı. Sorunsuz bir check-in için ihtiyacınız olan her şey burada.",
           "checkin": "Giriş saati", "checkout": "Çıkış saati", "address": "Adres", "directions": "Google Haritalar'da yol tarifini aç",
           "ref": "Rezervasyon numarası", "room": "Oda", "upsell": "Konaklamanızı daha da güzelleştirin", "upsell_hint": "Bu e-postayı yanıtlayın, rezervasyonunuza ekleyelim.",
           "footer": "Sorunuz mu var? Yanıtlamanız yeterli — yardımcı olmaktan mutluluk duyarız. Görüşmek üzere!", "per_stay": "konaklama başına", "per_night": "gece başına", "add": "Rezervasyonuma ekle"},
    "de": {"subject": "Bis in {days} Tagen — Ihr Aufenthalt im {hotel} ({ref})", "title": "Wir bereiten Ihr Zimmer vor",
           "hi": "Liebe/r {name}, Ihre Anreise ist in {days} Tagen. Hier finden Sie alles für einen reibungslosen Check-in.",
           "checkin": "Check-in ab", "checkout": "Check-out bis", "address": "Adresse", "directions": "Route in Google Maps öffnen",
           "ref": "Buchungsnummer", "room": "Zimmer", "upsell": "Machen Sie Ihren Aufenthalt noch schöner", "upsell_hint": "Antworten Sie auf diese E-Mail und wir fügen es Ihrer Buchung hinzu.",
           "footer": "Fragen? Einfach antworten — wir helfen gerne. Bis bald!", "per_stay": "pro Aufenthalt", "per_night": "pro Nacht", "add": "Zu meiner Buchung hinzufügen"},
}
DEFAULT_UPSELLS = [
    {"name": {"en": "Late check-out (until 14:00)", "tr": "Geç çıkış (14:00'e kadar)", "de": "Later Check-out (bis 14:00)"}, "price": 20.0, "price_type": "per_stay"},
    {"name": {"en": "Breakfast for two", "tr": "İki kişilik kahvaltı", "de": "Frühstück für zwei"}, "price": 15.0, "price_type": "per_night"},
    {"name": {"en": "Room upgrade (subject to availability)", "tr": "Oda yükseltme (müsaitliğe bağlı)", "de": "Zimmer-Upgrade (nach Verfügbarkeit)"}, "price": 35.0, "price_type": "per_night"},
]
DEFAULT_PACKAGE = {"name_en": "Event Package: breakfast + late check-out (14:00)", "name_tr": "Etkinlik Paketi: kahvaltı + geç çıkış (14:00)",
                   "name_de": "Event-Paket: Frühstück + Late Check-out (14:00)", "price_per_night": 25.0,
                   "includes": ["breakfast", "late_checkout"], "enabled": True}


def _sym(cur: str) -> str:
    return {"GBP": "£", "EUR": "€", "USD": "$", "CHF": "CHF ", "TRY": "₺"}.get(cur or "GBP", (cur or "") + " ")


def build_arrival_email(booking: dict, hotel: dict, upsells: list, lang: str) -> tuple:
    lang = lang if lang in T else "en"
    t = T[lang]
    sym = _sym(booking.get("currency", "GBP"))
    addr = ", ".join(x for x in [hotel.get("address"), hotel.get("city"), hotel.get("country")] if x) or hotel.get("name", "")
    maps = f"https://www.google.com/maps/search/?api=1&query={quote_plus(hotel.get('name', '') + ' ' + addr)}"
    rows = "".join(
        f"<tr><td style='padding:6px 0;font-size:14px'>{'⭐ ' if u.get('favorite') else ''}{u['label']}</td><td style='padding:6px 0;font-size:14px;text-align:right;font-weight:600'>{sym}{u['price']:.0f} <span style='font-size:11px;color:#888;font-weight:400'>{t['per_night'] if u['price_type'] == 'per_night' else t['per_stay']}</span>"
        + (f"<br><a href='{u['claim_url']}' style='display:inline-block;margin-top:4px;background:#2F855A;color:#fff;text-decoration:none;padding:5px 10px;border-radius:6px;font-size:11px'>+ {t['add']}</a>" if u.get('claim_url') else "")
        + "</td></tr>"
        for u in upsells)
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff">
      <div style="background:#1a3c5e;color:#fff;padding:24px;text-align:center"><h1 style="margin:0;font-size:22px">{t['title']}</h1></div>
      <div style="padding:24px">
        <p style="font-size:14px;color:#333">{t['hi'].format(name=booking.get('guest_name', ''), days=DAYS_BEFORE)}</p>
        <table style="width:100%;border-collapse:collapse;margin:12px 0">
          <tr><td style="padding:6px 0;color:#666;font-size:13px">{t['ref']}</td><td style="padding:6px 0;text-align:right;font-weight:700;letter-spacing:1px">{booking.get('booking_ref', '')}</td></tr>
          <tr><td style="padding:6px 0;color:#666;font-size:13px">{t['room']}</td><td style="padding:6px 0;text-align:right;font-weight:600">{booking.get('room_type', '')}</td></tr>
          <tr><td style="padding:6px 0;color:#666;font-size:13px">{t['checkin']}</td><td style="padding:6px 0;text-align:right;font-weight:600">{booking.get('check_in', '')} · {hotel.get('check_in_time', '15:00')}</td></tr>
          <tr><td style="padding:6px 0;color:#666;font-size:13px">{t['checkout']}</td><td style="padding:6px 0;text-align:right;font-weight:600">{booking.get('check_out', '')} · {hotel.get('check_out_time', '11:00')}</td></tr>
          <tr><td style="padding:6px 0;color:#666;font-size:13px">{t['address']}</td><td style="padding:6px 0;text-align:right">{addr}</td></tr>
        </table>
        <a href="{maps}" style="display:inline-block;background:#1a3c5e;color:#fff;text-decoration:none;padding:10px 16px;border-radius:8px;font-size:13px">📍 {t['directions']}</a>
        {f"<div style='margin-top:24px;background:#F5F7FA;border-radius:8px;padding:16px'><div style='font-weight:700;font-size:14px;margin-bottom:6px'>✨ {t['upsell']}</div><table style='width:100%;border-collapse:collapse'>{rows}</table><div style='font-size:11px;color:#777;margin-top:6px'>{t['upsell_hint']}</div></div>" if upsells else ''}
        <p style="margin-top:24px;font-size:12px;color:#666;text-align:center"><strong>{hotel.get('name', '')}</strong> — {t['footer']}</p>
      </div>
    </div>"""
    return t["subject"].format(days=DAYS_BEFORE, hotel=hotel.get("name", ""), ref=booking.get("booking_ref", "")), html


def create_arrival_reminder_router(db, require_roles):
    router = APIRouter(prefix="/arrival-reminder", tags=["arrival-reminder"])

    async def _hotel(pid: str) -> dict:
        prop = await db.properties.find_one({"id": pid}, {"_id": 0}) or {}
        ts = await db.tenant_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
        return {"name": ts.get("hotel_name") or prop.get("name") or "Hotel", "address": ts.get("address") or prop.get("address", ""),
                "city": prop.get("city", ""), "country": prop.get("country", ""),
                "check_in_time": ts.get("check_in_time") or prop.get("check_in_time") or "15:00",
                "check_out_time": ts.get("check_out_time") or prop.get("check_out_time") or "11:00"}

    async def _upsells(pid: str, lang: str, b: dict = None) -> list:
        """Kişiselleştirme: zaten eklenenleri çıkar, kahvaltı dahil planda kahvaltıyı gizle, geçmiş favorileri öne al."""
        b = b or {}
        items = await db.upsell_items.find({"property_id": pid, "is_active": {"$ne": False}}, {"_id": 0, "name": 1, "price": 1, "price_type": 1}).sort("price", 1).to_list(8)
        if items:
            ups = [{"label": i.get("name", ""), "price": float(i.get("price") or 0), "price_type": i.get("price_type", "per_stay")} for i in items]
        else:
            ups = [{"label": u["name"].get(lang, u["name"]["en"]), "price": u["price"], "price_type": u["price_type"]} for u in DEFAULT_UPSELLS]
        have = {str(u.get("name") or "").lower() for u in (b.get("post_upsells") or [])}
        if "breakfast" in str(b.get("rate_plan_code") or "").lower():
            have |= {u["label"].lower() for u in ups if any(k in u["label"].lower() for k in ("breakfast", "kahvaltı", "frühstück"))}
        ups = [u for u in ups if u["label"].lower() not in have]
        favs: set = set()
        if b.get("guest_email"):
            async for prev in db.bookings.find({"guest_email": b["guest_email"], "id": {"$ne": b.get("id")}, "post_upsells.0": {"$exists": True}}, {"_id": 0, "post_upsells.name": 1}).limit(10):
                favs |= {str(u.get("name") or "").lower() for u in prev.get("post_upsells") or []}
        for u in ups:
            u["favorite"] = u["label"].lower() in favs
        ups.sort(key=lambda u: (not u["favorite"], u["price"]))
        return ups[:3]

    async def _with_claim_links(b: dict, ups: list, lang: str) -> list:
        """One-click 'add to my booking' tokens → /api/revenue/upsell/claim/{token} (pay at property)."""
        base = (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
        nights = max(1, int(b.get("nights") or 1))
        sym = _sym(b.get("currency", "GBP"))
        out = []
        for u in ups:
            amount = round(u["price"] * (nights if u["price_type"] == "per_night" else 1), 2)
            token = uuid.uuid4().hex
            await db.upsell_claim_tokens.insert_one({
                "token": token, "booking_id": b.get("id"), "booking_ref": b.get("booking_ref"), "guest_email": b.get("guest_email"),
                "label": u["label"], "amount": amount, "amount_label": f"{sym}{amount:.2f}", "lang": lang,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()})
            out.append({**u, "claim_url": f"{base}/api/revenue/upsell/claim/{token}"})
        return out

    async def run_arrival_reminders_internal(property_id: str) -> dict:
        today = datetime.now(timezone.utc).date()
        targets = [(today + timedelta(days=DAYS_BEFORE)).isoformat(), (today + timedelta(days=1)).isoformat()]
        q = {"status": {"$in": ["confirmed", "pending"]}, "check_in": {"$in": targets},
             "guest_email": {"$nin": [None, ""]}, "arrival_reminder_sent_at": {"$exists": False}}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        bks = await db.bookings.find(q, {"_id": 0}).to_list(500)
        sent = mocked = failed = 0
        hotels: dict = {}
        for b in bks:
            pid = b.get("property_id", "default")
            if pid not in hotels:
                hotels[pid] = await _hotel(pid)
            lang = (b.get("guest_lang") or "en")[:2].lower()
            ups = await _upsells(pid, lang, b)
            ups = await _with_claim_links(b, ups, lang)
            subject, html = build_arrival_email(b, hotels[pid], ups, lang)
            status = await send_email(db, b["guest_email"], subject, html, kind="arrival_reminder",
                                      meta={"booking_id": b.get("id"), "booking_ref": b.get("booking_ref"), "lang": lang})
            now = datetime.now(timezone.utc).isoformat()
            channels = ["email"]
            wa_status = ""
            if b.get("guest_phone"):
                t = T.get(lang, T["en"])
                sym = _sym(b.get("currency", "GBP"))
                lines = [f"{'⭐ ' if u.get('favorite') else ''}{u['label']} — {sym}{u['price']:.0f}: {u.get('claim_url', '')}" for u in ups]
                body = f"{t['title']} · {hotels[pid]['name']}\n{t['hi'].format(name=b.get('guest_name', ''), days=DAYS_BEFORE)}\n\n✨ {t['upsell']}:\n" + "\n".join(lines)
                await db.whatsapp_outbox.insert_one({"id": str(uuid.uuid4()), "to": b["guest_phone"], "body": body, "kind": "arrival_reminder",
                                                     "booking_id": b.get("id"), "booking_ref": b.get("booking_ref"), "property_id": pid,
                                                     "status": "mocked", "created_at": now})
                channels.append("whatsapp"); wa_status = "mocked"
            await db.bookings.update_one({"id": b["id"]}, {"$set": {"arrival_reminder_sent_at": now, "arrival_reminder_status": status}})
            await db.arrival_reminder_log.insert_one({"id": str(uuid.uuid4()), "booking_id": b.get("id"), "booking_ref": b.get("booking_ref"),
                                                      "property_id": pid, "to": b["guest_email"], "guest_name": b.get("guest_name"),
                                                      "check_in": b.get("check_in"), "lang": lang, "subject": subject, "status": status,
                                                      "channels": channels, "whatsapp_status": wa_status, "favorites": sum(1 for u in ups if u.get("favorite")),
                                                      "upsells": len(ups), "sent_at": now})
            sent += status == "sent"
            mocked += status == "mocked"
            failed += status == "failed"
        return {"ok": True, "candidates": len(bks), "sent": sent, "mocked": mocked, "failed": failed, "targets": targets}

    router.run_arrival_reminders_internal = run_arrival_reminders_internal

    @router.post("/run/{property_id}")
    async def run_now(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_arrival_reminders_internal(property_id)

    @router.get("/log/{property_id}")
    async def log(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        return await db.arrival_reminder_log.find(q, {"_id": 0}).sort("sent_at", -1).to_list(50)

    @router.get("/stats/{property_id}")
    async def stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Hatırlatma → tıklama → dönüşüm raporu."""
        q = {} if property_id == "all" else {"property_id": property_id}
        logs = await db.arrival_reminder_log.find(q, {"_id": 0, "booking_id": 1, "channels": 1, "status": 1}).to_list(2000)
        bids = [l.get("booking_id") for l in logs if l.get("booking_id")]
        tokens = await db.upsell_claim_tokens.find({"booking_id": {"$in": bids}}, {"_id": 0, "used_at": 1, "amount": 1, "label": 1}).to_list(5000) if bids else []
        used = [t for t in tokens if t.get("used_at")]
        by_label: dict = {}
        for t in tokens:
            d = by_label.setdefault(t.get("label", ""), {"offered": 0, "claimed": 0, "revenue": 0.0})
            d["offered"] += 1
            if t.get("used_at"):
                d["claimed"] += 1; d["revenue"] = round(d["revenue"] + float(t.get("amount") or 0), 2)
        return {"reminders": len(logs), "email_sent": sum(1 for l in logs if l.get("status") == "sent"), "email_mocked": sum(1 for l in logs if l.get("status") == "mocked"),
                "whatsapp": sum(1 for l in logs if "whatsapp" in (l.get("channels") or [])),
                "offers": len(tokens), "claimed": len(used), "conversion_pct": round(len(used) / len(tokens) * 100, 1) if tokens else 0.0,
                "revenue": round(sum(float(t.get("amount") or 0) for t in used), 2),
                "by_label": sorted([{"label": k, **v} for k, v in by_label.items()], key=lambda x: -x["claimed"])[:6]}

    @router.get("/preview/{property_id}")
    async def preview(property_id: str, lang: str = "en", current_user: dict = Depends(require_roles("admin", "manager"))):
        hotel = await _hotel(property_id)
        sample = {"guest_name": "Anna Example", "booking_ref": "WEB-PREVIEW", "room_type": "Deluxe Suite",
                  "check_in": (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat(),
                  "check_out": (datetime.now(timezone.utc).date() + timedelta(days=4)).isoformat(), "currency": "GBP"}
        subject, html = build_arrival_email(sample, hotel, await _upsells(property_id, lang), lang)
        return {"subject": subject, "html": html}

    # ---------- EVENT PACKAGES ----------
    @router.get("/event-packages/{property_id}")
    async def list_packages(property_id: str):
        """Public: packages for the widget (widget shows enabled ones)."""
        return await db.event_packages.find({"property_id": property_id}, {"_id": 0}).sort("created_at", 1).to_list(20)

    @router.post("/event-packages/{property_id}")
    async def create_package(property_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        src = DEFAULT_PACKAGE if data.get("use_default") else data
        price = float(src.get("price_per_night") or 0)
        if price < 0 or not (src.get("name_en") or src.get("name_tr")):
            raise HTTPException(400, "Paket adı ve fiyatı gerekli")
        pkg = {"id": str(uuid.uuid4()), "property_id": property_id,
               "name_en": src.get("name_en") or src.get("name_tr"), "name_tr": src.get("name_tr") or src.get("name_en"),
               "name_de": src.get("name_de") or src.get("name_en") or src.get("name_tr"),
               "price_per_night": round(price, 2), "includes": list(src.get("includes") or [])[:8],
               "enabled": bool(src.get("enabled", True)), "created_by": current_user.get("name", ""),
               "created_at": datetime.now(timezone.utc).isoformat()}
        await db.event_packages.insert_one({**pkg})
        return pkg

    @router.put("/event-packages/{property_id}/{pkg_id}")
    async def update_package(property_id: str, pkg_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        upd = {k: data[k] for k in ("name_en", "name_tr", "name_de", "includes", "enabled") if k in data}
        if "price_per_night" in data:
            upd["price_per_night"] = round(float(data["price_per_night"] or 0), 2)
        r = await db.event_packages.update_one({"id": pkg_id, "property_id": property_id}, {"$set": upd})
        if r.matched_count == 0:
            raise HTTPException(404, "Paket bulunamadı")
        return await db.event_packages.find_one({"id": pkg_id}, {"_id": 0})

    @router.delete("/event-packages/{property_id}/{pkg_id}")
    async def delete_package(property_id: str, pkg_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.event_packages.delete_one({"id": pkg_id, "property_id": property_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Paket bulunamadı")
        return {"ok": True}

    return router
