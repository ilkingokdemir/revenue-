"""Deneme süresi e-postaları — 3 gün kala hatırlatma + bitişte yükseltme linki (Resend yoksa mock)."""
import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

logger = logging.getLogger(__name__)

STAGES = {
    "t3": {"days_max": 3, "kind": "trial_reminder"},
    "expired": {"days_max": 0, "kind": "trial_upgrade"},
}


def _base_url() -> str:
    return os.environ.get("BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com")).rstrip("/")


def trial_email_html(hotel_name: str, name: str, stage: str, days_left: int, upgrade_url: str) -> tuple:
    if stage == "t3":
        subject = f"{hotel_name} — deneme sürenizin bitmesine {days_left} gün kaldı ⏳"
        headline = f"Merhaba {name}, denemenizin bitmesine <b>{days_left} gün</b> kaldı"
        body = (f"<b>{hotel_name}</b> için 14 günlük ücretsiz denemeniz yakında sona eriyor. "
                "Fiyat önerileriniz, kanal senkronunuz ve rezervasyon motorunuz kesintisiz devam etsin diye "
                "şimdiden planınızı seçebilirsiniz.")
        cta = "Planımı Seç ve Devam Et →"
    else:
        subject = f"{hotel_name} — deneme süreniz sona erdi, yükseltme linkiniz hazır 🚀"
        headline = f"Merhaba {name}, 14 günlük denemeniz sona erdi"
        body = (f"<b>{hotel_name}</b> hesabınızdaki veriler ve ayarlar güvende. "
                "Kaldığınız yerden devam etmek için aşağıdaki bağlantıdan planınızı yükseltmeniz yeterli — "
                "tüm kurulumunuz, fiyat kurallarınız ve rezervasyonlarınız sizi bekliyor.")
        cta = "Planımı Yükselt →"
    html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;background:#fafaf9;padding:24px;">
      <tr><td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;padding:32px;">
          <tr><td style="font-size:20px;font-weight:bold;color:#1c1917;">{headline}</td></tr>
          <tr><td style="padding-top:10px;font-size:14px;color:#57534e;line-height:1.6;">{body}</td></tr>
          <tr><td style="padding-top:22px;" align="center">
            <a href="{upgrade_url}" style="display:inline-block;background:linear-gradient(90deg,#4f46e5,#7c3aed);color:#ffffff;
               font-size:14px;font-weight:bold;text-decoration:none;padding:12px 28px;border-radius:10px;">{cta}</a>
          </td></tr>
          <tr><td style="padding-top:18px;font-size:12px;color:#a8a29e;" align="center">
            Bağlantı çalışmazsa: <a href="{upgrade_url}" style="color:#6366f1;">{upgrade_url}</a>
          </td></tr>
          <tr><td style="padding-top:16px;font-size:12px;color:#a8a29e;">
            Sorunuz olursa bu e-postayı yanıtlamanız yeterli. — MyHotelBox &amp; ReveniQ Ekibi
          </td></tr>
        </table>
      </td></tr>
    </table>"""
    return subject, html


async def run_trial_email_check(db) -> dict:
    from routes.platform_ext.mailer import send_email
    now = datetime.now(timezone.utc)
    sent, skipped = [], 0
    props = await db.properties.find(
        {"signup_source": "self_signup", "trial_ends_at": {"$exists": True, "$ne": None},
         "is_active": {"$ne": False}}, {"_id": 0}).to_list(500)
    for p in props:
        pid = p["id"]
        try:
            ends = datetime.fromisoformat(p["trial_ends_at"])
            if ends.tzinfo is None:
                ends = ends.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        days_left = (ends - now).total_seconds() / 86400
        already = p.get("trial_emails_sent") or []
        stage = None
        if days_left <= 0 and "expired" not in already:
            stage = "expired"
        elif 0 < days_left <= 3 and "t3" not in already:
            stage = "t3"
        if not stage:
            skipped += 1
            continue
        user = await db.users.find_one(
            {"property_ids": pid, "signup_source": "self_signup", "is_active": {"$ne": False}}, {"_id": 0})
        if not user:
            user = await db.users.find_one(
                {"property_ids": pid, "role": "manager", "is_active": {"$ne": False}}, {"_id": 0})
        if not user or not user.get("email"):
            skipped += 1
            continue
        upgrade_url = f"{_base_url()}/?upgrade=1&property={pid}"
        subj, html = trial_email_html(p.get("name", "Oteliniz"), user.get("name", ""), stage,
                                      max(1, int(days_left + 0.999)), upgrade_url)
        status = await send_email(db, user["email"], subj, html, kind=STAGES[stage]["kind"],
                                  meta={"property_id": pid, "stage": stage})
        await db.properties.update_one({"id": pid}, {"$addToSet": {"trial_emails_sent": stage}})
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "info",
            "title": "Deneme e-postası gönderildi" if status == "sent" else "Deneme e-postası (mock) kaydedildi",
            "message": f"{p.get('name', pid)} → {user['email']} ({'bitişe 3 gün hatırlatması' if stage == 't3' else 'yükseltme daveti'}) — durum: {status}",
            "category": "platform", "target_user": "", "target_role": "admin",
            "link_to": "", "priority": "normal", "read": False,
            "created_by": "Deneme Takip Robotu", "created_at": now.isoformat()})
        sent.append({"property_id": pid, "email": user["email"], "stage": stage, "status": status})
    return {"checked": len(props), "sent": sent, "skipped": skipped}


async def trial_email_loop(db, interval_seconds: int = 3600):
    while True:
        try:
            r = await run_trial_email_check(db)
            if r["sent"]:
                logger.info(f"trial_email_loop: {len(r['sent'])} e-posta işlendi")
        except Exception as e:
            logger.warning(f"trial_email_loop error: {e}")
        await asyncio.sleep(interval_seconds)


def create_trial_emails_router(db, require_roles):
    router = APIRouter()

    @router.post("/trial-emails/run")
    async def run_now(user=Depends(require_roles("admin", "manager"))):
        return await run_trial_email_check(db)

    @router.get("/trial-emails/outbox")
    async def outbox(user=Depends(require_roles("admin", "manager"))):
        items = await db.email_outbox.find(
            {"kind": {"$in": ["trial_reminder", "trial_upgrade"]}},
            {"_id": 0, "html": 0}).sort("created_at", -1).to_list(50)
        return {"items": items}

    return router
