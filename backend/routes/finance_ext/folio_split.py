"""
Folio Split-Billing (P1)
------------------------
Split a single booking's folio between multiple payers (typically guest
personal + employer / agent / event organiser).

Each `folio_split` row defines a payer, charge categories that route to that
payer, and either a percentage cap or fixed amount cap. The settle step
generates a per-payer breakdown that becomes a self-contained mini-folio.

Endpoints
---------
POST /folio-split/{booking_id}/configure   Add / replace a payer split
GET  /folio-split/{booking_id}             View configured splits + computed allocation
POST /folio-split/{booking_id}/settle      Lock the allocation and generate per-payer folios
GET  /folio-split/{booking_id}/payer/{payer_id}/html  Per-payer mini-folio (HTML PDF)
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime, timezone
from typing import Dict, List
from html import escape
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _allocate(db, booking_id: str) -> Dict:
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(404, "Booking not found")
    splits = await db.folio_splits.find({"booking_id": booking_id}, {"_id": 0}).to_list(20)
    charges = await db.folio_charges.find({"booking_id": booking_id}, {"_id": 0}).to_list(500)
    if not charges and booking.get("total_price"):
        charges = [{
            "id": "implicit-room", "booking_id": booking_id, "category": "room",
            "description": f"Room rate · {booking.get('nights', 0)} nights",
            "amount": float(booking.get("total_price") or 0),
            "currency": booking.get("currency", "GBP"),
            "posted_at": booking.get("check_in") or _now(),
        }]
    payers: Dict[str, Dict] = {}
    for s in splits:
        payers[s["id"]] = {
            "payer_id": s["id"], "payer_name": s.get("payer_name", ""),
            "payer_email": s.get("payer_email", ""),
            "payer_type": s.get("payer_type", "guest"),
            "categories": s.get("categories") or [],
            "cap_pct": s.get("cap_pct"), "cap_amount": s.get("cap_amount"),
            "items": [], "subtotal": 0.0,
        }
    # "guest" implicit payer for the remainder
    payers.setdefault("guest_default", {
        "payer_id": "guest_default", "payer_name": booking.get("guest_name", ""),
        "payer_email": booking.get("guest_email", ""), "payer_type": "guest",
        "categories": ["*"], "items": [], "subtotal": 0.0,
    })

    for c in charges:
        cat = c.get("category", "other")
        amt = float(c.get("amount") or 0)
        # Find first split that claims this category and isn't capped out
        chosen = None
        for s in splits:
            if cat not in (s.get("categories") or []) and "*" not in (s.get("categories") or []):
                continue
            payer = payers[s["id"]]
            cap_amt = s.get("cap_amount")
            cap_pct = s.get("cap_pct")
            cap_limit = None
            if cap_amt:
                cap_limit = max(0, float(cap_amt) - payer["subtotal"])
            elif cap_pct:
                total = sum(float(x.get("amount") or 0) for x in charges)
                cap_limit = max(0, total * float(cap_pct) / 100 - payer["subtotal"])
            if cap_limit is not None and cap_limit < amt:
                # Charge straddles a cap — split the line
                if cap_limit > 0:
                    payer["items"].append({**c, "amount": round(cap_limit, 2)})
                    payer["subtotal"] += cap_limit
                    amt -= cap_limit
                continue
            chosen = payer
            break
        if amt > 0:
            target = chosen if chosen is not None else payers["guest_default"]
            target["items"].append({**c, "amount": round(amt, 2)})
            target["subtotal"] += amt
    out = []
    for p in payers.values():
        p["subtotal"] = round(p["subtotal"], 2)
        if p["subtotal"] > 0 or p["payer_id"] != "guest_default":
            out.append(p)
    return {"booking_id": booking_id, "currency": booking.get("currency", "GBP"),
             "payers": out, "total_charges": round(sum(p["subtotal"] for p in out), 2),
             "computed_at": _now()}


def create_folio_split_router(db, require_roles):
    router = APIRouter()

    @router.post("/folio-split/{booking_id}/configure")
    async def configure(booking_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        payer_name = (data.get("payer_name") or "").strip()
        if not payer_name:
            raise HTTPException(400, "payer_name required")
        cats = data.get("categories") or []
        if not cats:
            raise HTTPException(400, "categories required (e.g. ['room','tax'] or ['*'])")
        record = {
            "id": data.get("payer_id") or str(uuid.uuid4()),
            "booking_id": booking_id,
            "payer_name": payer_name,
            "payer_email": (data.get("payer_email") or "").strip().lower(),
            "payer_type": data.get("payer_type", "company"),  # guest | company | agent | event
            "categories": cats,
            "cap_pct": data.get("cap_pct"),
            "cap_amount": data.get("cap_amount"),
            "notes": data.get("notes", ""),
            "created_at": _now(),
            "created_by": current_user.get("name", "Staff"),
        }
        await db.folio_splits.update_one({"id": record["id"]}, {"$set": record}, upsert=True)
        return {"ok": True, "split": record}

    @router.get("/folio-split/{booking_id}")
    async def view(booking_id: str,
                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return await _allocate(db, booking_id)

    @router.post("/folio-split/{booking_id}/settle")
    async def settle(booking_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        alloc = await _allocate(db, booking_id)
        await db.folio_split_settlements.insert_one({
            "id": str(uuid.uuid4()), "booking_id": booking_id,
            "snapshot": alloc, "settled_at": _now(),
            "settled_by": current_user.get("name", "Staff"),
        })
        return {"ok": True, "allocation": alloc}

    @router.get("/folio-split/{booking_id}/payer/{payer_id}/html", response_class=HTMLResponse)
    async def payer_folio_html(booking_id: str, payer_id: str):
        alloc = await _allocate(db, booking_id)
        payer = next((p for p in alloc["payers"] if p["payer_id"] == payer_id), None)
        if not payer:
            raise HTTPException(404, "Payer split not found")
        cur = alloc["currency"]
        rows = "".join(
            f"<tr><td>{(c.get('posted_at','') or '')[:10]}</td>"
            f"<td>{escape(c.get('description', '') or c.get('category', ''))}</td>"
            f"<td class='r'>{cur} {float(c.get('amount') or 0):.2f}</td></tr>"
            for c in payer["items"]
        ) or "<tr><td colspan=3 class='muted'>No items.</td></tr>"
        return f"""<!doctype html><html><head><meta charset="utf-8"><title>Folio · {escape(payer['payer_name'])}</title>
<style>
*{{box-sizing:border-box;font-family:-apple-system,sans-serif}} body{{padding:24px;background:#f5f5f4;color:#1c1917}}
.wrap{{max-width:760px;margin:0 auto;background:#fff;padding:32px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}} td,th{{padding:6px 8px;border-bottom:1px solid #e7e5e4;text-align:left}}
.r{{text-align:right}} .muted{{color:#a8a29e;text-align:center}} .total{{margin-top:16px;border-top:2px solid #1c1917;padding-top:8px;font-size:14px;font-weight:600}}
.btn{{display:inline-block;padding:6px 14px;background:#0e7490;color:#fff;border-radius:4px;text-decoration:none;font-size:12px;margin-bottom:16px}}
@media print{{body{{background:#fff;padding:0}} .wrap{{box-shadow:none}}}}
</style></head><body><div class="wrap">
<a href="javascript:window.print()" class="btn">Print / Save as PDF</a>
<h1 style="margin:0">{escape(payer['payer_name'])} · Folio</h1>
<div style="color:#78716c;font-size:12px;margin-top:4px">Booking {escape(booking_id[:8])} · payer type: {escape(payer['payer_type'])}</div>
<table><thead><tr><th>Date</th><th>Description</th><th class="r">Amount</th></tr></thead><tbody>{rows}</tbody></table>
<div class="total"><table><tr><td>Total payable</td><td class="r">{cur} {payer['subtotal']:.2f}</td></tr></table></div>
</div></body></html>"""

    return router
