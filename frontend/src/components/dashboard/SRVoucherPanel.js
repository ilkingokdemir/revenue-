/**
 * Service Recovery Auto-Voucher Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Gift, Send, RefreshCw, Copy, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SRVoucherPanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState({ items: [], count: 0, redeemed_count: 0, redeem_rate: 0 });
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ guest_email: "", guest_name: "", score: 3, percent_off: 15, max_amount_off: 100, valid_days: 180 });

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const params = filter ? `?redeemed=${filter}` : "";
      const { data } = await axios.get(`${API}/service-recovery/${propertyId}/vouchers${params}`);
      setData(data);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId, filter]);

  useEffect(() => { refresh(); }, [refresh]);

  const issue = async () => {
    try {
      await axios.post(`${API}/service-recovery/voucher`, { property_id: propertyId, ...form });
      toast.success("Voucher issued");
      setAdding(false);
      refresh();
    } catch { toast.error("Failed"); }
  };

  const sweep = async () => {
    try {
      const { data } = await axios.post(`${API}/service-recovery/sweep`, { property_id: propertyId });
      toast.success(`Issued ${data.issued} vouchers from ${data.scanned} open tickets`);
      refresh();
    } catch { toast.error("Sweep failed"); }
  };

  const copy = (code) => { navigator.clipboard.writeText(code); toast.success(`Copied ${code}`); };

  return (
    <div className="space-y-6" data-testid="sr-voucher-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Service Recovery Vouchers</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Auto-issue apology coupons to low-rated guests — close the loop before a bad review hits.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Issued" value={data.count} />
        <Stat label="Redeemed" value={data.redeemed_count} highlight />
        <Stat label="Redeem rate" value={`${data.redeem_rate}%`} highlight={data.redeem_rate >= 30} />
        <Stat label="Outstanding" value={data.count - data.redeemed_count} />
      </div>

      <div className="flex flex-wrap gap-2">
        <button data-testid="sr-sweep-btn" onClick={sweep} className="text-sm px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2">
          <Send className="w-4 h-4" /> Auto-issue from open tickets
        </button>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
          <option value="">All</option><option value="no">Outstanding</option><option value="yes">Redeemed</option>
        </select>
        <button onClick={refresh} className="text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh
        </button>
        <button data-testid="sr-add-btn" onClick={() => setAdding(true)} className="ml-auto text-sm px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 flex items-center gap-2">
          <Gift className="w-4 h-4" /> Manual issue
        </button>
      </div>

      {adding && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
          <input data-testid="sr-form-email" placeholder="Guest email" value={form.guest_email} onChange={(e) => setForm({ ...form, guest_email: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 col-span-2" />
          <input placeholder="Guest name" value={form.guest_name} onChange={(e) => setForm({ ...form, guest_name: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input type="number" min={1} max={5} placeholder="Score" value={form.score} onChange={(e) => setForm({ ...form, score: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input type="number" placeholder="% off" value={form.percent_off} onChange={(e) => setForm({ ...form, percent_off: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input type="number" placeholder="Max £" value={form.max_amount_off} onChange={(e) => setForm({ ...form, max_amount_off: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <button data-testid="sr-issue-btn" onClick={issue} className="col-span-2 md:col-span-3 px-2 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200">Issue voucher</button>
        </div>
      )}

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr><th className="px-3 py-2">Code</th><th className="px-3 py-2">Guest</th><th className="px-3 py-2">Score</th><th className="px-3 py-2 text-right">% off</th><th className="px-3 py-2 text-right">Max</th><th className="px-3 py-2">Valid until</th><th className="px-3 py-2">Status</th></tr>
          </thead>
          <tbody>
            {data.items.map((v) => (
              <tr key={v.id} className="border-t border-stone-800/60 text-stone-200" data-testid="sr-voucher-row">
                <td className="px-3 py-2 font-mono text-xs"><button onClick={() => copy(v.code)} className="flex items-center gap-1 hover:text-cyan-300">{v.code} <Copy className="w-3 h-3 opacity-50" /></button></td>
                <td className="px-3 py-2"><div>{v.guest_name || "—"}</div><div className="text-[10px] text-stone-500">{v.guest_email}</div></td>
                <td className="px-3 py-2 text-xs">{v.source_score}/5</td>
                <td className="px-3 py-2 text-right">{v.percent_off}%</td>
                <td className="px-3 py-2 text-right">{v.currency} {v.max_amount_off}</td>
                <td className="px-3 py-2 text-xs text-stone-400">{(v.valid_until || "").slice(0, 10)}</td>
                <td className="px-3 py-2">{v.redeemed ? <span className="text-[10px] px-2 py-0.5 rounded border bg-emerald-500/20 border-emerald-500/40 text-emerald-200 flex items-center gap-1 w-fit"><CheckCircle2 className="w-3 h-3" /> redeemed</span> : <span className="text-[10px] px-2 py-0.5 rounded border bg-stone-800 border-stone-700 text-stone-300">open</span>}</td>
              </tr>
            ))}
            {data.items.length === 0 && <tr><td colSpan={7} className="px-3 py-6 text-center text-stone-500">No vouchers issued.</td></tr>}
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
