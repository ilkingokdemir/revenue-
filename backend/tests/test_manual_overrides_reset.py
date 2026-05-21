"""
Verify manual-override clear endpoints behave correctly (null clears the value).
Frontend reset buttons (adr-reset / room-count-reset / hero-occupancy-clear)
call these endpoints with the corresponding null payload.
"""
import os
import asyncio
import httpx


API = os.environ.get("API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


def test_manual_overrides_can_be_cleared():
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            pid = "test-reset-manual-pid"
            # Set a manual room count
            r = await client.post(f"{API}/revenue/market-robot/{pid}/room-count/manual", headers=h, json={"room_count": 25})
            assert r.status_code == 200 and r.json()["manual_room_count"] == 25
            # Clear it (frontend X button sends null)
            r = await client.post(f"{API}/revenue/market-robot/{pid}/room-count/manual", headers=h, json={"room_count": None})
            assert r.status_code == 200 and r.json().get("cleared") is True

            # Set manual ADR
            r = await client.post(f"{API}/revenue/market-robot/{pid}/adr/manual", headers=h, json={"adr": 150})
            assert r.status_code == 200
            # Clear it
            r = await client.post(f"{API}/revenue/market-robot/{pid}/adr/manual", headers=h, json={"adr": None})
            assert r.status_code == 200 and r.json().get("cleared") is True

            # Set manual occupancy
            r = await client.post(f"{API}/revenue/market-robot/{pid}/occupancy/manual", headers=h, json={"occupancy": 0.85})
            assert r.status_code == 200
            # Clear it
            r = await client.post(f"{API}/revenue/market-robot/{pid}/occupancy/manual", headers=h, json={"occupancy": None})
            assert r.status_code == 200 and r.json().get("cleared") is True
    asyncio.run(_go())
