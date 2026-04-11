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

# Import extracted route modules
from routes.messaging import create_messaging_router
from routes.automation import create_automation_router
from routes.dashboard import create_dashboard_router
from routes.staff_performance import create_staff_performance_router
from routes.calendar_gss import create_calendar_gss_router
from routes.housekeeping import create_housekeeping_router
from routes.guest_profiles import create_guest_profiles_router
from routes.campaigns import create_campaigns_router
from routes.guest_app import create_guest_app_router
from routes.auth_routes import create_auth_router
from routes.connections import create_connections_router
from routes.reviews import create_reviews_router
from routes.integrations import create_integrations_router
from routes.bookings import create_bookings_router

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
    GroupBookingRequest, GroupBooking,
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
GOOGLE_BUSINESS_CLIENT_ID = os.environ.get(' ', '')
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


stripe_api_key = os.environ.get("STRIPE_API_KEY", "")

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

# Wire up extracted route modules
messaging_router = create_messaging_router(db, require_roles, LlmChat, UserMessage, resend)
api_router.include_router(messaging_router)

automation_router = create_automation_router(db, require_roles, resend)
api_router.include_router(automation_router)

dashboard_router = create_dashboard_router(db, require_roles)
api_router.include_router(dashboard_router)

staff_perf_router = create_staff_performance_router(db, require_roles)
api_router.include_router(staff_perf_router)

calendar_gss_router = create_calendar_gss_router(db, require_roles)
api_router.include_router(calendar_gss_router)

housekeeping_router = create_housekeeping_router(db, require_roles)
api_router.include_router(housekeeping_router)

guest_profiles_router = create_guest_profiles_router(db, require_roles)
api_router.include_router(guest_profiles_router)

campaigns_router = create_campaigns_router(db, require_roles, resend)
api_router.include_router(campaigns_router)

guest_app_router = create_guest_app_router(db, require_roles)
api_router.include_router(guest_app_router)

auth_routes_router = create_auth_router(db, require_roles, get_current_user, hash_password, verify_password,
                                         create_access_token, create_refresh_token, get_jwt_secret, JWT_ALGORITHM)
api_router.include_router(auth_routes_router)

connections_router = create_connections_router(db, require_roles)
api_router.include_router(connections_router)

reviews_router = create_reviews_router(db, require_roles, get_current_user, verify_api_key, LlmChat, UserMessage, resend)
api_router.include_router(reviews_router)

integrations_router = create_integrations_router(db, require_roles, resend)
api_router.include_router(integrations_router)

bookings_router = create_bookings_router(db, require_roles, LlmChat, UserMessage, resend)
api_router.include_router(bookings_router)

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

