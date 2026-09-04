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


def create_review_autopilot_router(db, require_roles, LlmChat, UserMessage, analyze=None):
    router = APIRouter()
    from routes.guests.reviews import (get_review_agent_cfg, decide_action, quality_score, similarity_score,
                                       log_review_event, heuristic_flags, compute_risk, privacy_check_db)

    async def _generate(review: dict, tone_desc: str, api_key: str, sign_off: str = "") -> str:
        sign = f"Sign off exactly as '{sign_off}' (a real authorised person/team)." if sign_off and sign_off != "Yönetim" else "Sign off as 'The Management Team'."
        system_msg = f"""You are a professional hotel manager responding to guest reviews.
Your responses should be {tone_desc}. Keep responses concise (2-3 paragraphs max).
Always thank the guest. If negative, acknowledge concerns and offer to make things right.
If positive, express gratitude and invite them back.
Detect the language of the review and respond in the SAME language.
Every response MUST be UNIQUE and PERSONALIZED — reference specific details from the review.
Never use generic openings. Never ask the guest to change the review or rating, never mention room numbers,
booking references or payment details, never promise refunds. {sign}"""
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
        """Intake → Analysis (risk/spam) → Response → Quality/Similarity → Decision → Publish/Draft/Escalate/Skip."""
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"ok": False, "error": "EMERGENT_LLM_KEY missing"}
        q: Dict = {"response_status": "pending"}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        from routes.platform_ext.automation_settings import get_params
        cfg = await get_params(db, "review_autopilot", {"max_per_run": MAX_PER_RUN})
        pending = await db.reviews.find(q, {"_id": 0}).sort("created_at", -1).to_list(int(cfg["max_per_run"]))
        published, drafted, escalated, skipped_spam, errors = 0, 0, 0, 0, 0
        now = datetime.now(timezone.utc).isoformat()
        prop_cfg_cache: Dict[str, dict] = {}
        for r in pending:
            pid = r.get("property_id", "default")
            pcfg = prop_cfg_cache.get(pid) or await get_review_agent_cfg(db, pid)
            prop_cfg_cache[pid] = pcfg
            rating = int(r.get("rating") or 3)
            text_in = r.get("review_text") or r.get("comment") or ""
            analysis = r.get("sentiment_analysis") or {}
            if "risk_score" not in analysis:
                if analyze:
                    try:
                        analysis = await analyze(text_in, rating)
                    except Exception as e:
                        logger.warning(f"autopilot analyze failed {r['id']}: {e}")
                if "risk_score" not in analysis:
                    analysis = {"sentiment": "positive" if rating >= 4 else "negative" if rating <= 2 else "neutral", **heuristic_flags(text_in, rating)}
                    analysis.update(compute_risk(analysis, rating))
                    analysis["spam_suspected"] = analysis["spam_probability"] >= 0.8
                await db.reviews.update_one({"id": r["id"]}, {"$set": {"sentiment_analysis": analysis}})
                await log_review_event(db, r["id"], "ai_analysed", "autopilot", risk=analysis.get("risk_level"), spam=analysis.get("spam_probability"))
            if analysis.get("spam_suspected"):
                await db.reviews.update_one({"id": r["id"]}, {"$set": {"response_status": "do_not_reply", "autopilot_skipped_at": now}})
                await log_review_event(db, r["id"], "skipped_spam", "autopilot", spam=analysis.get("spam_probability"))
                skipped_spam += 1
                continue
            positive = rating >= 4
            try:
                text = await _generate(r, "warm, friendly, and personable" if positive
                                       else "sincere, apologetic, and solution-focused", api_key, pcfg.get("sign_off", ""))
            except Exception as e:
                logger.warning(f"review autopilot generate failed {r['id']}: {e}")
                errors += 1
                continue
            recent = [x["response_text"] for x in await db.reviews.find(
                {"property_id": pid, "response_text": {"$nin": [None, ""]}, "id": {"$ne": r["id"]}},
                {"_id": 0, "response_text": 1}).sort("response_date", -1).limit(100).to_list(100)]
            sim = similarity_score(text, recent)
            qual = quality_score(text, r, analysis, sim["max_pct"])
            decision = decide_action(analysis, rating, qual["total"], sim["max_pct"], pcfg)
            pv = await privacy_check_db(db, text, pid)
            if not pv["ok"] and decision["action"] == "auto_approve":
                decision = {**decision, "action": "human_approval", "reasons": ["privacy: " + ", ".join(v["type"] for v in pv["violations"])]}
            base = {"response_text": text, "response_quality": qual, "response_similarity": sim, "ai_decision": decision, "response_privacy": pv,
                    "draft_generated_at": now, "regeneration_count": 1}
            await log_review_event(db, r["id"], "draft_generated", "autopilot", quality=qual["total"], similarity=sim["max_pct"], decision=decision["action"])
            if decision["action"] == "auto_approve":
                await db.reviews.update_one({"id": r["id"]}, {"$set": {**base,
                    "response_status": "responded", "response_date": now, "response_by": "AI Autopilot",
                    "response_method": "ai_autopilot", "responded": True, "auto_approved": True}})
                await log_review_event(db, r["id"], "auto_approved", "autopilot", mode=decision["mode"])
                await log_review_event(db, r["id"], "published", "autopilot", channel=r.get("platform"))
                published += 1
            else:
                esc = decision["action"] == "escalate"
                await db.reviews.update_one({"id": r["id"]}, {"$set": {**base,
                    "response_status": "pending_approval", "response_method": "ai_autopilot_draft",
                    "approve_token": secrets.token_urlsafe(20), "escalated": esc,
                    **({"escalation_level": decision.get("escalation_level", "management"), "escalated_by": "autopilot", "escalated_at": now} if esc else {})}})
                if esc:
                    await log_review_event(db, r["id"], "escalated", "autopilot", level=decision.get("escalation_level"), reasons=decision["reasons"])
                    await db.notifications.insert_one({
                        "id": str(uuid.uuid4()), "category": "review_escalation", "priority": "high",
                        "title": f"🔺 Kritik yorum eskalasyonu: {r.get('guest_name', '')} {rating}★ (risk {analysis.get('risk_score')})",
                        "message": f"Otomatik eskalasyon — {', '.join(decision['reasons'])}. \"{text_in[:140]}\"",
                        "property_id": pid, "review_id": r["id"], "read": False, "created_at": now})
                    escalated += 1
                else:
                    drafted += 1
        return {"ok": True, "scanned": len(pending), "published": published,
                "drafted_for_approval": drafted, "escalated": escalated, "skipped_spam": skipped_spam, "errors": errors}

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
