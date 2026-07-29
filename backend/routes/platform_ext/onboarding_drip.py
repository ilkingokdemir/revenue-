"""
Onboarding Drip — "İlk 7 Gün" aktivasyon e-posta serisi.
Quick Start / onboarding tamamlanınca otel yöneticisi otomatik kaydolur;
0., 1., 3. ve 7. günlerde platformun çekirdek değerine yönlendiren e-postalar gider.

Collection: onboarding_drip
  { property_id, email, name, started_at, enabled, sent: [{key, day, sent_at, status}] }

Endpoints (/api/onboarding-drip/*):
- GET  /status/{property_id}   → enrollment + timeline
- POST /enroll/{property_id}   → manuel kayıt (body: {email?})
- POST /toggle/{property_id}   → seriyi aç/kapat
- POST /run-now                → bekleyen e-postaları hemen işle (test/admin)
- GET  /preview/{key}          → e-posta HTML önizlemesi
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_perm

logger = logging.getLogger(__name__)

BTN = ("display:inline-block;padding:12px 28px;background:#7c3aed;color:#ffffff;"
       "text-decoration:none;border-radius:10px;font-weight:700;font-size:14px")


def _wrap(title: str, body_html: str) -> str:
    return f"""
<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:560px;margin:0 auto;background:#fafaf9;padding:24px">
  <div style="background:#1c1917;border-radius:16px;padding:20px 24px;color:#fff">
    <div style="font-size:12px;letter-spacing:2px;color:#a8a29e;text-transform:uppercase">MyHotelBox · ReveniQ</div>
    <h1 style="font-size:22px;margin:8px 0 0">{title}</h1>
  </div>
  <div style="background:#ffffff;border:1px solid #e7e5e4;border-radius:16px;padding:24px;margin-top:12px;color:#44403c;font-size:14px;line-height:1.7">
    {body_html}
  </div>
  <p style="font-size:11px;color:#a8a29e;text-align:center;margin-top:16px">
    Bu seri, kurulumunuzu tamamladığınız için gönderildi. Panelden kapatabilirsiniz.
  </p>
</div>"""


DRIP_EMAILS = [
    {
        "key": "welcome", "day": 0,
        "subject": "🎉 Hoş geldiniz — oteliniz artık canlı!",
        "title": "Kurulum tamam, oteliniz canlı.",
        "body": """
<p>Merhaba {name},</p>
<p><b>{property_name}</b> için kurulum tamamlandı: oda tipleriniz envanterde, rate planlarınız hazır,
vergi kurallarınız bağlı ve takviminiz dolu.</p>
<p>Önümüzdeki 7 gün boyunca size platformun en değerli 3 özelliğini kısa e-postalarla göstereceğiz —
her biri 2 dakikada kurulur, gelirinizi doğrudan etkiler.</p>
<p style="text-align:center;margin-top:20px"><a href="{app_url}/login" style="%s">Panele Git →</a></p>""" % BTN,
    },
    {
        "key": "market_robot", "day": 1,
        "subject": "📡 1. Gün: Rakipleriniz bu gece fiyat değiştirdi — haberiniz var mı?",
        "title": "Market Robot'u başlatın.",
        "body": """
<p>Merhaba {name},</p>
<p>Şehrinizdeki oteller fiyatlarını her gün güncelliyor. <b>Market Robot</b>, Booking.com üzerindeki
rakip fiyatlarını 60 dakikada bir tarar ve sizin fiyatınızla arasındaki boşlukları gösterir.</p>
<p><b>Kurulum: tek tık.</b> Revenue &gt; Market Robot sayfasında "Start Market Robot" deyin —
şehriniz ve para biriminiz otomatik algılanır.</p>
<p style="text-align:center;margin-top:20px"><a href="{app_url}/login" style="%s">Market Robot'u Başlat →</a></p>""" % BTN,
    },
    {
        "key": "booking_url", "day": 3,
        "subject": "🔗 3. Gün: Booking.com listenizi bağlayın — canlı puan ve fiyat takibi",
        "title": "Kendi listenizi radara ekleyin.",
        "body": """
<p>Merhaba {name},</p>
<p>Booking.com sayfanızın URL'sini yapıştırın; sistem her 3 saatte bir <b>en düşük gecelik fiyatınızı</b>,
<b>misafir puanınızı</b> ve <b>müsaitliğinizi</b> çekerek "Biz vs Pazar" karşılaştırmasını canlı tutar.</p>
<p>Onboarding ekranındaki <b>Link Booking.com Listing</b> kartından ya da Market Robot &gt;
Our Booking.com Live kartından ekleyebilirsiniz.</p>
<p style="text-align:center;margin-top:20px"><a href="{app_url}/login" style="%s">URL'yi Bağla →</a></p>""" % BTN,
    },
    {
        "key": "revenue_brain", "day": 7,
        "subject": "🧠 7. Gün: Revenue Brain ilk derslerini çıkardı",
        "title": "Öğrenen fiyatlandırma devrede.",
        "body": """
<p>Merhaba {name},</p>
<p>Bir haftadır veri topluyoruz. <b>Revenue Brain</b>, geçmiş fiyat kararlarınızın sonuçlarını ölçüp
çarpan ağırlıklarını otomatik ayarlayan kapalı döngü bir öğrenme motorudur — her hafta biraz daha isabetli olur.</p>
<p>Revenue &gt; Revenue Brain sayfasında ilk dersleri ve öneri geçmişini inceleyin.
Haftalık Pulse e-postalarında da özet bulacaksınız.</p>
<p style="text-align:center;margin-top:20px"><a href="{app_url}/login" style="%s">Revenue Brain'i Aç →</a></p>""" % BTN,
    },
]

DRIP_BY_KEY = {e["key"]: e for e in DRIP_EMAILS}


class EnrollIn(BaseModel):
    email: Optional[str] = None


async def enroll_property(db, property_id: str, email: str, name: str = ""):
    """Idempotent kayıt — mevcut enrollment varsa dokunmaz."""
    if not email:
        return None
    existing = await db.onboarding_drip.find_one({"property_id": property_id})
    if existing:
        return existing.get("id")
    import uuid
    now = datetime.now(timezone.utc).isoformat()
    doc = {"id": str(uuid.uuid4()), "property_id": property_id, "email": email.lower(),
           "name": name or email.split("@")[0], "started_at": now, "enabled": True,
           "sent": [], "created_at": now}
    await db.onboarding_drip.insert_one(dict(doc))
    logger.info(f"onboarding_drip: enrolled {email} for {property_id}")
    return doc["id"]


def _render(tpl: dict, name: str, property_name: str) -> str:
    import os
    app_url = os.environ.get("APP_PUBLIC_URL", "https://app.myhotelbox.example")
    body = tpl["body"].format(name=name or "orada", property_name=property_name or "oteliniz", app_url=app_url)
    return _wrap(tpl["title"], body)


async def process_due_drips(db) -> dict:
    """Süresi gelen drip e-postalarını gönder. Loop ve run-now tarafından çağrılır."""
    from routes.revenue_ext.owner_pulse import _send_email
    now = datetime.now(timezone.utc)
    processed, sent = 0, 0
    async for enr in db.onboarding_drip.find({"enabled": True}):
        processed += 1
        try:
            started = datetime.fromisoformat(enr["started_at"])
        except (ValueError, KeyError):
            continue
        elapsed_days = (now - started).days
        sent_keys = {s["key"] for s in enr.get("sent", [])}
        prop = await db.properties.find_one({"id": enr["property_id"]}, {"_id": 0, "name": 1})
        pname = (prop or {}).get("name", "")
        for tpl in DRIP_EMAILS:
            if tpl["key"] in sent_keys or tpl["day"] > elapsed_days:
                continue
            # Atomic claim: only proceed if this key hasn't been recorded yet (guards
            # against run-now racing the background loop).
            claim = await db.onboarding_drip.update_one(
                {"id": enr["id"], "sent.key": {"$ne": tpl["key"]}},
                {"$push": {"sent": {"key": tpl["key"], "day": tpl["day"],
                                    "sent_at": now.isoformat(), "status": "sending"}}})
            if claim.modified_count == 0:
                continue
            html = _render(tpl, enr.get("name", ""), pname)
            status = await _send_email(enr["email"], tpl["subject"], html)
            await db.onboarding_drip.update_one(
                {"id": enr["id"], "sent.key": tpl["key"]},
                {"$set": {"sent.$.status": status}})
            sent += 1
    return {"processed": processed, "sent": sent}


def create_onboarding_drip_router(db):
    router = APIRouter(prefix="/onboarding-drip")

    @router.get("/status/{property_id}")
    async def status(property_id: str,
                     current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        enr = await db.onboarding_drip.find_one({"property_id": property_id}, {"_id": 0})
        timeline = []
        sent_map = {s["key"]: s for s in (enr or {}).get("sent", [])}
        for tpl in DRIP_EMAILS:
            s = sent_map.get(tpl["key"])
            timeline.append({"key": tpl["key"], "day": tpl["day"], "subject": tpl["subject"],
                             "sent_at": s.get("sent_at") if s else None,
                             "status": s.get("status") if s else "pending"})
        return {"enrolled": bool(enr), "enabled": bool(enr and enr.get("enabled")),
                "email": (enr or {}).get("email"), "started_at": (enr or {}).get("started_at"),
                "timeline": timeline}

    @router.post("/enroll/{property_id}")
    async def enroll(property_id: str, body: EnrollIn,
                     current_user: dict = Depends(require_perm("edit_bookings"))):
        email = (body.email or current_user.get("email") or "").lower().strip()
        if not email:
            raise HTTPException(400, "Email required")
        eid = await enroll_property(db, property_id, email, current_user.get("name", ""))
        return {"ok": True, "enrollment_id": eid, "email": email}

    @router.post("/toggle/{property_id}")
    async def toggle(property_id: str,
                     current_user: dict = Depends(require_perm("edit_bookings"))):
        enr = await db.onboarding_drip.find_one({"property_id": property_id})
        if not enr:
            raise HTTPException(404, "Not enrolled")
        new_val = not enr.get("enabled", True)
        await db.onboarding_drip.update_one({"id": enr["id"]}, {"$set": {"enabled": new_val}})
        return {"ok": True, "enabled": new_val}

    @router.post("/run-now")
    async def run_now(current_user: dict = Depends(require_perm("edit_bookings"))):
        return await process_due_drips(db)

    @router.get("/preview/{key}")
    async def preview(key: str,
                      current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        tpl = DRIP_BY_KEY.get(key)
        if not tpl:
            raise HTTPException(404, f"Unknown key. Valid: {list(DRIP_BY_KEY)}")
        return {"key": key, "day": tpl["day"], "subject": tpl["subject"],
                "html": _render(tpl, "Demo Yönetici", "Demo Hotel")}

    return router
