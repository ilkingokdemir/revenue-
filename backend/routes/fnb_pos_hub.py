"""
F&B POS Integration Hub — adapter-based bridge to external POS systems.

Each connection = (property, provider, credentials, status). Receipts are pulled
in via the adapter, normalised to `pos_receipts`, and optionally posted to a
guest folio. Daily reconciliation compares POS totals vs. our recorded totals.

Adapters are pluggable: production deployments would swap the MOCK adapter
for the real SDK (oracle-simphony, lightspeed-restaurant-api, square-python,
toast-api). The interface and contract stay identical.

Endpoints:
  GET    /api/fnb-pos/providers                 — supported adapter list
  GET    /api/fnb-pos/connections               — list (filter by property)
  POST   /api/fnb-pos/connections               — create connection
  PATCH  /api/fnb-pos/connections/{id}          — update / disable
  DELETE /api/fnb-pos/connections/{id}          — remove
  POST   /api/fnb-pos/connections/{id}/test     — test ping
  POST   /api/fnb-pos/connections/{id}/sync     — pull new receipts from POS
  GET    /api/fnb-pos/receipts                  — list normalised receipts
  POST   /api/fnb-pos/receipts/{id}/post-to-folio  — move charge to a folio
  GET    /api/fnb-pos/reconciliation/{property_id} — daily reconciliation report
"""
from datetime import datetime, timezone, timedelta
import random
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


PROVIDERS = [
    {"id": "simphony",   "name": "Oracle Simphony",
     "required_fields": ["server_url", "org_short_name", "api_key"]},
    {"id": "lightspeed", "name": "Lightspeed Restaurant",
     "required_fields": ["account_id", "api_token"]},
    {"id": "square",     "name": "Square POS",
     "required_fields": ["access_token", "location_id"]},
    {"id": "toast",      "name": "Toast POS",
     "required_fields": ["restaurant_guid", "client_id", "client_secret"]},
    {"id": "mock",       "name": "Mock / Demo POS",
     "required_fields": []},
]


class ConnectionIn(BaseModel):
    property_id: str
    provider: str
    name: str = ""
    credentials: dict = {}     # provider-specific
    outlet_name: str = ""      # restaurant / bar name
    revenue_account: str = "F&B"
    active: bool = True


# ============== ADAPTER PROTOCOL ==============
async def _mock_test_connection(creds: dict) -> dict:
    return {"ok": True, "version": "mock-1.0", "latency_ms": random.randint(40, 180)}


async def _mock_fetch_receipts(creds: dict, since_iso: str) -> list:
    """Return a small batch of mock receipts to demonstrate the flow."""
    now = datetime.now(timezone.utc)
    receipts = []
    # Generate 3 fake receipts in the last hour
    for i in range(random.randint(1, 3)):
        ts = (now - timedelta(minutes=random.randint(5, 50))).isoformat()
        if ts < since_iso:
            continue
        rid = "POS-" + uuid.uuid4().hex[:10].upper()
        items_count = random.randint(1, 4)
        items = []
        running = 0.0
        for _ in range(items_count):
            qty = random.randint(1, 3)
            price = round(random.choice([4.5, 6.0, 8.5, 12.0, 18.0, 24.0]), 2)
            items.append({"name": random.choice(
                ["Burger", "Caesar Salad", "Pizza Margherita", "Latte",
                 "House Red 175ml", "Tiramisu", "Espresso"]),
                "qty": qty, "unit_price": price, "total": round(qty * price, 2)})
            running += qty * price
        gross = round(running, 2)
        receipts.append({
            "external_id": rid,
            "opened_at": ts,
            "closed_at": ts,
            "guest_count": random.randint(1, 4),
            "table": f"T{random.randint(1, 20)}",
            "items": items,
            "gross": gross,
            "service_charge": round(gross * 0.10, 2),
            "tax": round(gross * 0.20, 2),
            "total": round(gross * 1.30, 2),
            "currency": "GBP",
            "payment_type": random.choice(["card", "cash", "room_charge"]),
            "room_number": None,
        })
    return receipts


ADAPTERS = {
    "mock": {"test": _mock_test_connection, "fetch": _mock_fetch_receipts},
    # Real providers stub to mock for now — swap once SDKs are wired
    "simphony": {"test": _mock_test_connection, "fetch": _mock_fetch_receipts},
    "lightspeed": {"test": _mock_test_connection, "fetch": _mock_fetch_receipts},
    "square": {"test": _mock_test_connection, "fetch": _mock_fetch_receipts},
    "toast": {"test": _mock_test_connection, "fetch": _mock_fetch_receipts},
}


def _mask(s: str) -> str:
    if not s or len(s) < 6:
        return "***"
    return s[:3] + "…" + s[-3:]


def _redact(creds: dict) -> dict:
    """Hide credential values when listing."""
    return {k: _mask(str(v)) for k, v in (creds or {}).items()}


def create_fnb_pos_router(db, require_roles):
    router = APIRouter(prefix="/fnb-pos")

    @router.get("/providers")
    async def list_providers(_: dict = Depends(require_roles("admin", "manager"))):
        return {"providers": PROVIDERS}

    @router.get("/connections")
    async def list_connections(property_id: str = "",
                               _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        rows = await db.fnb_pos_connections.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
        # Redact credentials
        for r in rows:
            r["credentials"] = _redact(r.get("credentials") or {})
        return {"connections": rows, "count": len(rows)}

    @router.post("/connections")
    async def create_connection(body: ConnectionIn,
                                current_user: dict = Depends(require_roles("admin"))):
        if body.provider not in {p["id"] for p in PROVIDERS}:
            raise HTTPException(400, f"Invalid provider; use one of {[p['id'] for p in PROVIDERS]}")
        # Validate required fields
        required = next((p["required_fields"] for p in PROVIDERS if p["id"] == body.provider), [])
        missing = [f for f in required if not body.credentials.get(f)]
        if missing:
            raise HTTPException(400, f"Missing required fields for {body.provider}: {missing}")
        doc = {
            "id": str(uuid.uuid4()),
            **body.dict(),
            "status": "untested",
            "last_sync_at": None,
            "last_test_at": None,
            "last_test_ok": None,
            "receipts_count": 0,
            "created_by": current_user.get("name", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.fnb_pos_connections.insert_one(doc)
        out = {k: v for k, v in doc.items() if k != "_id"}
        out["credentials"] = _redact(out.get("credentials") or {})
        return out

    @router.patch("/connections/{conn_id}")
    async def patch_connection(conn_id: str, body: dict,
                               _: dict = Depends(require_roles("admin"))):
        body["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.fnb_pos_connections.update_one({"id": conn_id}, {"$set": body})
        if r.matched_count == 0:
            raise HTTPException(404, "Connection not found")
        return {"updated": True}

    @router.delete("/connections/{conn_id}")
    async def delete_connection(conn_id: str,
                                _: dict = Depends(require_roles("admin"))):
        r = await db.fnb_pos_connections.delete_one({"id": conn_id})
        return {"deleted": r.deleted_count}

    @router.post("/connections/{conn_id}/test")
    async def test_connection(conn_id: str,
                              _: dict = Depends(require_roles("admin", "manager"))):
        conn = await db.fnb_pos_connections.find_one({"id": conn_id}, {"_id": 0})
        if not conn:
            raise HTTPException(404, "Connection not found")
        adapter = ADAPTERS.get(conn["provider"])
        result = await adapter["test"](conn.get("credentials") or {})
        now = datetime.now(timezone.utc).isoformat()
        await db.fnb_pos_connections.update_one(
            {"id": conn_id},
            {"$set": {"last_test_at": now, "last_test_ok": bool(result.get("ok")),
                      "status": "ok" if result.get("ok") else "error"}}
        )
        return result

    @router.post("/connections/{conn_id}/sync")
    async def sync_receipts(conn_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        conn = await db.fnb_pos_connections.find_one({"id": conn_id}, {"_id": 0})
        if not conn:
            raise HTTPException(404, "Connection not found")
        if not conn.get("active", True):
            raise HTTPException(400, "Connection is disabled")
        adapter = ADAPTERS.get(conn["provider"])
        # Pull since last sync (or last hour if never)
        last = conn.get("last_sync_at") or (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()
        raw = await adapter["fetch"](conn.get("credentials") or {}, last)
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0
        for r in raw:
            # De-duplicate by (connection_id, external_id)
            if await db.pos_receipts.find_one({"connection_id": conn_id,
                                                "external_id": r["external_id"]},
                                               {"_id": 0, "id": 1}):
                continue
            doc = {
                "id": str(uuid.uuid4()),
                "connection_id": conn_id,
                "property_id": conn["property_id"],
                "outlet_name": conn.get("outlet_name") or "F&B",
                "provider": conn["provider"],
                **r,
                "posted_to_folio": False,
                "synced_at": now,
            }
            await db.pos_receipts.insert_one(doc)
            inserted += 1
        await db.fnb_pos_connections.update_one(
            {"id": conn_id},
            {"$set": {"last_sync_at": now, "status": "ok"},
             "$inc": {"receipts_count": inserted}}
        )
        return {"fetched": len(raw), "inserted": inserted, "synced_at": now,
                "synced_by": current_user.get("name", "")}

    @router.get("/receipts")
    async def list_receipts(property_id: str = "", connection_id: str = "",
                            posted: str = "", limit: int = 100,
                            _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        if connection_id:
            q["connection_id"] = connection_id
        if posted == "true":
            q["posted_to_folio"] = True
        elif posted == "false":
            q["posted_to_folio"] = False
        rows = await db.pos_receipts.find(q, {"_id": 0}) \
                                     .sort("opened_at", -1) \
                                     .to_list(min(limit, 500))
        return {"receipts": rows, "count": len(rows)}

    @router.post("/receipts/{receipt_id}/post-to-folio")
    async def post_to_folio(receipt_id: str, body: dict,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Body: { booking_ref OR booking_id OR room_number }. Posts a charge to the folio."""
        receipt = await db.pos_receipts.find_one({"id": receipt_id}, {"_id": 0})
        if not receipt:
            raise HTTPException(404, "Receipt not found")
        if receipt.get("posted_to_folio"):
            raise HTTPException(400, "Receipt already posted to a folio")
        booking_ref = body.get("booking_ref")
        booking_id = body.get("booking_id")
        room_number = body.get("room_number")
        # Locate booking
        booking = None
        if booking_id:
            booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        elif booking_ref:
            booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
        elif room_number:
            booking = await db.bookings.find_one({
                "room_number": room_number,
                "status": {"$in": ["checked_in", "in_house"]},
            }, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found for the given reference")
        # Create a folio charge
        charge = {
            "id": str(uuid.uuid4()),
            "booking_id": booking["id"],
            "booking_ref": booking.get("booking_ref"),
            "kind": "fnb_pos",
            "description": f"{receipt.get('outlet_name', 'F&B')} — receipt {receipt['external_id']}",
            "amount": float(receipt.get("total", 0)),
            "currency": receipt.get("currency", "GBP"),
            "source_receipt_id": receipt_id,
            "items": receipt.get("items", []),
            "posted_by": current_user.get("name", ""),
            "posted_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.folio_charges.insert_one(charge)
        await db.pos_receipts.update_one(
            {"id": receipt_id},
            {"$set": {"posted_to_folio": True,
                      "folio_booking_id": booking["id"],
                      "folio_charge_id": charge["id"]}}
        )
        charge.pop("_id", None)
        return {"posted": True, "charge_id": charge["id"], "amount": charge["amount"]}

    @router.get("/reconciliation/{property_id}")
    async def reconciliation(property_id: str, date: str = "",
                             _: dict = Depends(require_roles("admin", "manager"))):
        """Compare POS totals vs. our recorded folio postings for a date."""
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        receipts = await db.pos_receipts.find(
            {"property_id": property_id, "closed_at": {"$regex": f"^{date}"}},
            {"_id": 0}
        ).to_list(500)
        # By outlet & payment type
        by_outlet: dict = {}
        by_payment: dict = {}
        total = 0.0
        posted = 0.0
        for r in receipts:
            outlet = r.get("outlet_name", "F&B")
            pay = r.get("payment_type", "unknown")
            tot = float(r.get("total", 0))
            by_outlet[outlet] = by_outlet.get(outlet, 0) + tot
            by_payment[pay] = by_payment.get(pay, 0) + tot
            total += tot
            if r.get("posted_to_folio"):
                posted += tot
        return {
            "property_id": property_id, "date": date,
            "receipts_count": len(receipts),
            "gross_total": round(total, 2),
            "posted_to_folio_total": round(posted, 2),
            "cash_card_total": round(total - posted, 2),
            "by_outlet": {k: round(v, 2) for k, v in by_outlet.items()},
            "by_payment": {k: round(v, 2) for k, v in by_payment.items()},
        }

    return router
