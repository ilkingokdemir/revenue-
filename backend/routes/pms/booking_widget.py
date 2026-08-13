"""
Online Booking Widget — Public booking form for hotel websites
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_booking_widget_router(db, require_roles):
    router = APIRouter()

    # ==================== PUBLIC: PROPERTY INFO ====================

    @router.get("/booking-widget/info/{property_id}")
    async def widget_info(property_id: str):
        """Public: Get property info and room types for booking widget"""
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")

        rooms = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        if not rooms:
            rooms = [
                {"id": "standard", "name": "Standard Room", "base_rate": 100, "max_occupancy": 2, "description": "Comfortable room with all essentials", "photo": "https://images.unsplash.com/photo-1631048730670-ff5cd0d08f15?w=600&q=75"},
                {"id": "deluxe", "name": "Deluxe Room", "base_rate": 150, "max_occupancy": 2, "description": "Spacious room with premium amenities", "photo": "https://images.unsplash.com/photo-1629140727571-9b5c6f6267b4?w=600&q=75"},
                {"id": "suite", "name": "Suite", "base_rate": 250, "max_occupancy": 4, "description": "Luxurious suite with separate living area", "photo": "https://images.unsplash.com/photo-1631049307305-1ceea96fb0e1?w=600&q=75"},
            ]

        # Default room photos by index
        default_photos = [
            "https://images.unsplash.com/photo-1631048730670-ff5cd0d08f15?w=600&q=75",
            "https://images.unsplash.com/photo-1629140727571-9b5c6f6267b4?w=600&q=75",
            "https://images.unsplash.com/photo-1631049307305-1ceea96fb0e1?w=600&q=75",
            "https://images.unsplash.com/photo-1631048835184-3f0ceda91b75?w=600&q=75",
            "https://images.pexels.com/photos/97083/pexels-photo-97083.jpeg?auto=compress&cs=tinysrgb&w=600",
        ]

        # Get rate plans for dynamic pricing
        plans = await db.rate_plans.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(20)

        # Get reviews
        reviews = await db.guest_reviews.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
        if not reviews:
            reviews = [
                {"guest_name": "Sarah M.", "country": "United Kingdom", "rating": 9.4, "title": "Wonderful stay!", "comment": "Beautiful rooms, amazing staff. The location was perfect and the breakfast was excellent. Would definitely come back!", "date": "March 2026"},
                {"guest_name": "Thomas L.", "country": "Germany", "rating": 9.1, "title": "Great value", "comment": "Clean, comfortable, and well-located. The staff went above and beyond to help with our requests. Highly recommended.", "date": "February 2026"},
                {"guest_name": "Maria G.", "country": "Spain", "rating": 9.6, "title": "Exceptional", "comment": "From check-in to check-out, everything was perfect. The room was spacious and immaculately clean. Best hotel experience in London.", "date": "January 2026"},
                {"guest_name": "James W.", "country": "United States", "rating": 8.8, "title": "Very comfortable", "comment": "Great location, friendly staff. The room was exactly as pictured. The only minor thing was the lift was slow during peak times.", "date": "March 2026"},
                {"guest_name": "Yuki T.", "country": "Japan", "rating": 9.7, "title": "Perfect in every way", "comment": "Absolutely loved our stay. The attention to detail was remarkable. Will definitely be our go-to hotel when visiting London.", "date": "February 2026"},
                {"guest_name": "Ahmed K.", "country": "UAE", "rating": 9.2, "title": "Premium quality", "comment": "Excellent service and beautiful property. The suite was luxurious with a stunning city view. Great breakfast selection too.", "date": "January 2026"},
            ]
        avg_rating = round(sum(r.get("rating", 0) for r in reviews) / max(len(reviews), 1), 1) if reviews else 0

        # Widget theme config
        wconfig = await db.booking_widget_config.find_one({"property_id": property_id}, {"_id": 0})
        theme = {
            "accent_color": (wconfig or {}).get("accent_color", "#1a3c5e"),
            "hero_image": (wconfig or {}).get("hero_image", "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=1920&q=80"),
            "tagline": (wconfig or {}).get("tagline", "Premium Accommodation"),
            "subtitle": (wconfig or {}).get("subtitle", "Experience exceptional hospitality with our best rate guarantee when you book direct"),
        }

        return {
            "hotel_name": hotel_name,
            "property_id": property_id,
            "logo_url": ts.get("logo_url", ""),
            "rooms": [{"id": r.get("id", ""), "name": r.get("name", ""), "base_rate": r.get("base_rate", 0), "max_occupancy": r.get("max_occupancy", 2), "description": r.get("description", ""), "amenities": r.get("amenities", []), "photo": r.get("photo", "") or default_photos[i % len(default_photos)]} for i, r in enumerate(rooms)],
            "currency": ts.get("currency", "GBP"),
            "has_rate_plans": len(plans) > 0,
            "reviews": reviews,
            "avg_rating": avg_rating,
            "review_count": len(reviews),
            "theme": theme,
        }

    # ==================== PUBLIC: CHECK AVAILABILITY ====================

    @router.post("/booking-widget/loyalty-check")
    async def widget_loyalty_check(data: Dict):
        """Public: check whether a guest_email is a known loyalty member.
        Returns the tier and the exclusive direct-booking discount % to apply.
        """
        email = (data.get("guest_email") or "").strip().lower()
        if not email:
            raise HTTPException(400, "guest_email required")
        # Find loyalty member by email
        member = await db.loyalty_members.find_one(
            {"guest_email": {"$regex": f"^{email}$", "$options": "i"}},
            {"_id": 0, "tier": 1, "guest_name": 1, "lifetime_points": 1, "total_stays": 1}
        )
        if not member:
            return {"is_member": False, "tier": None, "discount_pct": 0}
        tier = member.get("tier", "standard")
        # Exclusive direct-book discounts (mirrors industry: bigger reward for higher tiers)
        discount = {"standard": 5, "silver": 8, "gold": 12, "platinum": 18}.get(tier, 5)
        return {
            "is_member": True,
            "tier": tier,
            "guest_name": member.get("guest_name", ""),
            "lifetime_points": member.get("lifetime_points", 0),
            "total_stays": member.get("total_stays", 0),
            "discount_pct": discount,
            "message": f"Welcome back! As a {tier.upper()} member you get {discount}% off when you book direct.",
        }

    @router.post("/booking-widget/check-availability")
    async def check_availability(data: Dict):
        """Public: Check room availability for dates"""
        property_id = data.get("property_id", "")
        check_in = data.get("check_in", "")
        check_out = data.get("check_out", "")

        if not all([property_id, check_in, check_out]):
            raise HTTPException(400, "property_id, check_in, check_out required")

        # Get all room types
        rooms = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        if not rooms:
            rooms = [
                {"id": "standard", "name": "Standard Room", "base_rate": 100, "total_rooms": 10, "max_occupancy": 2},
                {"id": "deluxe", "name": "Deluxe Room", "base_rate": 150, "total_rooms": 5, "max_occupancy": 2},
                {"id": "suite", "name": "Suite", "base_rate": 250, "total_rooms": 2, "max_occupancy": 4},
            ]

        # Check existing bookings for overlap
        available = []
        for room in rooms:
            booked = await db.bookings.count_documents({
                "property_id": property_id,
                "room_type": room.get("name", ""),
                "status": {"$in": ["confirmed", "checked_in"]},
                "check_in": {"$lt": check_out},
                "check_out": {"$gt": check_in},
            })
            total = room.get("total_rooms", 10)
            avail = max(total - booked, 0)
            if avail > 0:
                # Calculate nights
                try:
                    ci = datetime.strptime(check_in, "%Y-%m-%d")
                    co = datetime.strptime(check_out, "%Y-%m-%d")
                    nights = (co - ci).days
                except Exception:
                    nights = 1

                rate = room.get("base_rate") or 100
                default_photos = [
                    "https://images.unsplash.com/photo-1631048730670-ff5cd0d08f15?w=600&q=75",
                    "https://images.unsplash.com/photo-1629140727571-9b5c6f6267b4?w=600&q=75",
                    "https://images.unsplash.com/photo-1631049307305-1ceea96fb0e1?w=600&q=75",
                    "https://images.unsplash.com/photo-1631048835184-3f0ceda91b75?w=600&q=75",
                    "https://images.pexels.com/photos/97083/pexels-photo-97083.jpeg?auto=compress&cs=tinysrgb&w=600",
                ]
                idx = rooms.index(room) if room in rooms else 0
                available.append({
                    "room_type_id": room.get("id", ""),
                    "name": room.get("name", ""),
                    "photo": room.get("photo", "") or default_photos[idx % len(default_photos)],
                    "base_rate": rate,
                    "total_rate": round(rate * nights, 2),
                    "nights": nights,
                    "available": avail,
                    "max_occupancy": room.get("max_occupancy", 2),
                    "description": room.get("description", ""),
                    "amenities": room.get("amenities", []),
                })
        if not available and rooms:
            try:
                from routes.revenue_ext.lost_demand import log_lost_demand
                await log_lost_demand(db, property_id, {
                    "check_in": check_in, "check_out": check_out, "rooms": 1,
                    "channel": "widget", "reason": "no_availability",
                    "note": "Widget araması — müsait oda bulunamadı"}, source="widget_auto")
            except Exception as ex:
                logger.warning("Lost demand auto-log failed: %s", ex)
        return {"available_rooms": available, "check_in": check_in, "check_out": check_out}

    # ==================== PUBLIC: CREATE BOOKING ====================

    @router.post("/booking-widget/book")
    async def create_widget_booking(data: Dict, request: Request):
        """Public endpoint — guest submits the widget form.

        If `pay_now=true` (default), the booking is saved with `status=pending_payment`
        and a Stripe Checkout Session is created — the response includes `checkout_url`
        so the frontend can redirect the guest. The Stripe webhook flips the booking to
        `confirmed` + sends the confirmation email when payment lands.

        If `pay_now=false` (pay-at-property mode), the booking is `confirmed` immediately
        and an email mock is logged right away.
        """
        required = ["property_id", "room_type", "check_in", "check_out", "guest_name", "guest_email"]
        for f in required:
            if not data.get(f):
                raise HTTPException(400, f"{f} is required")

        now = datetime.now(timezone.utc).isoformat()
        booking_ref = f"WEB-{uuid.uuid4().hex[:8].upper()}"

        try:
            ci = datetime.strptime(data["check_in"], "%Y-%m-%d")
            co = datetime.strptime(data["check_out"], "%Y-%m-%d")
            nights = (co - ci).days
        except Exception:
            nights = 1

        rate = float(data.get("rate", 0))
        total = round(rate * nights * int(data.get("rooms", 1)), 2)

        # ABS — Attribute-Based Selling: seçilen oda özellikleri gecelik ek ücret
        abs_ids = data.get("abs_attribute_ids") or []
        abs_selected, abs_total = [], 0.0
        if isinstance(abs_ids, list) and abs_ids:
            attrs = await db.abs_attributes.find(
                {"property_id": data["property_id"],
                 "id": {"$in": [str(a) for a in abs_ids][:10]},
                 "active": {"$ne": False}},
                {"_id": 0, "id": 1, "name": 1, "price": 1}).to_list(10)
            for a in attrs:
                abs_selected.append(a)
                abs_total += float(a.get("price", 0) or 0)
            abs_total = round(abs_total * nights * int(data.get("rooms", 1)), 2)
            total = round(total + abs_total, 2)

        # Direct conversion kuponu (iter 376) — total üzerinden indirim
        coupon_code = (data.get("coupon_code") or "").strip().upper()
        coupon_info = None
        winback_offer = None
        import re as _re
        wb_match = _re.match(r"^WELCOME(\d{1,2})$", coupon_code)
        if wb_match:
            pct = int(wb_match.group(1))
            wb_q = {"property_id": data["property_id"], "discount_pct": pct,
                    "redeemed": {"$ne": True},
                    "$or": [{"expires_at": {"$exists": False}},
                            {"expires_at": {"$gte": now}}]}
            winback_offer = await db.winback_offers.find_one(
                {**wb_q, "guest_email": data["guest_email"]}, {"_id": 0}) or \
                await db.winback_offers.find_one(wb_q, {"_id": 0})
            if not winback_offer:
                raise HTTPException(400, "Bu geri kazanım kodu geçersiz, kullanılmış veya süresi dolmuş")
            wb_discount = round(total * pct / 100, 2)
            total = round(total - wb_discount, 2)
        elif coupon_code:
            from routes.integrations_pkg.direct_conversion import redeem_coupon_for_booking
            coupon_info = await redeem_coupon_for_booking(
                db, coupon_code, total, guest_email=data["guest_email"],
                booking_ref=booking_ref, nights=nights)
            if not coupon_info.get("ok"):
                raise HTTPException(400, coupon_info.get("reason", "Kupon geçersiz"))
            total = round(total - coupon_info["discount_amount"], 2)

        pay_now = bool(data.get("pay_now", True)) and total > 0
        currency = (data.get("currency", "GBP") or "GBP").upper()

        booking = {
            "id": str(uuid.uuid4()),
            "booking_ref": booking_ref,
            "property_id": data["property_id"],
            "guest_name": data["guest_name"],
            "guest_email": data["guest_email"],
            "guest_phone": data.get("guest_phone", ""),
            "check_in": data["check_in"],
            "check_out": data["check_out"],
            "rooms": int(data.get("rooms", 1)),
            "room_type": data["room_type"],
            "rate": rate,
            "total": total,
            "total_price": total,  # required by /payments/booking-checkout
            "nights": nights,
            "currency": currency,
            "status": "pending_payment" if pay_now else "confirmed",
            "payment_status": "pending" if pay_now else "pay_at_property",
            "source": "website_widget",
            "abs_attributes": abs_selected,
            "abs_total": abs_total,
            "special_requests": data.get("special_requests", ""),
            "guests": int(data.get("guests", 1)),
            "created_at": now,
        }
        if coupon_info:
            booking.update({
                "coupon_code": coupon_code,
                "coupon_discount_pct": coupon_info["discount_pct"],
                "coupon_discount_amount": coupon_info["discount_amount"],
                "coupon_commission_saved": coupon_info["commission_saved"],
            })
        if winback_offer:
            booking.update({
                "coupon_code": coupon_code,
                "coupon_discount_pct": winback_offer["discount_pct"],
                "coupon_discount_amount": wb_discount,
                "coupon_type": "winback",
            })
        await db.bookings.insert_one(booking)
        booking.pop("_id", None)

        if winback_offer:
            await db.winback_offers.update_one(
                {"id": winback_offer["id"]},
                {"$set": {"redeemed": True, "redeemed_at": now,
                          "redeemed_via": "reservation", "booking_ref": booking_ref}})

        # Confirmed (no payment) → log email mock immediately
        if not pay_now:
            await db.booking_email_log.insert_one({
                "id": str(uuid.uuid4()),
                "booking_id": booking["id"],
                "booking_ref": booking_ref,
                "to": booking["guest_email"],
                "subject": f"Booking confirmed · {booking_ref}",
                "type": "booking_confirmation",
                "status": "MOCKED",
                "sent_at": now,
            })
            return {"status": "confirmed", "booking_ref": booking_ref, "booking": booking}

        # Pay-now flow → forward to Stripe Checkout (reuses existing /payments/booking-checkout
        # logic by calling its underlying StripeCheckout client directly to avoid an
        # in-process HTTP hop).
        from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
        import os
        api_key = os.environ.get("STRIPE_API_KEY", "")
        host_url = str(request.base_url).rstrip("/")
        # Origin URL where Stripe should redirect — fall back to request host
        origin = (data.get("origin_url") or host_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        sc = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
        success_url = f"{origin}/book?property={booking['property_id']}&payment=success&session_id={{CHECKOUT_SESSION_ID}}&ref={booking_ref}"
        cancel_url = f"{origin}/book?property={booking['property_id']}&payment=cancelled&ref={booking_ref}"
        req = CheckoutSessionRequest(
            amount=total,
            currency=currency.lower(),
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "type": "booking",
                "booking_id": booking["id"],
                "booking_ref": booking_ref,
                "guest_name": booking["guest_name"],
                "guest_email": booking["guest_email"],
                "property_id": booking["property_id"],
            },
        )
        try:
            session = await sc.create_checkout_session(req)
            await db.payment_transactions.insert_one({
                "id": str(uuid.uuid4()),
                "session_id": session.session_id,
                "type": "booking",
                "reference_id": booking["id"],
                "reference_number": booking_ref,
                "property_id": booking["property_id"],
                "amount": total,
                "currency": currency.lower(),
                "guest_name": booking["guest_name"],
                "guest_email": booking["guest_email"],
                "payment_method": "stripe",
                "payment_status": "initiated",
                "metadata": req.metadata,
                "created_at": now,
            })
            return {
                "status": "pending_payment",
                "booking_ref": booking_ref,
                "booking": booking,
                "checkout_url": session.url,
                "session_id": session.session_id,
            }
        except Exception as e:
            logger.error(f"Stripe checkout creation failed: {e}")
            # Fall back to confirmed-without-payment so the guest's data isn't lost
            await db.bookings.update_one(
                {"id": booking["id"]},
                {"$set": {"status": "confirmed", "payment_status": "manual"}},
            )
            return {
                "status": "confirmed",
                "booking_ref": booking_ref,
                "booking": booking,
                "warning": f"Payment unavailable, booking saved as confirmed (manual): {e}",
            }

    @router.get("/booking-widget/payment-status/{booking_ref}")
    async def widget_payment_status(booking_ref: str):
        """Polled by the success page after Stripe redirect. Returns the latest booking
        status so the UI can show 'Confirmed' once the webhook flips it."""
        booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        return {
            "booking_ref": booking_ref,
            "status": booking.get("status"),
            "payment_status": booking.get("payment_status"),
            "total": booking.get("total"),
            "currency": booking.get("currency"),
            "guest_name": booking.get("guest_name"),
            "guest_email": booking.get("guest_email"),
            "check_in": booking.get("check_in"),
            "check_out": booking.get("check_out"),
        }

    # ==================== ADMIN: WIDGET CONFIG ====================

    @router.get("/booking-widget/config/{property_id}")
    async def get_widget_config(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        config = await db.booking_widget_config.find_one({"property_id": property_id}, {"_id": 0})
        if not config:
            return {"property_id": property_id, "enabled": True, "accent_color": "#1e3a5f", "show_rates": True}
        return config

    @router.put("/booking-widget/config/{property_id}")
    async def update_widget_config(property_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        data["property_id"] = property_id
        await db.booking_widget_config.update_one({"property_id": property_id}, {"$set": data}, upsert=True)
        return {"status": "saved"}

    # ==================== ADMIN: ROOM PHOTO UPLOAD ====================

    from fastapi import UploadFile, File, Form
    import os

    ROOM_UPLOAD_DIR = "/app/backend/uploads/rooms"
    os.makedirs(ROOM_UPLOAD_DIR, exist_ok=True)

    @router.post("/booking-widget/room-photo/{room_id}")
    async def upload_room_photo(room_id: str, file: UploadFile = File(...),
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        filename = f"{room_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(ROOM_UPLOAD_DIR, filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        photo_url = f"/api/uploads/rooms/{filename}"
        # Update room_types doc
        result = await db.room_types.update_one({"id": room_id}, {"$set": {"photo": photo_url}})
        if result.matched_count == 0:
            # Try adding to gallery
            await db.room_types.update_one({"id": room_id}, {"$push": {"gallery": photo_url}}, upsert=False)
        return {"status": "uploaded", "url": photo_url}

    @router.post("/booking-widget/room-gallery/{room_id}")
    async def upload_room_gallery_photo(room_id: str, file: UploadFile = File(...),
                                        current_user: dict = Depends(require_roles("admin", "manager"))):
        ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        filename = f"{room_id}_gallery_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(ROOM_UPLOAD_DIR, filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        photo_url = f"/api/uploads/rooms/{filename}"
        await db.room_types.update_one({"id": room_id}, {"$push": {"gallery": photo_url}})
        return {"status": "uploaded", "url": photo_url}

    # ==================== ADMIN: GUEST REVIEWS CRUD ====================

    @router.get("/booking-widget/social-proof/{property_id}")
    async def social_proof(property_id: str):
        """Public: live activity signals for conversion (real data only)."""
        now = datetime.now(timezone.utc)
        # record this view + count viewers in last 30 min (real, view-based)
        await db.widget_views.insert_one({"property_id": property_id, "ts": now.isoformat()})
        await db.widget_views.delete_many({"ts": {"$lt": (now - timedelta(hours=24)).isoformat()}})
        cutoff_30m = (now - timedelta(minutes=30)).isoformat()
        viewing_now = await db.widget_views.count_documents({"property_id": property_id, "ts": {"$gte": cutoff_30m}})

        base_q = {"property_id": property_id, "status": {"$nin": ["cancelled", "no_show"]}}
        cutoff_24h = (now - timedelta(hours=24)).isoformat()
        cutoff_7d = (now - timedelta(days=7)).isoformat()
        bookings_24h = await db.bookings.count_documents({**base_q, "created_at": {"$gte": cutoff_24h}})
        bookings_7d = await db.bookings.count_documents({**base_q, "created_at": {"$gte": cutoff_7d}})

        last_b = await db.bookings.find_one(base_q, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
        last_minutes = None
        if last_b and last_b.get("created_at"):
            try:
                dt = datetime.fromisoformat(last_b["created_at"].replace("Z", "+00:00"))
                last_minutes = max(1, int((now - dt).total_seconds() // 60))
            except Exception:
                pass

        snippet = None
        top = await db.reviews.find_one(
            {"property_id": property_id, "rating": {"$gte": 4},
             "review_text": {"$nin": ["", None]}},
            {"_id": 0, "guest_name": 1, "rating": 1, "review_text": 1},
            sort=[("review_date", -1)])
        if not top:
            top = await db.guest_reviews.find_one(
                {"property_id": property_id, "rating": {"$gte": 4},
                 "comment": {"$nin": ["", None]}},
                {"_id": 0, "guest_name": 1, "rating": 1, "comment": 1},
                sort=[("created_at", -1)])
        if top:
            text = (top.get("review_text") or top.get("comment") or "")[:110]
            snippet = {"guest_name": top.get("guest_name", "Guest"), "rating": top.get("rating"), "text": text}

        return {"property_id": property_id, "viewing_now": viewing_now,
                "bookings_24h": bookings_24h, "bookings_7d": bookings_7d,
                "last_booking_minutes_ago": last_minutes, "review_snippet": snippet}

    @router.get("/booking-widget/reviews/{property_id}")
    async def list_reviews(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.guest_reviews.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.post("/booking-widget/reviews")
    async def create_review(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        review = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "guest_name": data.get("guest_name", ""),
            "country": data.get("country", ""),
            "rating": float(data.get("rating", 0)),
            "title": data.get("title", ""),
            "comment": data.get("comment", ""),
            "date": data.get("date", now[:7].replace("-", " ")),
            "source": data.get("source", "direct"),
            "verified": True,
            "created_at": now,
        }
        await db.guest_reviews.insert_one(review)
        review.pop("_id", None)
        return review

    @router.delete("/booking-widget/reviews/{review_id}")
    async def delete_review(review_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.guest_reviews.delete_one({"id": review_id})
        return {"status": "deleted"}

    # ==================== PUBLIC: HOTEL GALLERY ====================

    @router.get("/booking-widget/gallery/{property_id}")
    async def get_gallery(property_id: str):
        rooms = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        gallery = []
        for r in rooms:
            if r.get("photo"):
                gallery.append({"url": r["photo"], "caption": r.get("name", ""), "type": "room"})
            for g in r.get("gallery", []):
                gallery.append({"url": g, "caption": r.get("name", ""), "type": "room"})
        # Add property-level gallery images
        prop_gallery = await db.property_gallery.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        for pg in prop_gallery:
            gallery.append({"url": pg.get("url", ""), "caption": pg.get("caption", ""), "type": "property"})
        if not gallery:
            gallery = [
                {"url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&q=75", "caption": "Hotel Exterior", "type": "property"},
                {"url": "https://images.unsplash.com/photo-1631048730670-ff5cd0d08f15?w=800&q=75", "caption": "Standard Room", "type": "room"},
                {"url": "https://images.unsplash.com/photo-1629140727571-9b5c6f6267b4?w=800&q=75", "caption": "Deluxe Room", "type": "room"},
                {"url": "https://images.unsplash.com/photo-1631049307305-1ceea96fb0e1?w=800&q=75", "caption": "Suite", "type": "room"},
                {"url": "https://images.unsplash.com/photo-1631048835184-3f0ceda91b75?w=800&q=75", "caption": "Executive Suite", "type": "room"},
                {"url": "https://images.pexels.com/photos/97083/pexels-photo-97083.jpeg?auto=compress&cs=tinysrgb&w=800", "caption": "Luxury Room", "type": "room"},
            ]
        return gallery

    return router
