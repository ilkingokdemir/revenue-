"""Deneme süresi e-postaları — 3 gün kala hatırlatma + bitişte yükseltme linki (Resend yoksa mock)."""
import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

STAGES = {
    "t3": {"days_max": 3, "kind": "trial_reminder"},
    "expired": {"days_max": 0, "kind": "trial_upgrade"},
    "survey": {"days_max": -3, "kind": "churn_survey"},
}

CHURN_REASONS = {
    "price": "💰 Fiyat yüksekti",
    "features": "🧩 Aradığım özellik yoktu",
    "setup": "🔧 Kurulum zor geldi",
    "competitor": "🏃 Başka ürün seçtim",
    "no_time": "⏰ Denemeye vaktim olmadı",
}

_expired_cache = {"pids": frozenset(), "ts": 0.0}


def invalidate_trial_cache():
    _expired_cache["ts"] = 0.0


async def get_expired_trial_pids(db) -> frozenset:
    """Süresi dolmuş + dönüşmemiş self-signup tesis id'leri (30 sn cache)."""
    import time
    if time.time() - _expired_cache["ts"] < 30:
        return _expired_cache["pids"]
    now_iso = datetime.now(timezone.utc).isoformat()
    docs = await db.properties.find(
        {"signup_source": "self_signup", "converted_at": {"$exists": False},
         "trial_ends_at": {"$lt": now_iso}}, {"_id": 0, "id": 1}).to_list(500)
    _expired_cache["pids"] = frozenset(d["id"] for d in docs)
    _expired_cache["ts"] = time.time()
    return _expired_cache["pids"]


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


def churn_survey_email_html(hotel_name: str, name: str, links: dict) -> tuple:
    subject = f"{hotel_name} — tek soru: neden vazgeçtiniz? 🙏"
    buttons = "".join(
        f'<tr><td style="padding:5px 0;" align="center">'
        f'<a href="{links[k]}" style="display:block;width:82%;background:#f5f5f4;border:1px solid #d6d3d1;'
        f'color:#1c1917;font-size:13px;font-weight:bold;text-decoration:none;padding:11px 16px;border-radius:10px;">{lbl}</a>'
        f"</td></tr>" for k, lbl in CHURN_REASONS.items())
    html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;background:#fafaf9;padding:24px;">
      <tr><td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;padding:32px;">
          <tr><td style="font-size:19px;font-weight:bold;color:#1c1917;">Merhaba {name}, tek bir sorumuz var 🙏</td></tr>
          <tr><td style="padding-top:10px;font-size:14px;color:#57534e;line-height:1.6;">
            <b>{hotel_name}</b> denemeniz sona erdi ve devam etmemeyi seçtiniz — sorun değil!
            Ürünü daha iyi yapabilmemiz için tek tıkla söyler misiniz: <b>neden vazgeçtiniz?</b>
          </td></tr>
          {buttons}
          <tr><td style="padding-top:16px;font-size:12px;color:#a8a29e;" align="center">
            Tek tık yeter — sayfa açılınca işiniz bitti. Teşekkürler! — MyHotelBox Ekibi
          </td></tr>
        </table>
      </td></tr>
    </table>"""
    return subject, html


def winback_email_html(hotel_name: str, upgrade_url: str) -> tuple:
    subject = f"{hotel_name} — size özel %20 indirim, geri dönün 🎁"
    html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;background:#fafaf9;padding:24px;">
      <tr><td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;padding:32px;">
          <tr><td style="font-size:20px;font-weight:bold;color:#1c1917;">Sizi duyduk: fiyat yüksekti 💬</td></tr>
          <tr><td style="padding-top:10px;font-size:14px;color:#57534e;line-height:1.6;">
            Geri bildiriminiz için teşekkürler. <b>{hotel_name}</b> için özel bir teklifimiz var:
            ilk 6 ay <b>%20 indirim</b>. Tüm kurulumunuz ve verileriniz aynen duruyor — kaldığınız yerden devam edin.
          </td></tr>
          <tr><td style="padding-top:16px;" align="center">
            <div style="display:inline-block;background:#fef3c7;border:2px dashed #f59e0b;border-radius:10px;padding:10px 26px;
                        font-size:18px;font-weight:bold;color:#92400e;letter-spacing:2px;">WINBACK20</div>
          </td></tr>
          <tr><td style="padding-top:16px;" align="center">
            <a href="{upgrade_url}" style="display:inline-block;background:linear-gradient(90deg,#059669,#10b981);color:#ffffff;
               font-size:14px;font-weight:bold;text-decoration:none;padding:12px 28px;border-radius:10px;">%20 İndirimle Geri Dön →</a>
          </td></tr>
          <tr><td style="padding-top:16px;font-size:12px;color:#a8a29e;" align="center">
            Kod 14 gün geçerlidir. Yükseltme sırasında WINBACK20 kodunu belirtmeniz yeterli. — MyHotelBox Ekibi
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
        converted = bool(p.get("converted_at"))
        stage = None
        if not converted:
            if days_left <= -3 and "survey" not in already:
                stage = "survey"
            elif days_left <= 0 and "expired" not in already:
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
        if stage == "survey":
            token = str(uuid.uuid4())
            links = {k: f"{_base_url()}/api/public/churn-survey/{token}?reason={k}" for k in CHURN_REASONS}
            subj, html = churn_survey_email_html(p.get("name", "Oteliniz"), user.get("name", ""), links)
            await db.churn_surveys.insert_one({
                "id": token, "property_id": pid, "email": user["email"],
                "sent_at": now.isoformat(), "reason": None, "answered_at": None})
        else:
            subj, html = trial_email_html(p.get("name", "Oteliniz"), user.get("name", ""), stage,
                                          max(1, int(days_left + 0.999)), upgrade_url)
        status = await send_email(db, user["email"], subj, html, kind=STAGES[stage]["kind"],
                                  meta={"property_id": pid, "stage": stage})
        await db.properties.update_one({"id": pid}, {"$addToSet": {"trial_emails_sent": stage}})
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "info",
            "title": "Deneme e-postası gönderildi" if status == "sent" else "Deneme e-postası (mock) kaydedildi",
            "message": f"{p.get('name', pid)} → {user['email']} ({'kayıp nedeni anketi' if stage == 'survey' else 'bitişe 3 gün hatırlatması' if stage == 't3' else 'yükseltme daveti'}) — durum: {status}",
            "category": "platform", "target_user": "", "target_role": "admin",
            "link_to": "", "priority": "normal", "read": False,
            "created_by": "Deneme Takip Robotu", "created_at": now.isoformat()})
        sent.append({"property_id": pid, "email": user["email"], "stage": stage, "status": status})
    return {"checked": len(props), "sent": sent, "skipped": skipped}


async def load_email_settings(db):
    """DB'deki Resend ayarlarını env'e uygular (UI'dan girilen anahtar tüm modüllerde geçerli olsun)."""
    s = await db.platform_settings.find_one({"id": "email"}, {"_id": 0})
    if s and s.get("resend_api_key"):
        os.environ["RESEND_API_KEY"] = s["resend_api_key"]
        if s.get("sender_email"):
            os.environ["SENDER_EMAIL"] = s["sender_email"]
            os.environ["RESEND_FROM"] = s["sender_email"]
            os.environ["FROM_EMAIL"] = s["sender_email"]
    return s


async def trial_email_loop(db, interval_seconds: int = 3600):
    try:
        await load_email_settings(db)
    except Exception as e:
        logger.warning(f"load_email_settings error: {e}")
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

    # ---- Deneme Dönüşüm Paneli ----
    @router.get("/trial-conversion/summary")
    async def trial_summary(user=Depends(require_roles("admin"))):
        now = datetime.now(timezone.utc)
        props = await db.properties.find(
            {"signup_source": "self_signup"}, {"_id": 0}).sort("created_at", -1).to_list(500)
        rows = []
        for p in props:
            days_left = None
            try:
                ends = datetime.fromisoformat(p["trial_ends_at"])
                if ends.tzinfo is None:
                    ends = ends.replace(tzinfo=timezone.utc)
                days_left = round((ends - now).total_seconds() / 86400, 1)
            except Exception:
                pass
            user_doc = await db.users.find_one(
                {"property_ids": p["id"], "signup_source": "self_signup"}, {"_id": 0, "email": 1, "name": 1})
            converted = bool(p.get("converted_at"))
            status = "converted" if converted else ("expired" if (days_left is not None and days_left <= 0) else "active")
            survey = await db.churn_surveys.find_one(
                {"property_id": p["id"], "reason": {"$ne": None}}, {"_id": 0, "reason": 1, "winback_sent": 1})
            rows.append({"property_id": p["id"], "name": p.get("name"), "plan": p.get("plan"),
                         "signup_at": p.get("trial_started_at") or p.get("created_at"),
                         "trial_ends_at": p.get("trial_ends_at"), "days_left": days_left,
                         "emails_sent": p.get("trial_emails_sent") or [],
                         "owner_email": (user_doc or {}).get("email"), "owner_name": (user_doc or {}).get("name"),
                         "churn_reason": (survey or {}).get("reason"),
                         "winback_sent": bool((survey or {}).get("winback_sent")),
                         "status": status, "converted_at": p.get("converted_at"), "converted_plan": p.get("converted_plan")})
        total = len(rows)
        converted_n = sum(1 for r in rows if r["status"] == "converted")
        # Huni: Kayıt → Kuruluma Başladı → Hatırlatma Aldı → Süre Doldu → Dönüştü
        pids = [r["property_id"] for r in rows]
        setup_pids = set()
        for coll in (db.rms_setup, db.room_types):
            async for d in coll.find({"property_id": {"$in": pids}}, {"_id": 0, "property_id": 1}):
                setup_pids.add(d["property_id"])
        expired_reached = sum(1 for r in rows if r["days_left"] is not None and r["days_left"] <= 0)
        funnel = [
            {"step": "Kayıt", "count": total},
            {"step": "Kuruluma Başladı", "count": sum(1 for r in rows if r["property_id"] in setup_pids)},
            {"step": "Hatırlatma E-postası Aldı", "count": sum(1 for r in rows if r["emails_sent"])},
            {"step": "Süre Doldu", "count": expired_reached},
            {"step": "Dönüştü", "count": converted_n},
        ]
        # Son 8 hafta kohortu (kayıt haftasına göre: kayıt sayısı + o kohorttan dönüşenler)
        weeks = []
        monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(7, -1, -1):
            ws = monday - timedelta(weeks=i)
            we = ws + timedelta(weeks=1)
            cohort = []
            for r in rows:
                try:
                    su = datetime.fromisoformat(r["signup_at"])
                    if su.tzinfo is None:
                        su = su.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                if ws <= su < we:
                    cohort.append(r)
            weeks.append({"week": ws.strftime("%d %b"), "signups": len(cohort),
                          "conversions": sum(1 for r in cohort if r["status"] == "converted")})
        # Kayıp nedenleri kırılımı (huni yanına)
        surveys_sent = await db.churn_surveys.count_documents({"property_id": {"$in": pids}})
        churn_counts = {}
        async for s in db.churn_surveys.find({"property_id": {"$in": pids}, "reason": {"$ne": None}}, {"_id": 0, "reason": 1}):
            churn_counts[s["reason"]] = churn_counts.get(s["reason"], 0) + 1
        churn_reasons = [{"key": k, "label": lbl, "count": churn_counts.get(k, 0)}
                         for k, lbl in CHURN_REASONS.items()]
        return {"metrics": {"total": total, "active": sum(1 for r in rows if r["status"] == "active"),
                            "expired": sum(1 for r in rows if r["status"] == "expired"),
                            "converted": converted_n,
                            "conversion_rate": round(converted_n * 100 / total, 1) if total else 0.0},
                "funnel": funnel, "weekly": weeks,
                "churn": {"sent": surveys_sent, "answered": sum(churn_counts.values()), "reasons": churn_reasons},
                "trials": rows}

    @router.post("/trial-conversion/{pid}/convert")
    async def mark_converted(pid: str, body: dict, user=Depends(require_roles("admin"))):
        plan = body.get("plan") or "pro"
        if plan not in ("basic", "rms", "cm", "pro", "full"):
            raise HTTPException(status_code=422, detail="plan: basic|rms|cm|pro|full")
        p = await db.properties.find_one({"id": pid, "signup_source": "self_signup"}, {"_id": 0})
        if not p:
            raise HTTPException(status_code=404, detail="Deneme tesisi bulunamadı")
        await db.properties.update_one({"id": pid}, {"$set": {
            "plan": plan, "modules_enabled": "all" if plan == "full" else plan,
            "converted_at": datetime.now(timezone.utc).isoformat(), "converted_plan": plan}})
        invalidate_trial_cache()
        return {"ok": True, "property_id": pid, "plan": plan}

    @router.post("/trial-conversion/{pid}/extend")
    async def extend_trial(pid: str, user=Depends(require_roles("admin"))):
        p = await db.properties.find_one({"id": pid, "signup_source": "self_signup"}, {"_id": 0})
        if not p:
            raise HTTPException(status_code=404, detail="Deneme tesisi bulunamadı")
        now = datetime.now(timezone.utc)
        try:
            cur = datetime.fromisoformat(p["trial_ends_at"])
            if cur.tzinfo is None:
                cur = cur.replace(tzinfo=timezone.utc)
        except Exception:
            cur = now
        new_end = (max(now, cur) + timedelta(days=7)).isoformat()
        await db.properties.update_one({"id": pid}, {
            "$set": {"trial_ends_at": new_end},
            "$pull": {"trial_emails_sent": {"$in": ["t3", "expired"]}}})
        invalidate_trial_cache()
        return {"ok": True, "property_id": pid, "trial_ends_at": new_end}

    @router.post("/trial-conversion/{pid}/send-upgrade-email")
    async def send_upgrade_now(pid: str, user=Depends(require_roles("admin"))):
        from routes.platform_ext.mailer import send_email
        p = await db.properties.find_one({"id": pid, "signup_source": "self_signup"}, {"_id": 0})
        if not p:
            raise HTTPException(status_code=404, detail="Deneme tesisi bulunamadı")
        u = await db.users.find_one({"property_ids": pid, "signup_source": "self_signup"}, {"_id": 0}) or \
            await db.users.find_one({"property_ids": pid, "role": "manager"}, {"_id": 0})
        if not u or not u.get("email"):
            raise HTTPException(status_code=404, detail="Tesise bağlı kullanıcı e-postası yok")
        upgrade_url = f"{_base_url()}/?upgrade=1&property={pid}"
        subj, html = trial_email_html(p.get("name", "Oteliniz"), u.get("name", ""), "expired", 0, upgrade_url)
        status = await send_email(db, u["email"], subj, html, kind="trial_upgrade",
                                  meta={"property_id": pid, "stage": "manual"})
        return {"ok": True, "to": u["email"], "status": status}

    # ---- Resend E-posta Ayarları ----
    @router.get("/email-settings")
    async def get_email_settings(user=Depends(require_roles("admin"))):
        s = await db.platform_settings.find_one({"id": "email"}, {"_id": 0}) or {}
        key = s.get("resend_api_key") or ""
        env_key = os.environ.get("RESEND_API_KEY", "")
        env_active = bool(env_key and not env_key.startswith("re_1234") and env_key != "your_key_here")
        return {"key_set": bool(key), "key_masked": (key[:6] + "•••" + key[-4:]) if key else None,
                "sender_email": s.get("sender_email") or os.environ.get("SENDER_EMAIL", "onboarding@resend.dev"),
                "verified": s.get("verified", False), "live": env_active,
                "updated_at": s.get("updated_at")}

    @router.post("/email-settings")
    async def save_email_settings(body: dict, user=Depends(require_roles("admin"))):
        key = (body.get("resend_api_key") or "").strip()
        sender = (body.get("sender_email") or "").strip()
        if not key.startswith("re_") or len(key) < 12:
            raise HTTPException(status_code=422, detail="Geçersiz anahtar — Resend anahtarları re_ ile başlar")
        verified = False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=12) as client:
                r = await client.get("https://api.resend.com/domains",
                                     headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                verified = True
            elif r.status_code in (400, 401, 403):
                raise HTTPException(status_code=400, detail="Resend anahtarı geçersiz/reddedildi — anahtarı kontrol edin")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"resend verify unreachable: {e}")
        doc = {"id": "email", "resend_api_key": key, "sender_email": sender,
               "verified": verified, "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.platform_settings.update_one({"id": "email"}, {"$set": doc}, upsert=True)
        await load_email_settings(db)
        return {"ok": True, "verified": verified,
                "message": "Anahtar doğrulandı — e-postalar artık CANLI gönderilecek ✅" if verified
                else "Anahtar kaydedildi (Resend API'ye ulaşılamadı, gönderimde denenecek)"}

    @router.delete("/email-settings")
    async def delete_email_settings(user=Depends(require_roles("admin"))):
        await db.platform_settings.delete_one({"id": "email"})
        os.environ["RESEND_API_KEY"] = ""
        return {"ok": True}

    @router.post("/email-settings/test")
    async def send_test_email(body: dict, user=Depends(require_roles("admin"))):
        from routes.platform_ext.mailer import send_email
        to = (body.get("to") or "").strip()
        if "@" not in to:
            raise HTTPException(status_code=422, detail="Geçerli bir e-posta adresi girin")
        status = await send_email(db, to, "MyHotelBox — Test E-postası ✅",
                                  "<p>Bu bir test e-postasıdır. Resend entegrasyonunuz çalışıyor! 🎉</p>",
                                  kind="settings_test")
        return {"ok": True, "status": status,
                "message": "Gönderildi ✅" if status == "sent"
                else ("Gönderim başarısız — anahtarı kontrol edin" if status == "failed"
                      else "Anahtar yok/placeholder — MOCK olarak kaydedildi")}

    # ---- Kayıp Nedeni Anketi (public, tek tık) ----
    @router.get("/public/churn-survey/{token}")
    async def churn_survey_answer(token: str, reason: str = ""):
        from fastapi.responses import HTMLResponse
        s = await db.churn_surveys.find_one({"id": token}, {"_id": 0})
        if not s:
            return HTMLResponse("<h3 style='font-family:Arial;text-align:center;margin-top:80px;'>Bağlantı geçersiz veya süresi dolmuş.</h3>", status_code=404)
        if reason in CHURN_REASONS and not s.get("reason"):
            await db.churn_surveys.update_one({"id": token}, {"$set": {
                "reason": reason, "answered_at": datetime.now(timezone.utc).isoformat()}})
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "type": "info", "title": "Kayıp nedeni anketi yanıtlandı",
                "message": f"{s.get('email')} → {CHURN_REASONS[reason]}",
                "category": "platform", "target_user": "", "target_role": "admin",
                "link_to": "", "priority": "normal", "read": False,
                "created_by": "Deneme Takip Robotu", "created_at": datetime.now(timezone.utc).isoformat()})
            # 🎁 Geri kazanma: 'fiyat yüksekti' diyene otomatik %20 indirim teklifi
            if reason == "price" and not s.get("winback_sent"):
                from routes.platform_ext.mailer import send_email
                prop = await db.properties.find_one({"id": s["property_id"]}, {"_id": 0, "name": 1})
                upgrade_url = f"{_base_url()}/?upgrade=1&property={s['property_id']}&promo=WINBACK20"
                subj, whtml = winback_email_html((prop or {}).get("name", "Oteliniz"), upgrade_url)
                wstatus = await send_email(db, s["email"], subj, whtml, kind="winback_offer",
                                           meta={"property_id": s["property_id"], "promo": "WINBACK20"})
                await db.churn_surveys.update_one({"id": token}, {"$set": {
                    "winback_sent": True, "winback_status": wstatus,
                    "winback_at": datetime.now(timezone.utc).isoformat()}})
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()), "type": "info",
                    "title": "Geri kazanma teklifi gönderildi 🎁",
                    "message": f"{s.get('email')} → %20 indirim (WINBACK20) — durum: {wstatus}",
                    "category": "platform", "target_user": "", "target_role": "admin",
                    "link_to": "", "priority": "normal", "read": False,
                    "created_by": "Deneme Takip Robotu", "created_at": datetime.now(timezone.utc).isoformat()})
        chosen = CHURN_REASONS.get(s.get("reason") or reason, "")
        return HTMLResponse(f"""
        <div style="font-family:Arial;max-width:480px;margin:80px auto;text-align:center;background:#fff;border:1px solid #e7e5e4;border-radius:16px;padding:36px;">
          <div style="font-size:40px;">🙏</div>
          <h2 style="color:#1c1917;margin:12px 0 6px;">Teşekkürler!</h2>
          <p style="color:#57534e;font-size:14px;">Yanıtınız kaydedildi{f": <b>{chosen}</b>" if chosen else ""}.<br/>
          Geri bildiriminiz ürünü daha iyi yapmamıza yardımcı olacak.</p>
          <p style="color:#a8a29e;font-size:12px;">Fikrinizi değiştirirseniz kapımız her zaman açık — MyHotelBox Ekibi</p>
        </div>""")

    return router
