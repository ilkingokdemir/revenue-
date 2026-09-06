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
import { LanguageProvider, useLanguage } from "./i18n/LanguageContext";
import { LanguageSelector } from "./i18n/LanguageSelector";
import { SmartUpsellEngine } from "./templates/SmartUpsellEngine";
import { PriceComparisonWidget } from "./templates/PriceComparisonWidget";
import { SocialProofNotifications } from "./templates/SocialProofNotifications";
import { GoogleHotelStructuredData } from "./templates/GoogleHotelStructuredData";
import { SEOMetaTags } from "./templates/SEOMetaTags";
import { useCurrency, CurrencySelector } from "./i18n/CurrencySelector";
import { GroupBookingModal } from "./templates/GroupBookingModal";
import { AIConciergeChat } from "./templates/AIConciergeChat";
import { SpaceBookingSection } from "./templates/SpaceBookingSection";
import { CartBar } from "./templates/CartBar";
import { planNightPrice, roomNightBase } from "./templates/RatePlanRows";
import { GiftCardSection } from "./templates/GiftCardSection";
import { ExitIntentPopup, CookieBanner } from "./templates/ExitIntentPopup";
import { InlinePayment } from "./templates/InlinePayment";
import { useAnalytics, trackEvent } from "./site/analytics";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const STEPS = { SEARCH: 0, ROOMS: 1, DETAILS: 2, PAYMENT: 3, CONFIRM: 4 };

function BookingEngineInner() {
  const { t, isRTL } = useLanguage();
  const { currency, setCurrency, format: formatPrice, currencies, symbol: currSymbol } = useCurrency();
  const params = new URLSearchParams(window.location.search);
  const propertyId = params.get("property") || "aldgate-flats";
  const templateId = params.get("template") || "booking-classic";
  const baseTemplate = getTemplate(templateId);

  const [step, setStep] = useState(STEPS.SEARCH);
  const [property, setProperty] = useState(null);
  const [customSettings, setCustomSettings] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [ratePlans, setRatePlans] = useState([]);
  const [cart, setCart] = useState([]);
  const [flexData, setFlexData] = useState(null);
  useAnalytics(propertyId);
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
  const [dwConfig, setDwConfig] = useState(null);
  const [damageWaiver, setDamageWaiver] = useState(false);
  const [promoDiscount, setPromoDiscount] = useState(null);
  const [selectedAddOns, setSelectedAddOns] = useState([]);
  const [selectedUpsells, setSelectedUpsells] = useState([]);
  const [showGroupBooking, setShowGroupBooking] = useState(false);
  const [cartSaved, setCartSaved] = useState(false);
  const [giftCode, setGiftCode] = useState("");
  const [giftCard, setGiftCard] = useState(null);
  const [pendingPromo, setPendingPromo] = useState("");
  const [member, setMember] = useState(null);
  const [childAges, setChildAges] = useState([]);
  const [inlineBooking, setInlineBooking] = useState(null);
  const [inlineEnabled, setInlineEnabled] = useState(false);
  useEffect(() => { axios.get(`${API}/payments/config`).then(({ data }) => setInlineEnabled(!!data.inline_enabled)).catch(() => {}); }, []);
  useEffect(() => { const c = params.get("promo"); if (c) setPendingPromo(c.toUpperCase()); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const memberPct = member?.discount_pct || 0;
  const checkMember = async (email) => {
    try { const { data } = await axios.post(`${API}/booking/member-rate`, { email }); setMember(data.member ? { ...data, email } : { member: false, email }); if (!data.member) alert(t("member.notFound")); }
    catch { /* ignore */ }
  };
  const utmSource = (() => { const s = params.get("utm_source") || ""; return ["google_hotel_ads", "embed", "website", "metasearch"].includes(s) ? s : "booking_engine"; })();

  // Merge template defaults with custom overrides
  const tmpl = (() => {
    const cs = customSettings || {};
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
    const p = new URLSearchParams(window.location.search);
    const today = new Date();
    const d1 = new Date(today); d1.setDate(d1.getDate() + 1);
    const d2 = new Date(today); d2.setDate(d2.getDate() + 2);
    const ci = p.get("check_in"), co = p.get("check_out");
    const valid = ci && co && /^\d{4}-\d{2}-\d{2}$/.test(ci) && co > ci;
    setCheckIn(valid ? ci : d1.toISOString().split("T")[0]);
    setCheckOut(valid ? co : d2.toISOString().split("T")[0]);
    if (p.get("adults")) setAdults(Math.max(1, Math.min(10, Number(p.get("adults")) || 2)));
  }, []);

  const [autoSearched, setAutoSearched] = useState(false);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (!autoSearched && property && p.get("check_in") && checkIn && checkOut && checkIn === p.get("check_in")) {
      setAutoSearched(true);
      searchRooms(checkIn, checkOut);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [property, checkIn, checkOut]);

  useEffect(() => {
    const load = async () => {
      try {
        const [propRes, revRes] = await Promise.all([
          axios.get(`${API}/booking/property/${propertyId}`),
          axios.get(`${API}/booking/reviews/${propertyId}?limit=6`),
        ]);
        setProperty(propRes.data);
        setReviews(revRes.data);
        axios.get(`${API}/booking/damage-waiver/${propertyId}`)
          .then(r => setDwConfig(r.data?.enabled ? r.data : null))
          .catch(() => {});
        axios.get(`${API}/booking/rate-plans/${propertyId}`)
          .then(r => setRatePlans(Array.isArray(r.data) ? r.data : []))
          .catch(() => {});
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

  const searchRooms = useCallback(async (ci = checkIn, co = checkOut) => {
    if (!ci || !co) return;
    setLoading(true);
    setCart([]);
    try {
      const { data } = await axios.get(`${API}/booking/rooms/${propertyId}?check_in=${ci}&check_out=${co}&adults=${adults}&children=${children}`);
      setRooms(data);
      setStep(STEPS.ROOMS);
      axios.get(`${API}/booking/flex-dates/${propertyId}?check_in=${ci}&check_out=${co}&adults=${adults}`)
        .then(r => setFlexData(r.data)).catch(() => setFlexData(null));
    } catch (e) { console.error("Search failed:", e); }
    finally { setLoading(false); }
  }, [propertyId, checkIn, checkOut, adults, children]);

  const applyFlexDates = (ci, co) => { setCheckIn(ci); setCheckOut(co); searchRooms(ci, co); window.scrollTo({ top: 0, behavior: "smooth" }); };

  const addToCart = (room, plan, qty = 1, extraBeds = 0) => {
    setCart(prev => {
      const key = (c) => `${c.room.id}|${c.plan?.id || ""}`;
      const k = `${room.id}|${plan?.id || ""}`;
      const existing = prev.find(c => key(c) === k);
      if (existing) return prev.map(c => key(c) === k ? { ...c, qty, extraBeds } : c);
      return [...prev, { room, plan, qty, extraBeds }];
    });
  };
  const removeFromCart = (i) => setCart(prev => prev.filter((_, idx) => idx !== i));
  const continueToDetails = () => { if (!cart.length) return; setSelectedRoom(cart[0].room); setStep(STEPS.DETAILS); trackEvent("begin_checkout", { items: cart.length }); window.scrollTo({ top: 0, behavior: "smooth" }); };

  const nights = (() => {
    if (!checkIn || !checkOut) return 1;
    return Math.max(1, Math.round((new Date(checkOut) - new Date(checkIn)) / 86400000));
  })();

  const cartRooms = cart.reduce((s, c) => s + c.qty, 0) || roomCount;

  const addOnsTotal = selectedAddOns.reduce((sum, ao) => {
    if (ao.price_type === "per_night") return sum + ao.price * nights;
    if (ao.price_type === "per_person") return sum + ao.price * adults;
    if (ao.price_type === "per_person_per_night") return sum + ao.price * adults * nights;
    return sum + ao.price;
  }, 0);

  const upsellsTotal = selectedUpsells.reduce((sum, u) => {
    if (u.price_type === "per_night") return sum + u.price * nights;
    if (u.price_type === "per_person") return sum + u.price * adults;
    if (u.price_type === "per_person_per_night") return sum + u.price * adults * nights;
    return sum + u.price;
  }, 0);

  const subtotal = cart.length ? cart.reduce((s, c) => s + planNightPrice(roomNightBase(c.room), c.plan) * (1 - memberPct / 100) * nights * c.qty + (Number(c.room.extra_bed_price) || 0) * nights * (c.extraBeds || 0), 0) : (selectedRoom ? roomNightBase(selectedRoom) * nights * roomCount : 0);
  const taxRoom = cart[0]?.room || selectedRoom || {};
  const cityTax = (Number(taxRoom.city_tax_per_night) || 0) * nights * (cart.reduce((s, c) => s + c.qty, 0) || roomCount);
  const vatRate = Number(taxRoom.vat_rate) || 0;
  const childExtra = (() => { const cp = taxRoom.child_policy || {}; return childAges.slice(0, children).reduce((sum, a) => sum + (a < (cp.free_under_age || 0) ? 0 : (Number(cp.child_price_per_night) || 0) * nights), 0); })();
  const discountAmount = promoDiscount ? promoDiscount.discount_amount : 0;
  const waiverTotal = damageWaiver && dwConfig ? dwConfig.fee_per_night * nights * cartRooms : 0;
  const totalBeforeGift = Math.max(0, subtotal + addOnsTotal + upsellsTotal + waiverTotal + cityTax + childExtra - discountAmount);
  const giftApplied = giftCard ? Math.min(giftCard.balance, totalBeforeGift) : 0;
  const totalPrice = Math.max(0, totalBeforeGift - giftApplied);
  const depositDue = cart.length ? Math.round(cart.reduce((s, c) => s + planNightPrice(roomNightBase(c.room), c.plan) * (1 - memberPct / 100) * nights * c.qty * ((c.plan?.deposit_pct || 0) / 100), 0) * 100) / 100 : 0;

  const applyGift = async () => {
    if (!giftCode.trim()) return;
    try {
      const { data } = await axios.post(`${API}/booking/gift-cards/check`, { code: giftCode.trim(), property_id: propertyId });
      setGiftCard(data);
    } catch (e) { setGiftCard(null); alert(e.response?.data?.detail || "Invalid gift card"); }
  };

  useEffect(() => {
    if (step === STEPS.DETAILS && pendingPromo && subtotal > 0) {
      const code = pendingPromo; setPendingPromo("");
      axios.post(`${API}/promo-codes/validate?code=${code}&property_id=${propertyId}&nights=${nights}&subtotal=${subtotal}`)
        .then(({ data }) => { setPromoCode(code); setPromoDiscount(data); }).catch(() => {});
    }
  }, [step, pendingPromo, subtotal, propertyId, nights]);

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

  const toggleUpsell = (upsell) => {
    setSelectedUpsells(prev =>
      prev.find(u => u.id === upsell.id) ? prev.filter(u => u.id !== upsell.id) : [...prev, upsell]
    );
  };

  // Cart abandonment: save when user has email but navigates away
  useEffect(() => {
    const saveCart = () => {
      if (step === STEPS.DETAILS && guestForm.guest_email && selectedRoom && !cartSaved) {
        navigator.sendBeacon(`${API}/cart/save?property_id=${propertyId}&room_type_id=${selectedRoom.id}&room_name=${encodeURIComponent(selectedRoom.name)}&guest_email=${encodeURIComponent(guestForm.guest_email)}&guest_name=${encodeURIComponent(guestForm.guest_name)}&check_in=${checkIn}&check_out=${checkOut}&adults=${adults}&total_price=${totalPrice}`);
        setCartSaved(true);
      }
    };
    window.addEventListener("beforeunload", saveCart);
    return () => window.removeEventListener("beforeunload", saveCart);
  }, [step, guestForm.guest_email, guestForm.guest_name, selectedRoom, cartSaved, propertyId, checkIn, checkOut, adults, totalPrice]);

  const handleBooking = async () => {
    if (!guestForm.guest_name || !guestForm.guest_email) return;
    setBookingLoading(true);
    try {
      const payload = {
        property_id: propertyId,
        guest_name: guestForm.guest_name, guest_email: guestForm.guest_email,
        guest_phone: guestForm.guest_phone, check_in: checkIn, check_out: checkOut,
        adults, children, special_requests: guestForm.special_requests,
        damage_waiver: damageWaiver && !!dwConfig,
        promo_code: promoDiscount?.code || "",
        gift_card_code: giftCard?.code || "",
        source: utmSource,
        loyalty_email: member?.member ? member.email : "",
        items: (cart.length ? cart : [{ room: selectedRoom, plan: null, qty: roomCount }]).map((c, i) => ({ room_type_id: c.room.id, rate_plan_id: c.plan?.id || "", qty: c.qty, extra_beds: c.extraBeds || 0, children_ages: i === 0 ? childAges.slice(0, children) : [] })),
      };
      const { data } = await axios.post(`${API}/booking/reserve-multi`, payload);
      trackEvent("purchase", { transaction_id: data.booking_ref, value: data.total_price, currency: data.currency || "GBP", items: payload.items.length });
      if (totalPrice <= 0 && paymentMethod !== "hotel") {
        setConfirmation(data); setStep(STEPS.CONFIRM); window.scrollTo({ top: 0, behavior: "smooth" }); return;
      }
      if ((paymentMethod === "card" || paymentMethod === "deposit") && inlineEnabled) {
        setInlineBooking({ ...data, amountMode: paymentMethod === "deposit" ? "deposit" : "full" });
        setStep(STEPS.PAYMENT); window.scrollTo({ top: 0, behavior: "smooth" }); return;
      }
      if (paymentMethod === "card" || paymentMethod === "deposit") {
        const { data: pd } = await axios.post(`${API}/payments/booking-checkout`, {
          booking_id: data.id, origin_url: window.location.origin, amount_mode: paymentMethod === "deposit" ? "deposit" : "full"
        });
        if (pd.url) window.location.href = pd.url;
      } else if (paymentMethod === "iyzico") {
        const { data: pd } = await axios.post(`${API}/payments/iyzico-checkout`, {
          booking_id: data.id, origin_url: window.location.origin, currency: "TRY", installments: 12
        });
        if (pd.url) window.location.href = pd.url;
      } else if (paymentMethod === "paytr") {
        const { data: pd } = await axios.post(`${API}/payments/paytr-checkout`, {
          booking_id: data.id, origin_url: window.location.origin, currency: "TRY", installments: 12
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
    setCart([]);
    setGiftCard(null); setGiftCode("");
    setConfirmation(null);
    setGuestForm({ guest_name: "", guest_email: "", guest_phone: "", special_requests: "" });
  };

  const ratingScore = property?.avg_rating ? (property.avg_rating * 2).toFixed(1) : "8.4";
  const getRatingLabel = (r) => r >= 9 ? "Exceptional" : r >= 8 ? "Excellent" : r >= 7 ? "Very Good" : r >= 6 ? "Good" : "Pleasant";

  const searchProps = {
    checkIn, setCheckIn, checkOut, setCheckOut,
    adults, setAdults, children, setChildren,
    roomCount, setRoomCount, showGuestPicker, setShowGuestPicker,
    searchRooms: () => searchRooms(), propertyId, childAges, setChildAges,
  };

  if (loading && !property) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: tmpl.colors.bodyBg, fontFamily: tmpl.fonts.body }}>
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-t-transparent rounded-full animate-spin mx-auto mb-4" style={{ borderColor: tmpl.colors.accent, borderTopColor: "transparent" }} />
          <p className="text-slate-500">{t("loading")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" dir={isRTL ? "rtl" : "ltr"} style={{ background: tmpl.colors.bodyBg, fontFamily: tmpl.fonts.body }} data-testid="booking-engine" data-template={templateId}>
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:bg-white focus:px-3 focus:py-2 focus:rounded-lg focus:shadow-lg text-sm font-semibold">{t("a11y.skip")}</a>

      {/* Google Hotel Structured Data (SEO) */}
      <GoogleHotelStructuredData property={property} rooms={rooms.length > 0 ? rooms : property?.room_types} reviews={reviews} templateSettings={customSettings} />
      <SEOMetaTags property={property} templateSettings={customSettings} rooms={rooms.length > 0 ? rooms : property?.room_types} />

      {/* Social Proof Floating Notifications */}
      <SocialProofNotifications
        settings={property?.social_proof?.settings}
        recentBookings={property?.social_proof?.recent_bookings_24h || 0}
        roomsData={rooms}
      />

      {/* Header */}
      <header className="sticky top-0 z-50 shadow-sm" style={{ background: tmpl.colors.headerBg, color: tmpl.colors.headerText }} data-testid="booking-header">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {tmpl.custom?.logoUrl ? <img src={tmpl.custom.logoUrl} alt="" className="h-8 object-contain" /> : <Buildings size={22} weight="fill" />}
            <span className="font-semibold text-lg" style={{ fontFamily: tmpl.fonts.heading }}>{tmpl.custom?.hotelName || property?.name || "Hotel"}</span>
            {!tmpl.custom?.hotelName && tmpl.platform !== "Booking.com" && (
              <span className="text-xs opacity-60 hidden sm:inline">{t("header.poweredBy")}</span>
            )}
          </div>
          <div className="flex items-center gap-3 text-sm">
            <div className="hidden sm:flex items-center gap-1.5">
              <ShieldCheck size={16} weight="fill" style={{ color: tmpl.colors.success }} />
              <span style={{ opacity: 0.7 }}>{t("header.secureBooking")}</span>
            </div>
            {tmpl.custom?.contactPhone ? (
              <a href={`tel:${tmpl.custom.contactPhone}`} className="flex items-center gap-1.5 hover:opacity-80">
                <Phone size={15} />
                <span className="hidden sm:inline" style={{ opacity: 0.7 }}>{tmpl.custom.contactPhone}</span>
              </a>
            ) : (
              <div className="flex items-center gap-1.5">
                <Phone size={15} />
                <span className="hidden sm:inline" style={{ opacity: 0.7 }}>{t("header.support")}</span>
              </div>
            )}
            <LanguageSelector variant="minimal" />
            <CurrencySelector currency={currency} setCurrency={setCurrency} currencies={currencies} />
          </div>
        </div>
      </header>

      {/* Step Indicator */}
      {step > STEPS.SEARCH && step < STEPS.CONFIRM && step !== STEPS.PAYMENT && (
        <div className="bg-white border-b border-gray-200" data-testid="step-indicator">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
            <div className="flex items-center gap-2 text-sm">
              {[t("step.search"), t("step.selectRoom"), t("step.yourDetails")].map((label, i) => (
                <div key={i} className="flex items-center gap-2">
                  <button onClick={() => i < step && setStep(i)} className="flex items-center gap-1.5" style={{ color: i === step ? tmpl.colors.accent : i < step ? tmpl.colors.success : "#94a3b8", fontWeight: i === step ? 600 : 400, cursor: i < step ? "pointer" : "default" }} data-testid={`step-${i}`}>
                    {i < step ? <CheckCircle size={18} weight="fill" style={{ color: tmpl.colors.success }} /> : (
                      <span className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold" style={{ background: i === step ? tmpl.colors.accent : "#e2e8f0", color: i === step ? "#fff" : "#64748b" }}>{i + 1}</span>
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

      <main id="main-content">
      {/* Step 0: Landing / Search */}
      {step === STEPS.SEARCH && (
        <>
          <HeroSection t={tmpl} property={property} ratingScore={ratingScore} getRatingLabel={getRatingLabel} searchProps={searchProps} />
          <RoomPreviewCards t={tmpl} rooms={property?.room_types} searchRooms={() => searchRooms()} />
          {/* Facilities */}
          {property?.facilities?.length > 0 && (
            <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12" data-testid="facilities-section">
              <h2 className="text-2xl font-semibold text-slate-900 mb-6" style={{ fontFamily: tmpl.fonts.heading }}>{t("facilities.title")}</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                {property.facilities.map(f => (
                  <div key={f} className="flex items-center gap-2 text-sm text-slate-700 bg-white border border-gray-200 rounded-lg px-3 py-2.5" style={{ borderRadius: tmpl.borderRadius }}>
                    <CheckCircle size={14} weight="fill" style={{ color: tmpl.colors.success }} />
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
                <h2 className="text-2xl font-semibold text-slate-900 mb-6" style={{ fontFamily: tmpl.fonts.heading }}>{t("policies.title")}</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="rounded-lg p-4" style={{ background: tmpl.colors.bodyBg, borderRadius: tmpl.borderRadius }}>
                    <h3 className="font-semibold text-slate-800 text-sm mb-2">{t("policies.checkInOut")}</h3>
                    <div className="text-sm text-slate-600 space-y-1">
                      <p>{t("policies.checkIn")}: {property.policies.check_in_from} — {property.policies.check_in_until}</p>
                      <p>{t("policies.checkOut")}: {property.policies.check_out_from} — {property.policies.check_out_until}</p>
                    </div>
                  </div>
                  <div className="rounded-lg p-4" style={{ background: tmpl.colors.bodyBg, borderRadius: tmpl.borderRadius }}>
                    <h3 className="font-semibold text-slate-800 text-sm mb-2">{t("policies.cancellation")}</h3>
                    <p className="text-sm text-slate-600">
                      {property.policies.cancellation_text || (property.policies.cancellation_policy === "free" ? t("policies.freeCancellation") : property.policies.cancellation_policy === "moderate" ? t("policies.moderateCancellation", { hours: property.policies.cancellation_hours }) : t("policies.nonRefundable"))}
                    </p>
                  </div>
                  <div className="rounded-lg p-4" style={{ background: tmpl.colors.bodyBg, borderRadius: tmpl.borderRadius }}>
                    <h3 className="font-semibold text-slate-800 text-sm mb-2">{t("policies.goodToKnow")}</h3>
                    <div className="text-sm text-slate-600 space-y-1">
                      <p>{property.policies.children_policy}</p>
                      <p>{property.policies.pet_policy}</p>
                    </div>
                  </div>
                </div>
                {property.policies.house_rules?.length > 0 && (
                  <div className="mt-6 rounded-lg p-4" style={{ background: tmpl.colors.bodyBg, borderRadius: tmpl.borderRadius }}>
                    <h3 className="font-semibold text-slate-800 text-sm mb-2">{t("policies.houseRules")}</h3>
                    <ul className="text-sm text-slate-600 space-y-1 list-disc list-inside">
                      {property.policies.house_rules.map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            </section>
          )}
          {/* Group Booking CTA */}
          <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="group-booking-cta">
            <div className="bg-gradient-to-r from-slate-800 to-slate-900 rounded-2xl p-6 sm:p-8 flex flex-col sm:flex-row items-center justify-between gap-4" style={{ borderRadius: tmpl.borderRadius }}>
              <div className="text-white text-center sm:text-left">
                <h3 className="text-lg font-bold mb-1">Planning a Group Stay?</h3>
                <p className="text-sm opacity-70">Corporate events, weddings, conferences — get a custom quote for 5+ rooms</p>
              </div>
              <button onClick={() => setShowGroupBooking(true)}
                className="px-6 py-3 rounded-xl font-semibold text-sm whitespace-nowrap transition-transform hover:scale-105"
                style={{ background: tmpl.colors.accent, color: "#fff", borderRadius: tmpl.borderRadius }}
                data-testid="group-booking-btn">
                Request Group Quote
              </button>
            </div>
          </section>
          <ReviewsSection t={tmpl} reviews={reviews} property={property} ratingScore={ratingScore} getRatingLabel={getRatingLabel} />
          {/* Hourly/Space Bookings */}
          <SpaceBookingSection propertyId={propertyId} tmpl={tmpl} />
          <GiftCardSection t={tmpl} propertyId={propertyId} />
          <TrustFooter t={tmpl} />
        </>
      )}

      {/* Step 1: Room Selection */}
      {step === STEPS.ROOMS && (
        <>
          <RoomSelectionStep t={tmpl} rooms={rooms} loading={loading} nights={nights} adults={adults} children={children} roomCount={roomCount}
            checkIn={checkIn} checkOut={checkOut} onSelectRoom={addToCart} onChangeSearch={() => setStep(STEPS.SEARCH)}
            ratePlans={ratePlans} cart={cart} flexData={flexData} onApplyDates={applyFlexDates} fmt={formatPrice} memberPct={memberPct} onMemberCheck={checkMember} />
          <CartBar t={tmpl} cart={cart} nights={nights} onRemove={removeFromCart} onContinue={continueToDetails} fmt={formatPrice} memberPct={memberPct} />
          {cart.length > 0 && <div className="h-28" />}
        </>
      )}

      {/* Step 2: Guest Details */}
      {step === STEPS.DETAILS && selectedRoom && (
        <GuestDetailsStep t={tmpl} selectedRoom={selectedRoom} property={property} guestForm={guestForm} setGuestForm={setGuestForm}
          paymentMethod={paymentMethod} setPaymentMethod={setPaymentMethod} onBook={handleBooking} bookingLoading={bookingLoading}
          totalPrice={totalPrice} subtotal={subtotal} addOnsTotal={addOnsTotal + upsellsTotal} discountAmount={discountAmount}
          promoCode={promoCode} setPromoCode={setPromoCode} promoDiscount={promoDiscount} applyPromo={applyPromo} setPromoDiscount={setPromoDiscount}
          addOns={property?.add_ons || []} selectedAddOns={selectedAddOns} toggleAddOn={toggleAddOn}
          upsells={property?.upsells || []} selectedUpsells={selectedUpsells} toggleUpsell={toggleUpsell}
          nights={nights} adults={adults} children={children} roomCount={cartRooms} checkIn={checkIn} checkOut={checkOut}
          dwConfig={dwConfig} damageWaiver={damageWaiver} setDamageWaiver={setDamageWaiver} waiverTotal={waiverTotal}
          socialProofSettings={property?.social_proof?.settings} cart={cart} onBackToRooms={() => setStep(STEPS.ROOMS)}
          giftCode={giftCode} setGiftCode={setGiftCode} giftCard={giftCard} applyGift={applyGift} clearGift={() => { setGiftCard(null); setGiftCode(""); }} giftApplied={giftApplied}
          depositDue={depositDue} fmt={formatPrice} memberPct={memberPct} cityTax={cityTax} vatRate={vatRate} childExtra={childExtra} />
      )}

      {/* Step 3: Payment Processing */}
      {step === STEPS.PAYMENT && inlineBooking && (
        <InlinePayment t={tmpl} booking={inlineBooking} amountMode={inlineBooking.amountMode} fmt={formatPrice}
          onPaid={() => { setConfirmation({ ...inlineBooking, payment_status: "paid" }); setInlineBooking(null); setStep(STEPS.CONFIRM); window.scrollTo({ top: 0, behavior: "smooth" }); }}
          onFallback={async () => { try { const { data: pd } = await axios.post(`${API}/payments/booking-checkout`, { booking_id: inlineBooking.id, origin_url: window.location.origin, amount_mode: inlineBooking.amountMode }); if (pd.url) window.location.href = pd.url; } catch { /* ignore */ } }} />
      )}
      {step === STEPS.PAYMENT && !inlineBooking && (
        <div className="max-w-lg mx-auto px-4 py-20" data-testid="payment-processing-step">
          <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-10 text-center" style={{ borderRadius: tmpl.borderRadius }}>
            <div className="w-16 h-16 border-4 border-t-transparent rounded-full animate-spin mx-auto mb-6" style={{ borderColor: tmpl.colors.accent, borderTopColor: "transparent" }} />
            <h2 className="text-xl font-bold text-slate-900 mb-2" style={{ fontFamily: tmpl.fonts.heading }}>{t("processing.title")}</h2>
            <p className="text-slate-500">{t("processing.wait")}</p>
          </div>
        </div>
      )}

      {/* Step 4: Confirmation */}
      {step === STEPS.CONFIRM && <ConfirmationStep t={tmpl} confirmation={confirmation} onBookAnother={handleBookAnother} fmt={formatPrice} />}
      </main>

      {/* Mobile Sticky Search */}
      {step === STEPS.SEARCH && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg p-3 sm:hidden z-50" data-testid="mobile-sticky-bar">
          <button onClick={() => searchRooms()} className="w-full text-white py-3.5 rounded-lg font-bold text-base flex items-center justify-center gap-2" style={{ background: tmpl.colors.accent }}>
            <MagnifyingGlass size={18} weight="bold" /> {t("search.searchRooms")}
          </button>
        </div>
      )}

      {/* Footer */}
      <footer className="py-8 text-center text-sm" style={{ background: tmpl.colors.primary, color: `${tmpl.colors.headerText}99` }}>
        <div className="max-w-7xl mx-auto px-4">
          {tmpl.custom?.footerText ? (
            <p className="font-medium" style={{ color: tmpl.colors.headerText }}>{tmpl.custom.footerText}</p>
          ) : (
            <p>{t("footer.poweredBy", { name: "MyHotelBox" })}</p>
          )}
          {tmpl.custom?.socialLinks && Object.values(tmpl.custom.socialLinks).some(v => v) && (
            <div className="flex items-center justify-center gap-4 mt-3">
              {tmpl.custom.socialLinks.facebook && <a href={tmpl.custom.socialLinks.facebook} target="_blank" rel="noopener noreferrer" className="hover:opacity-100 opacity-60 transition-opacity" data-testid="social-facebook">Facebook</a>}
              {tmpl.custom.socialLinks.instagram && <a href={tmpl.custom.socialLinks.instagram} target="_blank" rel="noopener noreferrer" className="hover:opacity-100 opacity-60 transition-opacity" data-testid="social-instagram">Instagram</a>}
              {tmpl.custom.socialLinks.twitter && <a href={tmpl.custom.socialLinks.twitter} target="_blank" rel="noopener noreferrer" className="hover:opacity-100 opacity-60 transition-opacity" data-testid="social-twitter">X / Twitter</a>}
              {tmpl.custom.socialLinks.tripadvisor && <a href={tmpl.custom.socialLinks.tripadvisor} target="_blank" rel="noopener noreferrer" className="hover:opacity-100 opacity-60 transition-opacity" data-testid="social-tripadvisor">TripAdvisor</a>}
            </div>
          )}
          <div className="flex items-center justify-center gap-4 mt-3 text-xs">
            <span className="flex items-center gap-1"><ShieldCheck size={12} /> {t("footer.sslSecure")}</span>
            <span className="flex items-center gap-1"><Lock size={12} /> {t("footer.pciCompliant")}</span>
            <span className="flex items-center gap-1"><CheckCircle size={12} /> {t("footer.verifiedProperty")}</span>
          </div>
        </div>
      </footer>

      {/* Group Booking Modal */}
      <GroupBookingModal isOpen={showGroupBooking} onClose={() => setShowGroupBooking(false)}
        propertyId={propertyId} propertyName={tmpl.custom?.hotelName || property?.name || "Hotel"} tmpl={tmpl} />

      {/* AI Concierge Floating Chat */}
      <AIConciergeChat propertyId={propertyId} tmpl={tmpl} />
      <ExitIntentPopup t={tmpl} propertyId={propertyId} active={step < STEPS.PAYMENT} onApply={(code) => { setPendingPromo(code); setPromoCode(code); if (step < STEPS.DETAILS && cart.length) continueToDetails(); }} />
      <CookieBanner accent={tmpl.colors.accent} radius={tmpl.borderRadius} />
    </div>
  );
}

/* ========================= INLINE SUB-COMPONENTS ========================= */

function ReviewsSection({ t, reviews, property, ratingScore, getRatingLabel }) {
  const { t: tr } = useLanguage();
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
              <span className="text-lg text-slate-700">{property?.total_reviews || reviews.length} {tr("hero.reviews")}</span>
            </div>
          ) : (
            <>
              <div className="font-bold px-3 py-2 rounded-tl-lg rounded-br-lg rounded-tr-sm rounded-bl-sm text-xl" style={{ background: t.colors.ratingBg, color: t.colors.ratingText }}>{ratingScore}</div>
              <div>
                <h2 className="text-xl font-semibold text-slate-900" style={{ fontFamily: t.fonts.heading }}>{getRatingLabel(parseFloat(ratingScore))}</h2>
                <p className="text-sm text-slate-500">{property?.total_reviews || reviews.length} {tr("reviews.verifiedReviews")}</p>
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
  const { t: tr } = useLanguage();
  if (!t.showSecurityBadges) return null;
  return (
    <section className="py-10 text-white" style={{ background: t.colors.primary }} data-testid="trust-footer">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
          {[
            { icon: ShieldCheck, label: tr("trust.secureBooking"), sub: tr("trust.sslEncrypted") },
            { icon: CheckCircle, label: tr("trust.freeCancellation"), sub: tr("trust.onMostRooms") },
            { icon: CreditCard, label: tr("trust.bestPrice"), sub: tr("trust.directDiscount") },
            { icon: Phone, label: tr("trust.support"), sub: tr("trust.hereToHelp") },
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

/* ========================= WRAPPER WITH PROVIDER ========================= */
export default function BookingEngine() {
  return (
    <LanguageProvider>
      <BookingEngineInner />
    </LanguageProvider>
  );
}
