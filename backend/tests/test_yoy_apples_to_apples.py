"""
Regression test for YoY apples-to-apples comparison (iter 334).

Bug user reported: YoY Δ showing +71,354% on a property with only 2 months of
prev-year history but 12 months of forecast. The full-year forecast (£437k)
was being compared to a 2-month sample (£612), giving nonsense.

Fix: only sum forecast months for which prev_year_revenue > 0 → apples-apples.
"""
import os
import asyncio
import httpx


API = os.environ.get("API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


def test_yoy_comparison_is_apples_to_apples():
    """If only 2 of 12 forecast months have prev-year data, the comparison
    must use only those 2 months of forecast (not the full 12-month total)."""
    from datetime import datetime, timezone
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            pid = "test-yoy-apples-pytest"
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-history", headers=h)
            # Forecast covers next 12 months starting today. Upload prev-year
            # data for ONLY the first 2 months of that window (i.e. this month
            # and next month, but one year earlier).
            now = datetime.now(timezone.utc)
            m1, m2 = now.month, (now.month % 12) + 1
            y1 = now.year - 1
            y2 = (now.year - 1) if m2 > m1 else now.year  # roll over Dec→Jan
            payload = {
                "entries": [
                    {"year": y1, "month": m1, "revenue": 1000.0},
                    {"year": y2, "month": m2, "revenue": 1200.0},
                ],
                "expenses": [],
                "source_kind": "manual",
            }
            r = await client.post(f"{API}/revenue/market-robot/{pid}/yoy-upload/confirm", headers=h, json=payload)
            assert r.status_code == 200
            perf = await client.get(f"{API}/revenue/market-robot/{pid}/performance", headers=h)
            assert perf.status_code == 200
            af = perf.json()["annual_forecast"]
            yoy = af["yoy_comparison"]
            assert yoy["months_with_history"] == 2, f"got {yoy['months_with_history']}"
            assert yoy["prev_year_total_revenue"] == 2200.0
            assert yoy["this_year_forecast_revenue"] < af["annual_revenue"]
            assert yoy["full_year_forecast"] == af["annual_revenue"]
            assert abs(yoy["delta_pct"]) < 5000, f"delta_pct={yoy['delta_pct']} still inflated"
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-history", headers=h)
    asyncio.run(_go())


def test_yoy_full_12_months_uses_full_forecast():
    """With prev-year data for all 12 forecast months, comparable == full."""
    from datetime import datetime, timezone
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            pid = "test-yoy-full12-pytest"
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-history", headers=h)
            # Generate prev-year keys for the next 12 forecast months (today → +12)
            now = datetime.now(timezone.utc)
            entries = []
            y, m = now.year, now.month
            for i in range(12):
                py = y - 1
                entries.append({"year": py, "month": m, "revenue": 5000.0 + i * 100})
                m += 1
                if m > 12:
                    m = 1
                    y += 1
            payload = {"entries": entries, "expenses": [], "source_kind": "manual"}
            r = await client.post(f"{API}/revenue/market-robot/{pid}/yoy-upload/confirm", headers=h, json=payload)
            assert r.status_code == 200
            perf = await client.get(f"{API}/revenue/market-robot/{pid}/performance", headers=h)
            af = perf.json()["annual_forecast"]
            yoy = af["yoy_comparison"]
            assert yoy["months_with_history"] == 12, f"got {yoy['months_with_history']}"
            assert yoy["this_year_forecast_revenue"] == af["annual_revenue"]
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-history", headers=h)
    asyncio.run(_go())
