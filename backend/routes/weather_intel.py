"""
Weather Intelligence — Fetches 7-14 day forecast from Open-Meteo (free, no API key).
Correlates weather with demand patterns to suggest pricing opportunities.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import httpx
import logging

logger = logging.getLogger(__name__)

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}

WEATHER_ICONS = {
    0: "sun", 1: "sun", 2: "cloud-sun", 3: "cloud",
    45: "cloud-fog", 48: "cloud-fog", 51: "cloud-drizzle", 53: "cloud-drizzle",
    55: "cloud-drizzle", 61: "cloud-rain", 63: "cloud-rain", 65: "cloud-rain-heavy",
    71: "snowflake", 73: "snowflake", 75: "snowflake", 77: "snowflake",
    80: "cloud-rain", 81: "cloud-rain", 82: "cloud-rain-heavy",
    85: "snowflake", 86: "snowflake", 95: "cloud-lightning", 96: "cloud-lightning", 99: "cloud-lightning",
}


def create_weather_router(db, require_roles):
    router = APIRouter()

    @router.get("/revenue/weather/{property_id}")
    async def get_weather_forecast(property_id: str, days: int = 14,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Fetch weather forecast and correlate with demand/pricing data."""
        # Get property city
        config = await db.market_robot_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        city = config.get("city", "London")
        country = config.get("country", "United Kingdom")

        # Get coordinates for city
        coords = await _geocode(city, country)
        if not coords:
            coords = {"lat": 51.5074, "lon": -0.1278}  # London fallback

        # Fetch forecast from Open-Meteo
        forecast = await _fetch_forecast(coords["lat"], coords["lon"], days)

        # Get demand data for correlation
        supply_docs = await db.market_supply.find(
            {"$or": [{"property_id": property_id}, {"property_id": "all"}]},
            {"_id": 0}
        ).sort("scanned_at", -1).to_list(500)
        supply_map = {}
        for s in supply_docs:
            if s["date"] not in supply_map:
                supply_map[s["date"]] = s

        # Get our rates
        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        base_rate = float(rt.get("base_rate", 100) or 100) if rt else 100.0
        overrides = await db.rate_overrides.find({"property_id": property_id}, {"_id": 0}).to_list(500)
        override_map = {ov["date"]: float(ov.get("custom_rate", base_rate)) for ov in overrides}

        # Get events
        events = await db.events_db.find({}, {"_id": 0}).to_list(200)
        event_map = {}
        for ev in events:
            ed = ev.get("date", "")
            if ed:
                event_map[ed] = ev

        # Build daily data with weather + demand correlation
        daily = []
        opportunities = []

        for i, f_day in enumerate(forecast):
            ds = f_day["date"]
            demand = None
            sup = supply_map.get(ds, {})
            if sup:
                demand = sup.get("unavailable_pct")

            our_rate = override_map.get(ds, base_rate)
            event = event_map.get(ds)

            # Weather-demand score (0-100)
            weather_score = _calc_weather_score(f_day)
            is_weekend = f_day.get("is_weekend", False)

            # Pricing opportunity detection
            opportunity = None
            if weather_score >= 70 and is_weekend:
                opportunity = {
                    "type": "sunny_weekend",
                    "title": f"Sunny weekend — {f_day['description']}",
                    "suggestion": "Consider raising rates by 10-20%. Good weather + weekend = high walk-in potential.",
                    "impact": "high",
                }
            elif weather_score >= 70 and event:
                opportunity = {
                    "type": "sunny_event",
                    "title": f"Good weather + {event.get('name', 'Event')}",
                    "suggestion": "Premium pricing opportunity. Favorable weather amplifies event demand.",
                    "impact": "high",
                }
            elif weather_score <= 30 and is_weekend:
                opportunity = {
                    "type": "bad_weather_weekend",
                    "title": f"Poor weather weekend — {f_day['description']}",
                    "suggestion": "Consider promotions or packages. Bad weather reduces spontaneous bookings.",
                    "impact": "medium",
                }
            elif weather_score >= 80:
                opportunity = {
                    "type": "exceptional_weather",
                    "title": f"Exceptional weather — {f_day['description']}, {f_day['temp_max']}°C",
                    "suggestion": "Outdoor attractions will draw visitors. Boost visibility on OTAs.",
                    "impact": "medium",
                }

            if opportunity:
                opportunity["date"] = ds
                opportunity["weather_score"] = weather_score
                opportunities.append(opportunity)

            daily.append({
                **f_day,
                "demand": demand,
                "our_rate": our_rate,
                "weather_score": weather_score,
                "event": event.get("name") if event else None,
                "opportunity": opportunity,
            })

        # Summary stats
        avg_temp = round(sum(d["temp_avg"] for d in daily) / max(len(daily), 1), 1) if daily else 0
        sunny_days = sum(1 for d in daily if d["weather_score"] >= 70)
        rainy_days = sum(1 for d in daily if d.get("precip_mm", 0) > 2)
        best_day = max(daily, key=lambda d: d["weather_score"]) if daily else None
        worst_day = min(daily, key=lambda d: d["weather_score"]) if daily else None

        return {
            "city": city,
            "coordinates": coords,
            "days": len(daily),
            "summary": {
                "avg_temp": avg_temp,
                "sunny_days": sunny_days,
                "rainy_days": rainy_days,
                "best_day": {"date": best_day["date"], "score": best_day["weather_score"], "desc": best_day["description"]} if best_day else None,
                "worst_day": {"date": worst_day["date"], "score": worst_day["weather_score"], "desc": worst_day["description"]} if worst_day else None,
            },
            "opportunities": opportunities,
            "daily": daily,
        }

    return router


async def _geocode(city, country):
    """Get coordinates for a city using Open-Meteo geocoding."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1")
            data = r.json()
            if data.get("results"):
                res = data["results"][0]
                return {"lat": res["latitude"], "lon": res["longitude"]}
    except Exception as e:
        logger.error(f"Geocode error: {e}")
    return None


async def _fetch_forecast(lat, lon, days):
    """Fetch weather forecast from Open-Meteo."""
    days = min(days, 16)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&"
                f"daily=weather_code,temperature_2m_max,temperature_2m_min,"
                f"apparent_temperature_max,apparent_temperature_min,"
                f"precipitation_sum,precipitation_probability_max,"
                f"wind_speed_10m_max,uv_index_max,sunshine_duration&"
                f"timezone=auto&forecast_days={days}"
            )
            r = await client.get(url)
            data = r.json()

            daily_data = data.get("daily", {})
            dates = daily_data.get("time", [])
            result = []
            for i, ds in enumerate(dates):
                d = datetime.strptime(ds, "%Y-%m-%d")
                code = daily_data.get("weather_code", [0] * len(dates))[i]
                result.append({
                    "date": ds,
                    "day": d.day,
                    "dow": d.strftime("%a"),
                    "month": d.strftime("%b"),
                    "is_weekend": d.weekday() >= 5,
                    "weather_code": code,
                    "description": WMO_CODES.get(code, "Unknown"),
                    "icon": WEATHER_ICONS.get(code, "cloud"),
                    "temp_max": daily_data.get("temperature_2m_max", [0] * len(dates))[i],
                    "temp_min": daily_data.get("temperature_2m_min", [0] * len(dates))[i],
                    "temp_avg": round((daily_data.get("temperature_2m_max", [0] * len(dates))[i] + daily_data.get("temperature_2m_min", [0] * len(dates))[i]) / 2, 1),
                    "feels_max": daily_data.get("apparent_temperature_max", [0] * len(dates))[i],
                    "precip_mm": daily_data.get("precipitation_sum", [0] * len(dates))[i],
                    "precip_prob": daily_data.get("precipitation_probability_max", [0] * len(dates))[i],
                    "wind_max": daily_data.get("wind_speed_10m_max", [0] * len(dates))[i],
                    "uv_index": daily_data.get("uv_index_max", [0] * len(dates))[i],
                    "sunshine_hrs": round((daily_data.get("sunshine_duration", [0] * len(dates))[i] or 0) / 3600, 1),
                })
            return result
    except Exception as e:
        logger.error(f"Weather fetch error: {e}")
        return []


def _calc_weather_score(day):
    """Calculate a 0-100 weather desirability score."""
    score = 50
    code = day.get("weather_code", 3)
    if code <= 1:
        score += 30
    elif code <= 2:
        score += 20
    elif code <= 3:
        score += 5
    elif code >= 61:
        score -= 20
    elif code >= 95:
        score -= 30

    temp = day.get("temp_max", 15)
    if 18 <= temp <= 28:
        score += 15
    elif 15 <= temp <= 30:
        score += 8
    elif temp < 5 or temp > 35:
        score -= 15

    precip = day.get("precip_prob", 0)
    if precip <= 10:
        score += 10
    elif precip >= 70:
        score -= 15

    sunshine = day.get("sunshine_hrs", 5)
    if sunshine >= 10:
        score += 10
    elif sunshine >= 6:
        score += 5
    elif sunshine < 2:
        score -= 10

    return max(0, min(100, score))
