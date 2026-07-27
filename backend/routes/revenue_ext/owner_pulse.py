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

try:
    import resend
except Exception:
    resend = None

import os
import asyncio
import uuid

logger = logging.getLogger(__name__)


async def _send_email(to_email: str, subject: str, html: str) -> str:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend or not api_key or api_key.startswith("re_1234"):
        logger.info(f"[MOCK EMAIL] Pulse digest to {to_email}: {subject}")
        return "mock"
    try:
        resend.api_key = api_key
        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM", "MyHotelBox <onboarding@resend.dev>"),
            "to": [to_email], "subject": subject, "html": html,
        })
        return "sent"
    except Exception as e:
        logger.warning(f"Pulse digest email failed: {e}")
        return "failed"

MODULE_KEYS = ["dashboard", "demand_radar", "compset", "reports", "rates", "portfolio"]
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
    # ── Kendi otelin pace'i: OTB snapshot (≥7 gün önce) vs bugünkü durum ──
    snap_cut = (today - timedelta(days=7)).isoformat()
    old_scan = await db.otb_daily_snapshots.find_one(
        {"property_id": pid, "scan_date": {"$lte": snap_cut}},
        {"_id": 0, "scan_date": 1}, sort=[("scan_date", -1)])
    old_booked = {}
    pace_source = "bookings"
    if old_scan:
        pace_source = "snapshot"
        async for s in db.otb_daily_snapshots.find(
                {"property_id": pid, "scan_date": old_scan["scan_date"]},
                {"_id": 0, "date": 1, "rooms_booked": 1}):
            old_booked[s["date"]] = s["rooms_booked"]
    occ_series = []
    for i in range(90):
        iso = (today + timedelta(days=i)).isoformat()
        pace = (day_occ[iso] - old_booked.get(iso, 0)) if pace_source == "snapshot" else pickup_counts["7d"][iso]
        occ_series.append({"date": iso, "occ": min(100, round(day_occ[iso] * 100 / rooms)),
                           "pickup_24h": pickup_counts["24h"][iso], "pickup_7d": pickup_counts["7d"][iso],
                           "pace": pace})

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
            "rooms": rooms, "pace_source": pace_source, "month_cards": cards, "occ_series": occ_series,
            "recent_bookings": recent, "annual": annual}


async def build_portfolio_overview(db, pids) -> Dict:
    """Portföy panosu — birleşik aylık kartlar + doluluk ısı haritası + tesis bazlı YoY tabloları."""
    today = ddate.today()
    now = datetime.now(timezone.utc)
    cy, py = today.year, today.year - 1
    heat_days = [(today + timedelta(days=i)).isoformat() for i in range(30)]
    dow_tr = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

    windows = []
    for offset, label in [(-1, "Geçen Ay"), (0, "Bu Ay"), (1, "Gelecek Ay")]:
        y, m = today.year, today.month + offset
        if m < 1:
            y, m = y - 1, 12
        elif m > 12:
            y, m = y + 1, 1
        tag = "FINAL" if offset == -1 else ("MTD" if offset == 0 else "OTB")
        windows.append({"label": label, "tag": tag, "y": y, "m": m,
                        "rev": 0.0, "nights": 0, "cap": 0,
                        "ly_rev": 0.0, "ly_nights": 0, "ly_cap": 0})

    props_out, heat_rows, currencies = [], [], []
    for pid in pids:
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1, "currency": 1}) or {}
        cur = prop.get("currency") or "GBP"
        currencies.append(cur)
        rooms = await _total_rooms(db, pid)
        bookings = await _fetch_bookings(db, pid)

        # birleşik aylık kartlar
        for w in windows:
            s = _month_stats(bookings, rooms, w["y"], w["m"])
            ls = _month_stats(bookings, rooms, w["y"] - 1, w["m"])
            mdays = calendar.monthrange(w["y"], w["m"])[1]
            w["rev"] += s["revenue"]; w["nights"] += s["nights"]; w["cap"] += rooms * mdays
            w["ly_rev"] += ls["revenue"]; w["ly_nights"] += ls["nights"]; w["ly_cap"] += rooms * mdays

        # ısı haritası (30 gün) + pace + adr + müsait oda
        day_occ = defaultdict(int)
        day_rev = defaultdict(float)
        pickup7 = defaultdict(int)
        h_end = today + timedelta(days=30)
        for b in bookings:
            ci, co = _parse_d(b.get("check_in")), _parse_d(b.get("check_out"))
            if not ci or not co:
                continue
            created = _parse_created(b.get("created_at"))
            fresh = created and (now - created).total_seconds() <= 7 * 86400
            per_night = float(b.get("total_price") or 0) / max((co - ci).days, 1)
            d = max(ci, today)
            while d < min(co, h_end):
                iso = d.isoformat()
                day_occ[iso] += 1
                day_rev[iso] += per_night
                if fresh:
                    pickup7[iso] += 1
                d += timedelta(days=1)
        cells = []
        for x in heat_days:
            booked = day_occ[x]
            cells.append({"occ": min(100, round(booked * 100 / rooms)), "pace": pickup7[x],
                          "adr": round(day_rev[x] / booked) if booked else 0,
                          "avail": max(0, rooms - booked)})
        avg_occ = round(sum(c["occ"] for c in cells) / len(cells), 1)
        heat_rows.append({"property_id": pid, "name": prop.get("name") or pid, "rooms": rooms,
                          "avg_occ": avg_occ, "risk": avg_occ < 35, "cells": cells})

        # tesis bazlı 12 ay YoY
        months = []
        for m in range(1, 13):
            p = _month_stats(bookings, rooms, py, m)
            c = _month_stats(bookings, rooms, cy, m)
            var = round((c["revenue"] - p["revenue"]) * 100 / p["revenue"], 1) if p["revenue"] else None
            months.append({"month": MONTH_TR[m - 1], "mtd": (m == today.month),
                           "p_occ": p["occ"], "p_adr": p["adr"], "p_rev": p["revenue"],
                           "c_occ": c["occ"], "c_adr": c["adr"], "c_rev": c["revenue"], "var_pct": var})
        props_out.append({"property_id": pid, "name": prop.get("name") or pid,
                          "currency": cur, "rooms": rooms, "months": months})

    heat_rows.sort(key=lambda r: r["avg_occ"])  # risk önce
    cards = []
    for w in windows:
        occ = round(w["nights"] * 100 / w["cap"], 1) if w["cap"] else 0
        ly_occ = round(w["ly_nights"] * 100 / w["ly_cap"], 1) if w["ly_cap"] else 0
        adr = round(w["rev"] / w["nights"], 2) if w["nights"] else 0
        ly_adr = round(w["ly_rev"] / w["ly_nights"], 2) if w["ly_nights"] else 0
        yoy = round((w["rev"] - w["ly_rev"]) * 100 / w["ly_rev"], 1) if w["ly_rev"] else None
        cards.append({"label": w["label"], "tag": w["tag"], "month": f"{MONTH_TR[w['m']-1]} {w['y']}",
                      "revenue": round(w["rev"], 2), "occ": occ, "adr": adr,
                      "ly_revenue": round(w["ly_rev"], 2), "ly_occ": ly_occ, "ly_adr": ly_adr,
                      "yoy_pct": yoy})
    uniq = list(dict.fromkeys(currencies))
    return {"currency": uniq[0] if len(uniq) == 1 else "MIX",
            "currency_mixed": len(uniq) > 1, "prev_year": py, "cur_year": cy,
            "month_cards": cards,
            "heatmap": {"days": [{"date": x, "dow": dow_tr[ddate.fromisoformat(x).weekday()]} for x in heat_days],
                        "rows": heat_rows},
            "properties": props_out}


async def build_recovery_plan(db, pid: str) -> Dict:
    """Riskli tesis için kural tabanlı kurtarma planı — zayıf tarihler + fiyat/promosyon aksiyonları."""
    today = ddate.today()
    rooms = await _total_rooms(db, pid)
    bookings = await _fetch_bookings(db, pid)
    prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1, "currency": 1}) or {}
    day_occ = defaultdict(int)
    day_rev = defaultdict(float)
    h_end = today + timedelta(days=30)
    for b in bookings:
        ci, co = _parse_d(b.get("check_in")), _parse_d(b.get("check_out"))
        if not ci or not co:
            continue
        per_night = float(b.get("total_price") or 0) / max((co - ci).days, 1)
        d = max(ci, today)
        while d < min(co, h_end):
            day_occ[d.isoformat()] += 1
            day_rev[d.isoformat()] += per_night
            d += timedelta(days=1)
    days = [(today + timedelta(days=i)).isoformat() for i in range(30)]
    occ_of = {x: min(100, round(day_occ[x] * 100 / rooms)) for x in days}
    weak = [x for x in days if occ_of[x] < 35]
    weak_lastmin = [x for x in weak if (ddate.fromisoformat(x) - today).days <= 7]
    weak_weekend = [x for x in weak if ddate.fromisoformat(x).weekday() >= 4]
    avg_occ = round(sum(occ_of.values()) / 30, 1)
    sold = sum(day_occ.values())
    my_adr = round(sum(day_rev.values()) / sold, 2) if sold else 0

    wap_vals = []
    async for s in db.market_supply.find({"property_id": pid, "date": {"$gte": days[0], "$lte": days[-1]}},
                                         {"_id": 0, "avg_price": 1}).sort("scanned_at", -1).limit(500):
        if s.get("avg_price"):
            wap_vals.append(float(s["avg_price"]))
    market_wap = round(sum(wap_vals) / len(wap_vals), 2) if wap_vals else None
    events = await db.market_events.find(
        {"property_id": pid, "date": {"$gte": days[0], "$lte": days[-1]}},
        {"_id": 0, "date": 1, "name": 1}).to_list(20)
    weak_events = [e for e in events if e.get("date") in set(weak)]

    floors = await db.min_rate_floors.find(
        {"property_id": pid, "date": {"$gte": days[0], "$lte": days[-1]}},
        {"_id": 0, "floor_rate": 1}).to_list(100)
    avg_floor = round(sum(float(f.get("floor_rate") or 0) for f in floors) / len(floors), 2) if floors else None

    actions = []
    if weak:
        if market_wap and my_adr and my_adr > market_wap:
            target = round(max(avg_floor or 0, market_wap * 0.95), 2)
            actions.append({"type": "price", "title": "Kurtarma fiyatı uygula",
                            "desc": f"ADR'niz ({my_adr}) pazar ortalamasının ({market_wap}) üzerinde. {len(weak)} zayıf tarihte fiyatı ~{target} seviyesine çekin (taban korunur).",
                            "impact": "yüksek"})
        elif my_adr:
            target = round(max(avg_floor or 0, my_adr * 0.88), 2)
            actions.append({"type": "price", "title": "Zayıf tarihlerde %12 indirim",
                            "desc": f"{len(weak)} zayıf tarihte fiyatı ~{target} seviyesine indirin (mevcut ADR {my_adr}, taban {avg_floor or '—'}).",
                            "impact": "yüksek"})
        else:
            actions.append({"type": "price", "title": "Agresif açılış fiyatı",
                            "desc": f"30 günde satış yok denecek kadar az. Pazar ortalamasının %15 altında görünürlük fiyatı açın{f' (~{round(market_wap*0.85,2)})' if market_wap else ''}.",
                            "impact": "yüksek"})
    if weak_lastmin:
        actions.append({"type": "promo", "title": "Son dakika flash promosyonu",
                        "desc": f"Önümüzdeki 7 günde {len(weak_lastmin)} zayıf tarih var. %15 son-dakika indirimi + mobil kupon açın (indirim katmanı üzerinden).",
                        "impact": "yüksek"})
    if weak_weekend:
        actions.append({"type": "restriction", "title": "Min. konaklama kısıtını kaldır",
                        "desc": f"{len(weak_weekend)} zayıf hafta sonu günü var — MLOS kısıtlarını kaldırıp 1 gecelik satışa açın.",
                        "impact": "orta"})
    if weak_events:
        ev_names = ", ".join(sorted({e['name'] for e in weak_events})[:3])
        actions.append({"type": "event", "title": "Etkinlik paketi oluştur",
                        "desc": f"Zayıf tarihlere denk gelen etkinlikler: {ev_names}. Etkinlik temalı paket + OTA görünürlük kampanyası önerilir.",
                        "impact": "orta"})
    actions.append({"type": "crm", "title": "Rebook kuponu gönder",
                    "desc": "Geçmiş misafirlere zayıf tarihler için %10-15 dönüş kuponu tarat (Rebook A/B modülü hazır).",
                    "impact": "orta"})
    return {"property_id": pid, "property_name": prop.get("name") or pid,
            "currency": prop.get("currency") or "GBP", "rooms": rooms,
            "avg_occ_30d": avg_occ, "my_adr": my_adr, "market_wap": market_wap,
            "avg_floor": avg_floor, "weak_days": len(weak), "weak_dates": weak[:14],
            "weak_dates_all": weak, "actions": actions}


async def apply_recovery_action(db, pid: str, action_type: str, applied_by: str) -> Dict:
    """Kurtarma planı aksiyonunu tek tıkla uygular ve loglar."""
    from routes.revenue_ext.owner_rates import set_manual_rate
    plan = await build_recovery_plan(db, pid)
    weak = plan["weak_dates_all"]
    now_iso = datetime.now(timezone.utc).isoformat()

    if action_type == "price":
        if not weak:
            raise HTTPException(400, "Zayıf tarih yok — fiyat aksiyonu gereksiz")
        wap, adr, floor = plan["market_wap"], plan["my_adr"], plan["avg_floor"] or 0
        if wap and adr and adr > wap:
            target = round(max(floor, wap * 0.95), 2)
        elif adr:
            target = round(max(floor, adr * 0.88), 2)
        elif wap:
            target = round(max(floor, wap * 0.85), 2)
        else:
            raise HTTPException(400, "Referans fiyat bulunamadı")
        applied = 0
        for d in weak:
            try:
                await set_manual_rate(db, pid, {"date": d, "rate": target, "mode": "gross"},
                                      applied_by, "recovery-plan")
                applied += 1
            except HTTPException:
                continue
        detail = f"{applied} zayıf tarihe ~{target} kurtarma fiyatı yazıldı (taban korumalı, iki yönlü panoda görünür)"
    elif action_type == "promo":
        exists = await db.discount_layers.find_one(
            {"property_id": pid, "source": "recovery_plan", "active": True}, {"_id": 0, "id": 1})
        if exists:
            detail = "Kurtarma promosyonu zaten aktif — mevcut katman korunuyor"
        else:
            count = await db.discount_layers.count_documents({"property_id": pid})
            await db.discount_layers.insert_one({
                "id": str(uuid.uuid4())[:8], "property_id": pid,
                "name": "Kurtarma: Son dakika %15", "pct": 15.0, "active": True,
                "order": count, "source": "recovery_plan",
                "created_at": now_iso, "created_by_owner": applied_by})
            detail = "%15 son-dakika indirim katmanı açıldı — nihai satış fiyatına anında yansır"
    elif action_type in ("restriction", "event", "crm"):
        titles = {"restriction": "MLOS kısıtlarını kaldır (zayıf hafta sonları)",
                  "event": "Etkinlik paketi + OTA kampanyası hazırla",
                  "crm": "Rebook kupon taraması başlat (A/B modülü)"}
        await db.recovery_tasks.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "action_type": action_type,
            "title": titles[action_type], "status": "open",
            "weak_dates": weak[:14], "created_by": applied_by, "created_at": now_iso})
        detail = f"Operasyon görevi oluşturuldu: {titles[action_type]}"
    else:
        raise HTTPException(400, "Bilinmeyen aksiyon tipi")

    await db.recovery_actions.insert_one({
        "id": str(uuid.uuid4()), "property_id": pid, "action_type": action_type,
        "detail": detail, "applied_by": applied_by, "applied_at": now_iso})
    return {"ok": True, "action_type": action_type, "detail": detail}


async def build_owner_report(db, pid: str, key: str, radar_build=None, compset_build=None, owner=None) -> Dict:
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
    if key == "events" and radar_build:
        radar = await radar_build(property_id=pid, days=90, current_user=owner or {})
        # kendi otelin o tarihteki doluluğu
        day_occ = defaultdict(int)
        for b in bookings:
            ci, co = _parse_d(b.get("check_in")), _parse_d(b.get("check_out"))
            if not ci or not co:
                continue
            d = max(ci, today)
            while d < min(co, today + timedelta(days=90)):
                day_occ[d.isoformat()] += 1
                d += timedelta(days=1)
        rows = []
        for r in radar.get("daily", []):
            if not r.get("event"):
                continue
            dem = r.get("demand")
            my_occ = min(100, round(day_occ[r["date"]] * 100 / rooms))
            if dem is not None and dem >= 70 and my_occ < 60:
                action = "Fiyat artışı fırsatı — talep yüksek, dolulukta yer var"
            elif dem is not None and dem >= 70:
                action = "Yield koru — kalan odaları yüksek fiyatla sat"
            elif my_occ < 30:
                action = "Promosyon düşün — etkinliğe rağmen dolum zayıf"
            else:
                action = "İzle"
            rows.append({"date": r["date"], "event": r["event"],
                         "demand": f"{dem}%" if dem is not None else "—",
                         "wap": r.get("wap") or "—", "my_occ": f"{my_occ}%", "action": action})
        return {"title": "Etkinlik Etkisi (90 gün)",
                "columns": [{"key": "date", "label": "Tarih"}, {"key": "event", "label": "Etkinlik"},
                            {"key": "demand", "label": "Pazar Talebi"}, {"key": "wap", "label": "Pazar Fiyatı"},
                            {"key": "my_occ", "label": "Benim Doluluğum"}, {"key": "action", "label": "Önerilen Aksiyon"}],
                "rows": rows}
    if key == "positioning" and compset_build:
        cs = await compset_build(property_id=pid, days=30, current_user=owner or {})
        k = cs.get("kpis", {})
        rows = []
        for r in cs.get("daily", []):
            occ_d = round(r["my_occ"] - r["comp_occ"], 1)
            adr_d = round(r["my_adr"] - r["comp_adr"], 1)
            if occ_d >= 0 and adr_d >= 0:
                pos = "Lider — hem dolulukta hem fiyatta önde"
            elif occ_d >= 0:
                pos = "Hacim önde, fiyat geride"
            elif adr_d >= 0:
                pos = "Fiyat önde, hacim geride"
            else:
                pos = "Geride — aksiyon gerekli"
            rows.append({"date": r["date"], "my_occ": f'{r["my_occ"]}%', "comp_occ": f'{r["comp_occ"]}%',
                         "occ_delta": f"{'+' if occ_d >= 0 else ''}{occ_d}pp",
                         "my_adr": round(r["my_adr"]), "comp_adr": round(r["comp_adr"]),
                         "adr_delta": f"{'+' if adr_d >= 0 else ''}{adr_d}", "position": pos})
        return {"title": f'Rekabetçi Konumlanma — Occ #{k.get("occ_rank")}, ADR #{k.get("adr_rank")}, RevPAR #{k.get("revpar_rank")} / {k.get("segment_size")} otel',
                "columns": [{"key": "date", "label": "Tarih"}, {"key": "my_occ", "label": "Benim Occ"},
                            {"key": "comp_occ", "label": "Segment Occ"}, {"key": "occ_delta", "label": "Δ Occ"},
                            {"key": "my_adr", "label": "Benim ADR"}, {"key": "comp_adr", "label": "Segment ADR"},
                            {"key": "adr_delta", "label": "Δ ADR"}, {"key": "position", "label": "Konum"}],
                "rows": rows}
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

    async def _digest_enabled(pid: str) -> bool:
        cfg = await db.owner_pulse_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        return bool(cfg.get("digest_enabled", False))

    # ── Haftalık Pulse Özeti (digest) ──
    def _sym(cur: str) -> str:
        return {"GBP": "£", "EUR": "€", "TRY": "₺", "USD": "$"}.get(cur, (cur or "") + " ")

    async def _build_digest_html(owner: dict) -> str:
        pid = _pid(owner)
        dash = await build_owner_dashboard(db, pid)
        c = _sym(dash["currency"])
        try:
            radar = await demand_radar_router.build(property_id=pid, days=90, current_user=owner)
            insights = (radar.get("insights") or [])[:3]
        except Exception:
            insights = []
        cards_html = ""
        for m in dash["month_cards"]:
            yoy = ""
            if m.get("yoy_pct") is not None:
                col = "#059669" if m["yoy_pct"] >= 0 else "#e11d48"
                yoy = f'<span style="color:{col};font-size:11px;font-weight:bold;">YoY {"+" if m["yoy_pct"]>=0 else ""}{m["yoy_pct"]}%</span>'
            cards_html += f"""
            <td style="width:33%;padding:6px;">
              <div style="border:1px solid #e7e5e4;border-radius:10px;padding:12px;">
                <div style="font-size:10px;color:#78716c;text-transform:uppercase;">{m['label']} · {m['tag']} {yoy}</div>
                <div style="font-size:22px;font-weight:bold;color:#1c1917;margin-top:4px;">{c}{m['revenue']:,.0f}</div>
                <div style="font-size:11px;color:#78716c;">Doluluk {m['occ']}% · ADR {c}{m['adr']:.0f}</div>
              </div>
            </td>"""
        ins_html = "".join(
            f'<li style="margin-bottom:6px;"><b>{i.get("title","")}</b><br/><span style="color:#78716c;font-size:12px;">{i.get("desc","")}</span></li>'
            for i in insights) or '<li style="color:#78716c;">Bu hafta öne çıkan içgörü yok.</li>'
        pf_html = ""
        pids = owner.get("property_ids") or []
        if len(pids) > 1:
            rows = ""
            for p in pids[:10]:
                prop = await db.properties.find_one({"id": p}, {"_id": 0, "name": 1, "currency": 1}) or {}
                try:
                    cs_data = await compset_router.build(property_id=p, days=30, current_user=owner)
                    k = cs_data.get("kpis", {})
                except Exception:
                    continue
                ps = _sym(prop.get("currency") or "GBP")
                rows += f'<tr><td style="padding:5px 8px;border-top:1px solid #f5f5f4;">{prop.get("name") or p}</td><td style="padding:5px 8px;border-top:1px solid #f5f5f4;text-align:right;">{k.get("my_occupancy")}%</td><td style="padding:5px 8px;border-top:1px solid #f5f5f4;text-align:right;">{ps}{k.get("my_adr")}</td><td style="padding:5px 8px;border-top:1px solid #f5f5f4;text-align:right;">#{k.get("occ_rank")}/{k.get("segment_size")}</td></tr>'
            if rows:
                pf_html = f"""
                <h3 style="font-size:14px;color:#1c1917;margin:22px 0 8px;">Portföy Özeti</h3>
                <table style="width:100%;border-collapse:collapse;font-size:12px;">
                  <tr style="color:#a8a29e;font-size:10px;text-transform:uppercase;"><td style="padding:5px 8px;">Tesis</td><td style="padding:5px 8px;text-align:right;">Occ</td><td style="padding:5px 8px;text-align:right;">ADR</td><td style="padding:5px 8px;text-align:right;">Sıra</td></tr>
                  {rows}
                </table>"""
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        return f"""
        <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#292524;">
          <h2 style="color:#0f766e;margin-bottom:2px;">Haftalık Pulse Özeti</h2>
          <div style="font-size:12px;color:#78716c;margin-bottom:14px;">{dash.get('property_name') or pid} · Merhaba {owner.get('name','')}</div>
          <table style="width:100%;border-collapse:collapse;"><tr>{cards_html}</tr></table>
          <h3 style="font-size:14px;color:#1c1917;margin:22px 0 8px;">Bu Haftanın İçgörüleri</h3>
          <ul style="font-size:13px;padding-left:18px;margin:0;">{ins_html}</ul>
          {pf_html}
          <p style="text-align:center;margin:26px 0 8px;">
            <a href="{base}/owner" style="background:#0f766e;color:#fff;text-decoration:none;padding:11px 26px;border-radius:10px;font-weight:bold;display:inline-block;">Portalı Aç</a>
          </p>
          <p style="font-size:11px;color:#a8a29e;text-align:center;">Bu özet her Pazartesi otomatik gönderilir. Kapatmak için yönetim ofisiyle iletişime geçin.</p>
        </div>"""

    async def _digest_sweep(pid: str) -> dict:
        q = {"$or": [{"property_id": pid}, {"property_ids": pid}]}
        if pid == "default":
            q["$or"].append({"property_id": {"$in": [None, ""]}})
        owners = await db.unit_owners.find(q, {"_id": 0}).to_list(50)
        now_iso = datetime.now(timezone.utc).isoformat()
        sent = 0
        for o in owners:
            email = (o.get("email") or "").strip()
            if not email:
                continue
            html = await _build_digest_html(o)
            result = await _send_email(email, "Haftalık Pulse Özeti — otelinizin nabzı", html)
            await db.owner_digest_log.insert_one({
                "id": str(uuid.uuid4()), "property_id": pid, "owner_id": o.get("id"),
                "owner_email": email, "status": result, "sent_at": now_iso})
            if result in ("sent", "mock"):
                sent += 1
        return {"ok": True, "owners": len(owners), "sent": sent}

    async def _digest_loop(interval_seconds: int = 21600):
        while True:
            try:
                now = datetime.now(timezone.utc)
                if now.weekday() == 0:  # Pazartesi
                    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
                    async for cfg in db.owner_pulse_config.find({"digest_enabled": True}, {"_id": 0, "property_id": 1}):
                        pid = cfg["property_id"]
                        already = await db.owner_digest_log.find_one(
                            {"property_id": pid, "sent_at": {"$gte": week_start}}, {"_id": 1})
                        if not already:
                            r = await _digest_sweep(pid)
                            logger.info(f"Pulse digest ({pid}): {r['sent']}/{r['owners']} gönderildi")
            except Exception as e:
                logger.warning(f"Pulse digest loop error: {e}")
            await asyncio.sleep(interval_seconds)

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
        for pid in pids:
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

    @router.get("/portal/portfolio-overview")
    async def portal_portfolio_overview(owner: dict = Depends(get_current_owner)):
        await _check(_pid(owner), "portfolio")
        pids = owner.get("property_ids") or [_pid(owner)]
        return await build_portfolio_overview(db, pids)

    @router.get("/portal/recovery/{pid}")
    async def portal_recovery(pid: str, owner: dict = Depends(get_current_owner)):
        await _check(_pid(owner), "portfolio")
        allowed = owner.get("property_ids") or [_pid(owner)]
        if pid not in allowed:
            raise HTTPException(403, "Bu tesise erişiminiz yok")
        return await build_recovery_plan(db, pid)

    @router.get("/portfolio/overview")
    async def admin_portfolio_overview(current_user: dict = Depends(require_roles("admin", "manager"))):
        pids = [p["id"] async for p in db.properties.find({}, {"_id": 0, "id": 1}) if p.get("id")]
        return await build_portfolio_overview(db, pids)

    @router.get("/portfolio/recovery/{pid}")
    async def admin_recovery(pid: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        return await build_recovery_plan(db, pid)

    @router.post("/portfolio/recovery/{pid}/apply")
    async def admin_recovery_apply(pid: str, data: Dict,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        return await apply_recovery_action(db, pid, (data or {}).get("action_type", ""),
                                           current_user.get("email", "admin"))

    @router.post("/portal/recovery/{pid}/apply")
    async def portal_recovery_apply(pid: str, data: Dict, owner: dict = Depends(get_current_owner)):
        await _check(_pid(owner), "portfolio")
        allowed = owner.get("property_ids") or [_pid(owner)]
        if pid not in allowed:
            raise HTTPException(403, "Bu tesise erişiminiz yok")
        return await apply_recovery_action(db, pid, (data or {}).get("action_type", ""),
                                           owner.get("email", "owner"))

    @router.get("/portal/reports/{key}")
    async def portal_report(key: str, owner: dict = Depends(get_current_owner)):
        await _check(_pid(owner), "reports")
        return await build_owner_report(db, _pid(owner), key,
                                        radar_build=demand_radar_router.build,
                                        compset_build=compset_router.build, owner=owner)

    # ── Admin endpoints ──
    @router.get("/{pid}/config")
    async def admin_get_config(pid: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        return {"property_id": pid, "modules": await _modules(pid),
                "digest_enabled": await _digest_enabled(pid)}

    @router.put("/{pid}/config")
    async def admin_set_config(pid: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        mods = {k: bool((data.get("modules") or {}).get(k, True)) for k in MODULE_KEYS}
        update = {"property_id": pid, "modules": mods,
                  "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": current_user.get("email", "")}
        if "digest_enabled" in data:
            update["digest_enabled"] = bool(data["digest_enabled"])
        await db.owner_pulse_config.update_one(
            {"property_id": pid}, {"$set": update}, upsert=True)
        return {"ok": True, "modules": mods, "digest_enabled": update.get("digest_enabled")}

    @router.get("/{pid}/dashboard")
    async def admin_preview_dashboard(pid: str,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        return await build_owner_dashboard(db, pid)

    @router.post("/{pid}/digest/send-now")
    async def admin_send_digest(pid: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _digest_sweep(pid)

    @router.get("/{pid}/digest/log")
    async def admin_digest_log(pid: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.owner_digest_log.find(
            {"property_id": pid}, {"_id": 0}).sort("sent_at", -1).to_list(20)
        return {"items": rows}

    @router.get("/{pid}/digest/preview")
    async def admin_digest_preview(pid: str,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {"$or": [{"property_id": pid}, {"property_ids": pid}]}
        if pid == "default":
            q["$or"].append({"property_id": {"$in": [None, ""]}})
        owner = await db.unit_owners.find_one(q, {"_id": 0})
        if not owner:
            raise HTTPException(404, "Bu tesise bağlı sahip yok")
        return {"html": await _build_digest_html(owner), "owner_email": owner.get("email")}

    router.digest_loop = _digest_loop
    return router
