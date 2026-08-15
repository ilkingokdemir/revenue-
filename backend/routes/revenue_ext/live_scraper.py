"""Canlı Compset Scraper — kamuya açık OTA fiyatlarını yasal toplama (opsiyon 2).
Kullanıcı kararı (2026-08-15): rakip gibi kendi scraping'imiz CANLI opsiyon olur.
Mod: scraper (canlı) | licensed (lisanslı feed, gelecek) | mock (sentetik)."""
import re
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


async def scrape_booking_city(city: str, checkin: str, checkout: str) -> dict:
    """Booking.com arama sayfasından halka açık fiyatları dener; bloklama/parse hatasında boş döner."""
    url = "https://www.booking.com/searchresults.html"
    params = {"ss": city, "checkin": checkin, "checkout": checkout,
              "group_adults": 2, "no_rooms": 1, "selected_currency": "EUR"}
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True,
                                     headers={"User-Agent": UA, "Accept-Language": "en"}) as client:
            r = await client.get(url, params=params)
        if r.status_code != 200:
            return {"ok": False, "reason": f"HTTP {r.status_code}", "hotels": []}
        html = r.text
        names = re.findall(r'data-testid="title"[^>]*>([^<]{3,80})<', html)
        prices = re.findall(r'data-testid="price-and-discounted-price"[^>]*>[^0-9]*([\d.,]+)', html)
        if not prices:
            prices = re.findall(r'[€$£₺]\s?([\d.,]{2,9})', html)[:40]
        hotels = []
        for i, p in enumerate(prices[:30]):
            try:
                val = float(p.replace(".", "").replace(",", ".")) if "," in p else float(p.replace(",", ""))
            except ValueError:
                continue
            if 15 <= val <= 5000:
                hotels.append({"name": names[i] if i < len(names) else f"Otel {i+1}", "price": round(val, 2)})
        return {"ok": len(hotels) > 0, "reason": "" if hotels else "parse boş (bot koruması olası)",
                "hotels": hotels}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200], "hotels": []}


def create_live_scraper_router(db, require_roles):
    router = APIRouter(prefix="/live-scraper", tags=["live-scraper"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}/status")
    async def status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await db.compset_source_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        last = await db.compset_live.find_one({"property_id": pid}, {"_id": 0},
                                              sort=[("scanned_at", -1)])
        cnt = await db.compset_live.count_documents({"property_id": pid})
        return {"property_id": pid, "mode": cfg.get("mode", "mock"),
                "city": cfg.get("city", ""), "total_scans": cnt,
                "last_scan": {"at": last.get("scanned_at"), "source": last.get("source"),
                              "hotels": last.get("hotel_count")} if last else None,
                "modes": ["scraper", "licensed", "mock"],
                "note": "Uyum notu: scraper modu YALNIZCA kamuya açık fiyatları toplar (D1 ilkesi rev.2). Licensed mod gelecekte lisanslı feed'e bağlanır."}

    @router.put("/{pid}/config")
    async def set_config(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        mode = data.get("mode") if data.get("mode") in ("scraper", "licensed", "mock") else "mock"
        await db.compset_source_config.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "mode": mode, "city": (data.get("city") or "").strip(),
                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, "mode": mode}

    @router.post("/{pid}/scan")
    async def scan(pid: str, data: dict = None, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await db.compset_source_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "city": 1}) or {}
        city = (data or {}).get("city") or cfg.get("city") or prop.get("city") or "Istanbul"
        checkin = (data or {}).get("checkin") or (datetime.now(timezone.utc).date() + timedelta(days=7)).isoformat()
        checkout = (datetime.strptime(checkin, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
        mode = cfg.get("mode", "mock")
        now = datetime.now(timezone.utc).isoformat()
        source, hotels, reason = "mock", [], ""
        if mode == "scraper":
            res = await scrape_booking_city(city, checkin, checkout)
            if res["ok"]:
                source, hotels = "scraped_live", res["hotels"]
            else:
                reason = res["reason"]
        if not hotels:
            import random
            base = 90 + random.random() * 60
            hotels = [{"name": f"Compset Otel {i+1}", "price": round(base * (0.8 + random.random() * 0.5), 2)}
                      for i in range(8)]
            source = "mock_fallback" if mode == "scraper" else "mock"
        prices = [h["price"] for h in hotels]
        doc = {"id": str(uuid.uuid4()), "property_id": pid, "city": city, "date": checkin,
               "source": source, "fallback_reason": reason, "hotel_count": len(hotels),
               "hotels": hotels[:30], "avg_price": round(sum(prices) / len(prices), 2),
               "min_price": min(prices), "max_price": max(prices), "scanned_at": now}
        await db.compset_live.insert_one(dict(doc))
        doc.pop("_id", None)
        return {"ok": True, "mode": mode, **doc}

    @router.get("/{pid}/history")
    async def history(pid: str, limit: int = 10, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.compset_live.find(
            {"property_id": pid}, {"_id": 0, "hotels": 0}).sort("scanned_at", -1).to_list(min(limit, 50))
        return {"scans": rows}

    return router
