/**
 * No-Show Auto-Charge Panel
 * -------------------------
 * Lists today's no-show candidates (still confirmed past check-in date),
 * allows bulk auto-mark or single manual mark with fee override.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Ghost, RefreshCw, Settings2, Zap, X, AlertTriangle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function NoShowPanel({ propertyId, hotelName = "" }) {
  const today = new Date().toISOString().slice(0, 10);
  const [target, setTarget] = useState(today);
  const [data, setData] = useState({ items: [], policy: null, count: 0 });
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [policy, setPolicy] = useState(null);
  const [showPolicy, setShowPolicy] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/no-show/${propertyId}/candidates?on_date=${target}`);
      setData(data); setPolicy(data.policy);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId, target]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setData({ items: [], policy: null, count: 0 }); }, [propertyId]);

  const bulkRun = async () => {
    if (!window.confirm(`Auto-mark ${data.count} bookings as no-show and post fees?`)) return;
    setRunning(true);
    try {
      const { data: r } = await axios.post(`${API}/no-show/${propertyId}/run`, { on_date: target });
      toast.success(`${r.marked} marked · £${r.total_fee.toFixed(2)} posted`);
      load();
    } catch { toast.error("Bulk run failed"); }
    setRunning(false);
  };

  const markOne = async (b) => {
    if (!window.confirm(`Mark ${b.guest_name || b.booking_ref} as no-show? Fee £${b.fee.toFixed(2)}`)) return;
    try {
      await axios.post(`${API}/no-show/${b.id}/mark`, {});
      toast.success("Marked no-show");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Mark failed"); }
  };

  const savePolicy = async () => {
    try {
      await axios.post(`${API}/no-show/${propertyId}/policy`, policy);
      toast.success("Policy saved");
      setShowPolicy(false); load();
    } catch { toast.error("Save failed"); }
  };

  return (
    <div className="space-y-6" data-testid="no-show-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Ghost className="w-5 h-5 text-rose-400" />  <h2 className="text-2xl font-semibold text-stone-100">No-Show Auto-Charge</h2>
          </div>
          <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Auto-mark past-check-in confirmed bookings + post cancellation fee.</p>
        </div>
        <div className="flex gap-2">
          <input data-testid="no-show-target-date" type="date" value={target} onChange={(e) => setTarget(e.target.value)}
            className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          <button data-testid="no-show-policy-btn" onClick={() => setShowPolicy(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <Settings2 className="w-4 h-4" /> Policy
          </button>
          <button data-testid="no-show-refresh-btn" onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </div>

      {policy && (
        <div className="rounded-lg border border-stone-800 bg-stone-900/60 p-3 text-sm text-stone-300 flex items-center gap-3 flex-wrap">
          <span className="text-stone-500 text-xs">POLICY</span>
          <span>Fee type: <strong>{policy.fee_type}</strong></span>
          {policy.fee_type === "percent_total" && <span>· {policy.fee_pct}% of total</span>}
          {policy.fee_type === "flat" && <span>· £{policy.flat_amount}</span>}
          <span>· cut-off {String(policy.grace_hour).padStart(2, "0")}:00</span>
          <span className={`px-2 py-0.5 text-xs rounded ${policy.auto_run_enabled ? "bg-emerald-500/15 text-emerald-300" : "bg-stone-700 text-stone-300"}`}>
            {policy.auto_run_enabled ? "auto-run on" : "manual"}
          </span>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="text-stone-100 font-semibold">{data.count} candidate{data.count === 1 ? "" : "s"}</div>
        {data.count > 0 && (
          <button data-testid="no-show-bulk-btn" onClick={bulkRun} disabled={running}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 text-sm">
            {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            Auto-mark all & charge
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12 text-stone-500"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : data.items.length === 0 ? (
        <div className="text-center text-stone-500 py-12 flex flex-col items-center gap-2">
          <AlertTriangle className="w-8 h-8 text-stone-600" />
          No no-show candidates for {target}.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-stone-800 bg-stone-900/60">
          <table className="min-w-full text-sm">
            <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr>
                <th className="px-3 py-2">Booking</th>
                <th className="px-3 py-2">Guest</th>
                <th className="px-3 py-2">Channel</th>
                <th className="px-3 py-2">Check-in</th>
                <th className="px-3 py-2 text-right">Total</th>
                <th className="px-3 py-2 text-right">Fee</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((b) => (
                <tr key={b.id} className="border-t border-stone-800/60 text-stone-200" data-testid="no-show-row">
                  <td className="px-3 py-2 text-xs text-stone-400">{b.booking_ref || b.id?.slice(0, 8)}</td>
                  <td className="px-3 py-2">{b.guest_name || "—"}</td>
                  <td className="px-3 py-2 text-stone-400 text-xs">{b.channel || "direct"}</td>
                  <td className="px-3 py-2 text-stone-400 text-xs">{b.check_in}</td>
                  <td className="px-3 py-2 text-right">£{b.total_price.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right text-rose-300 font-medium">£{b.fee.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">
                    <button data-testid="no-show-mark-btn" onClick={() => markOne(b)}
                      className="px-2 py-1 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200 text-xs hover:bg-rose-500/30">
                      Mark no-show
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showPolicy && policy && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowPolicy(false)}>
          <div className="bg-stone-900 border border-stone-800 rounded-xl max-w-md w-full p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <div className="text-stone-100 font-semibold">No-show fee policy</div>
              <button onClick={() => setShowPolicy(false)} className="p-1 rounded hover:bg-stone-800 text-stone-500"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-3 text-sm">
              <label className="flex flex-col gap-1">
                <span className="text-stone-300">Fee type</span>
                <select value={policy.fee_type} onChange={(e) => setPolicy({ ...policy, fee_type: e.target.value })}
                  className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100">
                  <option value="first_night">First night</option>
                  <option value="percent_total">% of total</option>
                  <option value="flat">Flat amount</option>
                </select>
              </label>
              {policy.fee_type === "percent_total" && (
                <label className="flex justify-between items-center"><span>Percent</span>
                  <input type="number" value={policy.fee_pct} onChange={(e) => setPolicy({ ...policy, fee_pct: parseFloat(e.target.value) || 0 })}
                    className="w-24 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-right" /></label>
              )}
              {policy.fee_type === "flat" && (
                <label className="flex justify-between items-center"><span>Amount</span>
                  <input type="number" value={policy.flat_amount} onChange={(e) => setPolicy({ ...policy, flat_amount: parseFloat(e.target.value) || 0 })}
                    className="w-24 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-right" /></label>
              )}
              <label className="flex justify-between items-center"><span>Cut-off hour</span>
                <input type="number" min={0} max={23} value={policy.grace_hour} onChange={(e) => setPolicy({ ...policy, grace_hour: parseInt(e.target.value, 10) || 0 })}
                  className="w-24 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-right" /></label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={!!policy.auto_run_enabled} onChange={(e) => setPolicy({ ...policy, auto_run_enabled: e.target.checked })} />
                <span className="text-stone-300">Auto-run scheduler</span>
              </label>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setShowPolicy(false)} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
              <button data-testid="no-show-save-policy" onClick={savePolicy}
                className="px-3 py-1.5 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200 text-sm">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
