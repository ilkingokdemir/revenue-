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
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContent
import resend
import bcrypt
import jwt
import secrets
from bson import ObjectId

# Import extracted route modules
from routes.guests.messaging import create_messaging_router
from routes.guests.messaging_advanced import create_messaging_advanced_router
from routes.guests.surveys import create_surveys_router
from routes.automation import create_automation_router
from routes.platform_ext.dashboard import create_dashboard_router
from routes.hotel_ops.staff_performance import create_staff_performance_router
from routes.pms.calendar_gss import create_calendar_gss_router
from routes.hotel_ops.housekeeping import create_housekeeping_router
from routes.platform_ext.admin import create_admin_router
from routes.hotel_ops.night_audit import create_night_audit_router
from routes.guests.loyalty_logbook_forecast import create_loyalty_router
from routes.pms.guest_profiles import create_guest_profiles_router
from routes.marketing.campaigns import create_campaigns_router
from routes.pms.guest_app import create_guest_app_router
from routes.integrations_pkg.smart_locks import create_smart_locks_router
from routes.platform_ext.setup_wizard import create_setup_wizard_router
from routes.hotel_ops.stock import create_stock_router
from routes.finance_ext.accounting import create_accounting_router
from routes.finance_ext.accounting_advanced import create_accounting_advanced_router
from routes.finance_ext.bank_reconciliation import create_bank_reconciliation_router
from routes.pms.enhanced_features import create_enhanced_features_router
from routes.hotel_ops.pos import create_pos_router
from routes.hotel_ops.pos_advanced import create_pos_advanced_router
from routes.hotel_ops.pos_ai import create_pos_ai_router
from routes.finance_ext.payments import create_payments_router
from routes.hotel_ops.terminal import create_terminal_router
from routes.platform_ext.auth_routes import create_auth_router
from routes.integrations_pkg.connections import create_connections_router
from routes.guests.reviews import create_reviews_router
from routes.integrations_pkg.integrations import create_integrations_router
from routes.pms.bookings import create_bookings_router
from routes.pms.guest_payment import create_guest_payment_router
from routes.pms.guest_journey import create_guest_journey_router
from routes.hotel_ops.maintenance import create_maintenance_router
from routes.revenue_ext.rate_manager import create_rate_manager_router
from routes.integrations_pkg.reports import create_reports_router
from routes.pms.booking_widget import create_booking_widget_router
from routes.hotel_ops.operations import create_operations_router
from routes.hotel_ops.shifts import create_shifts_router, create_shifts_v2_router
from routes.revenue_ext.rates_grid import create_rates_grid_router
from routes.hotel_ops.workforce_extras import create_workforce_extras_router
from routes.integrations_pkg.notifications import create_notifications_router
from routes.finance_ext.finance import create_finance_router
from routes.pms.my_tasks import create_my_tasks_router
from routes.hotel_ops.lost_found import create_lost_found_router
from routes.hotel_ops.events import create_events_router
from routes.platform_ext.settings_hub import create_settings_hub_router
from routes.revenue_ext.revenue import create_revenue_router
from routes.revenue_ext.revenue_advanced import create_revenue_advanced_router
from routes.revenue_ext.revenue_phase2 import create_revenue_phase2_router
from routes.revenue_ext.revenue_copilot import create_revenue_copilot_router
from routes.revenue_ext.revenue_exports import create_revenue_exports_router
from routes.revenue_ext.market_robot import create_market_robot_router
from routes.revenue_ext.ai_pricing_engine import create_ai_pricing_router
from routes.chatbot_automation import create_chatbot_router
from routes.revenue_ext.dynamic_pricing import create_dynamic_pricing_router
from routes.hotel_ops.event_intelligence import create_event_intelligence_router
from routes.revenue_ext.parity_analysis import create_parity_analysis_router
from routes.distribution.channel_manager import create_channel_manager_router
from routes.revenue_ext.historical_pricing import create_historical_pricing_router
from routes.revenue_ext.revenue_intelligence import create_revenue_intelligence_router
from routes.revenue_ext.demand_radar import create_demand_radar_router
from routes.revenue_ext.compset_intel import create_compset_intel_router
from routes.revenue_ext.price_alerts import create_price_alerts_router
from routes.pms.booking_timeline import create_booking_timeline_router
from routes.pms.guest_services import create_guest_services_router
from routes.revenue_ext.displacement import create_displacement_router
from routes.revenue_ext.los_optimizer import create_los_optimizer_router
from routes.integrations_pkg.mobile_api import create_mobile_router
from routes.marketing.weekly_digest import create_weekly_digest_router
from routes.marketing.upsell_engine import create_upsell_router
from routes.revenue_ext.rate_scraper import create_rate_scraper_router
from routes.platform_ext.enhanced_dashboard import create_enhanced_dashboard_router
from routes.integrations_pkg.reports_hub import create_reports_hub_router
from routes.finance_ext.finance_pl import create_finance_pl_router
from routes.hotel_ops.shift_scheduler import create_shift_scheduler_router
from routes.pms.pass_over import create_pass_over_router
from routes.security.compliance import create_compliance_router
from routes.security.tr_compliance import create_tr_compliance_router
from routes.security.eu_compliance import create_eu_compliance_router
from routes.distribution.channel_revenue import create_channel_revenue_router
from routes.hotel_ops.pos_kds import create_pos_kds_router
from routes.guests.loyalty_v2 import create_loyalty_v2_router
from routes.integrations_pkg.sentiment import create_sentiment_router as create_cross_sentiment_router
from routes.pms.self_checkin_v2 import create_self_checkin_v2_router
from routes.platform_ext.brand_portal import create_brand_portal_router
from routes.hotel_ops.ops_v2 import create_ops_v2_router
from routes.revenue_ext.forecast_v2 import create_forecast_v2_router
from routes.security.anomaly_detection import create_anomaly_router
from routes.hotel_ops.tipping import create_tipping_router
from routes.pms.guest_portal_v2 import create_guest_portal_v2_router
from routes.hotel_ops.conference_sc import create_conference_sc_router
from routes.ai.copilot import create_copilot_router
from routes.ai.image_ai import create_image_ai_router
from routes.hotel_ops.fnb_tabs import create_fnb_tabs_router
from routes.finance_ext.bi_feed import create_bi_feed_router
from routes.hotel_ops.hk_turnover import create_hk_turnover_router
from routes.revenue_ext.pricing_explain import create_pricing_explain_router
from routes.guests.loyalty_tier import create_loyalty_tier_router
from routes.hotel_ops.banquet_orders import create_banquet_orders_router
from routes.platform_ext.help import create_help_router
from routes.platform_ext.site_feasibility import create_site_feasibility_router
from routes.pms.self_checkin_auto import create_self_checkin_auto_router
from routes.integrations_pkg.lock_sdk import create_lock_sdk_router
from routes.hotel_ops.recipe_cogs import create_recipe_cogs_router
from routes.marketing.voice_concierge import create_voice_concierge_router
from routes.marketing.whatsapp_voice import create_whatsapp_voice_router
from routes.ai.ai_predictions import create_ai_predictions_router
from routes.hotel_ops.laundry import create_laundry_router
from routes.finance_ext.payroll import create_payroll_router
from routes.finance_ext.expenses import create_expenses_router
from routes.finance_ext.cashflow import create_cashflow_router
from routes.pms.arrivals import create_arrivals_router
from routes.finance_ext.contracts import create_contracts_router
from routes.security.legal_documents import create_legal_documents_router
from routes.hotel_ops.staff_onboarding import create_staff_onboarding_router
from routes.finance_ext.payroll_matrix import create_payroll_matrix_router
from routes.security.bug_tracker import create_bug_tracker_router
from routes.platform_ext.roles import create_roles_router
from routes.imports import create_imports_router

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
    title="Hotel PMS & Revenue Management API",
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


# ==================== GLOBAL VALIDATION HATA YAKALAYICILAR (iter 381) ====================
# Handler'lar içinde manuel Pydantic model kurulumu / data["x"] erişimi 500 yerine 4xx dönsün
from pydantic import ValidationError as _PydanticValidationError
from fastapi.responses import JSONResponse as _JSONResponse

@app.exception_handler(_PydanticValidationError)
async def _pydantic_error_handler(request, exc):
    errs = [{"field": ".".join(str(l) for l in e.get("loc", [])), "msg": e.get("msg", "")}
            for e in exc.errors()[:10]]
    return _JSONResponse(status_code=422, content={"detail": "Doğrulama hatası", "errors": errs})

@app.exception_handler(KeyError)
async def _keyerror_handler(request, exc):
    return _JSONResponse(status_code=400, content={"detail": f"Eksik alan: {exc}"})

@app.exception_handler(ValueError)
async def _valueerror_handler(request, exc):
    return _JSONResponse(status_code=400, content={"detail": f"Geçersiz değer: {str(exc)[:200]}"})

from bson.errors import InvalidId as _BsonInvalidId, BSONError as _BSONError

@app.exception_handler(_BsonInvalidId)
async def _invalid_bson_id_handler(request, exc):
    return _JSONResponse(status_code=400, content={"detail": "Geçersiz ID formatı."})

@app.exception_handler(_BSONError)
async def _bson_error_handler(request, exc):
    return _JSONResponse(status_code=400, content={"detail": f"Geçersiz veri formatı: {str(exc)[:200]}"})


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
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "password_hash": hashed,
            "name": "Hotel Admin",
            "role": "admin",
            "department": "management",
            "is_active": True,
            "is_activated": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Admin user seeded: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
        logger.info(f"Admin password updated: {admin_email}")
    # Ensure admin has id field
    if existing and not existing.get("id"):
        await db.users.update_one({"email": admin_email}, {"$set": {"id": str(uuid.uuid4())}})
    
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    # iter 332 — market_supply was indexless and /geo-supply was scanning the
    # full collection (~10K docs per property) → 25s for a chart load and the
    # frontend was hitting ingress 60s timeout. Compound indexes drop this
    # to ~3-6s.
    try:
        await db.market_supply.create_index([("property_id", 1), ("scan_type", 1), ("date", 1)])
        await db.market_supply.create_index([("property_id", 1), ("scan_type", 1), ("scanned_at", -1)])
        await db.market_supply.create_index([("scan_type", 1), ("date", 1)])
        await db.market_competitors.create_index([("property_id", 1)])
        # iter 338 — Hard-prevent duplicate competitor inserts via PARALLEL
        # bulk-add calls (race condition: 2 concurrent /bulk-add reads the
        # same `existing` snapshot and both pass dedup). The application-
        # level dedup in add_competitor + bulk_add_competitors handles the
        # serial path; this index closes the race window.
        await db.market_competitors.create_index(
            [("property_id", 1), ("booking_url", 1)],
            unique=True, name="prop_url_uniq",
        )
        await db.bookings.create_index([("property_id", 1), ("check_in", 1), ("check_out", 1), ("status", 1)])
    except Exception as e:
        logger.warning("market_supply index creation failed: %s", e)


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

# NOT (iter 377): Stripe webhook handler'ı payments.py'ye taşındı (tek kanonik handler).
# Eski app-level mükerrer handler kaldırıldı — booking confirm + email log + tip
# işleme artık routes/finance_ext/payments.py POST /webhook/stripe içinde.

# Diagnostics — çalışan asyncio görev envanteri (iter 378)
@app.get("/api/admin/diagnostics/tasks")
async def diag_tasks(current_user: dict = Depends(require_roles("admin"))):
    import asyncio as _a
    from collections import Counter
    names = Counter()
    for t in _a.all_tasks():
        coro = t.get_coro()
        names[getattr(coro, "__qualname__", str(coro))[:80]] += 1
    return {"total_tasks": sum(names.values()),
            "by_coro": dict(sorted(names.items(), key=lambda x: -x[1]))}

# Wire up extracted route modules
messaging_router = create_messaging_router(db, require_roles, LlmChat, UserMessage, resend)
api_router.include_router(messaging_router)

messaging_adv_router = create_messaging_advanced_router(db, require_roles, LlmChat, UserMessage)
api_router.include_router(messaging_adv_router)

surveys_router = create_surveys_router(db, require_roles, LlmChat, UserMessage, resend)
api_router.include_router(surveys_router)

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

from routes.hotel_ops.predictive_hk import create_predictive_hk_router
api_router.include_router(create_predictive_hk_router(db, require_roles))

guest_profiles_router = create_guest_profiles_router(db, require_roles)
api_router.include_router(guest_profiles_router)

campaigns_router = create_campaigns_router(db, require_roles, resend)
api_router.include_router(campaigns_router)

guest_app_router = create_guest_app_router(db, require_roles)
api_router.include_router(guest_app_router)

smart_locks_router = create_smart_locks_router(db, require_roles)
api_router.include_router(smart_locks_router)

setup_wizard_router = create_setup_wizard_router(db, require_roles)
api_router.include_router(setup_wizard_router)

stock_router = create_stock_router(db, require_roles)
api_router.include_router(stock_router)

accounting_router = create_accounting_router(db, require_roles)
api_router.include_router(accounting_router)

accounting_adv_router = create_accounting_advanced_router(db, require_roles)
api_router.include_router(accounting_adv_router)

bank_recon_router = create_bank_reconciliation_router(db, require_roles)
api_router.include_router(bank_recon_router)

enhanced_router = create_enhanced_features_router(db, require_roles)
api_router.include_router(enhanced_router)

pos_router = create_pos_router(db, require_roles)
api_router.include_router(pos_router)

pos_adv_router = create_pos_advanced_router(db, require_roles, resend)
api_router.include_router(pos_adv_router)

pos_ai_router = create_pos_ai_router(db, require_roles, LlmChat, UserMessage)
api_router.include_router(pos_ai_router)

payments_router = create_payments_router(db, require_roles)
api_router.include_router(payments_router)

terminal_router = create_terminal_router(db, require_roles)
api_router.include_router(terminal_router)

auth_routes_router = create_auth_router(db, require_roles, get_current_user, hash_password, verify_password,
                                         create_access_token, create_refresh_token, get_jwt_secret, JWT_ALGORITHM)
api_router.include_router(auth_routes_router)

connections_router = create_connections_router(db, require_roles)
api_router.include_router(connections_router)

# Register sentiment router BEFORE reviews router to avoid /reviews/{review_id} catching /reviews/sentiment/*
from routes.integrations_pkg.review_sentiment import create_sentiment_router
api_router.include_router(create_sentiment_router(db, require_roles, LlmChat, UserMessage))

reviews_router = create_reviews_router(db, require_roles, get_current_user, verify_api_key, LlmChat, UserMessage, resend)
api_router.include_router(reviews_router)

integrations_router = create_integrations_router(db, require_roles, resend)
api_router.include_router(integrations_router)

bookings_router = create_bookings_router(db, require_roles, LlmChat, UserMessage, resend)
api_router.include_router(bookings_router)

guest_payment_router = create_guest_payment_router(db, require_roles)
api_router.include_router(guest_payment_router)

admin_router = create_admin_router(db, require_roles)
api_router.include_router(admin_router)

night_audit_router = create_night_audit_router(db, require_roles)
api_router.include_router(night_audit_router)

loyalty_router = create_loyalty_router(db, require_roles)
api_router.include_router(loyalty_router)

guest_journey_router = create_guest_journey_router(db, require_roles)
api_router.include_router(guest_journey_router)

maintenance_router = create_maintenance_router(db, require_roles)
api_router.include_router(maintenance_router)

rate_manager_router = create_rate_manager_router(db, require_roles)
api_router.include_router(rate_manager_router)

reports_router = create_reports_router(db, require_roles)
api_router.include_router(reports_router)

booking_widget_router = create_booking_widget_router(db, require_roles)
api_router.include_router(booking_widget_router)

operations_router = create_operations_router(db, require_roles)
api_router.include_router(operations_router)

shifts_router = create_shifts_router(db, require_roles)
api_router.include_router(shifts_router)
shifts_v2_router = create_shifts_v2_router(db, require_roles)
api_router.include_router(shifts_v2_router)

rates_grid_router = create_rates_grid_router(db, require_roles)
api_router.include_router(rates_grid_router)

workforce_extras_router = create_workforce_extras_router(db, require_roles)
api_router.include_router(workforce_extras_router)

notifications_router = create_notifications_router(db, require_roles)
api_router.include_router(notifications_router)

finance_router = create_finance_router(db, require_roles)
api_router.include_router(finance_router)

my_tasks_router = create_my_tasks_router(db, require_roles)
api_router.include_router(my_tasks_router)

lost_found_router = create_lost_found_router(db, require_roles)
api_router.include_router(lost_found_router)

events_router = create_events_router(db, require_roles)
api_router.include_router(events_router)

settings_hub_router = create_settings_hub_router(db, require_roles)
api_router.include_router(settings_hub_router)

revenue_router = create_revenue_router(db, require_roles)
api_router.include_router(revenue_router)

revenue_advanced_router = create_revenue_advanced_router(db, require_roles)
api_router.include_router(revenue_advanced_router)

revenue_phase2_router = create_revenue_phase2_router(db, require_roles)
api_router.include_router(revenue_phase2_router)

revenue_copilot_router = create_revenue_copilot_router(db, require_roles)
api_router.include_router(revenue_copilot_router)

revenue_exports_router = create_revenue_exports_router(db, require_roles)
api_router.include_router(revenue_exports_router)

market_robot_router = create_market_robot_router(db, require_roles, resend)
api_router.include_router(market_robot_router)

ai_pricing_router = create_ai_pricing_router(db, require_roles)
api_router.include_router(ai_pricing_router)

chatbot_router = create_chatbot_router(db, require_roles)
api_router.include_router(chatbot_router)

dynamic_pricing_router = create_dynamic_pricing_router(db, require_roles)
api_router.include_router(dynamic_pricing_router)

event_intelligence_router = create_event_intelligence_router(db, require_roles)
api_router.include_router(event_intelligence_router)
parity_analysis_router = create_parity_analysis_router(db, require_roles)
api_router.include_router(parity_analysis_router)
channel_manager_router = create_channel_manager_router(db, require_roles)
api_router.include_router(channel_manager_router)
historical_pricing_router = create_historical_pricing_router(db, require_roles)
api_router.include_router(historical_pricing_router)
revenue_intelligence_router = create_revenue_intelligence_router(db, require_roles)
api_router.include_router(revenue_intelligence_router)
demand_radar_router = create_demand_radar_router(db, require_roles)
api_router.include_router(demand_radar_router)
compset_intel_router = create_compset_intel_router(db, require_roles)
api_router.include_router(compset_intel_router)

from routes.revenue_ext.owner_pulse import create_owner_pulse_router
owner_pulse_router = create_owner_pulse_router(db, require_roles, demand_radar_router, compset_intel_router)
api_router.include_router(owner_pulse_router)

@app.on_event("startup")
async def _start_owner_pulse_digest():
    import asyncio as _asyncio
    _asyncio.create_task(owner_pulse_router.digest_loop())
    _asyncio.create_task(owner_pulse_router.autopilot_loop())
price_alerts_router = create_price_alerts_router(db, require_roles)
api_router.include_router(price_alerts_router)
booking_timeline_router = create_booking_timeline_router(db, require_roles)
api_router.include_router(booking_timeline_router)
guest_services_router = create_guest_services_router(db, require_roles, resend)
api_router.include_router(guest_services_router)
displacement_router = create_displacement_router(db, require_roles)
api_router.include_router(displacement_router)
los_optimizer_router = create_los_optimizer_router(db, require_roles)
api_router.include_router(los_optimizer_router)
mobile_router = create_mobile_router(db, require_roles)
api_router.include_router(mobile_router)
weekly_digest_router = create_weekly_digest_router(db, require_roles, LlmChat, UserMessage)
api_router.include_router(weekly_digest_router)
upsell_router = create_upsell_router(db, require_roles, LlmChat, UserMessage)
api_router.include_router(upsell_router)
rate_scraper_router = create_rate_scraper_router(db, require_roles)
api_router.include_router(rate_scraper_router)
enhanced_dashboard_router = create_enhanced_dashboard_router(db, require_roles)
api_router.include_router(enhanced_dashboard_router)
reports_hub_router = create_reports_hub_router(db, require_roles)
api_router.include_router(reports_hub_router)
finance_pl_router = create_finance_pl_router(db, require_roles)
api_router.include_router(finance_pl_router)
shift_scheduler_router = create_shift_scheduler_router(db, require_roles)
api_router.include_router(shift_scheduler_router)
pass_over_router = create_pass_over_router(db, require_roles)
api_router.include_router(pass_over_router)
compliance_router = create_compliance_router(db, require_roles)
api_router.include_router(compliance_router)
tr_compliance_router = create_tr_compliance_router(db, require_roles)
api_router.include_router(tr_compliance_router)
eu_compliance_router = create_eu_compliance_router(db, require_roles)
api_router.include_router(eu_compliance_router)
channel_revenue_router = create_channel_revenue_router(db, require_roles)
api_router.include_router(channel_revenue_router)
pos_kds_router = create_pos_kds_router(db, require_roles)
api_router.include_router(pos_kds_router)
loyalty_v2_router = create_loyalty_v2_router(db, require_roles)
api_router.include_router(loyalty_v2_router)
sentiment_router = create_cross_sentiment_router(db, require_roles)
api_router.include_router(sentiment_router)
self_checkin_v2_router = create_self_checkin_v2_router(db, require_roles)
api_router.include_router(self_checkin_v2_router)
brand_portal_router = create_brand_portal_router(db, require_roles)
api_router.include_router(brand_portal_router)
ops_v2_router = create_ops_v2_router(db, require_roles)
api_router.include_router(ops_v2_router)
forecast_v2_router = create_forecast_v2_router(db, require_roles)
api_router.include_router(forecast_v2_router)

from routes.revenue_ext.forecast_plans import create_forecast_plans_router
api_router.include_router(create_forecast_plans_router(db, require_roles))

from routes.revenue_ext.intraday_reprice import create_intraday_reprice_router, intraday_reprice_loop
_idr_auto_fn = getattr(ai_pricing_router, "run_auto_apply_internal", None)
intraday_reprice_router = create_intraday_reprice_router(db, require_roles, _idr_auto_fn)
api_router.include_router(intraday_reprice_router)

@app.on_event("startup")
async def _start_intraday_reprice():
    import asyncio as _asyncio
    _asyncio.create_task(intraday_reprice_loop(db, _idr_auto_fn))

from routes.revenue_ext.restriction_advisor import create_restriction_advisor_router
restriction_advisor_router = create_restriction_advisor_router(db, require_roles)
api_router.include_router(restriction_advisor_router)
anomaly_router = create_anomaly_router(db, require_roles, LlmChat, UserMessage)
api_router.include_router(anomaly_router)
tipping_router = create_tipping_router(db, require_roles, stripe_api_key)
api_router.include_router(tipping_router)
guest_portal_v2_router = create_guest_portal_v2_router(db, require_roles)
api_router.include_router(guest_portal_v2_router)
conference_sc_router = create_conference_sc_router(db, require_roles)
api_router.include_router(conference_sc_router)
copilot_router = create_copilot_router(db, require_roles, LlmChat, UserMessage)
api_router.include_router(copilot_router)
image_ai_router = create_image_ai_router(db, require_roles, LlmChat, UserMessage, FileContent)
api_router.include_router(image_ai_router)
fnb_tabs_router = create_fnb_tabs_router(db, require_roles)
api_router.include_router(fnb_tabs_router)
bi_feed_router = create_bi_feed_router(db, require_roles)
api_router.include_router(bi_feed_router)
hk_turnover_router = create_hk_turnover_router(db, require_roles, LlmChat, UserMessage, FileContent)
api_router.include_router(hk_turnover_router)
pricing_explain_router = create_pricing_explain_router(db, require_roles, LlmChat, UserMessage)
api_router.include_router(pricing_explain_router)
loyalty_tier_router = create_loyalty_tier_router(db, require_roles)
api_router.include_router(loyalty_tier_router)
banquet_orders_router = create_banquet_orders_router(db, require_roles)
api_router.include_router(banquet_orders_router)
help_router = create_help_router(require_roles)
api_router.include_router(help_router)
site_feasibility_router = create_site_feasibility_router(db, require_roles)
api_router.include_router(site_feasibility_router)
self_checkin_auto_router = create_self_checkin_auto_router(db, require_roles)
api_router.include_router(self_checkin_auto_router)
api_router.include_router(create_lock_sdk_router(db, require_roles))
api_router.include_router(create_recipe_cogs_router(db, require_roles))
api_router.include_router(create_voice_concierge_router(db, require_roles))
api_router.include_router(create_whatsapp_voice_router(db, require_roles))
ai_predictions_router = create_ai_predictions_router(db, require_roles)
api_router.include_router(ai_predictions_router)
laundry_router = create_laundry_router(db, require_roles)
api_router.include_router(laundry_router)
payroll_router = create_payroll_router(db, require_roles)
api_router.include_router(payroll_router)
expenses_router = create_expenses_router(db, require_roles)
api_router.include_router(expenses_router)
cashflow_router = create_cashflow_router(db, require_roles)
api_router.include_router(cashflow_router)
# NOT (iter 377): integrations_pkg/marketplace kaldırıldı — platform_ext/marketplace tek kanonik modül
arrivals_router = create_arrivals_router(db, require_roles)
api_router.include_router(arrivals_router)
contracts_router = create_contracts_router(db, require_roles)
api_router.include_router(contracts_router)
legal_docs_router = create_legal_documents_router(db, require_roles, get_current_user)
api_router.include_router(legal_docs_router)
onboarding_router = create_staff_onboarding_router(db, require_roles, get_current_user, resend)
api_router.include_router(onboarding_router)
payroll_matrix_router = create_payroll_matrix_router(db, require_roles)
api_router.include_router(payroll_matrix_router)
bug_tracker_router = create_bug_tracker_router(db, require_roles, get_current_user)
api_router.include_router(bug_tracker_router)
roles_router = create_roles_router(db, require_roles, get_current_user)
api_router.include_router(roles_router)
imports_router = create_imports_router(db, require_roles, get_current_user)
api_router.include_router(imports_router)
from routes.security.audit_trail import create_audit_trail_router
audit_trail_router = create_audit_trail_router(db)
api_router.include_router(audit_trail_router)
from routes.pms.collisions import create_collisions_router
collisions_router = create_collisions_router(db)
api_router.include_router(collisions_router)
from routes.finance_ext.profit_os import create_profit_os_router
profit_os_router = create_profit_os_router(db)
api_router.include_router(profit_os_router)
from routes.pms.oos_blocks import create_oos_router
oos_router = create_oos_router(db)
api_router.include_router(oos_router)
from routes.finance_ext.city_ledger import create_city_ledger_router
city_ledger_router = create_city_ledger_router(db, resend)
api_router.include_router(city_ledger_router)
from routes.finance_ext.tax_config import create_tax_config_router
tax_config_router = create_tax_config_router(db)
api_router.include_router(tax_config_router)
from routes.finance_ext.deposit_policies import create_deposit_policies_router
deposit_policies_router = create_deposit_policies_router(db)
api_router.include_router(deposit_policies_router)
from routes.integrations_pkg.unified_inbox import create_unified_inbox_router
unified_inbox_router = create_unified_inbox_router(db)
api_router.include_router(unified_inbox_router)
from routes.revenue_ext.competitor_parity import create_competitor_parity_router
competitor_parity_router = create_competitor_parity_router(db, require_roles)
api_router.include_router(competitor_parity_router)
from routes.revenue_ext.forecast_accuracy import create_forecast_accuracy_router
forecast_accuracy_router = create_forecast_accuracy_router(db, require_roles)
api_router.include_router(forecast_accuracy_router)
from routes.marketing.concierge import create_concierge_router
concierge_router = create_concierge_router(db)
api_router.include_router(concierge_router)
from routes.hotel_ops.sustainability import create_sustainability_router
sustainability_router = create_sustainability_router(db, require_roles)
api_router.include_router(sustainability_router)
from routes.marketing.nightly_recap import create_nightly_recap_router, create_concierge_topics_router
nightly_recap_router = create_nightly_recap_router(db, require_roles)
api_router.include_router(nightly_recap_router)
concierge_topics_router = create_concierge_topics_router(db, require_roles)
api_router.include_router(concierge_topics_router)
from routes.finance_ext.accounting_export import create_accounting_export_router
accounting_export_router = create_accounting_export_router(db, require_roles)
api_router.include_router(accounting_export_router)
from routes.finance_ext.currency_fx import create_currency_fx_router
currency_fx_router = create_currency_fx_router(db)
api_router.include_router(currency_fx_router)
from routes.revenue_ext.rate_structure import create_rate_structure_router
rate_structure_router = create_rate_structure_router(db)
api_router.include_router(rate_structure_router)

from routes.pms.rms_pro import create_rms_pro_router
rms_pro_router = create_rms_pro_router(db, require_roles)
api_router.include_router(rms_pro_router)
from routes.pms.groups import create_groups_router
groups_router = create_groups_router(db)
api_router.include_router(groups_router)
from routes.security.gdpr import create_gdpr_router
gdpr_router = create_gdpr_router(db)
api_router.include_router(gdpr_router)
from routes.marketing.og_images import create_og_router
og_router = create_og_router()
api_router.include_router(og_router)
from routes.platform_ext.property_onboarding import create_onboarding_router
onboarding_router = create_onboarding_router(db)
api_router.include_router(onboarding_router)
from routes.platform_ext.onboarding_drip import create_onboarding_drip_router
onboarding_drip_router = create_onboarding_drip_router(db)
api_router.include_router(onboarding_drip_router)
from routes.platform_ext.department_shortcuts import create_department_shortcuts_router
department_shortcuts_router = create_department_shortcuts_router(db)
api_router.include_router(department_shortcuts_router)
from routes.revenue_ext.group_displacement import create_group_displacement_router
group_displacement_router = create_group_displacement_router(db)
api_router.include_router(group_displacement_router)
from routes.finance_ext.damage_protection import create_damage_protection_router
damage_protection_router = create_damage_protection_router(db)
api_router.include_router(damage_protection_router)
from routes.guests.id_verification import create_id_verification_router
id_verification_router = create_id_verification_router(db)
api_router.include_router(id_verification_router)
from routes.finance_ext.pay_by_link import create_pay_by_link_router
pay_by_link_router = create_pay_by_link_router(db)
api_router.include_router(pay_by_link_router)
from routes.pms.pickup_pulse import create_pickup_pulse_router
api_router.include_router(create_pickup_pulse_router(db))
from routes.platform_ext.mobile_push import create_mobile_push_router
api_router.include_router(create_mobile_push_router(db))
from routes.platform_ext.demo_seeder import create_demo_seeder_router
demo_seeder_router = create_demo_seeder_router(db)
api_router.include_router(demo_seeder_router)

# ===== Iter 156 — Top-10 competitor gap features =====
from routes.hotel_ops.night_audit_close import create_night_audit_close_router
api_router.include_router(create_night_audit_close_router(db, require_roles))

from routes.finance_ext.deposit_ledger import create_deposit_ledger_router
api_router.include_router(create_deposit_ledger_router(db, require_roles))

from routes.finance_ext.commission_recon import create_commission_recon_router
api_router.include_router(create_commission_recon_router(db, require_roles))

from routes.finance_ext.gift_cards import create_gift_cards_router
api_router.include_router(create_gift_cards_router(db, require_roles))

# Note: review_sentiment router is registered earlier (before reviews_router) to avoid route conflicts

from routes.pms.guest_rfm import create_rfm_router
api_router.include_router(create_rfm_router(db, require_roles))

from routes.hotel_ops.preventive_maintenance import create_preventive_maintenance_router
api_router.include_router(create_preventive_maintenance_router(db, require_roles))

from routes.hotel_ops.asset_register import create_asset_register_router
api_router.include_router(create_asset_register_router(db, require_roles))

from routes.finance_ext.cash_drawer import create_cash_drawer_router
api_router.include_router(create_cash_drawer_router(db, require_roles))

from routes.security.two_factor_auth import create_2fa_router
api_router.include_router(create_2fa_router(db, require_roles, get_current_user))

# ===== Iter 157 — Revenue Health + IP Allowlist + PCI Card Vault =====
from routes.revenue_ext.revenue_health import create_revenue_health_router
api_router.include_router(create_revenue_health_router(db, require_roles))

from routes.security.ip_allowlist import create_ip_allowlist_router
api_router.include_router(create_ip_allowlist_router(db, require_roles))

from routes.finance_ext.card_vault import create_card_vault_router
api_router.include_router(create_card_vault_router(db, require_roles))

# Iter 158 — Deposit Automation (bridges deposit_policies + card_vault + folio_items)
from routes.finance_ext.deposit_automation import create_deposit_automation_router
deposit_auto_router = create_deposit_automation_router(db, require_roles)
api_router.include_router(deposit_auto_router)

# Iter 159 — Scheduler (async background task runner, currently nightly auto-deposit)
from routes.hotel_ops.scheduler import create_scheduler_router, scheduler_loop
_auto_capture_fn = getattr(deposit_auto_router, "run_capture", None)

async def _job_auto_deposit_capture(property_id: str) -> dict:
    """Scheduled job: run a full (non-dry) deposit capture for a property."""
    if _auto_capture_fn is None:
        return {"error": "auto-capture helper missing"}
    return await _auto_capture_fn(property_id=property_id, dry_run=False,
                                  only_ids=None, max_charges=200,
                                  triggered_by="scheduler")

JOB_HANDLERS = {"auto_deposit_capture": _job_auto_deposit_capture}

# Iter 339 — AI Pricing daily auto-apply hook.
# Calls the internal helper attached to the ai_pricing_router so the cron does
# not need to go through HTTP/auth. Runs once per day at 06:00 UTC after the
# Mon 05:00 fleet competitor price scrape — keeping rates fresh.
_ai_auto_fn = getattr(ai_pricing_router, "run_auto_apply_internal", None)

async def _job_ai_pricing_auto_apply(property_id: str) -> dict:
    if _ai_auto_fn is None:
        return {"applied": 0, "error": "internal helper missing"}
    try:
        return await _ai_auto_fn(property_id)
    except Exception as e:
        return {"applied": 0, "error": str(e)}

JOB_HANDLERS["ai_pricing_auto_apply"] = _job_ai_pricing_auto_apply
api_router.include_router(create_scheduler_router(db, require_roles, JOB_HANDLERS))

@app.on_event("startup")
async def _start_scheduler():
    import asyncio as _asyncio
    _asyncio.create_task(scheduler_loop(db, JOB_HANDLERS))
    # Market Robot auto-scan loop (Iter 167.1)
    _mr_loop = getattr(market_robot_router, "auto_scan_loop", None)
    if _mr_loop:
        _asyncio.create_task(_mr_loop())
    # Self check-in auto-trigger loop
    _sca_loop = getattr(self_checkin_auto_router, "auto_trigger_loop", None)
    if _sca_loop:
        _asyncio.create_task(_sca_loop())
    # RMS Pro Autopilot daily loop (Iter 305)
    _ap_loop = getattr(rms_pro_router, "autopilot_loop", None)
    if _ap_loop:
        _asyncio.create_task(_ap_loop())

# Iter 160 — Channel Manager MVP (restrictions + inbound + parity)
from routes.distribution.channel_restrictions import create_channel_restrictions_router
api_router.include_router(create_channel_restrictions_router(db, require_roles))

from routes.distribution.channel_inbound import create_channel_inbound_router
api_router.include_router(create_channel_inbound_router(db, require_roles))

from routes.distribution.channel_parity import create_channel_parity_router
api_router.include_router(create_channel_parity_router(db, require_roles))

# Iter 161 — OTA Health Dashboard (composite of parity + commission + direct + balance)
from routes.distribution.ota_health import create_ota_health_router
api_router.include_router(create_ota_health_router(db, require_roles))

# Iter 162 — Channel mappings + Sync queue with exponential backoff
from routes.distribution.channel_mappings import create_channel_mappings_router
api_router.include_router(create_channel_mappings_router(db, require_roles))

from routes.integrations_pkg.sync_queue import create_sync_queue_router, process_due_tasks
api_router.include_router(create_sync_queue_router(db, require_roles))

# Wire the sync-queue worker into the scheduler engine from Iter 159
async def _job_sync_queue_tick(property_id: str) -> dict:
    return await process_due_tasks(db, max_tasks=50)

JOB_HANDLERS["sync_queue_tick"] = _job_sync_queue_tick

# Iter 163 — Channel Hub (configs, payload profiles, publish jobs,
# price overrides, channel audit, benchmark cockpit)
from routes.distribution.channel_hub import create_channel_hub_router, nightly_dry_publish
api_router.include_router(create_channel_hub_router(db, require_roles))

# Wire the nightly dry-run publisher into the scheduler engine
async def _job_nightly_dry_publish(property_id: str) -> dict:
    return await nightly_dry_publish(db, property_id)

JOB_HANDLERS["nightly_dry_publish"] = _job_nightly_dry_publish

# Iter 320 — Weekly fleet-wide geo-validate (Camden→Boston bug auto-repair).
from routes.revenue_ext.market_robot import (
    fleet_geo_validate_worker,
    fleet_vision_enrich_worker,
    fleet_competitor_price_scan_worker,
)

async def _job_fleet_geo_validate(property_id: str) -> dict:
    # property_id is always "" for fleet-wide jobs.
    return await fleet_geo_validate_worker(db, fix=True)

JOB_HANDLERS["fleet_geo_validate"] = _job_fleet_geo_validate

# Iter 326 — Weekly fleet-wide Vision enrich (room counts + prices fresh).
async def _job_fleet_vision_enrich(property_id: str) -> dict:
    return await fleet_vision_enrich_worker(db, max_per_property=25)

JOB_HANDLERS["fleet_vision_enrich"] = _job_fleet_vision_enrich

# Iter 333 — Weekly fleet-wide competitor PRICE scrape (Booking.com per-date
# rates). Keeps the Per-Hotel Price Trend chart populated without any user
# action. Runs after the Vision enrich so booking_hotel_id is already resolved.
async def _job_fleet_competitor_price_scan(property_id: str) -> dict:
    return await fleet_competitor_price_scan_worker(
        db, days_ahead=30, max_per_property=25, comp_concurrency=3,
    )

JOB_HANDLERS["fleet_competitor_price_scan"] = _job_fleet_competitor_price_scan

# Iter 164 — Inventory Allocations (pooled / dedicated / capped per channel×room)
from routes.hotel_ops.inventory_allocations import create_inventory_allocations_router
api_router.include_router(create_inventory_allocations_router(db, require_roles))

# Iter 165 — Group Blocks (group reservations)
from routes.pms.group_blocks import create_group_blocks_router
api_router.include_router(create_group_blocks_router(db, require_roles))

# Iter 165 — Smart Rate Control (bulk rate/availability editor)
from routes.revenue_ext.smart_rate_control import create_smart_rate_control_router
api_router.include_router(create_smart_rate_control_router(db, require_roles))

from routes.revenue_ext.hurdle_lrv import create_hurdle_lrv_router
api_router.include_router(create_hurdle_lrv_router(db, require_roles))

from routes.pms.late_checkout import create_late_checkout_router
api_router.include_router(create_late_checkout_router(db, require_roles))

from routes.guests.service_recovery import create_service_recovery_router
api_router.include_router(create_service_recovery_router(db, require_roles))

from routes.pms.room_qr import create_room_qr_router
api_router.include_router(create_room_qr_router(db, require_roles))

from routes.finance_ext.tax_presets import create_tax_presets_router
api_router.include_router(create_tax_presets_router(db, require_roles))

from routes.pms.walkin import create_walkin_router
api_router.include_router(create_walkin_router(db, require_roles))

from routes.pms.no_show import create_no_show_router
api_router.include_router(create_no_show_router(db, require_roles))

from routes.pms.guest_prefs import create_guest_prefs_router
api_router.include_router(create_guest_prefs_router(db, require_roles))

from routes.hotel_ops.cleaning_checklists import create_cleaning_checklists_router
api_router.include_router(create_cleaning_checklists_router(db, require_roles))

from routes.pms.room_move import create_room_move_router
api_router.include_router(create_room_move_router(db, require_roles))

from routes.hotel_ops.lost_found_match import create_lost_found_match_router
api_router.include_router(create_lost_found_match_router(db, require_roles))

from routes.hotel_ops.glitch_log import create_glitch_log_router
api_router.include_router(create_glitch_log_router(db, require_roles))

from routes.hotel_ops.sops import create_sops_router
api_router.include_router(create_sops_router(db, require_roles))

from routes.automation_rules import create_automation_router, fire_event as _fire_event
api_router.include_router(create_automation_router(db, require_roles))
# Expose for other modules to import: routes.automation_rules.fire_event
__all__ = ["_fire_event"]

from routes.integrations_pkg.team_chat import create_team_chat_router
api_router.include_router(create_team_chat_router(db, require_roles))

from routes.guests.crm_360 import create_crm360_router
api_router.include_router(create_crm360_router(db, require_roles))

from routes.distribution.channels_v2 import create_channels_v2_router
api_router.include_router(create_channels_v2_router(db, require_roles))

from routes.pms.group_rooming import create_group_rooming_router
api_router.include_router(create_group_rooming_router(db, require_roles))

from routes.marketing.attribution import create_attribution_router
api_router.include_router(create_attribution_router(db, require_roles))

from routes.hotel_ops.timeslots import create_timeslot_router
api_router.include_router(create_timeslot_router(db, require_roles))

from routes.hotel_ops.staff_ops import create_staff_ops_router
api_router.include_router(create_staff_ops_router(db, require_roles))

from routes.revenue_ext.revenue_protection import create_revenue_protection_router
api_router.include_router(create_revenue_protection_router(db, require_roles))

from routes.hotel_ops.spaces import create_spaces_router
api_router.include_router(create_spaces_router(db, require_roles))

from routes.hotel_ops.extras_v1 import create_extras_router
api_router.include_router(create_extras_router(db, require_roles))

from routes.ai.agents_b2b import create_agents_router
api_router.include_router(create_agents_router(db, require_roles))

from routes.hotel_ops.extras_v2 import create_extras_v2_router
api_router.include_router(create_extras_v2_router(db, require_roles))

# ===== Batch 6 (final P0): Pre-Auth, Chargeback, Web Push, PMS-CRS, Public API =====
from routes.finance_ext.preauth import create_preauth_router
api_router.include_router(create_preauth_router(db, require_roles))

from routes.finance_ext.chargeback import create_chargeback_router
api_router.include_router(create_chargeback_router(db, require_roles))

from routes.marketing.web_push import create_web_push_router
api_router.include_router(create_web_push_router(db, require_roles))

from routes.pms.pms_crs import create_pms_crs_router
api_router.include_router(create_pms_crs_router(db, require_roles))

from routes.distribution.public_api import create_public_api_router
api_router.include_router(create_public_api_router(db, require_roles))

# ===== Batch 7 (P1 keyless): Mid-stay survey, Live folio PDF, A/B tests, Pre-arrival drip, Menu engineering =====
from routes.pms.mid_stay import create_mid_stay_router
api_router.include_router(create_mid_stay_router(db, require_roles))

from routes.finance_ext.folio_live import create_folio_live_router
api_router.include_router(create_folio_live_router(db, require_roles))

from routes.marketing.ab_test import create_ab_test_router
api_router.include_router(create_ab_test_router(db, require_roles))

from routes.pms.pre_arrival import create_pre_arrival_router
api_router.include_router(create_pre_arrival_router(db, require_roles))

from routes.hotel_ops.menu_engineering import create_menu_engineering_router
api_router.include_router(create_menu_engineering_router(db, require_roles))

# ===== Batch 8 (P1 keyless): SR Voucher, Folio split, Loyalty auto, Late checkout offer, OTA stop-sell forecast =====
from routes.hotel_ops.sr_voucher import create_service_recovery_voucher_router
api_router.include_router(create_service_recovery_voucher_router(db, require_roles))

from routes.finance_ext.folio_split import create_folio_split_router
api_router.include_router(create_folio_split_router(db, require_roles))

from routes.guests.loyalty_auto import create_loyalty_auto_router
api_router.include_router(create_loyalty_auto_router(db, require_roles))

from routes.pms.late_checkout_offer import create_late_checkout_offer_router
api_router.include_router(create_late_checkout_offer_router(db, require_roles))

from routes.distribution.ota_stop_sell_forecast import create_ota_stop_sell_forecast_router
api_router.include_router(create_ota_stop_sell_forecast_router(db, require_roles))

# ===== Batch 9 (P1 keyless): Msg Templates, Birthday auto-discount, Low-stock alerts, Rebook CTA, Stay extension, Long-stay discount =====
from routes.guests.msg_templates import create_msg_templates_router
api_router.include_router(create_msg_templates_router(db, require_roles))

from routes.guests.birthday import create_birthday_router
api_router.include_router(create_birthday_router(db, require_roles))

from routes.hotel_ops.low_stock import create_low_stock_router
api_router.include_router(create_low_stock_router(db, require_roles))

from routes.guests.rebook import create_rebook_router
rebook_router = create_rebook_router(db, require_roles)
api_router.include_router(rebook_router)

async def _job_rebook_sweep(property_id: str) -> dict:
    try:
        return await rebook_router.run_sweep_internal(property_id=property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["rebook_sweep"] = _job_rebook_sweep

from routes.pms.abandoned_recovery import create_abandoned_recovery_router
abandoned_router = create_abandoned_recovery_router(db, require_roles)
api_router.include_router(abandoned_router)

async def _job_abandoned_recovery(property_id: str) -> dict:
    try:
        return await abandoned_router.run_recovery_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["abandoned_recovery"] = _job_abandoned_recovery

from routes.ai.upsell_autopilot import create_upsell_autopilot_router
upsell_autopilot_router = create_upsell_autopilot_router(db, require_roles)
api_router.include_router(upsell_autopilot_router)

async def _job_upsell_autopilot(property_id: str) -> dict:
    try:
        return await upsell_autopilot_router.run_autopilot_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["upsell_autopilot"] = _job_upsell_autopilot

from routes.marketing.nudge import create_nudge_router
nudge_router = create_nudge_router(db, require_roles)
api_router.include_router(nudge_router)

async def _job_email_nudge(property_id: str) -> dict:
    try:
        return await nudge_router.run_nudge_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["email_nudge"] = _job_email_nudge

from routes.marketing.daily_pulse import create_daily_pulse_router
daily_pulse_router = create_daily_pulse_router(db, require_roles)
api_router.include_router(daily_pulse_router)

async def _job_daily_pulse(property_id: str) -> dict:
    try:
        return await daily_pulse_router.run_pulse_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["daily_pulse"] = _job_daily_pulse

from routes.revenue_ext.leakage import create_leakage_router
leakage_router = create_leakage_router(db, require_roles)
api_router.include_router(leakage_router)

async def _job_leakage_sweep(property_id: str) -> dict:
    try:
        return await leakage_router.run_leakage_sweep_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["leakage_sweep"] = _job_leakage_sweep

from routes.ai.cancel_save_autopilot import create_cancel_save_router
cancel_save_router = create_cancel_save_router(db, require_roles)
api_router.include_router(cancel_save_router)

async def _job_cancel_save(property_id: str) -> dict:
    try:
        return await cancel_save_router.run_cancel_save_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["cancel_save"] = _job_cancel_save

from routes.marketing.report_card import create_report_card_router
report_card_router = create_report_card_router(db, require_roles)
api_router.include_router(report_card_router)

async def _job_report_card(property_id: str) -> dict:
    try:
        return await report_card_router.run_report_card_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["monthly_report_card"] = _job_report_card

from routes.guests.review_autopilot import create_review_autopilot_router
review_autopilot_router = create_review_autopilot_router(db, require_roles, LlmChat, UserMessage)
api_router.include_router(review_autopilot_router)

async def _job_review_autopilot(property_id: str) -> dict:
    try:
        return await review_autopilot_router.run_review_autopilot_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["review_autopilot"] = _job_review_autopilot

from routes.guests.risk_score import create_guest_risk_router
guest_risk_router = create_guest_risk_router(db, require_roles)
api_router.include_router(guest_risk_router)

async def _job_deposit_autopilot(property_id: str) -> dict:
    try:
        return await guest_risk_router.run_deposit_autopilot_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["deposit_autopilot"] = _job_deposit_autopilot

from routes.guests.segments import create_segments_router
segments_router = create_segments_router(db, require_roles, guest_risk_router.risk_for_internal)
api_router.include_router(segments_router)

async def _job_segment_refresh(property_id: str) -> dict:
    try:
        return await segments_router.run_segment_refresh_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["segment_refresh"] = _job_segment_refresh

from routes.distribution.channel_health import create_channel_health_router
channel_health_router = create_channel_health_router(db, require_roles)
api_router.include_router(channel_health_router)

async def _job_ota_sync_watchdog(property_id: str) -> dict:
    try:
        return await channel_health_router.run_watchdog_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["ota_sync_watchdog"] = _job_ota_sync_watchdog

from routes.distribution.push_history import create_push_history_router
api_router.include_router(create_push_history_router(db, require_roles))

from routes.distribution.two_way_sync import create_two_way_sync_router
two_way_sync_router = create_two_way_sync_router(db, require_roles)
api_router.include_router(two_way_sync_router)

async def _job_overbooking_auto_move(property_id: str) -> dict:
    try:
        return await two_way_sync_router.run_auto_move_sweep_internal(db)
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["overbooking_auto_move"] = _job_overbooking_auto_move

from routes.finance_ext.vcc_automation import create_vcc_router
vcc_router = create_vcc_router(db, require_roles)
api_router.include_router(vcc_router)

async def _job_vcc_auto_charge(property_id: str) -> dict:
    try:
        return await vcc_router.run_vcc_job_internal(db)
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["vcc_auto_charge"] = _job_vcc_auto_charge

from routes.finance_ext.invoice_reminders import create_invoice_reminders_router
invoice_reminders_router = create_invoice_reminders_router(db, require_roles)
api_router.include_router(invoice_reminders_router)

async def _job_invoice_reminders(property_id: str) -> dict:
    try:
        return await invoice_reminders_router.run_invoice_reminders_internal(db)
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["invoice_reminders"] = _job_invoice_reminders

from routes.revenue_ext.key_figures import create_key_figures_router
key_figures_router = create_key_figures_router(db, require_roles)
api_router.include_router(key_figures_router)

from routes.marketing.weekly_report import create_weekly_report_router
weekly_report_router = create_weekly_report_router(db, require_roles, key_figures_router.compute_internal)

from routes.revenue_ext.owner_summary import create_owner_summary_router
owner_summary_router = create_owner_summary_router(db, require_roles, key_figures_router.compute_internal)
api_router.include_router(owner_summary_router)

async def _job_owner_summary(property_id: str) -> dict:
    try:
        return await owner_summary_router.run_monthly_internal()
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["owner_summary_monthly"] = _job_owner_summary
api_router.include_router(weekly_report_router)

from routes.platform_ext.chain_benchmark import create_chain_benchmark_router
api_router.include_router(create_chain_benchmark_router(db, require_roles, key_figures_router.compute_internal))

async def _job_weekly_report(property_id: str) -> dict:
    try:
        return await weekly_report_router.run_weekly_report_internal(property_id or "all")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["weekly_report"] = _job_weekly_report

from routes.revenue_ext.comp_radar import create_comp_radar_router
comp_radar_router = create_comp_radar_router(db, require_roles)
api_router.include_router(comp_radar_router)

# Iter 508: Profit-first pricing + ABS + RevPAM (Total Revenue Management)
from routes.revenue_ext.profit_pricing import create_profit_pricing_router
api_router.include_router(create_profit_pricing_router(db, require_roles))
from routes.revenue_ext.abs_selling import create_abs_router
api_router.include_router(create_abs_router(db, require_roles))
from routes.revenue_ext.revpam import create_revpam_router
api_router.include_router(create_revpam_router(db, require_roles))

async def _job_comp_radar(property_id: str) -> dict:
    try:
        return await comp_radar_router.run_comp_radar_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["comp_radar"] = _job_comp_radar

# ── Mews 2026 paritesi: NL Automation + Inbox AI Agent + AR Recon + Waitlist ──
from routes.platform_ext.nl_automation import create_nl_automation_router
api_router.include_router(create_nl_automation_router(db, require_roles))

from routes.integrations_pkg.inbox_agent import create_inbox_agent_router
api_router.include_router(create_inbox_agent_router(db, require_roles))

from routes.finance_ext.ar_recon_agent import create_ar_recon_router
ar_recon_router = create_ar_recon_router(db, require_roles)
api_router.include_router(ar_recon_router)

async def _job_ar_recon(property_id: str) -> dict:
    try:
        return await ar_recon_router.run_match_internal()
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["ar_recon"] = _job_ar_recon

from routes.pms.waitlist import create_waitlist_router
waitlist_router = create_waitlist_router(db, require_roles)
api_router.include_router(waitlist_router)

async def _job_waitlist_match(property_id: str) -> dict:
    try:
        from routes.platform_ext.automation_settings import get_params
        params = await get_params(db, "waitlist_match", {"offer_ttl_hours": 48})
        return await waitlist_router.run_match_internal(ttl_hours=int(params.get("offer_ttl_hours", 48)))
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["waitlist_match"] = _job_waitlist_match

from routes.hotel_ops.hk_dispatch import create_hk_dispatch_router
hk_dispatch_router = create_hk_dispatch_router(db, require_roles)
api_router.include_router(hk_dispatch_router)

async def _job_hk_dispatch(property_id: str) -> dict:
    try:
        return await hk_dispatch_router.run_dispatch_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["hk_dispatch"] = _job_hk_dispatch

from routes.distribution.allotments import create_allotments_router
allotments_router = create_allotments_router(db, require_roles)
api_router.include_router(allotments_router)

async def _job_allotment_release(property_id: str) -> dict:
    try:
        return await allotments_router.run_release_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["allotment_release"] = _job_allotment_release

async def _job_restriction_advisor(property_id: str) -> dict:
    try:
        return await restriction_advisor_router.run_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["restriction_advisor"] = _job_restriction_advisor

from routes.marketing.gap_filler import create_gap_filler_router
gap_filler_router = create_gap_filler_router(db, require_roles)
api_router.include_router(gap_filler_router)

from routes.revenue_ext.lost_demand import create_lost_demand_router
api_router.include_router(create_lost_demand_router(db, require_roles))

from routes.marketing.demo_requests import create_demo_requests_router
api_router.include_router(create_demo_requests_router(db, require_roles))

from routes.revenue_ext.revenue_strategist import create_revenue_strategist_router
revenue_strategist_router = create_revenue_strategist_router(db, require_roles)
api_router.include_router(revenue_strategist_router)

from routes.revenue_ext.min_rate_floors import create_min_rate_floors_router
api_router.include_router(create_min_rate_floors_router(db, require_roles))

from routes.revenue_ext.discount_stack import create_discount_stack_router
api_router.include_router(create_discount_stack_router(db, require_roles))

from routes.revenue_ext.owner_rates import create_owner_rates_router
api_router.include_router(create_owner_rates_router(db, require_roles))

async def _job_revenue_strategist(property_id: str) -> dict:
    try:
        return await revenue_strategist_router.run_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["revenue_strategist"] = _job_revenue_strategist

async def _job_gap_filler(property_id: str) -> dict:
    try:
        return await gap_filler_router.run_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["gap_filler"] = _job_gap_filler

from routes.pms.res_quality import create_res_quality_router
res_quality_router = create_res_quality_router(db, require_roles)
api_router.include_router(res_quality_router)

async def _job_res_quality(property_id: str) -> dict:
    try:
        return await res_quality_router.run_autofix_internal(property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["res_quality"] = _job_res_quality

from routes.finance_ext.vcc_recovery import create_vcc_recovery_router
vcc_recovery_router = create_vcc_recovery_router(db, require_roles)
api_router.include_router(vcc_recovery_router)

async def _job_vcc_recovery(property_id: str) -> dict:
    try:
        return await vcc_recovery_router.run_internal()
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["vcc_recovery"] = _job_vcc_recovery

from routes.guests.guest_incidents import create_guest_incidents_router
guest_incidents_router = create_guest_incidents_router(db, require_roles)
api_router.include_router(guest_incidents_router)

async def _job_returning_guest_watch(property_id: str) -> dict:
    try:
        return await guest_incidents_router.run_watch_internal(property_id or "all")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["returning_guest_watch"] = _job_returning_guest_watch

from routes.finance_ext.pay_by_link import run_pay_link_reminders as _run_pay_link_reminders
from routes.pms.pickup_pulse import run_weekly_pickup_report as _run_weekly_pickup_report

async def _job_pay_link_reminder(property_id: str) -> dict:
    try:
        return await _run_pay_link_reminders(db, property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["pay_link_reminder"] = _job_pay_link_reminder

async def _job_pickup_weekly_report(property_id: str) -> dict:
    try:
        return await _run_weekly_pickup_report(db, property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["pickup_weekly_report"] = _job_pickup_weekly_report

from routes.hotel_ops.smart_rooms import run_eco_sweep as _run_eco_sweep

async def _job_eco_sweep(property_id: str) -> dict:
    try:
        return await _run_eco_sweep(db, property_id or "", triggered_by="nightly_cron")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["eco_sweep"] = _job_eco_sweep

from routes.platform_ext.mobile_push import run_mobile_daily_pulse as _run_mobile_daily_pulse

async def _job_mobile_daily_pulse(property_id: str) -> dict:
    try:
        return await _run_mobile_daily_pulse(db, property_id or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}

JOB_HANDLERS["mobile_daily_pulse"] = _job_mobile_daily_pulse

from routes.finance_ext.digital_auth import create_digital_auth_router
api_router.include_router(create_digital_auth_router(db, require_roles))

from routes.platform_ext.automation_simulator import create_automation_simulator_router
api_router.include_router(create_automation_simulator_router(db, require_roles, guest_risk_router.risk_for_internal))

from routes.platform_ext.automation_settings import create_automation_settings_router
api_router.include_router(create_automation_settings_router(db, require_roles))

from routes.marketing.automation_roi import create_automation_roi_router
api_router.include_router(create_automation_roi_router(db, require_roles, runners={
    "rebook_sweep": lambda pid, d: rebook_router.run_sweep_internal(property_id=pid, days_after=d),
    "abandoned_recovery": abandoned_router.run_recovery_internal,
    "upsell_autopilot": upsell_autopilot_router.run_autopilot_internal,
}))

from routes.pms.stay_ext import create_stay_ext_router
api_router.include_router(create_stay_ext_router(db, require_roles))

from routes.hotel_ops.long_stay import create_long_stay_router
api_router.include_router(create_long_stay_router(db, require_roles))

# ===== Batch 10 (P1 keyless final): Cancel insurance, Group rooming wizard, Tax reports v2, Check-in slots =====
from routes.finance_ext.cancel_insurance import create_cancel_insurance_router
api_router.include_router(create_cancel_insurance_router(db, require_roles))

from routes.pms.group_rooming_wiz import create_group_rooming_router
api_router.include_router(create_group_rooming_router(db, require_roles))

from routes.finance_ext.tax_reports_v2 import create_tax_reports_router
api_router.include_router(create_tax_reports_router(db, require_roles))

from routes.pms.ci_slots import create_ci_slots_router
api_router.include_router(create_ci_slots_router(db, require_roles))

# ===== Batch 11: Tier-1 Master Operations Dashboard (aggregates KPIs from all 50 keyless features) =====
from routes.platform_ext.tier1_dashboard import create_tier1_dashboard_router
api_router.include_router(create_tier1_dashboard_router(db, require_roles))

# ===== Competitor Parity v3 (Booking Engine v2, Groups, Owner Portal, Spa, Loyalty Tiers,
#                              Budget vs Actual, Compset, Webhooks & API keys, Automation Analytics) =====
from routes.pms.booking_engine_v2 import create_booking_engine_v2_router
api_router.include_router(create_booking_engine_v2_router(db, require_roles))

# Note: Group Bookings module already exists at routes/group_blocks.py
# (used by GroupBlocksPanel). The newer routes/group_bookings.py is a
# parallel implementation kept on disk for reference but NOT registered
# to avoid path collisions at /group-blocks.

from routes.platform_ext.owner_portal import create_owner_portal_router
api_router.include_router(create_owner_portal_router(db, require_roles))

from routes.hotel_ops.spa_activities import create_spa_router
api_router.include_router(create_spa_router(db, require_roles))

from routes.guests.loyalty_tiers import create_loyalty_tiers_router
api_router.include_router(create_loyalty_tiers_router(db, require_roles))

from routes.finance_ext.budget_actual import create_budget_router
api_router.include_router(create_budget_router(db, require_roles))

from routes.revenue_ext.compset import create_compset_router
api_router.include_router(create_compset_router(db, require_roles))

from routes.integrations_pkg.webhooks_api_keys import create_webhooks_api_keys_router
api_router.include_router(create_webhooks_api_keys_router(db, require_roles))

from routes.automation_analytics import create_automation_analytics_router
api_router.include_router(create_automation_analytics_router(db, require_roles))

# ===== Meeting & Events Sales (MICE pipeline) =====
from routes.hotel_ops.meetings_sales import create_meetings_router
api_router.include_router(create_meetings_router(db, require_roles))

# ===== F&B POS Integration Hub (Simphony / Lightspeed / Square / Toast) =====
from routes.hotel_ops.fnb_pos_hub import create_fnb_pos_router
api_router.include_router(create_fnb_pos_router(db, require_roles))

# ===== Owner Self-Service Login (Iter 282) =====
from routes.platform_ext.owner_self_service import create_owner_auth_router
api_router.include_router(create_owner_auth_router(db, require_roles))

# ===== TÜRSAB Agency Portal (Iter 284) =====
from routes.distribution.agency_portal import create_agency_portal_router
api_router.include_router(create_agency_portal_router(db, require_roles))

# ===== AI 24/7 Web Concierge (Iter 284 - Eviivo parity) =====
from routes.ai.web_concierge import create_web_concierge_router
api_router.include_router(create_web_concierge_router(db, require_roles))

# ===== AI Review Agent (Iter 284 - Lighthouse parity) =====
from routes.ai.review_agent import create_review_agent_router
api_router.include_router(create_review_agent_router(db, require_roles))

from routes.ai.learning_agent import create_learning_agent_router, run_morning_drafts, run_weekly_summary, run_monthly_karne
api_router.include_router(create_learning_agent_router(db, require_roles))
JOB_HANDLERS["ai_morning_drafts"] = run_morning_drafts
JOB_HANDLERS["ai_weekly_summary"] = run_weekly_summary
JOB_HANDLERS["ai_monthly_karne"] = run_monthly_karne

from routes.integrations_pkg.gbp_publish import create_gbp_router
api_router.include_router(create_gbp_router(db, require_roles))

from routes.integrations_pkg.review_sources import create_review_sources_router, run_review_source_sync
api_router.include_router(create_review_sources_router(db, require_roles))
JOB_HANDLERS["review_source_sync"] = run_review_source_sync

from routes.integrations_pkg.reputation_benchmark import create_reputation_router, run_reputation_scan
api_router.include_router(create_reputation_router(db, require_roles))
JOB_HANDLERS["reputation_scan"] = run_reputation_scan

# ===== Duetto Open Pricing (Iter 285 - segment×channel×room matrix) =====
from routes.revenue_ext.open_pricing import create_open_pricing_router
api_router.include_router(create_open_pricing_router(db, require_roles))

# ===== Beach POS (Iter 285 - Elektra TR niche) =====
from routes.hotel_ops.beach_pos import create_beach_pos_router
api_router.include_router(create_beach_pos_router(db, require_roles))

# ===== Public Event Listings + ROX Personalization (Iter 285 - Tripleseat parity) =====
from routes.distribution.public_events import create_public_events_router
api_router.include_router(create_public_events_router(db, require_roles))

# ===== Agentic AI Loops (Iter 286 - Mews 2026 parity) =====
from routes.ai.agents import create_agents_router
api_router.include_router(create_agents_router(db, require_roles))

# ===== Vacation Rental dedicated view (Iter 286 - Eviivo/Lighthouse parity) =====
from routes.hotel_ops.vacation_rental import create_vacation_rental_router
api_router.include_router(create_vacation_rental_router(db, require_roles))

# ===== Public Developer Portal (Iter 287 - Mews Marketplace v2 parity) =====
from routes.platform_ext.dev_portal import create_dev_portal_router
api_router.include_router(create_dev_portal_router(db, require_roles))

# ===== Wholesaler / Net Rate Network (Iter 287 - Cloudbeds Hotel Trader parity) =====
from routes.distribution.wholesaler import create_wholesaler_router
api_router.include_router(create_wholesaler_router(db, require_roles))

# ===== Lead Funnel Bridge + Lighthouse Adapter (Iter 287) =====
from routes.marketing.lead_funnel import create_lead_funnel_router
api_router.include_router(create_lead_funnel_router(db, require_roles))

# ===== Marketing Video Generator (Iter 288 - Sora 2 integration) =====
from routes.marketing.marketing_videos import create_marketing_videos_router
api_router.include_router(create_marketing_videos_router(db, require_roles))

# ===== Brand Voice Studio (Iter 289 - centralized tone-of-voice service) =====
from routes.ai.brand_voice import create_brand_voice_router
api_router.include_router(create_brand_voice_router(db, require_roles))

# ===== Mews-parity AI features (Iter 356) — Smart Tips, Duplicate Guest Auto-Merge, BI AI Summary =====
from routes.ai.mews_parity import create_mews_parity_router
api_router.include_router(create_mews_parity_router(db, require_roles))

# ===== Marketplace v1 (Iter 358) — Integration Hub (20 curated 3rd-party apps) =====
from routes.platform_ext.marketplace import create_marketplace_router
api_router.include_router(create_marketplace_router(db, require_roles))

# ===== Kiosk PWA (Iter 359) — Self-service check-in for lobby tablets =====
from routes.pms.kiosk import create_kiosk_router
api_router.include_router(create_kiosk_router(db))

# ===== Voice HK reports + Booking attribution tracker (Iter 361) =====
from routes.ai.voice_attribution import create_voice_and_attribution_router
api_router.include_router(create_voice_and_attribution_router(db, require_roles))

from routes.hotel_ops.mews_university import create_university_router
api_router.include_router(create_university_router(db, require_roles))

from routes.pms.scheduled_checkout import create_scheduled_checkout_router
api_router.include_router(create_scheduled_checkout_router(db, require_roles))

from routes.platform_ext.scheduled_reports import create_reports_router
api_router.include_router(create_reports_router(db, require_roles))

from routes.platform_ext.custom_dashboards import create_dashboards_router
api_router.include_router(create_dashboards_router(db, require_roles))

from routes.pms.digital_keys import create_digital_keys_router
api_router.include_router(create_digital_keys_router(db, require_roles))

from routes.hotel_ops.smart_rooms import create_smart_rooms_router
api_router.include_router(create_smart_rooms_router(db, require_roles))

from routes.revenue_ext.base_price_curve import create_base_price_curve_router
api_router.include_router(create_base_price_curve_router(db, require_roles))

from routes.revenue_ext.str_market import create_str_market_router
api_router.include_router(create_str_market_router(db, require_roles))

from routes.marketing.price_checker import create_price_checker_router
api_router.include_router(create_price_checker_router(db))

from routes.revenue_ext.revenue_brain import create_revenue_brain_router
api_router.include_router(create_revenue_brain_router(db, require_roles))

from routes.integrations_pkg.ota_inbound import create_ota_inbound_router
api_router.include_router(create_ota_inbound_router(db, require_roles))

from routes.integrations_pkg.external_loyalty import create_external_loyalty_router
api_router.include_router(create_external_loyalty_router(db, require_roles))

from routes.pms.digital_lock_providers import create_lock_providers_router
api_router.include_router(create_lock_providers_router(db, require_roles))

from routes.integrations_pkg.ota_commission import create_ota_commission_router
api_router.include_router(create_ota_commission_router(db, require_roles))

from routes.integrations_pkg.direct_conversion import create_direct_conversion_router
api_router.include_router(create_direct_conversion_router(db, require_roles))

from routes.distribution.siteminder_adapter import create_siteminder_router
api_router.include_router(create_siteminder_router(db, require_roles))

# ===== Booking.com Premier prototype (Iter 290 - XML push, pre-cert ready) =====
from routes.distribution.booking_com import create_booking_com_router
api_router.include_router(create_booking_com_router(db, require_roles))

# ===== PMS Pro (Iter 295) — Smart Assign / AI Concierge / Journey Rules / Anomaly Alerts =====
from routes.pms.pms_pro import create_pms_pro_router, journey_engine_loop as _journey_engine_loop
api_router.include_router(create_pms_pro_router(db, require_roles))

@app.on_event("startup")
async def _start_journey_engine():
    import asyncio as _asyncio
    _asyncio.create_task(_journey_engine_loop(db, interval_seconds=60))

# ===== Nightly Insights cron (Iter 376) — gece fiyat pattern analizi + bildirim =====
from routes.revenue_ext.rates_grid import nightly_insights_loop as _nightly_insights_loop

@app.on_event("startup")
async def _start_nightly_insights():
    import asyncio as _asyncio
    _asyncio.create_task(_nightly_insights_loop(db))

app.include_router(api_router)

# Serve uploaded files (guest IDs etc)
from fastapi.staticfiles import StaticFiles
os.makedirs("/app/backend/uploads/ids", exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory="/app/backend/uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- PRODUCTION HARDENING (health, request-id, error handler, env validation) ----------
from hardening import install_hardening
install_hardening(app, db)

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
    # Migrate: ensure every property has a native currency (default GBP)
    await db.properties.update_many(
        {"currency": {"$exists": False}},
        {"$set": {"currency": "GBP"}}
    )
    await db.properties.update_many(
        {"currency": None},
        {"$set": {"currency": "GBP"}}
    )
    logger.info("Admin user seeded and indexes created")

    # Iter 502 — Seed pay-link reminder (daily 10:00 UTC) + weekly pickup report (Mon 07:00 UTC)
    try:
        if not await db.scheduler_config.find_one({"property_id": "", "job": "pay_link_reminder"}, {"_id": 1}):
            await db.scheduler_config.insert_one({
                "property_id": "", "job": "pay_link_reminder", "enabled": True,
                "cron_hour": 10, "cron_minute": 0, "cron_dow": None,
                "notes": "Ödenmemiş Stripe pay-by-link'ler için 24 saat sonra otomatik hatırlatma e-postası (yeni link üretir)",
                "created_at": datetime.now(timezone.utc).isoformat(), "created_by": "system"})
            logger.info("Scheduler: seeded pay_link_reminder daily cron (10:00 UTC)")
        if not await db.scheduler_config.find_one({"property_id": "", "job": "pickup_weekly_report"}, {"_id": 1}):
            await db.scheduler_config.insert_one({
                "property_id": "", "job": "pickup_weekly_report", "enabled": True,
                "cron_hour": 7, "cron_minute": 0, "cron_dow": 0,
                "notes": "Haftalık pickup özeti — her pazartesi admin/manager'lara e-posta",
                "created_at": datetime.now(timezone.utc).isoformat(), "created_by": "system"})
            logger.info("Scheduler: seeded pickup_weekly_report weekly cron (Mon 07:00 UTC)")
        if not await db.scheduler_config.find_one({"property_id": "", "job": "eco_sweep"}, {"_id": 1}):
            await db.scheduler_config.insert_one({
                "property_id": "", "job": "eco_sweep", "enabled": True,
                "cron_hour": 3, "cron_minute": 30, "cron_dow": None,
                "notes": "Gece Eco Sweep — boş odaları otomatik eco moda alır (enerji tasarrufu)",
                "created_at": datetime.now(timezone.utc).isoformat(), "created_by": "system"})
            logger.info("Scheduler: seeded eco_sweep nightly cron (03:30 UTC)")
        if not await db.scheduler_config.find_one({"property_id": "", "job": "mobile_daily_pulse"}, {"_id": 1}):
            await db.scheduler_config.insert_one({
                "property_id": "", "job": "mobile_daily_pulse", "enabled": True,
                "cron_hour": 9, "cron_minute": 0, "cron_dow": None,
                "notes": "Mobil push günlük özeti — güçlü satış günü ve kanal düşüşü bildirimleri",
                "created_at": datetime.now(timezone.utc).isoformat(), "created_by": "system"})
            logger.info("Scheduler: seeded mobile_daily_pulse cron (09:00 UTC)")
    except Exception as e:
        logger.warning("pickup/pay-link cron seed failed: %s", e)

    # Iter 320 — Seed weekly geo-validate cron (every Monday 03:00 UTC).
    # Idempotent: upsert + don't override user changes if already exists.
    try:
        existing = await db.scheduler_config.find_one({"property_id": "", "job": "fleet_geo_validate"}, {"_id": 0})
        if not existing:
            await db.scheduler_config.insert_one({
                "property_id": "",
                "job": "fleet_geo_validate",
                "enabled": True,
                "cron_hour": 3,
                "cron_minute": 0,
                "cron_dow": 0,  # 0 = Monday (Python weekday())
                "notes": "Haftalık fleet-wide koordinat doğrulama + otomatik onarım (Camden→Boston bug koruyucu)",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "system",
            })
            logger.info("Scheduler: seeded fleet_geo_validate weekly cron (Mon 03:00 UTC)")
    except Exception as e:
        logger.warning("fleet_geo_validate cron seed failed: %s", e)

    # Iter 326 — Seed weekly fleet Vision enrich cron (Mon 04:00 UTC, after geo-validate).
    try:
        existing_v = await db.scheduler_config.find_one({"property_id": "", "job": "fleet_vision_enrich"}, {"_id": 0})
        if not existing_v:
            await db.scheduler_config.insert_one({
                "property_id": "",
                "job": "fleet_vision_enrich",
                "enabled": True,
                "cron_hour": 4,
                "cron_minute": 0,
                "cron_dow": 0,  # Monday
                "notes": "Haftalık fleet-wide rakip Vision enrich — oda sayıları + fiyatları taze tutar (GPT-4o-mini screenshot OCR)",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "system",
            })
            logger.info("Scheduler: seeded fleet_vision_enrich weekly cron (Mon 04:00 UTC)")
    except Exception as e:
        logger.warning("fleet_vision_enrich cron seed failed: %s", e)

    # Iter 333 — Seed weekly fleet competitor PRICE scrape cron (Mon 05:00
    # UTC, after Vision enrich). Populates per-date prices on every
    # competitor row so the Per-Hotel Price Trend chart is fresh.
    try:
        existing_c = await db.scheduler_config.find_one({"property_id": "", "job": "fleet_competitor_price_scan"}, {"_id": 0})
        if not existing_c:
            await db.scheduler_config.insert_one({
                "property_id": "",
                "job": "fleet_competitor_price_scan",
                "enabled": True,
                "cron_hour": 5,
                "cron_minute": 0,
                "cron_dow": 0,  # Monday
                "notes": "Haftalık fleet-wide rakip 30-günlük Booking.com fiyat taraması — Per-Hotel Price Trend chart'ı otomatik günceller",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "system",
            })
            logger.info("Scheduler: seeded fleet_competitor_price_scan weekly cron (Mon 05:00 UTC)")
    except Exception as e:
        logger.warning("fleet_competitor_price_scan cron seed failed: %s", e)

    # Ensure Playwright Chromium binary exists — it disappears between pod
    # restarts on this environment. Use the resilient helper from
    # booking_scraper which has timeout, logging, and idempotent checks.
    #
    # iter 330 (user-approved): we now run this BLOCKING during startup.
    # Background task was racing the first /competitors/discover request
    # and producing 500s while the binary downloaded. The trade-off is a
    # 10-30s one-time delay on cold start when the binary is missing.
    # Subsequent boots are instant because the version-aware check sees
    # the correct revision on disk and returns immediately.
    try:
        from utils.booking_scraper import _ensure_chromium_installed
        ok = await _ensure_chromium_installed()
        if ok:
            logger.info("Playwright Chromium ready at startup ✓")
        else:
            logger.warning("Playwright Chromium ensure returned False — discover may 500")
    except Exception as e:
        logger.warning("Playwright Chromium ensure failed: %s", e)

    # Best-effort: start a local Tor daemon for free IP rotation. Booking.com
    # blocks our static pod IP, but Tor exit relays give us a moving target.
    # `USE_TOR_FOR_BOOKING=0` env var disables this entirely.
    try:
        from utils.tor_manager import tor_enabled, ensure_tor_running_async
        if tor_enabled():
            ok = await ensure_tor_running_async(wait_seconds=20)
            logger.info("Tor SOCKS proxy %s for Booking scraping",
                        "ready ✓" if ok else "NOT available — falling back to direct pod IP")
    except Exception as e:
        logger.warning("Tor startup failed: %s", e)

    # tick workers (workers.py — ROADMAP P1 refactor)
    import asyncio
    from workers import scheduled_checkout_loop, reports_loop, otb_snapshot_loop, str_scan_loop, revenue_brain_loop, complaint_task_sync_loop, complaint_sla_loop, rating_trend_alert_loop, winback_reminder_loop, publish_day_alert_loop, praise_hunter_loop
    asyncio.create_task(scheduled_checkout_loop(db))
    asyncio.create_task(reports_loop(db))
    asyncio.create_task(otb_snapshot_loop(db))
    asyncio.create_task(str_scan_loop(db))
    asyncio.create_task(revenue_brain_loop(db))
    asyncio.create_task(complaint_task_sync_loop(db))
    asyncio.create_task(complaint_sla_loop(db))
    asyncio.create_task(rating_trend_alert_loop(db))
    asyncio.create_task(winback_reminder_loop(db))
    asyncio.create_task(publish_day_alert_loop(db))
    asyncio.create_task(praise_hunter_loop(db))
    from workers import winning_topic_loop, social_report_loop, photo_contest_loop, email_dispatch_loop
    asyncio.create_task(winning_topic_loop(db))
    asyncio.create_task(social_report_loop(db))
    asyncio.create_task(photo_contest_loop(db))
    asyncio.create_task(email_dispatch_loop(db))

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

("Admin user seeded and indexes created")
