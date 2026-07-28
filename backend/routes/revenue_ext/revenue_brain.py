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
        # Baseline: aynı gün tipindeki önceki 4 tarihin ortalama doluluğu
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


async def run_learning_cycle(db, pid: str) -> dict:
    measured = await measure_outcomes(db, pid)
    weights = await learn_weights(db, pid)
    lessons = await generate_lessons(db, pid)
    await db.revenue_brain_state.update_one(
        {"property_id": pid},
        {"$set": {"property_id": pid, "last_cycle_at": _now(),
                  "last_measured": measured, "last_weights": weights,
                  "last_lessons": lessons}}, upsert=True)
    logger.info(f"Revenue Brain cycle {pid}: measured={measured} weights={weights} lessons={lessons}")
    return {"measured": measured, "weights_updated": weights, "lessons": lessons}


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
        return {
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
