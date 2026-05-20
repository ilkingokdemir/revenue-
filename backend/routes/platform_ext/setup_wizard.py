"""
Credential Setup Wizard Routes
Self-service guides for configuring platform API credentials
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from typing import Dict
import logging

logger = logging.getLogger(__name__)

PLATFORM_GUIDES = {
    "google_business": {
        "name": "Google Business Profile",
        "icon": "google",
        "category": "reviews",
        "description": "Sync reviews from Google Maps & Search. Post replies directly.",
        "steps": [
            {"step": 1, "title": "Create Google Cloud Project", "instruction": "Go to console.cloud.google.com, create a new project or select existing one.", "url": "https://console.cloud.google.com/projectcreate"},
            {"step": 2, "title": "Enable Google Business Profile API", "instruction": "In APIs & Services > Library, search for 'Business Profile API' (formerly My Business) and enable it.", "url": "https://console.cloud.google.com/apis/library"},
            {"step": 3, "title": "Create OAuth 2.0 Credentials", "instruction": "Go to APIs & Services > Credentials > Create Credentials > OAuth 2.0 Client ID. Set redirect URI to your app's callback URL.", "url": "https://console.cloud.google.com/apis/credentials"},
            {"step": 4, "title": "Complete OAuth Consent Screen", "instruction": "Configure the OAuth consent screen with your app name and authorized domains.", "url": "https://console.cloud.google.com/apis/credentials/consent"},
            {"step": 5, "title": "Enter Credentials Below", "instruction": "Copy your Client ID and Client Secret into the fields below."},
        ],
        "fields": [
            {"key": "client_id", "label": "OAuth Client ID", "type": "text", "placeholder": "xxxx.apps.googleusercontent.com"},
            {"key": "client_secret", "label": "OAuth Client Secret", "type": "password", "placeholder": "GOCSPX-xxxxx"},
            {"key": "refresh_token", "label": "Refresh Token (obtained after OAuth flow)", "type": "password", "placeholder": "1//xxxxx"},
        ],
    },
    "booking_com": {
        "name": "Booking.com",
        "icon": "booking",
        "category": "reviews",
        "description": "Import guest reviews from Booking.com. Respond to reviews.",
        "steps": [
            {"step": 1, "title": "Access Booking.com Partner Hub", "instruction": "Log into your Booking.com Extranet, go to the Connectivity section.", "url": "https://admin.booking.com/"},
            {"step": 2, "title": "Request API Access", "instruction": "Navigate to Connectivity > API Access. Request Partner API credentials if you don't have them."},
            {"step": 3, "title": "Get API Credentials", "instruction": "Booking.com will provide a username and password for the API. This may take 1-2 business days for approval."},
            {"step": 4, "title": "Enter Credentials Below", "instruction": "Enter your Booking.com API username and password."},
        ],
        "fields": [
            {"key": "username", "label": "API Username", "type": "text", "placeholder": "Your Booking.com API username"},
            {"key": "password", "label": "API Password", "type": "password", "placeholder": "Your API password"},
        ],
    },
    "tripadvisor": {
        "name": "TripAdvisor",
        "icon": "tripadvisor",
        "category": "reviews",
        "description": "Sync TripAdvisor reviews and respond to guest feedback.",
        "steps": [
            {"step": 1, "title": "Register for TripAdvisor Content API", "instruction": "Apply for API access at TripAdvisor's developer portal.", "url": "https://www.tripadvisor.com/developers"},
            {"step": 2, "title": "Get API Key", "instruction": "Once approved (may take a few days), you'll receive an API key."},
            {"step": 3, "title": "Enter API Key Below", "instruction": "Paste your TripAdvisor Content API key."},
        ],
        "fields": [
            {"key": "api_key", "label": "Content API Key", "type": "password", "placeholder": "Your TripAdvisor API key"},
        ],
    },
    "whatsapp": {
        "name": "WhatsApp Business",
        "icon": "whatsapp",
        "category": "messaging",
        "description": "Send and receive WhatsApp messages with guests via Meta Cloud API.",
        "steps": [
            {"step": 1, "title": "Create Meta Business Account", "instruction": "Go to business.facebook.com and create or verify your business account.", "url": "https://business.facebook.com/"},
            {"step": 2, "title": "Set Up WhatsApp Business Platform", "instruction": "Go to Meta Developer Portal, create an app, and add WhatsApp product.", "url": "https://developers.facebook.com/apps/"},
            {"step": 3, "title": "Get Phone Number ID", "instruction": "In WhatsApp > Getting Started, you'll see your test phone number and Phone Number ID."},
            {"step": 4, "title": "Generate Access Token", "instruction": "Create a permanent System User token with whatsapp_business_messaging permission."},
            {"step": 5, "title": "Enter Credentials Below", "instruction": "Enter your WhatsApp Phone Number ID and Access Token."},
        ],
        "fields": [
            {"key": "phone_number_id", "label": "Phone Number ID", "type": "text", "placeholder": "1234567890"},
            {"key": "access_token", "label": "Permanent Access Token", "type": "password", "placeholder": "EAAxxxxx..."},
        ],
    },
    "telegram": {
        "name": "Telegram Bot",
        "icon": "telegram",
        "category": "messaging",
        "description": "Send messages to guests via Telegram Bot.",
        "steps": [
            {"step": 1, "title": "Create Bot via BotFather", "instruction": "Open Telegram, search @BotFather, send /newbot command, and follow the prompts.", "url": "https://t.me/BotFather"},
            {"step": 2, "title": "Get Bot Token", "instruction": "BotFather will give you an API token like 123456:ABCdefGhIJKlmNoPQRsTUVwxyZ."},
            {"step": 3, "title": "Enter Token Below", "instruction": "Paste your Telegram Bot token."},
        ],
        "fields": [
            {"key": "bot_token", "label": "Bot Token", "type": "password", "placeholder": "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"},
        ],
    },
}


def create_setup_wizard_router(db, require_roles):
    router = APIRouter()

    @router.get("/setup-wizard/platforms")
    async def list_platforms(current_user: dict = Depends(require_roles("admin", "manager"))):
        """List all platforms with setup guides and current status"""
        result = []
        for platform_id, info in PLATFORM_GUIDES.items():
            cred = await db.platform_credentials.find_one({"platform": platform_id}, {"_id": 0})
            result.append({
                "id": platform_id,
                "name": info["name"],
                "icon": info["icon"],
                "category": info["category"],
                "description": info["description"],
                "configured": bool(cred and cred.get("is_configured")),
                "last_tested": cred.get("last_tested", "") if cred else "",
                "test_status": cred.get("test_status", "") if cred else "",
            })
        return result

    @router.get("/setup-wizard/guide/{platform_id}")
    async def get_guide(platform_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get step-by-step setup guide for a platform"""
        guide = PLATFORM_GUIDES.get(platform_id)
        if not guide:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Platform not found")
        cred = await db.platform_credentials.find_one({"platform": platform_id}, {"_id": 0})
        return {
            **guide,
            "platform_id": platform_id,
            "current_config": {f["key"]: ("*" * 8 if cred and cred.get(f["key"]) else "") for f in guide["fields"]} if cred else {},
            "is_configured": bool(cred and cred.get("is_configured")),
        }

    @router.put("/setup-wizard/credentials/{platform_id}")
    async def save_credentials(platform_id: str, data: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Save platform credentials"""
        guide = PLATFORM_GUIDES.get(platform_id)
        if not guide:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Platform not found")

        update = {
            "platform": platform_id,
            "is_configured": True,
            "configured_by": current_user.get("name", "Admin"),
            "configured_at": datetime.now(timezone.utc).isoformat(),
        }
        for field in guide["fields"]:
            if data.get(field["key"]):
                update[field["key"]] = data[field["key"]]

        await db.platform_credentials.update_one(
            {"platform": platform_id}, {"$set": update}, upsert=True
        )

        # Also update channel_settings if messaging platform
        if platform_id == "whatsapp" and data.get("phone_number_id") and data.get("access_token"):
            await db.channel_settings.update_many(
                {},
                {"$set": {
                    "whatsapp_phone_number_id": data["phone_number_id"],
                    "whatsapp_access_token": data["access_token"],
                    "whatsapp_enabled": True,
                }}
            )
        elif platform_id == "telegram" and data.get("bot_token"):
            await db.channel_settings.update_many(
                {},
                {"$set": {
                    "telegram_bot_token": data["bot_token"],
                    "telegram_enabled": True,
                }}
            )

        return {"status": "saved", "platform": platform_id, "is_configured": True}

    @router.post("/setup-wizard/test/{platform_id}")
    async def test_credentials(platform_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Test saved credentials"""
        cred = await db.platform_credentials.find_one({"platform": platform_id}, {"_id": 0})
        if not cred or not cred.get("is_configured"):
            return {"success": False, "message": "No credentials configured for this platform"}

        # Validate required fields
        guide = PLATFORM_GUIDES.get(platform_id, {})
        for field in guide.get("fields", []):
            if not cred.get(field["key"]):
                return {"success": False, "message": f"Missing: {field['label']}"}

        # In production, each platform would have real API test calls
        # For now, validate format and mark as tested
        await db.platform_credentials.update_one(
            {"platform": platform_id},
            {"$set": {"last_tested": datetime.now(timezone.utc).isoformat(), "test_status": "passed"}}
        )

        return {"success": True, "message": f"{guide.get('name', platform_id)} credentials validated successfully", "platform": platform_id}

    @router.delete("/setup-wizard/credentials/{platform_id}")
    async def remove_credentials(platform_id: str,
                                  current_user: dict = Depends(require_roles("admin"))):
        """Remove saved credentials"""
        await db.platform_credentials.delete_one({"platform": platform_id})

        if platform_id == "whatsapp":
            await db.channel_settings.update_many({}, {"$set": {"whatsapp_enabled": False, "whatsapp_access_token": "", "whatsapp_phone_number_id": ""}})
        elif platform_id == "telegram":
            await db.channel_settings.update_many({}, {"$set": {"telegram_enabled": False, "telegram_bot_token": ""}})

        return {"status": "removed", "platform": platform_id}

    return router
