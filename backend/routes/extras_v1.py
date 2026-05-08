"""
Multi-currency Widget Pricing + Multi-property Roll-up + BEO PDF
----------------------------------------------------------------
Three small endpoints bundled to save router files.

1. CURRENCY — converts a base price to N target currencies using either
   a stored FX table or a simple cached rate set. Public for widget calls.

2. MULTI-PROPERTY ROLL-UP — chain dashboard: aggregates KPIs (occupancy,
   ADR, RevPAR, total revenue, complaints, no-shows) across all properties
   the requesting user has access to.

3. BANQUET EVENT ORDER (BEO) PDF — generates a printable HTML "function
   sheet" for an event booking: timing, room setup, AV, F&B, billing,
   contact list. Pure stdlib HTML — printable to PDF via browser.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


# Built-in fallback FX rates (vs GBP). Updated quarterly.
DEFAULT_RATES_GBP = {
    "GBP": 1.0,    "EUR": 1.18,   "USD": 1.27,   "TRY": 41.0,
    "AED": 4.66,   "AUD": 1.96,   "CAD": 1.74,   "CHF": 1.13,
    "JPY": 191.0,  "CNY": 9.27,   "INR": 107.0,  "ZAR": 23.4,
    "SGD": 1.71,   "SEK": 13.6,   "NOK": 13.7,   "PLN": 5.05,
    "MXN": 22.7,   "BRL": 6.45,   "RUB": 119.0,  "SAR": 4.77,
}


def create_extras_router(db, require_roles):
    router = APIRouter()

    # ---------------- Currency ----------------

    async def _rates_for(property_id: str) -> Dict[str, float]:
        # Prefer property-level override
        custom = await db.fx_rates.find_one({"property_id": property_id}, {"_id": 0}) or {}
        rates = dict(DEFAULT_RATES_GBP)
        rates.update(custom.get("rates", {}))
        return rates

    @router.get("/currency/rates")
    async def list_rates(property_id: str = ""):
        """PUBLIC — used by booking widget."""
        rates = await _rates_for(property_id) if property_id else dict(DEFAULT_RATES_GBP)
        return {"base": "GBP", "rates": rates, "currencies": sorted(rates.keys())}

    @router.post("/currency/rates")
    async def save_rates(data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = data.get("property_id", "")
        rates = data.get("rates") or {}
        clean = {k.upper(): float(v) for k, v in rates.items() if v}
        await db.fx_rates.update_one(
            {"property_id": property_id},
            {"$set": {"property_id": property_id, "rates": clean,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"ok": True, "rates": clean}

    @router.post("/currency/convert")
    async def convert(data: Dict):
        """PUBLIC — booking widget calls. Body: {amount, from, to, property_id?}"""
        amount = float(data.get("amount") or 0)
        f = (data.get("from") or "GBP").upper()
        t = (data.get("to") or "GBP").upper()
        rates = await _rates_for(data.get("property_id", ""))
        if f not in rates or t not in rates:
            raise HTTPException(400, f"unknown currency: {f if f not in rates else t}")
        # All rates are vs GBP. amount(GBP) = amount(f) / rate(f). amount(t) = amount(GBP) * rate(t).
        gbp = amount / rates[f]
        out = round(gbp * rates[t], 2)
        return {"amount_in": amount, "from": f, "to": t, "amount_out": out, "rate_used": round(rates[t] / rates[f], 6)}

    # ---------------- Multi-property Roll-up ----------------

    @router.get("/multi-property/rollup")
    async def rollup(days: int = 30,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        # Properties this user has access to. We just take all properties owned
        # by the same org as the user. Falls back to all properties if no org.
        query: Dict = {}
        if current_user.get("org_id"):
            query["org_id"] = current_user["org_id"]
        properties = await db.properties.find(query, {"_id": 0}).to_list(200)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        today_str = date.today().isoformat()

        items = []
        chain_revenue = 0.0
        chain_bookings = 0
        chain_complaints = 0
        chain_no_shows = 0

        for p in properties:
            pid = p["id"]
            bookings = await db.bookings.find(
                {"property_id": pid, "created_at": {"$gte": since}}, {"_id": 0}
            ).to_list(2000)
            confirmed = [b for b in bookings if b.get("status") not in ("cancelled", "no_show")]
            revenue = sum(float(b.get("total_price") or 0) for b in confirmed)
            no_shows = sum(1 for b in bookings if b.get("status") == "no_show")
            occupied_today = await db.bookings.count_documents({
                "property_id": pid, "check_in": {"$lte": today_str}, "check_out": {"$gt": today_str},
                "status": {"$in": ["confirmed", "checked_in"]},
            })
            room_count = await db.room_statuses.count_documents({"property_id": pid})
            occ_pct = round(occupied_today / room_count * 100, 1) if room_count else 0
            adr = round(revenue / max(1, len(confirmed)), 2)
            revpar = round(revenue / max(1, room_count) / max(1, days), 2) if room_count else 0
            complaints = await db.guest_complaints.count_documents({
                "property_id": pid, "created_at": {"$gte": since}
            })
            items.append({
                "property_id": pid,
                "name": p.get("name", pid),
                "currency": p.get("currency", "GBP"),
                "rooms": room_count,
                "bookings": len(confirmed),
                "revenue": round(revenue, 2),
                "adr": adr, "revpar": revpar,
                "occupancy_today_pct": occ_pct,
                "no_shows": no_shows,
                "complaints": complaints,
            })
            chain_revenue += revenue
            chain_bookings += len(confirmed)
            chain_complaints += complaints
            chain_no_shows += no_shows
        items.sort(key=lambda x: x["revenue"], reverse=True)
        return {
            "window_days": days,
            "property_count": len(items),
            "chain_revenue": round(chain_revenue, 2),
            "chain_bookings": chain_bookings,
            "chain_complaints": chain_complaints,
            "chain_no_shows": chain_no_shows,
            "properties": items,
        }

    # ---------------- BEO PDF (HTML) ----------------

    @router.get("/beo/{event_id}/sheet", response_class=HTMLResponse)
    async def beo_sheet(event_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "fnb"))):
        ev = (await db.events.find_one({"id": event_id}, {"_id": 0})
              or await db.bookings_events.find_one({"id": event_id}, {"_id": 0})
              or await db.event_bookings.find_one({"id": event_id}, {"_id": 0}))
        if not ev:
            raise HTTPException(404, "Event not found")
        prop = await db.properties.find_one({"id": ev.get("property_id", "")}, {"_id": 0}) or {}
        prop_name = prop.get("name", "")
        rooms = ev.get("function_rooms") or ev.get("rooms") or []
        agenda = ev.get("agenda") or []
        catering = ev.get("catering") or []
        av = ev.get("av_setup") or []
        billing = ev.get("billing") or {}
        contact = ev.get("contact") or {}

        def _list(html_class, items, formatter):
            if not items:
                return f"<p class='muted'>None.</p>"
            rows = "".join(f"<li>{formatter(i)}</li>" for i in items)
            return f"<ul class='{html_class}'>{rows}</ul>"

        html = f"""<!doctype html>
<html><head>
<meta charset='utf-8' />
<title>BEO — {ev.get('name','Event')}</title>
<style>
  @page {{ size: A4; margin: 14mm; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         color:#0f172a; margin:0; padding: 14px; }}
  h1 {{ font-size: 24px; margin: 0 0 4px; }}
  h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: 0.04em; color:#475569;
       margin: 18px 0 6px; border-bottom:1px solid #cbd5e1; padding-bottom: 4px; }}
  .meta {{ color:#64748b; font-size: 12px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; font-size: 13px; }}
  .box {{ border:1px solid #e2e8f0; border-radius: 8px; padding: 10px; }}
  .muted {{ color:#94a3b8; }}
  ul {{ margin: 0; padding-left: 16px; font-size: 12.5px; }}
  table {{ width:100%; border-collapse: collapse; font-size: 12.5px; }}
  th, td {{ text-align:left; padding: 6px 8px; border-bottom: 1px solid #e2e8f0; }}
  th {{ color:#475569; font-weight: 600; font-size: 11px; text-transform: uppercase; }}
  .toolbar {{ position: fixed; top: 8px; right: 8px; }}
  @media print {{ .toolbar {{ display:none; }} }}
  .totals {{ display: flex; justify-content: space-between; padding: 8px 0; font-weight: 600; }}
  .stamp {{ display: inline-block; padding: 2px 8px; border-radius: 4px; background:#f1f5f9; color:#475569; font-size: 11px; }}
</style></head>
<body>
  <div class='toolbar'><button onclick='window.print()'>Print / Save PDF</button></div>
  <h1>{ev.get('name', 'Event')}</h1>
  <div class='meta'>{prop_name} · BEO #{event_id[:8]} · printed {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div>

  <div class='grid'>
    <div class='box'>
      <h2>Event details</h2>
      <table>
        <tr><th>Date</th><td>{ev.get('event_date', ev.get('date', '—'))}</td></tr>
        <tr><th>Start → End</th><td>{ev.get('start_time','—')} → {ev.get('end_time','—')}</td></tr>
        <tr><th>Pax</th><td>{ev.get('pax', ev.get('guests', '—'))}</td></tr>
        <tr><th>Type</th><td><span class='stamp'>{ev.get('event_type', ev.get('type', 'event'))}</span></td></tr>
        <tr><th>Status</th><td><span class='stamp'>{ev.get('status', 'confirmed')}</span></td></tr>
      </table>
    </div>
    <div class='box'>
      <h2>Client contact</h2>
      <table>
        <tr><th>Name</th><td>{contact.get('name', ev.get('client_name','—'))}</td></tr>
        <tr><th>Company</th><td>{contact.get('company', ev.get('company',''))}</td></tr>
        <tr><th>Email</th><td>{contact.get('email', ev.get('client_email',''))}</td></tr>
        <tr><th>Phone</th><td>{contact.get('phone', ev.get('client_phone',''))}</td></tr>
      </table>
    </div>
  </div>

  <h2>Function rooms</h2>
  {_list('rooms', rooms, lambda r: f"<strong>{r.get('name','Room')}</strong> · setup {r.get('setup','—')} · capacity {r.get('capacity','—')}")}

  <h2>Agenda</h2>
  {_list('agenda', agenda, lambda a: f"<strong>{a.get('time','—')}</strong> · {a.get('title','—')}{(' — ' + a.get('notes','')) if a.get('notes') else ''}")}

  <h2>Catering / F&B</h2>
  {_list('cat', catering, lambda c: f"<strong>{c.get('name','Item')}</strong> × {c.get('qty',1)} @ {c.get('rate','—')} · {c.get('notes','')}")}

  <h2>AV & Setup</h2>
  {_list('av', av, lambda x: f"{x.get('item','—')} × {x.get('qty',1)} {('· ' + x.get('notes','')) if x.get('notes') else ''}")}

  <h2>Billing</h2>
  <div class='box'>
    <div class='totals'><span>Quoted total</span><span>{billing.get('quoted_total', ev.get('quoted_price','—'))} {billing.get('currency', ev.get('currency','GBP'))}</span></div>
    <div class='totals'><span>Deposit paid</span><span>{billing.get('deposit_paid', 0)}</span></div>
    <div class='totals'><span>Balance due</span><span>{billing.get('balance_due', '—')}</span></div>
    <div class='muted' style='font-size:11px;'>Payment terms: {billing.get('terms','Net 7 days from event date')}</div>
  </div>

  <h2>Notes</h2>
  <p style='font-size:12.5px; white-space: pre-wrap;'>{ev.get('notes', ev.get('internal_notes', ''))}</p>

  <p class='muted' style='margin-top:24px;'>Signed — Banqueting manager: __________________________ &nbsp;&nbsp;&nbsp; Client: __________________________</p>
</body></html>
"""
        return HTMLResponse(content=html)

    return router
