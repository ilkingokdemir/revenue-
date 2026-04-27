/**
 * Long-Stay Discount Auto-Apply Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Save, Send, RefreshCw, Plus, Trash2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function LongStayPanel({ propertyId, hotelName = "" }) {
  const [cfg, setCfg] = useState(null);
  const [log, setLog] = useState({ items: [], discounts_total: 0, nights_total: 0, count: 0 });
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: c }, { data: l }] = await Promise.all([
        axios.get(`${API}/long-stay/${propertyId}/config`),
        axios.get(`${API}/long-stay/${propertyId}/log?days=90`),
      ]);
      setCfg(c); setLog(l);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const updateTier = (i, field, val) => {
    const ladder = [...cfg.ladder];
    ladder[i] = { ...ladder[i], [field]: parseFloat(val) || 0 };
    setCfg({ ...cfg, ladder });
  };
  const addTier = () => setCfg({ ...cfg, ladder: [...cfg.ladder, { min_nights: 35, discount_pct: 30 }] });
  const rmTier = (i) => setCfg({ ...cfg, ladder: cfg.ladder.filter((_, j) => j !== i) });

  const save = async () => {
    try {
      await axios.post(`${API}/long-stay/config`, { property_id: propertyId, ...cfg });
      toast.success("Saved"); refresh();
    } catch { toast.error("Failed"); }
  };

  const sweep = async () => {
    try {
      const { data } = await axios.post(`${API}/long-stay/sweep`, { property_id: propertyId });
      toast.success(`Applied to ${data.applied} bookings (${data.scanned} scanned)`);
      refresh();
    } catch { toast.error("Sweep failed"); }
  };

  return (
    <div className="space-y-6" data-testid="long-stay-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Long-Stay Discount</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Auto-apply tiered discounts to long bookings (e.g. 7n=10%, 14n=15%, 28n=25%).</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Stat label="Applied (90d)" value={log.count} />
        <Stat label="Total nights discounted" value={log.nights_total} />
        <Stat label="Total discounts" value={`£${log.discounts_total}`} highlight />
      </div>

      {cfg && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2">
          <div className="text-xs uppercase tracking-wider text-stone-400 flex items-center justify-between">
            <span>Tier ladder</span>
            <label className="flex items-center gap-1 text-xs text-stone-300"><input type="checkbox" checked={!!cfg.enabled} onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} /> Enabled</label>
          </div>
          {cfg.ladder.map((t, i) => (
            <div key={i} className="flex items-center gap-2" data-testid="lst-tier-row">
              <span className="text-xs text-stone-500 w-20">≥ nights</span>
              <input type="number" min={2} value={t.min_nights} onChange={(e) => updateTier(i, "min_nights", e.target.value)} className="w-24 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" />
              <span className="text-xs text-stone-500 ml-2">→ discount %</span>
              <input type="number" min={0} max={50} value={t.discount_pct} onChange={(e) => updateTier(i, "discount_pct", e.target.value)} className="w-24 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" />
              <button onClick={() => rmTier(i)} className="ml-auto text-xs px-2 py-1 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200"><Trash2 className="w-3 h-3" /></button>
            </div>
          ))}
          <button onClick={addTier} className="text-xs px-3 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1"><Plus className="w-3 h-3" /> Add tier</button>
          <div className="flex gap-2">
            <button data-testid="lst-save-btn" onClick={save} className="text-sm px-3 py-1 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 flex items-center gap-2"><Save className="w-3 h-3" /> Save ladder</button>
            <button data-testid="lst-sweep-btn" onClick={sweep} className="text-sm px-3 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2"><Send className="w-3 h-3" /> Apply now</button>
            <button onClick={refresh} className="text-sm px-3 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2 ml-auto">{loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} Refresh</button>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr><th className="px-3 py-2">Applied</th><th className="px-3 py-2">Guest</th><th className="px-3 py-2 text-right">Nights</th><th className="px-3 py-2 text-right">% off</th><th className="px-3 py-2 text-right">Discount £</th></tr>
          </thead>
          <tbody>
            {log.items.map((r) => (
              <tr key={r.id} className="border-t border-stone-800/60 text-stone-200" data-testid="lst-log-row">
                <td className="px-3 py-2 text-xs text-stone-400">{(r.applied_at || "").slice(0, 16)}</td>
                <td className="px-3 py-2">{r.guest_name}</td>
                <td className="px-3 py-2 text-right">{r.nights}</td>
                <td className="px-3 py-2 text-right">{r.discount_pct}%</td>
                <td className="px-3 py-2 text-right text-emerald-300">£{r.discount_amount}</td>
              </tr>
            ))}
            {log.items.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-stone-500">No long-stay discounts applied yet.</td></tr>}
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
