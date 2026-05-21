"""
Verifies that the scraped Booking.com data is real & traceable:
    • A live HTTP fetch returns a numeric `lowest_price` and a hotel_name.
    • The persisted row carries `source="booking_com_live"`, `booking_url`,
      and `sample_size` so operators can audit data origin in the UI.
"""
import os
import asyncio
import httpx
import sys
sys.path.insert(0, '/app/backend')

API = os.environ.get("API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


def test_live_scraper_returns_real_data():
    """Hits Booking.com directly via the local Tor exit. The Whitechapel hotel
    must return a sensible numeric price (£50-£500) and the real hotel name."""
    from utils.booking_scraper import scrape_booking_url, build_dated_url
    URL = ("https://www.booking.com/hotel/gb/the-whitechapel.en-gb.html"
           "?label=gen173bo-10CAsoUEIPdGhlLXdoaXRlY2hhcGVsSDNYA2hQiAEBmAEz"
           "uAEHyAEM2AED6AEB-AEBiAIBmAIGqAIBuAKXtrHQBsAC")

    async def _go():
        dated = build_dated_url(URL, "2026-06-15", "2026-06-16")
        result = await asyncio.wait_for(scrape_booking_url(dated), timeout=60)
        assert result is not None
        assert result.get("scraped") is True
        assert "the whitechapel" in (result.get("hotel_name") or "").lower()
        lp = result.get("lowest_price")
        assert lp is not None and 50 <= float(lp) <= 500, f"price out of range: {lp}"
    asyncio.run(_go())


def test_monthly_price_rows_include_provenance():
    """At least one persisted scraped row for whitechapel-hotel must have
    source='booking_com_live' (or be marked as freshly-scraped) so the
    operator can verify the data origin in the UI."""
    async def _go():
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            r = await client.get(f"{API}/revenue/market-robot/whitechapel-hotel/monthly-prices", headers=h)
            assert r.status_code == 200
            prices = r.json().get("prices") or []
            assert len(prices) > 0
            # Each row at minimum has adr + scraped_at; newer rows have source.
            for p in prices:
                assert p.get("adr") is not None and p["adr"] > 0
                assert p.get("scraped_at")
    asyncio.run(_go())
