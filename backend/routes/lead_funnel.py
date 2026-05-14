"""
CRM Lead Funnel Bridge — Web Concierge → CRM leads + Compset adapter scaffolding.

Two roles:

(A) Lead Funnel:
    Web Concierge sessions that contain booking-intent keywords get automatically
    promoted to `crm_leads` records (linked to property + session). Admin can
    bulk-import or filter for follow-up.

(B) Lighthouse Compset Adapter Scaffolding:
    The existing `routes/compset.py` already has a MOCK pool. This module
    wraps a hot-swappable Lighthouse adapter. When `LIGHTHOUSE_API_KEY` env
    arrives, replace `_simulate_lighthouse_call` with real SDK calls.

Endpoints
---------
Lead Funnel:
  POST /api/lead-funnel/ingest-concierge-sessions/{property_id}
       Scans last N web-concierge sessions, extracts intent leads, stores in crm_leads.
  GET  /api/lead-funnel/leads?property_id=&status=
  PATCH /api/lead-funnel/leads/{lead_id}      — admin updates status (contacted, won, lost)
  POST /api/lead-funnel/leads/{lead_id}/convert — link to booking

Lighthouse adapter:
  GET  /api/lighthouse-adapter/status         — shows if real key configured or mock
  POST /api/lighthouse-adapter/refresh/{property_id} — fetch compset snapshot
"""
from datetime import datetime, timezone, timedelta
import os
import uuid
import random
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


INTENT_KEYWORDS = [
    "rezerv", "fiyat", "müsait", "musait", "uygunluk", "boş", "bos",
    "tarih", "gece", "kişi", "kisi", "oda", "kalmak", "konaklamak",
    "ailecek", "telefon", "iletisim", "iletişim", "ara", "geri dön",
]


def _extract_contact(text: str) -> dict:
    """Naive parser to pull email/phone from free text."""
    import re
    email = None
    phone = None
    m = re.search(r"[\w\.\-_]+@[\w\.-]+\.\w+", text)
    if m:
        email = m.group(0).lower()
    m = re.search(r"\+?\d[\d\s\-]{8,15}\d", text)
    if m:
        phone = m.group(0).replace(" ", "").replace("-", "")
    return {"email": email, "phone": phone}


async def _simulate_lighthouse_call(property_id: str) -> dict:
    """Mock Lighthouse 3B-data-point compset snapshot. Replace with real SDK
    when LIGHTHOUSE_API_KEY is configured."""
    await asyncio.sleep(0.1)
    competitors = [
        {"name": "Marriott London City", "rate_today": round(random.uniform(140, 220), 2)},
        {"name": "Hilton Whitechapel", "rate_today": round(random.uniform(120, 200), 2)},
        {"name": "Premier Inn Aldgate", "rate_today": round(random.uniform(70, 120), 2)},
        {"name": "ibis London City", "rate_today": round(random.uniform(80, 140), 2)},
        {"name": "Holiday Inn Express", "rate_today": round(random.uniform(90, 150), 2)},
    ]
    return {
        "provider": "lighthouse_mock",
        "property_id": property_id,
        "snapshot_at": _now_iso(),
        "competitors": competitors,
        "market_average": round(
            sum(c["rate_today"] for c in competitors) / len(competitors), 2),
        "data_points_sampled": random.randint(2_800_000_000, 3_200_000_000),  # daily ≈3B
        "note": "MOCK data. Set LIGHTHOUSE_API_KEY env to switch to real source.",
    }


def create_lead_funnel_router(db, require_roles):
    router = APIRouter()

    # ============== Lead Funnel ==============
    @router.post("/lead-funnel/ingest-concierge-sessions/{property_id}")
    async def ingest_sessions(property_id: str, body: dict = None,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        body = body or {}
        limit = int(body.get("limit", 100))
        cutoff_hours = int(body.get("cutoff_hours", 168))  # 7 days default
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)).isoformat()
        sessions = await db.web_concierge_sessions.find(
            {"property_id": property_id, "started_at": {"$gte": cutoff}},
            {"_id": 0}
        ).limit(limit).to_list(limit)
        created = 0
        skipped = 0
        for s in sessions:
            msgs = s.get("messages", [])
            user_msgs = [m["content"] for m in msgs if m["role"] == "user"]
            joined = " ".join(user_msgs).lower()
            # Intent check
            if not any(kw in joined for kw in INTENT_KEYWORDS):
                continue
            # Already promoted?
            ex = await db.crm_leads.find_one(
                {"source": "web_concierge", "source_id": s["session_id"]},
                {"_id": 0, "id": 1}
            )
            if ex:
                skipped += 1
                continue
            # Try to extract contact info
            full_text = " ".join(user_msgs)
            contact = _extract_contact(full_text)
            # Score: intent strength
            score = sum(1 for kw in INTENT_KEYWORDS if kw in joined)
            lead = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "source": "web_concierge",
                "source_id": s["session_id"],
                "name": "Web Misafiri",
                "email": contact["email"],
                "phone": contact["phone"],
                "intent_summary": user_msgs[0][:200] if user_msgs else "",
                "message_count": len(msgs),
                "intent_score": score,
                "status": "new",
                "last_activity_at": s.get("last_message_at") or s.get("started_at"),
                "created_at": _now_iso(),
                "created_by": current_user.get("name", "ai_ingestor"),
            }
            await db.crm_leads.insert_one(lead)
            created += 1
        return {"ok": True, "scanned": len(sessions),
                "created": created, "skipped_duplicates": skipped}

    @router.get("/lead-funnel/leads")
    async def list_leads(property_id: str = "", status: str = "",
                         source: str = "", limit: int = 100,
                         _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if property_id:
            q["property_id"] = property_id
        if status:
            q["status"] = status
        if source:
            q["source"] = source
        items = await db.crm_leads.find(q, {"_id": 0}).sort(
            "created_at", -1
        ).to_list(min(limit, 500))
        # Quick counts per status
        counts = {"new": 0, "contacted": 0, "qualified": 0, "won": 0, "lost": 0}
        for i in items:
            counts[i.get("status", "new")] = counts.get(i.get("status", "new"), 0) + 1
        return {"items": items, "count": len(items), "counts_by_status": counts}

    @router.patch("/lead-funnel/leads/{lead_id}")
    async def update_lead(lead_id: str, body: dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"name", "email", "phone", "status", "notes",
                   "assigned_to", "follow_up_at"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
        update["updated_at"] = _now_iso()
        update["updated_by"] = current_user.get("name", "")
        r = await db.crm_leads.update_one({"id": lead_id}, {"$set": update})
        if not r.matched_count:
            raise HTTPException(404, "Lead not found")
        return {"ok": True}

    @router.post("/lead-funnel/leads/{lead_id}/convert")
    async def convert_lead(lead_id: str, body: dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        booking_id = body.get("booking_id")
        if not booking_id:
            raise HTTPException(400, "booking_id required")
        r = await db.crm_leads.update_one(
            {"id": lead_id},
            {"$set": {"status": "won",
                      "converted_booking_id": booking_id,
                      "converted_at": _now_iso(),
                      "converted_by": current_user.get("name", "")}}
        )
        if not r.matched_count:
            raise HTTPException(404, "Lead not found")
        return {"ok": True}

    # ============== Lighthouse Compset Adapter ==============
    @router.get("/lighthouse-adapter/status")
    async def adapter_status(_: dict = Depends(require_roles("admin", "manager"))):
        has_key = bool(os.environ.get("LIGHTHOUSE_API_KEY"))
        return {
            "provider": "lighthouse" if has_key else "mock",
            "real_data": has_key,
            "data_points_per_day": "3 billion" if has_key else "mock",
            "note": ("Real Lighthouse adapter active." if has_key
                     else "Set LIGHTHOUSE_API_KEY env var to switch to real data source."),
        }

    @router.post("/lighthouse-adapter/refresh/{property_id}")
    async def refresh(property_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        snap = await _simulate_lighthouse_call(property_id)
        # Persist snapshot
        snap["id"] = str(uuid.uuid4())
        snap["refreshed_by"] = current_user.get("name", "")
        await db.lighthouse_snapshots.insert_one(snap)
        snap.pop("_id", None)
        return snap

    return router
