"""
AI Pricing Suggestion Engine — Hybrid (formula + LLM rationale).

Computes per-day price recommendations for upcoming dates based on:
  - Competitor avg from `market_supply` (geo scan)
  - Current occupancy from `bookings` collection
  - Lead-time (days from now)
  - Base rate floor/ceiling guardrails

Workflow:
  1. Compute formula baseline (deterministic)
  2. Optionally enrich with GPT-4o-mini one-line Turkish rationale
  3. Smart auto-apply: |delta| <= threshold AND config.auto_apply → silent write
     Otherwise the suggestion stays "pending" awaiting Accept / Reject.

Storage:
  - ai_pricing_config       (per property settings)
  - ai_pricing_decisions    (audit log of accepted / rejected / auto-applied)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import asyncio
import logging
import os
import uuid

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure formula helpers (deterministic, side-effect free → easy unit-testing)
# ---------------------------------------------------------------------------

def _lead_time_multiplier(days_out: int) -> float:
    """Closer to today → tilt price up (scarcity), further out → tilt slightly down."""
    if days_out <= 1:
        return 1.06
    if days_out <= 3:
        return 1.04
    if days_out <= 7:
        return 1.00
    if days_out <= 14:
        return 0.985
    if days_out <= 30:
        return 0.97
    return 0.95


def _occupancy_multiplier(occupancy_pct: float) -> float:
    """Higher current occupancy → push price up; very low occupancy → discount."""
    if occupancy_pct >= 95:
        return 1.18
    if occupancy_pct >= 80:
        return 1.10
    if occupancy_pct >= 60:
        return 1.05
    if occupancy_pct >= 30:
        return 1.00
    return 0.95


def _str_pressure_multiplier(str_unavail: float, str_median: float, ref: float,
                             str_median_avg: float = 0.0) -> float:
    """Canlı STR (Airbnb/tatil evi) talep baskısı → fiyat çarpanı."""
    if str_unavail >= 90:
        m = 1.10
    elif str_unavail >= 80:
        m = 1.06
    elif str_unavail >= 70:
        m = 1.03
    else:
        m = 1.0
    # Tarih bazlı STR fiyat sıçraması da talep baskısı sinyalidir
    if str_median and str_median_avg:
        if str_median >= str_median_avg * 1.25:
            m = max(m, 1.05)
        elif str_median >= str_median_avg * 1.15:
            m = max(m, 1.03)
    if m > 1.0 and str_median and ref and str_median > ref * 1.3:
        m += 0.02
    return round(min(m, 1.12), 3)


def _classify_demand(occupancy_pct: float, unavailable_pct: float) -> str:
    """Bucket label used in UI badges / LLM prompt."""
    score = max(occupancy_pct, unavailable_pct)
    if score >= 85:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def compute_suggestion(
    *,
    base_rate: float,
    current_rate: float,
    market_avg: float,
    market_min: float,
    occupancy_pct: float,
    unavailable_pct: float,
    days_out: int,
    min_pct: int = 60,
    max_pct: int = 250,
    str_mult: float = 1.0,
) -> dict:
    """Return the deterministic part of the suggestion (no LLM call)."""
    ref = market_avg if market_avg > 0 else (market_min or base_rate)
    lead_m = _lead_time_multiplier(days_out)
    occ_m = _occupancy_multiplier(occupancy_pct)
    raw = ref * lead_m * occ_m * (str_mult or 1.0)

    floor_rate = round(base_rate * min_pct / 100.0, 2)
    ceil_rate = round(base_rate * max_pct / 100.0, 2)
    suggested = round(max(floor_rate, min(ceil_rate, raw)), 2)
    clamped = round(raw, 2) != suggested

    delta_pct = 0.0
    if current_rate and current_rate > 0:
        delta_pct = round((suggested - current_rate) / current_rate * 100.0, 2)

    return {
        "suggested_rate": suggested,
        "raw_rate": round(raw, 2),
        "ref_price": round(ref, 2),
        "lead_time_mult": lead_m,
        "occupancy_mult": occ_m,
        "str_mult": round(str_mult or 1.0, 3),
        "floor_rate": floor_rate,
        "ceil_rate": ceil_rate,
        "delta_vs_current_pct": delta_pct,
        "clamped": clamped,
        "demand_bucket": _classify_demand(occupancy_pct, unavailable_pct),
    }


# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "enabled": True,
    "auto_apply": False,
    "auto_apply_threshold_pct": 5.0,     # |delta| <= 5% → safe to apply silently
    "use_llm": True,                      # whether to call GPT for rationale
    "min_rate_pct": 60,                   # floor as % of base rate
    "max_rate_pct": 250,                  # ceiling as % of base rate
    "days_horizon": 30,                   # how many days ahead to compute
    "target_updates_per_day": 12,         # autopilot cadence target (RPG parity)
    "anomaly_mode": "human",              # anomali: "human" = dondur + onay iste, "auto" = bildir + devam
    "last_run_at": None,
    "last_auto_applied": 0,
    "last_pending": 0,
}


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_ai_pricing_router(db, require_roles):
    router = APIRouter()

    async def _get_cfg(property_id: str) -> dict:
        cfg = await db.ai_pricing_config.find_one({"property_id": property_id}, {"_id": 0})
        if not cfg:
            cfg = {"property_id": property_id, **DEFAULT_CONFIG}
        # Merge defaults for any missing keys (forward compat)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg

    async def _occupancy_for_date(property_id: str, target_date: str, total_rooms: int) -> dict:
        booked = await db.bookings.count_documents({
            "property_id": property_id,
            "check_in": {"$lte": target_date},
            "check_out": {"$gt": target_date},
            "status": {"$nin": ["cancelled"]},
        })
        occ = round(min(100, (booked / total_rooms * 100) if total_rooms else 0), 1)
        return {"bookings": booked, "occupancy_pct": occ, "total_rooms": total_rooms}

    async def _llm_rationales(items: list, currency_symbol: str) -> dict:
        """Send a single GPT-4o-mini call with all items and parse one-line rationales.
        Returns map: date → rationale string (Turkish). Best-effort; on any error returns {}.
        """
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key or not items:
            return {}
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            import json as _json
            compact = [
                {
                    "d": i["date"],
                    "do": i["days_out"],
                    "occ": i["occupancy_pct"],
                    "unv": i["unavailable_pct"],
                    "mavg": i["market_avg"],
                    "cur": i["current_rate"],
                    "sug": i["suggested_rate"],
                    "dlt": i["delta_vs_current_pct"],
                }
                for i in items
            ]
            prompt = (
                "Sen bir otel revenue manager asistanısın. Aşağıda her gün için "
                "(d=tarih, do=lead-time gün, occ=doluluk %, unv=rakip dolu %, "
                "mavg=pazar ort fiyat, cur=mevcut fiyat, sug=önerilen fiyat, "
                "dlt=mevcut fiyata göre %% fark) verisi var. Her gün için TEK CÜMLELİK "
                f"TÜRKÇE gerekçe ver (max 18 kelime). Para birimi sembolü: {currency_symbol}. "
                "Sadece geçerli JSON döndür: "
                '{"rationales":[{"d":"YYYY-MM-DD","r":"..."}]} — başka açıklama YOK.\n\n'
                f"Veri: {_json.dumps(compact, ensure_ascii=False)}"
            )
            chat = LlmChat(
                api_key=api_key,
                session_id=f"ai-pricing-{uuid.uuid4().hex[:8]}",
                system_message=(
                    "Sen kısa, sayısal ve aksiyona dönük revenue manager rationale'larını "
                    "üreten bir asistansın. Çıktı her zaman geçerli JSON olmalı."
                ),
            ).with_model("openai", "gpt-4o-mini")
            reply = await chat.send_message(UserMessage(text=prompt))
            raw = (reply or "").strip()
            # Try to find JSON braces
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1:
                return {}
            blob = _json.loads(raw[start:end + 1])
            out = {}
            for r in blob.get("rationales", []):
                if r.get("d") and r.get("r"):
                    out[r["d"]] = str(r["r"]).strip()
            return out
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"AI pricing LLM rationale failed: {exc}")
            return {}

    async def _build_suggestions(property_id: str, days: int, use_llm: bool):
        """Compute the full suggestion set for the next `days` days."""
        cfg = await _get_cfg(property_id)

        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1, "name": 1}) or {}
        currency = (prop.get("currency") or "GBP").upper()
        symbol = {"GBP": "£", "EUR": "€", "USD": "$", "TRY": "₺", "CHF": "CHF "}.get(currency, "")

        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        if not room_types:
            room_types = [{"id": "default", "name": "Standard", "base_rate": 130, "total_rooms": 20}]
        total_rooms = sum(int(r.get("total_rooms", 0)) for r in room_types) or 20
        base_rate_avg = (
            sum(float(r.get("base_rate", 0) or 0) for r in room_types) / max(len(room_types), 1)
            if room_types else 130
        ) or 130.0

        today = datetime.now(timezone.utc)
        today_str = today.strftime("%Y-%m-%d")
        end_str = (today + timedelta(days=days)).strftime("%Y-%m-%d")

        # Latest snapshot per date from market_supply (geo scan)
        pipeline = [
            {"$match": {"property_id": property_id, "scan_type": "geo",
                        "date": {"$gte": today_str, "$lte": end_str}}},
            {"$sort": {"scanned_at": -1}},
            {"$group": {"_id": "$date", "doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$doc"}},
            {"$sort": {"date": 1}},
            {"$project": {"_id": 0}},
        ]
        snaps = await db.market_supply.aggregate(pipeline).to_list(500)

        # Pre-fetch existing rate overrides + decisions for ALL dates in one go
        ov_rows = await db.rate_overrides.find(
            {"property_id": property_id, "date": {"$gte": today_str, "$lte": end_str}},
            {"_id": 0, "date": 1, "custom_rate": 1, "room_type_id": 1},
        ).to_list(2000)
        ov_map = {(o["date"], o.get("room_type_id") or ""): float(o.get("custom_rate") or 0) for o in ov_rows}

        dec_rows = await db.ai_pricing_decisions.find(
            {"property_id": property_id, "date": {"$gte": today_str, "$lte": end_str}},
            {"_id": 0},
        ).to_list(2000)
        dec_map = {(d["date"], d.get("room_type_id") or ""): d for d in dec_rows}

        # Canlı STR (Booking.com apartman/tatil evi) talep baskısı sinyali (<48h taze)
        str_cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        str_rows = await db.str_market_snapshots.find(
            {"property_id": property_id, "date": {"$gte": today_str, "$lte": end_str},
             "scanned_at": {"$gte": str_cutoff}},
            {"_id": 0, "date": 1, "median_rate": 1, "unavailable_pct": 1},
        ).to_list(600)
        str_map = {r["date"]: r for r in str_rows}
        _meds = [float(r.get("median_rate") or 0) for r in str_rows if r.get("median_rate")]
        str_med_avg = (sum(_meds) / len(_meds)) if _meds else 0.0

        # 🧠 Öğrenilmiş çarpanlar (Revenue Brain kapalı döngüsü)
        lw_rows = await db.learned_pricing_weights.find(
            {"property_id": property_id, "factor": {"$ne": 1.0}},
            {"_id": 0, "bucket_key": 1, "factor": 1}).to_list(100)
        learned_map = {w["bucket_key"]: float(w["factor"]) for w in lw_rows}
        # 🗺️ Bölgesel hafıza önseli (×0.7 etki) — yerel ders yoksa bölge dersi devralınır
        _p = await db.properties.find_one({"id": property_id}, {"_id": 0, "country": 1, "city": 1})
        _region = ((_p or {}).get("country") or (_p or {}).get("city") or "diger").strip() or "diger"
        r_rows = await db.revenue_brain_regional_memory.find(
            {"region": _region, "factor": {"$ne": 1.0}},
            {"_id": 0, "bucket_key": 1, "factor": 1}).to_list(100)
        for r in r_rows:
            if r["bucket_key"] not in learned_map:
                learned_map[r["bucket_key"]] = round(1 + (float(r["factor"]) - 1) * 0.7, 4)
        # 🌍 Küresel hafıza önseli: yerel/bölgesel ders yoksa tüm otellerin dersi yarı etkiyle uygulanır
        g_rows = await db.revenue_brain_global_memory.find(
            {"factor": {"$ne": 1.0}}, {"_id": 0, "bucket_key": 1, "factor": 1}).to_list(100)
        for g in g_rows:
            if g["bucket_key"] not in learned_map:
                learned_map[g["bucket_key"]] = round(1 + (float(g["factor"]) - 1) * 0.5, 4)

        # 💰 Net RevPAR hedef fonksiyonu — karma kanal kesintisi (komisyon+ödeme+iade+promo) + CPOR
        from routes.revenue_ext.profit_pricing import _get_settings as _profit_settings, _get_rate as _comm_rate, DEFAULT_RATES as _CHS
        _ps = await _profit_settings(db, property_id)
        _mix_rows = await db.bookings.aggregate([
            {"$match": {"property_id": property_id, "status": {"$nin": ["cancelled", "no_show"]},
                        "created_at": {"$gte": (today - timedelta(days=60)).isoformat()}}},
            {"$group": {"_id": "$source", "n": {"$sum": 1}}}]).to_list(20)
        _tot = sum(r["n"] for r in _mix_rows) or 1
        _ded_pct = 0.0
        for _r in _mix_rows:
            _ch = (_r["_id"] or "direct").lower()
            if _ch not in _CHS:
                _ch = "booking" if "book" in _ch else ("expedia" if "exped" in _ch else "direct")
            _c = await _comm_rate(db, _ch, property_id)
            _ded_pct += (_r["n"] / _tot) * (_c + _ps["payment_fee_pct"] / 100
                        + _ps["refund_risk_pct"].get(_ch, 0) / 100 + _ps["promo_funding_pct"].get(_ch, 0) / 100)
        if not _mix_rows:
            _ded_pct = (await _comm_rate(db, "booking", property_id)) + _ps["payment_fee_pct"] / 100
        _cpor = float(_ps["cpor"])

        # Parallel occupancy fan-out per date
        async def _occ_for(snap):
            return snap.get("date"), await _occupancy_for_date(property_id, snap.get("date", ""), total_rooms)
        occ_results = await asyncio.gather(*[_occ_for(s) for s in snaps]) if snaps else []
        occ_map = {d: data for d, data in occ_results}

        # Build flat suggestions list — one per (date, room_type)
        suggestions: list[dict] = []
        llm_input: list[dict] = []

        for snap in snaps:
            date = snap.get("date")
            if not date:
                continue
            market_avg = float(snap.get("avg_price") or 0)
            market_min = float(snap.get("min_price") or 0)
            unavail = float(snap.get("unavailable_pct") or 0)
            occ_data = occ_map.get(date, {"occupancy_pct": 0, "bookings": 0, "total_rooms": total_rooms})
            occ_pct = float(occ_data.get("occupancy_pct") or 0)

            days_out = (datetime.strptime(date, "%Y-%m-%d").date() - today.date()).days

            str_snap = str_map.get(date)
            ref_for_str = market_avg if market_avg > 0 else base_rate_avg
            str_mult = _str_pressure_multiplier(
                float(str_snap.get("unavailable_pct") or 0),
                float(str_snap.get("median_rate") or 0),
                ref_for_str, str_med_avg) if str_snap else 1.0

            for rt in room_types:
                rt_id = rt.get("id", "")
                base = float(rt.get("base_rate", base_rate_avg) or base_rate_avg)
                current_rate = ov_map.get((date, rt_id)) or ov_map.get((date, "")) or base

                calc = compute_suggestion(
                    base_rate=base,
                    current_rate=current_rate,
                    market_avg=market_avg,
                    market_min=market_min,
                    occupancy_pct=occ_pct,
                    unavailable_pct=unavail,
                    days_out=days_out,
                    min_pct=int(cfg.get("min_rate_pct", 60)),
                    max_pct=int(cfg.get("max_rate_pct", 250)),
                    str_mult=str_mult,
                )
                # 🧠 Öğrenilmiş çarpan uygula (yön + bağlam kovasına göre)
                learned_mult = 1.0
                learned_bucket = None
                if learned_map and calc["suggested_rate"] != current_rate:
                    from routes.revenue_ext.revenue_brain import bucket_key as _bk
                    direction = "up" if calc["delta_vs_current_pct"] > 0 else "down"
                    learned_bucket = _bk(days_out, date, direction)
                    learned_mult = learned_map.get(learned_bucket, 1.0)
                    if learned_mult != 1.0:
                        adj = round(max(calc["floor_rate"], min(calc["ceil_rate"],
                                    calc["suggested_rate"] * learned_mult)), 2)
                        calc["suggested_rate"] = adj
                        if current_rate:
                            calc["delta_vs_current_pct"] = round((adj - current_rate) / current_rate * 100.0, 2)

                prev_decision = dec_map.get((date, rt_id), {})
                status = prev_decision.get("status", "pending")

                item = {
                    "id": f"{property_id}:{date}:{rt_id or 'default'}",
                    "property_id": property_id,
                    "date": date,
                    "days_out": days_out,
                    "room_type_id": rt_id,
                    "room_type_name": rt.get("name", "Standard"),
                    "base_rate": round(base, 2),
                    "current_rate": round(current_rate, 2),
                    "market_avg": round(market_avg, 2),
                    "market_min": round(market_min, 2),
                    "unavailable_pct": round(unavail, 1),
                    "str_median": float(str_snap.get("median_rate")) if str_snap else None,
                    "str_unavailable_pct": float(str_snap.get("unavailable_pct") or 0) if str_snap else None,
                    "learned_mult": round(learned_mult, 3),
                    "learned_bucket": learned_bucket if learned_mult != 1.0 else None,
                    "occupancy_pct": occ_pct,
                    "bookings": occ_data.get("bookings", 0),
                    "total_rooms": occ_data.get("total_rooms", total_rooms),
                    **calc,
                    "status": status,
                    "decision_reason": prev_decision.get("reason"),
                    "auto_apply_eligible": abs(calc["delta_vs_current_pct"]) <= float(cfg.get("auto_apply_threshold_pct", 5.0)),
                    "rationale": prev_decision.get("rationale"),
                }
                if current_rate > 0 and float(calc.get("suggested_rate") or 0) > 0:
                    _net_cur = round(current_rate * (1 - _ded_pct) - _cpor, 2)
                    _net_new = round(calc["suggested_rate"] * (1 - _ded_pct) - _cpor, 2)
                    item["net_current_rate"] = _net_cur
                    item["net_new_rate"] = _net_new
                    item["net_delta_pct"] = round((_net_new - _net_cur) / abs(_net_cur) * 100, 2) if _net_cur else None
                    if calc["suggested_rate"] != current_rate:
                        item["net_note"] = (f"NET RevPAR: £{_net_cur} → £{_net_new}"
                                            f" (kesinti %{_ded_pct * 100:.0f} + CPOR £{_cpor:.0f} düşülmüş)")
                suggestions.append(item)

                # Build LLM input for primary room type only (avoid burning tokens on duplicates)
                if rt is room_types[0] and not item.get("rationale"):
                    llm_input.append(item)

        # Optional LLM enrichment — with 12h cache to avoid re-spending tokens on every reload.
        if use_llm and cfg.get("use_llm", True) and llm_input:
            # Step 1: try cache first
            cache_dates = [i["date"] for i in llm_input]
            cache_cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
            cache_rows = await db.ai_pricing_rationale_cache.find(
                {"property_id": property_id, "date": {"$in": cache_dates},
                 "cached_at": {"$gte": cache_cutoff}},
                {"_id": 0, "date": 1, "rationale": 1},
            ).to_list(500)
            cache_hits = {c["date"]: c["rationale"] for c in cache_rows}

            # Apply cache hits and shrink the LLM payload to true misses
            misses = [i for i in llm_input if i["date"] not in cache_hits]
            for s in suggestions:
                if not s.get("rationale") and s["date"] in cache_hits:
                    s["rationale"] = cache_hits[s["date"]]

            # Step 2: call LLM only for cache misses
            if misses:
                rationales = await _llm_rationales(misses[:30], symbol)
                if rationales:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    bulk_ops = []
                    for d, txt in rationales.items():
                        bulk_ops.append({"property_id": property_id, "date": d,
                                          "rationale": txt, "cached_at": now_iso})
                    # Upsert each rationale (small N=<=30 so safe to do sequentially via update_many alternative)
                    for op in bulk_ops:
                        await db.ai_pricing_rationale_cache.update_one(
                            {"property_id": property_id, "date": op["date"]},
                            {"$set": op},
                            upsert=True,
                        )
                    for s in suggestions:
                        if not s.get("rationale") and s["date"] in rationales:
                            s["rationale"] = rationales[s["date"]]

        try:
            from routes.revenue_ext.los_wash_metrics import compute_los_tiers
            los_tiers = (await compute_los_tiers(db, property_id)).get("suggested_tiers", [])
        except Exception:
            los_tiers = []
        return {
            "property_id": property_id,
            "currency": currency,
            "currency_symbol": symbol,
            "horizon_days": days,
            "config": cfg,
            "suggestions": suggestions,
            "los_tiers": los_tiers,
            "summary": _summarize(suggestions, cfg),
        }

    def _summarize(suggestions: list, cfg: dict) -> dict:
        if not suggestions:
            return {"total": 0, "auto_eligible": 0, "outside_threshold": 0, "avg_delta_pct": 0,
                    "uplift_estimate": 0, "pending": 0, "accepted": 0, "rejected": 0}
        total = len(suggestions)
        auto_ok = sum(1 for s in suggestions if s["auto_apply_eligible"])
        outside = total - auto_ok
        avg_delta = round(sum(s["delta_vs_current_pct"] for s in suggestions) / total, 2)
        uplift = round(sum((s["suggested_rate"] - s["current_rate"]) for s in suggestions), 2)
        return {
            "total": total,
            "auto_eligible": auto_ok,
            "outside_threshold": outside,
            "avg_delta_pct": avg_delta,
            "uplift_estimate": uplift,
            "pending": sum(1 for s in suggestions if s["status"] == "pending"),
            "accepted": sum(1 for s in suggestions if s["status"] == "accepted"),
            "rejected": sum(1 for s in suggestions if s["status"] == "rejected"),
            "auto_applied": sum(1 for s in suggestions if s["status"] == "auto-applied"),
        }

    async def _apply_one(property_id: str, item: dict, source: str, rationale: Optional[str] = None) -> None:
        """Write a single suggestion to rate_overrides and log decision."""
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.rate_overrides.update_one(
            {"property_id": property_id, "date": item["date"], "room_type_id": item.get("room_type_id", "")},
            {"$set": {
                "property_id": property_id,
                "room_type_id": item.get("room_type_id", ""),
                "date": item["date"],
                "custom_rate": float(item["suggested_rate"]),
                "set_by": source,
                "reason": (
                    f"AI Pricing · ref £{item.get('ref_price')} × lead {item.get('lead_time_mult')} "
                    f"× occ {item.get('occupancy_mult')}"
                    + (f" × STR {item.get('str_mult')}" if (item.get('str_mult') or 1.0) != 1.0 else "")
                    + (f" × öğrenilmiş {item.get('learned_mult')}" if (item.get('learned_mult') or 1.0) != 1.0 else "")
                    + f" → {item['suggested_rate']}"
                ),
                "updated_at": now_iso,
            }},
            upsert=True,
        )
        await db.ai_pricing_decisions.update_one(
            {"property_id": property_id, "date": item["date"], "room_type_id": item.get("room_type_id", "")},
            {"$set": {
                "property_id": property_id,
                "date": item["date"],
                "room_type_id": item.get("room_type_id", ""),
                "room_type_name": item.get("room_type_name"),
                "prev_rate": item.get("current_rate"),
                "new_rate": float(item["suggested_rate"]),
                "delta_pct": item.get("delta_vs_current_pct"),
                "market_avg": item.get("market_avg"),
                "occupancy_pct": item.get("occupancy_pct"),
                "days_out": item.get("days_out"),
                "status": "auto-applied" if source == "ai-pricing-auto" else "accepted",
                "set_by": source,
                "str_mult": item.get("str_mult", 1.0),
                "str_median": item.get("str_median"),
                "str_unavailable_pct": item.get("str_unavailable_pct"),
                "learned_mult": item.get("learned_mult", 1.0),
                "learned_bucket": item.get("learned_bucket"),
                "net_prev_rate": item.get("net_current_rate"),
                "net_new_rate": item.get("net_new_rate"),
                "net_delta_pct": item.get("net_delta_pct"),
                "rationale": ((rationale or item.get("rationale") or "")
                              + ((" · " + item["net_note"]) if item.get("net_note") else "")) or None,
                "decided_at": now_iso,
            }},
            upsert=True,
        )

    async def _detect_anomaly(property_id: str, suggestions: list):
        """Anomali tespiti: rakip verisi saçmalaması veya OTB ani sıçraması."""
        for s in suggestions[:80]:
            ma, br = float(s.get("market_avg") or 0), float(s.get("base_rate") or 0)
            if ma and br and (ma < br * 0.35 or ma > br * 3.0):
                return f"Rakip verisi anormal: {s['date']} pazar ort £{ma:.0f} vs baz fiyat £{br:.0f}"
        now = datetime.now(timezone.utc)
        cnts = []
        for i in range(8):
            d0 = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            d1 = (now - timedelta(days=i - 1)).strftime("%Y-%m-%d")
            c = await db.bookings.count_documents(
                {"property_id": property_id, "created_at": {"$gte": d0, "$lt": d1}})
            cnts.append(c)
        prior_avg = sum(cnts[1:]) / 7
        if cnts[0] >= 5 and cnts[0] > 3 * max(prior_avg, 0.5):
            return f"OTB ani sıçrama: bugün {cnts[0]} rezervasyon (7 gün ort. {prior_avg:.1f}) — talep şoku olabilir"
        return None

    async def _handle_anomaly(property_id: str, cfg: dict, suggestions: list):
        """Anomali varsa moda göre işlem: human=dondur+onay iste, auto=bildir+devam. (frozen, reason) döner."""
        import uuid as _uuid
        now_iso = datetime.now(timezone.utc).isoformat()
        frozen = await db.pricing_freeze.find_one({"property_id": property_id, "active": True}, {"_id": 0})
        if frozen and cfg.get("anomaly_mode", "human") == "human":
            return True, frozen.get("reason")
        anomaly = await _detect_anomaly(property_id, suggestions)
        if not anomaly:
            return False, None
        if cfg.get("anomaly_mode", "human") == "human":
            await db.pricing_freeze.update_one(
                {"property_id": property_id},
                {"$set": {"property_id": property_id, "active": True, "reason": anomaly,
                          "frozen_at": now_iso}}, upsert=True)
            await db.notifications.insert_one({
                "id": str(_uuid.uuid4()), "type": "warning",
                "title": "İnsan onayı gerekli — fiyat oto-uygulama donduruldu",
                "message": f"{anomaly}. Robot fiyatları dondurdu; kontrol edip 'Dondurmayı Kaldır' ile devam ettirin.",
                "category": "revenue", "target_user": "", "target_role": "manager",
                "link_to": "revenue", "priority": "high", "read": False,
                "created_by": "Anomali Guardrail", "created_at": now_iso})
            return True, anomaly
        await db.notifications.insert_one({
            "id": str(_uuid.uuid4()), "type": "info",
            "title": "Anomali algılandı (otomatik mod)",
            "message": f"{anomaly}. Mod 'otomatik' olduğu için uygulamaya devam edildi — izlemede.",
            "category": "revenue", "target_user": "", "target_role": "manager",
            "link_to": "revenue", "priority": "normal", "read": False,
            "created_by": "Anomali Guardrail", "created_at": now_iso})
        return False, anomaly

    # ---------------- ROUTES ----------------

    @router.get("/revenue/ai-pricing/{property_id}/config")
    async def get_config(property_id: str,
                          _u: dict = Depends(require_roles("admin", "manager"))):
        cfg = await _get_cfg(property_id)
        cfg["freeze"] = await db.pricing_freeze.find_one(
            {"property_id": property_id, "active": True}, {"_id": 0})
        return cfg

    @router.post("/revenue/ai-pricing/{property_id}/rollback-last")
    async def rollback_last(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Tek Tık Toplu Geri Alma — son otomatik/toplu fiyat koşusunu eski değerlere döndürür."""
        import uuid as _uuid
        last = await db.ai_pricing_run_log.find_one(
            {"property_id": property_id, "applied": {"$gt": 0}}, {"_id": 0}, sort=[("run_at", -1)])
        if not last:
            return {"ok": False, "reverted": 0, "reason": "Geri alınacak koşu bulunamadı"}
        run_at = last["run_at"]
        lo = run_at[:16]
        decs = await db.ai_pricing_decisions.find(
            {"property_id": property_id, "status": {"$in": ["auto-applied", "accepted"]},
             "decided_at": {"$gte": lo}}, {"_id": 0}).to_list(500)
        reverted = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        for d in decs:
            prev = d.get("prev_rate")
            if prev is None:
                continue
            await db.rate_overrides.update_one(
                {"property_id": property_id, "date": d["date"], "room_type_id": d.get("room_type_id", "")},
                {"$set": {"custom_rate": float(prev), "set_by": "rollback",
                          "reason": f"Toplu geri alma ({current_user.get('email', '')}) — {run_at[:16]} koşusu",
                          "updated_at": now_iso}})
            await db.ai_pricing_decisions.update_one(
                {"property_id": property_id, "date": d["date"], "room_type_id": d.get("room_type_id", "")},
                {"$set": {"status": "rolled-back", "rolled_back_at": now_iso}})
            reverted += 1
        await db.notifications.insert_one({
            "id": str(_uuid.uuid4()), "type": "info",
            "title": "Toplu geri alma tamamlandı",
            "message": f"{reverted} fiyat, {run_at[:16]} koşusu öncesi değerlere döndürüldü.",
            "category": "revenue", "target_user": "", "target_role": "manager",
            "link_to": "revenue", "priority": "normal", "read": False,
            "created_by": current_user.get("email", ""), "created_at": now_iso})
        return {"ok": True, "reverted": reverted, "run_at": run_at}

    @router.post("/revenue/ai-pricing/{property_id}/unfreeze")
    async def unfreeze(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.pricing_freeze.update_one(
            {"property_id": property_id},
            {"$set": {"active": False, "cleared_by": current_user.get("email", ""),
                      "cleared_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True}

    @router.put("/revenue/ai-pricing/{property_id}/config")
    async def put_config(property_id: str, data: Dict,
                          _u: dict = Depends(require_roles("admin", "manager"))):
        payload = {
            "property_id": property_id,
            "enabled": bool(data.get("enabled", True)),
            "auto_apply": bool(data.get("auto_apply", False)),
            "experiment_holdout_pct": max(0.0, min(float(data.get("experiment_holdout_pct", 0) or 0), 30)),
            "auto_apply_threshold_pct": max(0.5, min(25.0, float(data.get("auto_apply_threshold_pct", 5.0)))),
            "use_llm": bool(data.get("use_llm", True)),
            "min_rate_pct": max(10, min(100, int(data.get("min_rate_pct", 60)))),
            "max_rate_pct": max(100, min(500, int(data.get("max_rate_pct", 250)))),
            "days_horizon": max(1, min(540, int(data.get("days_horizon", 30)))),
            "target_updates_per_day": max(1, min(24, int(data.get("target_updates_per_day", 12)))),
            "anomaly_mode": data.get("anomaly_mode") if data.get("anomaly_mode") in ("human", "auto") else "human",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.ai_pricing_config.update_one(
            {"property_id": property_id},
            {"$set": payload},
            upsert=True,
        )
        return await _get_cfg(property_id)

    @router.get("/revenue/ai-pricing/{property_id}/suggestions")
    async def list_suggestions(property_id: str, days: int = 30, use_llm: bool = True,
                                _u: dict = Depends(require_roles("admin", "manager"))):
        days = max(1, min(540, int(days)))
        return await _build_suggestions(property_id, days, use_llm)

    @router.get("/revenue/ai-pricing/{property_id}/cadence")
    async def cadence(property_id: str,
                      _u: dict = Depends(require_roles("admin", "manager"))):
        cfg = await _get_cfg(property_id)
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        runs = await db.ai_pricing_run_log.find(
            {"property_id": property_id, "run_at": {"$gte": today_start}},
            {"_id": 0, "applied": 1, "run_at": 1, "source": 1},
        ).sort("run_at", -1).to_list(100)
        return {
            "property_id": property_id,
            "runs_today": len(runs),
            "applied_today": sum(r.get("applied", 0) for r in runs),
            "target_updates_per_day": int(cfg.get("target_updates_per_day", 12)),
            "last_run_at": cfg.get("last_run_at"),
            "horizon_days": int(cfg.get("days_horizon", 30)),
            "recent_runs": runs[:10],
        }

    @router.post("/revenue/ai-pricing/{property_id}/accept")
    async def accept_suggestion(property_id: str, data: Dict,
                                 _u: dict = Depends(require_roles("admin", "manager"))):
        """Accept one or many suggestions. Body: { items: [{date, room_type_id, suggested_rate, ... }] }
        If `items` omitted, accept ALL auto_apply_eligible suggestions in the horizon.
        """
        items = data.get("items")
        cfg = await _get_cfg(property_id)
        if not items:
            payload = await _build_suggestions(property_id, int(cfg.get("days_horizon", 30)), use_llm=False)
            items = [s for s in payload["suggestions"] if s["auto_apply_eligible"] and s["status"] == "pending"]

        from routes.revenue_ext.hurdle_lrv import compute_lrv_floor
        from routes.revenue_ext.min_rate_floors import effective_bounds_map, clamp_to_bounds
        lrv_map = await compute_lrv_floor(db, property_id, int(cfg.get("days_horizon", 30)))
        min_map = await effective_bounds_map(
            db, property_id, [it.get("date", "") for it in items])
        applied, lrv_clamped, min_clamped = 0, 0, 0
        for it in items:
            floor = lrv_map.get(it.get("date", ""))
            if floor and float(it["suggested_rate"]) < floor:
                it["suggested_rate"] = floor
                it["rationale"] = (it.get("rationale") or "") + f" · LRV guardrail: fiyat £{floor} tabanına yükseltildi"
                lrv_clamped += 1
            bounds = min_map.get(it.get("date", ""), {})
            res = clamp_to_bounds(float(it["suggested_rate"]), bounds)
            if res["clamped"]:
                it["suggested_rate"] = res["rate"]
                it["rationale"] = (it.get("rationale") or "") + f" · Fiyat koruması ({res['reason']}): £{res['rate']} sınırına ayarlandı"
                min_clamped += 1
            await _apply_one(property_id, it, source="ai-pricing-manual", rationale=it.get("rationale"))
            applied += 1
        return {"accepted": applied, "lrv_clamped": lrv_clamped, "min_rate_clamped": min_clamped}

    @router.post("/revenue/ai-pricing/{property_id}/reject")
    async def reject_suggestion(property_id: str, data: Dict,
                                 _u: dict = Depends(require_roles("admin", "manager"))):
        """Reject one suggestion. Body: { date, room_type_id?, reason }"""
        date = data.get("date")
        if not date:
            raise HTTPException(status_code=400, detail="date is required")
        room_type_id = data.get("room_type_id", "")
        reason = (data.get("reason") or "").strip() or "Manuel reddedildi"
        await db.ai_pricing_decisions.update_one(
            {"property_id": property_id, "date": date, "room_type_id": room_type_id},
            {"$set": {
                "property_id": property_id,
                "date": date,
                "room_type_id": room_type_id,
                "status": "rejected",
                "reason": reason,
                "decided_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        return {"status": "rejected", "date": date, "reason": reason}

    @router.post("/revenue/ai-pricing/{property_id}/run-auto-apply")
    async def run_auto_apply(property_id: str,
                              _u: dict = Depends(require_roles("admin", "manager"))):
        """Compute fresh suggestions and silently apply all that fall within the auto_apply_threshold.
        This is the endpoint called by:
          - The 'Auto-Apply Şimdi Çalıştır' button in UI
          - The daily cron job (registered by server.py scheduler)
        """
        cfg = await _get_cfg(property_id)
        if not cfg.get("enabled") or not cfg.get("auto_apply"):
            await db.ai_pricing_run_log.insert_one({
                "property_id": property_id, "applied": 0,
                "source": "skipped-disabled",
                "run_at": datetime.now(timezone.utc).isoformat()})
            return {"applied": 0, "skipped_reason": "auto_apply disabled", "config": cfg}

        days = int(cfg.get("days_horizon", 30))
        payload = await _build_suggestions(property_id, days, use_llm=False)
        frozen, freeze_reason = await _handle_anomaly(property_id, cfg, payload["suggestions"])
        if frozen:
            await db.ai_pricing_run_log.insert_one({
                "property_id": property_id, "applied": 0, "source": "frozen-anomaly",
                "reason": freeze_reason, "run_at": datetime.now(timezone.utc).isoformat()})
            return {"applied": 0, "frozen": True, "freeze_reason": freeze_reason,
                    "summary": payload["summary"]}
        from routes.revenue_ext.hurdle_lrv import compute_lrv_floor
        lrv_map = await compute_lrv_floor(db, property_id, days)
        applied = 0
        lrv_clamped = 0
        holdout_n = 0
        import random as _rnd
        hpct = float(cfg.get("experiment_holdout_pct", 0) or 0)
        for s in payload["suggestions"]:
            if s["status"] != "pending":
                continue
            if not s["auto_apply_eligible"]:
                continue
            # extra guardrail: don't bother if the change is < 0.5%
            if abs(s["delta_vs_current_pct"]) < 0.5:
                continue
            if hpct > 0 and _rnd.random() * 100 < hpct:
                # A/B deney: bu karar HOLDOUT — fiyat uygulanmaz, nedensel kıyas için saklanır
                await db.ai_pricing_decisions.update_one(
                    {"property_id": property_id, "date": s["date"], "room_type_id": s.get("room_type_id", "")},
                    {"$set": {"property_id": property_id, "date": s["date"],
                              "room_type_id": s.get("room_type_id", ""),
                              "room_type_name": s.get("room_type_name"),
                              "prev_rate": s.get("current_rate"), "new_rate": float(s["suggested_rate"]),
                              "delta_pct": s.get("delta_vs_current_pct"), "days_out": s.get("days_out"),
                              "status": "holdout", "set_by": "experiment",
                              "decided_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
                holdout_n += 1
                continue
            floor = lrv_map.get(s.get("date", ""))
            if floor and float(s["suggested_rate"]) < floor:
                s["suggested_rate"] = floor
                s["rationale"] = (s.get("rationale") or "") + f" · LRV guardrail: fiyat £{floor} tabanına yükseltildi"
                lrv_clamped += 1
            await _apply_one(property_id, s, source="ai-pricing-auto", rationale=s.get("rationale"))
            applied += 1

        now_iso = datetime.now(timezone.utc).isoformat()
        await db.ai_pricing_config.update_one(
            {"property_id": property_id},
            {"$set": {
                "last_run_at": now_iso,
                "last_auto_applied": applied,
                "last_pending": payload["summary"]["pending"] - applied,
            }},
            upsert=True,
        )
        await db.ai_pricing_run_log.insert_one({
            "property_id": property_id, "applied": applied,
            "source": "manual-or-cron", "run_at": now_iso})
        return {"applied": applied, "lrv_clamped": lrv_clamped, "summary": payload["summary"], "run_at": now_iso}

    @router.get("/revenue/ai-pricing/{property_id}/history")
    async def history(property_id: str, limit: int = 200,
                       _u: dict = Depends(require_roles("admin", "manager"))):
        limit = max(1, min(1000, int(limit)))
        rows = await db.ai_pricing_decisions.find(
            {"property_id": property_id},
            {"_id": 0},
        ).sort("decided_at", -1).limit(limit).to_list(limit)
        return {"property_id": property_id, "count": len(rows), "items": rows}

    # ---- Internal helper exposed on the router for the scheduler cron ----
    async def _internal_auto_apply(property_id: str) -> dict:
        cfg = await _get_cfg(property_id)
        if not cfg.get("enabled") or not cfg.get("auto_apply"):
            return {"applied": 0, "skipped_reason": "auto_apply disabled"}
        days = int(cfg.get("days_horizon", 30))
        payload = await _build_suggestions(property_id, days, use_llm=False)
        frozen, freeze_reason = await _handle_anomaly(property_id, cfg, payload["suggestions"])
        if frozen:
            return {"applied": 0, "frozen": True, "freeze_reason": freeze_reason}
        from routes.revenue_ext.hurdle_lrv import compute_lrv_floor
        lrv_map = await compute_lrv_floor(db, property_id, days)
        applied = 0
        for s in payload["suggestions"]:
            if s["status"] != "pending":
                continue
            if not s["auto_apply_eligible"]:
                continue
            if abs(s["delta_vs_current_pct"]) < 0.5:
                continue
            floor = lrv_map.get(s.get("date", ""))
            if floor and float(s["suggested_rate"]) < floor:
                s["suggested_rate"] = floor
                s["rationale"] = (s.get("rationale") or "") + f" · LRV guardrail: fiyat £{floor} tabanına yükseltildi"
            await _apply_one(property_id, s, source="ai-pricing-auto", rationale=s.get("rationale"))
            applied += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.ai_pricing_config.update_one(
            {"property_id": property_id},
            {"$set": {
                "last_run_at": now_iso,
                "last_auto_applied": applied,
                "last_pending": payload["summary"]["pending"] - applied,
            }},
            upsert=True,
        )
        await db.ai_pricing_run_log.insert_one({
            "property_id": property_id, "applied": applied,
            "source": "scheduler", "run_at": now_iso})
        return {"applied": applied, "summary": payload["summary"], "run_at": now_iso}

    router.run_auto_apply_internal = _internal_auto_apply
    return router
