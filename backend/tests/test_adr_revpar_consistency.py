"""Regression: ADR ve RevPAR ilişkisi (iter 351).

User report: "camden adr 80 iken revpar nasil 93 olabilir arada bag kurlmamis"
Root cause: `annual_forecast.adr` base_rate'i echo ediyordu; aylık scraped
ADR'ler çok daha yüksek olduğunda effective ADR < RevPAR çelişkisi doğdu.
Fix: effective_adr = annual_gross / total_room_nights_sold (room-nights ağırlıklı).

Bu test her property için: RevPAR ≤ ADR (gross) garantisini doğrular.
"""
import os
import asyncio
import httpx


API = os.environ.get("API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


def test_revpar_le_adr_for_seeded_properties():
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}

            for pid in ["camden-suites", "aldgate-flats", "whitechapel-hotel", "default"]:
                r = await client.get(f"{API}/revenue/market-robot/{pid}/performance", headers=h)
                assert r.status_code == 200, f"{pid}: {r.text}"
                af = r.json()["annual_forecast"]
                adr = af["adr"]
                revpar = af["revpar"]
                occ = af["avg_occupancy_pct"]
                # Core invariant: RevPAR = ADR × occupancy → RevPAR ≤ ADR
                assert revpar <= adr + 0.05, f"{pid}: revpar {revpar} > adr {adr}"
                # Sanity: revpar ≈ adr × (occ/100) ±2 GBP
                expected = adr * occ / 100.0
                assert abs(revpar - expected) < 2.0, \
                    f"{pid}: revpar {revpar} vs adr*occ {expected:.2f} drift > £2"
                # New fields are exposed
                assert "adr_base_rate" in af and "adr_net" in af and "revpar_net" in af
                assert af["revpar_net"] <= af["adr_net"] + 0.05

    asyncio.run(_go())
