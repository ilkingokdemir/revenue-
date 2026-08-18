/**
 * Pre-Authorization Holds Panel
 * Front desk view: list active card holds, capture or release them at checkout.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, ShieldCheck, Plus, RefreshCw, CheckCircle2, XCircle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmt = (n, c = "GBP") => new Intl.NumberFormat("en-GB", { style: "currency", currency: c }).format(Number(n || 0));

export default function PreAuthPanel({ propertyId, hotelName = "" }) {
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState({ status: "", days: 30 });
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ booking_id: "", guest_name: "", room_number: "", amount: 200, hold_days: 7, reason: "incidentals", card_last4: "4242", card_brand: "visa" });

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ days: filter.days });
      if (filter.status) params.append("status", filter.status);
      const [{ data: list }, { data: sum }] = await Promise.all([
        axios.get(`${API}/preauth/${propertyId}/holds?${params}`),
        axios.get(`${API}/preauth/${propertyId}/summary?days=${filter.days}`),
      ]);
      setItems(list.items || []);
      setSummary(sum);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId, filter]);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!form.booking_id || !form.amount) return toast.error("Booking ID + amount required");
    try {
      await axios.post(`${API}/preauth/holds`, { property_id: propertyId, ...form });
      toast.success("Hold authorized");
      setAdding(false);
      load();
    } catch { toast.error("Hold failed"); }
  };

  const capture = async (h) => {
    const amt = parseFloat(prompt(`Capture amount (max ${h.amount}):`, h.amount));
    if (!amt || amt <= 0 || amt > h.amount) return;
    try {
      await axios.post(`${API}/preauth/holds/${h.id}/capture`, { amount: amt, reason: "damage" });
      toast.success(`Captured ${fmt(amt, h.currency)}`);
      load();
    } catch { toast.error("Capture failed"); }
  };

  const release = async (h) => {
    if (!window.confirm("Release this hold without charging?")) return;
    try {
      await axios.post(`${API}/preauth/holds/${h.id}/release`, {});
      toast.success("Hold released");
      load();
    } catch { toast.error("Release failed"); }
  };

  const expireDue = async () => {
    try {
      const { data } = await axios.post(`${API}/preauth/holds/expire-due`, {});
      toast.success(`Expired ${data.expired} stale holds`);
      load();
    } catch { toast.error("Sweep failed"); }
  };

  return (
    <div className="space-y-6" data-testid="preauth-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Pre-Authorization Holds</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Card pre-auth ledger — held at check-in, captured for damages or released at checkout.</p>
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Stat label="Currently held" value={fmt(summary.total_currently_held)} highlight />
          <Stat label="Total captured" value={fmt(summary.total_captured)} />
          <Stat label="Open" value={summary.by_status.authorized || 0} />
          <Stat label="Captured" value={summary.by_status.captured || 0} />
          <Stat label="Released / expired" value={(summary.by_status.released || 0) + (summary.by_status.expired || 0)} />
        </div>
      )}

      <div className="flex flex-wrap gap-2 items-center">
        <select value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" data-testid="preauth-filter-status">
          <option value="">All statuses</option>
          {["authorized", "captured", "released", "expired"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filter.days} onChange={(e) => setFilter({ ...filter, days: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
          {[7, 14, 30, 90].map((d) => <option key={d} value={d}>{`${d}d`}</option>)}
        </select>
        <button data-testid="preauth-refresh-btn" onClick={load} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1">
          <RefreshCw className="w-3 h-3" /> Refresh
        </button>
        <button data-testid="preauth-expire-btn" onClick={expireDue} className="text-xs px-2 py-1 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200">Sweep expired</button>
        <button data-testid="preauth-add-btn" onClick={() => setAdding(true)} className="ml-auto text-xs px-3 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-1">
          <Plus className="w-3 h-3" /> New hold
        </button>
      </div>

      {adding && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          <input data-testid="preauth-form-booking" placeholder="Booking ID" value={form.booking_id} onChange={(e) => setForm({ ...form, booking_id: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 col-span-2" />
          <input placeholder="Guest name" value={form.guest_name} onChange={(e) => setForm({ ...form, guest_name: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input placeholder="Room #" value={form.room_number} onChange={(e) => setForm({ ...form, room_number: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input data-testid="preauth-form-amount" type="number" placeholder="Amount" value={form.amount} onChange={(e) => setForm({ ...form, amount: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input type="number" placeholder="Hold days" value={form.hold_days} onChange={(e) => setForm({ ...form, hold_days: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <select value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100">
            {["incidentals", "damage", "extra_services"].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <input placeholder="Card last4" value={form.card_last4} onChange={(e) => setForm({ ...form, card_last4: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <button data-testid="preauth-save-btn" onClick={create} className="col-span-2 md:col-span-4 px-2 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-xs">Authorize hold</button>
        </div>
      )}

      {loading ? <Loader2 className="w-5 h-5 animate-spin text-stone-500" /> : (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr>
                <th className="px-3 py-2">Authorized</th>
                <th className="px-3 py-2">Booking / Guest</th>
                <th className="px-3 py-2">Room</th>
                <th className="px-3 py-2">Card</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Expires</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((h) => (
                <tr key={h.id} className="border-t border-stone-800/60 text-stone-200" data-testid="preauth-row">
                  <td className="px-3 py-2 text-stone-400 text-xs">{(h.authorized_at || "").slice(0, 16)}</td>
                  <td className="px-3 py-2"><div>{h.guest_name || "—"}</div><div className="text-[10px] text-stone-500">{h.booking_id?.slice(0, 8)}</div></td>
                  <td className="px-3 py-2">{h.room_number || "—"}</td>
                  <td className="px-3 py-2 text-xs text-stone-400">{h.card_brand} ····{h.card_last4}</td>
                  <td className="px-3 py-2 text-right">{fmt(h.amount, h.currency)}{h.captured_amount > 0 && <div className="text-[10px] text-emerald-300">cap: {fmt(h.captured_amount, h.currency)}</div>}</td>
                  <td className="px-3 py-2">
                    <StatusPill status={h.status} />
                  </td>
                  <td className="px-3 py-2 text-xs text-stone-400">{(h.expires_at || "").slice(0, 10)}</td>
                  <td className="px-3 py-2 text-right">
                    {h.status === "authorized" && (
                      <div className="flex gap-1 justify-end">
                        <button data-testid="preauth-capture-btn" onClick={() => capture(h)} className="px-2 py-1 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200 text-xs flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> Capture
                        </button>
                        <button data-testid="preauth-release-btn" onClick={() => release(h)} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 text-xs flex items-center gap-1">
                          <XCircle className="w-3 h-3" /> Release
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={8} className="px-3 py-6 text-center text-stone-500"><ShieldCheck className="w-5 h-5 mx-auto mb-1 opacity-60" />No holds in window.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    authorized: "bg-cyan-500/20 border-cyan-500/40 text-cyan-200",
    captured: "bg-emerald-500/20 border-emerald-500/40 text-emerald-200",
    released: "bg-stone-800 border-stone-700 text-stone-300",
    expired: "bg-amber-500/20 border-amber-500/40 text-amber-200",
  };
  return <span className={`text-[10px] px-2 py-0.5 rounded border ${map[status] || ""}`}>{status}</span>;
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-cyan-500/10 border-cyan-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-cyan-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
