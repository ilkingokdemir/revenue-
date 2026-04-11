import { useState } from "react";
import { Users, X, Buildings, CalendarBlank, Phone, EnvelopeSimple, CheckCircle } from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

const EVENT_TYPES = [
  { value: "corporate", label: "Corporate Event" },
  { value: "wedding", label: "Wedding" },
  { value: "conference", label: "Conference" },
  { value: "tour_group", label: "Tour Group" },
  { value: "sports_team", label: "Sports Team" },
  { value: "family_reunion", label: "Family Reunion" },
  { value: "other", label: "Other" },
];

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export function GroupBookingModal({ isOpen, onClose, propertyId, propertyName, tmpl }) {
  const { t } = useLanguage();
  const [form, setForm] = useState({
    contact_name: "", contact_email: "", contact_phone: "", company_name: "",
    event_type: "", check_in: "", check_out: "", total_rooms: 5, total_guests: 10,
    room_preferences: "", special_requirements: "", budget_range: "",
  });
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!form.contact_name || !form.contact_email || !form.check_in || !form.check_out) {
      setError("Please fill in required fields"); return;
    }
    setLoading(true); setError("");
    try {
      const res = await fetch(`${BACKEND_URL}/api/group-booking/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, property_id: propertyId }),
      });
      if (!res.ok) { const d = await res.json(); setError(d.detail); return; }
      setSubmitted(true);
    } catch { setError("Failed to submit. Please try again."); }
    finally { setLoading(false); }
  };

  const update = (field, value) => setForm(p => ({ ...p, [field]: value }));

  if (submitted) return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-md w-full p-8 text-center" onClick={e => e.stopPropagation()} data-testid="group-booking-success">
        <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle size={36} weight="fill" className="text-emerald-600" />
        </div>
        <h2 className="text-xl font-bold text-slate-900 mb-2">Request Submitted!</h2>
        <p className="text-sm text-slate-500 mb-6">Our team will contact you within 24 hours with a custom quote for your group booking at {propertyName}.</p>
        <button onClick={onClose} className="px-6 py-2.5 bg-slate-900 text-white rounded-xl font-semibold text-sm hover:bg-slate-800 transition-colors">Close</button>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="group-booking-modal">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between rounded-t-2xl">
          <div className="flex items-center gap-2">
            <Users size={20} style={{ color: tmpl?.colors?.accent || "#2563eb" }} />
            <h2 className="text-lg font-bold text-slate-900">Group Booking Request</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" data-testid="close-group-modal"><X size={20} /></button>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-sm text-slate-500">Planning a group stay at <strong>{propertyName}</strong>? Fill in the details and our team will prepare a custom quote.</p>

          {/* Contact Info */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Contact Name *</label>
              <input value={form.contact_name} onChange={e => update("contact_name", e.target.value)}
                placeholder="John Smith" className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" data-testid="group-contact-name" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Company</label>
              <input value={form.company_name} onChange={e => update("company_name", e.target.value)}
                placeholder="Acme Corp" className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Email *</label>
              <input value={form.contact_email} onChange={e => update("contact_email", e.target.value)} type="email"
                placeholder="john@company.com" className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" data-testid="group-contact-email" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Phone</label>
              <input value={form.contact_phone} onChange={e => update("contact_phone", e.target.value)}
                placeholder="+44 7XXX XXXXXX" className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" />
            </div>
          </div>

          {/* Event Type */}
          <div>
            <label className="text-xs font-medium text-slate-700 block mb-1">Event Type</label>
            <select value={form.event_type} onChange={e => update("event_type", e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" data-testid="group-event-type">
              <option value="">Select type...</option>
              {EVENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>

          {/* Dates & Numbers */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Check-in *</label>
              <input type="date" value={form.check_in} onChange={e => update("check_in", e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" data-testid="group-checkin" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Check-out *</label>
              <input type="date" value={form.check_out} onChange={e => update("check_out", e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" data-testid="group-checkout" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Total Rooms</label>
              <input type="number" min={1} value={form.total_rooms} onChange={e => update("total_rooms", parseInt(e.target.value) || 1)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" data-testid="group-rooms" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Total Guests</label>
              <input type="number" min={1} value={form.total_guests} onChange={e => update("total_guests", parseInt(e.target.value) || 1)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm" />
            </div>
          </div>

          {/* Special Requirements */}
          <div>
            <label className="text-xs font-medium text-slate-700 block mb-1">Special Requirements</label>
            <textarea value={form.special_requirements} onChange={e => update("special_requirements", e.target.value)}
              placeholder="Meeting rooms, AV equipment, dietary requirements..."
              rows={3} className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm resize-none" data-testid="group-requirements" />
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <button onClick={handleSubmit} disabled={loading}
            className="w-full text-white py-3 rounded-xl font-semibold text-sm transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            style={{ background: tmpl?.colors?.accent || "#2563eb" }}
            data-testid="submit-group-booking-btn">
            {loading ? <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" /> : "Submit Group Booking Request"}
          </button>
        </div>
      </div>
    </div>
  );
}
