"""
Haftalık Yönetici Bülteni — her pazartesi geçen haftanın gelir, doluluk, ADR,
giriş/iptal ve merdiven kazançlarını tek şık e-postada özetler.
Collection: weekly_digests
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import asyncio
import logging

from routes.platform_ext.mailer import send_email
from routes.revenue_ext.morning_karne import compute_ladder_weekly

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


async def _week_metrics(db, pid: str, start, total_rooms: int) -> Dict:
    days = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    revenue, sold_nights = 0.0, 0
    for d in days:
        async for b in db.bookings.find(
                {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                 "source": {"$ne": "pms_history_import"},
                 "check_in": {"$lte": d}, "check_out": {"$gt": d}},
                {"_id": 0, "rate": 1, "total_price": 1, "nights": 1}):
            nightly = float(b.get("rate", 0) or 0)
            if nightly <= 0:
                nights = max(1, int(b.get("nights", 1) or 1))
                nightly = float(b.get("total_price", 0) or 0) / nights
            revenue += nightly
            sold_nights += 1
    occ = round(sold_nights / (total_rooms * 7) * 100, 1) if total_rooms else 0.0
    adr = round(revenue / sold_nights, 2) if sold_nights else 0.0
    end = start + timedelta(days=7)
    arrivals = await db.bookings.count_documents(
        {"property_id": pid, "check_in": {"$gte": start.isoformat(), "$lt": end.isoformat()},
         "status": {"$nin": ["cancelled"]}, "source": {"$ne": "pms_history_import"}})
    cancels = await db.bookings.count_documents(
        {"property_id": pid, "status": "cancelled",
         "check_in": {"$gte": start.isoformat(), "$lt": end.isoformat()}})
    return {"revenue": round(revenue, 2), "occupancy": occ, "adr": adr,
            "sold_nights": sold_nights, "arrivals": arrivals, "cancellations": cancels}


def _delta(cur: float, prev: float, pts: bool = False):
    if pts:
        return round(cur - prev, 1)
    if prev <= 0:
        return None
    return round((cur - prev) / prev * 100, 1)


async def build_digest(db, pid: str) -> Dict:
    today = _now().date()
    start = today - timedelta(days=7)
    total_rooms = 0
    async for rt in db.room_types.find({"property_id": pid}, {"_id": 0, "total_rooms": 1}):
        total_rooms += int(rt.get("total_rooms", 0))
    cur = await _week_metrics(db, pid, start, total_rooms)
    prev = await _week_metrics(db, pid, start - timedelta(days=7), total_rooms)
    ladder = await compute_ladder_weekly(db, pid)

    # Rebase & Deney özeti (son 30 gün)
    rebase = None
    rep = await db.rebase_reports.find_one({"property_id": pid}, {"_id": 0, "rows": 0}, sort=[("created_at", -1)])
    if rep and rep.get("created_at", "") >= (today - timedelta(days=30)).isoformat():
        exp_line = None
        exp = await db.rebase_experiments.find_one({"property_id": pid}, {"_id": 0}, sort=[("started_at", -1)])
        if exp:
            from routes.revenue_ext.rebase_impact import compute_experiment_progress
            prog = await compute_experiment_progress(db, exp)
            exp_line = prog["verdict_tr"]
        rebase = {"date": rep["created_at"][:10],
                  "weighted_change_pct": rep.get("weighted_change_pct"),
                  "loss": rep.get("contribution", {}).get("loss"),
                  "breakeven_feasible": rep.get("breakeven", {}).get("feasible"),
                  "occ_needed_pct": rep.get("breakeven", {}).get("occ_needed_pct"),
                  "experiment_verdict": exp_line}
    abs_changes = await db.abs_price_log.count_documents(
        {"property_id": pid, "at": {"$gte": (today - timedelta(days=7)).isoformat()}})

    return {"week_start": start.isoformat(), "week_end": (today - timedelta(days=1)).isoformat(),
            **cur, "prev": prev,
            "deltas": {"revenue_pct": _delta(cur["revenue"], prev["revenue"]),
                       "occupancy_pts": _delta(cur["occupancy"], prev["occupancy"], pts=True),
                       "adr_pct": _delta(cur["adr"], prev["adr"]),
                       "arrivals_diff": cur["arrivals"] - prev["arrivals"]},
            "ladder": ladder, "rebase": rebase, "abs_price_changes_7d": abs_changes}


def _arrow(v, suffix="%"):
    if v is None:
        return "<span style='color:#a8a29e;font-size:11px'>geçen hafta verisi yok</span>"
    if v > 0:
        return f"<span style='color:#059669;font-size:12px;font-weight:700'>▲ +{v}{suffix}</span>"
    if v < 0:
        return f"<span style='color:#dc2626;font-size:12px;font-weight:700'>▼ {v}{suffix}</span>"
    return f"<span style='color:#a8a29e;font-size:12px'>= 0{suffix}</span>"


def _digest_html(prop_name: str, d: Dict) -> str:
    box = ("display:inline-block;width:31%;margin:1%;padding:14px 6px;background:#fafaf9;"
           "border-radius:12px;text-align:center;vertical-align:top")
    big = "font-size:22px;font-weight:800;color:#1c1917"
    small = "font-size:11px;color:#78716c"
    l = d["ladder"]
    dl = d.get("deltas", {})
    return (f"<div style='font-family:Arial,sans-serif;max-width:600px;margin:auto'>"
            f"<div style='background:#1c1917;color:#fff;border-radius:14px;padding:22px'>"
            f"<div style='font-size:11px;letter-spacing:2px;color:#d6d3d1'>HAFTALIK YÖNETİCİ BÜLTENİ</div>"
            f"<h2 style='margin:6px 0'>{prop_name}</h2>"
            f"<div style='font-size:12px;color:#a8a29e'>{d['week_start']} → {d['week_end']} · geçen haftayla kıyaslı</div></div>"
            f"<div style='padding:14px 0'>"
            f"<div style='{box}'><div style='{big}'>£{d['revenue']}</div><div style='{small}'>Oda geliri (7g)</div>{_arrow(dl.get('revenue_pct'))}</div>"
            f"<div style='{box}'><div style='{big}'>%{d['occupancy']}</div><div style='{small}'>Ortalama doluluk</div>{_arrow(dl.get('occupancy_pts'), ' puan')}</div>"
            f"<div style='{box}'><div style='{big}'>£{d['adr']}</div><div style='{small}'>ADR</div>{_arrow(dl.get('adr_pct'))}</div>"
            f"<div style='{box}'><div style='{big}'>{d['arrivals']}</div><div style='{small}'>Giriş</div>{_arrow(dl.get('arrivals_diff'), '')}</div>"
            f"<div style='{box}'><div style='{big}'>{d['cancellations']}</div><div style='{small}'>İptal</div></div>"
            f"<div style='{box}'><div style='{big}'>≈£{l['total_estimate']}</div><div style='{small}'>Merdiven katkısı</div></div>"
            f"</div>"
            f"<div style='background:#ecfdf5;border:1px solid #a7f3d0;border-radius:12px;padding:12px;font-size:13px'>"
            f"🪜 Son-gün merdiveni ≈£{l['lastday']['recovered_estimate']} kurtardı "
            f"({l['lastday']['sold_after_discount']} gece indirimle satıldı) · "
            f"📈 Zam merdiveni ≈£{l['ramp']['uplift_estimate']} ek gelir "
            f"({l['ramp']['guest_approved']} misafir-onaylı kademe)</div>"
            + _rebase_section_html(d) +
            f"<p style='color:#a8a29e;font-size:11px'>MyHotelBox — her pazartesi otomatik gönderilir.</p></div>")


def _rebase_section_html(d: Dict) -> str:
    r = d.get("rebase")
    parts = []
    if r:
        be = "✅ ulaşılabilir" if r.get("breakeven_feasible") else f"⛔ İMKÂNSIZ (%{r.get('occ_needed_pct')} doluluk gerekir)"
        loss = r.get("loss") or 0
        parts.append(
            f"🧪 <b>Rebase analizi ({r['date']})</b>: otel geneli %{r.get('weighted_change_pct')} · "
            f"90 günde katkı kaybı £{loss:,} · başabaş {be}")
        if r.get("experiment_verdict"):
            parts.append(f"🔬 <b>Deney:</b> {r['experiment_verdict']}")
    if d.get("abs_price_changes_7d"):
        parts.append(f"🤖 <b>ABS otomatik fiyat:</b> bu hafta {d['abs_price_changes_7d']} özellik fiyatı güncellendi.")
    if not parts:
        return ""
    inner = "".join(f"<div style='margin-bottom:6px'>{p}</div>" for p in parts)
    return (f"<div style='background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;"
            f"padding:12px;font-size:13px;margin-top:10px'>{inner}</div>")


async def send_digest(db, pid: str, forced: bool = False) -> Dict:
    week_key = _now().strftime("%G-W%V")
    if not forced:
        if await db.weekly_digests.find_one({"property_id": pid, "week_key": week_key}):
            return {"skipped": "already_sent_this_week"}
    digest = await build_digest(db, pid)
    prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
    admins = await db.users.find({"role": {"$in": ["admin", "manager"]},
                                  "is_active": {"$ne": False}},
                                 {"_id": 0, "email": 1}).to_list(20)
    html = _digest_html(prop.get("name", pid), digest)
    sent_to = []
    for a in admins:
        if a.get("email"):
            await send_email(db, a["email"],
                             f"📊 Haftalık Bülten — {prop.get('name', pid)} · {digest['week_start']}",
                             html, kind="weekly_digest", meta={"property_id": pid})
            sent_to.append(a["email"])
    doc = {"id": str(uuid.uuid4()), "property_id": pid, "week_key": week_key,
           "digest": digest, "sent_to": sent_to, "forced": forced,
           "created_at": _now().isoformat()}
    await db.weekly_digests.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def weekly_digest_loop(db, interval_seconds: int = 1800):
    await asyncio.sleep(360)
    while True:
        try:
            now = _now()
            if now.weekday() == 0 and now.hour >= 7:  # Pazartesi ≥ 10:00 TR
                for pid in await db.properties.distinct("id"):
                    r = await send_digest(db, pid)
                    if not r.get("skipped"):
                        logger.info("Haftalık bülten gönderildi: %s", pid)
        except Exception as ex:
            logger.warning("Weekly digest loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_weekly_digest_router(db, require_roles):
    router = APIRouter(prefix="/weekly-digest", tags=["weekly-digest"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}/latest")
    async def latest(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        doc = await db.weekly_digests.find_one({"property_id": pid}, {"_id": 0},
                                               sort=[("created_at", -1)])
        preview = await build_digest(db, pid)
        return {"latest": doc, "live_preview": preview,
                "schedule": "Her pazartesi ~10:00 (TR) otomatik gönderilir"}

    @router.get("/{pid}/history")
    async def history(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        docs = await db.weekly_digests.find({"property_id": pid}, {"_id": 0}).sort(
            "created_at", -1).to_list(20)
        return {"history": docs}

    @router.get("/{pid}/render/{digest_id}")
    async def render_digest(pid: str, digest_id: str, _u: dict = Depends(require_roles(*ROLES))):
        """Arşivdeki bülteni e-postadaki haliyle HTML olarak döndürür."""
        doc = await db.weekly_digests.find_one({"id": digest_id, "property_id": pid}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Bülten bulunamadı")
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        return {"html": _digest_html(prop.get("name", pid), doc["digest"]),
                "week_key": doc["week_key"], "created_at": doc["created_at"],
                "sent_to": doc.get("sent_to", [])}

    @router.post("/{pid}/send-now")
    async def send_now(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await send_digest(db, pid, forced=True)

    return router
