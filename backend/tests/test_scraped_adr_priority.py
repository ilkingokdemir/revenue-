"""
Regression: when a property has scraped Booking.com per-month ADRs, the
base_rate (headline ADR) must use that scraped average — NOT the £100
fallback — even when no room_types are configured.

User complaint: cleared manual ADR on whitechapel-hotel → ADR dropped to
£100 fallback despite having 11/12 months of scraped Booking.com data.
"""
import os
import asyncio
import httpx


API = os.environ.get("API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


def test_scraped_per_month_adrs_become_base_rate():
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            # whitechapel-hotel has 11 months of scraped prices and was hitting
            # the £100 fallback before. Verify it now uses booking_com_scraped.
            r = await client.get(f"{API}/revenue/market-robot/whitechapel-hotel/performance", headers=h)
            assert r.status_code == 200
            d = r.json()
            assert d["adr_source"] == "booking_com_scraped", \
                f"Expected booking_com_scraped, got {d['adr_source']}"
            assert d["base_rate"] > 150, \
                f"Scraped London-market ADR should be £150-£300, got £{d['base_rate']}"
            assert d["annual_forecast"]["scraped_months_count"] >= 8
    asyncio.run(_go())


def test_priority_order_manual_beats_scraped():
    """Manual ADR override still wins over scraped (operator intent first)."""
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            try:
                # Set manual ADR
                r = await client.post(f"{API}/revenue/market-robot/whitechapel-hotel/adr/manual",
                                       headers=h, json={"adr": 999})
                assert r.status_code == 200
                r = await client.get(f"{API}/revenue/market-robot/whitechapel-hotel/performance", headers=h)
                d = r.json()
                assert d["adr_source"] == "manual", f"got {d['adr_source']}"
                assert d["base_rate"] == 999
            finally:
                # Always clear manual override so we don't pollute the demo property
                await client.post(f"{API}/revenue/market-robot/whitechapel-hotel/adr/manual",
                                  headers=h, json={"adr": None})
    asyncio.run(_go())
