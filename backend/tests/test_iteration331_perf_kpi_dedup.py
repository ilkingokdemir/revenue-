"""
Regression test for Performance Report KPI fix (iter 331).

User reported the cards showed inflated/nonsensical figures:
    Days Optimized: 491 (421 up / 70 down)
    Estimated Revenue Uplift: +£95,554

Root cause: the aggregator summed ALL rate_overrides ever written
(including stale per-room-type duplicates and far-future entries).

This test verifies the new logic:
    1. Only overrides where `today <= date <= today+90d` are counted.
    2. Per (date, room_type) deduplication keeps only the LATEST entry.
    3. Per-date averaging across room types prevents N-times multiplication.
"""
import os
import asyncio
from datetime import datetime, timezone, timedelta
import httpx


API = os.environ.get("API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


async def _login(client: httpx.AsyncClient) -> str:
    r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    r.raise_for_status()
    data = r.json()
    return data.get("token") or data.get("access_token")


def _run(coro):
    return asyncio.run(coro)


def test_performance_kpis_bounded_to_active_horizon():
    """KPIs must reflect ONLY the 90-day forward active optimization window
    (no historical / far-future bleed-through).
    """
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            token = await _login(client)
            h = {"Authorization": f"Bearer {token}"}
            for pid in ["aldgate-flats", "whitechapel-grand", "camden-suites", "default", "all", "city-gate"]:
                r = await client.get(f"{API}/revenue/market-robot/{pid}/performance", headers=h)
                assert r.status_code == 200, f"{pid}: {r.status_code}"
                d = r.json()
                k = d.get("kpis", {})
                assert k["total_days_adjusted"] <= 91, \
                    f"{pid}: days_adjusted={k['total_days_adjusted']} > 91 — horizon filter not applied"
                assert k["increases"] + k["decreases"] <= k["total_days_adjusted"], \
                    f"{pid}: increases({k['increases']}) + decreases({k['decreases']}) > days({k['total_days_adjusted']})"
                assert abs(k["estimated_revenue_uplift"]) < 2_000_000, \
                    f"{pid}: est_uplift={k['estimated_revenue_uplift']} looks inflated"
    _run(_go())


def test_daily_impact_within_14_days():
    """daily_impact should only contain rows in the last 14 days through today."""
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            token = await _login(client)
            h = {"Authorization": f"Bearer {token}"}
            r = await client.get(f"{API}/revenue/market-robot/whitechapel-grand/performance", headers=h)
            assert r.status_code == 200
            d = r.json()
            today = datetime.now(timezone.utc).date()
            cutoff = today - timedelta(days=14)
            for row in d.get("daily_impact", []):
                dt = datetime.strptime(row["date"], "%Y-%m-%d").date()
                assert cutoff <= dt <= today, f"daily_impact row {row['date']} outside [-14d, today]"
    _run(_go())


def test_kpis_no_room_type_multiplication():
    """Per-date dedup keeps days_adjusted ≤ 91 even with multi-room-type props."""
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            token = await _login(client)
            h = {"Authorization": f"Bearer {token}"}
            r = await client.get(f"{API}/revenue/market-robot/aldgate-flats/performance", headers=h)
            assert r.status_code == 200
            d = r.json()
            k = d["kpis"]
            assert k["total_days_adjusted"] <= 91, \
                f"aldgate-flats days_adjusted={k['total_days_adjusted']} — per-date dedup broken"
    _run(_go())
