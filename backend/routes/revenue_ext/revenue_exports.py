"""
Revenue Reports & Export — CSV, Excel, and PDF-ready data exports
Performance, Pickup, Budget Variance, Profit OS, Forecasting, Distribution
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone, timedelta
from typing import Dict
import csv
import io
import calendar
import logging

logger = logging.getLogger(__name__)


def create_revenue_exports_router(db, require_roles):
    router = APIRouter()

    async def _get_props(property_id):
        if property_id == "all":
            return await db.properties.find({}, {"_id": 0}).to_list(50)
        p = await db.properties.find_one({"id": property_id}, {"_id": 0})
        return [p] if p else []

    async def _total_rooms(props):
        t = 0
        for p in props:
            t += await db.rooms.count_documents({"property_id": p.get("id", "")}) or 10
        return max(t, 1)

    async def _day_stats(props, total_rooms, date_str):
        booked = 0; rev = 0
        for p in props:
            pid = p.get("id", "")
            b = await db.bookings.count_documents({"property_id": pid, "check_in": {"$lte": date_str}, "check_out": {"$gt": date_str}, "status": {"$ne": "cancelled"}})
            booked += b
            bks = await db.bookings.find({"property_id": pid, "check_in": {"$lte": date_str}, "check_out": {"$gt": date_str}}, {"_id": 0, "total_price": 1, "nights": 1}).to_list(200)
            rev += sum(float(x.get("total_price", 0) or 0) / max(int(x.get("nights", 1) or 1), 1) for x in bks)
        occ = min(100, round((booked / total_rooms) * 100))
        adr = round(rev / max(booked, 1), 2)
        revpar = round(rev / total_rooms, 2)
        return {"booked": booked, "remaining": total_rooms - booked, "occupancy": occ, "adr": adr, "revpar": revpar, "revenue": round(rev, 2)}

    def _csv_response(rows, headers, filename):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    def _excel_response(rows, headers, filename, sheet_name="Report"):
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name

        # Title row
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        title_cell = ws.cell(row=1, column=1, value=f"My Hotel Box — {sheet_name}")
        title_cell.font = Font(name="Calibri", size=14, bold=True, color="4A1D96")
        title_cell.alignment = Alignment(horizontal="center")

        # Date
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(headers))
        date_cell = ws.cell(row=2, column=1, value=f"Generated: {datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M UTC')}")
        date_cell.font = Font(name="Calibri", size=10, color="666666")
        date_cell.alignment = Alignment(horizontal="center")

        # Headers
        header_fill = PatternFill(start_color="F3F0FF", end_color="F3F0FF", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="4A1D96")
        thin_border = Border(
            bottom=Side(style="thin", color="E5E7EB"),
        )
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border

        # Data
        for row_idx, row in enumerate(rows, 5):
            for col_idx, val in enumerate(row, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = Font(name="Calibri", size=10)
                cell.alignment = Alignment(horizontal="center")
                cell.border = thin_border

        # Auto-width
        for col_cells in ws.columns:
            col_letter = None
            max_len = 0
            for cell in col_cells:
                if hasattr(cell, "column_letter"):
                    col_letter = cell.column_letter
                if cell.value and not isinstance(cell, type(None)):
                    try:
                        max_len = max(max_len, len(str(cell.value)))
                    except (TypeError, AttributeError):
                        pass
            if col_letter:
                ws.column_dimensions[col_letter].width = min(max_len + 4, 30)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    # ==================== PERFORMANCE EXPORT ====================
    @router.get("/revenue/export/performance/{property_id}")
    async def export_performance(property_id: str, format: str = "csv", period: str = "mtd",
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        props = await _get_props(property_id)
        total_rooms = await _total_rooms(props)
        if period == "last30": start = now - timedelta(days=30)
        elif period == "last90": start = now - timedelta(days=90)
        else: start = now.replace(day=1)
        num_days = (now - start).days + 1

        headers = ["Date", "Day", "Occupancy %", "ADR (£)", "RevPAR (£)", "Revenue (£)"]
        rows = []
        for i in range(num_days):
            d = start + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            stats = await _day_stats(props, total_rooms, ds)
            rows.append([ds, d.strftime("%A"), stats["occupancy"], stats["adr"], stats["revpar"], stats["revenue"]])

        fname = f"performance_{period}_{now.strftime('%Y%m%d')}"
        if format == "excel":
            return _excel_response(rows, headers, f"{fname}.xlsx", "Performance Report")
        return _csv_response(rows, headers, f"{fname}.csv")

    # ==================== PICKUP EXPORT ====================
    @router.get("/revenue/export/pickup/{property_id}")
    async def export_pickup(property_id: str, format: str = "csv", days: int = 30,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        props = await _get_props(property_id)
        total_rooms = await _total_rooms(props)

        headers = ["Date", "Day", "Days Out", "On Books", "Remaining", "Occupancy %", "ADR (£)", "SDLY", "vs SDLY %", "Pace"]
        rows = []
        for i in range(days):
            d = now + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            stats = await _day_stats(props, total_rooms, ds)
            sdly_d = d.replace(year=d.year - 1)
            sdly_stats = await _day_stats(props, total_rooms, sdly_d.strftime("%Y-%m-%d"))
            vs_sdly = round(((stats["booked"] - sdly_stats["booked"]) / max(sdly_stats["booked"], 1)) * 100, 1) if sdly_stats["booked"] > 0 else 0
            pace = "Ahead" if vs_sdly > 5 else "Behind" if vs_sdly < -5 else "On Pace"
            rows.append([ds, d.strftime("%A"), f"{i}d" if i > 0 else "Today", stats["booked"], stats["remaining"], stats["occupancy"], stats["adr"], sdly_stats["booked"], vs_sdly, pace])

        fname = f"pickup_report_{now.strftime('%Y%m%d')}"
        if format == "excel":
            return _excel_response(rows, headers, f"{fname}.xlsx", "Pickup Report")
        return _csv_response(rows, headers, f"{fname}.csv")

    # ==================== BUDGET VARIANCE EXPORT ====================
    @router.get("/revenue/export/budget/{property_id}")
    async def export_budget(property_id: str, format: str = "csv",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        props = await _get_props(property_id)
        total_rooms = await _total_rooms(props)
        start = now.replace(day=1)
        num_days = (now - start).days + 1

        budget = await db.revenue_budgets.find_one({"property_id": property_id, "month": now.month, "year": now.year}, {"_id": 0})
        budget_occ = budget.get("target_occupancy", 0) if budget else 0
        budget_rev = budget.get("target_revenue", 0) if budget else 0
        daily_budget_rev = round(budget_rev / max(calendar.monthrange(now.year, now.month)[1], 1), 2) if budget_rev > 0 else 0

        headers = ["Date", "Day", "Actual Occ %", "Budget Occ %", "Variance (pp)", "Actual Rev (£)", "Budget Rev (£)", "Variance (£)"]
        rows = []
        for i in range(num_days):
            d = start + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            stats = await _day_stats(props, total_rooms, ds)
            occ_var = stats["occupancy"] - budget_occ if budget_occ > 0 else ""
            rev_var = round(stats["revenue"] - daily_budget_rev, 2) if daily_budget_rev > 0 else ""
            rows.append([ds, d.strftime("%A"), stats["occupancy"], budget_occ or "—", occ_var, stats["revenue"], daily_budget_rev or "—", rev_var])

        fname = f"budget_variance_{now.strftime('%Y%m')}"
        if format == "excel":
            return _excel_response(rows, headers, f"{fname}.xlsx", "Budget Variance")
        return _csv_response(rows, headers, f"{fname}.csv")

    # ==================== FORECASTING EXPORT ====================
    @router.get("/revenue/export/forecasting/{property_id}")
    async def export_forecasting(property_id: str, format: str = "csv", days: int = 30,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        props = await _get_props(property_id)
        total_rooms = await _total_rooms(props)

        headers = ["Date", "Day", "Days Out", "Forecast Occ %", "On Books", "Remaining", "Forecast ADR (£)", "SDLY Occ %", "vs SDLY", "Confidence %"]
        rows = []
        for i in range(days):
            d = now + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            stats = await _day_stats(props, total_rooms, ds)
            sdly_d = d.replace(year=d.year - 1)
            sdly_stats = await _day_stats(props, total_rooms, sdly_d.strftime("%Y-%m-%d"))
            pickup_factor = max(0, min(30, 30 - i)) / 30
            forecast_occ = min(100, round(stats["occupancy"] + (100 - stats["occupancy"]) * pickup_factor * 0.4))
            forecast_adr = round(stats["adr"] * (1 + (forecast_occ - stats["occupancy"]) / 200), 2) if stats["adr"] > 0 else round(sdly_stats["adr"] * 1.05, 2) if sdly_stats["adr"] > 0 else 75
            confidence = max(20, min(95, 95 - i))
            vs_sdly = round(forecast_occ - sdly_stats["occupancy"])
            rows.append([ds, d.strftime("%A"), i, forecast_occ, stats["booked"], stats["remaining"], forecast_adr, sdly_stats["occupancy"], vs_sdly, confidence])

        fname = f"forecast_{now.strftime('%Y%m%d')}"
        if format == "excel":
            return _excel_response(rows, headers, f"{fname}.xlsx", "Demand Forecast")
        return _csv_response(rows, headers, f"{fname}.csv")

    # ==================== PROFIT OS EXPORT ====================
    @router.get("/revenue/export/profit-os/{property_id}")
    async def export_profit_os(property_id: str, format: str = "csv",
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        props = await _get_props(property_id)
        total_rooms = await _total_rooms(props)
        start = (now - timedelta(days=30)).strftime("%Y-%m-%d")

        channel_data = {}
        for p in props:
            bks = await db.bookings.find({"property_id": p.get("id", ""), "check_in": {"$gte": start}}, {"_id": 0}).to_list(500)
            for b in bks:
                ch = b.get("source", "Direct") or "Direct"
                if ch not in channel_data:
                    channel_data[ch] = {"days": 0, "gross_rev": 0}
                channel_data[ch]["days"] += max(1, int(b.get("nights", 1) or 1))
                channel_data[ch]["gross_rev"] += float(b.get("total_price", 0) or 0)

        commission_rates = {"Booking.com": 0.15, "Expedia": 0.18, "Airbnb": 0.03, "Direct": 0, "Walk-in": 0, "Phone": 0}
        headers = ["Channel", "Room Nights", "Gross ADR (£)", "Commission %", "Net ADR (£)", "ContributionPAR (£)", "Total Contribution (£)"]
        rows = []
        for ch, data in sorted(channel_data.items(), key=lambda x: -x[1]["gross_rev"]):
            comm = commission_rates.get(ch, 0.10)
            gross_adr = round(data["gross_rev"] / max(data["days"], 1), 2)
            net_adr = round(gross_adr * (1 - comm), 2)
            contrib_par = round(data["gross_rev"] * (1 - comm) / max(total_rooms, 1), 2)
            total_contrib = round(data["gross_rev"] * (1 - comm), 2)
            rows.append([ch, data["days"], gross_adr, round(comm * 100), net_adr, contrib_par, total_contrib])

        fname = f"profit_os_{now.strftime('%Y%m%d')}"
        if format == "excel":
            return _excel_response(rows, headers, f"{fname}.xlsx", "Profit OS")
        return _csv_response(rows, headers, f"{fname}.csv")

    # ==================== DISTRIBUTION EXPORT ====================
    @router.get("/revenue/export/distribution/{property_id}")
    async def export_distribution(property_id: str, format: str = "csv",
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        props = await _get_props(property_id)
        total_rooms = await _total_rooms(props)
        start = (now - timedelta(days=30)).strftime("%Y-%m-%d")

        channel_perf = {}
        for p in props:
            bks = await db.bookings.find({"property_id": p.get("id", ""), "check_in": {"$gte": start}}, {"_id": 0}).to_list(500)
            for b in bks:
                ch = b.get("source", "Direct") or "Direct"
                if ch not in channel_perf:
                    channel_perf[ch] = {"days": 0, "gross_rev": 0, "bookings": 0}
                channel_perf[ch]["days"] += max(1, int(b.get("nights", 1) or 1))
                channel_perf[ch]["gross_rev"] += float(b.get("total_price", 0) or 0)
                channel_perf[ch]["bookings"] += 1

        commission_rates = {"Booking.com": 0.15, "Expedia": 0.18, "Airbnb": 0.03, "Direct": 0, "Walk-in": 0, "Phone": 0}
        headers = ["Channel", "Room Nights", "Bookings", "Avg Gross ADR (£)", "Avg Net ADR (£)", "Avg ContributionPAR (£)", "Total ContributionPAR (£)"]
        rows = []
        for ch, data in sorted(channel_perf.items(), key=lambda x: -x[1]["gross_rev"]):
            comm = commission_rates.get(ch, 0.10)
            gross_adr = round(data["gross_rev"] / max(data["days"], 1), 2)
            net_adr = round(gross_adr * (1 - comm), 2)
            contrib_par = round(data["gross_rev"] * (1 - comm) / max(total_rooms, 1), 2)
            total_contrib = round(data["gross_rev"] * (1 - comm), 2)
            rows.append([ch, data["days"], data["bookings"], gross_adr, net_adr, contrib_par, total_contrib])

        fname = f"distribution_{now.strftime('%Y%m%d')}"
        if format == "excel":
            return _excel_response(rows, headers, f"{fname}.xlsx", "Distribution Cockpit")
        return _csv_response(rows, headers, f"{fname}.csv")

    # ==================== EXECUTIVE SUMMARY ====================
    @router.get("/revenue/export/executive-summary/{property_id}")
    async def export_executive_summary(property_id: str, format: str = "excel",
                                       current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        props = await _get_props(property_id)
        total_rooms = await _total_rooms(props)
        today_str = now.strftime("%Y-%m-%d")
        today_stats = await _day_stats(props, total_rooms, today_str)

        # MTD stats
        start = now.replace(day=1)
        num_days = (now - start).days + 1
        total_occ = 0; total_adr = 0; total_rev = 0
        for i in range(num_days):
            d = start + timedelta(days=i)
            stats = await _day_stats(props, total_rooms, d.strftime("%Y-%m-%d"))
            total_occ += stats["occupancy"]; total_adr += stats["adr"]; total_rev += stats["revenue"]
        avg_occ = round(total_occ / max(num_days, 1))
        avg_adr = round(total_adr / max(num_days, 1), 2)

        # Next 7 days
        next7_occ = 0
        for i in range(1, 8):
            d = now + timedelta(days=i)
            stats = await _day_stats(props, total_rooms, d.strftime("%Y-%m-%d"))
            next7_occ += stats["occupancy"]
        next7_avg = round(next7_occ / 7)

        # Channel mix
        channel_data = {}
        for p in props:
            bks = await db.bookings.find({"property_id": p.get("id", ""), "check_in": {"$gte": start.strftime("%Y-%m-%d")}}, {"_id": 0, "source": 1}).to_list(500)
            for b in bks:
                src = b.get("source", "Direct") or "Direct"
                channel_data[src] = channel_data.get(src, 0) + 1

        headers = ["Metric", "Value"]
        rows = [
            ["Report Date", now.strftime("%B %d, %Y")],
            ["Properties", len(props)],
            ["Total Rooms", total_rooms],
            ["", ""],
            ["=== TODAY ===", ""],
            ["Today's Occupancy", f"{today_stats['occupancy']}%"],
            ["Today's ADR", f"£{today_stats['adr']}"],
            ["Today's RevPAR", f"£{today_stats['revpar']}"],
            ["Today's Revenue", f"£{today_stats['revenue']}"],
            ["", ""],
            ["=== MONTH-TO-DATE ===", ""],
            ["MTD Avg Occupancy", f"{avg_occ}%"],
            ["MTD Avg ADR", f"£{avg_adr}"],
            ["MTD Total Revenue", f"£{round(total_rev, 2)}"],
            ["", ""],
            ["=== NEXT 7 DAYS ===", ""],
            ["Forecast Avg Occupancy", f"{next7_avg}%"],
            ["", ""],
            ["=== CHANNEL MIX (MTD) ===", ""],
        ]
        for ch, cnt in sorted(channel_data.items(), key=lambda x: -x[1]):
            rows.append([ch, f"{cnt} bookings"])

        fname = f"executive_summary_{now.strftime('%Y%m%d')}"
        if format == "csv":
            return _csv_response(rows, headers, f"{fname}.csv")
        return _excel_response(rows, headers, f"{fname}.xlsx", "Executive Summary")

    return router
