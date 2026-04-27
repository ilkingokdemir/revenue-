/**
 * Stay Extension Wizard Panel
 * Quote → Apply flow for extending an active stay.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Plus, RefreshCw, CheckCircle2, AlertTriangle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function StayExtPanel({ propertyId, hotelName = "" }) {
  const [bookingId, setBookingId] = useState("");
  const [extra, setExtra] = useState(1);
  const [discount, setDiscount] = useState(0);
  const [quote, setQuote] = useState(null);
  const [loading, setLoading] = useState(false);
  const [recent, setRecent] = useState({ items: [], extra_nights_total: 0, extra_revenue: 0 });

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    try {
      const { data } = await axios.get(`${API}/stay-ext/${propertyId}/recent?days=60`);
      setRecent(data);
    } catch { /* swallow */ }
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const fmt = (n, c = "GBP") => `${c} ${Number(n || 0).toFixed(2)}`;

  const getQuote = async () => {
    if (!bookingId.trim()) return toast.error("Booking ID required");
    setLoading(true); setQuote(null);
    try {
      const { data } = await axios.post(`${API}/stay-ext/quote`, { booking_id: bookingId.trim(), extra_nights: extra, discount_pct: discount });
      setQuote(data);
    } catch (e) { toast.error(e.response?.data?.detail || "Quote failed"); }
    setLoading(false);
  };

  const apply = async () => {
    if (!quote) return;
    if (!quote.room_available) return toast.error("Room not available — quote denied");
    if (!window.confirm(`Extend by ${quote.extra_nights} night(s) at ${fmt(quote.total_extra_charge, quote.currency)}?`)) return;
    try {
      const { data } = await axios.post(`${API}/stay-ext/apply`, { booking_id: bookingId.trim(), extra_nights: extra, discount_pct: discount });
      toast.success(`Stay extended to ${data.proposed_check_out}, charged ${fmt(data.total_extra_charge, data.currency)}`);
      setQuote(null);
      refresh();
    } catch (e) { toast.error(e.response?.data?.detail || "Apply failed"); }
  };

  return (
    <div className="space-y-6" data-testid="stay-ext-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Stay Extension Wizard</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Quote first → check the room is free → apply with one click. Folio updated automatically.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Extensions (60d)" value={recent.count} />
        <Stat label="Extra nights" value={recent.extra_nights_total} />
        <Stat label="Extra revenue" value={`£${recent.extra_revenue}`} highlight />
        <button onClick={refresh} className="text-xs px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2 justify-center">
          <RefreshCw className="w-3 h-3" /> Refresh
        </button>
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <input data-testid="se-booking-input" value={bookingId} onChange={(e) => setBookingId(e.target.value)} placeholder="Booking ID" className="md:col-span-2 px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm font-mono" />
          <label className="flex items-center gap-2 text-xs">Nights:
            <input data-testid="se-nights-input" type="number" min={1} value={extra} onChange={(e) => setExtra(parseInt(e.target.value, 10))} className="w-20 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          </label>
          <label className="flex items-center gap-2 text-xs">Disc %:
            <input type="number" min={0} max={50} value={discount} onChange={(e) => setDiscount(parseFloat(e.target.value))} className="w-20 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          </label>
        </div>
        <div className="flex gap-2">
          <button data-testid="se-quote-btn" onClick={getQuote} disabled={loading} className="text-sm px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Get quote
          </button>
          {quote && quote.room_available && (
            <button data-testid="se-apply-btn" onClick={apply} className="text-sm px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 flex items-center gap-2"><CheckCircle2 className="w-4 h-4" /> Apply extension</button>
          )}
        </div>

        {quote && (
          <div className={`rounded-lg border p-3 ${quote.room_available ? "border-emerald-500/40 bg-emerald-500/10" : "border-rose-500/40 bg-rose-500/10"}`} data-testid="se-quote-box">
            {!quote.room_available ? (
              <div className="text-rose-200 flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> Room not available for {quote.extra_nights} extra night(s)</div>
            ) : (
              <>
                <div className="text-stone-100 font-medium">Extend to {quote.proposed_check_out}</div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2 text-sm">
                  <Cell label="Per night" value={fmt(quote.rate_per_night_charged, quote.currency)} />
                  <Cell label="Disc %" value={`${quote.discount_pct}%`} />
                  <Cell label="Extra nights" value={quote.extra_nights} />
                  <Cell label="Total charge" value={fmt(quote.total_extra_charge, quote.currency)} highlight />
                </div>
              </>
            )}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr><th className="px-3 py-2">Applied</th><th className="px-3 py-2">Booking</th><th className="px-3 py-2">Nights</th><th className="px-3 py-2">Old → New checkout</th><th className="px-3 py-2 text-right">Charge</th><th className="px-3 py-2">By</th></tr>
          </thead>
          <tbody>
            {recent.items.map((r) => (
              <tr key={r.id} className="border-t border-stone-800/60 text-stone-200" data-testid="se-log-row">
                <td className="px-3 py-2 text-xs text-stone-400">{(r.applied_at || "").slice(0, 16)}</td>
                <td className="px-3 py-2 font-mono text-xs">{r.booking_id?.slice(0, 8)}</td>
                <td className="px-3 py-2">+{r.extra_nights}</td>
                <td className="px-3 py-2 text-xs">{r.old_check_out} → <span className="text-emerald-300">{r.new_check_out}</span></td>
                <td className="px-3 py-2 text-right">£{r.charge}</td>
                <td className="px-3 py-2 text-xs text-stone-400">{r.applied_by}</td>
              </tr>
            ))}
            {recent.items.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-stone-500">No extensions yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-emerald-500/10 border-emerald-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-emerald-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}

function Cell({ label, value, highlight = false }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-stone-400">{label}</div>
      <div className={`text-base font-semibold ${highlight ? "text-emerald-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
