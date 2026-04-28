"""
HK Turnover Kanban with AI Cleanliness Auto-Approval.

State machine per room:
  vacant_dirty → cleaning_in_progress → ai_inspection → vacant_clean (sellable)
                                       ↓
                                    needs_rework (back to cleaning)

AI integration:
  Submitting photos auto-runs cleanliness scoring.
  score >= ai_pass_threshold (default 75) → auto vacant_clean (no supervisor needed)
  score 50-74 → ai_inspection (supervisor reviews)
  score < 50 → needs_rework (back to cleaning)

This delivers "0-tap supervisor approval" — game-changing flow.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import List, Optional
import uuid
import os
import json as _json
import logging

logger = logging.getLogger(__name__)


VALID_STATES = {"vacant_dirty", "cleaning_in_progress", "ai_inspection", "vacant_clean", "needs_rework", "out_of_service"}


class StartCleaningReq(BaseModel):
    assigned_to: Optional[str] = None     # staff email
    note: Optional[str] = None


class SubmitPhotosReq(BaseModel):
    photos_base64: List[str]               # 1..3 photos
    notes: Optional[str] = None
    ai_pass_threshold: int = 75            # 0..100


class ManualReviewReq(BaseModel):
    decision: str                          # "approve" | "reject"
    note: Optional[str] = None


class SetStateReq(BaseModel):
    state: str
    reason: Optional[str] = None


def _state_label(s: str) -> str:
    return {
        "vacant_dirty": "Kirli",
        "cleaning_in_progress": "Temizleniyor",
        "ai_inspection": "AI Denetiminde",
        "vacant_clean": "Temiz",
        "needs_rework": "Yeniden Yapılmalı",
        "out_of_service": "Servis Dışı",
    }.get(s, s)


async def _ensure_room_card(db, room_id: str, property_id: str):
    """Get or create a turnover card for the room."""
    existing = await db.hk_turnover.find_one({"room_id": room_id, "property_id": property_id}, {"_id": 0})
    if existing:
        return existing
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "room_id": room_id,
        "property_id": property_id,
        "state": "vacant_dirty",
        "assigned_to": None,
        "started_at": None,
        "completed_at": None,
        "last_score": None,
        "last_score_id": None,
        "history": [{"at": now, "state": "vacant_dirty", "by": "system"}],
        "created_at": now,
        "updated_at": now,
    }
    await db.hk_turnover.insert_one(doc)
    doc.pop("_id", None)
    return doc


def create_hk_turnover_router(db, require_roles, LlmChat=None, UserMessage=None, FileContent=None):
    router = APIRouter()

    # ---------- KANBAN BOARD ----------
    @router.get("/hk-turnover/{property_id}")
    async def board(property_id: str,
                    current_user: dict = Depends(require_roles("admin", "manager", "housekeeping", "receptionist"))):
        # All real rooms for property
        rooms = await db.rooms.find({"property_id": property_id}, {"_id": 0, "id": 1, "room_number": 1, "room_type": 1}).to_list(500)
        cards = await db.hk_turnover.find({"property_id": property_id}, {"_id": 0}).to_list(500)
        cards_by_room = {c["room_id"]: c for c in cards}

        result = []
        for r in rooms:
            rid = r.get("room_number") or r.get("id")
            card = cards_by_room.get(rid)
            if not card:
                # Create on first read
                card = await _ensure_room_card(db, rid, property_id)
            result.append({**card, "room_type": r.get("room_type")})

        # Group by state
        by_state = {s: [] for s in VALID_STATES}
        for c in result:
            by_state.setdefault(c["state"], []).append(c)
        # Also order by id within each
        for s in by_state:
            by_state[s].sort(key=lambda x: x["room_id"])

        counts = {s: len(rows) for s, rows in by_state.items()}
        return {"property_id": property_id, "by_state": by_state, "counts": counts, "total": len(result)}

    # ---------- START CLEANING ----------
    @router.post("/hk-turnover/{room_id}/start-cleaning")
    async def start_cleaning(room_id: str, req: StartCleaningReq, property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        card = await _ensure_room_card(db, room_id, property_id)
        if card["state"] not in ("vacant_dirty", "needs_rework"):
            raise HTTPException(400, f"Cannot start cleaning from state {card['state']}")
        now = datetime.now(timezone.utc).isoformat()
        history = card.get("history", []) + [{
            "at": now, "state": "cleaning_in_progress",
            "by": current_user.get("email"),
            "assigned_to": req.assigned_to,
            "note": req.note,
        }]
        await db.hk_turnover.update_one(
            {"id": card["id"]},
            {"$set": {
                "state": "cleaning_in_progress",
                "assigned_to": req.assigned_to or current_user.get("email"),
                "started_at": now,
                "history": history,
                "updated_at": now,
            }}
        )
        return {"state": "cleaning_in_progress", "started_at": now}

    # ---------- SUBMIT PHOTOS (AI auto-approve) ----------
    @router.post("/hk-turnover/{room_id}/submit-photos")
    async def submit_photos(room_id: str, req: SubmitPhotosReq, property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        card = await _ensure_room_card(db, room_id, property_id)
        if card["state"] not in ("cleaning_in_progress", "ai_inspection", "needs_rework"):
            raise HTTPException(400, f"Cannot submit photos from state {card['state']}")
        if not req.photos_base64:
            raise HTTPException(400, "At least 1 photo required")
        if len(req.photos_base64) > 3:
            raise HTTPException(400, "Max 3 photos")
        if req.ai_pass_threshold < 0 or req.ai_pass_threshold > 100:
            raise HTTPException(400, "ai_pass_threshold must be 0..100")

        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key or not LlmChat or not UserMessage or not FileContent:
            raise HTTPException(503, "AI scoring unavailable")

        # Strip data URI prefix
        clean_imgs = [img.split(",", 1)[1] if img.startswith("data:") else img for img in req.photos_base64]

        system = (
            "You are a hotel housekeeping supervisor with 20 years experience. "
            "Analyze photos of a cleaned guest room. Return ONLY a JSON object: "
            '{"cleanliness_score": 0-100, "severity": "pass"|"warning"|"fail", '
            '"issues": ["..."], "observations": ["..."], "next_action": "..."}. '
            "Score 90+ impeccable, 70-89 acceptable minor issues, 50-69 rework, <50 fail. "
            "Turkish text inside JSON values."
        )
        prompt = "Review these room photos and score cleanliness." + (f" Notes: {req.notes}" if req.notes else "")

        try:
            file_contents = [FileContent(content_type="image", file_content_base64=b) for b in clean_imgs]
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"hk-turnover-{uuid.uuid4()}",
                system_message=system,
            ).with_model("openai", "gpt-5.2")
            resp = await chat.send_message(UserMessage(text=prompt, file_contents=file_contents))
            raw = str(resp).strip() if resp else ""
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
                if raw.endswith("```"):
                    raw = raw[:-3]
            parsed = _json.loads(raw)
        except _json.JSONDecodeError:
            raise HTTPException(502, "AI did not return valid JSON")
        except Exception as e:
            logger.exception("AI scoring failed")
            raise HTTPException(502, f"AI scoring failed: {str(e)[:150]}")

        score = max(0, min(100, int(parsed.get("cleanliness_score", 0))))
        severity = parsed.get("severity", "warning")
        issues = parsed.get("issues", [])[:10] if isinstance(parsed.get("issues"), list) else []
        observations = parsed.get("observations", [])[:10] if isinstance(parsed.get("observations"), list) else []
        next_action = str(parsed.get("next_action") or "")[:500]

        # Save score (also visible in main image_ai history)
        now = datetime.now(timezone.utc).isoformat()
        score_doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "room_id": room_id,
            "scored_at": now,
            "scored_by": current_user.get("email"),
            "photo_count": len(clean_imgs),
            "score": score,
            "severity": severity,
            "issues": issues,
            "observations": observations,
            "next_action": next_action,
            "notes": req.notes,
            "photos_b64": clean_imgs,
            "source": "hk_turnover",
            "ai_pass_threshold": req.ai_pass_threshold,
        }
        await db.hk_cleanliness_scores.insert_one(score_doc)

        # Decide next state
        if score >= req.ai_pass_threshold:
            new_state = "vacant_clean"
            decision = "auto_approved"
        elif score >= 50:
            new_state = "ai_inspection"
            decision = "needs_supervisor_review"
        else:
            new_state = "needs_rework"
            decision = "auto_rejected"

        history = card.get("history", []) + [{
            "at": now, "state": new_state, "by": current_user.get("email"),
            "score": score, "decision": decision, "score_id": score_doc["id"],
        }]
        patch = {
            "state": new_state,
            "last_score": score,
            "last_score_id": score_doc["id"],
            "history": history,
            "updated_at": now,
        }
        if new_state == "vacant_clean":
            patch["completed_at"] = now
        await db.hk_turnover.update_one({"id": card["id"]}, {"$set": patch})

        return {
            "score": score,
            "severity": severity,
            "decision": decision,
            "new_state": new_state,
            "issues": issues,
            "observations": observations,
            "next_action": next_action,
            "score_id": score_doc["id"],
        }

    # ---------- SUPERVISOR MANUAL REVIEW ----------
    @router.post("/hk-turnover/{room_id}/manual-review")
    async def manual_review(room_id: str, req: ManualReviewReq, property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        if req.decision not in ("approve", "reject"):
            raise HTTPException(400, "decision must be 'approve' or 'reject'")
        card = await _ensure_room_card(db, room_id, property_id)
        if card["state"] != "ai_inspection":
            raise HTTPException(400, f"Room not in ai_inspection (current: {card['state']})")

        new_state = "vacant_clean" if req.decision == "approve" else "needs_rework"
        now = datetime.now(timezone.utc).isoformat()
        history = card.get("history", []) + [{
            "at": now, "state": new_state, "by": current_user.get("email"),
            "decision": f"manual_{req.decision}", "note": req.note,
        }]
        patch = {"state": new_state, "history": history, "updated_at": now}
        if new_state == "vacant_clean":
            patch["completed_at"] = now
        await db.hk_turnover.update_one({"id": card["id"]}, {"$set": patch})
        return {"new_state": new_state, "decision": f"manual_{req.decision}"}

    # ---------- DIRECT STATE CHANGE (admin override) ----------
    @router.post("/hk-turnover/{room_id}/set-state")
    async def set_state(room_id: str, req: SetStateReq, property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        if req.state not in VALID_STATES:
            raise HTTPException(400, f"state must be one of {sorted(VALID_STATES)}")
        card = await _ensure_room_card(db, room_id, property_id)
        now = datetime.now(timezone.utc).isoformat()
        history = card.get("history", []) + [{
            "at": now, "state": req.state, "by": current_user.get("email"),
            "decision": "manual_override", "reason": req.reason,
        }]
        await db.hk_turnover.update_one(
            {"id": card["id"]},
            {"$set": {"state": req.state, "history": history, "updated_at": now}}
        )
        return {"state": req.state}

    # ---------- DASHBOARD ----------
    @router.get("/hk-turnover/dashboard/{property_id}")
    async def dashboard(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        rooms = await db.rooms.count_documents({"property_id": property_id})
        cards = await db.hk_turnover.find({"property_id": property_id}, {"_id": 0, "state": 1, "last_score": 1, "completed_at": 1}).to_list(500)

        counts = {s: 0 for s in VALID_STATES}
        for c in cards:
            counts[c.get("state", "vacant_dirty")] = counts.get(c.get("state", "vacant_dirty"), 0) + 1

        # AI auto-approval rate (today's scores)
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        scores_today = await db.hk_cleanliness_scores.find({
            "property_id": property_id,
            "scored_at": {"$gte": today_start},
            "source": "hk_turnover",
        }, {"_id": 0, "score": 1, "ai_pass_threshold": 1}).to_list(2000)

        auto_approved = sum(1 for s in scores_today if s.get("score", 0) >= s.get("ai_pass_threshold", 75))
        rejected = sum(1 for s in scores_today if s.get("score", 0) < 50)
        rework_or_review = len(scores_today) - auto_approved - rejected
        avg_score = round(sum(s.get("score", 0) for s in scores_today) / len(scores_today), 1) if scores_today else 0

        return {
            "total_rooms": rooms,
            "by_state": counts,
            "scores_today": len(scores_today),
            "auto_approved_today": auto_approved,
            "rejected_today": rejected,
            "review_pending_today": rework_or_review,
            "avg_score_today": avg_score,
            "auto_approval_rate": round(auto_approved / len(scores_today) * 100, 1) if scores_today else 0,
        }

    return router
