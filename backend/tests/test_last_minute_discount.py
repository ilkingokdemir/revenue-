"""
Last-minute discount feature tests (iter 336).

User asked: discount option (10%/20%/30%) that applies to monthly + annual
revenue forecast. Verifies:
    • POST /last-minute-discount persists config to property doc
    • GET /performance applies the discount to forecast and returns last_minute meta
    • Disabling reverts forecast to gross figures
    • Annual total reflects discount: annual = gross × (1 - discount_pct × share_pct)
"""
import os
import asyncio
import httpx


API = os.environ.get("API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PID = "test-lm-discount-pid"


def test_last_minute_discount_lifecycle():
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}

            # 1. Baseline (no discount)
            r = await client.post(f"{API}/revenue/market-robot/{PID}/last-minute-discount",
                                   headers=h, json={"enabled": False, "discount_pct": 0, "share_pct": 0})
            assert r.status_code == 200
            r = await client.get(f"{API}/revenue/market-robot/{PID}/performance", headers=h)
            af = r.json()["annual_forecast"]
            baseline_annual = af["annual_revenue"]
            assert af["last_minute"]["enabled"] is False
            assert af["last_minute"]["factor"] == 1.0

            # 2. Apply 20% discount on 20% of nights → factor = 1 - 0.20*0.20 = 0.96
            r = await client.post(f"{API}/revenue/market-robot/{PID}/last-minute-discount",
                                   headers=h, json={"enabled": True, "discount_pct": 20, "share_pct": 20})
            assert r.status_code == 200
            r = await client.get(f"{API}/revenue/market-robot/{PID}/performance", headers=h)
            af = r.json()["annual_forecast"]
            assert af["last_minute"]["enabled"] is True
            assert af["last_minute"]["factor"] == 0.96
            # Annual should be ~96% of baseline (within rounding)
            assert abs(af["annual_revenue"] - baseline_annual * 0.96) < 5, \
                f"annual {af['annual_revenue']} not ~96% of {baseline_annual}"
            # Monthly rows should each carry gross_revenue + last_minute_discount
            for m in af["monthly"]:
                assert m["gross_revenue"] > m["revenue"]
                assert abs(m["last_minute_discount"] - (m["gross_revenue"] - m["revenue"])) < 0.01

            # 3. Try 30% discount → factor = 1 - 0.30*0.20 = 0.94
            r = await client.post(f"{API}/revenue/market-robot/{PID}/last-minute-discount",
                                   headers=h, json={"enabled": True, "discount_pct": 30, "share_pct": 20})
            r = await client.get(f"{API}/revenue/market-robot/{PID}/performance", headers=h)
            af = r.json()["annual_forecast"]
            assert af["last_minute"]["factor"] == 0.94

            # 4. Disable → factor back to 1.0
            r = await client.post(f"{API}/revenue/market-robot/{PID}/last-minute-discount",
                                   headers=h, json={"enabled": False, "discount_pct": 0, "share_pct": 20})
            r = await client.get(f"{API}/revenue/market-robot/{PID}/performance", headers=h)
            af = r.json()["annual_forecast"]
            assert af["last_minute"]["enabled"] is False
            assert af["last_minute"]["factor"] == 1.0
            assert af["annual_revenue"] == baseline_annual

    asyncio.run(_go())


def test_invalid_discount_returns_400():
    async def _go():
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            # discount_pct > 50 must reject
            r = await client.post(f"{API}/revenue/market-robot/{PID}/last-minute-discount",
                                   headers=h, json={"enabled": True, "discount_pct": 75, "share_pct": 20})
            assert r.status_code == 400
            # share_pct > 100 must reject
            r = await client.post(f"{API}/revenue/market-robot/{PID}/last-minute-discount",
                                   headers=h, json={"enabled": True, "discount_pct": 20, "share_pct": 150})
            assert r.status_code == 400
    asyncio.run(_go())
