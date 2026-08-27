"""Sosyal Sentiment Fiyat Katmanı — yorum duyarlılığını talep sinyali olarak fiyata besler (Duetto paritesi)."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict
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

    return router
