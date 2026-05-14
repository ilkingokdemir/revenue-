"""
One-shot script: discover & seed 5 nearby competitors for EVERY active property
that currently has no market_competitors records (or fewer than 3).

Run with:
    cd /app/backend && set -a && source .env && set +a && python3 scripts/seed_competitors_all.py
"""
import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timezone

# Make sure we can import from /app/backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from utils.booking_scraper import discover_nearby_hotels, close_browser


TARGET_PER_PROPERTY = 5
MIN_BEFORE_SKIP = 3  # already has at least N comps → skip


async def seed_for_property(db, prop) -> dict:
    pid = prop["id"]
    existing = await db.market_competitors.count_documents({"property_id": pid})
    if existing >= MIN_BEFORE_SKIP:
        return {"property_id": pid, "skipped": True, "existing": existing}

    postcode = (prop.get("postcode") or "").strip()
    city = (prop.get("city") or "London").strip()
    lat = prop.get("latitude")
    lng = prop.get("longitude")
    currency = (prop.get("currency") or "GBP").upper()

    if not postcode and not city and not (lat and lng):
        return {"property_id": pid, "skipped": True, "reason": "no_location"}

    candidates = await discover_nearby_hotels(
        postcode=postcode,
        city=city,
        latitude=lat,
        longitude=lng,
        property_type="any",
        max_results=15,
        currency=currency,
    )

    # Filter out self + already-imported + bad rows
    existing_rows = await db.market_competitors.find(
        {"property_id": pid}, {"_id": 0, "booking_url": 1, "booking_hotel_id": 1},
    ).to_list(500)
    existing_urls = {(c.get("booking_url") or "").rstrip("/").split("?")[0] for c in existing_rows}
    existing_hids = {str(c.get("booking_hotel_id")) for c in existing_rows if c.get("booking_hotel_id")}
    our_url = (prop.get("booking_url") or "").rstrip("/").split("?")[0]

    picked = []
    for c in candidates:
        url = (c.get("booking_url") or "").rstrip("/").split("?")[0]
        if not url or not c.get("name"):
            continue
        if url == our_url:
            continue
        if url in existing_urls:
            continue
        hid = str(c.get("hotel_id") or "")
        if hid and hid in existing_hids:
            continue
        picked.append(c)
        if len(picked) >= TARGET_PER_PROPERTY:
            break

    if not picked:
        return {"property_id": pid, "skipped": True, "reason": "no_candidates", "candidates": len(candidates)}

    now_iso = datetime.now(timezone.utc).isoformat()
    to_insert = []
    for cand in picked:
        url = (cand.get("booking_url") or "").rstrip("/").split("?")[0]
        hid = str(cand.get("hotel_id") or "")
        slug_m = re.search(r"/hotel/[a-z]{2}/([a-z0-9-]+)\.", url)
        slug = slug_m.group(1) if slug_m else cand["name"].lower().replace(" ", "-")[:40]
        to_insert.append({
            "id": str(uuid.uuid4()),
            "property_id": pid,
            "name": cand["name"],
            "booking_url": url,
            "slug": slug,
            "booking_hotel_id": hid or None,
            "stars": cand.get("stars"),
            "review_score": cand.get("review_score"),
            "prices": [],
            "score": None,
            "last_scraped": None,
            "last_source": "auto-seed",
            "last_validation": {
                "ok": True, "checked_at": now_iso,
                "hotel_name": cand["name"], "hotel_id": hid or None,
            },
            "created_at": now_iso,
            "created_by": "seed_competitors_all_script",
        })

    if to_insert:
        await db.market_competitors.insert_many(to_insert)

    return {"property_id": pid, "added": len(to_insert), "candidates_found": len(candidates)}


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    props = await db.properties.find({}, {"_id": 0}).to_list(500)
    # Skip 'default' / 'all' pseudo-properties
    props = [p for p in props if p.get("id") and p["id"] not in ("default", "all")]
    print(f"Seeding competitors for {len(props)} properties (target {TARGET_PER_PROPERTY} each)...")

    results = []
    for p in props:
        pid = p.get("id")
        try:
            r = await seed_for_property(db, p)
            print(f"  {pid:25s} → {r}")
            results.append(r)
        except Exception as e:
            print(f"  {pid:25s} → ERROR: {e}")
            results.append({"property_id": pid, "error": str(e)})

    total_added = sum(r.get("added", 0) for r in results)
    print(f"\n✅ Done — {total_added} new competitors inserted across {len(results)} properties.")
    await close_browser()


if __name__ == "__main__":
    asyncio.run(main())
