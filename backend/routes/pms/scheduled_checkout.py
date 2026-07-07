"""
Scheduled Online Check-out (iter 367) — Mews parity
====================================================
Guests pick a check-out time via portal / kiosk and walk out without
stopping at reception. Managers see a "Departures today" board with
scheduled times. When the scheduled time arrives (or 15 min after),
the booking auto-transitions to `checked_out`.

Endpoints
---------
  POST /api/checkout/schedule
        body: {booking_id, checkout_at (ISO), notes?, guest_email?}
        → creates/updates a scheduled_checkouts row.
        Publicly callable (guest portal doesn't require auth).

  GET  /api/checkout/schedule/{booking_id}
        → what the guest scheduled (or null).

  DELETE /api/checkout/schedule/{booking_id}
        → guest / staff cancels the scheduled checkout.

  GET  /api/checkout/scheduled/today          (admin/manager/receptionist)
        → list of scheduled check-outs today with booking + guest snapshot.

  POST /api/checkout/scheduled/{booking_id}/execute-now  (staff)
        → immediately execute the checkout (bypass the timer).

  POST /api/checkout/scheduled/tick                       (internal)
        → cron-safe endpoint that flushes ripe scheduled checkouts
          (invocation-safe: idempotent, no dup-flush).

Collection
----------
  scheduled_checkouts {
    id,               booking_id,   property_id,   checkout_at (ISO),
    notes,            guest_email,  status: "pending" | "done" | "cancelled",
    executed_at?,     created_at,   updated_at,
  }
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScheduleCheckoutBody(BaseModel):
    booking_id: str
    checkout_at: str  # ISO datetime string
    notes: Optional[str] = Field(default=None, max_length=500)
    guest_email: Optional[str] = None


def create_scheduled_checkout_router(db, require_roles):
    router = APIRouter(prefix="/checkout", tags=["scheduled-checkout"])

    async def _booking(booking_id: str) -> dict:
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Rezervasyon bulunamadı")
        return b

    def _parse_iso(s: str) -> datetime:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, "checkout_at ISO 8601 formatında olmalı") from exc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    # ─── Guest / public: schedule (idempotent per booking) ─────────────
    @router.post("/schedule")
    async def schedule_checkout(body: ScheduleCheckoutBody):
        booking = await _booking(body.booking_id)
        checkout_dt = _parse_iso(body.checkout_at)
        # Guardrails
        now = datetime.now(timezone.utc)
        if checkout_dt < now - timedelta(minutes=5):
            raise HTTPException(400, "Check-out zamanı geçmişte olamaz")
        # Cap: max 48h ahead
        if checkout_dt > now + timedelta(hours=48):
            raise HTTPException(400, "En fazla 48 saat sonrası seçilebilir")

        doc = {
            "booking_id":   body.booking_id,
            "property_id":  booking.get("property_id"),
            "checkout_at":  checkout_dt.isoformat(),
            "notes":        (body.notes or "").strip(),
            "guest_email":  body.guest_email or booking.get("guest_email"),
            "status":       "pending",
            "updated_at":   _now(),
        }
        await db.scheduled_checkouts.update_one(
            {"booking_id": body.booking_id},
            {"$set": doc,
             "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": _now()}},
            upsert=True,
        )
        return {"ok": True, "booking_id": body.booking_id, "checkout_at": doc["checkout_at"]}

    @router.get("/schedule/{booking_id}")
    async def get_scheduled(booking_id: str):
        row = await db.scheduled_checkouts.find_one({"booking_id": booking_id}, {"_id": 0})
        return row or {}

    # Public lightweight booking snapshot — needed by SelfCheckoutPage.
    # Returns only fields safe to expose without auth (no billing, no email log).
    @router.get("/booking/{booking_id}/snapshot")
    async def public_booking_snapshot(booking_id: str):
        b = await _booking(booking_id)
        return {
            "id":              b.get("id"),
            "guest_name":      b.get("guest_name"),
            "guest_email":     b.get("guest_email"),
            "room_number":     b.get("room_number"),
            "check_in_date":   b.get("check_in") or b.get("check_in_date"),
            "check_out_date":  b.get("check_out") or b.get("check_out_date"),
            "status":          b.get("status"),
        }

    @router.delete("/schedule/{booking_id}")
    async def cancel_scheduled(booking_id: str):
        res = await db.scheduled_checkouts.update_one(
            {"booking_id": booking_id, "status": "pending"},
            {"$set": {"status": "cancelled", "updated_at": _now()}},
        )
        return {"ok": True, "cancelled": res.modified_count > 0}

    # ─── Staff: today's board ───────────────────────────────────────────
    @router.get("/scheduled/today")
    async def list_scheduled_today(
        property_id: Optional[str] = None,
        _: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        q = {
            "status": "pending",
            "checkout_at": {"$gte": start.isoformat(), "$lt": end.isoformat()},
        }
        if property_id and property_id != "all":
            q["property_id"] = property_id
        rows = await db.scheduled_checkouts.find(q, {"_id": 0}).sort("checkout_at", 1).to_list(500)

        # Hydrate with booking + guest snapshot for the board
        booking_ids = [r["booking_id"] for r in rows]
        bookings = await db.bookings.find({"id": {"$in": booking_ids}}, {"_id": 0}).to_list(500)
        b_map = {b["id"]: b for b in bookings}

        now = datetime.now(timezone.utc)
        out = []
        for r in rows:
            b = b_map.get(r["booking_id"], {})
            dt = _parse_iso(r["checkout_at"])
            out.append({
                **r,
                "guest_name":    (b.get("guest_name") or "").strip(),
                "room_number":   b.get("room_number"),
                "booking_ref":   b.get("id"),
                "total_price":   b.get("total_price"),
                "minutes_left":  round((dt - now).total_seconds() / 60),
                "is_overdue":    dt < now,
            })
        return {"total": len(out), "items": out}

    # ─── Staff: force-execute (guest already left) ──────────────────────
    @router.post("/scheduled/{booking_id}/execute-now")
    async def execute_now(
        booking_id: str,
        _: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        return await _execute_one(booking_id)

    # ─── Cron: tick every ~5 min ─────────────────────────────────────────
    @router.post("/scheduled/tick")
    async def tick():
        """Flush all `pending` scheduled checkouts whose time has passed.
        Idempotent — status guards prevent double-processing."""
        now_iso = _now()
        ripe = await db.scheduled_checkouts.find(
            {"status": "pending", "checkout_at": {"$lte": now_iso}}, {"_id": 0}
        ).to_list(500)
        results = []
        for row in ripe:
            try:
                r = await _execute_one(row["booking_id"])
                results.append({"booking_id": row["booking_id"], **r})
            except HTTPException as e:
                results.append({"booking_id": row["booking_id"], "error": e.detail})
        return {"processed": len(results), "items": results}

    async def _execute_one(booking_id: str) -> dict:
        row = await db.scheduled_checkouts.find_one({"booking_id": booking_id}, {"_id": 0})
        if not row:
            raise HTTPException(404, "Planlı check-out kaydı yok")
        if row["status"] == "done":
            return {"ok": True, "already_done": True}
        if row["status"] == "cancelled":
            raise HTTPException(400, "İptal edilmiş kayıt çalıştırılamaz")
        booking = await _booking(booking_id)
        # Flip booking status to checked_out (guard: only if currently checked-in / confirmed)
        cur = (booking.get("status") or "").lower()
        if cur not in {"checked_out", "cancelled"}:
            await db.bookings.update_one(
                {"id": booking_id},
                {"$set": {
                    "status": "checked_out",
                    "checked_out_at": _now(),
                    "checkout_channel": "scheduled_self_service",
                }},
            )
        await db.scheduled_checkouts.update_one(
            {"booking_id": booking_id},
            {"$set": {"status": "done", "executed_at": _now(), "updated_at": _now()}},
        )
        return {"ok": True, "booking_id": booking_id, "executed_at": _now()}

    return router
