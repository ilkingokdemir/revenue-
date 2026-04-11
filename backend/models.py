"""
Pydantic models for the Hotel Review Hub & Booking Engine.
Extracted from server.py for maintainability.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime, timezone
import uuid
import secrets


# ==================== REVIEW HUB MODELS ====================

class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class Review(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str = "default"
    platform: str
    guest_name: str
    guest_avatar: Optional[str] = None
    rating: int
    review_text: str
    review_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stay_date: Optional[str] = None
    room_type: Optional[str] = None
    response_status: str = "pending"
    response_text: Optional[str] = None
    response_date: Optional[datetime] = None
    drafted_by: Optional[str] = None
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None
    external_review_id: Optional[str] = None
    synced_to_platform: bool = False
    response_uniqueness_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ReviewCreate(BaseModel):
    property_id: str = "default"
    platform: str
    guest_name: str
    guest_avatar: Optional[str] = None
    rating: int
    review_text: str
    stay_date: Optional[str] = None
    room_type: Optional[str] = None

class ReviewResponse(BaseModel):
    response_text: str

class AIGenerateRequest(BaseModel):
    review_id: str
    tone: str = "professional"
    language: str = "auto"

class AIGenerateResponse(BaseModel):
    generated_text: str
    detected_language: Optional[str] = None

class NotificationSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    notify_negative_reviews: bool = True
    negative_threshold: int = 2
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class NotificationSettingsUpdate(BaseModel):
    email: Optional[str] = None
    notify_negative_reviews: Optional[bool] = None
    negative_threshold: Optional[int] = None
    enabled: Optional[bool] = None

class ReportSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    frequency: str = "weekly"
    include_competitor_comparison: bool = True
    include_sentiment_summary: bool = True
    include_action_items: bool = True
    enabled: bool = True
    last_sent: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ReportSettingsUpdate(BaseModel):
    email: Optional[str] = None
    frequency: Optional[str] = None
    include_competitor_comparison: Optional[bool] = None
    include_sentiment_summary: Optional[bool] = None
    include_action_items: Optional[bool] = None
    enabled: Optional[bool] = None

class ResponseTemplate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str
    content: str
    tone: str = "professional"
    usage_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ResponseTemplateCreate(BaseModel):
    name: str
    category: str
    content: str
    tone: str = "professional"

class ResponseTemplateUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    tone: Optional[str] = None

class SentimentAnalysis(BaseModel):
    sentiment: str
    score: float
    urgency: str
    topics: List[str]
    suggested_tone: str
    suggested_category: str
    key_issues: List[str]
    key_praises: List[str]

class CompetitorData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    platform: str
    avg_rating: float
    total_reviews: int
    response_rate: float
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CompetitorCreate(BaseModel):
    name: str
    platform: str
    avg_rating: float
    total_reviews: int
    response_rate: float

class CompetitorUpdate(BaseModel):
    name: Optional[str] = None
    platform: Optional[str] = None
    avg_rating: Optional[float] = None
    total_reviews: Optional[int] = None
    response_rate: Optional[float] = None

class AnalyticsData(BaseModel):
    period: str
    total_reviews: int
    avg_rating: float
    sentiment_distribution: dict
    response_rate: float
    avg_response_time_hours: float
    top_topics: List[dict]
    rating_trend: List[dict]


# ==================== INTEGRATION MODELS ====================

class PlatformIntegration(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    platform: str
    status: str = "disconnected"
    credentials_configured: bool = False
    last_sync: Optional[datetime] = None
    sync_enabled: bool = False
    location_id: Optional[str] = None
    property_name: Optional[str] = None
    total_reviews_synced: int = 0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PlatformCredentials(BaseModel):
    platform: str
    credentials: Dict[str, str]
    location_id: Optional[str] = None
    property_name: Optional[str] = None

class ManualReviewImport(BaseModel):
    platform: str
    guest_name: str
    rating: int
    review_text: str
    review_date: Optional[str] = None
    stay_date: Optional[str] = None
    room_type: Optional[str] = None
    external_review_id: Optional[str] = None

class SyncResponse(BaseModel):
    platform: str
    reviews_synced: int
    errors: List[str]
    status: str


# ==================== BRANDING MODELS ====================

class BrandingSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    app_name: str = "Review Hub"
    subtitle: str = "Manage all your guest reviews in one place"
    primary_color: str = "#3E5245"
    accent_color: str = "#D4A373"
    logo_url: Optional[str] = None
    powered_by_text: str = ""
    powered_by_visible: bool = False
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BrandingSettingsUpdate(BaseModel):
    app_name: Optional[str] = None
    subtitle: Optional[str] = None
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None
    powered_by_text: Optional[str] = None
    powered_by_visible: Optional[bool] = None


# ==================== AUTH MODELS ====================

class UserRegister(BaseModel):
    email: str
    password: str
    name: str
    role: str = "receptionist"
    department: str = "front_desk"

class UserLogin(BaseModel):
    email: str
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None

class ApprovalAction(BaseModel):
    action: str
    notes: Optional[str] = None


# ==================== PROPERTY MODELS ====================

class Property(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    property_type: str = "hotel"
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PropertyCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    property_type: str = "hotel"

class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    property_type: Optional[str] = None
    is_active: Optional[bool] = None

VALID_ROLES = ["admin", "manager", "receptionist"]
VALID_DEPARTMENTS = ["front_desk", "management", "housekeeping", "food_beverage", "maintenance", "spa_wellness", "concierge"]
VALID_PROPERTY_TYPES = ["hotel", "resort", "hostel", "apartment", "villa", "boutique", "motel", "bed_breakfast"]


# ==================== BOOKING ENGINE MODELS ====================

class RoomType(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str
    description: str = ""
    max_guests: int = 2
    bed_type: str = "double"
    size_sqm: int = 0
    amenities: List[str] = []
    photos: List[str] = []
    base_price: float = 0
    currency: str = "GBP"
    is_active: bool = True
    total_rooms: int = 1
    free_cancellation: bool = True
    breakfast_included: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class RoomTypeCreate(BaseModel):
    property_id: str
    name: str
    description: str = ""
    max_guests: int = 2
    bed_type: str = "double"
    size_sqm: int = 0
    amenities: List[str] = []
    photos: List[str] = []
    base_price: float = 0
    currency: str = "GBP"
    total_rooms: int = 1
    free_cancellation: bool = True
    breakfast_included: bool = False

class RoomTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_guests: Optional[int] = None
    bed_type: Optional[str] = None
    size_sqm: Optional[int] = None
    amenities: Optional[List[str]] = None
    photos: Optional[List[str]] = None
    base_price: Optional[float] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None
    total_rooms: Optional[int] = None
    free_cancellation: Optional[bool] = None
    breakfast_included: Optional[bool] = None

class Booking(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    room_type_id: str
    guest_name: str
    guest_email: str
    guest_phone: str = ""
    check_in: str
    check_out: str
    adults: int = 1
    children: int = 0
    rooms: int = 1
    total_price: float = 0
    currency: str = "GBP"
    status: str = "confirmed"
    payment_status: str = "pending"
    special_requests: str = ""
    booking_ref: str = Field(default_factory=lambda: f"MHB-{secrets.token_hex(4).upper()}")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class BookingCreate(BaseModel):
    property_id: str
    room_type_id: str
    guest_name: str
    guest_email: str
    guest_phone: str = ""
    check_in: str
    check_out: str
    adults: int = 1
    children: int = 0
    rooms: int = 1
    special_requests: str = ""


# ==================== INBOUND WEBHOOK MODEL ====================

class InboundReviewPayload(BaseModel):
    external_review_id: str
    guest_name: str
    rating: int
    review_text: str
    review_date: Optional[str] = None
    stay_date: Optional[str] = None
    room_type: Optional[str] = None
    guest_avatar: Optional[str] = None
    property_external_id: Optional[str] = None
    property_id: Optional[str] = "default"
    language: Optional[str] = None
    reviewer_avatar: Optional[str] = None


# ==================== TEMPLATE CUSTOMIZATION MODELS ====================

class TemplateSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    template_id: str = "booking-classic"
    # Hotel info overrides
    hotel_name: str = ""
    tagline: str = ""
    description: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    address: str = ""
    # Branding
    logo_url: str = ""
    hero_image_url: str = ""
    gallery_images: List[str] = []
    # Color overrides (empty = use template defaults)
    primary_color: str = ""
    accent_color: str = ""
    header_bg_color: str = ""
    header_text_color: str = ""
    body_bg_color: str = ""
    # Feature toggles
    show_rating_badge: Optional[bool] = None
    show_urgency: Optional[bool] = None
    show_free_cancellation: Optional[bool] = None
    show_security_badges: Optional[bool] = None
    # Custom text
    footer_text: str = ""
    booking_button_text: str = ""
    welcome_message: str = ""
    # Social links
    facebook_url: str = ""
    instagram_url: str = ""
    twitter_url: str = ""
    tripadvisor_url: str = ""
    # SEO
    meta_title: str = ""
    meta_description: str = ""
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class TemplateSettingsUpdate(BaseModel):
    template_id: Optional[str] = None
    hotel_name: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    hero_image_url: Optional[str] = None
    gallery_images: Optional[List[str]] = None
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None
    header_bg_color: Optional[str] = None
    header_text_color: Optional[str] = None
    body_bg_color: Optional[str] = None
    show_rating_badge: Optional[bool] = None
    show_urgency: Optional[bool] = None
    show_free_cancellation: Optional[bool] = None
    show_security_badges: Optional[bool] = None
    footer_text: Optional[str] = None
    booking_button_text: Optional[str] = None
    welcome_message: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    twitter_url: Optional[str] = None
    tripadvisor_url: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
