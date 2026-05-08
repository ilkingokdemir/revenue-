/**
 * Walk-in Express Check-in Panel
 * ------------------------------
 * 90-second flow: enter nights/guests → see available room types with all-in
 * pricing → pick a room → fill guest minimums → check-in + folio open in one
 * click.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, UserPlus, Search, CheckCircle2, Bed, BadgePoundSterling } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function WalkInPanel({ propertyId, hotelName = "" }) {
  const today = new Date().toISOString().slice(0, 10);
  const [check_in, setCheckIn] = useState(today);
  const [nights, setNights] = useState(1);
  const [guests, setGuests] = useState(1);
  const [loading, setLoading] = useState(false);
  const [offerings, setOfferings] = useState([]);
  const [selected, setSelected] = useState(null);   // { offering, room }
  const [guest, setGuest] = useState({ name: "", email: "", phone: "", id_doc: "", id_type: "passport" });
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [deposit, setDeposit] = useState(0);
  const [confirming, setConfirming] = useState(false);

  const search = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true); setOfferings([]); setSelected(null);
    try {
      const { data } = await axios.post(`${API}/walkin/availability`, {
        property_id: propertyId, check_in, nights, guests,
      });
      setOfferings(data.offerings || []);
      if ((data.offerings || []).length === 0) toast.info("No available rooms tonight");
    } catch (e) { toast.error(e?.response?.data?.detail || "Search failed"); }
    setLoading(false);
  }, [propertyId, check_in, nights, guests]);

  useEffect(() => { setOfferings([]); setSelected(null); }, [propertyId]);

  const confirm = async () => {
    if (!selected || !guest.name) return toast.error("Pick a room and enter guest name");
    setConfirming(true);
    try {
      const body = {
        property_id: propertyId,
        room_type_id: selected.offering.room_type_id,
        room_number: selected.room.room_number,
        nights, guests, check_in,
        rate: selected.offering.base_rate,
        guest, payment_method: paymentMethod, deposit_paid: deposit,
      };
      const { data } = await axios.post(`${API}/walkin/create`, body);
      toast.success(`Walk-in checked in · ${data.booking.booking_ref} · balance £${data.balance_due.toFixed(2)}`);
      setSelected(null); setGuest({ name: "", email: "", phone: "", id_doc: "", id_type: "passport" });
      setDeposit(0); search();
    } catch (e) { toast.error(e?.response?.data?.detail || "Check-in failed"); }
    setConfirming(false);
  };

  const fmt = (n) => `£${Number(n || 0).toFixed(2)}`;

  return (
    <div className="space-y-6" data-testid="walkin-panel">
      <div>
        <div className="flex items-center gap-2">
          <UserPlus className="w-5 h-5 text-cyan-400" />
          <h2 className="text-2xl font-semibold text-stone-100">Walk-in Express Check-in</h2>
          <span className="px-2 py-0.5 text-[10px] uppercase tracking-wider bg-cyan-500/15 text-cyan-300 rounded">≈90 sn</span>
        </div>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Find an available room, enter the guest, check-in instantly.</p>
      </div>

      {/* Search bar */}
      <div className="rounded-xl border border-stone-800 bg-gradient-to-br from-cyan-500/5 via-stone-900/60 to-stone-950 p-5">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Field label="Check-in">
            <input data-testid="walkin-checkin" type="date" value={check_in} onChange={(e) => setCheckIn(e.target.value)} className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          </Field>
          <Field label="Nights">
            <input data-testid="walkin-nights" type="number" min={1} max={30} value={nights}
              onChange={(e) => setNights(parseInt(e.target.value, 10) || 1)}
              className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          </Field>
          <Field label="Guests">
            <input data-testid="walkin-guests" type="number" min={1} max={6} value={guests}
              onChange={(e) => setGuests(parseInt(e.target.value, 10) || 1)}
              className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          </Field>
          <div className="col-span-2 flex items-end">
            <button data-testid="walkin-search-btn" onClick={search}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 text-sm">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              Find available rooms
            </button>
          </div>
        </div>
      </div>

      {/* Offerings */}
      {offerings.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-3">
          {offerings.map((o) => (
            <div key={o.room_type_id}
              className={`rounded-xl border p-4 transition cursor-pointer ${
                selected?.offering?.room_type_id === o.room_type_id
                  ? "border-cyan-500/60 bg-cyan-500/10"
                  : "border-stone-800 bg-stone-900/60 hover:border-stone-700"
              }`}>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <div className="text-stone-100 font-semibold">{o.room_type_name}</div>
                  <div className="text-xs text-stone-500">{o.available_count} rooms clean</div>
                </div>
                <div className="text-right">
                  <div className="text-stone-100 font-semibold">{fmt(o.grand_total)}</div>
                  <div className="text-[10px] text-stone-500">incl. tax</div>
                </div>
              </div>
              <div className="text-xs text-stone-400 mb-2">
                {fmt(o.base_rate)}/n × {nights}n + {fmt(o.taxes_added)} tax
              </div>
              <div className="flex flex-wrap gap-1">
                {o.available_rooms.slice(0, 6).map((r) => (
                  <button key={r.room_id} data-testid="walkin-pick-room"
                    onClick={() => setSelected({ offering: o, room: r })}
                    className={`px-2 py-1 rounded text-xs border ${
                      selected?.room?.room_id === r.room_id
                        ? "bg-cyan-500/30 border-cyan-500/60 text-cyan-100"
                        : "bg-stone-800 border-stone-700 text-stone-300 hover:bg-stone-700"
                    }`}>
                    <Bed className="w-3 h-3 inline mr-1" /> {r.room_number}
                  </button>
                ))}
                {o.available_rooms.length > 6 && (
                  <span className="text-stone-500 text-xs self-center">+{o.available_rooms.length - 6}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Guest form */}
      {selected && (
        <div className="rounded-xl border border-cyan-500/40 bg-cyan-500/5 p-5 space-y-3" data-testid="walkin-guest-form">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <div className="text-stone-100 font-semibold">Room {selected.room.room_number} · {selected.offering.room_type_name}</div>
              <div className="text-xs text-stone-400">Total: {fmt(selected.offering.grand_total)} for {nights} night(s)</div>
            </div>
            <button onClick={() => setSelected(null)} className="text-xs px-2 py-1 rounded bg-stone-800 text-stone-300">Change</button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input data-testid="walkin-guest-name" placeholder="Guest name *" value={guest.name}
              onChange={(e) => setGuest({ ...guest, name: e.target.value })}
              className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
            <input placeholder="Email" value={guest.email}
              onChange={(e) => setGuest({ ...guest, email: e.target.value })}
              className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
            <input placeholder="Phone" value={guest.phone}
              onChange={(e) => setGuest({ ...guest, phone: e.target.value })}
              className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
            <input placeholder="ID document #" value={guest.id_doc}
              onChange={(e) => setGuest({ ...guest, id_doc: e.target.value })}
              className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
            <select value={guest.id_type} onChange={(e) => setGuest({ ...guest, id_type: e.target.value })}
              className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
              {["passport", "national_id", "driving_licence", "other"].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}
              className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
              {["cash", "card", "bank_transfer", "city_ledger"].map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
            <Field label="Deposit paid">
              <input type="number" min={0} step={0.01} value={deposit}
                onChange={(e) => setDeposit(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
            </Field>
          </div>

          <button data-testid="walkin-confirm-btn" onClick={confirm} disabled={confirming || !guest.name}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-200 disabled:opacity-50">
            {confirming ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            Check in & open folio
          </button>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</label>
      {children}
    </div>
  );
}
