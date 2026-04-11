import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import "@fontsource/outfit/400.css";
import "@fontsource/outfit/600.css";
import "@fontsource/outfit/700.css";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import {
  Star, MagnifyingGlass, CalendarBlank, Users, Bed, ShieldCheck, CheckCircle,
  ArrowRight, ArrowLeft, MapPin, WifiHigh, Snowflake, Television, Coffee, Bathtub,
  Lock, Lightning, CaretDown, CaretLeft, CaretRight, Check, Phone, EnvelopeSimple, User, CreditCard,
  Buildings, Heart, Sparkle, Medal, Crown, TreePalm, Briefcase, Baby, X,
} from "@phosphor-icons/react";
import { getTemplate, TEMPLATES } from "./templates/templateConfig";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const STEPS = { SEARCH: 0, ROOMS: 1, DETAILS: 2, PAYMENT: 3, CONFIRM: 4 };

const amenityIcons = {
  "Free WiFi": WifiHigh, "Air conditioning": Snowflake, "Flat-screen TV": Television,
  "55\" Smart TV": Television, "65\" Smart TV": Television, "Tea/coffee maker": Coffee,
  "Nespresso machine": Coffee, "Bathtub": Bathtub, "Rain shower": Bathtub, "Jacuzzi bath": Bathtub,
};

const platformIcons = {
  "Booking.com": Buildings, "Airbnb": Heart, "Expedia": Sparkle, "Hotels.com": Medal,
};

// Mini photo carousel for room cards
function PhotoCarousel({ photos, borderRadius }) {
  const [idx, setIdx] = useState(0);
  if (!photos || photos.length === 0) return <div className="w-full h-full flex items-center justify-center bg-slate-200"><Bed size={48} className="text-slate-300" /></div>;
  return (
    <div className="relative w-full h-full group overflow-hidden">
      <img src={photos[idx]} alt="" className="w-full h-full object-cover transition-opacity duration-300" loading="lazy" />
      {photos.length > 1 && (
        <>
          <button onClick={(e) => { e.stopPropagation(); setIdx(i => (i - 1 + photos.length) % photos.length); }}
            className="absolute left-1.5 top-1/2 -translate-y-1/2 w-7 h-7 bg-white/90 rounded-full flex items-center justify-center shadow opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white">
            <CaretLeft size={14} weight="bold" className="text-slate-700" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); setIdx(i => (i + 1) % photos.length); }}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 w-7 h-7 bg-white/90 rounded-full flex items-center justify-center shadow opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white">
            <CaretRight size={14} weight="bold" className="text-slate-700" />
          </button>
          <div className="absolute bottom-1.5 left-1/2 -translate-x-1/2 flex gap-1">
            {photos.map((_, i) => <div key={i} className={`w-1.5 h-1.5 rounded-full transition-colors ${i === idx ? "bg-white" : "bg-white/40"}`} />)}
          </div>
        </>
      )}
    </div>
  );
}

export default function BookingEngine() {
  const params = new URLSearchParams(window.location.search);
  const propertyId = params.get("property") || "aldgate-flats";
  const templateId = params.get("template") || "booking-classic";
  const t = getTemplate(templateId);

  const [step, setStep] = useState(STEPS.SEARCH);
  const [property, setProperty] = useState(null);
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

  const totalPrice = selectedRoom ? selectedRoom.base_price * nights * roomCount : 0;

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

  const ratingScore = property?.avg_rating ? (property.avg_rating * 2).toFixed(1) : "8.4";
  const getRatingLabel = (r) => r >= 9 ? "Exceptional" : r >= 8 ? "Excellent" : r >= 7 ? "Very Good" : r >= 6 ? "Good" : "Pleasant";
  const PlatformIcon = platformIcons[t.platform] || Buildings;

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

  // ========================= RENDER =========================
  return (
    <div className="min-h-screen" style={{ background: t.colors.bodyBg, fontFamily: t.fonts.body }} data-testid="booking-engine" data-template={templateId}>

      {/* ============ HEADER ============ */}
      <header className="sticky top-0 z-50 shadow-sm" style={{ background: t.colors.headerBg, color: t.colors.headerText }} data-testid="booking-header">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <PlatformIcon size={22} weight="fill" />
            <span className="font-semibold text-lg" style={{ fontFamily: t.fonts.heading }}>{property?.name || "Hotel"}</span>
            {t.platform !== "Booking.com" && (
              <span className="text-xs opacity-60 hidden sm:inline">Powered by MyHotelBox</span>
            )}
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="hidden sm:flex items-center gap-1.5">
              <ShieldCheck size={16} weight="fill" style={{ color: t.colors.success }} />
              <span style={{ opacity: 0.7 }}>Secure Booking</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Phone size={15} />
              <span className="hidden sm:inline" style={{ opacity: 0.7 }}>24/7 Support</span>
            </div>
          </div>
        </div>
      </header>

      {/* ============ STEP INDICATOR ============ */}
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
                  {i < 2 && <ArrowRight size={14} className="text-slate-300" />}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ============ HERO + SEARCH (Step 0) ============ */}
      {step === STEPS.SEARCH && (
        <>
          {/* AIRBNB-STYLE: Photo Grid Hero */}
          {t.layout === "airbnb" ? (
            <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8" data-testid="hero-section">
              {/* Photo Grid */}
              <div className="grid grid-cols-4 grid-rows-2 gap-2 h-[400px] rounded-2xl overflow-hidden mb-6" style={{ borderRadius: t.borderRadius }}>
                <div className="col-span-2 row-span-2 bg-slate-200 relative overflow-hidden">
                  <img src="https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800" alt="Hotel" className="w-full h-full object-cover hover:scale-105 transition-transform duration-500" />
                </div>
                {["https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=400",
                  "https://images.unsplash.com/photo-1590490360182-c33d57733427?w=400",
                  "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=400",
                  "https://images.unsplash.com/photo-1578683010236-d716f9a3f461?w=400"
                ].map((src, i) => (
                  <div key={i} className="bg-slate-200 overflow-hidden relative">
                    <img src={src} alt="" className="w-full h-full object-cover hover:scale-105 transition-transform duration-500" loading="lazy" />
                  </div>
                ))}
              </div>
              {/* Property Info Bar */}
              <div className="flex items-start justify-between pb-6 border-b border-gray-200">
                <div>
                  <h1 className="text-3xl font-bold text-slate-900" style={{ fontFamily: t.fonts.heading }}>{property?.name}</h1>
                  <p className="text-slate-500 mt-1 flex items-center gap-1"><MapPin size={14} /> {property?.city || "London"}, {property?.country || "United Kingdom"}</p>
                  <div className="flex items-center gap-3 mt-2">
                    <div className="flex items-center gap-1">
                      <Star size={16} weight="fill" style={{ color: t.colors.accent }} />
                      <span className="font-bold text-slate-900">{ratingScore}</span>
                      <span className="text-slate-500 text-sm">{getRatingLabel(parseFloat(ratingScore))}</span>
                    </div>
                    <span className="text-slate-400">&middot;</span>
                    <span className="text-sm text-slate-500">{property?.total_reviews || 0} reviews</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="p-2 border border-gray-300 rounded-lg hover:bg-gray-50"><Heart size={20} /></button>
                </div>
              </div>
            </section>
          ) : (
            /* STANDARD: Full-width Image Hero */
            <section className="relative bg-cover bg-center" style={{ backgroundImage: `url(https://images.pexels.com/photos/9119725/pexels-photo-9119725.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940)`, minHeight: "480px" }} data-testid="hero-section">
              <div className="absolute inset-0" style={{ background: t.colors.heroOverlay }} />
              <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
                <div className="text-center text-white mb-10">
                  <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-3" style={{ fontFamily: t.fonts.heading }} data-testid="hero-title">
                    {property?.name || "Book Your Stay"}
                  </h1>
                  <p className="text-lg sm:text-xl max-w-2xl mx-auto" style={{ opacity: 0.8 }}>
                    {property?.city ? `${property.city}, ${property.country}` : "Find your perfect room at the best price"}
                  </p>
                  {property?.avg_rating > 0 && t.showRatingBadge && (
                    <div className="flex items-center justify-center gap-3 mt-4">
                      <div className="font-bold px-2.5 py-1 rounded-tl-lg rounded-br-lg rounded-tr-sm rounded-bl-sm text-sm" style={{ background: t.colors.ratingBg, color: t.colors.ratingText }}>
                        {ratingScore}
                      </div>
                      <span className="font-semibold text-white">{getRatingLabel(parseFloat(ratingScore))}</span>
                      <span style={{ opacity: 0.7 }}>&middot; {property.total_reviews} reviews</span>
                    </div>
                  )}
                  {/* Platform-specific badges */}
                  {t.platform === "Expedia" && (
                    <div className="flex items-center justify-center gap-2 mt-3">
                      <span className="text-xs px-3 py-1 rounded-full font-semibold" style={{ background: t.colors.accent, color: t.colors.primary }}>
                        <Sparkle size={12} weight="fill" className="inline mr-1" />Member Price Available
                      </span>
                    </div>
                  )}
                  {t.platform === "Hotels.com" && t.id === "hotels-rewards" && (
                    <div className="flex items-center justify-center gap-2 mt-3">
                      <span className="text-xs px-3 py-1 rounded-full font-semibold bg-white/20 text-white">
                        <Medal size={12} weight="fill" className="inline mr-1" />Collect stamps with every stay
                      </span>
                    </div>
                  )}
                  {t.id === "hotels-family" && (
                    <div className="flex items-center justify-center gap-2 mt-3">
                      <span className="text-xs px-3 py-1 rounded-full font-semibold bg-white/20 text-white">
                        <Baby size={12} weight="fill" className="inline mr-1" />Family Friendly Property
                      </span>
                    </div>
                  )}
                  {t.id === "booking-business" && (
                    <div className="flex items-center justify-center gap-2 mt-3">
                      <span className="text-xs px-3 py-1 rounded-full font-semibold bg-white/20 text-white">
                        <Briefcase size={12} weight="fill" className="inline mr-1" />Business Travel Ready
                      </span>
                    </div>
                  )}
                  {t.id === "booking-resort" && (
                    <div className="flex items-center justify-center gap-2 mt-3">
                      <span className="text-xs px-3 py-1 rounded-full font-semibold bg-white/20 text-white">
                        <TreePalm size={12} weight="fill" className="inline mr-1" />Resort & Spa
                      </span>
                    </div>
                  )}
                  {t.id === "booking-boutique" && (
                    <div className="flex items-center justify-center gap-2 mt-3">
                      <span className="text-xs px-3 py-1 rounded-full font-semibold bg-white/20 text-white">
                        <Crown size={12} weight="fill" className="inline mr-1" />Boutique Collection
                      </span>
                    </div>
                  )}
                </div>

                {/* Search Widget */}
                <SearchWidget t={t} checkIn={checkIn} setCheckIn={setCheckIn} checkOut={checkOut} setCheckOut={setCheckOut}
                  adults={adults} setAdults={setAdults} children={children} setChildren={setChildren}
                  roomCount={roomCount} setRoomCount={setRoomCount} showGuestPicker={showGuestPicker}
                  setShowGuestPicker={setShowGuestPicker} searchRooms={searchRooms} />
              </div>
            </section>
          )}

          {/* Airbnb: Search Widget below photo grid */}
          {t.layout === "airbnb" && (
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
              <SearchWidget t={t} checkIn={checkIn} setCheckIn={setCheckIn} checkOut={checkOut} setCheckOut={setCheckOut}
                adults={adults} setAdults={setAdults} children={children} setChildren={setChildren}
                roomCount={roomCount} setRoomCount={setRoomCount} showGuestPicker={showGuestPicker}
                setShowGuestPicker={setShowGuestPicker} searchRooms={searchRooms} />
            </div>
          )}

          {/* Room Preview Cards */}
          {property?.room_types?.length > 0 && (
            <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16" data-testid="rooms-preview-section">
              <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 mb-2" style={{ fontFamily: t.fonts.heading }}>
                {t.layout === "airbnb" ? "Rooms & Suites" : "Our Rooms"}
              </h2>
              <p className="text-slate-500 mb-8">Choose from our selection of comfortable rooms</p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {property.room_types.slice(0, 6).map((room) => (
                  <div key={room.id} className="bg-white border border-gray-200 overflow-hidden hover:shadow-lg transition-all hover:-translate-y-1" style={{ borderRadius: t.borderRadius }} data-testid={`room-preview-${room.id}`}>
                    <div className="h-48 bg-slate-200 relative overflow-hidden">
                      <PhotoCarousel photos={room.photos} borderRadius={t.borderRadius} />
                      {t.showFreeCancellation && room.free_cancellation && (
                        <div className="absolute top-3 left-3 text-xs font-semibold px-2 py-1 rounded flex items-center gap-1" style={{ background: t.colors.badgeBg, color: t.colors.success, border: `1px solid ${t.colors.success}20` }}>
                          <CheckCircle size={12} weight="fill" /> Free cancellation
                        </div>
                      )}
                    </div>
                    <div className="p-4">
                      <h3 className="font-semibold text-slate-900 text-lg mb-1" style={{ fontFamily: t.fonts.heading }}>{room.name}</h3>
                      <div className="flex items-center gap-3 text-xs text-slate-500 mb-3">
                        <span className="flex items-center gap-1"><Users size={12} /> {room.max_guests} guests</span>
                        <span className="flex items-center gap-1"><Bed size={12} /> {room.bed_type}</span>
                        {room.size_sqm > 0 && <span>{room.size_sqm} m&sup2;</span>}
                      </div>
                      <div className="flex flex-wrap gap-1.5 mb-4">
                        {room.amenities?.slice(0, 4).map((a) => (
                          <span key={a} className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{a}</span>
                        ))}
                      </div>
                      <div className="flex items-end justify-between border-t border-gray-100 pt-3">
                        <div>
                          <span className="text-2xl font-bold text-slate-900">&pound;{room.base_price}</span>
                          <span className="text-sm text-slate-500 ml-1">/ night</span>
                          {room.breakfast_included && (
                            <div className="text-[11px] font-medium mt-0.5 flex items-center gap-1" style={{ color: t.colors.success }}>
                              <CheckCircle size={11} weight="fill" /> Breakfast included
                            </div>
                          )}
                        </div>
                        <button onClick={searchRooms} className="text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid={`see-availability-${room.id}`}>
                          See availability
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Reviews Section */}
          {reviews.length > 0 && (
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
          )}

          {/* Trust Footer */}
          {t.showSecurityBadges && (
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
          )}
        </>
      )}

      {/* ============ ROOM SELECTION (Step 1) ============ */}
      {step === STEPS.ROOMS && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="room-selection">
          <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6 flex flex-wrap items-center gap-4" style={{ borderRadius: t.borderRadius }}>
            <div className="flex items-center gap-2 text-sm">
              <CalendarBlank size={16} style={{ color: t.colors.accent }} />
              <span className="font-medium text-slate-700">{new Date(checkIn).toLocaleDateString("en-GB", { day: "numeric", month: "short" })} — {new Date(checkOut).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</span>
              <span className="text-slate-400">({nights} night{nights !== 1 ? "s" : ""})</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Users size={16} style={{ color: t.colors.accent }} />
              <span className="font-medium text-slate-700">{adults} adult{adults !== 1 ? "s" : ""}{children > 0 ? `, ${children} child${children !== 1 ? "ren" : ""}` : ""}</span>
            </div>
            <button onClick={() => setStep(STEPS.SEARCH)} className="ml-auto text-sm font-semibold hover:underline" style={{ color: t.colors.accent }} data-testid="change-search-btn">Change search</button>
          </div>

          <h2 className="text-2xl font-semibold text-slate-900 mb-6" style={{ fontFamily: t.fonts.heading }}>Available rooms</h2>

          {loading ? (
            <div className="flex justify-center py-20">
              <div className="w-10 h-10 border-4 border-t-transparent rounded-full animate-spin" style={{ borderColor: t.colors.accent, borderTopColor: "transparent" }} />
            </div>
          ) : rooms.length === 0 ? (
            <div className="text-center py-20 bg-white rounded-lg border border-gray-200">
              <Bed size={48} className="mx-auto text-slate-300 mb-4" />
              <h3 className="text-lg font-semibold text-slate-700">No rooms available</h3>
              <p className="text-slate-500 mt-1">Try different dates</p>
            </div>
          ) : (
            <div className="space-y-4">
              {rooms.map((room) => (
                <div key={room.id} className="bg-white border border-gray-200 overflow-hidden hover:shadow-md transition-shadow" style={{ borderRadius: t.borderRadius }} data-testid={`room-card-${room.id}`}>
                  <div className="flex flex-col md:flex-row">
                    <div className="md:w-72 h-48 md:h-auto bg-slate-200 flex-shrink-0 overflow-hidden" style={{ minHeight: "180px" }}>
                      <PhotoCarousel photos={room.photos} borderRadius="0" />
                    </div>
                    <div className="flex-1 p-5">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="text-xl font-semibold" style={{ color: t.colors.accent, fontFamily: t.fonts.heading }}>{room.name}</h3>
                          <div className="flex items-center gap-3 text-sm text-slate-500 mt-1">
                            <span className="flex items-center gap-1"><Users size={14} /> {room.max_guests} guests</span>
                            <span className="flex items-center gap-1"><Bed size={14} /> {room.bed_type} bed</span>
                            {room.size_sqm > 0 && <span>{room.size_sqm} m&sup2;</span>}
                          </div>
                        </div>
                        {t.showUrgency && room.available_rooms <= 3 && room.available_rooms > 0 && (
                          <span className="text-sm font-semibold flex items-center gap-1 flex-shrink-0" style={{ color: t.colors.urgency }} data-testid={`urgency-${room.id}`}>
                            <Lightning size={14} weight="fill" /> Only {room.available_rooms} left!
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-600 mb-3 line-clamp-2">{room.description}</p>
                      <div className="flex flex-wrap gap-2 mb-4">
                        {room.amenities?.slice(0, 6).map((a) => {
                          const Icon = amenityIcons[a];
                          return <span key={a} className="text-xs text-slate-600 flex items-center gap-1">{Icon ? <Icon size={12} style={{ color: t.colors.accent }} /> : <Check size={12} style={{ color: t.colors.success }} />}{a}</span>;
                        })}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {t.showFreeCancellation && room.free_cancellation && (
                          <span className="text-xs font-semibold px-2.5 py-1 rounded flex items-center gap-1" style={{ background: t.colors.badgeBg, color: t.colors.success }}>
                            <CheckCircle size={13} weight="fill" /> Free cancellation
                          </span>
                        )}
                        {room.breakfast_included && (
                          <span className="text-xs font-semibold px-2.5 py-1 rounded flex items-center gap-1" style={{ background: t.colors.badgeBg, color: t.colors.success }}>
                            <CheckCircle size={13} weight="fill" /> Breakfast included
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="md:w-56 p-5 border-l border-gray-200 flex flex-col justify-between" style={{ background: t.colors.priceBg }}>
                      <div>
                        <div className="text-xs text-slate-500 mb-1">{nights} night{nights !== 1 ? "s" : ""}, {adults} adult{adults !== 1 ? "s" : ""}</div>
                        <div className="text-3xl font-bold text-slate-900">&pound;{(room.base_price * nights * roomCount).toFixed(0)}</div>
                        <div className="text-xs text-slate-500 mt-0.5">Includes taxes and fees</div>
                      </div>
                      <button onClick={() => handleSelectRoom(room)} disabled={!room.is_available}
                        className="mt-4 w-full py-3 rounded-lg font-semibold text-sm transition-colors text-white disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed"
                        style={{ background: room.is_available ? t.colors.accent : undefined, borderRadius: t.borderRadius }}
                        data-testid={`select-room-${room.id}`}>
                        {room.is_available ? "Reserve" : "Sold out"}
                      </button>
                      <div className="mt-2 text-center text-[10px] text-slate-400 flex items-center justify-center gap-1"><Lock size={10} /> Secure booking</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ============ GUEST DETAILS (Step 2) ============ */}
      {step === STEPS.DETAILS && selectedRoom && (
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="guest-details-step">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }}>
                <h2 className="text-xl font-semibold text-slate-900 mb-6 flex items-center gap-2" style={{ fontFamily: t.fonts.heading }}>
                  <User size={22} style={{ color: t.colors.accent }} /> Your Details
                </h2>
                <div className="space-y-4">
                  {[
                    { label: "Full Name *", field: "guest_name", type: "text", icon: User, placeholder: "John Smith", testId: "guest-name-input" },
                    { label: "Email Address *", field: "guest_email", type: "email", icon: EnvelopeSimple, placeholder: "john@example.com", testId: "guest-email-input" },
                    { label: "Phone Number", field: "guest_phone", type: "tel", icon: Phone, placeholder: "+44 7XXX XXXXXX", testId: "guest-phone-input" },
                  ].map(({ label, field, type, icon: Icon, placeholder, testId }) => (
                    <div key={field}>
                      <label className="text-sm font-medium text-slate-700 mb-1 block">{label}</label>
                      <div className="relative">
                        <Icon size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input type={type} value={guestForm[field]} onChange={e => setGuestForm(p => ({ ...p, [field]: e.target.value }))}
                          placeholder={placeholder} className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 focus:ring-2 focus:border-transparent"
                          style={{ "--tw-ring-color": t.colors.accent }} data-testid={testId} />
                      </div>
                    </div>
                  ))}
                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-1 block">Special Requests</label>
                    <textarea value={guestForm.special_requests} onChange={e => setGuestForm(p => ({ ...p, special_requests: e.target.value }))}
                      placeholder="Any special requirements?" rows={3} className="w-full border border-gray-300 rounded-lg px-3 py-3 resize-none" data-testid="special-requests-input" />
                  </div>
                </div>
              </div>

              {/* Payment Method */}
              <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }} data-testid="payment-method-section">
                <h2 className="text-xl font-semibold text-slate-900 mb-4 flex items-center gap-2" style={{ fontFamily: t.fonts.heading }}>
                  <CreditCard size={22} style={{ color: t.colors.accent }} /> Payment Method
                </h2>
                <div className="space-y-3">
                  {[
                    { value: "card", icon: CreditCard, label: "Pay Now with Card", sub: "Secure payment via Stripe. Instantly confirmed.", showSecure: true },
                    { value: "hotel", icon: Buildings, label: "Pay at Hotel", sub: "Pay when you arrive. No payment required now." },
                  ].map(({ value, icon: Icon, label, sub, showSecure }) => (
                    <label key={value} className="flex items-center gap-3 p-4 rounded-lg border-2 cursor-pointer transition-colors"
                      style={{ borderColor: paymentMethod === value ? t.colors.accent : "#e5e7eb", background: paymentMethod === value ? `${t.colors.accent}08` : "transparent", borderRadius: t.borderRadius }}
                      data-testid={`payment-${value}-option`}>
                      <input type="radio" name="payment" value={value} checked={paymentMethod === value} onChange={() => setPaymentMethod(value)} className="sr-only" />
                      <div className="w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0" style={{ borderColor: paymentMethod === value ? t.colors.accent : "#d1d5db" }}>
                        {paymentMethod === value && <div className="w-2.5 h-2.5 rounded-full" style={{ background: t.colors.accent }} />}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <Icon size={18} style={{ color: paymentMethod === value ? t.colors.accent : "#64748b" }} />
                          <span className="font-semibold text-slate-800 text-sm">{label}</span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">{sub}</p>
                      </div>
                      {showSecure && <div className="flex items-center gap-1 text-xs text-slate-400"><ShieldCheck size={14} weight="fill" style={{ color: t.colors.success }} /><span>Secure</span></div>}
                    </label>
                  ))}
                </div>
              </div>

              <button onClick={handleBooking} disabled={bookingLoading || !guestForm.guest_name || !guestForm.guest_email}
                className="w-full text-white py-4 rounded-lg font-bold text-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3 shadow-xl"
                style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="complete-booking-btn">
                {bookingLoading ? <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin" />
                  : paymentMethod === "card" ? <><CreditCard size={20} weight="fill" /> Pay &pound;{totalPrice.toFixed(0)} &amp; Complete Booking</>
                  : <><Lock size={20} weight="fill" /> Complete Booking — Pay at Hotel</>}
              </button>
              <p className="text-center text-xs text-slate-400 flex items-center justify-center gap-1 mt-2">
                <ShieldCheck size={14} weight="fill" style={{ color: t.colors.success }} /> Your personal data is protected by SSL encryption
              </p>
            </div>

            {/* Booking Summary */}
            <div className="lg:col-span-1">
              <div className="bg-white rounded-lg border border-gray-200 p-5 sticky top-20" style={{ borderRadius: t.borderRadius }} data-testid="booking-summary">
                <h3 className="font-semibold text-slate-900 mb-4" style={{ fontFamily: t.fonts.heading }}>Booking Summary</h3>
                <div className="flex gap-3 mb-4 pb-4 border-b border-gray-100">
                  <div className="w-20 h-16 rounded-lg bg-slate-200 overflow-hidden flex-shrink-0">
                    {selectedRoom.photos?.[0] ? <img src={selectedRoom.photos[0]} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center"><Bed size={20} className="text-slate-300" /></div>}
                  </div>
                  <div>
                    <div className="font-semibold text-sm text-slate-900">{selectedRoom.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{property?.name}</div>
                  </div>
                </div>
                <div className="space-y-2 text-sm mb-4 pb-4 border-b border-gray-100">
                  {[
                    ["Check-in", new Date(checkIn).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })],
                    ["Check-out", new Date(checkOut).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })],
                    ["Duration", `${nights} night${nights !== 1 ? "s" : ""}`],
                    ["Guests", `${adults} adult${adults !== 1 ? "s" : ""}${children > 0 ? `, ${children} child${children !== 1 ? "ren" : ""}` : ""}`],
                    ["Rooms", roomCount],
                  ].map(([l, v]) => <div key={l} className="flex justify-between"><span className="text-slate-500">{l}</span><span className="font-medium text-slate-800">{v}</span></div>)}
                </div>
                <div className="space-y-2 text-sm mb-4 pb-4 border-b border-gray-100">
                  <div className="flex justify-between"><span className="text-slate-500">&pound;{selectedRoom.base_price} x {nights} night{nights !== 1 ? "s" : ""}</span><span>&pound;{totalPrice.toFixed(0)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Taxes & fees</span><span>Included</span></div>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="font-semibold text-slate-900">Total</span>
                  <span className="text-2xl font-bold text-slate-900">&pound;{totalPrice.toFixed(0)}</span>
                </div>
                {selectedRoom.free_cancellation && (
                  <div className="mt-3 rounded-lg p-3 text-xs font-medium flex items-center gap-1.5" style={{ background: t.colors.badgeBg, color: t.colors.success }}>
                    <CheckCircle size={14} weight="fill" /> Free cancellation available
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============ PAYMENT PROCESSING (Step 3) ============ */}
      {step === STEPS.PAYMENT && (
        <div className="max-w-lg mx-auto px-4 py-20" data-testid="payment-processing-step">
          <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-10 text-center" style={{ borderRadius: t.borderRadius }}>
            <div className="w-16 h-16 border-4 border-t-transparent rounded-full animate-spin mx-auto mb-6" style={{ borderColor: t.colors.accent, borderTopColor: "transparent" }} />
            <h2 className="text-xl font-bold text-slate-900 mb-2" style={{ fontFamily: t.fonts.heading }}>Processing Your Payment</h2>
            <p className="text-slate-500">Please wait while we confirm your payment...</p>
          </div>
        </div>
      )}

      {/* ============ CONFIRMATION (Step 4) ============ */}
      {step === STEPS.CONFIRM && confirmation && (
        <div className="max-w-3xl mx-auto px-4 py-12" data-testid="confirmation-step">
          <div className="bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden" style={{ borderRadius: t.borderRadius }}>
            <div className="text-white px-8 py-6 text-center" style={{ background: t.colors.success }}>
              <CheckCircle size={48} weight="fill" className="mx-auto mb-3" />
              <h2 className="text-2xl font-bold mb-1" style={{ fontFamily: t.fonts.heading }}>Booking Confirmed!</h2>
              <p style={{ opacity: 0.8 }}>{confirmation.payment_status === "paid" ? "Payment received" : "Your reservation is confirmed"}</p>
            </div>
            <div className="p-8">
              <div className="rounded-lg p-5 mb-6 text-center" style={{ background: t.colors.bodyBg }}>
                <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Booking Reference</div>
                <div className="text-3xl font-bold tracking-wider" style={{ color: t.colors.primary }} data-testid="booking-ref">{confirmation.booking_ref}</div>
                <p className="text-xs text-slate-500 mt-2">Save this reference for your records</p>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                {[
                  ["Guest Name", confirmation.guest_name],
                  ["Email", confirmation.guest_email],
                  ["Check-in", new Date(confirmation.check_in).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })],
                  ["Check-out", new Date(confirmation.check_out).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })],
                  ["Guests", `${confirmation.adults} adult${confirmation.adults !== 1 ? "s" : ""}${confirmation.children > 0 ? `, ${confirmation.children} children` : ""}`],
                  ["Total", `£${confirmation.total_price?.toFixed(0)}`],
                ].map(([l, v]) => <div key={l}><span className="text-slate-500 block mb-0.5">{l}</span><span className="font-semibold text-slate-800" data-testid={l === "Guest Name" ? "confirm-guest-name" : undefined}>{v}</span></div>)}
              </div>
              <div className="mt-6 pt-6 border-t border-gray-100 flex justify-center">
                <button onClick={() => { setStep(STEPS.SEARCH); setSelectedRoom(null); setConfirmation(null); setGuestForm({ guest_name: "", guest_email: "", guest_phone: "", special_requests: "" }); }}
                  className="text-white px-6 py-3 rounded-lg font-semibold transition-colors" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="book-another-btn">
                  Book Another Room
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Mobile Sticky */}
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
          <p>Powered by <span className="font-semibold" style={{ color: t.colors.headerText }}>MyHotelBox</span> Booking Engine</p>
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

// ========================= SEARCH WIDGET =========================
function SearchWidget({ t, checkIn, setCheckIn, checkOut, setCheckOut, adults, setAdults, children, setChildren, roomCount, setRoomCount, showGuestPicker, setShowGuestPicker, searchRooms }) {
  const isAirbnb = t.layout === "airbnb";
  return (
    <div className={`${isAirbnb ? "bg-white border border-gray-200 shadow-md" : "bg-white shadow-2xl border border-gray-200"} p-6 sm:p-8`}
      style={{ borderRadius: isAirbnb ? "16px" : t.borderRadius }} data-testid="search-widget">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">Check-in</label>
          <div className="relative">
            <CalendarBlank size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="date" value={checkIn} onChange={e => setCheckIn(e.target.value)} min={new Date().toISOString().split("T")[0]}
              className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 text-slate-800 font-medium focus:ring-2 focus:border-transparent"
              data-testid="check-in-input" />
          </div>
        </div>
        <div>
          <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">Check-out</label>
          <div className="relative">
            <CalendarBlank size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="date" value={checkOut} onChange={e => setCheckOut(e.target.value)} min={checkIn}
              className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 text-slate-800 font-medium focus:ring-2 focus:border-transparent"
              data-testid="check-out-input" />
          </div>
        </div>
        <div>
          <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">Guests</label>
          <div className="relative">
            <button onClick={() => setShowGuestPicker(!showGuestPicker)}
              className="w-full border border-gray-300 rounded-lg px-3 py-3 text-left text-slate-800 font-medium flex items-center gap-2" data-testid="guest-picker-trigger">
              <Users size={18} className="text-slate-400" />
              <span>{adults} Adult{adults !== 1 ? "s" : ""}{children > 0 ? `, ${children} Child${children !== 1 ? "ren" : ""}` : ""}</span>
              <CaretDown size={14} className="ml-auto text-slate-400" />
            </button>
            {showGuestPicker && (
              <div className="absolute top-full mt-1 left-0 right-0 bg-white border border-gray-200 rounded-lg shadow-xl p-4 z-20" data-testid="guest-picker-dropdown">
                {[
                  { label: "Adults", value: adults, set: setAdults, min: 1, max: 10 },
                  { label: "Children", value: children, set: setChildren, min: 0, max: 6 },
                  { label: "Rooms", value: roomCount, set: setRoomCount, min: 1, max: 5 },
                ].map(({ label, value, set, min, max }) => (
                  <div key={label} className="flex items-center justify-between py-2">
                    <span className="text-sm text-slate-700 font-medium">{label}</span>
                    <div className="flex items-center gap-3">
                      <button onClick={() => set(Math.max(min, value - 1))} className="w-8 h-8 rounded-full border border-gray-300 flex items-center justify-center text-slate-600 hover:bg-slate-50">-</button>
                      <span className="w-6 text-center font-semibold">{value}</span>
                      <button onClick={() => set(Math.min(max, value + 1))} className="w-8 h-8 rounded-full border border-gray-300 flex items-center justify-center text-slate-600 hover:bg-slate-50">+</button>
                    </div>
                  </div>
                ))}
                <button onClick={() => setShowGuestPicker(false)} className="w-full mt-2 text-white py-2 rounded-lg font-semibold text-sm" style={{ background: t.colors.accent }}>Done</button>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-end">
          <button onClick={searchRooms} className="w-full text-white py-3 rounded-lg font-semibold text-base transition-colors flex items-center justify-center gap-2 shadow-lg"
            style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="search-rooms-btn">
            <MagnifyingGlass size={18} weight="bold" /> Search
          </button>
        </div>
      </div>
    </div>
  );
}
