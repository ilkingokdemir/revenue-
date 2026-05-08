/**
 * Spaces (Multi-Product Inventory) Panel
 * --------------------------------------
 * Parking, EV chargers, meeting rooms, bicycles, lockers etc.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Boxes, Plus, RefreshCw, Trash2, X, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const KINDS = ["parking", "ev_charger", "meeting_room", "bicycle", "locker", "cabana", "kayak", "other"];
const fmt = (n) => `£${Number(n || 0).toFixed(2)}`;

export default function SpacesPanel({ propertyId, hotelName = "" }) {
  const [spaces, setSpaces] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [editing, setEditing] = useState(null);
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [s, b] = await Promise.all([
        axios.get(`${API}/spaces/${propertyId}`),
        axios.get(`${API}/space-bookings/${propertyId}?days=14`),
      ]);
      setSpaces(s.data || []); setBookings(b.data || []);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setSpaces([]); setBookings([]); }, [propertyId]);

  const removeSpace = async (id) => {
    if (!window.confirm("Deactivate space?")) return;
    await axios.delete(`${API}/spaces/${propertyId}/${id}`); load();
  };
  const cancelBk = async (id) => {
    if (!window.confirm("Cancel booking?")) return;
    await axios.post(`${API}/space-bookings/${id}/cancel`); toast.success("Cancelled"); load();
  };

  return (
    <div className="space-y-6" data-testid="spaces-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Boxes className="w-5 h-5 text-teal-400" />
            <h2 className="text-2xl font-semibold text-stone-100">Spaces — Multi-Product Inventory</h2>
          </div>
          <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Parking, EV chargers, meeting rooms, bikes, lockers — all bookable.</p>
        </div>
        <div className="flex gap-2">
          <button data-testid="spaces-refresh-btn" onClick={load} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button data-testid="spaces-new-btn" onClick={() => setEditing({})}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-500/20 hover:bg-teal-500/30 border border-teal-500/40 text-teal-200 text-sm">
            <Plus className="w-4 h-4" /> New space
          </button>
        </div>
      </div>

      {loading ? <Loader2 className="w-6 h-6 animate-spin text-stone-500" /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {spaces.map((s) => (
            <div key={s.id} data-testid="space-card" className="rounded-lg border border-stone-800 bg-stone-900/60 p-3">
              <div className="flex items-center justify-between mb-1">
                <div>
                  <div className="text-stone-100 font-medium">{s.name}</div>
                  <div className="text-[10px] uppercase tracking-wider text-stone-500">{s.kind} · {s.code || `cap ${s.capacity}`}</div>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => setEditing(s)} className="text-xs px-2 py-0.5 rounded bg-stone-800 text-stone-300 border border-stone-700">Edit</button>
                  <button onClick={() => removeSpace(s.id)} className="p-1 rounded text-stone-500 hover:text-rose-400"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
              <div className="text-xs text-stone-400">
                {fmt(s.rate_per_unit)} per {s.unit_minutes ? `${s.unit_minutes}min` : "day"} · {s.open_hour}:00–{s.close_hour}:00
              </div>
              <button data-testid="space-book-btn" onClick={() => setBook(s)}
                className="w-full mt-2 px-2 py-1 rounded bg-teal-500/20 border border-teal-500/40 text-teal-200 text-xs">
                Book
              </button>
            </div>
          ))}
          {spaces.length === 0 && <div className="text-stone-500 text-sm col-span-full">No spaces yet.</div>}
        </div>
      )}

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
        <div className="text-stone-100 font-semibold mb-2">Upcoming bookings</div>
        {bookings.length === 0 ? <div className="text-sm text-stone-500">None.</div> : (
          <div className="space-y-1">
            {bookings.slice(0, 30).map((b) => (
              <div key={b.id} data-testid="space-booking-row" className="flex items-center justify-between bg-stone-800/40 rounded px-2 py-1 text-sm">
                <span>
                  <span className="text-xs text-stone-400 font-mono">{b.start.slice(0, 16).replace("T", " ")}</span>
                  <span className="text-stone-200 ml-2">{b.guest_name}</span>
                  <span className="text-xs text-stone-500 ml-2">· {b.space_name}</span>
                  {b.status === "cancelled" && <span className="text-[10px] px-1 ml-1 rounded bg-rose-500/20 text-rose-300">cancelled</span>}
                </span>
                <span className="flex items-center gap-2">
                  <span className="text-xs text-emerald-300">{fmt(b.price)}</span>
                  {b.status !== "cancelled" && (
                    <button onClick={() => cancelBk(b.id)} className="text-[10px] px-2 py-0.5 rounded bg-stone-800 hover:bg-rose-500/20 text-stone-300 border border-stone-700">Cancel</button>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {editing !== null && (
        <Editor propertyId={propertyId} space={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      )}
      {book && (
        <BookModal propertyId={propertyId} space={book} onClose={() => setBook(null)} onSaved={() => { setBook(null); load(); }} />
      )}
    </div>
  );
}

function Editor({ propertyId, space, onClose, onSaved }) {
  const [f, setF] = useState({
    id: space.id,
    kind: space.kind || "parking",
    name: space.name || "",
    code: space.code || "",
    capacity: space.capacity || 1,
    rate_per_unit: space.rate_per_unit || 0,
    currency: space.currency || "GBP",
    unit_minutes: space.unit_minutes ?? "",  // empty = daily
    open_hour: space.open_hour ?? 0,
    close_hour: space.close_hour ?? 24,
    description: space.description || "",
  });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      const body = { ...f, unit_minutes: f.unit_minutes === "" ? null : parseInt(f.unit_minutes, 10) };
      await axios.post(`${API}/spaces/${propertyId}`, body); toast.success("Saved"); onSaved();
    } catch { toast.error("Save failed"); }
    setSaving(false);
  };
  return (
    <Modal title={f.id ? "Edit space" : "New space"} onClose={onClose}>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100">
          {KINDS.map((k) => <option key={k} value={k}>{k.replaceAll("_", " ")}</option>)}
        </select>
        <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Name" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="Code (e.g. P-12)" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="number" value={f.capacity} onChange={(e) => setF({ ...f, capacity: +e.target.value })} placeholder="Capacity" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="number" step="0.01" value={f.rate_per_unit} onChange={(e) => setF({ ...f, rate_per_unit: +e.target.value })} placeholder="Rate per unit" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input value={f.currency} onChange={(e) => setF({ ...f, currency: e.target.value })} placeholder="Currency" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="number" value={f.unit_minutes} onChange={(e) => setF({ ...f, unit_minutes: e.target.value })} placeholder="Unit min (blank = daily)" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="number" value={f.open_hour} onChange={(e) => setF({ ...f, open_hour: +e.target.value })} placeholder="Open hour" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="number" value={f.close_hour} onChange={(e) => setF({ ...f, close_hour: +e.target.value })} placeholder="Close hour" className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
        <button data-testid="space-save-btn" onClick={save} disabled={saving} className="flex items-center gap-2 px-3 py-1.5 rounded bg-teal-500/20 border border-teal-500/40 text-teal-200 text-sm">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />} Save
        </button>
      </div>
    </Modal>
  );
}

function BookModal({ propertyId, space, onClose, onSaved }) {
  const now = new Date(); const later = new Date(now.getTime() + 60 * 60000);
  const iso = (d) => d.toISOString().slice(0, 16);
  const [f, setF] = useState({
    space_id: space.id, start: iso(now), end: iso(later),
    guest_name: "", guest_email: "", booking_id: "", room_number: "", charge_to: "room",
  });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (!f.guest_name) return toast.error("Guest name required");
    setSaving(true);
    try {
      const body = { ...f, start: f.start + ":00", end: f.end + ":00" };
      await axios.post(`${API}/space-bookings`, body); toast.success("Booked"); onSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Book failed"); }
    setSaving(false);
  };
  return (
    <Modal title={`Book ${space.name}`} onClose={onClose}>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <input data-testid="space-book-name" placeholder="Guest name *" value={f.guest_name} onChange={(e) => setF({ ...f, guest_name: e.target.value })} className="col-span-2 px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="datetime-local" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input type="datetime-local" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input placeholder="Booking ID (folio)" value={f.booking_id} onChange={(e) => setF({ ...f, booking_id: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <input placeholder="Room #" value={f.room_number} onChange={(e) => setF({ ...f, room_number: e.target.value })} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <select value={f.charge_to} onChange={(e) => setF({ ...f, charge_to: e.target.value })} className="col-span-2 px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100">
          {["room", "card", "cash", "comp"].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
        <button data-testid="space-confirm-book" onClick={save} disabled={saving} className="flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">
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
