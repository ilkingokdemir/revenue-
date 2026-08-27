"""
Reports, Branding, Platform Integrations, Inbound Webhooks, Sync Log, Property Mapping Routes
Extracted from server.py for maintainability
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import os
import uuid
import csv
import io
import asyncio
import httpx
import logging

from routes.helpers import serialize_review
from models import Review

logger = logging.getLogger(__name__)


async def send_negative_review_notification(review_doc):
    logger.info("Negatif yorum bildirimi (mock): %s", (review_doc or {}).get("guest_name", ""))


def create_integrations_router(db, require_roles, resend):
    """Factory function that creates integration routes with injected dependencies"""
    from models import (
        ReportSettings, ReportSettingsUpdate,
        BrandingSettings, BrandingSettingsUpdate,
        PlatformIntegration, PlatformCredentials, ManualReviewImport, SyncResponse,
        InboundReviewPayload,
    )
    router = APIRouter()

    # Platform API configurations
    GOOGLE_BUSINESS_CLIENT_ID = os.environ.get('GOOGLE_BUSINESS_CLIENT_ID', '')
    GOOGLE_BUSINESS_CLIENT_SECRET = os.environ.get('GOOGLE_BUSINESS_CLIENT_SECRET', '')
    GOOGLE_BUSINESS_REFRESH_TOKEN = os.environ.get('GOOGLE_BUSINESS_REFRESH_TOKEN', '')
    BOOKING_API_USERNAME = os.environ.get('BOOKING_API_USERNAME', '')
    BOOKING_API_PASSWORD = os.environ.get('BOOKING_API_PASSWORD', '')
    TRIPADVISOR_API_KEY = os.environ.get('TRIPADVISOR_API_KEY', '')
    SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
    NOTIFICATION_EMAIL = os.environ.get('NOTIFICATION_EMAIL', '')

    # ==================== REPORT ROUTES ====================

    async def generate_report_html(settings: dict) -> str:
        """Generate HTML report with performance summary"""
        # Get analytics data
        total_reviews = await db.reviews.count_documents({})
        responded = await db.reviews.count_documents({"response_status": "responded"})
        pending = await db.reviews.count_documents({"response_status": "pending"})

        # Average rating
        rating_pipeline = [{"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}]
        rating_result = await db.reviews.aggregate(rating_pipeline).to_list(1)
        avg_rating = round(rating_result[0]["avg_rating"], 2) if rating_result else 0

        response_rate = round((responded / total_reviews * 100) if total_reviews > 0 else 0, 1)

        # Rating distribution
        rating_dist_pipeline = [
            {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
            {"$sort": {"_id": -1}}
        ]
        rating_dist = await db.reviews.aggregate(rating_dist_pipeline).to_list(10)

        # Sentiment distribution
        sentiment_pipeline = [
            {"$match": {"sentiment_analysis": {"$exists": True}}},
            {"$group": {"_id": "$sentiment_analysis.sentiment", "count": {"$sum": 1}}}
        ]
        sentiment_result = await db.reviews.aggregate(sentiment_pipeline).to_list(10)

        # Platform stats (reserved for future use in detailed reports)
        platform_pipeline = [
            {"$group": {"_id": "$platform", "count": {"$sum": 1}, "avg_rating": {"$avg": "$rating"}}}
        ]
        _ = await db.reviews.aggregate(platform_pipeline).to_list(10)

        # Urgent reviews
        urgent_count = await db.reviews.count_documents({
            "response_status": "pending",
            "$or": [
                {"rating": {"$lte": 2}},
                {"sentiment_analysis.urgency": {"$in": ["high", "critical"]}}
            ]
        })

        # Competitor benchmark
        competitors = await db.competitors.find({}, {"_id": 0}).to_list(100)
        # Review istatistikleri (iter 378: eksik closure referansı inline hesaplamayla düzeltildi)
        _total_reviews = await db.reviews.count_documents({})
        _agg = await db.reviews.aggregate(
            [{"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}]).to_list(1)
        _avg = _agg[0]["avg_rating"] if _agg and _agg[0].get("avg_rating") else 0
        our_stats = {"total_reviews": _total_reviews,
                     "average_rating": round(_avg, 1) if _avg else 0}

        # Calculate ranking
        all_ratings = [our_stats.get("average_rating", 0)] + [c.get("avg_rating", 0) for c in competitors]
        all_ratings.sort(reverse=True)
        rating_rank = all_ratings.index(our_stats.get("average_rating", 0)) + 1

        # Generate HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #FAF9F6; margin: 0; padding: 20px; }}
                .container {{ max-width: 700px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
                .header {{ background: linear-gradient(135deg, #3E5245 0%, #2A3B30 100%); color: white; padding: 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header p {{ margin: 10px 0 0; opacity: 0.9; }}
                .content {{ padding: 30px; }}
                .metrics {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 30px; }}
                .metric {{ background: #FAF9F6; border-radius: 8px; padding: 20px; text-align: center; }}
                .metric-value {{ font-size: 32px; font-weight: bold; color: #3E5245; }}
                .metric-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #57534E; margin-top: 5px; }}
                .section {{ margin-bottom: 25px; }}
                .section-title {{ font-size: 16px; font-weight: 600; color: #1C1917; margin-bottom: 15px; padding-bottom: 8px; border-bottom: 2px solid #E8EDE7; }}
                .competitor-row {{ display: flex; justify-content: space-between; padding: 12px; background: #FAF9F6; border-radius: 6px; margin-bottom: 8px; }}
                .competitor-row.highlight {{ background: #E8EDE7; border-left: 3px solid #3E5245; }}
                .badge {{ display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }}
                .badge-success {{ background: #5A6B50; color: white; }}
                .badge-warning {{ background: #D4A373; color: white; }}
                .badge-danger {{ background: #C05A44; color: white; }}
                .action-item {{ display: flex; align-items: center; gap: 10px; padding: 12px; background: #FEF3C7; border-radius: 6px; margin-bottom: 8px; }}
                .action-icon {{ width: 24px; height: 24px; background: #D4A373; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 14px; }}
                .footer {{ background: #FAF9F6; padding: 20px; text-align: center; color: #57534E; font-size: 12px; }}
                .rating-bar {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
                .rating-bar-fill {{ height: 8px; background: #D4A373; border-radius: 4px; }}
                .rating-bar-track {{ flex: 1; height: 8px; background: #E7E5E4; border-radius: 4px; overflow: hidden; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Weekly Performance Report</h1>
                    <p>Review Hub Summary • {datetime.now(timezone.utc).strftime('%B %d, %Y')}</p>
                </div>

                <div class="content">
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-value">{total_reviews}</div>
                            <div class="metric-label">Total Reviews</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{avg_rating}/5</div>
                            <div class="metric-label">Average Rating</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{response_rate}%</div>
                            <div class="metric-label">Response Rate</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{pending}</div>
                            <div class="metric-label">Pending Responses</div>
                        </div>
                    </div>
        """

        # Rating Distribution
        html += """
                    <div class="section">
                        <div class="section-title">⭐ Rating Distribution</div>
        """
        for item in sorted(rating_dist, key=lambda x: x["_id"], reverse=True):
            pct = round((item["count"] / total_reviews * 100)) if total_reviews > 0 else 0
            html += f"""
                        <div class="rating-bar">
                            <span style="width: 50px;">{item["_id"]} star</span>
                            <div class="rating-bar-track">
                                <div class="rating-bar-fill" style="width: {pct}%;"></div>
                            </div>
                            <span style="width: 60px; text-align: right;">{item["count"]} ({pct}%)</span>
                        </div>
            """
        html += "</div>"

        # Sentiment Summary
        if settings.get("include_sentiment_summary", True) and sentiment_result:
            html += """
                    <div class="section">
                        <div class="section-title">🎯 Sentiment Summary</div>
                        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            """
            for sent in sentiment_result:
                if sent["_id"]:
                    badge_class = "badge-success" if sent["_id"] == "positive" else "badge-danger" if sent["_id"] == "negative" else "badge-warning"
                    html += f'<span class="badge {badge_class}">{sent["_id"].capitalize()}: {sent["count"]}</span>'
            html += "</div></div>"

        # Competitor Comparison
        if settings.get("include_competitor_comparison", True) and competitors:
            html += f"""
                    <div class="section">
                        <div class="section-title">🏆 Competitive Position</div>
                        <p style="margin-bottom: 15px;">You rank <strong>#{rating_rank}</strong> out of {len(competitors) + 1} hotels in your competitive set.</p>

                        <div class="competitor-row highlight">
                            <span><strong>Your Hotel</strong></span>
                            <span>{avg_rating}/5 • {total_reviews} reviews • {response_rate}% response</span>
                        </div>
            """
            for comp in sorted(competitors, key=lambda x: x.get("avg_rating", 0), reverse=True)[:5]:
                html += f"""
                        <div class="competitor-row">
                            <span>{comp.get("name", "Unknown")}</span>
                            <span>{comp.get("avg_rating", 0)}/5 • {comp.get("total_reviews", 0)} reviews • {comp.get("response_rate", 0)}% response</span>
                        </div>
                """
            html += "</div>"

        # Action Items
        if settings.get("include_action_items", True):
            html += """
                    <div class="section">
                        <div class="section-title">📋 Action Items</div>
            """
            if urgent_count > 0:
                html += f"""
                        <div class="action-item">
                            <div class="action-icon">!</div>
                            <span><strong>{urgent_count} urgent reviews</strong> need immediate attention (negative feedback)</span>
                        </div>
                """
            if response_rate < 80:
                html += f"""
                        <div class="action-item">
                            <div class="action-icon">↑</div>
                            <span>Improve response rate from <strong>{response_rate}%</strong> to industry standard 80%+</span>
                        </div>
                """
            if avg_rating < 4.0:
                html += f"""
                        <div class="action-item">
                            <div class="action-icon">⭐</div>
                            <span>Focus on service quality to improve rating from <strong>{avg_rating}</strong> to 4.0+</span>
                        </div>
                """
            if urgent_count == 0 and response_rate >= 80 and avg_rating >= 4.0:
                html += """
                        <div class="action-item" style="background: #E8EDE7;">
                            <div class="action-icon" style="background: #5A6B50;">✓</div>
                            <span>Great job! All metrics are looking healthy. Keep up the excellent work!</span>
                        </div>
                """
            html += "</div>"

        # Footer
        html += """
                </div>

                <div class="footer">
                    <p>This report was automatically generated by Review Hub.</p>
                    <p>Manage your report settings in the dashboard.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    @router.get("/reports/settings")
    async def get_report_settings():
        """Get current report settings"""
        settings = await db.report_settings.find_one({}, {"_id": 0})
        if not settings:
            return {
                "id": None,
                "email": NOTIFICATION_EMAIL or "",
                "frequency": "weekly",
                "include_competitor_comparison": True,
                "include_sentiment_summary": True,
                "include_action_items": True,
                "enabled": False,
                "last_sent": None,
                "message": "Report settings not configured. Update to enable."
            }
        return settings

    @router.put("/reports/settings")
    async def update_report_settings(settings: ReportSettingsUpdate):
        """Update report settings"""
        existing = await db.report_settings.find_one({}, {"_id": 0})

        if existing:
            update_data = {k: v for k, v in settings.model_dump().items() if v is not None}
            if update_data:
                await db.report_settings.update_one(
                    {"id": existing["id"]},
                    {"$set": update_data}
                )
            updated = await db.report_settings.find_one({}, {"_id": 0})
            return updated
        else:
            new_settings = ReportSettings(
                email=settings.email or NOTIFICATION_EMAIL or "",
                frequency=settings.frequency or "weekly",
                include_competitor_comparison=settings.include_competitor_comparison if settings.include_competitor_comparison is not None else True,
                include_sentiment_summary=settings.include_sentiment_summary if settings.include_sentiment_summary is not None else True,
                include_action_items=settings.include_action_items if settings.include_action_items is not None else True,
                enabled=settings.enabled if settings.enabled is not None else True
            )
            doc = new_settings.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            if doc.get('last_sent'):
                doc['last_sent'] = doc['last_sent'].isoformat()
            await db.report_settings.insert_one(doc)
            return new_settings

    @router.post("/reports/send-now")
    async def send_report_now():
        """Send a report immediately"""
        settings = await db.report_settings.find_one({}, {"_id": 0})

        if not settings:
            raise HTTPException(status_code=400, detail="Report settings not configured")

        email = settings.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="No email address configured")

        # Generate report HTML
        report_html = await generate_report_html(settings)

        # Send email
        if not resend.api_key or resend.api_key == 're_123456789':
            # Demo mode - log but don't send
            await db.report_log.insert_one({
                "id": str(uuid.uuid4()),
                "email": email,
                "status": "demo_logged",
                "created_at": datetime.now(timezone.utc).isoformat()
            })

            # Update last_sent
            await db.report_settings.update_one(
                {"id": settings["id"]},
                {"$set": {"last_sent": datetime.now(timezone.utc).isoformat()}}
            )

            return {
                "status": "demo_logged",
                "message": f"Report logged (demo mode). In production, would be sent to {email}",
                "preview_available": True
            }

        try:
            params = {
                "from": SENDER_EMAIL,
                "to": [email],
                "subject": f"📊 Weekly Performance Report - Review Hub ({datetime.now(timezone.utc).strftime('%b %d, %Y')})",
                "html": report_html
            }

            email_result = await asyncio.to_thread(resend.Emails.send, params)

            # Log and update last_sent
            await db.report_log.insert_one({
                "id": str(uuid.uuid4()),
                "email": email,
                "email_id": email_result.get('id'),
                "status": "sent",
                "created_at": datetime.now(timezone.utc).isoformat()
            })

            await db.report_settings.update_one(
                {"id": settings["id"]},
                {"$set": {"last_sent": datetime.now(timezone.utc).isoformat()}}
            )

            return {"status": "sent", "message": f"Report sent to {email}"}

        except Exception as e:
            logger.error(f"Failed to send report: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to send report: {str(e)}")

    @router.get("/reports/preview")
    async def preview_report():
        """Preview the report without sending"""
        settings = await db.report_settings.find_one({}, {"_id": 0})
        if not settings:
            settings = {
                "include_competitor_comparison": True,
                "include_sentiment_summary": True,
                "include_action_items": True
            }

        report_html = await generate_report_html(settings)
        return {"html": report_html}

    @router.get("/reports/log")
    async def get_report_log():
        """Get report sending history"""
        logs = await db.report_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
        return logs

    # ==================== PLATFORM INTEGRATION SERVICES ====================

    class PlatformService:
        """Base class for platform integrations"""

        @staticmethod
        async def get_google_access_token():
            """Get Google OAuth access token from refresh token"""
            if not GOOGLE_BUSINESS_REFRESH_TOKEN:
                return None

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": GOOGLE_BUSINESS_CLIENT_ID,
                        "client_secret": GOOGLE_BUSINESS_CLIENT_SECRET,
                        "refresh_token": GOOGLE_BUSINESS_REFRESH_TOKEN,
                        "grant_type": "refresh_token"
                    }
                )
                if response.status_code == 200:
                    return response.json().get("access_token")
                return None

        @staticmethod
        async def fetch_google_reviews(location_id: str) -> List[dict]:
            """Fetch reviews from Google Business Profile API"""
            access_token = await PlatformService.get_google_access_token()
            if not access_token:
                raise HTTPException(status_code=401, detail="Google authentication failed")

            reviews = []
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://mybusiness.googleapis.com/v4/{location_id}/reviews",
                    headers={"Authorization": f"Bearer {access_token}"}
                )

                if response.status_code == 200:
                    data = response.json()
                    for review in data.get("reviews", []):
                        reviews.append({
                            "external_id": review.get("reviewId"),
                            "guest_name": review.get("reviewer", {}).get("displayName", "Google User"),
                            "rating": {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}.get(review.get("starRating"), 3),
                            "review_text": review.get("comment", ""),
                            "review_date": review.get("createTime"),
                            "has_reply": bool(review.get("reviewReply"))
                        })

            return reviews

        @staticmethod
        async def post_google_reply(location_id: str, review_id: str, reply_text: str) -> bool:
            """Post reply to Google review"""
            access_token = await PlatformService.get_google_access_token()
            if not access_token:
                raise HTTPException(status_code=401, detail="Google authentication failed")

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"https://mybusiness.googleapis.com/v4/{location_id}/reviews/{review_id}/reply",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={"comment": reply_text}
                )
                return response.status_code == 200

    # ==================== BRANDING ROUTES ====================

    @router.get("/branding")
    async def get_branding():
        """Get current branding settings"""
        branding = await db.branding_settings.find_one({}, {"_id": 0})
        if not branding:
            branding = {
                "app_name": "MyHotelBox & ReveniQ",
                "subtitle": "Otel PMS & Revenue Management",
                "primary_color": "#3E5245",
                "accent_color": "#D4A373",
                "logo_url": None,
                "powered_by_text": "",
                "powered_by_visible": False
            }
        if "updated_at" in branding and isinstance(branding["updated_at"], datetime):
            branding["updated_at"] = branding["updated_at"].isoformat()
        return branding

    @router.put("/branding")
    async def update_branding(settings: BrandingSettingsUpdate):
        """Update branding settings"""
        existing = await db.branding_settings.find_one({}, {"_id": 0})
        update_data = {k: v for k, v in settings.model_dump().items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        if existing:
            await db.branding_settings.update_one({}, {"$set": update_data})
        else:
            new_settings = {
                "app_name": "MyHotelBox & ReveniQ",
                "subtitle": "Otel PMS & Revenue Management",
                "primary_color": "#3E5245",
                "accent_color": "#D4A373",
                "logo_url": None,
                "powered_by_text": "",
                "powered_by_visible": False,
                **update_data
            }
            await db.branding_settings.insert_one(new_settings)

        branding = await db.branding_settings.find_one({}, {"_id": 0})
        if "updated_at" in branding and isinstance(branding["updated_at"], datetime):
            branding["updated_at"] = branding["updated_at"].isoformat()
        return branding

    @router.post("/branding/logo")
    async def upload_logo(file: UploadFile = File(...)):
        """Upload a logo image (stored as base64 in DB)"""
        import base64

        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        contents = await file.read()
        if len(contents) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image must be under 2MB")

        b64 = base64.b64encode(contents).decode("utf-8")
        logo_url = f"data:{file.content_type};base64,{b64}"

        existing = await db.branding_settings.find_one({})
        if existing:
            await db.branding_settings.update_one({}, {"$set": {"logo_url": logo_url, "updated_at": datetime.now(timezone.utc).isoformat()}})
        else:
            await db.branding_settings.insert_one({
                "app_name": "MyHotelBox & ReveniQ",
                "subtitle": "Otel PMS & Revenue Management",
                "primary_color": "#3E5245",
                "accent_color": "#D4A373",
                "logo_url": logo_url,
                "powered_by_text": "",
                "powered_by_visible": False,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })

        return {"logo_url": logo_url}

    @router.delete("/branding/logo")
    async def delete_logo():
        """Remove the custom logo"""
        await db.branding_settings.update_one({}, {"$set": {"logo_url": None, "updated_at": datetime.now(timezone.utc).isoformat()}})
        return {"message": "Logo removed"}

    # ==================== PLATFORM INTEGRATION ROUTES ====================

    @router.get("/integrations")
    async def get_integrations():
        """Get all platform integrations status"""
        integrations = await db.platform_integrations.find({}, {"_id": 0}).to_list(100)

        # Ensure all platforms have an entry
        platforms = [
            "google", "booking.com", "tripadvisor", "airbnb", "expedia", "trip.com",
            "agoda", "hotels.com", "yelp", "facebook", "makemytrip", "hrs", "despegar", "hostelworld"
        ]
        existing_platforms = {i["platform"] for i in integrations}

        for platform in platforms:
            if platform not in existing_platforms:
                default_integration = {
                    "id": str(uuid.uuid4()),
                    "platform": platform,
                    "status": "disconnected",
                    "credentials_configured": False,
                    "sync_enabled": False,
                    "total_reviews_synced": 0,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                # Create a copy for MongoDB insert (it will add _id to the dict)
                insert_doc = dict(default_integration)
                await db.platform_integrations.insert_one(insert_doc)
                integrations.append(default_integration)

        # Check which have credentials configured via env vars
        for integration in integrations:
            if integration["platform"] == "google":
                integration["credentials_configured"] = bool(GOOGLE_BUSINESS_CLIENT_ID and GOOGLE_BUSINESS_REFRESH_TOKEN)
            elif integration["platform"] == "booking.com":
                integration["credentials_configured"] = bool(BOOKING_API_USERNAME and BOOKING_API_PASSWORD)
            elif integration["platform"] == "tripadvisor":
                integration["credentials_configured"] = bool(TRIPADVISOR_API_KEY)

        return integrations

    @router.put("/integrations/{platform}/configure")
    async def configure_integration(platform: str, config: PlatformCredentials):
        """Configure platform integration credentials"""
        integration = await db.platform_integrations.find_one({"platform": platform}, {"_id": 0})

        if not integration:
            integration = {
                "id": str(uuid.uuid4()),
                "platform": platform,
                "status": "disconnected",
                "credentials_configured": False,
                "sync_enabled": False,
                "total_reviews_synced": 0,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.platform_integrations.insert_one(integration)

        update_data = {
            "credentials_configured": True,
            "location_id": config.location_id,
            "property_name": config.property_name,
            "status": "configured"
        }

        # Store credentials securely (in production, use a secrets manager)
        await db.platform_credentials.update_one(
            {"platform": platform},
            {"$set": {
                "platform": platform,
                "credentials": config.credentials,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )

        await db.platform_integrations.update_one(
            {"platform": platform},
            {"$set": update_data}
        )

        return {"status": "configured", "message": f"{platform} integration configured successfully"}

    @router.post("/integrations/{platform}/test-connection")
    async def test_platform_connection(platform: str):
        """Test connection to a configured platform"""
        integration = await db.platform_integrations.find_one({"platform": platform}, {"_id": 0})

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        if not integration.get("credentials_configured"):
            return {"success": False, "message": "No credentials configured. Please configure the platform first."}

        if platform == "google":
            try:
                access_token = await PlatformService.get_google_access_token()
                if access_token:
                    # Try to list accounts to verify the token works
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(
                            "https://mybusiness.googleapis.com/v4/accounts",
                            headers={"Authorization": f"Bearer {access_token}"}
                        )
                        if resp.status_code == 200:
                            await db.platform_integrations.update_one(
                                {"platform": "google"},
                                {"$set": {"status": "connected", "last_test": datetime.now(timezone.utc).isoformat()}}
                            )
                            return {"success": True, "message": "Google Business Profile connected successfully!"}
                        else:
                            return {"success": False, "message": f"Google API returned status {resp.status_code}. Check your credentials."}
                else:
                    return {"success": False, "message": "Failed to obtain access token. Check your Client ID, Secret, and Refresh Token."}
            except Exception as e:
                return {"success": False, "message": f"Connection test failed: {str(e)[:200]}"}

        # For platforms without direct API test, verify credentials are stored
        creds = await db.platform_credentials.find_one({"platform": platform}, {"_id": 0})
        if creds and creds.get("credentials"):
            return {"success": True, "message": f"Credentials saved for {platform}. Platform will be synced when API access is available."}

        return {"success": False, "message": "No credentials found. Please configure the platform first."}

    @router.post("/integrations/{platform}/sync")
    async def sync_platform_reviews(platform: str):
        """Sync reviews from a specific platform"""
        integration = await db.platform_integrations.find_one({"platform": platform}, {"_id": 0})

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        if not integration.get("credentials_configured"):
            raise HTTPException(status_code=400, detail="Platform credentials not configured")

        reviews_synced = 0
        errors = []

        try:
            if platform == "google":
                location_id = integration.get("location_id")
                if not location_id:
                    raise HTTPException(status_code=400, detail="Google location ID not configured")

                google_reviews = await PlatformService.fetch_google_reviews(location_id)

                for review_data in google_reviews:
                    # Check if review already exists
                    existing = await db.reviews.find_one({
                        "external_review_id": review_data["external_id"],
                        "platform": "google"
                    })

                    if not existing:
                        new_review = Review(
                            platform="google",
                            guest_name=review_data["guest_name"],
                            rating=review_data["rating"],
                            review_text=review_data["review_text"],
                            response_status="responded" if review_data["has_reply"] else "pending",
                            external_review_id=review_data["external_id"]
                        )
                        doc = new_review.model_dump()
                        doc = serialize_review(doc)
                        await db.reviews.insert_one(doc)
                        reviews_synced += 1

                        # Trigger notification for negative reviews
                        if review_data["rating"] <= 2:
                            await send_negative_review_notification(doc)

            else:
                # For other platforms, return a helpful message about requirements
                platform_info = {
                    "booking.com": "Requires Connectivity Partner approval. Apply at connect.booking.com",
                    "tripadvisor": "Requires Content API partner approval. Apply at developer.tripadvisor.com",
                    "airbnb": "API access requires Airbnb Partner program membership",
                    "expedia": "Requires Expedia Partner Central API access",
                    "trip.com": "Requires Trip.com Partner API credentials"
                }
                errors.append(f"Live sync not available. {platform_info.get(platform, 'Contact platform for API access.')}")

            # Update integration status
            await db.platform_integrations.update_one(
                {"platform": platform},
                {"$set": {
                    "last_sync": datetime.now(timezone.utc).isoformat(),
                    "status": "connected" if reviews_synced > 0 else integration.get("status"),
                    "total_reviews_synced": integration.get("total_reviews_synced", 0) + reviews_synced
                }}
            )

            return SyncResponse(
                platform=platform,
                reviews_synced=reviews_synced,
                errors=errors,
                status="success" if not errors else "partial"
            )

        except Exception as e:
            logger.error(f"Sync error for {platform}: {str(e)}")
            await db.platform_integrations.update_one(
                {"platform": platform},
                {"$set": {"status": "error", "error_message": str(e)}}
            )
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/integrations/{platform}/post-reply")
    async def post_reply_to_platform(platform: str, review_id: str, reply_text: str):
        """Post a reply to a review on the original platform"""
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})

        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        if review.get("platform") != platform:
            raise HTTPException(status_code=400, detail="Review platform mismatch")

        integration = await db.platform_integrations.find_one({"platform": platform}, {"_id": 0})

        if not integration or not integration.get("credentials_configured"):
            # Save reply locally and log
            await db.reviews.update_one({"id": review_id}, {"$set": {
                "response_text": reply_text,
                "response_status": "responded",
                "response_date": datetime.now(timezone.utc).isoformat(),
                "synced_to_platform": False
            }})
            await log_sync(db, platform, "outbound", "skipped", f"Reply saved locally — {platform} credentials not configured", review_id)
            return {
                "status": "logged",
                "message": f"Reply saved locally. Platform sync not configured for {platform}.",
                "synced_to_platform": False
            }

        # Attempt to post to platform
        success = False
        error_msg = ""

        try:
            if platform == "google" and review.get("external_review_id"):
                location_id = integration.get("location_id")
                success = await PlatformService.post_google_reply(
                    location_id,
                    review["external_review_id"],
                    reply_text
                )
            elif platform == "booking.com" and review.get("external_review_id"):
                # Booking.com Connectivity Partner API v3
                credentials = integration.get("credentials", {})
                api_user = credentials.get("username") or BOOKING_API_USERNAME
                api_pass = credentials.get("password") or BOOKING_API_PASSWORD
                hotel_id = integration.get("hotel_id", "")
                if api_user and api_pass and hotel_id:
                    async with httpx.AsyncClient(timeout=15.0) as c:
                        resp = await c.post(
                            f"https://supply-xml.booking.com/hotels/xml/reviews",
                            auth=(api_user, api_pass),
                            json={
                                "hotel_id": hotel_id,
                                "review_id": review["external_review_id"],
                                "response": {"text": reply_text}
                            },
                            headers={"Content-Type": "application/json"}
                        )
                        success = 200 <= resp.status_code < 300
                        if not success:
                            error_msg = f"Booking.com API returned {resp.status_code}"
                else:
                    error_msg = "Booking.com credentials incomplete"
            elif platform == "tripadvisor" and review.get("external_review_id"):
                # TripAdvisor Content API
                ta_key = integration.get("credentials", {}).get("api_key") or TRIPADVISOR_API_KEY
                location_id = integration.get("location_id", "")
                if ta_key and location_id:
                    async with httpx.AsyncClient(timeout=15.0) as c:
                        resp = await c.post(
                            f"https://api.tripadvisor.com/api/partner/2.0/location/{location_id}/reviews/{review['external_review_id']}/response",
                            headers={"X-TripAdvisor-API-Key": ta_key, "Content-Type": "application/json"},
                            json={"response_text": reply_text}
                        )
                        success = 200 <= resp.status_code < 300
                        if not success:
                            error_msg = f"TripAdvisor API returned {resp.status_code}"
                else:
                    error_msg = "TripAdvisor credentials incomplete"
            elif platform == "expedia" and review.get("external_review_id"):
                # Expedia Partner Central API
                credentials = integration.get("credentials", {})
                api_key = credentials.get("api_key", "")
                api_secret = credentials.get("api_secret", "")
                if api_key and api_secret:
                    async with httpx.AsyncClient(timeout=15.0) as c:
                        resp = await c.post(
                            f"https://services.expediapartnercentral.com/reviews/v1/reviews/{review['external_review_id']}/respond",
                            headers={"Authorization": f"Basic {api_key}", "Content-Type": "application/json"},
                            json={"body": reply_text}
                        )
                        success = 200 <= resp.status_code < 300
                        if not success:
                            error_msg = f"Expedia API returned {resp.status_code}"
                else:
                    error_msg = "Expedia credentials incomplete"
            else:
                # Platform-specific sync not yet supported
                error_msg = f"Outbound sync for {platform} requires platform API credentials"
        except httpx.TimeoutException:
            error_msg = f"Timeout connecting to {platform} API"
        except httpx.ConnectError:
            error_msg = f"Could not connect to {platform} API"
        except Exception as e:
            error_msg = str(e)[:200]

        # Update review sync status
        if success:
            await db.reviews.update_one({"id": review_id}, {"$set": {
                "response_text": reply_text,
                "response_status": "responded",
                "response_date": datetime.now(timezone.utc).isoformat(),
                "synced_to_platform": True,
                "sync_timestamp": datetime.now(timezone.utc).isoformat()
            }})
            await log_sync(db, platform, "outbound", "success", f"Reply posted to {platform} for review {review_id}", review_id)
            # Fire response.published webhook
            asyncio.create_task(fire_webhooks(db, "response.published", {
                "review_id": review_id,
                "platform": platform,
                "reply_text": reply_text[:200],
                "synced_at": datetime.now(timezone.utc).isoformat()
            }))
        else:
            await db.reviews.update_one({"id": review_id}, {"$set": {
                "response_text": reply_text,
                "response_status": "responded",
                "response_date": datetime.now(timezone.utc).isoformat(),
                "synced_to_platform": False,
                "sync_error": error_msg
            }})
            await log_sync(db, platform, "outbound", "error" if error_msg else "skipped", error_msg or f"Reply saved locally for {platform}", review_id)

        return {
            "status": "synced" if success else "logged",
            "message": f"Reply {'posted to ' + platform if success else 'saved locally' + (': ' + error_msg if error_msg else '')}",
            "synced_to_platform": success,
            "error": error_msg if not success else None
        }

    @router.get("/integrations/outbound-status")
    async def get_outbound_sync_status(current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get outbound sync status — how many responses are pending sync to platforms"""
        # Count responses by sync status
        responded_total = await db.reviews.count_documents({"response_status": "responded"})
        synced = await db.reviews.count_documents({"synced_to_platform": True})
        pending_sync = await db.reviews.count_documents({"response_status": "responded", "synced_to_platform": {"$ne": True}})

        # Group by platform
        pipeline = [
            {"$match": {"response_status": "responded"}},
            {"$group": {
                "_id": "$platform",
                "total": {"$sum": 1},
                "synced": {"$sum": {"$cond": [{"$eq": ["$synced_to_platform", True]}, 1, 0]}},
                "pending": {"$sum": {"$cond": [{"$ne": ["$synced_to_platform", True]}, 1, 0]}},
            }}
        ]
        by_platform = await db.reviews.aggregate(pipeline).to_list(50)

        # Recent sync logs (outbound)
        recent_logs = await db.sync_logs.find(
            {"direction": "outbound"}, {"_id": 0}
        ).sort("timestamp", -1).to_list(20)

        return {
            "total_responded": responded_total,
            "synced_to_platform": synced,
            "pending_sync": pending_sync,
            "by_platform": [{
                "platform": p["_id"],
                "total": p["total"],
                "synced": p["synced"],
                "pending": p["pending"]
            } for p in by_platform],
            "recent_activity": recent_logs,
        }

    @router.post("/integrations/sync-all-outbound")
    async def sync_all_pending_replies(current_user: dict = Depends(require_roles("admin"))):
        """Attempt to post all unsynchronised approved responses to their platforms"""
        pending = await db.reviews.find(
            {"response_status": "responded", "response_text": {"$ne": None}, "synced_to_platform": {"$ne": True}},
            {"_id": 0}
        ).to_list(100)

        results = {"synced": 0, "failed": 0, "skipped": 0, "details": []}

        for review in pending:
            platform = review.get("platform", "")
            integration = await db.platform_integrations.find_one({"platform": platform}, {"_id": 0})

            if not integration or not integration.get("credentials_configured"):
                results["skipped"] += 1
                results["details"].append({"review_id": review["id"], "platform": platform, "status": "skipped", "reason": "No credentials configured"})
                continue

            # Attempt sync via the post-reply endpoint logic
            try:
                reply_result = await post_reply_to_platform(platform, review["id"], review["response_text"])
                if reply_result.get("synced_to_platform"):
                    results["synced"] += 1
                    results["details"].append({"review_id": review["id"], "platform": platform, "status": "synced"})
                else:
                    results["failed"] += 1
                    results["details"].append({"review_id": review["id"], "platform": platform, "status": "failed", "error": reply_result.get("error", "")})
            except Exception as e:
                results["failed"] += 1
                results["details"].append({"review_id": review["id"], "platform": platform, "status": "error", "error": str(e)[:100]})

        return results

    @router.post("/integrations/import")
    async def import_reviews_manually(reviews: List[ManualReviewImport]):
        """Manually import reviews from CSV or manual entry"""
        imported = 0
        errors = []

        for review_data in reviews:
            try:
                new_review = Review(
                    platform=review_data.platform,
                    guest_name=review_data.guest_name,
                    rating=review_data.rating,
                    review_text=review_data.review_text,
                    stay_date=review_data.stay_date,
                    room_type=review_data.room_type,
                    response_status="pending",
                    external_review_id=review_data.external_review_id
                )

                # Parse review_date if provided
                if review_data.review_date:
                    try:
                        new_review.review_date = datetime.fromisoformat(review_data.review_date.replace("Z", "+00:00"))
                    except ValueError:
                        pass

                doc = new_review.model_dump()
                doc = serialize_review(doc)
                await db.reviews.insert_one(doc)
                imported += 1

                # Trigger notification for negative reviews
                if review_data.rating <= 2:
                    await send_negative_review_notification(doc)

            except Exception as e:
                errors.append(f"Error importing review from {review_data.guest_name}: {str(e)}")

        return {
            "imported": imported,
            "errors": errors,
            "message": f"Successfully imported {imported} reviews"
        }

    @router.post("/integrations/import-csv")
    async def import_reviews_from_csv(file: UploadFile = File(...)):
        """Import reviews from CSV file"""
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV")

        content = await file.read()
        decoded = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))

        reviews = []
        for row in reader:
            reviews.append(ManualReviewImport(
                platform=row.get('platform', 'unknown'),
                guest_name=row.get('guest_name', 'Guest'),
                rating=int(row.get('rating', 3)),
                review_text=row.get('review_text', ''),
                review_date=row.get('review_date'),
                stay_date=row.get('stay_date'),
                room_type=row.get('room_type'),
                external_review_id=row.get('external_id')
            ))

        return await import_reviews_manually(reviews)

    @router.get("/integrations/requirements")
    async def get_integration_requirements():
        """Get requirements for each platform integration"""
        return {
            "google": {
                "name": "Google Business Profile",
                "requirements": [
                    "Verified Google Business Profile",
                    "Google Cloud Project with Business Profile API enabled",
                    "OAuth 2.0 credentials (Client ID, Client Secret)",
                    "Refresh token with accounts.locations.reviews scope"
                ],
                "setup_url": "https://developers.google.com/my-business/content/review-data",
                "fields_needed": ["client_id", "client_secret", "refresh_token", "location_id"]
            },
            "booking.com": {
                "name": "Booking.com",
                "requirements": [
                    "Approved Connectivity Partner status",
                    "Machine account credentials",
                    "Property ID in Booking.com system"
                ],
                "setup_url": "https://connect.booking.com",
                "fields_needed": ["username", "password", "property_id"],
                "note": "Requires partner approval - not available for direct hotel connections"
            },
            "tripadvisor": {
                "name": "TripAdvisor",
                "requirements": [
                    "Content API partner approval",
                    "API key",
                    "Location ID"
                ],
                "setup_url": "https://developer.tripadvisor.com",
                "fields_needed": ["api_key", "location_id"]
            },
            "airbnb": {
                "name": "Airbnb",
                "requirements": [
                    "Airbnb Partner program membership",
                    "API credentials",
                    "Property listing ID"
                ],
                "setup_url": "https://www.airbnb.com/partner",
                "fields_needed": ["api_key", "listing_id"],
                "note": "Limited API access - mainly for property managers"
            },
            "expedia": {
                "name": "Expedia",
                "requirements": [
                    "Expedia Partner Central account",
                    "API credentials",
                    "Property ID"
                ],
                "setup_url": "https://expediapartnercentral.com",
                "fields_needed": ["api_key", "secret_key", "property_id"]
            },
            "trip.com": {
                "name": "Trip.com",
                "requirements": [
                    "Trip.com Partner API access",
                    "API credentials",
                    "Hotel ID"
                ],
                "setup_url": "https://partner.trip.com",
                "fields_needed": ["api_key", "hotel_id"]
            },
            "agoda": {
                "name": "Agoda",
                "requirements": [
                    "Agoda Partner Program membership",
                    "YCS (Yield Control System) account",
                    "API credentials from Agoda connectivity team",
                    "Property ID"
                ],
                "setup_url": "https://partners.agoda.com",
                "fields_needed": ["api_key", "property_id"],
                "note": "Agoda is part of Booking Holdings - contact your market manager for API access"
            },
            "hotels.com": {
                "name": "Hotels.com",
                "requirements": [
                    "Hotels.com Partner account",
                    "Expedia Partner Central API access (same system)",
                    "Property ID"
                ],
                "setup_url": "https://www.hotels.com/hotel-supplier",
                "fields_needed": ["api_key", "secret_key", "property_id"],
                "note": "Hotels.com is part of Expedia Group - use Expedia Partner Central for API"
            },
            "yelp": {
                "name": "Yelp",
                "requirements": [
                    "Claimed Yelp Business page",
                    "Yelp Fusion API key",
                    "Business ID"
                ],
                "setup_url": "https://www.yelp.com/developers",
                "fields_needed": ["api_key", "business_id"],
                "note": "Yelp Fusion API is free for limited use - great for local discovery"
            },
            "facebook": {
                "name": "Facebook Reviews",
                "requirements": [
                    "Facebook Business Page",
                    "Meta Business Suite access",
                    "Facebook Graph API access token",
                    "Page ID"
                ],
                "setup_url": "https://developers.facebook.com",
                "fields_needed": ["access_token", "page_id"],
                "note": "Use Meta Business Suite for managing reviews - Graph API for automation"
            },
            "makemytrip": {
                "name": "MakeMyTrip",
                "requirements": [
                    "MakeMyTrip Partner extranet account",
                    "API access from MMT partner team",
                    "Property ID"
                ],
                "setup_url": "https://partner.makemytrip.com",
                "fields_needed": ["api_key", "property_id"],
                "note": "#1 platform in India - contact partner support for API access"
            },
            "hrs": {
                "name": "HRS",
                "requirements": [
                    "HRS Partner account",
                    "HRS API credentials",
                    "Hotel ID"
                ],
                "setup_url": "https://www.hrs.com/hotel",
                "fields_needed": ["api_key", "hotel_id"],
                "note": "Popular in Germany and Europe for business travel"
            },
            "despegar": {
                "name": "Despegar",
                "requirements": [
                    "Despegar Partner account",
                    "API credentials from Despegar team",
                    "Property ID"
                ],
                "setup_url": "https://www.despegar.com/hoteles",
                "fields_needed": ["api_key", "property_id"],
                "note": "#1 OTA in Latin America - contact partner team for API access"
            },
            "hostelworld": {
                "name": "Hostelworld",
                "requirements": [
                    "Hostelworld Inbox account",
                    "API credentials",
                    "Property ID"
                ],
                "setup_url": "https://www.hostelworldgroup.com",
                "fields_needed": ["api_key", "property_id"],
                "note": "Best for hostels and budget accommodations"
            },
            "manual_import": {
                "name": "Manual Import",
                "description": "Import reviews via CSV file or manual entry when API access is not available",
                "csv_format": {
                    "columns": ["platform", "guest_name", "rating", "review_text", "review_date", "stay_date", "room_type", "external_id"],
                    "example": "google,John Doe,5,Great stay!,2024-01-15,January 2024,Deluxe Room,abc123"
                }
            }
        }

    # ==================== P0: INBOUND PLATFORM WEBHOOKS ====================
    # InboundReviewPayload imported from models.py

    @router.post("/platforms/{platform}/incoming")
    async def receive_platform_review(platform: str, payload: InboundReviewPayload, request: Request):
        """Receive inbound review from a platform webhook.
        Authenticate via X-Platform-Secret header or api_key query param."""
        # Authenticate
        secret = request.headers.get("X-Platform-Secret") or request.query_params.get("api_key")
        if not secret:
            raise HTTPException(status_code=401, detail="Authentication required: X-Platform-Secret header or api_key param")

        # Check API key
        key_doc = await db.api_keys.find_one({"key": secret, "is_active": True})
        if not key_doc:
            # Also check platform-specific secrets
            integration = await db.platform_integrations.find_one({"platform": platform}, {"_id": 0})
            if not integration or integration.get("inbound_secret") != secret:
                raise HTTPException(status_code=401, detail="Invalid authentication")

        # Deduplicate
        existing = await db.reviews.find_one({
            "external_review_id": payload.external_review_id,
            "platform": platform
        })
        if existing:
            # Log but don't create duplicate
            await log_sync(db, platform, "inbound", "skipped", "Duplicate review", payload.external_review_id)
            return {"status": "skipped", "message": "Review already exists", "review_id": existing.get("id")}

        # Create review
        new_review = Review(
            platform=platform,
            guest_name=payload.guest_name,
            rating=payload.rating,
            review_text=payload.review_text,
            stay_date=payload.stay_date,
            room_type=payload.room_type,
            response_status="pending",
            external_review_id=payload.external_review_id,
            property_id=payload.property_id or "default"
        )
        doc = new_review.model_dump()
        doc = serialize_review(doc)
        await db.reviews.insert_one(doc)

        await log_sync(db, platform, "inbound", "success", f"Review from {payload.guest_name}", payload.external_review_id)

        # Update integration stats
        await db.platform_integrations.update_one(
            {"platform": platform},
            {"$set": {"last_sync": datetime.now(timezone.utc).isoformat(), "status": "connected"},
             "$inc": {"total_reviews_synced": 1}}
        )

        # Trigger low-rating alert
        if payload.rating <= 2:
            await send_negative_review_notification(doc)

        # Fire webhooks
        await fire_webhooks(db, "review.created", doc)

        return {"status": "created", "review_id": doc["id"], "message": "Review received successfully"}

    @router.post("/platforms/{platform}/incoming/batch")
    async def receive_platform_reviews_batch(platform: str, request: Request):
        """Receive batch of reviews from a platform"""
        secret = request.headers.get("X-Platform-Secret") or request.query_params.get("api_key")
        if not secret:
            raise HTTPException(status_code=401, detail="Authentication required")

        key_doc = await db.api_keys.find_one({"key": secret, "is_active": True})
        if not key_doc:
            integration = await db.platform_integrations.find_one({"platform": platform}, {"_id": 0})
            if not integration or integration.get("inbound_secret") != secret:
                raise HTTPException(status_code=401, detail="Invalid authentication")

        body = await request.json()
        reviews = body if isinstance(body, list) else body.get("reviews", [])

        created = 0
        skipped = 0
        for r in reviews:
            existing = await db.reviews.find_one({"external_review_id": r.get("external_review_id"), "platform": platform})
            if existing:
                skipped += 1
                continue
            new_review = Review(
                platform=platform, guest_name=r.get("guest_name", "Guest"),
                rating=r.get("rating", 3), review_text=r.get("review_text", ""),
                stay_date=r.get("stay_date"), room_type=r.get("room_type"),
                response_status="pending", external_review_id=r.get("external_review_id"),
                property_id=r.get("property_id", "default")
            )
            doc = new_review.model_dump()
            doc = serialize_review(doc)
            await db.reviews.insert_one(doc)
            created += 1
            if r.get("rating", 3) <= 2:
                await send_negative_review_notification(doc)

        await log_sync(db, platform, "inbound_batch", "success", f"Created {created}, skipped {skipped}")
        return {"status": "success", "created": created, "skipped": skipped}

    @router.get("/platforms/{platform}/inbound-url")
    async def get_inbound_url(platform: str, request: Request, current_user: dict = Depends(require_roles("admin"))):
        """Get the inbound webhook URL for a platform to POST reviews to"""
        base_url = str(request.base_url).rstrip("/")

        # Generate or fetch platform-specific inbound secret
        integration = await db.platform_integrations.find_one({"platform": platform}, {"_id": 0})
        inbound_secret = None
        if integration:
            inbound_secret = integration.get("inbound_secret")
        if not inbound_secret:
            inbound_secret = f"psk_{uuid.uuid4().hex[:24]}"
            await db.platform_integrations.update_one(
                {"platform": platform},
                {"$set": {"inbound_secret": inbound_secret}}, upsert=True
            )

        return {
            "webhook_url": f"{base_url}/api/platforms/{platform}/incoming",
            "batch_url": f"{base_url}/api/platforms/{platform}/incoming/batch",
            "secret": inbound_secret,
            "headers": {"X-Platform-Secret": inbound_secret, "Content-Type": "application/json"},
            "payload_format": {
                "external_review_id": "string (unique ID from platform)",
                "guest_name": "string",
                "rating": "int (1-5)",
                "review_text": "string",
                "property_id": "string (optional, defaults to 'default')",
                "review_date": "ISO date string (optional)",
                "stay_date": "string (optional)",
                "room_type": "string (optional)"
            }
        }

    # ==================== SYNC LOG ====================

    async def log_sync(db, platform: str, direction: str, status: str, message: str = "", ref_id: str = ""):
        """Log a sync event"""
        await db.sync_logs.insert_one({
            "id": str(uuid.uuid4()),
            "platform": platform,
            "direction": direction,
            "status": status,
            "message": message,
            "ref_id": ref_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    # NOT (iter 377): fire_webhooks mükerrer closure kaldırıldı — kanonik: routes/helpers.py
    from routes.helpers import fire_webhooks

    @router.get("/sync-logs")
    async def get_sync_logs(request: Request, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get sync activity log"""
        platform = request.query_params.get("platform")
        limit = min(int(request.query_params.get("limit", "50")), 100)
        query = {"platform": platform} if platform else {}
        logs = await db.sync_logs.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)
        return logs

    # ==================== P1: PROPERTY MAPPING ====================

    @router.put("/properties/{property_id}/mapping")
    async def update_property_mapping(property_id: str, request: Request, current_user: dict = Depends(require_roles("admin"))):
        """Map a Review Hub property to an external system (e.g., MyHotelBox branch)"""
        body = await request.json()
        external_id = body.get("external_id", "")
        external_name = body.get("external_name", "")
        external_system = body.get("external_system", "myhotelbox")

        result = await db.properties.update_one(
            {"id": property_id},
            {"$set": {
                "external_id": external_id,
                "external_name": external_name,
                "external_system": external_system,
                "mapping_updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        updated = await db.properties.find_one({"id": property_id}, {"_id": 0})
        return updated

    @router.get("/properties/by-external/{external_id}")
    async def get_property_by_external_id(external_id: str):
        """Lookup a property by its external system ID (for incoming webhooks)"""
        prop = await db.properties.find_one({"external_id": external_id}, {"_id": 0})
        if not prop:
            raise HTTPException(status_code=404, detail="No property mapped to this external ID")
        return prop


    return router
