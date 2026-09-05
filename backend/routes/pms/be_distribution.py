"""Booking Engine dağıtım paketi: Google Hotel Ads feed'leri, gömme scripti, hediye çeki satışı, exit-intent."""
import os
import uuid
import secrets
import string
from datetime import datetime, timezone, timedelta, date as _date
from typing import Dict
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from routes.pms.be_conversion import plan_night_price

GIFT_PRESETS = [50, 100, 150, 200, 300, 500]


def _code(prefix="MHB"):
    a = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return f"{prefix}-" + "-".join("".join(secrets.choice(a) for _ in range(4)) for _ in range(3))


def create_be_distribution_router(db, require_roles):
    router = APIRouter()
    ROLES = ("admin", "manager")
    stripe_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY", "")

    def _base(request: Request) -> str:
        return (os.environ.get("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")

    # ---------------- GOOGLE HOTEL ADS ----------------
    @router.get("/hotel-ads/hotel-list/{pid}.xml")
    async def hotel_list_feed(pid: str):
        prop = await db.properties.find_one({"id": pid}, {"_id": 0})
        if not prop:
            raise HTTPException(404, "Tesis yok")
        site = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0, "content": 1}) or {}
        c = site.get("content") or {}
        lat, lng = prop.get("latitude"), prop.get("longitude")
        xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<listings xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
               f'<language>{escape(prop.get("language", "en"))}</language>', '<listing>', f'<id>{escape(pid)}</id>',
               f'<name>{escape(prop.get("name", ""))}</name>',
               f'<address format="simple"><component name="addr1">{escape(c.get("address") or prop.get("address", ""))}</component>'
               f'<component name="city">{escape(prop.get("city", ""))}</component><component name="postal_code">{escape(prop.get("postcode", "") or prop.get("zip", ""))}</component></address>',
               f'<country>{escape((prop.get("country_code") or "GB")[:2].upper())}</country>']
        if lat is not None and lng is not None:
            xml.append(f'<latitude>{lat}</latitude><longitude>{lng}</longitude>')
        if c.get("phone") or prop.get("phone"):
            xml.append(f'<phone type="main">{escape(c.get("phone") or prop.get("phone"))}</phone>')
        xml.append('<category>hotel</category>')
        if c.get("about"):
            xml.append(f'<content><text type="description"><link>{escape(c.get("seo_title") or prop.get("name", ""))}</link><title>{escape(prop.get("name", ""))}</title><body>{escape(c["about"][:1000])}</body></text></content>')
        xml += ['</listing>', '</listings>']
        return Response("\n".join(xml), media_type="application/xml")

    @router.get("/hotel-ads/ari/{pid}.xml")
    async def ari_feed(pid: str, days: int = 60, nights: int = 1):
        """Transaction (Rate/Availability) feed — Google Hotel Prices formatı, en düşük oran planı."""
        days = max(1, min(180, days))
        rooms = await db.room_types.find({"property_id": pid, "is_active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "base_price": 1, "total_rooms": 1, "max_guests": 1}).to_list(50)
        plans = await db.be_rate_plans.find({"property_id": pid, "is_active": {"$ne": False}}, {"_id": 0}).to_list(20)
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "currency": 1}) or {}
        cur = prop.get("currency", "GBP")
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=days + nights)
        booked: Dict[tuple, int] = {}
        async for b in db.bookings.find({"property_id": pid, "status": {"$nin": ["cancelled"]}, "check_in": {"$lt": end.isoformat()}, "check_out": {"$gt": today.isoformat()}},
                                        {"_id": 0, "room_type_id": 1, "check_in": 1, "check_out": 1, "rooms": 1}):
            try:
                d = max(_date.fromisoformat(b["check_in"][:10]), today); co = _date.fromisoformat(b["check_out"][:10])
            except Exception:
                continue
            while d < co and d < end:
                booked[(b["room_type_id"], d.isoformat())] = booked.get((b["room_type_id"], d.isoformat()), 0) + int(b.get("rooms") or 1)
                d += timedelta(days=1)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<Transaction timestamp="{ts}" id="{uuid.uuid4().hex[:12]}">']
        for r in rooms:
            for off in range(days):
                d = today + timedelta(days=off)
                ok = all(int(r.get("total_rooms") or 1) - booked.get((r["id"], (d + timedelta(days=n)).isoformat()), 0) > 0 for n in range(nights))
                if not ok:
                    continue
                for p in (plans or [None]):
                    rate = round(plan_night_price(r.get("base_price", 0), p) * nights, 2)
                    refundable = 'true' if (p or {}).get("cancellation_type", "free") == "free" else 'false'
                    out.append(f'<Result><Property>{escape(pid)}</Property><Checkin>{d.isoformat()}</Checkin><Nights>{nights}</Nights>'
                               f'<RoomID>{escape(r["id"])}</RoomID><RatePlanID>{escape((p or {}).get("code", "standard"))}</RatePlanID>'
                               f'<Baserate currency="{cur}">{rate}</Baserate><Tax currency="{cur}">0</Tax><OtherFees currency="{cur}">0</OtherFees>'
                               f'<Occupancy>{min(2, int(r.get("max_guests") or 2))}</Occupancy>'
                               f'<Refundable available="{refundable}"/></Result>')
        out.append('</Transaction>')
        return Response("\n".join(out), media_type="application/xml")

    @router.get("/hotel-ads/landing")
    async def hotel_ads_landing(property: str, checkin: str = "", nights: int = 1, adults: int = 2, room: str = "", rate: str = ""):
        """Google point-of-sale URL hedefi → booking engine'e tarihlerle yönlendir."""
        try:
            ci = _date.fromisoformat(checkin) if checkin else datetime.now(timezone.utc).date() + timedelta(days=1)
        except Exception:
            ci = datetime.now(timezone.utc).date() + timedelta(days=1)
        co = ci + timedelta(days=max(1, min(30, nights)))
        await db.site_visits.insert_one({"id": str(uuid.uuid4()), "property_id": property, "event": "view", "visitor_id": "", "source": "google_hotel_ads",
                                         "referrer": "google_hotel_ads", "date": datetime.now(timezone.utc).date().isoformat(), "created_at": datetime.now(timezone.utc).isoformat()})
        url = f"/book?property={property}&check_in={ci.isoformat()}&check_out={co.isoformat()}&adults={max(1, min(10, adults))}&utm_source=google_hotel_ads&utm_medium=metasearch"
        if room:
            url += f"&room={room}"
        if rate:
            url += f"&rate={rate}"
        return RedirectResponse(url, status_code=302)

    @router.get("/hotel-ads/status/{pid}")
    async def hotel_ads_status(pid: str, request: Request, _u: dict = Depends(require_roles(*ROLES))):
        prop = await db.properties.find_one({"id": pid}, {"_id": 0}) or {}
        site = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0}) or {}
        c = site.get("content") or {}
        base = _base(request)
        plans = await db.be_rate_plans.count_documents({"property_id": pid, "is_active": {"$ne": False}})
        checks = [
            {"key": "name", "label": "Tesis adı", "ok": bool(prop.get("name"))},
            {"key": "address", "label": "Adres (site içeriği veya tesis)", "ok": bool(c.get("address") or prop.get("address"))},
            {"key": "geo", "label": "Enlem/boylam (properties.latitude/longitude)", "ok": prop.get("latitude") is not None and prop.get("longitude") is not None},
            {"key": "phone", "label": "Telefon", "ok": bool(c.get("phone") or prop.get("phone"))},
            {"key": "rate_plans", "label": "En az 1 aktif oran planı", "ok": plans > 0},
            {"key": "site", "label": "Web sitesi yayında (landing için)", "ok": bool(site.get("published"))},
        ]
        ga_bookings = await db.bookings.count_documents({"property_id": pid, "source": "google_hotel_ads"})
        ga_clicks = await db.site_visits.count_documents({"property_id": pid, "source": "google_hotel_ads"})
        return {"property_id": pid, "checks": checks, "ready": all(x["ok"] for x in checks),
                "feeds": {"hotel_list": f"{base}/api/hotel-ads/hotel-list/{pid}.xml", "ari": f"{base}/api/hotel-ads/ari/{pid}.xml?days=60",
                          "point_of_sale": f"{base}/api/hotel-ads/landing?property={pid}&checkin=(CHECKINDAY)&nights=(LENGTH)&adults=(NUM-ADULTS)&room=(PARTNER-ROOM-ID)&rate=(PARTNER-RATE-ID)"},
                "stats": {"clicks": ga_clicks, "bookings": ga_bookings},
                "steps": ["Google Hotel Center hesabı açın (hotelcenter.google.com) ve 'Free Booking Links' seçin.",
                          "Hotel List Feed URL'sini 'Feeds → Hotel list' bölümüne ekleyin.",
                          "Fiyat için 'Pull' modunu seçip ARI feed URL'sini verin (Google 15dk-24s aralıkla çeker).",
                          "Point-of-sale (landing) URL şablonunu 'Booking links' bölümüne yapıştırın.",
                          "Google onayı (1-3 iş günü) sonrası ücretsiz linkler Google Otel kartında çıkar."]}

    # ---------------- GÖMME SCRIPTİ ----------------
    @router.get("/embed/widget.js")
    async def embed_widget(property: str, request: Request, accent: str = "#0f4c5c", radius: str = "12px", lang: str = "tr", target: str = "_blank"):
        base = _base(request)
        if not property.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(422, "property")
        accent = accent if accent.startswith("#") and len(accent) in (4, 7) else "#0f4c5c"
        lab = {"tr": ("Giriş", "Çıkış", "Misafir", "Müsaitlik & Fiyat"), "en": ("Check-in", "Check-out", "Guests", "Check availability"),
               "de": ("Anreise", "Abreise", "Gäste", "Verfügbarkeit prüfen")}.get(lang, ("Check-in", "Check-out", "Guests", "Check availability"))
        js = f"""(function(){{
var el=document.getElementById('mhb-booking-widget');if(!el)return;
var t=new Date(),a=new Date(t);a.setDate(a.getDate()+1);var b=new Date(t);b.setDate(b.getDate()+2);
function iso(d){{return d.toISOString().slice(0,10);}}
el.innerHTML='<form class="mhb-w" style="display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end;font-family:system-ui,sans-serif;background:#fff;padding:14px;border:1px solid #e5e7eb;border-radius:{radius};box-shadow:0 8px 30px rgba(0,0,0,.08)">'+
'<label style="flex:1;min-width:130px;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#6b7280">{lab[0]}<input name="ci" type="date" value="'+iso(a)+'" min="'+iso(t)+'" style="display:block;margin-top:4px;width:100%;padding:10px;border:1px solid #d1d5db;border-radius:{radius};font-size:14px"></label>'+
'<label style="flex:1;min-width:130px;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#6b7280">{lab[1]}<input name="co" type="date" value="'+iso(b)+'" style="display:block;margin-top:4px;width:100%;padding:10px;border:1px solid #d1d5db;border-radius:{radius};font-size:14px"></label>'+
'<label style="flex:0 0 110px;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#6b7280">{lab[2]}<select name="ad" style="display:block;margin-top:4px;width:100%;padding:10px;border:1px solid #d1d5db;border-radius:{radius};font-size:14px"><option>1</option><option selected>2</option><option>3</option><option>4</option><option>5</option><option>6</option></select></label>'+
'<button type="submit" style="flex:1;min-width:160px;padding:12px 16px;background:{accent};color:#fff;border:0;border-radius:{radius};font-weight:700;font-size:14px;cursor:pointer">{lab[3]}</button></form>';
el.querySelector('form').addEventListener('submit',function(e){{e.preventDefault();var f=e.target;
var u='{base}/book?property={property}&check_in='+f.ci.value+'&check_out='+f.co.value+'&adults='+f.ad.value+'&utm_source=embed&utm_medium=widget&lang={lang}';
window.open(u,'{target}');}});
}})();"""
        return Response(js, media_type="application/javascript", headers={"Cache-Control": "public, max-age=300", "Access-Control-Allow-Origin": "*"})

    @router.get("/embed/snippet/{pid}")
    async def embed_snippet(pid: str, request: Request, _u: dict = Depends(require_roles(*ROLES))):
        base = _base(request)
        return {"snippet": f'<div id="mhb-booking-widget"></div>\n<script src="{base}/api/embed/widget.js?property={pid}&accent=%230f4c5c&lang=tr" async></script>',
                "iframe": f'<iframe src="{base}/book?property={pid}" style="width:100%;min-height:900px;border:0" loading="lazy" title="Rezervasyon"></iframe>',
                "params": {"accent": "Hex renk (örn. %23b45309)", "radius": "Köşe yuvarlaklığı (örn. 8px)", "lang": "tr | en | de", "target": "_blank | _self"}}

    # ---------------- HEDİYE ÇEKİ (PUBLIC SATIŞ) ----------------
    @router.get("/booking/gift-cards/config/{pid}")
    async def gift_config(pid: str):
        cfg = await db.gift_card_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "currency": 1, "name": 1}) or {}
        return {"enabled": cfg.get("enabled", True), "presets": cfg.get("presets") or GIFT_PRESETS, "min": cfg.get("min", 25), "max": cfg.get("max", 2000),
                "currency": prop.get("currency", "GBP"), "property_name": prop.get("name", ""), "expires_days": cfg.get("expires_days", 365)}

    @router.put("/gift-cards/config/{pid}")
    async def gift_config_save(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {"property_id": pid, "enabled": bool(data.get("enabled", True)),
               "presets": [int(x) for x in (data.get("presets") or GIFT_PRESETS) if int(x) > 0][:8],
               "min": int(data.get("min") or 25), "max": int(data.get("max") or 2000), "expires_days": int(data.get("expires_days") or 365)}
        await db.gift_card_config.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True}

    @router.post("/booking/gift-cards/purchase")
    async def gift_purchase(data: Dict, request: Request):
        pid = (data.get("property_id") or "").strip()
        cfg = await gift_config(pid)
        if not cfg["enabled"]:
            raise HTTPException(400, "Hediye çeki satışı kapalı")
        amount = float(data.get("amount") or 0)
        if amount < cfg["min"] or amount > cfg["max"]:
            raise HTTPException(400, f"Tutar {cfg['min']}–{cfg['max']} arasında olmalı")
        p_email = (data.get("purchaser_email") or "").strip()
        if "@" not in p_email:
            raise HTTPException(422, "Geçerli e-posta girin")
        now = datetime.now(timezone.utc)
        card = {"id": str(uuid.uuid4()), "code": _code(), "property_id": pid, "initial_amount": round(amount, 2), "balance": round(amount, 2),
                "currency": cfg["currency"], "recipient_name": (data.get("recipient_name") or "")[:80], "recipient_email": (data.get("recipient_email") or "")[:120],
                "purchaser_name": (data.get("purchaser_name") or "")[:80], "purchaser_email": p_email[:120], "message": (data.get("message") or "")[:300],
                "status": "pending_payment", "source": "booking_engine", "expires_at": (now + timedelta(days=cfg["expires_days"])).isoformat(),
                "created_at": now.isoformat(), "created_by": "guest", "redemption_log": []}
        await db.gift_cards.insert_one(dict(card))
        origin = (data.get("origin_url") or _base(request)).rstrip("/")
        if not stripe_key:
            await db.gift_cards.update_one({"id": card["id"]}, {"$set": {"status": "active", "paid_at": now.isoformat(), "payment": "MOCK"}})
            return {"mock": True, "card_id": card["id"], "code": card["code"], "url": f"{origin}/book?property={pid}&gift=success&gift_id={card['id']}"}
        from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
        sc = StripeCheckout(api_key=stripe_key, webhook_url=f"{str(request.base_url).rstrip('/')}/api/webhook/stripe")
        req = CheckoutSessionRequest(amount=round(amount, 2), currency=cfg["currency"].lower(),
                                     success_url=f"{origin}/book?property={pid}&gift=success&gift_id={card['id']}&session_id={{CHECKOUT_SESSION_ID}}",
                                     cancel_url=f"{origin}/book?property={pid}&gift=cancelled",
                                     metadata={"type": "gift_card", "card_id": card["id"], "property_id": pid, "purchaser_email": p_email})
        session = await sc.create_checkout_session(req)
        await db.payment_transactions.insert_one({"id": str(uuid.uuid4()), "session_id": session.session_id, "type": "gift_card", "reference_id": card["id"],
                                                  "reference_number": card["code"], "property_id": pid, "amount": round(amount, 2), "currency": cfg["currency"].lower(),
                                                  "guest_name": card["purchaser_name"], "guest_email": p_email, "payment_method": "stripe", "payment_status": "initiated",
                                                  "metadata": req.metadata, "created_at": now.isoformat()})
        return {"url": session.url, "session_id": session.session_id, "card_id": card["id"]}

    @router.get("/booking/gift-cards/status/{card_id}")
    async def gift_status(card_id: str, session_id: str = ""):
        card = await db.gift_cards.find_one({"id": card_id}, {"_id": 0})
        if not card:
            raise HTTPException(404, "Çek yok")
        if card["status"] == "pending_payment" and session_id and stripe_key:
            try:
                import stripe as _stripe
                _stripe.api_key = stripe_key
                s = _stripe.checkout.Session.retrieve(session_id)
                if s.payment_status == "paid":
                    await db.gift_cards.update_one({"id": card_id}, {"$set": {"status": "active", "paid_at": datetime.now(timezone.utc).isoformat()}})
                    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"payment_status": "paid"}})
                    card["status"] = "active"
            except Exception:
                pass
        return {"status": card["status"], "code": card["code"] if card["status"] in ("active", "redeemed") else None,
                "amount": card["initial_amount"], "currency": card["currency"], "recipient_name": card.get("recipient_name"), "expires_at": card.get("expires_at")}

    @router.post("/booking/gift-cards/check")
    async def gift_check(data: Dict):
        code = (data.get("code") or "").upper().strip()
        card = await db.gift_cards.find_one({"code": code}, {"_id": 0, "balance": 1, "status": 1, "currency": 1, "expires_at": 1, "property_id": 1})
        if not card or card.get("status") != "active":
            raise HTTPException(404, "Geçersiz veya kullanılmış hediye çeki")
        if card.get("expires_at") and card["expires_at"] < datetime.now(timezone.utc).isoformat():
            raise HTTPException(400, "Hediye çekinin süresi dolmuş")
        if data.get("property_id") and card.get("property_id") and card["property_id"] != data["property_id"]:
            raise HTTPException(400, "Bu çek bu tesiste geçerli değil")
        return {"valid": True, "code": code, "balance": card["balance"], "currency": card.get("currency", "GBP")}

    # ---------------- EXIT INTENT ----------------
    @router.get("/booking/exit-intent/{pid}")
    async def exit_intent_public(pid: str):
        cfg = await db.exit_intent_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        if not cfg.get("enabled", True):
            return {"enabled": False}
        return {"enabled": True, "title": cfg.get("title") or "Gitmeden önce…", "body": cfg.get("body") or "Doğrudan rezervasyona özel %{pct} indirim kodunuz hazır.",
                "discount_pct": int(cfg.get("discount_pct") or 10), "code": cfg.get("code") or "STAYDIRECT10", "delay_sec": int(cfg.get("delay_sec") or 8)}

    @router.put("/exit-intent/config/{pid}")
    async def exit_intent_save(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        pct = max(1, min(50, int(data.get("discount_pct") or 10)))
        code = (data.get("code") or "STAYDIRECT10").upper().strip()[:20]
        upd = {"property_id": pid, "enabled": bool(data.get("enabled", True)), "title": (data.get("title") or "")[:80], "body": (data.get("body") or "")[:200],
               "discount_pct": pct, "code": code, "delay_sec": max(3, min(60, int(data.get("delay_sec") or 8)))}
        await db.exit_intent_config.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        await db.promo_codes.update_one({"code": code}, {"$set": {"code": code, "property_id": pid, "discount_type": "percentage", "discount_value": pct,
                                                                 "description": "Exit-intent direct booking offer", "is_active": True, "source": "exit_intent"},
                                                        "$setOnInsert": {"id": str(uuid.uuid4()), "used_count": 0, "created_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, **upd}

    @router.get("/exit-intent/config/{pid}")
    async def exit_intent_get(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await db.exit_intent_config.find_one({"property_id": pid}, {"_id": 0}) or {"property_id": pid, "enabled": True, "discount_pct": 10, "code": "STAYDIRECT10", "delay_sec": 8, "title": "", "body": ""}
        shown = await db.site_visits.count_documents({"property_id": pid, "event": "exit_intent_shown"})
        used = await db.bookings.count_documents({"property_id": pid, "promo_code": cfg.get("code", "STAYDIRECT10")})
        return {**cfg, "stats": {"shown": shown, "converted": used}}

    @router.post("/booking/exit-intent/{pid}/shown")
    async def exit_intent_shown(pid: str):
        now = datetime.now(timezone.utc)
        await db.site_visits.insert_one({"id": str(uuid.uuid4()), "property_id": pid, "event": "exit_intent_shown", "visitor_id": "", "source": "direct",
                                         "referrer": "", "date": now.date().isoformat(), "created_at": now.isoformat()})
        return {"ok": True}

    return router
