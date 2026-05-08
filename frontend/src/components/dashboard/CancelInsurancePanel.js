/**
 * Cancellation Insurance Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, ShieldCheck, Save, RefreshCw, Plus } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CancelInsurancePanel({ propertyId, hotelName = "" }) {
  const [cfg, setCfg] = useState(null);
  const [data, setData] = useState({ items: [], count: 0, fee_revenue: 0, claimed: 0 });
  const [loading, setLoading] = useState(false);
  const [bookingId, setBookingId] = useState("");

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: c }, { data: l }] = await Promise.all([
        axios.get(`${API}/cancel-insurance/${propertyId}/config`),
        axios.get(`${API}/cancel-insurance/${propertyId}/policies?days=90`),
      ]);
      setCfg(c); setData(l);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const save = async () => {
    try {
      await axios.post(`${API}/cancel-insurance/config`, { property_id: propertyId, ...cfg });
      toast.success("Saved");
    } catch { toast.error("Failed"); }
  };

  const attach = async () => {
    if (!bookingId.trim()) return toast.error("Booking ID required");
    try {
      const { data: r } = await axios.post(`${API}/cancel-insurance/attach`, { booking_id: bookingId.trim() });
      toast.success(`Policy ${r.policy.policy_ref} attached, fee ${r.policy.currency} ${r.policy.fee}`);
      setBookingId("");
      refresh();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const claim = async (booking_id) => {
    if (!window.confirm("Claim insurance? Booking will be cancelled with refund.")) return;
    try {
      const { data: r } = await axios.post(`${API}/cancel-insurance/${booking_id}/claim`, {});
      toast.success(`Claim ok · refund due ${r.refund_due}`);
      refresh();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="space-y-6" data-testid="cancel-insurance-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Cancellation Insurance</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Optional add-on at booking — full refund if cancelled inside the policy window.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Policies (90d)" value={data.count} />
        <Stat label="Fee revenue" value={`£${data.fee_revenue}`} highlight />
        <Stat label="Claimed" value={data.claimed} />
        <Stat label="Net P&L" value={`£${(data.fee_revenue || 0) - (data.claim_loss_estimate || 0)}`} highlight />
      </div>

      {cfg && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
          <label className="flex items-center gap-2 mt-4 text-stone-300"><input type="checkbox" checked={!!cfg.enabled} onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} /> Enabled</label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Fee %</span><input type="number" value={cfg.fee_pct} onChange={(e) => setCfg({ ...cfg, fee_pct: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Min £</span><input type="number" value={cfg.fee_min} onChange={(e) => setCfg({ ...cfg, fee_min: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Max £</span><input type="number" value={cfg.fee_max} onChange={(e) => setCfg({ ...cfg, fee_max: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <button data-testid="ci-save-cfg-btn" onClick={save} className="px-2 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 mt-4 flex items-center justify-center gap-1"><Save className="w-3 h-3" /> Save</button>
        </div>
      )}

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 flex flex-wrap gap-2">
        <input data-testid="ci-booking-input" value={bookingId} onChange={(e) => setBookingId(e.target.value)} placeholder="Booking ID to attach policy to" className="flex-1 min-w-[300px] px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm font-mono" />
        <button data-testid="ci-attach-btn" onClick={attach} className="px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-sm flex items-center gap-2"><Plus className="w-4 h-4" /> Attach</button>
        <button onClick={refresh} className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 text-sm flex items-center gap-2">{loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}</button>
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr><th className="px-3 py-2">Ref</th><th className="px-3 py-2">Guest</th><th className="px-3 py-2 text-right">Fee</th><th className="px-3 py-2">Status</th><th className="px-3 py-2"></th></tr>
          </thead>
          <tbody>
            {data.items.map((p) => (
              <tr key={p.id} className="border-t border-stone-800/60 text-stone-200" data-testid="ci-policy-row">
                <td className="px-3 py-2 font-mono text-xs">{p.policy_ref}</td>
                <td className="px-3 py-2"><div>{p.guest_name}</div><div className="text-[10px] text-stone-500">{p.booking_id?.slice(0, 8)}</div></td>
                <td className="px-3 py-2 text-right">{p.currency} {p.fee}</td>
                <td className="px-3 py-2"><span className={`text-[10px] px-2 py-0.5 rounded border ${p.status === "active" ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-200" : p.status === "claimed" ? "bg-amber-500/20 border-amber-500/40 text-amber-200" : "bg-stone-800 border-stone-700 text-stone-400"}`}>{p.status}</span></td>
                <td className="px-3 py-2 text-right">{p.status === "active" && <button data-testid="ci-claim-btn" onClick={() => claim(p.booking_id)} className="text-xs px-2 py-1 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200 flex items-center gap-1 ml-auto"><ShieldCheck className="w-3 h-3" /> Claim</button>}</td>
              </tr>
            ))}
            {data.items.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-stone-500">No policies sold yet.</td></tr>}
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
