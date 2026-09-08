"""
Booking Engine Routes: Template Settings, Room Types, Bookings CRUD,
Availability, Reservations, Guest Features, Payments (Stripe)
Extracted from server.py for maintainability
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
from emergentintegrations.llm.chat import LlmChat, UserMessage
import os
import uuid
import asyncio
import resend
import logging

from routes.helpers import log_sync, fire_webhooks
from auth import require_perm

logger = logging.getLogger(__name__)


def create_bookings_router(db, require_roles, LlmChat_dep, UserMessage_dep, resend_dep):
    """Factory function that creates booking routes with injected dependencies"""
    from models import (
        RoomType, RoomTypeCreate, RoomTypeUpdate, Booking, BookingCreate,
        TemplateSettings, TemplateSettingsUpdate,
        AMENITY_CATALOG, FACILITY_CATALOG,
        PromoCode, PromoCodeCreate,
        AddOnService, AddOnServiceCreate,
        HotelPolicies, HotelPoliciesUpdate,
        PropertyFacilities,
        UpsellItem, UpsellItemCreate, SocialProofSettings,
        GroupBookingRequest, GroupBooking,
    )
    router = APIRouter()
    stripe_api_key = os.environ.get("STRIPE_API_KEY", "")
    SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

    # ==================== BOOKING ENGINE ROUTES ====================

    # --- Template Customization ---

    # ==================== AMENITY & FACILITY CATALOGS ====================

    @router.get("/amenities/catalog")
    async def get_amenity_catalog():
        """Public: Get the full categorized amenity catalog"""
        return AMENITY_CATALOG

    @router.get("/facilities/catalog")
    async def get_facility_catalog():
        """Public: Get the full categorized facility catalog"""
        return FACILITY_CATALOG

    # ==================== PROPERTY FACILITIES ====================

    @router.get("/property-facilities/{property_id}")
    async def get_property_facilities(property_id: str):
        """Public: Get property facilities"""
        doc = await db.property_facilities.find_one({"property_id": property_id}, {"_id": 0})
        return doc or {"property_id": property_id, "facilities": []}

    @router.put("/property-facilities/{property_id}")
    async def save_property_facilities(property_id: str, facilities: List[str], current_user: dict = Depends(require_perm("edit_bookings"))):
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

    @router.get("/hotel-policies/{property_id}")
    async def get_hotel_policies(property_id: str):
        """Public: Get hotel policies"""
        doc = await db.hotel_policies.find_one({"property_id": property_id}, {"_id": 0})
        if doc:
            return doc
        return HotelPolicies(property_id=property_id).model_dump()

    @router.put("/hotel-policies/{property_id}")
    async def save_hotel_policies(property_id: str, update: HotelPoliciesUpdate, current_user: dict = Depends(require_perm("edit_bookings"))):
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

    @router.get("/promo-codes")
    async def list_promo_codes(property_id: str = "", current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        """Admin: List promo codes"""
        q = {"property_id": property_id} if property_id else {}
        codes = await db.promo_codes.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
        return codes

    @router.post("/promo-codes")
    async def create_promo_code(data: PromoCodeCreate, current_user: dict = Depends(require_perm("edit_bookings"))):
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

    @router.delete("/promo-codes/{code_id}")
    async def delete_promo_code(code_id: str, current_user: dict = Depends(require_perm("delete_bookings"))):
        """Admin: Delete promo code"""
        await db.promo_codes.delete_one({"id": code_id})
        return {"status": "deleted"}

    @router.put("/promo-codes/{code_id}/toggle")
    async def toggle_promo_code(code_id: str, current_user: dict = Depends(require_perm("edit_bookings"))):
        """Admin: Toggle promo code active status"""
        code = await db.promo_codes.find_one({"id": code_id})
        if not code:
            raise HTTPException(status_code=404, detail="Promo code not found")
        new_status = not code.get("is_active", True)
        await db.promo_codes.update_one({"id": code_id}, {"$set": {"is_active": new_status}})
        return {"is_active": new_status}

    @router.post("/promo-codes/validate")
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

    @router.get("/add-ons/{property_id}")
    async def get_add_ons(property_id: str):
        """Public: Get add-on services for a property"""
        addons = await db.add_on_services.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(50)
        return addons

    @router.get("/add-ons")
    async def list_all_add_ons(property_id: str = "", current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        """Admin: List all add-ons"""
        q = {"property_id": property_id} if property_id else {}
        addons = await db.add_on_services.find(q, {"_id": 0}).to_list(200)
        return addons

    @router.post("/add-ons")
    async def create_add_on(data: AddOnServiceCreate, current_user: dict = Depends(require_perm("edit_bookings"))):
        """Admin: Create add-on service"""
        addon = AddOnService(**data.model_dump())
        doc = addon.model_dump()
        await db.add_on_services.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/add-ons/{addon_id}")
    async def delete_add_on(addon_id: str, current_user: dict = Depends(require_perm("delete_bookings", "edit_bookings", mode="any"))):
        """Admin: Delete add-on service"""
        await db.add_on_services.delete_one({"id": addon_id})
        return {"status": "deleted"}

    @router.put("/add-ons/{addon_id}/toggle")
    async def toggle_add_on(addon_id: str, current_user: dict = Depends(require_perm("edit_bookings"))):
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

    @router.get("/translations/{property_id}/{lang_code}")
    async def get_property_translations(property_id: str, lang_code: str):
        """Public: Get custom translation overrides for a property and language"""
        doc = await db.translation_overrides.find_one(
            {"property_id": property_id, "lang_code": lang_code}, {"_id": 0}
        )
        return doc or {"property_id": property_id, "lang_code": lang_code, "overrides": {}}

    @router.put("/translations/{property_id}/{lang_code}")
    async def save_property_translations(
        property_id: str, lang_code: str,
        overrides: Dict[str, str],
        current_user: dict = Depends(require_perm("edit_bookings"))
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

    @router.get("/translations/{property_id}")
    async def list_property_translations(property_id: str, current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        """Admin: List all translation overrides for a property"""
        docs = await db.translation_overrides.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        return docs

    @router.post("/translations/ai-translate")
    async def ai_translate_text(
        texts: Dict[str, str],
        target_lang: str,
        current_user: dict = Depends(require_perm("edit_bookings"))
    ):
        """Admin: AI-translate custom hotel texts to target language"""
        try:
            llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
            if not llm_key:
                raise HTTPException(status_code=500, detail="LLM key not configured")
            chat = LlmChat(api_key=llm_key, session_id=f"translate-{uuid.uuid4()}", system_message="You are a professional hotel content translator.").with_model("openai", "gpt-5.2")
            text_list = "\n".join([f"- {k}: {v}" for k, v in texts.items()])
            prompt = f"Translate the following hotel/booking texts to {target_lang}. Return ONLY a JSON object with the same keys and translated values. No explanation.\n\n{text_list}"
            response = await chat.send_message(UserMessage(text=prompt))
            import json
            try:
                translated = json.loads(response.strip().strip("```json").strip("```"))
            except Exception:
                translated = {}
            return {"translations": translated, "target_lang": target_lang}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

    # --- Upsell Items ---

    @router.get("/upsell-templates")
    async def get_upsell_templates():
        """Get predefined upsell templates for quick setup"""
        from models import UPSELL_TEMPLATES
        return UPSELL_TEMPLATES

    @router.get("/upsells/{property_id}")
    async def get_upsells(property_id: str):
        """Public: Get active upsell items for a property"""
        items = await db.upsell_items.find(
            {"property_id": property_id, "is_active": True}, {"_id": 0}
        ).sort("sort_order", 1).to_list(50)
        return items

    @router.get("/upsells/admin/{property_id}")
    async def get_all_upsells(property_id: str, current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        """Admin: Get all upsell items including inactive"""
        items = await db.upsell_items.find({"property_id": property_id}, {"_id": 0}).sort("sort_order", 1).to_list(50)
        return items

    @router.post("/upsells")
    async def create_upsell(data: UpsellItemCreate, current_user: dict = Depends(require_perm("edit_bookings"))):
        item = UpsellItem(**data.model_dump())
        doc = item.model_dump()
        await db.upsell_items.insert_one(doc)
        del doc["_id"]
        return doc

    @router.put("/upsells/{upsell_id}")
    async def update_upsell(upsell_id: str, updates: Dict, current_user: dict = Depends(require_perm("edit_bookings"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.upsell_items.update_one({"id": upsell_id}, {"$set": updates})
        doc = await db.upsell_items.find_one({"id": upsell_id}, {"_id": 0})
        return doc

    @router.delete("/upsells/{upsell_id}")
    async def delete_upsell(upsell_id: str, current_user: dict = Depends(require_perm("delete_bookings"))):
        await db.upsell_items.delete_one({"id": upsell_id})
        return {"status": "deleted"}

    @router.post("/upsells/seed/{property_id}")
    async def seed_upsells(property_id: str, current_user: dict = Depends(require_perm("edit_bookings"))):
        """Seed default upsell items from templates"""
        from models import UPSELL_TEMPLATES
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

    @router.get("/social-proof/{property_id}")
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

    @router.get("/social-proof/settings/{property_id}")
    async def get_social_proof_settings(property_id: str, current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        settings = await db.social_proof_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not settings:
            from models import SocialProofSettings
            settings = SocialProofSettings(property_id=property_id).model_dump()
        return settings

    @router.put("/social-proof/settings/{property_id}")
    async def update_social_proof_settings(property_id: str, updates: Dict, current_user: dict = Depends(require_perm("edit_bookings"))):
        updates.pop("_id", None)
        updates["property_id"] = property_id
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.social_proof_settings.update_one(
            {"property_id": property_id}, {"$set": updates}, upsert=True
        )
        doc = await db.social_proof_settings.find_one({"property_id": property_id}, {"_id": 0})
        return doc

    # --- Guest Review Collection ---

    @router.get("/review-collection/settings/{property_id}")
    async def get_review_collection_settings(property_id: str, current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        doc = await db.review_collection_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            from models import ReviewCollectionSettings
            doc = ReviewCollectionSettings(property_id=property_id).model_dump()
        return doc

    @router.put("/review-collection/settings/{property_id}")
    async def update_review_collection_settings(property_id: str, updates: Dict, current_user: dict = Depends(require_perm("edit_bookings"))):
        updates.pop("_id", None)
        updates["property_id"] = property_id
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.review_collection_settings.update_one({"property_id": property_id}, {"$set": updates}, upsert=True)
        return await db.review_collection_settings.find_one({"property_id": property_id}, {"_id": 0})

    @router.get("/review-collection/reviews/{property_id}")
    async def get_collected_reviews(property_id: str, status: str = "", current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        query = {"property_id": property_id, "source": "direct"}
        if status:
            query["status"] = status
        docs = await db.guest_reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    @router.post("/review-collection/submit")
    async def submit_guest_review(
        property_id: str, booking_ref: str, rating: int,
        title: str = "", review_text: str = "", guest_name: str = "", guest_email: str = ""
    ):
        """Public: Guest submits a review via the collection link"""
        booking = await db.bookings.find_one({"booking_ref": booking_ref, "property_id": property_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        # Check if already reviewed
        existing = await db.guest_reviews.find_one({"booking_ref": booking_ref}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="Review already submitted for this booking")
        from models import GuestReview
        review = GuestReview(
            property_id=property_id, booking_ref=booking_ref,
            guest_name=guest_name or booking.get("guest_name", ""),
            guest_email=guest_email or booking.get("guest_email", ""),
            rating=max(1, min(5, rating)), title=title, review_text=review_text,
            room_type=booking.get("room_type_id", ""),
            stay_dates=f"{booking.get('check_in', '')} to {booking.get('check_out', '')}",
        )
        doc = review.model_dump()
        await db.guest_reviews.insert_one(doc)
        doc.pop("_id", None)
        # Also add to main reviews collection for Review Hub
        hub_review = {
            "id": str(uuid.uuid4()), "property_id": property_id,
            "platform": "Direct", "guest_name": doc["guest_name"],
            "rating": doc["rating"], "review_text": doc["review_text"],
            "review_date": doc["created_at"], "response_status": "new",
            "sentiment": "positive" if doc["rating"] >= 4 else "neutral" if doc["rating"] >= 3 else "negative",
            "source": "guest_collection", "booking_ref": booking_ref,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.reviews.insert_one(hub_review)
        coupon = None
        if int(doc.get("rating") or 0) <= 2:
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "category": "guest_recovery", "priority": "high",
                "title": f"⚠️ Misafir kurtarma: {doc.get('rating')}★ yorum — {booking.get('guest_name') or doc.get('guest_name', '')}",
                "message": (f"{booking.get('booking_ref', '')} · {booking.get('room_type', '')} · çıkış {booking.get('check_out', '')} · "
                            f"\"{(doc.get('title') or '')[:60]}\" — {(doc.get('review_text') or '')[:180]} · Kupon gönderilmedi; misafirle iletişime geçin."),
                "property_id": booking.get("property_id", ""), "booking_id": booking.get("id"), "booking_ref": booking.get("booking_ref"),
                "guest_email": booking.get("guest_email", ""), "rating": doc.get("rating"), "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()})
            # Mevcut Service Recovery akışına vaka aç (Arandı/Çözüldü takibi orada)
            await db.guest_complaints.insert_one({
                "id": str(uuid.uuid4()), "property_id": booking.get("property_id", ""), "booking_id": booking.get("id", ""),
                "booking_ref": booking.get("booking_ref", ""), "guest_name": booking.get("guest_name") or doc.get("guest_name", ""),
                "guest_phone": booking.get("guest_phone", ""), "guest_email": booking.get("guest_email", ""),
                "room_number": "", "category": "review", "channel": "review",
                "text": f"{doc.get('rating')}★ yorum — {doc.get('title') or ''}: {doc.get('review_text') or ''}",
                "severity": "high" if int(doc.get("rating") or 0) <= 1 else "medium", "status": "open",
                "ai_summary": f"Konaklama sonrası {doc.get('rating')} yıldızlı yorum (otomatik açıldı)", "ai_action": "Misafiri arayın, özür + telafi teklifi",
                "ai_comp_pct": 0, "ai_reasoning": "", "ai_fallback": True, "compensation_amount": 0.0, "compensation_type": "",
                "resolution_notes": "", "resolved_at": "", "resolved_by": "", "created_by": "review-robot",
                "created_at": datetime.now(timezone.utc).isoformat()})
        else:
            coupon = await _issue_review_thanks_coupon(booking, doc)
        return {"status": "success", "message": "Thank you for your review!", "coupon": coupon}

    REVIEW_COUPON_PCT, REVIEW_COUPON_DAYS = 10, 365
    COUPON_T = {
        "en": ("A thank-you gift from {hotel}: {pct}% off your next stay", "Thank you for your review!",
               "As a small thank-you, here's {pct}% off your next direct booking. Use the code at checkout on our website.", "Valid until {until} · one use · direct bookings only", "Book your next stay"),
        "tr": ("{hotel} teşekkür hediyesi: sonraki konaklamanızda %{pct} indirim", "Yorumunuz için teşekkürler!",
               "Küçük bir teşekkür olarak bir sonraki direkt rezervasyonunuzda %{pct} indirim. Kodu web sitemizde ödeme adımında kullanın.", "{until} tarihine kadar geçerli · tek kullanım · yalnızca direkt rezervasyon", "Sonraki konaklamanızı planlayın"),
        "de": ("Ein Dankeschön von {hotel}: {pct}% Rabatt auf Ihren nächsten Aufenthalt", "Vielen Dank für Ihre Bewertung!",
               "Als kleines Dankeschön erhalten Sie {pct}% Rabatt auf Ihre nächste Direktbuchung. Code beim Checkout auf unserer Website eingeben.", "Gültig bis {until} · einmalig · nur Direktbuchungen", "Nächsten Aufenthalt buchen"),
    }

    async def _issue_review_thanks_coupon(booking: dict, review: dict) -> dict | None:
        """Reviewer reward: one-time 10% promo code (existing promo_codes infra) e-mailed in guest language."""
        email = (review.get("guest_email") or booking.get("guest_email") or "").strip()
        if not email:
            return None
        if await db.promo_codes.find_one({"source": "review_thanks", "booking_ref": booking.get("booking_ref")}, {"_id": 0, "code": 1}):
            return None
        from routes.platform_ext.mailer import send_email as _mail
        pid = booking.get("property_id", "")
        lang = (booking.get("guest_lang") or "en")[:2].lower()
        subj, title, body, valid, cta = COUPON_T.get(lang, COUPON_T["en"])
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        ts = await db.template_settings.find_one({"property_id": pid}, {"_id": 0, "hotel_name": 1}) or {}
        hotel = ts.get("hotel_name") or prop.get("name") or "Hotel"
        until = (datetime.now(timezone.utc) + timedelta(days=REVIEW_COUPON_DAYS)).date().isoformat()
        code = "THANKS" + uuid.uuid4().hex[:6].upper()
        await db.promo_codes.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "code": code, "kind": "percent", "amount": REVIEW_COUPON_PCT,
            "valid_from": datetime.now(timezone.utc).date().isoformat(), "valid_to": until, "max_uses": 1, "used": 0,
            "min_nights": 1, "applies_to_products": [], "active": True, "source": "review_thanks",
            "booking_ref": booking.get("booking_ref"), "guest_email": email, "review_rating": review.get("rating"),
            "created_at": datetime.now(timezone.utc).isoformat()})
        book_url = f"{_get_base_url()}/book/{pid}?coupon={code}&lang={lang}"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">
          <div style="background:#1a3c5e;color:#fff;padding:28px;text-align:center;"><h1 style="margin:0;font-size:22px;">🎁 {title}</h1></div>
          <div style="padding:28px;text-align:center;">
            <p style="font-size:15px;color:#475569;line-height:1.6;">{body.format(pct=REVIEW_COUPON_PCT)}</p>
            <div style="display:inline-block;background:#F5F7FA;border:2px dashed #1a3c5e;border-radius:10px;padding:14px 28px;margin:16px 0;font-size:26px;font-weight:800;letter-spacing:3px;color:#1a3c5e;">{code}</div>
            <p style="font-size:12px;color:#94a3b8;">{valid.format(until=until)}</p>
            <a href="{book_url}" style="display:inline-block;margin-top:12px;background:#2563eb;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:700;font-size:14px;">{cta}</a>
            <p style="margin-top:24px;font-size:12px;color:#666;"><strong>{hotel}</strong></p>
          </div>
        </div>"""
        status = await _mail(db, email, subj.format(hotel=hotel, pct=REVIEW_COUPON_PCT), html, kind="review_thanks_coupon",
                             meta={"booking_ref": booking.get("booking_ref"), "code": code, "lang": lang})
        return {"code": code, "pct": REVIEW_COUPON_PCT, "valid_to": until, "email_status": status}

    @router.get("/review-collection/page/{property_id}/{booking_ref}")
    async def get_review_page_data(property_id: str, booking_ref: str):
        """Public: Get data for review collection page"""
        booking = await db.bookings.find_one({"booking_ref": booking_ref, "property_id": property_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        existing = await db.guest_reviews.find_one({"booking_ref": booking_ref}, {"_id": 0})
        return {
            "booking": {"booking_ref": booking["booking_ref"], "guest_name": booking["guest_name"], "check_in": booking["check_in"], "check_out": booking["check_out"]},
            "property": {"name": ts.get("hotel_name") or (prop or {}).get("name", "Hotel"), "id": property_id},
            "already_reviewed": existing is not None,
        }

    # --- Self Check-In ---

    @router.get("/checkin/settings/{property_id}")
    async def get_checkin_settings(property_id: str, current_user: dict = Depends(require_perm("checkin_bookings", "edit_bookings", mode="any"))):
        doc = await db.checkin_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            from models import CheckInSettings
            doc = CheckInSettings(property_id=property_id).model_dump()
        return doc

    @router.put("/checkin/settings/{property_id}")
    async def update_checkin_settings(property_id: str, updates: Dict, current_user: dict = Depends(require_perm("edit_bookings"))):
        updates.pop("_id", None)
        updates["property_id"] = property_id
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.checkin_settings.update_one({"property_id": property_id}, {"$set": updates}, upsert=True)
        return await db.checkin_settings.find_one({"property_id": property_id}, {"_id": 0})

    @router.get("/checkin/status/{booking_ref}")
    async def get_checkin_status(booking_ref: str):
        """Public: Get check-in status for a booking"""
        doc = await db.guest_checkins.find_one({"booking_ref": booking_ref}, {"_id": 0})
        if not doc:
            booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
            if not booking:
                raise HTTPException(status_code=404, detail="Booking not found")
            return {"booking_ref": booking_ref, "status": "not_started"}
        return doc

    @router.post("/checkin/start/{booking_ref}")
    async def start_checkin(booking_ref: str):
        """Public: Initialize or get check-in for a booking"""
        booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        existing = await db.guest_checkins.find_one({"booking_ref": booking_ref}, {"_id": 0})
        if existing:
            return existing
        from models import GuestCheckIn
        checkin = GuestCheckIn(
            booking_ref=booking_ref, property_id=booking["property_id"],
            guest_name=booking["guest_name"], guest_email=booking["guest_email"],
        )
        doc = checkin.model_dump()
        await db.guest_checkins.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.post("/checkin/complete/{booking_ref}")
    async def complete_checkin(booking_ref: str, terms_accepted: bool = True, special_notes: str = ""):
        """Public: Complete the check-in process"""
        checkin = await db.guest_checkins.find_one({"booking_ref": booking_ref})
        if not checkin:
            raise HTTPException(status_code=404, detail="Check-in not found. Please start check-in first.")
        await db.guest_checkins.update_one(
            {"booking_ref": booking_ref},
            {"$set": {
                "status": "completed", "terms_accepted": terms_accepted,
                "special_notes": special_notes,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        await db.bookings.update_one({"booking_ref": booking_ref}, {"$set": {"checkin_status": "completed"}})
        doc = await db.guest_checkins.find_one({"booking_ref": booking_ref}, {"_id": 0})
        return doc

    @router.get("/checkin/admin/{property_id}")
    async def admin_list_checkins(property_id: str, current_user: dict = Depends(require_perm("view_bookings", "checkin_bookings", mode="any"))):
        docs = await db.guest_checkins.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.put("/checkin/assign-room/{booking_ref}")
    async def assign_room(booking_ref: str, room_assignment: str, current_user: dict = Depends(require_perm("assign_rooms", "checkin_bookings", mode="any"))):
        await db.guest_checkins.update_one({"booking_ref": booking_ref}, {"$set": {"room_assignment": room_assignment}})
        doc = await db.guest_checkins.find_one({"booking_ref": booking_ref}, {"_id": 0})
        return doc

    # --- Guest Portal ---

    @router.post("/guest-portal/request-access")
    async def request_guest_portal_access(guest_email: str):
        """Public: Send magic link to guest's email"""
        bookings = await db.bookings.find({"guest_email": guest_email}, {"_id": 0}).to_list(1)
        if not bookings:
            return {"status": "sent"}  # Don't reveal if email exists
        from models import GuestPortalSession
        session = GuestPortalSession(guest_email=guest_email)
        doc = session.model_dump()
        await db.guest_portal_sessions.insert_one(doc)
        doc.pop("_id", None)
        # Send portal email with magic link
        asyncio.create_task(_send_guest_portal_email(guest_email, doc["magic_token"]))
        return {"status": "sent", "message": "Check your email for the access link", "token": doc["magic_token"]}

    @router.post("/guest-portal/verify")
    async def verify_guest_portal(token: str):
        """Public: Verify magic link token"""
        session = await db.guest_portal_sessions.find_one({"magic_token": token}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=401, detail="Invalid or expired link")
        if datetime.fromisoformat(session["expires_at"]) < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Link has expired. Please request a new one.")
        return {"status": "verified", "guest_email": session["guest_email"]}

    @router.get("/guest-portal/bookings")
    async def get_guest_bookings(token: str):
        """Public: Get all bookings for a verified guest"""
        session = await db.guest_portal_sessions.find_one({"magic_token": token}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session")
        if datetime.fromisoformat(session["expires_at"]) < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired")
        bookings = await db.bookings.find({"guest_email": session["guest_email"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
        # Enrich with room names
        for b in bookings:
            room = await db.room_types.find_one({"id": b.get("room_type_id")}, {"_id": 0, "name": 1, "photos": 1})
            b["room_name"] = room.get("name", "Room") if room else "Room"
            b["room_photo"] = (room.get("photos") or [""])[0] if room else ""
            prop = await db.properties.find_one({"id": b.get("property_id")}, {"_id": 0, "name": 1})
            b["property_name"] = prop.get("name", "") if prop else ""
        return bookings

    @router.post("/guest-portal/rebook")
    async def rebook_from_portal(token: str, booking_ref: str):
        """Public: Get rebooking data from a previous booking"""
        session = await db.guest_portal_sessions.find_one({"magic_token": token}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session")
        booking = await db.bookings.find_one({"booking_ref": booking_ref, "guest_email": session["guest_email"]}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        return {
            "property_id": booking["property_id"],
            "room_type_id": booking.get("room_type_id"),
            "adults": booking.get("adults", 2),
            "children": booking.get("children", 0),
            "guest_name": booking.get("guest_name", ""),
            "guest_email": booking.get("guest_email", ""),
            "guest_phone": booking.get("guest_phone", ""),
        }

    # --- Cart Abandonment Recovery ---

    @router.post("/cart/save")
    async def save_abandoned_cart(
        property_id: str, room_type_id: str = "", room_name: str = "",
        guest_email: str = "", guest_name: str = "",
        check_in: str = "", check_out: str = "", adults: int = 2, total_price: float = 0
    ):
        """Public: Save cart state when guest starts but doesn't complete booking"""
        if not guest_email:
            return {"status": "skipped", "message": "No email provided"}
        from models import AbandonedCart
        cart = AbandonedCart(
            property_id=property_id, guest_email=guest_email, guest_name=guest_name,
            room_type_id=room_type_id, room_name=room_name,
            check_in=check_in, check_out=check_out, adults=adults, total_price=total_price,
        )
        doc = cart.model_dump()
        await db.abandoned_carts.insert_one(doc)
        doc.pop("_id", None)
        return {"status": "saved", "recovery_token": doc["recovery_token"]}

    @router.get("/cart/recover/{token}")
    async def recover_cart(token: str):
        """Public: Recover an abandoned cart via email link"""
        cart = await db.abandoned_carts.find_one({"recovery_token": token, "status": {"$in": ["abandoned", "email_sent"]}}, {"_id": 0})
        if not cart:
            raise HTTPException(status_code=404, detail="Cart not found or already recovered")
        await db.abandoned_carts.update_one({"recovery_token": token}, {"$set": {"status": "recovered", "recovered_at": datetime.now(timezone.utc).isoformat()}})
        return cart

    @router.get("/cart/abandoned/{property_id}")
    async def list_abandoned_carts(property_id: str, current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        carts = await db.abandoned_carts.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return carts

    @router.get("/cart/stats/{property_id}")
    async def cart_abandonment_stats(property_id: str, current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        total = await db.abandoned_carts.count_documents({"property_id": property_id})
        recovered = await db.abandoned_carts.count_documents({"property_id": property_id, "status": "recovered"})
        email_sent = await db.abandoned_carts.count_documents({"property_id": property_id, "status": "email_sent"})
        return {"total_abandoned": total, "recovered": recovered, "email_sent": email_sent, "recovery_rate": round(recovered / total * 100, 1) if total > 0 else 0}

    @router.post("/cart/send-recovery-emails/{property_id}")
    async def send_cart_recovery_emails(property_id: str, current_user: dict = Depends(require_perm("edit_bookings"))):
        """Admin: Send recovery emails to all abandoned carts that haven't been emailed yet"""
        # Find carts older than 1 hour that haven't been emailed
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        carts = await db.abandoned_carts.find({
            "property_id": property_id, "status": "abandoned",
            "guest_email": {"$ne": ""}, "created_at": {"$lte": cutoff}
        }, {"_id": 0}).to_list(50)
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        prop_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")
        sent = 0
        for cart in carts:
            asyncio.create_task(_send_cart_recovery_email(cart, prop_name))
            sent += 1
        return {"sent": sent, "message": f"Sending recovery emails to {sent} guests"}

    @router.post("/review-collection/send/{property_id}")
    async def send_review_collection_emails(property_id: str, current_user: dict = Depends(require_perm("edit_bookings"))):
        """Admin: Send review collection emails to guests who checked out but haven't been emailed"""
        res = await run_review_requests_internal(property_id)
        return {**res, "sent": res["sent"] + res["mocked"], "message": f"{res['candidates']} misafir · {res['sent']} gönderildi · {res['mocked']} MOCK · {res['skipped_reviewed']} zaten yorum yapmış"}

    # --- Multi-Currency ---

    @router.get("/currencies")
    async def get_supported_currencies():
        from models import CURRENCY_CONFIG
        return CURRENCY_CONFIG

    @router.get("/currency/convert")
    async def convert_currency(amount: float, from_currency: str = "GBP", to_currency: str = "USD"):
        """Public: Convert price between currencies (approximate rates)"""
        # Approximate exchange rates from GBP (updated periodically in production)
        rates_from_gbp = {
            "GBP": 1.0, "USD": 1.27, "EUR": 1.17, "AED": 4.67, "SAR": 4.76,
            "JPY": 192.5, "CNY": 9.21, "KRW": 1750, "INR": 106.5, "BRL": 7.35,
            "RUB": 118.0, "AUD": 1.95, "CAD": 1.73, "CHF": 1.12, "SGD": 1.71,
            "THB": 44.2, "MYR": 5.65, "TRY": 41.5,
        }
        if from_currency not in rates_from_gbp or to_currency not in rates_from_gbp:
            raise HTTPException(status_code=400, detail="Unsupported currency")
        gbp_amount = amount / rates_from_gbp[from_currency]
        converted = gbp_amount * rates_from_gbp[to_currency]
        return {"original": amount, "from": from_currency, "to": to_currency, "converted": round(converted, 2), "rate": round(rates_from_gbp[to_currency] / rates_from_gbp[from_currency], 4)}

    # --- Group Bookings ---

    @router.post("/group-booking/request")
    async def submit_group_booking(data: GroupBookingRequest):
        """Public: Submit a group/corporate booking request"""
        group = GroupBooking(**data.model_dump())
        doc = group.model_dump()
        await db.group_bookings.insert_one(doc)
        doc.pop("_id", None)
        return {"status": "submitted", "id": doc["id"], "message": "Your group booking request has been submitted. Our team will contact you within 24 hours."}

    @router.get("/group-booking/requests/{property_id}")
    async def list_group_bookings(property_id: str, current_user: dict = Depends(require_perm("view_group_blocks", "view_bookings", mode="any"))):
        docs = await db.group_bookings.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.put("/group-booking/{booking_id}")
    async def update_group_booking(booking_id: str, updates: Dict, current_user: dict = Depends(require_perm("edit_group_blocks", "edit_bookings", mode="any"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.group_bookings.update_one({"id": booking_id}, {"$set": updates})
        doc = await db.group_bookings.find_one({"id": booking_id}, {"_id": 0})
        return doc

    # --- Hourly / Space Booking ---

    @router.get("/spaces/templates")
    async def get_space_templates():
        from models import SPACE_TYPES
        return SPACE_TYPES

    @router.get("/spaces/public/{property_id}")
    async def get_property_spaces(property_id: str):
        """Public: Get available spaces for a property (hourly rental templates)"""
        spaces = await db.property_spaces.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(50)
        return spaces

    @router.post("/spaces")
    async def create_space(data: Dict, current_user: dict = Depends(require_perm("edit_bookings"))):
        from models import PropertySpace
        space = PropertySpace(**data)
        doc = space.model_dump()
        await db.property_spaces.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/spaces/{space_id}")
    async def update_space(space_id: str, updates: Dict, current_user: dict = Depends(require_perm("edit_bookings"))):
        updates.pop("_id", None); updates.pop("id", None)
        await db.property_spaces.update_one({"id": space_id}, {"$set": updates})
        return await db.property_spaces.find_one({"id": space_id}, {"_id": 0})

    @router.delete("/spaces/{space_id}")
    async def delete_space(space_id: str, current_user: dict = Depends(require_perm("delete_bookings"))):
        await db.property_spaces.delete_one({"id": space_id})
        return {"status": "deleted"}

    @router.post("/spaces/seed/{property_id}")
    async def seed_spaces(property_id: str, current_user: dict = Depends(require_perm("edit_bookings"))):
        from models import SPACE_TYPES, PropertySpace
        existing = await db.property_spaces.count_documents({"property_id": property_id})
        if existing > 0:
            return {"message": f"Already has {existing} spaces", "count": existing}
        items = []
        for t in SPACE_TYPES:
            space = PropertySpace(property_id=property_id, name=t["name"], category=t["category"], hourly_rate=t["hourly_rate"], capacity=t["capacity"], icon=t["icon"])
            doc = space.model_dump()
            items.append(doc)
        if items:
            await db.property_spaces.insert_many(items)
            for i in items: i.pop("_id", None)
        return {"message": f"Seeded {len(items)} spaces", "items": items}

    @router.post("/spaces/book")
    async def book_space(
        property_id: str, space_id: str, guest_name: str, guest_email: str,
        booking_date: str, start_time: str, end_time: str,
        guest_phone: str = "", notes: str = ""
    ):
        """Public: Book a space/room by the hour"""
        space = await db.property_spaces.find_one({"id": space_id, "property_id": property_id}, {"_id": 0})
        if not space:
            raise HTTPException(status_code=404, detail="Space not found")
        # Calculate hours
        try:
            sh, sm = map(int, start_time.split(":"))
            eh, em = map(int, end_time.split(":"))
            hours = (eh * 60 + em - sh * 60 - sm) / 60
            if hours <= 0:
                raise HTTPException(status_code=400, detail="End time must be after start time")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")
        total_price = round(space["hourly_rate"] * hours, 2)
        # Check for half/full day rates
        if hours >= 8 and space.get("full_day_rate", 0) > 0:
            total_price = space["full_day_rate"]
        elif hours >= 4 and space.get("half_day_rate", 0) > 0:
            total_price = space["half_day_rate"]
        from models import SpaceBooking
        booking = SpaceBooking(
            property_id=property_id, space_id=space_id, space_name=space["name"],
            guest_name=guest_name, guest_email=guest_email, guest_phone=guest_phone,
            booking_date=booking_date, start_time=start_time, end_time=end_time,
            hours=hours, total_price=total_price, notes=notes,
        )
        doc = booking.model_dump()
        await db.space_bookings.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/spaces/bookings/{property_id}")
    async def list_space_bookings(property_id: str, date: str = "", current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        query = {"property_id": property_id}
        if date:
            query["booking_date"] = date
        docs = await db.space_bookings.find(query, {"_id": 0}).sort("booking_date", -1).to_list(200)
        return docs

    # --- AI Concierge Chat ---

    @router.post("/concierge/chat")
    async def concierge_chat(property_id: str, message: str, session_id: str = ""):
        """Public: AI concierge answers guest questions about the property"""
        # Gather property context
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        policies = await db.hotel_policies.find_one({"property_id": property_id}, {"_id": 0}) or {}
        facilities = await db.property_facilities.find_one({"property_id": property_id}, {"_id": 0})
        rooms = await db.room_types.find({"property_id": property_id}, {"_id": 0, "name": 1, "base_price": 1, "max_guests": 1, "amenities": 1}).to_list(10)
        spaces = await db.property_spaces.find({"property_id": property_id, "is_active": True}, {"_id": 0, "name": 1, "hourly_rate": 1, "capacity": 1}).to_list(10)

        prop_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")
        fac_list = (facilities or {}).get("selected_facilities", [])

        context = f"""You are a friendly, multilingual concierge for {prop_name}. 
    IMPORTANT: Detect the guest's language automatically and ALWAYS respond in the SAME language they use. You support 130+ languages natively.
    If the guest writes in Spanish, reply in Spanish. If they write in Arabic, reply in Arabic. If Chinese, reply in Chinese. And so on for any language.
    
    Answer questions helpfully and concisely.
    Property info:
    - Name: {prop_name}
    - Address: {ts.get('address', (prop or {}).get('city', 'London'))}
    - Contact: {ts.get('contact_phone', '')} / {ts.get('contact_email', '')}
    - Check-in: {policies.get('check_in_from', '15:00')} - {policies.get('check_in_until', '22:00')}
    - Check-out: {policies.get('check_out_from', '07:00')} - {policies.get('check_out_until', '11:00')}
    - Cancellation: {policies.get('cancellation_policy', 'flexible')}
    - Children: {policies.get('children_policy', 'Welcome')}
    - Pets: {policies.get('pet_policy', 'Not allowed')}
    - Facilities: {', '.join(fac_list[:15]) if fac_list else 'Standard hotel facilities'}
    - Rooms: {'; '.join([f"{r['name']} (£{r['base_price']}/night, {r['max_guests']} guests)" for r in rooms[:5]])}
    - Spaces/Meeting Rooms: {'; '.join([f"{s['name']} (£{s['hourly_rate']}/hr, {s['capacity']} people)" for s in spaces]) if spaces else 'None available'}
    - House rules: {', '.join(policies.get('house_rules', [])[:5]) if policies.get('house_rules') else 'Standard'}

    Answer naturally in the guest's language, recommending bookings when appropriate. Keep responses under 150 words."""

        # Get conversation history if session exists
        history = []
        if session_id:
            hist_docs = await db.concierge_chats.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(10)
            for h in hist_docs:
                history.append({"role": h["role"], "content": h["content"]})

        try:
            llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
            if not llm_key:
                raise HTTPException(status_code=500, detail="AI not configured")
            # Build initial_messages from history
            initial_msgs = [{"role": "system", "content": context}]
            for h in history[-6:]:
                initial_msgs.append({"role": h["role"], "content": h["content"]})
            chat = LlmChat(api_key=llm_key, session_id=session_id or "new", system_message=context, initial_messages=initial_msgs)
            chat = chat.with_model("openai", "gpt-5.2")
            reply = await chat.send_message(UserMessage(text=message))
        except Exception as e:
            logger.error(f"Concierge chat error: {e}")
            reply = f"I apologize, I'm having trouble connecting right now. Please contact us directly at {ts.get('contact_phone', '')} or {ts.get('contact_email', '')} for assistance."

        # Generate session_id if not provided
        if not session_id:
            session_id = str(uuid.uuid4())

        # Save both messages
        await db.concierge_chats.insert_one({"session_id": session_id, "property_id": property_id, "role": "user", "content": message, "created_at": datetime.now(timezone.utc).isoformat()})
        await db.concierge_chats.insert_one({"session_id": session_id, "property_id": property_id, "role": "assistant", "content": reply, "created_at": datetime.now(timezone.utc).isoformat()})

        return {"reply": reply, "session_id": session_id}


    # --- Template Settings ---

    @router.get("/template-settings/{property_id}")
    async def get_template_settings(property_id: str):
        """Public endpoint: Get template customization settings for a property"""
        settings = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0})
        return settings or {"property_id": property_id, "template_id": "booking-classic"}

    @router.get("/template-settings")
    async def list_all_template_settings(current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        """Admin: List all template settings"""
        settings = await db.template_settings.find({}, {"_id": 0}).to_list(100)
        return settings

    @router.put("/template-settings/{property_id}")
    async def save_template_settings(property_id: str, update: TemplateSettingsUpdate, current_user: dict = Depends(require_perm("edit_bookings"))):
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

    @router.delete("/template-settings/{property_id}")
    async def delete_template_settings(property_id: str, current_user: dict = Depends(require_perm("delete_bookings"))):
        """Admin: Reset template settings for a property"""
        await db.template_settings.delete_one({"property_id": property_id})
        return {"status": "deleted"}

    @router.get("/booking/property/{property_id}")
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

    @router.get("/booking/rooms/{property_id}")
    async def get_booking_rooms(property_id: str, check_in: str = "", check_out: str = "", adults: int = 2, children: int = 0):
        """Public endpoint: Get available room types for a property"""
        rooms = await db.room_types.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(50)

        if check_in and check_out:
            # Check availability for each room type
            for room in rooms:
                bookings_count = await db.bookings.count_documents({
                    "room_type_id": room["id"],
                    "status": {"$nin": ["cancelled"]},
                    "day_use": {"$ne": True},
                    "$or": [
                        {"check_in": {"$lt": check_out}, "check_out": {"$gt": check_in}}
                    ]
                })
                room["available_rooms"] = max(0, room.get("total_rooms", 1) - bookings_count)
                room["is_available"] = room["available_rooms"] > 0
            # Tek fiyat motoru: RMS dinamik gecelik fiyat + LOS kısıtı + fiyat açıklaması (widget ile aynı)
            try:
                from routes.pms.widget_pricing import nightly_rates, explain_price, check_los_restrictions
                los = await check_los_restrictions(db, property_id, check_in, check_out)
                prop_tax = await db.properties.find_one({"id": property_id}, {"_id": 0, "vat_rate": 1, "city_tax_per_night": 1, "child_policy": 1, "extra_bed_price": 1}) or {}
                for room in rooms:
                    nightly = await nightly_rates(db, property_id, room, check_in, check_out)
                    room["nightly"] = nightly
                    room["stay_total"] = round(sum(n["rate"] for n in nightly), 2)
                    room["avg_nightly"] = round(room["stay_total"] / max(1, len(nightly)), 2)
                    room["price_explanation"] = explain_price(nightly)
                    if los:
                        room["los_block"] = los
                        room["is_available"] = False
                    room["vat_rate"] = prop_tax.get("vat_rate")
                    room["city_tax_per_night"] = prop_tax.get("city_tax_per_night")
                    room["extra_bed_price"] = room.get("extra_bed_price") or prop_tax.get("extra_bed_price")
                    room["child_policy"] = prop_tax.get("child_policy")
            except Exception as _e:
                logger.warning(f"pricing unify failed: {_e}")
        else:
            for room in rooms:
                room["available_rooms"] = room.get("total_rooms", 1)
                room["is_available"] = True

        return rooms

    @router.get("/booking/availability/{property_id}")
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

    @router.get("/booking/damage-waiver/{property_id}")
    async def public_damage_waiver(property_id: str):
        """Public: booking engine'in hasar koruması teklifini gösterebilmesi için."""
        cfg = await db.damage_protection_config.find_one(
            {"property_id": property_id, "enabled": True}, {"_id": 0})
        if not cfg:
            return {"enabled": False}
        return {"enabled": True, "fee_per_night": float(cfg.get("fee_per_night", 0) or 0),
                "coverage_limit": float(cfg.get("coverage_limit", 0) or 0),
                "currency": cfg.get("currency", "GBP")}

    @router.post("/booking/reserve")
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

        # Calculate price using owner-locked override if present, else room base.
        # This is the PMS link from the My Rates panel.
        try:
            ci = datetime.fromisoformat(booking_data.check_in)
            co = datetime.fromisoformat(booking_data.check_out)
            nights = max(1, (co - ci).days)
        except ValueError:
            nights = 1

        base_price = room.get("base_price", 0)
        rt_id = booking_data.room_type_id or ""
        nightly_total = 0.0
        for n in range(nights):
            d_iso = (ci + timedelta(days=n)).strftime("%Y-%m-%d")
            # 1) Room-type specific owner override
            ov = await db.rate_overrides.find_one(
                {"property_id": booking_data.property_id, "date": d_iso,
                 "set_by": "owner-override", "room_type_id": rt_id},
                {"_id": 0, "custom_rate": 1}
            )
            # 2) Fall back to property-wide owner override
            if not ov or not ov.get("custom_rate"):
                ov = await db.rate_overrides.find_one(
                    {"property_id": booking_data.property_id, "date": d_iso,
                     "set_by": "owner-override", "room_type_id": ""},
                    {"_id": 0, "custom_rate": 1}
                )
            night_rate = float(ov["custom_rate"]) if ov and ov.get("custom_rate") else base_price
            nightly_total += night_rate
        total_price = nightly_total * booking_data.rooms

        # Optional damage waiver fee (guest opted in on the booking engine)
        damage_waiver_fee = 0.0
        if booking_data.damage_waiver:
            dw_cfg = await db.damage_protection_config.find_one(
                {"property_id": booking_data.property_id, "enabled": True}, {"_id": 0})
            if dw_cfg:
                damage_waiver_fee = round(
                    float(dw_cfg.get("fee_per_night", 0) or 0) * nights * booking_data.rooms, 2)
                total_price += damage_waiver_fee

        # Pull native currency from property (source of truth) with fallbacks
        prop_doc = await db.properties.find_one(
            {"id": booking_data.property_id}, {"_id": 0, "currency": 1}
        )
        booking_currency = (
            (prop_doc or {}).get("currency")
            or room.get("currency")
            or "GBP"
        )

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
            currency=booking_currency,
            special_requests=booking_data.special_requests,
            status="confirmed",
            payment_status="pending"
        )

        doc = booking.model_dump()
        if damage_waiver_fee > 0:
            doc["damage_waiver"] = True
            doc["damage_waiver_fee"] = damage_waiver_fee
        await db.bookings.insert_one(doc)
        doc.pop("_id", None)

        # Fire automation rules (Flexkeeping-style event dispatcher)
        try:
            from routes.automation_rules import fire_event
            asyncio.create_task(fire_event(db, "booking_created", {
                "property_id": doc.get("property_id"),
                "booking_ref": doc.get("booking_ref"),
                "guest_name": doc.get("guest_name", ""),
                "guest_email": doc.get("guest_email", ""),
                "room_number": room.get("name", ""),
                "tags": doc.get("tags", []),
                "nights": doc.get("nights", 1),
                "total_price": doc.get("total_price", 0),
                "source": doc.get("source", "direct"),
            }))
        except Exception:
            pass

        # Send confirmation email in background
        prop_doc = await db.properties.find_one({"id": booking_data.property_id}, {"_id": 0})
        prop_name_for_email = prop_doc.get("name", "Hotel") if prop_doc else "Hotel"
        asyncio.create_task(_send_booking_confirmation(doc, room.get("name", "Room")))
        # Send check-in email in background
        asyncio.create_task(_send_checkin_email(doc, prop_name_for_email))

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
        asyncio.create_task(fire_webhooks(db, "booking.created", webhook_data))
        await log_sync(db, "booking-engine", "outbound", "success", f"Booking {doc.get('booking_ref')} created — webhook fired", doc.get("booking_ref", ""))

        # Cross-module: auto-update guest profile
        guest_email = doc.get("guest_email", "")
        guest_phone = doc.get("guest_phone", "")
        guest_name = doc.get("guest_name", "")
        if guest_email or guest_phone:
            profile_query = {"email": guest_email} if guest_email else {"phone": guest_phone}
            existing_profile = await db.guest_profiles.find_one(profile_query, {"_id": 0, "id": 1})
            if existing_profile:
                await db.guest_profiles.update_one(
                    {"id": existing_profile["id"]},
                    {"$inc": {"total_stays": 1, "total_spend": doc.get("total_price", 0) or 0},
                     "$set": {"last_stay": doc.get("check_in", ""), "updated_at": datetime.now(timezone.utc).isoformat()},
                     "$addToSet": {"properties": doc.get("property_id", "")}}
                )
            elif guest_name:
                from models import GuestProfile
                profile = GuestProfile(
                    name=guest_name, email=guest_email, phone=guest_phone,
                    total_stays=1, total_spend=doc.get("total_price", 0) or 0,
                    first_stay=doc.get("check_in", ""), last_stay=doc.get("check_in", ""),
                    source="booking-engine",
                )
                pd = profile.model_dump()
                pd["properties"] = [doc.get("property_id", "")]
                await db.guest_profiles.insert_one(pd)

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

    # Get base URL for email links
    def _get_base_url():
        return os.environ.get("BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com"))

    REVIEW_T = {
        "en": ("How was your stay at {hotel}?", "How was your stay?", "Hi {name},",
               "Thank you for staying with us ({ci} — {co}). We'd love to hear about your experience — your feedback helps us improve and helps other travellers.",
               "Leave a Review", "It only takes 2 minutes"),
        "tr": ("{hotel} konaklamanız nasıldı?", "Konaklamanız nasıldı?", "Merhaba {name},",
               "Bizi tercih ettiğiniz için teşekkürler ({ci} — {co}). Deneyiminizi duymak isteriz — geri bildiriminiz hem bize hem diğer misafirlere yardımcı olur.",
               "Yorum Bırak", "Sadece 2 dakikanızı alır"),
        "de": ("Wie war Ihr Aufenthalt im {hotel}?", "Wie war Ihr Aufenthalt?", "Hallo {name},",
               "Vielen Dank für Ihren Aufenthalt bei uns ({ci} — {co}). Wir würden uns über Ihr Feedback freuen — es hilft uns und anderen Reisenden.",
               "Bewertung abgeben", "Dauert nur 2 Minuten"),
    }

    async def _send_review_collection_email(booking: dict, property_name: str) -> str:
        """Post-stay review request in the guest's language (TR/EN/DE) via mailer (Resend or MOCK)."""
        from routes.platform_ext.mailer import send_email as _mail
        lang = (booking.get("guest_lang") or "en")[:2].lower()
        subj, title, hi, body, cta, hint = REVIEW_T.get(lang, REVIEW_T["en"])
        base_url = _get_base_url()
        review_link = f"{base_url}/review?property={booking.get('property_id','')}&ref={booking.get('booking_ref','')}&lang={lang}"
        ci, co = booking.get("check_in", ""), booking.get("check_out", "")
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">
          <div style="background:linear-gradient(135deg,#1e293b,#334155);color:#fff;padding:32px;text-align:center;">
            <h1 style="margin:0;font-size:24px;">{title}</h1>
            <p style="margin:8px 0 0;opacity:0.7;font-size:14px;">{property_name}</p>
          </div>
          <div style="padding:32px;">
            <p style="font-size:15px;color:#475569;line-height:1.6;">{hi.format(name=booking.get('guest_name',''))}</p>
            <p style="font-size:15px;color:#475569;line-height:1.6;">{body.format(ci=ci, co=co)}</p>
            <div style="text-align:center;margin:28px 0;">
              <a href="{review_link}" style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px;">{cta}</a>
            </div>
            <p style="font-size:13px;color:#94a3b8;text-align:center;">{hint}</p>
          </div>
        </div>"""
        status = await _mail(db, booking.get("guest_email", ""), subj.format(hotel=property_name), html, kind="review_request",
                             meta={"booking_id": booking.get("id"), "booking_ref": booking.get("booking_ref"), "lang": lang})
        # WhatsApp kanalı (Twilio, anahtar yoksa MOCK/queued) — nötr metin, puan istenmez, herkese gider (gating yok)
        wa_status = "no_phone"
        phone = (booking.get("guest_phone") or "").strip()
        if phone:
            WA_T = {"en": "Hi {name}, thank you for staying at {hotel}. If you have a moment, we'd love to hear about your experience: {link}",
                    "tr": "Merhaba {name}, {hotel} tercihiniz için teşekkürler. Vaktiniz olursa deneyiminizi bizimle paylaşır mısınız? {link}",
                    "de": "Hallo {name}, vielen Dank für Ihren Aufenthalt im {hotel}. Wir würden uns freuen, von Ihrer Erfahrung zu hören: {link}"}
            try:
                from routes.marketing.whatsapp_voice import _send_whatsapp_reply
                to = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone if phone.startswith('+') else '+' + phone}"
                r = await _send_whatsapp_reply(to, WA_T.get(lang, WA_T["en"]).format(name=booking.get("guest_name", ""), hotel=property_name, link=review_link))
                wa_status = r.get("status", "queued")
            except Exception as e:
                wa_status = f"error:{str(e)[:60]}"
            await db.review_request_log.insert_one({"id": str(uuid.uuid4()), "booking_id": booking.get("id"), "channel": "whatsapp",
                                                    "status": wa_status, "lang": lang, "created_at": datetime.now(timezone.utc).isoformat()})
        await db.bookings.update_one({"id": booking.get("id")}, {"$set": {
            "review_request_sent_at": datetime.now(timezone.utc).isoformat(), "review_request_status": status, "review_request_lang": lang,
            "review_request_whatsapp": wa_status}})
        return status

    async def run_review_requests_internal(property_id: str) -> dict:
        """Robot: guests who checked out yesterday (or earlier, max 7 days) and were never asked → review e-mail."""
        today = datetime.now(timezone.utc).date()
        q = {"check_out": {"$lte": (today - timedelta(days=1)).isoformat(), "$gte": (today - timedelta(days=7)).isoformat()},
             "status": {"$in": ["checked_out", "confirmed", "completed"]}, "guest_email": {"$nin": [None, ""]},
             "review_request_sent_at": {"$exists": False}}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        bks = await db.bookings.find(q, {"_id": 0}).to_list(500)
        names: dict = {}
        sent = mocked = skipped = 0
        for b in bks:
            if await db.guest_reviews.find_one({"booking_ref": b.get("booking_ref")}, {"_id": 0, "id": 1}):
                await db.bookings.update_one({"id": b["id"]}, {"$set": {"review_request_sent_at": "skipped_already_reviewed"}})
                skipped += 1
                continue
            pid = b.get("property_id", "")
            if pid not in names:
                prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
                ts = await db.template_settings.find_one({"property_id": pid}, {"_id": 0, "hotel_name": 1}) or {}
                names[pid] = ts.get("hotel_name") or prop.get("name") or "Hotel"
            st = await _send_review_collection_email(b, names[pid])
            sent += st == "sent"
            mocked += st == "mocked"
        return {"ok": True, "candidates": len(bks), "sent": sent, "mocked": mocked, "skipped_reviewed": skipped}

    router.run_review_requests_internal = run_review_requests_internal

    REMIND_T = {
        "en": ("Reminder: your {pct}% thank-you code expires on {until}", "Your {pct}% code is still waiting", "Use code {code} on your next direct booking before {until}.", "Book now"),
        "tr": ("Hatırlatma: %{pct} teşekkür kodunuz {until} tarihinde sona eriyor", "%{pct} kodunuz sizi bekliyor", "{code} kodunu {until} tarihinden önce bir sonraki direkt rezervasyonunuzda kullanın.", "Hemen rezervasyon yap"),
        "de": ("Erinnerung: Ihr {pct}%-Dankeschön-Code läuft am {until} ab", "Ihr {pct}%-Code wartet noch", "Nutzen Sie den Code {code} vor dem {until} für Ihre nächste Direktbuchung.", "Jetzt buchen"),
    }

    async def run_coupon_reminders_internal(property_id: str) -> dict:
        """Unused THANKS codes expiring in ≤30 days → one reminder e-mail in guest language."""
        from routes.platform_ext.mailer import send_email as _mail
        today = datetime.now(timezone.utc).date()
        q = {"source": "review_thanks", "used": 0, "active": True, "reminder_sent_at": {"$exists": False},
             "valid_to": {"$gte": today.isoformat(), "$lte": (today + timedelta(days=30)).isoformat()}}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        codes = await db.promo_codes.find(q, {"_id": 0}).to_list(500)
        sent = mocked = 0
        for c in codes:
            bk = await db.bookings.find_one({"booking_ref": c.get("booking_ref")}, {"_id": 0, "guest_lang": 1, "guest_name": 1}) or {}
            lang = (bk.get("guest_lang") or "en")[:2].lower()
            subj, title, body, cta = REMIND_T.get(lang, REMIND_T["en"])
            pct = int(c.get("amount") or 10)
            url = f"{_get_base_url()}/book/{c.get('property_id','')}?coupon={c['code']}&lang={lang}"
            html = (f"<div style='font-family:Arial,sans-serif;max-width:600px;margin:0 auto;text-align:center;padding:28px'>"
                    f"<h2 style='color:#1a3c5e'>🎁 {title.format(pct=pct)}</h2><p style='color:#475569'>{body.format(code=c['code'], until=c['valid_to'])}</p>"
                    f"<div style='display:inline-block;border:2px dashed #1a3c5e;border-radius:10px;padding:12px 24px;font-size:24px;font-weight:800;letter-spacing:3px;color:#1a3c5e'>{c['code']}</div>"
                    f"<p><a href='{url}' style='display:inline-block;margin-top:12px;background:#2563eb;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:700'>{cta}</a></p></div>")
            st = await _mail(db, c.get("guest_email", ""), subj.format(pct=pct, until=c["valid_to"]), html, kind="coupon_reminder",
                             meta={"code": c["code"], "lang": lang})
            await db.promo_codes.update_one({"id": c["id"]}, {"$set": {"reminder_sent_at": datetime.now(timezone.utc).isoformat(), "reminder_status": st}})
            sent += st == "sent"
            mocked += st == "mocked"
        return {"ok": True, "candidates": len(codes), "sent": sent, "mocked": mocked}

    router.run_coupon_reminders_internal = run_coupon_reminders_internal

    @router.post("/review-collection/coupon-reminders/{property_id}")
    async def coupon_reminders_now(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_coupon_reminders_internal(property_id)

    async def _send_checkin_email(booking: dict, property_name: str):
        """Send pre-arrival self check-in email"""
        if not resend.api_key or resend.api_key == 're_123456789':
            logger.info("No Resend API key, skipping check-in email")
            return
        base_url = _get_base_url()
        checkin_link = f"{base_url}/checkin?ref={booking.get('booking_ref','')}"
        try:
            ci = datetime.fromisoformat(booking["check_in"]).strftime("%A, %d %B %Y") if booking.get("check_in") else ""
        except Exception:
            ci = booking.get("check_in", "")
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">
          <div style="background:linear-gradient(135deg,#059669,#10b981);color:#fff;padding:32px;text-align:center;">
            <h1 style="margin:0;font-size:24px;">Online Check-in Available</h1>
            <p style="margin:8px 0 0;opacity:0.8;font-size:14px;">Skip the queue at {property_name}</p>
          </div>
          <div style="padding:32px;">
            <p style="font-size:15px;color:#475569;line-height:1.6;">Hi {booking.get('guest_name','')},</p>
            <p style="font-size:15px;color:#475569;line-height:1.6;">Your stay is approaching! Complete your online check-in now so you can head straight to your room on arrival.</p>
            <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin:20px 0;">
              <table style="width:100%;font-size:14px;">
                <tr><td style="color:#6b7280;padding:4px 0;">Booking Ref</td><td style="text-align:right;font-weight:600;">{booking.get('booking_ref','')}</td></tr>
                <tr><td style="color:#6b7280;padding:4px 0;">Check-in Date</td><td style="text-align:right;font-weight:600;">{ci}</td></tr>
              </table>
            </div>
            <div style="text-align:center;margin:28px 0;">
              <a href="{checkin_link}" style="display:inline-block;background:#059669;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px;">Check-in Now</a>
            </div>
            <p style="font-size:13px;color:#94a3b8;text-align:center;">Takes less than 2 minutes</p>
            <div style="border-top:1px solid #e2e8f0;margin-top:24px;padding-top:16px;text-align:center;font-size:12px;color:#94a3b8;">
              <p>Powered by MyHotelBox</p>
            </div>
          </div>
        </div>"""
        try:
            await asyncio.to_thread(resend.Emails.send, {"from": SENDER_EMAIL, "to": [booking.get("guest_email", "")], "subject": f"Check-in online for your stay at {property_name}", "html": html})
            logger.info(f"Check-in email sent for {booking.get('booking_ref','')}")
        except Exception as e:
            logger.error(f"Failed to send check-in email: {e}")

    async def _send_cart_recovery_email(cart: dict, property_name: str):
        """Send cart abandonment recovery email"""
        if not resend.api_key or resend.api_key == 're_123456789':
            logger.info("No Resend API key, skipping cart recovery email")
            return
        base_url = _get_base_url()
        recovery_link = f"{base_url}/book?property={cart.get('property_id','')}&recover={cart.get('recovery_token','')}"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">
          <div style="background:linear-gradient(135deg,#dc2626,#ef4444);color:#fff;padding:32px;text-align:center;">
            <h1 style="margin:0;font-size:24px;">You left something behind!</h1>
            <p style="margin:8px 0 0;opacity:0.8;font-size:14px;">{property_name}</p>
          </div>
          <div style="padding:32px;">
            <p style="font-size:15px;color:#475569;line-height:1.6;">Hi {cart.get('guest_name','there')},</p>
            <p style="font-size:15px;color:#475569;line-height:1.6;">We noticed you were looking at our <strong>{cart.get('room_name','')}</strong> but didn't complete your booking. Your room is still available!</p>
            <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:16px;margin:20px 0;text-align:center;">
              <p style="margin:0;font-size:14px;color:#dc2626;font-weight:600;">Room availability is limited — book now to secure your dates</p>
              <p style="margin:8px 0 0;font-size:12px;color:#6b7280;">{cart.get('check_in','')} — {cart.get('check_out','')}</p>
            </div>
            <div style="text-align:center;margin:28px 0;">
              <a href="{recovery_link}" style="display:inline-block;background:#dc2626;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px;">Complete Your Booking</a>
            </div>
            <div style="border-top:1px solid #e2e8f0;margin-top:24px;padding-top:16px;text-align:center;font-size:12px;color:#94a3b8;">
              <p>Powered by MyHotelBox</p>
            </div>
          </div>
        </div>"""
        try:
            await asyncio.to_thread(resend.Emails.send, {"from": SENDER_EMAIL, "to": [cart.get("guest_email", "")], "subject": f"Complete your booking at {property_name}", "html": html})
            await db.abandoned_carts.update_one({"recovery_token": cart["recovery_token"]}, {"$set": {"status": "email_sent", "email_sent_at": datetime.now(timezone.utc).isoformat()}})
            logger.info(f"Cart recovery email sent to {cart.get('guest_email','')}")
        except Exception as e:
            logger.error(f"Failed to send cart recovery email: {e}")

    async def _send_guest_portal_email(guest_email: str, magic_token: str):
        """Send guest portal magic link email"""
        if not resend.api_key or resend.api_key == 're_123456789':
            logger.info("No Resend API key, skipping portal email")
            return
        base_url = _get_base_url()
        portal_link = f"{base_url}/guest-portal?token={magic_token}"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">
          <div style="background:linear-gradient(135deg,#1e293b,#475569);color:#fff;padding:32px;text-align:center;">
            <h1 style="margin:0;font-size:24px;">Your Guest Portal Access</h1>
          </div>
          <div style="padding:32px;">
            <p style="font-size:15px;color:#475569;line-height:1.6;">Hi,</p>
            <p style="font-size:15px;color:#475569;line-height:1.6;">Click below to securely access your booking history and manage your stays.</p>
            <div style="text-align:center;margin:28px 0;">
              <a href="{portal_link}" style="display:inline-block;background:#1e293b;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px;">Access Guest Portal</a>
            </div>
            <p style="font-size:13px;color:#94a3b8;text-align:center;">This link expires in 24 hours</p>
            <div style="border-top:1px solid #e2e8f0;margin-top:24px;padding-top:16px;text-align:center;font-size:12px;color:#94a3b8;">
              <p>Powered by MyHotelBox</p>
            </div>
          </div>
        </div>"""
        try:
            await asyncio.to_thread(resend.Emails.send, {"from": SENDER_EMAIL, "to": [guest_email], "subject": "Your Guest Portal Access Link", "html": html})
            logger.info(f"Portal email sent to {guest_email}")
        except Exception as e:
            logger.error(f"Failed to send portal email: {e}")

    @router.get("/booking/reservation/{booking_ref}")
    async def get_booking_by_ref(booking_ref: str):
        """Public endpoint: Get booking details by reference"""
        booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        room = await db.room_types.find_one({"id": booking["room_type_id"]}, {"_id": 0})
        prop = await db.properties.find_one({"id": booking["property_id"]}, {"_id": 0})

        return {**booking, "room_type": room, "property": prop}

    @router.get("/booking/reviews/{property_id}")
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
    @router.post("/room-types")
    async def create_room_type(room: RoomTypeCreate, current_user: dict = Depends(require_perm("manage_room_categories"))):
        """Create a new room type"""
        room_type = RoomType(**room.model_dump())
        doc = room_type.model_dump()
        await db.room_types.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/room-types")
    async def list_room_types(property_id: str = ""):
        """List room types, optionally filtered by property"""
        query = {"property_id": property_id} if property_id else {}
        rooms = await db.room_types.find(query, {"_id": 0}).to_list(100)
        return rooms

    @router.put("/room-types/{room_id}")
    async def update_room_type(room_id: str, update: RoomTypeUpdate, current_user: dict = Depends(require_perm("manage_room_categories"))):
        """Update a room type"""
        update_data = {k: v for k, v in update.model_dump().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")

        result = await db.room_types.update_one({"id": room_id}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Room type not found")

        updated = await db.room_types.find_one({"id": room_id}, {"_id": 0})
        return updated

    @router.delete("/room-types/{room_id}")
    async def delete_room_type(room_id: str, current_user: dict = Depends(require_perm("manage_room_categories", "delete_bookings", mode="any"))):
        """Delete a room type"""
        result = await db.room_types.delete_one({"id": room_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Room type not found")
        return {"status": "deleted"}

    # Admin: Bookings management
    @router.post("/bookings")
    async def create_manual_booking(data: Dict,
                                    current_user: dict = Depends(require_perm("view_bookings"))):
        """Personel manuel rezervasyon oluşturma (iter 379 — eksik endpoint tamamlandı)."""
        required = ["property_id", "guest_name", "check_in", "check_out"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            raise HTTPException(400, f"Eksik alanlar: {', '.join(missing)}")
        try:
            ci = datetime.strptime(data["check_in"], "%Y-%m-%d")
            co = datetime.strptime(data["check_out"], "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Tarih formatı YYYY-MM-DD olmalı")
        nights = (co - ci).days
        if nights < 1:
            raise HTTPException(400, "check_out, check_in'den sonra olmalı")
        rate = float(data.get("rate") or 0)
        total = float(data.get("total_price") or (rate * nights * int(data.get("rooms", 1) or 1)))
        now = datetime.now(timezone.utc).isoformat()
        booking = {
            "id": str(uuid.uuid4()),
            "booking_ref": f"BK-{str(uuid.uuid4())[:6].upper()}",
            "property_id": data["property_id"],
            "room_type_id": data.get("room_type_id"),
            "room_type": data.get("room_type"),
            "room_id": data.get("room_id"),
            "room_number": data.get("room_number"),
            "guest_name": data["guest_name"],
            "guest_email": data.get("guest_email", ""),
            "guest_phone": data.get("guest_phone", ""),
            "check_in": data["check_in"],
            "check_out": data["check_out"],
            "nights": nights,
            "adults": int(data.get("adults", 2) or 2),
            "children": int(data.get("children", 0) or 0),
            "rooms": int(data.get("rooms", 1) or 1),
            "rate": rate,
            "total_price": total,
            "currency": data.get("currency", "GBP"),
            "status": data.get("status", "confirmed"),
            "payment_status": data.get("payment_status", "pending"),
            "source": data.get("source", "manual"),
            "channel": data.get("channel", "direct"),
            "notes": data.get("notes", ""),
            "created_by": current_user.get("name", ""),
            "created_at": now,
            "updated_at": now,
        }
        booking = {k: v for k, v in booking.items() if v is not None}
        await db.bookings.insert_one(dict(booking))
        try:
            from routes.revenue_ext.reprice_bridge import fire_reprice
            fire_reprice(db, booking["property_id"], "booking_created", booking.get("id", ""))
        except Exception:
            pass
        booking.pop("_id", None)
        asyncio.create_task(fire_webhooks(db, "booking.created", booking))
        return booking

    @router.get("/bookings")
    async def list_bookings(property_id: str = "", status: str = "", current_user: dict = Depends(require_perm("view_bookings"))):
        """List bookings with optional filters, enriched with live folio balance."""
        query = {}
        if property_id:
            query["property_id"] = property_id
        if status:
            query["status"] = status

        bookings = await db.bookings.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        if not bookings:
            return bookings

        # One aggregated query across folio entries for all bookings in the result set.
        # Primary collection is `folio_items` (what guest_services writes); include
        # `folio_charges` too for any legacy rows.
        booking_ids = [b["id"] for b in bookings if b.get("id")]
        paid_by_booking: Dict[str, float] = {}
        charged_by_booking: Dict[str, float] = {}
        if booking_ids:
            pipeline = [
                {"$match": {"booking_id": {"$in": booking_ids}}},
                {"$group": {
                    "_id": {"b": "$booking_id", "t": "$type"},
                    "sum": {"$sum": {"$toDouble": {"$ifNull": ["$amount", 0]}}},
                }},
            ]
            for coll_name in ("folio_items", "folio_charges"):
                async for row in db[coll_name].aggregate(pipeline):
                    key = row["_id"]
                    bid = key.get("b")
                    if not bid:
                        continue
                    t = (key.get("t") or "").lower()
                    if t == "payment":
                        paid_by_booking[bid] = paid_by_booking.get(bid, 0) + float(row["sum"])
                    else:
                        # Every non-payment line contributes to gross charges
                        charged_by_booking[bid] = charged_by_booking.get(bid, 0) + float(row["sum"])

        for b in bookings:
            bid = b.get("id")
            paid = round(paid_by_booking.get(bid, 0), 2)
            charged = round(charged_by_booking.get(bid, 0), 2)
            # Gross due = folio charges if present, else booking.total_price (pre-folio bookings)
            gross = charged if charged > 0 else round(float(b.get("total_price") or 0), 2)
            b["folio_paid"] = paid
            b["folio_charged"] = charged
            b["balance_due"] = max(0.0, round(gross - paid, 2))
        return bookings

    @router.put("/bookings/{booking_id}/room")
    async def move_booking_room(booking_id: str, data: dict, current_user: dict = Depends(require_perm("edit_bookings"))):
        """Oda değiştir/taşı — Cloudbeds paritesi."""
        room = str(data.get("room_number", "")).strip()[:20]
        if not room:
            raise HTTPException(status_code=422, detail="Oda numarası gerekli")
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0, "room_number": 1, "property_id": 1, "check_in": 1, "check_out": 1})
        if not b:
            raise HTTPException(status_code=404, detail="Booking not found")
        clash = await db.bookings.find_one({
            "id": {"$ne": booking_id}, "property_id": b.get("property_id"),
            "room_number": room, "status": {"$nin": ["cancelled", "no_show", "checked_out"]},
            "check_in": {"$lt": b.get("check_out", "")}, "check_out": {"$gt": b.get("check_in", "")}},
            {"_id": 0, "guest_name": 1})
        if clash:
            raise HTTPException(status_code=409, detail=f"Oda {room} bu tarihlerde dolu ({clash.get('guest_name', '')})")
        await db.bookings.update_one({"id": booking_id},
                                     {"$set": {"room_number": room,
                                               "room_moved_by": current_user.get("email", ""),
                                               "room_moved_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True, "old_room": b.get("room_number"), "new_room": room}

    @router.put("/bookings/{booking_id}/dates")
    async def update_booking_dates(booking_id: str, data: dict, current_user: dict = Depends(require_perm("edit_bookings"))):
        """Tarih düzenle — giriş/çıkış tarihlerini çakışma kontrolüyle günceller."""
        try:
            ci = datetime.strptime(str(data.get("check_in", "")), "%Y-%m-%d")
            co = datetime.strptime(str(data.get("check_out", "")), "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=422, detail="Tarih formatı YYYY-MM-DD olmalı")
        nights = (co - ci).days
        if nights < 1:
            raise HTTPException(status_code=422, detail="Çıkış tarihi girişten sonra olmalı")
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(status_code=404, detail="Booking not found")
        ci_s, co_s = ci.strftime("%Y-%m-%d"), co.strftime("%Y-%m-%d")
        if b.get("room_id"):
            clash = await db.bookings.find_one({
                "id": {"$ne": booking_id}, "room_id": b["room_id"],
                "status": {"$nin": ["cancelled", "no_show", "checked_out"]},
                "check_in": {"$lt": co_s}, "check_out": {"$gt": ci_s}},
                {"_id": 0, "guest_name": 1, "check_in": 1, "check_out": 1})
            if clash:
                raise HTTPException(status_code=409,
                                    detail=f"Çakışma: {clash.get('guest_name', '')} ({clash.get('check_in')} → {clash.get('check_out')})")
        rate = float(b.get("rate") or 0)
        updates = {"check_in": ci_s, "check_out": co_s, "nights": nights,
                   "updated_at": datetime.now(timezone.utc).isoformat(),
                   "dates_changed_by": current_user.get("email", "")}
        if rate > 0:
            updates["total_price"] = round(rate * nights * int(b.get("rooms", 1) or 1), 2)
        await db.bookings.update_one({"id": booking_id}, {"$set": updates})
        return {"ok": True, "check_in": ci_s, "check_out": co_s, "nights": nights,
                "total_price": updates.get("total_price", b.get("total_price"))}

    @router.post("/bookings/{booking_id}/split")
    async def split_booking(booking_id: str, data: dict, current_user: dict = Depends(require_perm("edit_bookings"))):
        """Rezervasyonu böl — split_date'te ikiye ayır, ikinci kısım yeni odaya taşınır."""
        split_date = str(data.get("split_date", "")).strip()
        new_room_id = str(data.get("new_room_id", "")).strip()
        if not split_date or not new_room_id:
            raise HTTPException(status_code=422, detail="split_date ve new_room_id zorunlu")
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(status_code=404, detail="Booking not found")
        ci, co = b.get("check_in", ""), b.get("check_out", "")
        if not (ci < split_date < co):
            raise HTTPException(status_code=422, detail=f"Bölme tarihi {ci} ile {co} arasında olmalı")
        new_room = await db.rooms.find_one({"id": new_room_id}, {"_id": 0})
        if not new_room:
            raise HTTPException(status_code=404, detail="Hedef oda bulunamadı")
        clash = await db.bookings.find_one({
            "id": {"$ne": booking_id}, "room_id": new_room_id,
            "status": {"$nin": ["cancelled", "no_show", "checked_out"]},
            "check_in": {"$lt": co}, "check_out": {"$gt": split_date}},
            {"_id": 0, "guest_name": 1})
        if clash:
            raise HTTPException(status_code=409, detail=f"Hedef oda bu tarihlerde dolu ({clash.get('guest_name', '')})")
        total = float(b.get("total_price") or 0)
        orig_nights = max(1, (datetime.strptime(co, "%Y-%m-%d") - datetime.strptime(ci, "%Y-%m-%d")).days)
        first_nights = (datetime.strptime(split_date, "%Y-%m-%d") - datetime.strptime(ci, "%Y-%m-%d")).days
        second_nights = orig_nights - first_nights
        first_total = round(total * first_nights / orig_nights, 2)
        second_total = round(total - first_total, 2)
        now = datetime.now(timezone.utc).isoformat()
        second = {
            "id": str(uuid.uuid4()),
            "booking_ref": f"{b.get('booking_ref') or booking_id[:6].upper()}-B",
            "property_id": b.get("property_id"),
            "room_type_id": new_room.get("room_type_id"),
            "room_id": new_room_id,
            "room_number": new_room.get("name", ""),
            "guest_name": b.get("guest_name"),
            "guest_email": b.get("guest_email", ""),
            "guest_phone": b.get("guest_phone", ""),
            "check_in": split_date, "check_out": co, "nights": second_nights,
            "adults": b.get("adults", 2), "children": b.get("children", 0),
            "rooms": b.get("rooms", 1), "rate": b.get("rate", 0),
            "total_price": second_total, "currency": b.get("currency", "GBP"),
            "status": "confirmed" if b.get("status") == "checked_in" else b.get("status", "confirmed"),
            "payment_status": "pending",
            "source": b.get("source", "manual"), "channel": b.get("channel", "direct"),
            "notes": f"Bölünmüş konaklama (2/2) — {b.get('booking_ref', '')}. {b.get('notes', '')}".strip(),
            "split_from": booking_id,
            "created_by": current_user.get("name", ""), "created_at": now, "updated_at": now,
        }
        await db.bookings.insert_one(dict(second))
        await db.bookings.update_one({"id": booking_id}, {"$set": {
            "check_out": split_date, "nights": first_nights, "total_price": first_total,
            "split_into": second["id"], "updated_at": now,
            "notes": f"Bölünmüş konaklama (1/2). {b.get('notes', '')}".strip()}})
        second.pop("_id", None)
        return {"ok": True, "first": {"id": booking_id, "check_out": split_date, "nights": first_nights, "total_price": first_total},
                "second": second}

    @router.post("/bookings/{booking_id}/resend-confirmation")
    async def resend_confirmation(booking_id: str, current_user: dict = Depends(require_perm("edit_bookings"))):
        """Rezervasyon onay e-postasını yeniden gönderir."""
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(status_code=404, detail="Booking not found")
        if not b.get("guest_email"):
            raise HTTPException(status_code=422, detail="Misafirin e-posta adresi yok")
        html = (f"<h3>Rezervasyon Onayı — {b.get('booking_ref') or booking_id[:8]}</h3>"
                f"<p>Sayın {b.get('guest_name', '')},</p>"
                f"<p>Rezervasyonunuz onaylıdır:</p>"
                f"<ul><li>Giriş: {b.get('check_in')}</li><li>Çıkış: {b.get('check_out')}</li>"
                f"<li>Oda: {b.get('room_number') or b.get('room_type_id', '')}</li>"
                f"<li>Tutar: {b.get('currency', 'GBP')} {b.get('total_price')}</li></ul>"
                f"<p>Görüşmek üzere!</p>")
        from routes.platform_ext.mailer import send_email
        last = b.get("confirmation_resent_at")
        if last:
            try:
                if (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() < 60:
                    raise HTTPException(status_code=429, detail="Lütfen 1 dakika bekleyin — onay az önce gönderildi")
            except ValueError:
                pass
        await send_email(db, b["guest_email"],
                         f"✅ Rezervasyon Onayı — {b.get('booking_ref') or booking_id[:8]}",
                         html, kind="booking_confirmation_resend", meta={"booking_id": booking_id})
        await db.bookings.update_one({"id": booking_id}, {"$set": {"confirmation_resent_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True, "to": b["guest_email"]}

    @router.put("/bookings/{booking_id}/status")
    async def update_booking_status(booking_id: str, status: str, current_user: dict = Depends(require_perm("edit_bookings", "cancel_bookings", "checkin_bookings", "checkout_bookings", "confirm_bookings", mode="any"))):
        """Update booking status"""
        valid = ["confirmed", "cancelled", "checked_in", "checked_out", "no_show"]
        if status not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")

        result = await db.bookings.update_one({"id": booking_id}, {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}})
        if result.matched_count:
            try:
                from routes.revenue_ext.reprice_bridge import fire_reprice
                _b = await db.bookings.find_one({"id": booking_id}, {"_id": 0, "property_id": 1})
                if _b and status in ("cancelled", "no_show", "confirmed"):
                    fire_reprice(db, _b["property_id"], f"booking_{status}", booking_id)
            except Exception:
                pass
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
            asyncio.create_task(fire_webhooks(db, "booking.cancelled", wh_data))
            await log_sync(db, "booking-engine", "outbound", "success", f"Booking {updated.get('booking_ref')} cancelled — webhook fired", updated.get("booking_ref", ""))
        elif status == "confirmed":
            asyncio.create_task(fire_webhooks(db, "booking.confirmed", wh_data))
        elif status == "checked_out":
            try:
                from routes.security.tr_compliance import auto_issue_on_checkout
                asyncio.create_task(auto_issue_on_checkout(updated))
            except Exception as _e:  # noqa: BLE001
                logger.warning(f"auto e-invoice hook failed: {_e}")
            # Housekeeping auto-dispatch: block the room with a "Deep Clean" OOS so
            # nobody double-books a dirty room. Housekeeping removes it when the
            # room is back to "clean".
            if updated.get("room_id"):
                import uuid as _uuid
                co_date = updated.get("check_out") or datetime.now(timezone.utc).date().isoformat()
                # Block from checkout date through end-of-next-day (exclusive checkout semantics handled on render)
                end_date = (datetime.strptime(co_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                await db.oos_blocks.insert_one({
                    "id": str(_uuid.uuid4()),
                    "room_id": updated["room_id"],
                    "property_id": updated.get("property_id", ""),
                    "start": co_date,
                    "end": end_date,
                    "reason": "Deep Clean",
                    "auto": True,
                    "booking_id": booking_id,
                    "created_by": "system:housekeeping-autodispatch",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                # Mark room housekeeping status as dirty
                await db.rooms.update_one({"id": updated["room_id"]}, {"$set": {"housekeeping": "dirty"}})
            asyncio.create_task(fire_webhooks(db, "booking.checked_out", wh_data))
            # Direct Booking Conversion Engine — OTA misafirine kupon gönder (iter 375)
            try:
                from routes.integrations_pkg.direct_conversion import process_checkout_conversion
                asyncio.create_task(process_checkout_conversion(db, updated))
            except Exception:
                pass

        return updated

    # Include the router in the main app


    return router
