"""Sosyal Sentiment Fiyat Katmanı — yorum duyarlılığını talep sinyali olarak fiyata besler (Duetto paritesi)."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict
import os
import uuid

ACTOR = "sentiment-pricing"


def _now():
    return datetime.now(timezone.utc)


async def analyze_sentiment(db, pid: str) -> Dict:
    since90 = (_now() - timedelta(days=90)).isoformat()
    since30 = (_now() - timedelta(days=30)).isoformat()
    q = {"review_date": {"$gte": since90}}
    if pid != "all":
        q["property_id"] = pid
    rows = await db.reviews.find(q, {"_id": 0, "rating": 1, "review_date": 1,
                                     "review_text": 1, "platform": 1,
                                     "guest_name": 1}).to_list(2000)
    if not rows:
        return {"index": None, "reviews_90d": 0}
    recent = [r for r in rows if r["review_date"] >= since30]
    prior = [r for r in rows if r["review_date"] < since30]
    avg_all = sum(r.get("rating", 0) for r in rows) / len(rows)
    avg_recent = sum(r.get("rating", 0) for r in recent) / len(recent) if recent else avg_all
    avg_prior = sum(r.get("rating", 0) for r in prior) / len(prior) if prior else avg_all
    trend = round(avg_recent - avg_prior, 2)
    index = round(max(0, min(avg_all / 5 * 80 + trend * 20 + min(len(rows) / 5, 10), 100)), 0)
    if index >= 80 and trend >= 0:
        adj, signal = 4.0, "güçlü itibar — fiyat gücünüz var, %4 artış taşınabilir"
    elif index >= 70:
        adj, signal = 2.0, "sağlıklı itibar — ölçülü %2 artış denenebilir"
    elif index >= 45:
        adj, signal = 0.0, "nötr itibar — fiyatı itibar üzerinden değiştirmeyin"
    else:
        adj, signal = -2.0, "zayıf itibar — artıştan kaçının, önce yorum sorunlarını çözün"
    low_recent = sorted([r for r in recent if r.get("rating", 5) <= 3],
                        key=lambda x: x["review_date"], reverse=True)[:3]
    return {"index": index, "avg_rating": round(avg_all, 2),
            "avg_recent_30d": round(avg_recent, 2), "trend": trend,
            "reviews_90d": len(rows), "reviews_30d": len(recent),
            "suggested_adj_pct": adj, "signal": signal,
            "risk_reviews": [{"guest": r.get("guest_name", ""), "rating": r.get("rating"),
                              "text": (r.get("review_text") or "")[:140],
                              "platform": r.get("platform", "")} for r in low_recent]}


async def run_theme_analysis(db, pid: str) -> Dict:
    """Yorum metinlerini LLM ile tema bazında analiz eder ve günlük cache'ler."""
    from fastapi import HTTPException as _HE
    cached = await db.sentiment_themes.find_one(
        {"property_id": pid, "day": _now().date().isoformat()}, {"_id": 0})
    if cached:
        return cached
    since = (_now() - timedelta(days=90)).isoformat()
    q = {"review_date": {"$gte": since}, "review_text": {"$ne": ""}}
    if pid != "all":
        q["property_id"] = pid
    rows = await db.reviews.find(q, {"_id": 0, "rating": 1, "review_text": 1}).sort(
        "review_date", -1).to_list(40)
    if len(rows) < 3:
        raise _HE(422, "Tema analizi için en az 3 metinli yorum gerekli")
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise _HE(503, "LLM anahtarı yok")
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import json as _json
    corpus = "\n".join(f"[{r.get('rating')}★] {(r.get('review_text') or '')[:220]}"
                       for r in rows)
    chat = LlmChat(api_key=api_key, session_id=f"themes-{uuid.uuid4()}",
                   system_message="Otel yorumlarını tema bazında analiz et. SADECE JSON döndür.").with_model("openai", "gpt-5.2")
    prompt = f"""Aşağıdaki otel yorumlarını analiz et. SADECE şu JSON'u döndür:
{{"themes": [{{"theme": "temizlik|personel|konum|konfor|fiyat|kahvaltı", "score": 0-100, "mentions": sayı, "summary": "1 cümle Türkçe özet"}}], "pricing_note": "Bu temaların fiyat gücüne etkisi hakkında 1-2 cümle Türkçe değerlendirme"}}
Yorumlar:
{corpus}"""
    reply = await chat.send_message(UserMessage(text=prompt))
    cleaned = reply.strip().strip("```json").strip("```").strip()
    parsed = _json.loads(cleaned)
    prev = await db.sentiment_themes.find_one(
        {"property_id": pid, "day": {"$lt": _now().date().isoformat()}},
        {"_id": 0, "themes": 1, "day": 1}, sort=[("day", -1)])
    themes = parsed.get("themes", [])
    alerts = []
    if prev:
        prev_scores = {t["theme"]: t.get("score", 0) for t in prev.get("themes", [])}
        for t in themes:
            old = prev_scores.get(t["theme"])
            if old is not None:
                t["delta"] = round(t.get("score", 0) - old, 0)
                if t["delta"] <= -10:
                    alerts.append(f"{t['theme']} puanı {old}→{t['score']} düştü")
    doc = {"property_id": pid, "day": _now().date().isoformat(),
           "week": _now().strftime("%G-W%V"), "themes": themes,
           "pricing_note": parsed.get("pricing_note", ""),
           "alerts": alerts, "reviews_analyzed": len(rows),
           "created_at": _now().isoformat()}
    await db.sentiment_themes.update_one(
        {"property_id": pid, "day": doc["day"]}, {"$set": doc}, upsert=True)
    if alerts:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "title": "⚠️ Yorum teması düşüşte",
            "message": f"{pid}: " + "; ".join(alerts) + " — fiyat gücünü etkileyebilir.",
            "category": "revenue", "priority": "high", "read": False,
            "created_at": _now().isoformat()})
    return doc


async def sentiment_theme_loop(db):
    """Haftada bir tüm oteller için tema analizini otomatik koşar (ISO hafta idempotent)."""
    import asyncio
    while True:
        try:
            week = _now().strftime("%G-W%V")
            for p in await db.properties.find({}, {"_id": 0, "id": 1}).to_list(50):
                if await db.sentiment_themes.find_one(
                        {"property_id": p["id"], "week": week}, {"_id": 1}):
                    continue
                try:
                    await run_theme_analysis(db, p["id"])
                except Exception:
                    pass
        except Exception:
            pass
        await asyncio.sleep(12 * 3600)


def create_sentiment_pricing_router(db, require_roles):
    router = APIRouter(prefix="/sentiment-pricing", tags=["sentiment-pricing"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def get_analysis(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        a = await analyze_sentiment(db, pid)
        applies = await db.sentiment_pricing_applies.find(
            {"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(5)
        return {"property_id": pid, **a, "applies": applies,
                "note": "Endeks = ortalama puan (%80 ağırlık) + 30 günlük trend + hacim bonusu. Sinyal fiyat motoruna önümüzdeki 30 gün için % ayar olarak uygulanabilir."}

    @router.post("/{pid}/apply")
    async def apply(pid: str, data: Dict = None, u: dict = Depends(require_roles(*ROLES))):
        a = await analyze_sentiment(db, pid)
        adj = float((data or {}).get("adj_pct", a.get("suggested_adj_pct") or 0) or 0)
        adj = max(-5.0, min(adj, 5.0))
        if adj == 0:
            raise HTTPException(422, "Sıfır ayar uygulanamaz — sinyal nötr")
        from routes.revenue_ext.write_lease import acquire_lease
        rts = await db.room_types.find(
            {"property_id": pid}, {"_id": 0, "id": 1, "base_price": 1}).to_list(50)
        today = ddate.today()
        written, skipped = 0, 0
        for i in range(1, 31):
            day = (today + timedelta(days=i)).isoformat()
            for rt in rts:
                rt_id = rt.get("id", "")
                ex = await db.rate_overrides.find_one(
                    {"property_id": pid, "room_type_id": rt_id, "date": day},
                    {"_id": 0, "set_by": 1, "custom_rate": 1})
                sb = (ex or {}).get("set_by") or ""
                if ex and (sb in ("event-intelligence", "owner-override")
                           or "@" in sb or " " in sb):
                    skipped += 1
                    continue
                cur = float((ex or {}).get("custom_rate") or rt.get("base_price") or 0)
                if cur <= 0:
                    continue
                if await acquire_lease(db, pid, rt_id, day, ACTOR) is None:
                    skipped += 1
                    continue
                await db.rate_overrides.update_one(
                    {"property_id": pid, "room_type_id": rt_id, "date": day},
                    {"$set": {"custom_rate": round(cur * (1 + adj / 100), 0),
                              "set_by": ACTOR,
                              "reason": f"Sentiment sinyali (endeks {a.get('index')}, {adj:+g}%)",
                              "updated_at": _now().isoformat()}}, upsert=True)
                written += 1
        log = {"id": str(uuid.uuid4()), "property_id": pid, "adj_pct": adj,
               "index": a.get("index"), "written": written, "skipped": skipped,
               "by": u.get("name") or u.get("email", ""), "created_at": _now().isoformat()}
        await db.sentiment_pricing_applies.insert_one(dict(log))
        try:
            from routes.revenue_ext.reprice_bridge import fire_reprice
            fire_reprice(db, pid, "sentiment_apply", log["id"])
        except Exception:
            pass
        log.pop("_id", None)
        return {"ok": True, **log}

    @router.post("/{pid}/analyze-themes")
    async def analyze_themes(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Yorum metinlerini AI ile tema bazında analiz eder (temizlik, personel, konum...)."""
        return await run_theme_analysis(db, pid)

    @router.get("/{pid}/theme-trends")
    async def theme_trends(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        snaps = await db.sentiment_themes.find(
            {"property_id": pid}, {"_id": 0}).sort("day", -1).to_list(12)
        snaps.reverse()
        series: Dict = {}
        for s in snaps:
            for t in s.get("themes", []):
                series.setdefault(t["theme"], []).append(
                    {"day": s["day"], "score": t.get("score", 0)})
        trends = []
        for theme, pts in series.items():
            delta = round(pts[-1]["score"] - pts[-2]["score"], 0) if len(pts) >= 2 else None
            trends.append({"theme": theme, "points": pts,
                           "latest": pts[-1]["score"], "delta": delta,
                           "alert": delta is not None and delta <= -10})
        trends.sort(key=lambda x: (x["delta"] if x["delta"] is not None else 0))
        return {"property_id": pid, "snapshots": len(snaps), "trends": trends,
                "note": "Haftalık otomatik analiz + manuel analizler. 10+ puan düşüş yüksek öncelikli bildirim üretir."}

    return router
