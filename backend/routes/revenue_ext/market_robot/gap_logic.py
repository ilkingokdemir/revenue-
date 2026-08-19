"""Market gap kapama çekirdeği — /close-gap ve /fleet-close-gap tarafından paylaşılır."""
async def _internal_close_gap(db, property_id: str, strategy: str = "half",
                              days: int = 14, dry_run: bool = False,
                              min_gap_pct: float = 0.0,
                              source: str = "market-gap-close",
                              user_name: str = "system",
                              batch_id: str | None = None) -> dict:
    """Re-usable gap-close logic — used by both /close-gap endpoint and /fleet-close-gap.

    Sadece pazarın altındaki günlere yazar. min_gap_pct (default 0) altında olanlar
    skip edilir. batch_id geçerse rate_overrides'a batch_id ile damgalanır (undo için).
    """
    from datetime import datetime, timezone, timedelta

    comps = await db.market_competitors.find(
        {"property_id": property_id}, {"_id": 0, "prices": 1}
    ).to_list(50)
    per_day: dict = {}
    for c in comps:
        for row in (c.get("prices") or []):
            if not row.get("scraped"):
                continue
            d = row.get("date")
            lp = row.get("lowest_price")
            if not (d and lp):
                continue
            try:
                per_day.setdefault(d, []).append(float(lp))
            except Exception:
                pass

    if not per_day:
        return {"applied": 0, "skipped": 0, "avg_uplift_pct": 0,
                "days_evaluated": days, "reason": "no_competitor_data"}

    now = datetime.now(timezone.utc)
    date_keys = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

    rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
    base_rate = float((rt or {}).get("base_rate") or 100)
    existing_ov = await db.rate_overrides.find(
        {"property_id": property_id, "date": {"$in": date_keys}},
        {"_id": 0, "date": 1, "custom_rate": 1},
    ).to_list(500)
    ov_map = {o["date"]: o.get("custom_rate") for o in existing_ov if o.get("custom_rate")}

    applied = 0
    skipped = 0
    total_uplift_pct = 0.0
    upserts = []
    for d in date_keys:
        prices = per_day.get(d) or []
        if not prices:
            skipped += 1
            continue
        market_avg = sum(prices) / len(prices)
        market_min = min(prices)
        our_rate = float(ov_map.get(d, base_rate))

        gap_pct = ((market_avg - our_rate) / market_avg) * 100 if market_avg else 0
        if gap_pct < min_gap_pct or our_rate >= market_avg:
            skipped += 1
            continue

        if strategy == "full":
            new_rate = market_avg
        elif strategy == "half":
            new_rate = our_rate + (market_avg - our_rate) * 0.5
        elif strategy == "floor":
            new_rate = max(our_rate, market_min)
        else:  # value
            new_rate = market_avg * 0.95

        if strategy != "full":
            new_rate = min(new_rate, market_avg)
        new_rate = max(new_rate, our_rate)
        new_rate = round(new_rate, 2)

        if new_rate > our_rate:
            uplift_pct = ((new_rate - our_rate) / our_rate) * 100 if our_rate else 0
            applied += 1
            total_uplift_pct += uplift_pct
            ctx = {
                "strategy": strategy,
                "market_avg": round(market_avg, 2),
                "market_min": round(market_min, 2),
                "previous_rate": round(our_rate, 2),
            }
            if batch_id:
                ctx["batch_id"] = batch_id
            upserts.append({
                "property_id": property_id, "date": d,
                "custom_rate": new_rate, "source": source,
                "set_by": user_name, "set_at": now.isoformat(),
                "context": ctx,
            })

    if not dry_run and upserts:
        for u in upserts:
            await db.rate_overrides.update_one(
                {"property_id": property_id, "date": u["date"]},
                {"$set": u}, upsert=True,
            )

    return {
        "applied": applied,
        "skipped": skipped,
        "days_evaluated": days,
        "avg_uplift_pct": round(total_uplift_pct / applied, 1) if applied else 0,
    }
