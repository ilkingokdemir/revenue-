from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Request, Response, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import httpx
import csv
import io
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
from emergentintegrations.llm.chat import LlmChat, UserMessage
import resend
import bcrypt
import jwt
import secrets
from bson import ObjectId

# Import extracted modules
from models import (
    StatusCheck, StatusCheckCreate, Review, ReviewCreate, ReviewResponse,
    AIGenerateRequest, AIGenerateResponse, NotificationSettings, NotificationSettingsUpdate,
    ReportSettings, ReportSettingsUpdate, ResponseTemplate, ResponseTemplateCreate, ResponseTemplateUpdate,
    SentimentAnalysis, CompetitorData, CompetitorCreate, CompetitorUpdate, AnalyticsData,
    PlatformIntegration, PlatformCredentials, ManualReviewImport, SyncResponse,
    BrandingSettings, BrandingSettingsUpdate,
    UserRegister, UserLogin, UserUpdate, ApprovalAction,
    Property, PropertyCreate, PropertyUpdate,
    VALID_ROLES, VALID_DEPARTMENTS, VALID_PROPERTY_TYPES,
    RoomType, RoomTypeCreate, RoomTypeUpdate, Booking, BookingCreate,
    InboundReviewPayload,
    TemplateSettings, TemplateSettingsUpdate,
    AMENITY_CATALOG, FACILITY_CATALOG,
    PromoCode, PromoCodeCreate,
    AddOnService, AddOnServiceCreate,
    HotelPolicies, HotelPoliciesUpdate,
    PropertyFacilities,
    UpsellItem, UpsellItemCreate, SocialProofSettings,
)
from database import db, client
from auth import (
    get_jwt_secret, hash_password, verify_password,
    create_access_token, create_refresh_token,
    get_current_user, require_roles, verify_api_key,
    JWT_ALGORITHM,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Resend configuration
resend.api_key = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
NOTIFICATION_EMAIL = os.environ.get('NOTIFICATION_EMAIL', '')

# Platform API configurations
GOOGLE_BUSINESS_CLIENT_ID = os.environ.get('GOOGLE_BUSINESS_CLIENT_ID', '')
GOOGLE_BUSINESS_CLIENT_SECRET = os.environ.get('GOOGLE_BUSINESS_CLIENT_SECRET', '')
GOOGLE_BUSINESS_REFRESH_TOKEN = os.environ.get('GOOGLE_BUSINESS_REFRESH_TOKEN', '')
BOOKING_API_USERNAME = os.environ.get('BOOKING_API_USERNAME', '')
BOOKING_API_PASSWORD = os.environ.get('BOOKING_API_PASSWORD', '')
TRIPADVISOR_API_KEY = os.environ.get('TRIPADVISOR_API_KEY', '')

# Create the main app without a prefix
app = FastAPI(
    title="Hotel Review Hub API",
    description="""
## Hotel Review Management API

Complete API for managing guest reviews across 14+ online platforms with AI-powered response generation.

### Key Features
- **Authentication** — JWT-based auth with Admin/Manager/Receptionist roles
- **Reviews** — CRUD operations, AI response generation, multi-language support
- **Approval Workflow** — Draft → Pending Approval → Approved/Rejected → Published
- **Analytics** — Dashboard, sentiment analysis, competitor benchmarking
- **Integrations** — 14 platform configurations (Google, Booking.com, Airbnb, etc.)
- **Branding** — White-label customization (logo, colors, name)

### Authentication
Login via `POST /api/auth/login` to receive a JWT token. Use the token as:
- **Cookie**: Automatically set as `access_token` httpOnly cookie
- **Header**: `Authorization: Bearer <token>`
    """,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== AUTH (imported from auth.py) ====================
# get_jwt_secret, hash_password, verify_password, create_access_token,
# create_refresh_token, get_current_user, require_roles, verify_api_key
# are all imported from auth.py

# ==================== MODELS (imported from models.py) ====================
# All Pydantic models imported from models.py

# ==================== HELPER FUNCTIONS ====================

def serialize_review(review: dict) -> dict:
    """Serialize review for JSON response"""
    for field in ['review_date', 'response_date', 'created_at']:
        if field in review and isinstance(review[field], datetime):
            review[field] = review[field].isoformat()
    return review

def deserialize_review(review: dict) -> dict:
    """Deserialize review from MongoDB"""
    for field in ['review_date', 'response_date', 'created_at']:
        if field in review and isinstance(review[field], str):
            review[field] = datetime.fromisoformat(review[field])
    return review

# Seed admin user
async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@hotelbox.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "HotelAdmin2026!")
    
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hashed,
            "name": "Hotel Admin",
            "role": "admin",
            "department": "management",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Admin user seeded: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
        logger.info(f"Admin password updated: {admin_email}")
    
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register")
async def register(user: UserRegister, request: Request, response: Response, current_user: dict = Depends(require_roles("admin"))):
    """Register new user (admin only)"""
    email = user.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if user.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")
    if user.department not in VALID_DEPARTMENTS:
        raise HTTPException(status_code=400, detail=f"Invalid department. Must be one of: {', '.join(VALID_DEPARTMENTS)}")
    
    hashed = hash_password(user.password)
    new_user = {
        "email": email,
        "password_hash": hashed,
        "name": user.name,
        "role": user.role,
        "department": user.department,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.users.insert_one(new_user)
    return {
        "id": str(result.inserted_id),
        "email": email,
        "name": user.name,
        "role": user.role,
        "department": user.department,
        "is_active": True
    }

@api_router.post("/auth/login")
async def login(user: UserLogin, request: Request, response: Response):
    """Login"""
    email = user.email.lower().strip()
    client_ip = request.client.host if request.client else "unknown"
    identifier = f"{client_ip}:{email}"
    attempts = await db.login_attempts.find_one({"identifier": identifier})
    if attempts and attempts.get("count", 0) >= 5:
        last_attempt = attempts.get("last_attempt")
        if last_attempt:
            if isinstance(last_attempt, str):
                last_attempt = datetime.fromisoformat(last_attempt)
            if datetime.now(timezone.utc) - last_attempt < timedelta(minutes=15):
                raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 15 minutes.")
    
    db_user = await db.users.find_one({"email": email})
    if not db_user or not verify_password(user.password, db_user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"last_attempt": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not db_user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is deactivated")
    
    await db.login_attempts.delete_one({"identifier": identifier})
    
    user_id = str(db_user["_id"])
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=86400, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
    
    return {
        "id": user_id,
        "email": db_user["email"],
        "name": db_user["name"],
        "role": db_user["role"],
        "department": db_user.get("department", "front_desk"),
        "token": access_token
    }

@api_router.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["_id"],
        "email": current_user["email"],
        "name": current_user["name"],
        "role": current_user["role"],
        "department": current_user.get("department", "front_desk"),
        "is_active": current_user.get("is_active", True)
    }

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out"}

@api_router.post("/auth/refresh")
async def refresh_token_endpoint(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        new_access = create_access_token(str(user["_id"]), user["email"])
        response.set_cookie(key="access_token", value=new_access, httponly=True, secure=False, samesite="lax", max_age=86400, path="/")
        return {"message": "Token refreshed"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

# ==================== USER MANAGEMENT ROUTES ====================

@api_router.get("/users")
async def list_users(current_user: dict = Depends(require_roles("admin", "manager"))):
    users = await db.users.find({}, {"password_hash": 0}).to_list(100)
    for u in users:
        u["_id"] = str(u["_id"])
        u["id"] = u.pop("_id")
    return users

@api_router.put("/users/{user_id}")
async def update_user(user_id: str, update: UserUpdate, current_user: dict = Depends(require_roles("admin"))):
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if "role" in update_data and update_data["role"] not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if "department" in update_data and update_data["department"] not in VALID_DEPARTMENTS:
        raise HTTPException(status_code=400, detail="Invalid department")
    result = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User updated"}

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(require_roles("admin"))):
    if current_user["_id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    result = await db.users.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}

# ==================== PROPERTY MANAGEMENT ROUTES ====================

@api_router.get("/properties")
async def list_properties(request: Request):
    """List all properties"""
    current_user = await get_current_user(request)
    properties = await db.properties.find({}, {"_id": 0}).to_list(100)
    if not properties:
        # Seed a default property if none exist
        default_prop = {
            "id": "default",
            "name": "My Hotel",
            "address": "",
            "city": "",
            "country": "",
            "property_type": "hotel",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.properties.insert_one(default_prop)
        properties = [default_prop]
    return [{k: v for k, v in p.items() if k != "_id"} for p in properties]

@api_router.post("/properties")
async def create_property(prop: PropertyCreate, current_user: dict = Depends(require_roles("admin"))):
    """Create a new property (admin only)"""
    if prop.property_type not in VALID_PROPERTY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid property type. Must be one of: {', '.join(VALID_PROPERTY_TYPES)}")
    new_prop = Property(**prop.model_dump())
    doc = new_prop.model_dump()
    await db.properties.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.put("/properties/{property_id}")
async def update_property(property_id: str, update: PropertyUpdate, current_user: dict = Depends(require_roles("admin"))):
    """Update a property (admin only)"""
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if "property_type" in update_data and update_data["property_type"] not in VALID_PROPERTY_TYPES:
        raise HTTPException(status_code=400, detail="Invalid property type")
    result = await db.properties.update_one({"id": property_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Property not found")
    updated = await db.properties.find_one({"id": property_id}, {"_id": 0})
    return updated

@api_router.delete("/properties/{property_id}")
async def delete_property(property_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Delete a property (admin only)"""
    if property_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default property")
    result = await db.properties.delete_one({"id": property_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Property not found")
    return {"message": "Property deleted"}

@api_router.get("/roles")
async def get_roles():
    return {
        "roles": [
            {"id": "admin", "name": "Admin", "description": "Full access, manage users and settings"},
            {"id": "manager", "name": "Manager", "description": "Approve/reject responses, view analytics"},
            {"id": "receptionist", "name": "Receptionist", "description": "Draft responses, submit for approval"}
        ],
        "departments": [
            {"id": "front_desk", "name": "Front Desk"},
            {"id": "management", "name": "Management"},
            {"id": "housekeeping", "name": "Housekeeping"},
            {"id": "food_beverage", "name": "Food & Beverage"},
            {"id": "maintenance", "name": "Maintenance"},
            {"id": "spa_wellness", "name": "Spa & Wellness"},
            {"id": "concierge", "name": "Concierge"}
        ]
    }

# ==================== API CONNECTION ROUTES ====================

@api_router.get("/api-keys")
async def list_api_keys(current_user: dict = Depends(require_roles("admin"))):
    """List all API keys"""
    keys = await db.api_keys.find({}, {"_id": 0}).to_list(50)
    # Mask the key value for security
    for k in keys:
        if k.get("key"):
            k["key_masked"] = k["key"][:8] + "..." + k["key"][-4:]
    return keys

@api_router.post("/api-keys")
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

@api_router.delete("/api-keys/{key_id}")
async def delete_api_key(key_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Delete an API key"""
    result = await db.api_keys.delete_one({"id": key_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"message": "API key deleted"}

# ==================== WEBHOOK ROUTES ====================

@api_router.get("/webhooks")
async def list_webhooks(current_user: dict = Depends(require_roles("admin", "manager"))):
    """List all webhook configurations"""
    webhooks = await db.webhooks.find({}, {"_id": 0}).to_list(50)
    return webhooks

@api_router.post("/webhooks")
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

@api_router.put("/webhooks/{webhook_id}")
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

@api_router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Delete a webhook"""
    result = await db.webhooks.delete_one({"id": webhook_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"message": "Webhook deleted"}

@api_router.post("/webhooks/{webhook_id}/test")
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

@api_router.get("/webhooks/{webhook_id}/deliveries")
async def get_webhook_deliveries(webhook_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Get delivery log for a webhook (last 20)"""
    webhook = await db.webhooks.find_one({"id": webhook_id}, {"_id": 0})
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    deliveries = await db.webhook_deliveries.find(
        {"webhook_id": webhook_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(20)
    return deliveries

@api_router.get("/webhooks/events")
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

@api_router.get("/integration-guide")
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

# ==================== WIDGET API (API Key Auth) ====================

@api_router.get("/widget/reviews")
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

@api_router.get("/widget/reviews/new")
async def widget_new_reviews(request: Request, key_doc: dict = Depends(verify_api_key)):
    """Get reviews created after a given timestamp (for polling)"""
    property_id = request.query_params.get("property_id", "default")
    since = request.query_params.get("since")
    if not since:
        return []
    query = {"property_id": property_id, "created_at": {"$gt": since}}
    reviews = await db.reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(10)
    return reviews

@api_router.get("/widget/stats")
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

@api_router.get("/widget/unread-count")
async def widget_unread_count(request: Request, key_doc: dict = Depends(verify_api_key)):
    """Get count of unread reviews"""
    property_id = request.query_params.get("property_id", "default")
    count = await db.reviews.count_documents({"property_id": property_id, "is_read": {"$ne": True}})
    return {"unread": count}

@api_router.put("/widget/reviews/{review_id}/read")
async def widget_mark_read(review_id: str, key_doc: dict = Depends(verify_api_key)):
    """Mark a review as read"""
    result = await db.reviews.update_one({"id": review_id}, {"$set": {"is_read": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"ok": True}

@api_router.put("/widget/reviews/mark-all-read")
async def widget_mark_all_read(request: Request, key_doc: dict = Depends(verify_api_key)):
    """Mark all reviews as read for a property"""
    property_id = request.query_params.get("property_id", "default")
    result = await db.reviews.update_many(
        {"property_id": property_id, "is_read": {"$ne": True}},
        {"$set": {"is_read": True}}
    )
    return {"marked": result.modified_count}

@api_router.post("/widget/generate-response")
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
        chat = LlmChat(api_key=api_key, model="gpt-5.2")
        response = chat.send_message(UserMessage(content=prompt))
        response_text = response.content.strip()
        
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

@api_router.post("/reviews/{review_id}/submit-for-approval")
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

@api_router.post("/reviews/{review_id}/approve")
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

@api_router.get("/reviews/pending-approval")
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

@api_router.get("/")
async def root():
    return {"message": "Hotel Review Management API"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks

# ==================== REVIEW ROUTES ====================

@api_router.get("/reviews", response_model=List[Review])
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

@api_router.get("/reviews/{review_id}", response_model=Review)
async def get_review(review_id: str):
    """Get a single review by ID"""
    review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    deserialize_review(review)
    return review

@api_router.post("/reviews", response_model=Review)
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

@api_router.put("/reviews/{review_id}/respond", response_model=Review)
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
            await _log_sync(platform, "outbound", "skipped", f"No credentials configured for {platform}", review_id)
            return
        
        success = False
        if platform == "google":
            location_id = integration.get("location_id")
            if location_id:
                success = await PlatformService.post_google_reply(location_id, external_review_id, reply_text)
        
        if success:
            await db.reviews.update_one({"id": review_id}, {"$set": {"synced_to_platform": True, "sync_date": datetime.now(timezone.utc).isoformat()}})
            await _log_sync(platform, "outbound", "success", f"Reply posted to {platform}", review_id)
        else:
            await _log_sync(platform, "outbound", "skipped", f"Outbound sync to {platform} not yet supported or failed", review_id)
    except Exception as e:
        logger.error(f"Outbound sync error for {platform}: {e}")
        await _log_sync(platform, "outbound", "error", str(e)[:200], review_id)

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

@api_router.post("/reviews/generate-ai-response", response_model=AIGenerateResponse)
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

@api_router.post("/reviews/{review_id}/detect-language")
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

@api_router.post("/reviews/translate")
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

@api_router.get("/languages")
async def get_languages():
    """Get supported languages"""
    return [{"code": k, "name": v} for k, v in SUPPORTED_LANGUAGES.items()]

@api_router.get("/reviews/stats/summary")
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

@api_router.post("/reviews/seed")
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

@api_router.delete("/reviews/clear")
async def clear_reviews():
    """Clear all reviews (for testing)"""
    result = await db.reviews.delete_many({})
    return {"message": f"Deleted {result.deleted_count} reviews"}

# ==================== NOTIFICATION SETTINGS ROUTES ====================

@api_router.get("/notifications/settings")
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

@api_router.put("/notifications/settings")
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

@api_router.get("/notifications/log")
async def get_notification_log():
    """Get notification history"""
    logs = await db.notification_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return logs

@api_router.post("/notifications/test")
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

@api_router.get("/templates", response_model=List[ResponseTemplate])
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

@api_router.get("/templates/{template_id}", response_model=ResponseTemplate)
async def get_template(template_id: str):
    """Get a single template by ID"""
    template = await db.response_templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if isinstance(template.get('created_at'), str):
        template['created_at'] = datetime.fromisoformat(template['created_at'])
    return template

@api_router.post("/templates", response_model=ResponseTemplate)
async def create_template(input: ResponseTemplateCreate):
    """Create a new response template"""
    template = ResponseTemplate(**input.model_dump())
    doc = template.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.response_templates.insert_one(doc)
    return template

@api_router.put("/templates/{template_id}", response_model=ResponseTemplate)
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

@api_router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete a template"""
    result = await db.response_templates.delete_one({"id": template_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted"}

@api_router.post("/templates/{template_id}/use")
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

@api_router.post("/templates/seed")
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

@api_router.post("/reviews/{review_id}/analyze")
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

@api_router.post("/reviews/analyze-batch")
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

@api_router.get("/analytics/dashboard")
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

@api_router.get("/competitors")
async def get_competitors():
    """Get all competitor data"""
    competitors = await db.competitors.find({}, {"_id": 0}).to_list(100)
    for comp in competitors:
        if isinstance(comp.get('last_updated'), str):
            comp['last_updated'] = datetime.fromisoformat(comp['last_updated'])
    return competitors

@api_router.post("/competitors")
async def add_competitor(input: CompetitorCreate):
    """Add a competitor for benchmarking"""
    competitor = CompetitorData(**input.model_dump())
    doc = competitor.model_dump()
    doc['last_updated'] = doc['last_updated'].isoformat()
    await db.competitors.insert_one(doc)
    return competitor

@api_router.put("/competitors/{competitor_id}")
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

@api_router.delete("/competitors/{competitor_id}")
async def delete_competitor(competitor_id: str):
    """Delete a competitor"""
    result = await db.competitors.delete_one({"id": competitor_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Competitor not found")
    return {"message": "Competitor deleted"}

@api_router.get("/competitors/benchmark")
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

@api_router.post("/competitors/seed")
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
    our_stats = await get_review_stats_internal()
    
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

@api_router.get("/reports/settings")
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

@api_router.put("/reports/settings")
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

@api_router.post("/reports/send-now")
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

@api_router.get("/reports/preview")
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

@api_router.get("/reports/log")
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

@api_router.get("/branding")
async def get_branding():
    """Get current branding settings"""
    branding = await db.branding_settings.find_one({}, {"_id": 0})
    if not branding:
        branding = {
            "app_name": "Review Hub",
            "subtitle": "Manage all your guest reviews in one place",
            "primary_color": "#3E5245",
            "accent_color": "#D4A373",
            "logo_url": None,
            "powered_by_text": "",
            "powered_by_visible": False
        }
    if "updated_at" in branding and isinstance(branding["updated_at"], datetime):
        branding["updated_at"] = branding["updated_at"].isoformat()
    return branding

@api_router.put("/branding")
async def update_branding(settings: BrandingSettingsUpdate):
    """Update branding settings"""
    existing = await db.branding_settings.find_one({}, {"_id": 0})
    update_data = {k: v for k, v in settings.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    if existing:
        await db.branding_settings.update_one({}, {"$set": update_data})
    else:
        new_settings = {
            "app_name": "Review Hub",
            "subtitle": "Manage all your guest reviews in one place",
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

@api_router.post("/branding/logo")
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
            "app_name": "Review Hub",
            "subtitle": "Manage all your guest reviews in one place",
            "primary_color": "#3E5245",
            "accent_color": "#D4A373",
            "logo_url": logo_url,
            "powered_by_text": "",
            "powered_by_visible": False,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {"logo_url": logo_url}

@api_router.delete("/branding/logo")
async def delete_logo():
    """Remove the custom logo"""
    await db.branding_settings.update_one({}, {"$set": {"logo_url": None, "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"message": "Logo removed"}

# ==================== PLATFORM INTEGRATION ROUTES ====================

@api_router.get("/integrations")
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

@api_router.put("/integrations/{platform}/configure")
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

@api_router.post("/integrations/{platform}/test-connection")
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

@api_router.post("/integrations/{platform}/sync")
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

@api_router.post("/integrations/{platform}/post-reply")
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
        await _log_sync(platform, "outbound", "skipped", f"Reply saved locally — {platform} credentials not configured", review_id)
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
        await _log_sync(platform, "outbound", "success", f"Reply posted to {platform} for review {review_id}", review_id)
        # Fire response.published webhook
        asyncio.create_task(_fire_webhooks("response.published", {
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
        await _log_sync(platform, "outbound", "error" if error_msg else "skipped", error_msg or f"Reply saved locally for {platform}", review_id)
    
    return {
        "status": "synced" if success else "logged",
        "message": f"Reply {'posted to ' + platform if success else 'saved locally' + (': ' + error_msg if error_msg else '')}",
        "synced_to_platform": success,
        "error": error_msg if not success else None
    }

@api_router.get("/integrations/outbound-status")
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

@api_router.post("/integrations/sync-all-outbound")
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

@api_router.post("/integrations/import")
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

@api_router.post("/integrations/import-csv")
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

@api_router.get("/integrations/requirements")
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

@api_router.post("/platforms/{platform}/incoming")
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
        await _log_sync(platform, "inbound", "skipped", "Duplicate review", payload.external_review_id)
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
    
    await _log_sync(platform, "inbound", "success", f"Review from {payload.guest_name}", payload.external_review_id)
    
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
    await _fire_webhooks("review.created", doc)
    
    return {"status": "created", "review_id": doc["id"], "message": "Review received successfully"}

@api_router.post("/platforms/{platform}/incoming/batch")
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
    
    await _log_sync(platform, "inbound_batch", "success", f"Created {created}, skipped {skipped}")
    return {"status": "success", "created": created, "skipped": skipped}

@api_router.get("/platforms/{platform}/inbound-url")
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

async def _log_sync(platform: str, direction: str, status: str, message: str = "", ref_id: str = ""):
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

async def _fire_webhooks(event: str, data: dict):
    """Fire active webhooks for an event"""
    clean_data = {k: v for k, v in data.items() if k != "_id"}
    webhooks = await db.webhooks.find({"is_active": True}, {"_id": 0}).to_list(50)
    for wh in webhooks:
        if wh.get("events") and event not in wh["events"]:
            continue
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                await c.post(wh["url"], json={"event": event, "data": clean_data, "timestamp": datetime.now(timezone.utc).isoformat()},
                    headers={"X-Webhook-Secret": wh.get("secret", ""), "X-Webhook-Event": event})
            await db.webhook_deliveries.insert_one({
                "id": str(uuid.uuid4()), "webhook_id": wh["id"], "event": event,
                "url": wh["url"], "status_code": 200, "success": True,
                "response_time_ms": 0, "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception:
            pass

@api_router.get("/sync-logs")
async def get_sync_logs(request: Request, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Get sync activity log"""
    platform = request.query_params.get("platform")
    limit = min(int(request.query_params.get("limit", "50")), 100)
    query = {"platform": platform} if platform else {}
    logs = await db.sync_logs.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return logs

# ==================== P1: PROPERTY MAPPING ====================

@api_router.put("/properties/{property_id}/mapping")
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

@api_router.get("/properties/by-external/{external_id}")
async def get_property_by_external_id(external_id: str):
    """Lookup a property by its external system ID (for incoming webhooks)"""
    prop = await db.properties.find_one({"external_id": external_id}, {"_id": 0})
    if not prop:
        raise HTTPException(status_code=404, detail="No property mapped to this external ID")
    return prop

# ==================== BOOKING ENGINE ROUTES ====================

# --- Template Customization ---

# ==================== AMENITY & FACILITY CATALOGS ====================

@api_router.get("/amenities/catalog")
async def get_amenity_catalog():
    """Public: Get the full categorized amenity catalog"""
    return AMENITY_CATALOG

@api_router.get("/facilities/catalog")
async def get_facility_catalog():
    """Public: Get the full categorized facility catalog"""
    return FACILITY_CATALOG

# ==================== PROPERTY FACILITIES ====================

@api_router.get("/property-facilities/{property_id}")
async def get_property_facilities(property_id: str):
    """Public: Get property facilities"""
    doc = await db.property_facilities.find_one({"property_id": property_id}, {"_id": 0})
    return doc or {"property_id": property_id, "facilities": []}

@api_router.put("/property-facilities/{property_id}")
async def save_property_facilities(property_id: str, facilities: List[str], current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: Save property facilities"""
    existing = await db.property_facilities.find_one({"property_id": property_id})
    data = {"facilities": facilities, "updated_at": datetime.now(timezone.utc).isoformat()}
    if existing:
        await db.property_facilities.update_one({"property_id": property_id}, {"$set": data})
    else:
        data["property_id"] = property_id
        data["id"] = str(uuid.uuid4())
        await db.property_facilities.insert_one(data)
    result = await db.property_facilities.find_one({"property_id": property_id}, {"_id": 0})
    return result

# ==================== HOTEL POLICIES ====================

@api_router.get("/hotel-policies/{property_id}")
async def get_hotel_policies(property_id: str):
    """Public: Get hotel policies"""
    doc = await db.hotel_policies.find_one({"property_id": property_id}, {"_id": 0})
    if doc:
        return doc
    return HotelPolicies(property_id=property_id).model_dump()

@api_router.put("/hotel-policies/{property_id}")
async def save_hotel_policies(property_id: str, update: HotelPoliciesUpdate, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: Save hotel policies"""
    existing = await db.hotel_policies.find_one({"property_id": property_id})
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    if existing:
        await db.hotel_policies.update_one({"property_id": property_id}, {"$set": update_data})
    else:
        pol = HotelPolicies(property_id=property_id, **update_data)
        doc = pol.model_dump()
        await db.hotel_policies.insert_one(doc)
        doc.pop("_id", None)
    result = await db.hotel_policies.find_one({"property_id": property_id}, {"_id": 0})
    return result

# ==================== PROMO CODES ====================

@api_router.get("/promo-codes")
async def list_promo_codes(property_id: str = "", current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: List promo codes"""
    q = {"property_id": property_id} if property_id else {}
    codes = await db.promo_codes.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    return codes

@api_router.post("/promo-codes")
async def create_promo_code(data: PromoCodeCreate, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: Create promo code"""
    existing = await db.promo_codes.find_one({"code": data.code.upper()})
    if existing:
        raise HTTPException(status_code=400, detail="Promo code already exists")
    promo_data = data.model_dump()
    promo_data["code"] = data.code.upper()
    promo = PromoCode(**promo_data)
    doc = promo.model_dump()
    await db.promo_codes.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.delete("/promo-codes/{code_id}")
async def delete_promo_code(code_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Admin: Delete promo code"""
    await db.promo_codes.delete_one({"id": code_id})
    return {"status": "deleted"}

@api_router.put("/promo-codes/{code_id}/toggle")
async def toggle_promo_code(code_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: Toggle promo code active status"""
    code = await db.promo_codes.find_one({"id": code_id})
    if not code:
        raise HTTPException(status_code=404, detail="Promo code not found")
    new_status = not code.get("is_active", True)
    await db.promo_codes.update_one({"id": code_id}, {"$set": {"is_active": new_status}})
    return {"is_active": new_status}

@api_router.post("/promo-codes/validate")
async def validate_promo_code(code: str, property_id: str = "", nights: int = 1, subtotal: float = 0):
    """Public: Validate a promo code"""
    promo = await db.promo_codes.find_one({"code": code.upper(), "is_active": True}, {"_id": 0})
    if not promo:
        raise HTTPException(status_code=404, detail="Invalid or expired promo code")
    if promo.get("property_id") and promo["property_id"] != property_id:
        raise HTTPException(status_code=400, detail="This code is not valid for this property")
    if promo.get("max_uses") and promo.get("used_count", 0) >= promo["max_uses"]:
        raise HTTPException(status_code=400, detail="This code has reached its usage limit")
    if promo.get("min_nights") and nights < promo["min_nights"]:
        raise HTTPException(status_code=400, detail=f"Minimum {promo['min_nights']} nights required")
    if promo.get("min_amount") and subtotal < promo["min_amount"]:
        raise HTTPException(status_code=400, detail=f"Minimum spend of {promo['min_amount']} required")
    now = datetime.now(timezone.utc).isoformat()
    if promo.get("valid_from") and now < promo["valid_from"]:
        raise HTTPException(status_code=400, detail="This code is not yet active")
    if promo.get("valid_until") and now > promo["valid_until"]:
        raise HTTPException(status_code=400, detail="This code has expired")
    discount = promo["discount_value"] if promo["discount_type"] == "fixed" else round(subtotal * promo["discount_value"] / 100, 2)
    return {
        "valid": True,
        "code": promo["code"],
        "description": promo.get("description", ""),
        "discount_type": promo["discount_type"],
        "discount_value": promo["discount_value"],
        "discount_amount": min(discount, subtotal),
    }

# ==================== ADD-ON SERVICES ====================

@api_router.get("/add-ons/{property_id}")
async def get_add_ons(property_id: str):
    """Public: Get add-on services for a property"""
    addons = await db.add_on_services.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(50)
    return addons

@api_router.get("/add-ons")
async def list_all_add_ons(property_id: str = "", current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: List all add-ons"""
    q = {"property_id": property_id} if property_id else {}
    addons = await db.add_on_services.find(q, {"_id": 0}).to_list(200)
    return addons

@api_router.post("/add-ons")
async def create_add_on(data: AddOnServiceCreate, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: Create add-on service"""
    addon = AddOnService(**data.model_dump())
    doc = addon.model_dump()
    await db.add_on_services.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.delete("/add-ons/{addon_id}")
async def delete_add_on(addon_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Admin: Delete add-on service"""
    await db.add_on_services.delete_one({"id": addon_id})
    return {"status": "deleted"}

@api_router.put("/add-ons/{addon_id}/toggle")
async def toggle_add_on(addon_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: Toggle add-on active status"""
    addon = await db.add_on_services.find_one({"id": addon_id})
    if not addon:
        raise HTTPException(status_code=404, detail="Add-on not found")
    new_status = not addon.get("is_active", True)
    await db.add_on_services.update_one({"id": addon_id}, {"$set": {"is_active": new_status}})
    return {"is_active": new_status}

# --- Translations ---

class TranslationOverride(BaseModel):
    property_id: str
    lang_code: str
    overrides: Dict[str, str] = {}

@api_router.get("/translations/{property_id}/{lang_code}")
async def get_property_translations(property_id: str, lang_code: str):
    """Public: Get custom translation overrides for a property and language"""
    doc = await db.translation_overrides.find_one(
        {"property_id": property_id, "lang_code": lang_code}, {"_id": 0}
    )
    return doc or {"property_id": property_id, "lang_code": lang_code, "overrides": {}}

@api_router.put("/translations/{property_id}/{lang_code}")
async def save_property_translations(
    property_id: str, lang_code: str,
    overrides: Dict[str, str],
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Admin: Save custom translation overrides for a property"""
    await db.translation_overrides.update_one(
        {"property_id": property_id, "lang_code": lang_code},
        {"$set": {
            "property_id": property_id,
            "lang_code": lang_code,
            "overrides": overrides,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True
    )
    doc = await db.translation_overrides.find_one(
        {"property_id": property_id, "lang_code": lang_code}, {"_id": 0}
    )
    return doc

@api_router.get("/translations/{property_id}")
async def list_property_translations(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: List all translation overrides for a property"""
    docs = await db.translation_overrides.find({"property_id": property_id}, {"_id": 0}).to_list(20)
    return docs

@api_router.post("/translations/ai-translate")
async def ai_translate_text(
    texts: Dict[str, str],
    target_lang: str,
    current_user: dict = Depends(require_roles("admin", "manager"))
):
    """Admin: AI-translate custom hotel texts to target language"""
    try:
        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key:
            raise HTTPException(status_code=500, detail="LLM key not configured")
        chat = LlmChat(emergent_api_key=llm_key, model="gpt-5.2")
        text_list = "\n".join([f"- {k}: {v}" for k, v in texts.items()])
        prompt = f"Translate the following hotel/booking texts to {target_lang}. Return ONLY a JSON object with the same keys and translated values. No explanation.\n\n{text_list}"
        response = await chat.send_message(UserMessage(content=prompt))
        import json
        try:
            translated = json.loads(response.content.strip().strip("```json").strip("```"))
        except Exception:
            translated = {}
        return {"translations": translated, "target_lang": target_lang}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

# --- Upsell Items ---

@api_router.get("/upsell-templates")
async def get_upsell_templates():
    """Get predefined upsell templates for quick setup"""
    from models import UPSELL_TEMPLATES
    return UPSELL_TEMPLATES

@api_router.get("/upsells/{property_id}")
async def get_upsells(property_id: str):
    """Public: Get active upsell items for a property"""
    items = await db.upsell_items.find(
        {"property_id": property_id, "is_active": True}, {"_id": 0}
    ).sort("sort_order", 1).to_list(50)
    return items

@api_router.get("/upsells/admin/{property_id}")
async def get_all_upsells(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: Get all upsell items including inactive"""
    items = await db.upsell_items.find({"property_id": property_id}, {"_id": 0}).sort("sort_order", 1).to_list(50)
    return items

@api_router.post("/upsells")
async def create_upsell(data: UpsellItemCreate, current_user: dict = Depends(require_roles("admin", "manager"))):
    from models import UpsellItem
    item = UpsellItem(**data.model_dump())
    doc = item.model_dump()
    await db.upsell_items.insert_one(doc)
    del doc["_id"]
    return doc

@api_router.put("/upsells/{upsell_id}")
async def update_upsell(upsell_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
    updates.pop("_id", None)
    updates.pop("id", None)
    await db.upsell_items.update_one({"id": upsell_id}, {"$set": updates})
    doc = await db.upsell_items.find_one({"id": upsell_id}, {"_id": 0})
    return doc

@api_router.delete("/upsells/{upsell_id}")
async def delete_upsell(upsell_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
    await db.upsell_items.delete_one({"id": upsell_id})
    return {"status": "deleted"}

@api_router.post("/upsells/seed/{property_id}")
async def seed_upsells(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Seed default upsell items from templates"""
    from models import UPSELL_TEMPLATES, UpsellItem
    existing = await db.upsell_items.count_documents({"property_id": property_id})
    if existing > 0:
        return {"message": f"Property already has {existing} upsells", "count": existing}
    items = []
    for i, tmpl in enumerate(UPSELL_TEMPLATES):
        item = UpsellItem(property_id=property_id, sort_order=i, **tmpl)
        doc = item.model_dump()
        items.append(doc)
    if items:
        await db.upsell_items.insert_many(items)
        for item in items:
            item.pop("_id", None)
    return {"message": f"Seeded {len(items)} upsell items", "items": items}

# --- Social Proof & Price Comparison ---

@api_router.get("/social-proof/{property_id}")
async def get_social_proof_data(property_id: str):
    """Public: Get social proof data for booking page"""
    # Get recent bookings count (last 24h)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent_bookings = await db.bookings.count_documents({
        "property_id": property_id,
        "created_at": {"$gte": cutoff}
    })
    # Get total bookings this month
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0).isoformat()
    monthly_bookings = await db.bookings.count_documents({
        "property_id": property_id,
        "created_at": {"$gte": month_start}
    })
    # Get settings
    settings = await db.social_proof_settings.find_one({"property_id": property_id}, {"_id": 0})
    if not settings:
        from models import SocialProofSettings
        settings = SocialProofSettings(property_id=property_id).model_dump()

    return {
        "recent_bookings_24h": recent_bookings,
        "monthly_bookings": monthly_bookings,
        "settings": settings
    }

@api_router.get("/social-proof/settings/{property_id}")
async def get_social_proof_settings(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
    settings = await db.social_proof_settings.find_one({"property_id": property_id}, {"_id": 0})
    if not settings:
        from models import SocialProofSettings
        settings = SocialProofSettings(property_id=property_id).model_dump()
    return settings

@api_router.put("/social-proof/settings/{property_id}")
async def update_social_proof_settings(property_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
    updates.pop("_id", None)
    updates["property_id"] = property_id
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.social_proof_settings.update_one(
        {"property_id": property_id}, {"$set": updates}, upsert=True
    )
    doc = await db.social_proof_settings.find_one({"property_id": property_id}, {"_id": 0})
    return doc

# --- Template Settings ---

@api_router.get("/template-settings/{property_id}")
async def get_template_settings(property_id: str):
    """Public endpoint: Get template customization settings for a property"""
    settings = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0})
    return settings or {"property_id": property_id, "template_id": "booking-classic"}

@api_router.get("/template-settings")
async def list_all_template_settings(current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: List all template settings"""
    settings = await db.template_settings.find({}, {"_id": 0}).to_list(100)
    return settings

@api_router.put("/template-settings/{property_id}")
async def save_template_settings(property_id: str, update: TemplateSettingsUpdate, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Admin: Save template customization for a property (upsert)"""
    existing = await db.template_settings.find_one({"property_id": property_id})
    
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    if existing:
        await db.template_settings.update_one({"property_id": property_id}, {"$set": update_data})
    else:
        new_settings = TemplateSettings(property_id=property_id, **update_data)
        doc = new_settings.model_dump()
        await db.template_settings.insert_one(doc)
        doc.pop("_id", None)
    
    result = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0})
    return result

@api_router.delete("/template-settings/{property_id}")
async def delete_template_settings(property_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Admin: Reset template settings for a property"""
    await db.template_settings.delete_one({"property_id": property_id})
    return {"status": "deleted"}

@api_router.get("/booking/property/{property_id}")
async def get_booking_property_info(property_id: str):
    """Public endpoint: Get property info for booking engine"""
    prop = await db.properties.find_one({"id": property_id, "is_active": True}, {"_id": 0})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Get property branding
    branding = await db.branding_settings.find_one({}, {"_id": 0}) or {}
    
    # Get template customization
    template_settings = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
    
    # Get property facilities
    facilities_doc = await db.property_facilities.find_one({"property_id": property_id}, {"_id": 0})
    facilities = facilities_doc.get("facilities", []) if facilities_doc else []
    
    # Get hotel policies
    policies = await db.hotel_policies.find_one({"property_id": property_id}, {"_id": 0})
    if not policies:
        policies = HotelPolicies(property_id=property_id).model_dump()
    
    # Get add-on services
    add_ons = await db.add_on_services.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(50)
    
    # Get upsell items
    upsells = await db.upsell_items.find({"property_id": property_id, "is_active": True}, {"_id": 0}).sort("sort_order", 1).to_list(50)
    
    # Get social proof settings
    sp_settings = await db.social_proof_settings.find_one({"property_id": property_id}, {"_id": 0})
    if not sp_settings:
        sp_settings = SocialProofSettings(property_id=property_id).model_dump()
    
    # Get recent booking count for social proof
    cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent_bookings = await db.bookings.count_documents({"property_id": property_id, "created_at": {"$gte": cutoff_24h}})
    
    # Get average rating from reviews
    reviews = await db.reviews.find({"property_id": property_id}, {"_id": 0, "rating": 1}).to_list(1000)
    if not reviews:
        reviews = await db.reviews.find({}, {"_id": 0, "rating": 1}).to_list(1000)
    
    avg_rating = sum(r.get("rating", 0) for r in reviews) / len(reviews) if reviews else 0
    total_reviews = len(reviews)
    
    # Get room types
    rooms = await db.room_types.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(50)
    
    return {
        **prop,
        "branding": branding,
        "template_settings": template_settings,
        "facilities": facilities,
        "policies": policies,
        "add_ons": add_ons,
        "upsells": upsells,
        "social_proof": {
            "settings": sp_settings,
            "recent_bookings_24h": recent_bookings,
        },
        "avg_rating": round(avg_rating, 1),
        "total_reviews": total_reviews,
        "room_types": rooms
    }

@api_router.get("/booking/rooms/{property_id}")
async def get_booking_rooms(property_id: str, check_in: str = "", check_out: str = "", adults: int = 2, children: int = 0):
    """Public endpoint: Get available room types for a property"""
    rooms = await db.room_types.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(50)
    
    if check_in and check_out:
        # Check availability for each room type
        for room in rooms:
            bookings_count = await db.bookings.count_documents({
                "room_type_id": room["id"],
                "status": {"$nin": ["cancelled"]},
                "$or": [
                    {"check_in": {"$lt": check_out}, "check_out": {"$gt": check_in}}
                ]
            })
            room["available_rooms"] = max(0, room.get("total_rooms", 1) - bookings_count)
            room["is_available"] = room["available_rooms"] > 0
    else:
        for room in rooms:
            room["available_rooms"] = room.get("total_rooms", 1)
            room["is_available"] = True
    
    return rooms

@api_router.get("/booking/availability/{property_id}")
async def check_availability(property_id: str, check_in: str = "", check_out: str = ""):
    """Public endpoint: Check property availability summary"""
    rooms = await db.room_types.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(50)
    
    available_rooms = []
    for room in rooms:
        if check_in and check_out:
            bookings_count = await db.bookings.count_documents({
                "room_type_id": room["id"],
                "status": {"$nin": ["cancelled"]},
                "$or": [
                    {"check_in": {"$lt": check_out}, "check_out": {"$gt": check_in}}
                ]
            })
            avail = max(0, room.get("total_rooms", 1) - bookings_count)
        else:
            avail = room.get("total_rooms", 1)
        
        available_rooms.append({
            "room_type_id": room["id"],
            "name": room["name"],
            "available": avail,
            "total": room.get("total_rooms", 1),
            "base_price": room.get("base_price", 0)
        })
    
    return {"property_id": property_id, "rooms": available_rooms}

@api_router.post("/booking/reserve")
async def create_booking(booking_data: BookingCreate):
    """Public endpoint: Create a new booking reservation"""
    # Validate room type exists
    room = await db.room_types.find_one({"id": booking_data.room_type_id, "is_active": True}, {"_id": 0})
    if not room:
        raise HTTPException(status_code=404, detail="Room type not found")
    
    # Check availability
    bookings_count = await db.bookings.count_documents({
        "room_type_id": booking_data.room_type_id,
        "status": {"$nin": ["cancelled"]},
        "$or": [
            {"check_in": {"$lt": booking_data.check_out}, "check_out": {"$gt": booking_data.check_in}}
        ]
    })
    
    available = max(0, room.get("total_rooms", 1) - bookings_count)
    if available < booking_data.rooms:
        raise HTTPException(status_code=400, detail="Not enough rooms available for the selected dates")
    
    # Calculate price
    try:
        ci = datetime.fromisoformat(booking_data.check_in)
        co = datetime.fromisoformat(booking_data.check_out)
        nights = max(1, (co - ci).days)
    except ValueError:
        nights = 1
    
    total_price = room.get("base_price", 0) * nights * booking_data.rooms
    
    booking = Booking(
        property_id=booking_data.property_id,
        room_type_id=booking_data.room_type_id,
        guest_name=booking_data.guest_name,
        guest_email=booking_data.guest_email,
        guest_phone=booking_data.guest_phone,
        check_in=booking_data.check_in,
        check_out=booking_data.check_out,
        adults=booking_data.adults,
        children=booking_data.children,
        rooms=booking_data.rooms,
        total_price=total_price,
        currency=room.get("currency", "GBP"),
        special_requests=booking_data.special_requests,
        status="confirmed",
        payment_status="pending"
    )
    
    doc = booking.model_dump()
    await db.bookings.insert_one(doc)
    doc.pop("_id", None)
    
    # Send confirmation email in background
    asyncio.create_task(_send_booking_confirmation(doc, room.get("name", "Room")))
    
    # Fire booking webhooks
    webhook_data = {
        "booking_ref": doc.get("booking_ref"),
        "property_id": doc.get("property_id"),
        "room_type_id": doc.get("room_type_id"),
        "room_name": room.get("name", ""),
        "guest_name": doc.get("guest_name"),
        "guest_email": doc.get("guest_email"),
        "check_in": doc.get("check_in"),
        "check_out": doc.get("check_out"),
        "adults": doc.get("adults"),
        "children": doc.get("children"),
        "rooms": doc.get("rooms"),
        "total_price": doc.get("total_price"),
        "currency": doc.get("currency"),
        "status": doc.get("status"),
        "payment_status": doc.get("payment_status"),
        "created_at": doc.get("created_at"),
    }
    asyncio.create_task(_fire_webhooks("booking.created", webhook_data))
    await _log_sync("booking-engine", "outbound", "success", f"Booking {doc.get('booking_ref')} created — webhook fired", doc.get("booking_ref", ""))
    
    return doc

async def _send_booking_confirmation(booking: dict, room_name: str):
    """Send booking confirmation email to guest"""
    if not resend.api_key:
        logger.info("No Resend API key, skipping booking confirmation email")
        return
    try:
        ci = datetime.fromisoformat(booking["check_in"]).strftime("%A, %d %B %Y") if booking.get("check_in") else booking.get("check_in", "")
        co = datetime.fromisoformat(booking["check_out"]).strftime("%A, %d %B %Y") if booking.get("check_out") else booking.get("check_out", "")
    except Exception:
        ci = booking.get("check_in", "")
        co = booking.get("check_out", "")
    
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">
      <div style="background:#003B95;color:#fff;padding:24px;text-align:center;">
        <h1 style="margin:0;font-size:24px;">Booking Confirmed</h1>
        <p style="margin:8px 0 0;opacity:0.8;">Thank you for your reservation</p>
      </div>
      <div style="padding:24px;">
        <div style="background:#F5F7FA;border-radius:8px;padding:20px;text-align:center;margin-bottom:20px;">
          <p style="margin:0;font-size:12px;color:#666;text-transform:uppercase;letter-spacing:1px;">Booking Reference</p>
          <p style="margin:8px 0 0;font-size:28px;font-weight:bold;color:#003B95;letter-spacing:2px;">{booking.get('booking_ref','')}</p>
        </div>
        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px 0;color:#666;font-size:14px;">Guest Name</td><td style="padding:8px 0;font-weight:600;font-size:14px;text-align:right;">{booking.get('guest_name','')}</td></tr>
          <tr><td style="padding:8px 0;color:#666;font-size:14px;">Room</td><td style="padding:8px 0;font-weight:600;font-size:14px;text-align:right;">{room_name}</td></tr>
          <tr><td style="padding:8px 0;color:#666;font-size:14px;">Check-in</td><td style="padding:8px 0;font-weight:600;font-size:14px;text-align:right;">{ci}</td></tr>
          <tr><td style="padding:8px 0;color:#666;font-size:14px;">Check-out</td><td style="padding:8px 0;font-weight:600;font-size:14px;text-align:right;">{co}</td></tr>
          <tr><td style="padding:8px 0;color:#666;font-size:14px;">Guests</td><td style="padding:8px 0;font-weight:600;font-size:14px;text-align:right;">{booking.get('adults',1)} adult(s){f", {booking.get('children',0)} child(ren)" if booking.get('children',0)>0 else ''}</td></tr>
          <tr style="border-top:2px solid #e5e7eb;"><td style="padding:12px 0;font-weight:700;font-size:16px;">Total</td><td style="padding:12px 0;font-weight:700;font-size:20px;text-align:right;">&pound;{booking.get('total_price',0):.0f}</td></tr>
        </table>
        {f'<div style="background:#F0FFF4;border:1px solid #C6F6D5;border-radius:8px;padding:12px;margin-top:16px;font-size:13px;color:#2F855A;">Special requests: {booking.get("special_requests","")}</div>' if booking.get("special_requests") else ''}
        <div style="margin-top:24px;padding:16px;background:#F5F7FA;border-radius:8px;text-align:center;font-size:12px;color:#666;">
          <p style="margin:0;">Powered by <strong>MyHotelBox</strong> Booking Engine</p>
          <p style="margin:4px 0 0;">If you have questions, please contact the property directly.</p>
        </div>
      </div>
    </div>
    """
    
    try:
        await asyncio.to_thread(resend.Emails.send, {
            "from": SENDER_EMAIL,
            "to": [booking.get("guest_email", "")],
            "subject": f"Booking Confirmed - {booking.get('booking_ref','')}",
            "html": html,
        })
        logger.info(f"Confirmation email sent for {booking.get('booking_ref','')}")
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {e}")

@api_router.get("/booking/reservation/{booking_ref}")
async def get_booking_by_ref(booking_ref: str):
    """Public endpoint: Get booking details by reference"""
    booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    room = await db.room_types.find_one({"id": booking["room_type_id"]}, {"_id": 0})
    prop = await db.properties.find_one({"id": booking["property_id"]}, {"_id": 0})
    
    return {**booking, "room_type": room, "property": prop}

@api_router.get("/booking/reviews/{property_id}")
async def get_booking_reviews(property_id: str, limit: int = 10):
    """Public endpoint: Get recent positive reviews for booking engine display"""
    reviews = await db.reviews.find(
        {"property_id": property_id, "rating": {"$gte": 3}},
        {"_id": 0, "id": 1, "guest_name": 1, "rating": 1, "review_text": 1, "platform": 1, "created_at": 1}
    ).sort("created_at", -1).to_list(limit)
    
    if not reviews:
        reviews = await db.reviews.find(
            {"rating": {"$gte": 3}},
            {"_id": 0, "id": 1, "guest_name": 1, "rating": 1, "review_text": 1, "platform": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(limit)
    
    return reviews

# Admin: Room Types CRUD
@api_router.post("/room-types")
async def create_room_type(room: RoomTypeCreate, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Create a new room type"""
    room_type = RoomType(**room.model_dump())
    doc = room_type.model_dump()
    await db.room_types.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/room-types")
async def list_room_types(property_id: str = ""):
    """List room types, optionally filtered by property"""
    query = {"property_id": property_id} if property_id else {}
    rooms = await db.room_types.find(query, {"_id": 0}).to_list(100)
    return rooms

@api_router.put("/room-types/{room_id}")
async def update_room_type(room_id: str, update: RoomTypeUpdate, current_user: dict = Depends(require_roles("admin", "manager"))):
    """Update a room type"""
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    result = await db.room_types.update_one({"id": room_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Room type not found")
    
    updated = await db.room_types.find_one({"id": room_id}, {"_id": 0})
    return updated

@api_router.delete("/room-types/{room_id}")
async def delete_room_type(room_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Delete a room type"""
    result = await db.room_types.delete_one({"id": room_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Room type not found")
    return {"status": "deleted"}

# Admin: Bookings management
@api_router.get("/bookings")
async def list_bookings(property_id: str = "", status: str = "", current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
    """List bookings with optional filters"""
    query = {}
    if property_id:
        query["property_id"] = property_id
    if status:
        query["status"] = status
    
    bookings = await db.bookings.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return bookings

@api_router.put("/bookings/{booking_id}/status")
async def update_booking_status(booking_id: str, status: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
    """Update booking status"""
    valid = ["confirmed", "cancelled", "checked_in", "checked_out", "no_show"]
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")
    
    result = await db.bookings.update_one({"id": booking_id}, {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    updated = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    
    # Fire webhooks for status changes
    wh_data = {
        "booking_ref": updated.get("booking_ref"),
        "property_id": updated.get("property_id"),
        "guest_name": updated.get("guest_name"),
        "guest_email": updated.get("guest_email"),
        "check_in": updated.get("check_in"),
        "check_out": updated.get("check_out"),
        "total_price": updated.get("total_price"),
        "currency": updated.get("currency"),
        "status": status,
        "updated_by": current_user.get("name", current_user.get("email")),
    }
    if status == "cancelled":
        asyncio.create_task(_fire_webhooks("booking.cancelled", wh_data))
        await _log_sync("booking-engine", "outbound", "success", f"Booking {updated.get('booking_ref')} cancelled — webhook fired", updated.get("booking_ref", ""))
    elif status == "confirmed":
        asyncio.create_task(_fire_webhooks("booking.confirmed", wh_data))
    
    return updated

# Include the router in the main app

# ==================== STRIPE PAYMENT ROUTES ====================

stripe_api_key = os.environ.get("STRIPE_API_KEY", "")

@api_router.post("/payments/create-checkout")
async def create_payment_checkout(request: Request, booking_id: str = "", origin_url: str = ""):
    """Create Stripe checkout session for a booking"""
    if not stripe_api_key:
        raise HTTPException(status_code=500, detail="Payment processing not configured")
    
    if not booking_id:
        raise HTTPException(status_code=400, detail="booking_id is required")
    
    # Get booking details
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="This booking has already been paid")
    
    # Get room type for description
    room = await db.room_types.find_one({"id": booking["room_type_id"]}, {"_id": 0})
    room_name = room["name"] if room else "Room"
    
    # Amount from server-side booking record (NOT from frontend)
    amount = float(booking.get("total_price", 0))
    currency = booking.get("currency", "GBP").lower()
    
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid booking amount")
    
    # Build URLs from provided origin
    if not origin_url:
        origin_url = str(request.base_url).rstrip("/")
    
    success_url = f"{origin_url}/book?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/book?payment=cancelled&booking_ref={booking.get('booking_ref', '')}"
    
    # Initialize Stripe
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    
    metadata = {
        "booking_id": booking_id,
        "booking_ref": booking.get("booking_ref", ""),
        "guest_name": booking.get("guest_name", ""),
        "guest_email": booking.get("guest_email", ""),
        "property_id": booking.get("property_id", ""),
        "room_type": room_name
    }
    
    checkout_request = CheckoutSessionRequest(
        amount=amount,
        currency=currency,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata
    )
    
    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
    
    # Create payment transaction record
    transaction = {
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "booking_id": booking_id,
        "booking_ref": booking.get("booking_ref", ""),
        "amount": amount,
        "currency": currency,
        "guest_email": booking.get("guest_email", ""),
        "guest_name": booking.get("guest_name", ""),
        "metadata": metadata,
        "payment_status": "pending",
        "status": "initiated",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payment_transactions.insert_one(transaction)
    
    # Update booking with session ID
    await db.bookings.update_one(
        {"id": booking_id},
        {"$set": {"stripe_session_id": session.session_id, "payment_status": "processing"}}
    )
    
    return {"url": session.url, "session_id": session.session_id}

@api_router.get("/payments/status/{session_id}")
async def get_payment_status(session_id: str, request: Request):
    """Check payment status for a checkout session"""
    if not stripe_api_key:
        raise HTTPException(status_code=500, detail="Payment processing not configured")
    
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    
    try:
        checkout_status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
    except Exception as e:
        logger.error(f"Stripe status check error: {e}")
        # Check if we have a local record
        existing = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if existing:
            return {
                "payment_status": existing.get("payment_status", "unknown"),
                "status": existing.get("status", "unknown"),
                "amount": existing.get("amount", 0),
                "currency": existing.get("currency", ""),
                "booking_ref": existing.get("booking_ref", ""),
                "booking_id": existing.get("booking_id", "")
            }
        raise HTTPException(status_code=404, detail="Payment session not found or expired")
    
    checkout_status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
    
    # Check if already processed to prevent double processing
    existing = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    
    if existing and existing.get("payment_status") == "paid":
        # Already processed, return cached status
        booking = await db.bookings.find_one({"stripe_session_id": session_id}, {"_id": 0})
        return {
            "payment_status": "paid",
            "status": checkout_status.status,
            "amount": checkout_status.amount_total,
            "currency": checkout_status.currency,
            "booking_ref": booking.get("booking_ref") if booking else "",
            "booking_id": existing.get("booking_id", "")
        }
    
    # Update transaction record
    update_data = {
        "payment_status": checkout_status.payment_status,
        "status": checkout_status.status,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": update_data}
    )
    
    # If paid, update the booking
    if checkout_status.payment_status == "paid":
        booking_id = existing.get("booking_id") if existing else checkout_status.metadata.get("booking_id")
        if booking_id:
            await db.bookings.update_one(
                {"id": booking_id},
                {"$set": {"payment_status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}}
            )
            # Fire payment webhook
            paid_booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
            if paid_booking:
                asyncio.create_task(_fire_webhooks("booking.payment_received", {
                    "booking_ref": paid_booking.get("booking_ref"),
                    "property_id": paid_booking.get("property_id"),
                    "guest_name": paid_booking.get("guest_name"),
                    "guest_email": paid_booking.get("guest_email"),
                    "total_price": paid_booking.get("total_price"),
                    "currency": paid_booking.get("currency"),
                    "payment_method": "stripe",
                    "paid_at": datetime.now(timezone.utc).isoformat(),
                }))
                await _log_sync("booking-engine", "outbound", "success", f"Payment received for {paid_booking.get('booking_ref')} — webhook fired", paid_booking.get("booking_ref", ""))
    elif checkout_status.status == "expired":
        booking_id = existing.get("booking_id") if existing else checkout_status.metadata.get("booking_id")
        if booking_id:
            await db.bookings.update_one(
                {"id": booking_id},
                {"$set": {"payment_status": "expired"}}
            )
    
    booking = await db.bookings.find_one({"stripe_session_id": session_id}, {"_id": 0})
    
    return {
        "payment_status": checkout_status.payment_status,
        "status": checkout_status.status,
        "amount": checkout_status.amount_total,
        "currency": checkout_status.currency,
        "booking_ref": booking.get("booking_ref") if booking else "",
        "booking_id": existing.get("booking_id") if existing else ""
    }

@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    try:
        body = await request.body()
        signature = request.headers.get("Stripe-Signature", "")
        
        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
        
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        
        if webhook_response.payment_status == "paid":
            # Update transaction
            await db.payment_transactions.update_one(
                {"session_id": webhook_response.session_id},
                {"$set": {"payment_status": "paid", "status": "complete", "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            # Update booking
            booking_id = webhook_response.metadata.get("booking_id", "")
            if booking_id:
                await db.bookings.update_one(
                    {"id": booking_id},
                    {"$set": {"payment_status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}}
                )
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return {"status": "error", "message": str(e)}
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def seed_myhotelbox_branches():
    """Seed all MyHotelBox branches as properties"""
    branches = [
        {"id": "aldgate-flats", "name": "ALDGATE FLATS", "property_type": "apartment", "external_id": "aldgate-flats-001", "external_name": "ALDGATE FLATS", "external_system": "myhotelbox"},
        {"id": "camden-suites", "name": "CAMDEN SUITES", "property_type": "apartment", "external_id": "camden-suites-001", "external_name": "CAMDEN SUITES", "external_system": "myhotelbox"},
        {"id": "city-gate", "name": "CITY GATE", "property_type": "hotel", "external_id": "city-gate-001", "external_name": "CITY GATE", "external_system": "myhotelbox"},
        {"id": "city-rooms", "name": "CITY ROOMS", "property_type": "hotel", "external_id": "city-rooms-001", "external_name": "CITY ROOMS", "external_system": "myhotelbox"},
        {"id": "london-suites", "name": "LONDON SUITES", "property_type": "apartment", "external_id": "london-suites-001", "external_name": "LONDON SUITES", "external_system": "myhotelbox"},
        {"id": "ryam-suites", "name": "Ryam Suites", "property_type": "apartment", "external_id": "ryam-suites-001", "external_name": "Ryam Suites", "external_system": "myhotelbox"},
        {"id": "whitechapel-hotel", "name": "THE WHITECHAPEL HOTEL", "property_type": "hotel", "external_id": "whitechapel-hotel-001", "external_name": "THE WHITECHAPEL HOTEL", "external_system": "myhotelbox"},
        {"id": "vilenza-hotel", "name": "VILENZA HOTEL", "property_type": "hotel", "external_id": "vilenza-hotel-001", "external_name": "VILENZA HOTEL", "external_system": "myhotelbox"},
        {"id": "whitechapel-grand", "name": "Whitechapel Grand", "property_type": "hotel", "external_id": "whitechapel-grand-001", "external_name": "Whitechapel Grand", "external_system": "myhotelbox"},
    ]
    for branch in branches:
        existing = await db.properties.find_one({"id": branch["id"]})
        if not existing:
            await db.properties.insert_one({
                **branch,
                "address": "", "city": "London", "country": "UK",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "mapping_updated_at": datetime.now(timezone.utc).isoformat()
            })
    logger.info("MyHotelBox branches seeded")

async def seed_sample_room_types():
    """Seed room types for ALL properties with multiple photos"""
    existing = await db.room_types.count_documents({})
    if existing > 0:
        return
    
    # Photo library
    photos = {
        "standard": [
            "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=800",
            "https://images.unsplash.com/photo-1629140727571-9b5c6f6267b4?w=800",
            "https://images.pexels.com/photos/97083/pexels-photo-97083.jpeg?w=800",
        ],
        "deluxe": [
            "https://images.unsplash.com/photo-1590490360182-c33d57733427?w=800",
            "https://images.unsplash.com/photo-1578683010236-d716f9a3f461?w=800",
            "https://images.pexels.com/photos/6466490/pexels-photo-6466490.jpeg?w=800",
        ],
        "suite": [
            "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=800",
            "https://images.unsplash.com/photo-1741506131058-533fcf894483?w=800",
            "https://images.unsplash.com/photo-1561912774-79769a0a0a7a?w=800",
        ],
        "twin": [
            "https://images.unsplash.com/photo-1566665797739-1674de7a421a?w=800",
            "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=800",
        ],
        "executive": [
            "https://images.unsplash.com/photo-1578683010236-d716f9a3f461?w=800",
            "https://images.unsplash.com/photo-1590490360182-c33d57733427?w=800",
            "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=800",
        ],
    }
    
    # Room templates (reused across properties with price variations)
    room_templates = [
        {
            "slug": "double",
            "name": "Standard Double Room",
            "description": "Comfortable room with a double bed, en-suite bathroom, and city views. Perfect for solo travellers or couples.",
            "max_guests": 2, "bed_type": "double", "size_sqm": 18, "photos": photos["standard"],
            "amenities": ["Free WiFi", "Air conditioning", "Flat-screen TV", "Tea/coffee maker", "Hair dryer", "Safe", "Daily housekeeping"],
            "base_price": 89, "total_rooms": 8, "free_cancellation": True, "breakfast_included": False,
        },
        {
            "slug": "king",
            "name": "Deluxe King Room",
            "description": "Spacious room featuring a king-size bed, premium linens, work desk, and a luxurious rain shower.",
            "max_guests": 2, "bed_type": "king", "size_sqm": 28, "photos": photos["deluxe"],
            "amenities": ["Free WiFi", "Air conditioning", "55\" Smart TV", "Nespresso machine", "Mini bar", "Bathrobes & slippers", "Rain shower", "Safe", "Work desk", "Room service"],
            "base_price": 149, "total_rooms": 4, "free_cancellation": True, "breakfast_included": True,
        },
        {
            "slug": "suite",
            "name": "Family Suite",
            "description": "Generous two-room suite with a separate living area, perfect for families. Includes a king bed and two single beds.",
            "max_guests": 4, "bed_type": "suite", "size_sqm": 45, "photos": photos["suite"],
            "amenities": ["Free WiFi", "Air conditioning", "2 TVs", "Kitchenette", "Microwave", "Sofa bed", "Bathtub", "Cot available", "Safe", "Laundry service"],
            "base_price": 219, "total_rooms": 2, "free_cancellation": True, "breakfast_included": True,
        },
        {
            "slug": "twin",
            "name": "Superior Twin Room",
            "description": "Bright and modern room with two single beds, ideal for friends or colleagues travelling together.",
            "max_guests": 2, "bed_type": "twin", "size_sqm": 22, "photos": photos["twin"],
            "amenities": ["Free WiFi", "Air conditioning", "Flat-screen TV", "Tea/coffee maker", "Hair dryer", "Iron", "Safe"],
            "base_price": 109, "total_rooms": 5, "free_cancellation": True, "breakfast_included": False,
        },
        {
            "slug": "exec",
            "name": "Executive Suite",
            "description": "Our finest accommodation with a separate lounge, premium amenities, complimentary minibar, and panoramic views.",
            "max_guests": 2, "bed_type": "king", "size_sqm": 55, "photos": photos["executive"],
            "amenities": ["Free WiFi", "Air conditioning", "65\" Smart TV", "Nespresso machine", "Complimentary minibar", "Bathrobes & slippers", "Jacuzzi bath", "Work desk", "Lounge area", "Priority check-in", "Late checkout", "Room service", "Turndown service"],
            "base_price": 349, "total_rooms": 2, "free_cancellation": True, "breakfast_included": True,
        },
    ]
    
    # Price multipliers per property type
    price_mult = {
        "aldgate-flats": 1.0, "camden-suites": 1.15, "city-gate": 1.2,
        "city-rooms": 0.9, "london-suites": 1.1, "ryam-suites": 0.95,
        "whitechapel-hotel": 1.05, "vilenza-hotel": 1.25, "whitechapel-grand": 1.3,
    }
    
    properties = await db.properties.find({"id": {"$ne": "default"}}, {"_id": 0, "id": 1, "name": 1}).to_list(20)
    count = 0
    now = datetime.now(timezone.utc).isoformat()
    
    for prop in properties:
        mult = price_mult.get(prop["id"], 1.0)
        for tmpl in room_templates:
            room = {
                k: v for k, v in tmpl.items() if k != "slug"
            }
            room.update({
                "id": f"{tmpl['slug']}-{prop['id']}",
                "property_id": prop["id"],
                "base_price": round(tmpl["base_price"] * mult),
                "currency": "GBP",
                "is_active": True,
                "created_at": now,
            })
            await db.room_types.insert_one(room)
            count += 1
    
    logger.info(f"Seeded {count} room types across {len(properties)} properties")

@app.on_event("startup")
async def startup_event():
    await seed_admin()
    await seed_myhotelbox_branches()
    await seed_sample_room_types()
    # Migrate: ensure all reviews have property_id
    await db.reviews.update_many(
        {"property_id": {"$exists": False}},
        {"$set": {"property_id": "default"}}
    )
    logger.info("Admin user seeded and indexes created")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
