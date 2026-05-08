"""
Profit OS — ContributionPAR Analysis.

Computes per-channel, per-room-type profitability by deducting
distribution costs (OTA commissions, payment processing fees, etc.)
from gross room revenue to reveal the TRUE net contribution.

Key metric: ContributionPAR (CPAR) = net_contribution / available_rooms
(net of commissions & fees — the dollar of revenue that actually hits the P&L)

Sources: Booking.com / Airbnb / Expedia / Agoda / Hotelbeds / Direct / Stripe / Google
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta, date
from typing import Optional
from collections import defaultdict
import os
import uuid
import json
import logging
import re

from auth import require_perm

logger = logging.getLogger(__name__)


# Default industry-standard cost assumptions. These are per-channel percentages
# applied to gross_revenue. Can be overridden per-property later via
# `profit_os_cost_models` collection (future P2.1 feature).
DEFAULT_COMMISSION = {
    "Booking.com": 0.15,   # 15% OTA commission
    "Expedia":     0.18,   # 18% merchant-model commission
    "Airbnb":      0.03,   # 3% host-only fee
    "Agoda":       0.17,
    "Hotelbeds":   0.22,   # wholesaler
    "Google":      0.12,   # Hotel Ads pay-per-stay
    "Direct":      0.0,
    "Web":         0.0,
    "Stripe":      0.0,    # no commission, but payment fee below
    "PayAtHotel":  0.0,
    "Turkish_Payment": 0.0,
    "Phone":       0.0,
    "Walk-in":     0.0,
    "Website":     0.0,
    "Affiliate":   0.08,
}

# Payment processing fee — applied universally to all card payments.
DEFAULT_PAYMENT_FEE_PCT = 0.029  # 2.9% Stripe/card
DEFAULT_PAYMENT_FEE_FIXED = 0.30  # $0.30 per transaction

# Channels that collect payment themselves (no card fee paid by hotel)
CHANNELS_NO_CARD_FEE = {"Booking.com", "Expedia", "Airbnb", "Agoda", "Hotelbeds", "PayAtHotel"}


def _pct(numer, denom):
    return (numer / denom * 100.0) if denom else 0.0


def _parse_iso_date(s: str, fallback: date) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return fallback


def create_profit_os_router(db):
    router = APIRouter()

    @router.get("/revenue/profit-os")
    async def profit_os(
        property_id: str = "",
        start: str = "",
        end: str = "",
        current_user: dict = Depends(require_perm("view_profit_reports", "revenue_profit_os_view", mode="any")),
    ):
        """Return a full ContributionPAR breakdown for the date window."""
        today = datetime.now(timezone.utc).date()
        start_d = _parse_iso_date(start, today - timedelta(days=29))
        end_d = _parse_iso_date(end, today)
        if end_d < start_d:
            start_d, end_d = end_d, start_d
        window_nights = (end_d - start_d).days + 1

        # Pull bookings whose check-in falls in window — we measure revenue by
        # check-in date for simplicity (matches RevPAR convention in most PMS).
        query: dict = {
            "check_in": {"$gte": start_d.isoformat(), "$lte": end_d.isoformat()},
            "status":   {"$in": ["confirmed", "checked_in", "checked_out"]},
        }
        if property_id:
            query["property_id"] = property_id

        bookings = await db.bookings.find(
            query,
            {
                "_id": 0, "id": 1, "property_id": 1, "room_id": 1, "room_type_id": 1,
                "source": 1, "source_code": 1, "check_in": 1, "check_out": 1,
                "nights": 1, "total_price": 1, "currency": 1, "status": 1,
                "guest_name": 1,
            }
        ).to_list(length=20000)

        # Determine available-room universe (for RevPAR / CPAR denominator)
        rt_query = {}
        if property_id:
            rt_query["property_id"] = property_id
        room_types = await db.room_types.find(rt_query, {"_id": 0, "id": 1, "name": 1, "property_id": 1, "inventory": 1}).to_list(length=500)
        total_rooms = sum((rt.get("inventory") or 1) for rt in room_types) or 1
        available_room_nights = total_rooms * window_nights

        # Aggregators
        gross_total = 0.0
        comm_total = 0.0
        fee_total = 0.0
        net_total = 0.0
        occ_nights = 0

        by_channel = defaultdict(lambda: {
            "source": "", "bookings": 0, "gross": 0.0, "commission": 0.0,
            "fee": 0.0, "net": 0.0, "nights": 0,
        })
        by_room_type = defaultdict(lambda: {
            "room_type_id": "", "room_type_name": "", "bookings": 0,
            "gross": 0.0, "net": 0.0, "nights": 0,
        })

        # Daily trend (gross, net, bookings per day — indexed by check_in)
        daily = defaultdict(lambda: {"gross": 0.0, "net": 0.0, "bookings": 0})

        room_type_name = {rt["id"]: rt.get("name", rt["id"]) for rt in room_types}

        for bk in bookings:
            gross = float(bk.get("total_price") or 0.0)
            nights = int(bk.get("nights") or max((
                _parse_iso_date(bk.get("check_out", ""), end_d) - _parse_iso_date(bk.get("check_in", ""), start_d)
            ).days, 1))
            src = bk.get("source") or bk.get("source_code") or "Direct"

            comm_pct = DEFAULT_COMMISSION.get(src, 0.0)
            commission = gross * comm_pct

            if src in CHANNELS_NO_CARD_FEE:
                fee = 0.0
            else:
                fee = gross * DEFAULT_PAYMENT_FEE_PCT + DEFAULT_PAYMENT_FEE_FIXED

            net = gross - commission - fee

            gross_total += gross
            comm_total += commission
            fee_total += fee
            net_total += net
            occ_nights += nights

            ch = by_channel[src]
            ch["source"] = src
            ch["bookings"] += 1
            ch["gross"] += gross
            ch["commission"] += commission
            ch["fee"] += fee
            ch["net"] += net
            ch["nights"] += nights

            rtid = bk.get("room_type_id") or "unknown"
            rt = by_room_type[rtid]
            rt["room_type_id"] = rtid
            rt["room_type_name"] = room_type_name.get(rtid, rtid)
            rt["bookings"] += 1
            rt["gross"] += gross
            rt["net"] += net
            rt["nights"] += nights

            ck = bk.get("check_in")
            if ck:
                d = daily[ck]
                d["gross"] += gross
                d["net"] += net
                d["bookings"] += 1

        # Finalise channel list with commission_pct + contribution_pct
        channels = []
        for src, v in by_channel.items():
            v["commission_pct"] = _pct(v["commission"], v["gross"])
            v["fee_pct"] = _pct(v["fee"], v["gross"])
            v["net_margin_pct"] = _pct(v["net"], v["gross"])
            v["contribution_pct"] = _pct(v["net"], net_total)  # share of total net
            v["adr"] = (v["gross"] / v["nights"]) if v["nights"] else 0.0
            channels.append(v)
        channels.sort(key=lambda x: -x["net"])

        room_types_out = []
        for rtid, v in by_room_type.items():
            v["cpar"] = v["net"] / window_nights if window_nights else 0.0
            v["adr"] = (v["gross"] / v["nights"]) if v["nights"] else 0.0
            v["net_margin_pct"] = _pct(v["net"], v["gross"])
            room_types_out.append(v)
        room_types_out.sort(key=lambda x: -x["net"])

        # Build daily trend with zero-filled dates
        trend = []
        d = start_d
        while d <= end_d:
            k = d.isoformat()
            rec = daily.get(k, {"gross": 0.0, "net": 0.0, "bookings": 0})
            trend.append({"date": k, **rec, "cpar": (rec["net"] / total_rooms) if total_rooms else 0.0})
            d += timedelta(days=1)

        # KPIs
        occupancy_pct = _pct(occ_nights, available_room_nights)
        revpar = (gross_total / available_room_nights) if available_room_nights else 0.0
        cpar = (net_total / available_room_nights) if available_room_nights else 0.0
        adr = (gross_total / occ_nights) if occ_nights else 0.0

        return {
            "window": {"start": start_d.isoformat(), "end": end_d.isoformat(), "nights": window_nights},
            "scope": {"property_id": property_id, "total_rooms": total_rooms, "available_room_nights": available_room_nights},
            "kpis": {
                "gross_revenue": round(gross_total, 2),
                "total_commission": round(comm_total, 2),
                "total_payment_fees": round(fee_total, 2),
                "net_revenue": round(net_total, 2),
                "net_margin_pct": round(_pct(net_total, gross_total), 2),
                "commission_pct": round(_pct(comm_total, gross_total), 2),
                "adr": round(adr, 2),
                "revpar": round(revpar, 2),
                "cpar": round(cpar, 2),
                "occupancy_pct": round(occupancy_pct, 2),
                "occupied_nights": occ_nights,
                "bookings_count": len(bookings),
            },
            "by_channel": channels,
            "by_room_type": room_types_out,
            "trend": trend,
            "cost_model": {
                "commission_rates": DEFAULT_COMMISSION,
                "payment_fee_pct": DEFAULT_PAYMENT_FEE_PCT,
                "payment_fee_fixed": DEFAULT_PAYMENT_FEE_FIXED,
                "channels_without_card_fee": sorted(CHANNELS_NO_CARD_FEE),
            },
        }

    @router.post("/revenue/profit-os/advisor")
    async def profit_os_advisor(
        body: dict,
        current_user: dict = Depends(require_perm("view_profit_reports", "revenue_profit_os_view", mode="any")),
    ):
        """Call GPT-5 to analyze a Profit OS snapshot and suggest 3 actionable revenue moves."""
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")

        kpis = body.get("kpis") or {}
        channels = body.get("by_channel") or []
        room_types = body.get("by_room_type") or []

        if not kpis or not channels:
            raise HTTPException(400, "kpis and by_channel are required in the payload")

        # Keep the prompt compact — top 8 channels, top 6 room types is enough signal.
        channel_rows = [
            {
                "src": c.get("source"),
                "bookings": c.get("bookings"),
                "gross": round(c.get("gross", 0), 2),
                "commission_pct": round(c.get("commission_pct", 0), 1),
                "net": round(c.get("net", 0), 2),
                "margin_pct": round(c.get("net_margin_pct", 0), 1),
                "contribution_pct": round(c.get("contribution_pct", 0), 1),
                "adr": round(c.get("adr", 0), 2),
            }
            for c in channels[:8]
        ]
        room_rows = [
            {
                "room": r.get("room_type_name"),
                "bookings": r.get("bookings"),
                "gross": round(r.get("gross", 0), 2),
                "net": round(r.get("net", 0), 2),
                "cpar": round(r.get("cpar", 0), 2),
                "adr": round(r.get("adr", 0), 2),
                "margin_pct": round(r.get("net_margin_pct", 0), 1),
            }
            for r in room_types[:6]
        ]

        system_msg = (
            "You are a seasoned hotel revenue management consultant (ex-IDeaS / Duetto). "
            "Given a ContributionPAR (CPAR) snapshot, surface the 3 most actionable, quantified "
            "revenue moves a General Manager could make THIS WEEK. Prioritise channel mix "
            "rebalancing, room-type yield, and commission-leakage. Be specific: cite the exact "
            "channel or room type, quantify the projected monthly impact in GBP, and state the "
            "operational next step (e.g., 'tighten last-room availability on Agoda', "
            "'boost Direct via a 5% residual-stay discount', 'lift Executive Suite floor rate £15'). "
            "Return STRICT JSON: "
            '{"headline": "<one-line diagnosis>", '
            '"recommendations": ['
            '  {"title": "<short>", "channel_or_room": "<name>", "impact_gbp_per_month": <number>, '
            '   "severity": "high|medium|low", "rationale": "<1 sentence>", "action": "<1 sentence>"},'
            '  ... (exactly 3) ], '
            '"risk_flag": "<optional one-line risk to watch, or empty string>"}'
            " No markdown, no explanation outside the JSON."
        )

        user_content = (
            "CPAR SNAPSHOT\n"
            f"Window: {body.get('window', {})}\n"
            f"KPIs: {json.dumps(kpis, default=str)}\n\n"
            f"Top channels (up to 8):\n{json.dumps(channel_rows, indent=2)}\n\n"
            f"Top room types (up to 6):\n{json.dumps(room_rows, indent=2)}\n\n"
            "Produce the 3 highest-leverage recommendations now."
        )

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"profit-os-advisor-{current_user.get('id','x')}-{uuid.uuid4().hex[:8]}",
                system_message=system_msg,
            ).with_model("anthropic", "claude-sonnet-4-5")
            resp = await chat.send_message(UserMessage(text=user_content))
            resp_text = resp if isinstance(resp, str) else str(resp)
            m = re.search(r"\{[\s\S]*\}", resp_text)
            if not m:
                raise ValueError("No JSON in LLM response")
            parsed = json.loads(m.group(0))

            recs = parsed.get("recommendations") or []
            # Normalize
            out = []
            for r in recs[:3]:
                out.append({
                    "title": str(r.get("title") or "Recommendation"),
                    "channel_or_room": str(r.get("channel_or_room") or "—"),
                    "impact_gbp_per_month": float(r.get("impact_gbp_per_month") or 0),
                    "severity": (r.get("severity") or "medium").lower(),
                    "rationale": str(r.get("rationale") or ""),
                    "action": str(r.get("action") or ""),
                })
            return {
                "headline": parsed.get("headline") or "Revenue pulse",
                "recommendations": out,
                "risk_flag": parsed.get("risk_flag") or "",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "model": "claude-sonnet-4-5",
            }
        except Exception as e:
            logger.exception("Profit OS advisor failed")
            raise HTTPException(500, f"AI advisor failed: {e}")

    return router
