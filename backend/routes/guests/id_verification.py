"""
ID Verification — Canary paritesi.
Misafir kimlik/pasaport fotoğrafı AI (GPT-5.4 vision) ile okunur, alanlar çıkarılır,
rezervasyondaki isimle eşleştirilir ve arrivals'a "doğrulandı" rozeti düşer.

Collection: id_verifications { booking_id, property_id, status: verified|mismatch|unreadable,
  extracted: {full_name, document_type, document_number, nationality, date_of_birth, expiry_date},
  name_match, confidence, verified_at, verified_by }
"""
import json
import logging
import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_perm

logger = logging.getLogger(__name__)


class VerifyIn(BaseModel):
    booking_id: str
    image_base64: str


def _norm(s: str) -> set:
    tr = str.maketrans("çğıöşüâîû", "cgiosuaiu")
    s = (s or "").lower().translate(tr)
    return set(re.sub(r"[^a-z ]", "", s).split())


def _name_match(a: str, b: str) -> float:
    ta, tb = _norm(a), _norm(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def create_id_verification_router(db):
    router = APIRouter(prefix="/id-verification")

    @router.post("/verify")
    async def verify(body: VerifyIn,
                     current_user: dict = Depends(require_perm("edit_bookings"))):
        booking = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        img = body.image_base64.split(",")[-1].strip()
        if len(img) < 500:
            raise HTTPException(400, "Geçersiz görüntü")

        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            raise HTTPException(503, "AI anahtarı yapılandırılmamış")

        extracted = {}
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
            chat = LlmChat(
                api_key=api_key,
                session_id=f"idv-{body.booking_id[:8]}-{datetime.now(timezone.utc).timestamp():.0f}",
                system_message=(
                    "You are an ID document reader. Extract fields from the identity document photo. "
                    "Reply ONLY with JSON: {\"full_name\": str, \"document_type\": \"passport|id_card|driving_license|other\", "
                    "\"document_number\": str, \"nationality\": str, \"date_of_birth\": str, \"expiry_date\": str, "
                    "\"readable\": bool}. Use empty string for missing fields. "
                    "readable=false if the image is not an identity document or text is illegible."
                ),
            ).with_model("openai", "gpt-5.4")
            resp = await chat.send_message(UserMessage(
                text="Extract the fields from this ID document.",
                file_contents=[ImageContent(image_base64=img)],
            ))
            raw = (resp or "").strip()
            raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.M).strip()
            extracted = json.loads(raw)
        except Exception as e:
            logger.exception("ID verification LLM failed: %s", e)
            raise HTTPException(502, f"AI okuma başarısız: {str(e)[:120]}")

        if not extracted.get("readable", True) or not extracted.get("full_name"):
            status_val, match, conf = "unreadable", 0.0, 0.0
        else:
            match = _name_match(extracted.get("full_name", ""), booking.get("guest_name", ""))
            conf = round(match, 2)
            status_val = "verified" if match >= 0.5 else "mismatch"

        now = datetime.now(timezone.utc).isoformat()
        doc = {"booking_id": body.booking_id, "property_id": booking.get("property_id"),
               "status": status_val, "extracted": {k: v for k, v in extracted.items() if k != "readable"},
               "name_match": round(match, 2), "confidence": conf,
               "verified_at": now, "verified_by": current_user.get("email", "")}
        await db.id_verifications.update_one(
            {"booking_id": body.booking_id}, {"$set": doc}, upsert=True)
        return doc

    @router.get("/{booking_id}")
    async def get_status(booking_id: str,
                         current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        doc = await db.id_verifications.find_one({"booking_id": booking_id}, {"_id": 0})
        return doc or {"booking_id": booking_id, "status": "none"}

    return router
