"""Resend e-posta servisi — RESEND_API_KEY yoksa zarifçe MOCK'lar (email_outbox kaydı)."""
import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def resolve_key(db) -> str:
    """Panelden girilen DB anahtarı env'e tercih edilir."""
    s = await db.platform_settings.find_one({"id": "email"}, {"_id": 0}) or {}
    key = (s.get("resend_api_key") or "").strip()
    if not key:
        key = os.environ.get("RESEND_API_KEY", "").strip()
    if key in ("re_123456789", "your_key_here"):
        key = ""
    return key


async def send_email(db, to: str, subject: str, html: str, kind: str = "generic", meta: dict = None) -> str:
    doc = {"id": str(uuid.uuid4()), "to": to, "subject": subject, "html": html, "kind": kind,
           **(meta or {}), "created_at": datetime.now(timezone.utc).isoformat()}
    key = await resolve_key(db)
    if key:
        try:
            import resend
            resend.api_key = key
            settings = await db.platform_settings.find_one({"id": "email"}, {"_id": 0}) or {}
            sender = settings.get("sender_email") or os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
            r = await asyncio.to_thread(resend.Emails.send, {
                "from": sender,
                "to": [to], "subject": subject, "html": html})
            doc["status"] = "sent"
            doc["provider_id"] = (r or {}).get("id")
        except Exception as e:
            logger.warning(f"resend send failed: {e}")
            doc["status"] = "failed"
            doc["error"] = str(e)
    else:
        doc["status"] = "mocked"
    await db.email_outbox.insert_one(doc)
    return doc["status"]


def welcome_email_html(hotel_name: str, name: str, plan: str) -> tuple:
    steps = {
        "rms": ["Revenue & rates → <b>RMS Hızlı Kurulum (30 dk)</b> sihirbazını açın",
                "Baz oda fiyatınızı ve oda tipi farklarını girin",
                "Min/Max fiyat korumanızı (guardrail) belirleyin",
                "Rakip setinizi ekleyin ve fiyatlama modunu seçin (Autopilot / Co-Pilot)",
                "Go-Live kontrol listesini %80 üzerine çıkarın — ilk önerileriniz hazır!"],
        "cm": ["Channels & Distribution → <b>CM Hızlı Kurulum</b> sihirbazını açın",
               "Satış kanallarınızı seçin (Booking.com, Expedia, Airbnb...)",
               "Oda tiplerinizi kanal kodlarıyla eşleyin",
               "ARI senkron kapsamını ve stop-sell ayarını yapın",
               "Test push gönderin ve Go-Live kontrolünü tamamlayın"],
    }
    plan_steps = steps.get(plan, steps["rms"] + ["Ön büro takvimi ve rezervasyonlarınızı keşfedin"])
    items = "".join(
        f'<tr><td style="padding:6px 0;font-size:14px;color:#44403c;">{i+1}. {s}</td></tr>'
        for i, s in enumerate(plan_steps))
    html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;background:#fafaf9;padding:24px;">
      <tr><td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;padding:32px;">
          <tr><td style="font-size:20px;font-weight:bold;color:#1c1917;">Hoş geldiniz, {name}! 🎉</td></tr>
          <tr><td style="padding-top:8px;font-size:14px;color:#57534e;">
            <b>{hotel_name}</b> için {plan.upper()} planlı hesabınız hazır. 14 günlük ücretsiz denemeniz başladı.
          </td></tr>
          <tr><td style="padding-top:20px;font-size:15px;font-weight:bold;color:#1c1917;">Kurulum adımlarınız:</td></tr>
          {items}
          <tr><td style="padding-top:20px;font-size:12px;color:#a8a29e;">
            Sorunuz olursa bu e-postayı yanıtlamanız yeterli. — MyHotelBox &amp; ReveniQ Ekibi
          </td></tr>
        </table>
      </td></tr>
    </table>"""
    return f"{hotel_name} hesabınız hazır — kuruluma başlayın 🚀", html
