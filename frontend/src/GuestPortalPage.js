import { useState, useEffect } from "react";
import {
  EnvelopeSimple, ArrowRight, Buildings, Bed, CalendarBlank,
  CheckCircle, SignOut, ArrowsClockwise, MapPin, Users, Receipt,
} from "@phosphor-icons/react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function GuestPortalPage() {
  const params = new URLSearchParams(window.location.search);
  const tokenFromUrl = params.get("token") || "";

  const [email, setEmail] = useState("");
  const [token, setToken] = useState(tokenFromUrl);
  const [verified, setVerified] = useState(false);
  const [guestEmail, setGuestEmail] = useState("");
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [linkSent, setLinkSent] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (tokenFromUrl) verifyToken(tokenFromUrl);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const requestAccess = async () => {
    if (!email.trim()) return;
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API}/guest-portal/request-access?guest_email=${encodeURIComponent(email)}`, { method: "POST" });
      const data = await res.json();
      setLinkSent(true);
      // In dev, auto-verify with returned token
      if (data.token) { setToken(data.token); verifyToken(data.token); }
    } catch { setError("Failed to send. Please try again."); }
    finally { setLoading(false); }
  };

  const verifyToken = async (t) => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/guest-portal/verify?token=${t}`, { method: "POST" });
      if (!res.ok) { const d = await res.json(); setError(d.detail); setLoading(false); return; }
      const data = await res.json();
      setGuestEmail(data.guest_email);
      setVerified(true);
      // Load bookings
      const bRes = await fetch(`${API}/guest-portal/bookings?token=${t}`);
      if (bRes.ok) setBookings(await bRes.json());
    } catch { setError("Invalid or expired link"); }
    finally { setLoading(false); }
  };

  const handleRebook = (booking) => {
    window.location.href = `/book?property=${booking.property_id}&prefill_name=${encodeURIComponent(booking.guest_name)}&prefill_email=${encodeURIComponent(booking.guest_email)}`;
  };

  const logout = () => { setVerified(false); setToken(""); setBookings([]); setGuestEmail(""); setLinkSent(false); };

  const getStatusColor = (status) => {
    const map = { confirmed: "bg-emerald-100 text-emerald-700", completed: "bg-blue-100 text-blue-700", cancelled: "bg-red-100 text-red-700", pending: "bg-amber-100 text-amber-700" };
    return map[status] || "bg-slate-100 text-slate-700";
  };

  // Login Screen
  if (!verified) return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center p-4" data-testid="guest-portal-login">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden">
        <div className="bg-gradient-to-r from-slate-800 to-slate-900 px-6 py-8 text-white text-center">
          <Buildings size={32} weight="fill" className="mx-auto mb-3 opacity-70" />
          <h1 className="text-xl font-bold">Guest Portal</h1>
          <p className="text-sm opacity-70 mt-1">View your bookings and manage your stays</p>
        </div>
        <div className="p-6">
          {linkSent && !token ? (
            <div className="text-center" data-testid="link-sent">
              <div className="w-14 h-14 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <EnvelopeSimple size={28} className="text-blue-600" />
              </div>
              <h2 className="text-lg font-bold text-slate-900 mb-2">Check Your Email</h2>
              <p className="text-sm text-slate-500">We've sent a secure login link to <strong>{email}</strong></p>
              <button onClick={() => setLinkSent(false)} className="text-sm text-blue-600 mt-4 hover:underline">Use a different email</button>
            </div>
          ) : (
            <>
              <h2 className="text-lg font-semibold text-slate-900 mb-1">Sign in with your email</h2>
              <p className="text-sm text-slate-500 mb-5">Enter the email you used when booking</p>
              <div className="relative mb-4">
                <EnvelopeSimple size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input value={email} onChange={e => setEmail(e.target.value)} type="email"
                  placeholder="your.email@example.com"
                  className="w-full border border-gray-200 rounded-xl pl-10 pr-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  onKeyDown={e => e.key === "Enter" && requestAccess()}
                  data-testid="portal-email-input" />
              </div>
              {error && <p className="text-red-500 text-sm mb-3" data-testid="portal-error">{error}</p>}
              <button onClick={requestAccess} disabled={loading || !email.trim()}
                className="w-full bg-slate-900 text-white py-3.5 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-slate-800 transition-colors disabled:opacity-40"
                data-testid="portal-submit-btn">
                {loading ? <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <><ArrowRight size={18} /> Continue</>}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );

  // Dashboard
  const upcoming = bookings.filter(b => new Date(b.check_in) >= new Date() && b.status !== "cancelled");
  const past = bookings.filter(b => new Date(b.check_in) < new Date() || b.status === "cancelled");

  return (
    <div className="min-h-screen bg-slate-50" data-testid="guest-portal-dashboard">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Buildings size={20} weight="fill" className="text-slate-400" />
            <span className="font-semibold text-slate-900">Guest Portal</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-500">{guestEmail}</span>
            <button onClick={logout} className="text-slate-400 hover:text-red-500 transition-colors" data-testid="portal-logout">
              <SignOut size={18} />
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: "Total Bookings", value: bookings.length, icon: Receipt },
            { label: "Upcoming", value: upcoming.length, icon: CalendarBlank },
            { label: "Completed", value: past.filter(b => b.status !== "cancelled").length, icon: CheckCircle },
          ].map(({ label, value, icon: Icon }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex items-center gap-2 mb-1">
                <Icon size={16} className="text-slate-400" />
                <span className="text-xs text-slate-500">{label}</span>
              </div>
              <span className="text-2xl font-bold text-slate-900">{value}</span>
            </div>
          ))}
        </div>

        {/* Upcoming Bookings */}
        {upcoming.length > 0 && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Upcoming Stays</h2>
            <div className="space-y-3">
              {upcoming.map(b => (
                <BookingCard key={b.id || b.booking_ref} booking={b} onRebook={handleRebook} getStatusColor={getStatusColor} isUpcoming />
              ))}
            </div>
          </div>
        )}

        {/* Past Bookings */}
        {past.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Past Stays</h2>
            <div className="space-y-3">
              {past.map(b => (
                <BookingCard key={b.id || b.booking_ref} booking={b} onRebook={handleRebook} getStatusColor={getStatusColor} />
              ))}
            </div>
          </div>
        )}

        {bookings.length === 0 && (
          <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
            <Bed size={48} className="mx-auto text-slate-300 mb-4" />
            <h3 className="text-lg font-semibold text-slate-700">No bookings found</h3>
            <p className="text-slate-500 mt-1">No bookings are associated with this email address</p>
          </div>
        )}
      </div>
    </div>
  );
}

function BookingCard({ booking, onRebook, getStatusColor, isUpcoming }) {
  const b = booking;
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-md transition-shadow" data-testid={`booking-card-${b.booking_ref}`}>
      <div className="flex">
        {b.room_photo ? (
          <div className="w-28 h-28 flex-shrink-0 bg-slate-200">
            <img src={b.room_photo} alt="" className="w-full h-full object-cover" />
          </div>
        ) : (
          <div className="w-28 h-28 flex-shrink-0 bg-slate-100 flex items-center justify-center">
            <Bed size={28} className="text-slate-300" />
          </div>
        )}
        <div className="flex-1 p-4">
          <div className="flex items-start justify-between mb-1">
            <div>
              <h3 className="font-semibold text-slate-900 text-sm">{b.room_name || "Room"}</h3>
              <p className="text-xs text-slate-500 flex items-center gap-1"><MapPin size={11} /> {b.property_name}</p>
            </div>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${getStatusColor(b.status)}`}>{b.status}</span>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-500 mt-2">
            <span className="flex items-center gap-1"><CalendarBlank size={12} /> {new Date(b.check_in).toLocaleDateString("en-GB", { day: "numeric", month: "short" })} — {new Date(b.check_out).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</span>
            <span className="flex items-center gap-1"><Users size={12} /> {b.adults} guest{b.adults !== 1 ? "s" : ""}</span>
            <span className="font-semibold text-slate-800">&pound;{b.total_price?.toFixed(0)}</span>
          </div>
          <div className="flex gap-2 mt-2.5">
            <span className="text-[10px] text-slate-400 font-mono">Ref: {b.booking_ref}</span>
            <button onClick={() => onRebook(b)} className="ml-auto text-xs text-blue-600 font-semibold hover:underline flex items-center gap-1" data-testid={`rebook-${b.booking_ref}`}>
              <ArrowsClockwise size={12} /> {isUpcoming ? "Modify" : "Book Again"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
