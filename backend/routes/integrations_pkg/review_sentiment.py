"""
Review Sentiment AI (P1) — uses Emergent LLM Key / Claude Sonnet 4.5 to extract
themes + sentiment from reviews. Caches results in `review_sentiments` to avoid
re-processing.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import os
import json
import uuid
import logging

logger = logging.getLogger(__name__)


def create_sentiment_router(db, require_roles, LlmChat, UserMessage):
    router = APIRouter()

    @router.post("/reviews/sentiment/analyze")
    async def analyze(data: Dict,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Batch-analyze up to 50 reviews. Body: {property_id, review_ids: [..]} or {property_id, limit: 50}"""
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="LLM key not configured")

        property_id = data.get("property_id", "")
        q = {"property_id": property_id} if property_id and property_id != "all" else {}
        if data.get("review_ids"):
            q["id"] = {"$in": data["review_ids"]}
        limit = int(data.get("limit", 50))
        reviews = await db.reviews.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
        if not reviews:
            return {"analyzed": 0, "themes": [], "sentiments": []}

        # Skip already-analyzed ones
        existing = await db.review_sentiments.find(
            {"review_id": {"$in": [r.get("id") for r in reviews if r.get("id")]}},
            {"_id": 0, "review_id": 1}
        ).to_list(5000)
        done_ids = {r["review_id"] for r in existing}
        pending = [r for r in reviews if r.get("id") and r.get("id") not in done_ids][:20]

        results = []
        if pending:
            compact = [{"id": r["id"], "text": (r.get("review_text") or r.get("content") or "")[:600], "rating": r.get("rating")} for r in pending]
            prompt = (
                "For each review below, return JSON {\"items\":[{\"id\":...,\"sentiment\":\"positive|neutral|negative\",\"score\":-1..1,\"themes\":[\"dirty_bathroom\",\"slow_checkin\"]}]}\n"
                "Themes must be lowercase_snake_case from this allowed set: clean, dirty_bathroom, dirty_room, friendly_staff, rude_staff, slow_checkin, fast_checkin, noisy, quiet, great_location, poor_location, comfortable_bed, uncomfortable_bed, great_breakfast, poor_breakfast, good_value, overpriced, wifi_issues, amenities_issue, parking_issue, other.\n"
                "Return ONLY valid JSON.\n\nReviews:\n" + json.dumps(compact)
            )
            try:
                chat = LlmChat(
                    api_key=api_key, session_id=f"sentiment-{uuid.uuid4()}",
                    system_message="You are a hotel review sentiment & theme extractor. Output ONLY JSON.",
                ).with_model("anthropic", "claude-sonnet-4-5-20250929")
                reply = await chat.send_message(UserMessage(text=prompt))
                # Strip code fences if present
                txt = reply.strip()
                if txt.startswith("```"):
                    txt = txt.split("```", 2)[1].lstrip("json").strip()
                    if txt.endswith("```"):
                        txt = txt[:-3]
                parsed = json.loads(txt)
                for it in parsed.get("items", []):
                    record = {
                        "id": str(uuid.uuid4()),
                        "review_id": it.get("id"),
                        "sentiment": it.get("sentiment", "neutral"),
                        "score": float(it.get("score", 0) or 0),
                        "themes": it.get("themes", []) or [],
                        "analyzed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    await db.review_sentiments.insert_one(record)
                    record.pop("_id", None)
                    results.append(record)
            except Exception as e:
                logger.warning(f"Sentiment AI failed: {e}")

        return {"analyzed": len(results), "pending_skipped": max(0, len(pending) - len(results)), "already_done": len(done_ids)}

    @router.get("/reviews/sentiment/summary/{property_id}")
    async def summary(property_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Theme frequency + sentiment distribution for a property."""
        pq = {"property_id": property_id} if property_id and property_id != "all" else {}
        reviews = await db.reviews.find(pq, {"_id": 0, "id": 1}).to_list(10000)
        review_ids = [r["id"] for r in reviews if r.get("id")]
        if not review_ids:
            return {"theme_counts": [], "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0}, "total_analyzed": 0}

        sentiments = await db.review_sentiments.find({"review_id": {"$in": review_ids}}, {"_id": 0}).to_list(20000)
        theme_counts = {}
        sent_dist = {"positive": 0, "neutral": 0, "negative": 0}
        for s in sentiments:
            sent_dist[s.get("sentiment", "neutral")] = sent_dist.get(s.get("sentiment", "neutral"), 0) + 1
            for t in s.get("themes", []) or []:
                theme_counts[t] = theme_counts.get(t, 0) + 1

        THEME_LABELS = {
            "dirty_bathroom": ("Dirty Bathroom", "negative"),
            "dirty_room": ("Dirty Room", "negative"),
            "clean": ("Clean", "positive"),
            "friendly_staff": ("Friendly Staff", "positive"),
            "rude_staff": ("Rude Staff", "negative"),
            "slow_checkin": ("Slow Check-in", "negative"),
            "fast_checkin": ("Fast Check-in", "positive"),
            "noisy": ("Noisy", "negative"),
            "quiet": ("Quiet", "positive"),
            "great_location": ("Great Location", "positive"),
            "poor_location": ("Poor Location", "negative"),
            "comfortable_bed": ("Comfortable Bed", "positive"),
            "uncomfortable_bed": ("Uncomfortable Bed", "negative"),
            "great_breakfast": ("Great Breakfast", "positive"),
            "poor_breakfast": ("Poor Breakfast", "negative"),
            "good_value": ("Good Value", "positive"),
            "overpriced": ("Overpriced", "negative"),
            "wifi_issues": ("Wi-Fi Issues", "negative"),
            "amenities_issue": ("Amenities Issue", "negative"),
            "parking_issue": ("Parking Issue", "negative"),
            "other": ("Other", "neutral"),
        }
        themes_out = sorted([
            {"theme": t, "label": THEME_LABELS.get(t, (t.replace('_', ' ').title(), 'neutral'))[0],
             "polarity": THEME_LABELS.get(t, (t, 'neutral'))[1], "count": c}
            for t, c in theme_counts.items()
        ], key=lambda r: -r["count"])[:20]

        return {
            "theme_counts": themes_out,
            "sentiment_distribution": sent_dist,
            "total_analyzed": len(sentiments),
            "total_reviews": len(review_ids),
        }

    return router
