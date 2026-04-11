import { useState, useEffect } from "react";
import {
  PresentationChart, UsersThree, Crown, Desktop, Door,
  Confetti, Car, FlowerLotus, Clock, Users, CheckCircle, X,
} from "@phosphor-icons/react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ICONS = {
  "presentation-chart": PresentationChart, "users": UsersThree, "crown": Crown,
  "desktop": Desktop, "door": Door, "confetti": Confetti,
  "car": Car, "flower-lotus": FlowerLotus,
};

const CATEGORY_LABELS = {
  business: "Business", workspace: "Workspace", events: "Events",
  parking: "Parking", wellness: "Wellness",
};

export function SpaceBookingSection({ propertyId, tmpl }) {
  const [spaces, setSpaces] = useState([]);
  const [selectedSpace, setSelectedSpace] = useState(null);
  const [form, setForm] = useState({ guest_name: "", guest_email: "", guest_phone: "", booking_date: "", start_time: "09:00", end_time: "10:00", notes: "" });
  const [submitted, setSubmitted] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/spaces/${propertyId}`)
      .then(r => r.json()).then(setSpaces).catch(() => {});
  }, [propertyId]);

  if (spaces.length === 0) return null;

  const handleBook = async () => {
    if (!form.guest_name || !form.guest_email || !form.booking_date) { setError("Please fill required fields"); return; }
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({
        property_id: propertyId, space_id: selectedSpace.id, guest_name: form.guest_name,
        guest_email: form.guest_email, guest_phone: form.guest_phone, booking_date: form.booking_date,
        start_time: form.start_time, end_time: form.end_time, notes: form.notes,
      });
      const res = await fetch(`${API}/spaces/book?${params}`, { method: "POST" });
      if (!res.ok) { const d = await res.json(); setError(d.detail); return; }
      const data = await res.json();
      setSubmitted(data);
    } catch { setError("Failed to book. Please try again."); }
    finally { setLoading(false); }
  };

  const categories = [...new Set(spaces.map(s => s.category))];

  // Calculate hours and price for selected space
  const calcHoursPrice = () => {
    if (!selectedSpace || !form.start_time || !form.end_time) return { hours: 0, price: 0 };
    const [sh, sm] = form.start_time.split(":").map(Number);
    const [eh, em] = form.end_time.split(":").map(Number);
    const hours = Math.max(0, (eh * 60 + em - sh * 60 - sm) / 60);
    let price = selectedSpace.hourly_rate * hours;
    if (hours >= 8 && selectedSpace.full_day_rate) price = selectedSpace.full_day_rate;
    else if (hours >= 4 && selectedSpace.half_day_rate) price = selectedSpace.half_day_rate;
    return { hours: Math.round(hours * 10) / 10, price: Math.round(price) };
  };

  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12" data-testid="space-booking-section">
      <h2 className="text-2xl font-semibold text-slate-900 mb-2" style={{ fontFamily: tmpl.fonts.heading }}>
        Book a Space by the Hour
      </h2>
      <p className="text-slate-500 text-sm mb-6">Meeting rooms, coworking desks, event halls, and more</p>

      {/* Space Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {spaces.map(space => {
          const Icon = ICONS[space.icon] || PresentationChart;
          const isSelected = selectedSpace?.id === space.id;
          return (
            <button key={space.id} onClick={() => { setSelectedSpace(space); setSubmitted(null); setError(""); }}
              className="bg-white border-2 rounded-xl p-4 text-left transition-all hover:shadow-md"
              style={{ borderColor: isSelected ? tmpl.colors.accent : "#e5e7eb", borderRadius: tmpl.borderRadius }}
              data-testid={`space-${space.id}`}>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ background: isSelected ? `${tmpl.colors.accent}15` : "#f1f5f9" }}>
                  <Icon size={22} weight="fill" style={{ color: isSelected ? tmpl.colors.accent : "#64748b" }} />
                </div>
                <div>
                  <span className="text-sm font-semibold text-slate-900 block">{space.name}</span>
                  <span className="text-[10px] text-slate-400 uppercase">{CATEGORY_LABELS[space.category] || space.category}</span>
                </div>
              </div>
              <div className="flex items-end justify-between mt-2">
                <div>
                  <span className="text-lg font-bold text-slate-900">&pound;{space.hourly_rate}</span>
                  <span className="text-xs text-slate-500">/hr</span>
                </div>
                <span className="text-xs text-slate-400 flex items-center gap-1"><Users size={11} /> {space.capacity}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Booking Form */}
      {selectedSpace && !submitted && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 max-w-2xl mx-auto" style={{ borderRadius: tmpl.borderRadius }} data-testid="space-booking-form">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-900">Book: {selectedSpace.name}</h3>
            <button onClick={() => setSelectedSpace(null)} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Name *</label>
              <input value={form.guest_name} onChange={e => setForm(p => ({ ...p, guest_name: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" data-testid="space-guest-name" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Email *</label>
              <input type="email" value={form.guest_email} onChange={e => setForm(p => ({ ...p, guest_email: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" data-testid="space-guest-email" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Date *</label>
              <input type="date" value={form.booking_date} onChange={e => setForm(p => ({ ...p, booking_date: e.target.value }))}
                min={new Date().toISOString().split("T")[0]}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" data-testid="space-booking-date" />
            </div>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="text-xs font-medium text-slate-700 block mb-1">From</label>
                <input type="time" value={form.start_time} onChange={e => setForm(p => ({ ...p, start_time: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" data-testid="space-start-time" />
              </div>
              <div className="flex-1">
                <label className="text-xs font-medium text-slate-700 block mb-1">To</label>
                <input type="time" value={form.end_time} onChange={e => setForm(p => ({ ...p, end_time: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" data-testid="space-end-time" />
              </div>
            </div>
          </div>
          {/* Price Preview */}
          {(() => {
            const { hours, price } = calcHoursPrice();
            return hours > 0 ? (
              <div className="mt-4 bg-slate-50 rounded-lg p-3 flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-slate-600">
                  <Clock size={16} /> {hours} {hours === 1 ? "hour" : "hours"}
                </div>
                <span className="text-xl font-bold text-slate-900">&pound;{price}</span>
              </div>
            ) : null;
          })()}
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
          <button onClick={handleBook} disabled={loading}
            className="w-full mt-4 text-white py-3 rounded-lg font-semibold text-sm transition-colors disabled:opacity-50"
            style={{ background: tmpl.colors.accent, borderRadius: tmpl.borderRadius }}
            data-testid="book-space-btn">
            {loading ? "Booking..." : `Book Now — £${calcHoursPrice().price}`}
          </button>
        </div>
      )}

      {/* Confirmation */}
      {submitted && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-6 max-w-md mx-auto text-center" style={{ borderRadius: tmpl.borderRadius }} data-testid="space-booking-confirmed">
          <CheckCircle size={36} weight="fill" className="text-emerald-600 mx-auto mb-3" />
          <h3 className="font-bold text-slate-900 mb-1">Space Booked!</h3>
          <p className="text-sm text-slate-600 mb-3">{submitted.space_name} on {submitted.booking_date}</p>
          <div className="text-sm text-slate-500 space-y-1">
            <p>{submitted.start_time} — {submitted.end_time} ({submitted.hours}h)</p>
            <p className="font-bold text-slate-900">&pound;{submitted.total_price}</p>
          </div>
          <button onClick={() => { setSelectedSpace(null); setSubmitted(null); }}
            className="mt-4 text-sm font-semibold hover:underline" style={{ color: tmpl.colors.accent }}>
            Book another space
          </button>
        </div>
      )}
    </section>
  );
}
