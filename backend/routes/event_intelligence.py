"""
Event Intelligence — Detects concerts, matches, exhibitions, marathons, and major events
in the configured city. Uses web scraping + GPT-5.2 to classify events by attendance
and auto-adjusts hotel pricing for event dates + surrounding days.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import re
import os
import logging
import httpx

logger = logging.getLogger(__name__)

IMPACT_LEVELS = {
    "mega": {"min_attendance": 50000, "price_boost_pct": 40, "label": "Mega Event", "color": "red"},
    "large": {"min_attendance": 20000, "price_boost_pct": 25, "label": "Large Event", "color": "orange"},
    "medium": {"min_attendance": 5000, "price_boost_pct": 12, "label": "Medium Event", "color": "amber"},
    "small": {"min_attendance": 1000, "price_boost_pct": 5, "label": "Small Event", "color": "blue"},
}


def create_event_intelligence_router(db, require_roles):
    router = APIRouter()

    async def _search_events_web(city: str, days_ahead: int = 90):
        """Search for upcoming events in the city using web scraping."""
        now = datetime.now(timezone.utc)
        events_raw = []

        queries = [
            f"major events concerts festivals {city} {now.strftime('%B %Y')} next 3 months",
            f"football matches stadium events {city} {now.strftime('%Y')} upcoming",
            f"marathon exhibition conference {city} {now.strftime('%B %Y')} schedule",
        ]

        for query in queries:
            try:
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&gl=uk"
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    }
                    resp = await client.get(search_url, headers=headers)
                    events_raw.append(resp.text[:10000])
            except Exception as e:
                logger.warning(f"Event search failed: {e}")

        return "\n".join(events_raw)

    async def _analyze_events_with_ai(city: str, raw_text: str, days_ahead: int):
        """Use GPT-5.2 to extract and classify events from scraped data."""
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        now = datetime.now(timezone.utc)
        date_from = now.strftime("%Y-%m-%d")
        date_to = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        system_prompt = f"""You are an event intelligence analyst for a hotel revenue management system in {city}.
Your job is to identify ALL upcoming events that could impact hotel demand.

IMPORTANT: Return ONLY a valid JSON array. No markdown, no explanation, just the JSON array.

For each event, estimate:
- name: Event name
- date: Date in YYYY-MM-DD format (must be between {date_from} and {date_to})
- end_date: End date if multi-day, else same as date
- venue: Venue name
- category: One of: concert, sports, exhibition, marathon, festival, conference, theatre, other
- estimated_attendance: Number estimate
- impact: One of: mega (50000+), large (20000-50000), medium (5000-20000), small (1000-5000)
- description: Brief description
- confidence: high, medium, or low

Include events you know about for {city} even if not in the scraped text — use your knowledge of recurring annual events, sports seasons, concert tours, etc.

Focus on events with 1000+ expected attendance. Return at least 10-20 events for the next {days_ahead} days."""

        try:
            api_key = os.environ.get("EMERGENT_LLM_KEY", "")
            chat = LlmChat(
                api_key=api_key,
                session_id=f"event-intel-{city}-{now.strftime('%Y%m%d')}",
                system_message=system_prompt,
            ).with_model("openai", "gpt-5.2")

            user_msg = UserMessage(
                text=f"Here is scraped web data about events in {city}. Analyze and return events as JSON array:\n\n{raw_text[:4000]}"
            )
            response = await chat.send_message(user_msg)

            # Parse JSON from response
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                import json
                events = json.loads(json_match.group())
                return events
            return []
        except Exception as e:
            logger.error(f"AI event analysis failed: {e}")
            return []

    async def _apply_event_pricing(db, property_id, events):
        """Apply price boosts for event dates and surrounding days."""
        now = datetime.now(timezone.utc)
        applied = 0

        for event in events:
            impact = event.get("impact", "small")
            boost = IMPACT_LEVELS.get(impact, {}).get("price_boost_pct", 5)
            event_date = event.get("date", "")
            end_date = event.get("end_date", event_date)

            try:
                start = datetime.strptime(event_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue

            # Apply to event days + 1 day before + 1 day after
            d = start - timedelta(days=1)
            while d <= end + timedelta(days=1):
                ds = d.strftime("%Y-%m-%d")
                # Reduce boost for surrounding days
                if d < start or d > end:
                    day_boost = round(boost * 0.5)
                else:
                    day_boost = boost

                # Get base rate
                rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
                base = float(rt.get("base_rate", 100) or 100) if rt else 100

                # Check existing override
                existing = await db.rate_overrides.find_one(
                    {"property_id": property_id, "date": ds}, {"_id": 0}
                )
                current = float(existing.get("custom_rate", base)) if existing else base
                new_rate = round(current * (1 + day_boost / 100), 2)
                max_rate = round(base * 3.0, 2)
                new_rate = min(new_rate, max_rate)

                await db.rate_overrides.update_one(
                    {"property_id": property_id, "date": ds, "room_type_id": ""},
                    {"$set": {
                        "property_id": property_id,
                        "room_type_id": "",
                        "date": ds,
                        "custom_rate": new_rate,
                        "set_by": "event-intelligence",
                        "reason": f"{event.get('name', 'Event')} ({impact}, +{day_boost}%)",
                        "updated_at": now.isoformat(),
                    }},
                    upsert=True,
                )
                applied += 1
                d += timedelta(days=1)

        return applied

    # ==================== ENDPOINTS ====================

    @router.get("/revenue/events/{property_id}")
    async def get_events(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        events = await db.market_events.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("date", 1).to_list(200)

        mega = sum(1 for e in events if e.get("impact") == "mega")
        large = sum(1 for e in events if e.get("impact") == "large")
        medium = sum(1 for e in events if e.get("impact") == "medium")
        small = sum(1 for e in events if e.get("impact") == "small")

        return {
            "events": events,
            "counts": {"mega": mega, "large": large, "medium": medium, "small": small, "total": len(events)},
        }

    @router.post("/revenue/events/{property_id}/scan")
    async def scan_events(property_id: str, data: Dict = {},
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Scan for events using web + AI, store them, and optionally auto-price."""
        config = await db.market_robot_config.find_one(
            {"property_id": property_id}, {"_id": 0}
        ) or {}
        city = data.get("city") or config.get("city", "London")
        days_ahead = int(data.get("days_ahead", 90))
        auto_price = data.get("auto_price", True)
        now = datetime.now(timezone.utc)

        # Step 1: Scrape web for event data
        raw_text = await _search_events_web(city, days_ahead)

        # Step 2: AI analysis
        events = await _analyze_events_with_ai(city, raw_text, days_ahead)

        # Step 3: Store events
        stored = 0
        for event in events:
            event_date = event.get("date", "")
            if not event_date:
                continue
            # Validate date range
            try:
                ed = datetime.strptime(event_date, "%Y-%m-%d")
                now_naive = now.replace(tzinfo=None)
                if ed.date() < now_naive.date() or ed > now_naive + timedelta(days=days_ahead):
                    continue
            except (ValueError, TypeError):
                continue

            doc = {
                "id": str(uuid.uuid4())[:8],
                "property_id": property_id,
                "city": city,
                "name": event.get("name", "Unknown Event"),
                "date": event_date,
                "end_date": event.get("end_date", event_date),
                "venue": event.get("venue", ""),
                "category": event.get("category", "other"),
                "estimated_attendance": int(event.get("estimated_attendance", 0) or 0),
                "impact": event.get("impact", "small"),
                "description": event.get("description", ""),
                "confidence": event.get("confidence", "medium"),
                "scanned_at": now.isoformat(),
            }
            # Upsert by name+date to avoid duplicates
            await db.market_events.update_one(
                {"property_id": property_id, "name": doc["name"], "date": doc["date"]},
                {"$set": doc},
                upsert=True,
            )
            stored += 1

        # Step 4: Auto-price if enabled
        applied = 0
        if auto_price and events:
            applied = await _apply_event_pricing(db, property_id, events)

        return {
            "city": city,
            "events_found": len(events),
            "events_stored": stored,
            "prices_adjusted": applied,
            "events": events[:15],
        }

    @router.post("/revenue/events/{property_id}/add")
    async def add_manual_event(property_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Manually add an event."""
        config = await db.market_robot_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        now = datetime.now(timezone.utc)
        att = int(data.get("estimated_attendance", 0) or 0)
        impact = "mega" if att >= 50000 else "large" if att >= 20000 else "medium" if att >= 5000 else "small"

        doc = {
            "id": str(uuid.uuid4())[:8],
            "property_id": property_id,
            "city": config.get("city", "London"),
            "name": data.get("name", ""),
            "date": data.get("date", ""),
            "end_date": data.get("end_date", data.get("date", "")),
            "venue": data.get("venue", ""),
            "category": data.get("category", "other"),
            "estimated_attendance": att,
            "impact": impact,
            "description": data.get("description", ""),
            "confidence": "high",
            "source": "manual",
            "scanned_at": now.isoformat(),
        }
        await db.market_events.insert_one(doc)
        doc.pop("_id", None)

        # Auto-price for this event
        applied = await _apply_event_pricing(db, property_id, [doc])

        return {**doc, "prices_adjusted": applied}

    @router.delete("/revenue/events/{event_id}")
    async def delete_event(event_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.market_events.delete_one({"id": event_id})
        return {"message": "Event removed"}

    return router
