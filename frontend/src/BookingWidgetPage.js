import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
import ConciergeChat from "./components/ConciergeChat";
import { Calendar } from "./components/ui/calendar";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v, c) => `${c === "GBP" ? "£" : c === "EUR" ? "€" : c === "USD" ? "$" : c}${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

function SocialProofBadge({ propertyId }) {
  const [messages, setMessages] = useState([]);
  const [idx, setIdx] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let mounted = true;
    axios.get(`${API}/booking-widget/social-proof/${propertyId}`).then(({ data }) => {
      if (!mounted) return;
      const msgs = [];
      if (data.bookings_24h > 0) msgs.push({ icon: "🔥", text: `${data.bookings_24h} booking${data.bookings_24h > 1 ? "s" : ""} in the last 24 hours` });
      else if (data.bookings_7d > 0) msgs.push({ icon: "🔥", text: `${data.bookings_7d} booking${data.bookings_7d > 1 ? "s" : ""} this week` });
      if (data.last_booking_minutes_ago != null) {
        const m = data.last_booking_minutes_ago;
        const ago = m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} hour${Math.round(m / 60) > 1 ? "s" : ""} ago` : `${Math.round(m / 1440)} day${Math.round(m / 1440) > 1 ? "s" : ""} ago`;
        msgs.push({ icon: "🛎️", text: `Last booking made ${ago}` });
      }
      if (data.viewing_now > 1) msgs.push({ icon: "👀", text: `${data.viewing_now} people viewed this hotel in the last 30 min` });
      if (data.review_snippet?.text) msgs.push({ icon: "⭐", text: `"${data.review_snippet.text}${data.review_snippet.text.length >= 110 ? "…" : ""}" — ${data.review_snippet.guest_name}` });
      setMessages(msgs);
    }).catch(() => {});
    return () => { mounted = false; };
  }, [propertyId]);

  useEffect(() => {
    if (messages.length < 2) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % messages.length), 7000);
    return () => clearInterval(t);
  }, [messages]);

  if (dismissed || messages.length === 0) return null;
  const m = messages[idx];
  return (
    <div className="fixed bottom-4 left-4 z-40 max-w-xs" data-testid="be-social-proof-badge">
      <AnimatePresence mode="wait">
        <motion.div key={idx} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.35 }}
          className="bg-white/95 backdrop-blur border border-stone-200 shadow-lg rounded-xl px-4 py-3 flex items-start gap-2.5">
          <span className="text-lg leading-none mt-0.5">{m.icon}</span>
          <p className="text-xs text-stone-700 leading-snug flex-1">{m.text}</p>
          <button onClick={() => setDismissed(true)} data-testid="be-social-proof-dismiss"
            className="text-stone-300 hover:text-stone-500 text-sm leading-none" aria-label="Dismiss">×</button>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function WaitlistJoinCard({ propertyId, checkIn, checkOut, guests }) {
  const [form, setForm] = useState({ guest_name: "", email: "" });
  const [state, setState] = useState("idle"); // idle | saving | done

  const join = async () => {
    if (!form.guest_name.trim() || !form.email.includes("@")) return;
    setState("saving");
    try {
      await axios.post(`${API}/waitlist/${propertyId}/join`, {
        guest_name: form.guest_name.trim(), email: form.email.trim(),
        check_in: checkIn, check_out: checkOut, guests,
      });
      setState("done");
    } catch { setState("idle"); }
  };

  if (state === "done") {
    return (
      <div className="max-w-md mx-auto bg-emerald-50 border border-emerald-200 rounded-xl p-5 text-left" data-testid="be-waitlist-done">
        <p className="text-sm font-semibold text-emerald-800">✓ You're on the waitlist!</p>
        <p className="text-xs text-emerald-700 mt-1">If a room opens up for {checkIn} → {checkOut}, we'll email you a priority booking link right away.</p>
      </div>
    );
  }
  return (
    <div className="max-w-md mx-auto bg-amber-50 border border-amber-200 rounded-xl p-5 text-left" data-testid="be-waitlist-card">
      <p className="text-sm font-semibold text-stone-800 mb-1">Join the waitlist</p>
      <p className="text-xs text-stone-500 mb-3">If a cancellation opens up your dates, you'll get an email with a priority booking link.</p>
      <div className="space-y-2">
        <input value={form.guest_name} onChange={e => setForm(f => ({ ...f, guest_name: e.target.value }))}
          placeholder="Your name" data-testid="be-waitlist-name"
          className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
        <input value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
          placeholder="Email address" type="email" data-testid="be-waitlist-email"
          className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
        <button onClick={join} disabled={state === "saving" || !form.guest_name.trim() || !form.email.includes("@")}
          data-testid="be-waitlist-join-btn"
          className="w-full px-3 py-2 text-sm font-semibold text-white bg-amber-600 hover:bg-amber-700 rounded-lg disabled:opacity-50">
          {state === "saving" ? "Joining…" : "Notify me when available"}
        </button>
      </div>
    </div>
  );
}

export default function BookingWidgetPage({ propertyId }) {
  const [hotel, setHotel] = useState({ hotel_name: "Hotel", rooms: [], currency: "GBP", logo_url: "", reviews: [], avg_rating: 0, review_count: 0, theme: {} });
  const [step, setStep] = useState("home");
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [guests, setGuests] = useState(2);
  const [children, setChildren] = useState(0);
  const [roomCount, setRoomCount] = useState(1);
  const [available, setAvailable] = useState([]);
  const [selected, setSelected] = useState(null);
  const [searching, setSearching] = useState(false);
  const [booking, setBooking] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const [form, setForm] = useState({ guest_name: "", guest_email: "", guest_phone: "", special_requests: "" });
  const [loyalty, setLoyalty] = useState(null);  // { is_member, tier, discount_pct, message }
  const [loyaltyChecking, setLoyaltyChecking] = useState(false);
  const [ecoBadge, setEcoBadge] = useState(null);  // { score, grade, show_badge, highlight_initiatives[] }
  const [carbonOffset, setCarbonOffset] = useState({ opt_in: false, total_fee: 0, co2_kg: 0 });
  const [coupon, setCoupon] = useState({ code: "", applied: null, checking: false, error: null });
  const [absAttrs, setAbsAttrs] = useState([]);
  const [absSelected, setAbsSelected] = useState([]);
  const [ab, setAb] = useState({ assigned: false, variant: null, experiment_id: null, show_badge: true });

  const abSessionId = (() => {
    let sid = localStorage.getItem("be_session_id");
    if (!sid) { sid = crypto.randomUUID(); localStorage.setItem("be_session_id", sid); }
    return sid;
  })();

  useEffect(() => {
    axios.get(`${API}/abs/public/${propertyId}`).then(({ data }) => setAbsAttrs(data.attributes || [])).catch(() => {});
  }, [propertyId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    axios.post(`${API}/ab/assign`, { property_id: propertyId, key: "social_proof_badge", session_id: abSessionId })
      .then(({ data }) => {
        if (data.assigned) {
          setAb({ assigned: true, variant: data.variant, experiment_id: data.experiment_id, show_badge: data.payload?.show !== false });
          localStorage.setItem("be_ab_social_proof_variant", data.variant);
        }
      }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId]);

  const abTrack = (event, value = 0) => {
    if (!ab.assigned) return;
    axios.post(`${API}/ab/track`, { experiment_id: ab.experiment_id, session_id: abSessionId, variant: ab.variant, event, value }).catch(() => {});
  };

  const captureAbandoned = (email) => {
    if (!email || !email.includes("@") || !email.includes(".")) return;
    axios.post(`${API}/booking-widget/abandoned/capture`, {
      session_id: abSessionId, property_id: propertyId,
      guest_email: email, guest_name: form.guest_name,
      check_in: checkIn, check_out: checkOut,
      room_type_id: selected?.room_type_id || selected?.id || "",
      rate: selected?.base_rate || 0,
    }).catch(() => {});
  };

  useEffect(() => {
    if (step !== "details") return;
    const t = setTimeout(() => captureAbandoned(form.guest_email), 1500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.guest_email, form.guest_name, step]);

  const applyCoupon = async (codeOverride) => {
    const code = (typeof codeOverride === "string" ? codeOverride : coupon.code).trim();
    if (!code) return;
    setCoupon(p => ({ ...p, code, checking: true, error: null }));
    try {
      const ni = Math.round((new Date(checkOut) - new Date(checkIn)) / 86400000);
      const { data } = await axios.post(`${API}/direct-conversion/validate`, {
        coupon_code: code,
        booking_value: Number(selected?.total_rate) || 0,
        nights: Number.isFinite(ni) && ni > 0 ? ni : 1,
      });
      if (data.ok) setCoupon(p => ({ ...p, applied: data, checking: false, error: null }));
      else setCoupon(p => ({ ...p, applied: null, checking: false, error: data.reason || "Invalid coupon" }));
    } catch (e) {
      const det = e.response?.data?.detail;
      setCoupon(p => ({ ...p, applied: null, checking: false,
        error: typeof det === "string" ? det : "Coupon could not be validated" }));
    }
  };

  // Deep-link: /book/{property}?coupon=DIRECT-XXX → kuponu otomatik uygula (iter 377)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const c = (params.get("coupon") || "").trim().toUpperCase();
    if (c) applyCoupon(c);
    const rb = (params.get("rebook") || "").trim();
    if (rb) axios.get(`${API}/rebook/token/${rb}`).catch(() => {}); // click tracking
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchCarbonOffset = async (n, r) => {
    if (!ecoBadge?.show_badge) return;
    try {
      const { data } = await axios.get(`${API}/esg/${propertyId}/carbon-offset-quote?nights=${n}&rooms=${r}`);
      setCarbonOffset(prev => ({ ...prev, total_fee: data.total_fee, co2_kg: data.estimated_co2_kg }));
    } catch { /* noop */ }
  };

  const checkLoyalty = async (email) => {
    const e = (email || "").trim();
    if (!e || !e.includes("@")) { setLoyalty(null); return; }
    setLoyaltyChecking(true);
    try {
      const { data } = await axios.post(`${API}/booking-widget/loyalty-check`, { guest_email: e });
      setLoyalty(data?.is_member ? data : null);
    } catch { setLoyalty(null); }
    setLoyaltyChecking(false);
  };
  const [guestOpen, setGuestOpen] = useState(false);
  const [datesOpen, setDatesOpen] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [gallery, setGallery] = useState([]);
  const [lightbox, setLightbox] = useState({ open: false, index: 0 });

  useEffect(() => {
    axios.get(`${API}/booking-widget/info/${propertyId}`).then(r => setHotel(r.data)).catch(() => {});
    axios.get(`${API}/booking-widget/gallery/${propertyId}`).then(r => setGallery(r.data)).catch(() => {});
    axios.get(`${API}/esg/${propertyId}/public-badge`).then(r => setEcoBadge(r.data)).catch(() => {});
    const urlp = new URLSearchParams(window.location.search);
    const pci = urlp.get("checkin"), pco = urlp.get("checkout");
    if (pci && pco && /^\d{4}-\d{2}-\d{2}$/.test(pci) && /^\d{4}-\d{2}-\d{2}$/.test(pco)) {
      setCheckIn(pci); setCheckOut(pco);
    } else {
      const today = new Date();
      const ci = new Date(today); ci.setDate(ci.getDate() + 1);
      const co = new Date(today); co.setDate(co.getDate() + 3);
      setCheckIn(ci.toISOString().split("T")[0]);
      setCheckOut(co.toISOString().split("T")[0]);
    }
  }, [propertyId]);

  const nights = (() => { try { return Math.max(1, Math.round((new Date(checkOut) - new Date(checkIn)) / 86400000)); } catch { return 1; } })();

  useEffect(() => {
    if (selected && nights > 0 && roomCount > 0 && ecoBadge?.show_badge) {
      fetchCarbonOffset(nights, roomCount);
    }
  }, [selected, nights, roomCount, ecoBadge]); // eslint-disable-line react-hooks/exhaustive-deps

  const fmtDate = (d) => { try { return new Date(d + "T00:00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }); } catch { return d; } };

  const [paymentMode, setPaymentMode] = useState("pay_now"); // "pay_now" | "pay_at_property"

  // After Stripe redirects back with ?payment=success or ?payment=cancelled, parse it
  // and either show the confirmed receipt or surface a friendly cancellation banner.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const payment = params.get("payment");
    const ref = params.get("ref");
    if (payment === "success" && ref) {
      // Poll up to 15s for the webhook to flip the booking → confirmed
      let attempts = 0;
      const poll = async () => {
        attempts += 1;
        try {
          const { data } = await axios.get(`${API}/booking-widget/payment-status/${ref}`);
          if (data.status === "confirmed") {
            axios.post(`${API}/booking-widget/abandoned/convert`, { session_id: localStorage.getItem("be_session_id") || "" }).catch(() => {});
            {
              const wlt = new URLSearchParams(window.location.search).get("waitlist");
              if (wlt) axios.post(`${API}/waitlist/convert/${wlt}`, { booking_id: data.id || "" }).catch(() => {});
            }
            const abv = localStorage.getItem("be_ab_social_proof_variant");
            if (abv) axios.post(`${API}/ab/track`, { key: "social_proof_badge", session_id: localStorage.getItem("be_session_id") || "", variant: abv, event: "booking_completed", value: Number(data.total_price || 0) }).catch(() => {});
            setConfirmation({
              status: "confirmed",
              booking_ref: ref,
              booking: data,
              paid: true,
            });
            setStep("confirmed");
            return;
          }
        } catch { /* booking might not be visible yet */ }
        if (attempts < 8) setTimeout(poll, 2000);
        else {
          // Show "Payment received, finalising…" — webhook will catch up shortly
          setConfirmation({ status: "pending", booking_ref: ref, paid: true });
          setStep("confirmed");
        }
      };
      poll();
    } else if (payment === "cancelled" && ref) {
      setConfirmation({ status: "cancelled", booking_ref: ref });
      setStep("confirmed");
    }
    // Clean URL after we've captured the params so a refresh doesn't replay
    if (payment) {
      const cleanUrl = window.location.pathname + window.location.hash;
      window.history.replaceState({}, "", cleanUrl);
    }
  }, []);

  const search = async () => {
    if (!checkIn || !checkOut) return;
    setSearching(true);
    abTrack("check_availability");
    try {
      const { data } = await axios.post(`${API}/booking-widget/check-availability`, { property_id: propertyId, check_in: checkIn, check_out: checkOut });
      setAvailable(data.available_rooms || []);
      setStep("results");
    } catch { /* silent */ }
    setSearching(false);
  };

  const book = async () => {
    if (!form.guest_name || !form.guest_email || !selected) return;
    setBooking(true);
    const discPct = (loyalty?.is_member && loyalty.discount_pct) || 0;
    const finalRate = discPct > 0
      ? Number((selected.base_rate * (1 - discPct / 100)).toFixed(2))
      : selected.base_rate;
    try {
      const { data } = await axios.post(`${API}/booking-widget/book`, {
        property_id: propertyId, room_type: selected.name, check_in: checkIn, check_out: checkOut,
        guest_name: form.guest_name, guest_email: form.guest_email, guest_phone: form.guest_phone,
        special_requests: form.special_requests, rate: finalRate, guests, rooms: roomCount, currency: hotel.currency,
        pay_now: paymentMode === "pay_now",
        loyalty_tier: loyalty?.tier || null,
        loyalty_discount_pct: discPct,
        carbon_offset_opt_in: !!carbonOffset.opt_in,
        carbon_offset_fee: carbonOffset.opt_in ? carbonOffset.total_fee : 0,
        carbon_offset_co2_kg: carbonOffset.opt_in ? carbonOffset.co2_kg : 0,
        coupon_code: coupon.applied ? coupon.applied.coupon_code : null,
        abs_attribute_ids: absSelected,
        origin_url: window.location.origin,
      });
      // Stripe path → redirect immediately (state lost on redirect; OK because effect picks
      // it up on return via ?payment=success&ref=...).
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      // Pay-at-property or fallback path → show confirmation in-place
      abTrack("booking_completed", Number(data?.booking?.total_price || finalRate || 0));
      axios.post(`${API}/booking-widget/abandoned/convert`, { session_id: abSessionId }).catch(() => {});
      {
        const wlt = new URLSearchParams(window.location.search).get("waitlist");
        if (wlt) axios.post(`${API}/waitlist/convert/${wlt}`, { booking_id: data?.booking?.id || "" }).catch(() => {});
      }
      setConfirmation(data);
      setStep("confirmed");
    } catch { /* silent */ }
    setBooking(false);
  };

  const cn = hotel.hotel_name;
  const cc = hotel.currency;
  const theme = hotel.theme || {};
  const ac = theme.accent_color || "#1a3c5e";
  const heroImg = theme.hero_image || "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=1920&q=80";
  const tagline = theme.tagline || "Premium Accommodation";
  const subtitle = theme.subtitle || "Experience exceptional hospitality with our best rate guarantee when you book direct";
  const roomAmenities = ["Free WiFi", "Air Conditioning", "Flat-screen TV", "Private Bathroom", "Daily Housekeeping", "24hr Front Desk"];

  // ─── HEADER ───
  const Header = () => (
    <header className="fixed top-0 left-0 right-0 z-50 transition-all bg-white/95 backdrop-blur-md border-b border-stone-200 shadow-sm" data-testid="be-header">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center text-white font-bold text-sm" style={{ backgroundColor: ac }}>{cn[0]}</div>
          <div>
            <div className="font-semibold text-sm tracking-tight" style={{ color: ac }}>{cn}</div>
            <div className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /><span className="text-[10px] text-emerald-600 font-medium">OFFICIAL SITE</span></div>
          </div>
        </div>
        <nav className="hidden md:flex items-center gap-6 text-sm">
          <button onClick={() => setStep("home")} className="text-stone-600 hover:text-[#1a3c5e] font-medium transition-colors" data-testid="be-nav-home">Home</button>
          <button onClick={() => { setStep("home"); setTimeout(() => document.getElementById("be-rooms")?.scrollIntoView({ behavior: "smooth" }), 100); }} className="text-stone-600 hover:text-[#1a3c5e] font-medium" data-testid="be-nav-rooms">Rooms</button>
          <button onClick={() => search()} className="px-5 py-2 text-white rounded-lg font-medium text-sm hover:opacity-90 transition-colors shadow-sm" style={{ backgroundColor: ac }} data-testid="be-nav-book">Book Now</button>
        </nav>
        <button onClick={() => setMobileMenu(!mobileMenu)} className="md:hidden p-2 text-stone-500" data-testid="be-mobile-menu">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
        </button>
      </div>
      {mobileMenu && <div className="md:hidden border-t border-stone-100 bg-white p-4 space-y-3">
        <button onClick={() => { setStep("home"); setMobileMenu(false); }} className="block w-full text-left text-stone-600 py-2">Home</button>
        <button onClick={() => { search(); setMobileMenu(false); }} className="block w-full py-2.5 bg-[#1a3c5e] text-white rounded-lg text-center font-medium">Book Now</button>
      </div>}
    </header>
  );

  // ─── HERO ───
  const Hero = () => (
    <section className="relative min-h-[85vh] flex items-center justify-center overflow-hidden" data-testid="be-hero">
      <div className="absolute inset-0 bg-gradient-to-b from-[#0a1628]/80 via-[#0a1628]/50 to-[#0a1628]/80 z-10" />
      <div className="absolute inset-0" style={{ backgroundImage: `url('${heroImg}')`, backgroundSize: "cover", backgroundPosition: "center" }} />
      <div className="relative z-20 text-center px-4 max-w-4xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-white/10 backdrop-blur-md rounded-full border border-white/20 mb-6">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-white/90 text-xs font-medium tracking-wide">OFFICIAL WEBSITE — BEST RATE GUARANTEED</span>
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-7xl font-light text-white tracking-tight mb-4" style={{ fontFamily: "'Georgia', serif" }}>{cn}</h1>
          <div className="w-12 h-0.5 bg-amber-400 mx-auto mb-4" />
          <p className="text-white/60 text-sm tracking-[0.2em] uppercase mb-2">{tagline}</p>
          <p className="text-white/80 text-base max-w-lg mx-auto">{subtitle}</p>
        </motion.div>
      </div>
      {/* Booking Bar */}
      <div className="absolute bottom-0 left-0 right-0 z-30 px-4 pb-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="max-w-5xl mx-auto bg-white rounded-2xl shadow-2xl shadow-black/20 p-4 sm:p-5" data-testid="be-booking-bar">
          <div className="flex flex-col sm:flex-row items-stretch gap-3">
            <div className="flex-[2] min-w-0 relative">
              <label className="text-[10px] font-semibold text-stone-400 uppercase tracking-wider mb-1 block">Dates</label>
              <button onClick={() => setDatesOpen(!datesOpen)} data-testid="be-dates-btn"
                className="w-full text-left text-sm font-medium text-stone-800 border border-stone-200 rounded-lg px-3 py-2.5 focus:ring-2 focus:ring-[#1a3c5e]/20 outline-none flex items-center justify-between gap-2">
                <span className={checkIn ? "" : "text-stone-400"}>
                  {checkIn && checkOut ? `${fmtDate(checkIn)} → ${fmtDate(checkOut)}`
                    : checkIn ? `${fmtDate(checkIn)} → check-out seçin`
                    : "Check-in → Check-out"}
                </span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-stone-400 shrink-0"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              </button>
              {datesOpen && (
                <div className="absolute top-full left-0 mt-1 bg-white border border-stone-200 rounded-xl shadow-2xl p-3 z-50" data-testid="be-dates-popover">
                  <Calendar
                    mode="range"
                    numberOfMonths={2}
                    disabled={{ before: new Date() }}
                    selected={{
                      from: checkIn ? new Date(checkIn + "T00:00:00") : undefined,
                      to: checkOut ? new Date(checkOut + "T00:00:00") : undefined,
                    }}
                    onSelect={(range) => {
                      const iso = (d) => d ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}` : "";
                      setCheckIn(iso(range?.from));
                      setCheckOut(iso(range?.to));
                      if (range?.from && range?.to && range.from.getTime() !== range.to.getTime()) setDatesOpen(false);
                    }}
                  />
                  {/* Eski test akışlarıyla uyumluluk için gizli native inputlar */}
                  <div className="flex gap-2 px-2 pb-1">
                    <input type="date" value={checkIn} onChange={e => setCheckIn(e.target.value)} className="flex-1 text-xs border border-stone-200 rounded px-2 py-1" data-testid="be-checkin" />
                    <input type="date" value={checkOut} onChange={e => setCheckOut(e.target.value)} className="flex-1 text-xs border border-stone-200 rounded px-2 py-1" data-testid="be-checkout" />
                  </div>
                </div>
              )}
            </div>
            <div className="flex-1 min-w-0 relative">
              <label className="text-[10px] font-semibold text-stone-400 uppercase tracking-wider mb-1 block">Guests & Rooms</label>
              <button onClick={() => setGuestOpen(!guestOpen)} className="w-full text-left text-sm font-medium text-stone-800 border border-stone-200 rounded-lg px-3 py-2.5" data-testid="be-guests-btn">
                {guests} Adults · {children} Children · {roomCount} Room
              </button>
              {guestOpen && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-stone-200 rounded-xl shadow-xl p-4 z-50" data-testid="be-guests-dropdown">
                  {[{ label: "Adults", val: guests, set: setGuests, min: 1 }, { label: "Children", val: children, set: setChildren, min: 0 }, { label: "Rooms", val: roomCount, set: setRoomCount, min: 1 }].map(g => (
                    <div key={g.label} className="flex items-center justify-between py-2.5 border-b border-stone-100 last:border-0">
                      <span className="text-sm text-stone-700">{g.label}</span>
                      <div className="flex items-center gap-3">
                        <button onClick={() => g.set(Math.max(g.min, g.val - 1))} className="w-8 h-8 rounded-full border border-stone-300 flex items-center justify-center text-stone-500 hover:bg-stone-50">-</button>
                        <span className="text-sm font-semibold w-4 text-center">{g.val}</span>
                        <button onClick={() => g.set(g.val + 1)} className="w-8 h-8 rounded-full border border-stone-300 flex items-center justify-center text-stone-500 hover:bg-stone-50">+</button>
                      </div>
                    </div>
                  ))}
                  <button onClick={() => setGuestOpen(false)} className="w-full mt-3 py-2 bg-[#1a3c5e] text-white rounded-lg text-sm font-medium">Done</button>
                </div>
              )}
            </div>
            <div className="flex-shrink-0 flex items-end">
              <button onClick={search} disabled={searching}
                className="w-full sm:w-auto px-8 py-3 bg-[#1a3c5e] text-white rounded-xl font-semibold text-sm hover:bg-[#0f2a45] transition-all shadow-lg shadow-[#1a3c5e]/30 disabled:opacity-60" data-testid="be-search-btn">
                {searching ? "Searching..." : "CHECK AVAILABILITY"}
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );

  // ─── TRUST BAR ───
  const TrustBar = () => (
    <div className="bg-[#f8f6f3] border-y border-stone-200" data-testid="be-trust-bar">
      <div className="max-w-6xl mx-auto px-4 py-4 flex flex-wrap items-center justify-center gap-x-8 gap-y-2 text-xs text-stone-500">
        {[
          { icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z", text: "Secure SSL Booking" },
          { icon: "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z", text: "Best Price Guarantee" },
          { icon: "M6 18L18 6M6 6l12 12", text: "Free Cancellation" },
          { icon: "M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z", text: "No Prepayment Required" },
          { icon: "M5 13l4 4L19 7", text: "Instant Confirmation" },
        ].map(t => (
          <div key={t.text} className="flex items-center gap-1.5">
            <svg className="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={t.icon} /></svg>
            <span className="font-medium">{t.text}</span>
          </div>
        ))}
      </div>
    </div>
  );

  // ─── ROOMS PREVIEW ───
  const RoomsPreview = () => (
    <section id="be-rooms" className="max-w-6xl mx-auto px-4 py-16" data-testid="be-rooms-section">
      <div className="text-center mb-10">
        <p className="text-xs font-semibold text-[#1a3c5e] uppercase tracking-[0.2em] mb-2">ACCOMMODATION</p>
        <h2 className="text-2xl sm:text-3xl font-light text-stone-800" style={{ fontFamily: "'Georgia', serif" }}>Our Rooms & Suites</h2>
        <div className="w-10 h-0.5 bg-amber-400 mx-auto mt-3" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {(hotel.rooms || []).map((r, i) => (
          <motion.div key={r.id} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }}
            className="group bg-white rounded-2xl overflow-hidden border border-stone-200 hover:shadow-xl transition-all duration-300" data-testid={`be-room-card-${r.id}`}>
            <div className="h-48 bg-gradient-to-br from-stone-200 to-stone-300 relative overflow-hidden">
              <div className="absolute inset-0 bg-cover bg-center group-hover:scale-105 transition-transform duration-500" style={{ backgroundImage: `url('${r.photo || "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=600&q=70"}')` }} />
              <div className="absolute top-3 right-3 bg-white/90 backdrop-blur-sm px-2.5 py-1 rounded-lg shadow-sm">
                <span className="text-xs font-bold" style={{ color: ac }}>From {cur(r.base_rate, cc)}<span className="text-stone-400 font-normal">/night</span></span>
              </div>
            </div>
            <div className="p-5">
              <h3 className="font-semibold text-stone-800 text-base mb-1">{r.name}</h3>
              <p className="text-xs text-stone-500 mb-3 line-clamp-2">{r.description || "Comfortable accommodation with premium amenities"}</p>
              <div className="flex flex-wrap gap-1.5 mb-4">
                {roomAmenities.slice(0, 4).map(a => (
                  <span key={a} className="text-[10px] bg-stone-100 text-stone-500 px-2 py-0.5 rounded-full">{a}</span>
                ))}
              </div>
              <div className="flex items-center justify-between pt-3 border-t border-stone-100">
                <div><span className="text-lg font-bold" style={{ color: ac }}>{cur(r.base_rate, cc)}</span><span className="text-xs text-stone-400"> / night</span></div>
                <button onClick={() => search()} className="px-4 py-2 text-white rounded-lg text-xs font-semibold hover:opacity-90 transition-colors" style={{ backgroundColor: ac }} data-testid={`be-select-room-${r.id}`}>
                  Select Dates
                </button>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );

  // ─── PHOTO GALLERY WITH LIGHTBOX ───
  const GallerySection = () => {
    if (gallery.length === 0) return null;
    const openLB = (i) => setLightbox({ open: true, index: i });
    return (
      <section className="max-w-6xl mx-auto px-4 py-16" data-testid="be-gallery-section">
        <div className="text-center mb-10">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] mb-2" style={{ color: ac }}>GALLERY</p>
          <h2 className="text-2xl sm:text-3xl font-light text-stone-800" style={{ fontFamily: "'Georgia', serif" }}>Explore Our Property</h2>
          <div className="w-10 h-0.5 bg-amber-400 mx-auto mt-3" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 md:gap-3">
          {gallery.slice(0, 6).map((img, i) => (
            <motion.button key={i} onClick={() => openLB(i)} whileHover={{ scale: 1.02 }}
              className={`relative overflow-hidden rounded-xl group ${i === 0 ? "md:col-span-2 md:row-span-2" : ""}`}
              style={{ height: i === 0 ? "100%" : "200px", minHeight: i === 0 ? "300px" : "200px" }}
              data-testid={`be-gallery-img-${i}`}>
              <div className="absolute inset-0 bg-cover bg-center group-hover:scale-110 transition-transform duration-500"
                style={{ backgroundImage: `url('${img.url}')` }} />
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-end">
                <div className="p-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <span className="text-white text-xs font-medium bg-black/40 px-2 py-1 rounded">{img.caption}</span>
                </div>
              </div>
            </motion.button>
          ))}
        </div>
        {gallery.length > 6 && (
          <div className="text-center mt-4">
            <button onClick={() => openLB(0)} className="text-sm font-medium hover:underline" style={{ color: ac }} data-testid="be-gallery-see-all">
              See all {gallery.length} photos
            </button>
          </div>
        )}
      </section>
    );
  };

  // ─── LIGHTBOX OVERLAY ───
  const Lightbox = () => {
    if (!lightbox.open || gallery.length === 0) return null;
    const img = gallery[lightbox.index];
    const prev = () => setLightbox(p => ({ ...p, index: (p.index - 1 + gallery.length) % gallery.length }));
    const next = () => setLightbox(p => ({ ...p, index: (p.index + 1) % gallery.length }));
    return (
      <div className="fixed inset-0 z-[100] bg-black/95 flex items-center justify-center" data-testid="be-lightbox">
        <button onClick={() => setLightbox({ open: false, index: 0 })} className="absolute top-4 right-4 text-white/80 hover:text-white p-2 z-10" data-testid="be-lightbox-close">
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
        <button onClick={prev} className="absolute left-4 text-white/80 hover:text-white p-3 bg-white/10 rounded-full" data-testid="be-lightbox-prev">
          <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
        </button>
        <div className="max-w-5xl max-h-[80vh] mx-4">
          <img src={img?.url} alt={img?.caption} className="max-w-full max-h-[75vh] object-contain rounded-lg mx-auto" data-testid="be-lightbox-image" />
          <div className="text-center mt-3">
            <p className="text-white text-sm">{img?.caption}</p>
            <p className="text-white/50 text-xs mt-1">{lightbox.index + 1} / {gallery.length}</p>
          </div>
        </div>
        <button onClick={next} className="absolute right-4 text-white/80 hover:text-white p-3 bg-white/10 rounded-full" data-testid="be-lightbox-next">
          <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
        </button>
      </div>
    );
  };

  // ─── GUEST REVIEWS ───
  const ReviewsSection = () => {
    const reviews = hotel.reviews || [];
    if (reviews.length === 0) return null;
    const ratingLabel = (r) => r >= 9.5 ? "Exceptional" : r >= 9 ? "Superb" : r >= 8.5 ? "Fabulous" : r >= 8 ? "Very Good" : "Good";
    return (
      <section className="bg-white py-16 border-t border-stone-100" data-testid="be-reviews-section">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-10 gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] mb-2" style={{ color: ac }}>GUEST REVIEWS</p>
              <h2 className="text-2xl sm:text-3xl font-light text-stone-800" style={{ fontFamily: "'Georgia', serif" }}>What Our Guests Say</h2>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <div className="text-white rounded-xl px-4 py-3 text-center" style={{ backgroundColor: ac }}>
                <div className="text-2xl font-bold">{hotel.avg_rating}</div>
                <div className="text-[10px] opacity-80">/10</div>
              </div>
              <div>
                <div className="font-semibold text-stone-800">{ratingLabel(hotel.avg_rating)}</div>
                <div className="text-xs text-stone-400">{hotel.review_count} verified reviews</div>
              </div>
              {ecoBadge?.show_badge && (
                <div className="flex items-center gap-2 ml-2 px-3 py-2 rounded-xl bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-200" data-testid="be-eco-badge">
                  <span className="text-2xl">🌿</span>
                  <div>
                    <div className="text-[10px] uppercase tracking-widest font-bold text-emerald-700">Eco-friendly</div>
                    <div className="text-sm font-black text-emerald-900">ESG {ecoBadge.grade} · {ecoBadge.score}/100</div>
                    {ecoBadge.highlight_initiatives?.length > 0 && (
                      <div className="text-[9px] text-emerald-700">{ecoBadge.highlight_initiatives.slice(0, 2).join(" · ")}</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {reviews.slice(0, 6).map((r, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.06 }}
                className="border border-stone-200 rounded-2xl p-5 bg-white hover:shadow-md transition-all" data-testid={`be-review-${i}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-full flex items-center justify-center text-white font-bold text-sm" style={{ backgroundColor: ac }}>{r.guest_name?.[0] || "G"}</div>
                    <div>
                      <div className="text-sm font-semibold text-stone-800">{r.guest_name}</div>
                      <div className="text-[10px] text-stone-400">{r.country}</div>
                    </div>
                  </div>
                  <div className="text-white text-sm font-bold px-2 py-1 rounded-lg" style={{ backgroundColor: ac }}>{r.rating}</div>
                </div>
                <h4 className="font-semibold text-stone-700 text-sm mb-1">{r.title}</h4>
                <p className="text-xs text-stone-500 leading-relaxed line-clamp-3">{r.comment}</p>
                <div className="text-[10px] text-stone-400 mt-2">{r.date}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    );
  };

  // ─── WHY BOOK DIRECT ───
  const WhyDirect = () => (
    <section className="py-16" style={{ backgroundColor: ac }} data-testid="be-why-direct">
      <div className="max-w-5xl mx-auto px-4">
        <div className="text-center mb-10">
          <p className="text-xs font-semibold text-amber-400 uppercase tracking-[0.2em] mb-2">WHY BOOK DIRECT</p>
          <h2 className="text-2xl sm:text-3xl font-light text-white" style={{ fontFamily: "'Georgia', serif" }}>The Best Rate, Guaranteed</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { title: "Best Price Promise", desc: "Our direct rates are always equal to or lower than any OTA. Find it cheaper and we'll match it.", icon: "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" },
            { title: "Free Cancellation", desc: "Most rates offer free cancellation up to 48 hours before arrival — no questions asked.", icon: "M6 18L18 6M6 6l12 12" },
            { title: "No Hidden Fees", desc: "The price you see is the price you pay. All taxes and charges included upfront.", icon: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" },
          ].map(c => (
            <div key={c.title} className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-center">
              <div className="w-12 h-12 rounded-full bg-amber-400/20 flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={c.icon} /></svg>
              </div>
              <h3 className="font-semibold text-white mb-2">{c.title}</h3>
              <p className="text-sm text-white/60 leading-relaxed">{c.desc}</p>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 mt-8 text-sm text-white/70">
          {["Free cancellation up to 48 hours", "No prepayment required", "Instant confirmation", "Best rate guaranteed"].map(t => (
            <div key={t} className="flex items-center gap-1.5"><svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg><span>{t}</span></div>
          ))}
        </div>
      </div>
    </section>
  );

  // ─── FOOTER ───
  const Footer = () => (
    <footer className="bg-[#0f1f33] text-white/60 py-12" data-testid="be-footer">
      <div className="max-w-5xl mx-auto px-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          <div><h4 className="font-semibold text-white mb-2">{cn}</h4><p className="text-sm">Premium accommodation with the best rate guarantee when you book direct.</p></div>
          <div><h4 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3">Quick Links</h4>
            <div className="space-y-2 text-sm"><button onClick={() => setStep("home")} className="block hover:text-white">Home</button><button onClick={() => search()} className="block hover:text-white">Check Availability</button></div>
          </div>
          <div><h4 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3">Booking Guarantee</h4>
            <div className="space-y-2 text-sm"><p>Best Price Promise</p><p>Free Cancellation</p><p>Secure SSL Payment</p><p>Instant Confirmation</p></div>
          </div>
        </div>
        <div className="border-t border-white/10 pt-6 flex flex-wrap items-center justify-between gap-4 text-xs">
          <span>&copy; {new Date().getFullYear()} {cn}. All rights reserved.</span>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1"><svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>SSL Secured</span>
            <span>Powered by My Hotel Box</span>
          </div>
        </div>
      </div>
    </footer>
  );

  // ─── RESULTS PAGE ───
  const ResultsPage = () => (
    <div className="pt-20 pb-12 min-h-screen bg-[#f8f6f3]" data-testid="be-results-page">
      <div className="max-w-5xl mx-auto px-4">
        <div className="bg-white rounded-2xl border border-stone-200 p-5 mb-6 shadow-sm">
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <div className="flex items-center gap-2"><svg className="w-5 h-5 text-[#1a3c5e]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
              <span className="font-semibold text-stone-800">{fmtDate(checkIn)} — {fmtDate(checkOut)}</span><span className="text-stone-400">({nights} night{nights > 1 ? "s" : ""})</span></div>
            <div className="text-stone-500">{guests} Adults · {children} Children · {roomCount} Room</div>
            <button onClick={() => setStep("home")} className="ml-auto text-[#1a3c5e] font-medium hover:underline text-xs" data-testid="be-modify-search">Modify Search</button>
          </div>
        </div>
        <div className="flex items-center gap-2 mb-4"><span className="text-emerald-600 text-sm font-medium">{available.length} room{available.length !== 1 ? "s" : ""} available</span><span className="text-xs text-stone-400">for your dates</span></div>
        {available.length === 0 ? (
          <div className="bg-white rounded-2xl p-12 text-center border border-stone-200">
            <svg className="w-16 h-16 text-stone-300 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
            <h3 className="text-lg font-semibold text-stone-800 mb-2">No rooms available</h3>
            <p className="text-sm text-stone-500 mb-6">Try different dates or contact us directly.</p>
            <WaitlistJoinCard propertyId={propertyId} checkIn={checkIn} checkOut={checkOut} guests={guests} />
          </div>
        ) : available.map((r, i) => (
          <motion.div key={r.room_type_id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
            className="bg-white rounded-2xl border border-stone-200 mb-4 overflow-hidden hover:shadow-lg transition-all" data-testid={`be-result-room-${r.room_type_id}`}>
            <div className="flex flex-col md:flex-row">
              <div className="md:w-64 h-48 md:h-auto bg-cover bg-center flex-shrink-0" style={{ backgroundImage: `url('${r.photo || "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=400&q=70"}')` }} />
              <div className="flex-1 p-5">
                <div className="flex items-start justify-between mb-2">
                  <div><h3 className="font-semibold text-stone-800 text-lg">{r.name}</h3><p className="text-xs text-stone-500">{r.description}</p></div>
                  <div className="flex-shrink-0 ml-4 text-white px-2.5 py-1 rounded-lg" style={{ backgroundColor: ac }}><span className="text-xs">Score</span><div className="text-sm font-bold">{hotel.avg_rating || "9.2"}</div></div>
                </div>
                <div className="flex flex-wrap gap-1.5 my-3">{roomAmenities.map(a => <span key={a} className="text-[10px] bg-stone-100 text-stone-600 px-2 py-0.5 rounded-full">{a}</span>)}</div>
                <div className="flex items-center gap-3 text-xs text-stone-500 mb-3">
                  <span>Max {r.max_occupancy} guests</span><span>&middot;</span><span>{r.available} room{r.available > 1 ? "s" : ""} left</span>
                  {r.available <= 3 && <span className="text-red-500 font-semibold animate-pulse">Only {r.available} left!</span>}
                </div>
                <div className="flex items-end justify-between pt-3 border-t border-stone-100">
                  <div>
                    <div className="text-xs text-stone-400 line-through">{cur(r.base_rate * 1.15, cc)}</div>
                    <div className="text-2xl font-bold" style={{ color: ac }}>{cur(r.total_rate, cc)}</div>
                    <div className="text-xs text-stone-400">{nights} night{nights > 1 ? "s" : ""} · {cur(r.base_rate, cc)}/night · Includes taxes</div>
                  </div>
                  <div className="text-right">
                    <div className="flex items-center gap-1 mb-1"><svg className="w-3.5 h-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg><span className="text-[10px] text-emerald-600">Free cancellation</span></div>
                    <div className="flex items-center gap-1 mb-2"><svg className="w-3.5 h-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg><span className="text-[10px] text-emerald-600">No prepayment</span></div>
                    <button onClick={() => { setSelected(r); setStep("details"); }} className="px-6 py-2.5 text-white rounded-lg font-semibold text-sm hover:opacity-90 transition-colors shadow-md" style={{ backgroundColor: ac }} data-testid={`be-book-room-${r.room_type_id}`}>
                      Reserve
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );

  // ─── DETAILS / CHECKOUT PAGE ───
  const DetailsPage = () => (
    <div className="pt-20 pb-12 min-h-screen bg-[#f8f6f3]" data-testid="be-details-page">
      <div className="max-w-4xl mx-auto px-4">
        <button onClick={() => setStep("results")} className="flex items-center gap-1 text-sm text-[#1a3c5e] font-medium mb-4 hover:underline" data-testid="be-back-results">
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" /></svg>
          Back to rooms
        </button>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
          <div className="md:col-span-3">
            <div className="bg-white rounded-2xl border border-stone-200 p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-stone-800 mb-1">Your Details</h2>
              <p className="text-xs text-stone-400 mb-5">Please fill in your details to complete the reservation</p>
              <div className="space-y-4">
                <div><label className="text-xs font-semibold text-stone-500 mb-1 block">Full Name *</label>
                  <input value={form.guest_name} onChange={e => setForm({ ...form, guest_name: e.target.value })} className="w-full border border-stone-200 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-[#1a3c5e]/20 focus:border-[#1a3c5e] outline-none" placeholder="John Smith" data-testid="be-guest-name" /></div>
                <div><label className="text-xs font-semibold text-stone-500 mb-1 block">Email Address *</label>
                  <input type="email" value={form.guest_email} onChange={e => setForm({ ...form, guest_email: e.target.value })} onBlur={e => { checkLoyalty(e.target.value); captureAbandoned(e.target.value); }} className="w-full border border-stone-200 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-[#1a3c5e]/20 focus:border-[#1a3c5e] outline-none" placeholder="john@example.com" data-testid="be-guest-email" />
                  {loyaltyChecking && <p className="text-[10px] text-stone-400 mt-1">Checking membership…</p>}
                  {loyalty?.is_member && (
                    <div className="mt-2 rounded-lg bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-300 p-3" data-testid="loyalty-banner">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">{ {standard:"🏨", silver:"🥈", gold:"🥇", platinum:"💎"}[loyalty.tier] || "⭐"}</span>
                        <div className="flex-1">
                          <p className="text-xs font-bold text-amber-900">{loyalty.message}</p>
                          <p className="text-[10px] text-amber-700">{loyalty.lifetime_points?.toLocaleString() || 0} lifetime points · {loyalty.total_stays} stays</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                <div><label className="text-xs font-semibold text-stone-500 mb-1 block">Phone Number</label>
                  <input type="tel" value={form.guest_phone} onChange={e => setForm({ ...form, guest_phone: e.target.value })} className="w-full border border-stone-200 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-[#1a3c5e]/20 focus:border-[#1a3c5e] outline-none" placeholder="+44 7911 123456" data-testid="be-guest-phone" /></div>
                <div><label className="text-xs font-semibold text-stone-500 mb-1 block">Special Requests</label>
                  <textarea value={form.special_requests} onChange={e => setForm({ ...form, special_requests: e.target.value })} rows={3} className="w-full border border-stone-200 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-[#1a3c5e]/20 focus:border-[#1a3c5e] outline-none resize-none" placeholder="Late check-in, extra pillows..." data-testid="be-special-requests" /></div>
              </div>
              {/* Attribute-Based Selling — ücretli oda tercihleri */}
              {absAttrs.length > 0 && (
                <div className="mt-5" data-testid="abs-section">
                  <label className="text-xs font-semibold text-stone-500 mb-2 block">Room Preferences <span className="text-stone-400 font-normal">(paid extras)</span></label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {absAttrs.map(a => { const on = absSelected.includes(a.id); return (
                      <button key={a.id} type="button" data-testid={`abs-attr-${a.id}`}
                        onClick={() => setAbsSelected(p => on ? p.filter(x => x !== a.id) : [...p, a.id])}
                        className={`flex items-center gap-3 p-2.5 rounded-xl border-2 text-left transition-all ${on ? "border-sky-500 bg-sky-50" : "border-stone-200 hover:border-stone-300"}`}>
                        {a.image_url && <img src={a.image_url} alt={a.name} className="w-14 h-14 rounded-lg object-cover flex-shrink-0" />}
                        <span className="flex-1 min-w-0">
                          <span className="text-xs font-bold text-stone-800 block">
                            {a.name}
                            {a.popular && <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[9px] font-bold align-middle" data-testid={`abs-popular-${a.id}`}>Popüler</span>}
                          </span>
                          {a.description && <span className="text-[10px] text-stone-400">{a.description}</span>}
                        </span>
                        <span className="text-xs font-semibold flex-shrink-0 ml-1" style={{ color: ac }}>+{cur(a.price, cc)}/night</span>
                      </button>
                    ); })}
                  </div>
                </div>
              )}
              {/* Payment mode picker — guest chooses Pay Now (Stripe) vs Pay At Property */}
              <div className="mt-5">
                <label className="text-xs font-semibold text-stone-500 mb-2 block">Payment</label>
                <div className="grid grid-cols-2 gap-2">
                  <button type="button" onClick={() => setPaymentMode("pay_now")}
                    data-testid="be-pay-now"
                    className={`flex items-center gap-2 p-3 rounded-xl border-2 text-left transition-all ${paymentMode === "pay_now" ? "border-emerald-500 bg-emerald-50" : "border-stone-200 hover:border-stone-300"}`}>
                    <div className={`w-4 h-4 rounded-full border-2 flex-shrink-0 ${paymentMode === "pay_now" ? "border-emerald-500 bg-emerald-500" : "border-stone-300"}`}>
                      {paymentMode === "pay_now" && <svg className="w-full h-full text-white p-0.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>}
                    </div>
                    <div>
                      <div className="text-xs font-bold text-stone-900">Pay Now · Card</div>
                      <div className="text-[10px] text-stone-500">Secure Stripe checkout</div>
                    </div>
                  </button>
                  <button type="button" onClick={() => setPaymentMode("pay_at_property")}
                    data-testid="be-pay-at-property"
                    className={`flex items-center gap-2 p-3 rounded-xl border-2 text-left transition-all ${paymentMode === "pay_at_property" ? "border-violet-500 bg-violet-50" : "border-stone-200 hover:border-stone-300"}`}>
                    <div className={`w-4 h-4 rounded-full border-2 flex-shrink-0 ${paymentMode === "pay_at_property" ? "border-violet-500 bg-violet-500" : "border-stone-300"}`}>
                      {paymentMode === "pay_at_property" && <svg className="w-full h-full text-white p-0.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>}
                    </div>
                    <div>
                      <div className="text-xs font-bold text-stone-900">Pay at Property</div>
                      <div className="text-[10px] text-stone-500">No charge today</div>
                    </div>
                  </button>
                </div>
              </div>
              <button onClick={book} disabled={booking || !form.guest_name || !form.guest_email}
                className="w-full mt-6 py-3.5 text-white rounded-xl font-semibold text-base hover:opacity-90 transition-colors shadow-lg disabled:opacity-50" style={{ backgroundColor: ac }} data-testid="be-confirm-booking">
                {booking ? "Processing..." : (paymentMode === "pay_now" ? "PROCEED TO PAYMENT" : "COMPLETE BOOKING")}
              </button>
              <div className="flex items-center justify-center gap-4 mt-4 text-[10px] text-stone-400">
                <span className="flex items-center gap-1"><svg className="w-3.5 h-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>SSL Encrypted</span>
                <span>{paymentMode === "pay_now" ? "Powered by Stripe" : "No payment taken now"}</span><span>Free cancellation</span>
              </div>
            </div>
          </div>
          <div className="md:col-span-2">
            <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm sticky top-20">
              <h3 className="font-semibold text-stone-800 mb-3 text-sm">Booking Summary</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between"><span className="text-stone-500">Hotel</span><span className="font-medium text-stone-800">{cn}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Room</span><span className="font-medium text-stone-800">{selected?.name}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Check-in</span><span className="text-stone-700">{fmtDate(checkIn)}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Check-out</span><span className="text-stone-700">{fmtDate(checkOut)}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Duration</span><span className="text-stone-700">{nights} night{nights > 1 ? "s" : ""}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Guests</span><span className="text-stone-700">{guests} adults{children > 0 ? `, ${children} children` : ""}</span></div>
              </div>
              <div className="border-t border-stone-100 mt-4 pt-4">
                <div className="flex justify-between text-xs text-stone-400 mb-1"><span>{nights} night{nights > 1 ? "s" : ""} x {cur(selected?.base_rate, cc)}</span><span>{cur(selected?.total_rate, cc)}</span></div>
                {absSelected.map(id => { const a = absAttrs.find(x => x.id === id); return a ? (
                  <div key={id} className="flex justify-between text-xs text-sky-700 mb-1" data-testid={`abs-line-${id}`}>
                    <span>+ {a.name}</span><span>+{cur(a.price * nights * roomCount, cc)}</span>
                  </div>
                ) : null; })}
                {loyalty?.is_member && loyalty.discount_pct > 0 && (
                  <div className="flex justify-between text-xs text-emerald-600 font-bold mb-1" data-testid="loyalty-line">
                    <span>{(loyalty.tier || "").toUpperCase()} member discount</span>
                    <span>−{loyalty.discount_pct}%</span>
                  </div>
                )}
                {/* Direct booking coupon (iter 376) */}
                <div className="mb-2" data-testid="coupon-section">
                  {coupon.applied ? (
                    <div className="flex justify-between items-center text-xs text-emerald-700 font-bold" data-testid="coupon-applied-line">
                      <span>🎟 {coupon.applied.coupon_code}</span>
                      <span className="flex items-center gap-2">
                        {coupon.applied.discount_label || `−${coupon.applied.discount_pct}%`}
                        <button onClick={() => setCoupon({ code: "", applied: null, checking: false, error: null })}
                          className="text-stone-400 hover:text-red-500 font-normal" data-testid="coupon-remove-btn">✕</button>
                      </span>
                    </div>
                  ) : (
                    <>
                      <div className="flex gap-1.5">
                        <input value={coupon.code}
                          onChange={e => setCoupon(p => ({ ...p, code: e.target.value.toUpperCase(), error: null }))}
                          placeholder="Promo / coupon code"
                          className="flex-1 min-w-0 border border-stone-200 rounded-lg px-2.5 py-1.5 text-xs uppercase focus:outline-none focus:ring-1 focus:ring-emerald-500"
                          data-testid="coupon-input" />
                        <button onClick={applyCoupon} disabled={coupon.checking || !coupon.code.trim()}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white disabled:opacity-40"
                          style={{ backgroundColor: ac }} data-testid="coupon-apply-btn">
                          {coupon.checking ? "..." : "Apply"}
                        </button>
                      </div>
                      {coupon.error && (
                        <div className="text-[10px] text-red-500 mt-1" data-testid="coupon-error">{coupon.error}</div>
                      )}
                    </>
                  )}
                </div>
                {ecoBadge?.show_badge && carbonOffset.total_fee > 0 && (
                  <div className="flex items-center justify-between text-xs text-emerald-700 font-bold mb-1" data-testid="carbon-offset-row">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={carbonOffset.opt_in}
                        onChange={e => setCarbonOffset(p => ({ ...p, opt_in: e.target.checked }))}
                        className="accent-emerald-600" data-testid="carbon-offset-toggle" />
                      <span>🌿 Offset {carbonOffset.co2_kg} kg CO₂</span>
                    </label>
                    <span>+£{carbonOffset.total_fee}</span>
                  </div>
                )}
                <div className="flex justify-between text-xs text-stone-400 mb-1"><span>Taxes & fees</span><span>Included</span></div>
                <div className="flex justify-between"><span className="text-stone-500 font-medium">Total</span><span className="text-2xl font-bold" style={{ color: ac }}>{(() => {
                  let t = selected?.total_rate || 0;
                  if (loyalty?.is_member && loyalty.discount_pct > 0) t = Number((t * (1 - loyalty.discount_pct / 100)).toFixed(2));
                  t += absSelected.reduce((s, id) => s + ((absAttrs.find(x => x.id === id)?.price || 0) * nights * roomCount), 0);
                  if (coupon.applied?.discount_pct) t = Number((t * (1 - coupon.applied.discount_pct / 100)).toFixed(2));
                  if (carbonOffset.opt_in) t += carbonOffset.total_fee;
                  return cur(t, cc);
                })()}</span></div>
              </div>
              <div className="mt-4 space-y-1.5">{["Free cancellation until 48h before", "No prepayment needed", "Instant email confirmation"].map(t => (
                <div key={t} className="flex items-center gap-1.5 text-[10px] text-emerald-600"><svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>{t}</div>
              ))}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // ─── CONFIRMATION PAGE ───
  const ConfirmationPage = () => {
    const isCancelled = confirmation?.status === "cancelled";
    const isPaid = confirmation?.paid || confirmation?.booking?.payment_status === "paid";
    const isPendingWebhook = confirmation?.status === "pending" && confirmation?.paid;
    const guestEmail = confirmation?.booking?.guest_email || form.guest_email;
    const total = confirmation?.booking?.total;
    return (
    <div className="pt-20 pb-12 min-h-screen bg-[#f8f6f3] flex items-center justify-center" data-testid="be-confirmation-page">
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="max-w-lg mx-auto px-4 w-full">
        <div className="bg-white rounded-2xl border border-stone-200 p-8 text-center shadow-lg">
          {isCancelled ? (
            <>
              <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              </div>
              <h2 className="text-xl font-semibold text-stone-800 mb-1">Payment Cancelled</h2>
              <p className="text-sm text-stone-500 mb-6">No charge was made. Your booking <b>{confirmation?.booking_ref}</b> is on hold — try again or contact us.</p>
            </>
          ) : (
            <>
              <div className={`w-16 h-16 rounded-full ${isPendingWebhook ? "bg-cyan-100" : "bg-emerald-100"} flex items-center justify-center mx-auto mb-4`}>
                {isPendingWebhook ? (
                  <svg className="w-8 h-8 text-cyan-600 animate-spin" fill="none" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" strokeWidth="4" stroke="currentColor" strokeDasharray="40" strokeDashoffset="20" /></svg>
                ) : (
                  <svg className="w-8 h-8 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                )}
              </div>
              <h2 className="text-xl font-semibold text-stone-800 mb-1">
                {isPendingWebhook ? "Payment Received" : "Booking Confirmed!"}
                {isPaid && !isPendingWebhook && (
                  <span className="ml-2 text-[10px] font-bold text-emerald-700 bg-emerald-100 border border-emerald-200 rounded-full px-2 py-0.5 uppercase tracking-wide">PAID</span>
                )}
              </h2>
              <p className="text-sm text-stone-500 mb-6">
                {isPendingWebhook
                  ? "Finalising your reservation. A confirmation email will arrive shortly."
                  : `A confirmation email has been sent to ${guestEmail}.`}
              </p>
            </>
          )}
          {!isCancelled && (
            <div className="bg-[#f8f6f3] rounded-xl p-4 mb-6 text-left space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-stone-500">Reference</span><span className="font-bold text-[#1a3c5e] text-base">{confirmation?.booking_ref}</span></div>
              <div className="flex justify-between"><span className="text-stone-500">Hotel</span><span className="font-medium">{cn}</span></div>
              {confirmation?.booking?.room_type && <div className="flex justify-between"><span className="text-stone-500">Room</span><span>{confirmation.booking.room_type}</span></div>}
              <div className="flex justify-between"><span className="text-stone-500">Dates</span><span>{fmtDate(confirmation?.booking?.check_in || checkIn)} — {fmtDate(confirmation?.booking?.check_out || checkOut)}</span></div>
              {total != null && <div className="flex justify-between"><span className="text-stone-500">Total</span><span className="font-bold text-lg">{cur(total, cc)}</span></div>}
            </div>
          )}
          <div className="space-y-1.5 text-xs text-stone-500 mb-6">
            <p>Free cancellation up to 48 hours before arrival</p>
            {isPaid ? <p className="text-emerald-700 font-semibold">Payment processed via Stripe</p> : <p>No prepayment required — pay at property</p>}
          </div>
          <button onClick={() => { setStep("home"); setConfirmation(null); setSelected(null); setForm({ guest_name: "", guest_email: "", guest_phone: "", special_requests: "" }); }}
            className="px-8 py-2.5 bg-[#1a3c5e] text-white rounded-xl font-medium text-sm" data-testid="be-back-home">
            Back to Home
          </button>
        </div>
      </motion.div>
    </div>
    );
  };

  // Embed mode: when the page is loaded inside an <iframe> from a hotel's website,
  // we strip the marketing chrome (header, gallery, reviews, footer) and keep only
  // the booking flow itself. Triggered by `?embed=1` in the URL.
  const isEmbed = (() => {
    if (typeof window === "undefined") return false;
    const p = new URLSearchParams(window.location.search);
    return p.get("embed") === "1" || p.get("embed") === "true";
  })();

  return (
    <div className={`bg-white ${isEmbed ? "" : "min-h-screen"}`} style={{ fontFamily: "'Inter', -apple-system, sans-serif" }} data-testid="booking-engine">
      {!isEmbed && <Header />}
      <AnimatePresence mode="wait">
        {step === "home" && <motion.div key="home" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <Hero />{!isEmbed && <><TrustBar /><RoomsPreview /><GallerySection /><ReviewsSection /><WhyDirect /></>}{!isEmbed && <Footer />}
        </motion.div>}
        {step === "results" && <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }}><ResultsPage />{!isEmbed && <Footer />}</motion.div>}
        {step === "details" && <motion.div key="details" initial={{ opacity: 0 }} animate={{ opacity: 1 }}><DetailsPage />{!isEmbed && <Footer />}</motion.div>}
        {step === "confirmed" && <motion.div key="confirmed" initial={{ opacity: 0 }} animate={{ opacity: 1 }}><ConfirmationPage /></motion.div>}
      </AnimatePresence>
      <Lightbox />
      {!isEmbed && step !== "confirmed" && ab.show_badge && <SocialProofBadge propertyId={propertyId} />}
      {!isEmbed && (
        <ConciergeChat
          propertyId={propertyId}
          hotelName={hotel.hotel_name}
          accentColor={ac}
        />
      )}
    </div>
  );
}

