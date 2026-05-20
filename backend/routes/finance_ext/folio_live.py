"""
In-stay Folio PDF (P1)
----------------------
Lets a guest pull their *running* folio at any moment during their stay
(not just at checkout). Surfaces every charge posted so far, payments
received, and balance owing — printable to PDF in the browser.

Endpoints
---------
GET /folio-live/{booking_id}                Pull live folio JSON
GET /folio-live/{booking_id}/html           Printable A4 HTML view
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime, timezone
from typing import Dict
from html import escape


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _build_folio(db, booking_id: str) -> Dict:
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(404, "Booking not found")
    prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0}) or {}

    charges = await db.folio_charges.find({"booking_id": booking_id}, {"_id": 0}).sort("posted_at", 1).to_list(500)
    payments = await db.payments.find({"booking_id": booking_id}, {"_id": 0}).sort("paid_at", 1).to_list(200)

    # Fold the room rate as a charge if no folio_charges exist yet (seed flows post stay-rate at checkout only)
    has_room_charge = any((c.get("category") or "") == "room" for c in charges)
    if not has_room_charge and booking.get("total_price"):
        charges.append({
            "id": "implicit-room",
            "booking_id": booking_id,
            "category": "room",
            "description": f"Room rate · {booking.get('nights', 0)} nights",
            "amount": float(booking.get("total_price") or 0),
            "currency": booking.get("currency", "GBP"),
            "posted_at": booking.get("check_in") or _now(),
        })

    total_charges = round(sum(float(c.get("amount") or 0) for c in charges), 2)
    total_payments = round(sum(float(p.get("amount") or 0) for p in payments), 2)
    balance = round(total_charges - total_payments, 2)

    return {
        "as_of": _now(),
        "booking": {
            "id": booking_id,
            "guest_name": booking.get("guest_name", ""),
            "room_number": booking.get("room_number", ""),
            "check_in": booking.get("check_in", ""),
            "check_out": booking.get("check_out", ""),
            "nights": booking.get("nights", 0),
            "currency": booking.get("currency", "GBP"),
        },
        "hotel": {
            "name": prop.get("name", ""),
            "address": prop.get("address", ""),
            "tax_id": prop.get("tax_id", ""),
            "phone": prop.get("phone", ""),
        },
        "charges": charges,
        "payments": payments,
        "totals": {
            "charges": total_charges,
            "payments": total_payments,
            "balance_due": balance,
        },
    }


def create_folio_live_router(db, require_roles):
    router = APIRouter()

    @router.get("/folio-live/{booking_id}")
    async def folio_json(booking_id: str):
        return await _build_folio(db, booking_id)

    @router.get("/folio-live/{booking_id}/html", response_class=HTMLResponse)
    async def folio_html(booking_id: str):
        f = await _build_folio(db, booking_id)
        cur = f["booking"]["currency"]

        def fmt(n: float) -> str:
            return f"{cur} {float(n or 0):.2f}"

        rows_charges = "".join(
            f"<tr><td>{(c.get('posted_at','') or '')[:10]}</td>"
            f"<td>{escape(c.get('description', '') or c.get('category', ''))}</td>"
            f"<td class='r'>{fmt(c.get('amount', 0))}</td></tr>"
            for c in f["charges"]
        ) or "<tr><td colspan=3 class='muted'>No charges posted yet.</td></tr>"

        rows_payments = "".join(
            f"<tr><td>{(p.get('paid_at','') or '')[:10]}</td>"
            f"<td>{escape((p.get('method') or '') + ' ' + (p.get('reference') or ''))}</td>"
            f"<td class='r'>{fmt(p.get('amount', 0))}</td></tr>"
            for p in f["payments"]
        ) or "<tr><td colspan=3 class='muted'>No payments received yet.</td></tr>"

        return f"""<!doctype html><html><head><meta charset="utf-8"><title>In-stay Folio · {escape(f['booking']['guest_name'])}</title>
<style>
  *{{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}}
  body{{margin:0;background:#f5f5f4;color:#1c1917;padding:24px}}
  .wrap{{max-width:760px;margin:0 auto;background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.06);padding:32px}}
  h1{{margin:0 0 4px;font-size:22px}}
  h2{{margin:24px 0 8px;font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:#57534e}}
  table{{width:100%;border-collapse:collapse;margin-bottom:8px;font-size:13px}}
  td,th{{padding:6px 8px;border-bottom:1px solid #e7e5e4;text-align:left}}
  th{{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#78716c}}
  td.r,th.r{{text-align:right}}
  .muted{{color:#a8a29e;text-align:center;padding:12px 0}}
  .totals{{margin-top:16px;border-top:2px solid #1c1917;padding-top:8px;font-size:14px}}
  .balance{{font-size:20px;font-weight:600;color:#dc2626}}
  .bal-ok{{color:#059669}}
  .meta{{font-size:12px;color:#78716c;margin-top:4px}}
  @media print {{body{{background:#fff;padding:0}} .wrap{{box-shadow:none}}}}
  .btn{{display:inline-block;padding:6px 14px;background:#0e7490;color:#fff;border-radius:4px;text-decoration:none;font-size:12px;margin-bottom:16px}}
</style></head>
<body><div class="wrap">
<a href="javascript:window.print()" class="btn">Print / Save as PDF</a>
<h1>{escape(f['hotel']['name'] or 'Hotel')}</h1>
<div class="meta">{escape(f['hotel']['address'] or '')} · Tax ID: {escape(f['hotel']['tax_id'] or '—')}</div>
<h2>In-stay Folio</h2>
<table>
<tr><td>Guest</td><td><b>{escape(f['booking']['guest_name'])}</b></td></tr>
<tr><td>Room</td><td>{escape(str(f['booking']['room_number']))}</td></tr>
<tr><td>Stay</td><td>{escape(f['booking']['check_in'][:10])} → {escape(f['booking']['check_out'][:10])} ({f['booking']['nights']}n)</td></tr>
<tr><td>Statement as of</td><td>{escape(f['as_of'][:19])}</td></tr>
</table>

<h2>Charges</h2>
<table>
<thead><tr><th>Date</th><th>Description</th><th class="r">Amount</th></tr></thead>
<tbody>{rows_charges}</tbody>
</table>

<h2>Payments</h2>
<table>
<thead><tr><th>Date</th><th>Method</th><th class="r">Amount</th></tr></thead>
<tbody>{rows_payments}</tbody>
</table>

<div class="totals">
<table>
<tr><td>Total charges</td><td class="r">{fmt(f['totals']['charges'])}</td></tr>
<tr><td>Total payments</td><td class="r">−{fmt(f['totals']['payments'])}</td></tr>
<tr><td><b>Balance due</b></td><td class="r balance {'bal-ok' if f['totals']['balance_due']<=0 else ''}">{fmt(f['totals']['balance_due'])}</td></tr>
</table>
</div>

<div class="meta" style="margin-top:24px">This is an interim statement — final folio at checkout may differ as further charges post.</div>
</div></body></html>"""

    return router
