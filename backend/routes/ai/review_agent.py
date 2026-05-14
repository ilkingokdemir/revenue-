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
    }

    async def _get_config(property_id: str) -> dict:
        cfg = await db.review_agent_config.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        if cfg:
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
                   "language", "require_review_before_publish"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
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
        for r in reviews:
            draft = await _generate_response(r, cfg)
            rating = int(r.get("rating") or 0)
            # auto-publish path
            should_auto = (
                cfg.get("auto_respond_enabled") and
                not cfg.get("require_review_before_publish", True) and
                cfg.get("min_rating_for_auto", 4) <= rating <=
                cfg.get("max_rating_for_auto", 5)
            )
            update = {
                "ai_draft": draft,
                "ai_draft_at": _now_iso(),
                "ai_draft_status": "published" if should_auto else "pending_review",
            }
            if should_auto:
                update.update({
                    "response_text": draft,
                    "responded_at": _now_iso(),
                    "responded_by": "ai_agent",
                    "ai_assisted": True,
                })
                auto_published += 1
            await db.reviews.update_one({"id": r["id"]}, {"$set": update})
            drafted.append({"review_id": r["id"], "rating": rating,
                            "auto_published": should_auto,
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
