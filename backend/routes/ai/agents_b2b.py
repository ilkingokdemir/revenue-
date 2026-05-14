"""
Travel Agent / Corporate B2B Portal
-----------------------------------
Per-property TA/corporate accounts with negotiated rates, commission tracking
and a "book on behalf of" endpoint that creates regular bookings tagged with
the agent_id. Commission accrues per stay and can be reconciled monthly.

Endpoints:
  GET    /api/agents/{property_id}                    — list agents
  POST   /api/agents/{property_id}                     — upsert (admin)
  DELETE /api/agents/{property_id}/{agent_id}
  GET    /api/agents/{agent_id}/rates                  — rate plans
  POST   /api/agents/{agent_id}/book                   — book on behalf
  GET    /api/agents/{property_id}/commission-report?from=&to=
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid


def create_agents_router(db, require_roles):
    router = APIRouter()

    @router.get("/agents/{property_id}")
    async def list_agents(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.travel_agents.find(
            {"property_id": property_id, "active": {"$ne": False}}, {"_id": 0}
        ).sort("name", 1).to_list(200)
        return rows

    @router.post("/agents/{property_id}")
    async def upsert_agent(property_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        aid = data.get("id") or str(uuid.uuid4())
        update = {
            "id": aid,
            "property_id": property_id,
            "name": data.get("name", "Unnamed agent"),
            "type": data.get("type", "travel_agent"),  # travel_agent | corporate | wholesaler
            "iata": data.get("iata", ""),
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "contact_person": data.get("contact_person", ""),
            "negotiated_discount_pct": float(data.get("negotiated_discount_pct") or 0),
            "commission_pct": float(data.get("commission_pct") or 10),
            "fixed_rate_overrides": data.get("fixed_rate_overrides") or {},  # {room_type_id: rate}
            "credit_limit": float(data.get("credit_limit") or 0),
            "billing_terms": data.get("billing_terms", "Net 30"),
            "active": bool(data.get("active", True)),
            "notes": data.get("notes", ""),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.travel_agents.update_one(
            {"id": aid}, {"$set": update, "$setOnInsert": {
                "created_at": update["updated_at"],
                "portal_token": str(uuid.uuid4()),
            }}, upsert=True
        )
        doc = await db.travel_agents.find_one({"id": aid}, {"_id": 0})
        return {"ok": True, "agent": doc}

    @router.delete("/agents/{property_id}/{agent_id}")
    async def deactivate(property_id: str, agent_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.travel_agents.update_one(
            {"id": agent_id, "property_id": property_id}, {"$set": {"active": False}}
        )
        return {"ok": True}

    @router.get("/agents/{agent_id}/rates")
    async def agent_rates(agent_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        agent = await db.travel_agents.find_one({"id": agent_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        rts = await db.room_types.find(
            {"property_id": agent["property_id"], "is_active": {"$ne": False}}, {"_id": 0}
        ).to_list(50)
        items = []
        for rt in rts:
            base = float(rt.get("base_price") or rt.get("price_per_night") or 0)
            override = (agent.get("fixed_rate_overrides") or {}).get(rt.get("id"))
            if override:
                final = float(override)
            else:
                final = round(base * (1 - agent.get("negotiated_discount_pct", 0) / 100), 2)
            items.append({
                "room_type_id": rt.get("id"),
                "room_type_name": rt.get("name") or rt.get("type"),
                "base_rate": base,
                "agent_rate": final,
                "savings_pct": round((base - final) / base * 100, 1) if base else 0,
                "override": bool(override),
            })
        return {"agent": agent, "rates": items}

    @router.post("/agents/{agent_id}/book")
    async def book_on_behalf(agent_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        agent = await db.travel_agents.find_one({"id": agent_id}, {"_id": 0})
        if not agent:
            raise HTTPException(404, "Agent not found")
        room_type_id = data.get("room_type_id", "")
        check_in = data.get("check_in", "")
        nights = max(1, int(data.get("nights") or 1))
        guest = data.get("guest") or {}
        if not room_type_id or not check_in or not guest.get("name"):
            raise HTTPException(400, "room_type_id, check_in, guest.name required")
        d_in = datetime.fromisoformat(check_in).date()
        d_out = d_in + timedelta(days=nights)

        rt = await db.room_types.find_one({"id": room_type_id}, {"_id": 0})
        if not rt:
            raise HTTPException(404, "Room type not found")
        base_rate = float(rt.get("base_price") or rt.get("price_per_night") or 0)
        override = (agent.get("fixed_rate_overrides") or {}).get(room_type_id)
        rate = float(override) if override else round(base_rate * (1 - agent.get("negotiated_discount_pct", 0) / 100), 2)
        subtotal = round(rate * nights, 2)
        commission = round(subtotal * agent.get("commission_pct", 0) / 100, 2)

        booking_id = str(uuid.uuid4())
        booking_ref = f"TA-{agent_id[:6].upper()}-{booking_id[:6].upper()}"
        booking = {
            "id": booking_id,
            "property_id": agent["property_id"],
            "booking_ref": booking_ref,
            "channel": "travel_agent",
            "source": agent["name"],
            "agent_id": agent_id,
            "agent_name": agent["name"],
            "agent_iata": agent.get("iata", ""),
            "guest_name": guest.get("name", ""),
            "guest_email": guest.get("email", ""),
            "guest_phone": guest.get("phone", ""),
            "room_type_id": room_type_id,
            "room_type_name": rt.get("name") or rt.get("type"),
            "check_in": check_in,
            "check_out": d_out.isoformat(),
            "nights": nights,
            "guests": int(data.get("guests") or 1),
            "rate_per_night": rate,
            "subtotal": subtotal,
            "total_price": subtotal,
            "currency": rt.get("currency", "GBP"),
            "agent_commission_pct": agent.get("commission_pct", 0),
            "agent_commission_amount": commission,
            "agent_commission_status": "accrued",
            "status": "confirmed",
            "internal_notes": data.get("notes", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", "Staff"),
        }
        await db.bookings.insert_one(dict(booking))
        booking.pop("_id", None)
        return {"ok": True, "booking": booking, "commission_amount": commission}

    @router.get("/agents/{property_id}/commission-report")
    async def commission_report(property_id: str, from_date: Optional[str] = None,
                                  to_date: Optional[str] = None,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        f = from_date or (date.today() - timedelta(days=30)).isoformat()
        t = to_date   or date.today().isoformat()
        bookings = await db.bookings.find(
            {"property_id": property_id, "channel": "travel_agent",
             "check_out": {"$gte": f, "$lte": t}, "status": {"$ne": "cancelled"}},
            {"_id": 0}
        ).to_list(2000)
        by_agent: Dict[str, dict] = {}
        for b in bookings:
            aid = b.get("agent_id", "")
            row = by_agent.setdefault(aid, {
                "agent_id": aid,
                "agent_name": b.get("agent_name", ""),
                "agent_iata": b.get("agent_iata", ""),
                "bookings": 0, "revenue": 0.0, "commission": 0.0,
            })
            row["bookings"] += 1
            row["revenue"] += float(b.get("total_price") or 0)
            row["commission"] += float(b.get("agent_commission_amount") or 0)
        agents = list(by_agent.values())
        for a in agents:
            a["revenue"] = round(a["revenue"], 2)
            a["commission"] = round(a["commission"], 2)
        agents.sort(key=lambda x: x["commission"], reverse=True)
        return {
            "from": f, "to": t,
            "bookings_count": len(bookings),
            "total_revenue": round(sum(a["revenue"] for a in agents), 2),
            "total_commission": round(sum(a["commission"] for a in agents), 2),
            "agents": agents,
        }

    return router
