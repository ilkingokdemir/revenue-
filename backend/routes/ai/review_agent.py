"""
AI Review Agent — Lighthouse 2026 parity.

Auto-drafts and (optionally) auto-publishes professional responses to
guest reviews using GPT-4o-mini. Operates on the existing `reviews`
collection. Per-property toggle: drafts vs auto-publish.

Endpoints
---------
  GET  /api/review-agent/config/{property_id}
  POST /api/review-agent/config/{property_id}   — set auto-respond + tone
  POST /api/review-agent/draft/{review_id}      — generate draft (manager/admin)
  POST /api/review-agent/publish/{review_id}    — accept & publish draft
  POST /api/review-agent/batch-draft/{property_id} — generate drafts for last N un-responded
  GET  /api/review-agent/queue/{property_id}    — pending review responses
"""
from datetime import datetime, timezone
import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from routes.guests.reviews import (DEFAULT_AUTO_RULES, PUBLISHING_MODES, get_review_agent_cfg, decide_action,
                                   quality_score, similarity_score, heuristic_flags, compute_risk, log_review_event, privacy_check_db)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_review_agent_router(db, require_roles):
    router = APIRouter()

    DEFAULT_CONFIG = {
        "auto_respond_enabled": False,
        "min_rating_for_auto": 4,         # only auto-publish 4+ stars
        "max_rating_for_auto": 5,
        "tone": "warm_professional",      # warm_professional | formal | friendly
        "sign_off": "Yönetim",
        "language": "tr",
        "require_review_before_publish": True,
        "publishing_mode": "smart_auto",   # manual | smart_auto | full_auto
        "auto_rules": dict(DEFAULT_AUTO_RULES),
    }

    async def _get_config(property_id: str) -> dict:
        cfg = await db.review_agent_config.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        if cfg:
            cfg.setdefault("publishing_mode", "smart_auto")
            cfg["auto_rules"] = {**DEFAULT_AUTO_RULES, **(cfg.get("auto_rules") or {})}
            return cfg
        # Lazy seed
        cfg = {"property_id": property_id, **DEFAULT_CONFIG,
               "created_at": _now_iso()}
        await db.review_agent_config.insert_one(cfg)
        cfg.pop("_id", None)
        return cfg

    async def _generate_response(review: dict, cfg: dict) -> str:
        """Use LLM to draft a response. Falls back to template on error."""
        rating = int(review.get("rating") or 0)
        text = (review.get("comment") or review.get("text") or "").strip()
        author = (review.get("author") or review.get("guest_name") or "Misafir").strip()
        tone = cfg.get("tone", "warm_professional")
        sign_off = cfg.get("sign_off", "Yönetim")
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            llm_key = os.environ.get("EMERGENT_LLM_KEY")
            if llm_key:
                tone_map = {
                    "warm_professional": "sıcak ve profesyonel",
                    "formal": "resmi ve saygılı",
                    "friendly": "samimi ve içten",
                }
                tone_str = tone_map.get(tone, "sıcak ve profesyonel")
                system_prompt = (
                    f"Sen otel yönetimi adına misafir yorumlarına yanıt yazan bir "
                    f"uzmansın. Türkçe, {tone_str} bir dille yaz. "
                    f"Olumlu yorumlarda teşekkür et ve geri davet et. "
                    f"Olumsuz yorumlarda özür dile, sorumluluğu üstlen, somut "
                    f"adımlardan bahset ve düzeltme fırsatı iste. "
                    f"Yanıtın 3-5 cümle olsun, klişe ifadelerden kaçın. "
                    f"Sonunda '— {sign_off}' yaz, başka imza ekleme."
                )
                client = LlmChat(
                    api_key=llm_key,
                    session_id=f"review-{review.get('id', 'x')}",
                    system_message=system_prompt,
                ).with_model("openai", "gpt-4o-mini")
                user_msg = UserMessage(text=(
                    f"Misafir: {author}\nPuan: {rating}/5\nYorum: {text}\n\n"
                    f"Bu yoruma profesyonel bir yanıt yaz."
                ))
                return await client.send_message(user_msg)
        except Exception as e:
            logger.warning(f"review-agent LLM failed, falling back: {e}")
        # Template fallback
        if rating >= 4:
            return (f"Sayın {author}, değerli yorumunuz için çok teşekkür ederiz. "
                    f"Sizi tekrar ağırlamaktan büyük mutluluk duyacağız.\n— {sign_off}")
        elif rating >= 3:
            return (f"Sayın {author}, yorumunuz için teşekkürler. Geri bildiriminizi "
                    f"ekibimizle paylaşıp gelişim alanlarımız üzerinde çalışacağız.\n— {sign_off}")
        else:
            return (f"Sayın {author}, yaşadıklarınız için içtenlikle özür dileriz. "
                    f"Bu yorum doğrudan yönetimin masasına geldi ve gereken aksiyon "
                    f"alınacaktır. Bir sonraki konaklamanızda gönülden ağırlamak için "
                    f"sizinle iletişime geçmemize izin verir misiniz?\n— {sign_off}")

    # =========== Config ===========
    @router.get("/review-agent/config/{property_id}")
    async def get_config(property_id: str,
                         _: dict = Depends(require_roles("admin", "manager"))):
        return await _get_config(property_id)

    @router.post("/review-agent/config/{property_id}")
    async def set_config(property_id: str, body: dict,
                         _: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"auto_respond_enabled", "min_rating_for_auto",
                   "max_rating_for_auto", "tone", "sign_off",
                   "language", "require_review_before_publish",
                   "publishing_mode", "auto_rules", "full_auto_authorised_by", "show_team_star"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
        if "publishing_mode" in update:
            if update["publishing_mode"] not in PUBLISHING_MODES:
                raise HTTPException(400, "publishing_mode: manual | smart_auto | full_auto")
            if update["publishing_mode"] == "full_auto" and not (update.get("full_auto_authorised_by") or body.get("full_auto_authorised_by")):
                raise HTTPException(400, "Full Auto için işletme yetkilendirmesi gerekir (full_auto_authorised_by)")
        if "auto_rules" in update:
            update["auto_rules"] = {**DEFAULT_AUTO_RULES, **{k: v for k, v in (update["auto_rules"] or {}).items() if k in DEFAULT_AUTO_RULES}}
        update["updated_at"] = _now_iso()
        await db.review_agent_config.update_one(
            {"property_id": property_id},
            {"$set": update},
            upsert=True
        )
        return await _get_config(property_id)

    # =========== Single draft ===========
    @router.post("/review-agent/draft/{review_id}")
    async def draft_response(review_id: str,
                             _: dict = Depends(require_roles("admin", "manager"))):
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(404, "Review not found")
        cfg = await _get_config(review.get("property_id", ""))
        draft = await _generate_response(review, cfg)
        await db.reviews.update_one(
            {"id": review_id},
            {"$set": {
                "ai_draft": draft,
                "ai_draft_at": _now_iso(),
                "ai_draft_status": "pending_review",
            }}
        )
        return {"review_id": review_id, "draft": draft,
                "status": "pending_review"}

    @router.post("/review-agent/publish/{review_id}")
    async def publish_response(review_id: str, body: dict = None,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        body = body or {}
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(404, "Review not found")
        text = (body.get("response_text") or review.get("ai_draft") or "").strip()
        if not text:
            raise HTTPException(400, "No draft or response_text provided")
        pv = await privacy_check_db(db, text, review.get("property_id", ""))
        if not pv["ok"]:
            await log_review_event(db, review_id, "publish_blocked_privacy", current_user.get("name", ""), violations=[v["type"] for v in pv["violations"]])
            raise HTTPException(400, "Gizlilik ihlali — yayın engellendi: " + ", ".join(v["type"] for v in pv["violations"]))
        await db.reviews.update_one(
            {"id": review_id},
            {"$set": {
                "response_text": text,
                "responded_at": _now_iso(),
                "responded_by": current_user.get("name", ""),
                "ai_draft_status": "published",
                "ai_assisted": True,
            }}
        )
        return {"ok": True, "review_id": review_id,
                "response_text": text}

    # =========== Batch draft ===========
    @router.post("/review-agent/batch-draft/{property_id}")
    async def batch_draft(property_id: str, body: dict = None,
                          _: dict = Depends(require_roles("admin", "manager"))):
        body = body or {}
        limit = int(body.get("limit", 25))
        cfg = await _get_config(property_id)
        # Only un-responded reviews
        q = {"property_id": property_id,
             "$or": [{"response_text": {"$exists": False}},
                     {"response_text": ""}]}
        reviews = await db.reviews.find(q, {"_id": 0}).sort(
            "created_at", -1
        ).to_list(limit)
        drafted = []
        auto_published = 0
        recent = [x["response_text"] for x in await db.reviews.find(
            {"property_id": property_id, "response_text": {"$nin": [None, ""]}},
            {"_id": 0, "response_text": 1}).sort("response_date", -1).limit(100).to_list(100)]
        for r in reviews:
            draft = await _generate_response(r, cfg)
            rating = int(r.get("rating") or 0)
            analysis = r.get("sentiment_analysis") or {}
            if "risk_score" not in analysis:
                analysis = {**analysis, **heuristic_flags(r.get("review_text") or r.get("comment") or "", rating)}
                analysis.update(compute_risk(analysis, rating))
                analysis["spam_suspected"] = analysis["spam_probability"] >= 0.8
            sim = similarity_score(draft, recent)
            qual = quality_score(draft, r, analysis, sim["max_pct"])
            decision = decide_action(analysis, rating, qual["total"], sim["max_pct"], cfg)
            # legacy toggles still honoured: auto only if enabled AND no human-review flag AND decision says auto
            pv = await privacy_check_db(db, draft, property_id)
            should_auto = bool(
                pv["ok"] and
                cfg.get("auto_respond_enabled") and
                not cfg.get("require_review_before_publish", True) and
                cfg.get("min_rating_for_auto", 4) <= rating <= cfg.get("max_rating_for_auto", 5) and
                decision["action"] == "auto_approve"
            )
            update = {
                "ai_draft": draft,
                "ai_draft_at": _now_iso(),
                "ai_draft_status": "published" if should_auto else "pending_review",
                "sentiment_analysis": analysis, "response_quality": qual,
                "response_similarity": sim, "ai_decision": decision, "response_privacy": pv,
            }
            await log_review_event(db, r["id"], "draft_generated", "review-agent", quality=qual["total"],
                                   similarity=sim["max_pct"], decision=decision["action"])
            if should_auto:
                update.update({
                    "response_text": draft,
                    "responded_at": _now_iso(),
                    "responded_by": "ai_agent", "response_method": "ai_agent_auto",
                    "response_status": "responded", "responded": True,
                    "ai_assisted": True,
                })
                auto_published += 1
                recent.insert(0, draft)
            await db.reviews.update_one({"id": r["id"]}, {"$set": update})
            if should_auto:
                await log_review_event(db, r["id"], "auto_approved", "review-agent", mode=decision["mode"])
                await log_review_event(db, r["id"], "published", "review-agent", channel=r.get("platform"))
            drafted.append({"review_id": r["id"], "rating": rating,
                            "auto_published": should_auto, "decision": decision["action"],
                            "reasons": decision["reasons"], "quality": qual["total"],
                            "risk": analysis.get("risk_level"), "similarity": sim["max_pct"],
                            "draft_preview": draft[:120]})
        return {
            "property_id": property_id,
            "drafted_count": len(drafted),
            "auto_published_count": auto_published,
            "items": drafted,
        }

    @router.get("/review-agent/queue/{property_id}")
    async def get_queue(property_id: str, limit: int = 50,
                        _: dict = Depends(require_roles("admin", "manager"))):
        items = await db.reviews.find(
            {"property_id": property_id,
             "ai_draft_status": "pending_review"},
            {"_id": 0}
        ).sort("ai_draft_at", -1).to_list(min(limit, 200))
        return {"items": items, "count": len(items)}

    return router
