"""
AI Revenue Strategist — Gelir Strateji Robotu. Geçmişi, mevcut OTB durumunu,
piyasayı (rakip fiyatları), etkinlikleri ve yapılan RM aksiyonlarını toplar;
LLM ile yorumlatıp "mevcut durum → yapılanlar → yapılması gerekenler" strateji
raporu üretir. Önerilen fiyat aksiyonları tek tıkla rate_overrides'a uygulanır;
auto_apply açıksa düşük riskli (≤%15) fiyat değişimleri otomatik uygulanır.
Collections: strategist_reports, strategist_config
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict
import uuid
import json
import os
import logging

logger = logging.getLogger(__name__)

HORIZONS = (30, 90, 365)
LANGS = ("tr", "en")
ACTION_TYPES = ("price_increase", "price_decrease", "restriction", "campaign", "monitor")
AUTO_APPLY_MAX_CHANGE_PCT = 15.0
DEFAULT_CFG = {"auto_apply": False, "language": "tr", "horizon_days": 90}


def _iso():
    return datetime.now(timezone.utc).isoformat()


async def _get_cfg(db, pid: str) -> Dict:
    doc = await db.strategist_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    return {**DEFAULT_CFG, **{k: doc[k] for k in DEFAULT_CFG if k in doc}}


async def _occ_map(db, pid: str, start: ddate, end: ddate) -> Dict[str, Dict]:
    """date -> {rooms_sold, revenue} between start (incl) and end (excl)."""
    out: Dict[str, Dict] = {}
    bookings = await db.bookings.find({
        "property_id": pid, "status": {"$in": ["confirmed", "checked_in", "checked_out"]},
        "check_in": {"$lt": end.isoformat()}, "check_out": {"$gt": start.isoformat()},
    }, {"_id": 0, "check_in": 1, "check_out": 1, "rate_per_night": 1, "rooms": 1}).to_list(20000)
    for b in bookings:
        try:
            ci = ddate.fromisoformat(b["check_in"][:10])
            co = ddate.fromisoformat(b["check_out"][:10])
        except Exception:
            continue
        rooms = max(int(b.get("rooms", 1) or 1), 1)
        rate = float(b.get("rate_per_night", 0) or 0)
        d = max(ci, start)
        while d < co and d < end:
            k = d.isoformat()
            slot = out.setdefault(k, {"rooms_sold": 0, "revenue": 0.0})
            slot["rooms_sold"] += rooms
            slot["revenue"] += rate * rooms
            d += timedelta(days=1)
    return out


async def _gather_intel(db, pid: str, horizon: int) -> Dict:
    today = ddate.today()
    end = today + timedelta(days=horizon)

    total_rooms = 0
    base_rate = 100.0
    async for rt in db.room_types.find({"property_id": pid}, {"_id": 0, "total_rooms": 1, "base_rate": 1}):
        total_rooms += int(rt.get("total_rooms", 0) or 0)
        if rt.get("base_rate"):
            base_rate = float(rt["base_rate"])
    total_rooms = max(total_rooms, 1)

    # Forward OTB + comp rates + own rate
    fwd = await _occ_map(db, pid, today, end)
    ov_docs = await db.rate_overrides.find(
        {"property_id": pid, "date": {"$gte": today.isoformat(), "$lt": end.isoformat()}},
        {"_id": 0, "date": 1, "custom_rate": 1}).to_list(1000)
    ov_map = {o["date"]: float(o["custom_rate"]) for o in ov_docs if o.get("custom_rate")}

    comp_by_date: Dict[str, list] = {}
    async for s in db.comp_rate_snapshots.find(
            {"property_id": pid, "date": {"$gte": today.isoformat(), "$lt": end.isoformat()}},
            {"_id": 0, "date": 1, "rate": 1}):
        comp_by_date.setdefault(s["date"], []).append(float(s.get("rate", 0) or 0))

    daily = []
    for i in range(horizon):
        d = (today + timedelta(days=i)).isoformat()
        sold = fwd.get(d, {}).get("rooms_sold", 0)
        comps = sorted(comp_by_date.get(d, []))
        comp_median = comps[len(comps) // 2] if comps else None
        own = ov_map.get(d, base_rate)
        daily.append({
            "date": d, "occ_pct": round(sold / total_rooms * 100, 1),
            "rooms_sold": sold, "own_rate": round(own, 2),
            "comp_median": round(comp_median, 2) if comp_median else None,
            "gap_pct": round((comp_median - own) / comp_median * 100, 1) if comp_median else None,
        })

    # Past 30 days performance
    p_start = today - timedelta(days=30)
    past = await _occ_map(db, pid, p_start, today)
    p_sold = sum(v["rooms_sold"] for v in past.values())
    p_rev = sum(v["revenue"] for v in past.values())
    past_perf = {
        "occ_pct": round(p_sold / (total_rooms * 30) * 100, 1),
        "adr": round(p_rev / p_sold, 2) if p_sold else 0,
        "revenue": round(p_rev, 2), "room_nights": p_sold,
    }

    # STLY: same forward window last year
    ly_start, ly_end = today - timedelta(days=365), end - timedelta(days=365)
    stly = await _occ_map(db, pid, ly_start, ly_end)
    s_sold = sum(v["rooms_sold"] for v in stly.values())
    s_rev = sum(v["revenue"] for v in stly.values())
    stly_perf = {
        "occ_pct": round(s_sold / (total_rooms * horizon) * 100, 1),
        "adr": round(s_rev / s_sold, 2) if s_sold else 0, "room_nights": s_sold,
    }

    # Future events — Event Robot (market_events: talep skoru, etki, katılım)
    events = await db.market_events.find(
        {"property_id": {"$in": [pid, "all"]},
         "date": {"$gte": today.isoformat(), "$lt": end.isoformat()}},
        {"_id": 0, "name": 1, "date": 1, "end_date": 1, "category": 1, "impact": 1,
         "hotel_demand_score": 1, "estimated_attendance": 1, "visitor_origin": 1,
         "reasoning": 1}).sort("hotel_demand_score", -1).to_list(200)
    event_score_by_date: Dict[str, int] = {}
    for e in events:
        try:
            es = ddate.fromisoformat(e["date"][:10])
            ee = ddate.fromisoformat((e.get("end_date") or e["date"])[:10])
        except Exception:
            continue
        d = es
        while d <= ee:
            k = d.isoformat()
            event_score_by_date[k] = max(event_score_by_date.get(k, 0),
                                         int(e.get("hotel_demand_score", 0) or 0))
            d += timedelta(days=1)

    # Market occupancy — Market Robot supply scans (pazar doluluk baskısı)
    market_occ: Dict[str, float] = {}
    try:
        pipeline = [
            {"$match": {"property_id": {"$in": [pid, "all"]},
                        "date": {"$gte": today.isoformat(), "$lt": end.isoformat()}}},
            {"$sort": {"scanned_at": -1}},
            {"$group": {"_id": "$date", "unavailable_pct": {"$first": "$unavailable_pct"}}},
        ]
        async for row in db.market_supply.aggregate(pipeline):
            market_occ[row["_id"]] = float(row.get("unavailable_pct", 0) or 0)
    except Exception as e:
        logger.warning(f"market_supply aggregate failed: {e}")

    # Pickup — son 7 günde alınan rezervasyonlar (talep hızı)
    pk_since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    pickup_7d = await db.bookings.count_documents({
        "property_id": pid, "created_at": {"$gte": pk_since},
        "status": {"$in": ["confirmed", "checked_in"]}})

    # İptal & no-show trendi (son 30 gün oluşturulan rezervasyonlar üzerinden)
    c_since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    created_30d = await db.bookings.count_documents({"property_id": pid, "created_at": {"$gte": c_since}})
    cancelled_30d = await db.bookings.count_documents({
        "property_id": pid, "created_at": {"$gte": c_since}, "status": "cancelled"})
    noshow_30d = await db.bookings.count_documents({
        "property_id": pid, "created_at": {"$gte": c_since}, "status": "no_show"})
    fwd_cancelled = await db.bookings.count_documents({
        "property_id": pid, "status": "cancelled",
        "check_in": {"$gte": today.isoformat(), "$lt": end.isoformat()}})
    cancellations = {
        "cancel_rate_30d_pct": round(cancelled_30d / created_30d * 100, 1) if created_30d else 0,
        "cancelled_30d": cancelled_30d, "noshow_30d": noshow_30d,
        "created_30d": created_30d, "fwd_period_cancellations": fwd_cancelled,
    }

    # Lead time dağılımı (son 60 günde oluşturulan rezervasyonlar)
    lt_since = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    lt_buckets = {"0-3": 0, "4-7": 0, "8-14": 0, "15-30": 0, "31-60": 0, "60+": 0}
    leads = []
    async for b in db.bookings.find(
            {"property_id": pid, "created_at": {"$gte": lt_since},
             "status": {"$in": ["confirmed", "checked_in", "checked_out"]}},
            {"_id": 0, "created_at": 1, "check_in": 1}).limit(5000):
        try:
            lead = (ddate.fromisoformat(b["check_in"][:10]) -
                    ddate.fromisoformat(b["created_at"][:10])).days
        except Exception:
            continue
        lead = max(lead, 0)
        leads.append(lead)
        if lead <= 3:
            lt_buckets["0-3"] += 1
        elif lead <= 7:
            lt_buckets["4-7"] += 1
        elif lead <= 14:
            lt_buckets["8-14"] += 1
        elif lead <= 30:
            lt_buckets["15-30"] += 1
        elif lead <= 60:
            lt_buckets["31-60"] += 1
        else:
            lt_buckets["60+"] += 1
    leads.sort()
    lead_time = {
        "median_days": leads[len(leads) // 2] if leads else None,
        "buckets": lt_buckets, "sample": len(leads),
    }

    # daily satırlarına pazar doluluğu ve etkinlik skoru ekle
    for x in daily:
        x["market_occ_pct"] = market_occ.get(x["date"])
        x["event_score"] = event_score_by_date.get(x["date"], 0)

    # Actions taken (last 14 days)
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    ov_recent = await db.rate_overrides.count_documents({"property_id": pid, "set_at": {"$gte": since}})
    campaigns = await db.gap_campaigns.find({"property_id": pid}, {"_id": 0, "name": 1, "created_at": 1}).sort("created_at", -1).to_list(5)
    intraday = await db.intraday_reprice_events.count_documents({"property_id": pid, "created_at": {"$gte": since}})
    restr = await db.restriction_recommendations.count_documents({"property_id": pid, "created_at": {"$gte": since}})
    lost = await db.lost_demand.find({"property_id": pid}, {"_id": 0, "reason": 1, "est_lost_revenue": 1}).sort("created_at", -1).to_list(200)
    lost_rev = round(sum(float(x.get("est_lost_revenue", 0) or 0) for x in lost), 2)

    fwd_sold = sum(x["rooms_sold"] for x in daily)
    gaps = [x["gap_pct"] for x in daily if x["gap_pct"] is not None]
    underpriced = [x for x in daily if (x["gap_pct"] or 0) >= 8]
    potential = round(sum(((x["comp_median"] or 0) - x["own_rate"]) * max(total_rooms - x["rooms_sold"], 0) * 0.3
                          for x in underpriced), 2)
    mo_vals = list(market_occ.values())
    high_events = [e for e in events if int(e.get("hotel_demand_score", 0) or 0) >= 40
                   or (e.get("impact") in ("major", "high", "significant"))]

    return {
        "total_rooms": total_rooms, "base_rate": base_rate, "horizon": horizon,
        "daily": daily, "past_perf": past_perf, "stly_perf": stly_perf,
        "events": events[:25], "high_impact_events": high_events[:10],
        "pickup_7d": pickup_7d, "cancellations": cancellations, "lead_time": lead_time,
        "actions_taken": {"rate_overrides_14d": ov_recent, "intraday_events_14d": intraday,
                          "restriction_recs_14d": restr, "recent_campaigns": campaigns,
                          "lost_demand_records": len(lost), "lost_demand_revenue": lost_rev},
        "kpis": {
            "fwd_occ_pct": round(fwd_sold / (total_rooms * horizon) * 100, 1),
            "avg_market_gap_pct": round(sum(gaps) / len(gaps), 1) if gaps else None,
            "avg_market_occ_pct": round(sum(mo_vals) / len(mo_vals), 1) if mo_vals else None,
            "underpriced_dates": len(underpriced),
            "high_impact_events": len(high_events),
            "cancel_rate_30d_pct": cancellations["cancel_rate_30d_pct"],
            "median_lead_time_days": lead_time["median_days"],
            "potential_extra_revenue": potential,
            "max_observed_comp_rate": max((x["comp_median"] or 0) for x in daily) if daily else 0,
        },
    }


def _bucketize(daily, horizon):
    """Compact daily rows for LLM: daily for <=30d, weekly buckets beyond."""
    def _mkt(x):
        return f", pazar doluluk %{x['market_occ_pct']}" if x.get("market_occ_pct") is not None else ""

    def _ev(x):
        return f", ETKİNLİK (talep skoru {x['event_score']})" if x.get("event_score") else ""

    if horizon <= 35:
        return [f"{x['date']}: doluluk %{x['occ_pct']}, fiyat €{x['own_rate']}, rakip medyan "
                f"{'€' + str(x['comp_median']) if x['comp_median'] else 'veri yok'}{_mkt(x)}{_ev(x)}"
                for x in daily]
    lines = []
    for i in range(0, len(daily), 7):
        wk = daily[i:i + 7]
        occ = round(sum(w["occ_pct"] for w in wk) / len(wk), 1)
        own = round(sum(w["own_rate"] for w in wk) / len(wk), 2)
        comps = [w["comp_median"] for w in wk if w["comp_median"]]
        cm = round(sum(comps) / len(comps), 2) if comps else None
        mos = [w["market_occ_pct"] for w in wk if w.get("market_occ_pct") is not None]
        mo = f", pazar doluluk %{round(sum(mos) / len(mos), 1)}" if mos else ""
        evs = max((w.get("event_score") or 0) for w in wk)
        ev = f", ETKİNLİK haftası (maks skor {evs})" if evs else ""
        lines.append(f"{wk[0]['date']} – {wk[-1]['date']}: ort. doluluk %{occ}, ort. fiyat €{own}, "
                     f"rakip medyan {'€' + str(cm) if cm else 'veri yok'}{mo}{ev}")
    return lines


def _build_prompt(intel: Dict, language: str) -> str:
    ev_lines = []
    for e in intel["events"][:20]:
        score = e.get("hotel_demand_score", 0)
        att = e.get("estimated_attendance")
        ev_lines.append(
            f"- {e.get('name', 'Etkinlik')} ({e.get('date')}"
            f"{' → ' + e['end_date'] if e.get('end_date') and e['end_date'] != e.get('date') else ''}) · "
            f"kategori: {e.get('category', '?')} · otel talep skoru: {score}/100 · etki: {e.get('impact', '?')}"
            f"{' · katılım ~' + str(att) if att else ''}"
            f"{' · ziyaretçi: ' + e['visitor_origin'] if e.get('visitor_origin') else ''}"
            f"{' · not: ' + e['reasoning'][:100] if e.get('reasoning') else ''}")
    ev = "\n".join(ev_lines) or "- Kayıtlı etkinlik yok"
    at = intel["actions_taken"]
    camp = ", ".join(c.get("name", "") for c in at["recent_campaigns"]) or "yok"
    rows = "\n".join(_bucketize(intel["daily"], intel["horizon"]))
    k = intel["kpis"]
    mo = f"%{k['avg_market_occ_pct']}" if k.get("avg_market_occ_pct") is not None else "veri yok"
    lang_line = "Raporu TÜRKÇE yaz." if language == "tr" else "Write the report in ENGLISH."
    return f"""OTEL VERİLERİ (kapasite: {intel['total_rooms']} oda, baz fiyat €{intel['base_rate']}):

GELECEK {intel['horizon']} GÜN (tarih bazlı: kendi doluluk / kendi fiyat / rakip medyan / pazar doluluk / etkinlik):
{rows}

GEÇMİŞ 30 GÜN PERFORMANS: doluluk %{intel['past_perf']['occ_pct']}, ADR €{intel['past_perf']['adr']}, gelir €{intel['past_perf']['revenue']}
GEÇEN YIL AYNI DÖNEM (STLY): doluluk %{intel['stly_perf']['occ_pct']}, ADR €{intel['stly_perf']['adr']}
TALEP HIZI: son 7 günde {intel['pickup_7d']} yeni rezervasyon (pickup)
İPTAL & NO-SHOW TRENDİ (son 30 gün): iptal oranı %{intel['cancellations']['cancel_rate_30d_pct']} ({intel['cancellations']['cancelled_30d']} iptal, {intel['cancellations']['noshow_30d']} no-show / {intel['cancellations']['created_30d']} rezervasyon) · ileri dönemde {intel['cancellations']['fwd_period_cancellations']} iptal mevcut
LEAD TIME DAĞILIMI (son 60 gün, {intel['lead_time']['sample']} rezervasyon, medyan {intel['lead_time']['median_days']} gün): {', '.join(f"{k} gün: {v}" for k, v in intel['lead_time']['buckets'].items())}
PAZAR DOLULUĞU (Market Robot taraması, şehir geneli ort.): {mo}

ETKİNLİK ROBOTU VERİLERİ (yaklaşan etkinlikler — talep skorlarıyla):
{ev}

SON 14 GÜNDE YAPILAN RM AKSİYONLARI:
- Fiyat güncellemeleri: {at['rate_overrides_14d']} · Gün içi repricing: {at['intraday_events_14d']} · Kısıtlama önerileri: {at['restriction_recs_14d']}
- Kampanyalar: {camp}
- Kayıp talep: {at['lost_demand_records']} kayıt, tahmini €{at['lost_demand_revenue']} kaçan gelir

ÖZET KPI: ileri dönem doluluk %{k['fwd_occ_pct']}, ort. pazar farkı %{k['avg_market_gap_pct']}, pazar altı gün sayısı {k['underpriced_dates']}, yüksek etkili etkinlik sayısı {k['high_impact_events']}, potansiyel ek gelir €{k['potential_extra_revenue']}, gözlenen maksimum rakip fiyat €{k['max_observed_comp_rate']}

GÖREV: Fiyata etki edecek TÜM etkenleri birlikte değerlendir — etkinlikler (talep skorlarına göre), pazar doluluğu (arz baskısı), rakip fiyat konumu, kendi doluluk/pace, pickup hızı, iptal/no-show trendi (net talebi düşürür), lead time dağılımı (talep penceresine göre fiyatlama zamanlaması), geçmiş/STLY trendi, kayıp talep. Geliri POZİTİF ve NEGATİF etkileyecek unsurları açıkça ayır ve stratejiyi bu etkenlere dayandır. Etkinlik günlerinde talep skoru yüksekse fiyat yukarı esnekliğini, pazar doluluğu düşükken agresif fiyatın riskini mutlaka değerlendir. Lead time kısaysa (son dakika pazarı) erken indirimin gereksizliğini, iptal oranı yüksekse overbooking/sıkı iptal politikası ihtiyacını değerlendir.

{lang_line}
SADECE geçerli JSON döndür (markdown yok, kod bloğu yok):
{{
 "situation_report": "mevcut durumun kapsamlı yorumu (doluluk, fiyat konumu, pace, pazar)",
 "market_analysis": "piyasa, pazar doluluğu ve rakip analizi + maksimum satılabilir fiyat değerlendirmesi",
 "past_performance": "geçmiş + STLY karşılaştırma yorumu",
 "what_was_done": "yapılan RM aksiyonlarının değerlendirmesi",
 "positive_factors": ["geliri POZİTİF etkileyecek etken 1 (ör. etkinlik, pazar doluluğu, talep)", "..."],
 "negative_factors": ["geliri NEGATİF etkileyecek etken 1 (ör. zayıf pace, arz fazlası, düşük sezon)", "..."],
 "risks": ["risk 1", "risk 2"],
 "opportunities": ["fırsat 1", "fırsat 2"],
 "recommendations": [
   {{"title": "kısa başlık", "detail": "somut, sayısal gerekçeli öneri (hangi etkene dayandığını belirt)",
     "action_type": "price_increase|price_decrease|restriction|campaign|monitor",
     "date_start": "YYYY-MM-DD", "date_end": "YYYY-MM-DD",
     "target_rate": 150.0, "priority": "high|medium|low", "expected_impact": "beklenen etki"}}
 ]
}}
target_rate sadece fiyat aksiyonlarında zorunlu. En az 3, en fazla 8 öneri ver."""


SYSTEM_PROMPT = """You are the AI Revenue Strategist robot of MyHotelBox & ReveniQ — a senior hotel revenue management director. You analyze past performance, current on-the-books position, market/competitor rates, occupancy, upcoming events and previously taken actions, then produce a decisive strategy report with concrete, number-backed recommendations. Always consider ALL factors together (market, history, competitors, occupancy, future events, maximum sellable rate). Be specific with dates and euro amounts. Return ONLY valid JSON exactly in the requested schema."""


def _parse_llm_json(text: str) -> Dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        if t.startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON in LLM response")
    return json.loads(t[start:end + 1])


async def _apply_price_action(db, pid: str, action: Dict, source: str, user: str) -> Dict:
    target = float(action.get("target_rate") or 0)
    if target <= 0:
        raise HTTPException(400, "target_rate gerekli")
    try:
        d = ddate.fromisoformat(action["date_start"])
        d_end = ddate.fromisoformat(action.get("date_end") or action["date_start"])
    except Exception:
        raise HTTPException(400, "Geçersiz tarih aralığı")
    now = _iso()
    days = 0
    while d <= d_end and days < 120:
        await db.rate_overrides.update_one(
            {"property_id": pid, "date": d.isoformat()},
            {"$set": {"property_id": pid, "date": d.isoformat(), "custom_rate": round(target, 2),
                      "source": source, "set_by": user, "set_at": now,
                      "context": {"strategist_action": action.get("id"), "title": action.get("title", "")}}},
            upsert=True)
        d += timedelta(days=1)
        days += 1
    return {"dates_updated": days, "rate": round(target, 2)}


def create_revenue_strategist_router(db, require_roles):
    router = APIRouter(prefix="/strategist")

    async def run_analysis(pid: str, horizon: int, language: str, trigger: str, user: str) -> Dict:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        intel = await _gather_intel(db, pid, horizon)
        prompt = _build_prompt(intel, language)
        chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
                       session_id=f"strategist-{pid}-{uuid.uuid4().hex[:8]}",
                       system_message=SYSTEM_PROMPT).with_model("openai", "gpt-5.2")
        raw = await chat.send_message(UserMessage(text=prompt))
        parsed = _parse_llm_json(raw)

        recs = []
        for r in (parsed.get("recommendations") or [])[:8]:
            if r.get("action_type") not in ACTION_TYPES:
                r["action_type"] = "monitor"
            recs.append({"id": str(uuid.uuid4())[:8], "status": "suggested", **r})

        cfg = await _get_cfg(db, pid)
        auto_applied = 0
        if cfg["auto_apply"]:
            for r in recs:
                if r["action_type"] in ("price_increase", "price_decrease") and r.get("target_rate"):
                    cur = intel["base_rate"]
                    change_pct = abs(float(r["target_rate"]) - cur) / cur * 100 if cur else 100
                    if change_pct <= AUTO_APPLY_MAX_CHANGE_PCT:
                        try:
                            await _apply_price_action(db, pid, r, "ai-strategist-auto", "strategist-robot")
                            r["status"] = "auto_applied"
                            r["applied_at"] = _iso()
                            auto_applied += 1
                        except Exception as e:
                            logger.warning(f"Strategist auto-apply failed: {e}")

        report = {
            "id": str(uuid.uuid4()), "property_id": pid, "horizon_days": horizon,
            "language": language, "trigger": trigger, "created_by": user,
            "situation_report": parsed.get("situation_report", ""),
            "market_analysis": parsed.get("market_analysis", ""),
            "past_performance": parsed.get("past_performance", ""),
            "what_was_done": parsed.get("what_was_done", ""),
            "positive_factors": parsed.get("positive_factors", []),
            "negative_factors": parsed.get("negative_factors", []),
            "risks": parsed.get("risks", []), "opportunities": parsed.get("opportunities", []),
            "recommendations": recs, "kpis": intel["kpis"],
            "events_considered": [{"name": e.get("name"), "date": e.get("date"),
                                   "score": e.get("hotel_demand_score", 0),
                                   "impact": e.get("impact")} for e in intel["high_impact_events"]],
            "auto_applied_count": auto_applied, "created_at": _iso(),
        }
        await db.strategist_reports.insert_one(dict(report))
        report.pop("_id", None)
        return report

    @router.get("/{pid}/config")
    async def get_config(pid: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _get_cfg(db, pid)

    @router.put("/{pid}/config")
    async def put_config(pid: str, payload: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        upd = {}
        if "auto_apply" in payload:
            upd["auto_apply"] = bool(payload["auto_apply"])
        if payload.get("language") in LANGS:
            upd["language"] = payload["language"]
        if payload.get("horizon_days") in HORIZONS:
            upd["horizon_days"] = int(payload["horizon_days"])
        if upd:
            await db.strategist_config.update_one(
                {"property_id": pid}, {"$set": {**upd, "property_id": pid, "updated_at": _iso()}}, upsert=True)
        return await _get_cfg(db, pid)

    @router.post("/{pid}/analyze")
    async def analyze(pid: str, payload: Dict = None,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        payload = payload or {}
        cfg = await _get_cfg(db, pid)
        horizon = payload.get("horizon_days") if payload.get("horizon_days") in HORIZONS else cfg["horizon_days"]
        language = payload.get("language") if payload.get("language") in LANGS else cfg["language"]
        try:
            return await run_analysis(pid, horizon, language, "manual", current_user.get("email", ""))
        except json.JSONDecodeError:
            raise HTTPException(502, "AI yanıtı çözümlenemedi — lütfen tekrar deneyin")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Strategist analyze error: {e}")
            raise HTTPException(502, f"Analiz başarısız: {str(e)[:150]}")

    @router.get("/{pid}/reports")
    async def list_reports(pid: str, limit: int = 10,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        items = await db.strategist_reports.find({"property_id": pid}, {"_id": 0}).sort(
            "created_at", -1).to_list(min(limit, 30))
        return {"items": items}

    @router.post("/{pid}/reports/{rid}/actions/{aid}/apply")
    async def apply_action(pid: str, rid: str, aid: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        rep = await db.strategist_reports.find_one({"id": rid, "property_id": pid}, {"_id": 0})
        if not rep:
            raise HTTPException(404, "Rapor bulunamadı")
        action = next((a for a in rep.get("recommendations", []) if a["id"] == aid), None)
        if not action:
            raise HTTPException(404, "Aksiyon bulunamadı")
        if action.get("status") in ("applied", "auto_applied"):
            raise HTTPException(400, "Aksiyon zaten uygulanmış")

        result = {}
        user = current_user.get("email", "")
        if action["action_type"] in ("price_increase", "price_decrease"):
            result = await _apply_price_action(db, pid, action, "ai-strategist", user)
        elif action["action_type"] == "restriction":
            await db.restriction_recommendations.insert_one({
                "id": str(uuid.uuid4()), "property_id": pid, "source": "ai-strategist",
                "date_start": action.get("date_start"), "date_end": action.get("date_end"),
                "title": action.get("title", ""), "detail": action.get("detail", ""),
                "status": "pending", "created_at": _iso()})
            result = {"queued": "restriction_recommendations"}
        elif action["action_type"] == "campaign":
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "property_id": pid, "type": "strategist_campaign",
                "title": f"AI Strateji: {action.get('title', 'Kampanya önerisi')}",
                "message": action.get("detail", ""), "read": False, "created_at": _iso()})
            result = {"queued": "gap_filler_suggestion"}
        else:
            result = {"noted": True}

        await db.strategist_reports.update_one(
            {"id": rid, "recommendations.id": aid},
            {"$set": {"recommendations.$.status": "applied",
                      "recommendations.$.applied_at": _iso(),
                      "recommendations.$.applied_by": user}})
        return {"ok": True, "action_type": action["action_type"], **result}

    @router.post("/{pid}/reports/{rid}/actions/{aid}/dismiss")
    async def dismiss_action(pid: str, rid: str, aid: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.strategist_reports.update_one(
            {"id": rid, "property_id": pid, "recommendations.id": aid},
            {"$set": {"recommendations.$.status": "dismissed"}})
        if res.matched_count == 0:
            raise HTTPException(404, "Aksiyon bulunamadı")
        return {"ok": True}

    async def run_internal(property_id: str = "") -> dict:
        """Scheduler job: weekly auto strategy report per property."""
        pids = [property_id] if property_id else [p["id"] async for p in db.properties.find({}, {"_id": 0, "id": 1})]
        done = 0
        for pid in pids:
            try:
                cfg = await _get_cfg(db, pid)
                await run_analysis(pid, cfg["horizon_days"], cfg["language"], "scheduled", "strategist-robot")
                done += 1
            except Exception as e:
                logger.warning(f"Scheduled strategist run failed for {pid}: {e}")
        return {"ok": True, "reports_generated": done}

    router.run_internal = run_internal
    return router
