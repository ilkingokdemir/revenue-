"""
Image AI Cleanliness Scoring — HK supervisor photo check powered by GPT-5.2 Vision.

Use case:
  HK attendant cleans a room, takes 1-3 photos → uploads to endpoint.
  AI analyzes the images and returns:
    - cleanliness_score 0-100
    - issues[] (e.g. "unmade bed", "toiletry missing", "trash visible")
    - severity (pass / warning / fail)
    - specific_observations[] (specific visual details)

This eliminates subjective supervisor approval bias and speeds up room turnaround.

Competitor comparison:
  None of Cloudbeds/Mews/Opera provide AI-vision HK scoring.
  This is a unique competitive edge.
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


class ScoreReq(BaseModel):
    property_id: str
    room_id: str
    photos_base64: List[str]   # data URIs or raw base64 (<=3 images)
    staff_id: Optional[str] = None
    notes: Optional[str] = None


class ManualScoreReq(BaseModel):
    score_override: int


def create_image_ai_router(db, require_roles, LlmChat=None, UserMessage=None, FileContent=None):
    router = APIRouter()

    @router.post("/image-ai/cleanliness-score")
    async def score_cleanliness(req: ScoreReq,
                                current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        if not req.photos_base64:
            raise HTTPException(400, "At least 1 photo required")
        if len(req.photos_base64) > 3:
            raise HTTPException(400, "Max 3 photos per scoring")

        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key or not LlmChat or not UserMessage or not FileContent:
            raise HTTPException(503, "AI scoring unavailable (no LLM key)")

        # Strip data URI prefix if present
        clean_imgs = []
        for img in req.photos_base64:
            if img.startswith("data:"):
                _, b64 = img.split(",", 1)
                clean_imgs.append(b64)
            else:
                clean_imgs.append(img)

        system = (
            "You are a hotel housekeeping supervisor with 20 years experience. "
            "Analyze photos of a cleaned guest room. Be strict but fair. "
            "Return ONLY a JSON object with this exact shape: "
            '{"cleanliness_score": 0-100, "severity": "pass"|"warning"|"fail", '
            '"issues": ["..."], "observations": ["..."], "next_action": "..."}. '
            "Score 90+ = impeccable; 70-89 = acceptable with minor issues; "
            "50-69 = needs rework; <50 = fail. Write Turkish text inside the JSON values."
        )
        prompt = (
            "Review these room photos and score cleanliness. "
            + (f"Staff notes: {req.notes}\n" if req.notes else "")
            + "Return only JSON, no markdown fences."
        )

        try:
            file_contents = [FileContent(content_type="image", file_content_base64=b) for b in clean_imgs]
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"cleanliness-{uuid.uuid4()}",
                system_message=system,
            ).with_model("openai", "gpt-5.2")
            msg = UserMessage(text=prompt, file_contents=file_contents)
            resp = await chat.send_message(msg)
            raw = str(resp).strip() if resp else ""
            # Strip markdown fences
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
                if raw.endswith("```"):
                    raw = raw[:-3]
            parsed = _json.loads(raw)
        except _json.JSONDecodeError as e:
            logger.warning(f"Cleanliness scoring JSON parse failed: {e}")
            raise HTTPException(502, "AI did not return valid JSON")
        except Exception as e:
            logger.exception(f"Cleanliness scoring failed: {e}")
            raise HTTPException(502, f"AI scoring failed: {str(e)[:150]}")

        score = int(parsed.get("cleanliness_score", 0))
        severity = parsed.get("severity", "warning")
        if severity not in ("pass", "warning", "fail"):
            severity = "warning"
        issues = parsed.get("issues", [])[:10] if isinstance(parsed.get("issues"), list) else []
        observations = parsed.get("observations", [])[:10] if isinstance(parsed.get("observations"), list) else []
        next_action = str(parsed.get("next_action") or "")[:500]

        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": req.property_id,
            "room_id": req.room_id,
            "staff_id": req.staff_id,
            "scored_at": now,
            "scored_by": current_user.get("email"),
            "photo_count": len(clean_imgs),
            "score": max(0, min(100, score)),
            "severity": severity,
            "issues": issues,
            "observations": observations,
            "next_action": next_action,
            "notes": req.notes,
            "photos_b64": clean_imgs,  # store for audit
            "source": "ai",
        }
        await db.hk_cleanliness_scores.insert_one(doc)

        return {k: v for k, v in doc.items() if k not in ("_id", "photos_b64")}

    @router.get("/image-ai/cleanliness-history/{property_id}")
    async def history(property_id: str, room_id: Optional[str] = None, limit: int = 50,
                      current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        if limit < 1 or limit > 200:
            raise HTTPException(400, "limit must be 1..200")
        q = {"property_id": property_id}
        if room_id:
            q["room_id"] = room_id
        rows = await db.hk_cleanliness_scores.find(q, {"_id": 0, "photos_b64": 0}).sort("scored_at", -1).limit(limit).to_list(limit)
        total = len(rows)
        pass_count = sum(1 for r in rows if r.get("severity") == "pass")
        fail_count = sum(1 for r in rows if r.get("severity") == "fail")
        avg_score = round(sum(r.get("score", 0) for r in rows) / total, 1) if total else 0
        return {
            "rows": rows,
            "count": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pass_rate": round(pass_count / total * 100, 1) if total else 0,
            "avg_score": avg_score,
        }

    @router.get("/image-ai/cleanliness-score/{score_id}")
    async def score_detail(score_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        row = await db.hk_cleanliness_scores.find_one({"id": score_id}, {"_id": 0})
        if not row:
            raise HTTPException(404, "Score not found")
        return row

    return router
