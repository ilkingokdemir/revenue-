"""
Nightly Recap — "What happened last night?" digest. Different from
Morning Brief which is forward-looking. This screen is what owners want at
9 AM with their coffee:

  - Last-night occupancy %, revenue, ADR, RevPAR
  - Top performing room types
  - No-shows, cancellations, walk-ins
  - Departures + arrivals counts
  - Unit-level events (early check-ins, late check-outs, comp upgrades)
  - YoY comparison
  - Auto-generated 3-line GPT-5.2 commentary

Concierge Most-Asked-Topics — GPT-5.2 clusters the last N days of guest
questions into topics with counts. Surfaces hidden FAQs the hotel team should
answer in the website / pre-arrival email / room directory.

Endpoints:
- GET /api/nightly-recap/{property_id}?date=YYYY-MM-DD&yoy=true
- GET /api/concierge/admin/{property_id}/topics?days=30
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional
import os
import uuid
import logging

logger = logging.getLogger(__name__)


def create_nightly_recap_router(db, require_roles):
    router = APIRouter()

    async def _date_metrics(property_id: str, target_iso: str):
        """Returns metrics for a single night."""
        next_iso = (date.fromisoformat(target_iso) + timedelta(days=1)).isoformat()
        # Total rooms
        rooms = await db.room_types.aggregate([
            {"$match": {"property_id": property_id}},
            {"$group": {"_id": None, "t": {"$sum": "$total_rooms"}}}
        ]).to_list(1)
        total_rooms = int((rooms[0]["t"] if rooms else 0) or 0)

        # Bookings overlapping this night (sold rooms)
        sold = []
        async for b in db.bookings.find({
            "property_id": property_id,
            "check_in":  {"$lte": target_iso},
            "check_out": {"$gt":  target_iso},
            "status": {"$nin": ["cancelled"]},
        }, {"_id": 0}):
            sold.append(b)
        rooms_sold = len(sold)
        revenue = 0.0
        for b in sold:
            try:
                ci = date.fromisoformat(b.get("check_in", "")[:10])
                co = date.fromisoformat(b.get("check_out", "")[:10])
                nights = max(1, (co - ci).days)
                revenue += float(b.get("total_price") or 0) / nights
            except Exception:
                continue
        revenue = round(revenue, 2)
        adr = round(revenue / rooms_sold, 2) if rooms_sold else 0
        revpar = round(revenue / total_rooms, 2) if total_rooms else 0
        occ = round((rooms_sold / total_rooms) * 100, 1) if total_rooms else 0

        # Arrivals/departures/walk-ins/no-shows that day
        arrivals = await db.bookings.count_documents({
            "property_id": property_id, "check_in": target_iso,
            "status": {"$nin": ["cancelled"]},
        })
        departures = await db.bookings.count_documents({
            "property_id": property_id, "check_out": target_iso,
            "status": {"$nin": ["cancelled"]},
        })
        no_shows = await db.bookings.count_documents({
            "property_id": property_id, "check_in": target_iso, "status": "no_show",
        })
        walk_ins = await db.bookings.count_documents({
            "property_id": property_id, "check_in": target_iso,
            "source": {"$in": ["walk-in", "walk_in"]},
        })
        cancellations = await db.bookings.count_documents({
            "property_id": property_id,
            "cancelled_at": {"$gte": target_iso, "$lt": next_iso},
            "status": "cancelled",
        })

        # Top performing room types
        rt_revenue: Dict[str, float] = {}
        rt_count: Dict[str, int] = {}
        for b in sold:
            rt = b.get("room_type") or "Standard"
            try:
                ci = date.fromisoformat(b.get("check_in", "")[:10])
                co = date.fromisoformat(b.get("check_out", "")[:10])
                nights = max(1, (co - ci).days)
                rt_revenue[rt] = rt_revenue.get(rt, 0) + float(b.get("total_price") or 0) / nights
            except Exception:
                pass
            rt_count[rt] = rt_count.get(rt, 0) + 1
        top_rooms = [
            {"room_type": rt, "rooms_sold": rt_count[rt], "revenue": round(rev, 2)}
            for rt, rev in sorted(rt_revenue.items(), key=lambda x: -x[1])[:5]
        ]

        return {
            "date": target_iso,
            "rooms_sold": rooms_sold,
            "total_rooms": total_rooms,
            "occupancy_pct": occ,
            "revenue": revenue,
            "adr": adr,
            "revpar": revpar,
            "arrivals": arrivals,
            "departures": departures,
            "no_shows": no_shows,
            "walk_ins": walk_ins,
            "cancellations": cancellations,
            "top_rooms": top_rooms,
        }

    @router.get("/nightly-recap/{property_id}")
    async def nightly_recap(property_id: str, date_str: str = "", yoy: bool = True,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Default: yesterday. Pass ?date_str=YYYY-MM-DD to recap a specific night."""
        if date_str:
            try:
                target = date.fromisoformat(date_str)
            except Exception:
                raise HTTPException(400, "date_str must be YYYY-MM-DD")
        else:
            target = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        target_iso = target.isoformat()
        metrics = await _date_metrics(property_id, target_iso)

        # YoY comparison
        yoy_block = None
        if yoy:
            ly_iso = (target - timedelta(days=365)).isoformat()
            ly = await _date_metrics(property_id, ly_iso)
            yoy_block = {
                "date": ly_iso,
                "rooms_sold": ly["rooms_sold"],
                "occupancy_pct": ly["occupancy_pct"],
                "revenue": ly["revenue"],
                "adr": ly["adr"],
                "revpar": ly["revpar"],
                "occ_delta_pp":   round(metrics["occupancy_pct"] - ly["occupancy_pct"], 1),
                "rev_delta_pct":  round(((metrics["revenue"] - ly["revenue"]) / ly["revenue"]) * 100, 1) if ly["revenue"] else None,
                "adr_delta_pct":  round(((metrics["adr"] - ly["adr"]) / ly["adr"]) * 100, 1) if ly["adr"] else None,
            }

        # GPT commentary
        commentary = ""
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if api_key:
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                payload = {"target": metrics, "ly": yoy_block}
                sys_prompt = (
                    "You are a hotel revenue manager writing a 3-line nightly recap. "
                    "Be concrete, mention the biggest mover (occupancy / ADR / RevPAR vs LY), "
                    "and end with a brief recommendation for tonight. Plain text only, "
                    "no markdown, no bullet points, max 70 words."
                )
                llm = LlmChat(
                    api_key=api_key, session_id=f"nightly-{property_id}-{target_iso}",
                    system_message=sys_prompt,
                ).with_model("openai", "gpt-5.2")
                import json as _json
                resp = await llm.send_message(UserMessage(text=_json.dumps(payload)))
                commentary = (resp or "").strip()[:600]
            except Exception as e:
                logger.exception("Nightly recap LLM failed: %s", e)

        return {
            "property_id": property_id,
            "as_of": datetime.now(timezone.utc).isoformat(),
            **metrics,
            "yoy": yoy_block,
            "commentary": commentary,
        }

    return router


def create_concierge_topics_router(db, require_roles):
    router = APIRouter()

    @router.get("/concierge/admin/{property_id}/topics")
    async def topics(property_id: str, days: int = 30,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Cluster recent guest questions into topics with counts."""
        days = max(7, min(int(days), 90))
        cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        msgs = await db.concierge_chats.find(
            {"property_id": property_id, "role": "user",
             "created_at": {"$gte": cutoff_iso}},
            {"_id": 0, "content": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(500)

        if not msgs:
            return {"topics": [], "samples": 0, "window_days": days, "fallback": False}

        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            # Heuristic keyword bucketing
            buckets = {
                "Parking":            ["park", "parking", "garage", "araç"],
                "Breakfast / F&B":    ["breakfast", "kahvaltı", "dinner", "restaurant", "food", "menu"],
                "Check-in / Check-out": ["check-in", "check in", "check-out", "checkout", "early", "late"],
                "WiFi / Tech":        ["wifi", "wi-fi", "internet", "password"],
                "Rooms / Beds":       ["bed", "twin", "double", "king", "queen", "smoking", "view"],
                "Local Area":         ["nearby", "metro", "station", "attraction", "tour", "restaurant nearby"],
                "Booking / Cancel":   ["cancel", "refund", "policy", "modify", "change date"],
            }
            counts = {k: 0 for k in buckets}
            samples_by_topic = {k: [] for k in buckets}
            for m in msgs:
                txt = (m.get("content") or "").lower()
                for topic, kws in buckets.items():
                    if any(k in txt for k in kws):
                        counts[topic] += 1
                        if len(samples_by_topic[topic]) < 3:
                            samples_by_topic[topic].append(m["content"][:120])
                        break
            results = [
                {"topic": k, "count": v, "samples": samples_by_topic[k]}
                for k, v in sorted(counts.items(), key=lambda x: -x[1]) if v > 0
            ]
            return {"topics": results, "samples": len(msgs), "window_days": days, "fallback": True}

        # GPT-5.2 clustering — single call, strict JSON
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        sample_text = "\n".join(f"- {m['content'][:200]}" for m in msgs[:200])
        sys_prompt = (
            "You are an analyst clustering guest questions for a hotel into 5-10 topics. "
            "Return STRICT JSON: "
            '{"topics":[{"topic":"…","count":N,"samples":["…","…","…"]}]} '
            "where count is the EXACT number of input lines that fit the topic, "
            "samples are 3 representative input lines. Sort topics by count desc. "
            "Translate the topic label to English even if input is mixed-language. "
            "No markdown, no other fields."
        )
        try:
            llm = LlmChat(
                api_key=api_key, session_id=f"topics-{property_id}",
                system_message=sys_prompt,
            ).with_model("openai", "gpt-5.2")
            import json as _json
            import re as _re
            resp = await llm.send_message(UserMessage(text=sample_text))
            txt = (resp or "").strip()
            mo = _re.search(r"\{.*\}", txt, _re.DOTALL)
            parsed = _json.loads(mo.group(0)) if mo else {"topics": []}
            return {
                "topics": parsed.get("topics", [])[:10],
                "samples": len(msgs),
                "window_days": days,
                "fallback": False,
            }
        except Exception as e:
            logger.exception("Topics clustering failed: %s", e)
            return {"topics": [], "samples": len(msgs), "window_days": days,
                    "fallback": True, "error": str(e)[:200]}

    return router
