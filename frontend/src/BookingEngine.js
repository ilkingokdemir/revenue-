import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import "@fontsource/outfit/400.css";
import "@fontsource/outfit/600.css";
import "@fontsource/outfit/700.css";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import {
  Star, MagnifyingGlass, ShieldCheck, CheckCircle, Phone, Lock, CreditCard, Buildings,
} from "@phosphor-icons/react";
import { getTemplate } from "./templates/templateConfig";
import { HeroSection } from "./templates/HeroSection";
import { RoomPreviewCards, RoomSelectionStep } from "./templates/RoomCards";
import { GuestDetailsStep } from "./templates/GuestDetailsStep";
import { ConfirmationStep } from "./templates/ConfirmationStep";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const STEPS = { SEARCH: 0, ROOMS: 1, DETAILS: 2, PAYMENT: 3, CONFIRM: 4 };

export default function BookingEngine() {
  const params = new URLSearchParams(window.location.search);
  const propertyId = params.get("property") || "aldgate-flats";
  const templateId = params.get("template") || "booking-classic";
  const baseTemplate = getTemplate(templateId);

  const [step, setStep] = useState(STEPS.SEARCH);
  const [property, setProperty] = useState(null);
  const [customSettings, setCustomSettings] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [adults, setAdults] = useState(2);
  const [children, setChildren] = useState(0);
  const [roomCount, setRoomCount] = useState(1);
  const [showGuestPicker, setShowGuestPicker] = useState(false);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState("card");
  const [guestForm, setGuestForm] = useState({ guest_name: "", guest_email: "", guest_phone: "", special_requests: "" });
  const [promoCode, setPromoCode] = useState("");
  const [promoDiscount, setPromoDiscount] = useState(null);
  const [selectedAddOns, setSelectedAddOns] = useState([]);

  // Merge template defaults with custom overrides
  const t = (() => {
    const cs = customSettings || {};
    // If the custom settings specify a different template, use that base
    const base = cs.template_id && cs.template_id !== templateId ? getTemplate(cs.template_id) : baseTemplate;
    return {
      ...base,
      colors: {
        ...base.colors,
        ...(cs.primary_color ? { primary: cs.primary_color } : {}),
        ...(cs.accent_color ? { accent: cs.accent_color, accentHover: cs.accent_color } : {}),
        ...(cs.header_bg_color ? { headerBg: cs.header_bg_color } : {}),
        ...(cs.header_text_color ? { headerText: cs.header_text_color } : {}),
        ...(cs.body_bg_color ? { bodyBg: cs.body_bg_color } : {}),
      },
      showRatingBadge: cs.show_rating_badge ?? base.showRatingBadge,
      showUrgency: cs.show_urgency ?? base.showUrgency,
      showFreeCancellation: cs.show_free_cancellation ?? base.showFreeCancellation,
      showSecurityBadges: cs.show_security_badges ?? base.showSecurityBadges,
      // Custom details (consumed by components that need them)
      custom: {
        hotelName: cs.hotel_name || "",
        tagline: cs.tagline || "",
        description: cs.description || "",
        contactPhone: cs.contact_phone || "",
        contactEmail: cs.contact_email || "",
        address: cs.address || "",
        logoUrl: cs.logo_url || "",
        heroImageUrl: cs.hero_image_url || "",
        galleryImages: cs.gallery_images || [],
        footerText: cs.footer_text || "",
        bookingButtonText: cs.booking_button_text || "",
        welcomeMessage: cs.welcome_message || "",
        socialLinks: {
          facebook: cs.facebook_url || "",
          instagram: cs.instagram_url || "",
          twitter: cs.twitter_url || "",
          tripadvisor: cs.tripadvisor_url || "",
        },
      },
    };
  })();

  useEffect(() => {
    const today = new Date();
    const d1 = new Date(today); d1.setDate(d1.getDate() + 1);
    const d2 = new Date(today); d2.setDate(d2.getDate() + 2);
    setCheckIn(d1.toISOString().split("T")[0]);
    setCheckOut(d2.toISOString().split("T")[0]);
  }, []);

  useEffect(() => {
    const load = async () => {
      try {
        const [propRes, revRes] = await Promise.all([
          axios.get(`${API}/booking/property/${propertyId}`),
          axios.get(`${API}/booking/reviews/${propertyId}?limit=6`),
        ]);
        setProperty(propRes.data);
        setReviews(revRes.data);
        if (propRes.data.template_settings && Object.keys(propRes.data.template_settings).length > 1) {
          setCustomSettings(propRes.data.template_settings);
        }
      } catch (e) { console.error("Load error:", e); }
      finally { setLoading(false); }
    };
    load();
  }, [propertyId]);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get("session_id");
    if (sessionId && urlParams.get("payment") === "success") {
      setStep(STEPS.PAYMENT);
      pollPaymentStatus(sessionId);
    } else if (urlParams.get("payment") === "cancelled") {
      setStep(STEPS.SEARCH);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pollPaymentStatus = async (sessionId, attempts = 0) => {
    if (attempts >= 10) { setStep(STEPS.CONFIRM); return; }
    try {
      const { data } = await axios.get(`${API}/payments/status/${sessionId}`);
      if (data.payment_status === "paid") {
        if (data.booking_ref) {
          const { data: bd } = await axios.get(`${API}/booking/reservation/${data.booking_ref}`);
          setConfirmation(bd);
        }
        setStep(STEPS.CONFIRM);
        window.history.replaceState({}, "", `${window.location.pathname}?property=${propertyId}&template=${templateId}`);
        return;
      }
      if (data.status === "expired") { setStep(STEPS.SEARCH); return; }
      setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), 2000);
    } catch (e) { setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), 2000); }
  };

  const searchRooms = useCallback(async () => {
    if (!checkIn || !checkOut) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/booking/rooms/${propertyId}?check_in=${checkIn}&check_out=${checkOut}&adults=${adults}&children=${children}`);
      setRooms(data);
      setStep(STEPS.ROOMS);
    } catch (e) { console.error("Search failed:", e); }
    finally { setLoading(false); }
  }, [propertyId, checkIn, checkOut, adults, children]);

  const handleSelectRoom = (room) => { setSelectedRoom(room); setStep(STEPS.DETAILS); window.scrollTo({ top: 0, behavior: "smooth" }); };

  const nights = (() => {
    if (!checkIn || !checkOut) return 1;
    return Math.max(1, Math.round((new Date(checkOut) - new Date(checkIn)) / 86400000));
  })();

  const addOnsTotal = selectedAddOns.reduce((sum, ao) => {
    if (ao.price_type === "per_night") return sum + ao.price * nights;
    if (ao.price_type === "per_person") return sum + ao.price * adults;
    if (ao.price_type === "per_person_per_night") return sum + ao.price * adults * nights;
    return sum + ao.price;
  }, 0);

  const subtotal = selectedRoom ? selectedRoom.base_price * nights * roomCount : 0;
  const discountAmount = promoDiscount ? promoDiscount.discount_amount : 0;
  const totalPrice = Math.max(0, subtotal + addOnsTotal - discountAmount);

  const applyPromo = async () => {
    if (!promoCode.trim()) return;
    try {
      const { data } = await axios.post(`${API}/promo-codes/validate?code=${promoCode}&property_id=${propertyId}&nights=${nights}&subtotal=${subtotal}`);
      setPromoDiscount(data);
    } catch (e) {
      setPromoDiscount(null);
      alert(e.response?.data?.detail || "Invalid promo code");
    }
  };

  const toggleAddOn = (addon) => {
    setSelectedAddOns(prev =>
      prev.find(a => a.id === addon.id) ? prev.filter(a => a.id !== addon.id) : [...prev, addon]
    );
  };

  const handleBooking = async () => {
    if (!guestForm.guest_name || !guestForm.guest_email) return;
    setBookingLoading(true);
    try {
      const { data } = await axios.post(`${API}/booking/reserve`, {
        property_id: propertyId, room_type_id: selectedRoom.id,
        guest_name: guestForm.guest_name, guest_email: guestForm.guest_email,
        guest_phone: guestForm.guest_phone, check_in: checkIn, check_out: checkOut,
        adults, children, rooms: roomCount, special_requests: guestForm.special_requests,
      });
      if (paymentMethod === "card") {
        const { data: pd } = await axios.post(`${API}/payments/create-checkout`, null, {
          params: { booking_id: data.id, origin_url: window.location.origin }
        });
        if (pd.url) window.location.href = pd.url;
      } else {
        setConfirmation(data);
        setStep(STEPS.CONFIRM);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    } catch (e) { alert(e.response?.data?.detail || "Booking failed."); }
    finally { setBookingLoading(false); }
  };

  const handleBookAnother = () => {
    setStep(STEPS.SEARCH);
    setSelectedRoom(null);
    setConfirmation(null);
    setGuestForm({ guest_name: "", guest_email: "", guest_phone: "", special_requests: "" });
  };

  const ratingScore = property?.avg_rating ? (property.avg_rating * 2).toFixed(1) : "8.4";
  const getRatingLabel = (r) => r >= 9 ? "Exceptional" : r >= 8 ? "Excellent" : r >= 7 ? "Very Good" : r >= 6 ? "Good" : "Pleasant";

  const searchProps = {
    checkIn, setCheckIn, checkOut, setCheckOut,
    adults, setAdults, children, setChildren,
    roomCount, setRoomCount, showGuestPicker, setShowGuestPicker,
    searchRooms,
  };

  if (loading && !property) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: t.colors.bodyBg, fontFamily: t.fonts.body }}>
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-t-transparent rounded-full animate-spin mx-auto mb-4" style={{ borderColor: t.colors.accent, borderTopColor: "transparent" }} />
          <p className="text-slate-500">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: t.colors.bodyBg, fontFamily: t.fonts.body }} data-testid="booking-engine" data-template={templateId}>

      {/* Header */}
      <header className="sticky top-0 z-50 shadow-sm" style={{ background: t.colors.headerBg, color: t.colors.headerText }} data-testid="booking-header">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {t.custom?.logoUrl ? <img src={t.custom.logoUrl} alt="" className="h-8 object-contain" /> : <Buildings size={22} weight="fill" />}
            <span className="font-semibold text-lg" style={{ fontFamily: t.fonts.heading }}>{t.custom?.hotelName || property?.name || "Hotel"}</span>
            {!t.custom?.hotelName && t.platform !== "Booking.com" && (
              <span className="text-xs opacity-60 hidden sm:inline">Powered by MyHotelBox</span>
            )}
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="hidden sm:flex items-center gap-1.5">
              <ShieldCheck size={16} weight="fill" style={{ color: t.colors.success }} />
              <span style={{ opacity: 0.7 }}>Secure Booking</span>
            </div>
            {t.custom?.contactPhone ? (
              <a href={`tel:${t.custom.contactPhone}`} className="flex items-center gap-1.5 hover:opacity-80">
                <Phone size={15} />
                <span className="hidden sm:inline" style={{ opacity: 0.7 }}>{t.custom.contactPhone}</span>
              </a>
            ) : (
              <div className="flex items-center gap-1.5">
                <Phone size={15} />
                <span className="hidden sm:inline" style={{ opacity: 0.7 }}>24/7 Support</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Step Indicator */}
      {step > STEPS.SEARCH && step < STEPS.CONFIRM && step !== STEPS.PAYMENT && (
        <div className="bg-white border-b border-gray-200" data-testid="step-indicator">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
            <div className="flex items-center gap-2 text-sm">
              {["Search", "Select Room", "Your Details"].map((label, i) => (
                <div key={label} className="flex items-center gap-2">
                  <button onClick={() => i < step && setStep(i)} className="flex items-center gap-1.5" style={{ color: i === step ? t.colors.accent : i < step ? t.colors.success : "#94a3b8", fontWeight: i === step ? 600 : 400, cursor: i < step ? "pointer" : "default" }} data-testid={`step-${i}`}>
                    {i < step ? <CheckCircle size={18} weight="fill" style={{ color: t.colors.success }} /> : (
                      <span className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold" style={{ background: i === step ? t.colors.accent : "#e2e8f0", color: i === step ? "#fff" : "#64748b" }}>{i + 1}</span>
                    )}
                    {label}
                  </button>
                  {i < 2 && <span className="text-slate-300">&rarr;</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Step 0: Landing / Search */}
      {step === STEPS.SEARCH && (
        <>
          <HeroSection t={t} property={property} ratingScore={ratingScore} getRatingLabel={getRatingLabel} searchProps={searchProps} />
          <RoomPreviewCards t={t} rooms={property?.room_types} searchRooms={searchRooms} />
          {/* Facilities */}
          {property?.facilities?.length > 0 && (
            <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12" data-testid="facilities-section">
              <h2 className="text-2xl font-semibold text-slate-900 mb-6" style={{ fontFamily: t.fonts.heading }}>Property Facilities</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                {property.facilities.map(f => (
                  <div key={f} className="flex items-center gap-2 text-sm text-slate-700 bg-white border border-gray-200 rounded-lg px-3 py-2.5" style={{ borderRadius: t.borderRadius }}>
                    <CheckCircle size={14} weight="fill" style={{ color: t.colors.success }} />
                    <span>{f}</span>
                  </div>
                ))}
              </div>
            </section>
          )}
          {/* Policies */}
          {property?.policies && (
            <section className="bg-white border-t border-gray-200 py-12" data-testid="policies-section">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <h2 className="text-2xl font-semibold text-slate-900 mb-6" style={{ fontFamily: t.fonts.heading }}>Hotel Policies</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="rounded-lg p-4" style={{ background: t.colors.bodyBg, borderRadius: t.borderRadius }}>
                    <h3 className="font-semibold text-slate-800 text-sm mb-2">Check-in / Check-out</h3>
                    <div className="text-sm text-slate-600 space-y-1">
                      <p>Check-in: {property.policies.check_in_from} — {property.policies.check_in_until}</p>
                      <p>Check-out: {property.policies.check_out_from} — {property.policies.check_out_until}</p>
                    </div>
                  </div>
                  <div className="rounded-lg p-4" style={{ background: t.colors.bodyBg, borderRadius: t.borderRadius }}>
                    <h3 className="font-semibold text-slate-800 text-sm mb-2">Cancellation</h3>
                    <p className="text-sm text-slate-600">
                      {property.policies.cancellation_text || (property.policies.cancellation_policy === "free" ? "Free cancellation" : property.policies.cancellation_policy === "moderate" ? `Free cancellation up to ${property.policies.cancellation_hours}h before check-in` : "Non-refundable")}
                    </p>
                  </div>
                  <div className="rounded-lg p-4" style={{ background: t.colors.bodyBg, borderRadius: t.borderRadius }}>
                    <h3 className="font-semibold text-slate-800 text-sm mb-2">Good to Know</h3>
                    <div className="text-sm text-slate-600 space-y-1">
                      <p>{property.policies.children_policy}</p>
                      <p>{property.policies.pet_policy}</p>
                    </div>
                  </div>
                </div>
                {property.policies.house_rules?.length > 0 && (
                  <div className="mt-6 rounded-lg p-4" style={{ background: t.colors.bodyBg, borderRadius: t.borderRadius }}>
                    <h3 className="font-semibold text-slate-800 text-sm mb-2">House Rules</h3>
                    <ul className="text-sm text-slate-600 space-y-1 list-disc list-inside">
                      {property.policies.house_rules.map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            </section>
          )}
          <ReviewsSection t={t} reviews={reviews} property={property} ratingScore={ratingScore} getRatingLabel={getRatingLabel} />
          <TrustFooter t={t} />
        </>
      )}

      {/* Step 1: Room Selection */}
      {step === STEPS.ROOMS && (
        <RoomSelectionStep t={t} rooms={rooms} loading={loading} nights={nights} adults={adults} children={children} roomCount={roomCount}
          checkIn={checkIn} checkOut={checkOut} onSelectRoom={handleSelectRoom} onChangeSearch={() => setStep(STEPS.SEARCH)} />
      )}

      {/* Step 2: Guest Details */}
      {step === STEPS.DETAILS && selectedRoom && (
        <GuestDetailsStep t={t} selectedRoom={selectedRoom} property={property} guestForm={guestForm} setGuestForm={setGuestForm}
          paymentMethod={paymentMethod} setPaymentMethod={setPaymentMethod} onBook={handleBooking} bookingLoading={bookingLoading}
          totalPrice={totalPrice} subtotal={subtotal} addOnsTotal={addOnsTotal} discountAmount={discountAmount}
          promoCode={promoCode} setPromoCode={setPromoCode} promoDiscount={promoDiscount} applyPromo={applyPromo} setPromoDiscount={setPromoDiscount}
          addOns={property?.add_ons || []} selectedAddOns={selectedAddOns} toggleAddOn={toggleAddOn}
          nights={nights} adults={adults} children={children} roomCount={roomCount} checkIn={checkIn} checkOut={checkOut} />
      )}

      {/* Step 3: Payment Processing */}
      {step === STEPS.PAYMENT && (
        <div className="max-w-lg mx-auto px-4 py-20" data-testid="payment-processing-step">
          <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-10 text-center" style={{ borderRadius: t.borderRadius }}>
            <div className="w-16 h-16 border-4 border-t-transparent rounded-full animate-spin mx-auto mb-6" style={{ borderColor: t.colors.accent, borderTopColor: "transparent" }} />
            <h2 className="text-xl font-bold text-slate-900 mb-2" style={{ fontFamily: t.fonts.heading }}>Processing Your Payment</h2>
            <p className="text-slate-500">Please wait while we confirm your payment...</p>
          </div>
        </div>
      )}

      {/* Step 4: Confirmation */}
      {step === STEPS.CONFIRM && <ConfirmationStep t={t} confirmation={confirmation} onBookAnother={handleBookAnother} />}

      {/* Mobile Sticky Search */}
      {step === STEPS.SEARCH && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg p-3 sm:hidden z-50" data-testid="mobile-sticky-bar">
          <button onClick={searchRooms} className="w-full text-white py-3.5 rounded-lg font-bold text-base flex items-center justify-center gap-2" style={{ background: t.colors.accent }}>
            <MagnifyingGlass size={18} weight="bold" /> Search Rooms
          </button>
        </div>
      )}

      {/* Footer */}
      <footer className="py-8 text-center text-sm" style={{ background: t.colors.primary, color: `${t.colors.headerText}99` }}>
        <div className="max-w-7xl mx-auto px-4">
          {t.custom?.footerText ? (
            <p className="font-medium" style={{ color: t.colors.headerText }}>{t.custom.footerText}</p>
          ) : (
            <p>Powered by <span className="font-semibold" style={{ color: t.colors.headerText }}>MyHotelBox</span> Booking Engine</p>
          )}
          {/* Social Links */}
          {t.custom?.socialLinks && Object.values(t.custom.socialLinks).some(v => v) && (
            <div className="flex items-center justify-center gap-4 mt-3">
              {t.custom.socialLinks.facebook && <a href={t.custom.socialLinks.facebook} target="_blank" rel="noopener noreferrer" className="hover:opacity-100 opacity-60 transition-opacity" data-testid="social-facebook">Facebook</a>}
              {t.custom.socialLinks.instagram && <a href={t.custom.socialLinks.instagram} target="_blank" rel="noopener noreferrer" className="hover:opacity-100 opacity-60 transition-opacity" data-testid="social-instagram">Instagram</a>}
              {t.custom.socialLinks.twitter && <a href={t.custom.socialLinks.twitter} target="_blank" rel="noopener noreferrer" className="hover:opacity-100 opacity-60 transition-opacity" data-testid="social-twitter">X / Twitter</a>}
              {t.custom.socialLinks.tripadvisor && <a href={t.custom.socialLinks.tripadvisor} target="_blank" rel="noopener noreferrer" className="hover:opacity-100 opacity-60 transition-opacity" data-testid="social-tripadvisor">TripAdvisor</a>}
            </div>
          )}
          <div className="flex items-center justify-center gap-4 mt-3 text-xs">
            <span className="flex items-center gap-1"><ShieldCheck size={12} /> SSL Secure</span>
            <span className="flex items-center gap-1"><Lock size={12} /> PCI Compliant</span>
            <span className="flex items-center gap-1"><CheckCircle size={12} /> Verified Property</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ========================= INLINE SUB-COMPONENTS ========================= */

function ReviewsSection({ t, reviews, property, ratingScore, getRatingLabel }) {
  if (!reviews || reviews.length === 0) return null;
  return (
    <section className="bg-white border-t border-gray-200 py-16" data-testid="reviews-section">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-4 mb-8">
          {t.layout === "airbnb" ? (
            <div className="flex items-center gap-2">
              <Star size={24} weight="fill" style={{ color: t.colors.accent }} />
              <span className="text-2xl font-bold text-slate-900">{ratingScore}</span>
              <span className="text-slate-400">&middot;</span>
              <span className="text-lg text-slate-700">{property?.total_reviews || reviews.length} reviews</span>
            </div>
          ) : (
            <>
              <div className="font-bold px-3 py-2 rounded-tl-lg rounded-br-lg rounded-tr-sm rounded-bl-sm text-xl" style={{ background: t.colors.ratingBg, color: t.colors.ratingText }}>{ratingScore}</div>
              <div>
                <h2 className="text-xl font-semibold text-slate-900" style={{ fontFamily: t.fonts.heading }}>{getRatingLabel(parseFloat(ratingScore))}</h2>
                <p className="text-sm text-slate-500">{property?.total_reviews || reviews.length} verified guest reviews</p>
              </div>
            </>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {reviews.map((r) => (
            <div key={r.id} className="rounded-lg p-4" style={{ background: t.colors.bodyBg, borderRadius: t.borderRadius }} data-testid={`review-card-${r.id}`}>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white" style={{ background: t.colors.ratingBg }}>
                  {r.guest_name?.charAt(0)?.toUpperCase()}
                </div>
                <div>
                  <span className="text-sm font-semibold text-slate-800">{r.guest_name}</span>
                  <div className="flex gap-0.5">
                    {[1,2,3,4,5].map((s) => <Star key={s} size={11} weight={s <= r.rating ? "fill" : "regular"} className={s <= r.rating ? "text-amber-400" : "text-slate-300"} />)}
                  </div>
                </div>
              </div>
              <p className="text-sm text-slate-600 line-clamp-3">{r.review_text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function TrustFooter({ t }) {
  if (!t.showSecurityBadges) return null;
  return (
    <section className="py-10 text-white" style={{ background: t.colors.primary }} data-testid="trust-footer">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
          {[
            { icon: ShieldCheck, label: "Secure Booking", sub: "SSL encrypted" },
            { icon: CheckCircle, label: "Free Cancellation", sub: "On most rooms" },
            { icon: CreditCard, label: "Best Price Guarantee", sub: "Direct booking discount" },
            { icon: Phone, label: "24/7 Support", sub: "We're here to help" },
          ].map(({ icon: Icon, label, sub }) => (
            <div key={label} className="flex flex-col items-center gap-2">
              <Icon size={28} weight="fill" style={{ opacity: 0.7 }} />
              <span className="font-semibold text-sm">{label}</span>
              <span className="text-xs" style={{ opacity: 0.6 }}>{sub}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
