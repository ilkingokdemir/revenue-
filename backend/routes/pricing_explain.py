"""
AI Pricing Explainability — Revenue Management's #1 unanswered question:
"Why did the system propose this rate?"

Competitors (IDeaS, Duetto, Mews RM) give numbers; we give *narrative + driver
breakdown + scenario alternatives* in plain language.

Endpoints
---------
POST /pricing/explain             → AI explains a rate proposal
GET  /pricing/explain/history/{property_id}
POST /pricing/explain/{id}/decision   → RM saves accept|reject|override

Data model `pricing_explanations`:
{
  id, property_id, room_type, target_date,
  current_rate, proposed_rate, occupancy_pct, pace_lead_30d,
  demand_signals, events, comp_set,
  narrative, confidence, key_drivers[], risks[], alternative_rates[],
  decision: null|accept|reject|override, decision_rate, decision_at, decision_by,
  created_at, created_by
}
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import uuid
import os
import json as _json
import logging

logger = logging.getLogger(__name__)


class CompSetItem(BaseModel):
    name: str
    rate: float


class ExplainReq(BaseModel):
    property_id: str
    room_type: str
    target_date: str                          # YYYY-MM-DD
    current_rate: float
    proposed_rate: float
    occupancy_pct: float = Field(..., ge=0, le=100)
    pace_lead_30d: Optional[float] = None     # bookings vs same-day-last-year
    demand_signals: Optional[List[str]] = None  # ["search spike", "weekend"]
    events: Optional[List[str]] = None        # ["Concert at Arena", "Conference"]
    comp_set: Optional[List[CompSetItem]] = None
    notes: Optional[str] = None


class DecisionReq(BaseModel):
    decision: str                              # accept | reject | override
    final_rate: Optional[float] = None         # required for override
    note: Optional[str] = None


def create_pricing_explain_router(db, require_roles, LlmChat=None, UserMessage=None):
    router = APIRouter()

    @router.post("/pricing/explain")
    async def explain(req: ExplainReq,
                      current_user: dict = Depends(require_roles("admin", "manager", "revenue"))):
        if not LlmChat or not UserMessage:
            raise HTTPException(503, "LLM not configured")
        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key:
            raise HTTPException(503, "EMERGENT_LLM_KEY missing")

        delta = req.proposed_rate - req.current_rate
        delta_pct = (delta / req.current_rate * 100) if req.current_rate else 0

        # Build compact context for LLM
        ctx = {
            "room_type": req.room_type,
            "target_date": req.target_date,
            "current_rate": req.current_rate,
            "proposed_rate": req.proposed_rate,
            "delta_pct": round(delta_pct, 1),
            "occupancy_pct": req.occupancy_pct,
            "pace_lead_30d": req.pace_lead_30d,
            "demand_signals": req.demand_signals or [],
            "events": req.events or [],
            "comp_set": [c.model_dump() for c in (req.comp_set or [])],
            "notes": req.notes,
        }

        system = (
            "You are a senior hotel revenue manager. Explain a proposed nightly rate change "
            "to a hotel manager who needs to decide whether to accept it.\n"
            "Return ONLY a JSON object with this exact shape:\n"
            '{\n'
            '  "narrative": "<2-4 sentences in Turkish, plain language, no jargon>",\n'
            '  "confidence": 0..100,\n'
            '  "key_drivers": [\n'
            '    {"label": "<short Turkish label>", "weight": 0..100, "direction": "up"|"down"|"neutral"}\n'
            '    // 3-5 drivers, weights sum approximately 100\n'
            '  ],\n'
            '  "risks": ["<short risk in Turkish>", ...],     // 1-3 items\n'
            '  "alternative_rates": [\n'
            '    {"rate": <number>, "scenario": "<short Turkish reason>"}\n'
            '    // exactly 2 alternatives — typically a more conservative and a more aggressive one\n'
            '  ]\n'
            '}\n'
            "Direction: 'up' = pushes rate higher, 'down' = pushes rate lower, 'neutral' = mixed."
        )
        comp_str = ", ".join(f"{c['name']}={c['rate']}" for c in ctx['comp_set']) or "—"
        prompt = (
            f"Otel: {req.property_id} | Oda: {ctx['room_type']} | Tarih: {ctx['target_date']}\n"
            f"Mevcut fiyat: {ctx['current_rate']} | Önerilen: {ctx['proposed_rate']} ({ctx['delta_pct']:+.1f}%)\n"
            f"Doluluk: {ctx['occupancy_pct']}% | Pace 30g: {ctx['pace_lead_30d']}\n"
            f"Talep sinyalleri: {', '.join(ctx['demand_signals']) or '—'}\n"
            f"Etkinlikler: {', '.join(ctx['events']) or '—'}\n"
            f"Comp set: {comp_str}\n"
            f"Not: {ctx['notes'] or '—'}"
        )

        try:
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"pricing-explain-{uuid.uuid4()}",
                system_message=system,
            ).with_model("openai", "gpt-5.2")
            resp = await chat.send_message(UserMessage(text=prompt))
            raw = str(resp).strip() if resp else ""
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
                if raw.endswith("```"):
                    raw = raw[:-3]
            parsed: Dict[str, Any] = _json.loads(raw)
        except _json.JSONDecodeError:
            raise HTTPException(502, "AI did not return valid JSON")
        except Exception as e:
            logger.exception("AI explain failed")
            raise HTTPException(502, f"AI explain failed: {str(e)[:150]}")

        # Sanitize
        narrative = str(parsed.get("narrative") or "")[:1200]
        confidence = max(0, min(100, int(parsed.get("confidence") or 0)))
        drivers_raw = parsed.get("key_drivers", []) if isinstance(parsed.get("key_drivers"), list) else []
        key_drivers = []
        for d in drivers_raw[:6]:
            if not isinstance(d, dict):
                continue
            key_drivers.append({
                "label": str(d.get("label") or "")[:60],
                "weight": max(0, min(100, int(d.get("weight") or 0))),
                "direction": d.get("direction") if d.get("direction") in ("up", "down", "neutral") else "neutral",
            })
        risks = [str(r)[:200] for r in (parsed.get("risks") or [])[:5] if isinstance(r, str)]
        alts_raw = parsed.get("alternative_rates", []) if isinstance(parsed.get("alternative_rates"), list) else []
        alternative_rates = []
        for a in alts_raw[:3]:
            if not isinstance(a, dict):
                continue
            try:
                alternative_rates.append({
                    "rate": round(float(a.get("rate") or 0), 2),
                    "scenario": str(a.get("scenario") or "")[:120],
                })
            except (TypeError, ValueError):
                pass

        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": req.property_id,
            "room_type": req.room_type,
            "target_date": req.target_date,
            "current_rate": req.current_rate,
            "proposed_rate": req.proposed_rate,
            "delta_pct": round(delta_pct, 2),
            "occupancy_pct": req.occupancy_pct,
            "pace_lead_30d": req.pace_lead_30d,
            "demand_signals": req.demand_signals or [],
            "events": req.events or [],
            "comp_set": [c.model_dump() for c in (req.comp_set or [])],
            "narrative": narrative,
            "confidence": confidence,
            "key_drivers": key_drivers,
            "risks": risks,
            "alternative_rates": alternative_rates,
            "decision": None,
            "decision_rate": None,
            "decision_at": None,
            "decision_by": None,
            "notes": req.notes,
            "created_at": now,
            "created_by": current_user.get("email"),
        }
        await db.pricing_explanations.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/pricing/explain/history/{property_id}")
    async def history(property_id: str, limit: int = 50,
                      current_user: dict = Depends(require_roles("admin", "manager", "revenue"))):
        limit = max(1, min(500, limit))
        items = await db.pricing_explanations.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(limit)
        return {"items": items, "count": len(items)}

    @router.post("/pricing/explain/{exp_id}/decision")
    async def decide(exp_id: str, req: DecisionReq,
                     current_user: dict = Depends(require_roles("admin", "manager", "revenue"))):
        if req.decision not in ("accept", "reject", "override"):
            raise HTTPException(400, "decision must be accept|reject|override")
        if req.decision == "override" and (req.final_rate is None or req.final_rate <= 0):
            raise HTTPException(400, "override requires positive final_rate")

        exp = await db.pricing_explanations.find_one({"id": exp_id}, {"_id": 0})
        if not exp:
            raise HTTPException(404, "explanation not found")
        if exp.get("decision"):
            raise HTTPException(400, f"already decided: {exp['decision']}")

        final_rate = (
            exp["proposed_rate"] if req.decision == "accept" else
            exp["current_rate"] if req.decision == "reject" else
            req.final_rate
        )
        now = datetime.now(timezone.utc).isoformat()
        await db.pricing_explanations.update_one(
            {"id": exp_id},
            {"$set": {
                "decision": req.decision,
                "decision_rate": final_rate,
                "decision_at": now,
                "decision_by": current_user.get("email"),
                "decision_note": req.note,
            }}
        )
        return {"id": exp_id, "decision": req.decision, "final_rate": final_rate, "decided_at": now}

    @router.get("/pricing/explain/dashboard/{property_id}")
    async def dashboard(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "revenue"))):
        items = await db.pricing_explanations.find(
            {"property_id": property_id}, {"_id": 0, "decision": 1, "delta_pct": 1, "confidence": 1, "decision_rate": 1, "proposed_rate": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(500)
        total = len(items)
        decided = [i for i in items if i.get("decision")]
        accepted = sum(1 for i in items if i.get("decision") == "accept")
        rejected = sum(1 for i in items if i.get("decision") == "reject")
        overridden = sum(1 for i in items if i.get("decision") == "override")
        avg_conf = round(sum(i.get("confidence", 0) for i in items) / total, 1) if total else 0
        avg_delta = round(sum(abs(i.get("delta_pct", 0)) for i in items) / total, 1) if total else 0
        accept_rate = round(accepted / len(decided) * 100, 1) if decided else 0
        return {
            "total": total,
            "pending": total - len(decided),
            "accepted": accepted,
            "rejected": rejected,
            "overridden": overridden,
            "accept_rate_pct": accept_rate,
            "avg_confidence": avg_conf,
            "avg_abs_delta_pct": avg_delta,
        }

    return router
