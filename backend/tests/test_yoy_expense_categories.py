"""
Tests for expense category classification + by_category breakdown (iter 333).
"""
import os
import asyncio
import httpx
from backend.utils.yoy_parser import classify_expense, EXPENSE_CATEGORY_NAMES


API = os.environ.get("API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


def test_classify_known_labels():
    cases = [
        ("rent", "Kira"),
        ("Rent 2025", "Kira"),
        ("kira aralik", "Kira"),
        ("commission", "Komisyon"),
        ("comissoin", "Komisyon"),
        ("temizlik ", "Temizlik"),
        ("cleaning crew", "Temizlik"),
        ("council tax", "Belediye/Council"),
        ("personel maas", "Personel"),
        ("KDV", "Vergi"),
        ("electricity bill", "Enerji & Su"),
        ("internet aboneliği", "İnternet & İletişim"),  # internet wins on longer match
        ("marketing reklam", "Pazarlama"),
        ("stripe fee", "Banka & Komisyon Ücretleri"),
        ("food cost", "Yiyecek & İçecek"),
        ("aslajdkasjd", "Diğer"),
        ("", "Diğer"),
    ]
    for label, expected in cases:
        got = classify_expense(label)
        assert got == expected, f"classify_expense({label!r}) = {got!r}, expected {expected!r}"


def test_category_list_endpoint():
    async def _go():
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            r = await client.get(f"{API}/revenue/market-robot/expense-categories", headers=h)
            assert r.status_code == 200
            cats = r.json()["categories"]
            assert "Kira" in cats and "Komisyon" in cats and "Diğer" in cats
            assert cats == EXPENSE_CATEGORY_NAMES
    asyncio.run(_go())


def test_performance_by_category_breakdown():
    """Upload manual expenses → confirm → check by_category is computed."""
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = r.json().get("token") or r.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            pid = "test-category-breakdown-pytest"
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-expenses", headers=h)
            payload = {
                "entries": [],
                "expenses": [
                    {"label": "Rent", "amount": 60000, "period": "annual", "category": "Kira"},
                    {"label": "Cleaning crew", "amount": 200, "period": "monthly", "category": "Temizlik"},
                    {"label": "Council tax", "amount": 8000, "period": "annual"},  # auto-classified
                    {"label": "OTA commission", "amount": 12000, "period": "annual", "category": "Komisyon"},
                ],
                "source_kind": "manual",
                "replace_expenses": True,
            }
            r = await client.post(f"{API}/revenue/market-robot/{pid}/yoy-upload/confirm", headers=h, json=payload)
            assert r.status_code == 200
            perf = await client.get(f"{API}/revenue/market-robot/{pid}/performance", headers=h)
            e = perf.json()["annual_forecast"]["expenses"]
            by_cat = {b["category"]: b for b in e["by_category"]}
            assert "Kira" in by_cat
            assert by_cat["Kira"]["annual_amount"] == 60000.0
            assert by_cat["Temizlik"]["annual_amount"] == 200 * 12  # monthly → annualised
            assert "Belediye/Council" in by_cat  # auto-classified from "Council tax"
            assert by_cat["Belediye/Council"]["annual_amount"] == 8000.0
            assert by_cat["Komisyon"]["annual_amount"] == 12000.0
            # Top category should be Kira by share
            assert e["by_category"][0]["category"] == "Kira"
            total_share = sum(b["share_pct"] for b in e["by_category"])
            assert 99.5 <= total_share <= 100.5, f"share_pct sum off: {total_share}"
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-expenses", headers=h)
    asyncio.run(_go())
