"""Background tick workers moved out of server.py (ROADMAP P1)."""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_TASK_DONE = {"done", "completed", "closed", "resolved"}

_TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _tr(s: str) -> str:
    return (s or "").translate(_TR_MAP)


async def generate_social_report_pdf(db) -> str:
    """Görselli haftalık sosyal medya PDF raporu üret, URL döndür."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    now_dt = datetime.now(timezone.utc)
    week_ago = (now_dt - timedelta(days=7)).isoformat()
    week_ahead = (now_dt + timedelta(days=7)).date().isoformat()
    published = await db.social_drafts.count_documents(
        {"published": True, "published_at": {"$gte": week_ago}})
    pending = await db.social_drafts.count_documents(
        {"auto": True, "approved": {"$ne": True}})
    upcoming = await db.social_drafts.find(
        {"publish_date": {"$gte": now_dt.date().isoformat(), "$lte": week_ahead}},
        {"_id": 0, "topic": 1, "publish_date": 1, "publish_time": 1, "property_id": 1}
    ).sort("publish_date", 1).to_list(10)
    perf = await db.social_drafts.find(
        {"performance.likes": {"$gt": 0}},
        {"_id": 0, "topic": 1, "performance": 1}).to_list(200)
    topics = {}
    for d in perf:
        t = d.get("topic") or "diger"
        a = topics.setdefault(t, [0, 0, 0])
        a[0] += d["performance"].get("likes", 0)
        a[1] += d["performance"].get("reach", 0)
        a[2] += 1
    rows = sorted(
        [(t, round(a[0] / a[2], 1), round(a[1] / a[2], 1), a[2]) for t, a in topics.items()],
        key=lambda x: -x[1])
    imgs = await db.social_drafts.find(
        {"image_url": {"$exists": True}},
        {"_id": 0, "image_url": 1, "topic": 1}).sort("created_at", -1).to_list(4)
    os.makedirs("/app/backend/uploads/reports", exist_ok=True)
    fname = f"sosyal-rapor-{now_dt.date().isoformat()}.pdf"
    path = f"/app/backend/uploads/reports/{fname}"
    c = pdfcanvas.Canvas(path, pagesize=A4)
    w, h = A4
    c.setFillColorRGB(0.75, 0.15, 0.55)
    c.rect(0, h - 34 * mm, w, 34 * mm, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 19)
    c.drawString(18 * mm, h - 17 * mm, "Haftalik Sosyal Medya Raporu")
    c.setFont("Helvetica", 11)
    c.drawString(18 * mm, h - 25 * mm, f"MyHotelBox  ·  {now_dt.date().isoformat()}")
    y = h - 46 * mm
    c.setFillColorRGB(0.1, 0.1, 0.1)
    for label, val in [("Son 7 gunde yayinlanan paket", str(published)),
                       ("Onay bekleyen otomatik taslak", str(pending)),
                       ("Planli gonderi (7 gun)", str(len(upcoming)))]:
        c.setFont("Helvetica", 11)
        c.drawString(18 * mm, y, label)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(95 * mm, y, val)
        y -= 8 * mm
    y -= 4 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(18 * mm, y, "Konu performansi (ort. begeni / erisim)")
    y -= 8 * mm
    for t, likes, reach, n in rows[:6] or []:
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, y, f"- {_tr(t)[:40]}")
        c.setFont("Helvetica-Bold", 10)
        c.drawString(95 * mm, y, f"{likes} begeni · {reach} erisim · {n} gonderi")
        y -= 6.5 * mm
    if not rows:
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, y, "- Henuz performans verisi girilmedi")
        y -= 6.5 * mm
    y -= 4 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(18 * mm, y, "Onumuzdeki 7 gunun yayin plani")
    y -= 8 * mm
    for u in upcoming or []:
        tm = f" {u['publish_time']}" if u.get("publish_time") else ""
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, y, f"- {u['publish_date']}{tm}: {_tr(u.get('topic') or '')[:40]} ({u.get('property_id')})")
        y -= 6.5 * mm
    if not upcoming:
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, y, "- Planli gonderi yok")
        y -= 6.5 * mm
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(18 * mm, y, "Son gorseller")
    y -= 46 * mm
    x = 18 * mm
    for im in imgs:
        fpath = "/app/backend/uploads/social_images/" + im["image_url"].split("?")[0].split("/")[-1]
        if not os.path.exists(fpath):
            continue
        try:
            c.drawImage(ImageReader(fpath), x, y, width=40 * mm, height=40 * mm,
                        preserveAspectRatio=True, anchor='sw')
            c.setFont("Helvetica", 7)
            c.setFillColorRGB(0.35, 0.35, 0.35)
            c.drawString(x, y - 4 * mm, _tr(im.get("topic") or "")[:24])
            c.setFillColorRGB(0.1, 0.1, 0.1)
            x += 45 * mm
        except Exception as e:
            logger.warning(f"pdf image skip: {e}")
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(18 * mm, 12 * mm,
                 f"MyHotelBox Sosyal Medya Robotu · olusturma: {now_dt.isoformat()[:16]}")
    c.showPage()
    c.save()
    return f"/api/uploads/reports/{fname}"


async def run_winning_topic_check(db) -> dict:
    """Kazanan konudan ayda 2 otomatik taslak üret (10 gün arayla, onay bekler)."""
    now_dt = datetime.now(timezone.utc)
    month_start = now_dt.replace(day=1).date().isoformat()
    created = []
    async for p in db.properties.find({}, {"_id": 0, "id": 1, "name": 1}):
        pid = p["id"]
        drafts = await db.social_drafts.find(
            {"property_id": pid, "performance.likes": {"$gt": 0}},
            {"_id": 0, "topic": 1, "performance": 1}).to_list(200)
        if not drafts:
            continue
        topics = {}
        for d in drafts:
            t = d.get("topic") or "diğer"
            a = topics.setdefault(t, [0, 0])
            a[0] += d["performance"].get("likes", 0)
            a[1] += 1
        top = max(topics.items(), key=lambda kv: kv[1][0] / kv[1][1])[0]
        this_month = await db.social_drafts.count_documents(
            {"property_id": pid, "source": "winning_topic_auto",
             "created_at": {"$gte": month_start}})
        if this_month >= 2:
            continue
        last = await db.social_drafts.find_one(
            {"property_id": pid, "source": "winning_topic_auto"},
            {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
        if last and last["created_at"] >= (now_dt - timedelta(days=10)).isoformat():
            continue
        draft = (f"✨ {p.get('name', '')} misafirlerinin favorisi: {top}! En çok beğeni alan "
                 f"konumuzdan yeni bir kare ile karşınızdayız. Sizi de aramızda görmek isteriz 🧡 "
                 f"#otel #{top.replace(' ', '')} #misafirmemnuniyeti")
        await db.social_drafts.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "topic": top,
            "draft": draft, "source": "winning_topic_auto",
            "auto": True, "approved": False,
            "created_at": now_dt.isoformat()})
        created.append(pid)
    return {"drafts_created": len(created), "properties": created}


async def winning_topic_loop(db, interval_seconds: int = 21600):
    while True:
        try:
            res = await run_winning_topic_check(db)
            if res["drafts_created"]:
                logger.info(f"winning topic drafts: {res}")
        except Exception as e:
            logger.warning(f"winning topic tick error: {e}")
        await asyncio.sleep(interval_seconds)


async def run_social_weekly_report(db, force: bool = False) -> dict:
    """Haftalık sosyal medya özeti — yönetici e-postasına (MOCKED kuyruk)."""
    now_dt = datetime.now(timezone.utc)
    last = await db.social_weekly_reports.find_one(
        {}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
    if not force and last and last["created_at"] >= (now_dt - timedelta(days=7)).isoformat():
        return {"sent": False, "reason": "son 7 günde rapor gönderildi"}
    week_ago = (now_dt - timedelta(days=7)).isoformat()
    week_ahead = (now_dt + timedelta(days=7)).date().isoformat()
    published = await db.social_drafts.count_documents(
        {"published": True, "published_at": {"$gte": week_ago}})
    pending = await db.social_drafts.count_documents(
        {"auto": True, "approved": {"$ne": True}})
    upcoming = await db.social_drafts.find(
        {"publish_date": {"$gte": now_dt.date().isoformat(), "$lte": week_ahead}},
        {"_id": 0, "topic": 1, "publish_date": 1, "property_id": 1}
    ).sort("publish_date", 1).to_list(20)
    perf = await db.social_drafts.find(
        {"performance.likes": {"$gt": 0}},
        {"_id": 0, "topic": 1, "performance": 1}).to_list(200)
    topics = {}
    for d in perf:
        t = d.get("topic") or "diğer"
        a = topics.setdefault(t, [0, 0])
        a[0] += d["performance"]["likes"]
        a[1] += 1
    top_line = ""
    if topics:
        t, a = max(topics.items(), key=lambda kv: kv[1][0] / kv[1][1])
        top_line = f"En iyi konu: {t} (ort. {round(a[0] / a[1], 1)} beğeni)\n"
    plan = "\n".join(f"- {u['publish_date']}: {u['topic']} ({u['property_id']})"
                     for u in upcoming) or "- planlı gönderi yok"
    try:
        pdf_url = await generate_social_report_pdf(db)
    except Exception as e:
        logger.warning(f"social report pdf failed: {e}")
        pdf_url = None
    body = (f"HAFTALIK SOSYAL MEDYA RAPORU ({now_dt.date().isoformat()})\n\n"
            f"Son 7 günde yayınlanan paket: {published}\n"
            f"Onay bekleyen otomatik taslak: {pending}\n{top_line}\n"
            f"Önümüzdeki 7 günün yayın planı:\n{plan}"
            + (f"\n\nGörselli PDF raporu: {pdf_url}" if pdf_url else ""))
    await db.outbound_email_queue.insert_one({
        "id": str(uuid.uuid4()), "property_id": "all",
        "to": os.environ.get("NOTIFICATION_EMAIL", "yonetici@otel.com"),
        "subject": f"🗞️ Haftalık Sosyal Medya Raporu — {now_dt.date().isoformat()}",
        "body": body, "attachment_url": pdf_url,
        "type": "social_weekly_report", "status": "queued",
        "delivery_status": "mocked_email_queued", "created_at": now_dt.isoformat()})
    await db.social_weekly_reports.insert_one({
        "id": str(uuid.uuid4()), "created_at": now_dt.isoformat(),
        "published": published, "pending": pending, "upcoming": len(upcoming),
        "pdf_url": pdf_url})
    return {"sent": True, "published": published, "pending": pending,
            "upcoming": len(upcoming), "pdf_url": pdf_url}


async def social_report_loop(db, interval_seconds: int = 21600):
    while True:
        try:
            res = await run_social_weekly_report(db)
            if res.get("sent"):
                logger.info(f"social weekly report: {res}")
        except Exception as e:
            logger.warning(f"social report tick error: {e}")
        await asyncio.sleep(interval_seconds)


async def run_rating_trend_check(db, threshold: float = -0.2) -> dict:
    """Şube puanı düşüş trendine girince yöneticiye bildirim aç (7 gün dedupe)."""
    now_dt = datetime.now(timezone.utc)
    d30 = (now_dt - timedelta(days=30)).isoformat()
    d60 = (now_dt - timedelta(days=60)).isoformat()
    d7 = (now_dt - timedelta(days=7)).isoformat()
    alerts = []
    async for p in db.properties.find({}, {"_id": 0, "id": 1, "name": 1}):
        pid = p["id"]
        cur = await db.reviews.aggregate([
            {"$match": {"property_id": pid, "rating": {"$type": "number"},
                        "created_at": {"$gte": d30}}},
            {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "n": {"$sum": 1}}}]).to_list(1)
        prev = await db.reviews.aggregate([
            {"$match": {"property_id": pid, "rating": {"$type": "number"},
                        "created_at": {"$gte": d60, "$lt": d30}}},
            {"$group": {"_id": None, "avg": {"$avg": "$rating"}}}]).to_list(1)
        if not cur or not prev or cur[0]["n"] < 2:
            continue
        trend = round(cur[0]["avg"] - prev[0]["avg"], 2)
        if trend > threshold:
            continue
        existing = await db.notifications.find_one(
            {"category": "rating_trend", "property_id": pid, "created_at": {"$gte": d7}},
            {"_id": 0, "id": 1})
        if existing:
            continue
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "warning",
            "title": f"📉 Puan düşüş uyarısı — {p.get('name', pid)}",
            "message": (f"{p.get('name', pid)} şubesinin ortalama puanı son 30 günde "
                        f"{abs(trend)} puan düştü ({round(prev[0]['avg'], 2)} → "
                        f"{round(cur[0]['avg'], 2)}). İçgörü raporunu inceleyin."),
            "category": "rating_trend", "property_id": pid,
            "target_user": "", "target_role": "", "link_to": "ai-reply-robot",
            "priority": "high", "read": False,
            "created_by": "System", "created_at": now_dt.isoformat()})
        alerts.append({"property_id": pid, "trend": trend})
    return {"alerts_created": len(alerts), "details": alerts}


async def run_photo_contest(db) -> dict:
    """Ayın Karesi: en beğenilen misafir fotoğrafını seç, kazanan duyurusu taslağı üret."""
    now_dt = datetime.now(timezone.utc)
    month = now_dt.strftime("%Y-%m")
    created = []
    async for p in db.properties.find({}, {"_id": 0, "id": 1, "name": 1}):
        pid = p["id"]
        existing = await db.social_drafts.find_one(
            {"property_id": pid, "source": "photo_contest", "contest_month": month},
            {"_id": 0, "id": 1})
        if existing:
            continue
        drafts = await db.social_drafts.find(
            {"property_id": pid, "source": "guest_photo"},
            {"_id": 0, "id": 1, "image_url": 1, "performance": 1,
             "survey_response_id": 1}).to_list(100)
        if not drafts:
            continue
        winner = max(drafts, key=lambda d: (d.get("performance") or {}).get("likes", 0))
        resp = await db.survey_responses.find_one(
            {"id": winner.get("survey_response_id")}, {"_id": 0, "guest_name": 1})
        first_name = ((resp or {}).get("guest_name") or "Misafirimiz").split()[0]
        likes = (winner.get("performance") or {}).get("likes", 0)
        draft_id = str(uuid.uuid4())
        src = "/app/backend/uploads/social_images/" + winner["image_url"].split("?")[0].split("/")[-1]
        img_url = None
        if os.path.exists(src):
            import shutil
            shutil.copyfile(src, f"/app/backend/uploads/social_images/{draft_id}.png")
            img_url = f"/api/uploads/social_images/{draft_id}.png"
        draft = (f"🏆 AYIN KARESİ ({month}): Kazanan {first_name}! "
                 + (f"{likes} beğeniyle " if likes else "")
                 + f"misafirlerimizin favorisi oldu. Tebrikler! 🎉 Siz de karenizi anketimizle "
                 f"paylaşın, gelecek ayın yıldızı siz olun ⭐ #ayınkaresi #misafirkaresi #otel")
        await db.social_drafts.insert_one({
            "id": draft_id, "property_id": pid, "topic": "ayın karesi",
            "draft": draft, "source": "photo_contest", "contest_month": month,
            "auto": True, "approved": False,
            **({"image_url": img_url} if img_url else {}),
            "winner_response_id": winner.get("survey_response_id"),
            "created_at": now_dt.isoformat()})
        created.append(pid)
    return {"drafts_created": len(created), "properties": created, "month": month}


async def photo_contest_loop(db, interval_seconds: int = 43200):
    while True:
        try:
            res = await run_photo_contest(db)
            if res["drafts_created"]:
                logger.info(f"photo contest: {res}")
        except Exception as e:
            logger.warning(f"photo contest tick error: {e}")
        await asyncio.sleep(interval_seconds)


async def rating_trend_alert_loop(db, interval_seconds: int = 21600):
    while True:
        try:
            res = await run_rating_trend_check(db)
            if res["alerts_created"]:
                logger.info(f"rating trend alerts: {res}")
        except Exception as e:
            logger.warning(f"rating trend alert tick error: {e}")
        await asyncio.sleep(interval_seconds)


async def run_winback_reminder_check(db) -> dict:
    """Süresi 5 gün içinde dolacak kullanılmamış kodlara hatırlatma e-postası kuyruğa ekle."""
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    d5 = (now_dt + timedelta(days=5)).isoformat()
    offers = await db.winback_offers.find(
        {"redeemed": {"$ne": True}, "reminder_sent": {"$ne": True},
         "guest_email": {"$nin": ["", None]},
         "expires_at": {"$gte": now, "$lte": d5}}, {"_id": 0}).to_list(100)
    queued = 0
    for o in offers:
        try:
            prop = await db.properties.find_one({"id": o["property_id"]}, {"_id": 0, "name": 1}) or {}
            days_left = max(1, (datetime.fromisoformat(o["expires_at"]) - now_dt).days)
            await db.outbound_email_queue.insert_one({
                "id": str(uuid.uuid4()), "property_id": o["property_id"],
                "to": o["guest_email"],
                "subject": f"⏳ %{o['discount_pct']} indirim kodunuzun süresi dolmak üzere — {prop.get('name', '')}",
                "body": (f"Merhaba,\n\nSize özel WELCOME{o['discount_pct']} geri kazanım kodunuzun "
                         f"geçerlilik süresi {days_left} gün içinde doluyor "
                         f"(son gün: {o['expires_at'][:10]}).\n"
                         f"Rezervasyonunuzda kodu kullanarak %{o['discount_pct']} indirimden yararlanabilirsiniz.\n\n"
                         f"Sizi tekrar ağırlamayı çok isteriz.\n— {prop.get('name', 'Otel Yönetimi')}"),
                "type": "winback_reminder", "status": "queued",
                "delivery_status": "mocked_email_queued", "created_at": now})
            await db.winback_offers.update_one(
                {"id": o["id"]}, {"$set": {"reminder_sent": True, "reminder_sent_at": now}})
            queued += 1
        except Exception as e:
            logger.warning(f"winback reminder failed {o.get('id')}: {e}")
    return {"reminders_queued": queued}


async def winback_reminder_loop(db, interval_seconds: int = 21600):
    while True:
        try:
            res = await run_winback_reminder_check(db)
            if res["reminders_queued"]:
                logger.info(f"winback reminders: {res}")
        except Exception as e:
            logger.warning(f"winback reminder tick error: {e}")
        await asyncio.sleep(interval_seconds)


async def run_publish_day_check(db) -> dict:
    """Yayın günü gelen sosyal medya paketleri için 'bugün yayınla' bildirimi."""
    today = datetime.now(timezone.utc).date().isoformat()
    drafts = await db.social_drafts.find(
        {"publish_date": today, "publish_alert_sent": {"$ne": True},
         "packaged_task_id": {"$exists": True}}, {"_id": 0}).to_list(50)
    created = 0
    for d in drafts:
        task = await db.staff_tasks.find_one(
            {"id": d["packaged_task_id"]}, {"_id": 0, "status": 1})
        if task and task.get("status") in ("done", "completed", "closed"):
            continue
        prop = await db.properties.find_one(
            {"id": d["property_id"]}, {"_id": 0, "name": 1}) or {}
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "info",
            "title": f"📣 Bugün yayınla — {d.get('topic', '')}",
            "message": (f"{prop.get('name', d['property_id'])} için '{d.get('topic')}' sosyal medya "
                        f"paketinin yayın günü bugün ({today}"
                        f"{', önerilen saat ' + d['publish_time'] if d.get('publish_time') else ''})."
                        f" Paket pazarlama görevinde hazır."),
            "category": "publish_day", "property_id": d["property_id"],
            "target_user": "", "target_role": "", "link_to": "ai-reply-robot",
            "priority": "high", "read": False,
            "created_by": "System", "created_at": datetime.now(timezone.utc).isoformat()})
        await db.social_drafts.update_one(
            {"id": d["id"]}, {"$set": {"publish_alert_sent": True}})
        created += 1
    return {"alerts_created": created}


async def publish_day_alert_loop(db, interval_seconds: int = 3600):
    while True:
        try:
            res = await run_publish_day_check(db)
            if res["alerts_created"]:
                logger.info(f"publish day alerts: {res}")
        except Exception as e:
            logger.warning(f"publish day alert tick error: {e}")
        await asyncio.sleep(interval_seconds)


async def run_praise_hunter(db) -> dict:
    """Haftada bir: en iyi anket övgüsünü otomatik sosyal taslağa çevir (onay bekler)."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    created = []
    async for p in db.properties.find({}, {"_id": 0, "id": 1, "name": 1}):
        pid = p["id"]
        recent = await db.social_drafts.find_one(
            {"property_id": pid, "source": "survey_praise_auto",
             "created_at": {"$gte": week_ago}}, {"_id": 0, "id": 1})
        if recent:
            continue
        resp = await db.survey_responses.find(
            {"property_id": pid, "nps_score": {"$gte": 9},
             "comment": {"$nin": ["", None]},
             "social_draft_created": {"$ne": True}},
            {"_id": 0}).sort([("nps_score", -1), ("submitted_at", -1)]).to_list(1)
        if not resp:
            continue
        r = resp[0]
        first_name = (r.get("guest_name") or "Misafirimiz").split()[0]
        draft = (f"🌟 {first_name} adlı misafirimizden {r.get('nps_score')}/10: "
                 f"\"{(r.get('comment') or '')[:180]}\" Bu güzel sözler için teşekkürler! "
                 f"#misafirmemnuniyeti #otel #tesekkurler")
        await db.social_drafts.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "topic": "anket övgüsü",
            "draft": draft, "source": "survey_praise_auto",
            "auto": True, "approved": False,
            "survey_response_id": r.get("id"),
            "created_at": datetime.now(timezone.utc).isoformat()})
        await db.survey_responses.update_one(
            {"id": r.get("id")}, {"$set": {"social_draft_created": True}})
        created.append(pid)
    return {"drafts_created": len(created), "properties": created}


async def praise_hunter_loop(db, interval_seconds: int = 21600):
    while True:
        try:
            res = await run_praise_hunter(db)
            if res["drafts_created"]:
                logger.info(f"praise hunter: {res}")
        except Exception as e:
            logger.warning(f"praise hunter tick error: {e}")
        await asyncio.sleep(interval_seconds)


async def complaint_sla_loop(db, interval_seconds: int = 300):
    """Yanıt süresi hedefi (SLA) aşılan şikayetlerde yöneticiyi uyar."""
    while True:
        try:
            cfgs = {}
            async for c in db.review_agent_config.find(
                    {}, {"_id": 0, "property_id": 1, "sla_minutes": 1}):
                cfgs[c["property_id"]] = int(c.get("sla_minutes", 60))
            now = datetime.now(timezone.utc)
            open_c = await db.guest_complaints.find(
                {"status": {"$nin": ["resolved", "closed"]},
                 "sla_alerted": {"$ne": True},
                 "$or": [{"guest_response_text": {"$exists": False}},
                         {"guest_response_text": ""}]},
                {"_id": 0, "id": 1, "property_id": 1, "guest_name": 1,
                 "created_at": 1, "category": 1}).to_list(300)
            breached = 0
            for c in open_c:
                sla = cfgs.get(c.get("property_id"), 60)
                try:
                    dt = datetime.fromisoformat((c.get("created_at") or "").replace("Z", "+00:00"))
                except Exception:
                    continue
                if (now - dt).total_seconds() / 60 > sla:
                    await db.guest_complaints.update_one(
                        {"id": c["id"]},
                        {"$set": {"sla_breached": True, "sla_alerted": True,
                                  "sla_alerted_at": now.isoformat()}})
                    try:
                        from routes.platform_ext.mobile_push import send_expo_push
                        await send_expo_push(
                            db, "⏰ Yanıt süresi aşıldı",
                            f"{c.get('guest_name') or 'Misafir'} şikayeti {sla} dk içinde yanıtlanmadı ({c.get('category', '')})",
                            {"type": "sla_breach", "id": c["id"]}, kind="sla_breach")
                    except Exception:
                        pass
                    breached += 1
            if breached:
                logger.info(f"complaint_sla: {breached} SLA breach alerted")
        except Exception as e:
            logger.warning(f"complaint_sla error: {e}")
        await asyncio.sleep(interval_seconds)


async def complaint_task_sync_loop(db, interval_seconds: int = 300):
    """Şikayetten oluşan departman görevi kapanınca şikayeti otomatik çözüldü yap."""
    while True:
        try:
            open_complaints = await db.guest_complaints.find(
                {"routed_task_id": {"$exists": True, "$ne": ""},
                 "status": {"$nin": ["resolved", "closed"]}},
                {"_id": 0, "id": 1, "routed_task_id": 1, "routed_collection": 1,
                 "routed_department": 1}).to_list(300)
            resolved = 0
            for c in open_complaints:
                coll = getattr(db, c.get("routed_collection") or "staff_tasks", None)
                if coll is None:
                    continue
                task = await coll.find_one({"id": c["routed_task_id"]}, {"_id": 0, "status": 1})
                if task and (task.get("status") or "").lower() in _TASK_DONE:
                    now = datetime.now(timezone.utc).isoformat()
                    await db.guest_complaints.update_one(
                        {"id": c["id"]},
                        {"$set": {"status": "resolved", "resolved_at": now,
                                  "resolved_by": f"auto ({c.get('routed_department', 'departman')} görevi tamamlandı)",
                                  "resolution_notes": "Departman görevi kapatıldığı için otomatik çözüldü."}})
                    resolved += 1
            if resolved:
                logger.info(f"complaint_task_sync: auto-resolved {resolved} complaints")
        except Exception as e:
            logger.warning(f"complaint_task_sync error: {e}")
        await asyncio.sleep(interval_seconds)


async def scheduled_checkout_loop(db, interval_seconds: int = 300):
    while True:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            ripe = await db.scheduled_checkouts.find(
                {"status": "pending", "checkout_at": {"$lte": now_iso}}, {"_id": 0}
            ).to_list(200)
            for row in ripe:
                b = await db.bookings.find_one({"id": row["booking_id"]}, {"_id": 0, "status": 1})
                if b and (b.get("status") or "").lower() not in {"checked_out", "cancelled"}:
                    await db.bookings.update_one(
                        {"id": row["booking_id"]},
                        {"$set": {
                            "status": "checked_out",
                            "checked_out_at": now_iso,
                            "checkout_channel": "scheduled_self_service",
                        }},
                    )
                await db.scheduled_checkouts.update_one(
                    {"booking_id": row["booking_id"]},
                    {"$set": {"status": "done", "executed_at": now_iso, "updated_at": now_iso}},
                )
            if ripe:
                logger.info(f"Scheduled-checkout tick: flushed {len(ripe)} rows")
        except Exception as e:
            logger.warning(f"Scheduled-checkout tick error: {e}")
        await asyncio.sleep(interval_seconds)


async def otb_snapshot_loop(db, interval_seconds: int = 21600):
    """Günlük OTB snapshot arşivi — gerçek pickup/pace hesapları için (idempotent, günde 1)."""
    from datetime import timedelta
    while True:
        try:
            today = datetime.now(timezone.utc).date()
            scan_date = today.isoformat()
            exists = await db.otb_daily_snapshots.find_one({"scan_date": scan_date}, {"_id": 1})
            if not exists:
                props = await db.properties.find({}, {"_id": 0, "id": 1}).to_list(200)
                total_docs = 0
                for p in props:
                    pid = p.get("id")
                    if not pid:
                        continue
                    day_counts = {}
                    async for b in db.bookings.find(
                            {"property_id": pid, "status": {"$ne": "cancelled"},
                             "check_out": {"$gt": scan_date}},
                            {"_id": 0, "check_in": 1, "check_out": 1}):
                        try:
                            ci = datetime.strptime(b["check_in"][:10], "%Y-%m-%d").date()
                            co = datetime.strptime(b["check_out"][:10], "%Y-%m-%d").date()
                        except (ValueError, TypeError, KeyError):
                            continue
                        d = max(ci, today)
                        end = min(co, today + timedelta(days=90))
                        while d < end:
                            day_counts[d.isoformat()] = day_counts.get(d.isoformat(), 0) + 1
                            d += timedelta(days=1)
                    if day_counts:
                        docs = [{"property_id": pid, "scan_date": scan_date, "date": k,
                                 "rooms_booked": v, "created_at": datetime.now(timezone.utc).isoformat()}
                                for k, v in day_counts.items()]
                        await db.otb_daily_snapshots.insert_many(docs)
                        total_docs += len(docs)
                # 180 günden eski snapshot'ları temizle
                purge_before = (today - timedelta(days=180)).isoformat()
                await db.otb_daily_snapshots.delete_many({"scan_date": {"$lt": purge_before}})
                logger.info(f"OTB snapshot: {scan_date} için {total_docs} satır arşivlendi")
        except Exception as e:
            logger.warning(f"OTB snapshot tick error: {e}")
        await asyncio.sleep(interval_seconds)


async def str_scan_loop(db, interval_seconds: int = 3600):
    """Gece STR taraması — canlı Booking.com STR verisini 20 saatte bir tazeler."""
    import logging
    logger = logging.getLogger(__name__)
    while True:
        try:
            from routes.revenue_ext.str_market import run_str_scan
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat()
            props = await db.properties.find(
                {"is_active": {"$ne": False}, "latitude": {"$ne": None}},
                {"_id": 0, "id": 1}).to_list(50)
            for p in props:
                pid = p["id"]
                status = await db.str_scan_status.find_one({"property_id": pid}, {"_id": 0})
                if status and status.get("status") == "running":
                    continue
                if status and (status.get("finished_at") or "") > cutoff:
                    continue
                await db.str_scan_status.update_one(
                    {"property_id": pid},
                    {"$set": {"property_id": pid, "status": "running", "scanned": 0,
                              "live_ok": 0, "started_at": datetime.now(timezone.utc).isoformat(),
                              "finished_at": None, "started_by": "cron"}},
                    upsert=True)
                res = await run_str_scan(db, pid)
                logger.info(f"str_scan_loop: {pid} → {res}")
                await asyncio.sleep(10)
        except Exception as e:
            logger.warning(f"str_scan_loop error: {e}")
        await asyncio.sleep(interval_seconds)


async def revenue_brain_loop(db, interval_seconds: int = 21600):
    """Revenue Brain öğrenme döngüsü — 20 saatte bir sonuç ölç + ağırlık öğren + ders üret."""
    import logging
    logger = logging.getLogger(__name__)
    while True:
        try:
            from routes.revenue_ext.revenue_brain import run_learning_cycle
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat()
            props = await db.properties.find(
                {"is_active": {"$ne": False}}, {"_id": 0, "id": 1}).to_list(50)
            for p in props:
                state = await db.revenue_brain_state.find_one(
                    {"property_id": p["id"]}, {"_id": 0, "last_cycle_at": 1})
                if state and (state.get("last_cycle_at") or "") > cutoff:
                    continue
                res = await run_learning_cycle(db, p["id"])
                logger.info(f"revenue_brain_loop: {p['id']} → {res}")
        except Exception as e:
            logger.warning(f"revenue_brain_loop error: {e}")
        await asyncio.sleep(interval_seconds)


async def onboarding_drip_loop(db, interval_seconds: int = 1800):
    """İlk 7 Gün aktivasyon e-posta serisi — 30 dk'da bir süresi gelenleri gönderir."""
    import logging
    logger = logging.getLogger(__name__)
    while True:
        try:
            from routes.platform_ext.onboarding_drip import process_due_drips
            res = await process_due_drips(db)
            if res.get("sent"):
                logger.info(f"onboarding_drip_loop: {res}")
        except Exception as e:
            logger.warning(f"onboarding_drip_loop error: {e}")
        await asyncio.sleep(interval_seconds)


async def reports_loop(db, interval_seconds: int = 300):
    while True:
        try:
            from routes.platform_ext.scheduled_reports import GENERATORS as _GENS, _next_run as _nr
            now_iso = datetime.now(timezone.utc).isoformat()
            due = await db.report_subscriptions.find(
                {"enabled": True, "next_run_at": {"$lte": now_iso}}, {"_id": 0}
            ).to_list(100)
            for sub in due:
                gen = _GENS.get(sub["report_key"])
                if not gen:
                    continue
                try:
                    payload, mime = await gen(db, sub.get("filters") or {}, sub.get("property_id"))
                    snap = {
                        "id":              str(uuid.uuid4()),
                        "subscription_id": sub["id"],
                        "report_key":      sub["report_key"],
                        "property_id":     sub.get("property_id"),
                        "email":           sub.get("email"),
                        "payload":         payload,
                        "mime_type":       mime,
                        "size_bytes":      len(payload.encode("utf-8")),
                        "created_at":      now_iso,
                        "delivery_status": "mocked_email_sent",
                    }
                    await db.report_snapshots.insert_one(snap)
                    await db.report_subscriptions.update_one(
                        {"id": sub["id"]},
                        {"$set": {
                            "last_run_at":      now_iso,
                            "last_snapshot_id": snap["id"],
                            "next_run_at":      _nr(sub["frequency"]),
                        }},
                    )
                except Exception as e:
                    logger.warning(f"Report gen failed for sub {sub['id']}: {e}")
            if due:
                logger.info(f"Scheduled-reports tick: processed {len(due)} subs")
        except Exception as e:
            logger.warning(f"Reports tick error: {e}")
        await asyncio.sleep(interval_seconds)
