"""Regression: Manuel ADR sovereign override (iter 352).

User report: "adr manuel degistiryorum ama degismiyor"
Root cause: scraped per-month overrides her zaman manual_adr'yi (base_rate)
domine ediyordu. Effective ADR sadece scrape edilmemiş aylar için base_rate'i
yansıttığından, manuel ADR değiştirmek hero ADR/RevPAR'ı görünür şekilde
değiştirmiyordu.

Fix: adr_source == 'manual' ise monthly_adr_overrides = {} (boş).
Test: manuel ADR set/değiştir → effective ADR == manuel değer.
"""
import os
import asyncio
import httpx


API = os.environ.get("API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PID = "camden-suites"


def test_manual_adr_sovereign_override():
    """Manuel ADR ayarlandığında effective ADR ona eşit olmalı, scraped data
    onu override etmemeli."""
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}

            # Önce eski değeri kaydet (sonra restore et)
            r = await client.get(f"{API}/revenue/market-robot/{PID}/performance", headers=h)
            original_manual = r.json()["annual_forecast"]["adr_base_rate"]

            for test_adr in [120, 175, 250]:
                # Set manual ADR
                r = await client.post(f"{API}/revenue/market-robot/{PID}/adr/manual",
                                       headers=h, json={"adr": test_adr})
                assert r.status_code == 200, r.text

                # Verify effective ADR matches manual + RevPAR consistent
                r = await client.get(f"{API}/revenue/market-robot/{PID}/performance", headers=h)
                d = r.json()
                af = d["annual_forecast"]
                assert d["adr_source"] == "manual", f"adr_source {d.get('adr_source')} != manual"
                assert abs(af["adr"] - test_adr) < 1.0, \
                    f"effective ADR {af['adr']} != manual {test_adr}"
                assert abs(af["adr_base_rate"] - test_adr) < 1.0
                # RevPAR = ADR × occ
                expected_revpar = af["adr"] * af["avg_occupancy_pct"] / 100.0
                assert abs(af["revpar"] - expected_revpar) < 2.0, \
                    f"revpar {af['revpar']} != adr×occ {expected_revpar:.2f}"
                # All 12 monthly ADRs should equal the manual value (no scrape override)
                for m in af["monthly"]:
                    assert abs(m["adr"] - test_adr) < 1.0, \
                        f"month {m['month_key']} ADR {m['adr']} should == manual {test_adr}"
                    assert m["adr_origin"] == "estimated", \
                        f"month {m['month_key']} origin {m['adr_origin']} should be 'estimated' (manual sovereign)"

            # Restore original
            await client.post(f"{API}/revenue/market-robot/{PID}/adr/manual",
                              headers=h, json={"adr": original_manual})

    asyncio.run(_go())
