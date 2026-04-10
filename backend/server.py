from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File
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
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage
import resend

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

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
    platform: str  # booking.com, airbnb, expedia, tripadvisor, google, trip.com
    guest_name: str
    guest_avatar: Optional[str] = None
    rating: int  # 1-5
    review_text: str
    review_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stay_date: Optional[str] = None
    room_type: Optional[str] = None
    response_status: str = "pending"  # pending, responded
    response_text: Optional[str] = None
    response_date: Optional[datetime] = None
    external_review_id: Optional[str] = None  # ID from original platform
    synced_to_platform: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ReviewCreate(BaseModel):
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
    tone: str = "professional"  # professional, friendly, apologetic

class AIGenerateResponse(BaseModel):
    generated_text: str

class NotificationSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    notify_negative_reviews: bool = True
    negative_threshold: int = 2  # Reviews with rating <= this value trigger notification
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
    frequency: str = "weekly"  # daily, weekly, monthly
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
    category: str  # positive, negative, neutral, complaint, praise
    content: str
    tone: str = "professional"  # professional, friendly, apologetic
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
    sentiment: str  # positive, negative, neutral, mixed
    score: float  # -1 to 1
    urgency: str  # low, medium, high, critical
    topics: List[str]  # cleanliness, staff, amenities, location, value, food, noise, etc.
    suggested_tone: str  # professional, friendly, apologetic
    suggested_category: str  # matches template categories
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

class PlatformIntegration(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    platform: str  # google, booking, tripadvisor, airbnb, expedia, trip
    status: str = "disconnected"  # connected, disconnected, error
    credentials_configured: bool = False
    last_sync: Optional[datetime] = None
    sync_enabled: bool = False
    location_id: Optional[str] = None  # Platform-specific location/property ID
    property_name: Optional[str] = None
    total_reviews_synced: int = 0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PlatformCredentials(BaseModel):
    platform: str
    credentials: Dict[str, str]  # Platform-specific credentials
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
    platform: Optional[str] = None,
    status: Optional[str] = None,
    rating: Optional[int] = None
):
    """Get all reviews with optional filters"""
    query = {}
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
    
    updated_review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
    deserialize_review(updated_review)
    return updated_review

@api_router.post("/reviews/generate-ai-response", response_model=AIGenerateResponse)
async def generate_ai_response(request: AIGenerateRequest):
    """Generate AI response for a review using GPT-5.2"""
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
    
    system_message = f"""You are a professional hotel manager responding to guest reviews. 
Your responses should be {tone}.
Keep responses concise (2-3 paragraphs max).
Always thank the guest for their feedback.
If the review is negative, acknowledge their concerns and offer to make things right.
If positive, express gratitude and invite them back.
Sign off as 'The Management Team'."""

    prompt = f"""Please write a response to this hotel review:

Platform: {review['platform']}
Rating: {review['rating']}/5 stars
Guest: {review['guest_name']}
Review: {review['review_text']}

Write a {tone} response to this review."""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"review-{request.review_id}",
            system_message=system_message
        ).with_model("openai", "gpt-5.2")
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        return AIGenerateResponse(generated_text=response)
    except Exception as e:
        logger.error(f"AI generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

@api_router.get("/reviews/stats/summary")
async def get_review_stats():
    """Get review statistics summary"""
    total = await db.reviews.count_documents({})
    responded = await db.reviews.count_documents({"response_status": "responded"})
    pending = await db.reviews.count_documents({"response_status": "pending"})
    
    # Calculate average rating
    pipeline = [
        {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}
    ]
    result = await db.reviews.aggregate(pipeline).to_list(1)
    avg_rating = result[0]["avg_rating"] if result else 0
    
    # Platform breakdown
    platform_pipeline = [
        {"$group": {"_id": "$platform", "count": {"$sum": 1}}}
    ]
    platform_result = await db.reviews.aggregate(platform_pipeline).to_list(100)
    platforms = {item["_id"]: item["count"] for item in platform_result}
    
    return {
        "total_reviews": total,
        "responded": responded,
        "pending": pending,
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

# ==================== PLATFORM INTEGRATION ROUTES ====================

@api_router.get("/integrations")
async def get_integrations():
    """Get all platform integrations status"""
    integrations = await db.platform_integrations.find({}, {"_id": 0}).to_list(100)
    
    # Ensure all platforms have an entry
    platforms = ["google", "booking.com", "tripadvisor", "airbnb", "expedia", "trip.com"]
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
        return {
            "status": "logged",
            "message": f"Reply saved locally. Platform sync not configured for {platform}.",
            "synced_to_platform": False
        }
    
    # Attempt to post to platform
    success = False
    if platform == "google" and review.get("external_review_id"):
        location_id = integration.get("location_id")
        success = await PlatformService.post_google_reply(
            location_id,
            review["external_review_id"],
            reply_text
        )
    
    return {
        "status": "synced" if success else "logged",
        "message": f"Reply {'posted to {platform}' if success else 'saved locally'}",
        "synced_to_platform": success
    }

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
        "manual_import": {
            "name": "Manual Import",
            "description": "Import reviews via CSV file or manual entry when API access is not available",
            "csv_format": {
                "columns": ["platform", "guest_name", "rating", "review_text", "review_date", "stay_date", "room_type", "external_id"],
                "example": "google,John Doe,5,Great stay!,2024-01-15,January 2024,Deluxe Room,abc123"
            }
        }
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
