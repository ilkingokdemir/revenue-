"""Aylık Hedef Panoları + Aylık Yönetim Raporu (otomatik ay kapanışı e-postası)."""
import asyncio
import calendar
import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)
ACTIVE = {"$nin": ["cancelled", "no_show"]}


def _now():
    return datetime.now(timezone.utc)


async def _month_metrics(db, pid: str, month_key: str) -> dict:
    """Verilen ay için gelir/doluluk/ADR/ABS metrikleri (check-in ayına göre)."""
    y, m = int(month_key[:4]), int(month_key[5:7])
    days = calendar.monthrange(y, m)[1]
    start, end = f"{month_key}-01", f"{month_key}-{days:02d}"
    revenue, sold_rn, arrivals = 0.0, 0, 0
    async for b in db.bookings.find(
            {"property_id": pid, "status": ACTIVE, "check_in": {"$gte": start, "$lte": end}},
            {"_id": 0, "total_price": 1, "nights": 1}):
        revenue += float(b.get("total_price") or 0)
        sold_rn += int(b.get("nights") or 0)
        arrivals += 1
    cancels = await db.bookings.count_documents(
        {"property_id": pid, "status": "cancelled", "check_in": {"$gte": start, "$lte": end}})
    abs_rev = 0.0
    async for b in db.bookings.find(
            {"property_id": pid, "status": ACTIVE, "abs_total": {"$gt": 0},
             "created_at": {"$gte": f"{start}T00:00:00", "$lte": f"{end}T23:59:59"}},
            {"_id": 0, "abs_total": 1}):
        abs_rev += float(b.get("abs_total") or 0)
    rooms = await db.rooms.count_documents({"property_id": pid})
    avail = max(1, rooms * days)
    return {"month": month_key, "revenue": round(revenue, 2), "sold_room_nights": sold_rn,
            "arrivals": arrivals, "cancellations": cancels,
            "occupancy_pct": round(100 * min(1.0, sold_rn / avail), 1),
            "adr": round(revenue / sold_rn, 2) if sold_rn else 0,
            "abs_revenue": round(abs_rev, 2), "rooms": rooms, "days": days}


async def get_targets_with_progress(db, pid: str) -> dict:
    now = _now()
    month_key = now.strftime("%Y-%m")
    t = await db.revenue_targets.find_one({"property_id": pid}, {"_id": 0}) or {}
    cur = await _month_metrics(db, pid, month_key)
    rev_t = float(t.get("revenue_target") or 0)
    occ_t = float(t.get("occupancy_target") or 0)
    return {"month": month_key,
            "revenue_target": rev_t, "occupancy_target": occ_t,
            "current": cur,
            "revenue_progress_pct": round(100 * cur["revenue"] / rev_t, 1) if rev_t > 0 else None,
            "occupancy_progress_pct": round(100 * cur["occupancy_pct"] / occ_t, 1) if occ_t > 0 else None}


async def build_monthly_report(db, pid: str, month_key: str) -> dict:
    cur = await _month_metrics(db, pid, month_key)
    y, m = int(month_key[:4]), int(month_key[5:7])
    prev_key = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
    prev = await _month_metrics(db, pid, prev_key)
    t = await db.revenue_targets.find_one({"property_id": pid}, {"_id": 0}) or {}
    abs_s = await db.abs_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
    rebase = await db.rebase_reports.find_one(
        {"property_id": pid, "created_at": {"$gte": f"{month_key}-01"}},
        {"_id": 0, "rows": 0}, sort=[("created_at", -1)])
    impacts = await db.root_cause_impacts.find({"property_id": pid, "created_at": {"$gte": f"{month_key}-01"}}, {"_id": 0}).to_list(50)
    imp_all = await db.root_cause_impacts.find({"property_id": pid}, {"_id": 0, "rating_delta": 1, "verdict": 1}).to_list(500)
    closed_month = await db.staff_tasks.count_documents({"property_id": pid, "source": "root_cause", "status": {"$in": ["done", "resolved", "completed", "closed"]},
                                                         "completed_at": {"$gte": f"{month_key}-01"}})
    impact = {"closed_tasks_month": closed_month, "reported_month": len(impacts),
              "improved": sum(1 for i in impacts if i.get("verdict") == "improved"), "worse": sum(1 for i in impacts if i.get("verdict") == "worse"),
              "total_rating_gain": round(sum(float(i.get("rating_delta") or 0) for i in impacts), 2),
              "cumulative_rating_gain": round(sum(float(i.get("rating_delta") or 0) for i in imp_all), 2),
              "items": [{"topic": i.get("topic"), "verdict": i.get("verdict"), "rating_delta": i.get("rating_delta"),
                         "before": (i.get("before") or {}).get("topic_avg_rating"), "after": (i.get("after") or {}).get("topic_avg_rating")} for i in impacts[:8]]}
    return {"month": month_key, "metrics": cur, "prev": prev, "impact": impact,
            "targets": {"revenue_target": float(t.get("revenue_target") or 0),
                        "occupancy_target": float(t.get("occupancy_target") or 0),
                        "abs_target": float(abs_s.get("abs_monthly_target") or 0)},
            "rebase": ({"date": rebase["created_at"][:10],
                        "weighted_change_pct": rebase.get("weighted_change_pct"),
                        "loss": rebase.get("contribution", {}).get("loss")} if rebase else None)}


def _pct_row(label, cur, prev, unit="£"):
    delta = round(100 * (cur - prev) / prev, 1) if prev else None
    d = f" <span style='color:{'#059669' if delta >= 0 else '#dc2626'}'>({'+' if delta >= 0 else ''}{delta}%)</span>" if delta is not None else ""
    val = f"{unit}{cur:,}" if unit == "£" else f"{cur}{unit}"
    return f"<tr><td style='padding:6px 10px;border-bottom:1px solid #f5f5f4'>{label}</td><td style='padding:6px 10px;border-bottom:1px solid #f5f5f4'><b>{val}</b>{d}</td></tr>"


def _target_line(label, actual, target, unit="£"):
    if target <= 0:
        return ""
    pct = round(100 * actual / target, 1)
    color = "#059669" if pct >= 100 else "#d97706" if pct >= 60 else "#dc2626"
    a = f"{unit}{actual:,}" if unit == "£" else f"{actual}{unit}"
    tt = f"{unit}{target:,}" if unit == "£" else f"{target}{unit}"
    return f"<div style='margin-bottom:6px;font-size:13px'>🎯 <b>{label}:</b> {a} / {tt} — <b style='color:{color}'>%{pct}</b></div>"


def _impact_html(imp: dict) -> str:
    if not imp:
        return ""
    rows = "".join(f"<tr><td style='padding:4px 8px;text-transform:capitalize'>{i['topic']}</td><td style='padding:4px 8px'>{i['before'] or '—'}★ → {i['after'] or '—'}★</td>"
                   f"<td style='padding:4px 8px;color:{'#15803d' if i['verdict']=='improved' else '#b91c1c' if i['verdict']=='worse' else '#78716c'}'>{'+' if (i['rating_delta'] or 0) > 0 else ''}{i['rating_delta'] if i['rating_delta'] is not None else '—'} · {i['verdict']}</td></tr>"
                   for i in imp.get("items", []))
    gain = imp.get("total_rating_gain", 0)
    return (f"<div style='background:#fffbeb;border:1px solid #fde68a;border-radius:12px;padding:12px;margin-top:12px'>"
            f"<b>Etki Panosu — Kök Neden Görevleri</b><br/>"
            f"<span style='font-size:13px'>Bu ay kapanan görev: <b>{imp.get('closed_tasks_month', 0)}</b> · Raporlanan etki: <b>{imp.get('reported_month', 0)}</b> "
            f"(📈 {imp.get('improved', 0)} iyileşti · 📉 {imp.get('worse', 0)} kötüleşti) · Toplam puan kazancı: <b style='color:{'#15803d' if gain >= 0 else '#b91c1c'}'>{'+' if gain > 0 else ''}{gain}★</b> "
            f"· Kümülatif: <b>{'+' if imp.get('cumulative_rating_gain', 0) > 0 else ''}{imp.get('cumulative_rating_gain', 0)}★</b></span>"
            + (f"<table style='font-size:12px;margin-top:8px;border-collapse:collapse'>{rows}</table>" if rows else "")
            + "</div>")


def _monthly_html(prop_name: str, r: dict) -> str:
    mtr, prev, tg = r["metrics"], r["prev"], r["targets"]
    targets_html = (_target_line("Oda geliri hedefi", mtr["revenue"], tg["revenue_target"])
                    + _target_line("Doluluk hedefi", mtr["occupancy_pct"], tg["occupancy_target"], unit="%")
                    + _target_line("ABS hedefi", mtr["abs_revenue"], tg["abs_target"]))
    rebase_html = ""
    if r.get("rebase"):
        rb = r["rebase"]
        rebase_html = (f"<div style='background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;padding:12px;font-size:13px;margin-top:10px'>"
                       f"🧪 <b>Rebase analizi ({rb['date']})</b>: otel geneli %{rb.get('weighted_change_pct')} · "
                       f"90 günde katkı kaybı £{(rb.get('loss') or 0):,}</div>")
    return (f"<div style='font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#292524'>"
            f"<div style='background:linear-gradient(90deg,#0f766e,#0284c7);border-radius:12px 12px 0 0;padding:20px 24px;color:#fff'>"
            f"<h1 style='margin:0;font-size:18px'>Aylık Yönetim Raporu — {prop_name}</h1>"
            f"<p style='margin:4px 0 0;font-size:12px;opacity:.9'>{r['month']} ay kapanışı</p></div>"
            f"<div style='border:1px solid #e7e5e4;border-top:none;border-radius:0 0 12px 12px;padding:20px 24px'>"
            f"<table style='width:100%;border-collapse:collapse;font-size:13px'>"
            + _pct_row("Oda geliri", mtr["revenue"], prev["revenue"])
            + _pct_row("Doluluk", mtr["occupancy_pct"], prev["occupancy_pct"], unit="%")
            + _pct_row("ADR", mtr["adr"], prev["adr"])
            + _pct_row("Varış (rezervasyon)", mtr["arrivals"], prev["arrivals"], unit="")
            + _pct_row("İptal", mtr["cancellations"], prev["cancellations"], unit="")
            + _pct_row("ABS geliri", mtr["abs_revenue"], prev["abs_revenue"])
            + f"</table>"
            + (f"<div style='background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:12px;margin-top:12px'>{targets_html}</div>" if targets_html else "")
            + rebase_html
            + _impact_html(r.get("impact") or {})
            + f"<p style='color:#a8a29e;font-size:11px;margin-top:20px'>MyHotelBox — her ay kapanışında otomatik hazırlanır. Önceki ay ({prev['month']}) ile karşılaştırmalıdır.</p></div></div>")


async def send_monthly_report(db, pid: str, month_key: str, forced: bool = False) -> dict:
    existing = await db.monthly_reports.find_one({"property_id": pid, "month": month_key}, {"_id": 0, "id": 1})
    if existing and not forced:
        return {"skipped": True, "reason": "already_sent"}
    report = await build_monthly_report(db, pid, month_key)
    prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
    html = _monthly_html(prop.get("name", pid), report)
    recipients = [u["email"] async for u in db.users.find(
        {"role": {"$in": ["admin", "manager"]}, "email": {"$exists": True}}, {"_id": 0, "email": 1}).limit(10)]
    from routes.platform_ext.mailer import send_email
    for to in recipients:
        try:
            await send_email(db, to, f"Aylık Yönetim Raporu — {prop.get('name', pid)} ({month_key})",
                             html, kind="monthly_report", meta={"property_id": pid, "month": month_key})
        except Exception:
            pass
    doc = {"id": str(uuid.uuid4()), "property_id": pid, "month": month_key,
           "report": report, "sent_to": recipients, "forced": forced,
           "created_at": _now().isoformat()}
    await db.monthly_reports.insert_one(dict(doc))
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()), "title": "🗓 Aylık yönetim raporu hazır",
        "message": f"{pid}: {month_key} kapanış raporu oluşturuldu ve {len(recipients)} yöneticiye gönderildi.",
        "category": "revenue", "priority": "medium", "read": False, "created_at": _now().isoformat()})
    doc.pop("_id", None)
    return {"ok": True, "sent_to": recipients, "report": report, "id": doc["id"]}


async def monthly_report_loop(db, interval_seconds: int = 3600):
    await asyncio.sleep(420)
    while True:
        try:
            now = _now()
            if now.day == 1 and now.hour >= 7:
                prev = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
                for pid in await db.properties.distinct("id"):
                    r = await send_monthly_report(db, pid, prev)
                    if not r.get("skipped"):
                        logger.info("Aylık rapor gönderildi: %s %s", pid, prev)
        except Exception as ex:
            logger.warning("Monthly report loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_monthly_report_router(db, require_roles):
    router = APIRouter(tags=["monthly-report"])
    ROLES = ("admin", "manager")

    @router.get("/revenue/targets/{property_id}")
    async def get_targets(property_id: str, _u: dict = Depends(require_roles(*ROLES))):
        return await get_targets_with_progress(db, property_id)

    @router.put("/revenue/targets/{property_id}")
    async def set_targets(property_id: str, body: dict, _u: dict = Depends(require_roles(*ROLES))):
        try:
            rev_t = float(body.get("revenue_target") or 0)
            occ_t = float(body.get("occupancy_target") or 0)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Hedefler sayı olmalı")
        if rev_t < 0 or occ_t < 0 or occ_t > 100:
            raise HTTPException(status_code=422, detail="Geçersiz hedef (doluluk 0-100 arası olmalı)")
        await db.revenue_targets.update_one(
            {"property_id": property_id},
            {"$set": {"revenue_target": rev_t, "occupancy_target": occ_t,
                      "updated_at": _now().isoformat(), "updated_by": _u.get("email", "")}},
            upsert=True)
        return {"ok": True, "revenue_target": rev_t, "occupancy_target": occ_t}

    @router.get("/monthly-report/{property_id}/history")
    async def report_history(property_id: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.monthly_reports.find({"property_id": property_id},
                                             {"_id": 0, "report": 0}).sort("created_at", -1).to_list(12)
        return {"history": rows}

    @router.get("/monthly-report/{property_id}/render/{report_id}")
    async def report_render(property_id: str, report_id: str, _u: dict = Depends(require_roles(*ROLES))):
        doc = await db.monthly_reports.find_one({"id": report_id, "property_id": property_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Rapor bulunamadı")
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1}) or {}
        return {"html": _monthly_html(prop.get("name", property_id), doc["report"]),
                "month": doc["month"], "created_at": doc["created_at"], "sent_to": doc.get("sent_to", [])}

    @router.post("/monthly-report/{property_id}/send-now")
    async def report_send_now(property_id: str, body: dict = None, _u: dict = Depends(require_roles(*ROLES))):
        month = (body or {}).get("month") or _now().strftime("%Y-%m")
        return await send_monthly_report(db, property_id, month, forced=True)

    return router
