/**
 * Late Check-out Panel
 * --------------------
 * Receptionist enters booking + requested hour → backend returns smart quote
 * with band (free / half / full), VIP grace, occupancy discount, and turnaround
 * block check vs next arrival. One-click accept posts a folio charge.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Loader2, Clock, BadgePoundSterling, RefreshCw, Settings2, AlertTriangle,
  CheckCircle2, Crown, Sparkles, Receipt,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BAND_META = {
  free:                       { label: "Complimentary", color: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40" },
  half_night:                 { label: "½ Night fee",    color: "bg-amber-500/15 text-amber-300 border-amber-500/40" },
  three_quarter_night:        { label: "¾ Night fee",   color: "bg-orange-500/15 text-orange-300 border-orange-500/40" },
  full_night:                 { label: "Full Night",    color: "bg-rose-500/15 text-rose-300 border-rose-500/40" },
};

function bandLabel(b) {
  const base = b?.replace("_quiet_night", "");
  const meta = BAND_META[base] || { label: b, color: "bg-stone-700/40 text-stone-300 border-stone-600" };
  return {
    ...meta,
    label: meta.label + (b?.endsWith("_quiet_night") ? " · quiet-night −30%" : ""),
  };
}

export default function LateCheckoutPanel({ propertyId, hotelName = "" }) {
  const [policy, setPolicy] = useState(null);
  const [showPolicy, setShowPolicy] = useState(false);
  const [bookingId, setBookingId] = useState("");
  const [requestedHour, setRequestedHour] = useState(13);
  const [quote, setQuote] = useState(null);
  const [recent, setRecent] = useState({ items: [], total_revenue: 0, count: 0 });
  const [loading, setLoading] = useState(false);
  const [accepting, setAccepting] = useState(false);

  const loadPolicy = useCallback(async () => {
    if (!propertyId) return;
    try {
      const { data } = await axios.get(`${API}/late-checkout/${propertyId}/policy`);
      setPolicy(data);
    } catch { /* swallow */ }
  }, [propertyId]);

  const loadRecent = useCallback(async () => {
    if (!propertyId) return;
    try {
      const { data } = await axios.get(`${API}/late-checkout/${propertyId}/list`);
      setRecent(data || { items: [], total_revenue: 0, count: 0 });
    } catch { /* swallow */ }
  }, [propertyId]);

  useEffect(() => { loadPolicy(); loadRecent(); }, [loadPolicy, loadRecent]);
  useEffect(() => { setQuote(null); setBookingId(""); }, [propertyId]);

  const fetchQuote = async () => {
    if (!bookingId) return toast.error("Booking ID required");
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/late-checkout/quote`, { booking_id: bookingId, requested_hour: requestedHour });
      setQuote(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Quote failed");
    }
    setLoading(false);
  };

  const accept = async () => {
    if (!quote || !quote.available) return;
    setAccepting(true);
    try {
      await axios.post(`${API}/late-checkout/${quote.booking_id}/accept`, {
        requested_hour: quote.requested_hour, fee: quote.fee,
      });
      toast.success(quote.fee > 0 ? `Posted £${quote.fee} to folio · checkout ${quote.new_checkout_time}` : `Comp late check-out approved`);
      setQuote(null); setBookingId("");
      loadRecent();
    } catch { toast.error("Accept failed"); }
    setAccepting(false);
  };

  const savePolicy = async () => {
    try {
      await axios.post(`${API}/late-checkout/${propertyId}/policy`, policy);
      toast.success("Policy saved");
      setShowPolicy(false);
    } catch { toast.error("Save failed"); }
  };

  const fmt = (n) => `£${Number(n || 0).toFixed(2)}`;

  return (
    <div className="space-y-6" data-testid="late-checkout-panel">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-amber-400" />
            <h2 className="text-2xl font-semibold text-stone-100">Late Check-out</h2>
            <span className="px-2 py-0.5 text-[10px] uppercase tracking-wider bg-amber-500/15 text-amber-300 rounded">
              Auto-quote
            </span>
          </div>
          <p className="text-sm text-stone-400 mt-1">
            {hotelName ? `${hotelName} · ` : ""}Smart pricing based on next arrival, occupancy & loyalty tier.
          </p>
        </div>
        <div className="flex gap-2">
          <button data-testid="late-checkout-policy-btn" onClick={() => setShowPolicy(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <Settings2 className="w-4 h-4" /> Policy
          </button>
        </div>
      </div>

      {/* Quote form */}
      <div className="rounded-xl border border-stone-800 bg-gradient-to-br from-amber-500/5 via-stone-900/60 to-stone-950 p-5">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="md:col-span-2">
            <label className="block text-[10px] uppercase tracking-wider text-stone-400 mb-1">Booking ID</label>
            <input data-testid="late-checkout-booking-id" value={bookingId} onChange={(e) => setBookingId(e.target.value)}
              placeholder="BK-…"
              className="w-full px-3 py-2 rounded-lg bg-stone-800/60 border border-stone-700 text-stone-100 text-sm" />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-stone-400 mb-1">New checkout hour</label>
            <select data-testid="late-checkout-hour" value={requestedHour} onChange={(e) => setRequestedHour(+e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-stone-800/60 border border-stone-700 text-stone-100 text-sm">
              {Array.from({ length: 14 }).map((_, i) => {
                const h = 10 + i;
                return <option key={h} value={h}>{`${h}:00`}</option>;
              })}
            </select>
          </div>
          <div className="flex items-end">
            <button data-testid="late-checkout-quote-btn" onClick={fetchQuote} disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-200 hover:bg-amber-500/30 text-sm">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              Get quote
            </button>
          </div>
        </div>
      </div>

      {/* Quote result */}
      {quote && (
        <div data-testid="late-checkout-quote" className={`rounded-xl border p-5 ${quote.available
            ? "border-amber-500/40 bg-amber-500/5"
            : "border-rose-500/40 bg-rose-500/5"
          }`}>
          {!quote.available ? (
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-6 h-6 text-rose-400" />
              <div>
                <div className="text-rose-200 font-semibold">Late check-out unavailable</div>
                <div className="text-sm text-rose-300/80 mt-0.5">{quote.block_reason}</div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <div className="text-stone-100 font-semibold flex items-center gap-2">
                    {quote.guest_name || "(no guest name)"}
                    {quote.is_vip && (
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/40">
                        <Crown className="w-3 h-3" /> VIP grace
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-stone-400 mt-0.5">
                    Room {quote.room_number || "—"} · current checkout {quote.current_checkout || "—"}
                  </div>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs border ${bandLabel(quote.band).color}`}>
                  {bandLabel(quote.band).label}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Stat label="New checkout" value={quote.new_checkout_time} icon={Clock} />
                <Stat label="Nightly rate" value={fmt(quote.nightly_rate)} icon={BadgePoundSterling} />
                <Stat label="Fee" value={fmt(quote.fee)} icon={Receipt} highlight />
                <Stat label="Occupancy tonight" value={`${quote.occupancy_pct}%`} icon={Sparkles} />
              </div>

              <button data-testid="late-checkout-accept-btn" onClick={accept} disabled={accepting}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-200">
                {accepting ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                {quote.fee > 0 ? `Charge ${fmt(quote.fee)} to folio & confirm` : "Confirm comp late check-out"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Recent */}
      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="text-stone-100 font-semibold">Recent late check-outs (30 d)</div>
          <button data-testid="late-checkout-refresh" onClick={loadRecent}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-stone-800 hover:bg-stone-700 text-stone-300 border border-stone-700">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          <Stat label="Approvals" value={recent.count} />
          <Stat label="Revenue captured" value={fmt(recent.total_revenue)} highlight />
          <Stat label="Avg ticket" value={recent.count ? fmt(recent.total_revenue / recent.count) : "—"} />
        </div>
        {recent.items?.length === 0 ? (
          <div className="text-center text-sm text-stone-500 py-6">No late check-outs in this window.</div>
        ) : (
          <div className="overflow-x-auto -mx-2">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-wider text-stone-500">
                  <th className="px-2 py-2">Date</th>
                  <th className="px-2 py-2">Guest</th>
                  <th className="px-2 py-2">Room</th>
                  <th className="px-2 py-2">New time</th>
                  <th className="px-2 py-2 text-right">Fee</th>
                  <th className="px-2 py-2">Approved by</th>
                </tr>
              </thead>
              <tbody>
                {recent.items.map((r) => (
                  <tr key={r.id} className="border-t border-stone-800/60 text-stone-200">
                    <td className="px-2 py-2 text-stone-400 text-xs">{new Date(r.approved_at).toLocaleString()}</td>
                    <td className="px-2 py-2">{r.guest_name || "—"}</td>
                    <td className="px-2 py-2">{r.room_number || "—"}</td>
                    <td className="px-2 py-2">{r.new_checkout_time}</td>
                    <td className="px-2 py-2 text-right font-medium">{fmt(r.fee)}</td>
                    <td className="px-2 py-2 text-stone-400 text-xs">{r.approved_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Policy modal */}
      {showPolicy && policy && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowPolicy(false)}>
          <div className="bg-stone-900 border border-stone-800 rounded-xl max-w-md w-full p-5"
            onClick={(e) => e.stopPropagation()}>
            <div className="text-stone-100 font-semibold mb-3">Late check-out policy</div>
            <div className="space-y-3 text-sm">
              <PolicyInput label="Free until (hr)" value={policy.free_until_hour}
                onChange={(v) => setPolicy({ ...policy, free_until_hour: v })} />
              <PolicyInput label="Half-night until (hr)" value={policy.half_until_hour}
                onChange={(v) => setPolicy({ ...policy, half_until_hour: v })} />
              <PolicyInput label="Full-night after (hr)" value={policy.full_after_hour}
                onChange={(v) => setPolicy({ ...policy, full_after_hour: v })} />
              <PolicyInput label="VIP grace until (hr)" value={policy.vip_free_until}
                onChange={(v) => setPolicy({ ...policy, vip_free_until: v })} />
              <PolicyInput label="Min turnaround (min)" value={policy.min_turnaround_min}
                onChange={(v) => setPolicy({ ...policy, min_turnaround_min: v })} />
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setShowPolicy(false)} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
              <button data-testid="late-checkout-save-policy" onClick={savePolicy}
                className="px-3 py-1.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200 text-sm">
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, icon: Icon, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight
      ? "bg-amber-500/10 border-amber-500/40"
      : "bg-stone-800/60 border-stone-800"}`}>
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-stone-400 mb-1">
        {Icon && <Icon className="w-3 h-3" />}{label}
      </div>
      <div className={`text-lg font-semibold ${highlight ? "text-amber-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}

function PolicyInput({ label, value, onChange }) {
  return (
    <label className="flex items-center justify-between gap-3">
      <span className="text-stone-300">{label}</span>
      <input type="number" value={value || 0} onChange={(e) => onChange(parseInt(e.target.value, 10) || 0)}
        className="w-24 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-right" />
    </label>
  );
}
