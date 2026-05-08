/**
 * Spa & Activity Time-Slot Booking Panel
 * --------------------------------------
 * Manage services and book guests into time slots.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Sparkles, Plus, RefreshCw, X, Clock, CheckCircle2, Trash2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmt = (n) => `£${Number(n || 0).toFixed(2)}`;

export default function TimeSlotsPanel({ propertyId, hotelName = "" }) {
  const today = new Date().toISOString().slice(0, 10);
  const [services, setServices] = useState([]);
  const [activeService, setActiveService] = useState(null);
  const [date, setDate] = useState(today);
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null);
  const [bookSlot, setBookSlot] = useState(null);
  const [bookings, setBookings] = useState([]);

  const loadServices = useCallback(async () => {
    if (!propertyId) return;
    const { data } = await axios.get(`${API}/timeslot-services/${propertyId}`);
    setServices(data || []);
    if (!activeService && data?.length) setActiveService(data[0]);
  }, [propertyId, activeService]);

  const loadAvailability = useCallback(async () => {
    if (!activeService) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/timeslot-services/${propertyId}/${activeService.id}/availability?date=${date}`);
      setSlots(data.slots || []);
    } catch { setSlots([]); }
    setLoading(false);
  }, [propertyId, activeService, date]);

  const loadBookings = useCallback(async () => {
    if (!propertyId) return;
    const { data } = await axios.get(`${API}/timeslot-bookings/${propertyId}?days=7`);
    setBookings(data || []);
  }, [propertyId]);

  useEffect(() => { loadServices(); loadBookings(); }, [loadServices, loadBookings]);
  useEffect(() => { loadAvailability(); }, [loadAvailability]);
  useEffect(() => { setActiveService(null); setSlots([]); setBookings([]); }, [propertyId]);

  const removeService = async (id) => {
    if (!window.confirm("Deactivate service?")) return;
    await axios.delete(`${API}/timeslot-services/${propertyId}/${id}`);
    loadServices();
  };

  const cancel = async (b) => {
    if (!window.confirm(`Cancel ${b.guest_name}'s booking?`)) return;
    await axios.post(`${API}/timeslot-bookings/${b.id}/cancel`);
    toast.success("Cancelled");
    loadBookings(); loadAvailability();
  };

  return (
    <div className="space-y-6" data-testid="timeslots-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-fuchsia-400" />
            <h2 className="text-2xl font-semibold text-stone-100">Spa & Activity Time-Slots</h2>
          </div>
          <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Spa, gym, golf, restaurant, classes — all in one slot engine.</p>
        </div>
        <div className="flex gap-2">
          <button data-testid="ts-refresh-btn" onClick={() => { loadServices(); loadAvailability(); loadBookings(); }}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button data-testid="ts-new-service-btn" onClick={() => setEditing({})}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-fuchsia-500/20 hover:bg-fuchsia-500/30 border border-fuchsia-500/40 text-fuchsia-200 text-sm">
            <Plus className="w-4 h-4" /> New service
          </button>
        </div>
      </div>

      {/* Service tabs */}
      <div className="flex flex-wrap gap-2">
        {services.map((s) => (
          <button key={s.id} data-testid="ts-service-tab" onClick={() => setActiveService(s)}
            className={`px-3 py-2 rounded-lg text-sm border ${activeService?.id === s.id
              ? "bg-fuchsia-500/20 border-fuchsia-500/40 text-fuchsia-200"
              : "bg-stone-800 border-stone-700 text-stone-300 hover:bg-stone-700"}`}>
            <div className="font-medium">{s.name}</div>
            <div className="text-[10px] opacity-70">{s.category} · {s.duration_min}m · {fmt(s.price)}</div>
          </button>
        ))}
        {services.length === 0 && <div className="text-sm text-stone-500">No services yet — create your first one.</div>}
      </div>

      {activeService && (
        <>
          <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <div className="text-stone-100 font-semibold">{activeService.name}</div>
                <div className="text-xs text-stone-400">Capacity {activeService.concurrent_capacity} · {activeService.open_hour}:00 → {activeService.close_hour}:00</div>
              </div>
              <div className="flex gap-2">
                <input data-testid="ts-date" type="date" value={date} onChange={(e) => setDate(e.target.value)}
                  className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
                <button onClick={() => setEditing(activeService)} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300">Edit</button>
                <button onClick={() => removeService(activeService.id)} className="p-1.5 rounded text-stone-500 hover:text-rose-400">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-6 text-stone-500"><Loader2 className="w-5 h-5 animate-spin" /></div>
            ) : (
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
                {slots.map((s) => {
                  const tm = s.start.slice(11, 16);
                  return (
                    <button key={s.start} data-testid="ts-slot" disabled={s.full} onClick={() => setBookSlot({ service: activeService, slot: s })}
                      className={`px-2 py-2 rounded text-xs border ${s.full
                        ? "bg-stone-800/40 border-stone-800 text-stone-600 line-through cursor-not-allowed"
                        : "bg-stone-800 border-stone-700 text-stone-200 hover:bg-fuchsia-500/20 hover:border-fuchsia-500/40"}`}>
                      <div className="font-mono">{tm}</div>
                      <div className="text-[10px] opacity-60">{s.full ? "full" : `${s.available} avail`}</div>
                    </button>
                  );
                })}
                {slots.length === 0 && <div className="col-span-full text-stone-500 text-sm text-center py-6">No slots — service may be closed today.</div>}
              </div>
            )}
          </div>
        </>
      )}

      {/* Recent bookings */}
      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
        <div className="text-stone-100 font-semibold mb-2">Upcoming bookings (7d)</div>
        {bookings.length === 0 ? (
          <div className="text-sm text-stone-500">None.</div>
        ) : (
          <div className="space-y-1">
            {bookings.slice(0, 30).map((b) => (
              <div key={b.id} data-testid="ts-booking-row" className="flex items-center justify-between bg-stone-800/40 rounded px-2 py-1 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-stone-400 font-mono">{b.start.slice(0, 16).replace("T", " ")}</span>
                  <span className="text-stone-200">{b.guest_name}</span>
                  <span className="text-xs text-stone-500">· {b.service_name}</span>
                  {b.status === "cancelled" && <span className="text-[10px] px-1 py-0.5 rounded bg-rose-500/20 text-rose-300">cancelled</span>}
                </div>
                {b.status !== "cancelled" && (
                  <button onClick={() => cancel(b)} className="text-xs px-2 py-0.5 rounded bg-stone-800 hover:bg-rose-500/20 text-stone-300 border border-stone-700">
                    Cancel
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {editing !== null && (
        <ServiceEditor propertyId={propertyId} service={editing}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); loadServices(); }} />
      )}
      {bookSlot && (
        <BookSlotModal propertyId={propertyId} service={bookSlot.service} slot={bookSlot.slot}
          onClose={() => setBookSlot(null)} onSaved={() => { setBookSlot(null); loadAvailability(); loadBookings(); }} />
      )}
    </div>
  );
}

function ServiceEditor({ propertyId, service, onClose, onSaved }) {
  const [f, setF] = useState({
    name: service.name || "",
    category: service.category || "spa",
    duration_min: service.duration_min || 60,
    price: service.price || 0,
    currency: service.currency || "GBP",
    concurrent_capacity: service.concurrent_capacity || 1,
    open_hour: service.open_hour ?? 9,
    close_hour: service.close_hour ?? 21,
    buffer_min: service.buffer_min || 0,
    description: service.description || "",
    active: service.active ?? true,
    id: service.id,
  });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/timeslot-services/${propertyId}`, f);
      toast.success("Service saved");
      onSaved();
    } catch { toast.error("Save failed"); }
    setSaving(false);
  };
  return (
    <Modal title={f.id ? "Edit service" : "New service"} onClose={onClose}>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Name" className="col-span-2 px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100">
          {["spa", "gym", "golf", "restaurant", "activity"].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <input type="number" value={f.duration_min} onChange={(e) => setF({ ...f, duration_min: +e.target.value })} placeholder="Duration min" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="number" step="0.01" value={f.price} onChange={(e) => setF({ ...f, price: +e.target.value })} placeholder="Price" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="number" value={f.concurrent_capacity} onChange={(e) => setF({ ...f, concurrent_capacity: +e.target.value })} placeholder="Concurrent capacity" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="number" value={f.open_hour} onChange={(e) => setF({ ...f, open_hour: +e.target.value })} placeholder="Open hour" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="number" value={f.close_hour} onChange={(e) => setF({ ...f, close_hour: +e.target.value })} placeholder="Close hour" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="number" value={f.buffer_min} onChange={(e) => setF({ ...f, buffer_min: +e.target.value })} placeholder="Buffer min" className="col-span-2 px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
        <button data-testid="ts-save-service" onClick={save} disabled={saving}
          className="flex items-center gap-2 px-3 py-1.5 rounded bg-fuchsia-500/20 border border-fuchsia-500/40 text-fuchsia-200 text-sm">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />} Save
        </button>
      </div>
    </Modal>
  );
}

function BookSlotModal({ propertyId, service, slot, onClose, onSaved }) {
  const [f, setF] = useState({ guest_name: "", guest_email: "", booking_id: "", room_number: "", charge_to: "room", notes: "" });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (!f.guest_name) return toast.error("Guest name required");
    setSaving(true);
    try {
      await axios.post(`${API}/timeslot-bookings`, { service_id: service.id, start: slot.start, ...f });
      toast.success("Slot booked");
      onSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Book failed"); }
    setSaving(false);
  };
  const tm = slot.start.slice(11, 16);
  return (
    <Modal title={`Book ${service.name} · ${slot.start.slice(0, 10)} ${tm}`} onClose={onClose}>
      <div className="space-y-2">
        <input data-testid="ts-book-name" placeholder="Guest name *" value={f.guest_name} onChange={(e) => setF({ ...f, guest_name: e.target.value })} className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        <div className="grid grid-cols-2 gap-2">
          <input placeholder="Email" value={f.guest_email} onChange={(e) => setF({ ...f, guest_email: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          <input placeholder="Booking ID (folio)" value={f.booking_id} onChange={(e) => setF({ ...f, booking_id: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          <input placeholder="Room #" value={f.room_number} onChange={(e) => setF({ ...f, room_number: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          <select value={f.charge_to} onChange={(e) => setF({ ...f, charge_to: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
            {["room", "card", "cash", "comp"].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <input placeholder="Notes" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        <div className="text-xs text-stone-500">Charge: {fmt(service.price)} · {f.charge_to === "room" ? "→ room folio" : "→ direct"}</div>
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
        <button data-testid="ts-confirm-book" onClick={save} disabled={saving}
          className="flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />} Confirm
        </button>
      </div>
    </Modal>
  );
}

function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-stone-900 border border-stone-800 rounded-xl max-w-lg w-full p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <div className="text-stone-100 font-semibold">{title}</div>
          <button onClick={onClose} className="p-1 rounded hover:bg-stone-800 text-stone-500"><X className="w-4 h-4" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}
