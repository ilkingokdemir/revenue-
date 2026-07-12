"""
Review Response Autopilot (iter 411) — daily AI responses to pending reviews:
positive (4-5★) are published directly; negative (≤3★) become drafts in the
existing approval queue (response_status: pending_approval).
"""
import os
import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

MAX_PER_RUN = 10


def create_review_autopilot_router(db, require_roles, LlmChat, UserMessage):
    router = APIRouter()

    async def _generate(review: dict, tone_desc: str, api_key: str) -> str:
        system_msg = f"""You are a professional hotel manager responding to guest reviews.
Your responses should be {tone_desc}. Keep responses concise (2-3 paragraphs max).
Always thank the guest. If negative, acknowledge concerns and offer to make things right.
If positive, express gratitude and invite them back.
Detect the language of the review and respond in the SAME language.
Every response MUST be UNIQUE and PERSONALIZED — reference specific details from the review.
Never use generic openings. Sign off as 'The Management Team'."""
        prompt = f"""Write a response to this hotel review:
Platform: {review.get('platform', 'Unknown')}
Rating: {review.get('rating', 3)}/5 stars
Guest: {review.get('guest_name', 'Guest')}
Review: {review.get('review_text', '')}"""
        chat = LlmChat(api_key=api_key,
                       session_id=f"review-autopilot-{review['id']}-{uuid.uuid4().hex[:6]}",
                       system_message=system_msg).with_model("openai", "gpt-5.2")
        return await chat.send_message(UserMessage(text=prompt))

    async def _autopilot_core(property_id: str = "") -> dict:
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"ok": False, "error": "EMERGENT_LLM_KEY missing"}
        q: Dict = {"response_status": "pending"}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        from routes.platform_ext.automation_settings import get_params
        cfg = await get_params(db, "review_autopilot", {"max_per_run": MAX_PER_RUN})
        pending = await db.reviews.find(q, {"_id": 0}).sort("created_at", -1).to_list(int(cfg["max_per_run"]))
        published, drafted, errors = 0, 0, 0
        now = datetime.now(timezone.utc).isoformat()
        for r in pending:
            rating = int(r.get("rating") or 3)
            positive = rating >= 4
            try:
                text = await _generate(
                    r, "warm, friendly, and personable" if positive
                    else "sincere, apologetic, and solution-focused", api_key)
            except Exception as e:
                logger.warning(f"review autopilot generate failed {r['id']}: {e}")
                errors += 1
                continue
            if positive:
                await db.reviews.update_one({"id": r["id"]}, {"$set": {
                    "response_text": text, "response_status": "responded",
                    "response_date": now, "response_by": "AI Autopilot",
                    "response_method": "ai_autopilot", "responded": True}})
                published += 1
            else:
                await db.reviews.update_one({"id": r["id"]}, {"$set": {
                    "response_text": text, "response_status": "pending_approval",
                    "draft_generated_at": now, "response_method": "ai_autopilot_draft",
                    "approve_token": secrets.token_urlsafe(20)}})
                drafted += 1
        return {"ok": True, "scanned": len(pending), "published": published,
                "drafted_for_approval": drafted, "errors": errors}

    @router.post("/reviews/autopilot/run")
    async def run_autopilot(data: Optional[Dict] = None,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _autopilot_core((data or {}).get("property_id", ""))

    @router.get("/reviews/autopilot/stats")
    async def stats(days: int = 30,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        published = await db.reviews.count_documents(
            {"response_method": "ai_autopilot", "response_date": {"$gte": since}})
        awaiting = await db.reviews.count_documents({"response_status": "pending_approval"})
        still_pending = await db.reviews.count_documents({"response_status": "pending"})
        return {"days": days, "auto_published": published,
                "awaiting_approval": awaiting, "still_pending": still_pending}

    @router.get("/public/review-approve/{token}")
    async def public_approve(token: str):
        def page(title, msg, color="#15803d"):
            return HTMLResponse(f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
            <body style="font-family:Arial,sans-serif;background:#f5f5f4;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;">
            <div style="background:#fff;border:1px solid #e7e5e4;border-radius:16px;padding:36px;max-width:440px;text-align:center;">
            <h2 style="color:{color};margin-top:0;">{title}</h2><p style="color:#57534e;font-size:14px;">{msg}</p>
            </div></body></html>""")
        r = await db.reviews.find_one({"approve_token": token}, {"_id": 0})
        if not r:
            return page("Bağlantı geçersiz", "Bu onay bağlantısı bulunamadı veya süresi dolmuş.", "#b91c1c")
        if r.get("response_status") == "responded":
            return page("Zaten yayınlandı ✓", "Bu yanıt daha önce onaylanıp yayınlanmıştı.")
        now = datetime.now(timezone.utc).isoformat()
        await db.reviews.update_one({"approve_token": token}, {"$set": {
            "response_status": "responded", "responded": True,
            "response_date": now, "response_by": "E-posta onayı",
            "response_method": "ai_autopilot_email_approved"}})
        return page("Yanıt yayınlandı ✓",
                    f"{r.get('guest_name', 'Misafir')} adlı misafirin {r.get('rating', '?')}★ yorumuna AI yanıtı onaylandı ve yayınlandı.")

    router.run_review_autopilot_internal = _autopilot_core
    return router
