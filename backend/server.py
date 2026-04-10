from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
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
