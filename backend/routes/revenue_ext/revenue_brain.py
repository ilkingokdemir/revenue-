"""
Revenue Brain — Öğrenen Revenue Yapay Zekâsı (kapalı öğrenme döngüsü).

Katman 1 — Outcome Tracker: geçmiş fiyat kararlarının gerçek sonucunu ölçer
  (nihai doluluk vs aynı gün tipi baseline) ve "worked / neutral / hurt" etiketler.
Katman 2 — Self-Tuning: sonuçları bağlam kovalarında (lead-time bandı × gün tipi
  × yön) toplar, öğrenilmiş düzeltme çarpanları üretir; fiyat motoru bunları uygular.
Katman 3 — Ders Hafızası + Hedef: Türkçe okunur dersler üretir (LLM stratejiste
  beslenir) ve aylık gelir hedefine karşı ilerleme/tavsiye hesaplar.

Collections: ai_pricing_outcomes, learned_pricing_weights, revenue_brain_lessons,
             revenue_goals, revenue_brain_state
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import calendar
import logging
import uuid

logger = logging.getLogger(__name__)

MIN_SAMPLES = 4
DOWN_F, UP_DAMPEN, UP_BOOST = 0.97, 0.95, 1.03


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _band(days_out) -> str:
    d = int(days_out or 0)
    if d <= 3:
        return "0-3"
    if d <= 7:
        return "4-7"
    if d <= 21:
        return "8-21"
    return "22+"


def _dow_type(date_str: str) -> str:
    return "weekend" if datetime.strptime(date_str, "%Y-%m-%d").weekday() in (4, 5) else "weekday"


def bucket_key(days_out, date_str: str, direction: str) -> str:
    return f"{_band(days_out)}|{_dow_type(date_str)}|{direction}"


BAND_TR = {"0-3": "son 3 gün", "4-7": "4-7 gün kala", "8-21": "1-3 hafta kala", "22+": "3+ hafta kala"}
DOW_TR = {"weekday": "hafta içi", "weekend": "hafta sonu"}
DIR_TR = {"up": "fiyat artışları", "down": "fiyat indirimleri"}


async def _occ_for_date(db, pid: str, date_str: str, total_rooms: int) -> float:
    if total_rooms <= 0:
        return 0.0
    n = await db.bookings.count_documents({
        "property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
        "check_in": {"$lte": date_str}, "check_out": {"$gt": date_str}})
    return round(min(n / total_rooms * 100.0, 100.0), 1)


async def measure_outcomes(db, pid: str) -> int:
    """Tarihi geçmiş, henüz ölçülmemiş fiyat kararlarını ölç."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_rooms = await db.rooms.count_documents({"property_id": pid})
    decisions = await db.ai_pricing_decisions.find(
        {"property_id": pid, "date": {"$lt": today}}, {"_id": 0}).to_list(500)
    measured = 0
    for dec in decisions:
        exists = await db.ai_pricing_outcomes.find_one(
            {"property_id": pid, "stay_date": dec["date"],
             "room_type_id": dec.get("room_type_id", "")}, {"_id": 0, "id": 1})
        if exists:
            continue
        stay = datetime.strptime(dec["date"], "%Y-%m-%d")
        final_occ = await _occ_for_date(db, pid, dec["date"], total_rooms)
        # Baseline: aynı haftanın gününe denk gelen önceki 4 tarihin ortalama doluluğu
        base_vals = []
        step = 7
        for k in range(1, 5):
            bd = (stay - timedelta(days=step * k)).strftime("%Y-%m-%d")
            base_vals.append(await _occ_for_date(db, pid, bd, total_rooms))
        baseline = round(sum(base_vals) / len(base_vals), 1) if base_vals else 0.0

        delta = float(dec.get("delta_pct") or 0)
        direction = "up" if delta > 0 else ("down" if delta < 0 else "flat")
        if direction == "up":
            verdict = "worked" if final_occ >= baseline - 3 else ("hurt" if final_occ < baseline - 10 else "neutral")
        elif direction == "down":
            verdict = "worked" if final_occ > baseline + 3 else ("hurt" if final_occ < baseline - 5 else "neutral")
        else:
            verdict = "neutral"

        await db.ai_pricing_outcomes.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid,
            "stay_date": dec["date"], "room_type_id": dec.get("room_type_id", ""),
            "delta_pct": delta, "direction": direction,
            "days_out": dec.get("days_out"), "band": _band(dec.get("days_out")),
            "dow_type": _dow_type(dec["date"]),
            "bucket_key": bucket_key(dec.get("days_out"), dec["date"], direction),
            "decision_occ": dec.get("occupancy_pct"),
            "final_occ": final_occ, "baseline_occ": baseline,
            "str_mult": dec.get("str_mult"), "set_by": dec.get("set_by"),
            "verdict": verdict, "measured_at": _now()})
        measured += 1
    return measured


async def learn_weights(db, pid: str) -> int:
    """Kovalara göre başarı oranından öğrenilmiş çarpanlar üret."""
    outcomes = await db.ai_pricing_outcomes.find(
        {"property_id": pid, "direction": {"$in": ["up", "down"]}}, {"_id": 0}).to_list(2000)
    buckets: Dict[str, list] = {}
    for o in outcomes:
        buckets.setdefault(o["bucket_key"], []).append(o)
    updated = 0
    for key, rows in buckets.items():
        if len(rows) < MIN_SAMPLES:
            continue
        worked = sum(1 for r in rows if r["verdict"] == "worked")
        hurt = sum(1 for r in rows if r["verdict"] == "hurt")
        worked_rate = round(worked / len(rows), 2)
        direction = key.split("|")[2]
        factor = 1.0
        if hurt > worked:
            factor = UP_DAMPEN if direction == "up" else DOWN_F
        elif direction == "up" and worked_rate >= 0.7:
            factor = UP_BOOST
        await db.learned_pricing_weights.update_one(
            {"property_id": pid, "bucket_key": key},
            {"$set": {"property_id": pid, "bucket_key": key, "factor": factor,
                      "samples": len(rows), "worked": worked, "hurt": hurt,
                      "worked_rate": worked_rate, "updated_at": _now()}},
            upsert=True)
        updated += 1
    return updated


async def generate_lessons(db, pid: str) -> int:
    """Öğrenilmiş ağırlıklardan Türkçe dersler üret (LLM stratejiste de beslenir)."""
    weights = await db.learned_pricing_weights.find(
        {"property_id": pid}, {"_id": 0}).to_list(100)
    lessons = []
    for w in weights:
        band, dow, direction = w["bucket_key"].split("|")
        ctx = f"{DOW_TR[dow]} {BAND_TR[band]} yapılan {DIR_TR.get(direction, direction)}"
        if w["factor"] < 1.0:
            lessons.append((w["bucket_key"],
                f"{ctx} {w['samples']} denemenin {w['hurt']}'inde talebi düşürdü (başarı %{w['worked_rate']*100:.0f}) — motor bu bağlamda değişimi ×{w['factor']} ile frenliyor."))
        elif w["factor"] > 1.0:
            lessons.append((w["bucket_key"],
                f"{ctx} %{w['worked_rate']*100:.0f} başarıyla sonuçlandı ({w['samples']} örnek) — motor bu bağlamda ×{w['factor']} ile daha cesur."))
        else:
            lessons.append((w["bucket_key"],
                f"{ctx} nötr seyretti ({w['samples']} örnek, başarı %{w['worked_rate']*100:.0f}) — motor standart davranıyor, veri toplamaya devam."))
    total_o = await db.ai_pricing_outcomes.count_documents({"property_id": pid})
    total_w = await db.ai_pricing_outcomes.count_documents({"property_id": pid, "verdict": "worked"})
    if total_o:
        lessons.append(("__overall__",
            f"Toplam {total_o} fiyat kararının sonucu ölçüldü; %{total_w/total_o*100:.0f}'i hedeflenen etkiyi yarattı. Beyin her gece yeni sonuçlarla kendini güncelliyor."))
    await db.revenue_brain_lessons.delete_many({"property_id": pid})
    now = _now()
    for bk, text in lessons:
        await db.revenue_brain_lessons.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "bucket_key": bk,
            "lesson": text, "created_at": now})
    return len(lessons)


async def _timeline_event(db, pid: str, ev_type: str, text: str, bucket_key: str = ""):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dup = await db.revenue_brain_timeline.find_one(
        {"property_id": pid, "type": ev_type, "bucket_key": bucket_key,
         "at": {"$gte": today}}, {"_id": 0, "id": 1})
    if dup:
        return
    await db.revenue_brain_timeline.insert_one({
        "id": str(uuid.uuid4()), "property_id": pid, "type": ev_type,
        "bucket_key": bucket_key, "text": text, "at": _now()})


async def _region_map(db) -> dict:
    m = {}
    async for p in db.properties.find({}, {"_id": 0, "id": 1, "country": 1, "city": 1}):
        m[p["id"]] = (p.get("country") or p.get("city") or "diger").strip() or "diger"
    return m


async def consolidate_regional_memory(db) -> int:
    """Bölgesel Hafıza: dersler ülke/şehir bazında birleşir — yeni otel önce
    kendi bölgesinin derslerini devralır (yerel > bölgesel > küresel önceliği)."""
    regions = await _region_map(db)
    agg = {}
    async for o in db.ai_pricing_outcomes.find(
            {"direction": {"$in": ["up", "down"]}},
            {"_id": 0, "property_id": 1, "bucket_key": 1, "verdict": 1}):
        reg = regions.get(o["property_id"], "diger")
        s = agg.setdefault((reg, o["bucket_key"]), {"n": 0, "worked": 0, "hurt": 0, "props": set()})
        s["n"] += 1
        s["props"].add(o["property_id"])
        if o["verdict"] == "worked":
            s["worked"] += 1
        elif o["verdict"] == "hurt":
            s["hurt"] += 1
    updated, now = 0, _now()
    for (reg, key), s in agg.items():
        if s["n"] < MIN_SAMPLES:
            continue
        band, dow, direction = key.split("|")
        worked_rate = round(s["worked"] / s["n"], 2)
        factor = 1.0
        if s["hurt"] > s["worked"]:
            factor = UP_DAMPEN if direction == "up" else DOWN_F
        elif direction == "up" and worked_rate >= 0.7:
            factor = UP_BOOST
        ctx = f"{DOW_TR[dow]} {BAND_TR[band]} {DIR_TR.get(direction, direction)}"
        detail = (f"{reg} bölgesi — {ctx}: {len(s['props'])} otelden {s['n']} sonuç, başarı %{worked_rate*100:.0f} "
                  f"— bölgesel çarpan ×{factor}. Bu bölgeye eklenen yeni oteller önce bu dersi devralır.")
        await db.revenue_brain_regional_memory.update_one(
            {"region": reg, "bucket_key": key},
            {"$set": {"region": reg, "bucket_key": key, "factor": factor,
                      "samples": s["n"], "worked": s["worked"], "hurt": s["hurt"],
                      "worked_rate": worked_rate, "properties_contributing": len(s["props"]),
                      "title": ctx, "detail": detail, "last_confirmed": now},
             "$setOnInsert": {"id": str(uuid.uuid4()), "first_learned": now}},
            upsert=True)
        updated += 1
    return updated



async def consolidate_global_memory(db) -> int:
    """Küresel Hafıza: TÜM otellerin ölçülmüş sonuçlarını bağlam kovasında birleştirir.
    Yeni otel/bölge/ülke için soğuk başlangıç önseli (prior) olarak fiyat motoruna beslenir."""
    pipeline = [
        {"$match": {"direction": {"$in": ["up", "down"]}}},
        {"$group": {"_id": "$bucket_key", "n": {"$sum": 1},
                    "worked": {"$sum": {"$cond": [{"$eq": ["$verdict", "worked"]}, 1, 0]}},
                    "hurt": {"$sum": {"$cond": [{"$eq": ["$verdict", "hurt"]}, 1, 0]}},
                    "props": {"$addToSet": "$property_id"}}}]
    updated = 0
    now = _now()
    async for g in db.ai_pricing_outcomes.aggregate(pipeline):
        if g["n"] < MIN_SAMPLES:
            continue
        key = g["_id"]
        band, dow, direction = key.split("|")
        worked_rate = round(g["worked"] / g["n"], 2)
        factor = 1.0
        if g["hurt"] > g["worked"]:
            factor = UP_DAMPEN if direction == "up" else DOWN_F
        elif direction == "up" and worked_rate >= 0.7:
            factor = UP_BOOST
        ctx = f"{DOW_TR[dow]} {BAND_TR[band]} {DIR_TR.get(direction, direction)}"
        detail = (f"{ctx}: {len(g['props'])} otelden {g['n']} ölçülmüş sonuç, başarı %{worked_rate*100:.0f} "
                  f"— küresel çarpan ×{factor}. Yeni otellerde yerel veri birikene kadar önsel olarak (yarı etkiyle) uygulanır.")
        await db.revenue_brain_global_memory.update_one(
            {"bucket_key": key},
            {"$set": {"bucket_key": key, "factor": factor, "samples": g["n"],
                      "worked": g["worked"], "hurt": g["hurt"], "worked_rate": worked_rate,
                      "properties_contributing": len(g["props"]),
                      "title": ctx, "detail": detail, "last_confirmed": now},
             "$setOnInsert": {"id": str(uuid.uuid4()), "first_learned": now}},
            upsert=True)
        updated += 1
    return updated


async def consolidate_memory(db, pid: str) -> int:
    """Kalıcı Hafıza: önemli öğrenmeleri asla silinmeyen arşive işler.
    Ders/ağırlık her döngüde yeniden üretilse bile, kritik öğrenme burada sonsuza dek saklanır."""
    now = _now()
    saved = 0
    weights = await db.learned_pricing_weights.find({"property_id": pid}, {"_id": 0}).to_list(200)
    for w in weights:
        band, dow, direction = w["bucket_key"].split("|")
        ctx = f"{DOW_TR[dow]} {BAND_TR[band]} {DIR_TR.get(direction, direction)}"
        existing = await db.revenue_brain_memory.find_one(
            {"property_id": pid, "bucket_key": w["bucket_key"]}, {"_id": 0, "id": 1, "status": 1})
        if w["factor"] != 1.0:
            importance = "kritik" if w["factor"] < 1.0 else "firsat"
            detail = (f"{ctx}: {w['samples']} denemede başarı %{w['worked_rate']*100:.0f} — "
                      f"kalıcı çarpan ×{w['factor']}. Bu ders unutulmaz; motor her fiyat kararında uygular.")
            await db.revenue_brain_memory.update_one(
                {"property_id": pid, "bucket_key": w["bucket_key"]},
                {"$set": {"property_id": pid, "bucket_key": w["bucket_key"],
                          "kind": "fiyat_dersi", "importance": importance,
                          "title": ctx, "detail": detail, "factor": w["factor"],
                          "samples": w["samples"], "worked_rate": w["worked_rate"],
                          "worked": w["worked"], "hurt": w["hurt"],
                          "status": "aktif", "last_confirmed": now},
                 "$setOnInsert": {"id": str(uuid.uuid4()), "first_learned": now},
                 "$inc": {"times_confirmed": 1}},
                upsert=True)
            if not existing:
                await _timeline_event(db, pid, "yeni_ders",
                                      f"Yeni kalıcı ders öğrenildi: {ctx} (çarpan ×{w['factor']})",
                                      w["bucket_key"])
            elif existing.get("status") != "aktif":
                await _timeline_event(db, pid, "ders_aktif",
                                      f"İzlemedeki ders yeniden aktifleşti: {ctx}", w["bucket_key"])
            else:
                await _timeline_event(db, pid, "ders_dogrulandi",
                                      f"Kalıcı ders yeni verilerle doğrulandı: {ctx} ({w['samples']} örnek)",
                                      w["bucket_key"])
            saved += 1
        elif existing:
            # Ağırlık nötre dönse bile hafıza SİLİNMEZ — izlemeye alınır
            await db.revenue_brain_memory.update_one(
                {"property_id": pid, "bucket_key": w["bucket_key"]},
                {"$set": {"status": "izlemede", "last_confirmed": now,
                          "samples": w["samples"], "worked_rate": w["worked_rate"]}})
            if existing.get("status") == "aktif":
                await _timeline_event(db, pid, "ders_izlemede",
                                      f"Ders nötre döndü, silinmedi — izlemeye alındı: {ctx}", w["bucket_key"])
    return saved


async def run_learning_cycle(db, pid: str) -> dict:
    measured = await measure_outcomes(db, pid)
    weights = await learn_weights(db, pid)
    lessons = await generate_lessons(db, pid)
    memory = await consolidate_memory(db, pid)
    global_mem = await consolidate_global_memory(db)
    regional_mem = await consolidate_regional_memory(db)
    try:
        from routes.revenue_ext.rm_expertise import compute_sensitivity, internalize_expertise
        await compute_sensitivity(db, pid)
        await internalize_expertise(db, pid)
        from routes.revenue_ext.ml_pickup import log_ml_forecasts, score_forecasts
        await log_ml_forecasts(db, pid)
        card = await score_forecasts(db, pid)
        if card.get("alert"):
            await _timeline_event(db, pid, "tahmin_sapmasi",
                                  f"UYARI: ML tahmin karnesi sapıyor — son 35 gün MAPE %{card['overall_mape']} "
                                  f"({card['scored']} skor). Model yeniden eğitim/kalibrasyon gerektirebilir.")
    except Exception:
        pass
    if measured > 0:
        await _timeline_event(db, pid, "ogrenme_dongusu",
                              f"Öğrenme döngüsü: {measured} yeni fiyat kararı sonucu ölçüldü, "
                              f"{weights} çarpan güncellendi.")
    await db.revenue_brain_state.update_one(
        {"property_id": pid},
        {"$set": {"property_id": pid, "last_cycle_at": _now(),
                  "last_measured": measured, "last_weights": weights,
                  "last_lessons": lessons, "last_memory": memory}}, upsert=True)
    logger.info(f"Revenue Brain cycle {pid}: measured={measured} weights={weights} lessons={lessons} memory={memory}")
    return {"measured": measured, "weights_updated": weights, "lessons": lessons,
            "memory_consolidated": memory, "global_memory_updated": global_mem,
            "regional_memory_updated": regional_mem}


async def build_goal_progress(db, pid: str) -> dict:
    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")
    goal = await db.revenue_goals.find_one({"property_id": pid, "month": month_key}, {"_id": 0})
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    month_end = now.replace(day=days_in_month).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                    "check_in": {"$gte": month_start, "$lte": month_end}}},
        {"$group": {"_id": None, "rev": {"$sum": "$total_price"}, "n": {"$sum": 1}}}]
    agg = await db.bookings.aggregate(pipeline).to_list(1)
    mtd_revenue = round((agg[0]["rev"] if agg else 0) or 0, 2)
    days_elapsed = now.day
    projection = round(mtd_revenue / max(days_elapsed, 1) * days_in_month, 2)
    out = {"month": month_key, "mtd_revenue": mtd_revenue, "projection": projection,
           "days_elapsed": days_elapsed, "days_in_month": days_in_month,
           "target_revenue": (goal or {}).get("target_revenue"),
           "target_occ": (goal or {}).get("target_occ")}
    if goal and goal.get("target_revenue"):
        target = float(goal["target_revenue"])
        out["progress_pct"] = round(mtd_revenue / target * 100, 1) if target else 0
        out["on_track"] = projection >= target
        gap = target - projection
        days_left = days_in_month - days_elapsed
        if gap > 0 and days_left > 0:
            out["recommendation"] = (
                f"Mevcut hızla ay sonu tahmini {projection:,.0f} — hedefin {gap:,.0f} altında. "
                f"Kalan {days_left} günde günlük ek {gap/days_left:,.0f} gelir gerekli: "
                f"beyin, yüksek talep sinyalli günlerde ADR artışı + düşük doluluk günlerinde kampanya öneriyor.")
        else:
            out["recommendation"] = f"Hedefin üzerindesiniz — ay sonu tahmini {projection:,.0f}. Beyin fiyat tavanlarını gevşetmeyi değerlendiriyor."
    return out


async def simulate_lesson_impact(db, pid: str, key: str) -> dict:
    """Ders Etki Simülatörü: bir ders kapatılırsa 14 günde gelirin nasıl değişeceğini tahmin eder."""
    mem = await db.revenue_brain_memory.find_one({"property_id": pid, "bucket_key": key}, {"_id": 0})
    if not mem:
        mem = await db.revenue_brain_global_memory.find_one({"bucket_key": key}, {"_id": 0})
    if not mem:
        raise HTTPException(404, "Ders bulunamadı")
    factor = float(mem.get("factor") or 1.0)
    band, dow, direction = key.split("|")
    from routes.distribution.push_history import resolve_rate
    total_rooms = await db.rooms.count_documents({"property_id": pid}) or 20
    today = datetime.now(timezone.utc).date()
    affected, delta = [], 0.0
    for i in range(14):
        ds = (today + timedelta(days=i)).isoformat()
        if _dow_type(ds) != dow:
            continue
        base, _src = await resolve_rate(db, pid, ds)
        sold = await db.bookings.count_documents({
            "property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
            "check_in": {"$lte": ds}, "check_out": {"$gt": ds}})
        exposure = max(sold, int(total_rooms * 0.3))
        day_delta = round(base * (factor - 1.0) * exposure, 2)
        delta += day_delta
        affected.append({"date": ds, "base_rate": round(base, 2),
                         "braked_rate": round(base * factor, 2),
                         "exposure_rooms": exposure, "est_delta": day_delta})
    hurt_rate = 0.0
    if mem.get("samples"):
        hurt_n = mem.get("hurt")
        if hurt_n is None:
            w = await db.learned_pricing_weights.find_one(
                {"property_id": pid, "bucket_key": key}, {"_id": 0, "hurt": 1})
            hurt_n = (w or {}).get("hurt") or 0
        hurt_rate = round(hurt_n / mem["samples"] * 100, 1)
    if factor < 1.0:
        rec = (f"Bu ders KAPATILIRSA motor frenlemeden agresif değişime döner. Geçmişte bu bağlamdaki kararların "
               f"%{hurt_rate}'i talebe ZARAR verdi. 14 günde ~{abs(round(delta, 2))} tutarında gelir oynaklığı riski. "
               f"Robotun önerisi: ders AÇIK kalsın.")
    elif factor > 1.0:
        rec = (f"Bu ders KAPATILIRSA motor bu bağlamdaki cesur artışlardan vazgeçer; 14 günde ~{abs(round(delta, 2))} "
               f"tutarında fırsat kaçabilir. Robotun önerisi: ders AÇIK kalsın.")
    else:
        rec = "Ders şu an nötr — kapatmanın ölçülebilir etkisi yok."
    return {"bucket_key": key, "factor": factor, "affected_days": len(affected),
            "est_revenue_delta_14d": round(delta, 2), "hurt_rate_pct": hurt_rate,
            "days": affected, "recommendation": rec}


def _build_memory_pdf(hotel_name: str, region: str, memory: list, regional: list,
                      global_mem: list, timeline: list, stats: dict) -> bytes:
    """Robot öğrenme raporu — sahip/yatırımcı sunumu için tek tık PDF."""
    import io
    import os as _os
    import textwrap
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = {
        "DVS": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf"],
        "DVSB": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
    }
    for fname, paths in candidates.items():
        if fname not in pdfmetrics.getRegisteredFontNames():
            for path in paths:
                if _os.path.exists(path):
                    pdfmetrics.registerFont(TTFont(fname, path))
                    break

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    ink, violet, grey = HexColor("#1c1917"), HexColor("#7c3aed"), HexColor("#6b7280")

    def header():
        c.setFillColor(ink)
        c.rect(0, H - 100, W, 100, stroke=0, fill=1)
        c.setFillColor(HexColor("#ffffff"))
        c.setFont("DVSB", 18)
        c.drawString(40, H - 50, hotel_name)
        c.setFont("DVS", 11)
        c.drawString(40, H - 72, "REVENUE ROBOTU — ÖĞRENME VE HAFIZA RAPORU")
        c.setFont("DVS", 9)
        c.drawRightString(W - 40, H - 72, datetime.now(timezone.utc).strftime("%d.%m.%Y"))

    y = [H - 130]

    def ensure(space):
        if y[0] < 60 + space:
            c.showPage()
            header()
            y[0] = H - 130

    def section(title):
        ensure(40)
        c.setFillColor(violet)
        c.setFont("DVSB", 12)
        c.drawString(40, y[0], title)
        y[0] -= 18

    def para(text, size=9, color=None, indent=40):
        c.setFont("DVS", size)
        c.setFillColor(color or HexColor("#111827"))
        for line in textwrap.wrap(text, width=110):
            ensure(14)
            c.drawString(indent, y[0], line)
            y[0] -= 12
        y[0] -= 4

    header()
    section("Özet")
    para(f"Ölçülen fiyat kararı: {stats.get('outcomes', 0)} · Başarı oranı: "
         f"%{stats.get('success_rate') if stats.get('success_rate') is not None else '—'} · "
         f"Kalıcı ders: {len(memory)} · Bölgesel ders ({region}): {len(regional)} · Küresel ders: {len(global_mem)}")

    section(f"Kalıcı Hafıza — Otel Dersleri ({len(memory)})")
    if not memory:
        para("Henüz kalıcı ders yok — öğrenme döngüleri biriktikçe eklenecek.", color=grey)
    for m in memory:
        para(f"• [{m.get('importance', '').upper()} · {m.get('status')}] {m.get('detail', '')} "
             f"(İlk öğrenme: {str(m.get('first_learned', ''))[:10]}, {m.get('times_confirmed', 1)}× doğrulandı)")

    section(f"Bölgesel Hafıza — {region} ({len(regional)})")
    if not regional:
        para("Bu bölge için henüz birleşik ders yok.", color=grey)
    for m in regional:
        para(f"• {m.get('detail', '')}")

    section(f"Küresel Hafıza — Tüm Portföy ({len(global_mem)})")
    if not global_mem:
        para("Henüz küresel ders yok.", color=grey)
    for m in global_mem:
        para(f"• {m.get('detail', '')}")

    section("Öğrenme Yolculuğu (son olaylar)")
    if not timeline:
        para("Henüz olay kaydı yok.", color=grey)
    for ev in timeline[:12]:
        para(f"{str(ev.get('at', ''))[:16].replace('T', ' ')} — {ev.get('text', '')}", size=8, color=grey)

    ensure(30)
    c.setFont("DVS", 8)
    c.setFillColor(grey)
    c.drawString(40, 40, "Bu rapor Revenue Robotu'nun kalıcı hafızasından otomatik üretilmiştir. Dersler asla silinmez; nötre dönen dersler 'izlemede' olarak saklanır.")
    c.save()
    return buf.getvalue()


def create_revenue_brain_router(db, require_roles):
    router = APIRouter(prefix="/revenue-brain", tags=["revenue-brain"])
    ROLES = ("admin", "manager")

    @router.post("/{pid}/learn")
    async def learn_now(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await run_learning_cycle(db, pid)

    @router.get("/{pid}/status")
    async def status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        outcomes = await db.ai_pricing_outcomes.count_documents({"property_id": pid})
        worked = await db.ai_pricing_outcomes.count_documents({"property_id": pid, "verdict": "worked"})
        hurt = await db.ai_pricing_outcomes.count_documents({"property_id": pid, "verdict": "hurt"})
        weights = await db.learned_pricing_weights.find(
            {"property_id": pid}, {"_id": 0}).sort("samples", -1).to_list(50)
        lessons = await db.revenue_brain_lessons.find(
            {"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(20)
        state = await db.revenue_brain_state.find_one({"property_id": pid}, {"_id": 0})
        recent = await db.ai_pricing_outcomes.find(
            {"property_id": pid}, {"_id": 0}).sort("measured_at", -1).to_list(10)
        memory = await db.revenue_brain_memory.find(
            {"property_id": pid}, {"_id": 0}).sort("first_learned", 1).to_list(50)
        global_mem = await db.revenue_brain_global_memory.find(
            {}, {"_id": 0}).sort("samples", -1).to_list(30)
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "country": 1, "city": 1})
        region = ((prop or {}).get("country") or (prop or {}).get("city") or "diger").strip() or "diger"
        regional_mem = await db.revenue_brain_regional_memory.find(
            {"region": region}, {"_id": 0}).sort("samples", -1).to_list(30)
        return {
            "permanent_memory": memory,
            "memory_count": len(memory),
            "global_memory": global_mem,
            "global_memory_count": len(global_mem),
            "region": region,
            "regional_memory": regional_mem,
            "regional_memory_count": len(regional_mem),
            "property_id": pid,
            "outcomes_measured": outcomes,
            "worked": worked, "hurt": hurt,
            "success_rate": round(worked / outcomes * 100, 1) if outcomes else None,
            "active_weights": sum(1 for w in weights if w.get("factor") != 1.0),
            "weights": weights,
            "lessons": lessons,
            "recent_outcomes": recent,
            "last_cycle_at": (state or {}).get("last_cycle_at"),
            "goal": await build_goal_progress(db, pid),
        }

    @router.get("/global-memory")
    async def global_memory(_u: dict = Depends(require_roles(*ROLES))):
        """Küresel hafıza — tüm otellerin birleşik öğrenmeleri (yeni otel/bölge önseli)."""
        items = await db.revenue_brain_global_memory.find(
            {}, {"_id": 0}).sort("samples", -1).to_list(100)
        return {"count": len(items), "items": items,
                "note": "Tüm otellerin ölçülmüş fiyat sonuçları bağlam kovalarında birleşir; "
                        "yeni bir otel/bölge/ülke eklendiğinde motor bu dersleri yarı etkiyle önsel olarak uygular."}

    @router.get("/regional-memory")
    async def regional_memory(region: str = "", _u: dict = Depends(require_roles(*ROLES))):
        """Bölgesel hafıza — ülke/şehir bazında birleşik dersler."""
        q = {"region": region} if region else {}
        items = await db.revenue_brain_regional_memory.find(
            q, {"_id": 0}).sort("samples", -1).to_list(200)
        regions = await db.revenue_brain_regional_memory.distinct("region")
        return {"count": len(items), "items": items, "regions": regions,
                "note": "Öncelik sırası: yerel ders (tam etki) > bölgesel ders (×0.7 etki) > küresel ders (×0.5 etki)."}

    @router.get("/{pid}/memory-pdf")
    async def memory_pdf(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Robotun tüm derslerini tek tıkla PDF rapor olarak indir."""
        from fastapi import Response
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1, "country": 1, "city": 1})
        region = ((prop or {}).get("country") or (prop or {}).get("city") or "diger").strip() or "diger"
        memory = await db.revenue_brain_memory.find({"property_id": pid}, {"_id": 0}).sort("first_learned", 1).to_list(100)
        regional = await db.revenue_brain_regional_memory.find({"region": region}, {"_id": 0}).sort("samples", -1).to_list(50)
        global_mem = await db.revenue_brain_global_memory.find({}, {"_id": 0}).sort("samples", -1).to_list(50)
        timeline_ev = await db.revenue_brain_timeline.find({"property_id": pid}, {"_id": 0}).sort("at", -1).to_list(12)
        outcomes = await db.ai_pricing_outcomes.count_documents({"property_id": pid})
        worked = await db.ai_pricing_outcomes.count_documents({"property_id": pid, "verdict": "worked"})
        stats = {"outcomes": outcomes,
                 "success_rate": round(worked / outcomes * 100, 1) if outcomes else None}
        pdf = _build_memory_pdf((prop or {}).get("name") or pid, region, memory, regional,
                                global_mem, timeline_ev, stats)
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="robot-hafiza-{pid}.pdf"'})

    @router.post("/{pid}/simulate-lesson")
    async def simulate_lesson(pid: str, body: Dict, _u: dict = Depends(require_roles(*ROLES))):
        key = (body.get("bucket_key") or "").strip()
        return await simulate_lesson_impact(db, pid, key)

    @router.get("/{pid}/timeline")
    async def timeline(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Öğrenme yolculuğu — tarih sıralı hafıza olayları."""
        items = await db.revenue_brain_timeline.find(
            {"property_id": pid}, {"_id": 0}).sort("at", -1).to_list(100)
        return {"property_id": pid, "count": len(items), "items": items}

    @router.get("/{pid}/memory")
    async def permanent_memory(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Kalıcı hafıza — asla silinmeyen önemli revenue öğrenmeleri."""
        items = await db.revenue_brain_memory.find(
            {"property_id": pid}, {"_id": 0}).sort("first_learned", 1).to_list(200)
        return {"property_id": pid, "count": len(items), "items": items,
                "note": "Bu hafıza kalıcıdır; öğrenmeler nötre dönse bile silinmez, izlemeye alınır."}

    @router.put("/{pid}/goal")
    async def set_goal(pid: str, data: Dict,
                       current_user: dict = Depends(require_roles(*ROLES))):
        target = float(data.get("target_revenue") or 0)
        if target <= 0:
            raise HTTPException(400, "target_revenue pozitif olmalı")
        month_key = data.get("month") or datetime.now(timezone.utc).strftime("%Y-%m")
        await db.revenue_goals.update_one(
            {"property_id": pid, "month": month_key},
            {"$set": {"property_id": pid, "month": month_key,
                      "target_revenue": target,
                      "target_occ": float(data.get("target_occ") or 0) or None,
                      "updated_by": current_user.get("email"), "updated_at": _now()}},
            upsert=True)
        return await build_goal_progress(db, pid)

    return router
