"""
Cross-Channel Sentiment Heatmap.

Aggregates guest-facing text from ALL channels (reviews, inbox messages,
mid-stay surveys, post-stay surveys) and produces:
  • Per-channel sentiment score + volume
  • Topic × sentiment heatmap (e.g. "cleanliness ↔ negative" cell count)
  • Trend line (daily sentiment over N days)
  • Top complaints + top praises (ranked quotes)

Heuristic keyword-based sentiment + topic extraction (fast, $0 cost).
Optional LLM "summarize" for drilldown.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
import logging
import re

logger = logging.getLogger(__name__)


# ---------- Sentiment lexicon ----------
# English + Turkish mixed lexicon, scored [-2..+2]
POSITIVE_WORDS = {
    "excellent": 2, "amazing": 2, "perfect": 2, "wonderful": 2, "fantastic": 2,
    "great": 1.5, "lovely": 1.5, "beautiful": 1.5, "clean": 1.5, "friendly": 1.5,
    "good": 1, "nice": 1, "comfortable": 1, "quiet": 1, "helpful": 1, "warm": 1,
    "mükemmel": 2, "harika": 2, "muhteşem": 2, "süper": 2,
    "çok iyi": 1.5, "temiz": 1.5, "güzel": 1.5, "konforlu": 1, "rahat": 1,
    "iyi": 1, "teşekkür": 1, "beğendim": 1.5,
    "love": 2, "loved": 2, "recommend": 1.5, "recommended": 1.5,
}

NEGATIVE_WORDS = {
    "terrible": -2, "horrible": -2, "awful": -2, "disgusting": -2, "nightmare": -2,
    "bad": -1.5, "dirty": -1.5, "rude": -1.5, "slow": -1, "noisy": -1,
    "cold": -0.5, "broken": -1.5, "leak": -1.5, "smell": -1, "disappointed": -1.5,
    "berbat": -2, "rezalet": -2, "iğrenç": -2, "kirli": -1.5, "kaba": -1.5,
    "kötü": -1.5, "yavaş": -1, "gürültülü": -1, "soğuk": -0.5, "bozuk": -1.5,
    "koku": -1, "hayal kırıklığı": -1.5,
    "never": -1, "hate": -2, "worst": -2, "unacceptable": -2,
}

# Topics (lemma → regex or keyword set)
TOPICS = {
    "Temizlik / Cleanliness": [
        r"clean", r"dirty", r"hygien", r"dust", r"smell", r"bathroom",
        r"temiz", r"kirli", r"koku", r"banyo",
    ],
    "Personel / Staff": [
        r"staff", r"reception", r"waiter", r"host", r"rude", r"friendly",
        r"personel", r"resepsiyon", r"garson", r"kaba", r"nazik",
    ],
    "Oda / Room": [
        r"room", r"bed", r"mattress", r"pillow", r"furniture",
        r"oda", r"yatak", r"minder", r"mobilya",
    ],
    "Yemek / F&B": [
        r"breakfast", r"food", r"meal", r"restaurant", r"dinner", r"menu",
        r"kahvaltı", r"yemek", r"restoran", r"menü",
    ],
    "Konum / Location": [
        r"location", r"area", r"nearby", r"beach", r"centre", r"station",
        r"konum", r"merkez", r"plaj", r"istasyon",
    ],
    "Fiyat / Value": [
        r"price", r"value", r"expensive", r"cheap", r"worth",
        r"fiyat", r"değer", r"pahalı", r"ucuz",
    ],
    "Gürültü / Noise": [
        r"noise", r"quiet", r"loud", r"music",
        r"gürültü", r"sessiz", r"yüksek sesli",
    ],
    "Wi-Fi / Internet": [
        r"wifi", r"wi-fi", r"internet", r"signal",
    ],
    "Check-in / Check-out": [
        r"check.?in", r"check.?out", r"front desk",
        r"giriş", r"çıkış", r"resepsiyon işlemleri",
    ],
    "Klima / Comfort": [
        r"ac\b", r"air cond", r"heating", r"hot", r"cold", r"temperature",
        r"klima", r"ısıtma", r"sıcaklık",
    ],
}


def _score_text(text: str) -> Dict:
    """Return {score, positives:[], negatives:[], topics:[]}."""
    if not text:
        return {"score": 0, "positives": [], "negatives": [], "topics": []}
    lower = text.lower()
    score = 0.0
    positives, negatives = [], []
    for word, s in POSITIVE_WORDS.items():
        cnt = lower.count(word)
        if cnt > 0:
            score += s * cnt
            positives.append(word)
    for word, s in NEGATIVE_WORDS.items():
        cnt = lower.count(word)
        if cnt > 0:
            score += s * cnt
            negatives.append(word)

    # Topics (any pattern hit = topic match)
    topics = []
    for topic, patterns in TOPICS.items():
        for p in patterns:
            if re.search(p, lower):
                topics.append(topic)
                break
    return {
        "score": round(score, 2),
        "positives": positives,
        "negatives": negatives,
        "topics": topics,
    }


def _band(score: float) -> str:
    if score >= 2:
        return "positive"
    if score <= -2:
        return "negative"
    return "neutral"


def create_sentiment_router(db, require_roles):
    router = APIRouter()

    async def _gather_sources(property_id: str, since: datetime) -> List[Dict]:
        """Pull text from reviews, inbox, mid-stay surveys, post-stay surveys."""
        since_iso = since.isoformat()
        rows = []

        # Reviews
        try:
            reviews = await db.reviews.find(
                {"property_id": property_id, "created_at": {"$gte": since_iso}},
                {"_id": 0}
            ).limit(1000).to_list(1000)
            for r in reviews:
                rows.append({
                    "source": "review",
                    "channel": r.get("source") or r.get("channel") or "review",
                    "created_at": r.get("created_at"),
                    "text": (r.get("review_text") or r.get("content") or r.get("comment") or ""),
                    "author": r.get("author_name") or r.get("guest_name"),
                    "rating": r.get("rating") or r.get("overall_rating"),
                    "_id": r.get("id"),
                })
        except Exception as ex:
            logger.debug(f"reviews pull: {ex}")

        # Unified inbox messages (guest-originated)
        for coll in ("unified_inbox", "inbox_messages", "guest_messages"):
            try:
                msgs = await db[coll].find(
                    {"property_id": property_id, "created_at": {"$gte": since_iso},
                     "direction": {"$in": ["inbound", "in", "incoming"]}},
                    {"_id": 0}
                ).limit(500).to_list(500)
                for m in msgs:
                    rows.append({
                        "source": "inbox",
                        "channel": m.get("channel") or m.get("source") or "inbox",
                        "created_at": m.get("created_at"),
                        "text": m.get("body") or m.get("text") or m.get("message") or "",
                        "author": m.get("from") or m.get("guest_name"),
                        "_id": m.get("id"),
                    })
            except Exception as ex:
                logger.debug(f"{coll} pull: {ex}")

        # Mid-stay + post-stay surveys
        for coll in ("mid_stay_responses", "survey_responses", "post_stay_surveys"):
            try:
                surveys = await db[coll].find(
                    {"property_id": property_id, "created_at": {"$gte": since_iso}},
                    {"_id": 0}
                ).limit(500).to_list(500)
                for s in surveys:
                    text = s.get("comments") or s.get("text") or s.get("feedback") or ""
                    if not text:
                        # Concatenate open-ended answers if stored per-q
                        answers = s.get("answers") or []
                        if isinstance(answers, list):
                            text = " | ".join(
                                str(a.get("answer") or a.get("value") or "")
                                for a in answers if isinstance(a, dict)
                            )
                    rows.append({
                        "source": "survey",
                        "channel": coll.replace("_", "-"),
                        "created_at": s.get("created_at"),
                        "text": text,
                        "author": s.get("guest_name"),
                        "rating": s.get("nps") or s.get("rating"),
                        "_id": s.get("id"),
                    })
            except Exception as ex:
                logger.debug(f"{coll} pull: {ex}")

        return rows

    @router.get("/sentiment/heatmap/{property_id}")
    async def sentiment_heatmap(property_id: str, days: int = 30,
                                current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Full cross-channel sentiment analysis."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = await _gather_sources(property_id, since)

        # Score each row
        for r in rows:
            r["_analysis"] = _score_text(r.get("text", ""))
            r["_band"] = _band(r["_analysis"]["score"])

        # Channel breakdown
        by_channel = {}
        for r in rows:
            ch = r["channel"]
            d = by_channel.setdefault(ch, {"count": 0, "avg": 0.0, "pos": 0, "neu": 0, "neg": 0, "score_sum": 0})
            d["count"] += 1
            d["score_sum"] += r["_analysis"]["score"]
            d[r["_band"][:3]] += 1
        for ch, d in by_channel.items():
            d["avg"] = round(d["score_sum"] / d["count"], 2) if d["count"] else 0
            del d["score_sum"]

        # Topic × sentiment matrix
        topic_matrix = {}
        for r in rows:
            for t in r["_analysis"]["topics"]:
                cell = topic_matrix.setdefault(t, {"positive": 0, "neutral": 0, "negative": 0, "total": 0})
                cell[r["_band"]] += 1
                cell["total"] += 1

        # Trend line (daily)
        daily = {}
        for r in rows:
            try:
                day = (r.get("created_at") or "")[:10]
                if not day:
                    continue
                d = daily.setdefault(day, {"count": 0, "score_sum": 0})
                d["count"] += 1
                d["score_sum"] += r["_analysis"]["score"]
            except Exception:
                pass
        trend = [
            {"date": day, "count": d["count"], "avg": round(d["score_sum"] / d["count"], 2) if d["count"] else 0}
            for day, d in sorted(daily.items())
        ]

        # Top complaints + praises (ranked)
        complaints = sorted(
            [r for r in rows if r["_band"] == "negative" and r.get("text")],
            key=lambda r: r["_analysis"]["score"]
        )[:10]
        praises = sorted(
            [r for r in rows if r["_band"] == "positive" and r.get("text")],
            key=lambda r: -r["_analysis"]["score"]
        )[:10]

        def _snippet(r):
            text = (r.get("text") or "").strip()
            return {
                "id": r.get("_id"),
                "text": text[:300] + ("…" if len(text) > 300 else ""),
                "score": r["_analysis"]["score"],
                "channel": r["channel"],
                "author": r.get("author"),
                "topics": r["_analysis"]["topics"],
                "created_at": r.get("created_at"),
            }

        # Overall score
        total_score = sum(r["_analysis"]["score"] for r in rows)
        overall_avg = round(total_score / len(rows), 2) if rows else 0
        positives = sum(1 for r in rows if r["_band"] == "positive")
        negatives = sum(1 for r in rows if r["_band"] == "negative")
        nps_like = round((positives - negatives) / max(1, len(rows)) * 100, 1)

        return {
            "property_id": property_id,
            "window_days": days,
            "total_responses": len(rows),
            "overall_avg": overall_avg,
            "overall_band": _band(overall_avg),
            "positive_count": positives,
            "neutral_count": sum(1 for r in rows if r["_band"] == "neutral"),
            "negative_count": negatives,
            "nps_like": nps_like,
            "by_channel": by_channel,
            "topic_matrix": topic_matrix,
            "trend": trend,
            "top_complaints": [_snippet(r) for r in complaints],
            "top_praises": [_snippet(r) for r in praises],
        }

    @router.get("/sentiment/drilldown/{property_id}")
    async def sentiment_drilldown(property_id: str, topic: str, days: int = 30,
                                  band: Optional[str] = None,
                                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """All responses mentioning `topic`, optionally filtered by band."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = await _gather_sources(property_id, since)

        matches = []
        for r in rows:
            a = _score_text(r.get("text", ""))
            if topic not in a["topics"]:
                continue
            b = _band(a["score"])
            if band and b != band:
                continue
            matches.append({
                "source": r["source"],
                "channel": r["channel"],
                "text": r["text"][:500],
                "score": a["score"],
                "band": b,
                "author": r.get("author"),
                "created_at": r.get("created_at"),
            })

        matches.sort(key=lambda x: x["score"])  # negatives first
        return {"topic": topic, "band_filter": band, "count": len(matches), "rows": matches[:100]}

    return router
