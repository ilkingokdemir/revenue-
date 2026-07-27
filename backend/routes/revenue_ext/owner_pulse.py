"""
Owner Pulse — Market Pulse tarzı sahip portalı analitik katmanı.
Owner JWT ile: Dashboard (aylık kartlar + YoY + pickup), Demand Radar,
Compset Intel ve Raporlar. Admin tarafı: modül görünürlük kontrolü + önizleme.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict
from collections import defaultdict
import calendar
import jwt
import logging

from routes.platform_ext.owner_self_service import _jwt_secret, JWT_ALGORITHM

logger = logging.getLogger(__name__)

MODULE_KEYS = ["dashboard", "demand_radar", "compset", "reports", "rates"]
MONTH_TR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def _parse_d(s):
    try:
        return datetime.strptime((s or "")[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _parse_created(s):
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


async def _total_rooms(db, pid: str) -> int:
    total = 0
    async for rt in db.room_types.find({"property_id": pid}, {"_id": 0, "total_rooms": 1}):
        total += int(rt.get("total_rooms", 0) or 0)
    if not total:
        total = await db.rooms.count_documents({"property_id": pid})
    return max(total, 1)


async def _fetch_bookings(db, pid: str):
    return await db.bookings.find(
        {"property_id": pid, "status": {"$ne": "cancelled"}},
        {"_id": 0, "check_in": 1, "check_out": 1, "nights": 1, "total_price": 1,
         "created_at": 1, "guest_name": 1, "channel": 1, "source": 1}
    ).to_list(20000)


def _month_stats(bookings, rooms: int, y: int, m: int) -> Dict:
    mdays = calendar.monthrange(y, m)[1]
    start = ddate(y, m, 1)
    end = ddate(y, m, mdays)
    rev, nights = 0.0, 0
    for b in bookings:
        ci, co = _parse_d(b.get("check_in")), _parse_d(b.get("check_out"))
        if not ci or not co or co <= ci:
            continue
        s = max(ci, start)
        e = min(co, end + timedelta(days=1))
        ov = max(0, (e - s).days)
        if ov == 0:
            continue
        total_n = max((co - ci).days, 1)
        rev += float(b.get("total_price") or 0) * ov / total_n
        nights += ov
    occ = round(nights * 100 / (rooms * mdays), 1)
    adr = round(rev / nights, 2) if nights else 0.0
    return {"revenue": round(rev, 2), "nights": nights, "occ": occ, "adr": adr}


async def build_owner_dashboard(db, pid: str) -> Dict:
    now = datetime.now(timezone.utc)
    today = now.date()
    rooms = await _total_rooms(db, pid)
    bookings = await _fetch_bookings(db, pid)
    prop = await db.properties.find_one({"id": pid}, {"_id": 0, "currency": 1, "name": 1}) or {}

    # ── Aylık kartlar: geçen ay / bu ay (MTD) / gelecek ay (OTB) + YoY ──
    cards = []
    for offset, label in [(-1, "Geçen Ay"), (0, "Bu Ay"), (1, "Gelecek Ay")]:
        y, m = today.year, today.month + offset
        if m < 1:
            y, m = y - 1, 12
        elif m > 12:
            y, m = y + 1, 1
        cur = _month_stats(bookings, rooms, y, m)
        ly = _month_stats(bookings, rooms, y - 1, m)
        yoy = round((cur["revenue"] - ly["revenue"]) * 100 / ly["revenue"], 1) if ly["revenue"] else None
        tag = "FINAL" if offset == -1 else ("MTD" if offset == 0 else "OTB")
        cards.append({"label": label, "tag": tag, "month": f"{MONTH_TR[m-1]} {y}",
                      **cur, "ly_revenue": ly["revenue"], "ly_occ": ly["occ"], "ly_adr": ly["adr"],
                      "yoy_pct": yoy})

    # ── 90 günlük doluluk + pickup serisi ──
    day_occ = defaultdict(int)
    horizon_end = today + timedelta(days=90)
    pickup_counts = {"24h": defaultdict(int), "7d": defaultdict(int)}
    for b in bookings:
        ci, co = _parse_d(b.get("check_in")), _parse_d(b.get("check_out"))
        if not ci or not co:
            continue
        created = _parse_created(b.get("created_at"))
        age_h = (now - created).total_seconds() / 3600 if created else 99999
        d = max(ci, today)
        while d < min(co, horizon_end):
            iso = d.isoformat()
            day_occ[iso] += 1
            if age_h <= 24:
                pickup_counts["24h"][iso] += 1
            if age_h <= 168:
                pickup_counts["7d"][iso] += 1
            d += timedelta(days=1)
    occ_series = []
    for i in range(90):
        iso = (today + timedelta(days=i)).isoformat()
        occ_series.append({"date": iso, "occ": min(100, round(day_occ[iso] * 100 / rooms)),
                           "pickup_24h": pickup_counts["24h"][iso], "pickup_7d": pickup_counts["7d"][iso]})

    # ── Son 7 gün rezervasyon akışı ──
    recent = []
    for i in range(7):
        d = today - timedelta(days=i)
        iso = d.isoformat()
        rows = [b for b in bookings if (b.get("created_at") or "")[:10] == iso]
        rn = sum(int(b.get("nights") or 1) for b in rows)
        rev = sum(float(b.get("total_price") or 0) for b in rows)
        recent.append({"date": iso, "dow": ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"][d.weekday()],
                       "bookings": len(rows), "room_nights": rn,
                       "adr": round(rev / rn, 2) if rn else 0, "revenue": round(rev, 2)})

    # ── Yıllık performans (12 ay YoY) ──
    cy, py = today.year, today.year - 1
    annual_rows, tot = [], {"p_rev": 0, "c_rev": 0, "p_n": 0, "c_n": 0}
    for m in range(1, 13):
        p = _month_stats(bookings, rooms, py, m)
        c = _month_stats(bookings, rooms, cy, m)
        delta_abs = round(c["revenue"] - p["revenue"], 2)
        delta_pct = round(delta_abs * 100 / p["revenue"], 1) if p["revenue"] else None
        annual_rows.append({"month": MONTH_TR[m - 1], "mtd": (m == today.month),
                            "p_occ": p["occ"], "p_adr": p["adr"], "p_rev": p["revenue"],
                            "c_occ": c["occ"], "c_adr": c["adr"], "c_rev": c["revenue"],
                            "delta_pct": delta_pct, "delta_abs": delta_abs})
        tot["p_rev"] += p["revenue"]; tot["c_rev"] += c["revenue"]
        tot["p_n"] += p["nights"]; tot["c_n"] += c["nights"]
    annual = {"prev_year": py, "cur_year": cy, "rows": annual_rows,
              "totals": {"p_rev": round(tot["p_rev"], 2), "c_rev": round(tot["c_rev"], 2),
                         "delta_pct": round((tot["c_rev"] - tot["p_rev"]) * 100 / tot["p_rev"], 1) if tot["p_rev"] else None}}

    return {"currency": prop.get("currency") or "GBP", "property_name": prop.get("name") or "",
            "rooms": rooms, "month_cards": cards, "occ_series": occ_series,
            "recent_bookings": recent, "annual": annual}


async def build_owner_report(db, pid: str, key: str) -> Dict:
    rooms = await _total_rooms(db, pid)
    bookings = await _fetch_bookings(db, pid)
    today = ddate.today()
    if key == "performance":
        day_occ = defaultdict(int)
        day_rev = defaultdict(float)
        start = today - timedelta(days=30)
        for b in bookings:
            ci, co = _parse_d(b.get("check_in")), _parse_d(b.get("check_out"))
            if not ci or not co or co <= ci:
                continue
            total_n = max((co - ci).days, 1)
            per_night = float(b.get("total_price") or 0) / total_n
            d = max(ci, start)
            while d < min(co, today + timedelta(days=1)):
                day_occ[d.isoformat()] += 1
                day_rev[d.isoformat()] += per_night
                d += timedelta(days=1)
        rows = []
        for i in range(30, -1, -1):
            iso = (today - timedelta(days=i)).isoformat()
            occ = min(100, round(day_occ[iso] * 100 / rooms))
            sold = day_occ[iso]
            rev = round(day_rev[iso], 2)
            adr = round(rev / sold, 2) if sold else 0
            rows.append({"date": iso, "occ": f"{occ}%", "adr": adr, "revpar": round(rev / rooms, 2), "revenue": rev})
        return {"title": "Performans Metrikleri (son 30 gün)",
                "columns": [{"key": "date", "label": "Tarih"}, {"key": "occ", "label": "Doluluk"},
                            {"key": "adr", "label": "ADR"}, {"key": "revpar", "label": "RevPAR"},
                            {"key": "revenue", "label": "Gelir"}], "rows": rows}
    if key == "yoy":
        dash = await build_owner_dashboard(db, pid)
        rows = [{"month": r["month"], "p_rev": r["p_rev"], "c_rev": r["c_rev"],
                 "p_occ": f'{r["p_occ"]}%', "c_occ": f'{r["c_occ"]}%',
                 "delta": f'{r["delta_pct"]:+}%' if r["delta_pct"] is not None else "—"}
                for r in dash["annual"]["rows"]]
        return {"title": f'Yıllık Karşılaştırma {dash["annual"]["prev_year"]} vs {dash["annual"]["cur_year"]}',
                "columns": [{"key": "month", "label": "Ay"}, {"key": "p_occ", "label": "Occ (önceki)"},
                            {"key": "p_rev", "label": "Gelir (önceki)"}, {"key": "c_occ", "label": "Occ (bu yıl)"},
                            {"key": "c_rev", "label": "Gelir (bu yıl)"}, {"key": "delta", "label": "Δ %"}], "rows": rows}
    if key == "bookings":
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        rows = [{"created": (b.get("created_at") or "")[:10], "guest": b.get("guest_name") or "—",
                 "check_in": b.get("check_in"), "nights": b.get("nights") or 1,
                 "channel": b.get("channel") or b.get("source") or "direct",
                 "total": float(b.get("total_price") or 0)}
                for b in bookings if (b.get("created_at") or "") >= cutoff]
        rows.sort(key=lambda r: r["created"], reverse=True)
        return {"title": "Rezervasyon Raporu (son 30 gün)",
                "columns": [{"key": "created", "label": "Oluşturma"}, {"key": "guest", "label": "Misafir"},
                            {"key": "check_in", "label": "Giriş"}, {"key": "nights", "label": "Gece"},
                            {"key": "channel", "label": "Kanal"}, {"key": "total", "label": "Tutar"}],
                "rows": rows[:200]}
    if key == "source":
        agg = defaultdict(lambda: {"count": 0, "nights": 0, "revenue": 0.0})
        for b in bookings:
            ch = (b.get("channel") or b.get("source") or "direct").split(":")[0]
            agg[ch]["count"] += 1
            agg[ch]["nights"] += int(b.get("nights") or 1)
            agg[ch]["revenue"] += float(b.get("total_price") or 0)
        total_rev = sum(v["revenue"] for v in agg.values()) or 1
        rows = [{"channel": k, "bookings": v["count"], "nights": v["nights"],
                 "revenue": round(v["revenue"], 2), "share": f'{round(v["revenue"]*100/total_rev,1)}%'}
                for k, v in sorted(agg.items(), key=lambda x: -x[1]["revenue"])]
        return {"title": "Kaynak / Kanal Raporu",
                "columns": [{"key": "channel", "label": "Kanal"}, {"key": "bookings", "label": "Rezervasyon"},
                            {"key": "nights", "label": "Gece"}, {"key": "revenue", "label": "Gelir"},
                            {"key": "share", "label": "Pay"}], "rows": rows}
    if key == "financial":
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        rows = []
        pays = await db.payments.find(
            {"property_id": pid, "created_at": {"$gte": cutoff}}, {"_id": 0}).to_list(500)
        for p in pays:
            rows.append({"date": (p.get("created_at") or "")[:10], "type": "Ödeme",
                         "method": p.get("method") or "—", "ref": p.get("booking_id") or "—",
                         "amount": round(float(p.get("amount") or 0), 2)})
        for b in bookings:
            if (b.get("created_at") or "") >= cutoff:
                rows.append({"date": (b.get("created_at") or "")[:10], "type": "Rezervasyon Geliri",
                             "method": (b.get("channel") or b.get("source") or "direct").split(":")[0],
                             "ref": b.get("guest_name") or "—",
                             "amount": round(float(b.get("total_price") or 0), 2)})
        rows.sort(key=lambda r: r["date"], reverse=True)
        return {"title": "Finansal İşlemler (son 30 gün)",
                "columns": [{"key": "date", "label": "Tarih"}, {"key": "type", "label": "Tür"},
                            {"key": "method", "label": "Yöntem/Kanal"}, {"key": "ref", "label": "Referans"},
                            {"key": "amount", "label": "Tutar"}], "rows": rows[:200]}
    if key == "takings":
        cy = today.year
        rows = []
        for m in range(1, 13):
            accrual = _month_stats(bookings, rooms, cy, m)["revenue"]
            cash = round(sum(float(b.get("total_price") or 0) for b in bookings
                             if (b.get("created_at") or "")[:7] == f"{cy}-{m:02d}"), 2)
            diff = round(cash - accrual, 2)
            rows.append({"month": f"{MONTH_TR[m-1]} {cy}", "cash": cash, "accrual": accrual,
                         "diff": f"{'+' if diff >= 0 else ''}{diff}"})
        return {"title": f"Aylık Tahsilat — Cash vs Accrual ({cy})",
                "columns": [{"key": "month", "label": "Ay"},
                            {"key": "cash", "label": "Cash (tahsilat, oluşturma bazlı)"},
                            {"key": "accrual", "label": "Accrual (hakediş, konaklama bazlı)"},
                            {"key": "diff", "label": "Fark"}], "rows": rows}
    raise HTTPException(404, "Bilinmeyen rapor")


def create_owner_pulse_router(db, require_roles, demand_radar_router, compset_router):
    router = APIRouter(prefix="/owner-pulse")

    async def get_current_owner(request: Request) -> dict:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(401, "Owner token gerekli")
        try:
            payload = jwt.decode(auth[7:], _jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "owner_access":
                raise HTTPException(401, "Geçersiz token kapsamı")
            owner = await db.unit_owners.find_one({"id": payload["sub"]}, {"_id": 0})
            if not owner:
                raise HTTPException(401, "Sahip bulunamadı")
            return owner
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Oturum süresi doldu")
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Geçersiz token")

    def _pid(owner: dict) -> str:
        return owner.get("property_id") or "default"

    async def _modules(pid: str) -> Dict:
        cfg = await db.owner_pulse_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        mods = cfg.get("modules") or {}
        return {k: bool(mods.get(k, True)) for k in MODULE_KEYS}

    async def _check(pid: str, key: str):
        mods = await _modules(pid)
        if not mods.get(key, True):
            raise HTTPException(403, "Bu modül yönetici tarafından kapatıldı")

    # ── Owner portal endpoints ──
    @router.get("/portal/config")
    async def portal_config(owner: dict = Depends(get_current_owner)):
        return {"modules": await _modules(_pid(owner))}

    @router.get("/portal/dashboard")
    async def portal_dashboard(owner: dict = Depends(get_current_owner)):
        await _check(_pid(owner), "dashboard")
        return await build_owner_dashboard(db, _pid(owner))

    @router.get("/portal/demand-radar")
    async def portal_radar(owner: dict = Depends(get_current_owner)):
        await _check(_pid(owner), "demand_radar")
        return await demand_radar_router.build(property_id=_pid(owner), days=90, current_user=owner)

    @router.get("/portal/booking-behavior")
    async def portal_behavior(owner: dict = Depends(get_current_owner)):
        await _check(_pid(owner), "demand_radar")
        return await demand_radar_router.build_behavior(property_id=_pid(owner), current_user=owner)

    @router.get("/portal/compset")
    async def portal_compset(owner: dict = Depends(get_current_owner)):
        await _check(_pid(owner), "compset")
        return await compset_router.build(property_id=_pid(owner), days=30, current_user=owner)

    @router.get("/portal/portfolio")
    async def portal_portfolio(owner: dict = Depends(get_current_owner)):
        """Portföy Rekabet Özeti — sahibin tüm tesisleri için occ/ADR/RevPAR vs segment."""
        await _check(_pid(owner), "compset")
        pids = owner.get("property_ids") or [_pid(owner)]
        items = []
        for pid in pids[:10]:
            prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1, "currency": 1}) or {}
            try:
                cs = await compset_router.build(property_id=pid, days=30, current_user=owner)
            except Exception:
                continue
            k = cs.get("kpis", {})
            items.append({"property_id": pid, "name": prop.get("name") or pid,
                          "currency": prop.get("currency") or "GBP",
                          "occ": k.get("my_occupancy"), "comp_occ": k.get("comp_occupancy"),
                          "adr": k.get("my_adr"), "comp_adr": k.get("comp_adr"),
                          "revpar": k.get("my_revpar"), "comp_revpar": k.get("comp_revpar"),
                          "occ_rank": k.get("occ_rank"), "segment_size": k.get("segment_size")})
        return {"count": len(items), "items": items}

    @router.get("/portal/reports/{key}")
    async def portal_report(key: str, owner: dict = Depends(get_current_owner)):
        await _check(_pid(owner), "reports")
        return await build_owner_report(db, _pid(owner), key)

    # ── Admin endpoints ──
    @router.get("/{pid}/config")
    async def admin_get_config(pid: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        return {"property_id": pid, "modules": await _modules(pid)}

    @router.put("/{pid}/config")
    async def admin_set_config(pid: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        mods = {k: bool((data.get("modules") or {}).get(k, True)) for k in MODULE_KEYS}
        await db.owner_pulse_config.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "modules": mods,
                      "updated_at": datetime.now(timezone.utc).isoformat(),
                      "updated_by": current_user.get("email", "")}},
            upsert=True)
        return {"ok": True, "modules": mods}

    @router.get("/{pid}/dashboard")
    async def admin_preview_dashboard(pid: str,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        return await build_owner_dashboard(db, pid)

    return router
