"""
Event Intelligence — Smart hotel-demand-aware event detection.
Only tracks events that ACTUALLY drive hotel bookings (out-of-town visitors).
Uses a Hotel Demand Score (HDS) based on: visitor origin, event time, duration,
international vs local, team quality, and event category.
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

# Hotel Demand Score replaces simple attendance-based impact
# Score 0-100: How likely attendees are to need hotel rooms
IMPACT_LEVELS = {
    "critical": {"min_hds": 80, "price_boost_pct": 45, "label": "Critical Demand", "color": "red"},
    "high": {"min_hds": 60, "price_boost_pct": 30, "label": "High Demand", "color": "orange"},
    "moderate": {"min_hds": 40, "price_boost_pct": 15, "label": "Moderate Demand", "color": "amber"},
    "low": {"min_hds": 20, "price_boost_pct": 5, "label": "Low Demand", "color": "blue"},
    "minimal": {"min_hds": 0, "price_boost_pct": 0, "label": "Minimal Impact", "color": "stone"},
}

# Keep old keys for backward compat
LEGACY_MAP = {"mega": "critical", "large": "high", "medium": "moderate", "small": "low"}


def create_event_intelligence_router(db, require_roles):
    router = APIRouter()

    async def _search_events_web(city: str, days_ahead: int = 365):
        """Search for upcoming events in the city using web scraping."""
        now = datetime.now(timezone.utc)
        events_raw = []
        queries = [
            f"major events concerts festivals {city} {now.strftime('%B %Y')} next 6 months",
            f"international football UEFA Champions League matches {city} {now.strftime('%Y')}",
            f"marathon exhibition conference {city} {now.strftime('%B %Y')} schedule",
            f"touring concerts stadium shows {city} {now.strftime('%Y')} tickets",
        ]
        for query in queries:
            try:
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&gl=uk"
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
                    resp = await client.get(search_url, headers=headers)
                    events_raw.append(resp.text[:10000])
            except Exception as e:
                logger.warning(f"Event search failed: {e}")
        return "\n".join(events_raw)

    async def _analyze_events_with_ai(city: str, raw_text: str, days_ahead: int):
        """GPT-5.2 smart analysis: only events that drive HOTEL demand."""
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        now = datetime.now(timezone.utc)
        date_from = now.strftime("%Y-%m-%d")
        date_to = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        system_prompt = f"""You are a HOTEL REVENUE intelligence analyst for {city}.
Your job is to identify events that will make people STAY IN HOTELS — NOT just any event.

CRITICAL RULES FOR HOTEL DEMAND:
1. FOOTBALL/SPORTS:
   - LOCAL league match (e.g. Arsenal vs Chelsea, both London teams) = MINIMAL hotel impact — fans live locally, they go home after
   - INTERNATIONAL match (FIFA, UEFA Champions League, Europa League) = HIGH hotel impact — away fans travel from abroad
   - Top team from DIFFERENT CITY visiting (e.g. Liverpool/Manchester playing in London) = MODERATE — traveling fans need hotels
   - Cup FINAL or SEMI-FINAL at neutral venue = CRITICAL — both sets of fans need hotels
   - Rugby/Cricket international = HIGH — fans travel from other countries

2. CONCERTS/MUSIC:
   - Major touring artist (Taylor Swift, Beyonce, Ed Sheeran etc) at STADIUM = CRITICAL — fans travel from everywhere
   - Festival (multi-day) = CRITICAL — people need accommodation for 2-3+ days
   - Arena concert (20k capacity) with touring act = HIGH — regional visitors
   - Local venue small gig = MINIMAL

3. CONFERENCES/EXHIBITIONS:
   - International conference (1000+ delegates) = HIGH — business travelers stay in hotels
   - Trade show/expo (multi-day) = HIGH — exhibitors + visitors need hotels
   - Local business meetup = MINIMAL

4. MARATHONS/SPORTS EVENTS:
   - City marathon = HIGH — runners + families travel in
   - Formula 1, Tennis Major, Golf Major = CRITICAL
   - Local fun run = MINIMAL

5. TIME OF DAY matters:
   - Evening event (concert, match after 6pm) = higher hotel demand (people stay overnight)
   - Morning/afternoon event = slightly lower (day-trippers)

6. DURATION:
   - Multi-day event = MUCH higher hotel demand
   - Single evening = moderate

For EACH event return:
- name, date (YYYY-MM-DD), end_date, venue, category
- estimated_attendance: total expected
- hotel_demand_score: 0-100 (YOUR KEY OUTPUT — how many % of attendees need hotel rooms)
- visitor_origin: "international", "national", "regional", "local"
- is_evening: true/false
- is_multi_day: true/false
- reasoning: WHY you scored it this way (1 sentence)
- impact: "critical" (HDS 80+), "high" (60-79), "moderate" (40-59), "low" (20-39), "minimal" (0-19)
- estimated_hotel_nights: rough estimate of total hotel room-nights generated
- confidence: high/medium/low

IMPORTANT: Return ONLY a valid JSON array. No markdown.
Only include events between {date_from} and {date_to}.
SKIP events with hotel_demand_score below 15 — they don't matter for hotel pricing.
Include known recurring events, sports seasons, touring concerts, etc."""

        try:
            api_key = os.environ.get("EMERGENT_LLM_KEY", "")
            chat = LlmChat(
                api_key=api_key,
                session_id=f"event-intel-smart-{city}-{now.strftime('%Y%m%d')}",
                system_message=system_prompt,
            ).with_model("openai", "gpt-5.2")

            user_msg = UserMessage(
                text=f"Scraped data about events in {city}:\n\n{raw_text[:4000]}"
            )
            response = await chat.send_message(user_msg)

            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                import json
                events = json.loads(json_match.group())
                # Filter out low-impact events
                return [e for e in events if int(e.get("hotel_demand_score", 0) or 0) >= 15]
            return []
        except Exception as e:
            logger.error(f"AI event analysis failed: {e}")
            return []

    def _get_impact_from_hds(hds):
        """Convert Hotel Demand Score to impact level."""
        if hds >= 80:
            return "critical"
        elif hds >= 60:
            return "high"
        elif hds >= 40:
            return "moderate"
        elif hds >= 20:
            return "low"
        return "minimal"

    def _get_price_boost(impact, hds):
        """Get price boost % based on impact and HDS."""
        level = IMPACT_LEVELS.get(impact, IMPACT_LEVELS["minimal"])
        base_boost = level["price_boost_pct"]
        # Fine-tune based on exact HDS (e.g. HDS 95 gets more than HDS 80)
        if hds >= 90:
            return round(base_boost * 1.2)
        elif hds >= 70:
            return base_boost
        elif hds >= 50:
            return round(base_boost * 0.8)
        return round(base_boost * 0.6)

    async def _apply_event_pricing(db, property_id, events):
        """Apply price boosts for hotel-demand-generating events only."""
        now = datetime.now(timezone.utc)
        applied = 0

        for event in events:
            hds = int(event.get("hotel_demand_score", 0) or 0)
            impact = event.get("impact") or _get_impact_from_hds(hds)
            # Map legacy impacts
            impact = LEGACY_MAP.get(impact, impact)

            if impact == "minimal" or hds < 15:
                continue

            boost = _get_price_boost(impact, hds)
            if boost <= 0:
                continue

            event_date = event.get("date", "")
            end_date = event.get("end_date", event_date)
            is_evening = event.get("is_evening", True)

            try:
                start = datetime.strptime(event_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue

            # Buffer days: 1 day before (arrival), 1 day after (departure)
            # Multi-day events: full duration + buffer
            d = start - timedelta(days=1)
            while d <= end + timedelta(days=1):
                ds = d.strftime("%Y-%m-%d")
                if d < start:
                    day_boost = round(boost * 0.6)  # Arrival day before
                elif d > end:
                    day_boost = round(boost * 0.4)  # Departure day after
                elif is_evening and d == start:
                    day_boost = boost  # Evening event = stay that night
                else:
                    day_boost = boost

                rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
                base = float(rt.get("base_rate", 100) or 100) if rt else 100
                existing = await db.rate_overrides.find_one(
                    {"property_id": property_id, "date": ds}, {"_id": 0}
                )
                current = float(existing.get("custom_rate", base)) if existing else base
                new_rate = round(current * (1 + day_boost / 100), 2)
                max_rate = round(base * 3.0, 2)
                new_rate = min(new_rate, max_rate)

                visitor = event.get("visitor_origin", "unknown")
                reason_detail = f"HDS:{hds} | {visitor} | {'+evening' if is_evening else 'daytime'}"

                await db.rate_overrides.update_one(
                    {"property_id": property_id, "date": ds, "room_type_id": ""},
                    {"$set": {
                        "property_id": property_id,
                        "room_type_id": "",
                        "date": ds,
                        "custom_rate": new_rate,
                        "set_by": "event-intelligence",
                        "reason": f"Event: {event.get('name', '')} ({impact}, +{day_boost}%) | {reason_detail}",
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
        ).sort("date", 1).to_list(300)

        counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "minimal": 0}
        for e in events:
            imp = LEGACY_MAP.get(e.get("impact", ""), e.get("impact", "minimal"))
            counts[imp] = counts.get(imp, 0) + 1

        # Backward compat
        counts["mega"] = counts.get("critical", 0)
        counts["large"] = counts.get("high", 0)
        counts["medium"] = counts.get("moderate", 0)
        counts["small"] = counts.get("low", 0)
        counts["total"] = len(events)

        return {"events": events, "counts": counts}

    @router.post("/revenue/events/{property_id}/scan")
    async def scan_events(property_id: str, data: Dict = {},
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Smart scan: only events that drive hotel bookings."""
        config = await db.market_robot_config.find_one(
            {"property_id": property_id}, {"_id": 0}
        ) or {}
        city = data.get("city") or config.get("city", "London")
        days_ahead = int(data.get("days_ahead", 365))
        auto_price = data.get("auto_price", True)
        now = datetime.now(timezone.utc)

        raw_text = await _search_events_web(city, days_ahead)
        events = await _analyze_events_with_ai(city, raw_text, days_ahead)

        stored = 0
        for event in events:
            event_date = event.get("date", "")
            if not event_date:
                continue
            try:
                ed = datetime.strptime(event_date, "%Y-%m-%d")
                now_naive = now.replace(tzinfo=None)
                if ed.date() < now_naive.date() or ed > now_naive + timedelta(days=days_ahead):
                    continue
            except (ValueError, TypeError):
                continue

            hds = int(event.get("hotel_demand_score", 0) or 0)
            impact = event.get("impact") or _get_impact_from_hds(hds)
            impact = LEGACY_MAP.get(impact, impact)

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
                "hotel_demand_score": hds,
                "visitor_origin": event.get("visitor_origin", "unknown"),
                "is_evening": event.get("is_evening", True),
                "is_multi_day": event.get("is_multi_day", False),
                "estimated_hotel_nights": int(event.get("estimated_hotel_nights", 0) or 0),
                "reasoning": event.get("reasoning", ""),
                "impact": impact,
                "description": event.get("description", ""),
                "confidence": event.get("confidence", "medium"),
                "scanned_at": now.isoformat(),
            }
            await db.market_events.update_one(
                {"property_id": property_id, "name": doc["name"], "date": doc["date"]},
                {"$set": doc}, upsert=True
            )
            stored += 1

        prices_adjusted = 0
        if auto_price and stored > 0:
            prices_adjusted = await _apply_event_pricing(db, property_id, events)

        skipped = len(events) - stored if len(events) > stored else 0

        return {
            "events_found": len(events),
            "events_stored": stored,
            "events_skipped": skipped,
            "prices_adjusted": prices_adjusted,
            "city": city,
            "days_scanned": days_ahead,
            "message": f"Smart scan: {stored} hotel-demand events stored from {len(events)} detected. {skipped} low-impact skipped. {prices_adjusted} rate adjustments applied.",
        }

    @router.post("/revenue/events/{property_id}/add")
    async def add_event(property_id: str, data: Dict,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        """Manually add an event with smart hotel demand scoring."""
        now = datetime.now(timezone.utc)
        attendance = int(data.get("estimated_attendance", 0) or 0)
        hds = int(data.get("hotel_demand_score", 50) or 50)
        impact = data.get("impact") or _get_impact_from_hds(hds)
        impact = LEGACY_MAP.get(impact, impact)
        visitor_origin = data.get("visitor_origin", "regional")
        is_evening = data.get("is_evening", True)
        is_multi_day = data.get("is_multi_day", False)

        doc = {
            "id": str(uuid.uuid4())[:8],
            "property_id": property_id,
            "city": data.get("city", "London"),
            "name": data.get("name", "Manual Event"),
            "date": data.get("date", now.strftime("%Y-%m-%d")),
            "end_date": data.get("end_date", data.get("date", now.strftime("%Y-%m-%d"))),
            "venue": data.get("venue", ""),
            "category": data.get("category", "other"),
            "estimated_attendance": attendance,
            "hotel_demand_score": hds,
            "visitor_origin": visitor_origin,
            "is_evening": is_evening,
            "is_multi_day": is_multi_day,
            "estimated_hotel_nights": int(data.get("estimated_hotel_nights", 0) or 0),
            "reasoning": data.get("reasoning", "Manually added"),
            "impact": impact,
            "description": data.get("description", ""),
            "confidence": "high",
            "source": "manual",
            "scanned_at": now.isoformat(),
        }

        await db.market_events.update_one(
            {"property_id": property_id, "name": doc["name"], "date": doc["date"]},
            {"$set": doc}, upsert=True
        )

        prices_adjusted = 0
        if data.get("auto_price", True):
            prices_adjusted = await _apply_event_pricing(db, property_id, [doc])

        return {
            "event": doc,
            "prices_adjusted": prices_adjusted,
            "message": f"Event '{doc['name']}' added (HDS: {hds}, Impact: {impact}). {prices_adjusted} rates adjusted.",
        }

    @router.delete("/revenue/events/{event_id}")
    async def delete_event(event_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.market_events.delete_one({"id": event_id})
        return {"message": "Event removed"}

    return router
