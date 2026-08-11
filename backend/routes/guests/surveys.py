"""
Guest Satisfaction Survey Routes
NPS + Category Ratings, configurable timing, multi-channel delivery, CRM integration
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from collections import defaultdict
import os
import uuid
import secrets
import logging

from routes.helpers import fire_webhooks, log_sync

logger = logging.getLogger(__name__)


def create_surveys_router(db, require_roles, LlmChat, UserMessage, resend):
    router = APIRouter()

    # ==================== SURVEY SETTINGS ====================

    @router.get("/surveys/settings/{property_id}")
    async def get_survey_settings(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.survey_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            default = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "enabled": True,
                "send_delay_hours": 2,
                "channels": ["email", "whatsapp"],
                "reminder_enabled": True,
                "reminder_delay_hours": 48,
                "survey_type": "detailed",
                "categories": [
                    {"key": "cleanliness", "label": "Cleanliness", "enabled": True},
                    {"key": "service", "label": "Staff & Service", "enabled": True},
                    {"key": "location", "label": "Location", "enabled": True},
                    {"key": "value", "label": "Value for Money", "enabled": True},
                    {"key": "comfort", "label": "Room Comfort", "enabled": True},
                    {"key": "facilities", "label": "Facilities", "enabled": True},
                ],
                "email_subject": "How was your stay at {hotel_name}?",
                "email_heading": "We'd love your feedback",
                "email_body": "Thank you for staying with us! Your honest feedback helps us improve and helps future guests. It takes just 2 minutes.",
                "whatsapp_message": "Hi {guest_name}! Thank you for staying at {hotel_name}. We'd love to hear how your stay was. Please take 2 minutes to share your feedback: {survey_link}",
                "thank_you_message": "Thank you for your feedback! Your responses help us provide the best possible experience for our guests.",
                "low_score_alert_threshold": 6,
                "low_score_alert_enabled": True,
                "auto_tag_profiles": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.survey_settings.insert_one(default)
            default.pop("_id", None)
            return default
        return doc

    @router.put("/surveys/settings/{property_id}")
    async def update_survey_settings(property_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.survey_settings.update_one({"property_id": property_id}, {"$set": updates}, upsert=True)
        doc = await db.survey_settings.find_one({"property_id": property_id}, {"_id": 0})
        return doc

    # ==================== SEND SURVEYS ====================

    @router.post("/surveys/send/{property_id}")
    async def send_surveys(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Send surveys to guests who checked out recently based on settings"""
        settings = await db.survey_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not settings or not settings.get("enabled"):
            return {"sent": 0, "message": "Surveys are disabled"}

        delay_hours = settings.get("send_delay_hours", 2)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=delay_hours)).strftime("%Y-%m-%d")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Find bookings that checked out between cutoff and today
        bookings = await db.bookings.find({
            "property_id": property_id,
            "check_out": {"$gte": cutoff, "$lte": today},
            "status": {"$ne": "cancelled"},
        }, {"_id": 0}).to_list(100)

        sent_count = 0
        for b in bookings:
            # Check if survey already sent for this booking
            existing = await db.survey_invites.find_one({
                "booking_ref": b.get("booking_ref"), "property_id": property_id
            })
            if existing:
                continue

            token = secrets.token_urlsafe(24)
            invite = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "booking_ref": b.get("booking_ref", ""),
                "guest_name": b.get("guest_name", ""),
                "guest_email": b.get("guest_email", ""),
                "guest_phone": b.get("guest_phone", ""),
                "room_type_id": b.get("room_type_id", ""),
                "check_in": b.get("check_in", ""),
                "check_out": b.get("check_out", ""),
                "token": token,
                "status": "sent",
                "channels_sent": settings.get("channels", ["email"]),
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "reminder_sent": False,
                "completed": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.survey_invites.insert_one(invite)
            invite.pop("_id", None)

            # Send via configured channels
            base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
            survey_link = f"{base_url}/survey/{token}"

            ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
            hotel_name = ts.get("hotel_name", property_id)

            if "email" in settings.get("channels", []) and b.get("guest_email"):
                subject = settings.get("email_subject", "How was your stay?").replace("{hotel_name}", hotel_name)
                heading = settings.get("email_heading", "We'd love your feedback")
                body_text = settings.get("email_body", "").replace("{hotel_name}", hotel_name).replace("{guest_name}", b.get("guest_name", "Guest"))
                html_body = f"""
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:30px;background:#fff;">
                    <h2 style="color:#1a1a1a;margin-bottom:5px;">{heading}</h2>
                    <p style="color:#666;font-size:15px;line-height:1.6;">{body_text}</p>
                    <div style="text-align:center;margin:30px 0;">
                        <a href="{survey_link}" style="background:#059669;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:16px;">Share Your Feedback</a>
                    </div>
                    <p style="color:#999;font-size:12px;text-align:center;">This survey takes about 2 minutes to complete.</p>
                </div>"""
                try:
                    sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
                    resend.emails.send({"from": sender, "to": [b["guest_email"]], "subject": subject, "html": html_body})
                except Exception as e:
                    logger.error(f"Survey email error: {e}")

            sent_count += 1

        return {"sent": sent_count, "message": f"Sent {sent_count} survey invitations"}

    @router.post("/surveys/send-manual")
    async def send_manual_survey(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Manually send survey to a specific guest"""
        property_id = data.get("property_id")
        token = secrets.token_urlsafe(24)
        invite = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "booking_ref": data.get("booking_ref", ""),
            "guest_name": data.get("guest_name", ""),
            "guest_email": data.get("guest_email", ""),
            "guest_phone": data.get("guest_phone", ""),
            "room_type_id": "",
            "check_in": data.get("check_in", ""),
            "check_out": data.get("check_out", ""),
            "token": token,
            "status": "sent",
            "channels_sent": ["email"],
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "reminder_sent": False,
            "completed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.survey_invites.insert_one(invite)
        invite.pop("_id", None)

        base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
        survey_link = f"{base_url}/survey/{token}"

        if data.get("guest_email"):
            ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
            hotel_name = ts.get("hotel_name", property_id)
            subject = f"How was your stay at {hotel_name}?"
            html_body = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:30px;">
                <h2>We'd love your feedback</h2>
                <p>Hi {data.get('guest_name', 'Guest')}, thank you for staying with us!</p>
                <div style="text-align:center;margin:30px 0;">
                    <a href="{survey_link}" style="background:#059669;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;">Share Your Feedback</a>
                </div>
            </div>"""
            try:
                sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
                resend.emails.send({"from": sender, "to": [data["guest_email"]], "subject": subject, "html": html_body})
            except Exception as e:
                logger.error(f"Manual survey email error: {e}")

        return {"invite": invite, "survey_link": survey_link}

    # ==================== PUBLIC SURVEY PAGE (No auth) ====================

    @router.get("/surveys/public/{token}")
    async def get_public_survey(token: str):
        """Public endpoint - no auth required. Returns survey form data."""
        if token.startswith("qr-"):
            pid = token[3:]
            settings = await db.survey_settings.find_one({"property_id": pid}, {"_id": 0})
            ts = await db.template_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
            return {
                "completed": False, "guest_name": "", "hotel_name": ts.get("hotel_name", pid),
                "check_in": "", "check_out": "", "anytime": True,
                "survey_type": settings.get("survey_type", "detailed") if settings else "detailed",
                "categories": settings.get("categories", []) if settings else [],
                "thank_you_message": settings.get("thank_you_message", "Thank you!") if settings else "Thank you!",
            }
        invite = await db.survey_invites.find_one({"token": token}, {"_id": 0})
        if not invite:
            raise HTTPException(404, "Survey not found or expired")
        if invite.get("completed"):
            return {"completed": True, "message": "You've already submitted this survey. Thank you!"}

        settings = await db.survey_settings.find_one({"property_id": invite["property_id"]}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": invite["property_id"]}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name", invite["property_id"])

        return {
            "completed": False,
            "guest_name": invite.get("guest_name", ""),
            "hotel_name": hotel_name,
            "check_in": invite.get("check_in", ""),
            "check_out": invite.get("check_out", ""),
            "survey_type": settings.get("survey_type", "detailed") if settings else "detailed",
            "categories": settings.get("categories", []) if settings else [],
            "thank_you_message": settings.get("thank_you_message", "Thank you!") if settings else "Thank you!",
        }

    @router.post("/surveys/public/{token}")
    async def submit_public_survey(token: str, data: Dict):
        """Public endpoint - no auth required. Submit survey response."""
        if token.startswith("qr-"):
            invite = {"property_id": token[3:], "id": "", "booking_ref": "qr-anytime",
                      "guest_name": data.get("guest_name", "Misafir"),
                      "guest_email": data.get("guest_email", ""),
                      "check_in": "", "check_out": "", "qr": True}
        else:
            invite = await db.survey_invites.find_one({"token": token}, {"_id": 0})
            if not invite:
                raise HTTPException(404, "Survey not found")
            if invite.get("completed"):
                raise HTTPException(400, "Survey already submitted")

        nps_score = data.get("nps_score", 0)
        category_ratings = data.get("category_ratings", {})
        comment = data.get("comment", "")

        # Calculate average category score
        cat_scores = [v for v in category_ratings.values() if isinstance(v, (int, float))]
        avg_category = round(sum(cat_scores) / len(cat_scores), 1) if cat_scores else 0

        response = {
            "id": str(uuid.uuid4()),
            "property_id": invite["property_id"],
            "invite_id": invite["id"],
            "booking_ref": invite.get("booking_ref", ""),
            "guest_name": invite.get("guest_name", ""),
            "guest_email": invite.get("guest_email", ""),
            "nps_score": nps_score,
            "category_ratings": category_ratings,
            "avg_category_score": avg_category,
            "comment": comment,
            "nps_category": "promoter" if nps_score >= 9 else ("passive" if nps_score >= 7 else "detractor"),
            "check_in": invite.get("check_in", ""),
            "check_out": invite.get("check_out", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.survey_responses.insert_one(response)
        response.pop("_id", None)

        # Mark invite as completed
        if not invite.get("qr"):
            await db.survey_invites.update_one({"token": token}, {"$set": {"completed": True, "completed_at": datetime.now(timezone.utc).isoformat()}})

        # Düşük skor → şikayet olarak robot gelen kutusuna düşür
        if (nps_score and nps_score <= 6) or (avg_category and avg_category <= 2.5):
            sev = "high" if (nps_score or 10) <= 3 else "medium"
            await db.guest_complaints.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": invite["property_id"],
                "guest_name": invite.get("guest_name") or "Anket Misafiri",
                "room_number": "", "category": "other", "channel": "survey",
                "text": comment or f"Düşük anket skoru (NPS: {nps_score}, kategori ort: {avg_category}). Yorum bırakılmadı.",
                "severity": sev, "status": "open",
                "source": "survey_low_score", "survey_response_id": response["id"],
                "created_by": "Survey Bot",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        # Update guest profile if auto_tag enabled
        settings = await db.survey_settings.find_one({"property_id": invite["property_id"]}, {"_id": 0})
        if settings and settings.get("auto_tag_profiles"):
            guest_email = invite.get("guest_email", "")
            if guest_email:
                nps_tag = f"nps:{response['nps_category']}"
                await db.guest_profiles.update_one(
                    {"email": guest_email},
                    {
                        "$set": {"last_nps_score": nps_score, "updated_at": datetime.now(timezone.utc).isoformat()},
                        "$addToSet": {"tags": nps_tag}
                    }
                )

        # Fire low-score alert
        if settings and settings.get("low_score_alert_enabled") and nps_score <= settings.get("low_score_alert_threshold", 6):
            await log_sync(db, "survey", "alert", "warning",
                f"Low NPS ({nps_score}) from {invite.get('guest_name', 'Guest')} - {invite.get('booking_ref', '')}",
                response["id"])

        return {"status": "submitted", "message": "Thank you for your feedback!",
                "review_prompt": await _review_prompt(invite["property_id"], nps_score, avg_category)}

    async def _review_prompt(pid: str, nps: int, avg_cat: float):
        """Yüksek skorlu misafiri TripAdvisor/Google yorumuna yönlendir (GuestRevu paritesi)."""
        if not ((nps and nps >= 9) or (avg_cat and avg_cat >= 4.5)):
            return {"show": False}
        cfg = await db.review_source_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        ta = cfg.get("tripadvisor_url", "")
        gp = cfg.get("google_place_id", "")
        google_url = f"https://search.google.com/local/writereview?placeid={gp}" if gp else ""
        if not ta and not google_url:
            return {"show": False}
        return {"show": True, "tripadvisor_url": ta, "google_url": google_url,
                "message": "Deneyiminizi çok beğendiğinize sevindik! Bir dakikanızı ayırıp yorumunuzu paylaşır mısınız?"}

    @router.get("/surveys/qr-image/{property_id}")
    async def survey_qr_image(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Her-an anket QR kodu (PNG) — lobiye/odaya asılabilir."""
        import io
        import qrcode
        from fastapi.responses import Response as FastAPIResponse
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
        link = f"{base_url}/survey/qr-{property_id}"
        img = qrcode.make(link)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return FastAPIResponse(content=buf.getvalue(), media_type="image/png",
                               headers={"X-Survey-Link": link})

    # ==================== SURVEY ANALYTICS (Admin) ====================

    @router.get("/surveys/responses/{property_id}")
    async def list_survey_responses(property_id: str, period: str = "30d", current_user: dict = Depends(require_roles("admin", "manager"))):
        days = int(period.replace("d", "")) if "d" in period else 30
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        responses = await db.survey_responses.find(
            {"property_id": property_id, "created_at": {"$gte": cutoff}}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)

        return responses

    @router.get("/surveys/analytics/{property_id}")
    async def survey_analytics(property_id: str, period: str = "30d", current_user: dict = Depends(require_roles("admin", "manager"))):
        days = int(period.replace("d", "")) if "d" in period else 30
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        responses = await db.survey_responses.find(
            {"property_id": property_id, "created_at": {"$gte": cutoff}}, {"_id": 0}
        ).to_list(1000)

        invites = await db.survey_invites.find(
            {"property_id": property_id, "created_at": {"$gte": cutoff}}, {"_id": 0}
        ).to_list(1000)

        total_sent = len(invites)
        total_responses = len(responses)
        response_rate = round((total_responses / total_sent) * 100, 1) if total_sent else 0

        nps_scores = [r["nps_score"] for r in responses if "nps_score" in r]
        avg_nps = round(sum(nps_scores) / len(nps_scores), 1) if nps_scores else 0

        promoters = sum(1 for s in nps_scores if s >= 9)
        passives = sum(1 for s in nps_scores if 7 <= s < 9)
        detractors = sum(1 for s in nps_scores if s < 7)
        nps_net = round(((promoters - detractors) / len(nps_scores)) * 100) if nps_scores else 0

        # Category averages
        cat_totals = defaultdict(list)
        for r in responses:
            for k, v in r.get("category_ratings", {}).items():
                if isinstance(v, (int, float)):
                    cat_totals[k].append(v)
        cat_averages = {k: round(sum(v) / len(v), 1) for k, v in cat_totals.items()}

        # Daily NPS trend
        daily = defaultdict(list)
        for r in responses:
            day = r["created_at"][:10]
            daily[day].append(r.get("nps_score", 0))
        daily_trend = [{"date": k, "avg_nps": round(sum(v) / len(v), 1), "count": len(v)} for k, v in sorted(daily.items())]

        # Recent comments
        recent_comments = [
            {"guest_name": r.get("guest_name"), "nps_score": r.get("nps_score"), "comment": r.get("comment"), "date": r.get("created_at", "")[:10]}
            for r in responses if r.get("comment")
        ][:10]

        return {
            "period_days": days,
            "total_sent": total_sent,
            "total_responses": total_responses,
            "response_rate": response_rate,
            "avg_nps": avg_nps,
            "nps_net_score": nps_net,
            "promoters": promoters,
            "passives": passives,
            "detractors": detractors,
            "category_averages": cat_averages,
            "daily_trend": daily_trend,
            "recent_comments": recent_comments,
        }

    @router.get("/surveys/invites/{property_id}")
    async def list_survey_invites(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.survey_invites.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    @router.delete("/surveys/responses/{response_id}")
    async def delete_survey_response(response_id: str, current_user: dict = Depends(require_roles("admin"))):
        await db.survey_responses.delete_one({"id": response_id})
        return {"status": "deleted"}

    return router
