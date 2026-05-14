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
from routes.messaging import create_messaging_router
from routes.messaging_advanced import create_messaging_advanced_router
from routes.surveys import create_surveys_router
from routes.automation import create_automation_router
from routes.dashboard import create_dashboard_router
from routes.staff_performance import create_staff_performance_router
from routes.calendar_gss import create_calendar_gss_router
from routes.housekeeping import create_housekeeping_router
from routes.admin import create_admin_router
from routes.night_audit import create_night_audit_router
from routes.loyalty_logbook_forecast import create_loyalty_router
from routes.guest_profiles import create_guest_profiles_router
from routes.campaigns import create_campaigns_router
from routes.guest_app import create_guest_app_router
from routes.smart_locks import create_smart_locks_router
from routes.setup_wizard import create_setup_wizard_router
from routes.stock import create_stock_router
from routes.finance_ext.accounting import create_accounting_router
from routes.finance_ext.accounting_advanced import create_accounting_advanced_router
from routes.finance_ext.bank_reconciliation import create_bank_reconciliation_router
from routes.enhanced_features import create_enhanced_features_router
from routes.pos import create_pos_router
from routes.pos_advanced import create_pos_advanced_router
from routes.pos_ai import create_pos_ai_router
from routes.finance_ext.payments import create_payments_router
from routes.terminal import create_terminal_router
from routes.auth_routes import create_auth_router
from routes.connections import create_connections_router
from routes.reviews import create_reviews_router
from routes.integrations import create_integrations_router
from routes.bookings import create_bookings_router
from routes.guest_payment import create_guest_payment_router
from routes.guest_journey import create_guest_journey_router
from routes.maintenance import create_maintenance_router
from routes.rate_manager import create_rate_manager_router
from routes.reports import create_reports_router
from routes.booking_widget import create_booking_widget_router
from routes.operations import create_operations_router
from routes.shifts import create_shifts_router, create_shifts_v2_router
from routes.rates_grid import create_rates_grid_router
from routes.workforce_extras import create_workforce_extras_router
from routes.notifications import create_notifications_router
from routes.finance_ext.finance import create_finance_router
from routes.my_tasks import create_my_tasks_router
from routes.lost_found import create_lost_found_router
from routes.events import create_events_router
from routes.settings_hub import create_settings_hub_router
from routes.revenue import create_revenue_router
from routes.revenue_advanced import create_revenue_advanced_router
from routes.revenue_phase2 import create_revenue_phase2_router
from routes.revenue_copilot import create_revenue_copilot_router
from routes.revenue_exports import create_revenue_exports_router
from routes.market_robot import create_market_robot_router
from routes.dynamic_pricing import create_dynamic_pricing_router
from routes.event_intelligence import create_event_intelligence_router
from routes.parity_analysis import create_parity_analysis_router
from routes.channel_manager import create_channel_manager_router
from routes.historical_pricing import create_historical_pricing_router
from routes.revenue_intelligence import create_revenue_intelligence_router
from routes.demand_radar import create_demand_radar_router
from routes.compset_intel import create_compset_intel_router
from routes.price_alerts import create_price_alerts_router
from routes.booking_timeline import create_booking_timeline_router
from routes.guest_services import create_guest_services_router
from routes.displacement import create_displacement_router
from routes.los_optimizer import create_los_optimizer_router
from routes.mobile_api import create_mobile_router
from routes.weekly_digest import create_weekly_digest_router
from routes.upsell_engine import create_upsell_router
from routes.rate_scraper import create_rate_scraper_router
from routes.enhanced_dashboard import create_enhanced_dashboard_router
from routes.reports_hub import create_reports_hub_router
from routes.finance_ext.finance_pl import create_finance_pl_router
from routes.shift_scheduler import create_shift_scheduler_router
from routes.pass_over import create_pass_over_router
from routes.compliance import create_compliance_router
from routes.tr_compliance import create_tr_compliance_router
from routes.eu_compliance import create_eu_compliance_router
from routes.channel_revenue import create_channel_revenue_router
from routes.pos_kds import create_pos_kds_router
from routes.loyalty_v2 import create_loyalty_v2_router
from routes.sentiment import create_sentiment_router as create_cross_sentiment_router
from routes.self_checkin_v2 import create_self_checkin_v2_router
from routes.brand_portal import create_brand_portal_router
from routes.ops_v2 import create_ops_v2_router
from routes.forecast_v2 import create_forecast_v2_router
from routes.anomaly_detection import create_anomaly_router
from routes.tipping import create_tipping_router
from routes.guest_portal_v2 import create_guest_portal_v2_router
from routes.conference_sc import create_conference_sc_router
from routes.copilot import create_copilot_router
from routes.image_ai import create_image_ai_router
from routes.fnb_tabs import create_fnb_tabs_router
from routes.bi_feed import create_bi_feed_router
from routes.hk_turnover import create_hk_turnover_router
from routes.pricing_explain import create_pricing_explain_router
from routes.loyalty_tier import create_loyalty_tier_router
from routes.banquet_orders import create_banquet_orders_router
from routes.help import create_help_router
from routes.site_feasibility import create_site_feasibility_router
from routes.self_checkin_auto import create_self_checkin_auto_router
from routes.lock_sdk import create_lock_sdk_router
from routes.recipe_cogs import create_recipe_cogs_router
from routes.voice_concierge import create_voice_concierge_router
from routes.whatsapp_voice import create_whatsapp_voice_router
from routes.ai.ai_predictions import create_ai_predictions_router
from routes.laundry import create_laundry_router
from routes.payroll import create_payroll_router
from routes.expenses import create_expenses_router
from routes.finance_ext.cashflow import create_cashflow_router
from routes.marketplace import create_marketplace_router
from routes.arrivals import create_arrivals_router
from routes.contracts import create_contracts_router
from routes.legal_documents import create_legal_documents_router
from routes.staff_onboarding import create_staff_onboarding_router
from routes.payroll_matrix import create_payroll_matrix_router
from routes.bug_tracker import create_bug_tracker_router
from routes.roles import create_roles_router
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
            # Tip? mark as paid
            if webhook_response.metadata.get("type") == "tip":
                await db.tips.update_one(
                    {"session_id": webhook_response.session_id},
                    {"$set": {"status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}}
                )
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return {"status": "error", "message": str(e)}

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
from routes.review_sentiment import create_sentiment_router
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
marketplace_router = create_marketplace_router(db, require_roles, LlmChat, UserMessage)
api_router.include_router(marketplace_router)
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
from routes.collisions import create_collisions_router
collisions_router = create_collisions_router(db)
api_router.include_router(collisions_router)
from routes.profit_os import create_profit_os_router
profit_os_router = create_profit_os_router(db)
api_router.include_router(profit_os_router)
from routes.oos_blocks import create_oos_router
oos_router = create_oos_router(db)
api_router.include_router(oos_router)
from routes.city_ledger import create_city_ledger_router
city_ledger_router = create_city_ledger_router(db, resend)
api_router.include_router(city_ledger_router)
from routes.finance_ext.tax_config import create_tax_config_router
tax_config_router = create_tax_config_router(db)
api_router.include_router(tax_config_router)
from routes.finance_ext.deposit_policies import create_deposit_policies_router
deposit_policies_router = create_deposit_policies_router(db)
api_router.include_router(deposit_policies_router)
from routes.unified_inbox import create_unified_inbox_router
unified_inbox_router = create_unified_inbox_router(db)
api_router.include_router(unified_inbox_router)
from routes.competitor_parity import create_competitor_parity_router
competitor_parity_router = create_competitor_parity_router(db, require_roles)
api_router.include_router(competitor_parity_router)
from routes.forecast_accuracy import create_forecast_accuracy_router
forecast_accuracy_router = create_forecast_accuracy_router(db, require_roles)
api_router.include_router(forecast_accuracy_router)
from routes.concierge import create_concierge_router
concierge_router = create_concierge_router(db)
api_router.include_router(concierge_router)
from routes.sustainability import create_sustainability_router
sustainability_router = create_sustainability_router(db, require_roles)
api_router.include_router(sustainability_router)
from routes.nightly_recap import create_nightly_recap_router, create_concierge_topics_router
nightly_recap_router = create_nightly_recap_router(db, require_roles)
api_router.include_router(nightly_recap_router)
concierge_topics_router = create_concierge_topics_router(db, require_roles)
api_router.include_router(concierge_topics_router)
from routes.finance_ext.accounting_export import create_accounting_export_router
accounting_export_router = create_accounting_export_router(db, require_roles)
api_router.include_router(accounting_export_router)
from routes.currency_fx import create_currency_fx_router
currency_fx_router = create_currency_fx_router(db)
api_router.include_router(currency_fx_router)
from routes.rate_structure import create_rate_structure_router
rate_structure_router = create_rate_structure_router(db)
api_router.include_router(rate_structure_router)
from routes.groups import create_groups_router
groups_router = create_groups_router(db)
api_router.include_router(groups_router)
from routes.security.gdpr import create_gdpr_router
gdpr_router = create_gdpr_router(db)
api_router.include_router(gdpr_router)
from routes.og_images import create_og_router
og_router = create_og_router()
api_router.include_router(og_router)
from routes.property_onboarding import create_onboarding_router
onboarding_router = create_onboarding_router(db)
api_router.include_router(onboarding_router)
from routes.demo_seeder import create_demo_seeder_router
demo_seeder_router = create_demo_seeder_router(db)
api_router.include_router(demo_seeder_router)

# ===== Iter 156 — Top-10 competitor gap features =====
from routes.night_audit_close import create_night_audit_close_router
api_router.include_router(create_night_audit_close_router(db, require_roles))

from routes.finance_ext.deposit_ledger import create_deposit_ledger_router
api_router.include_router(create_deposit_ledger_router(db, require_roles))

from routes.commission_recon import create_commission_recon_router
api_router.include_router(create_commission_recon_router(db, require_roles))

from routes.gift_cards import create_gift_cards_router
api_router.include_router(create_gift_cards_router(db, require_roles))

# Note: review_sentiment router is registered earlier (before reviews_router) to avoid route conflicts

from routes.guest_rfm import create_rfm_router
api_router.include_router(create_rfm_router(db, require_roles))

from routes.preventive_maintenance import create_preventive_maintenance_router
api_router.include_router(create_preventive_maintenance_router(db, require_roles))

from routes.asset_register import create_asset_register_router
api_router.include_router(create_asset_register_router(db, require_roles))

from routes.cash_drawer import create_cash_drawer_router
api_router.include_router(create_cash_drawer_router(db, require_roles))

from routes.two_factor_auth import create_2fa_router
api_router.include_router(create_2fa_router(db, require_roles, get_current_user))

# ===== Iter 157 — Revenue Health + IP Allowlist + PCI Card Vault =====
from routes.revenue_health import create_revenue_health_router
api_router.include_router(create_revenue_health_router(db, require_roles))

from routes.ip_allowlist import create_ip_allowlist_router
api_router.include_router(create_ip_allowlist_router(db, require_roles))

from routes.card_vault import create_card_vault_router
api_router.include_router(create_card_vault_router(db, require_roles))

# Iter 158 — Deposit Automation (bridges deposit_policies + card_vault + folio_items)
from routes.finance_ext.deposit_automation import create_deposit_automation_router
deposit_auto_router = create_deposit_automation_router(db, require_roles)
api_router.include_router(deposit_auto_router)

# Iter 159 — Scheduler (async background task runner, currently nightly auto-deposit)
from routes.scheduler import create_scheduler_router, scheduler_loop
_auto_capture_fn = getattr(deposit_auto_router, "run_capture", None)

async def _job_auto_deposit_capture(property_id: str) -> dict:
    """Scheduled job: run a full (non-dry) deposit capture for a property."""
    if _auto_capture_fn is None:
        return {"error": "auto-capture helper missing"}
    return await _auto_capture_fn(property_id=property_id, dry_run=False,
                                  only_ids=None, max_charges=200,
                                  triggered_by="scheduler")

JOB_HANDLERS = {"auto_deposit_capture": _job_auto_deposit_capture}
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

# Iter 160 — Channel Manager MVP (restrictions + inbound + parity)
from routes.channel_restrictions import create_channel_restrictions_router
api_router.include_router(create_channel_restrictions_router(db, require_roles))

from routes.channel_inbound import create_channel_inbound_router
api_router.include_router(create_channel_inbound_router(db, require_roles))

from routes.channel_parity import create_channel_parity_router
api_router.include_router(create_channel_parity_router(db, require_roles))

# Iter 161 — OTA Health Dashboard (composite of parity + commission + direct + balance)
from routes.ota_health import create_ota_health_router
api_router.include_router(create_ota_health_router(db, require_roles))

# Iter 162 — Channel mappings + Sync queue with exponential backoff
from routes.channel_mappings import create_channel_mappings_router
api_router.include_router(create_channel_mappings_router(db, require_roles))

from routes.sync_queue import create_sync_queue_router, process_due_tasks
api_router.include_router(create_sync_queue_router(db, require_roles))

# Wire the sync-queue worker into the scheduler engine from Iter 159
async def _job_sync_queue_tick(property_id: str) -> dict:
    return await process_due_tasks(db, max_tasks=50)

JOB_HANDLERS["sync_queue_tick"] = _job_sync_queue_tick

# Iter 163 — Channel Hub (configs, payload profiles, publish jobs,
# price overrides, channel audit, benchmark cockpit)
from routes.channel_hub import create_channel_hub_router, nightly_dry_publish
api_router.include_router(create_channel_hub_router(db, require_roles))

# Wire the nightly dry-run publisher into the scheduler engine
async def _job_nightly_dry_publish(property_id: str) -> dict:
    return await nightly_dry_publish(db, property_id)

JOB_HANDLERS["nightly_dry_publish"] = _job_nightly_dry_publish

# Iter 164 — Inventory Allocations (pooled / dedicated / capped per channel×room)
from routes.inventory_allocations import create_inventory_allocations_router
api_router.include_router(create_inventory_allocations_router(db, require_roles))

# Iter 165 — Group Blocks (group reservations)
from routes.group_blocks import create_group_blocks_router
api_router.include_router(create_group_blocks_router(db, require_roles))

# Iter 165 — Smart Rate Control (bulk rate/availability editor)
from routes.smart_rate_control import create_smart_rate_control_router
api_router.include_router(create_smart_rate_control_router(db, require_roles))

from routes.late_checkout import create_late_checkout_router
api_router.include_router(create_late_checkout_router(db, require_roles))

from routes.service_recovery import create_service_recovery_router
api_router.include_router(create_service_recovery_router(db, require_roles))

from routes.room_qr import create_room_qr_router
api_router.include_router(create_room_qr_router(db, require_roles))

from routes.finance_ext.tax_presets import create_tax_presets_router
api_router.include_router(create_tax_presets_router(db, require_roles))

from routes.walkin import create_walkin_router
api_router.include_router(create_walkin_router(db, require_roles))

from routes.no_show import create_no_show_router
api_router.include_router(create_no_show_router(db, require_roles))

from routes.guest_prefs import create_guest_prefs_router
api_router.include_router(create_guest_prefs_router(db, require_roles))

from routes.cleaning_checklists import create_cleaning_checklists_router
api_router.include_router(create_cleaning_checklists_router(db, require_roles))

from routes.room_move import create_room_move_router
api_router.include_router(create_room_move_router(db, require_roles))

from routes.lost_found_match import create_lost_found_match_router
api_router.include_router(create_lost_found_match_router(db, require_roles))

from routes.glitch_log import create_glitch_log_router
api_router.include_router(create_glitch_log_router(db, require_roles))

from routes.sops import create_sops_router
api_router.include_router(create_sops_router(db, require_roles))

from routes.automation_rules import create_automation_router, fire_event as _fire_event
api_router.include_router(create_automation_router(db, require_roles))
# Expose for other modules to import: routes.automation_rules.fire_event
__all__ = ["_fire_event"]

from routes.team_chat import create_team_chat_router
api_router.include_router(create_team_chat_router(db, require_roles))

from routes.crm_360 import create_crm360_router
api_router.include_router(create_crm360_router(db, require_roles))

from routes.channels_v2 import create_channels_v2_router
api_router.include_router(create_channels_v2_router(db, require_roles))

from routes.group_rooming import create_group_rooming_router
api_router.include_router(create_group_rooming_router(db, require_roles))

from routes.attribution import create_attribution_router
api_router.include_router(create_attribution_router(db, require_roles))

from routes.timeslots import create_timeslot_router
api_router.include_router(create_timeslot_router(db, require_roles))

from routes.staff_ops import create_staff_ops_router
api_router.include_router(create_staff_ops_router(db, require_roles))

from routes.revenue_protection import create_revenue_protection_router
api_router.include_router(create_revenue_protection_router(db, require_roles))

from routes.spaces import create_spaces_router
api_router.include_router(create_spaces_router(db, require_roles))

from routes.extras_v1 import create_extras_router
api_router.include_router(create_extras_router(db, require_roles))

from routes.ai.agents_b2b import create_agents_router
api_router.include_router(create_agents_router(db, require_roles))

from routes.extras_v2 import create_extras_v2_router
api_router.include_router(create_extras_v2_router(db, require_roles))

# ===== Batch 6 (final P0): Pre-Auth, Chargeback, Web Push, PMS-CRS, Public API =====
from routes.preauth import create_preauth_router
api_router.include_router(create_preauth_router(db, require_roles))

from routes.chargeback import create_chargeback_router
api_router.include_router(create_chargeback_router(db, require_roles))

from routes.web_push import create_web_push_router
api_router.include_router(create_web_push_router(db, require_roles))

from routes.pms_crs import create_pms_crs_router
api_router.include_router(create_pms_crs_router(db, require_roles))

from routes.public_api import create_public_api_router
api_router.include_router(create_public_api_router(db, require_roles))

# ===== Batch 7 (P1 keyless): Mid-stay survey, Live folio PDF, A/B tests, Pre-arrival drip, Menu engineering =====
from routes.mid_stay import create_mid_stay_router
api_router.include_router(create_mid_stay_router(db, require_roles))

from routes.folio_live import create_folio_live_router
api_router.include_router(create_folio_live_router(db, require_roles))

from routes.ab_test import create_ab_test_router
api_router.include_router(create_ab_test_router(db, require_roles))

from routes.pre_arrival import create_pre_arrival_router
api_router.include_router(create_pre_arrival_router(db, require_roles))

from routes.menu_engineering import create_menu_engineering_router
api_router.include_router(create_menu_engineering_router(db, require_roles))

# ===== Batch 8 (P1 keyless): SR Voucher, Folio split, Loyalty auto, Late checkout offer, OTA stop-sell forecast =====
from routes.sr_voucher import create_service_recovery_voucher_router
api_router.include_router(create_service_recovery_voucher_router(db, require_roles))

from routes.folio_split import create_folio_split_router
api_router.include_router(create_folio_split_router(db, require_roles))

from routes.loyalty_auto import create_loyalty_auto_router
api_router.include_router(create_loyalty_auto_router(db, require_roles))

from routes.late_checkout_offer import create_late_checkout_offer_router
api_router.include_router(create_late_checkout_offer_router(db, require_roles))

from routes.ota_stop_sell_forecast import create_ota_stop_sell_forecast_router
api_router.include_router(create_ota_stop_sell_forecast_router(db, require_roles))

# ===== Batch 9 (P1 keyless): Msg Templates, Birthday auto-discount, Low-stock alerts, Rebook CTA, Stay extension, Long-stay discount =====
from routes.msg_templates import create_msg_templates_router
api_router.include_router(create_msg_templates_router(db, require_roles))

from routes.birthday import create_birthday_router
api_router.include_router(create_birthday_router(db, require_roles))

from routes.low_stock import create_low_stock_router
api_router.include_router(create_low_stock_router(db, require_roles))

from routes.rebook import create_rebook_router
api_router.include_router(create_rebook_router(db, require_roles))

from routes.stay_ext import create_stay_ext_router
api_router.include_router(create_stay_ext_router(db, require_roles))

from routes.long_stay import create_long_stay_router
api_router.include_router(create_long_stay_router(db, require_roles))

# ===== Batch 10 (P1 keyless final): Cancel insurance, Group rooming wizard, Tax reports v2, Check-in slots =====
from routes.cancel_insurance import create_cancel_insurance_router
api_router.include_router(create_cancel_insurance_router(db, require_roles))

from routes.group_rooming_wiz import create_group_rooming_router
api_router.include_router(create_group_rooming_router(db, require_roles))

from routes.finance_ext.tax_reports_v2 import create_tax_reports_router
api_router.include_router(create_tax_reports_router(db, require_roles))

from routes.ci_slots import create_ci_slots_router
api_router.include_router(create_ci_slots_router(db, require_roles))

# ===== Batch 11: Tier-1 Master Operations Dashboard (aggregates KPIs from all 50 keyless features) =====
from routes.tier1_dashboard import create_tier1_dashboard_router
api_router.include_router(create_tier1_dashboard_router(db, require_roles))

# ===== Competitor Parity v3 (Booking Engine v2, Groups, Owner Portal, Spa, Loyalty Tiers,
#                              Budget vs Actual, Compset, Webhooks & API keys, Automation Analytics) =====
from routes.booking_engine_v2 import create_booking_engine_v2_router
api_router.include_router(create_booking_engine_v2_router(db, require_roles))

# Note: Group Bookings module already exists at routes/group_blocks.py
# (used by GroupBlocksPanel). The newer routes/group_bookings.py is a
# parallel implementation kept on disk for reference but NOT registered
# to avoid path collisions at /group-blocks.

from routes.owner_portal import create_owner_portal_router
api_router.include_router(create_owner_portal_router(db, require_roles))

from routes.spa_activities import create_spa_router
api_router.include_router(create_spa_router(db, require_roles))

from routes.loyalty_tiers import create_loyalty_tiers_router
api_router.include_router(create_loyalty_tiers_router(db, require_roles))

from routes.budget_actual import create_budget_router
api_router.include_router(create_budget_router(db, require_roles))

from routes.compset import create_compset_router
api_router.include_router(create_compset_router(db, require_roles))

from routes.webhooks_api_keys import create_webhooks_api_keys_router
api_router.include_router(create_webhooks_api_keys_router(db, require_roles))

from routes.automation_analytics import create_automation_analytics_router
api_router.include_router(create_automation_analytics_router(db, require_roles))

# ===== Meeting & Events Sales (MICE pipeline) =====
from routes.meetings_sales import create_meetings_router
api_router.include_router(create_meetings_router(db, require_roles))

# ===== F&B POS Integration Hub (Simphony / Lightspeed / Square / Toast) =====
from routes.fnb_pos_hub import create_fnb_pos_router
api_router.include_router(create_fnb_pos_router(db, require_roles))

# ===== Owner Self-Service Login (Iter 282) =====
from routes.owner_self_service import create_owner_auth_router
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

# ===== Booking.com Premier prototype (Iter 290 - XML push, pre-cert ready) =====
from routes.distribution.booking_com import create_booking_com_router
api_router.include_router(create_booking_com_router(db, require_roles))

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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

("Admin user seeded and indexes created")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

