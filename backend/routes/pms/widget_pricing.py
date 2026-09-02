"""Booking widget pricing — RMS rate_overrides → nightly guest prices, LOS restrictions, price transparency."""
from datetime import datetime, timedelta

SOURCE_LABELS = {
    "ramp-ladder": ("Talep yoğunluğu", "High demand"),
    "lastday-ladder": ("Son dakika fırsatı", "Last-minute deal"),
    "event-intelligence": ("Etkinlik dönemi", "Local event"),
    "owner-override": ("Otel fiyatı", "Hotel rate"),
    "market-robot": ("Piyasa koşulları", "Market conditions"),
    "ai-dynamic-pricing": ("Piyasa koşulları", "Market conditions"),
    "weather-calendar": ("Tatil / hava sinyali", "Holiday / weather"),
    "sentiment-pricing": ("Misafir puanı etkisi", "Guest review score"),
    "abs-auto-pricing": ("Oda özelliği talebi", "Room feature demand"),
}
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _parse(d: str):
    return datetime.strptime(d, "%Y-%m-%d").date()


async def nightly_rates(db, property_id: str, room: dict, check_in: str, check_out: str) -> list:
    """Per-night rate: room-type override → property-wide override → base rate."""
    base = float(room.get("base_rate") or room.get("base_price") or 100)
    rt_id = room.get("id", "")
    ci, co = _parse(check_in), _parse(check_out)
    nights = max(1, (co - ci).days)
    days = [(ci + timedelta(days=i)).isoformat() for i in range(nights)]
    ovs = await db.rate_overrides.find(
        {"property_id": property_id, "date": {"$in": days}, "room_type_id": {"$in": [rt_id, ""]},
         "custom_rate": {"$gt": 0}}, {"_id": 0}).to_list(400)
    by_day: dict = {}
    for ov in ovs:
        cur = by_day.get(ov["date"])
        if cur is None or (ov.get("room_type_id") and not cur.get("room_type_id")):
            by_day[ov["date"]] = ov
    out = []
    for d in days:
        ov = by_day.get(d)
        if ov:
            out.append({"date": d, "rate": round(float(ov["custom_rate"]), 2), "source": ov.get("set_by", ""),
                        "reason": ov.get("reason", ""), "base": base})
        else:
            out.append({"date": d, "rate": round(base, 2), "source": "", "reason": "", "base": base})
    return out


def explain_price(nightly: list) -> dict:
    total = round(sum(n["rate"] for n in nightly), 2)
    base_total = round(sum(n["base"] for n in nightly), 2)
    vs_base = round((total - base_total) / base_total * 100, 1) if base_total else 0.0
    drivers: dict = {}
    for n in nightly:
        if n["source"] and abs(n["rate"] - n["base"]) >= 0.01:
            tr, en = SOURCE_LABELS.get(n["source"], ("Dinamik fiyat", "Dynamic pricing"))
            drivers.setdefault(n["source"], {"label_tr": tr, "label_en": en, "nights": 0,
                                             "direction": "up" if n["rate"] > n["base"] else "down"})
            drivers[n["source"]]["nights"] += 1
    if vs_base > 2:
        head_tr = f"Bu tarihlerde talep yüksek — fiyat baz fiyatın %{vs_base:g} üzerinde"
        head_en = f"High demand on these dates — {vs_base:g}% above our standard rate"
    elif vs_base < -2:
        head_tr = f"Bu tarihlerde fiyat baz fiyatın %{abs(vs_base):g} altında — iyi fırsat"
        head_en = f"Good deal — {abs(vs_base):g}% below our standard rate for these dates"
    else:
        head_tr = "Standart fiyat — bu tarihlerde ek talep primi yok"
        head_en = "Standard rate — no demand surcharge on these dates"
    return {"vs_base_pct": vs_base, "base_total": base_total, "total": total,
            "headline_tr": head_tr, "headline_en": head_en, "drivers": list(drivers.values()),
            "dynamic_nights": sum(1 for n in nightly if n["source"]), "nights": len(nightly)}


async def check_los_restrictions(db, property_id: str, check_in: str, check_out: str) -> dict | None:
    """Returns a block dict if an enabled min/max stay restriction is violated, else None."""
    ci, co = _parse(check_in), _parse(check_out)
    nights = max(1, (co - ci).days)
    rules = await db.los_restrictions.find({"property_id": property_id, "enabled": {"$ne": False}}, {"_id": 0}).to_list(50)
    for r in rules:
        if r.get("date_from") and check_in < r["date_from"]:
            continue
        if r.get("date_to") and check_in > r["date_to"]:
            continue
        days = r.get("days") or []
        if r.get("applies_to") == "weekends" and not days:
            days = ["Fri", "Sat"]
        if days and DOW[ci.weekday()] not in days:
            continue
        val = int(r.get("value", 0) or 0)
        if r.get("type") == "min_stay" and nights < val:
            return {"type": "min_stay", "value": val, "nights": nights,
                    "message_tr": f"Bu tarihler için en az {val} gece konaklama gerekiyor (seçilen: {nights})",
                    "message_en": f"A minimum stay of {val} nights is required for these dates (selected: {nights})"}
        if r.get("type") == "max_stay" and val and nights > val:
            return {"type": "max_stay", "value": val, "nights": nights,
                    "message_tr": f"Bu tarihler için en fazla {val} gece konaklanabilir (seçilen: {nights})",
                    "message_en": f"Maximum stay for these dates is {val} nights (selected: {nights})"}
    return None
