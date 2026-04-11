import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import "@fontsource/outfit/400.css";
import "@fontsource/outfit/600.css";
import "@fontsource/outfit/700.css";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import {
  Star,
  MagnifyingGlass,
  CalendarBlank,
  Users,
  Bed,
  ShieldCheck,
  CheckCircle,
  ArrowRight,
  ArrowLeft,
  MapPin,
  WifiHigh,
  Snowflake,
  Television,
  Coffee,
  Bathtub,
  Lock,
  Lightning,
  CaretDown,
  X,
  Check,
  Phone,
  EnvelopeSimple,
  User,
  CreditCard,
  Info,
  Buildings,
  Heart,
  ShareNetwork,
} from "@phosphor-icons/react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Step constants
const STEPS = { SEARCH: 0, ROOMS: 1, DETAILS: 2, CONFIRM: 3 };

const amenityIcons = {
  "Free WiFi": WifiHigh,
  "Air conditioning": Snowflake,
  "Flat-screen TV": Television,
  "55\" Smart TV": Television,
  "65\" Smart TV": Television,
  "Tea/coffee maker": Coffee,
  "Nespresso machine": Coffee,
  "Bathtub": Bathtub,
  "Rain shower": Bathtub,
  "Jacuzzi bath": Bathtub,
};

export default function BookingEngine() {
  const params = new URLSearchParams(window.location.search);
  const propertyId = params.get("property") || "aldgate-flats";

  const [step, setStep] = useState(STEPS.SEARCH);
  const [property, setProperty] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [confirmation, setConfirmation] = useState(null);

  // Search state
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [adults, setAdults] = useState(2);
  const [children, setChildren] = useState(0);
  const [roomCount, setRoomCount] = useState(1);
  const [showGuestPicker, setShowGuestPicker] = useState(false);

  // Selected room
  const [selectedRoom, setSelectedRoom] = useState(null);

  // Guest details
  const [guestForm, setGuestForm] = useState({
    guest_name: "",
    guest_email: "",
    guest_phone: "",
    special_requests: "",
  });

  // Set default dates (today + 1 to today + 2)
  useEffect(() => {
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dayAfter = new Date(today);
    dayAfter.setDate(dayAfter.getDate() + 2);
    setCheckIn(tomorrow.toISOString().split("T")[0]);
    setCheckOut(dayAfter.toISOString().split("T")[0]);
  }, []);

  // Load property info & reviews
  useEffect(() => {
    const load = async () => {
      try {
        const [propRes, revRes] = await Promise.all([
          axios.get(`${API}/booking/property/${propertyId}`),
          axios.get(`${API}/booking/reviews/${propertyId}?limit=6`),
        ]);
        setProperty(propRes.data);
        setReviews(revRes.data);
      } catch (e) {
        console.error("Failed to load property:", e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [propertyId]);

  const searchRooms = useCallback(async () => {
    if (!checkIn || !checkOut) return;
    setLoading(true);
    try {
      const { data } = await axios.get(
        `${API}/booking/rooms/${propertyId}?check_in=${checkIn}&check_out=${checkOut}&adults=${adults}&children=${children}`
      );
      setRooms(data);
      setStep(STEPS.ROOMS);
    } catch (e) {
      console.error("Search failed:", e);
    } finally {
      setLoading(false);
    }
  }, [propertyId, checkIn, checkOut, adults, children]);

  const handleSelectRoom = (room) => {
    setSelectedRoom(room);
    setStep(STEPS.DETAILS);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const calculateNights = () => {
    if (!checkIn || !checkOut) return 1;
    const ci = new Date(checkIn);
    const co = new Date(checkOut);
    return Math.max(1, Math.round((co - ci) / (1000 * 60 * 60 * 24)));
  };

  const handleBooking = async () => {
    if (!guestForm.guest_name || !guestForm.guest_email) return;
    setBookingLoading(true);
    try {
      const { data } = await axios.post(`${API}/booking/reserve`, {
        property_id: propertyId,
        room_type_id: selectedRoom.id,
        guest_name: guestForm.guest_name,
        guest_email: guestForm.guest_email,
        guest_phone: guestForm.guest_phone,
        check_in: checkIn,
        check_out: checkOut,
        adults,
        children,
        rooms: roomCount,
        special_requests: guestForm.special_requests,
      });
      setConfirmation(data);
      setStep(STEPS.CONFIRM);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      alert(e.response?.data?.detail || "Booking failed. Please try again.");
    } finally {
      setBookingLoading(false);
    }
  };

  const nights = calculateNights();
  const totalPrice = selectedRoom ? selectedRoom.base_price * nights * roomCount : 0;

  const getRatingLabel = (rating) => {
    if (rating >= 9) return "Exceptional";
    if (rating >= 8) return "Excellent";
    if (rating >= 7) return "Very Good";
    if (rating >= 6) return "Good";
    return "Pleasant";
  };

  if (loading && !property) {
    return (
      <div className="min-h-screen bg-[#F5F7FA] flex items-center justify-center" style={{ fontFamily: "Manrope, sans-serif" }}>
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-[#006CE4] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-500">Loading booking engine...</p>
        </div>
      </div>
    );
  }

  const ratingScore = property?.avg_rating ? (property.avg_rating * 2).toFixed(1) : "8.4";

  return (
    <div className="min-h-screen bg-[#F5F7FA]" style={{ fontFamily: "Manrope, sans-serif" }} data-testid="booking-engine">
      {/* Header Bar */}
      <header className="bg-[#0A4297] text-white sticky top-0 z-50 shadow-lg" data-testid="booking-header">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Buildings size={22} weight="fill" />
            <span className="font-semibold text-lg" style={{ fontFamily: "Outfit, sans-serif" }}>
              {property?.name || "Hotel"}
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="hidden sm:flex items-center gap-1.5">
              <ShieldCheck size={16} weight="fill" className="text-green-300" />
              <span className="text-blue-100">Secure Booking</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Phone size={15} />
              <span className="text-blue-100 hidden sm:inline">24/7 Support</span>
            </div>
          </div>
        </div>
      </header>

      {/* Step Indicator */}
      {step > STEPS.SEARCH && step < STEPS.CONFIRM && (
        <div className="bg-white border-b border-gray-200" data-testid="step-indicator">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
            <div className="flex items-center gap-2 text-sm">
              {["Search", "Select Room", "Your Details"].map((label, i) => (
                <div key={label} className="flex items-center gap-2">
                  <button
                    onClick={() => i < step && setStep(i)}
                    className={`flex items-center gap-1.5 ${
                      i === step ? "text-[#006CE4] font-semibold" : i < step ? "text-[#008009] cursor-pointer" : "text-slate-400"
                    }`}
                    data-testid={`step-${i}`}
                  >
                    {i < step ? (
                      <CheckCircle size={18} weight="fill" className="text-[#008009]" />
                    ) : (
                      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                        i === step ? "bg-[#006CE4] text-white" : "bg-slate-200 text-slate-500"
                      }`}>{i + 1}</span>
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

      {/* HERO SECTION with Search Widget (Step 0) */}
      {step === STEPS.SEARCH && (
        <>
          <section
            className="relative bg-cover bg-center"
            style={{ backgroundImage: `url(https://images.pexels.com/photos/9119725/pexels-photo-9119725.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940)`, minHeight: "480px" }}
            data-testid="hero-section"
          >
            <div className="absolute inset-0 bg-gradient-to-b from-black/50 to-black/30" />
            <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
              <div className="text-center text-white mb-10">
                <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-3" style={{ fontFamily: "Outfit, sans-serif" }} data-testid="hero-title">
                  {property?.name || "Book Your Stay"}
                </h1>
                <p className="text-lg sm:text-xl text-white/80 max-w-2xl mx-auto">
                  {property?.city ? `${property.city}, ${property.country}` : "Find your perfect room at the best price"}
                </p>
                {property?.avg_rating > 0 && (
                  <div className="flex items-center justify-center gap-3 mt-4">
                    <div className="bg-[#0A4297] text-white font-bold px-2.5 py-1 rounded-tl-lg rounded-br-lg rounded-tr-sm rounded-bl-sm text-sm">
                      {ratingScore}
                    </div>
                    <span className="text-white font-semibold">{getRatingLabel(parseFloat(ratingScore))}</span>
                    <span className="text-white/70">&middot; {property.total_reviews} reviews</span>
                  </div>
                )}
              </div>

              {/* Search Widget */}
              <div className="max-w-4xl mx-auto bg-white rounded-xl shadow-2xl p-6 sm:p-8 border border-gray-200" data-testid="search-widget">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div>
                    <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">Check-in</label>
                    <div className="relative">
                      <CalendarBlank size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="date"
                        value={checkIn}
                        onChange={(e) => setCheckIn(e.target.value)}
                        min={new Date().toISOString().split("T")[0]}
                        className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 text-slate-800 font-medium focus:ring-2 focus:ring-[#006CE4] focus:border-transparent"
                        data-testid="check-in-input"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">Check-out</label>
                    <div className="relative">
                      <CalendarBlank size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="date"
                        value={checkOut}
                        onChange={(e) => setCheckOut(e.target.value)}
                        min={checkIn}
                        className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 text-slate-800 font-medium focus:ring-2 focus:ring-[#006CE4] focus:border-transparent"
                        data-testid="check-out-input"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold tracking-wider uppercase text-slate-500 mb-1.5 block">Guests</label>
                    <div className="relative">
                      <button
                        onClick={() => setShowGuestPicker(!showGuestPicker)}
                        className="w-full border border-gray-300 rounded-lg px-3 py-3 text-left text-slate-800 font-medium flex items-center gap-2 focus:ring-2 focus:ring-[#006CE4]"
                        data-testid="guest-picker-trigger"
                      >
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
                          <button onClick={() => setShowGuestPicker(false)} className="w-full mt-2 bg-[#006CE4] text-white py-2 rounded-lg font-semibold text-sm hover:bg-[#0056B3]">Done</button>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-end">
                    <button
                      onClick={searchRooms}
                      className="w-full bg-[#006CE4] text-white py-3 rounded-lg font-semibold text-base hover:bg-[#0056B3] transition-colors flex items-center justify-center gap-2 shadow-lg shadow-blue-500/20"
                      data-testid="search-rooms-btn"
                    >
                      <MagnifyingGlass size={18} weight="bold" />
                      Search
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Room Preview Cards */}
          {property?.room_types?.length > 0 && (
            <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16" data-testid="rooms-preview-section">
              <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 mb-2" style={{ fontFamily: "Outfit, sans-serif" }}>Our Rooms</h2>
              <p className="text-slate-500 mb-8">Choose from our selection of comfortable and well-appointed rooms</p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {property.room_types.slice(0, 6).map((room) => (
                  <div key={room.id} className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-lg transition-all hover:-translate-y-1" data-testid={`room-preview-${room.id}`}>
                    <div className="h-48 bg-slate-200 relative overflow-hidden">
                      {room.photos?.[0] ? (
                        <img src={room.photos[0]} alt={room.name} className="w-full h-full object-cover" loading="lazy" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center"><Bed size={48} className="text-slate-300" /></div>
                      )}
                      {room.free_cancellation && (
                        <div className="absolute top-3 left-3 bg-green-50 text-[#008009] border border-green-200 text-xs font-semibold px-2 py-1 rounded flex items-center gap-1">
                          <CheckCircle size={12} weight="fill" /> Free cancellation
                        </div>
                      )}
                    </div>
                    <div className="p-4">
                      <h3 className="font-semibold text-slate-900 text-lg mb-1" style={{ fontFamily: "Outfit, sans-serif" }}>{room.name}</h3>
                      <div className="flex items-center gap-3 text-xs text-slate-500 mb-3">
                        <span className="flex items-center gap-1"><Users size={12} /> {room.max_guests} guests</span>
                        <span className="flex items-center gap-1"><Bed size={12} /> {room.bed_type}</span>
                        {room.size_sqm > 0 && <span>{room.size_sqm} m&sup2;</span>}
                      </div>
                      <div className="flex flex-wrap gap-1.5 mb-4">
                        {room.amenities?.slice(0, 4).map((a) => (
                          <span key={a} className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{a}</span>
                        ))}
                        {room.amenities?.length > 4 && <span className="text-[10px] text-[#006CE4] font-medium">+{room.amenities.length - 4} more</span>}
                      </div>
                      <div className="flex items-end justify-between border-t border-gray-100 pt-3">
                        <div>
                          <span className="text-2xl font-bold text-slate-900">&pound;{room.base_price}</span>
                          <span className="text-sm text-slate-500 ml-1">/ night</span>
                          {room.breakfast_included && (
                            <div className="text-[11px] text-[#008009] font-medium mt-0.5 flex items-center gap-1">
                              <CheckCircle size={11} weight="fill" /> Breakfast included
                            </div>
                          )}
                        </div>
                        <button onClick={searchRooms} className="bg-[#006CE4] text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-[#0056B3] transition-colors" data-testid={`see-availability-${room.id}`}>
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
                  <div className="bg-[#0A4297] text-white font-bold px-3 py-2 rounded-tl-lg rounded-br-lg rounded-tr-sm rounded-bl-sm text-xl">{ratingScore}</div>
                  <div>
                    <h2 className="text-xl font-semibold text-slate-900" style={{ fontFamily: "Outfit, sans-serif" }}>{getRatingLabel(parseFloat(ratingScore))}</h2>
                    <p className="text-sm text-slate-500">{property?.total_reviews || reviews.length} verified guest reviews</p>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {reviews.map((r) => (
                    <div key={r.id} className="bg-[#F5F7FA] rounded-lg p-4" data-testid={`review-card-${r.id}`}>
                      <div className="flex items-center gap-2 mb-2">
                        <div className="w-8 h-8 rounded-full bg-[#0A4297] text-white flex items-center justify-center text-sm font-bold">
                          {r.guest_name?.charAt(0)?.toUpperCase()}
                        </div>
                        <div>
                          <span className="text-sm font-semibold text-slate-800">{r.guest_name}</span>
                          <div className="flex gap-0.5">
                            {[1, 2, 3, 4, 5].map((s) => (
                              <Star key={s} size={11} weight={s <= r.rating ? "fill" : "regular"} className={s <= r.rating ? "text-amber-400" : "text-slate-300"} />
                            ))}
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
          <section className="bg-[#0A4297] text-white py-10" data-testid="trust-footer">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
                {[
                  { icon: ShieldCheck, label: "Secure Booking", sub: "SSL encrypted" },
                  { icon: CheckCircle, label: "Free Cancellation", sub: "On most rooms" },
                  { icon: CreditCard, label: "Best Price Guarantee", sub: "Direct booking discount" },
                  { icon: Phone, label: "24/7 Support", sub: "We're here to help" },
                ].map(({ icon: Icon, label, sub }) => (
                  <div key={label} className="flex flex-col items-center gap-2">
                    <Icon size={28} weight="fill" className="text-blue-200" />
                    <span className="font-semibold text-sm">{label}</span>
                    <span className="text-xs text-blue-200">{sub}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </>
      )}

      {/* ROOM SELECTION (Step 1) */}
      {step === STEPS.ROOMS && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="room-selection">
          {/* Search summary bar */}
          <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6 flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2 text-sm">
              <CalendarBlank size={16} className="text-[#006CE4]" />
              <span className="font-medium text-slate-700">{new Date(checkIn).toLocaleDateString("en-GB", { day: "numeric", month: "short" })} — {new Date(checkOut).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</span>
              <span className="text-slate-400">({nights} night{nights !== 1 ? "s" : ""})</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Users size={16} className="text-[#006CE4]" />
              <span className="font-medium text-slate-700">{adults} adult{adults !== 1 ? "s" : ""}{children > 0 ? `, ${children} child${children !== 1 ? "ren" : ""}` : ""}</span>
            </div>
            <button onClick={() => setStep(STEPS.SEARCH)} className="ml-auto text-[#006CE4] text-sm font-semibold hover:underline" data-testid="change-search-btn">Change search</button>
          </div>

          <h2 className="text-2xl font-semibold text-slate-900 mb-6" style={{ fontFamily: "Outfit, sans-serif" }}>
            Available rooms for {property?.name}
          </h2>

          {loading ? (
            <div className="flex justify-center py-20">
              <div className="w-10 h-10 border-4 border-[#006CE4] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : rooms.length === 0 ? (
            <div className="text-center py-20 bg-white rounded-lg border border-gray-200">
              <Bed size={48} className="mx-auto text-slate-300 mb-4" />
              <h3 className="text-lg font-semibold text-slate-700">No rooms available</h3>
              <p className="text-slate-500 mt-1">Try different dates or check back later</p>
            </div>
          ) : (
            <div className="space-y-4">
              {rooms.map((room) => (
                <div key={room.id} className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow" data-testid={`room-card-${room.id}`}>
                  <div className="flex flex-col md:flex-row">
                    {/* Room Image */}
                    <div className="md:w-72 h-48 md:h-auto bg-slate-200 flex-shrink-0 relative overflow-hidden">
                      {room.photos?.[0] ? (
                        <img src={room.photos[0]} alt={room.name} className="w-full h-full object-cover" loading="lazy" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center"><Bed size={48} className="text-slate-300" /></div>
                      )}
                    </div>
                    {/* Room Info */}
                    <div className="flex-1 p-5">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="text-xl font-semibold text-[#006CE4]" style={{ fontFamily: "Outfit, sans-serif" }}>{room.name}</h3>
                          <div className="flex items-center gap-3 text-sm text-slate-500 mt-1">
                            <span className="flex items-center gap-1"><Users size={14} /> {room.max_guests} guests</span>
                            <span className="flex items-center gap-1"><Bed size={14} /> {room.bed_type} bed</span>
                            {room.size_sqm > 0 && <span>{room.size_sqm} m&sup2;</span>}
                          </div>
                        </div>
                        {room.available_rooms <= 3 && room.available_rooms > 0 && (
                          <span className="text-sm font-semibold text-[#D32F2F] flex items-center gap-1 flex-shrink-0" data-testid={`urgency-${room.id}`}>
                            <Lightning size={14} weight="fill" />
                            Only {room.available_rooms} left on our site!
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-600 mb-3 line-clamp-2">{room.description}</p>
                      <div className="flex flex-wrap gap-2 mb-4">
                        {room.amenities?.slice(0, 6).map((a) => {
                          const Icon = amenityIcons[a];
                          return (
                            <span key={a} className="text-xs text-slate-600 flex items-center gap-1">
                              {Icon ? <Icon size={12} className="text-[#006CE4]" /> : <Check size={12} className="text-[#008009]" />}
                              {a}
                            </span>
                          );
                        })}
                      </div>
                      {/* Badges */}
                      <div className="flex flex-wrap gap-2 mb-4">
                        {room.free_cancellation && (
                          <span className="bg-green-50 text-[#008009] border border-green-200 text-xs font-semibold px-2.5 py-1 rounded flex items-center gap-1">
                            <CheckCircle size={13} weight="fill" /> Free cancellation
                          </span>
                        )}
                        {room.breakfast_included && (
                          <span className="bg-green-50 text-[#008009] border border-green-200 text-xs font-semibold px-2.5 py-1 rounded flex items-center gap-1">
                            <CheckCircle size={13} weight="fill" /> Breakfast included
                          </span>
                        )}
                      </div>
                    </div>
                    {/* Price & CTA */}
                    <div className="md:w-56 p-5 bg-[#F5F7FA] border-l border-gray-200 flex flex-col justify-between">
                      <div>
                        <div className="text-xs text-slate-500 mb-1">{nights} night{nights !== 1 ? "s" : ""}, {adults} adult{adults !== 1 ? "s" : ""}</div>
                        <div className="text-3xl font-bold text-slate-900">&pound;{(room.base_price * nights * roomCount).toFixed(0)}</div>
                        <div className="text-xs text-slate-500 mt-0.5">Includes taxes and fees</div>
                      </div>
                      <button
                        onClick={() => handleSelectRoom(room)}
                        disabled={!room.is_available}
                        className={`mt-4 w-full py-3 rounded-lg font-semibold text-sm transition-colors ${
                          room.is_available
                            ? "bg-[#006CE4] text-white hover:bg-[#0056B3] shadow-lg shadow-blue-500/20"
                            : "bg-slate-200 text-slate-400 cursor-not-allowed"
                        }`}
                        data-testid={`select-room-${room.id}`}
                      >
                        {room.is_available ? "Reserve" : "Sold out"}
                      </button>
                      <div className="mt-2 text-center text-[10px] text-slate-400 flex items-center justify-center gap-1">
                        <Lock size={10} /> Secure booking
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* GUEST DETAILS (Step 2) */}
      {step === STEPS.DETAILS && selectedRoom && (
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="guest-details-step">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Form */}
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h2 className="text-xl font-semibold text-slate-900 mb-6 flex items-center gap-2" style={{ fontFamily: "Outfit, sans-serif" }}>
                  <User size={22} className="text-[#006CE4]" />
                  Your Details
                </h2>
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-1 block">Full Name *</label>
                    <div className="relative">
                      <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="text"
                        value={guestForm.guest_name}
                        onChange={(e) => setGuestForm(p => ({ ...p, guest_name: e.target.value }))}
                        placeholder="John Smith"
                        className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 focus:ring-2 focus:ring-[#006CE4] focus:border-transparent"
                        data-testid="guest-name-input"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-1 block">Email Address *</label>
                    <div className="relative">
                      <EnvelopeSimple size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="email"
                        value={guestForm.guest_email}
                        onChange={(e) => setGuestForm(p => ({ ...p, guest_email: e.target.value }))}
                        placeholder="john@example.com"
                        className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 focus:ring-2 focus:ring-[#006CE4] focus:border-transparent"
                        data-testid="guest-email-input"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-1 block">Phone Number</label>
                    <div className="relative">
                      <Phone size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="tel"
                        value={guestForm.guest_phone}
                        onChange={(e) => setGuestForm(p => ({ ...p, guest_phone: e.target.value }))}
                        placeholder="+44 7XXX XXXXXX"
                        className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 focus:ring-2 focus:ring-[#006CE4] focus:border-transparent"
                        data-testid="guest-phone-input"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-1 block">Special Requests</label>
                    <textarea
                      value={guestForm.special_requests}
                      onChange={(e) => setGuestForm(p => ({ ...p, special_requests: e.target.value }))}
                      placeholder="Any special requirements? (e.g., late check-in, extra pillows)"
                      rows={3}
                      className="w-full border border-gray-300 rounded-lg px-3 py-3 focus:ring-2 focus:ring-[#006CE4] focus:border-transparent resize-none"
                      data-testid="special-requests-input"
                    />
                  </div>
                </div>
              </div>

              {/* Complete Booking Button */}
              <button
                onClick={handleBooking}
                disabled={bookingLoading || !guestForm.guest_name || !guestForm.guest_email}
                className="w-full bg-[#006CE4] text-white py-4 rounded-lg font-bold text-lg hover:bg-[#0056B3] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3 shadow-xl shadow-blue-500/20"
                data-testid="complete-booking-btn"
              >
                {bookingLoading ? (
                  <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <Lock size={20} weight="fill" />
                    Complete Booking
                  </>
                )}
              </button>
              <p className="text-center text-xs text-slate-400 flex items-center justify-center gap-1 mt-2">
                <ShieldCheck size={14} weight="fill" className="text-green-500" />
                Your personal data is protected by SSL encryption
              </p>
            </div>

            {/* Booking Summary Sidebar */}
            <div className="lg:col-span-1">
              <div className="bg-white rounded-lg border border-gray-200 p-5 sticky top-20" data-testid="booking-summary">
                <h3 className="font-semibold text-slate-900 mb-4" style={{ fontFamily: "Outfit, sans-serif" }}>Booking Summary</h3>
                <div className="flex gap-3 mb-4 pb-4 border-b border-gray-100">
                  <div className="w-20 h-16 rounded-lg bg-slate-200 overflow-hidden flex-shrink-0">
                    {selectedRoom.photos?.[0] ? (
                      <img src={selectedRoom.photos[0]} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center"><Bed size={20} className="text-slate-300" /></div>
                    )}
                  </div>
                  <div>
                    <div className="font-semibold text-sm text-slate-900">{selectedRoom.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{property?.name}</div>
                  </div>
                </div>
                <div className="space-y-2 text-sm mb-4 pb-4 border-b border-gray-100">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Check-in</span>
                    <span className="font-medium text-slate-800">{new Date(checkIn).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Check-out</span>
                    <span className="font-medium text-slate-800">{new Date(checkOut).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Duration</span>
                    <span className="font-medium text-slate-800">{nights} night{nights !== 1 ? "s" : ""}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Guests</span>
                    <span className="font-medium text-slate-800">{adults} adult{adults !== 1 ? "s" : ""}{children > 0 ? `, ${children} child${children !== 1 ? "ren" : ""}` : ""}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Rooms</span>
                    <span className="font-medium text-slate-800">{roomCount}</span>
                  </div>
                </div>
                <div className="space-y-2 text-sm mb-4 pb-4 border-b border-gray-100">
                  <div className="flex justify-between">
                    <span className="text-slate-500">&pound;{selectedRoom.base_price} x {nights} night{nights !== 1 ? "s" : ""}{roomCount > 1 ? ` x ${roomCount} rooms` : ""}</span>
                    <span className="text-slate-800">&pound;{totalPrice.toFixed(0)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Taxes & fees</span>
                    <span className="text-slate-800">Included</span>
                  </div>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="font-semibold text-slate-900">Total</span>
                  <span className="text-2xl font-bold text-slate-900">&pound;{totalPrice.toFixed(0)}</span>
                </div>
                {selectedRoom.free_cancellation && (
                  <div className="mt-3 bg-green-50 border border-green-200 rounded-lg p-3 text-xs text-[#008009] font-medium flex items-center gap-1.5">
                    <CheckCircle size={14} weight="fill" /> Free cancellation available
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CONFIRMATION (Step 3) */}
      {step === STEPS.CONFIRM && confirmation && (
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12" data-testid="confirmation-step">
          <div className="bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden">
            {/* Success Header */}
            <div className="bg-[#008009] text-white px-8 py-6 text-center">
              <CheckCircle size={48} weight="fill" className="mx-auto mb-3" />
              <h2 className="text-2xl font-bold mb-1" style={{ fontFamily: "Outfit, sans-serif" }}>Booking Confirmed!</h2>
              <p className="text-green-100">Your reservation has been successfully created</p>
            </div>
            {/* Booking Details */}
            <div className="p-8">
              <div className="bg-[#F5F7FA] rounded-lg p-5 mb-6 text-center">
                <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Booking Reference</div>
                <div className="text-3xl font-bold text-[#0A4297] tracking-wider" data-testid="booking-ref">{confirmation.booking_ref}</div>
                <p className="text-xs text-slate-500 mt-2">Please save this reference number for your records</p>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-slate-500 block mb-0.5">Guest Name</span>
                  <span className="font-semibold text-slate-800" data-testid="confirm-guest-name">{confirmation.guest_name}</span>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Email</span>
                  <span className="font-semibold text-slate-800">{confirmation.guest_email}</span>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Check-in</span>
                  <span className="font-semibold text-slate-800">{new Date(confirmation.check_in).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</span>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Check-out</span>
                  <span className="font-semibold text-slate-800">{new Date(confirmation.check_out).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</span>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Guests</span>
                  <span className="font-semibold text-slate-800">{confirmation.adults} adult{confirmation.adults !== 1 ? "s" : ""}{confirmation.children > 0 ? `, ${confirmation.children} children` : ""}</span>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Total Price</span>
                  <span className="font-semibold text-slate-800 text-lg">&pound;{confirmation.total_price?.toFixed(0)}</span>
                </div>
              </div>
              {confirmation.special_requests && (
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <span className="text-slate-500 text-sm block mb-0.5">Special Requests</span>
                  <span className="text-sm text-slate-800">{confirmation.special_requests}</span>
                </div>
              )}
              <div className="mt-6 pt-6 border-t border-gray-100 flex justify-center gap-3">
                <button
                  onClick={() => { setStep(STEPS.SEARCH); setSelectedRoom(null); setConfirmation(null); setGuestForm({ guest_name: "", guest_email: "", guest_phone: "", special_requests: "" }); }}
                  className="bg-[#006CE4] text-white px-6 py-3 rounded-lg font-semibold hover:bg-[#0056B3] transition-colors"
                  data-testid="book-another-btn"
                >
                  Book Another Room
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Mobile Sticky Book Now Bar */}
      {step === STEPS.SEARCH && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg p-3 sm:hidden z-50" data-testid="mobile-sticky-bar">
          <button
            onClick={searchRooms}
            className="w-full bg-[#006CE4] text-white py-3.5 rounded-lg font-bold text-base flex items-center justify-center gap-2"
          >
            <MagnifyingGlass size={18} weight="bold" />
            Search Rooms
          </button>
        </div>
      )}

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 py-8 text-center text-sm">
        <div className="max-w-7xl mx-auto px-4">
          <p>Powered by <span className="text-white font-semibold">MyHotelBox</span> Booking Engine</p>
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
