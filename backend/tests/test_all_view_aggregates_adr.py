"""
Regression test: when viewing "all" or "default" property (no property-specific
scraped prices), the performance endpoint must aggregate monthly ADRs across
all configured branches instead of falling back to the £100 default.

User-reported bug: "All Branches" view showed £100 ADR fallback even though
multiple branches had scraped Booking.com prices.
"""
import os
import asyncio
import httpx


API = os.environ.get("API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


def test_all_view_aggregates_branch_adrs():
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            r = await client.get(f"{API}/revenue/market-robot/all/performance", headers=h)
            assert r.status_code == 200
            d = r.json()
            assert d.get("adr_source") == "aggregated_branches", \
                f"Expected aggregated_branches, got {d.get('adr_source')}"
            # ADR should be well above the £100 fallback (real London market ~£150-£300)
            assert d.get("base_rate", 0) > 110, \
                f"All-branches ADR={d.get('base_rate')} suspiciously low — aggregation may not be working"
            # At least one month should have a scraped override
            af = d["annual_forecast"]
            assert af["scraped_months_count"] > 0, \
                f"scraped_months_count={af['scraped_months_count']} — aggregation produced no overrides"
    asyncio.run(_go())


def test_specific_property_with_scraped_prices_uses_them():
    """For a property that HAS scraped per-month prices, those override the
    aggregate (don't accidentally get blended with other branches)."""
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            r = await client.get(f"{API}/revenue/market-robot/camden-suites/performance", headers=h)
            assert r.status_code == 200
            d = r.json()
            af = d["annual_forecast"]
            # camden-suites has its own scraped prices → not aggregated
            assert d.get("adr_source") != "aggregated_branches"
            assert af["scraped_months_count"] > 0
    asyncio.run(_go())
