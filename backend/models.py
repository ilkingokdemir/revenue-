"""
Pydantic models for the Hotel Review Hub & Booking Engine.
Extracted from server.py for maintainability.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
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

VALID_ROLES = ["admin", "manager", "receptionist", "housekeeper", "maintenance"]
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
    damage_waiver: bool = False

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



# ==================== AMENITY CATALOG ====================

AMENITY_CATALOG = {
    "bathroom": {
        "label": "Bathroom",
        "items": [
            "En-suite bathroom", "Shared bathroom", "Rain shower", "Walk-in shower", "Bathtub",
            "Jacuzzi bath", "Bidet", "Hair dryer", "Bathrobes", "Slippers",
            "Toiletries", "Premium toiletries", "Shampoo", "Conditioner", "Body wash",
            "Towels", "Heated towel rail", "Magnifying mirror", "Scales",
        ]
    },
    "bedroom": {
        "label": "Bedroom & Comfort",
        "items": [
            "Air conditioning", "Heating", "Ceiling fan", "Blackout curtains",
            "Premium bedding", "Hypoallergenic bedding", "Extra pillows", "Pillow menu",
            "Soundproofing", "Wardrobe", "Walk-in wardrobe", "Iron & ironing board",
            "Clothes rack", "Hangers", "Full-length mirror", "Alarm clock",
            "Crib available", "Extra bed available",
        ]
    },
    "kitchen": {
        "label": "Kitchen & Dining",
        "items": [
            "Kitchenette", "Full kitchen", "Microwave", "Refrigerator", "Mini fridge",
            "Minibar", "Complimentary minibar", "Oven", "Hob / Stovetop", "Dishwasher",
            "Toaster", "Kettle", "Coffee machine", "Nespresso machine", "Tea/coffee maker",
            "Dining area", "Dining table", "Cookware & utensils", "Plates & cutlery",
            "Wine glasses", "Washing machine", "Dryer", "Washer/dryer combo",
        ]
    },
    "technology": {
        "label": "Technology & Connectivity",
        "items": [
            "Free WiFi", "High-speed WiFi", "Wired internet", "Smart TV",
            "Flat-screen TV", "55\" Smart TV", "65\" Smart TV", "Cable TV", "Netflix",
            "Streaming services", "Bluetooth speaker", "USB charging ports",
            "Universal power sockets", "Telephone", "Tablet", "Smart home controls",
            "Chromecast", "HDMI input",
        ]
    },
    "entertainment": {
        "label": "Entertainment & Leisure",
        "items": [
            "Books & magazines", "Board games", "Gaming console",
            "DVD player", "Music system", "Balcony", "Terrace", "Patio",
            "Garden view", "Sea view", "City view", "Pool view", "Mountain view",
            "Private pool", "Hot tub", "BBQ facilities",
        ]
    },
    "business": {
        "label": "Business & Work",
        "items": [
            "Work desk", "Ergonomic chair", "Desk lamp", "Stationery",
            "Printer access", "Fax machine", "Meeting room access",
            "Co-working space access", "Business centre", "Scanner",
        ]
    },
    "safety": {
        "label": "Safety & Security",
        "items": [
            "In-room safe", "Laptop-size safe", "Smoke detector",
            "Carbon monoxide detector", "Fire extinguisher", "First aid kit",
            "Electronic door lock", "Security camera (common areas)",
            "24-hour security", "CCTV", "Peephole", "Door chain",
        ]
    },
    "accessibility": {
        "label": "Accessibility",
        "items": [
            "Wheelchair accessible", "Roll-in shower", "Grab bars",
            "Lowered sink", "Lowered peephole", "Wide doorways",
            "Step-free access", "Elevator access", "Visual fire alarm",
            "Hearing-accessible", "Braille signage",
        ]
    },
    "wellness": {
        "label": "Wellness & Spa",
        "items": [
            "Spa access", "Sauna", "Steam room", "Gym access",
            "Fitness equipment", "Yoga mat", "Massage available",
            "Indoor pool access", "Outdoor pool access",
            "Rooftop pool", "Beach access",
        ]
    },
    "services": {
        "label": "Services & Extras",
        "items": [
            "Room service", "24-hour room service", "Daily housekeeping",
            "Turndown service", "Concierge", "Laundry service", "Dry cleaning",
            "Luggage storage", "Wake-up service", "Breakfast included",
            "Airport shuttle", "Car hire", "Bicycle rental", "Tour desk",
            "Babysitting", "Pet friendly", "Parking available",
            "Free parking", "Valet parking", "EV charging",
            "Late checkout", "Early check-in", "Express check-in/out",
            "Priority check-in", "Newspaper delivery",
        ]
    },
}

FACILITY_CATALOG = {
    "general": {
        "label": "General",
        "items": [
            "24-hour front desk", "Concierge service", "Luggage storage",
            "Tour desk", "Currency exchange", "ATM on-site", "Gift shop",
            "Elevator / Lift", "Non-smoking property", "Smoking area",
        ]
    },
    "dining": {
        "label": "Food & Drink",
        "items": [
            "Restaurant", "Bar / Lounge", "Breakfast buffet", "Room service",
            "Coffee shop / Cafe", "Vending machines", "Packed lunches",
            "Special diet menus", "BBQ area", "Shared kitchen",
        ]
    },
    "wellness": {
        "label": "Wellness & Recreation",
        "items": [
            "Swimming pool (indoor)", "Swimming pool (outdoor)", "Rooftop pool",
            "Gym / Fitness centre", "Spa", "Sauna", "Steam room",
            "Hot tub / Jacuzzi", "Massage services", "Yoga studio",
            "Tennis court", "Golf course", "Kids' playground",
            "Game room", "Library", "Cinema room",
        ]
    },
    "business": {
        "label": "Business",
        "items": [
            "Business centre", "Meeting rooms", "Conference facilities",
            "Banquet hall", "Co-working space", "Fax / Photocopy services",
        ]
    },
    "transport": {
        "label": "Transport & Parking",
        "items": [
            "Free parking", "Paid parking", "Underground parking",
            "Valet parking", "EV charging station", "Airport shuttle (free)",
            "Airport shuttle (paid)", "Car hire desk", "Bicycle rental",
            "Bicycle storage",
        ]
    },
    "outdoor": {
        "label": "Outdoor & Views",
        "items": [
            "Garden", "Terrace", "Rooftop terrace", "Sun terrace",
            "Sun loungers", "Beach access", "Private beach",
            "Waterfront", "Courtyard",
        ]
    },
    "family": {
        "label": "Family & Accessibility",
        "items": [
            "Family rooms", "Kids' club", "Babysitting service",
            "Baby changing facilities", "High chairs", "Crib / Cot available",
            "Wheelchair accessible", "Accessible parking",
            "Step-free access", "Pet friendly",
        ]
    },
    "laundry": {
        "label": "Laundry & Housekeeping",
        "items": [
            "Laundry service", "Self-service laundry", "Dry cleaning",
            "Ironing service", "Daily housekeeping", "Shoe shine",
        ]
    },
}


# ==================== PROMO CODE MODELS ====================

class PromoCode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str = ""
    code: str
    description: str = ""
    discount_type: str = "percentage"
    discount_value: float = 10
    min_nights: int = 0
    min_amount: float = 0
    max_uses: int = 0
    used_count: int = 0
    valid_from: str = ""
    valid_until: str = ""
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PromoCodeCreate(BaseModel):
    property_id: str = ""
    code: str
    description: str = ""
    discount_type: str = "percentage"
    discount_value: float = 10
    min_nights: int = 0
    min_amount: float = 0
    max_uses: int = 0
    valid_from: str = ""
    valid_until: str = ""


# ==================== ADD-ON SERVICES ====================

class AddOnService(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str
    description: str = ""
    category: str = "experience"
    price: float = 0
    price_type: str = "per_stay"
    icon: str = ""
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class AddOnServiceCreate(BaseModel):
    property_id: str
    name: str
    description: str = ""
    category: str = "experience"
    price: float = 0
    price_type: str = "per_stay"
    icon: str = ""


# ==================== HOTEL POLICIES ====================

class HotelPolicies(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    check_in_from: str = "15:00"
    check_in_until: str = "23:00"
    check_out_from: str = "07:00"
    check_out_until: str = "11:00"
    cancellation_policy: str = "free"
    cancellation_hours: int = 24
    cancellation_text: str = ""
    children_policy: str = "Children of all ages are welcome."
    pet_policy: str = "Pets are not allowed."
    smoking_policy: str = "Smoking is not permitted anywhere on the property."
    payment_methods: List[str] = ["Visa", "Mastercard", "American Express"]
    accepted_currencies: List[str] = ["GBP"]
    damage_deposit: float = 0
    house_rules: List[str] = []
    extra_info: str = ""
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class HotelPoliciesUpdate(BaseModel):
    check_in_from: Optional[str] = None
    check_in_until: Optional[str] = None
    check_out_from: Optional[str] = None
    check_out_until: Optional[str] = None
    cancellation_policy: Optional[str] = None
    cancellation_hours: Optional[int] = None
    cancellation_text: Optional[str] = None
    children_policy: Optional[str] = None
    pet_policy: Optional[str] = None
    smoking_policy: Optional[str] = None
    payment_methods: Optional[List[str]] = None
    accepted_currencies: Optional[List[str]] = None
    damage_deposit: Optional[float] = None
    house_rules: Optional[List[str]] = None
    extra_info: Optional[str] = None


# ==================== PROPERTY FACILITIES ====================

class PropertyFacilities(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    facilities: List[str] = []
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())



# ==================== UPSELL ITEMS ====================

UPSELL_TEMPLATES = [
    {"name": "Early Check-in", "description": "Arrive early and settle in from 12:00 PM", "category": "convenience", "price": 25, "price_type": "per_stay", "icon": "clock"},
    {"name": "Late Check-out", "description": "Enjoy a relaxed departure until 3:00 PM", "category": "convenience", "price": 25, "price_type": "per_stay", "icon": "clock-afternoon"},
    {"name": "Breakfast Package", "description": "Full English breakfast served daily", "category": "dining", "price": 15, "price_type": "per_person_per_night", "icon": "coffee"},
    {"name": "Airport Transfer", "description": "Private car to/from the airport", "category": "transport", "price": 45, "price_type": "per_stay", "icon": "car"},
    {"name": "Welcome Champagne", "description": "Bottle of champagne waiting in your room", "category": "experience", "price": 35, "price_type": "per_stay", "icon": "champagne"},
    {"name": "Spa Access", "description": "Full access to spa and wellness facilities", "category": "wellness", "price": 20, "price_type": "per_person_per_night", "icon": "flower-lotus"},
    {"name": "Room Upgrade", "description": "Upgrade to the next room category (subject to availability)", "category": "upgrade", "price": 40, "price_type": "per_night", "icon": "arrow-up"},
    {"name": "Parking Space", "description": "Secure on-site parking for your vehicle", "category": "convenience", "price": 15, "price_type": "per_night", "icon": "car-simple"},
    {"name": "Pet Fee", "description": "Bring your furry friend along", "category": "convenience", "price": 20, "price_type": "per_night", "icon": "paw-print"},
    {"name": "Romantic Package", "description": "Rose petals, candles, and a bottle of wine", "category": "experience", "price": 55, "price_type": "per_stay", "icon": "heart"},
]

class UpsellItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str
    description: str = ""
    category: str = "convenience"
    price: float = 0
    price_type: str = "per_stay"  # per_stay, per_night, per_person, per_person_per_night
    icon: str = ""
    is_active: bool = True
    auto_suggest: bool = True  # Whether to auto-show during booking
    sort_order: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class UpsellItemCreate(BaseModel):
    property_id: str
    name: str
    description: str = ""
    category: str = "convenience"
    price: float = 0
    price_type: str = "per_stay"
    icon: str = ""
    auto_suggest: bool = True
    sort_order: int = 0


# ==================== SOCIAL PROOF SETTINGS ====================

class SocialProofSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    property_id: str
    enabled: bool = True
    show_viewing_count: bool = True
    show_recent_bookings: bool = True
    show_rooms_left: bool = True
    show_price_comparison: bool = True
    ota_markup_percent: float = 18  # How much more OTAs charge vs direct
    direct_saving_label: str = "Book direct & save {percent}%"
    booking_com_label: str = "Booking.com"
    expedia_label: str = "Expedia"
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())



# ==================== GUEST REVIEW COLLECTION ====================

class ReviewCollectionSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    property_id: str
    enabled: bool = True
    delay_hours: int = 24  # Hours after checkout to send email
    email_subject: str = "How was your stay at {hotel_name}?"
    email_heading: str = "We'd love to hear from you"
    email_body: str = "Thank you for staying with us. Your feedback helps us improve and helps other travellers make informed decisions."
    reminder_enabled: bool = True
    reminder_delay_hours: int = 72
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class GuestReview(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    booking_ref: str
    guest_name: str
    guest_email: str
    rating: int  # 1-5
    title: str = ""
    review_text: str = ""
    room_type: str = ""
    stay_dates: str = ""
    status: str = "published"  # published, pending, hidden
    source: str = "direct"  # direct collection
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== SELF CHECK-IN ====================

class CheckInSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    property_id: str
    enabled: bool = True
    send_hours_before: int = 24  # Hours before check-in to send link
    require_id_upload: bool = True
    require_terms_acceptance: bool = True
    terms_text: str = "I agree to the hotel's terms and conditions and house rules."
    welcome_message: str = "Welcome! Please complete your check-in before arrival."
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class GuestCheckIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    booking_ref: str
    property_id: str
    guest_name: str
    guest_email: str
    status: str = "pending"  # pending, completed, expired
    id_uploaded: bool = False
    terms_accepted: bool = False
    room_assignment: str = ""
    special_notes: str = ""
    completed_at: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== GUEST PORTAL ====================

class GuestPortalSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    guest_email: str
    magic_token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    expires_at: str = Field(default_factory=lambda: (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat())
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== CART ABANDONMENT ====================

class AbandonedCart(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    guest_email: str = ""
    guest_name: str = ""
    room_type_id: str = ""
    room_name: str = ""
    check_in: str = ""
    check_out: str = ""
    adults: int = 2
    total_price: float = 0
    recovery_token: str = Field(default_factory=lambda: secrets.token_urlsafe(16))
    status: str = "abandoned"  # abandoned, recovered, expired, email_sent
    email_sent_at: str = ""
    recovered_at: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== MULTI-CURRENCY ====================

CURRENCY_CONFIG = {
    "GBP": {"symbol": "£", "code": "GBP", "name": "British Pound"},
    "USD": {"symbol": "$", "code": "USD", "name": "US Dollar"},
    "EUR": {"symbol": "€", "code": "EUR", "name": "Euro"},
    "AED": {"symbol": "د.إ", "code": "AED", "name": "UAE Dirham"},
    "SAR": {"symbol": "﷼", "code": "SAR", "name": "Saudi Riyal"},
    "JPY": {"symbol": "¥", "code": "JPY", "name": "Japanese Yen"},
    "CNY": {"symbol": "¥", "code": "CNY", "name": "Chinese Yuan"},
    "KRW": {"symbol": "₩", "code": "KRW", "name": "South Korean Won"},
    "INR": {"symbol": "₹", "code": "INR", "name": "Indian Rupee"},
    "BRL": {"symbol": "R$", "code": "BRL", "name": "Brazilian Real"},
    "RUB": {"symbol": "₽", "code": "RUB", "name": "Russian Ruble"},
    "AUD": {"symbol": "A$", "code": "AUD", "name": "Australian Dollar"},
    "CAD": {"symbol": "C$", "code": "CAD", "name": "Canadian Dollar"},
    "CHF": {"symbol": "CHF", "code": "CHF", "name": "Swiss Franc"},
    "SGD": {"symbol": "S$", "code": "SGD", "name": "Singapore Dollar"},
    "THB": {"symbol": "฿", "code": "THB", "name": "Thai Baht"},
    "MYR": {"symbol": "RM", "code": "MYR", "name": "Malaysian Ringgit"},
    "TRY": {"symbol": "₺", "code": "TRY", "name": "Turkish Lira"},
}

# ==================== GROUP BOOKING ====================

class GroupBookingRequest(BaseModel):
    property_id: str
    contact_name: str
    contact_email: str
    contact_phone: str = ""
    company_name: str = ""
    event_type: str = ""  # corporate, wedding, conference, tour_group, other
    check_in: str
    check_out: str
    total_rooms: int = 1
    total_guests: int = 1
    room_preferences: str = ""
    special_requirements: str = ""
    budget_range: str = ""

class GroupBooking(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    contact_name: str
    contact_email: str
    contact_phone: str = ""
    company_name: str = ""
    event_type: str = ""
    check_in: str
    check_out: str
    total_rooms: int = 1
    total_guests: int = 1
    room_preferences: str = ""
    special_requirements: str = ""
    budget_range: str = ""
    status: str = "pending"  # pending, quoted, confirmed, cancelled
    admin_notes: str = ""
    quoted_price: float = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== HOURLY / SPACE BOOKING ====================

SPACE_TYPES = [
    {"name": "Meeting Room", "category": "business", "icon": "presentation-chart", "hourly_rate": 25, "capacity": 10},
    {"name": "Conference Room", "category": "business", "icon": "users", "hourly_rate": 50, "capacity": 30},
    {"name": "Boardroom", "category": "business", "icon": "crown", "hourly_rate": 75, "capacity": 12},
    {"name": "Co-working Desk", "category": "workspace", "icon": "desktop", "hourly_rate": 8, "capacity": 1},
    {"name": "Private Office", "category": "workspace", "icon": "door", "hourly_rate": 20, "capacity": 4},
    {"name": "Event Hall", "category": "events", "icon": "confetti", "hourly_rate": 150, "capacity": 100},
    {"name": "Parking Space", "category": "parking", "icon": "car", "hourly_rate": 3, "capacity": 1},
    {"name": "Spa Treatment Room", "category": "wellness", "icon": "flower-lotus", "hourly_rate": 40, "capacity": 2},
]

class PropertySpace(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str
    category: str = "business"
    description: str = ""
    capacity: int = 1
    hourly_rate: float = 0
    half_day_rate: float = 0
    full_day_rate: float = 0
    icon: str = ""
    amenities: list = Field(default_factory=list)
    photos: list = Field(default_factory=list)
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class SpaceBooking(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    space_id: str
    space_name: str = ""
    guest_name: str
    guest_email: str
    guest_phone: str = ""
    booking_date: str
    start_time: str
    end_time: str
    hours: float = 1
    total_price: float = 0
    status: str = "confirmed"
    notes: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== GUEST MESSAGING HUB MODELS ====================

MESSAGING_CHANNELS = ["whatsapp", "email", "sms", "internal", "telegram", "booking.com", "airbnb", "expedia", "website_chat"]
CONVERSATION_STATUSES = ["new", "in_progress", "waiting", "resolved", "snoozed"]
CONVERSATION_PRIORITIES = ["low", "medium", "high", "urgent"]

class Conversation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    guest_name: str
    guest_email: str = ""
    guest_phone: str = ""
    channel: str = "internal"
    status: str = "new"
    priority: str = "medium"
    sentiment: str = ""
    assigned_to: str = ""
    assigned_name: str = ""
    tags: list = Field(default_factory=list)
    booking_ref: str = ""
    guest_booking_info: dict = Field(default_factory=dict)
    last_message_preview: str = ""
    last_message_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    unread_count: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    sender_type: str = "guest"  # guest, staff, ai, system
    sender_name: str = ""
    content: str
    channel: str = "internal"
    is_ai_suggested: bool = False
    read: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class QuickReply(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str = "global"
    name: str
    content: str
    category: str = "general"
    shortcut: str = ""
    usage_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ChannelSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    property_id: str
    # WhatsApp (Meta Cloud API)
    whatsapp_enabled: bool = False
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_business_id: str = ""
    # Telegram Bot
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    # SMS (Twilio)
    sms_enabled: bool = False
    sms_provider: str = "twilio"
    sms_api_key: str = ""  # Twilio Account SID
    sms_api_secret: str = ""  # Twilio Auth Token
    sms_sender_number: str = ""
    # Email
    email_enabled: bool = True
    # Auto-reply
    auto_reply_enabled: bool = False
    auto_reply_message: str = "Thank you for reaching out! Our team will respond shortly."
    welcome_message: str = "Welcome! How can we help you today?"
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class AutoReplyRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str = "global"
    name: str
    keywords: list = Field(default_factory=list)  # trigger keywords
    response: str
    category: str = "faq"
    enabled: bool = True
    match_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

AUTO_REPLY_DEFAULTS = [
    {"name": "Check-in & Check-out Times", "keywords": ["check in", "checkin", "check-in", "check out", "checkout", "check-out", "what time"],
     "response": "Our check-in time is from 15:00 (3 PM) and check-out is by 11:00 (11 AM). Early check-in and late check-out are subject to availability — feel free to ask!", "category": "faq"},
    {"name": "WiFi Password", "keywords": ["wifi", "wi-fi", "internet", "password", "wireless"],
     "response": "Our complimentary WiFi network is 'Hotel_Guest'. No password required — just connect and accept the terms. Enjoy!", "category": "faq"},
    {"name": "Parking Information", "keywords": ["parking", "car park", "garage", "vehicle"],
     "response": "We offer on-site parking at £15 per day. Please share your vehicle registration number and we'll reserve a spot for you.", "category": "faq"},
    {"name": "Restaurant Hours", "keywords": ["restaurant", "breakfast", "lunch", "dinner", "food", "eat", "dining"],
     "response": "Our restaurant hours: Breakfast 07:00-10:30, Lunch 12:00-14:30, Dinner 18:00-22:00. Room service is available 24/7.", "category": "faq"},
    {"name": "Room Service", "keywords": ["room service", "order food", "menu", "in-room dining"],
     "response": "Room service is available 24/7! You can find the menu in your room or request it through our guest portal. Just call reception to place your order.", "category": "faq"},
    {"name": "Late Checkout", "keywords": ["late checkout", "late check-out", "extend stay", "stay longer"],
     "response": "Late checkout is available subject to availability. We can offer checkout until 14:00 for an additional £30. Would you like me to arrange this?", "category": "faq"},
    {"name": "Airport Transfer", "keywords": ["airport", "transfer", "taxi", "cab", "transport", "shuttle"],
     "response": "We can arrange airport transfers for you! Please let us know your flight details and preferred pickup time, and we'll organise a comfortable ride.", "category": "faq"},
    {"name": "Spa & Gym", "keywords": ["spa", "gym", "fitness", "pool", "swimming", "sauna", "massage"],
     "response": "Our fitness centre is open 24/7 on the ground floor. Spa treatments are available by appointment from 09:00-21:00. Would you like to book a treatment?", "category": "faq"},
    {"name": "Luggage Storage", "keywords": ["luggage", "bags", "storage", "store bags", "keep bags"],
     "response": "Yes, we offer complimentary luggage storage! You can leave your bags at reception before check-in or after check-out. Just ask our front desk team.", "category": "faq"},
    {"name": "Pet Policy", "keywords": ["pet", "dog", "cat", "animal", "pet friendly"],
     "response": "We are pet-friendly! Well-behaved dogs are welcome with a small cleaning fee of £25 per stay. Please let us know in advance so we can prepare your room.", "category": "faq"},
]

QUICK_REPLY_TEMPLATES = [
    {"name": "Welcome", "content": "Welcome to our hotel! How can I assist you today?", "category": "greeting", "shortcut": "/welcome"},
    {"name": "Check-in Time", "content": "Check-in is available from 15:00 and check-out is by 11:00. Early check-in may be available upon request.", "category": "info", "shortcut": "/checkin"},
    {"name": "WiFi Info", "content": "Our complimentary WiFi network is 'Hotel_Guest'. No password is needed — just accept the terms.", "category": "info", "shortcut": "/wifi"},
    {"name": "Room Service", "content": "Room service is available 24/7. You can find the menu in your room or request it digitally through our guest portal.", "category": "service", "shortcut": "/roomservice"},
    {"name": "Parking", "content": "We offer on-site parking at £15/day. Please let us know your vehicle registration and we'll reserve a spot.", "category": "info", "shortcut": "/parking"},
    {"name": "Late Checkout", "content": "Late checkout is subject to availability. We can offer checkout until 14:00 for an additional £30. Shall I arrange this?", "category": "service", "shortcut": "/latecheckout"},
    {"name": "Restaurant Hours", "content": "Our restaurant is open for breakfast (07:00-10:30), lunch (12:00-14:30), and dinner (18:00-22:00).", "category": "info", "shortcut": "/restaurant"},
    {"name": "Thank You", "content": "Thank you for choosing to stay with us! We hope you enjoyed your visit and look forward to welcoming you again.", "category": "farewell", "shortcut": "/thanks"},
    {"name": "Transfer Request", "content": "I'll connect you with the right team member who can help you with this. One moment please.", "category": "service", "shortcut": "/transfer"},
    {"name": "Complaint Acknowledgement", "content": "I'm truly sorry to hear about this experience. Your feedback is important and I'm escalating this to our manager right away.", "category": "complaint", "shortcut": "/sorry"},
]


# ==================== AUTOMATION ENGINE MODELS ====================

AUTOMATION_TRIGGERS = ["pre_arrival", "day_of_arrival", "during_stay", "post_checkout", "cart_abandonment"]
AUTOMATION_CHANNELS = ["email", "whatsapp", "sms", "telegram", "internal"]

class AutomationRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str
    trigger: str  # pre_arrival, day_of_arrival, during_stay, post_checkout, cart_abandonment
    timing_hours: int = -24  # negative = before event, positive = after. e.g. -24 = 24h before check-in
    channel: str = "email"
    subject: str = ""  # for email
    message_template: str = ""
    enabled: bool = True
    total_sent: int = 0
    total_opened: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class AutomationLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    rule_name: str = ""
    property_id: str
    guest_name: str
    guest_email: str = ""
    guest_phone: str = ""
    booking_ref: str = ""
    channel: str
    message: str
    status: str = "sent"  # sent, failed, opened
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

AUTOMATION_DEFAULTS = [
    {
        "name": "Pre-Arrival Welcome",
        "trigger": "pre_arrival",
        "timing_hours": -24,
        "channel": "email",
        "subject": "We're looking forward to welcoming you!",
        "message_template": "Dear {guest_name},\n\nWe're excited to welcome you to {hotel_name} tomorrow!\n\nHere are some useful details:\n- Check-in: from 15:00\n- Address: {hotel_address}\n- Your booking ref: {booking_ref}\n\nYou can also use our online self check-in to save time at reception:\n{checkin_link}\n\nIf you need anything before your arrival, simply reply to this message.\n\nWarm regards,\n{hotel_name} Team",
    },
    {
        "name": "Day-of-Arrival Reminder",
        "trigger": "day_of_arrival",
        "timing_hours": 0,
        "channel": "whatsapp",
        "subject": "",
        "message_template": "Hello {guest_name}! Welcome to {hotel_name} today. Check-in is from 15:00. WiFi: Hotel_Guest (no password). Need anything? Just reply here!",
    },
    {
        "name": "Mid-Stay Satisfaction Check",
        "trigger": "during_stay",
        "timing_hours": 24,
        "channel": "whatsapp",
        "subject": "",
        "message_template": "Hi {guest_name}, how is your stay at {hotel_name} so far? Is there anything we can do to make it even better? We're here to help!",
    },
    {
        "name": "Post-Checkout Thank You & Review",
        "trigger": "post_checkout",
        "timing_hours": 2,
        "channel": "email",
        "subject": "Thank you for staying with us!",
        "message_template": "Dear {guest_name},\n\nThank you for choosing {hotel_name}! We hope you had a wonderful stay.\n\nWe'd love to hear your feedback — it takes just 2 minutes:\n{review_link}\n\nYour review helps us improve and helps other travellers find the right place to stay.\n\nWe look forward to welcoming you again!\n\nWarm regards,\n{hotel_name} Team",
    },
    {
        "name": "Post-Checkout WhatsApp Follow-up",
        "trigger": "post_checkout",
        "timing_hours": 4,
        "channel": "whatsapp",
        "subject": "",
        "message_template": "Hi {guest_name}, thank you for staying at {hotel_name}! We'd love a quick review: {review_link} Safe travels!",
    },
    {
        "name": "Cart Abandonment Recovery",
        "trigger": "cart_abandonment",
        "timing_hours": 1,
        "channel": "email",
        "subject": "You left something behind...",
        "message_template": "Hi {guest_name},\n\nWe noticed you were looking at rooms at {hotel_name} but didn't complete your booking.\n\nYour selected room is still available — book now before it's gone!\n\n{cart_link}\n\nNeed help? Just reply to this message.\n\n{hotel_name} Team",
    },
]


# ==================== HOUSEKEEPING MODELS ====================

ROOM_STATUSES = ["clean", "dirty", "inspected", "out_of_order", "in_progress"]
TASK_PRIORITIES = ["low", "normal", "high", "urgent"]
TASK_TYPES = ["cleaning", "deep_clean", "turnover", "maintenance", "inspection", "amenity_restock"]

class HousekeepingTask(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    room_number: str = ""
    room_type_id: str = ""
    task_type: str = "cleaning"
    priority: str = "normal"
    status: str = "pending"  # pending, in_progress, completed, cancelled
    assigned_to: str = ""
    assigned_name: str = ""
    notes: str = ""
    checklist: list = Field(default_factory=list)
    due_date: str = ""
    completed_at: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class RoomStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    room_number: str
    room_type_id: str = ""
    floor: str = ""
    status: str = "clean"  # clean, dirty, inspected, out_of_order, in_progress
    guest_name: str = ""
    booking_ref: str = ""
    check_in: str = ""
    check_out: str = ""
    last_cleaned_at: str = ""
    last_cleaned_by: str = ""
    maintenance_notes: str = ""
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class MaintenanceRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    room_number: str = ""
    title: str = ""
    category: str = "general"  # plumbing, electrical, hvac, furniture, general
    description: str
    priority: str = "normal"
    status: str = "open"  # open, assigned, in_progress, resolved, closed
    assigned_to: str = ""
    reported_by: str = ""
    photos: list = Field(default_factory=list)
    resolution_notes: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str = ""


# ==================== GUEST PROFILE / CRM MODELS ====================

class GuestProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str = ""
    phone: str = ""
    name: str
    vip: bool = False
    tags: list = Field(default_factory=list)
    preferences: list = Field(default_factory=list)  # list of preference IDs: high_floor, quiet_room, etc.
    notes: list = Field(default_factory=list)  # list of {text, date, by} objects
    total_stays: int = 0
    total_spend: float = 0
    avg_rating_given: float = 0
    first_stay: str = ""
    last_stay: str = ""
    loyalty_tier: str = "standard"  # standard, silver, gold, platinum
    source: str = ""  # direct, booking.com, expedia, etc.
    nationality: str = ""  # guest nationality
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== CAMPAIGN MANAGER MODELS ====================

CAMPAIGN_CHANNELS = ["email", "whatsapp", "sms", "telegram"]
CAMPAIGN_STATUSES = ["draft", "scheduled", "sending", "sent", "cancelled"]

class Campaign(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str
    channel: str = "email"
    status: str = "draft"
    subject: str = ""
    message: str = ""
    segment: dict = Field(default_factory=dict)  # filters: vip, tags, last_stay, etc.
    scheduled_at: str = ""
    sent_at: str = ""
    total_recipients: int = 0
    total_sent: int = 0
    total_delivered: int = 0
    total_opened: int = 0
    total_clicked: int = 0
    created_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== GUEST APP / DIGITAL DIRECTORY MODELS ====================

class GuestDirectory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    wifi_name: str = ""
    wifi_password: str = ""
    welcome_message: str = ""
    checkout_time: str = "11:00"
    checkin_time: str = "15:00"


# ==================== SMART LOCK / DIGITAL KEY MODELS ====================

LOCK_PROVIDERS = ["ttlock", "nuki", "august_yale", "salto", "assa_abloy", "generic"]

class SmartLockConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    provider: str = "generic"
    api_key: str = ""
    api_secret: str = ""
    api_url: str = ""
    is_active: bool = False
    rooms: list = Field(default_factory=list)  # [{room_number, lock_id, lock_name}]
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class DigitalKey(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    booking_ref: str
    guest_name: str = ""
    guest_email: str = ""
    room_number: str = ""
    lock_id: str = ""
    access_code: str = Field(default_factory=lambda: str(secrets.randbelow(900000) + 100000))
    valid_from: str = ""
    valid_until: str = ""
    status: str = "active"  # active, expired, revoked
    used_count: int = 0
    last_used_at: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    front_desk_phone: str = ""
    front_desk_email: str = ""
    emergency_phone: str = ""
    address: str = ""
    sections: list = Field(default_factory=list)  # [{title, content, icon}]
    services: list = Field(default_factory=list)  # [{name, description, hours, price, category}]
    local_recommendations: list = Field(default_factory=list)  # [{name, type, distance, description, map_link}]
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())



# ==================== STOCK MANAGEMENT MODELS ====================

STOCK_CATEGORIES = ["food", "beverage", "spirits", "wine", "beer", "soft_drinks", "dairy", "meat", "produce", "dry_goods", "cleaning", "supplies", "other"]
STOCK_UNITS = ["kg", "g", "l", "ml", "pcs", "bottles", "cases", "portions", "packs"]
MOVEMENT_TYPES = ["purchase", "usage", "waste", "transfer_in", "transfer_out", "adjustment", "stocktake"]
OUTLET_TYPES = ["restaurant", "bar", "cafe", "room_service", "kitchen", "main_store"]

class StockProduct(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str
    category: str = "other"
    unit: str = "pcs"
    cost_price: float = 0
    sell_price: float = 0
    supplier: str = ""
    supplier_id: str = ""
    sku: str = ""
    reorder_level: float = 0
    par_level: float = 0
    current_stock: float = 0
    yield_pct: float = 100  # e.g., 70 means 1kg raw → 0.7kg usable
    expiry_days: int = 0  # shelf life in days, 0 = non-perishable
    allergens: list = Field(default_factory=list)  # ["gluten","dairy","nuts","shellfish","eggs","soy","fish","sesame"]
    storage_temp: str = ""  # ambient, chilled, frozen
    price_history: list = Field(default_factory=list)  # [{date, price, supplier}]
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Recipe(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str
    outlet: str = "restaurant"
    category: str = "food"
    sell_price: float = 0
    ingredients: list = Field(default_factory=list)  # [{product_id, product_name, quantity, unit}]
    sub_recipe_ids: list = Field(default_factory=list)  # sub-recipes used in this recipe
    total_cost: float = 0
    margin_pct: float = 0
    allergens: list = Field(default_factory=list)
    nutrition: dict = Field(default_factory=dict)  # {calories, protein_g, carbs_g, fat_g, fiber_g}
    total_sales: int = 0
    total_revenue: float = 0
    popularity_rank: int = 0
    menu_class: str = ""  # star, puzzle, plowhorse, dog (menu engineering)
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class StockMovement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    product_id: str
    product_name: str = ""
    movement_type: str  # purchase, usage, waste, transfer, adjustment, stocktake
    quantity: float
    unit: str = ""
    cost: float = 0
    outlet: str = ""
    from_outlet: str = ""
    to_outlet: str = ""
    reference: str = ""
    notes: str = ""
    recorded_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Outlet(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str
    outlet_type: str = "restaurant"
    is_active: bool = True

class StockVariance(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    product_id: str
    product_name: str = ""
    expected_stock: float = 0
    actual_stock: float = 0
    variance: float = 0
    variance_pct: float = 0
    variance_cost: float = 0
    status: str = "flagged"  # flagged, reviewed, resolved
    notes: str = ""
    recorded_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== HOTEL ACCOUNTING MODELS ====================

INCOME_CATEGORIES = ["room_revenue", "food_beverage", "spa_wellness", "events_meetings", "parking", "laundry", "minibar", "late_checkout", "cancellation_fees", "other"]
EXPENSE_CATEGORIES = ["staff_wages", "food_cost", "beverage_cost", "utilities", "maintenance", "marketing", "insurance", "rent_lease", "supplies", "technology", "commissions", "taxes", "depreciation", "other"]
DEPARTMENTS = ["rooms", "food_beverage", "spa", "events", "front_office", "housekeeping", "maintenance", "admin", "marketing", "other"]

class IncomeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    category: str
    amount: float
    currency: str = "GBP"
    description: str = ""
    department: str = ""
    date: str = ""
    source: str = "manual"  # manual, booking_engine, auto
    reference: str = ""
    created_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ExpenseEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    category: str
    amount: float
    currency: str = "GBP"
    description: str = ""
    department: str = ""
    vendor: str = ""
    date: str = ""
    receipt_ref: str = ""
    approved_by: str = ""
    created_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Budget(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    department: str
    category: str
    month: str  # YYYY-MM
    budgeted_amount: float = 0
    actual_amount: float = 0
    variance: float = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())



# ==================== ENHANCED STOCK MODELS (Apicbase-level) ====================

WASTE_REASONS = ["expired", "spoiled", "overproduction", "damaged", "spillage", "theft_suspected", "quality_issue", "other"]

class SubRecipe(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str
    yield_qty: float = 1
    yield_unit: str = "portions"
    ingredients: list = Field(default_factory=list)
    total_cost: float = 0
    cost_per_unit: float = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Supplier(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    payment_terms: str = "30 days"
    products: list = Field(default_factory=list)
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PurchaseOrder(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    supplier_id: str = ""
    supplier_name: str = ""
    status: str = "draft"  # draft, sent, received, cancelled
    items: list = Field(default_factory=list)  # [{product_id, product_name, quantity, unit, unit_cost, total}]
    total_amount: float = 0
    notes: str = ""
    order_date: str = ""
    expected_date: str = ""
    received_date: str = ""
    created_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class StockCount(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    name: str = ""
    status: str = "in_progress"  # in_progress, completed
    items: list = Field(default_factory=list)  # [{product_id, product_name, expected, counted, variance, variance_cost}]
    total_variance_cost: float = 0
    counted_by: str = ""
    completed_at: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== ENHANCED ACCOUNTING MODELS (M3/Xero-level) ====================

USALI_ACCOUNTS = {
    "revenue": ["4100-room_revenue","4200-fb_revenue","4300-other_revenue","4400-rental_income","4500-spa_revenue"],
    "cost_of_sales": ["5100-food_cost","5200-beverage_cost","5300-labour_cost","5400-other_cos"],
    "operating_expenses": ["6100-admin","6200-marketing","6300-utilities","6400-maintenance","6500-insurance","6600-technology","6700-depreciation"],
    "payroll": ["7100-salaries","7200-benefits","7300-payroll_taxes"],
}

class ChartOfAccount(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    code: str
    name: str
    account_type: str  # revenue, cost_of_sales, operating_expenses, payroll, asset, liability
    parent_code: str = ""
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Invoice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    invoice_type: str = "receivable"  # receivable (guest owes us), payable (we owe supplier)
    invoice_number: str = ""
    counterparty: str = ""  # guest name or supplier name
    items: list = Field(default_factory=list)  # [{description, quantity, unit_price, vat_rate, total}]
    subtotal: float = 0
    vat_amount: float = 0
    total: float = 0
    currency: str = "GBP"
    status: str = "draft"  # draft, sent, paid, overdue, cancelled
    due_date: str = ""
    paid_date: str = ""
    notes: str = ""
    created_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==================== GUEST PAYMENT LINK ====================

class PaymentLink(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    booking_id: str
    booking_ref: str = ""
    property_id: str = ""
    guest_name: str = ""
    guest_email: str = ""
    token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    amount: float = 0
    currency: str = "GBP"
    status: str = "pending"  # pending, paid, expired, cancelled
    extra_charges: list = Field(default_factory=list)  # [{description, amount, category}]
    notes: str = ""
    sent_at: str = ""
    paid_at: str = ""
    expires_at: str = Field(default_factory=lambda: (datetime.now(timezone.utc) + timedelta(days=7)).isoformat())
    created_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
