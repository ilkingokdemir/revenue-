"""
Online Booking Widget — Public booking form for hotel websites
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

from routes.pms.widget_pricing import nightly_rates, explain_price, check_los_restrictions, stay_signals
from routes.pms.guest_email_i18n import send_guest_confirmation

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
            "direct_advantage_pct": float((wconfig or {}).get("direct_advantage_pct", 5) or 0),
            "ota_banner_enabled": (wconfig or {}).get("ota_banner_enabled", True),
            "ota_ab_enabled": (wconfig or {}).get("ota_ab_enabled", False),
            "ota_ab_variant_b_pct": float((wconfig or {}).get("ota_ab_variant_b_pct", 8) or 0),
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

        # LOS restrictions (min/max stay) — enforced before listing rooms
        los_block = await check_los_restrictions(db, property_id, check_in, check_out)
        if los_block:
            return {"available_rooms": [], "check_in": check_in, "check_out": check_out,
                    "los_discount": None, "restriction": los_block}

        # Check existing bookings for overlap
        available = []
        signals = await stay_signals(db, property_id, check_in, check_out)
        wcfg = await db.booking_widget_config.find_one({"property_id": property_id}, {"_id": 0, "direct_advantage_pct": 1, "ota_banner_enabled": 1}) or {}
        direct_pct = float(wcfg.get("direct_advantage_pct", 5) or 0)
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
                nightly = await nightly_rates(db, property_id, room, check_in, check_out)
                nights = len(nightly)
                total_rate = round(sum(n["rate"] for n in nightly), 2)
                rate = round(total_rate / nights, 2)
                explanation = explain_price(nightly)
                explanation["signals"] = signals
                ota_total = round(total_rate / (1 - direct_pct / 100), 2) if 0 < direct_pct < 100 else total_rate
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
                    "total_rate": total_rate,
                    "nights": nights,
                    "nightly": nightly,
                    "price_explanation": explanation,
                    "ota_compare": {"ota_total": ota_total, "direct_total": total_rate, "saving": round(ota_total - total_rate, 2), "pct": direct_pct},
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
        # LOS fence: aktifse ve konaklama süresi kademeyi karşılıyorsa indirim uygula
        los_applied = None
        if available:
            fence = await db.los_fences.find_one({"property_id": property_id, "active": True}, {"_id": 0})
            if fence:
                nights_calc = available[0].get("nights", 1)
                elig = [t for t in fence.get("tiers", []) if nights_calc >= int(t.get("min_nights", 0))]
                if elig:
                    best = max(elig, key=lambda t: float(t.get("discount_pct", 0)))
                    pct = float(best["discount_pct"])
                    for r in available:
                        r["total_before_los"] = r["total_rate"]
                        r["total_rate"] = round(r["total_rate"] * (1 - pct / 100), 2)
                        r["los_discount_pct"] = pct
                    los_applied = {"min_nights": int(best["min_nights"]), "discount_pct": pct,
                                   "message": f"{best['min_nights']}+ gece konaklama indirimi: −%{pct:g}"}
        return {"available_rooms": available, "check_in": check_in, "check_out": check_out,
                "los_discount": los_applied}

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
        # Server-side repricing: RMS nightly rates are the source of truth (client rate ignored)
        los_block = await check_los_restrictions(db, data["property_id"], data["check_in"], data["check_out"])
        if los_block:
            raise HTTPException(409, los_block["message_en"])
        room_doc = await db.room_types.find_one(
            {"property_id": data["property_id"], "name": data["room_type"]}, {"_id": 0})
        nightly_breakdown = []
        if room_doc:
            nightly_breakdown = await nightly_rates(db, data["property_id"], room_doc, data["check_in"], data["check_out"])
            nights = len(nightly_breakdown)
            server_rate = round(sum(n["rate"] for n in nightly_breakdown) / nights, 2)
            loyalty_pct = float(data.get("loyalty_discount_pct") or 0)
            rate = round(server_rate * (1 - max(0.0, min(loyalty_pct, 50.0)) / 100), 2)
        total = round(rate * nights * int(data.get("rooms", 1)), 2)
        package = None
        if data.get("package_id"):
            pkg = await db.event_packages.find_one({"id": data["package_id"], "property_id": data["property_id"], "enabled": {"$ne": False}}, {"_id": 0})
            if not pkg:
                raise HTTPException(400, "Selected package is no longer available")
            pkg_total = round(float(pkg.get("price_per_night") or 0) * nights * int(data.get("rooms", 1)), 2)
            package = {"id": pkg["id"], "name_en": pkg.get("name_en"), "name_tr": pkg.get("name_tr"), "name_de": pkg.get("name_de"),
                       "price_per_night": pkg.get("price_per_night"), "includes": pkg.get("includes", []), "total": pkg_total}
            total = round(total + pkg_total, 2)

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

        # ABS oda garantisi — seçilen özelliklerin TAMAMINA sahip müsait oda ata
        abs_room = None
        if abs_selected:
            sel_ids = [a["id"] for a in abs_selected]
            cand_rooms = await db.rooms.find(
                {"property_id": data["property_id"], "abs_attrs": {"$all": sel_ids}},
                {"_id": 0, "id": 1, "name": 1, "room_type_id": 1}).to_list(100)
            if cand_rooms:
                busy = set()
                async for bb in db.bookings.find(
                        {"property_id": data["property_id"],
                         "room_id": {"$in": [r["id"] for r in cand_rooms]},
                         "status": {"$nin": ["cancelled", "no_show", "checked_out"]},
                         "check_in": {"$lt": data["check_out"]},
                         "check_out": {"$gt": data["check_in"]}},
                        {"_id": 0, "room_id": 1}):
                    busy.add(bb.get("room_id"))
                free = [r for r in cand_rooms if r["id"] not in busy]
                if not free:
                    raise HTTPException(409, "Seçilen oda özelliklerine uygun müsait oda kalmadı — lütfen bir özelliği kaldırıp tekrar deneyin")
                abs_room = free[0]
            # cand_rooms boşsa oda-özellik eşlemesi yapılmamış demektir — eski davranış (ek ücret, atama yok)

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
            "nightly_rates": [{"date": n["date"], "rate": n["rate"], "source": n["source"]} for n in nightly_breakdown],
            "currency": currency,
            "status": "pending_payment" if pay_now else "confirmed",
            "payment_status": "pending" if pay_now else "pay_at_property",
            "source": "website_widget",
            "channel_source": (data.get("channel_source") or "direct")[:60],
            "guest_lang": (data.get("lang") or "")[:5],
            "ab_variant": (data.get("ab_variant") or "")[:1].upper(),
            "package": package,
            "abs_attributes": abs_selected,
            "abs_total": abs_total,
            **({"room_id": abs_room["id"], "room_number": abs_room.get("name", ""),
                "room_type_id": abs_room.get("room_type_id", ""), "abs_room_guaranteed": True} if abs_room else {}),
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

        # Confirmed (no payment) → confirmation e-mail in guest's language (Resend or MOCK)
        if not pay_now:
            email = await send_guest_confirmation(db, booking)
            return {"status": "confirmed", "booking_ref": booking_ref, "booking": booking, "email": email}

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
        from object_storage import save_upload
        await save_upload(filepath.split("/uploads/")[1], content)
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
        from object_storage import save_upload
        await save_upload(filepath.split("/uploads/")[1], content)
        photo_url = f"/api/uploads/rooms/{filename}"
        await db.room_types.update_one({"id": room_id}, {"$push": {"gallery": photo_url}})
        return {"status": "uploaded", "url": photo_url}

    # ==================== ADMIN: GUEST REVIEWS CRUD ====================

    @router.post("/booking-widget/ota-banner-view")
    async def ota_banner_view(data: Dict):
        """Public: log an OTA→direct banner impression (guest arrived from an OTA)."""
        pid = data.get("property_id", "")
        if not pid:
            raise HTTPException(400, "property_id gerekli")
        await db.ota_banner_views.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "ota": (data.get("ota") or "")[:40],
            "lang": (data.get("lang") or "")[:5], "variant": (data.get("variant") or "A")[:1].upper(),
            "pct": float(data.get("pct") or 0), "ts": datetime.now(timezone.utc).isoformat()})
        return {"ok": True}

    AB_MIN_VIEWS, AB_MIN_DIFF_PTS = 20, 2.0

    async def _ab_variants(pid: str, since: str) -> list:
        out = []
        for v in ("A", "B"):
            vviews = await db.ota_banner_views.count_documents({"property_id": pid, "variant": v, "ts": {"$gte": since}})
            vbks = await db.bookings.count_documents({"property_id": pid, "ab_variant": v, "created_at": {"$gte": since},
                                                      "channel_source": {"$regex": "^ota_banner:"}, "status": {"$nin": ["cancelled", "no_show"]}})
            out.append({"variant": v, "views": vviews, "bookings": vbks, "conversion_pct": round(vbks / vviews * 100, 1) if vviews else 0.0})
        return out

    async def run_ab_auto_winner_internal(property_id: str) -> dict:
        """Robot: lock the winning banner % when the A/B test is statistically settled (simple threshold rule)."""
        q = {"ota_ab_enabled": True}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        cfgs = await db.booking_widget_config.find(q, {"_id": 0}).to_list(50)
        since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        locked, checked = [], 0
        for c in cfgs:
            pid = c["property_id"]
            checked += 1
            vs = await _ab_variants(pid, since)
            a, b = vs[0], vs[1]
            if a["views"] < AB_MIN_VIEWS or b["views"] < AB_MIN_VIEWS or abs(a["conversion_pct"] - b["conversion_pct"]) < AB_MIN_DIFF_PTS:
                continue
            win = a if a["conversion_pct"] > b["conversion_pct"] else b
            pct_a, pct_b = float(c.get("direct_advantage_pct", 5) or 0), float(c.get("ota_ab_variant_b_pct", 8) or 0)
            win_pct = pct_a if win["variant"] == "A" else pct_b
            now = datetime.now(timezone.utc).isoformat()
            lock = {"variant": win["variant"], "pct": win_pct, "at": now, "stats": vs, "prev_a_pct": pct_a, "prev_b_pct": pct_b}
            await db.booking_widget_config.update_one({"property_id": pid}, {"$set": {
                "direct_advantage_pct": win_pct, "ota_ab_enabled": False, "ota_ab_auto_locked": lock}})
            title = f"OTA şeridi A/B kazananı sabitlendi: Varyant {win['variant']} (%{win_pct:g})"
            msg = (f"A: {a['views']} gösterim / {a['bookings']} rez. (%{a['conversion_pct']}) · B: {b['views']} / {b['bookings']} (%{b['conversion_pct']}). "
                   f"Şerit yüzdesi %{win_pct:g} olarak sabitlendi, test kapatıldı.")
            await db.notifications.insert_one({"id": str(uuid.uuid4()), "category": "revenue", "priority": "normal", "title": title,
                                               "message": msg, "property_id": pid, "read": False, "created_at": now})
            from routes.platform_ext.mailer import send_email as _mail
            admins = await db.users.find({"role": {"$in": ["admin", "manager"]}, "email": {"$nin": [None, ""]}}, {"_id": 0, "email": 1}).to_list(30)
            for u in admins:
                await _mail(db, u["email"], title, f"<div style='font-family:sans-serif'><h3>{title}</h3><p>{msg}</p></div>", kind="ab_auto_winner", meta={"property_id": pid})
            locked.append({"property_id": pid, **lock, "emails": len(admins)})
        return {"ok": True, "checked": checked, "locked": locked}

    router.run_ab_auto_winner_internal = run_ab_auto_winner_internal

    @router.post("/booking-widget/ab-auto-winner/run/{property_id}")
    async def ab_auto_winner_run(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_ab_auto_winner_internal(property_id)

    @router.get("/booking-widget/ota-conversion/{property_id}")
    async def ota_conversion(property_id: str, days: int = 90,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))).isoformat()
        q_views = {"ts": {"$gte": since}}
        q_book = {"channel_source": {"$regex": "^ota_banner:"}, "created_at": {"$gte": since},
                  "status": {"$nin": ["cancelled", "no_show"]}}
        if property_id != "all":
            q_views["property_id"] = property_id
            q_book["property_id"] = property_id
        views = await db.ota_banner_views.count_documents(q_views)
        bks = await db.bookings.find(q_book, {"_id": 0, "total": 1, "channel_source": 1, "created_at": 1}).to_list(2000)
        revenue = round(sum(float(b.get("total") or 0) for b in bks), 2)
        wcfg = await db.booking_widget_config.find_one({"property_id": property_id}, {"_id": 0, "direct_advantage_pct": 1, "ota_ab_enabled": 1, "ota_ab_variant_b_pct": 1, "ota_ab_auto_locked": 1}) or {}
        if property_id == "all" and not wcfg.get("ota_ab_enabled"):
            # fleet view: reflect any property that has the A/B test switched on
            any_ab = await db.booking_widget_config.find_one({"ota_ab_enabled": True}, {"_id": 0, "direct_advantage_pct": 1, "ota_ab_enabled": 1, "ota_ab_variant_b_pct": 1})
            if any_ab:
                wcfg = {**any_ab, **wcfg, "ota_ab_enabled": True}
        direct_pct = float(wcfg.get("direct_advantage_pct", 5) or 0)
        # commission saved: what an OTA (≈15%) would have taken on the OTA-equivalent price
        ota_equiv = revenue / (1 - direct_pct / 100) if 0 < direct_pct < 100 else revenue
        commission_saved = round(ota_equiv * 0.15, 2)
        by_ota: dict = {}
        for b in bks:
            k = (b.get("channel_source") or "").split(":", 1)[-1] or "ota"
            by_ota[k] = by_ota.get(k, 0) + 1
        ab = []
        for v in ("A", "B"):
            vq = {**q_views, "variant": v}
            vviews = await db.ota_banner_views.count_documents(vq)
            vbks = await db.bookings.count_documents({**q_book, "ab_variant": v})
            ab.append({"variant": v, "views": vviews, "bookings": vbks,
                       "conversion_pct": round(vbks / vviews * 100, 1) if vviews else 0.0})
        winner = None
        if all(x["views"] >= 20 for x in ab) and ab[0]["conversion_pct"] != ab[1]["conversion_pct"]:
            winner = max(ab, key=lambda x: x["conversion_pct"])["variant"]
        return {"property_id": property_id, "days": days, "banner_views": views, "bookings": len(bks),
                "conversion_pct": round(len(bks) / views * 100, 1) if views else 0.0,
                "revenue": revenue, "commission_saved": commission_saved, "direct_advantage_pct": direct_pct,
                "by_ota": [{"ota": k, "bookings": v} for k, v in sorted(by_ota.items(), key=lambda x: -x[1])],
                "ab": {"enabled": bool(wcfg.get("ota_ab_enabled", False)), "variant_b_pct": float(wcfg.get("ota_ab_variant_b_pct", 8) or 0),
                       "variants": ab, "winner": winner, "min_views_for_winner": AB_MIN_VIEWS, "min_diff_pts": AB_MIN_DIFF_PTS,
                       "auto_locked": wcfg.get("ota_ab_auto_locked")}}

    @router.get("/booking-widget/upcoming-events/{property_id}")
    async def upcoming_events(property_id: str, days: int = 90, limit: int = 4):
        """Public: strongest upcoming city events (market_events) for the widget 'book early' strip."""
        today = datetime.now(timezone.utc).date()
        last = (today + timedelta(days=max(7, min(days, 365)))).isoformat()
        evs = await db.market_events.find(
            {"property_id": {"$in": [property_id, "all"]}, "end_date": {"$gte": today.isoformat()}, "date": {"$lte": last},
             "hotel_demand_score": {"$gte": 60}},
            {"_id": 0, "name": 1, "date": 1, "end_date": 1, "category": 1, "hotel_demand_score": 1}).sort("hotel_demand_score", -1).to_list(40)
        from routes.pms.widget_pricing import _event_kind
        out, kept = [], []
        for e in evs:
            d0, d1 = e["date"], e.get("end_date") or e["date"]
            icon, en, tr, de = _event_kind(e.get("category", ""))
            if any(k[0] == icon and k[1] <= d1 and k[2] >= d0 for k in kept):
                continue  # same kind, overlapping dates → duplicate listing
            kept.append((icon, d0, d1))
            ci = e["date"]
            end_d = datetime.strptime(e.get("end_date") or e["date"], "%Y-%m-%d").date()
            co = max(end_d + timedelta(days=1), datetime.strptime(ci, "%Y-%m-%d").date() + timedelta(days=2)).isoformat()
            out.append({"name": e.get("name", "")[:90], "date": e["date"], "end_date": e.get("end_date") or e["date"],
                        "icon": icon, "label_en": en, "label_tr": tr, "label_de": de, "score": e.get("hotel_demand_score", 0),
                        "suggest_check_in": ci, "suggest_check_out": co})
            if len(out) >= max(1, min(limit, 8)):
                break
        out.sort(key=lambda x: x["date"])
        return {"property_id": property_id, "events": out}

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
