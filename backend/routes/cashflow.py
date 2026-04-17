"""
Cash Flow Forecast — Projects inflows/outflows over 30/60/90 days by aggregating:
  • Confirmed future bookings (inflow on check_in)
  • Recurring expenses (outflow on next_due)
  • Recurring invoices (inflow on next_due)
  • Estimated payroll (last month's run divided evenly across days, or zero)
  • Manually dated future expenses
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, date, timedelta
from typing import Dict
import logging
import os
import uuid

logger = logging.getLogger(__name__)


def create_cashflow_router(db, require_roles, LlmChat=None, UserMessage=None):
    router = APIRouter()

    @router.get("/finance/cash-flow-forecast/{property_id}")
    async def forecast(property_id: str, days: int = 30, opening_balance: float = 0,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        if days not in (30, 60, 90):
            days = 30
        today = date.today()
        end = today + timedelta(days=days - 1)
        today_iso = today.isoformat()
        end_iso = end.isoformat()

        prop_filter_inc = {} if property_id == "all" else {"property_id": property_id}

        # ---------- INFLOWS ----------
        booking_query = {
            "check_in": {"$gte": today_iso, "$lte": end_iso},
            "status": {"$in": ["confirmed", "checked_in", "pending"]},
            **prop_filter_inc,
        }
        bookings = await db.bookings.find(booking_query, {"_id": 0, "id": 1, "guest_name": 1, "check_in": 1, "total": 1, "rooms": 1, "source": 1, "status": 1, "booking_ref": 1}).to_list(1000)

        recurring_inv = []
        try:
            ri_query = {"enabled": True, "next_due": {"$gte": today_iso, "$lte": end_iso}, **prop_filter_inc}
            recurring_inv = await db.recurring_invoices.find(ri_query, {"_id": 0}).to_list(200)
        except Exception:
            pass

        # ---------- OUTFLOWS ----------
        rec_exp_query = {"enabled": True, "next_due": {"$gte": today_iso, "$lte": end_iso}, **prop_filter_inc}
        recurring_exp = await db.recurring_expenses.find(rec_exp_query, {"_id": 0}).to_list(200)

        # Manually dated future expenses (e.g., a known bill due in 2 weeks)
        future_exp_q = {"date": {"$gte": today_iso, "$lte": end_iso}, **prop_filter_inc}
        future_exp = await db.expenses.find(future_exp_q, {"_id": 0}).to_list(500)

        # Payroll estimate: use last paid/approved run grand_total as monthly baseline
        payroll_estimate = 0.0
        last_runs = await db.payroll_runs.find(
            {"status": {"$in": ["approved", "paid"]}, **({} if property_id == "all" else {"property_id": property_id})},
            {"_id": 0, "grand_total": 1, "year": 1, "month": 1}
        ).sort([("year", -1), ("month", -1)]).to_list(3)
        if last_runs:
            payroll_estimate = sum(r.get("grand_total", 0) for r in last_runs) / len(last_runs)

        # ---------- Build daily buckets ----------
        buckets = {}
        for i in range(days):
            d = (today + timedelta(days=i)).isoformat()
            buckets[d] = {"date": d, "inflows": 0.0, "outflows": 0.0, "items": {"in": [], "out": []}}

        # Add booking inflows (on check_in date)
        for b in bookings:
            d = b.get("check_in", "")
            if d in buckets:
                amt = float(b.get("total", 0) or 0)
                buckets[d]["inflows"] += amt
                buckets[d]["items"]["in"].append({
                    "kind": "booking",
                    "label": f"{b.get('guest_name','')} · {b.get('booking_ref', b.get('id',''))[:10]}",
                    "amount": amt,
                    "source": b.get("source", ""),
                    "status": b.get("status", ""),
                })

        # Recurring invoices inflows
        for ri in recurring_inv:
            d = ri.get("next_due", "")
            if d in buckets:
                amt = float(ri.get("amount", 0) or 0)
                buckets[d]["inflows"] += amt
                buckets[d]["items"]["in"].append({
                    "kind": "recurring_invoice",
                    "label": ri.get("customer", ri.get("vendor", "Recurring invoice")),
                    "amount": amt,
                })

        # Recurring expense outflows
        for re in recurring_exp:
            d = re.get("next_due", "")
            if d in buckets:
                amt = float(re.get("amount", 0) or 0)
                buckets[d]["outflows"] += amt
                buckets[d]["items"]["out"].append({
                    "kind": "recurring_expense",
                    "label": re.get("vendor", re.get("description", "Recurring expense")),
                    "category": re.get("category", "other"),
                    "amount": amt,
                })

        # Known future expenses
        for fe in future_exp:
            d = fe.get("date", "")
            if d in buckets and d >= today_iso:  # future only
                # Skip if this was auto-posted from a recurring template in window (already counted)
                if fe.get("recurring_id"):
                    continue
                amt = float(fe.get("amount", 0) or 0)
                buckets[d]["outflows"] += amt
                buckets[d]["items"]["out"].append({
                    "kind": "expense",
                    "label": fe.get("vendor", fe.get("description", "Expense")),
                    "category": fe.get("category", "other"),
                    "amount": amt,
                })

        # Payroll outflow: estimate distributed on last day of each calendar month in window
        if payroll_estimate > 0:
            cursor = today
            while cursor <= end:
                # Last day of the month of cursor
                if cursor.month == 12:
                    last_day = date(cursor.year, 12, 31)
                else:
                    from calendar import monthrange
                    last_day = date(cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1])
                d_iso = last_day.isoformat()
                if d_iso in buckets:
                    buckets[d_iso]["outflows"] += payroll_estimate
                    buckets[d_iso]["items"]["out"].append({
                        "kind": "payroll_estimate",
                        "label": f"Payroll (est. from last {len(last_runs)} run{'s' if len(last_runs) != 1 else ''})",
                        "amount": round(payroll_estimate, 2),
                    })
                # Jump to first day of next month
                if last_day.month == 12:
                    cursor = date(last_day.year + 1, 1, 1)
                else:
                    cursor = date(last_day.year, last_day.month + 1, 1)

        # Compute running balance & find lowest
        running = float(opening_balance)
        lowest = running
        lowest_date = today_iso
        day_list = []
        total_in = 0.0
        total_out = 0.0
        for i in range(days):
            d = (today + timedelta(days=i)).isoformat()
            b = buckets[d]
            b["inflows"] = round(b["inflows"], 2)
            b["outflows"] = round(b["outflows"], 2)
            b["net"] = round(b["inflows"] - b["outflows"], 2)
            running += b["net"]
            b["running_balance"] = round(running, 2)
            if running < lowest:
                lowest = running
                lowest_date = d
            total_in += b["inflows"]
            total_out += b["outflows"]
            day_list.append(b)

        return {
            "period_days": days,
            "start": today_iso,
            "end": end_iso,
            "opening_balance": round(float(opening_balance), 2),
            "total_inflows": round(total_in, 2),
            "total_outflows": round(total_out, 2),
            "net": round(total_in - total_out, 2),
            "ending_balance": round(running, 2),
            "lowest_balance": round(lowest, 2),
            "lowest_date": lowest_date,
            "at_risk": lowest < 0,
            "payroll_estimate_monthly": round(payroll_estimate, 2),
            "counts": {
                "bookings": len(bookings),
                "recurring_invoices": len(recurring_inv),
                "recurring_expenses": len(recurring_exp),
                "future_expenses": len([e for e in future_exp if not e.get("recurring_id")]),
            },
            "days": day_list,
        }

    @router.post("/finance/cash-flow-forecast/{property_id}/ai-recommendations")
    async def ai_recommendations(property_id: str, data: Dict,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate prescriptive actions from a forecast snapshot."""
        if LlmChat is None or UserMessage is None:
            return {"error": "AI not configured", "recommendations": []}
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"error": "EMERGENT_LLM_KEY missing", "recommendations": []}

        forecast = data.get("forecast") or {}
        opening = forecast.get("opening_balance", 0)
        ending = forecast.get("ending_balance", 0)
        lowest = forecast.get("lowest_balance", 0)
        lowest_date = forecast.get("lowest_date", "")
        total_in = forecast.get("total_inflows", 0)
        total_out = forecast.get("total_outflows", 0)
        at_risk = forecast.get("at_risk", False)
        counts = forecast.get("counts", {})
        period = forecast.get("period_days", 30)

        # Top 10 events by magnitude for context
        days = forecast.get("days", [])
        events = []
        for d in days:
            for it in d.get("items", {}).get("in", []):
                events.append({"date": d["date"], "direction": "in", **it})
            for it in d.get("items", {}).get("out", []):
                events.append({"date": d["date"], "direction": "out", **it})
        events.sort(key=lambda x: -float(x.get("amount", 0)))
        top = events[:10]
        top_lines = "\n".join(
            f"  {e['date']} {e['direction'].upper()} £{float(e.get('amount',0)):.0f} · {e.get('kind','')} · {e.get('label','')[:60]}"
            for e in top
        ) or "  (no events)"

        data_summary = f"""PERIOD: {period} days (starting {forecast.get('start','')})
OPENING BALANCE: £{opening:.0f}
TOTAL INFLOWS: £{total_in:.0f} ({counts.get('bookings',0)} bookings + {counts.get('recurring_invoices',0)} recurring invoices)
TOTAL OUTFLOWS: £{total_out:.0f} ({counts.get('recurring_expenses',0)} recurring + {counts.get('future_expenses',0)} one-off)
ENDING BALANCE: £{ending:.0f}
LOWEST BALANCE: £{lowest:.0f} on {lowest_date}
AT RISK (goes negative): {"YES" if at_risk else "NO"}
PAYROLL ESTIMATE (monthly): £{forecast.get('payroll_estimate_monthly', 0):.0f}

TOP 10 CASH EVENTS BY SIZE:
{top_lines}
"""

        system_msg = """You are an expert hotelier CFO advisor. Given the cash flow forecast,
produce 3-5 concrete, prescriptive recommendations. Each recommendation MUST be a JSON object with:
  "title": short action (≤ 8 words)
  "rationale": one sentence explaining why, citing SPECIFIC numbers and dates from the data
  "impact": estimated £ impact (positive = saves/earns) — e.g. "+£1,200" or "-£380 risk avoided"
  "priority": one of "high", "medium", "low"
  "kind": one of "save_cost", "boost_revenue", "timing", "risk_alert", "efficiency"

Return ONLY a JSON array of these objects, no prose, no markdown. Be specific with £ amounts and calendar dates.
Use British English (£). If the forecast is healthy, still suggest optimisations."""

        try:
            session_id = f"cashflow-ai-{property_id}-{uuid.uuid4().hex[:8]}"
            chat = LlmChat(api_key=api_key, session_id=session_id, system_message=system_msg).with_model("openai", "gpt-5.2")
            text = await chat.send_message(UserMessage(text=f"Forecast data:\n{data_summary}"))
        except Exception as e:
            logger.error(f"Cash flow AI error: {e}")
            return {"error": f"AI generation failed: {str(e)[:120]}", "recommendations": []}

        # Parse JSON from response (strip markdown fences if present)
        import json as _json
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 2)[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.rsplit("```", 1)[0].strip()
        try:
            recs = _json.loads(cleaned)
            if not isinstance(recs, list):
                recs = []
        except Exception:
            # Fallback: wrap raw text into single recommendation
            recs = [{"title": "AI Analysis", "rationale": cleaned[:400], "impact": "—", "priority": "medium", "kind": "efficiency"}]

        # Persist for history
        snapshot = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": current_user.get("name", ""),
            "period_days": period,
            "opening_balance": opening,
            "ending_balance": ending,
            "lowest_balance": lowest,
            "recommendations": recs,
        }
        await db.cashflow_ai_snapshots.insert_one({**snapshot})
        return {"recommendations": recs, "generated_at": snapshot["generated_at"]}

    @router.get("/finance/cash-flow-forecast/{property_id}/ai-recommendations/latest")
    async def latest_recommendations(property_id: str,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        doc = await db.cashflow_ai_snapshots.find_one(q, {"_id": 0}, sort=[("generated_at", -1)])
        if not doc:
            return {"recommendations": [], "generated_at": None}
        return {"recommendations": doc.get("recommendations", []), "generated_at": doc.get("generated_at")}

    return router
