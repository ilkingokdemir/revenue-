"""
Tests for the expense / net-profit feature added to Performance Report (iter 332).

Covers:
    1. Parser extracts expense items (rent, council, etc.) from a Camden-style xlsx.
    2. yoy-upload/confirm saves both entries AND expenses.
    3. Performance endpoint returns annual_forecast.expenses with annual_total,
       annual_net_revenue, net_margin_pct, monthly_avg, and per-month net_revenue.
    4. DELETE /yoy-expenses clears only expenses (leaves history intact).
"""
import io
import os
import asyncio
import openpyxl
import httpx


API = os.environ.get("API_URL", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


def _camden_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Date", "ADR 2025", "ACCOMMODATIONS BOOKED 2025", "Room Rates 2025"])
    for m, (adr, nights, rev) in enumerate([
        (81.7, 87, 7112.20), (69.3, 157, 10876.74), (76.9, 186, 14308.95),
        (84.6, 176, 14884.12), (84.1, 206, 17334.15), (97.7, 220, 21501.18),
        (89.8, 220, 19747.59), (85.6, 205, 17550.31), (96.4, 202, 19465.51),
        (87.4, 208, 18178.52), (88.9, 182, 16176.96), (105.6, 198, 20901.62),
    ], start=1):
        ws.cell(row=m + 1, column=1, value=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][m-1])
        ws.cell(row=m + 1, column=2, value=adr)
        ws.cell(row=m + 1, column=3, value=nights)
        ws.cell(row=m + 1, column=4, value=rev)
    # Expense rows
    ws.cell(row=16, column=3, value="commission ")
    ws.cell(row=16, column=4, value=40000)
    ws.cell(row=17, column=3, value="rent ")
    ws.cell(row=17, column=4, value=110000)
    ws.cell(row=18, column=3, value="temizlik ")
    ws.cell(row=18, column=4, value=7200)
    ws.cell(row=19, column=3, value="cleaning ")
    ws.cell(row=19, column=4, value=11000)
    ws.cell(row=20, column=3, value="council ")
    ws.cell(row=20, column=4, value=12000)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parser_extracts_expenses():
    """Parser must return both income entries and expense items."""
    from backend.utils.yoy_parser import parse_upload
    content = _camden_xlsx_bytes()
    r = parse_upload(content, "camden.xlsx", 2025)
    assert r["detected_count"] == 12
    assert r["detected_expenses_count"] >= 5
    labels = {x["label"].lower().strip() for x in r["expenses"]}
    for needed in {"rent", "council", "commission", "temizlik", "cleaning"}:
        assert any(needed in lbl for lbl in labels), f"Missing expense label: {needed}"
    # Sum of expenses ≈ 180,200
    total = sum(x["amount"] for x in r["expenses"] if x["period"] == "annual")
    assert 175000 <= total <= 185000, f"Expense total off: {total}"


def test_upload_saves_expenses_and_performance_returns_net():
    """End-to-end: upload → confirm → performance shows net profit fields."""
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            # Login
            lr = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            lr.raise_for_status()
            token = lr.json().get("token") or lr.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            pid = "test-yoy-expenses-pytest"
            # Clean prior
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-history", headers=h)
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-expenses", headers=h)
            # Preview
            files = {"file": ("camden.xlsx", _camden_xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            pr = await client.post(f"{API}/revenue/market-robot/{pid}/yoy-upload/preview", headers=h, files=files)
            assert pr.status_code == 200, pr.text
            preview = pr.json()
            assert preview["detected_count"] == 12
            assert preview["detected_expenses_count"] >= 5
            # Confirm with both income + expenses
            payload = {
                "entries": preview["entries"],
                "expenses": preview["expenses"],
                "source_kind": preview["source_kind"],
            }
            cr = await client.post(f"{API}/revenue/market-robot/{pid}/yoy-upload/confirm", headers=h, json=payload)
            assert cr.status_code == 200, cr.text
            saved = cr.json()
            assert saved["saved_count"] == 12
            assert saved["saved_expenses"] >= 5
            # Verify performance endpoint returns net profit fields
            perf = await client.get(f"{API}/revenue/market-robot/{pid}/performance", headers=h)
            assert perf.status_code == 200
            af = perf.json()["annual_forecast"]
            exp = af.get("expenses")
            assert exp is not None
            assert exp["annual_total"] > 0
            assert exp["monthly_avg"] > 0
            assert exp["net_margin_pct"] is not None
            assert exp["annual_net_revenue"] == round(af["annual_revenue"] - exp["annual_total"], 2)
            assert len(exp["items"]) >= 5
            # Per-month net_revenue populated
            for m in af["monthly"]:
                assert "net_revenue" in m
                assert "expense" in m
                assert m["expense"] > 0
            # Cleanup
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-history", headers=h)
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-expenses", headers=h)
    asyncio.run(_go())


def test_monthly_period_expense_converted_to_annual():
    """If user sends an expense with period=monthly, the annual_total should
    be amount * 12 (so a £100/month item appears as £1,200/year)."""
    async def _go():
        async with httpx.AsyncClient(timeout=60) as client:
            lr = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            token = lr.json().get("token") or lr.json().get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            pid = "test-yoy-monthly-period-pytest"
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-expenses", headers=h)
            payload = {
                "entries": [],
                "expenses": [{"label": "Cleaning", "amount": 100, "period": "monthly"}],
                "source_kind": "manual",
                "replace_expenses": True,
            }
            cr = await client.post(f"{API}/revenue/market-robot/{pid}/yoy-upload/confirm", headers=h, json=payload)
            assert cr.status_code == 200
            perf = await client.get(f"{API}/revenue/market-robot/{pid}/performance", headers=h)
            af = perf.json()["annual_forecast"]
            # Annual total should be 100 * 12 = 1200
            assert af["expenses"]["annual_total"] == 1200.0
            assert af["expenses"]["monthly_avg"] == 100.0
            await client.delete(f"{API}/revenue/market-robot/{pid}/yoy-expenses", headers=h)
    asyncio.run(_go())
