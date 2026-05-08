"""
Review Management Routes: Widget API, Approval Workflow, Reviews CRUD,
Notification Settings, Response Templates, Sentiment/Analytics, Competitors
Extracted from server.py for maintainability
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import List, Dict, Optional
import os
import uuid
import asyncio
import logging

from routes.helpers import serialize_review, deserialize_review, log_sync, fire_webhooks

logger = logging.getLogger(__name__)


def create_reviews_router(db, require_roles, get_current_user, verify_api_key, LlmChat, UserMessage, resend):
    """Factory function that creates review routes with injected dependencies"""
    from models import (
        Review, ReviewCreate, ReviewResponse, AIGenerateRequest, AIGenerateResponse,
        NotificationSettings, NotificationSettingsUpdate,
        ResponseTemplate, ResponseTemplateCreate, ResponseTemplateUpdate,
        SentimentAnalysis, CompetitorData, CompetitorCreate, CompetitorUpdate,
        ApprovalAction, StatusCheck, StatusCheckCreate,
    )
    router = APIRouter()
    SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
    NOTIFICATION_EMAIL = os.environ.get('NOTIFICATION_EMAIL', '')

    async def analyze_sentiment(review_text: str, rating: int) -> dict:
        """Analyze sentiment of a review using GPT-5.2"""
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"sentiment": "neutral" if rating >= 3 else "negative", "key_phrases": [], "topics": []}
        try:
            chat = LlmChat(api_key=api_key, session_id=f"sentiment-{uuid.uuid4()}", system_message="Analyze hotel review sentiment. Return JSON only.").with_model("openai", "gpt-5.2")
            prompt = f"""Analyze this hotel review. Return ONLY a JSON object:
{{"sentiment": "positive|negative|neutral|mixed", "key_phrases": ["phrase1", "phrase2"], "topics": ["topic1"], "emotion": "happy|frustrated|disappointed|grateful|neutral", "urgency": "low|medium|high"}}
Rating: {rating}/5
Review: {review_text[:500]}"""
            reply = await chat.send_message(UserMessage(text=prompt))
            import json
            cleaned = reply.strip().strip("```json").strip("```").strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {"sentiment": "positive" if rating >= 4 else ("neutral" if rating >= 3 else "negative"), "key_phrases": [], "topics": []}

    # ==================== WIDGET API (API Key Auth) ====================

    @router.get("/widget/reviews")
    async def widget_get_reviews(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Get reviews for widget display (authenticated via API key)"""
        property_id = request.query_params.get("property_id", "default")
        platform = request.query_params.get("platform")
        status = request.query_params.get("status")
        limit = min(int(request.query_params.get("limit", "20")), 50)

        query = {"property_id": property_id}
        if platform:
            query["platform"] = platform
        if status:
            query["response_status"] = status

        reviews = await db.reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
        return reviews

    @router.get("/widget/reviews/new")
    async def widget_new_reviews(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Get reviews created after a given timestamp (for polling)"""
        property_id = request.query_params.get("property_id", "default")
        since = request.query_params.get("since")
        if not since:
            return []
        query = {"property_id": property_id, "created_at": {"$gt": since}}
        reviews = await db.reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(10)
        return reviews

    @router.get("/widget/stats")
    async def widget_get_stats(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Get review stats for widget display"""
        property_id = request.query_params.get("property_id", "default")
        query = {"property_id": property_id}

        total = await db.reviews.count_documents(query)
        responded = await db.reviews.count_documents({**query, "response_status": "responded"})
        pending = await db.reviews.count_documents({**query, "response_status": {"$in": ["pending", "draft"]}})

        pipeline = [{"$match": query}, {"$group": {"_id": None, "avg": {"$avg": "$rating"}}}]
        avg_result = await db.reviews.aggregate(pipeline).to_list(1)
        avg_rating = round(avg_result[0]["avg"], 1) if avg_result else 0

        return {
            "total_reviews": total,
            "average_rating": avg_rating,
            "response_rate": round((responded / total) * 100, 1) if total > 0 else 0,
            "responded": responded,
            "pending": pending
        }

    @router.get("/widget/unread-count")
    async def widget_unread_count(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Get count of unread reviews"""
        property_id = request.query_params.get("property_id", "default")
        count = await db.reviews.count_documents({"property_id": property_id, "is_read": {"$ne": True}})
        return {"unread": count}

    @router.put("/widget/reviews/{review_id}/read")
    async def widget_mark_read(review_id: str, key_doc: dict = Depends(verify_api_key)):
        """Mark a review as read"""
        result = await db.reviews.update_one({"id": review_id}, {"$set": {"is_read": True}})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Review not found")
        return {"ok": True}

    @router.put("/widget/reviews/mark-all-read")
    async def widget_mark_all_read(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Mark all reviews as read for a property"""
        property_id = request.query_params.get("property_id", "default")
        result = await db.reviews.update_many(
            {"property_id": property_id, "is_read": {"$ne": True}},
            {"$set": {"is_read": True}}
        )
        return {"marked": result.modified_count}

    @router.post("/widget/generate-response")
    async def widget_generate_response(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Generate AI response from widget"""
        body = await request.json()
        review_id = body.get("review_id")
        language = body.get("language", "en")
        tone = body.get("tone", "professional")

        if not review_id:
            raise HTTPException(status_code=400, detail="review_id required")

        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        prompt = f"""Generate a {tone} hotel review response in {language}.
    Guest: {review.get('guest_name', 'Guest')}
    Rating: {review.get('rating', 'N/A')}/5
    Platform: {review.get('platform', 'unknown')}
    Review: {review.get('review_text', '')}
    Keep it unique, warm, and under 150 words."""

        try:
            chat = LlmChat(api_key=api_key, session_id=f"widget-{uuid.uuid4()}", system_message="You are a hotel review response assistant.").with_model("openai", "gpt-5.2")
            response = await chat.send_message(UserMessage(text=prompt))
            response_text = response.strip()

            await db.reviews.update_one({"id": review_id}, {"$set": {
                "response_text": response_text,
                "response_status": "draft",
                "response_language": language,
                "response_generated_at": datetime.now(timezone.utc).isoformat()
            }})

            return {"response_text": response_text, "review_id": review_id, "status": "draft"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)[:100]}")

    # ==================== APPROVAL WORKFLOW ROUTES ====================

    @router.post("/reviews/{review_id}/submit-for-approval")
    async def submit_for_approval(review_id: str, request: Request):
        current_user = await get_current_user(request)
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        if not review.get("response_text"):
            raise HTTPException(status_code=400, detail="No response text to submit")
        await db.reviews.update_one({"id": review_id}, {"$set": {
            "response_status": "pending_approval",
            "drafted_by": current_user.get("name", current_user.get("email")),
        }})
        return {"message": "Submitted for approval", "status": "pending_approval"}

    @router.post("/reviews/{review_id}/approve")
    async def approve_response(review_id: str, action: ApprovalAction, request: Request):
        current_user = await get_current_user(request)
        if current_user["role"] not in ["admin", "manager"]:
            raise HTTPException(status_code=403, detail="Only managers and admins can approve")
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        if action.action == "approve":
            await db.reviews.update_one({"id": review_id}, {"$set": {
                "response_status": "responded",
                "approved_by": current_user.get("name", current_user.get("email")),
                "approval_notes": action.notes,
                "response_date": datetime.now(timezone.utc).isoformat()
            }})
            return {"message": "Response approved and published", "status": "responded"}
        elif action.action == "reject":
            await db.reviews.update_one({"id": review_id}, {"$set": {
                "response_status": "rejected",
                "approved_by": current_user.get("name", current_user.get("email")),
                "approval_notes": action.notes
            }})
            return {"message": "Response rejected", "status": "rejected"}
        else:
            raise HTTPException(status_code=400, detail="Invalid action")

    @router.get("/reviews/pending-approval")
    async def get_pending_approvals(request: Request):
        current_user = await get_current_user(request)
        if current_user["role"] not in ["admin", "manager"]:
            raise HTTPException(status_code=403, detail="Only managers and admins can view approval queue")
        reviews = await db.reviews.find({"response_status": "pending_approval"}, {"_id": 0}).to_list(100)
        return [serialize_review(r) for r in reviews]

    async def analyze_sentiment(review_text: str, rating: int) -> dict:
        """Analyze sentiment of a review using GPT-5.2"""
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            # Return basic analysis based on rating if no API key
            sentiment = "positive" if rating >= 4 else "negative" if rating <= 2 else "neutral"
            return {
                "sentiment": sentiment,
                "score": (rating - 3) / 2,  # -1 to 1 scale
                "urgency": "critical" if rating == 1 else "high" if rating == 2 else "low",
                "topics": [],
                "suggested_tone": "apologetic" if rating <= 2 else "friendly" if rating >= 4 else "professional",
                "suggested_category": "negative" if rating <= 2 else "positive" if rating >= 4 else "neutral",
                "key_issues": [],
                "key_praises": []
            }

        system_message = """You are a hotel review sentiment analyzer. Analyze the given review and return a JSON object with:
    - sentiment: "positive", "negative", "neutral", or "mixed"
    - score: float from -1 (very negative) to 1 (very positive)
    - urgency: "low", "medium", "high", or "critical" (critical for reviews mentioning health/safety/legal issues)
    - topics: array of topics mentioned (cleanliness, staff, amenities, location, value, food, noise, parking, wifi, bathroom, bed, check-in, check-out, etc.)
    - suggested_tone: "professional", "friendly", or "apologetic" based on what response tone would work best
    - suggested_category: "positive", "negative", "neutral", "complaint", or "praise" for template matching
    - key_issues: array of specific problems mentioned
    - key_praises: array of specific compliments mentioned

    Return ONLY valid JSON, no other text."""

        prompt = f"""Analyze this hotel review (rated {rating}/5 stars):

    "{review_text}"

    Return the sentiment analysis as JSON."""

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"sentiment-{uuid.uuid4()}",
                system_message=system_message
            ).with_model("openai", "gpt-5.2")

            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)

            # Parse JSON from response
            import json
            # Clean response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()

            result = json.loads(cleaned)
            return result
        except Exception as e:
            logger.error(f"Sentiment analysis error: {str(e)}")
            # Fallback to basic analysis
            sentiment = "positive" if rating >= 4 else "negative" if rating <= 2 else "neutral"
            return {
                "sentiment": sentiment,
                "score": (rating - 3) / 2,
                "urgency": "critical" if rating == 1 else "high" if rating == 2 else "low",
                "topics": [],
                "suggested_tone": "apologetic" if rating <= 2 else "friendly" if rating >= 4 else "professional",
                "suggested_category": "negative" if rating <= 2 else "positive" if rating >= 4 else "neutral",
                "key_issues": [],
                "key_praises": []
            }

    async def send_negative_review_notification(review: dict):
        """Send email notification for negative reviews (1-2 stars)"""
        settings = await db.notification_settings.find_one({}, {"_id": 0})

        if not settings or not settings.get('enabled', False):
            logger.info("Notifications disabled or not configured")
            return False

        if review.get('rating', 5) > settings.get('negative_threshold', 2):
            logger.info(f"Review rating {review.get('rating')} above threshold, skipping notification")
            return False

        notification_email = settings.get('email', NOTIFICATION_EMAIL)
        if not notification_email:
            logger.warning("No notification email configured")
            return False

        if not resend.api_key or resend.api_key == 're_123456789':
            logger.warning("Resend API key not configured - notification logged but not sent")
            # Log the notification for demo purposes
            await db.notification_log.insert_one({
                "id": str(uuid.uuid4()),
                "review_id": review.get('id'),
                "email": notification_email,
                "status": "demo_logged",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            return True

        platform_names = {
            "booking.com": "Booking.com",
            "airbnb": "Airbnb",
            "expedia": "Expedia",
            "tripadvisor": "TripAdvisor",
            "google": "Google",
            "trip.com": "Trip.com"
        }

        platform = platform_names.get(review.get('platform', ''), review.get('platform', 'Unknown'))
        rating_stars = '★' * review.get('rating', 1) + '☆' * (5 - review.get('rating', 1))

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #C05A44; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0; font-size: 24px;">⚠️ Negative Review Alert</h1>
            </div>
            <div style="background-color: #FAF9F6; padding: 20px; border: 1px solid #E7E5E4; border-top: none; border-radius: 0 0 8px 8px;">
                <p style="color: #57534E; margin-bottom: 20px;">A new negative review requires your attention:</p>

                <div style="background-color: white; border: 1px solid #E7E5E4; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                        <span style="background-color: #3E5245; color: white; padding: 4px 12px; border-radius: 4px; font-size: 12px;">{platform}</span>
                        <span style="color: #D4A373; font-size: 18px;">{rating_stars}</span>
                    </div>
                    <p style="font-weight: bold; color: #1C1917; margin-bottom: 5px;">{review.get('guest_name', 'Guest')}</p>
                    <p style="color: #57534E; font-size: 14px; margin-bottom: 15px;">
                        {review.get('room_type', '')} • {review.get('stay_date', '')}
                    </p>
                    <p style="color: #1C1917; line-height: 1.6; background-color: #FAF9F6; padding: 15px; border-radius: 4px;">
                        "{review.get('review_text', '')}"
                    </p>
                </div>

                <p style="color: #57534E; font-size: 14px;">
                    Quick response to negative reviews can help protect your hotel's reputation. 
                    Log in to Review Hub to craft a thoughtful response.
                </p>

                <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #E7E5E4; color: #57534E; font-size: 12px;">
                    This is an automated notification from Review Hub.
                </div>
            </div>
        </div>
        """

        try:
            params = {
                "from": SENDER_EMAIL,
                "to": [notification_email],
                "subject": f"⚠️ Negative Review Alert: {review.get('rating')}/5 on {platform}",
                "html": html_content
            }

            email_result = await asyncio.to_thread(resend.Emails.send, params)

            # Log successful notification
            await db.notification_log.insert_one({
                "id": str(uuid.uuid4()),
                "review_id": review.get('id'),
                "email": notification_email,
                "email_id": email_result.get('id'),
                "status": "sent",
                "created_at": datetime.now(timezone.utc).isoformat()
            })

            logger.info(f"Negative review notification sent to {notification_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            await db.notification_log.insert_one({
                "id": str(uuid.uuid4()),
                "review_id": review.get('id'),
                "email": notification_email,
                "status": "failed",
                "error": str(e),
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            return False

    # ==================== ROUTES ====================

    @router.get("/")
    async def root():
        return {"message": "Hotel Review Management API"}

    @router.post("/status", response_model=StatusCheck)
    async def create_status_check(input: StatusCheckCreate):
        status_dict = input.model_dump()
        status_obj = StatusCheck(**status_dict)
        doc = status_obj.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        _ = await db.status_checks.insert_one(doc)
        return status_obj

    @router.get("/status", response_model=List[StatusCheck])
    async def get_status_checks():
        status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
        for check in status_checks:
            if isinstance(check['timestamp'], str):
                check['timestamp'] = datetime.fromisoformat(check['timestamp'])
        return status_checks

    # ==================== REVIEW ROUTES ====================

    @router.get("/reviews", response_model=List[Review])
    async def get_reviews(
        property_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        rating: Optional[int] = None
    ):
        """Get all reviews with optional filters"""
        query = {}
        if property_id:
            query["property_id"] = property_id
        if platform and platform != "all":
            query["platform"] = platform
        if status and status != "all":
            query["response_status"] = status
        if rating:
            query["rating"] = rating

        reviews = await db.reviews.find(query, {"_id": 0}).sort("review_date", -1).to_list(1000)
        for review in reviews:
            deserialize_review(review)
        return reviews

    @router.get("/reviews/{review_id}", response_model=Review)
    async def get_review(review_id: str):
        """Get a single review by ID"""
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        deserialize_review(review)
        return review

    @router.post("/reviews", response_model=Review)
    async def create_review(input: ReviewCreate):
        """Create a new review"""
        review = Review(**input.model_dump())
        doc = review.model_dump()
        doc = serialize_review(doc)
        await db.reviews.insert_one(doc)

        # Trigger notification for negative reviews (1-2 stars)
        if input.rating <= 2:
            await send_negative_review_notification(doc)

        return review

    @router.put("/reviews/{review_id}/respond", response_model=Review)
    async def respond_to_review(review_id: str, response: ReviewResponse):
        """Submit a response to a review"""
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        update_data = {
            "response_text": response.response_text,
            "response_status": "responded",
            "response_date": datetime.now(timezone.utc).isoformat()
        }

        await db.reviews.update_one(
            {"id": review_id},
            {"$set": update_data}
        )

        # Attempt outbound platform sync in the background
        platform = review.get("platform")
        if platform and review.get("external_review_id"):
            asyncio.create_task(_attempt_outbound_sync(platform, review_id, review.get("external_review_id"), response.response_text))

        updated_review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        deserialize_review(updated_review)
        return updated_review

    async def _attempt_outbound_sync(platform: str, review_id: str, external_review_id: str, reply_text: str):
        """Attempt to post a reply back to the originating platform"""
        try:
            integration = await db.platform_integrations.find_one({"platform": platform}, {"_id": 0})
            if not integration or not integration.get("credentials_configured"):
                await log_sync(db, platform, "outbound", "skipped", f"No credentials configured for {platform}. Configure in Connections > Setup Wizard.", review_id)
                return

            success = False
            error_msg = ""

            if platform == "google":
                # Google Business Profile API - Reply to review
                access_token = integration.get("access_token", "")
                account_id = integration.get("account_id", "")
                location_id = integration.get("location_id", "")
                if access_token and account_id and location_id:
                    try:
                        import httpx
                        url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/reviews/{external_review_id}/reply"
                        async with httpx.AsyncClient() as client:
                            resp = await client.put(url,
                                json={"comment": reply_text},
                                headers={"Authorization": f"Bearer {access_token}"},
                                timeout=15)
                            if resp.status_code in (200, 201):
                                success = True
                            else:
                                error_msg = f"Google API {resp.status_code}: {resp.text[:150]}"
                    except Exception as e:
                        error_msg = str(e)[:200]
                else:
                    error_msg = "Missing Google credentials (access_token, account_id, location_id)"

            elif platform == "booking.com":
                # Booking.com Connectivity API
                api_key = integration.get("api_key", "")
                hotel_id = integration.get("hotel_id", "")
                if api_key and hotel_id:
                    try:
                        import httpx
                        url = f"https://supply-xml.booking.com/hotels/xml/reviews"
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(url,
                                json={"hotel_id": hotel_id, "review_id": external_review_id, "response": reply_text},
                                headers={"Authorization": f"Basic {api_key}"},
                                timeout=15)
                            if resp.status_code in (200, 201):
                                success = True
                            else:
                                error_msg = f"Booking.com API {resp.status_code}: {resp.text[:150]}"
                    except Exception as e:
                        error_msg = str(e)[:200]
                else:
                    error_msg = "Missing Booking.com credentials (api_key, hotel_id)"

            elif platform == "tripadvisor":
                # TripAdvisor Management Center API
                api_key = integration.get("api_key", "")
                location_id = integration.get("location_id", "")
                if api_key and location_id:
                    try:
                        import httpx
                        url = f"https://api.tripadvisor.com/api/partner/3.0/location/{location_id}/reviews/{external_review_id}/response"
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(url,
                                json={"response_text": reply_text},
                                headers={"x-tripadvisor-api-key": api_key},
                                timeout=15)
                            if resp.status_code in (200, 201):
                                success = True
                            else:
                                error_msg = f"TripAdvisor API {resp.status_code}: {resp.text[:150]}"
                    except Exception as e:
                        error_msg = str(e)[:200]
                else:
                    error_msg = "Missing TripAdvisor credentials (api_key, location_id)"

            else:
                error_msg = f"Outbound reply not yet supported for {platform}"

            if success:
                await db.reviews.update_one({"id": review_id}, {"$set": {
                    "synced_to_platform": True,
                    "sync_date": datetime.now(timezone.utc).isoformat(),
                    "sync_status": "synced",
                }})
                await log_sync(db, platform, "outbound", "success", f"Reply posted to {platform} for review {external_review_id}", review_id)
            else:
                await db.reviews.update_one({"id": review_id}, {"$set": {
                    "synced_to_platform": False,
                    "sync_status": "failed",
                    "sync_error": error_msg,
                }})
                await log_sync(db, platform, "outbound", "warning", f"Reply sync to {platform} failed: {error_msg}", review_id)
        except Exception as e:
            logger.error(f"Outbound sync error for {platform}: {e}")
            await log_sync(db, platform, "outbound", "error", str(e)[:200], review_id)

    SUPPORTED_LANGUAGES = {
        "auto": "Auto-detect",
        "en": "English",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "ar": "Arabic",
        "ru": "Russian",
        "nl": "Dutch",
        "th": "Thai",
        "hi": "Hindi",
        "tr": "Turkish"
    }

    @router.post("/reviews/generate-ai-response", response_model=AIGenerateResponse)
    async def generate_ai_response(request: AIGenerateRequest):
        """Generate AI response for a review using GPT-5.2 with multi-language support and uniqueness"""
        review = await db.reviews.find_one({"id": request.review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        tone_instructions = {
            "professional": "professional, courteous, and business-like",
            "friendly": "warm, friendly, and personable",
            "apologetic": "sincere, apologetic, and solution-focused"
        }

        tone = tone_instructions.get(request.tone, tone_instructions["professional"])

        # Language handling
        lang = request.language
        language_instruction = ""
        if lang == "auto":
            language_instruction = """First, detect the language of the guest's review.
    Then write your entire response in that SAME language the guest used.
    If the review is in English, respond in English. If in French, respond in French. Etc."""
        elif lang == "en":
            language_instruction = "Write your response entirely in English."
        else:
            lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
            language_instruction = f"Write your entire response in {lang_name}."

        # Fetch recent responses for uniqueness context
        recent_responses = await db.reviews.find(
            {"response_text": {"$ne": None}, "id": {"$ne": request.review_id}},
            {"response_text": 1, "_id": 0}
        ).sort("response_date", -1).limit(5).to_list(5)
        recent_texts = [r["response_text"] for r in recent_responses if r.get("response_text")]

        avoid_phrases = ""
        if recent_texts:
            avoid_phrases = "\n\nIMPORTANT: Make this response COMPLETELY UNIQUE. Do NOT reuse any of these opening lines or phrases from recent responses:\n"
            for i, text in enumerate(recent_texts[:3]):
                first_line = text.split('.')[0] if '.' in text else text[:80]
                avoid_phrases += f"- Avoid: \"{first_line}...\"\n"
            avoid_phrases += "Use a fresh, creative opening. Vary your sentence structure. Reference specific details from the guest's review."

        # Unique session ID each time to prevent caching
        unique_session = f"review-{request.review_id}-{lang}-{uuid.uuid4().hex[:8]}"

        system_message = f"""You are a professional hotel manager responding to guest reviews. 
    Your responses should be {tone}.
    Keep responses concise (2-3 paragraphs max).
    Always thank the guest for their feedback.
    If the review is negative, acknowledge their concerns and offer to make things right.
    If positive, express gratitude and invite them back.
    {language_instruction}

    CRITICAL: Every response must be UNIQUE and PERSONALIZED. 
    - Reference SPECIFIC details from the review (room type, dates, specific experiences mentioned).
    - Vary your opening line, sentence structure, and sign-off every time.
    - Never use generic phrases like "Thank you for your feedback" as an opener.
    - Be creative and genuine — guests can tell when responses are automated.
    Sign off creatively as 'The Management Team' or similar.{avoid_phrases}"""

        prompt = f"""Please write a response to this hotel review:

    Platform: {review['platform']}
    Rating: {review['rating']}/5 stars
    Guest: {review['guest_name']}
    Review: {review['review_text']}
    {f"Room: {review.get('room_type', '')}" if review.get('room_type') else ""}
    {f"Stay Date: {review.get('stay_date', '')}" if review.get('stay_date') else ""}

    Write a {tone}, UNIQUE and personalized response. {language_instruction}"""

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=unique_session,
                system_message=system_message
            ).with_model("openai", "gpt-5.2")

            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)

            # Store uniqueness hash
            import hashlib
            uniqueness_hash = hashlib.md5(response.encode()).hexdigest()[:12]

            return AIGenerateResponse(generated_text=response, detected_language=lang if lang != "auto" else None)
        except Exception as e:
            logger.error(f"AI generation error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    @router.post("/reviews/{review_id}/detect-language")
    async def detect_language(review_id: str):
        """Detect the language of a review using AI"""
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"lang-detect-{review_id}",
                system_message="You are a language detection assistant. Respond ONLY with a JSON object."
            ).with_model("openai", "gpt-5.2")

            prompt = f"""Detect the language of this text and respond ONLY with a JSON object in this exact format:
    {{"code": "en", "name": "English", "confidence": 0.95}}

    Use ISO 639-1 codes. Text:
    "{review['review_text']}" """

            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)

            import json as json_module
            # Parse the response - handle potential markdown wrapping
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            result = json_module.loads(clean)
            return {
                "code": result.get("code", "en"),
                "name": result.get("name", "English"),
                "confidence": result.get("confidence", 0.9)
            }
        except Exception as e:
            logger.error(f"Language detection error: {str(e)}")
            return {"code": "en", "name": "English", "confidence": 0.5}

    class TranslateRequest(BaseModel):
        text: str
        target_language: str = "en"

    @router.post("/reviews/translate")
    async def translate_text(request: TranslateRequest):
        """Translate text to a target language"""
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        target_name = SUPPORTED_LANGUAGES.get(request.target_language, "English")

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"translate-{request.target_language}",
                system_message=f"You are a professional translator. Translate the given text to {target_name}. Return ONLY the translated text, nothing else."
            ).with_model("openai", "gpt-5.2")

            user_message = UserMessage(text=f"Translate this to {target_name}:\n\n{request.text}")
            response = await chat.send_message(user_message)

            return {"translated_text": response, "target_language": request.target_language, "target_name": target_name}
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

    @router.post("/reviews/batch-auto-respond")
    async def batch_auto_respond(data: Dict = {},
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Batch auto-respond to all unresponded reviews using AI."""
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        tone = data.get("tone", "professional")
        limit = min(int(data.get("limit", 10)), 20)
        property_id = data.get("property_id")

        query = {"response_status": "pending"}
        if property_id:
            query["property_id"] = property_id

        unresponded = await db.reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
        if not unresponded:
            return {"processed": 0, "message": "No unresponded reviews found"}

        tone_map = {
            "professional": "professional, courteous, and business-like",
            "friendly": "warm, friendly, and personable",
            "apologetic": "sincere, apologetic, and solution-focused",
        }
        tone_desc = tone_map.get(tone, tone_map["professional"])

        results = []
        processed = 0
        errors = []

        for review in unresponded:
            try:
                unique_session = f"batch-{review['id']}-{uuid.uuid4().hex[:8]}"
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
Review: {review.get('review_text', '')}
{f"Room: {review.get('room_type', '')}" if review.get('room_type') else ""}
{f"Stay: {review.get('stay_date', '')}" if review.get('stay_date') else ""}"""

                chat = LlmChat(api_key=api_key, session_id=unique_session, system_message=system_msg).with_model("openai", "gpt-5.2")
                response_text = await chat.send_message(UserMessage(text=prompt))

                now_iso = datetime.now(timezone.utc).isoformat()
                await db.reviews.update_one({"id": review["id"]}, {"$set": {
                    "response_text": response_text,
                    "response_status": "responded",
                    "response_date": now_iso,
                    "response_by": current_user.get("name", "AI Auto-Respond"),
                    "response_method": "ai_batch",
                    "response_tone": tone,
                }})

                results.append({
                    "review_id": review["id"],
                    "guest_name": review.get("guest_name", ""),
                    "platform": review.get("platform", ""),
                    "rating": review.get("rating", 0),
                    "response_preview": response_text[:120] + "...",
                    "status": "responded",
                })
                processed += 1
            except Exception as e:
                logger.error(f"Batch respond error for {review.get('id')}: {e}")
                errors.append({"review_id": review.get("id"), "error": str(e)[:80]})

        return {
            "processed": processed,
            "errors": len(errors),
            "error_details": errors,
            "results": results,
            "tone": tone,
        }

    @router.get("/languages")
    async def get_languages():
        """Get supported languages"""
        return [{"code": k, "name": v} for k, v in SUPPORTED_LANGUAGES.items()]

    @router.get("/reviews/stats/summary")
    async def get_review_stats(property_id: Optional[str] = None):
        """Get review statistics summary"""
        query = {}
        if property_id:
            query["property_id"] = property_id

        total = await db.reviews.count_documents(query)
        responded = await db.reviews.count_documents({**query, "response_status": "responded"})
        pending = await db.reviews.count_documents({**query, "response_status": "pending"})
        pending_approval = await db.reviews.count_documents({**query, "response_status": "pending_approval"})

        # Calculate average rating
        match_stage = {"$match": query} if query else {"$match": {}}
        pipeline = [
            match_stage,
            {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}
        ]
        result = await db.reviews.aggregate(pipeline).to_list(1)
        avg_rating = result[0]["avg_rating"] if result else 0

        # Platform breakdown
        platform_pipeline = [
            match_stage,
            {"$group": {"_id": "$platform", "count": {"$sum": 1}}}
        ]
        platform_result = await db.reviews.aggregate(platform_pipeline).to_list(100)
        platforms = {item["_id"]: item["count"] for item in platform_result}

        return {
            "total_reviews": total,
            "responded": responded,
            "pending": pending,
            "pending_approval": pending_approval,
            "response_rate": round((responded / total * 100) if total > 0 else 0, 1),
            "average_rating": round(avg_rating, 1) if avg_rating else 0,
            "by_platform": platforms
        }

    @router.post("/reviews/seed")
    async def seed_reviews():
        """Seed database with mock reviews for demo purposes"""
        existing = await db.reviews.count_documents({})
        if existing > 0:
            return {"message": f"Database already has {existing} reviews", "seeded": False}

        # Seed default property if not exists
        prop_exists = await db.properties.find_one({"id": "default"})
        if not prop_exists:
            await db.properties.insert_one({
                "id": "default",
                "name": "My Hotel",
                "address": "",
                "city": "",
                "country": "",
                "property_type": "hotel",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })

        avatars = [
            "https://images.unsplash.com/photo-1624300862338-94028d2603a5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzOTB8MHwxfHNlYXJjaHwyfHxwZXJzb24lMjBwb3J0cmFpdCUyMG5ldXRyYWwlMjBiYWNrZ3JvdW5kfGVufDB8fHx8MTc3NTgyNjkzN3ww&ixlib=rb-4.1.0&q=85",
            "https://images.unsplash.com/photo-1576997355598-a5a9def46291?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzOTB8MHwxfHNlYXJjaHwxfHxwZXJzb24lMjBwb3J0cmFpdCUyMG5ldXRyYWwlMjBiYWNrZ3JvdW5kfGVufDB8fHx8MTc3NTgyNjkzN3ww&ixlib=rb-4.1.0&q=85",
            "https://images.unsplash.com/photo-1770058443069-e384cd001e9b?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzOTB8MHwxfHNlYXJjaHw0fHxwZXJzb24lMjBwb3J0cmFpdCUyMG5ldXRyYWwlMjBiYWNrZ3JvdW5kfGVufDB8fHx8MTc3NTgyNjkzN3ww&ixlib=rb-4.1.0&q=85",
            "https://images.pexels.com/photos/6627006/pexels-photo-6627006.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
            "https://images.pexels.com/photos/7719379/pexels-photo-7719379.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
        ]

        mock_reviews = [
            {
                "platform": "booking.com",
                "guest_name": "Sarah Johnson",
                "guest_avatar": avatars[0],
                "rating": 5,
                "review_text": "Absolutely wonderful stay! The room was immaculate, staff incredibly friendly, and the breakfast buffet exceeded all expectations. The location is perfect for exploring the city. Will definitely be back!",
                "stay_date": "December 2025",
                "room_type": "Deluxe Suite",
                "response_status": "pending"
            },
            {
                "platform": "airbnb",
                "guest_name": "Michael Chen",
                "guest_avatar": avatars[1],
                "rating": 4,
                "review_text": "Great location and comfortable beds. The check-in process was smooth. Only minor issue was the WiFi being a bit slow during peak hours. Otherwise, a pleasant experience overall.",
                "stay_date": "January 2026",
                "room_type": "Standard Room",
                "response_status": "pending"
            },
            {
                "platform": "expedia",
                "guest_name": "Emma Rodriguez",
                "guest_avatar": avatars[2],
                "rating": 3,
                "review_text": "The hotel is decent but room service was quite slow and the air conditioning wasn't working properly. Front desk staff were helpful in trying to resolve issues. Pool area was nice.",
                "stay_date": "January 2026",
                "room_type": "Premium Room",
                "response_status": "pending"
            },
            {
                "platform": "tripadvisor",
                "guest_name": "James Wilson",
                "guest_avatar": avatars[3],
                "rating": 5,
                "review_text": "Outstanding hotel! From the moment we arrived, we were treated like royalty. The spa facilities are world-class and the rooftop restaurant has amazing views. Highly recommend the seafood platter!",
                "stay_date": "December 2025",
                "room_type": "Executive Suite",
                "response_status": "responded",
                "response_text": "Dear James, thank you so much for your wonderful review! We're thrilled to hear you enjoyed your stay with us. Our team works hard to create memorable experiences, and it's always rewarding to receive such positive feedback. We look forward to welcoming you back soon! - The Management Team"
            },
            {
                "platform": "google",
                "guest_name": "Lisa Anderson",
                "guest_avatar": avatars[4],
                "rating": 2,
                "review_text": "Disappointed with my stay. The room wasn't ready at check-in time despite confirming in advance. Noise from the street made it hard to sleep. Expected more for the price paid.",
                "stay_date": "January 2026",
                "room_type": "City View Room",
                "response_status": "pending"
            },
            {
                "platform": "trip.com",
                "guest_name": "David Kim",
                "guest_avatar": avatars[0],
                "rating": 4,
                "review_text": "Solid choice for business travelers. Clean rooms, fast WiFi, and convenient location near the business district. The gym is well-equipped. Would appreciate more power outlets near the desk.",
                "stay_date": "January 2026",
                "room_type": "Business Suite",
                "response_status": "pending"
            },
            {
                "platform": "booking.com",
                "guest_name": "Anna Martinez",
                "guest_avatar": avatars[1],
                "rating": 5,
                "review_text": "Perfect family vacation! The kids loved the pool and the staff arranged wonderful activities. Rooms were spacious enough for our family of four. Breakfast had great variety for picky eaters.",
                "stay_date": "December 2025",
                "room_type": "Family Suite",
                "response_status": "responded",
                "response_text": "Dear Anna, what a pleasure it was to host your family! We're so glad the children had a wonderful time at the pool. Family happiness is our priority, and we're delighted we could contribute to your vacation memories. Can't wait to see you all again! - The Management Team"
            },
            {
                "platform": "airbnb",
                "guest_name": "Robert Brown",
                "guest_avatar": avatars[2],
                "rating": 1,
                "review_text": "Very disappointing experience. Found hair in the bathroom, the minibar was missing items that were charged to my bill, and housekeeping never came despite multiple requests. Will not return.",
                "stay_date": "January 2026",
                "room_type": "Standard Room",
                "response_status": "pending"
            },
            {
                "platform": "tripadvisor",
                "guest_name": "Jennifer Lee",
                "guest_avatar": avatars[3],
                "rating": 4,
                "review_text": "Lovely boutique hotel with character. The room decor was charming and unique. Breakfast could use more healthy options. Staff remembered our names which was a nice personal touch.",
                "stay_date": "December 2025",
                "room_type": "Boutique Room",
                "response_status": "pending"
            },
            {
                "platform": "google",
                "guest_name": "Thomas Wright",
                "guest_avatar": avatars[4],
                "rating": 5,
                "review_text": "Celebrated our anniversary here and the team made it unforgettable! Champagne in the room, special dinner arrangement, and the most beautiful room decoration. True five-star service!",
                "stay_date": "December 2025",
                "room_type": "Honeymoon Suite",
                "response_status": "pending"
            }
        ]

        for review_data in mock_reviews:
            review = Review(**review_data)
            doc = review.model_dump()
            doc = serialize_review(doc)
            await db.reviews.insert_one(doc)

        return {"message": f"Seeded {len(mock_reviews)} mock reviews", "seeded": True}

    @router.delete("/reviews/clear")
    async def clear_reviews():
        """Clear all reviews (for testing)"""
        result = await db.reviews.delete_many({})
        return {"message": f"Deleted {result.deleted_count} reviews"}

    # ==================== NOTIFICATION SETTINGS ROUTES ====================

    @router.get("/notifications/settings")
    async def get_notification_settings():
        """Get current notification settings"""
        settings = await db.notification_settings.find_one({}, {"_id": 0})
        if not settings:
            # Return default settings
            return {
                "id": None,
                "email": NOTIFICATION_EMAIL or "",
                "notify_negative_reviews": True,
                "negative_threshold": 2,
                "enabled": False,
                "message": "Notification settings not configured. Update to enable."
            }
        return settings

    @router.put("/notifications/settings")
    async def update_notification_settings(settings: NotificationSettingsUpdate):
        """Update notification settings"""
        existing = await db.notification_settings.find_one({}, {"_id": 0})

        if existing:
            update_data = {k: v for k, v in settings.model_dump().items() if v is not None}
            if update_data:
                await db.notification_settings.update_one(
                    {"id": existing["id"]},
                    {"$set": update_data}
                )
            updated = await db.notification_settings.find_one({}, {"_id": 0})
            return updated
        else:
            # Create new settings
            new_settings = NotificationSettings(
                email=settings.email or NOTIFICATION_EMAIL or "",
                notify_negative_reviews=settings.notify_negative_reviews if settings.notify_negative_reviews is not None else True,
                negative_threshold=settings.negative_threshold if settings.negative_threshold is not None else 2,
                enabled=settings.enabled if settings.enabled is not None else True
            )
            doc = new_settings.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            await db.notification_settings.insert_one(doc)
            return new_settings

    @router.get("/notifications/log")
    async def get_notification_log():
        """Get notification history"""
        logs = await db.notification_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return logs

    @router.post("/notifications/test")
    async def test_notification():
        """Send a test notification email"""
        settings = await db.notification_settings.find_one({}, {"_id": 0})

        if not settings or not settings.get('enabled'):
            raise HTTPException(status_code=400, detail="Notifications not enabled. Configure settings first.")

        test_review = {
            "id": "test-notification",
            "platform": "google",
            "guest_name": "Test Guest",
            "rating": 1,
            "review_text": "This is a test notification to verify your email alerts are working correctly.",
            "room_type": "Test Room",
            "stay_date": "Test Date"
        }

        success = await send_negative_review_notification(test_review)

        if success:
            return {"status": "success", "message": f"Test notification sent to {settings.get('email')}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send test notification")

    # ==================== RESPONSE TEMPLATES ROUTES ====================

    @router.get("/templates", response_model=List[ResponseTemplate])
    async def get_templates(category: Optional[str] = None):
        """Get all response templates with optional category filter"""
        query = {}
        if category and category != "all":
            query["category"] = category

        templates = await db.response_templates.find(query, {"_id": 0}).sort("usage_count", -1).to_list(100)
        for template in templates:
            if isinstance(template.get('created_at'), str):
                template['created_at'] = datetime.fromisoformat(template['created_at'])
        return templates

    @router.get("/templates/{template_id}", response_model=ResponseTemplate)
    async def get_template(template_id: str):
        """Get a single template by ID"""
        template = await db.response_templates.find_one({"id": template_id}, {"_id": 0})
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        if isinstance(template.get('created_at'), str):
            template['created_at'] = datetime.fromisoformat(template['created_at'])
        return template

    @router.post("/templates", response_model=ResponseTemplate)
    async def create_template(input: ResponseTemplateCreate):
        """Create a new response template"""
        template = ResponseTemplate(**input.model_dump())
        doc = template.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.response_templates.insert_one(doc)
        return template

    @router.put("/templates/{template_id}", response_model=ResponseTemplate)
    async def update_template(template_id: str, input: ResponseTemplateUpdate):
        """Update an existing template"""
        template = await db.response_templates.find_one({"id": template_id}, {"_id": 0})
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        update_data = {k: v for k, v in input.model_dump().items() if v is not None}
        if update_data:
            await db.response_templates.update_one(
                {"id": template_id},
                {"$set": update_data}
            )

        updated = await db.response_templates.find_one({"id": template_id}, {"_id": 0})
        if isinstance(updated.get('created_at'), str):
            updated['created_at'] = datetime.fromisoformat(updated['created_at'])
        return updated

    @router.delete("/templates/{template_id}")
    async def delete_template(template_id: str):
        """Delete a template"""
        result = await db.response_templates.delete_one({"id": template_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"message": "Template deleted"}

    @router.post("/templates/{template_id}/use")
    async def use_template(template_id: str):
        """Increment usage count when a template is used"""
        template = await db.response_templates.find_one({"id": template_id}, {"_id": 0})
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        await db.response_templates.update_one(
            {"id": template_id},
            {"$inc": {"usage_count": 1}}
        )

        updated = await db.response_templates.find_one({"id": template_id}, {"_id": 0})
        return {"message": "Template usage recorded", "usage_count": updated.get("usage_count", 0)}

    @router.post("/templates/seed")
    async def seed_templates():
        """Seed database with default response templates"""
        existing = await db.response_templates.count_documents({})
        if existing > 0:
            return {"message": f"Database already has {existing} templates", "seeded": False}

        default_templates = [
            {
                "name": "Thank You - Excellent Stay",
                "category": "positive",
                "tone": "friendly",
                "content": "Dear {guest_name},\n\nThank you so much for your wonderful review and for choosing to stay with us! We're absolutely delighted to hear that you had an excellent experience.\n\nYour kind words mean the world to our team, and we're thrilled that we could make your stay memorable. We truly appreciate you taking the time to share your feedback.\n\nWe look forward to welcoming you back soon!\n\nWarm regards,\nThe Management Team"
            },
            {
                "name": "Appreciation - Great Service",
                "category": "praise",
                "tone": "professional",
                "content": "Dear {guest_name},\n\nThank you for your generous review and for recognizing our team's dedication to providing exceptional service.\n\nWe're committed to ensuring every guest feels valued and comfortable during their stay. Your feedback encourages us to continue striving for excellence.\n\nWe hope to have the pleasure of hosting you again in the future.\n\nBest regards,\nThe Management Team"
            },
            {
                "name": "Apology - Service Issue",
                "category": "complaint",
                "tone": "apologetic",
                "content": "Dear {guest_name},\n\nThank you for taking the time to share your feedback. We sincerely apologize that your experience did not meet your expectations.\n\nYour concerns have been brought to the attention of our management team, and we are taking immediate steps to address the issues you've raised. We take all feedback seriously as it helps us improve.\n\nWe would appreciate the opportunity to make things right. Please contact us directly at your convenience so we can discuss how we can better serve you in the future.\n\nWith sincere apologies,\nThe Management Team"
            },
            {
                "name": "Apology - Cleanliness Concern",
                "category": "negative",
                "tone": "apologetic",
                "content": "Dear {guest_name},\n\nThank you for bringing this matter to our attention. We sincerely apologize for the cleanliness issues you experienced during your stay.\n\nMaintaining high standards of cleanliness is a top priority for us, and we are deeply sorry that we fell short on this occasion. We have addressed this with our housekeeping team and implemented additional quality checks.\n\nWe value your feedback and would be grateful for another opportunity to provide you with the exceptional experience you deserve.\n\nWith our sincere apologies,\nThe Management Team"
            },
            {
                "name": "Response - Room Issues",
                "category": "complaint",
                "tone": "apologetic",
                "content": "Dear {guest_name},\n\nThank you for your feedback regarding your recent stay. We apologize for any inconvenience caused by the room issues you mentioned.\n\nWe have immediately notified our maintenance team to inspect and resolve the problems you described. Guest comfort is our priority, and we regret that we did not meet your expectations.\n\nWe would love to welcome you back and show you the true quality of our accommodation. Please reach out to us directly if you'd like to discuss this further.\n\nSincerely,\nThe Management Team"
            },
            {
                "name": "Neutral - Mixed Review",
                "category": "neutral",
                "tone": "professional",
                "content": "Dear {guest_name},\n\nThank you for sharing your balanced feedback about your stay with us. We appreciate you highlighting both the positives and areas where we can improve.\n\nWe're pleased that some aspects of your stay met your expectations, and we take your constructive feedback seriously. Our team is always working to enhance the guest experience.\n\nWe hope to welcome you back and exceed your expectations on your next visit.\n\nBest regards,\nThe Management Team"
            }
        ]

        for template_data in default_templates:
            template = ResponseTemplate(**template_data)
            doc = template.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            await db.response_templates.insert_one(doc)

        return {"message": f"Seeded {len(default_templates)} default templates", "seeded": True}

    # ==================== SENTIMENT & ANALYTICS ROUTES ====================

    @router.post("/reviews/{review_id}/analyze")
    async def analyze_review_sentiment(review_id: str):
        """Analyze sentiment of a specific review"""
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        analysis = await analyze_sentiment(review['review_text'], review['rating'])

        # Store analysis with review
        await db.reviews.update_one(
            {"id": review_id},
            {"$set": {"sentiment_analysis": analysis}}
        )

        # Find matching templates based on suggested category
        matching_templates = await db.response_templates.find(
            {"category": analysis.get("suggested_category", "neutral")},
            {"_id": 0}
        ).sort("usage_count", -1).to_list(3)

        return {
            "analysis": analysis,
            "suggested_templates": matching_templates
        }

    @router.post("/reviews/analyze-batch")
    async def analyze_reviews_batch():
        """Analyze sentiment for all reviews without analysis"""
        reviews = await db.reviews.find(
            {"sentiment_analysis": {"$exists": False}},
            {"_id": 0}
        ).to_list(100)

        analyzed_count = 0
        for review in reviews:
            try:
                analysis = await analyze_sentiment(review['review_text'], review['rating'])
                await db.reviews.update_one(
                    {"id": review['id']},
                    {"$set": {"sentiment_analysis": analysis}}
                )
                analyzed_count += 1
            except Exception as e:
                logger.error(f"Error analyzing review {review['id']}: {str(e)}")

        return {"message": f"Analyzed {analyzed_count} reviews", "total": len(reviews)}

    @router.get("/analytics/dashboard")
    async def get_analytics_dashboard():
        """Get comprehensive analytics dashboard data"""
        # Basic stats
        total_reviews = await db.reviews.count_documents({})
        responded = await db.reviews.count_documents({"response_status": "responded"})
        pending = await db.reviews.count_documents({"response_status": "pending"})

        # Average rating
        rating_pipeline = [
            {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}
        ]
        rating_result = await db.reviews.aggregate(rating_pipeline).to_list(1)
        avg_rating = round(rating_result[0]["avg_rating"], 2) if rating_result else 0

        # Rating distribution
        rating_dist_pipeline = [
            {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        rating_dist = await db.reviews.aggregate(rating_dist_pipeline).to_list(10)
        rating_distribution = {item["_id"]: item["count"] for item in rating_dist}

        # Sentiment distribution (from analyzed reviews)
        sentiment_pipeline = [
            {"$match": {"sentiment_analysis": {"$exists": True}}},
            {"$group": {"_id": "$sentiment_analysis.sentiment", "count": {"$sum": 1}}}
        ]
        sentiment_result = await db.reviews.aggregate(sentiment_pipeline).to_list(10)
        sentiment_distribution = {item["_id"]: item["count"] for item in sentiment_result if item["_id"]}

        # Platform distribution
        platform_pipeline = [
            {"$group": {"_id": "$platform", "count": {"$sum": 1}, "avg_rating": {"$avg": "$rating"}}}
        ]
        platform_result = await db.reviews.aggregate(platform_pipeline).to_list(10)
        platform_stats = [
            {"platform": item["_id"], "count": item["count"], "avg_rating": round(item["avg_rating"], 2)}
            for item in platform_result
        ]

        # Urgency breakdown (from analyzed reviews)
        urgency_pipeline = [
            {"$match": {"sentiment_analysis.urgency": {"$exists": True}}},
            {"$group": {"_id": "$sentiment_analysis.urgency", "count": {"$sum": 1}}}
        ]
        urgency_result = await db.reviews.aggregate(urgency_pipeline).to_list(10)
        urgency_distribution = {item["_id"]: item["count"] for item in urgency_result if item["_id"]}

        # Top mentioned topics
        topic_pipeline = [
            {"$match": {"sentiment_analysis.topics": {"$exists": True}}},
            {"$unwind": "$sentiment_analysis.topics"},
            {"$group": {"_id": "$sentiment_analysis.topics", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        topic_result = await db.reviews.aggregate(topic_pipeline).to_list(10)
        top_topics = [{"topic": item["_id"], "count": item["count"]} for item in topic_result]

        # Common issues and praises
        issues_pipeline = [
            {"$match": {"sentiment_analysis.key_issues": {"$exists": True}}},
            {"$unwind": "$sentiment_analysis.key_issues"},
            {"$group": {"_id": "$sentiment_analysis.key_issues", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        issues_result = await db.reviews.aggregate(issues_pipeline).to_list(5)
        common_issues = [{"issue": item["_id"], "count": item["count"]} for item in issues_result]

        praises_pipeline = [
            {"$match": {"sentiment_analysis.key_praises": {"$exists": True}}},
            {"$unwind": "$sentiment_analysis.key_praises"},
            {"$group": {"_id": "$sentiment_analysis.key_praises", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        praises_result = await db.reviews.aggregate(praises_pipeline).to_list(5)
        common_praises = [{"praise": item["_id"], "count": item["count"]} for item in praises_result]

        # Response rate calculation
        response_rate = round((responded / total_reviews * 100) if total_reviews > 0 else 0, 1)

        # Priority queue - urgent reviews needing attention
        priority_reviews = await db.reviews.find(
            {
                "response_status": "pending",
                "$or": [
                    {"rating": {"$lte": 2}},
                    {"sentiment_analysis.urgency": {"$in": ["high", "critical"]}}
                ]
            },
            {"_id": 0}
        ).sort("rating", 1).to_list(10)

        for review in priority_reviews:
            deserialize_review(review)

        return {
            "overview": {
                "total_reviews": total_reviews,
                "responded": responded,
                "pending": pending,
                "response_rate": response_rate,
                "avg_rating": avg_rating
            },
            "rating_distribution": rating_distribution,
            "sentiment_distribution": sentiment_distribution,
            "urgency_distribution": urgency_distribution,
            "platform_stats": platform_stats,
            "top_topics": top_topics,
            "common_issues": common_issues,
            "common_praises": common_praises,
            "priority_queue": priority_reviews
        }

    # ==================== COMPETITOR ROUTES ====================

    @router.get("/competitors")
    async def get_competitors():
        """Get all competitor data"""
        competitors = await db.competitors.find({}, {"_id": 0}).to_list(100)
        for comp in competitors:
            if isinstance(comp.get('last_updated'), str):
                comp['last_updated'] = datetime.fromisoformat(comp['last_updated'])
        return competitors

    @router.post("/competitors")
    async def add_competitor(input: CompetitorCreate):
        """Add a competitor for benchmarking"""
        competitor = CompetitorData(**input.model_dump())
        doc = competitor.model_dump()
        doc['last_updated'] = doc['last_updated'].isoformat()
        await db.competitors.insert_one(doc)
        return competitor

    @router.put("/competitors/{competitor_id}")
    async def update_competitor(competitor_id: str, input: CompetitorUpdate):
        """Update competitor data"""
        existing = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Competitor not found")

        update_data = {k: v for k, v in input.model_dump().items() if v is not None}
        update_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        await db.competitors.update_one(
            {"id": competitor_id},
            {"$set": update_data}
        )

        updated = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
        return updated

    @router.delete("/competitors/{competitor_id}")
    async def delete_competitor(competitor_id: str):
        """Delete a competitor"""
        result = await db.competitors.delete_one({"id": competitor_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Competitor not found")
        return {"message": "Competitor deleted"}

    @router.get("/competitors/benchmark")
    async def get_competitor_benchmark():
        """Get benchmark comparison with competitors"""
        # Get our stats
        our_stats = await get_review_stats_internal()

        # Get competitors
        competitors = await db.competitors.find({}, {"_id": 0}).to_list(100)

        benchmark = {
            "your_hotel": {
                "avg_rating": our_stats.get("average_rating", 0),
                "total_reviews": our_stats.get("total_reviews", 0),
                "response_rate": our_stats.get("response_rate", 0)
            },
            "competitors": competitors,
            "ranking": {
                "rating_rank": 1,
                "response_rate_rank": 1
            }
        }

        # Calculate rankings
        all_ratings = [our_stats.get("average_rating", 0)] + [c.get("avg_rating", 0) for c in competitors]
        all_response_rates = [our_stats.get("response_rate", 0)] + [c.get("response_rate", 0) for c in competitors]

        all_ratings.sort(reverse=True)
        all_response_rates.sort(reverse=True)

        benchmark["ranking"]["rating_rank"] = all_ratings.index(our_stats.get("average_rating", 0)) + 1
        benchmark["ranking"]["response_rate_rank"] = all_response_rates.index(our_stats.get("response_rate", 0)) + 1
        benchmark["ranking"]["total_competitors"] = len(competitors) + 1

        return benchmark

    @router.post("/competitors/seed")
    async def seed_competitors():
        """Seed demo competitor data"""
        existing = await db.competitors.count_documents({})
        if existing > 0:
            return {"message": f"Database already has {existing} competitors", "seeded": False}

        demo_competitors = [
            {"name": "Grand Hotel Plaza", "platform": "all", "avg_rating": 4.2, "total_reviews": 1250, "response_rate": 78.5},
            {"name": "Seaside Resort & Spa", "platform": "all", "avg_rating": 4.5, "total_reviews": 890, "response_rate": 92.0},
            {"name": "City Center Inn", "platform": "all", "avg_rating": 3.8, "total_reviews": 2100, "response_rate": 45.0},
            {"name": "Mountain View Lodge", "platform": "all", "avg_rating": 4.0, "total_reviews": 560, "response_rate": 85.0},
            {"name": "Airport Express Hotel", "platform": "all", "avg_rating": 3.5, "total_reviews": 3200, "response_rate": 30.0}
        ]

        for comp_data in demo_competitors:
            competitor = CompetitorData(**comp_data)
            doc = competitor.model_dump()
            doc['last_updated'] = doc['last_updated'].isoformat()
            await db.competitors.insert_one(doc)

        return {"message": f"Seeded {len(demo_competitors)} competitors", "seeded": True}

    # Helper function used by benchmark (renamed to avoid conflict with API endpoint)
    async def get_review_stats_internal():
        """Get review statistics"""
        total = await db.reviews.count_documents({})
        responded = await db.reviews.count_documents({"response_status": "responded"})

        pipeline = [
            {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}
        ]
        result = await db.reviews.aggregate(pipeline).to_list(1)
        avg_rating = result[0]["avg_rating"] if result else 0

        return {
            "total_reviews": total,
            "responded": responded,
            "response_rate": round((responded / total * 100) if total > 0 else 0, 1),
            "average_rating": round(avg_rating, 1) if avg_rating else 0
        }


    return router
