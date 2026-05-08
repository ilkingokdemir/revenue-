/**
 * Dynamic Check-in Time Slots Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Save, RefreshCw, Clock } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CISlotsPanel({ propertyId, hotelName = "" }) {
  const [cfg, setCfg] = useState(null);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [avail, setAvail] = useState(null);
  const [reservations, setReservations] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: c }, { data: a }, { data: r }] = await Promise.all([
        axios.get(`${API}/ci-slots/${propertyId}/config`),
        axios.get(`${API}/ci-slots/${propertyId}/${date}/availability`),
        axios.get(`${API}/ci-slots/${propertyId}/${date}/reservations`),
      ]);
      setCfg(c); setAvail(a); setReservations(r.items || []);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId, date]);

  useEffect(() => { refresh(); }, [refresh]);

  const save = async () => {
    try {
      await axios.post(`${API}/ci-slots/config`, { property_id: propertyId, ...cfg });
      toast.success("Saved"); refresh();
    } catch { toast.error("Failed"); }
  };

  const cancel = async (id) => {
    try {
      await axios.delete(`${API}/ci-slots/reservations/${id}`);
      toast.success("Cancelled"); refresh();
    } catch { toast.error("Failed"); }
  };

  return (
    <div className="space-y-6" data-testid="ci-slots-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Check-in Time Slots</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Configurable slot grid with capacity caps. Pre-14:00 slots auto-charge an early-CI fee.</p>
      </div>

      {cfg && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-2 md:grid-cols-6 gap-2 text-xs">
          <label className="flex flex-col gap-1"><span className="text-stone-500">Start hour</span><input type="number" min={0} max={23} value={cfg.start_hour} onChange={(e) => setCfg({ ...cfg, start_hour: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">End hour</span><input type="number" min={1} max={24} value={cfg.end_hour} onChange={(e) => setCfg({ ...cfg, end_hour: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Slot mins</span><input type="number" value={cfg.slot_minutes} onChange={(e) => setCfg({ ...cfg, slot_minutes: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Cap / slot</span><input type="number" value={cfg.capacity_per_slot} onChange={(e) => setCfg({ ...cfg, capacity_per_slot: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Early fee £</span><input type="number" value={cfg.early_ci_fee} onChange={(e) => setCfg({ ...cfg, early_ci_fee: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <button data-testid="cis-save-cfg-btn" onClick={save} className="px-2 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 mt-4 flex items-center justify-center gap-1"><Save className="w-3 h-3" /> Save</button>
        </div>
      )}

      <div className="flex gap-2 items-center">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" />
        <button onClick={refresh} className="text-sm px-3 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">{loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} Refresh</button>
      </div>

      {avail && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
          <div className="text-xs uppercase tracking-wider text-stone-400 mb-2">Slot grid · capacity {avail.capacity_per_slot} per slot</div>
          <div className="grid grid-cols-3 md:grid-cols-6 lg:grid-cols-8 gap-1.5">
            {avail.slots.map((s) => (
              <div key={s.slot} className={`p-2 rounded border text-center text-xs ${s.free_seats <= 0 ? "bg-rose-500/10 border-rose-500/40 text-rose-200" : s.is_early ? "bg-amber-500/10 border-amber-500/40 text-amber-200" : "bg-emerald-500/10 border-emerald-500/40 text-emerald-200"}`} data-testid="cis-slot-cell">
                <div className="font-mono text-sm flex items-center justify-center gap-1"><Clock className="w-3 h-3 inline" />{s.slot}</div>
                <div className="text-[10px]">{s.free_seats} free</div>
                {s.is_early && <div className="text-[10px]">£{s.fee} fee</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <div className="px-4 py-2 border-b border-stone-800 text-xs uppercase tracking-wider text-stone-400">Reservations for {date} ({reservations.length})</div>
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500"><tr><th className="px-3 py-2">Slot</th><th className="px-3 py-2">Guest</th><th className="px-3 py-2">Booking</th><th className="px-3 py-2">Early?</th><th className="px-3 py-2 text-right">Fee</th><th className="px-3 py-2"></th></tr></thead>
          <tbody>
            {reservations.map((r) => (
              <tr key={r.id} className="border-t border-stone-800/60 text-stone-200" data-testid="cis-res-row">
                <td className="px-3 py-2 font-mono">{r.slot}</td>
                <td className="px-3 py-2">{r.guest_name || "—"}</td>
                <td className="px-3 py-2 font-mono text-xs">{r.booking_id?.slice(0, 8)}</td>
                <td className="px-3 py-2">{r.is_early ? <span className="text-[10px] px-2 py-0.5 rounded border bg-amber-500/20 border-amber-500/40 text-amber-200">early</span> : "—"}</td>
                <td className="px-3 py-2 text-right">£{r.fee_due}</td>
                <td className="px-3 py-2 text-right"><button data-testid="cis-cancel-btn" onClick={() => cancel(r.id)} className="text-xs px-2 py-1 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200">Cancel</button></td>
              </tr>
            ))}
            {reservations.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-stone-500">No reservations for this date.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
