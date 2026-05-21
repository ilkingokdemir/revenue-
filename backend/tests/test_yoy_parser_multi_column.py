"""
Regression test for YoY parser — multi-column Excel where the month column
sits alongside ADR, occupancy AND revenue columns. The parser must pick the
revenue column (the largest numeric one), not ADR or nights.

User-reported file: camden-suites 2025.xlsx
    Date | ADR 2025 | ACCOMMODATIONS BOOKED 2025 | Room Rates 2025
    Jan  | 81.74    | 87                          | 7112.20
    ...
Expected: 12 entries with the Room Rates column values (£7,112 → £20,901),
NOT the ADR column (£81 → £105).
"""
import io
import openpyxl
from backend.utils.yoy_parser import parse_spreadsheet


def _build_camden_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Date", "ADR 2025", "ACCOMMODATIONS BOOKED 2025", "Room Rates 2025"])
    rows = [
        ("Jan", 81.74, 87, 7112.20),
        ("Feb", 69.27, 157, 10876.74),
        ("Mar", 76.92, 186, 14308.95),
        ("Apr", 84.56, 176, 14884.12),
        ("May", 84.14, 206, 17334.15),
        ("Jun", 97.73, 220, 21501.18),
        ("Jul", 89.76, 220, 19747.59),
        ("Aug", 85.61, 205, 17550.31),
        ("Sep", 96.36, 202, 19465.51),
        ("Oct", 87.39, 208, 18178.52),
        ("Nov", 88.88, 182, 16176.96),
        ("Dec", 105.56, 198, 20901.62),
    ]
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_multi_column_xlsx_picks_revenue_not_adr():
    content = _build_camden_xlsx()
    entries, _expenses = parse_spreadsheet(content, "camden_2025.xlsx", 2025)
    assert len(entries) == 12, f"Expected 12 months, got {len(entries)}"
    jan = next((e for e in entries if e["month"] == 1), None)
    assert jan is not None
    assert jan["revenue"] == 7112.20, \
        f"Jan revenue should be 7112.20 (Room Rates), got {jan['revenue']} (likely picked ADR)"
    total = sum(e["revenue"] for e in entries)
    assert abs(total - 198037.85) < 1.0, f"Total mismatch: {total} vs expected 198037.85"


def test_multi_column_xlsx_month_order():
    content = _build_camden_xlsx()
    entries, _expenses = parse_spreadsheet(content, "camden_2025.xlsx", 2025)
    months = [e["month"] for e in entries]
    assert months == list(range(1, 13)), f"Months not in order: {months}"
