"""
Cash Float / Drawer Session Tracking (P3).
Receptionist opens a drawer with a float (opening balance), records cash
transactions during the shift, and closes with counted cash. Variance is
auto-flagged for manager review. Industry-standard shift close for front-desk cash.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_cash_drawer_router(db, require_roles):
    router = APIRouter()

    @router.get("/cash-drawer/active/{property_id}")
    async def get_active(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Is there an open drawer for this property right now?"""
        row = await db.cash_drawer_sessions.find_one(
            {"property_id": property_id, "status": "open"}, {"_id": 0}
        )
        return {"open": bool(row), "session": row}

    @router.get("/cash-drawer/sessions/{property_id}")
    async def list_sessions(property_id: str, limit: int = 30,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.cash_drawer_sessions.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("opened_at", -1).to_list(int(limit))
        return rows

    @router.post("/cash-drawer/open/{property_id}")
    async def open_drawer(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Start a shift. Body: {opening_float, notes}"""
        existing = await db.cash_drawer_sessions.find_one(
            {"property_id": property_id, "status": "open"}, {"_id": 0}
        )
        if existing:
            raise HTTPException(status_code=409, detail="A drawer is already open for this property")

        session = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "status": "open",
            "opening_float": float(data.get("opening_float") or 0),
            "currency": data.get("currency", "GBP"),
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "opened_by": current_user.get("name", ""),
            "opening_notes": (data.get("notes") or "").strip(),
            "transactions": [],
        }
        await db.cash_drawer_sessions.insert_one(session)
        session.pop("_id", None)
        return session

    @router.post("/cash-drawer/sessions/{session_id}/transaction")
    async def record_tx(session_id: str, data: Dict,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Log a cash-in or cash-out against the open drawer.
        Body: {direction: 'in'|'out', amount, description, booking_ref?}
        """
        session = await db.cash_drawer_sessions.find_one({"id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.get("status") != "open":
            raise HTTPException(status_code=409, detail="Drawer is closed")
        direction = data.get("direction", "in")
        if direction not in ("in", "out"):
            raise HTTPException(status_code=400, detail="direction must be 'in' or 'out'")
        amount = float(data.get("amount") or 0)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be > 0")

        tx = {
            "id": str(uuid.uuid4()),
            "at": datetime.now(timezone.utc).isoformat(),
            "by": current_user.get("name", ""),
            "direction": direction,
            "amount": round(amount, 2),
            "description": (data.get("description") or "").strip(),
            "booking_ref": (data.get("booking_ref") or "").strip(),
        }
        await db.cash_drawer_sessions.update_one(
            {"id": session_id}, {"$push": {"transactions": tx}}
        )
        return tx

    @router.post("/cash-drawer/sessions/{session_id}/close")
    async def close_drawer(session_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Close the drawer with counted cash. Computes variance."""
        session = await db.cash_drawer_sessions.find_one({"id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.get("status") != "open":
            raise HTTPException(status_code=409, detail="Drawer already closed")

        txs = session.get("transactions", [])
        cash_in = sum(t["amount"] for t in txs if t["direction"] == "in")
        cash_out = sum(t["amount"] for t in txs if t["direction"] == "out")
        expected = round(float(session.get("opening_float", 0)) + cash_in - cash_out, 2)
        counted = float(data.get("counted_cash") or 0)
        variance = round(counted - expected, 2)

        await db.cash_drawer_sessions.update_one(
            {"id": session_id},
            {"$set": {
                "status": "closed",
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "closed_by": current_user.get("name", ""),
                "closing_notes": (data.get("notes") or "").strip(),
                "cash_in": round(cash_in, 2),
                "cash_out": round(cash_out, 2),
                "expected_cash": expected,
                "counted_cash": round(counted, 2),
                "variance": variance,
                "variance_flagged": abs(variance) >= 5.0,
            }}
        )
        return await db.cash_drawer_sessions.find_one({"id": session_id}, {"_id": 0})

    return router
