"""Yönetici Haftalık Özeti — GOPPAR ligi + RMS uplift'i sahiplere tek sayfalık e-postayla gönderir."""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict
from fastapi import APIRouter, Depends

from routes.platform_ext.mailer import send_email
from routes.revenue_ext.profit_benchmark import compute_league
from routes.revenue_ext.rms_uplift import compute_uplift


def _now():
    return datetime.now(timezone.utc)


async def build_owner_summary(db) -> Dict:
    league = await compute_league(db, months=1)
    uplifts = []
    for p in league["properties"][:6]:
        try:
            u = await compute_uplift(db, p["property_id"], months=6)
            uplifts.append({"property_id": p["property_id"], "name": p["name"],
                            "total_uplift_gbp": u["total_uplift_gbp"],
                            "uplift_pct": u["uplift_pct"], "verdict": u["verdict"]})
        except Exception:
            pass
    return {"week_key": _now().strftime("%G-W%V"), "league": league, "uplifts": uplifts,
            "generated_at": _now().isoformat()}


def _html(s: Dict) -> str:
    lg = s["league"]
    rows = "".join(
        f"<tr><td style='padding:6px 10px'>{p['rank']}</td>"
        f"<td style='padding:6px 10px;font-weight:bold'>{p['name']}</td>"
        f"<td style='padding:6px 10px;color:{'#059669' if p['goppar'] >= lg['portfolio_goppar'] else '#e11d48'};font-weight:bold'>£{p['goppar']}</td>"
        f"<td style='padding:6px 10px'>£{p['revpar']}</td>"
        f"<td style='padding:6px 10px'>%{p['occ_pct']}</td>"
        f"<td style='padding:6px 10px;font-size:11px;color:#57534e'>{p['insight']}</td></tr>"
        for p in lg["properties"])
    ups = "".join(
        f"<li style='margin:4px 0'><b>{u['name']}</b>: "
        f"{'+' if (u['total_uplift_gbp'] or 0) >= 0 else ''}£{u['total_uplift_gbp']:,.0f} "
        f"({('%+.1f' % u['uplift_pct']) + '%' if u['uplift_pct'] is not None else '—'} RevPAR etkisi)</li>"
        for u in s["uplifts"])
    return f"""
<div style="font-family:Arial,sans-serif;max-width:640px;margin:auto">
  <h2 style="color:#1a3c5e">🏆 Haftalık Yönetici Özeti — {s['week_key']}</h2>
  <h3>GOPPAR Ligi (son 30 gün) — portföy ortalaması £{lg['portfolio_goppar']}</h3>
  <table style="border-collapse:collapse;width:100%;font-size:13px;border:1px solid #e7e5e4">
    <tr style="background:#f5f5f4;text-align:left">
      <th style="padding:6px 10px">#</th><th style="padding:6px 10px">Otel</th>
      <th style="padding:6px 10px">GOPPAR</th><th style="padding:6px 10px">RevPAR</th>
      <th style="padding:6px 10px">Doluluk</th><th style="padding:6px 10px">İçgörü</th></tr>
    {rows}
  </table>
  <h3 style="margin-top:18px">⚡ RMS Motor Etkisi (son 6 ay)</h3>
  <ul style="font-size:13px">{ups or '<li>Uplift verisi henüz yetersiz</li>'}</ul>
  <p style="font-size:11px;color:#a8a29e">MyHotelBox & ReveniQ — otomatik haftalık özet.
  GOPPAR = brüt işletme kârı / müsait oda-gece.</p>
</div>"""


async def send_owner_summary(db, forced: bool = False) -> Dict:
    week_key = _now().strftime("%G-W%V")
    if not forced and await db.owner_weekly_sends.find_one({"week_key": week_key}):
        return {"skipped": "already_sent_this_week"}
    s = await build_owner_summary(db)
    html = _html(s)
    admins = await db.users.find(
        {"role": {"$in": ["admin", "manager"]}, "is_active": {"$ne": False}},
        {"_id": 0, "email": 1}).to_list(20)
    sent_to = []
    for a in admins:
        if a.get("email"):
            await send_email(db, a["email"],
                             f"🏆 Haftalık Yönetici Özeti — GOPPAR Ligi & RMS Etkisi · {week_key}",
                             html, kind="owner_weekly", meta={})
            sent_to.append(a["email"])
    doc = {"id": str(uuid.uuid4()), "week_key": week_key, "sent_to": sent_to,
           "forced": forced, "summary": {"portfolio_goppar": s["league"]["portfolio_goppar"],
                                         "properties": len(s["league"]["properties"])},
           "created_at": _now().isoformat()}
    await db.owner_weekly_sends.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def owner_weekly_loop(db, interval_seconds: int = 3600):
    while True:
        try:
            if _now().weekday() == 0 and _now().hour >= 7:  # Pazartesi sabahı
                await send_owner_summary(db)
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)


def create_owner_weekly_router(db, require_roles):
    router = APIRouter(prefix="/owner-weekly", tags=["owner-weekly"])
    ROLES = ("admin", "manager")

    @router.get("/preview")
    async def preview(_u: dict = Depends(require_roles(*ROLES))):
        s = await build_owner_summary(db)
        return {**s, "html": _html(s)}

    @router.post("/send-now")
    async def send_now(_u: dict = Depends(require_roles("admin"))):
        return await send_owner_summary(db, forced=True)

    @router.get("/history")
    async def history(_u: dict = Depends(require_roles(*ROLES))):
        rows = await db.owner_weekly_sends.find({}, {"_id": 0}).sort(
            "created_at", -1).to_list(20)
        return {"sends": rows}

    return router
