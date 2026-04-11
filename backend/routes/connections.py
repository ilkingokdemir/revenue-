"""
API Connection, Webhooks, and Integration Guide Routes
Extracted from server.py for maintainability
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone
from typing import Dict
import os
import uuid
import secrets
import httpx
import logging

logger = logging.getLogger(__name__)


def create_connections_router(db, require_roles):
    """Factory function that creates connection routes with injected dependencies"""
    router = APIRouter()

    # ==================== API CONNECTION ROUTES ====================

    @router.get("/api-keys")
    async def list_api_keys(current_user: dict = Depends(require_roles("admin"))):
        """List all API keys"""
        keys = await db.api_keys.find({}, {"_id": 0}).to_list(50)
        # Mask the key value for security
        for k in keys:
            if k.get("key"):
                k["key_masked"] = k["key"][:8] + "..." + k["key"][-4:]
        return keys

    @router.post("/api-keys")
    async def create_api_key(request: Request, current_user: dict = Depends(require_roles("admin"))):
        """Generate a new API key for external integrations"""
        body = await request.json()
        label = body.get("label", "Default Key")

        key_value = f"rhk_{secrets.token_hex(24)}"
        new_key = {
            "id": str(uuid.uuid4()),
            "label": label,
            "key": key_value,
            "key_masked": key_value[:8] + "..." + key_value[-4:],
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", current_user.get("email")),
            "last_used": None,
            "request_count": 0
        }
        await db.api_keys.insert_one(new_key)
        new_key.pop("_id", None)
        return new_key

    @router.delete("/api-keys/{key_id}")
    async def delete_api_key(key_id: str, current_user: dict = Depends(require_roles("admin"))):
        """Delete an API key"""
        result = await db.api_keys.delete_one({"id": key_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="API key not found")
        return {"message": "API key deleted"}

    # ==================== WEBHOOK ROUTES ====================

    @router.get("/webhooks")
    async def list_webhooks(current_user: dict = Depends(require_roles("admin", "manager"))):
        """List all webhook configurations"""
        webhooks = await db.webhooks.find({}, {"_id": 0}).to_list(50)
        return webhooks

    @router.post("/webhooks")
    async def create_webhook(request: Request, current_user: dict = Depends(require_roles("admin"))):
        """Create a new webhook"""
        body = await request.json()
        url = body.get("url")
        events = body.get("events", [])
        label = body.get("label", "")

        if not url:
            raise HTTPException(status_code=400, detail="URL is required")

        valid_events = [
            "review.created", "review.responded", "review.approved", "review.rejected",
            "response.generated", "response.published",
            "rating.low", "rating.high",
            "booking.created", "booking.confirmed", "booking.cancelled", "booking.payment_received"
        ]

        for e in events:
            if e not in valid_events:
                raise HTTPException(status_code=400, detail=f"Invalid event: {e}. Valid: {', '.join(valid_events)}")

        webhook = {
            "id": str(uuid.uuid4()),
            "url": url,
            "label": label,
            "events": events or valid_events,
            "is_active": True,
            "secret": secrets.token_hex(16),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", current_user.get("email")),
            "last_triggered": None,
            "delivery_count": 0,
            "failure_count": 0
        }
        await db.webhooks.insert_one(webhook)
        webhook.pop("_id", None)
        return webhook

    @router.put("/webhooks/{webhook_id}")
    async def update_webhook(webhook_id: str, request: Request, current_user: dict = Depends(require_roles("admin"))):
        """Update a webhook"""
        body = await request.json()
        update_data = {}
        if "url" in body: update_data["url"] = body["url"]
        if "events" in body: update_data["events"] = body["events"]
        if "label" in body: update_data["label"] = body["label"]
        if "is_active" in body: update_data["is_active"] = body["is_active"]

        result = await db.webhooks.update_one({"id": webhook_id}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Webhook not found")
        updated = await db.webhooks.find_one({"id": webhook_id}, {"_id": 0})
        return updated

    @router.delete("/webhooks/{webhook_id}")
    async def delete_webhook(webhook_id: str, current_user: dict = Depends(require_roles("admin"))):
        """Delete a webhook"""
        result = await db.webhooks.delete_one({"id": webhook_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return {"message": "Webhook deleted"}

    @router.post("/webhooks/{webhook_id}/test")
    async def test_webhook(webhook_id: str, current_user: dict = Depends(require_roles("admin"))):
        """Send a test ping to a webhook URL"""
        webhook = await db.webhooks.find_one({"id": webhook_id}, {"_id": 0})
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")

        test_payload = {
            "event": "webhook.test",
            "test": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "review_id": "test-review-001",
                "platform": "google",
                "guest_name": "Test Guest",
                "rating": 5,
                "review_text": "This is a test webhook delivery from Review Hub.",
                "property_id": "default"
            }
        }

        import time
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client_http:
                resp = await client_http.post(
                    webhook["url"],
                    json=test_payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Secret": webhook.get("secret", ""),
                        "X-Webhook-Event": "webhook.test",
                        "User-Agent": "ReviewHub-Webhook/1.0"
                    }
                )
            elapsed_ms = round((time.monotonic() - start) * 1000)
            success = 200 <= resp.status_code < 300

            await db.webhooks.update_one({"id": webhook_id}, {"$set": {
                "last_triggered": datetime.now(timezone.utc).isoformat(),
                "last_test_result": {
                    "success": success,
                    "status_code": resp.status_code,
                    "response_time_ms": elapsed_ms,
                    "tested_at": datetime.now(timezone.utc).isoformat()
                }
            }, "$inc": {"delivery_count": 1, **({} if success else {"failure_count": 1})}})

            # Store delivery log
            await db.webhook_deliveries.insert_one({
                "id": str(uuid.uuid4()),
                "webhook_id": webhook_id,
                "event": "webhook.test",
                "url": webhook["url"],
                "status_code": resp.status_code,
                "success": success,
                "response_time_ms": elapsed_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload_preview": "Test ping payload"
            })

            return {
                "success": success,
                "status_code": resp.status_code,
                "response_time_ms": elapsed_ms,
                "message": "Webhook delivered successfully" if success else f"Webhook returned {resp.status_code}"
            }
        except httpx.TimeoutException:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            await db.webhooks.update_one({"id": webhook_id}, {"$set": {
                "last_test_result": {"success": False, "error": "timeout", "tested_at": datetime.now(timezone.utc).isoformat()}
            }, "$inc": {"failure_count": 1}})
            await db.webhook_deliveries.insert_one({
                "id": str(uuid.uuid4()), "webhook_id": webhook_id, "event": "webhook.test",
                "url": webhook["url"], "status_code": None, "success": False,
                "response_time_ms": elapsed_ms, "error": "timeout",
                "timestamp": datetime.now(timezone.utc).isoformat(), "payload_preview": "Test ping"
            })
            return {"success": False, "status_code": None, "response_time_ms": elapsed_ms, "message": "Connection timed out (10s)"}
        except httpx.ConnectError:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            await db.webhooks.update_one({"id": webhook_id}, {"$set": {
                "last_test_result": {"success": False, "error": "connection_refused", "tested_at": datetime.now(timezone.utc).isoformat()}
            }, "$inc": {"failure_count": 1}})
            await db.webhook_deliveries.insert_one({
                "id": str(uuid.uuid4()), "webhook_id": webhook_id, "event": "webhook.test",
                "url": webhook["url"], "status_code": None, "success": False,
                "response_time_ms": elapsed_ms, "error": "connection_refused",
                "timestamp": datetime.now(timezone.utc).isoformat(), "payload_preview": "Test ping"
            })
            return {"success": False, "status_code": None, "response_time_ms": elapsed_ms, "message": "Connection refused — check the URL"}
        except Exception as e:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            await db.webhooks.update_one({"id": webhook_id}, {"$set": {
                "last_test_result": {"success": False, "error": str(e), "tested_at": datetime.now(timezone.utc).isoformat()}
            }, "$inc": {"failure_count": 1}})
            await db.webhook_deliveries.insert_one({
                "id": str(uuid.uuid4()), "webhook_id": webhook_id, "event": "webhook.test",
                "url": webhook["url"], "status_code": None, "success": False,
                "response_time_ms": elapsed_ms, "error": str(e)[:200],
                "timestamp": datetime.now(timezone.utc).isoformat(), "payload_preview": "Test ping"
            })
            return {"success": False, "status_code": None, "response_time_ms": elapsed_ms, "message": f"Error: {str(e)[:100]}"}

    @router.get("/webhooks/{webhook_id}/deliveries")
    async def get_webhook_deliveries(webhook_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get delivery log for a webhook (last 20)"""
        webhook = await db.webhooks.find_one({"id": webhook_id}, {"_id": 0})
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        deliveries = await db.webhook_deliveries.find(
            {"webhook_id": webhook_id}, {"_id": 0}
        ).sort("timestamp", -1).to_list(20)
        return deliveries

    @router.get("/webhooks/events")
    async def get_webhook_events():
        """Get available webhook events"""
        return [
            {"id": "review.created", "name": "New Review", "description": "When a new review is received", "category": "reviews"},
            {"id": "review.responded", "name": "Review Responded", "description": "When a response is published", "category": "reviews"},
            {"id": "review.approved", "name": "Response Approved", "description": "When a response is approved by manager", "category": "reviews"},
            {"id": "review.rejected", "name": "Response Rejected", "description": "When a response is rejected", "category": "reviews"},
            {"id": "response.generated", "name": "AI Response Generated", "description": "When AI generates a response draft", "category": "reviews"},
            {"id": "response.published", "name": "Response Published", "description": "When response is synced to platform", "category": "reviews"},
            {"id": "rating.low", "name": "Low Rating Alert", "description": "When a review with rating <= 2 is received", "category": "reviews"},
            {"id": "rating.high", "name": "High Rating", "description": "When a review with rating >= 4 is received", "category": "reviews"},
            {"id": "booking.created", "name": "New Booking", "description": "When a new direct booking reservation is created", "category": "bookings"},
            {"id": "booking.confirmed", "name": "Booking Confirmed", "description": "When a booking is confirmed after payment", "category": "bookings"},
            {"id": "booking.cancelled", "name": "Booking Cancelled", "description": "When a booking is cancelled by guest or staff", "category": "bookings"},
            {"id": "booking.payment_received", "name": "Payment Received", "description": "When payment is successfully processed for a booking", "category": "bookings"},
        ]

    @router.get("/integration-guide")
    async def get_integration_guide(request: Request):
        """Get the MyHotelBox integration guide with live API base URL"""
        base_url = str(request.base_url).rstrip("/")
        return {
            "title": "MyHotelBox.com Integration Guide",
            "base_url": f"{base_url}/api",
            "steps": [
                {
                    "step": 1,
                    "title": "Generate an API Key",
                    "description": "Go to API Connection in Review Hub sidebar and create an API key. This key authenticates all requests from MyHotelBox."
                },
                {
                    "step": 2,
                    "title": "Set Up a Webhook",
                    "description": "Go to Webhooks in Review Hub sidebar. Create a webhook pointing to your MyHotelBox endpoint (e.g., https://myhotelbox.com/api/integrations/review-hub/webhook). Select the events you want to receive."
                },
                {
                    "step": 3,
                    "title": "Map Your Properties",
                    "description": "Each property in MyHotelBox (e.g., ALDGATE FLATS) should map to a property_id in Review Hub. Use the Properties API to create matching properties."
                },
                {
                    "step": 4,
                    "title": "Fetch Reviews from Review Hub",
                    "description": "Use the Reviews API to pull reviews into your MyHotelBox dashboard. Filter by property_id, platform, date range, or status."
                },
                {
                    "step": 5,
                    "title": "Test the Connection",
                    "description": "Use the 'Send Test Ping' button on your webhook to verify MyHotelBox receives events correctly."
                }
            ],
            "api_examples": {
                "auth_header": "Authorization: Bearer rhk_your_api_key",
                "endpoints": [
                    {"method": "GET", "path": "/api/reviews", "description": "List all reviews (supports ?property_id=&platform=&status= filters)"},
                    {"method": "GET", "path": "/api/reviews/stats/summary", "description": "Get review statistics (total, avg rating, response rate)"},
                    {"method": "POST", "path": "/api/reviews/generate-ai-response", "description": "Generate AI response for a review"},
                    {"method": "GET", "path": "/api/properties", "description": "List all properties"},
                    {"method": "POST", "path": "/api/properties", "description": "Create a new property"},
                    {"method": "GET", "path": "/api/webhooks/events", "description": "List available webhook event types"},
                    {"method": "GET", "path": "/api/integrations", "description": "List connected review platforms"},
                    {"method": "POST", "path": "/api/integrations/{platform}/sync", "description": "Trigger review sync for a platform"}
                ]
            },
            "webhook_payload_example": {
                "event": "review.created",
                "timestamp": "2026-04-10T20:00:00Z",
                "data": {
                    "review_id": "abc-123",
                    "platform": "booking.com",
                    "guest_name": "Elizabeth Elizabeth",
                    "rating": 5,
                    "review_text": "Wonderful stay at Aldgate Flats!",
                    "property_id": "aldgate-flats",
                    "stay_date": "2026-05-08",
                    "room_type": "One Bedroom"
                }
            },
            "webhook_headers": {
                "Content-Type": "application/json",
                "X-Webhook-Secret": "your_webhook_secret",
                "X-Webhook-Event": "review.created",
                "User-Agent": "ReviewHub-Webhook/1.0"
            }
        }


    return router
